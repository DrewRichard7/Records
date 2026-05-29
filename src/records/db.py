import os
from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine


def database_path() -> Path:
    configured = os.environ.get("RECORDS_DB_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.cwd() / "records.db"


DB_PATH = database_path()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)

