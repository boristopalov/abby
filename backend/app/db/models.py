from sqlalchemy import Boolean, Column, Integer, String, Float, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from ..db import Base, engine

class ChatSession(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(Integer, nullable=False)
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    is_user = Column(Boolean, nullable=False)
    type = Column(Enum("text", "tool", "error", name="message_type"), default="text")
    timestamp = Column(Integer, nullable=False)
    session = relationship("ChatSession", back_populates="messages")

class ParameterChange(Base):
    __tablename__ = "parameter_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
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

class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    system_prompt = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False) 

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)