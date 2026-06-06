from ntpath import exists
import os
from pathlib import Path

from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine, table

from records import models

# define where the database is stored: uses envvar if set, otherwise root dir
def database_path() -> Path:
    configured = os.environ.get("RECORDS_DB_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.cwd() / "records.db"

DB_PATH = database_path()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# create database engine
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

def _table_columns(connection, table_name: str) -> dict[str, str]:
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).mappings()
    return {row["name"]: (row["type"] or "").upper() for row in rows}
