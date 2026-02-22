import time

from fastapi import Depends
from sqlalchemy.orm import Session

from ..logger import logger
from ..models import (
    ClipData,
    ClipInfo,
    ClipNotes,
    DeviceData,
    DeviceFrontendInfo,
    DeviceParameters,
    Note,
    ParameterChangeRecord,
    ParameterData,
    TrackData,
    TrackDeviceSummary,
    TrackFrontendInfo,
    TrackMixerState,
)
from . import get_db
from .models import (
    Clip,
    ClipNote,
    Device,
    Parameter,
    ParameterChange,
    Track,
)
from .models import (
    TrackMixerState as TrackMixerStateModel,
)


class AbletonRepository:
    def __init__(self, db: Session):
        self.db = db

    def clear_project_structure(self, project_id: int) -> None:
        """Clear all tracks, devices, and parameters for a project (for re-indexing)."""
        self.db.query(Track).filter(Track.project_id == project_id).delete()
        self.db.commit()

    def save_project_structure(self, project_id: int, tracks: list[TrackData]) -> None:
        """Save tracks, devices, and parameters for a project."""
        for track_data in tracks:
            track = Track(
                project_id=project_id,
                track_index=track_data.id,
                name=track_data.name,
            )
            self.db.add(track)
            self.db.flush()

            for device_data in track_data.devices:
                device = Device(
                    track_id=track.id,
                    device_index=device_data.id,
                    name=device_data.name,
                    class_name=device_data.class_name,
                )
                self.db.add(device)
                self.db.flush()

                for param_data in device_data.parameters:
                    param = Parameter(
                        device_id=device.id,
                        param_index=param_data.id,
                        name=param_data.name,
                        value=param_data.value,
                        value_string=param_data.value_string,
                        min_value=param_data.min,
                        max_value=param_data.max,
                    )
                    self.db.add(param)

        self.db.commit()

    def load_project_structure(self, project_id: int) -> list[TrackData]:
        """Load tracks, devices, and parameters for a project."""
        tracks = (
            self.db.query(Track)
            .filter(Track.project_id == project_id)
            .order_by(Track.track_index)
            .all()
        )

        result: list[TrackData] = []
        for track in tracks:
            devices = (
                self.db.query(Device)
                .filter(Device.track_id == track.id)
                .order_by(Device.device_index)
                .all()
            )

            device_list: list[DeviceData] = []
            for device in devices:
                params = (
                    self.db.query(Parameter)
                    .filter(Parameter.device_id == device.id)
                    .order_by(Parameter.param_index)
                    .all()
                )

                device_list.append(
                    DeviceData(
                        id=device.device_index,
                        name=device.name,
                        class_name=device.class_name,
                        parameters=[
                            ParameterData(
                                id=p.param_index,
                                name=p.name,
                                value=p.value,
                                value_string=p.value_string,
                                min=p.min_value,
                                max=p.max_value,
                            )
                            for p in params
                        ],
                    )
                )

            result.append(
                TrackData(id=track.track_index, name=track.name, devices=device_list)
            )

        return result

    def get_project_tracks_for_frontend(
        self, project_id: int
    ) -> list[TrackFrontendInfo]:
        """Load tracks and devices in frontend format (without parameters)."""
        tracks = (
            self.db.query(Track)
            .filter(Track.project_id == project_id)
            .order_by(Track.track_index)
            .all()
        )

        result: list[TrackFrontendInfo] = []
        for track in tracks:
            devices = (
                self.db.query(Device)
                .filter(Device.track_id == track.id)
                .order_by(Device.device_index)
                .all()
            )

            result.append(
                TrackFrontendInfo(
                    id=track.track_index,
                    name=track.name,
                    devices=[
                        DeviceFrontendInfo(
                            id=device.device_index,
                            name=device.name,
                            class_name=device.class_name,
                        )
                        for device in devices
                    ],
                )
            )

        return result

    def get_track_devices_summary(
        self, project_id: int, track_index: int
    ) -> TrackDeviceSummary | None:
        """Get track name and device names for a track (for agent)."""
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        devices = (
            self.db.query(Device)
            .filter(Device.track_id == track.id)
            .order_by(Device.device_index)
            .all()
        )

        return TrackDeviceSummary(
            name=track.name,
            devices=[d.name for d in devices],
        )

    def get_device_parameters(
        self, project_id: int, track_index: int, device_index: int
    ) -> DeviceParameters | None:
        """Get all parameters for a device with value_string (for agent)."""
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        device = (
            self.db.query(Device)
            .filter(Device.track_id == track.id, Device.device_index == device_index)
            .first()
        )
        if not device:
            return None

        params = (
            self.db.query(Parameter)
            .filter(Parameter.device_id == device.id)
            .order_by(Parameter.param_index)
            .all()
        )

        return DeviceParameters(
            device_name=device.name,
            track_name=track.name,
            parameters=[
                ParameterData(
                    id=p.param_index,
                    name=p.name,
                    value=p.value,
                    value_string=p.value_string,
                    min=p.min_value,
                    max=p.max_value,
                )
                for p in params
            ],
        )

    def update_parameter_value(
        self,
        project_id: int,
        track_index: int,
        device_index: int,
        param_index: int,
        value: float,
        value_string: str | None = None,
    ) -> None:
        """Update a parameter's value and value_string in the DB.

        Also logs the change to the ParameterChange table for history tracking.

        Raises LookupError if the track, device, or parameter is not found.
        """
        row = (
            self.db.query(Parameter, Device, Track)
            .join(Device, Parameter.device_id == Device.id)
            .join(Track, Device.track_id == Track.id)
            .filter(
                Track.project_id == project_id,
                Track.track_index == track_index,
                Device.device_index == device_index,
                Parameter.param_index == param_index,
            )
            .first()
        )
        if not row:
            raise LookupError(
                f"Parameter not found: track={track_index}, device={device_index}, "
                f"param={param_index} in project {project_id}"
            )
        param, device, track = row

        value_changed = abs(value - param.value) > 0.0001
        string_changed = value_string is not None and value_string != param.value_string

        if not value_changed and not string_changed:
            logger.debug(
                f"[DB] Skipping parameter update (unchanged): "
                f"track={track_index}, device={device_index}, param={param_index}"
            )
            return

        logger.info(
            f"[DB] Updating parameter: track={track_index}, device={device_index}, "
            f"param={param_index}, value={param.value}->{value}, "
            f"value_string={param.value_string}->{value_string}"
        )

        if value_changed:
            change = ParameterChange(
                project_id=project_id,
                track_id=track_index,
                track_name=track.name,
                device_id=device_index,
                device_name=device.name,
                param_id=param_index,
                param_name=param.name,
                old_value=param.value,
                new_value=value,
                min_value=param.min_value,
                max_value=param.max_value,
                timestamp=int(time.time() * 1000),
            )
            self.db.add(change)
            param.value = value

        if string_changed:
            param.value_string = value_string

        self.db.commit()

    def get_parameter_changes_since(
        self, project_id: int, since_timestamp: int
    ) -> list[ParameterChangeRecord]:
        """Get parameter changes for a project since a given timestamp."""
        changes = (
            self.db.query(ParameterChange)
            .filter(
                ParameterChange.project_id == project_id,
                ParameterChange.timestamp > since_timestamp,
            )
            .order_by(ParameterChange.timestamp.asc())
            .all()
        )

        return [
            ParameterChangeRecord(
                track_id=c.track_id,
                track_name=c.track_name,
                device_id=c.device_id,
                device_name=c.device_name,
                param_id=c.param_id,
                param_name=c.param_name,
                old_value=c.old_value,
                new_value=c.new_value,
                min=c.min_value,
                max=c.max_value,
                timestamp=c.timestamp,
            )
            for c in changes
        ]

    def get_recent_parameter_changes(
        self, limit: int = 100
    ) -> list[ParameterChangeRecord]:
        changes = (
            self.db.query(ParameterChange)
            .order_by(ParameterChange.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            ParameterChangeRecord(
                track_id=c.track_id,
                track_name=c.track_name,
                device_id=c.device_id,
                device_name=c.device_name,
                param_id=c.param_id,
                param_name=c.param_name,
                old_value=c.old_value,
                new_value=c.new_value,
                min=c.min_value,
                max=c.max_value,
                timestamp=c.timestamp,
            )
            for c in changes
        ]

    def save_track_mixer_state(
        self, project_id: int, track_index: int, mixer: TrackMixerState
    ) -> None:
        """Save mixer state for a track."""
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return

        existing = (
            self.db.query(TrackMixerStateModel)
            .filter(TrackMixerStateModel.track_id == track.id)
            .first()
        )
        if existing:
            existing.volume = mixer.volume
            existing.panning = mixer.panning
            existing.mute = mixer.mute
            existing.solo = mixer.solo
            existing.arm = mixer.arm
            existing.is_grouped = mixer.is_grouped
            existing.has_midi_input = mixer.has_midi_input
            existing.has_audio_output = mixer.has_audio_output
            existing.output_routing = mixer.output_routing
        else:
            self.db.add(
                TrackMixerStateModel(
                    track_id=track.id,
                    volume=mixer.volume,
                    panning=mixer.panning,
                    mute=mixer.mute,
                    solo=mixer.solo,
                    arm=mixer.arm,
                    is_grouped=mixer.is_grouped,
                    has_midi_input=mixer.has_midi_input,
                    has_audio_output=mixer.has_audio_output,
                    output_routing=mixer.output_routing,
                )
            )
        self.db.commit()

    def save_clip(
        self, project_id: int, track_index: int, clip: ClipInfo
    ) -> int | None:
        """Save or update a single clip. Returns the Clip's database ID, or None if track not found."""
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        existing_clip = (
            self.db.query(Clip)
            .filter(Clip.track_id == track.id, Clip.clip_index == clip.clip_id)
            .first()
        )

        if existing_clip:
            existing_clip.name = clip.name
            existing_clip.length_beats = clip.length_beats
            existing_clip.is_midi = clip.is_midi
            existing_clip.loop_start = clip.loop_start
            existing_clip.loop_end = clip.loop_end
            existing_clip.gain = clip.gain
            self.db.commit()
            return existing_clip.id
        else:
            new_clip = Clip(
                track_id=track.id,
                clip_index=clip.clip_id,
                name=clip.name,
                length_beats=clip.length_beats,
                is_midi=clip.is_midi,
                loop_start=clip.loop_start,
                loop_end=clip.loop_end,
                gain=clip.gain,
            )
            self.db.add(new_clip)
            self.db.commit()
            return new_clip.id

    def get_clip(
        self, project_id: int, track_index: int, clip_index: int
    ) -> ClipData | None:
        """Get a single clip by track and clip index."""
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        clip = (
            self.db.query(Clip)
            .filter(Clip.track_id == track.id, Clip.clip_index == clip_index)
            .first()
        )
        if not clip:
            return None

        return ClipData(
            id=clip.id,
            clip_index=clip.clip_index,
            name=clip.name,
            length_beats=clip.length_beats,
            is_midi=clip.is_midi,
            loop_start=clip.loop_start,
            loop_end=clip.loop_end,
            gain=clip.gain,
        )

    def get_track_clips(
        self, project_id: int, track_index: int
    ) -> list[ClipData] | None:
        """Get all clips for a track. Returns list of ClipData or None if track not found."""
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        clips = (
            self.db.query(Clip)
            .filter(Clip.track_id == track.id)
            .order_by(Clip.clip_index)
            .all()
        )

        return [
            ClipData(
                id=clip.id,
                clip_index=clip.clip_index,
                name=clip.name,
                length_beats=clip.length_beats,
                is_midi=clip.is_midi,
                loop_start=clip.loop_start,
                loop_end=clip.loop_end,
                gain=clip.gain,
            )
            for clip in clips
        ]

    def save_clip_notes(self, clip_id: int, notes: list[Note]) -> None:
        """Save MIDI notes for a clip. Clears existing notes and saves new ones."""
        self.db.query(ClipNote).filter(ClipNote.clip_id == clip_id).delete()

        for note in notes:
            self.db.add(
                ClipNote(
                    clip_id=clip_id,
                    pitch=note.pitch,
                    start_time=note.start_time,
                    duration=note.duration,
                    velocity=note.velocity,
                    mute=note.mute,
                )
            )

        self.db.commit()

    def get_clip_notes(
        self, project_id: int, track_index: int, clip_index: int
    ) -> ClipNotes | None:
        """Get notes for a specific clip."""
        track = (
            self.db.query(Track)
            .filter(Track.project_id == project_id, Track.track_index == track_index)
            .first()
        )
        if not track:
            return None

        clip = (
            self.db.query(Clip)
            .filter(Clip.track_id == track.id, Clip.clip_index == clip_index)
            .first()
        )
        if not clip:
            return None

        notes = (
            self.db.query(ClipNote)
            .filter(ClipNote.clip_id == clip.id)
            .order_by(ClipNote.start_time)
            .all()
        )

        return ClipNotes(
            clip_name=clip.name,
            notes=[
                Note(
                    pitch=note.pitch,
                    start_time=note.start_time,
                    duration=note.duration,
                    velocity=note.velocity,
                    mute=note.mute,
                )
                for note in notes
            ],
        )


def get_ableton_repository(db: Session = Depends(get_db)) -> AbletonRepository:
    return AbletonRepository(db)
