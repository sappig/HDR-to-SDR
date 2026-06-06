import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .database import init_database
from .routers.files import router as files_router
from .routers.folders import router as folders_router
from .routers.queue import router as queue_router
from .routers.settings import router as settings_router
from .routers.system import router as system_router
from .routers.events import router as events_router
from .services.activity_logger import log_event
from .services.queue_manager import QueueManager
from .services.monitoring import FolderMonitor

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_engine(os.getenv("DATABASE_URL", "sqlite:////data/transcode.db"), connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    app.state.engine = engine
    app.state.session_factory = SessionLocal

    try:
        init_database(engine)

        app.state.queue_manager = QueueManager(SessionLocal)
        app.state.queue_task = asyncio.create_task(app.state.queue_manager.run())

        app.state.monitor = FolderMonitor(SessionLocal, app.state.queue_manager)
        try:
            app.state.monitor.start()
        except Exception:
            logger.exception("Folder monitor failed to start; continuing without folder watch")
            app.state.monitor = None

        logger.info("Application startup complete and queue manager running")
        session = SessionLocal()
        try:
            log_event(session, None, "system", "Application startup complete")
        finally:
            session.close()

        yield
    except Exception:
        logger.exception("Application startup failed")
        raise
    finally:
        if hasattr(app.state, "monitor") and app.state.monitor:
            app.state.monitor.stop()
        if hasattr(app.state, "queue_manager") and app.state.queue_manager:
            app.state.queue_manager.stop()
        if hasattr(app.state, "queue_task") and app.state.queue_task:
            app.state.queue_task.cancel()
            try:
                await app.state.queue_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="HDR to FHD Transcoding Manager", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(folders_router)
app.include_router(files_router)
app.include_router(queue_router)
app.include_router(settings_router)
app.include_router(system_router)
app.include_router(events_router)

static_dir = Path(__file__).resolve().parents[2] / "frontend_dist"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")


@app.get("/health")
def health():
    return {"status": "ok"}
