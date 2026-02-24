"""Sync service to keep DB in sync with Ableton via OSC listeners."""

from .ableton_client import AbletonClient
from .db import SessionLocal
from .db.ableton_repository import AbletonRepository
from .logger import logger
from .models import TrackData


class SyncService:
    """Keeps DB in sync with Ableton via OSC listeners.

    Registers listeners for all parameters in a project and updates
    the DB when parameter values change in Ableton.
    """

    def __init__(self, ableton_client: AbletonClient):
        self.client = ableton_client
        self.active_project_id: int | None = None
        self._listeners: list[tuple[int, int, int]] = []  # (track, device, param)

    def start_listeners(self, project_id: int, project_data: list[TrackData]) -> None:
        """Start listening to all parameters for a project.

        Args:
            project_id: The project ID in the DB
            project_data: List of TrackData with devices and parameters
        """
        # if self.active_project_id is not None:
        #     self.stop_listeners()

        # self.active_project_id = project_id
        # logger.info(f"[SYNC] Starting parameter listeners for project {project_id}")

        # self.client.set_parameter_change_handler(self._on_parameter_changed)

        # for track_data in project_data:
        #     track_id = track_data.id
        #     for device_data in track_data.devices:
        #         device_id = device_data.id
        #         for param_data in device_data.parameters:
        #             param_id = param_data.id
        #             self.client.start_parameter_listener(track_id, device_id, param_id)
        #             self._listeners.append((track_id, device_id, param_id))

        # logger.info(f"[SYNC] Started {len(self._listeners)} parameter listeners")

    def stop_listeners(self) -> None:
        """Stop all active listeners."""
        if not self._listeners:
            return

        logger.info(f"[SYNC] Stopping {len(self._listeners)} parameter listeners")

        for track_id, device_id, param_id in self._listeners:
            self.client.stop_parameter_listener(track_id, device_id, param_id)

        self._listeners.clear()
        self.active_project_id = None

    def _on_parameter_changed(self, address: str, *args) -> None:
        """Handle incoming parameter value change from Ableton.

        AbletonOSC sends updates on:
        - /live/device/get/parameter/value [track_id, device_id, param_id, value]

        We write to the DB immediately on value; value_string is not tracked via
        push events (it is captured during indexing).
        """
        if self.active_project_id is None:
            return

        if address != "/live/device/get/parameter/value":
            return

        if len(args) == 1 and isinstance(args[0], tuple):
            args = args[0]

        if len(args) < 4:
            logger.warning(f"[SYNC] Unexpected args for {address}: {args}")
            return

        track_id = int(args[0])
        device_id = int(args[1])
        param_id = int(args[2])
        value = float(args[3])
        logger.info(
            f"[SYNC] Received value update: ({track_id}, {device_id}, {param_id}) = {value}"
        )
        self._write_value(track_id, device_id, param_id, value)

    def _write_value(
        self, track_id: int, device_id: int, param_id: int, value: float
    ) -> None:
        """Write a parameter value update to the DB."""
        if self.active_project_id is None:
            return

        db = SessionLocal()
        try:
            ableton_repo = AbletonRepository(db)
            ableton_repo.update_parameter_value(
                self.active_project_id,
                track_id,
                device_id,
                param_id,
                value,
            )
        except LookupError as e:
            logger.warning(f"[SYNC] Parameter not in DB: {e}")
        except Exception as e:
            logger.error(f"[SYNC] Error updating DB: {e}")
        finally:
            db.close()


_sync_service: SyncService | None = None


def get_sync_service(ableton_client: AbletonClient) -> SyncService:
    """Get or create the sync service singleton."""
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService(ableton_client)
    return _sync_service
