import os
import re
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, List, Tuple

from google.genai import Client, types
from pydantic import BaseModel

from .ableton import AbletonClient
from .chat import ChatContext, get_chat_context
from .db.db_service import DBService
from .logger import logger
from .shared import GENRE_PROMPT, GENRE_SYSTEM_PROMPTS


# Tool schemas
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
                "name": "get_tracks_devices",
                "description": "get all devices of all tracks",
            },
            {
                "name": "get_device_params",
                "description": "get a specific device's params",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "track_id": {"type": "NUMBER", "description": "The track ID"},
                        "device_id": {"type": "NUMBER", "description": "The device ID"},
                    },
                    "required": ["track_id", "device_id"],
                },
            },
            {
                "name": "set_device_param",
                "description": "set a specific device's param",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "track_id": {"type": "NUMBER", "description": "The track ID"},
                        "device_id": {"type": "NUMBER", "description": "The device ID"},
                        "param_id": {
                            "type": "NUMBER",
                            "description": "The parameter ID to modify",
                        },
                        "value": {
                            "type": "NUMBER",
                            "description": "The new value to set",
                        },
                    },
                    "required": ["track_id", "device_id", "param_id", "value"],
                },
            },
        ]
        return [types.Tool(function_declarations=[decl]) for decl in tool_declarations]

    async def generate_function_response(
        self, osc_handler: AbletonClient, function_call: types.FunctionCall
    ) -> types.Part:
        """Handle function calls and generate responses using the new Gemini API format"""
        try:
            function_name = function_call.name
            function_args = function_call.args
            logger.info(
                f"Handling function call: {function_name} with args: {function_args}"
            )

            if function_name == "get_tracks_devices":
                result = await osc_handler.get_tracks_devices()

            elif function_name == "get_device_params":
                args = GetDeviceParamsInput(**function_args)
                result = await osc_handler.get_parameters(args.track_id, args.device_id)

            elif function_name == "set_device_param":
                args = SetDeviceParamInput(**function_args)
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
                name="unknown", response={"error": str(e)}
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
                logger.info("Generating response from Gemini")
                response_text = ""
                has_function_call = False

                stream = self.completion_model.models.generate_content_stream(
                    model="gemini-3-flash-preview",
                    contents=context.get_messages(),
                    config=types.GenerateContentConfig(
                        tools=self.tools,
                        max_output_tokens=2048,
                    ),
                )

                for chunk in stream:
                    # logger.info(f"CHUNK: {chunk}")
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
                            logger.debug(
                                f"Received function call: {part.function_call.name}"
                            )
                            yield {
                                "type": "function_call",
                                "content": part.function_call.name,
                            }

                            # Handle the function call
                            function_response = await self.generate_function_response(
                                osc_client, part.function_call
                            )
                            logger.info(f"function response: {str(function_response)}")
                            context.add_message(
                                types.Content(role="assistant", parts=[part])
                            )
                            context.add_message(
                                types.Content(
                                    role="assistant", parts=[function_response]
                                )
                            )

                # Store the final text response if we have one
                if response_text:
                    context.add_message(
                        types.Content(
                            role="assistant",
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
                logger.error(f"Error in process_message: {str(e)}")
                yield {"type": "error", "content": f"Error: {str(e)}"}
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
    return Agent(Client(api_key=os.getenv("GOOGLE_API_KEY")))
