from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import AppSetting
from ..schemas import SettingsRead, SettingsUpdate
from ..services.transcoder import TranscoderRunner

router = APIRouter(prefix="/settings", tags=["settings"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DEFAULTS = {
    "max_concurrent_transcodes": "2",
    "software_fallback": "false",
    "output_bitrate": "4500",
    "output_resolution": "1920x1080",
    "plex_transcoder_path": "",
    "scan_interval": "60",
    "log_retention_days": "30",
}


@router.get("", response_model=SettingsRead)
def get_settings(db: Session = Depends(get_db)):
    data = {}
    for row in db.query(AppSetting).all():
        data[row.key] = row.value
    for key, default in DEFAULTS.items():
        data.setdefault(key, default)

    runner = TranscoderRunner(lambda key, default=None: data.get(key, default))
    detected_version = None
    binary = runner.discover_plex_transcoder()
    if binary:
        detected_version = runner.get_version(binary)
    return SettingsRead(
        max_concurrent_transcodes=int(data.get("max_concurrent_transcodes", 2)),
        software_fallback=str(data.get("software_fallback", "false")).lower() == "true",
        output_bitrate=int(data.get("output_bitrate", 4500)),
        output_resolution=data.get("output_resolution", "1920x1080"),
        plex_transcoder_path=data.get("plex_transcoder_path") or None,
        scan_interval=int(data.get("scan_interval", 60)),
        log_retention_days=int(data.get("log_retention_days", 30)),
        qsv_available=runner.detect_qsv(),
        qsv_device="/dev/dri" if runner.detect_qsv() else None,
        detected_plex_version=detected_version,
    )


@router.post("")
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row:
            row.value = str(value)
        else:
            db.add(AppSetting(key=key, value=str(value)))
    db.commit()
    return {"updated": True}
