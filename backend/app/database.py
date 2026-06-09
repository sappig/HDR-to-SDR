import logging
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/transcode.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_sqlite_directory(engine):
    if engine.url.drivername == "sqlite":
        db_path = Path(engine.url.database)
        if db_path.parent and not db_path.parent.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)


def init_database(engine):
    ensure_sqlite_directory(engine)
    repo_root = Path(__file__).resolve().parents[1]
    alembic_ini = repo_root / "alembic.ini"
    alembic_env = repo_root / "app" / "migrations" / "env.py"

    if alembic_ini.exists() and alembic_env.exists():
        try:
            from alembic.config import Config
            from alembic import command

            alembic_cfg = Config(str(alembic_ini))
            alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
            command.upgrade(alembic_cfg, "head")
        except Exception:
            logger.exception("Alembic migration failed; falling back to SQLAlchemy metadata create_all")
            Base.metadata.create_all(engine)
    else:
        Base.metadata.create_all(engine)
