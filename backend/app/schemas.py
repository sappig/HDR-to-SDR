from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class FolderCreate(BaseModel):
    path: str
    enabled: bool = True


class FolderRead(FolderCreate):
    id: int
    created_at: datetime


class MediaFileRead(BaseModel):
    id: int
    folder_id: int
    path: str
    filename: str
    file_size: int
    resolution: Optional[str]
    codec: Optional[str]
    bitrate: Optional[int]
    audio_tracks: Optional[int]
    subtitle_tracks: Optional[int]
    hdr_detected: bool
    hdr_type: Optional[str]
    scanned_at: datetime
    status: str
    scan_error: Optional[str]
    output_path: Optional[str]
    metadata: Optional[str]


class QueueItemRead(BaseModel):
    id: int
    media_file_id: int
    priority: int
    sort_order: int
    state: str
    progress: float
    paused: bool
    eta_seconds: Optional[int]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    log_path: Optional[str]
    last_error: Optional[str]


class QueueReorderRequest(BaseModel):
    order: List[int]


class SettingsRead(BaseModel):
    max_concurrent_transcodes: int
    software_fallback: bool
    output_bitrate: int
    output_resolution: str
    plex_transcoder_path: Optional[str]
    scan_interval: int
    log_retention_days: int
    qsv_available: bool
    qsv_device: Optional[str]
    detected_plex_version: Optional[str]


class SettingsUpdate(BaseModel):
    max_concurrent_transcodes: Optional[int] = None
    software_fallback: Optional[bool] = None
    output_bitrate: Optional[int] = None
    output_resolution: Optional[str] = None
    plex_transcoder_path: Optional[str] = None
    scan_interval: Optional[int] = None
    log_retention_days: Optional[int] = None
