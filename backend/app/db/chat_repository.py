import time
from typing import List, Optional

from fastapi import Depends
from pydantic_ai import ModelMessage
from sqlalchemy.orm import Session

from . import get_db
from .models import ChatSession


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_chat_session(self, name: str, id: str) -> ChatSession:
        timestamp = int(time.time() * 1000)
        new_session = ChatSession(
            id=id,
            name=name,
            created_at=timestamp,
            message_history=[],
        )
        self.db.add(new_session)
        self.db.commit()
        return new_session

    def get_chat_session(self, session_id: str) -> Optional[ChatSession]:
        return self.db.query(ChatSession).filter(ChatSession.id == session_id).first()

    def get_all_chat_sessions(self) -> List[ChatSession]:
        return self.db.query(ChatSession).all()

    def delete_chat_session(self, session_id: str) -> None:
        self.db.query(ChatSession).filter(ChatSession.id == session_id).delete()
        self.db.commit()

    def save_message_history(self, session_id: str, messages: list) -> None:
        """Serialize and persist pydantic-ai message history for a session."""
        from pydantic_core import to_jsonable_python

        self.db.query(ChatSession).filter(ChatSession.id == session_id).update(
            {"message_history": to_jsonable_python(messages)}
        )
        self.db.commit()

    def load_message_history(self, session_id: str) -> list[ModelMessage]:
        """Load and deserialize pydantic-ai message history for a session."""
        from pydantic_ai import ModelMessagesTypeAdapter

        session = (
            self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        )
        if not session or not session.message_history:
            return []
        return ModelMessagesTypeAdapter.validate_python(session.message_history)

    def link_session_to_project(self, session_id: str, project_id: int) -> None:
        self.db.query(ChatSession).filter(ChatSession.id == session_id).update(
            {"project_id": project_id}
        )
        self.db.commit()


def get_chat_repository(db: Session = Depends(get_db)) -> ChatRepository:
    return ChatRepository(db)
