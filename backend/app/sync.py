"""Sync service to keep DB in sync with Ableton via OSC listeners."""

from .ableton import AbletonClient
from .db import SessionLocal
from .db.db_service import DBService
from .logger import logger


class SyncService:
    """Keeps DB in sync with Ableton via OSC listeners.

    Registers listeners for all parameters in a project and updates
    the DB when parameter values change in Ableton.
    """

    def __init__(self, ableton_client: AbletonClient):
        self.client = ableton_client
        self.active_project_id: int | None = None
        self._listeners: list[tuple[int, int, int]] = []  # (track, device, param)
        self._pending_values: dict[tuple[int, int, int], float] = {}
        self._pending_strings: dict[tuple[int, int, int], str] = {}

    def start_listeners(self, project_id: int, project_data: list[dict]) -> None:
        """Start listening to all parameters for a project.

        Args:
            project_id: The project ID in the DB
            project_data: List of track dicts with devices and parameters
        """

        # Skip if we are already listening for this project (might change this later)
        if self.active_project_id is not None:
            self.stop_listeners()

        self.active_project_id = project_id
        logger.info(f"[SYNC] Starting parameter listeners for project {project_id}")

        # Register our handler for parameter changes
        self.client.set_parameter_change_handler(self._on_parameter_changed)

        # Start listening to each parameter
        for track_data in project_data:
            track_id = track_data["id"]
            for device_data in track_data.get("devices", []):
                device_id = device_data["id"]
                for param_data in device_data.get("parameters", []):
                    param_id = param_data["id"]
                    self.client.start_parameter_listener(track_id, device_id, param_id)
                    self._listeners.append((track_id, device_id, param_id))

        logger.info(f"[SYNC] Started {len(self._listeners)} parameter listeners")

    def stop_listeners(self) -> None:
        """Stop all active listeners."""
        if not self._listeners:
            return

        logger.info(f"[SYNC] Stopping {len(self._listeners)} parameter listeners")

        for track_id, device_id, param_id in self._listeners:
            self.client.stop_parameter_listener(track_id, device_id, param_id)

        self._listeners.clear()
        self._pending_values.clear()
        self._pending_strings.clear()
        self.active_project_id = None

    def _on_parameter_changed(self, address: str, *args) -> None:
        """Handle incoming parameter change from Ableton.

        AbletonOSC sends updates on:
        - /live/device/get/parameter/value [track_id, device_id, param_id, value]
        - /live/device/get/parameter/value_string [track_id, device_id, param_id, value_string]

        We need both to update the DB, so we accumulate them and flush when we have both.
        """
        if self.active_project_id is None:
            return

        # OSC library may wrap args in a tuple - unwrap if needed
        if len(args) == 1 and isinstance(args[0], tuple):
            args = args[0]

        if len(args) < 4:
            logger.warning(f"[SYNC] Unexpected args for {address}: {args}")
            return

        track_id = int(args[0])
        device_id = int(args[1])
        param_id = int(args[2])
        key = (track_id, device_id, param_id)

        if address == "/live/device/get/parameter/value":
            value = float(args[3])
            self._pending_values[key] = value
            logger.info(f"[SYNC] Received value update: {key} = {value}")
        elif address == "/live/device/get/parameter/value_string":
            value_string = str(args[3])
            self._pending_strings[key] = value_string
            logger.info(f"[SYNC] Received value_string update: {key} = {value_string}")

        # Check if we have both value and value_string for this parameter
        if key in self._pending_values and key in self._pending_strings:
            self._flush_parameter_update(key)

    def _flush_parameter_update(self, key: tuple[int, int, int]) -> None:
        """Write the accumulated parameter update to the DB."""
        if self.active_project_id is None:
            return

        track_id, device_id, param_id = key
        value = self._pending_values.pop(key)
        value_string = self._pending_strings.pop(key)

        # Create a new session for the DB update (we're on a separate thread)
        db = SessionLocal()
        try:
            db_service = DBService(db)
            success = db_service.update_parameter_value(
                self.active_project_id,
                track_id,
                device_id,
                param_id,
                value,
                value_string,
            )
            if not success:
                logger.warning(
                    f"[SYNC] Failed to update parameter: track={track_id}, "
                    f"device={device_id}, param={param_id}"
                )
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
