from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    sessions: Mapped[list[ChatSession]] = relationship(back_populates="project")


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


def init_db():
    from ..db import Base, engine

    Base.metadata.create_all(engine)
