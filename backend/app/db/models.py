from sqlalchemy import Boolean, Column, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..db import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    indexed_at = Column(Integer, nullable=False)
    tracks = relationship(
        "Track", back_populates="project", cascade="all, delete-orphan"
    )
    sessions = relationship("ChatSession", back_populates="project")
    song_context = relationship(
        "SongContext",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    track_index = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    project = relationship("Project", back_populates="tracks")
    devices = relationship(
        "Device", back_populates="track", cascade="all, delete-orphan"
    )
    mixer_state = relationship(
        "TrackMixerState",
        back_populates="track",
        uselist=False,
        cascade="all, delete-orphan",
    )
    clips = relationship("Clip", back_populates="track", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_id = Column(
        Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    device_index = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    class_name = Column(String, nullable=False)
    track = relationship("Track", back_populates="devices")
    parameters = relationship(
        "Parameter", back_populates="device", cascade="all, delete-orphan"
    )


class Parameter(Base):
    __tablename__ = "parameters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    param_index = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    value_string = Column(
        String, nullable=True
    )  # Human-readable value (e.g., "-12 dB")
    min_value = Column(Float, nullable=False)
    max_value = Column(Float, nullable=False)
    device = relationship("Device", back_populates="parameters")


class TrackMixerState(Base):
    __tablename__ = "track_mixer_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_id = Column(
        Integer,
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    volume = Column(Float, nullable=False)  # 0-1 normalized
    panning = Column(Float, nullable=False)  # -1 to 1
    mute = Column(Boolean, nullable=False)
    solo = Column(Boolean, nullable=False)
    arm = Column(Boolean, nullable=False)
    is_grouped = Column(Boolean, nullable=False)
    has_midi_input = Column(Boolean, nullable=False)
    has_audio_output = Column(Boolean, nullable=False)
    output_routing = Column(String, nullable=True)
    track = relationship("Track", back_populates="mixer_state")


class Clip(Base):
    __tablename__ = "clips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_id = Column(
        Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    clip_index = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    length_beats = Column(Float, nullable=False)
    is_midi = Column(Boolean, nullable=False)
    loop_start = Column(Float, nullable=False, default=0.0)  # in beats
    loop_end = Column(Float, nullable=False, default=0.0)  # in beats
    gain = Column(Float, nullable=False, default=0.0)  # raw gain value
    track = relationship("Track", back_populates="clips")
    notes = relationship(
        "ClipNote", back_populates="clip", cascade="all, delete-orphan"
    )


class ClipNote(Base):
    __tablename__ = "clip_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clip_id = Column(
        Integer, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False
    )
    pitch = Column(Integer, nullable=False)  # MIDI pitch 0-127
    start_time = Column(Float, nullable=False)  # in beats
    duration = Column(Float, nullable=False)  # in beats
    velocity = Column(Integer, nullable=False)  # 0-127
    mute = Column(Boolean, nullable=False, default=False)
    clip = relationship("Clip", back_populates="notes")


class SongContext(Base):
    __tablename__ = "song_contexts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    tempo = Column(Float, nullable=False)
    time_sig_numerator = Column(Integer, nullable=False)
    time_sig_denominator = Column(Integer, nullable=False)
    num_tracks = Column(Integer, nullable=False)
    num_returns = Column(Integer, nullable=False)
    project = relationship("Project", back_populates="song_context")


class ChatSession(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(Integer, nullable=False)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    messages = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan"
    )
    project = relationship("Project", back_populates="sessions")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    text = Column(Text, nullable=False)
    is_user = Column(Boolean, nullable=False)
    type = Column(Enum("text", "tool", "error", name="message_type"), default="text")
    timestamp = Column(Integer, nullable=False)
    session = relationship("ChatSession", back_populates="messages")


class ParameterChange(Base):
    __tablename__ = "parameter_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    track_id = Column(Integer, nullable=False)
    track_name = Column(String, nullable=False)
    device_id = Column(Integer, nullable=False)
    device_name = Column(String, nullable=False)
    param_id = Column(Integer, nullable=False)
    param_name = Column(String, nullable=False)
    old_value = Column(Float, nullable=False)
    new_value = Column(Float, nullable=False)
    min_value = Column(Float, nullable=False)
    max_value = Column(Float, nullable=False)
    timestamp = Column(Integer, nullable=False)


def init_db():
    from ..db import Base, engine

    # Only create tables that don't exist (preserves data between restarts)
    Base.metadata.create_all(engine)
