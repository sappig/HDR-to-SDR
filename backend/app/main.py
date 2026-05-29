import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .database import init_database
from .routers.files import router as files_router
from .routers.folders import router as folders_router
from .routers.queue import router as queue_router
from .routers.settings import router as settings_router
from .routers.system import router as system_router
from .services.queue_manager import QueueManager
from .services.monitoring import FolderMonitor

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_engine(os.getenv("DATABASE_URL", "sqlite:////data/transcode.db"), connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    app.state.engine = engine
    app.state.session_factory = SessionLocal

    init_database(engine)

    app.state.queue_manager = QueueManager(SessionLocal)
    app.state.queue_task = asyncio.create_task(app.state.queue_manager.run())

    app.state.monitor = FolderMonitor(SessionLocal, app.state.queue_manager)
    app.state.monitor.start()

    yield

    app.state.monitor.stop()
    app.state.queue_manager.stop()
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


@app.get("/health")
def health():
    return {"status": "ok"}
