"""Formatting and unit-conversion helpers for Ableton data."""

import math

from .models import ParameterData, SongContext, TrackArrangementClips, TrackDevices, TrackInfo, TrackStructure


def volume_to_db(value: float) -> str:
    """Convert 0-1 volume to dB string."""
    if value <= 0:
        return "-inf dB"
    db = 20 * math.log10(value)
    return f"{db:.1f} dB"


def pan_to_string(value: float) -> str:
    """Convert -1 to 1 panning to string."""
    if value == 0:
        return "C"
    percentage = round(abs(value) * 100)
    if value < 0:
        return f"L{percentage}"
    return f"R{percentage}"


def pitch_to_note_name(pitch: int) -> str:
    """Convert MIDI pitch (0-127) to note name."""
    notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    note = notes[pitch % 12]
    octave = pitch // 12 - 1
    return f"{note}{octave}"


def beats_to_bars(beats: float, time_sig_numerator: int = 4) -> float:
    """Convert beats to bars."""
    return beats / time_sig_numerator


def format_bar_length(beats: float, time_sig_numerator: int = 4) -> str:
    """Format length as bars string."""
    bars = beats_to_bars(beats, time_sig_numerator)
    if bars == 1:
        return "1 bar"
    if bars == int(bars):
        return f"{int(bars)} bars"
    return f"{bars} bars"


def format_song_context(ctx: SongContext) -> str:
    """Format song context as compact summary for LLM."""
    return (
        f"Tempo: {ctx.tempo} BPM | "
        f"Time signature: {ctx.time_sig_numerator}/{ctx.time_sig_denominator} | "
        f"Tracks: {ctx.num_tracks}"
    )


def format_track_devices(track_data: TrackDevices) -> str:
    """Format track devices as compact summary for LLM."""
    return f"Track: {track_data.name}\nDevices: {', '.join(d.name for d in track_data.devices) or 'None'}"


def format_device_params(params: list[ParameterData]) -> str:
    """Format device parameters as compact key=value string for LLM."""
    param_strs = [f"{p.name}={p.value_string}" for p in params if p.value_string]
    return f"', '.join{param_strs}"


def format_track_info(info: TrackInfo) -> str:
    """Format full track info as compact summary for LLM."""
    if info.is_foldable:
        track_type = "Group"
    elif info.is_midi_track:
        track_type = "MIDI"
    elif info.is_audio_track:
        track_type = "Audio"
    else:
        track_type = "Return"
    flags = [f for f, v in [("muted", info.mute), ("solo", info.solo), ("armed", info.arm)] if v]
    lines = [
        f"Track [{info.index}]: {info.name} ({track_type})",
        f"Volume: {volume_to_db(info.volume)} | Pan: {pan_to_string(info.panning)}"
        + (f" | {', '.join(flags)}" if flags else ""),
        f"Devices: {', '.join(d.name for d in info.devices) or 'None'}",
    ]
    if info.clip_slot_count:
        lines.append(f"Session clip slots: {info.clip_slot_count}")
    return "\n".join(lines)


def format_track_structure(structure: TrackStructure) -> str:
    """Format all tracks as an indented list showing groups and nesting."""
    lines = []
    for t in structure.tracks:
        indent = "  " if t.is_grouped else ""
        if t.type == "group":
            label = "[group]"
        else:
            label = f"[{t.type}]"
        lines.append(f"{indent}{t.index}: {t.name} {label}")
    return "\n".join(lines)


def format_arrangement_clips(data: TrackArrangementClips) -> str:
    """Format arrangement clips as compact summary for LLM."""
    if not data.clips:
        return f"Track [{data.track_index}] '{data.track_name}': no arrangement clips"
    lines = [f"Track [{data.track_index}] '{data.track_name}': {len(data.clips)} clip(s)"]
    for c in data.clips:
        kind = "MIDI" if c.is_midi else "audio"
        name = f'"{c.name}"' if c.name else "(unnamed)"
        lines.append(f"  {name} | {kind} | {c.start_time:.1f}–{c.end_time:.1f} beats")
    return "\n".join(lines)
