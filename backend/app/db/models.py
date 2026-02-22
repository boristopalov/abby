from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    indexed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tracks: Mapped[list[Track]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[ChatSession]] = relationship(back_populates="project")
    song_context: Mapped[SongContext | None] = relationship(
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    track_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String)
    project: Mapped[Project] = relationship(back_populates="tracks")
    devices: Mapped[list[Device]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )
    mixer_state: Mapped[TrackMixerState | None] = relationship(
        back_populates="track",
        uselist=False,
        cascade="all, delete-orphan",
    )
    clips: Mapped[list[Clip]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    device_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String)
    class_name: Mapped[str] = mapped_column(String)
    track: Mapped[Track] = relationship(back_populates="devices")
    parameters: Mapped[list[Parameter]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class Parameter(Base):
    __tablename__ = "parameters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    param_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float)
    value_string: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # Human-readable value (e.g., "-12 dB")
    min_value: Mapped[float] = mapped_column(Float)
    max_value: Mapped[float] = mapped_column(Float)
    device: Mapped[Device] = relationship(back_populates="parameters")


class TrackMixerState(Base):
    __tablename__ = "track_mixer_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        unique=True,
    )
    volume: Mapped[float] = mapped_column(Float)  # 0-1 normalized
    panning: Mapped[float] = mapped_column(Float)  # -1 to 1
    mute: Mapped[bool] = mapped_column(Boolean)
    solo: Mapped[bool] = mapped_column(Boolean)
    arm: Mapped[bool] = mapped_column(Boolean)
    is_grouped: Mapped[bool] = mapped_column(Boolean)
    has_midi_input: Mapped[bool] = mapped_column(Boolean)
    has_audio_output: Mapped[bool] = mapped_column(Boolean)
    output_routing: Mapped[str | None] = mapped_column(String, nullable=True)
    track: Mapped[Track] = relationship(back_populates="mixer_state")


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    clip_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String)
    length_beats: Mapped[float] = mapped_column(Float)
    is_midi: Mapped[bool] = mapped_column(Boolean)
    loop_start: Mapped[float] = mapped_column(Float, default=0.0)  # in beats
    loop_end: Mapped[float] = mapped_column(Float, default=0.0)  # in beats
    gain: Mapped[float] = mapped_column(Float, default=0.0)  # raw gain value
    track: Mapped[Track] = relationship(back_populates="clips")
    notes: Mapped[list[ClipNote]] = relationship(
        back_populates="clip", cascade="all, delete-orphan"
    )


class ClipNote(Base):
    __tablename__ = "clip_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    clip_id: Mapped[int] = mapped_column(ForeignKey("clips.id", ondelete="CASCADE"))
    pitch: Mapped[int] = mapped_column(Integer)  # MIDI pitch 0-127
    start_time: Mapped[float] = mapped_column(Float)  # in beats
    duration: Mapped[float] = mapped_column(Float)  # in beats
    velocity: Mapped[int] = mapped_column(Integer)  # 0-127
    mute: Mapped[bool] = mapped_column(Boolean, default=False)
    clip: Mapped[Clip] = relationship(back_populates="notes")


class SongContext(Base):
    __tablename__ = "song_contexts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
    )
    tempo: Mapped[float] = mapped_column(Float)
    time_sig_numerator: Mapped[int] = mapped_column(Integer)
    time_sig_denominator: Mapped[int] = mapped_column(Integer)
    num_tracks: Mapped[int] = mapped_column(Integer)
    project: Mapped[Project] = relationship(back_populates="song_context")


class ChatSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[int] = mapped_column(Integer)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    message_history: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    project: Mapped[Project | None] = relationship(back_populates="sessions")


class ParameterChange(Base):
    __tablename__ = "parameter_changes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    track_id: Mapped[int] = mapped_column(Integer)
    track_name: Mapped[str] = mapped_column(String)
    device_id: Mapped[int] = mapped_column(Integer)
    device_name: Mapped[str] = mapped_column(String)
    param_id: Mapped[int] = mapped_column(Integer)
    param_name: Mapped[str] = mapped_column(String)
    old_value: Mapped[float] = mapped_column(Float)
    new_value: Mapped[float] = mapped_column(Float)
    min_value: Mapped[float] = mapped_column(Float)
    max_value: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[int] = mapped_column(Integer)


def init_db():
    from sqlalchemy import text

    from ..db import Base, engine

    # Only create tables that don't exist (preserves data between restarts)
    Base.metadata.create_all(engine)

    # Migrate: add message_history column if it doesn't exist yet
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN message_history TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists
