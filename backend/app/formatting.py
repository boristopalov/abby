"""Formatting and unit-conversion helpers for Ableton data."""

import math

from .models import ParameterData, TrackDevices


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


def format_track_devices(track_data: TrackDevices) -> str:
    """Format track devices as compact summary for LLM."""
    return f"Track: {track_data.name}\nDevices: {', '.join(d.name for d in track_data.devices) or 'None'}"


def format_device_params(params: list[ParameterData]) -> str:
    """Format device parameters as compact key=value string for LLM."""
    param_strs = [f"{p.name}={p.value_string}" for p in params if p.value_string]
    return f"', '.join{param_strs}"
