from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    media_files = relationship("MediaFile", back_populates="folder")


class MediaFile(Base):
    __tablename__ = "media_files"

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=False)
    path = Column(String, unique=True, nullable=False)
    filename = Column(String, nullable=False)
    file_size = Column(Integer, default=0, nullable=False)
    resolution = Column(String, nullable=True)
    codec = Column(String, nullable=True)
    bitrate = Column(Integer, nullable=True)
    audio_tracks = Column(Integer, nullable=True)
    subtitle_tracks = Column(Integer, nullable=True)
    hdr_detected = Column(Boolean, default=False, nullable=False)
    hdr_type = Column(String, nullable=True)
    scanned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String, default="Discovered", nullable=False)
    scan_error = Column(Text, nullable=True)
    output_path = Column(String, nullable=True)
    extra_metadata = Column(Text, nullable=True)

    folder = relationship("Folder", back_populates="media_files")


class QueueItem(Base):
    __tablename__ = "queue"

    id = Column(Integer, primary_key=True, index=True)
    media_file_id = Column(Integer, ForeignKey("media_files.id"), nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    state = Column(String, default="Pending", nullable=False)
    progress = Column(Float, default=0.0, nullable=False)
    paused = Column(Boolean, default=False, nullable=False)
    eta_seconds = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    log_path = Column(String, nullable=True)
    last_error = Column(Text, nullable=True)
    transcode_command = Column(Text, nullable=True)
    media_file = relationship("MediaFile")


class TranscodeHistory(Base):
    __tablename__ = "transcode_history"

    id = Column(Integer, primary_key=True, index=True)
    media_file_id = Column(Integer, ForeignKey("media_files.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    result = Column(String, nullable=True)
    log = Column(Text, nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)
