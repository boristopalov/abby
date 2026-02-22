import time
from typing import List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from ..models import SongContext
from . import get_db
from .models import (
    Project,
)
from .models import (
    SongContext as SongContextModel,
)


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_project(self, name: str) -> Project:
        project = Project(name=name, indexed_at=None)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_project(self, project_id: int) -> Optional[Project]:
        return self.db.query(Project).filter(Project.id == project_id).first()

    def get_project_by_name(self, name: str) -> Optional[Project]:
        return self.db.query(Project).filter(Project.name == name).first()

    def get_all_projects(self) -> List[Project]:
        return self.db.query(Project).all()

    def delete_project(self, project_id: int) -> None:
        self.db.query(Project).filter(Project.id == project_id).delete()
        self.db.commit()

    def update_project_indexed_at(self, project_id: int) -> None:
        timestamp = int(time.time() * 1000)
        self.db.query(Project).filter(Project.id == project_id).update(
            {"indexed_at": timestamp}
        )
        self.db.commit()

    def clear_project_indexed_at(self, project_id: int) -> None:
        self.db.query(Project).filter(Project.id == project_id).update(
            {"indexed_at": None}
        )
        self.db.commit()

    def save_song_context(self, project_id: int, context: SongContext) -> None:
        """Save song context (tempo, time sig, counts) for a project."""
        existing = (
            self.db.query(SongContextModel)
            .filter(SongContextModel.project_id == project_id)
            .first()
        )
        if existing:
            existing.tempo = context.tempo
            existing.time_sig_numerator = context.time_sig_numerator
            existing.time_sig_denominator = context.time_sig_denominator
            existing.num_tracks = context.num_tracks
        else:
            self.db.add(
                SongContextModel(
                    project_id=project_id,
                    tempo=context.tempo,
                    time_sig_numerator=context.time_sig_numerator,
                    time_sig_denominator=context.time_sig_denominator,
                    num_tracks=context.num_tracks,
                )
            )
        self.db.commit()

    def get_song_context(self, project_id: int) -> SongContext | None:
        """Get song context for a project."""
        row = (
            self.db.query(SongContextModel)
            .filter(SongContextModel.project_id == project_id)
            .first()
        )
        if not row:
            return None
        return SongContext(
            tempo=row.tempo,
            time_sig_numerator=row.time_sig_numerator,
            time_sig_denominator=row.time_sig_denominator,
            num_tracks=row.num_tracks,
        )


def get_project_repository(db: Session = Depends(get_db)) -> ProjectRepository:
    return ProjectRepository(db)
