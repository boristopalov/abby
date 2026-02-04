import time
from typing import List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from ..logger import logger
from . import get_db
from .models import (
    ChatSession,
    Clip,
    ClipNote,
    Device,
    Message,
    Parameter,
    ParameterChange,
    Project,
    SongContext,
    Track,
    TrackMixerState,
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

    def save_project_structure(self, project_id: int, tracks_data: List[dict]) -> None:
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
                        value_string=param_data.get("value_string"),
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
                    device_data["parameters"].append(
                        {
                            "id": param.param_index,
                            "name": param.name,
                            "value": param.value,
                            "value_string": param.value_string,
                            "min": param.min_value,
                            "max": param.max_value,
                        }
                    )

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
                track_data["devices"].append(
                    {
                        "id": device.device_index,
                        "name": device.name,
                        "className": device.class_name,
                    }
                )

            result.append(track_data)

        return result

    # Agent read methods (fast DB reads instead of slow OSC calls)

    def get_track_devices_summary(
        self, project_id: int, track_index: int
    ) -> dict | None:
        """Get track name and device names for a track (for agent).

        Returns:
            {"name": "Bass", "devices": [{"name": "Compressor"}, ...]}
            or None if track not found
        """
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        devices = (
            self.db.query(Device)
            .filter(Device.track_id == track.id)
            .order_by(Device.device_index)
            .all()
        )

        return {
            "name": track.name,
            "devices": [{"name": d.name} for d in devices],
        }

    def get_device_parameters(
        self, project_id: int, track_index: int, device_index: int
    ) -> tuple[str, str, list[dict]] | None:
        """Get all parameters for a device with value_string (for agent).

        Returns:
            (device_name, track_name, [{"id": 0, "name": "Threshold", "value": 0.5, "value_string": "-12 dB", ...}, ...])
            or None if device not found
        """
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        device = (
            self.db.query(Device)
            .filter(Device.track_id == track.id, Device.device_index == device_index)
            .first()
        )
        if not device:
            return None

        params = (
            self.db.query(Parameter)
            .filter(Parameter.device_id == device.id)
            .order_by(Parameter.param_index)
            .all()
        )

        return (
            device.name,
            track.name,
            [
                {
                    "id": p.param_index,
                    "name": p.name,
                    "value": p.value,
                    "value_string": p.value_string,
                    "min": p.min_value,
                    "max": p.max_value,
                }
                for p in params
            ],
        )

    def update_parameter_value(
        self,
        project_id: int,
        track_index: int,
        device_index: int,
        param_index: int,
        value: float,
        value_string: str | None = None,
    ) -> bool:
        """Update a parameter's value and value_string in the DB.

        Also logs the change to the ParameterChange table for history tracking.

        Returns True if parameter was found and updated, False otherwise.
        """
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return False

        device = (
            self.db.query(Device)
            .filter(Device.track_id == track.id, Device.device_index == device_index)
            .first()
        )
        if not device:
            return False

        param = (
            self.db.query(Parameter)
            .filter(
                Parameter.device_id == device.id, Parameter.param_index == param_index
            )
            .first()
        )
        if not param:
            return False

        # Check if anything actually changed
        value_changed = abs(value - param.value) > 0.0001
        string_changed = value_string is not None and value_string != param.value_string

        if not value_changed and not string_changed:
            logger.debug(
                f"[DB] Skipping parameter update (unchanged): "
                f"track={track_index}, device={device_index}, param={param_index}"
            )
            return True  # No change needed, skip write

        logger.info(
            f"[DB] Updating parameter: track={track_index}, device={device_index}, "
            f"param={param_index}, value={param.value}->{value}, "
            f"value_string={param.value_string}->{value_string}"
        )

        if value_changed:
            change = ParameterChange(
                project_id=project_id,
                track_id=track_index,
                track_name=track.name,
                device_id=device_index,
                device_name=device.name,
                param_id=param_index,
                param_name=param.name,
                old_value=param.value,
                new_value=value,
                min_value=param.min_value,
                max_value=param.max_value,
                timestamp=int(time.time() * 1000),
            )
            self.db.add(change)
            param.value = value

        if string_changed:
            param.value_string = value_string

        self.db.commit()
        return True

    def get_parameter_changes_since(
        self, project_id: int, since_timestamp: int
    ) -> list[dict]:
        """Get parameter changes for a project since a given timestamp.

        Args:
            project_id: The project ID
            since_timestamp: Unix timestamp in milliseconds

        Returns:
            List of change dicts with track/device/param names and values
        """
        changes = (
            self.db.query(ParameterChange)
            .filter(
                ParameterChange.project_id == project_id,
                ParameterChange.timestamp > since_timestamp,
            )
            .order_by(ParameterChange.timestamp.asc())
            .all()
        )

        return [
            {
                "trackId": c.track_id,
                "trackName": c.track_name,
                "deviceId": c.device_id,
                "deviceName": c.device_name,
                "paramId": c.param_id,
                "paramName": c.param_name,
                "oldValue": c.old_value,
                "newValue": c.new_value,
                "min": c.min_value,
                "max": c.max_value,
                "timestamp": c.timestamp,
            }
            for c in changes
        ]

    # Song Context methods

    def save_song_context(self, project_id: int, context_data: dict) -> None:
        """Save song context (tempo, time sig, counts) for a project.

        context_data: {"tempo": float, "time_sig_numerator": int, "time_sig_denominator": int, "num_tracks": int, "num_returns": int}

        Replace existing context if present.
        """
        existing = (
            self.db.query(SongContext)
            .filter(SongContext.project_id == project_id)
            .first()
        )
        if existing:
            existing.tempo = context_data["tempo"]
            existing.time_sig_numerator = context_data["time_sig_numerator"]
            existing.time_sig_denominator = context_data["time_sig_denominator"]
            existing.num_tracks = context_data["num_tracks"]
            existing.num_returns = context_data["num_returns"]
        else:
            song_context = SongContext(
                project_id=project_id,
                tempo=context_data["tempo"],
                time_sig_numerator=context_data["time_sig_numerator"],
                time_sig_denominator=context_data["time_sig_denominator"],
                num_tracks=context_data["num_tracks"],
                num_returns=context_data["num_returns"],
            )
            self.db.add(song_context)
        self.db.commit()

    def get_song_context(self, project_id: int) -> dict | None:
        """Get song context for a project.

        Returns: {"tempo": float, "time_sig_numerator": int, "time_sig_denominator": int, "num_tracks": int, "num_returns": int}
        or None if not found.
        """
        song_context = (
            self.db.query(SongContext)
            .filter(SongContext.project_id == project_id)
            .first()
        )
        if not song_context:
            return None

        return {
            "tempo": song_context.tempo,
            "time_sig_numerator": song_context.time_sig_numerator,
            "time_sig_denominator": song_context.time_sig_denominator,
            "num_tracks": song_context.num_tracks,
            "num_returns": song_context.num_returns,
        }

    # Track Mixer State methods

    def save_track_mixer_state(
        self, project_id: int, track_index: int, mixer_data: dict
    ) -> None:
        """Save mixer state for a track.

        mixer_data: {"volume": float, "panning": float, "mute": bool, "solo": bool, "arm": bool, "is_grouped": bool, "has_midi_input": bool, "has_audio_output": bool, "output_routing": str|None, "sends": list[float]}

        First find the Track by project_id and track_index, then save/update its mixer_state.
        """
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return

        existing = (
            self.db.query(TrackMixerState)
            .filter(TrackMixerState.track_id == track.id)
            .first()
        )
        if existing:
            existing.volume = mixer_data["volume"]
            existing.panning = mixer_data["panning"]
            existing.mute = mixer_data["mute"]
            existing.solo = mixer_data["solo"]
            existing.arm = mixer_data["arm"]
            existing.is_grouped = mixer_data["is_grouped"]
            existing.has_midi_input = mixer_data["has_midi_input"]
            existing.has_audio_output = mixer_data["has_audio_output"]
            existing.output_routing = mixer_data.get("output_routing")
        else:
            mixer_state = TrackMixerState(
                track_id=track.id,
                volume=mixer_data["volume"],
                panning=mixer_data["panning"],
                mute=mixer_data["mute"],
                solo=mixer_data["solo"],
                arm=mixer_data["arm"],
                is_grouped=mixer_data["is_grouped"],
                has_midi_input=mixer_data["has_midi_input"],
                has_audio_output=mixer_data["has_audio_output"],
                output_routing=mixer_data.get("output_routing"),
            )
            self.db.add(mixer_state)
        self.db.commit()

    def get_track_mixer_state(self, project_id: int, track_index: int) -> dict | None:
        """Get mixer state for a track by project and track index.

        Returns: mixer_data dict or None if not found.
        """
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        mixer_state = (
            self.db.query(TrackMixerState)
            .filter(TrackMixerState.track_id == track.id)
            .first()
        )
        if not mixer_state:
            return None

        return {
            "volume": mixer_state.volume,
            "panning": mixer_state.panning,
            "mute": mixer_state.mute,
            "solo": mixer_state.solo,
            "arm": mixer_state.arm,
            "is_grouped": mixer_state.is_grouped,
            "has_midi_input": mixer_state.has_midi_input,
            "has_audio_output": mixer_state.has_audio_output,
            "output_routing": mixer_state.output_routing,
        }

    # Clip methods

    def save_clip(
        self, project_id: int, track_index: int, clip_data: dict
    ) -> int | None:
        """Save or update a single clip.

        clip_data: {"clip_id": int, "name": str, "length_beats": float, "is_midi": bool,
                    "loop_start": float, "loop_end": float, "gain": float}

        Returns: The Clip's database ID, or None if track not found.
        """
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        # Check if clip already exists
        existing_clip = (
            self.db.query(Clip)
            .filter(Clip.track_id == track.id, Clip.clip_index == clip_data["clip_id"])
            .first()
        )

        if existing_clip:
            # Update existing clip
            existing_clip.name = clip_data["name"]
            existing_clip.length_beats = clip_data["length_beats"]
            existing_clip.is_midi = clip_data["is_midi"]
            existing_clip.loop_start = clip_data["loop_start"]
            existing_clip.loop_end = clip_data["loop_end"]
            existing_clip.gain = clip_data["gain"]
            self.db.commit()
            return existing_clip.id
        else:
            # Create new clip
            clip = Clip(
                track_id=track.id,
                clip_index=clip_data["clip_id"],
                name=clip_data["name"],
                length_beats=clip_data["length_beats"],
                is_midi=clip_data["is_midi"],
                loop_start=clip_data["loop_start"],
                loop_end=clip_data["loop_end"],
                gain=clip_data["gain"],
            )
            self.db.add(clip)
            self.db.commit()
            return clip.id

    def get_clip(
        self, project_id: int, track_index: int, clip_index: int
    ) -> dict | None:
        """Get a single clip by track and clip index.

        Returns: clip dict or None if not found.
        """
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        clip = (
            self.db.query(Clip)
            .filter(Clip.track_id == track.id, Clip.clip_index == clip_index)
            .first()
        )
        if not clip:
            return None

        return {
            "id": clip.id,
            "clip_index": clip.clip_index,
            "name": clip.name,
            "length_beats": clip.length_beats,
            "is_midi": clip.is_midi,
            "loop_start": clip.loop_start,
            "loop_end": clip.loop_end,
            "gain": clip.gain,
        }

    def get_track_clips(self, project_id: int, track_index: int) -> list[dict] | None:
        """Get all clips for a track.

        Returns: list of clip dicts or None if track not found.
        """
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        clips = (
            self.db.query(Clip)
            .filter(Clip.track_id == track.id)
            .order_by(Clip.clip_index)
            .all()
        )

        return [
            {
                "id": clip.id,
                "clip_index": clip.clip_index,
                "name": clip.name,
                "length_beats": clip.length_beats,
                "is_midi": clip.is_midi,
                "loop_start": clip.loop_start,
                "loop_end": clip.loop_end,
                "gain": clip.gain,
            }
            for clip in clips
        ]

    # Clip Notes methods

    def save_clip_notes(self, clip_id: int, notes_data: list[dict]) -> None:
        """Save MIDI notes for a clip.

        notes_data: [{"pitch": int, "start_time": float, "duration": float, "velocity": int, "mute": bool}, ...]

        Clear existing notes and save new ones.
        """
        # Clear existing notes
        self.db.query(ClipNote).filter(ClipNote.clip_id == clip_id).delete()

        # Save new notes
        for note_data in notes_data:
            note = ClipNote(
                clip_id=clip_id,
                pitch=note_data["pitch"],
                start_time=note_data["start_time"],
                duration=note_data["duration"],
                velocity=note_data["velocity"],
                mute=note_data.get("mute", False),
            )
            self.db.add(note)

        self.db.commit()

    def get_clip_notes(
        self, project_id: int, track_index: int, clip_index: int
    ) -> dict | None:
        """Get notes for a specific clip.

        Returns: {"clip_name": str, "notes": [...]} or None if not found.
        """
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        clip = (
            self.db.query(Clip)
            .filter(Clip.track_id == track.id, Clip.clip_index == clip_index)
            .first()
        )
        if not clip:
            return None

        notes = (
            self.db.query(ClipNote)
            .filter(ClipNote.clip_id == clip.id)
            .order_by(ClipNote.start_time)
            .all()
        )

        return {
            "clip_name": clip.name,
            "notes": [
                {
                    "pitch": note.pitch,
                    "start_time": note.start_time,
                    "duration": note.duration,
                    "velocity": note.velocity,
                    "mute": note.mute,
                }
                for note in notes
            ],
        }


def get_db_service(db: Session = Depends(get_db)) -> DBService:
    return DBService(db)
