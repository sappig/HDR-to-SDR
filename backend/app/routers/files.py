from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import MediaFile

router = APIRouter(prefix="/files", tags=["files"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def list_files(db: Session = Depends(get_db)):
    files = db.query(MediaFile).order_by(MediaFile.scanned_at.desc()).all()
    return [
        {
            "id": f.id,
            "folder_id": f.folder_id,
            "path": f.path,
            "filename": f.filename,
            "file_size": f.file_size,
            "resolution": f.resolution,
            "codec": f.codec,
            "bitrate": f.bitrate,
            "audio_tracks": f.audio_tracks,
            "subtitle_tracks": f.subtitle_tracks,
            "hdr_detected": f.hdr_detected,
            "hdr_type": f.hdr_type,
            "scanned_at": f.scanned_at,
            "status": f.status,
            "scan_error": f.scan_error,
            "output_path": f.output_path,
            "extra_metadata": f.extra_metadata,
        }
        for f in files
    ]


@router.get("/{file_id}")
def get_file(file_id: int, db: Session = Depends(get_db)):
    media_file = db.query(MediaFile).filter(MediaFile.id == file_id).first()
    if not media_file:
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "id": media_file.id,
        "folder_id": media_file.folder_id,
        "path": media_file.path,
        "filename": media_file.filename,
        "file_size": media_file.file_size,
        "resolution": media_file.resolution,
        "codec": media_file.codec,
        "bitrate": media_file.bitrate,
        "audio_tracks": media_file.audio_tracks,
        "subtitle_tracks": media_file.subtitle_tracks,
        "hdr_detected": media_file.hdr_detected,
        "hdr_type": media_file.hdr_type,
        "scanned_at": media_file.scanned_at,
        "status": media_file.status,
        "scan_error": media_file.scan_error,
        "output_path": media_file.output_path,
        "extra_metadata": media_file.extra_metadata,
    }
