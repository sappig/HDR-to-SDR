from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import QueueItem
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
    return db.query(QueueItem).order_by(QueueItem.sort_order.asc()).all()


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


@router.delete("/{item_id}")
def remove_queue_item(item_id: int, db: Session = Depends(get_db)):
    queue_item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    db.delete(queue_item)
    db.commit()
    return {"removed": True}
