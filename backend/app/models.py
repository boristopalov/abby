from pydantic import BaseModel, ConfigDict, Field


class ParameterData(BaseModel):
    id: int  # param_index (0-based position in device)
    name: str
    value: float
    value_string: str | None = None
    min: float
    max: float


class DeviceData(BaseModel):
    id: int  # device_index (0-based position in track)
    name: str
    class_name: str
    parameters: list[ParameterData] = []


class TrackData(BaseModel):
    id: int  # track_index (0-based position in song)
    name: str
    devices: list[DeviceData] = []


class TrackDevice(BaseModel):
    index: int
    name: str
    class_name: str


class TrackDevices(BaseModel):
    index: int
    name: str
    devices: list[TrackDevice] = []


class DeviceParameters(BaseModel):
    """Device parameters result, replaces (device_name, track_name, list[dict]) tuple."""

    device_name: str
    track_name: str
    parameters: list[ParameterData]


class SongContext(BaseModel):
    tempo: float
    time_sig_numerator: int
    time_sig_denominator: int
    num_tracks: int


class TrackMixerState(BaseModel):
    volume: float  # 0-1 normalized
    panning: float  # -1 to 1
    mute: bool
    solo: bool
    arm: bool
    is_grouped: bool
    has_midi_input: bool
    has_audio_output: bool
    output_routing: str | None = None
    sends: list[float] = []


class ClipInfo(BaseModel):
    """Clip data as received from Ableton OSC, used as input to save_clip."""

    clip_id: int  # 0-based clip slot index
    name: str
    length_beats: float
    is_midi: bool
    loop_start: float
    loop_end: float
    gain: float


class ClipData(BaseModel):
    """Clip data as stored in DB."""

    id: int  # DB primary key
    clip_index: int  # 0-based clip slot index
    name: str
    length_beats: float
    is_midi: bool
    loop_start: float
    loop_end: float
    gain: float


class Note(BaseModel):
    pitch: int  # MIDI pitch 0-127
    start_time: float  # in beats
    duration: float  # in beats
    velocity: int  # 0-127
    mute: bool = False


class ClipNotes(BaseModel):
    clip_name: str
    notes: list[Note]


class ParameterChangeRecord(BaseModel):
    track_id: int
    track_name: str
    device_id: int
    device_name: str
    param_id: int
    param_name: str
    old_value: float
    new_value: float
    min: float
    max: float
    timestamp: int  # Unix ms


class ProjectIndex(BaseModel):
    """Full project data returned from Ableton indexing."""

    song_context: SongContext
    tracks: list[TrackData]


class DeviceFrontendInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str
    class_name: str = Field(serialization_alias="className")


class TrackFrontendInfo(BaseModel):
    id: int
    name: str
    devices: list[DeviceFrontendInfo] = []


class TrackInfo(BaseModel):
    index: int
    name: str
    is_foldable: bool | None = None  # True = group track
    is_audio_track: bool | None = None
    is_midi_track: bool | None = None
    mute: bool | None = None
    solo: bool | None = None
    arm: bool | None = None
    volume: float
    panning: float
    devices: list[TrackDevice] = []
    clip_slot_count: int = 0


class TrackSummary(BaseModel):
    index: int
    name: str
    type: str  # "group", "midi", "audio"
    is_grouped: bool  # True = nested inside a group track


class TrackStructure(BaseModel):
    tracks: list[TrackSummary]


class ArrangementClip(BaseModel):
    name: str
    start_time: float   # beats
    end_time: float     # beats
    length: float       # beats
    is_midi: bool


class TrackArrangementClips(BaseModel):
    track_index: int
    track_name: str
    clips: list[ArrangementClip] = []
