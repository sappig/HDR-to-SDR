from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Activity

router = APIRouter(prefix="/events", tags=["events"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def list_events(db: Session = Depends(get_db)):
    events = db.query(Activity).order_by(Activity.created_at.desc()).limit(50).all()
    return [
        {
            "id": event.id,
            "media_file_id": event.media_file_id,
            "category": event.category,
            "message": event.message,
            "created_at": event.created_at,
        }
        for event in events
    ]
