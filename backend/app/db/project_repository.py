from typing import List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from . import get_db
from .models import (
    Project,
)


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_project(self, name: str) -> Project:
        project = Project(name=name)
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


def get_project_repository(db: Session = Depends(get_db)) -> ProjectRepository:
    return ProjectRepository(db)
