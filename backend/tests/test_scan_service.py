import json
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base, Folder, MediaFile, QueueItem
from backend.app.services.scan_service import ScanService, find_tv_episode, normalize_title


class DummyQueueManager:
    pass


def create_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_find_tv_episode_parsing():
    match = find_tv_episode("Show.S01E03.HDR.mkv")
    assert match == (1, 3, "show")


def test_normalize_title_removes_noise():
    assert normalize_title("Movie.2024.HDR.1080p.mkv") == "movie"


def test_process_path_creates_queue_entry(monkeypatch):
    session = create_session()
    folder = Folder(path="/tmp", enabled=True)
    session.add(folder)
    session.commit()

    def fake_ffprobe(path):
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "codec_name": "hevc",
                    "bit_rate": "4500000",
                    "color_transfer": "smpte2084",
                }
            ]
        }

    def fake_mediainfo(path):
        return {"media": {"track": [{"@type": "Video", "HDR_Format": "HDR10"}]}}

    def fake_mkvtoolnix(path):
        return "HDR10"

    service = ScanService(session, DummyQueueManager())
    monkeypatch.setattr(service, "run_ffprobe", fake_ffprobe)
    monkeypatch.setattr(service, "run_mediainfo", fake_mediainfo)
    monkeypatch.setattr(service, "run_mkvtoolnix", fake_mkvtoolnix)

    with tempfile.NamedTemporaryFile(suffix=".mkv") as tmp:
        media_file = service.process_path(tmp.name, folder.id)
        assert media_file.hdr_detected is True
        assert media_file.hdr_type == "smpte2084"

        queue_item = session.query(QueueItem).filter_by(media_file_id=media_file.id).first()
        assert queue_item is not None
        assert queue_item.state == "Pending"
