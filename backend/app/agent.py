from functools import lru_cache
import os
from typing import Dict, Any, List, AsyncGenerator, Tuple
from pydantic import BaseModel
import json
from .chat import ChatContext, get_chat_context
from .db.db_service import DBService
from .shared import GENRE_PROMPT, GENRE_SYSTEM_PROMPTS
import re
from google.genai import Client

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
        self.completion_model = completion_model

    TOOLS = [
        {
            "name": "get_tracks_devices",
            "description": "get all devices of all tracks",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "get_device_params",
            "description": "get a specific device's params",
            "input_schema": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "number"},
                    "device_id": {"type": "number"},
                },
            },
        },
        {
            "name": "set_device_param",
            "description": "set a specific device's param",
            "input_schema": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "number"},
                    "device_id": {"type": "number"},
                    "param_id": {"type": "number"},
                    "value": {"type": "number"},
                },
                "required": ["track_id", "device_id", "param_id", "value"],
            },
        },
    ]

    async def generate_response(self, osc_handler: Any, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool calls and generate responses"""
        try:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})

            if tool_name == "get_tracks_devices":
                result = await osc_handler.get_tracks_devices()
                return {
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(result)
                }
            
            elif tool_name == "get_device_params":
                args = GetDeviceParamsInput(**tool_args)
                result = await osc_handler.get_device_params(args.track_id, args.device_id)
                return {
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(result)
                }
            
            elif tool_name == "set_device_param":
                args = SetDeviceParamInput(**tool_args)
                result = await osc_handler.set_device_param(
                    args.track_id, 
                    args.device_id, 
                    args.param_id, 
                    args.value
                )
                return {
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(result)
                }
            
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

        except Exception as e:
            return {
                "role": "tool",
                "name": tool_name,
                "content": json.dumps({"error": str(e)}),
                "is_error": True
            }

    async def stream_llm_response(self, context: ChatContext) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream LLM responses with their types"""
        try:
            stream = self.completion_model.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[{"role": m["role"], "parts": [{"text": m["content"]}]} for m in context.messages],
                tools=self.TOOLS,
                stream=True
            )

            for chunk in stream:
                if chunk.text:
                    yield {
                        "type": "text",
                        "content": chunk.text
                    }
                
            # Signal end of message
            yield {
                "type": "end_message",
                "content": "<|END_MESSAGE|>"
            }

        except Exception as e:
            yield {
                "type": "error",
                "content": f"Error: {str(e)}"
            }

    async def process_message(
        self,
        context: ChatContext,
        message: Dict[str, Any], 
        db_service: DBService, 
        osc_handler: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process messages and yield responses"""
        session = db_service.get_session(context.current_session_id)
        if not session:
            yield {
                "type": "error",
                "content": "No active session"
            }
            return

        # Add message to context and database
        context.add_message(message)
        if message["role"] == "user":
            db_service.add_message(context.current_session_id, {
                "text": message["content"],
                "isUser": True,
                "type": "text"
            })

        continue_loop = True
        while continue_loop:
            # Stream LLM response
            response_text = ""
            async for chunk in self.stream_llm_response(context):
                if chunk["type"] == "error":
                    yield chunk
                    continue_loop = False
                    break
                    
                yield chunk
                if chunk["type"] == "text":
                    response_text += chunk["content"]

            if not continue_loop:
                break

            # Add assistant message to context and database
            context.add_message({
                "role": "assistant",
                "content": response_text
            })
            db_service.add_message(context.current_session_id, {
                "text": response_text,
                "isUser": False,
                "type": "text"
            })

            # Handle tool calls if present
            tool_calls = []  # TODO: Extract tool calls from Gemini response
            if tool_calls:
                for tool_call in tool_calls:
                    yield {
                        "type": "tool",
                        "content": tool_call["name"]
                    }

                    response = await self.generate_response(osc_handler, tool_call)
                    if response.get("is_error"):
                        yield {
                            "type": "error",
                            "content": "Tool usage failed!"
                        }
                        continue_loop = False
                        break

                    context.add_message({
                        "role": "user",
                        "content": response
                    })
            else:
                continue_loop = False

    async def generate_random_genre(self) -> Tuple[str, str]:
        try:            
            response = await self.completion_model.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=GENRE_PROMPT,
                generation_config={"max_output_tokens": 2048}
            )
            content = response.content[0].text if response.content[0].type == "text" else ""

            genre_match = re.search(r'GENRE_NAME:\s*"([^"]+)"', content)
            prompt_match = re.search(r'PROMPT:\s*"""\n([\s\S]+?)"""', content)

            if not genre_match or not prompt_match:
                raise ValueError("Failed to parse genre response")

            genre_name = genre_match.group(1)
            prompt = prompt_match.group(1).strip()

            # Add the new genre to the GENRE_SYSTEM_PROMPTS
            GENRE_SYSTEM_PROMPTS[genre_name] = prompt
            
            return genre_name, prompt
        except Exception as e:
            print("Error generating random genre:", str(e))




@lru_cache()
def get_agent() -> Agent:
    return Agent(Client(api_key=os.getenv("GOOGLE_API_KEY")))