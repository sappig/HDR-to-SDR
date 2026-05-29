import os

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.models import Base
import backend.app.routers.folders as folders_router
import backend.app.routers.settings as settings_router


class DummyMonitor:
    def start(self):
        return None

    def stop(self):
        return None

    def watch_folder(self, folder):
        return None

    def scan_folder(self, folder):
        return None


class DummyQueueManager:
    async def run(self):
        return None

    def stop(self):
        return None


def test_folder_api_and_settings(monkeypatch):
    in_memory_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(in_memory_engine)
    session_factory = sessionmaker(bind=in_memory_engine)

    folders_router.SessionLocal = session_factory
    settings_router.SessionLocal = session_factory

    monkeypatch.setattr("backend.app.main.init_database", lambda engine: None)
    monkeypatch.setattr("backend.app.main.FolderMonitor", lambda *args, **kwargs: DummyMonitor())
    monkeypatch.setattr("backend.app.main.QueueManager", lambda *args, **kwargs: DummyQueueManager())

    client = TestClient(app)

    response = client.get("/folders")
    assert response.status_code == 200

    add_response = client.post("/folders", json={"path": "/media/movies", "enabled": True})
    assert add_response.status_code == 200
    folder = add_response.json()
    assert folder["path"] == "/media/movies"

    settings_response = client.get("/settings")
    assert settings_response.status_code == 200
    assert settings_response.json()["output_bitrate"] == 4500

    client.delete(f"/folders/{folder['id']}")
