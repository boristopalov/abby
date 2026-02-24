from .ableton_client import AbletonClient
from .db.ableton_repository import AbletonRepository
from .db.project_repository import ProjectRepository
from .logger import logger
from .models import TrackData


class IndexingService:
    def __init__(
        self,
        ableton: AbletonClient,
        project_repo: ProjectRepository,
        ableton_repo: AbletonRepository,
    ):
        self.ableton: AbletonClient = ableton
        self.project_repo: ProjectRepository = project_repo
        self.ableton_repo: AbletonRepository = ableton_repo

    async def index_project(self, project_id: int) -> list[TrackData]:
        """Fetch project structure from Ableton and persist to DB.

        Returns the indexed project structure so the caller can start sync listeners.
        Raises on failure; the caller is responsible for sending error events.
        """
        # Single round trip replaces ~800 individual OSC calls.
        project = await self.ableton.get_project_index()

        self.project_repo.save_song_context(project_id, project.song_context)
        num_tracks = project.song_context.num_tracks
        logger.info(f"[INDEXING] Project {project_id}: {num_tracks} tracks to index")

        existing_track_indices = {
            t.id for t in self.ableton_repo.load_project_structure(project_id)
        }
        if existing_track_indices:
            logger.info(
                f"[INDEXING] Resuming: {len(existing_track_indices)} tracks already indexed, "
                f"{num_tracks - len(existing_track_indices)} remaining"
            )

        for track_data in project.tracks:
            if track_data.id in existing_track_indices:
                continue
            self.ableton_repo.save_project_structure(project_id, [track_data])

        self.project_repo.update_project_indexed_at(project_id)

        project_data = self.ableton_repo.load_project_structure(project_id)
        logger.info(f"[INDEXING] Completed for project {project_id}")
        return project_data
