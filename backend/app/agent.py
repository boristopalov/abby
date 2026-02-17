import os
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, List

from google.genai import Client, types
from pydantic import BaseModel

from .ableton import (
    AbletonClient,
    format_bar_length,
    format_device_params_from_db,
    format_device_summary,
    pan_to_string,
    pitch_to_note_name,
    volume_to_db,
)
from .chat import ChatContext
from .db.db_service import DBService
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

### get_track_clips(track_id)
Returns list of clips on a track with length, type (MIDI/audio), loop status.

### get_clip_notes(track_id, clip_id)
Analyzes MIDI clip content: note count, pitch range, velocity, rhythm density.
Only works on MIDI clips.

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

**Creative feedback on a MIDI track:**
1. get_track_clips(track_id) → find clips
2. get_clip_notes(track_id, clip_id) → analyze melody/rhythm
3. Provide feedback on note choices, velocity, rhythm

**When giving feedback:**
- Reference specific values ("your compressor ratio is 8:1")
- Explain the "why" not just the "what"
- Consider the genre/style context
- Suggest specific parameter changes when appropriate
"""


# Tool schemas
class GetTrackInfoInput(BaseModel):
    track_id: int


class GetTrackClipsInput(BaseModel):
    track_id: int


class GetClipNotesInput(BaseModel):
    track_id: int
    clip_id: int


class GetDeviceParamsInput(BaseModel):
    track_id: int
    device_id: int


class SetDeviceParamInput(BaseModel):
    track_id: int
    device_id: int
    param_id: int
    value: float


class Agent:
    def __init__(self, completion_model: Client):
        logger.info("Initializing Agent with Gemini model")
        self.completion_model = completion_model
        self.tools = self._setup_tools()

    def _setup_tools(self) -> List[types.Tool]:
        logger.debug("Setting up tool declarations")
        tool_declarations = [
            {
                "name": "get_song_context",
                "description": "Get project-level info: tempo, time signature, track count, return tracks. Use this first to understand the project structure.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_track_info",
                "description": "Get mixer state for a track: volume (in dB), pan, mute, solo, arm status, routing. Use this to understand a track's role in the mix.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "track_id": {
                            "type": "NUMBER",
                            "description": "0-indexed track position",
                        },
                    },
                    "required": ["track_id"],
                },
            },
            {
                "name": "get_track_clips",
                "description": "Get list of arrangement clips on a track with length, type (MIDI/audio), loop status. Use to discover clip content before analyzing.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "track_id": {
                            "type": "NUMBER",
                            "description": "0-indexed track position",
                        },
                    },
                    "required": ["track_id"],
                },
            },
            {
                "name": "get_clip_notes",
                "description": "Analyze MIDI clip content: note count, pitch range, velocity stats, rhythm density. Only works on MIDI clips, not audio.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "track_id": {
                            "type": "NUMBER",
                            "description": "0-indexed track position",
                        },
                        "clip_id": {
                            "type": "NUMBER",
                            "description": "0-indexed clip slot from get_track_clips",
                        },
                    },
                    "required": ["track_id", "clip_id"],
                },
            },
            {
                "name": "get_track_devices",
                "description": "Get a summary of devices on a track. Returns track name and list of device names (not parameters). Use this to discover what devices exist before drilling into details.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "track_id": {
                            "type": "NUMBER",
                            "description": "0-indexed track position",
                        },
                    },
                    "required": ["track_id"],
                },
            },
            {
                "name": "get_device_params",
                "description": "Get all parameters for a specific device with human-readable values (e.g., '-12 dB', '4:1', '100%'). Use after get_track_devices to inspect a specific device.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "track_id": {
                            "type": "NUMBER",
                            "description": "0-indexed track position",
                        },
                        "device_id": {
                            "type": "NUMBER",
                            "description": "0-indexed device position in the track's device chain",
                        },
                    },
                    "required": ["track_id", "device_id"],
                },
            },
            {
                "name": "set_device_param",
                "description": "Set a device parameter to a new value. Value must be normalized between 0.0 and 1.0.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "track_id": {
                            "type": "NUMBER",
                            "description": "0-indexed track position",
                        },
                        "device_id": {
                            "type": "NUMBER",
                            "description": "0-indexed device position in the track's device chain",
                        },
                        "param_id": {
                            "type": "NUMBER",
                            "description": "0-indexed parameter position in the device's parameter list",
                        },
                        "value": {
                            "type": "NUMBER",
                            "description": "Normalized value between 0.0 and 1.0",
                        },
                    },
                    "required": ["track_id", "device_id", "param_id", "value"],
                },
            },
        ]
        return [types.Tool(function_declarations=[decl]) for decl in tool_declarations]

    async def generate_function_response(
        self,
        osc_handler: AbletonClient,
        function_call: types.FunctionCall,
        db_service: DBService,
        project_id: int,
    ) -> types.Part:
        """Handle function calls and generate responses using the new Gemini API format.

        Reads (get_track_devices, get_device_params) use the DB for fast access.
        Writes (set_device_param) still go through OSC to Ableton.
        """
        try:
            function_name = function_call.name
            function_args = function_call.args
            logger.info(
                f"Handling function call: {function_name} with args: {function_args}"
            )

            if function_name == "get_song_context":
                # Read from DB
                context_data = db_service.get_song_context(project_id)
                if context_data is None:
                    result = "Song context not found"
                else:
                    result = (
                        f"Project Context:\n"
                        f"  Tempo: {context_data['tempo']} BPM\n"
                        f"  Time Signature: {context_data['time_sig_numerator']}/{context_data['time_sig_denominator']}\n"
                        f"  Tracks: {context_data['num_tracks']}\n"
                        f"  Return Tracks: {context_data['num_returns']}"
                    )

            elif function_name == "get_track_info":
                args = GetTrackInfoInput(**function_args)
                # Get track name from devices summary
                track_data = db_service.get_track_devices_summary(
                    project_id, args.track_id
                )
                if track_data is None:
                    result = f"Track {args.track_id} not found"
                else:
                    track_name = track_data["name"]
                    mixer_state = db_service.get_track_mixer_state(
                        project_id, args.track_id
                    )
                    if mixer_state is None:
                        result = f"Mixer state for track {args.track_id} not found"
                    else:
                        volume_db = volume_to_db(mixer_state["volume"])
                        pan_str = pan_to_string(mixer_state["panning"])
                        mute_str = "On" if mixer_state["mute"] else "Off"
                        solo_str = "On" if mixer_state["solo"] else "Off"
                        arm_str = "Yes" if mixer_state["arm"] else "No"
                        track_type = (
                            "MIDI" if mixer_state["has_midi_input"] else "Audio"
                        )
                        output = mixer_state.get("output_routing") or "Master"
                        grouped_str = "Yes" if mixer_state["is_grouped"] else "No"
                        result = (
                            f'Track {args.track_id}: "{track_name}"\n'
                            f"  Volume: {volume_db}, Pan: {pan_str}\n"
                            f"  Mute: {mute_str}, Solo: {solo_str}, Armed: {arm_str}\n"
                            f"  Type: {track_type} -> {output}\n"
                            f"  Grouped: {grouped_str}"
                        )

            elif function_name == "get_track_clips":
                args = GetTrackClipsInput(**function_args)
                # Get track name from devices summary
                track_data = db_service.get_track_devices_summary(
                    project_id, args.track_id
                )
                if track_data is None:
                    result = f"Track {args.track_id} not found"
                else:
                    track_name = track_data["name"]
                    clips = db_service.get_track_clips(project_id, args.track_id)
                    if clips is None:
                        result = f"Track {args.track_id} not found"
                    elif len(clips) == 0:
                        result = (
                            f'Track {args.track_id} "{track_name}" - 0 clips indexed'
                        )
                    else:
                        lines = [
                            f'Track {args.track_id} "{track_name}" - {len(clips)} clips:'
                        ]
                        for clip in clips:
                            clip_type = "MIDI" if clip["is_midi"] else "audio"
                            length = format_bar_length(clip["length_beats"])
                            # Determine if looped: loop region is defined
                            loop_len = clip["loop_end"] - clip["loop_start"]
                            loop_status = (
                                f"loop={format_bar_length(loop_len)}"
                                if loop_len > 0
                                else ""
                            )
                            gain_str = (
                                f", gain={clip['gain']:.2f}"
                                if clip["gain"] != 0.0
                                else ""
                            )
                            extras = ", ".join(
                                [s for s in [loop_status, gain_str.strip(", ")] if s]
                            )
                            if extras:
                                extras = ", " + extras
                            lines.append(
                                f'  [{clip["clip_index"]}] "{clip["name"]}" ({clip_type}, {length}{extras})'
                            )
                        result = "\n".join(lines)

            elif function_name == "get_clip_notes":
                args = GetClipNotesInput(**function_args)
                clip_data = db_service.get_clip_notes(
                    project_id, args.track_id, args.clip_id
                )
                if clip_data is None:
                    result = f"Clip {args.clip_id} on track {args.track_id} not found"
                else:
                    notes = clip_data["notes"]
                    clip_name = clip_data["clip_name"]
                    if len(notes) == 0:
                        result = f'Clip "{clip_name}" (MIDI):\n  No notes'
                    else:
                        # Compute derived metrics
                        pitches = [n["pitch"] for n in notes]
                        velocities = [n["velocity"] for n in notes]
                        min_pitch = min(pitches)
                        max_pitch = max(pitches)
                        unique_pitches = len(set(pitches))
                        min_vel = min(velocities)
                        max_vel = max(velocities)
                        avg_vel = sum(velocities) / len(velocities)

                        # Compute length in beats from note positions
                        max_end_time = max(
                            n["start_time"] + n["duration"] for n in notes
                        )
                        # Note density = notes per beat
                        density = len(notes) / max_end_time if max_end_time > 0 else 0

                        length_str = format_bar_length(max_end_time)
                        low_note = pitch_to_note_name(min_pitch)
                        high_note = pitch_to_note_name(max_pitch)

                        result = (
                            f'Clip "{clip_name}" (MIDI):\n'
                            f"  Length: {length_str}\n"
                            f"  Notes: {len(notes)} total, {density:.1f} per beat\n"
                            f"  Pitch: {low_note} to {high_note} ({unique_pitches} unique)\n"
                            f"  Velocity: {min_vel}-{max_vel}, avg {avg_vel:.0f}"
                        )

            elif function_name == "get_track_devices":
                track_id = int(function_args["track_id"])
                # Read from DB instead of OSC
                track_data = db_service.get_track_devices_summary(project_id, track_id)
                if track_data is None:
                    result = f"Track {track_id} not found"
                else:
                    result = format_device_summary(track_data)

            elif function_name == "get_device_params":
                args = GetDeviceParamsInput(**function_args)
                # Read from DB instead of OSC
                device_data = db_service.get_device_parameters(
                    project_id, args.track_id, args.device_id
                )
                if device_data is None:
                    result = (
                        f"Device {args.device_id} on track {args.track_id} not found"
                    )
                else:
                    device_name, track_name, params = device_data
                    result = format_device_params_from_db(
                        device_name, track_name, params
                    )

            elif function_name == "set_device_param":
                args = SetDeviceParamInput(**function_args)
                # Writes still go through OSC
                result = await osc_handler.set_parameter(
                    args.track_id, args.device_id, args.param_id, args.value
                )

            else:
                raise ValueError(f"Unknown function: {function_name}")

            return types.Part.from_function_response(
                name=function_name, response={"result": result}
            )

        except Exception as e:
            logger.error(f"Error handling function call: {str(e)}")
            return types.Part.from_function_response(
                name=function_call.name, response={"error": str(e)}
            )

    async def process_message(
        self,
        context: ChatContext,
        message: Dict[str, Any],
        db_service: DBService,
        osc_client: AbletonClient,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process messages and yield responses"""
        if not context.current_session_id:
            logger.error(
                f"No active session found for ID: {context.current_session_id}"
            )
            yield {"type": "error", "content": "No active session"}
            return

        session = db_service.get_chat_session(context.current_session_id)
        if not session:
            logger.error(
                f"No active session found for ID: {context.current_session_id}"
            )
            yield {"type": "error", "content": "No active session"}
            return

        logger.info(f"Processing message for session {context.current_session_id}")

        # Add message to context and database
        if message["role"] == "user":
            logger.info(f"Adding user message to database: {message}")
            context.add_message(
                types.Content(
                    role="user", parts=[types.Part.from_text(text=message["content"])]
                )
            )
            db_service.add_message(
                context.current_session_id,
                {"text": message["content"], "isUser": True, "type": "text"},
            )

        continue_loop = True
        while continue_loop:
            try:
                response_text = ""
                has_function_call = False

                messages = context.get_messages()
                logger.info(
                    f"Generating response from Gemini - "
                    f"session={context.current_session_id}, "
                    f"message_count={len(messages)}, "
                    f"last_role={messages[-1].role if messages else 'none'}"
                )
                # Debug: log message structure
                for i, msg in enumerate(messages):
                    parts_info = []
                    if msg.parts:
                        for p in msg.parts:
                            if hasattr(p, "text") and p.text:
                                parts_info.append(f"text:{p.text[:30]}...")
                            elif hasattr(p, "function_call") and p.function_call:
                                sig = getattr(p, "thought_signature", None)
                                parts_info.append(
                                    f"fn_call:{p.function_call.name}(sig={sig is not None})"
                                )
                            elif (
                                hasattr(p, "function_response") and p.function_response
                            ):
                                parts_info.append(f"fn_resp:{p.function_response.name}")
                    logger.info(f"  msg[{i}] role={msg.role} parts={parts_info}")

                stream = self.completion_model.models.generate_content_stream(
                    model="gemini-3-flash-preview",
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=self.tools,
                        max_output_tokens=2048,
                    ),
                )

                # Accumulate all parts from the stream before processing
                # This is needed because parallel function calls come in separate chunks
                # but must be combined into a single Content (only first has thought_signature)
                all_parts = []
                first_fc_content = None  # Will hold the content with thought_signature

                for chunk in stream:
                    logger.info(f"CHUNK: {chunk}")
                    if (
                        not chunk.candidates
                        or not chunk.candidates[0].content
                        or not chunk.candidates[0].content.parts
                    ):
                        continue

                    for part in chunk.candidates[0].content.parts:
                        if hasattr(part, "text") and part.text:
                            logger.debug(f"Received text: {part.text[:50]}...")
                            response_text += part.text
                            yield {"type": "text", "content": part.text}
                        elif hasattr(part, "function_call") and part.function_call:
                            has_function_call = True
                            all_parts.append(part)
                            # Keep the first function call content (has thought_signature)
                            if first_fc_content is None:
                                first_fc_content = chunk.candidates[0].content
                            yield {
                                "type": "function_call",
                                "content": part.function_call.name,
                            }

                # Process all collected function calls after stream ends
                if all_parts:
                    # Add any accumulated text before the function calls
                    if response_text:
                        context.add_message(
                            types.Content(
                                role="model",
                                parts=[types.Part.from_text(text=response_text)],
                            )
                        )
                        db_service.add_message(
                            context.current_session_id,
                            {"text": response_text, "isUser": False, "type": "text"},
                        )
                        response_text = ""

                    # Build combined Content with all function call parts
                    # Use parts from all chunks, preserving thought_signature from first
                    combined_content = types.Content(role="model", parts=all_parts)
                    context.add_message(combined_content)

                    # Execute all function calls and collect responses
                    function_response_parts = []
                    for part in all_parts:
                        function_response = await self.generate_function_response(
                            osc_client,
                            part.function_call,
                            db_service,
                            context.current_project_id,
                        )
                        logger.info(f"function response: {str(function_response)}")
                        function_response_parts.append(function_response)

                    # Add all function responses in a single Content
                    context.add_message(
                        types.Content(role="user", parts=function_response_parts)
                    )

                # Store the final text response if we have one
                if response_text:
                    context.add_message(
                        types.Content(
                            role="model",
                            parts=[types.Part.from_text(text=response_text)],
                        )
                    )
                    db_service.add_message(
                        context.current_session_id,
                        {"text": response_text, "isUser": False, "type": "text"},
                    )

                # Exit loop if no function calls were made
                if not has_function_call:
                    continue_loop = False

                # Signal end of current iteration
                yield {"type": "end_message", "content": "<|END_MESSAGE|>"}

            except Exception as e:
                logger.exception(
                    f"Error in process_message: {str(e)} | "
                    f"session={context.current_session_id}, "
                )
                yield {
                    "type": "error",
                    "content": "Something went wrong. Please try again.",
                }
                continue_loop = False

    # def generate_random_genre(self) -> Tuple[str, str]:
    #     try:
    #         logger.info("Generating random genre")
    #         response = self.completion_model.models.generate_content(
    #             model="gemini-2.0-flash-exp",
    #             contents=[types.Content(parts=[types.Part.from_text(GENRE_PROMPT)])],
    #             config=types.GenerateContentConfig(max_output_tokens=2048),
    #         )

    #         if not response.candidates:
    #             logger.error("No response candidates from Gemini")
    #             raise ValueError("No response from model")

    #         content = response.candidates[0].content.parts[0].text

    #         genre_match = re.search(r'GENRE_NAME:\s*"([^"]+)"', content)
    #         prompt_match = re.search(r'PROMPT:\s*"""\n([\s\S]+?)"""', content)

    #         if not genre_match or not prompt_match:
    #             logger.error("Failed to parse genre response")
    #             raise ValueError("Failed to parse genre response")

    #         genre_name = genre_match.group(1)
    #         prompt = prompt_match.group(1)
    #         logger.info(f"Generated new genre: {genre_name}")

    #         # Add the new genre to the GENRE_SYSTEM_PROMPTS
    #         GENRE_SYSTEM_PROMPTS[genre_name] = prompt

    #         return genre_name, prompt
    #     except Exception as e:
    #         logger.error(f"Error generating random genre: {str(e)}")
    #         raise


@lru_cache()
def get_agent() -> Agent:
    return Agent(Client(api_key=os.getenv("GEMINI_API_KEY")))
