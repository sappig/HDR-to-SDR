from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import MediaFile, QueueItem
from ..schemas import QueueReorderRequest

router = APIRouter(prefix="/queue", tags=["queue"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def list_queue(db: Session = Depends(get_db)):
    items = db.query(QueueItem).order_by(QueueItem.sort_order.asc()).all()
    result = []
    for item in items:
        media_file = db.query(MediaFile).filter(MediaFile.id == item.media_file_id).first()
        result.append({
            "id": item.id,
            "media_file_id": item.media_file_id,
            "filename": media_file.filename if media_file else None,
            "file_path": media_file.path if media_file else None,
            "output_path": media_file.output_path if media_file else None,
            "state": item.state,
            "progress": item.progress,
            "paused": item.paused,
            "sort_order": item.sort_order,
            "eta_seconds": item.eta_seconds,
            "started_at": item.started_at,
            "completed_at": item.completed_at,
            "transcode_command": item.transcode_command,
            "last_error": item.last_error,
        })
    return result


@router.post("/reorder")
def reorder_queue(payload: QueueReorderRequest, db: Session = Depends(get_db)):
    for index, item_id in enumerate(payload.order):
        queue_item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
        if not queue_item:
            raise HTTPException(status_code=404, detail="Queue item not found")
        queue_item.sort_order = index
    db.commit()
    return {"updated": True}


@router.post("/pause")
def pause_queue(payload: dict, db: Session = Depends(get_db)):
    ids = payload.get("ids") or []
    for item_id in ids:
        queue_item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
        if queue_item:
            queue_item.paused = True
            queue_item.state = "Waiting"
    db.commit()
    return {"paused": len(ids)}


@router.post("/{item_id}/pause")
def pause_queue_item(item_id: int, db: Session = Depends(get_db)):
    queue_item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    queue_item.paused = True
    queue_item.state = "Waiting"
    db.commit()
    return {"paused": True}


@router.post("/resume")
def resume_queue(payload: dict, db: Session = Depends(get_db)):
    ids = payload.get("ids") or []
    for item_id in ids:
        queue_item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
        if queue_item:
            queue_item.paused = False
            queue_item.state = "Pending"
    db.commit()
    return {"resumed": len(ids)}


@router.post("/{item_id}/resume")
def resume_queue_item(item_id: int, db: Session = Depends(get_db)):
    queue_item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    queue_item.paused = False
    queue_item.state = "Pending"
    db.commit()
    return {"resumed": True}


@router.delete("/{item_id}")
def remove_queue_item(item_id: int, db: Session = Depends(get_db)):
    queue_item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    db.delete(queue_item)
    db.commit()
    return {"removed": True}
