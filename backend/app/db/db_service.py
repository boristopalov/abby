import time
from typing import List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from ..shared import GENRE_SYSTEM_PROMPTS, TRIBAL_SCIFI_TECHNO
from . import get_db
from .models import ChatSession, Genre, Message, ParameterChange


class DBService:
    def __init__(self, db: Session):
        self.db = db

    def create_chat_session(self, name: str, id: str) -> ChatSession:
        timestamp = int(time.time() * 1000)
        new_session = ChatSession(
            id=id,
            name=name,
            created_at=timestamp,
            messages=[],
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

    def add_message(self, session_id: str, message: dict) -> Message:
        timestamp = int(time.time() * 1000)
        db_message = Message(
            session_id=session_id,
            text=message["text"],
            is_user=message["isUser"],
            type=message.get("type", "text"),
            timestamp=timestamp,
        )
        self.db.add(db_message)
        self.db.commit()
        return db_message

    def get_messages(self, session_id: str) -> List[Message]:
        return (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.timestamp.asc())
            .all()
        )

    def add_parameter_change(self, change: dict) -> ParameterChange:
        db_change = ParameterChange(
            track_id=change["trackId"],
            track_name=change["trackName"],
            device_id=change["deviceId"],
            device_name=change["deviceName"],
            param_id=change["paramId"],
            param_name=change["paramName"],
            old_value=change["oldValue"],
            new_value=change["newValue"],
            min_value=change["min"],
            max_value=change["max"],
            timestamp=change["timestamp"],
        )
        self.db.add(db_change)
        self.db.commit()
        return db_change

    def get_recent_parameter_changes(self, limit: int = 100) -> List[ParameterChange]:
        return (
            self.db.query(ParameterChange)
            .order_by(ParameterChange.timestamp.desc())
            .limit(limit)
            .all()
        )

    def add_genre(
        self, name: str, system_prompt: str, is_default: bool = False
    ) -> Genre:
        if is_default:
            self.db.query(Genre).filter(Genre.is_default).update({"is_default": False})

        db_genre = Genre(name=name, system_prompt=system_prompt, is_default=is_default)
        self.db.add(db_genre)
        self.db.commit()
        return db_genre

    def get_genres(self) -> List[Genre]:
        return self.db.query(Genre).all()

    def get_default_genre(self) -> Optional[Genre]:
        return self.db.query(Genre).filter(Genre.is_default).first()

    def set_default_genre(self, name: str) -> None:
        self.db.query(Genre).filter(Genre.is_default).update({"is_default": False})
        self.db.query(Genre).filter(Genre.name == name).update({"is_default": True})
        self.db.commit()

    def get_genre_by_name(self, name: str) -> Optional[Genre]:
        return self.db.query(Genre).filter(Genre.name == name).first()

    def initialize_genres(self) -> None:
        existing_genres = self.get_genres()
        if existing_genres:
            return

        for name, prompt in GENRE_SYSTEM_PROMPTS.items():
            self.add_genre(name, prompt, name == TRIBAL_SCIFI_TECHNO)


def get_db_service(db: Session = Depends(get_db)) -> DBService:
    return DBService(db)
