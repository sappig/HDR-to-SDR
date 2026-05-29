from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Folder
from ..schemas import FolderCreate, FolderRead

router = APIRouter(prefix="/folders", tags=["folders"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=list[FolderRead])
def list_folders(db: Session = Depends(get_db)):
    return db.query(Folder).order_by(Folder.created_at.asc()).all()


@router.post("", response_model=FolderRead)
def create_folder(folder: FolderCreate, request: Request, db: Session = Depends(get_db)):
    existing = db.query(Folder).filter(Folder.path == folder.path).first()
    if existing:
        return existing
    db_folder = Folder(path=folder.path, enabled=folder.enabled, created_at=datetime.utcnow())
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    monitor = getattr(request.app.state, "monitor", None)
    if monitor:
        monitor.watch_folder(db_folder)
        monitor.scan_folder(db_folder)
    return db_folder


@router.post("/{folder_id}/toggle")
def toggle_folder(folder_id: int, request: Request, db: Session = Depends(get_db)):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    folder.enabled = not folder.enabled
    db.commit()
    monitor = getattr(request.app.state, "monitor", None)
    if monitor:
        if folder.enabled:
            monitor.watch_folder(folder)
            monitor.scan_folder(folder)
        elif folder.id in monitor.watchers:
            monitor.observer.unschedule(monitor.watchers[folder.id])
            del monitor.watchers[folder.id]
    return folder


@router.delete("/{folder_id}")
def delete_folder(folder_id: int, request: Request, db: Session = Depends(get_db)):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    monitor = getattr(request.app.state, "monitor", None)
    if monitor and folder.id in monitor.watchers:
        monitor.observer.unschedule(monitor.watchers[folder.id])
        del monitor.watchers[folder.id]
    db.delete(folder)
    db.commit()
    return {"deleted": True}
