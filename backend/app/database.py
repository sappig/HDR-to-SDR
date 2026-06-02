import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/transcode.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_database(engine):
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    env_file = migrations_dir / "env.py"

    if env_file.exists():
        from alembic.config import Config
        from alembic import command

        repo_root = Path(__file__).resolve().parents[1]
        alembic_ini = repo_root / "alembic.ini"
        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
        command.upgrade(alembic_cfg, "head")
    else:
        Base.metadata.create_all(engine)
