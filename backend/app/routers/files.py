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
    return db.query(MediaFile).order_by(MediaFile.scanned_at.desc()).all()


@router.get("/{file_id}")
def get_file(file_id: int, db: Session = Depends(get_db)):
    media_file = db.query(MediaFile).filter(MediaFile.id == file_id).first()
    if not media_file:
        raise HTTPException(status_code=404, detail="File not found")
    return media_file
