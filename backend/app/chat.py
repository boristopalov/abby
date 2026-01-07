from dataclasses import dataclass, field
from typing import List, Optional

from google.genai import types


@dataclass
class ChatContext:
    current_session_id: Optional[str] = None
    handlers_initialized: bool = False
    handlers_loading: bool = False
    messages: List[types.Content] = field(default_factory=list)

    def __post_init__(self):
        self.messages = []

    def add_message(self, message: types.Content) -> None:
        """Add a message to the context.

        Args:
            message: A Gemini Content object containing the role and parts
                    (text parts or function calls/responses)
        """
        self.messages.append(message)

    def get_messages(self) -> List[types.Content]:
        """Get messages formatted for Gemini API."""
        return self.messages

    def clear_messages(self) -> None:
        self.messages = []

    def reset_session(self):
        self.handlers_initialized = False
        self.current_session_id = None
        self.messages = []
        self.handlers_loading = False


chat_context = ChatContext()


def get_chat_context() -> ChatContext:
    return chat_context
