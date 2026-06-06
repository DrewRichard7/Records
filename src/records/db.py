from ntpath import exists
import os
from pathlib import Path
from shlex import join

from sqlalchemy import text
from sqlalchemy.orm.sync import source_modified
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

def _migrate_entry_category_column() -> None:
    with enging.begin() as connection:
        columns = _table_columns(connection, "entry")
        if not columns:
            return

        has_category_id = "category_id" in columns
        category_name_type = columns.get("category_name", "")
        has_text_category_name = category_name_type in {"VARCHAR", "TEXT", "STRING"}
        if not has_category_id and has_text_category_name:
            return

        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(text("DROP TABLE IF EXISTS entry_old"))
        connection.execute(text("ALTER TABLE entry RENAME TO entry_old"))
        for index_name in (
                "ix_entry_category_id",
                "ix_entry_category_name",
                "ix_entry_created_at",
                "ix_entry_creator",
                "ix_entry_tags",
                "ix_entry_title",
                ):
            connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
        SQLModel.metadata.tables["entry"].create(connection)

        old_columns = _table_columns(connection, "entry_old")
        shared_columns = [
                name
                for name in ("id", "title", "creator", "notes", "tags", "created_at", "updated_at")
                if name in old_columns
                ]
        target_columns = ", ".join([*shared_columns, "category_name"])
        source_columns = ", ".join(f"entry_old.{name}" for name in shared_columns)
        if has_category_id:
            category_expression = "category.name"
            join_clause = "LEFT JOIN category ON category.id = entry_old.category_id"
        else:
            category_expression = "COALESCE(category.name, entry_old.category_name)"
            join_clause = "LEFT JOIN category ON category.id = entry_old.category_name"

        connection.execute(
                text(
                    f"""
                    INSERT INTO entry ({target_columns})
                    SELECT {source_columns}, {category_expression}
                    FROM entry_old
                    {join_clause}
                    WHERE {category_expression} IS NOT NULL
                    """
                    )
                )

