from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


class TextDeltaEvent(BaseModel):
    run_id: str
    role: str = "model"
    content: str
    type: Literal["text"] = "text"


class ToolCallEvent(BaseModel):
    run_id: str
    role: str = "model"
    tool_call_id: str
    content: str
    arguments: dict[str, Any]
    type: Literal["function_call"] = "function_call"


class ToolResultEvent(BaseModel):
    run_id: str
    role: str = "model"
    content: str
    tool_call_id: str
    type: Literal["function_result"] = "function_result"


class EndEvent(BaseModel):
    run_id: str
    role: str = "model"
    content: str = "<|END_MESSAGE|>"
    type: Literal["end_message"] = "end_message"


class ErrorEvent(BaseModel):
    run_id: str
    content: str
    type: Literal["error"] = "error"


AgentEvent = Annotated[
    Union[TextDeltaEvent, ToolCallEvent, ToolResultEvent, EndEvent, ErrorEvent],
    Field(discriminator="type"),
]
