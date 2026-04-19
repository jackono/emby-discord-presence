from dataclasses import dataclass


@dataclass
class PlaybackState:
    session_id: str
    media_type: str
    title: str
    series: str | None
    season: int | None
    episode: int | None
    year: int | None
    paused: bool
    position_seconds: float
    duration_seconds: float
    device_name: str
    client_name: str
