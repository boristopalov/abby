from typing import Dict, Any, List, AsyncGenerator
from pydantic import BaseModel
import json
from ..core.context import ChatContext
from ..services.db_service import DBService

# Tool schemas
class GetDeviceParamsInput(BaseModel):
    track_id: int
    device_id: int

class SetDeviceParamInput(BaseModel):
    track_id: int
    device_id: int
    param_id: int
    value: float

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


async def generate_response(osc_handler: Any, tool_call: Dict[str, Any]) -> Dict[str, Any]:
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

async def stream_llm_response(context: ChatContext, messages: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream LLM responses with their types"""
    try:
        stream = context.gemini.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[{"role": m["role"], "parts": [{"text": m["content"]}]} for m in messages],
            tools=TOOLS,
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
    message: Dict[str, Any], 
    context: ChatContext,
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
        async for chunk in stream_llm_response(context, context.messages):
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

                response = await generate_response(osc_handler, tool_call)
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
