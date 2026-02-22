import asyncio
import math
import os
import sys
from functools import lru_cache
from typing import Any, List, Optional

from fastapi import WebSocket

from .logger import logger
from .models import (
    ClipInfo,
    DeviceData,
    Note,
    ParameterData,
    ProjectIndex,
    SongContext,
    TrackData,
    TrackDeviceSummary,
)

# Add AbletonOSC to Python path
# TODO: better way of doing this
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "AbletonOSC"))
from AbletonOSC.client.client import AsyncAbletonOSCClient

# Unit conversion helpers


def volume_to_db(value: float) -> str:
    """Convert 0-1 volume to dB string.

    Args:
        value: Volume value from 0 to 1

    Returns:
        dB string, e.g., "-6.0 dB" or "-inf dB" for 0
    """
    if value <= 0:
        return "-inf dB"
    db = 20 * math.log10(value)
    return f"{db:.1f} dB"


def pan_to_string(value: float) -> str:
    """Convert -1 to 1 panning to string.

    Args:
        value: Pan value from -1 (full left) to 1 (full right)

    Returns:
        Pan string, e.g., "C", "L50", "R100"
    """
    if value == 0:
        return "C"
    percentage = round(abs(value) * 100)
    if value < 0:
        return f"L{percentage}"
    return f"R{percentage}"


def pitch_to_note_name(pitch: int) -> str:
    """Convert MIDI pitch (0-127) to note name.

    Args:
        pitch: MIDI pitch value (0-127)

    Returns:
        Note name with octave, e.g., "C4", "A4", "C#3"
    """
    notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    note = notes[pitch % 12]
    octave = pitch // 12 - 1
    return f"{note}{octave}"


def beats_to_bars(beats: float, time_sig_numerator: int = 4) -> float:
    """Convert beats to bars.

    Args:
        beats: Number of beats
        time_sig_numerator: Beats per bar (default 4 for 4/4 time)

    Returns:
        Number of bars as float
    """
    return beats / time_sig_numerator


def format_bar_length(beats: float, time_sig_numerator: int = 4) -> str:
    """Format length as bars string.

    Args:
        beats: Number of beats
        time_sig_numerator: Beats per bar (default 4 for 4/4 time)

    Returns:
        Formatted string, e.g., "4 bars", "1 bar", "1.5 bars"
    """
    bars = beats_to_bars(beats, time_sig_numerator)
    if bars == 1:
        return "1 bar"
    # Format as integer if whole number, otherwise keep decimal
    if bars == int(bars):
        return f"{int(bars)} bars"
    return f"{bars} bars"


def format_device_summary(track_data: TrackDeviceSummary) -> str:
    """Format track devices as compact summary for LLM."""
    return (
        f"Track: {track_data.name}\nDevices: {', '.join(track_data.devices) or 'None'}"
    )


def format_device_params(
    device_name: str, track_name: str, params: list[ParameterData]
) -> str:
    """Format device parameters as compact key=value string for LLM."""
    param_strs = [f"{p.name}={p.value_string}" for p in params if p.value_string]
    return f"{device_name} on {track_name}:\n  {', '.join(param_strs)}"


class AbletonClient:
    def __init__(self, hostname="127.0.0.1", port=11000, client_port=11001):
        logger.info(f"[ABLETON] Initializing AbletonClient on {hostname}:{port}")
        self.client = AsyncAbletonOSCClient(hostname, port, client_port)
        self.websocket: Optional[WebSocket] = None

    async def start(self) -> None:
        """Start the asyncio UDP listener. Must be called once before any queries."""
        await self.client.start()
        self.client.set_handler("/live/error", self._on_osc_error)

    def _on_osc_error(self, address: str, *args) -> None:
        """Log errors returned by AbletonOSC (e.g. index out of bounds)."""
        if len(args) == 1 and isinstance(args[0], tuple):
            args = args[0]
        logger.error(f"[ABLETON] OSC error from Live: {args}")

    async def query_with_retry(
        self, path: str, args: List = [], max_retries: int = 3
    ) -> Any:
        """Query Ableton Live with retry logic"""
        await self.start()
        for attempt in range(max_retries):
            try:
                return await self.client.query(path, args, timeout=5.0)
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

    async def get_num_sends(self, track_id: int, max_sends: int = 12) -> int:
        """Get the number of sends for a track by probing.

        AbletonOSC doesn't have a num_sends endpoint, so we probe by
        trying to query sends until we get an error.
        """
        for i in range(max_sends):
            try:
                self.client.query("/live/track/get/send", [track_id, i], timeout=1.0)
            except Exception:
                return i
        return max_sends

    async def get_track_name(self, track_id: int) -> str:
        """Get track name by ID."""
        result = await self.query_with_retry(
            "/live/song/get/track_data", [track_id, track_id + 1, "track.name"]
        )
        return result[0] if result else f"Track {track_id}"

    async def get_device_name(self, track_id: int, device_id: int) -> str:
        """Get device name by track and device ID."""
        result = await self.query_with_retry(
            "/live/device/get/name", [track_id, device_id]
        )
        return result[-1] if result else f"Device {device_id}"

    async def _get_value_strings(
        self, track_id: int, device_id: int, param_count: int
    ) -> List[str]:
        """Fetch value_string for all parameters in parallel."""
        tasks = [
            self.query_with_retry(
                "/live/device/get/parameter/value_string", [track_id, device_id, idx]
            )
            for idx in range(param_count)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [
            r[-1] if isinstance(r, (list, tuple)) and len(r) > 0 else "?"
            for r in results
        ]

    async def _index_single_track(self, track_index: int, track_name: str) -> TrackData:
        """Index a single track's devices and parameters."""
        track_num_devices = (
            await self.query_with_retry("/live/track/get/num_devices", [track_index])
        )[1]

        devices: list[DeviceData] = []

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
                params = await self.get_parameters(
                    track_index, device_index, include_value_string=True
                )
                device = DeviceData(
                    id=device_index,
                    name=device_name,
                    class_name=device_classes[device_index + 1],
                    parameters=params,
                )
                devices.append(device)
                logger.info(f"[ABLETON] device_data: {device}")
        else:
            logger.debug(f"[ABLETON] Track {track_name} has no devices")

        return TrackData(id=track_index, name=track_name, devices=devices)

    async def index_project(self) -> ProjectIndex:
        """Query Ableton for all tracks, devices, and parameters."""
        logger.info("[ABLETON] Starting project indexing")
        await self._send_progress(0)

        song_context = await self.get_song_context()
        logger.info(f"[ABLETON] Song context: {song_context}")
        await self._send_progress(5)

        num_tracks = song_context.num_tracks
        logger.info(f"[ABLETON] Found {num_tracks} tracks")
        await self._send_progress(10)

        track_names = await self.query_with_retry(
            "/live/song/get/track_data", [0, num_tracks, "track.name"]
        )
        await self._send_progress(20)

        tracks: list[TrackData] = []
        for i in range(0, len(track_names), 5):
            chunk = track_names[i : i + 5]
            tasks = [
                self._index_single_track(i + j, track_name)
                for j, track_name in enumerate(chunk)
            ]
            chunk_results = await asyncio.gather(*tasks)
            tracks.extend(chunk_results)

        await self._send_progress(90)
        logger.info("[ABLETON] Completed project indexing")
        return ProjectIndex(song_context=song_context, tracks=tracks)

    # TODO: websocket transport should not be exposed here
    # we should instead send this event and let another layer handle the transport
    async def _send_progress(self, progress: int):
        if self.websocket:
            await self.websocket.send_json(
                {
                    "type": "indexing_status",
                    "content": {"isIndexing": True, "progress": progress},
                }
            )
            await asyncio.sleep(0)
            logger.info(f"[ABLETON] Progress update: {progress}%")

    async def get_track_devices(self, track_id: int) -> str:
        """Get summary of devices on a track (compact format for LLM consumption)."""
        logger.info(f"[ABLETON] get_track_devices() args: track_id={track_id}")

        track_name = await self.get_track_name(track_id)

        track_num_devices = (
            await self.query_with_retry("/live/track/get/num_devices", [track_id])
        )[1]

        device_names: list[str] = []
        if track_num_devices > 0:
            result = await self.query_with_retry(
                "/live/track/get/devices/name", [track_id]
            )
            device_names = list(result[1:])

        track_data = TrackDeviceSummary(name=track_name, devices=device_names)
        return format_device_summary(track_data)

    async def get_parameters(
        self, track_id: int, device_id: int, include_value_string: bool = False
    ) -> list[ParameterData]:
        logger.info(
            f"[ABLETON] get_parameters() args: track_id={track_id}, device_id={device_id}, include_value_string={include_value_string}"
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

        # unfortunately there is no direct value_strings query
        # that will return all value strings, like there is values
        num_parameters = await self.query_with_retry(
            "/live/device/get/num_parameters", [track_id, device_id]
        )
        param_count = int(num_parameters[2])
        value_strings: List[str] = [""] * param_count
        if include_value_string:
            value_strings = await self._get_value_strings(
                track_id, device_id, param_count
            )

        return [
            ParameterData(
                id=idx,
                name=names[idx + 2],
                value=float(values[idx + 2]),
                min=float(mins[idx + 2]),
                max=float(maxes[idx + 2]),
                value_string=value_strings[idx] or None,
            )
            for idx in range(param_count)
        ]

    async def set_parameter(
        self, track_id: int, device_id: int, param_id: int, value: float
    ) -> str:
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

        return final_value

    async def is_live(self) -> bool:
        try:
            await self.query_with_retry("/live/test")
            logger.info("[ABLETON] Successfully connected to Ableton Live")
            return True
        except RuntimeError:
            logger.error("[ABLETON] Failed to connect to Ableton Live")
            return False

    def set_websocket(self, websocket: WebSocket):
        """Set the websocket for sending updates"""
        self.websocket = websocket
        logger.info("[ABLETON] WebSocket connection established")

    def unset_websocket(self):
        """Remove the websocket reference"""
        self.websocket = None
        logger.info("[ABLETON] WebSocket connection removed")

    # Listener methods for real-time sync

    def start_parameter_listener(
        self, track_id: int, device_id: int, param_id: int
    ) -> None:
        """Start listening to a specific parameter for value changes."""
        self.client.send_message(
            "/live/device/start_listen/parameter/value",
            [track_id, device_id, param_id],
        )

    def stop_parameter_listener(
        self, track_id: int, device_id: int, param_id: int
    ) -> None:
        """Stop listening to a specific parameter."""
        self.client.send_message(
            "/live/device/stop_listen/parameter/value",
            [track_id, device_id, param_id],
        )

    def set_parameter_change_handler(self, handler) -> None:
        """Register handler for incoming parameter value changes.

        Handler signature: handler(address: str, *args)
        Only value (float) updates trigger DB writes; value_string push events are ignored.
        """
        self.client.set_handler("/live/device/get/parameter/value", handler)

    async def get_song_context(self) -> SongContext:
        """Get high-level song context information."""
        logger.info("[ABLETON] get_song_context()")

        tempo_result = await self.query_with_retry("/live/song/get/tempo")
        numerator_result = await self.query_with_retry(
            "/live/song/get/signature_numerator"
        )
        denominator_result = await self.query_with_retry(
            "/live/song/get/signature_denominator"
        )
        num_tracks_result = await self.query_with_retry("/live/song/get/num_tracks")

        return SongContext(
            tempo=float(tempo_result[0]),
            time_sig_numerator=int(numerator_result[0]),
            time_sig_denominator=int(denominator_result[0]),
            num_tracks=int(num_tracks_result[0]),
        )

    async def get_clip_info(self, track_id: int, clip_id: int) -> ClipInfo | None:
        """Get info for a specific clip.

        Returns:
            ClipInfo or None if clip doesn't exist.
        """
        logger.info(
            f"[ABLETON] get_clip_info() args: track_id={track_id}, clip_id={clip_id}"
        )

        try:
            name_result = await self.query_with_retry(
                "/live/clip/get/name", [track_id, clip_id]
            )
            length_result = await self.query_with_retry(
                "/live/clip/get/length", [track_id, clip_id]
            )
            is_midi_result = await self.query_with_retry(
                "/live/clip/get/is_midi_clip", [track_id, clip_id]
            )
            gain_result = await self.query_with_retry(
                "/live/clip/get/gain", [track_id, clip_id]
            )
            loop_start_result = await self.query_with_retry(
                "/live/clip/get/loop_start", [track_id, clip_id]
            )
            loop_end_result = await self.query_with_retry(
                "/live/clip/get/loop_end", [track_id, clip_id]
            )

            # Result format: [track_id, clip_id, value]
            return ClipInfo(
                clip_id=clip_id,
                name=str(name_result[2]),
                length_beats=float(length_result[2]),
                is_midi=bool(is_midi_result[2]),
                gain=float(gain_result[2]),
                loop_start=float(loop_start_result[2]),
                loop_end=float(loop_end_result[2]),
            )
        except Exception as e:
            logger.warning(
                f"[ABLETON] Failed to get clip {clip_id} on track {track_id}: {e}"
            )
            return None

    async def get_clip_notes(self, track_id: int, clip_id: int) -> list[Note]:
        """Get MIDI notes from a clip.

        OSC endpoint: /live/clip/get/notes [track_id, clip_id]
        Returns: [track_id, clip_id, pitch, start_time, duration, velocity, mute, ...]
        """
        logger.info(
            f"[ABLETON] get_clip_notes() args: track_id={track_id}, clip_id={clip_id}"
        )

        notes_result = await self.query_with_retry(
            "/live/clip/get/notes", [track_id, clip_id]
        )

        note_data = notes_result[2:] if len(notes_result) > 2 else []

        notes: list[Note] = []
        i = 0
        while i + 5 <= len(note_data):
            notes.append(
                Note(
                    pitch=int(note_data[i]),
                    start_time=float(note_data[i + 1]),
                    duration=float(note_data[i + 2]),
                    velocity=int(note_data[i + 3]),
                    mute=bool(note_data[i + 4]),
                )
            )
            i += 5

        return notes


@lru_cache()
def get_ableton_client() -> AbletonClient:
    logger.info("[ABLETON] Creating new AbletonClient instance")
    return AbletonClient()
