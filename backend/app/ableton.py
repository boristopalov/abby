from functools import lru_cache
from typing import Dict, Optional, List
from dataclasses import dataclass
import time
import threading
import json
import sys
import os
from fastapi import WebSocket

# Add AbletonOSC to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'AbletonOSC'))
from AbletonOSC.client.client import AbletonOSCClient

@dataclass
class ParameterData:
    track_id: int
    track_name: str
    device_id: int
    device_name: str
    param_id: int
    param_name: str
    value: float
    min: float
    max: float
    is_initial_value: bool
    time_last_modified: float
    debounce_timer: Optional[threading.Timer] = None

@dataclass
class DeviceInfo:
    id: int
    name: str
    class_name: str

@dataclass
class TrackInfo:
    id: int
    track_name: str
    devices: List[DeviceInfo]

@dataclass
class ParameterInfo:
    id: int
    name: str
    value: float
    min: float
    max: float

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
        self.client = AbletonOSCClient(hostname, port, client_port)
        self.parameter_metadata: Dict[str, ParameterData] = {}
        self.websocket: Optional[WebSocket] = None
        
    def _get_param_key(self, track_id: int, device_id: int, param_id: int) -> str:
        return f"{track_id}-{device_id}-{param_id}"

    async def get_tracks_devices(self, send_progress: bool = False) -> List[TrackInfo]:
        summary = []
        
        # Get track count
        if send_progress:
            await self._send_progress(0)
            
        num_tracks = self.client.query("/live/song/get/num_tracks")[0]
        
        if send_progress:
            await self._send_progress(10)
            
        # Get track data
        track_data = self.client.query("/live/song/get/track_data", [0, num_tracks, "track.name"])
        
        if send_progress:
            await self._send_progress(20)

        # Process each track
        for track_index, track_name in enumerate(track_data):
            if send_progress:
                progress_per_track = 30 / len(track_data)
                current_progress = 20 + progress_per_track * track_index
                await self._send_progress(round(current_progress))

            track_num_devices = self.client.query("/live/track/get/num_devices", [track_index])[1]
            
            if track_num_devices == 0:
                continue

            track_device_names = self.client.query("/live/track/get/devices/name", [track_index])
            track_device_classes = self.client.query("/live/track/get/devices/class_name", [track_index])

            devices = [
                DeviceInfo(
                    id=idx,
                    name=name,
                    class_name=track_device_classes[idx + 1]
                )
                for idx, name in enumerate(track_device_names[1:])
            ]

            summary.append(TrackInfo(
                id=track_index,
                track_name=track_name,
                devices=devices
            ))

        if send_progress:
            await self._send_progress(50)

        return summary

    async def subscribe_to_device_parameters(self):
        # First get all tracks and their devices
        if self.websocket:
            await self._send_progress(0)

        tracks = await self.get_tracks_devices(True)
        
        # Set up parameter change handler
        def on_parameter_change(address: str, params: tuple):
            track_id, device_id, param_id, value = params
            key = self._get_param_key(track_id, device_id, param_id)
            metadata = self.parameter_metadata.get(key)

            if metadata:
                if metadata.is_initial_value:
                    metadata.is_initial_value = False
                    self.parameter_metadata[key] = metadata
                    return

                if metadata.value == value:
                    return

                # Cancel existing timer if any
                if metadata.debounce_timer:
                    metadata.debounce_timer.cancel()

                async def send_change():
                    change = ParameterChange(
                        track_id=metadata.track_id,
                        track_name=metadata.track_name,
                        device_id=metadata.device_id,
                        device_name=metadata.device_name,
                        param_id=metadata.param_id,
                        param_name=metadata.param_name,
                        old_value=metadata.value,
                        new_value=value,
                        min=metadata.min,
                        max=metadata.max,
                        timestamp=time.time() * 1000
                    )

                    if self.websocket:
                        await self.websocket.send(json.dumps({
                            "type": "parameter_change",
                            "content": change.__dict__
                        }))

                    metadata.value = value
                    metadata.time_last_modified = time.time()
                    self.parameter_metadata[key] = metadata
                    metadata.debounce_timer = None

                # Set new timer
                metadata.debounce_timer = threading.Timer(0.5, send_change)
                metadata.debounce_timer.start()

        # Register the handler
        self.client.set_handler("/live/device/get/parameter/value", on_parameter_change)

        # Subscribe to all parameters
        for track in tracks:
            for device in track.devices:
                parameters = await self.get_parameters(track.id, device.id)
                
                for param in parameters:
                    key = self._get_param_key(track.id, device.id, param.id)
                    self.parameter_metadata[key] = ParameterData(
                        track_id=track.id,
                        track_name=track.track_name,
                        device_id=device.id,
                        device_name=device.name,
                        param_id=param.id,
                        param_name=param.name,
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

        if self.websocket:
            await self._send_progress(100)

    async def _send_progress(self, progress: int):
        if self.websocket:
            await self.websocket.send(json.dumps({
                "type": "loading_progress",
                "content": progress
            }))

    async def get_parameters(self, track_id: int, device_id: int) -> List[ParameterInfo]:
        names = self.client.query("/live/device/get/parameters/name", [track_id, device_id])
        values = self.client.query("/live/device/get/parameters/value", [track_id, device_id])
        mins = self.client.query("/live/device/get/parameters/min", [track_id, device_id])
        maxes = self.client.query("/live/device/get/parameters/max", [track_id, device_id])

        return [
            ParameterInfo(
                id=idx,
                name=names[idx + 2],
                value=float(values[idx + 2]),
                min=float(mins[idx + 2]),
                max=float(maxes[idx + 2])
            )
            for idx in range(len(names[2:]))
        ]

    async def set_parameter(self, track_id: int, device_id: int, param_id: int, value: float):
        # Get device and parameter names
        device_name = self.client.query("/live/device/get/name", [track_id, device_id])
        param_names = self.client.query("/live/device/get/parameters/name", [track_id, device_id])
        param_name = param_names[param_id]

        # Get original parameter value string
        original_value = self.client.query(
            "/live/device/get/parameter/value_string",
            [track_id, device_id, param_id]
        )

        # Set the new value
        self.client.send_message(
            "/live/device/set/parameter/value",
            [track_id, device_id, param_id, value]
        )

        # Get final parameter value string
        final_value = self.client.query(
            "/live/device/get/parameter/value_string",
            [track_id, device_id, param_id]
        )

        return {
            "device": device_name,
            "param": param_name,
            "from": original_value,
            "to": final_value
        }

    async def unsubscribe_from_device_parameters(self):
        tracks = await self.get_tracks_devices()
        
        # Clear all stored metadata
        self.parameter_metadata.clear()

        # Unsubscribe from all parameters
        for track in tracks:
            for device in track.devices:
                parameters = await self.get_parameters(track.id, device.id)
                
                for param in parameters:
                    self.client.send_message(
                        "/live/device/stop_listen/parameter/value",
                        [track.id, device.id, param.id]
                    )

    async def is_live(self) -> bool:
        try:
            self.client.query("/live/test", timeout=5.0)
            return True
        except RuntimeError:
            return False

    def set_websocket(self, websocket: WebSocket):
        """Set the websocket for sending updates"""
        self.websocket = websocket

    def unset_websocket(self):
        """Remove the websocket reference"""
        self.websocket = None


@lru_cache()
def get_ableton_client() -> AbletonClient:
    return AbletonClient()