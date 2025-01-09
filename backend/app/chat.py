from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from .shared import GENRE_SYSTEM_PROMPTS, TRIBAL_SCIFI_TECHNO
from .db.db_service import DBService


@dataclass
class ChatContext:
    current_session_id: Optional[str] = None
    handlers_initialized: bool = False
    handlers_loading: bool = False
    messages: List[Dict[str, Any]] = None
    current_genre: Dict[str, str] = None

    def __post_init__(self):
        self.messages = []
        self.current_genre = {
            "genre": TRIBAL_SCIFI_TECHNO,
            "systemPrompt": GENRE_SYSTEM_PROMPTS[TRIBAL_SCIFI_TECHNO]
        }

    def add_message(self, message: Dict[str, Any]) -> None:
        self.messages.append(message)

    def clear_messages(self) -> None:
        self.messages = []

    def set_current_genre(self, genre: str, db_service: DBService) -> None:
        genre_data = db_service.get_genre_by_name(genre)
        if not genre_data:
            raise ValueError(f"Genre {genre} not found")
        
        self.current_genre = {
            "genre": genre_data["name"],
            "systemPrompt": genre_data["systemPrompt"]
        }

chat_context = ChatContext()

def get_chat_context():
    return chat_context
    