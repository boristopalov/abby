import json
import uuid
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict

from pydantic_ai import (
    Agent,
    AgentRunResultEvent,
    ApprovalRequired,
    DeferredToolRequests,
    DeferredToolResults,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    RunContext,
    TextPart,
    TextPartDelta,
    ToolCallPart,
    ToolDenied,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.messages import TextPart as MsgTextPart

from .ableton_client import AbletonClient
from .db.chat_repository import ChatRepository
from .events import (
    AgentEvent,
    ApprovalRequest,
    ApprovalRequestEvent,
    EndEvent,
    ModelErrorEvent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from .formatting import (
    format_arrangement_clips,
    format_device_params,
    format_song_context,
    format_track_info,
    format_track_structure,
)
from .live_docs import search as search_live_docs
from .logger import logger

SYSTEM_PROMPT = """You are a music production assistant embedded inside Ableton Live. You have
direct access to the user's session and can read and modify it in real time.

---

## Who You Are

You help producers at every skill level — from beginners learning fundamentals
to professionals automating repetitive workflows. Your tone is direct and
practical. You explain the reasoning behind decisions, not just the decision
itself.

---

## What You Cannot Do

- **You cannot hear.** You have no audio output. Never infer or comment on
  how something sounds. If asked "does this sound good?", say you cannot
  hear, then offer to inspect the technical setup instead.

- **Parameter values you set are estimates.** You know which parameters
  matter and typical ranges, but the right value depends on audio, genre,
  and taste — things you cannot perceive. Prefer direction over precision
  ("increase the attack") unless you have a strong technical reason for a
  specific number. Always give ranges, not single values, and explain the
  trade-off.

- **Normalized values are not always linear.** Many parameters (frequency,
  threshold, ratio) use logarithmic curves internally. After setting a
  parameter, tell the user to verify the displayed value in Ableton matches
  their intent.

- **You cannot map macros.** After building a rack, output written macro
  recommendations for the user to implement manually.

- **Third-party plugins require exact names.** Ask the user for the exact
  name as it appears in their Ableton browser before attempting to add a
  plugin not on the native device list.

---

## How to Respond

**Explain before suggesting.** For mixing advice or sound design, explain
the technique and the reasoning before offering to apply it. "Your compressor
attack is 2 ms — at this speed it's clamping transients. Try 20–40 ms for
more snap" is more useful than "increase attack."

**Ask for context when it changes the answer.** Genre, tempo, skill level,
and creative intent meaningfully shape advice. Ask when you'll use the
answer. Don't ask for information you won't act on.

**Reference the actual session.** When session data is available, use it.
Say "your compressor attack is set to 2 ms" not "if your attack is fast."
Specific references beat hypotheticals.

**After setting a parameter, remind the user to verify.** Normalization
curves mean the displayed value may not match the number you passed.

---

## Domain Knowledge

### Mixing

Use compressors, gates, EQ, limiting, and saturation with an understanding
of signal flow. Know typical threshold, ratio, attack, and release ranges
by instrument and genre. Understand sidechain compression, parallel
compression, and mid-side processing. Know when to cut vs. boost on EQ.

### Sound Design

Understand subtractive, additive, FM, and wavetable synthesis. Know how
attack/decay/sustain/release envelopes shape timbre and expression. Explain
modulation routing (LFOs, envelopes, macros) clearly.

### Arrangement

Genre-specific structure: section lengths, layering, energy arcs. Transition
techniques (risers, drops, fills, breakdowns) and when each applies. Reference
actual clips and tracks in the session when available. Focus on structure —
you cannot judge feel or groove.

**Before arranging, always understand track grouping.**
A session with 30–40 tracks is not 30–40 independent arrangement layers — it
is typically 5–8 functional groups (e.g. Kick, Drums/Perc, Bass, Synths/Leads,
Pads/Atmosphere). Arrangements are built around groups, not individual tracks.

When the user asks to arrange or structure a track:
1. Call `get_track_structure()` to see all tracks with their type and group nesting.
2. Map each leaf track to a functional role (kick, bass, lead, pad, etc.).
3. If the grouping is ambiguous, ask the user: "I see [X] groups and [Y] leaf tracks.
   Before I arrange, can you confirm: which tracks form the kick layer, bass layer,
   lead/melodic layer, and pad/atmosphere layer?" Only arrange once you have this map.

**Intro length guidelines by genre (at 4/4):**
- Techno / Hard Techno: intro is 8–16 bars (kick only or kick + minimal perc).
  First major element (bass/rumble) enters by bar 16–32 at the latest.
- House: 8–16 bars before bass enters.
- Trance / Prog: 16–32 bars is acceptable; energy builds slowly.
Never default to a 32-bar intro for anything faster than 125 BPM unless the user
asks for it. Energy should shift noticeably within the first 16 bars.

**Dedicated clip tools** — always use these instead of `send_raw_command` or
`live_exec` for clip operations. Check this list before reaching for a raw command.

Session view:
- `create_session_clip(track_index, slot_index, length)` — creates an empty MIDI
  clip in a session slot. The slot must be empty.
- `add_notes_to_session_clip(track_index, slot_index, notes)` — adds MIDI notes
  to an existing session clip.

Arrangement view:
- `fill_arrangement_section(track_index, source_slot, start_beat, end_beat)` —
  tiles a session clip repeatedly across the arrangement timeline.
- `create_midi_arrangement_clip(track_index, start_beat, length)` — creates an
  empty MIDI clip in the arrangement. Only works on MIDI tracks.
- `create_audio_arrangement_clip(track_index, file_path, start_beat)` — inserts
  an audio file as an arrangement clip. Only works on audio tracks.
- `add_notes_to_arrangement_clip(track_index, clip_index, notes)` — adds MIDI
  notes to an existing arrangement clip.
- `delete_arrangement_clip(track_index, clip_index)` — deletes a single
  arrangement clip. **Requires user approval.** Tell the user the clip name and
  beat range before calling.
- `clear_track_arrangement(track_index)` — deletes all arrangement clips on a
  track. **Requires user approval.** Always tell the user what will be removed
  before calling this.

Note format for `add_notes_*` tools: each note is a dict with `pitch` (0–127),
`start_time` (beat offset from clip start), `duration` (beats),
`velocity` (0–127, default 100), `mute` (bool, optional).

**Arrangement clip deletion API note:** The correct Live API method is
`track.delete_clip(clip)` where `clip` is an element of `track.arrangement_clips`.
`Clip.delete()` does not exist. `ClipSlot.delete_clip()` only applies to
session-view clip slots, not arrangement clips.

**Arrangement changes must be atomic and incremental.**
- Process at most 5 tracks per `live_exec` call. Do not bulk-process all tracks
  in a single call — it will time out and corrupt state.
- After each batch, verify the result with a `live_eval` before continuing.
- If a `live_exec` times out, split the batch in half and retry — do not repeat
  the same large call.
- Never delete clips in bulk without first telling the user exactly what will be
  removed and getting explicit confirmation. Deletions are hard to undo if
  something goes wrong mid-batch.

### Session Organization

Naming conventions, color-coding by instrument family or role, grouping
strategies, track ordering. When organizing, explain the purpose behind a
scheme, not just the mechanics.

---

## Rack Creation

You can build Audio Effect Racks and Instrument Racks from native Ableton
devices.

**Workflow:**
1. Insert an empty rack at the desired position.
2. Add devices into the rack's chain.
3. Output macro recommendations for the user to map manually.

**Native device names:**

| Category | Devices |
|---|---|
| Dynamics | Compressor, Glue Compressor, Multiband Dynamics, Gate, Limiter |
| EQ / Filter | EQ Eight, EQ Three, Channel EQ, Auto Filter |
| Saturation / Distortion | Saturator, Overdrive, Pedal, Dynamic Tube, Redux, Vinyl Distortion |
| Reverb / Delay | Reverb, Delay, Echo, Filter Delay, Grain Delay |
| Modulation | Chorus-Ensemble, Flanger, Phaser-Flanger, Auto Pan |
| Instruments | Operator, Wavetable, Analog, Drift, Simpler, Sampler, Impulse, Drum Rack |
| Utility | Utility, Tuner |

**Macro recommendations** — output after every rack build. Prioritize
expressive and performance-critical parameters over set-and-forget ones.
Cap at 8 macros. Format:

  Suggested macros:
  1. [Label] → [Device] > [Parameter]
  2. ...

---

## Ableton Live API Reference

`search_live_api` searches the unofficial Ableton Live Python API documentation.
This documentation was generated by decompiling Ableton's `.pyc` bytecode —
it reflects the actual internal API used to write MIDI Remote Scripts, including
the one backing this assistant.

Use it when you need to:
- Look up properties, method signatures, or sub-objects on Live classes
  (e.g. `Live.Track.Track`, `Live.Device.Device`, `Live.Song.Song`)
- Understand what a property returns before using it in a new MIDI script handler
- Verify a field name or return type you are unsure about

**Query with identifiers, not descriptions.** The index is text-based (FTS5).
Queries like `"Track delete_clip"` or `"Clip arrangement_clips"` work well.
Descriptive phrases like `"delete arrangement clip"` or `"clip properties methods"`
return poor or no results. When you know the class name, always include it.

This is a fallback tool. Only reach for it when the task requires capabilities
not covered by existing tools and you need to understand the Live API to plan a
new approach. Do not use it for routine session operations.

---

## Raw Command

**`send_raw_command` is a last-resort escape hatch.** Before calling it, confirm
that no existing named tool covers the operation. The dedicated tools — including
all `get_*`, `set_*`, `create_*`, `add_notes_*`, `fill_*`, `delete_*`, `clear_*`,
`create_rack`, `add_device_to_rack`, and `search_live_api` — cover the vast
majority of operations. If a named tool exists for what you need, use it.

Only reach for `send_raw_command` when:
- A registered script command exists but has no dedicated tool
  (e.g. `fire_clip`, `set_clip_name`, `load_browser_item`)
- You need `live_eval` to read an arbitrary Live API value not exposed elsewhere
- You need `live_exec` for a mutation that no named tool covers

Command format: `{"type": "command_type", "params": {"key": "value"}}`

Registered read commands: `get_session_info`, `get_track_structure`,
`get_track_info`, `get_track_devices`, `get_device_parameters`,
`get_arrangement_clips`, `get_project_index`, `get_browser_item`,
`get_browser_tree`, `get_browser_items_at_path`, `live_eval` (see below).

Registered write commands: `set_tempo`, `set_track_name`, `set_device_parameter`,
`create_midi_track`, `create_audio_track`, `delete_track`, `create_clip`,
`delete_clip`, `add_notes_to_clip`, `add_notes_to_arrangement_clip`,
`set_clip_name`, `fire_clip`, `stop_clip`, `start_playback`, `stop_playback`,
`load_browser_item`, `create_rack`, `add_device_to_rack`, `live_exec` (see below).

**Generic escape hatches** for anything not covered by a registered command:
- `live_eval` — read any Live API value: `{"expr": "song.tracks[0].name"}`
- `live_exec` — mutate state (runs on main thread): `{"code": "song.tracks[0].name = 'Kick'"}`
Both run with `song` and `app` in scope plus safe builtins (`len`, `enumerate`,
`list`, `sorted`, etc.). Use `search_live_api` first to look up the correct
attribute path.

**`live_exec` code style rules:**
- No comments. Comments add noise and waste tokens. Write clean, minimal code only.
- Process at most 5 tracks per call. More than that risks a timeout.
- Do not include dead code, pass statements, or placeholder loops.

**Approval required:** Calling `send_raw_command` with `cmd_type` of `live_exec`,
`delete_track`, or `delete_clip` pauses execution and asks the user to approve
before running. The user will see the tool name and arguments.

Never issue destructive commands (delete_track, delete_clip) via raw command
without explicit user confirmation.

---

## Session View vs. Arrangement View

Ableton has two clip contexts:
- **Session view** — clip slots on each track (accessible via `get_track_info`
  which returns `clip_slot_count`).
- **Arrangement view** — clips placed on a timeline (`get_arrangement_clips`).

**Group and return tracks have no arrangement clips.** Only leaf (non-group)
tracks do.

When the user mentions clips, arrangements, or timeline structure, **ask which
view they are working in** if it isn't clear from context. This determines
which tool to use and prevents confusing "no arrangement clips" errors.

---

## Tool Call Ordering

1. Call `get_song_context()` first in any new session before making
   track-specific calls.
2. For arrangement or organisation tasks, call `get_track_structure()` next —
   it gives the full track list with types and group nesting in one round trip,
   without the cost of fetching devices or clips.
3. Call `get_track_info()` before `get_device_params()` — you need the
   device list before you can inspect parameters.
4. Call `get_device_params()` before `set_device_param()` — you need the
   current parameter values and names before modifying anything.
"""


@dataclass
class AbletonDeps:
    project_id: int
    ableton_client: AbletonClient


# TODO: swap to claude
ableton_agent = Agent(
    "anthropic:claude-sonnet-4-6",
    system_prompt=SYSTEM_PROMPT,
    deps_type=AbletonDeps,
    output_type=[str, DeferredToolRequests],
)


# Unused for now
# @ableton_agent.tool
# async def get_track_clips(ctx: RunContext[AbletonDeps], track_id: int) -> str:
#     """Get list of arrangement clips on a track with length, type (MIDI/audio), loop status.

#     Args:
#         track_id: 0-indexed track position.
#     """
#     track_data = ctx.deps.ableton_repo.get_track_devices_summary(
#         ctx.deps.project_id, track_id
#     )
#     if track_data is None:
#         return f"Track {track_id} not found"
#     track_name = track_data.name
#     clips = ctx.deps.ableton_repo.get_track_clips(ctx.deps.project_id, track_id)
#     if clips is None:
#         return f"Track {track_id} not found"
#     if len(clips) == 0:
#         return f'Track {track_id} "{track_name}" - 0 clips indexed'
#     lines = [f'Track {track_id} "{track_name}" - {len(clips)} clips:']
#     for clip in clips:
#         clip_type = "MIDI" if clip.is_midi else "audio"
#         length = format_bar_length(clip.length_beats)
#         loop_len = clip.loop_end - clip.loop_start
#         loop_status = f"loop={format_bar_length(loop_len)}" if loop_len > 0 else ""
#         gain_str = f", gain={clip.gain:.2f}" if clip.gain != 0.0 else ""
#         extras = ", ".join([s for s in [loop_status, gain_str.strip(", ")] if s])
#         if extras:
#             extras = ", " + extras
#         lines.append(
#             f'  [{clip.clip_index}] "{clip.name}" ({clip_type}, {length}{extras})'
#         )
#     return "\n".join(lines)


# Unused for now
# @ableton_agent.tool
# async def get_clip_notes(
#     ctx: RunContext[AbletonDeps], track_id: int, clip_id: int
# ) -> str:
#     """Analyze MIDI clip content: note count, pitch range, velocity stats, rhythm density.
#     Only works on MIDI clips, not audio.

#     Args:
#         track_id: 0-indexed track position.
#         clip_id: 0-indexed clip slot from get_track_clips.
#     """
#     clip_data = ctx.deps.ableton_repo.get_clip_notes(
#         ctx.deps.project_id, track_id, clip_id
#     )
#     if clip_data is None:
#         return f"Clip {clip_id} on track {track_id} not found"
#     notes = clip_data.notes
#     clip_name = clip_data.clip_name
#     if len(notes) == 0:
#         return f'Clip "{clip_name}" (MIDI):\n  No notes'
#     pitches = [n.pitch for n in notes]
#     velocities = [n.velocity for n in notes]
#     min_pitch = min(pitches)
#     max_pitch = max(pitches)
#     unique_pitches = len(set(pitches))
#     min_vel = min(velocities)
#     max_vel = max(velocities)
#     avg_vel = sum(velocities) / len(velocities)
#     max_end_time = max(n.start_time + n.duration for n in notes)
#     density = len(notes) / max_end_time if max_end_time > 0 else 0
#     length_str = format_bar_length(max_end_time)
#     low_note = pitch_to_note_name(min_pitch)
#     high_note = pitch_to_note_name(max_pitch)
#     return (
#         f'Clip "{clip_name}" (MIDI):\n'
#         f"  Length: {length_str}\n"
#         f"  Notes: {len(notes)} total, {density:.1f} per beat\n"
#         f"  Pitch: {low_note} to {high_note} ({unique_pitches} unique)\n"
#         f"  Velocity: {min_vel}-{max_vel}, avg {avg_vel:.0f}"
#     )


@ableton_agent.tool
async def get_song_context(ctx: RunContext[AbletonDeps]) -> str:
    """Get high-level session info: tempo, time signature, and track count.
    Call this first at the start of any new session before making track-specific calls.
    """
    song_ctx = await ctx.deps.ableton_client.get_song_context()
    return format_song_context(song_ctx)


@ableton_agent.tool
async def get_track_structure(ctx: RunContext[AbletonDeps]) -> str:
    """Get the structural overview of all tracks: index, name, type (group/midi/audio),
    and whether each track is nested inside a group.

    Use this before any arrangement or organisation task to map out the session's
    functional layers (kick, bass, synths, pads, etc.) without fetching heavy device
    or clip data. It replaces ad-hoc live_eval calls for track enumeration.
    """
    structure = await ctx.deps.ableton_client.get_track_structure()
    return format_track_structure(structure)


@ableton_agent.tool
async def get_track_info(ctx: RunContext[AbletonDeps], track_index: int) -> str:
    """Get full information about a track: name, type, volume, pan, mute/solo/arm state,
    device list, and session clip-slot count.
    Use this before get_device_params to discover devices; prefer it over live_eval
    for single-track inspection.

    Args:
        track_index: 0-indexed track position.
    """
    info = await ctx.deps.ableton_client.get_track_info(track_index)
    return format_track_info(info)


@ableton_agent.tool
async def get_arrangement_clips(ctx: RunContext[AbletonDeps], track_index: int) -> str:
    """Get all arrangement-view clips on a track with names, beat positions, and type.
    Only works on regular MIDI/audio tracks — group and return tracks will return an error.
    Use this when the user is in Arrangement view or asks about arrangement structure.

    Args:
        track_index: 0-indexed track position.
    """
    try:
        data = await ctx.deps.ableton_client.get_arrangement_clips(track_index)
        return format_arrangement_clips(data)
    except RuntimeError as e:
        return str(e)


@ableton_agent.tool
async def get_device_params(
    ctx: RunContext[AbletonDeps], track_id: int, device_id: int
) -> str:
    """Get all parameters for a specific device with human-readable values.
    Use after get_track_info to inspect a specific device.

    Args:
        track_id: 0-indexed track position.
        device_id: 0-indexed device position in the track's device chain.
    """
    device_params = await ctx.deps.ableton_client.get_device_parameters(
        track_id, device_id
    )
    if device_params is None:
        return f"Device {device_id} on track {track_id} not found"
    return format_device_params(device_params)


@ableton_agent.tool
async def create_rack(
    ctx: RunContext[AbletonDeps],
    track_index: int,
    rack_type: str,
) -> str:
    """Insert an empty Audio Effect Rack or Instrument Rack on a track.
    This is step 1 of the rack-building workflow. The returned device index
    is required for subsequent add_device_to_rack calls.

    Args:
        track_index: 0-indexed track position.
        rack_type: "audio_effect" for Audio Effect Rack, "instrument" for Instrument Rack.
    """
    return await ctx.deps.ableton_client.create_rack(track_index, rack_type)


@ableton_agent.tool
async def add_device_to_rack(
    ctx: RunContext[AbletonDeps],
    track_index: int,
    rack_device_index: int,
    device_name: str,
    chain_index: int = 0,
) -> str:
    """Add a native Ableton device into a rack's chain.
    Call create_rack first to get the rack_device_index.
    Only native devices are supported — ask the user for exact plugin names for third-party devices.

    Args:
        track_index: 0-indexed track position.
        rack_device_index: 0-indexed position of the rack in the track's device chain.
        device_name: Exact native device name (e.g. "Compressor", "EQ Eight", "Reverb").
        chain_index: 0-indexed chain inside the rack (default 0).
    """
    return await ctx.deps.ableton_client.add_device_to_rack(
        track_index, rack_device_index, device_name, chain_index
    )


@ableton_agent.tool
async def set_device_param(
    ctx: RunContext[AbletonDeps],
    track_id: int,
    device_id: int,
    param_id: int,
    value: float,
) -> str:
    """Set a device parameter to a new value. Value must be normalized between 0.0 and 1.0.

    Args:
        track_id: 0-indexed track position.
        device_id: 0-indexed device position in the track's device chain.
        param_id: 0-indexed parameter position in the device's parameter list.
        value: Normalized value between 0.0 and 1.0.

    Returns: The updated value as a string.
    """
    return await ctx.deps.ableton_client.set_parameter(
        track_id, device_id, param_id, value
    )


@ableton_agent.tool
async def search_live_api(ctx: RunContext[AbletonDeps], query: str) -> str:
    """Search the Ableton Live Python API documentation.

    The docs were generated by decompiling Ableton's .pyc bytecode and reflect
    the actual internal API available inside MIDI Remote Scripts. Use this to look
    up class properties, method signatures, and return types before writing or
    planning a new MIDI script handler.

    This is a fallback tool — only use it when existing tools are insufficient
    and you need to understand the Live API to plan a new approach.

    The index is text-based (FTS5), not semantic. Query with actual API identifiers,
    not descriptive phrases.
    - Good: "Track delete_clip", "Clip arrangement_clips", "Song create_clip"
    - Avoid: "how to delete a clip", "arrangement clip properties"
    Dots in class paths are fine — "Live.Track.Track.delete_clip" is split into
    tokens automatically.

    Args:
        query: API identifier terms (e.g. "Track delete_clip", "ClipSlot has_clip").
    """
    return search_live_docs(query)


@ableton_agent.tool
async def send_raw_command(
    ctx: RunContext[AbletonDeps],
    cmd_type: str,
    params: dict[str, Any],
) -> str:
    """Send an arbitrary command to the MIDI Remote Script over TCP.

    Use this when a capability exists in the script but has no dedicated tool
    (e.g. fire_clip, set_clip_name, load_browser_item). The result is returned
    as a JSON string including error responses, so failures are visible.

    Two generic escape-hatch commands are always available for anything not
    covered by a registered handler:
    - live_eval: read any Live API value via a Python expression.
      params: {"expr": "song.tracks[0].name"}
    - live_exec: mutate Live state via a Python code block (runs on main thread).
      params: {"code": "song.tracks[0].name = 'Kick'"}
    Both run with `song` and `app` in scope plus safe builtins (len, enumerate, etc.).

    This is a fallback tool — always prefer named tools over raw commands. Never
    send destructive commands (delete_track, delete_clip) without explicit user
    confirmation.

    Args:
        cmd_type: The command type string (e.g. "fire_clip", "live_eval").
        params: Command parameters as a dict.
    """
    _APPROVAL_REQUIRED_CMDS = {"live_exec", "delete_track", "delete_clip"}
    if cmd_type in _APPROVAL_REQUIRED_CMDS and not ctx.tool_call_approved:
        raise ApprovalRequired()
    return await ctx.deps.ableton_client.send_raw_command(cmd_type, params)


@ableton_agent.tool
async def fill_arrangement_section(
    ctx: RunContext[AbletonDeps],
    track_index: int,
    source_slot: int,
    start_beat: float,
    end_beat: float,
) -> str:
    """Tile a session-view clip across an arrangement section.

    Duplicates the clip at clip_slots[source_slot] repeatedly from start_beat to
    end_beat using duplicate_clip_to_arrangement. The clip's natural length
    determines the step size. Use this instead of live_exec for placing clips.

    Args:
        track_index: 0-indexed track position.
        source_slot: 0-indexed session clip slot to use as the source.
        start_beat: First beat position to place a clip (0 = beginning of arrangement).
        end_beat: Stop placing clips once this beat is reached (exclusive).
    """
    code = (
        f"t = song.tracks[{track_index}]\n"
        f"src = t.clip_slots[{source_slot}].clip\n"
        f"clip_len = src.length\n"
        f"pos = {float(start_beat)}\n"
        f"while pos < {float(end_beat)}:\n"
        f"    t.duplicate_clip_to_arrangement(src, pos)\n"
        f"    pos += clip_len"
    )
    raw = await ctx.deps.ableton_client.send_raw_command("live_exec", {"code": code})
    result = json.loads(raw)
    if result.get("status") == "error":
        return f"Error: {result.get('message')}"
    return f"Filled track {track_index} from beat {start_beat} to {end_beat}"


@ableton_agent.tool(requires_approval=True)
async def clear_track_arrangement(
    ctx: RunContext[AbletonDeps],
    track_index: int,
) -> str:
    """Delete all arrangement clips on a track.

    Always tell the user which track will be cleared and what clips will be lost
    before calling this. Requires user approval before executing.

    Args:
        track_index: 0-indexed track position.
    """
    code = (
        f"t = song.tracks[{track_index}]\n"
        f"for c in list(t.arrangement_clips):\n"
        f"    t.delete_clip(c)"
    )
    raw = await ctx.deps.ableton_client.send_raw_command("live_exec", {"code": code})
    result = json.loads(raw)
    if result.get("status") == "error":
        return f"Error: {result.get('message')}"
    return f"Cleared all arrangement clips on track {track_index}"


@ableton_agent.tool(requires_approval=True)
async def delete_arrangement_clip(
    ctx: RunContext[AbletonDeps],
    track_index: int,
    clip_index: int,
) -> str:
    """Delete a single arrangement clip on a track.

    Always tell the user which clip (name, position) will be deleted before calling this.
    Requires user approval before executing.

    Args:
        track_index: 0-indexed track position.
        clip_index: 0-indexed position in track.arrangement_clips (from get_arrangement_clips).
    """
    code = (
        f"t = song.tracks[{track_index}]\n"
        f"t.delete_clip(t.arrangement_clips[{clip_index}])"
    )
    raw = await ctx.deps.ableton_client.send_raw_command("live_exec", {"code": code})
    result = json.loads(raw)
    if result.get("status") == "error":
        return f"Error: {result.get('message')}"
    return f"Deleted arrangement clip {clip_index} on track {track_index}"


@ableton_agent.tool
async def create_midi_arrangement_clip(
    ctx: RunContext[AbletonDeps],
    track_index: int,
    start_beat: float,
    length: float,
) -> str:
    """Create an empty MIDI clip in the arrangement at a given position.

    Only works on MIDI tracks. The track must not be frozen or currently recording.

    Args:
        track_index: 0-indexed track position.
        start_beat: Beat position where the clip starts (0 = arrangement start).
        length: Clip length in beats.
    """
    code = (
        f"t = song.tracks[{track_index}]\n"
        f"t.create_midi_clip({float(start_beat)}, {float(length)})"
    )
    raw = await ctx.deps.ableton_client.send_raw_command("live_exec", {"code": code})
    result = json.loads(raw)
    if result.get("status") == "error":
        return f"Error: {result.get('message')}"
    return f"Created MIDI clip on track {track_index} at beat {start_beat}, length {length}"


@ableton_agent.tool
async def create_audio_arrangement_clip(
    ctx: RunContext[AbletonDeps],
    track_index: int,
    file_path: str,
    start_beat: float,
) -> str:
    """Create an audio clip in the arrangement referencing a file on disk.

    Only works on audio tracks. The track must not be frozen or currently recording.
    The file must be a valid audio file accessible on the local filesystem.

    Args:
        track_index: 0-indexed track position.
        file_path: Absolute path to the audio file.
        start_beat: Beat position where the clip starts (0 = arrangement start).
    """
    escaped_path = json.dumps(file_path)
    code = (
        f"t = song.tracks[{track_index}]\n"
        f"t.create_audio_clip({escaped_path}, {float(start_beat)})"
    )
    raw = await ctx.deps.ableton_client.send_raw_command("live_exec", {"code": code})
    result = json.loads(raw)
    if result.get("status") == "error":
        return f"Error: {result.get('message')}"
    return f"Created audio clip on track {track_index} at beat {start_beat} from {file_path}"


@ableton_agent.tool
async def create_session_clip(
    ctx: RunContext[AbletonDeps],
    track_index: int,
    slot_index: int,
    length: float,
) -> str:
    """Create an empty MIDI clip in a session-view clip slot.

    The slot must be empty. Only works on MIDI tracks.

    Args:
        track_index: 0-indexed track position.
        slot_index: 0-indexed clip slot (row in the session grid).
        length: Clip length in beats.
    """
    try:
        info = await ctx.deps.ableton_client.create_session_clip(
            track_index, slot_index, length
        )
        return (
            f"Created session clip '{info.name}' in slot {slot_index} "
            f"on track {track_index} ({info.length_beats} beats)"
        )
    except RuntimeError as e:
        return f"Error: {e}"


@ableton_agent.tool
async def add_notes_to_session_clip(
    ctx: RunContext[AbletonDeps],
    track_index: int,
    slot_index: int,
    notes: list[dict],
) -> str:
    """Add MIDI notes to a session-view clip.

    The clip must already exist in the slot — create it with create_session_clip if needed.

    Each note is a dict with:
      - pitch: int, MIDI note number (0–127, e.g. 60 = C3)
      - start_time: float, beat offset from the clip's start
      - duration: float, note length in beats
      - velocity: int, 0–127 (default 100)
      - mute: bool, optional (default false)

    Args:
        track_index: 0-indexed track position.
        slot_index: 0-indexed clip slot.
        notes: List of note dicts.
    """
    try:
        count = await ctx.deps.ableton_client.add_notes_to_session_clip(
            track_index, slot_index, notes
        )
        return f"Added {count} note(s) to session clip in slot {slot_index} on track {track_index}"
    except RuntimeError as e:
        return f"Error: {e}"


@ableton_agent.tool
async def add_notes_to_arrangement_clip(
    ctx: RunContext[AbletonDeps],
    track_index: int,
    clip_index: int,
    notes: list[dict],
) -> str:
    """Add MIDI notes to an arrangement clip.

    Call get_arrangement_clips first to confirm the clip exists and is MIDI.
    The clip must already exist — create it with create_midi_arrangement_clip if needed.

    Each note is a dict with:
      - pitch: int, MIDI note number (0–127, e.g. 60 = C3)
      - start_time: float, beat offset from the clip's start
      - duration: float, note length in beats
      - velocity: int, 0–127 (default 100)
      - mute: bool, optional (default false)

    Args:
        track_index: 0-indexed track position.
        clip_index: 0-indexed position in track.arrangement_clips.
        notes: List of note dicts.
    """
    try:
        count = await ctx.deps.ableton_client.add_notes_to_arrangement_clip(
            track_index, clip_index, notes
        )
        return f"Added {count} note(s) to arrangement clip {clip_index} on track {track_index}"
    except RuntimeError as e:
        return f"Error: {e}"


class ChatService:
    def __init__(
        self,
        chat_repo: ChatRepository,
        ableton_client: AbletonClient,
    ):
        self.chat_repo = chat_repo
        self.ableton_client = ableton_client
        # Holds DeferredToolRequests for sessions paused waiting for approval.
        self._pending_deferred: dict[str, DeferredToolRequests] = {}

    async def _run_agent_stream(
        self,
        run_id: str,
        session_id: str,
        user_prompt: str | None,
        message_history: list,
        deps: AbletonDeps,
        deferred_tool_results: DeferredToolResults | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Route run_stream_events to typed AgentEvents.

        Yields all response events. When the run ends with DeferredToolRequests
        (i.e. a tool needs approval), stores the pending requests in
        _pending_deferred and yields an ApprovalRequestEvent — the caller must
        NOT yield EndEvent in that case.
        """
        async for event in ableton_agent.run_stream_events(
            user_prompt,
            message_history=message_history,
            deferred_tool_results=deferred_tool_results,
            deps=deps,
        ):
            if isinstance(event, FunctionToolCallEvent):
                logger.info(
                    f"Tool call: {event.part.tool_name}; Tool call ID: {event.tool_call_id}"
                )
                yield ToolCallEvent(
                    run_id=run_id,
                    content=event.part.tool_name,
                    arguments=event.part.args_as_dict(),
                    tool_call_id=event.tool_call_id,
                )
            elif isinstance(event, FunctionToolResultEvent):
                if isinstance(event.result, ToolReturnPart):
                    logger.info(
                        f"Tool result: {event.result.tool_name}; Tool call ID: {event.tool_call_id}"
                    )
                    yield ToolResultEvent(
                        run_id=run_id,
                        tool_call_id=event.tool_call_id,
                        content=event.result.model_response_str(),
                    )
            elif isinstance(event, PartStartEvent):
                if isinstance(event.part, TextPart) and event.part.content:
                    yield TextDeltaEvent(run_id=run_id, content=event.part.content)
            elif isinstance(event, PartDeltaEvent):
                if isinstance(event.delta, TextPartDelta) and event.delta.content_delta:
                    yield TextDeltaEvent(
                        run_id=run_id, content=event.delta.content_delta
                    )
            elif isinstance(event, AgentRunResultEvent):
                self.chat_repo.save_message_history(
                    session_id, event.result.all_messages()
                )
                if isinstance(event.result.output, DeferredToolRequests):
                    self._pending_deferred[session_id] = event.result.output
                    yield ApprovalRequestEvent(
                        run_id=run_id,
                        requests=[
                            ApprovalRequest(
                                tool_call_id=call.tool_call_id,
                                tool_name=call.tool_name,
                                arguments=call.args_as_dict(),
                            )
                            for call in event.result.output.approvals
                        ],
                    )

    async def process_message(
        self,
        session_id: str,
        project_id: int,
        message: Dict[str, Any],
    ) -> AsyncGenerator[AgentEvent, None]:
        """Process a message and yield response chunks for the websocket."""
        run_id = str(uuid.uuid4())
        if not self.chat_repo.get_chat_session(session_id):
            logger.error(f"Session not found: {session_id}")
            yield ModelErrorEvent(run_id=run_id, content="No active session")
            return

        logger.info(f"Processing message for session {session_id}")

        deps = AbletonDeps(
            project_id=project_id,
            ableton_client=self.ableton_client,
        )

        try:
            async for agent_event in self._run_agent_stream(
                run_id,
                session_id,
                message["content"],
                self.chat_repo.load_message_history(session_id),
                deps,
            ):
                yield agent_event

        except Exception as e:
            logger.exception(f"Error in process_message: {e} | session={session_id}")
            yield ModelErrorEvent(
                run_id=run_id, content="Something went wrong. Please try again."
            )
            return

        if session_id not in self._pending_deferred:
            yield EndEvent(run_id=run_id)

    async def resume_with_approvals(
        self,
        session_id: str,
        project_id: int,
        approvals: Dict[str, bool],
    ) -> AsyncGenerator[AgentEvent, None]:
        """Resume a run that was paused for tool approval.

        approvals maps tool_call_id to True (approved) or False (denied).
        """
        run_id = str(uuid.uuid4())
        pending = self._pending_deferred.pop(session_id, None)
        if pending is None:
            yield ModelErrorEvent(
                run_id=run_id,
                content="No pending approval requests for this session.",
            )
            return

        results = DeferredToolResults(
            approvals={
                call_id: True if approved else ToolDenied("User denied this action.")
                for call_id, approved in approvals.items()
            }
        )
        deps = AbletonDeps(
            project_id=project_id,
            ableton_client=self.ableton_client,
        )

        try:
            async for agent_event in self._run_agent_stream(
                run_id,
                session_id,
                None,
                self.chat_repo.load_message_history(session_id),
                deps,
                deferred_tool_results=results,
            ):
                yield agent_event

        except Exception as e:
            logger.exception(
                f"Error in resume_with_approvals: {e} | session={session_id}"
            )
            yield ModelErrorEvent(
                run_id=run_id, content="Something went wrong. Please try again."
            )
            return

        if session_id not in self._pending_deferred:
            yield EndEvent(run_id=run_id)

    def get_messages_for_display(self, session_id: str) -> list[dict]:
        """Extract all displayable messages from pydantic-ai message history.

        Returns user text, assistant text, tool calls, and tool results in order.
        Tool results are merged into their corresponding tool call entry (matched by
        tool_call_id), mirroring how they are rendered in the real-time stream.
        """
        model_messages = self.chat_repo.load_message_history(session_id)
        result: list[dict] = []
        # Keyed by tool_call_id so we can attach results to their call entry later.
        tool_call_by_id: dict[str, dict] = {}

        for i, msg in enumerate(model_messages):
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if isinstance(part, UserPromptPart):
                        result.append(
                            {
                                "id": i,
                                "text": part.content,
                                "isUser": True,
                                "type": "text",
                                "timestamp": int(msg.timestamp.timestamp() * 1000),  # pyright: ignore
                            }
                        )
                    elif isinstance(part, ToolReturnPart):
                        entry = tool_call_by_id.get(part.tool_call_id)
                        if entry is not None:
                            entry["result"] = part.model_response_str()
            elif isinstance(msg, ModelResponse):
                text_parts: list[str] = []
                for part in msg.parts:
                    if isinstance(part, MsgTextPart):
                        text_parts.append(part.content)
                    elif isinstance(part, ToolCallPart):
                        entry = {
                            "id": i,
                            "text": part.tool_name,
                            "isUser": False,
                            "type": "function_call",
                            "arguments": part.args_as_dict(),
                            "tool_call_id": part.tool_call_id,
                            "timestamp": int(msg.timestamp.timestamp() * 1000),
                        }
                        result.append(entry)
                        tool_call_by_id[part.tool_call_id] = entry
                if text_parts:
                    result.append(
                        {
                            "id": i,
                            "text": "".join(text_parts),
                            "isUser": False,
                            "type": "text",
                            "timestamp": int(msg.timestamp.timestamp() * 1000),
                        }
                    )
        return result
