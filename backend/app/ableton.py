import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional

from fastapi import WebSocket

from .logger import logger

# Add AbletonOSC to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "AbletonOSC"))
from AbletonOSC.client.client import AbletonOSCClient


@dataclass
class ParameterInfo:
    id: int
    name: str
    value: float
    min: float
    max: float


@dataclass
class DeviceInfo:
    id: int
    name: str
    class_name: str
    parameters: List[ParameterInfo] = field(default_factory=list)


@dataclass
class TrackInfo:
    id: int
    name: str
    devices: List[DeviceInfo] = field(default_factory=list)


@dataclass
class RuntimeParamState:
    """Runtime state for parameter change tracking (not persisted)."""

    value: float
    is_initial_value: bool = True
    debounce_timer: Optional[asyncio.TimerHandle] = None


class AbletonClient:
    def __init__(self, hostname="127.0.0.1", port=11000, client_port=11001):
        logger.info(f"[ABLETON] Initializing AbletonClient on {hostname}:{port}")
        self.client = AbletonOSCClient(hostname, port, client_port)
        self.websocket: Optional[WebSocket] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        # Runtime state for tracking parameter changes (not persisted)
        self._param_state: Dict[str, RuntimeParamState] = {}
        # Cache of project structure for param change lookups
        self._project_cache: Optional[List[dict]] = None

    def _get_param_key(self, track_id: int, device_id: int, param_id: int) -> str:
        return f"{track_id}-{device_id}-{param_id}"

    async def query_with_retry(
        self, path: str, args: List = [], max_retries: int = 3
    ) -> Any:
        """Query Ableton Live with retry logic"""
        for attempt in range(max_retries):
            try:
                return self.client.query(path, args, timeout=5.0)  # type: ignore
            except Exception as e:
                wait_time = (2**attempt) * 0.5  # 0.5s, 1s, 2s
                logger.warning(
                    f"[ABLETON] Failed to query {path} (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                if attempt < max_retries - 1:
                    logger.info(f"[ABLETON] Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"[ABLETON] Max retries reached for {path}, giving up")
                    raise

    async def _index_single_track(
        self, track_index: int, track_name: str
    ) -> dict:
        """Index a single track's devices and parameters."""
        track_num_devices = (
            await self.query_with_retry("/live/track/get/num_devices", [track_index])
        )[1]

        track_data = {
            "id": track_index,
            "name": track_name,
            "devices": [],
        }

        if track_num_devices > 0:
            device_names = await self.query_with_retry(
                "/live/track/get/devices/name", [track_index]
            )
            device_classes = await self.query_with_retry(
                "/live/track/get/devices/class_name", [track_index]
            )

            logger.info(
                f"[ABLETON] Track '{track_name}' has {track_num_devices} devices"
            )

            for device_index, device_name in enumerate(device_names[1:]):
                device_data = {
                    "id": device_index,
                    "name": device_name,
                    "class_name": device_classes[device_index + 1],
                    "parameters": [],
                }

                # Get parameters for this device
                params = await self.get_parameters(track_index, device_index)
                device_data["parameters"] = [
                    {
                        "id": p.id,
                        "name": p.name,
                        "value": p.value,
                        "min": p.min,
                        "max": p.max,
                    }
                    for p in params
                ]

                track_data["devices"].append(device_data)
        else:
            logger.debug(f"[ABLETON] Track {track_name} has no devices")

        return track_data

    async def index_project(self) -> List[dict]:
        """Query Ableton for all tracks, devices, and parameters.

        Returns a list of track dicts suitable for saving to DB.
        """
        logger.info("[ABLETON] Starting project indexing")
        await self._send_progress(0)

        num_tracks = (await self.query_with_retry("/live/song/get/num_tracks"))[0]
        logger.info(f"[ABLETON] Found {num_tracks} tracks")
        await self._send_progress(10)

        track_names = await self.query_with_retry(
            "/live/song/get/track_data", [0, num_tracks, "track.name"]
        )
        await self._send_progress(20)

        # Index all tracks in parallel
        tasks = [
            self._index_single_track(track_index, track_name)
            for track_index, track_name in enumerate(track_names)
        ]
        tracks_data = await asyncio.gather(*tasks)

        await self._send_progress(90)
        logger.info("[ABLETON] Completed project indexing")
        return list(tracks_data)

    async def subscribe_to_parameters(self, project_data: List[dict]) -> None:
        """Subscribe to parameter changes using project data from DB.

        Args:
            project_data: List of track dicts with devices and parameters
        """
        logger.info("[ABLETON] Starting parameter subscription process")

        # Cache project data for lookups during change events
        self._project_cache = project_data
        self._param_state.clear()

        def on_parameter_change(address: str, params: tuple):
            track_id, device_id, param_id, value = params
            param_key = self._get_param_key(track_id, device_id, param_id)

            state = self._param_state.get(param_key)
            if not state:
                logger.warning(f"[ABLETON] Unknown parameter: {param_key}")
                return

            # Skip initial value notification
            if state.is_initial_value:
                state.is_initial_value = False
                return

            if state.value == value:
                return

            # Cancel existing timer if any
            if state.debounce_timer:
                state.debounce_timer.cancel()

            # Look up names from cache
            track_data = next(
                (t for t in self._project_cache or [] if t["id"] == track_id), None
            )
            if not track_data:
                return

            device_data = next(
                (d for d in track_data["devices"] if d["id"] == device_id), None
            )
            if not device_data:
                return

            param_data = next(
                (p for p in device_data["parameters"] if p["id"] == param_id), None
            )
            if not param_data:
                return

            old_value = state.value

            async def send_change():
                logger.info(
                    f"[ABLETON] Parameter change: {track_data['name']}/{device_data['name']}/{param_data['name']}: {old_value:.2f} -> {value:.2f}"
                )

                if self.websocket:
                    await self.websocket.send_json(
                        {
                            "type": "parameter_change",
                            "content": {
                                "trackId": track_id,
                                "trackName": track_data["name"],
                                "deviceId": device_id,
                                "deviceName": device_data["name"],
                                "paramId": param_id,
                                "paramName": param_data["name"],
                                "oldValue": old_value,
                                "newValue": value,
                                "min": param_data["min"],
                                "max": param_data["max"],
                                "timestamp": time.time() * 1000,
                            },
                        }
                    )
                    await asyncio.sleep(0)

                state.value = value
                state.debounce_timer = None

            # Set new timer
            if self.event_loop:
                state.debounce_timer = self.event_loop.call_later(
                    0.5, lambda: asyncio.create_task(send_change())
                )

        # Register the handler
        self.client.set_handler("/live/device/get/parameter/value", on_parameter_change)
        logger.info("[ABLETON] Registered parameter change handler")

        # Subscribe to all parameters
        total_params = 0

        for track_data in project_data:
            track_id = track_data["id"]

            for device_data in track_data["devices"]:
                device_id = device_data["id"]
                logger.info(
                    f"[ABLETON] Subscribing to {track_data['name']}/{device_data['name']}"
                )

                for param_data in device_data["parameters"]:
                    param_id = param_data["id"]
                    param_key = self._get_param_key(track_id, device_id, param_id)

                    # Initialize runtime state
                    self._param_state[param_key] = RuntimeParamState(
                        value=param_data["value"],
                        is_initial_value=True,
                    )

                    self.client.send_message(
                        "/live/device/start_listen/parameter/value",
                        [track_id, device_id, param_id],
                    )
                    total_params += 1

        logger.info(f"[ABLETON] Subscribed to {total_params} parameters")

    async def _send_progress(self, progress: int):
        if self.websocket:
            await self.websocket.send_json(
                {"type": "loading_progress", "content": progress}
            )
            await asyncio.sleep(0)
            logger.info(f"[ABLETON] Progress update: {progress}%")

    async def get_parameters(
        self, track_id: int, device_id: int
    ) -> List[ParameterInfo]:
        logger.debug(
            f"[ABLETON] get_parameters() args: track_id={track_id}, device_id={device_id}"
        )

        names = await self.query_with_retry(
            "/live/device/get/parameters/name", [track_id, device_id]
        )
        values = await self.query_with_retry(
            "/live/device/get/parameters/value", [track_id, device_id]
        )
        mins = await self.query_with_retry(
            "/live/device/get/parameters/min", [track_id, device_id]
        )
        maxes = await self.query_with_retry(
            "/live/device/get/parameters/max", [track_id, device_id]
        )

        return [
            ParameterInfo(
                id=idx,
                name=names[idx + 2],
                value=float(values[idx + 2]),
                min=float(mins[idx + 2]),
                max=float(maxes[idx + 2]),
            )
            for idx in range(len(names[2:]))
        ]

    async def set_parameter(
        self, track_id: int, device_id: int, param_id: int, value: float
    ):
        logger.info(
            f"[ABLETON] set_parameters() args: track_id={track_id}, device_id={device_id}, param_id={param_id}, value={value}"
        )
        # Get device and parameter names
        device_name = await self.query_with_retry(
            "/live/device/get/name", [track_id, device_id]
        )
        param_names = await self.query_with_retry(
            "/live/device/get/parameters/name", [track_id, device_id]
        )
        param_name = param_names[param_id]

        logger.info(
            f"[ABLETON] Setting parameter {device_name}/{param_name} to {value}"
        )

        # Get original parameter value string
        original_value = await self.query_with_retry(
            "/live/device/get/parameter/value_string", [track_id, device_id, param_id]
        )

        # Set the new value
        self.client.send_message(
            "/live/device/set/parameter/value", [track_id, device_id, param_id, value]
        )

        # Get final parameter value string
        final_value = await self.query_with_retry(
            "/live/device/get/parameter/value_string", [track_id, device_id, param_id]
        )

        logger.info(
            f"[ABLETON] Parameter {device_name}/{param_name} changed from {original_value} to {final_value}"
        )

        return {
            "device": device_name,
            "param": param_name,
            "from": original_value,
            "to": final_value,
        }

    def unsubscribe_all(self) -> None:
        """Unsubscribe from all parameter changes."""
        logger.info("[ABLETON] Unsubscribing from all parameters")

        total_params = 0
        for param_key in self._param_state:
            parts = param_key.split("-")
            track_id, device_id, param_id = int(parts[0]), int(parts[1]), int(parts[2])
            self.client.send_message(
                "/live/device/stop_listen/parameter/value",
                [track_id, device_id, param_id],
            )
            total_params += 1

        self._param_state.clear()
        self._project_cache = None
        logger.info(f"[ABLETON] Unsubscribed from {total_params} parameters")

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
        logger.info("[ABLETON] WebSocket connection removed")


@lru_cache()
def get_ableton_client() -> AbletonClient:
    logger.info("[ABLETON] Creating new AbletonClient instance")
    return AbletonClient()
