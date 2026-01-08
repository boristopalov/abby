from dataclasses import dataclass, field
from typing import List, Optional

from google.genai import types


@dataclass
class ChatContext:
    """Manages chat state for the current session."""

    current_session_id: Optional[str] = None
    current_project_id: Optional[int] = None
    messages: List[types.Content] = field(default_factory=list)

    def __post_init__(self):
        self.messages = []

    def add_message(self, message: types.Content) -> None:
        """Add a message to the context."""
        self.messages.append(message)

    def get_messages(self) -> List[types.Content]:
        """Get messages formatted for Gemini API."""
        return self.messages

    def clear_messages(self) -> None:
        self.messages = []

    def set_session(self, session_id: str, project_id: int) -> None:
        """Set the current session and project."""
        if session_id != self.current_session_id:
            self.messages = []
        self.current_session_id = session_id
        self.current_project_id = project_id


chat_context = ChatContext()


def get_chat_context() -> ChatContext:
    return chat_context
