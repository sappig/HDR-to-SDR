from datetime import datetime

from ..models import Activity


def log_event(session, media_file_id: int | None, category: str, message: str):
    event = Activity(
        media_file_id=media_file_id,
        category=category,
        message=message,
        created_at=datetime.utcnow(),
    )
    session.add(event)
    session.commit()
