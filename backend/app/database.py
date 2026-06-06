import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/transcode.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_database(engine):
    repo_root = Path(__file__).resolve().parents[1]
    alembic_ini = repo_root / "alembic.ini"
    alembic_env = repo_root / "app" / "migrations" / "env.py"

    if alembic_ini.exists() and alembic_env.exists():
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
        command.upgrade(alembic_cfg, "head")
    else:
        Base.metadata.create_all(engine)
