import os
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine


def database_path() -> Path:
    configured = os.environ.get("RECORDS_DB_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.cwd() / "records.db"

DB_PATH = database_path()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def upload_dir() -> Path:
    configured = os.environ.get("RECORDS_UPLOAD_DIR")
    if configured:
        return Path(configured).expanduser()
    return DB_PATH.parent / "uploads"


UPLOAD_DIR = upload_dir()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

def _table_columns(connection, table_name: str) -> dict[str, str]:
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).mappings()
    return {row["name"]: (row["type"] or "").upper() for row in rows}

def _add_column_if_missing(connection, table_name: str, column_name: str, ddl: str) -> None:
    if column_name not in _table_columns(connection, table_name):
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))


def _migrate_category_columns() -> None:
    with engine.begin() as connection:
        if not _table_columns(connection, "category"):
            return
        _add_column_if_missing(connection, "category", "created_at", "created_at DATETIME")
        _add_column_if_missing(connection, "category", "updated_at", "updated_at DATETIME")
        connection.execute(
            text("UPDATE category SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        )
        connection.execute(
            text("UPDATE category SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
        )


def _migrate_entry_table() -> None:
    with engine.begin() as connection:
        columns = _table_columns(connection, "entry")
        old_entry_columns = _table_columns(connection, "entry_old")
        if not columns:
            return

        has_category_id = "category_id" in columns
        needs_rebuild = not has_category_id

        if not needs_rebuild:
            _add_column_if_missing(connection, "entry", "source_url", "source_url VARCHAR NOT NULL DEFAULT ''")
            _add_column_if_missing(connection, "entry", "image_url", "image_url VARCHAR NOT NULL DEFAULT ''")
            _add_column_if_missing(connection, "entry", "document_filename", "document_filename VARCHAR NOT NULL DEFAULT ''")
            _add_column_if_missing(connection, "entry", "document_original_name", "document_original_name VARCHAR NOT NULL DEFAULT ''")
            _add_column_if_missing(connection, "entry", "document_content_type", "document_content_type VARCHAR NOT NULL DEFAULT ''")
            if old_entry_columns and "category_name" in old_entry_columns:
                _copy_legacy_entries(connection, old_entry_columns)
                connection.execute(text("DROP TABLE entry_old"))
            return

        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(text("DROP TABLE IF EXISTS entry_old"))
        connection.execute(text("ALTER TABLE entry RENAME TO entry_old"))
        for index_name in (
                "ix_entry_category_id",
                "ix_entry_created_at",
                "ix_entry_creator",
                "ix_entry_tags",
                "ix_entry_title",
                ):
            connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
        SQLModel.metadata.tables["entry"].create(connection)

        old_columns = _table_columns(connection, "entry_old")
        _copy_legacy_entries(connection, old_columns)
        connection.execute(text("DROP TABLE entry_old"))
        connection.execute(text("PRAGMA foreign_keys=ON"))


def _copy_legacy_entries(connection, old_columns: dict[str, str]) -> None:
        if "category_name" not in old_columns:
            return
        copy_columns = ["id", "title", "creator", "notes", "tags", "created_at", "updated_at"]
        target_columns_list = [name for name in copy_columns if name in old_columns]
        source_columns_list = [f"entry_old.{name}" for name in target_columns_list]
        for optional_column in (
            "source_url",
            "image_url",
            "document_filename",
            "document_original_name",
            "document_content_type",
        ):
            target_columns_list.append(optional_column)
            if optional_column in old_columns:
                source_columns_list.append(f"COALESCE(entry_old.{optional_column}, '')")
            else:
                source_columns_list.append("''")
        target_columns = ", ".join([*target_columns_list, "category_id"])
        source_columns = ", ".join(source_columns_list)
        category_expression = "category.id"
        join_clause = "LEFT JOIN category ON category.name = entry_old.category_name"

        connection.execute(
                text(
                    f"""
                    INSERT OR IGNORE INTO entry ({target_columns})
                    SELECT {source_columns}, {category_expression}
                    FROM entry_old
                    {join_clause}
                    WHERE category.id IS NOT NULL
                    """
                    )
                )

def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_category_columns()
    _migrate_entry_table()

def get_session() -> Session:
    return Session(engine)
