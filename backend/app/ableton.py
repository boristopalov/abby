import asyncio
from functools import lru_cache
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
import time
import threading
import sys
import os
from fastapi import WebSocket
from .logger import logger

# Add AbletonOSC to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'AbletonOSC'))
from AbletonOSC.client.client import AbletonOSCClient

@dataclass
class ParameterInfo:
    id: int
    name: str
    value: float
    min: float
    max: float
    time_last_modified: float
    is_initial_value: bool = True
    debounce_timer: Optional[threading.Timer] = None

@dataclass
class DeviceInfo:
    id: int
    name: str
    class_name: str
    parameters: Dict[int, ParameterInfo]

@dataclass
class TrackInfo:
    id: int
    track_name: str
    devices: Dict[int, DeviceInfo]


@dataclass
class ParameterChange:
    track_id: int
    track_name: str
    device_id: int
    device_name: str
    param_id: int
    param_name: str
    old_value: float
    new_value: float
    min: float
    max: float
    timestamp: float

class AbletonClient:
    def __init__(self, hostname="127.0.0.1", port=11000, client_port=11001):
        logger.info(f"[ABLETON] Initializing AbletonClient on {hostname}:{port}")
        self.client = AbletonOSCClient(hostname, port, client_port)
        self.tracks_device_params: Dict[int, TrackInfo] = {}
        self.websocket: Optional[WebSocket] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        
    def _get_param_key(self, track_id: int, device_id: int, param_id: int) -> str:
        return f"{track_id}-{device_id}-{param_id}"

    async def query_with_retry(self, path: str, args: List = None, max_retries: int = 3) -> Any:
        """Query Ableton Live with retry logic"""
        for attempt in range(max_retries):
            try:
                return self.client.query(path, args, timeout=5.0)
            except Exception as e:
                wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                logger.warning(f"[ABLETON] Failed to query {path} (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"[ABLETON] Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"[ABLETON] Max retries reached for {path}, giving up")
                    raise

    async def get_tracks_devices(self, send_progress: bool = False) -> List[TrackInfo]:
        logger.info("[ABLETON] Starting track and device discovery")
        summary = []
        tracks_info = []
        
        # Get track count
        if send_progress:
            await self._send_progress(0)
            
        num_tracks = (await self.query_with_retry("/live/song/get/num_tracks"))[0]
        logger.info(f"[ABLETON] Found {num_tracks} tracks")
        
        if send_progress:
            await self._send_progress(10)
            
        # Get track data
        track_data = await self.query_with_retry("/live/song/get/track_data", [0, num_tracks, "track.name"])
        
        if send_progress:
            await self._send_progress(20)

        # Process each track
        for track_index, track_name in enumerate(track_data):
            if send_progress:
                progress_per_track = 30 / len(track_data)
                current_progress = 20 + progress_per_track * track_index
                await self._send_progress(round(current_progress))

            track_num_devices = (await self.query_with_retry("/live/track/get/num_devices", [track_index]))[1]
            track_info = {
                "id": track_index,
                "name": track_name,
                "devices": []
            }

            # Initialize track in parameter metadata
            if track_index not in self.tracks_device_params:
                self.tracks_device_params[track_index] = TrackInfo(
                    id=track_index,
                    track_name=track_name,
                    devices={}
                )

            if track_num_devices > 0:
                track_device_names = await self.query_with_retry("/live/track/get/devices/name", [track_index])
                track_device_classes = await self.query_with_retry("/live/track/get/devices/class_name", [track_index])

                logger.info(f"[ABLETON] Track '{track_name}' has {track_num_devices} devices")

                devices = [
                    DeviceInfo(
                        id=idx,
                        name=name,
                        class_name=track_device_classes[idx + 1],
                        parameters={}
                    )
                    for idx, name in enumerate(track_device_names[1:])
                ]

                # Convert devices list to dictionary for tracks_device_params
                devices_dict = {device.id: device for device in devices}
                self.tracks_device_params[track_index].devices = devices_dict

                summary.append(TrackInfo(
                    id=track_index,
                    track_name=track_name,
                    devices=devices_dict
                ))

                # Add devices to track info (for WebSocket message)
                track_info["devices"] = [
                    {
                        "id": device.id,
                        "name": device.name,
                        "className": device.class_name
                    }
                    for device in devices
                ]
            else:
                logger.debug(f"[ABLETON] Track {track_name} has no devices, skipping")

            tracks_info.append(track_info)

        if send_progress:
            await self._send_progress(50)

        # Send tracks info via WebSocket
        if self.websocket:
            await self.websocket.send_json({
                "type": "tracks",
                "content": tracks_info
            })
            await asyncio.sleep(0)

        logger.info("[ABLETON] Completed track and device discovery")
        return summary

    async def subscribe_to_device_parameters(self):
        logger.info("[ABLETON] Starting parameter subscription process")
        if self.websocket:
            await self._send_progress(0)

        def on_parameter_change(address: str, params: tuple):
            track_id, device_id, param_id, value = params
            track = self.tracks_device_params.get(track_id)

            if not track:
                logger.error(f"[ABLETON] No track found with ID {track_id}")
                return
            device = track.devices.get(device_id)
            if not device:
                logger.error(f"[ABLETON] No device found with ID {device_id}")
                return
            param = device.parameters.get(param_id)
            if not param:
                logger.error(f"[ABLETON] No parameter found with ID {param_id}")
                return

            if param.is_initial_value:
                param.is_initial_value = False
                self.tracks_device_params[track_id].devices[device_id].parameters[param_id] = param
                return

            if param.value == value:
                return

            # Cancel existing timer if any
            if param.debounce_timer:
                param.debounce_timer.cancel()

            async def send_change():
                logger.info(f"[ABLETON] Parameter change detected: {track.track_name}/{device.name}/{param.name}: {param.value:.2f} -> {value:.2f}")

                if self.websocket:
                    await self.websocket.send_json({
                        "type": "parameter_change",
                        "content": {
                            "trackId": track_id,
                            "trackName": track.track_name,
                            "deviceId": device_id,
                            "deviceName": device.name,
                            "paramId": param_id,
                            "paramName": param.name,
                            "oldValue": param.value,
                            "newValue": value,
                            "min": param.min,
                            "max": param.max,
                            "timestamp": time.time() * 100
                        }
                    })
                    await asyncio.sleep(0)

                param.value = value
                param.time_last_modified = time.time()
                device.parameters[param_id] = param
                param.debounce_timer = None
                self.tracks_device_params[track_id].devices[device_id].parameters[param_id] = param

            # Set new timer
            param.debounce_timer = self.event_loop.call_later(
                0.5,
                lambda: asyncio.create_task(send_change())
            )

        # Register the handler
        self.client.set_handler("/live/device/get/parameter/value", on_parameter_change)
        logger.info("[ABLETON] Registered parameter change handler")

        # Subscribe to all parameters
        total_params = 0
        tracks = await self.get_tracks_devices(True)  # This gets us to 50% progress
        
        # Calculate total work to be done
        total_devices = sum(len(track.devices) for track in tracks)
        
        current_track = 0
        current_device = 0
        
        for track in tracks:
            if track.id not in self.tracks_device_params:
                logger.warning(f"[ABLETON] track {track.id} not found in tracks_device_params... adding it now")
                self.tracks_device_params[track.id] = track
                
            for device_id, device in track.devices.items():
                parameters = await self.get_parameters(track.id, device.id)
                logger.info(f"[ABLETON] Subscribing to parameters for {track.track_name}/{device.name}")

                # Initialize device in parameter metadata
                if device.id not in self.tracks_device_params[track.id].devices:
                    self.tracks_device_params[track.id].devices[device_id] = device
                
                for param in parameters:
                    total_params += 1
                    self.tracks_device_params[track.id].devices[device.id].parameters[param.id] = ParameterInfo(
                        id=param.id,
                        name=param.name,
                        value=param.value,
                        min=float(param.min),
                        max=float(param.max),
                        is_initial_value=False,
                        time_last_modified=time.time()
                    )

                    self.client.send_message(
                        "/live/device/start_listen/parameter/value",
                        [track.id, device.id, param.id]
                    )
                
                current_device += 1
                # Calculate progress from 50 to 99 based on devices processed
                device_progress = int(50 + (current_device / total_devices * 49))
                await self._send_progress(device_progress)
            
            current_track += 1

        logger.info(f"[ABLETON] Successfully subscribed to {total_params} parameters across {len(tracks)} tracks")
        await self._send_progress(100)

    async def _send_progress(self, progress: int):
        if self.websocket:
            await self.websocket.send_json({
                "type": "loading_progress",
                "content": progress
            })
            await asyncio.sleep(0)
            logger.info(f"[ABLETON] Progress update: {progress}%")

    async def get_parameters(self, track_id: int, device_id: int, max_retries: int = 3) -> List[ParameterInfo]:
        logger.info(f"[ABLETON] get_parameters() args: track_id={track_id}, device_id={device_id}")
        
        names = await self.query_with_retry("/live/device/get/parameters/name", [track_id, device_id])
        values = await self.query_with_retry("/live/device/get/parameters/value", [track_id, device_id])
        mins = await self.query_with_retry("/live/device/get/parameters/min", [track_id, device_id])
        maxes = await self.query_with_retry("/live/device/get/parameters/max", [track_id, device_id])

        return [
            ParameterInfo(
                id=idx,
                name=names[idx + 2],
                value=float(values[idx + 2]),
                min=float(mins[idx + 2]),
                max=float(maxes[idx + 2]),
                time_last_modified=time.time()
            )
            for idx in range(len(names[2:]))
        ]

    async def set_parameter(self, track_id: int, device_id: int, param_id: int, value: float):
        logger.info(f"[ABLETON] set_parameters() args: track_id={track_id}, device_id={device_id}, param_id={param_id}, value={value}")
        # Get device and parameter names
        device_name = await self.query_with_retry("/live/device/get/name", [track_id, device_id])
        param_names = await self.query_with_retry("/live/device/get/parameters/name", [track_id, device_id])
        param_name = param_names[param_id]

        logger.info(f"[ABLETON] Setting parameter {device_name}/{param_name} to {value}")

        # Get original parameter value string
        original_value = await self.query_with_retry(
            "/live/device/get/parameter/value_string",
            [track_id, device_id, param_id]
        )

        # Set the new value
        self.client.send_message(
            "/live/device/set/parameter/value",
            [track_id, device_id, param_id, value]
        )

        # Get final parameter value string
        final_value = await self.query_with_retry(
            "/live/device/get/parameter/value_string",
            [track_id, device_id, param_id]
        )

        logger.info(f"[ABLETON] Parameter {device_name}/{param_name} changed from {original_value} to {final_value}")

        return {
            "device": device_name,
            "param": param_name,
            "from": original_value,
            "to": final_value
        }

    async def unsubscribe_from_device_parameters(self):
        logger.info("[ABLETON] Starting parameter unsubscription process")
        tracks = await self.get_tracks_devices()
        
        # Clear all stored metadata
        self.tracks_device_params.clear()

        # Unsubscribe from all parameters
        total_params = 0
        for track in tracks:
            for device in track.devices:
                parameters = await self.get_parameters(track.id, device.id)
                
                for param in parameters:
                    total_params += 1
                    self.client.send_message(
                        "/live/device/stop_listen/parameter/value",
                        [track.id, device.id, param.id]
                    )

        logger.info(f"[ABLETON] Successfully unsubscribed from {total_params} parameters")

    async def is_live(self) -> bool:
        try:
            await self.query_with_retry("/live/test")
            logger.info("[ABLETON] Successfully connected to Ableton Live")
            return True
        except RuntimeError:
            logger.error("[ABLETON] Failed to connect to Ableton Live")
            return False

    def set_websocket(self, websocket: WebSocket, loop: asyncio.AbstractEventLoop):
        """Set the websocket for sending updates"""
        self.websocket = websocket
        self.event_loop = loop
        logger.info("[ABLETON] WebSocket connection established")

    def unset_websocket(self):
        """Remove the websocket reference"""
        self.websocket = None
        self.event_loop = None
        logger.info("[ABLETON] WebSocket connection removed")

    def get_cached_tracks_devices(self) -> List[dict]:
        """Get tracks and devices info from cached track and device info"""
        return [
            {
                "id": track_id,
                "name": track.track_name,
                "devices": [
                    {
                        "id": device_id,
                        "name": device.name,
                        "className": device.class_name
                    }
                    for device_id, device in track.devices.items()
                ]
            }
            for track_id, track in self.tracks_device_params.items()
        ]
    
    def reset_project(self):
        self.tracks_device_params = {}


@lru_cache()
def get_ableton_client() -> AbletonClient:
    logger.info("[ABLETON] Creating new AbletonClient instance")
    return AbletonClient()