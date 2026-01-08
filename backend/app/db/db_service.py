import time
from typing import Dict, List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from ..shared import GENRE_SYSTEM_PROMPTS, TRIBAL_SCIFI_TECHNO
from . import get_db
from .models import (
    ChatSession,
    Device,
    Genre,
    Message,
    Parameter,
    ParameterChange,
    Project,
    Track,
)


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

    # Project methods

    def get_project(self, project_id: int) -> Optional[Project]:
        return self.db.query(Project).filter(Project.id == project_id).first()

    def get_project_by_name(self, name: str) -> Optional[Project]:
        return self.db.query(Project).filter(Project.name == name).first()

    def get_all_projects(self) -> List[Project]:
        return self.db.query(Project).all()

    def create_project(self, name: str) -> Project:
        timestamp = int(time.time() * 1000)
        project = Project(name=name, indexed_at=timestamp)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete_project(self, project_id: int) -> None:
        self.db.query(Project).filter(Project.id == project_id).delete()
        self.db.commit()

    def update_project_indexed_at(self, project_id: int) -> None:
        timestamp = int(time.time() * 1000)
        self.db.query(Project).filter(Project.id == project_id).update(
            {"indexed_at": timestamp}
        )
        self.db.commit()

    def clear_project_structure(self, project_id: int) -> None:
        """Clear all tracks, devices, and parameters for a project (for re-indexing)."""
        self.db.query(Track).filter(Track.project_id == project_id).delete()
        self.db.commit()

    def save_project_structure(
        self, project_id: int, tracks_data: List[dict]
    ) -> None:
        """Save tracks, devices, and parameters for a project.

        Args:
            project_id: The project ID
            tracks_data: List of track dicts with structure:
                [{
                    "id": track_index,
                    "name": track_name,
                    "devices": [{
                        "id": device_index,
                        "name": device_name,
                        "class_name": class_name,
                        "parameters": [{
                            "id": param_index,
                            "name": param_name,
                            "value": value,
                            "min": min_value,
                            "max": max_value
                        }]
                    }]
                }]
        """
        for track_data in tracks_data:
            track = Track(
                project_id=project_id,
                track_index=track_data["id"],
                name=track_data["name"],
            )
            self.db.add(track)
            self.db.flush()  # Get the track ID

            for device_data in track_data.get("devices", []):
                device = Device(
                    track_id=track.id,
                    device_index=device_data["id"],
                    name=device_data["name"],
                    class_name=device_data["class_name"],
                )
                self.db.add(device)
                self.db.flush()  # Get the device ID

                for param_data in device_data.get("parameters", []):
                    param = Parameter(
                        device_id=device.id,
                        param_index=param_data["id"],
                        name=param_data["name"],
                        value=param_data["value"],
                        min_value=param_data["min"],
                        max_value=param_data["max"],
                    )
                    self.db.add(param)

        self.db.commit()

    def load_project_structure(self, project_id: int) -> List[dict]:
        """Load tracks, devices, and parameters for a project.

        Returns:
            List of track dicts with the same structure as save_project_structure
        """
        tracks = (
            self.db.query(Track)
            .filter(Track.project_id == project_id)
            .order_by(Track.track_index)
            .all()
        )

        result = []
        for track in tracks:
            track_data = {
                "id": track.track_index,
                "name": track.name,
                "devices": [],
            }

            devices = (
                self.db.query(Device)
                .filter(Device.track_id == track.id)
                .order_by(Device.device_index)
                .all()
            )

            for device in devices:
                device_data = {
                    "id": device.device_index,
                    "name": device.name,
                    "class_name": device.class_name,
                    "parameters": [],
                }

                params = (
                    self.db.query(Parameter)
                    .filter(Parameter.device_id == device.id)
                    .order_by(Parameter.param_index)
                    .all()
                )

                for param in params:
                    device_data["parameters"].append({
                        "id": param.param_index,
                        "name": param.name,
                        "value": param.value,
                        "min": param.min_value,
                        "max": param.max_value,
                    })

                track_data["devices"].append(device_data)

            result.append(track_data)

        return result

    def link_session_to_project(self, session_id: str, project_id: int) -> None:
        self.db.query(ChatSession).filter(ChatSession.id == session_id).update(
            {"project_id": project_id}
        )
        self.db.commit()

    def get_project_tracks_for_frontend(self, project_id: int) -> List[dict]:
        """Load tracks and devices in frontend format (without parameters)."""
        tracks = (
            self.db.query(Track)
            .filter(Track.project_id == project_id)
            .order_by(Track.track_index)
            .all()
        )

        result = []
        for track in tracks:
            track_data = {
                "id": track.track_index,
                "name": track.name,
                "devices": [],
            }

            devices = (
                self.db.query(Device)
                .filter(Device.track_id == track.id)
                .order_by(Device.device_index)
                .all()
            )

            for device in devices:
                track_data["devices"].append({
                    "id": device.device_index,
                    "name": device.name,
                    "className": device.class_name,
                })

            result.append(track_data)

        return result


def get_db_service(db: Session = Depends(get_db)) -> DBService:
    return DBService(db)
