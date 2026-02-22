"""IndexingService: coordinates Ableton OSC queries, DB persistence, and WebSocket progress."""

from fastapi import WebSocket

from .ableton import AbletonClient
from .db.ableton_repository import AbletonRepository
from .db.project_repository import ProjectRepository
from .logger import logger
from .models import DeviceData, TrackData


class IndexingService:
    def __init__(
        self,
        ableton: AbletonClient,
        project_repo: ProjectRepository,
        ableton_repo: AbletonRepository,
    ):
        self.ableton = ableton
        self.project_repo = project_repo
        self.ableton_repo = ableton_repo

    async def index_project(
        self, project_id: int, websocket: WebSocket
    ) -> list[TrackData]:
        """Index project from Ableton, persist to DB, stream progress over websocket.

        Returns the indexed project structure so the caller can start sync listeners.
        Raises on failure after sending an error message over the websocket.
        """
        await websocket.send_json(
            {"type": "indexing_status", "content": {"isIndexing": True, "progress": 5}}
        )

        song_context = await self.ableton.get_song_context()
        self.project_repo.save_song_context(project_id, song_context)
        num_tracks = song_context.num_tracks
        logger.info(f"[INDEXING] Project {project_id}: {num_tracks} tracks to index")

        await websocket.send_json(
            {"type": "indexing_status", "content": {"isIndexing": True, "progress": 10}}
        )

        track_names = await self.ableton.query_with_retry(
            "/live/song/get/track_data", [0, num_tracks, "track.name"]
        )

        existing_track_indices = {
            t.id for t in self.ableton_repo.load_project_structure(project_id)
        }
        if existing_track_indices:
            logger.info(
                f"[INDEXING] Resuming: {len(existing_track_indices)} tracks already indexed, "
                f"{num_tracks - len(existing_track_indices)} remaining"
            )

        await websocket.send_json(
            {"type": "indexing_status", "content": {"isIndexing": True, "progress": 15}}
        )

        for track_index, track_name in enumerate(track_names):
            if track_index in existing_track_indices:
                continue
            track_data = await self._index_single_track(track_index, track_name)
            self.ableton_repo.save_project_structure(project_id, [track_data])
            progress = 15 + int(75 * (track_index + 1) / num_tracks)
            await websocket.send_json(
                {
                    "type": "indexing_status",
                    "content": {"isIndexing": True, "progress": progress},
                }
            )

        self.project_repo.update_project_indexed_at(project_id)

        tracks_for_frontend = self.ableton_repo.get_project_tracks_for_frontend(
            project_id
        )
        await websocket.send_json(
            {
                "type": "tracks",
                "content": [t.model_dump(by_alias=True) for t in tracks_for_frontend],
            }
        )
        await websocket.send_json(
            {"type": "indexing_status", "content": {"isIndexing": False}}
        )

        project_data = self.ableton_repo.load_project_structure(project_id)
        logger.info(f"[INDEXING] Completed for project {project_id}")
        return project_data

    async def _index_single_track(self, track_index: int, track_name: str) -> TrackData:
        """Index a single track's devices and parameters."""
        track_num_devices = (
            await self.ableton.query_with_retry(
                "/live/track/get/num_devices", [track_index]
            )
        )[1]

        devices: list[DeviceData] = []

        if track_num_devices > 0:
            device_names = await self.ableton.query_with_retry(
                "/live/track/get/devices/name", [track_index]
            )
            device_classes = await self.ableton.query_with_retry(
                "/live/track/get/devices/class_name", [track_index]
            )

            logger.info(
                f"[INDEXING] Track '{track_name}' has {track_num_devices} devices"
            )

            for device_index, device_name in enumerate(device_names[1:]):
                params = await self.ableton.get_parameters(
                    track_index, device_index, include_value_string=True
                )
                device = DeviceData(
                    id=device_index,
                    name=device_name,
                    class_name=device_classes[device_index + 1],
                    parameters=params,
                )
                devices.append(device)
                logger.info(f"[INDEXING] device_data: {device}")
        else:
            logger.debug(f"[INDEXING] Track {track_name} has no devices")

        return TrackData(id=track_index, name=track_name, devices=devices)
