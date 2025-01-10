from dataclasses import dataclass, field
from typing import Optional, List, Dict

from .shared import GENRE_SYSTEM_PROMPTS, TRIBAL_SCIFI_TECHNO
from google.genai import types


@dataclass
class ChatContext:
    current_session_id: Optional[str] = None
    handlers_initialized: bool = False
    handlers_loading: bool = False
    messages: List[types.Content] = field(default_factory=list)
    current_genre: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.messages = []
        self.current_genre = {
            "genre": TRIBAL_SCIFI_TECHNO,
            "systemPrompt": GENRE_SYSTEM_PROMPTS[TRIBAL_SCIFI_TECHNO]
        }

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

    def set_current_genre(self, genre_name: str, prompt: str) -> None:
        self.current_genre = {
            "genre": genre_name,
            "systemPrompt": prompt
        }

    def reset_session(self):
        self.handlers_initialized = False
        self.current_session_id = None
        self.messages = None
        self.handlers_loading = False

chat_context = ChatContext()

def get_chat_context() -> ChatContext:
    return chat_context
    