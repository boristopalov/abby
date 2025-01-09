from sqlalchemy.orm import Session
from typing import List, Optional
import time

from .models import ChatSession, Message, ParameterChange, Genre
from ..shared import GENRE_SYSTEM_PROMPTS, TRIBAL_SCIFI_TECHNO
from fastapi import Depends
from . import get_db

class DBService:
    def __init__(self, db: Session):
        self.db = db

    def create_chat_session(self, name: str, id: str) -> dict:
        timestamp = int(time.time() * 1000)
        new_session = ChatSession(
            id=id,
            name=name,
            timestamp=timestamp,
            messages=[],
        )
        self.db.add(new_session)
        self.db.commit()
        return {
            "id": id,
            "name": name,
            "createdAt": timestamp,
            "messages": []
        }

    def get_chat_session(self, session_id: str) -> Optional[dict]:
        messages = self.get_messages(session_id)
        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            return None
        return {
            "id": session.id,
            "name": session.name,
            "createdAt": session.created_at,
            "messages": messages
        }

    def get_all_chat_sessions(self) -> List[dict]:
        sessions = self.db.query(ChatSession).all()
        return [{
            "id": session.id,
            "name": session.name,
            "createdAt": session.created_at,
            "messages": self.get_messages(session.id)
        } for session in sessions]

    def delete_chat_session(self, session_id: str) -> None:
        self.db.query(ChatSession).filter(ChatSession.id == session_id).delete()
        self.db.commit()

    def add_message(self, session_id: str, message: dict) -> None:
        timestamp = int(time.time() * 1000)
        db_message = Message(
            session_id=session_id,
            text=message["text"],
            is_user=message["isUser"],
            type=message.get("type", "text"),
            timestamp=timestamp
        )
        self.db.add(db_message)
        self.db.commit()

    def get_messages(self, session_id: str) -> List[dict]:
        messages = self.db.query(Message).filter(
            Message.session_id == session_id
        ).order_by(Message.timestamp.asc()).all()
        
        return [{
            "text": msg.text,
            "isUser": msg.is_user,
            "type": msg.type,
            "timestamp": msg.timestamp
        } for msg in messages]

    def add_parameter_change(self, change: dict) -> None:
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
            timestamp=change["timestamp"]
        )
        self.db.add(db_change)
        self.db.commit()

    def get_recent_parameter_changes(self, limit: int = 100) -> List[dict]:
        changes = self.db.query(ParameterChange).order_by(
            ParameterChange.timestamp.desc()
        ).limit(limit).all()
        
        return [{
            "trackId": change.track_id,
            "trackName": change.track_name,
            "deviceId": change.device_id,
            "deviceName": change.device_name,
            "paramId": change.param_id,
            "paramName": change.param_name,
            "oldValue": change.old_value,
            "newValue": change.new_value,
            "min": change.min_value,
            "max": change.max_value,
            "timestamp": change.timestamp
        } for change in changes]

    def add_genre(self, name: str, system_prompt: str, is_default: bool = False) -> None:
        if is_default:
            self.db.query(Genre).filter(Genre.is_default == True).update({"is_default": False})
        
        db_genre = Genre(name=name, system_prompt=system_prompt, is_default=is_default)
        self.db.add(db_genre)
        self.db.commit()

    def get_genres(self) -> List[dict]:
        genres = self.db.query(Genre).all()
        return [{
            "name": genre.name,
            "systemPrompt": genre.system_prompt,
            "isDefault": genre.is_default
        } for genre in genres]

    def get_default_genre(self) -> Optional[dict]:
        genre = self.db.query(Genre).filter(Genre.is_default == True).first()
        if not genre:
            return None
        return {
            "name": genre.name,
            "systemPrompt": genre.system_prompt
        }

    def set_default_genre(self, name: str) -> None:
        self.db.query(Genre).filter(Genre.is_default == True).update({"is_default": False})
        self.db.query(Genre).filter(Genre.name == name).update({"is_default": True})
        self.db.commit()

    def get_genre_by_name(self, name: str) -> Optional[dict]:
        genre = self.db.query(Genre).filter(Genre.name == name).first()
        if not genre:
            return None
        return {
            "name": genre.name,
            "systemPrompt": genre.system_prompt
        }

    def initialize_genres(self) -> None:
        existing_genres = self.get_genres()
        if existing_genres:
            return

        for name, prompt in GENRE_SYSTEM_PROMPTS.items():
            self.add_genre(name, prompt, name == TRIBAL_SCIFI_TECHNO) 

def get_db_service(db: Session = Depends(get_db)) -> DBService:
    return DBService(db) 