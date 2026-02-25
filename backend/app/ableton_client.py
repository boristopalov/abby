"""Async TCP client for Our Remote MIDI Script (replaces the OSC-based AbletonClient in ableton.py)."""

import asyncio
import json
import uuid
from collections.abc import Coroutine
from functools import lru_cache
from typing import Any, Callable

from .logger import logger
from .models import (
    ClipInfo,
    DeviceData,
    Note,
    ParameterData,
    ProjectIndex,
    SongContext,
    TrackData,
    TrackDevices,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9877


# ---------------------------------------------------------------------------
# Low-level transport
# ---------------------------------------------------------------------------


class _AbletonConnection:
    """Persistent async TCP connection to Our Remote MIDI Script.

    Maintains a background read loop that routes responses to their waiting
    futures by request ID.  Messages without an ``id`` field are push events
    and are forwarded to the registered event handler.

    Invariant: ``_reader`` and ``_writer`` are both ``None`` or both set.
    The lock serialises reconnection attempts; individual commands can be sent
    concurrently once connected because each has its own future keyed by
    request ID.
    """

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._event_handler: (
            Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None
        ) = None
        self._connect_lock = asyncio.Lock()
        self._read_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        async with self._connect_lock:
            if self._writer is not None and not self._writer.is_closing():
                return
            logger.info(
                f"[ABLETON] Connecting to Our Remote MIDI Script at {self._host}:{self._port}"
            )
            self._reader, self._writer = await asyncio.open_connection(
                self._host,
                self._port,
                limit=10 * 1024 * 1024,  # 10 MB
            )
            self._read_task = asyncio.create_task(self._read_loop())
            logger.info("[ABLETON] Connected to Our Remote MIDI Script")

    async def _read_loop(self) -> None:
        """Background task: read newline-delimited JSON and dispatch."""
        assert self._reader is not None
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                try:
                    message: dict[str, Any] = json.loads(line.decode("utf-8"))
                except ValueError:
                    logger.warning("[ABLETON] Received malformed JSON line, skipping")
                    continue

                if "id" in message:
                    # Command response — route to the waiting future.
                    future = self._pending.pop(message["id"], None)
                    if future is not None and not future.done():
                        future.set_result(message)
                else:
                    # Push event (no id) — forward to registered handler.
                    if self._event_handler is not None:
                        asyncio.create_task(self._event_handler(message))
        except Exception as exc:
            logger.error(f"[ABLETON] Read loop error: {exc}")
        finally:
            # Connection lost — fail all waiting futures.
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(
                        RuntimeError("Our Remote MIDI Script connection lost")
                    )
            self._pending.clear()
            self._writer = None
            self._reader = None
            logger.info("[ABLETON] Disconnected from Our Remote MIDI Script")

    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a command and await its response. Auto-reconnects if needed."""
        if self._writer is None or self._writer.is_closing():
            await self.connect()
        assert self._writer is not None

        request_id = str(uuid.uuid4())
        payload = {**payload, "id": request_id}

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = future

        self._writer.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self._writer.drain()
        return await future

    def set_event_handler(
        self, handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None
    ) -> None:
        self._event_handler = handler


# ---------------------------------------------------------------------------
# Command helper
# ---------------------------------------------------------------------------


async def _cmd(
    conn: _AbletonConnection,
    cmd_type: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """Send a command and return ``result``, raising ``RuntimeError`` on error."""
    resp = await conn.send({"type": cmd_type, "params": params or {}})
    if resp.get("status") == "error":
        raise RuntimeError(
            f"Our Remote MIDI Script error ({cmd_type}): {resp.get('message')}"
        )
    return resp.get("result", {})


# ---------------------------------------------------------------------------
# Public client
# ---------------------------------------------------------------------------


class AbletonClient:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self._conn = _AbletonConnection(host, port)

    async def start(self) -> None:
        """No-op: connection is lazy.  Kept for interface compatibility."""
        pass

    # --- Connectivity ---

    async def is_live(self) -> bool:
        try:
            await _cmd(self._conn, "get_session_info")
            logger.info("[ABLETON] Successfully connected to Ableton Live")
            return True
        except Exception:
            logger.error("[ABLETON] Failed to connect to Ableton Live")
            return False

    # --- Song-level ---

    async def get_song_context(self) -> SongContext:
        logger.info("[ABLETON] get_song_context()")
        r = await _cmd(self._conn, "get_session_info")
        return SongContext(
            tempo=float(r["tempo"]),
            time_sig_numerator=int(r["signature_numerator"]),
            time_sig_denominator=int(r["signature_denominator"]),
            num_tracks=int(r["track_count"]),
        )

    async def set_tempo(self, tempo: float) -> float:
        r = await _cmd(self._conn, "set_tempo", {"tempo": tempo})
        return float(r["tempo"])

    async def start_playing(self) -> None:
        await _cmd(self._conn, "start_playback")

    async def stop_playing(self) -> None:
        await _cmd(self._conn, "stop_playback")

    async def create_midi_track(self, index: int = -1) -> str:
        """Create a MIDI track at a given index, defaults to end if index not provided"""
        r = await _cmd(self._conn, "create_midi_track", {"index": index})
        return str(r["name"])

    async def create_audio_track(self) -> str:
        """Create an audio track at the end"""
        r = await _cmd(self._conn, "create_audio_track")
        return str(r["name"])

    async def delete_track(self, index: int) -> int:
        """Delete a track at the provided index"""
        r = await _cmd(self._conn, "delete_track", {"index": index})
        return int(r["index"])

    # --- Track-level ---

    async def get_track_name(self, track_index: int) -> str:
        r = await _cmd(self._conn, "get_track_devices", {"track_index": track_index})
        return str(r["track_name"])

    async def get_track_names(self, num_tracks: int) -> list[str]:
        tasks = [self.get_track_name(i) for i in range(num_tracks)]
        return list(await asyncio.gather(*tasks))

    async def get_track_devices(self, track_index: int) -> TrackDevices:
        r = await _cmd(self._conn, "get_track_devices", {"track_index": track_index})
        return TrackDevices(
            index=r["track_index"],
            name=r["track_name"],
            devices=r["devices"],
        )

    # --- Device/parameter-level ---

    async def get_device_name(self, track_index: int, device_index: int) -> str:
        r = await _cmd(
            self._conn,
            "get_device_parameters",
            {"track_index": track_index, "device_index": device_index},
        )
        return str(r["device_name"])

    async def get_device_parameters(
        self,
        track_index: int,
        device_index: int,
        include_value_string: bool = True,
    ) -> list[ParameterData]:
        logger.info(
            f"[ABLETON] get_parameters() track={track_index} device={device_index}"
        )
        r = await _cmd(
            self._conn,
            "get_device_parameters",
            {"track_index": track_index, "device_index": device_index},
        )
        return [
            ParameterData(
                id=p["index"],
                name=p["name"],
                value=float(p["value"]),
                min=float(p["min"]),
                max=float(p["max"]),
                value_string=p.get("value_string") if include_value_string else None,
            )
            for p in r["parameters"]
        ]

    async def set_parameter(
        self,
        track_index: int,
        device_index: int,
        param_index: int,
        value: float,
    ) -> str:
        logger.info(
            f"[ABLETON] set_parameter() track={track_index} device={device_index}"
            f" param={param_index} value={value}"
        )
        r = await _cmd(
            self._conn,
            "set_device_parameter",
            {
                "track_index": track_index,
                "device_index": device_index,
                "parameter_index": param_index,
                "value": value,
            },
        )
        return str(r.get("value_string", str(round(value, 4))))

    # --- Clip operations ---

    async def get_clip_info(self, track_index: int, clip_index: int) -> ClipInfo | None:
        try:
            r = await _cmd(self._conn, "get_track_info", {"track_index": track_index})
            slots: list[dict[str, Any]] = r.get("clip_slots", [])
            if clip_index >= len(slots):
                return None
            slot = slots[clip_index]
            if not slot.get("has_clip"):
                return None
            clip = slot["clip"]
            return ClipInfo(
                clip_id=clip_index,
                name=clip["name"],
                length_beats=float(clip["length"]),
                is_midi=True,
                loop_start=0.0,
                loop_end=float(clip["length"]),
                gain=1.0,
            )
        except Exception as exc:
            logger.warning(
                f"[ABLETON] Failed to get clip {clip_index} on track {track_index}: {exc}"
            )
            return None

    async def get_clip_notes(self, track_index: int, clip_index: int) -> list[Note]:
        # Our Remote MIDI Script does not yet have a get_notes command.
        raise NotImplementedError

    async def delete_clip(self, track_index: int, clip_index: int) -> bool:
        r = await _cmd(
            self._conn,
            "delete_clip",
            {"track_index": track_index, "clip_index": clip_index},
        )
        return bool(r.get("success", False))

    async def create_clip(
        self, track_index: int, clip_index: int, length: float
    ) -> ClipInfo:
        r = await _cmd(
            self._conn,
            "create_clip",
            {"track_index": track_index, "clip_index": clip_index, "length": length},
        )
        return ClipInfo(
            clip_id=clip_index,
            name=r["name"],
            length_beats=float(r["length"]),
            is_midi=True,
            loop_start=0.0,
            loop_end=float(r["length"]),
            gain=1.0,
        )

    # --- Sync/listener stubs ---

    def start_parameter_listener(
        self, track_id: int, device_id: int, param_id: int
    ) -> None:
        raise NotImplementedError

    def stop_parameter_listener(
        self, track_id: int, device_id: int, param_id: int
    ) -> None:
        raise NotImplementedError

    def set_parameter_change_handler(self, handler: Any) -> None:
        raise NotImplementedError

    # --- Batch commands ---

    async def get_project_index(self) -> ProjectIndex:
        """Return the full project structure in a single round trip."""
        r = await _cmd(self._conn, "get_project_index")
        song_context = SongContext(
            tempo=float(r["tempo"]),
            time_sig_numerator=int(r["signature_numerator"]),
            time_sig_denominator=int(r["signature_denominator"]),
            num_tracks=int(r["track_count"]),
        )
        tracks: list[TrackData] = []
        for raw_track in r.get("tracks", []):
            devices: list[DeviceData] = []
            for raw_device in raw_track.get("devices", []):
                params = [
                    ParameterData(
                        id=p["index"],
                        name=p["name"],
                        value=float(p["value"]),
                        min=float(p["min"]),
                        max=float(p["max"]),
                        value_string=p.get("value_string"),
                    )
                    for p in raw_device.get("parameters", [])
                ]
                devices.append(
                    DeviceData(
                        id=raw_device["index"],
                        name=raw_device["name"],
                        class_name=raw_device["class_name"],
                        parameters=params,
                    )
                )
            tracks.append(
                TrackData(
                    id=raw_track["index"],
                    name=raw_track["name"],
                    devices=devices,
                )
            )
        return ProjectIndex(song_context=song_context, tracks=tracks)


@lru_cache()
def get_ableton_client() -> AbletonClient:
    logger.info("[ABLETON] Creating new AbletonClient instance")
    return AbletonClient()
