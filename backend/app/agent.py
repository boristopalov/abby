import uuid
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict

from pydantic_ai import (
    Agent,
    AgentRunResultEvent,
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
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.messages import TextPart as MsgTextPart

from .ableton import AbletonClient
from .db.ableton_repository import AbletonRepository
from .db.chat_repository import ChatRepository
from .events import (
    AgentEvent,
    EndEvent,
    ErrorEvent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from .formatting import (
    format_device_params,
    format_device_summary,
)
from .logger import logger

SYSTEM_PROMPT = """You are an assistant that helps users with Ableton Live projects. You can view and modify device parameters, and analyze tracks for mixing and creative feedback.

## Tools

### get_song_context()
Returns project-level info: tempo, time signature, track count, return tracks.
Use this first to understand the project structure.

### get_track_info(track_id)
Returns mixer state for a track: volume, pan, mute, solo, sends, routing.
Use this to understand a track's role in the mix.

### get_track_devices(track_id)
Returns device chain on a track. Use to see what plugins/effects are loaded.

### get_device_params(track_id, device_id)
Returns all parameters for a device with human-readable values.

### set_device_param(track_id, device_id, param_id, value)
Sets a parameter value. Value must be normalized 0.0-1.0.

## IDs
- track_id: 0-indexed position in track list
- device_id: 0-indexed position in device chain
- param_id: 0-indexed position in parameter list
- clip_id: 0-indexed clip slot (arrangement position)

## Workflow Examples

**Mixing feedback:**
1. get_song_context() → understand tempo, track count
2. get_track_info(track_id) → see volume, pan, routing
3. get_track_devices(track_id) → see processing chain
4. get_device_params() for specific devices → check settings


**When giving feedback:**
- Reference specific values ("your compressor ratio is 8:1")
- Explain the "why" not just the "what"
- Consider the genre/style context
- Suggest specific parameter changes when appropriate
"""


@dataclass
class AbletonDeps:
    ableton_repo: AbletonRepository
    project_id: int
    osc: AbletonClient


ableton_agent = Agent(
    "google-gla:gemini-3-flash-preview",
    system_prompt=SYSTEM_PROMPT,
    deps_type=AbletonDeps,
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
async def get_track_devices(ctx: RunContext[AbletonDeps], track_id: int) -> str:
    """Get a summary of devices on a track. Returns track name and list of device names.
    Use this to discover what devices exist before drilling into details.

    Args:
        track_id: 0-indexed track position.
    """
    track_data = ctx.deps.ableton_repo.get_track_devices_summary(
        ctx.deps.project_id, track_id
    )
    if track_data is None:
        return f"Track {track_id} not found"
    return format_device_summary(track_data)


@ableton_agent.tool
async def get_device_params(
    ctx: RunContext[AbletonDeps], track_id: int, device_id: int
) -> str:
    """Get all parameters for a specific device with human-readable values.
    Use after get_track_devices to inspect a specific device.

    Args:
        track_id: 0-indexed track position.
        device_id: 0-indexed device position in the track's device chain.
    """
    device_data = ctx.deps.ableton_repo.get_device_parameters(
        ctx.deps.project_id, track_id, device_id
    )
    if device_data is None:
        return f"Device {device_id} on track {track_id} not found"
    return format_device_params(
        device_data.device_name, device_data.track_name, device_data.parameters
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
    return await ctx.deps.osc.set_parameter(track_id, device_id, param_id, value)


class ChatService:
    def __init__(
        self,
        chat_repo: ChatRepository,
        ableton_repo: AbletonRepository,
        ableton: AbletonClient,
    ):
        self.chat_repo = chat_repo
        self.ableton_repo = ableton_repo
        self.ableton = ableton

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
            yield ErrorEvent(run_id=run_id, content="No active session")
            return

        logger.info(f"Processing message for session {session_id}")

        deps = AbletonDeps(
            ableton_repo=self.ableton_repo,
            project_id=project_id,
            osc=self.ableton,
        )

        try:
            async for event in ableton_agent.run_stream_events(
                message["content"],
                message_history=self.chat_repo.load_message_history(session_id),
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
                    if (
                        isinstance(event.delta, TextPartDelta)
                        and event.delta.content_delta
                    ):
                        yield TextDeltaEvent(
                            run_id=run_id, content=event.delta.content_delta
                        )
                elif isinstance(event, AgentRunResultEvent):
                    self.chat_repo.save_message_history(
                        session_id, event.result.all_messages()
                    )

        except Exception as e:
            logger.exception(f"Error in process_message: {e} | session={session_id}")
            yield ErrorEvent(
                run_id=run_id, content="Something went wrong. Please try again."
            )
            return

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
