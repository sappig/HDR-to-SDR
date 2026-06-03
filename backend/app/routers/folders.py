import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Folder
from ..schemas import DirectoryEntry, FolderCreate, FolderRead


BROWSE_ROOTS = [root.strip() for root in os.getenv("BROWSE_ROOTS", "/mnt/movies,/mnt/tv,/media").split(",") if root.strip()]
ALLOWED_ROOTS = [os.path.realpath(root) for root in BROWSE_ROOTS]


def resolve_and_validate_path(path: str) -> str:
    real_path = os.path.realpath(path)
    if not any(os.path.commonpath([real_path, root]) == root for root in ALLOWED_ROOTS):
        raise HTTPException(status_code=400, detail="Path is not within allowed browse roots")
    return real_path

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


@router.get("/browse", response_model=list[DirectoryEntry])
def browse_folders(path: str | None = Query(default=None, description="Path to browse")):
    if path is None:
        entries = []
        for root in ALLOWED_ROOTS:
            if os.path.exists(root):
                entries.append(DirectoryEntry(name=os.path.basename(root) or root, path=root, is_dir=True, parent=None))
        return sorted(entries, key=lambda e: e.name.lower())

    real_path = resolve_and_validate_path(path)
    if not os.path.isdir(real_path):
        raise HTTPException(status_code=404, detail="Directory not found")

    entries = []
    if os.path.dirname(real_path) and os.path.realpath(real_path) not in ALLOWED_ROOTS:
        parent_dir = os.path.dirname(real_path)
        if any(os.path.commonpath([parent_dir, root]) == root for root in ALLOWED_ROOTS):
            entries.append(DirectoryEntry(name="..", path=parent_dir, is_dir=True, parent=os.path.dirname(parent_dir)))
    for item in sorted(os.listdir(real_path)):
        item_path = os.path.join(real_path, item)
        if os.path.isdir(item_path):
            entries.append(DirectoryEntry(name=item, path=item_path, is_dir=True, parent=os.path.dirname(real_path)))
    return entries
