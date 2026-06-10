from datetime import datetime

from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from records.models import Category, Entry, utc_now

SORT_COLUMNS = {
        "Title": Entry.title,
        "Creator": Entry.creator,
        "Created": Entry.created_at,
        }

def create_category(session: Session, name: str, description: str = "") -> Category:
    """Create a new category from variables defined in models.py and set in db.py"""
    now = utc_now()
    category = Category(name=name.strip(), description=description.strip(), created_at=now, updated_at=now)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category

def list_categories(session: Session) -> list[Category]:
    """Lists the categories that have been created."""
    statement = select(Category).order_by(Category.name)
    return list(session.exec(statement))


def list_categories_with_counts(session: Session) -> list[tuple[Category, int]]:
    statement = (
        select(Category, func.count(Entry.id))
        .outerjoin(Entry)
        .group_by(Category.id)
        .order_by(Category.name)
    )
    return [(category, count) for category, count in session.exec(statement).all()]


def get_category(session: Session, category_id: int) -> Category | None:
    return session.get(Category, category_id)


def update_category(session: Session, category_id: int, *, name: str, description: str = "") -> Category | None:
    category = session.get(Category, category_id)
    if category is None:
        return None
    category.name = name.strip()
    category.description = description.strip()
    category.updated_at = utc_now()
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def delete_category(session: Session, category_id: int) -> bool:
    category = session.get(Category, category_id)
    if category is None:
        return False
    for entry in list(category.entries):
        session.delete(entry)
    session.delete(category)
    session.commit()
    return True


def create_entry(
        session: Session,
        *,
        category_id: int,
        title: str,
        creator: str,
        tags: str = "",
        notes: str = "",
        source_url: str = "",
        image_url: str = "",
        document_filename: str = "",
        document_original_name: str = "",
        document_content_type: str = "",
        ) -> Entry:
    """
    takes in variables from the Entry model defined in models.py and set in db.py and adds them to the records.db
    """
    now = utc_now()
    entry = Entry(
            category_id=category_id,
            title=title.strip(),
            creator=creator.strip(),
            tags=tags.strip(),
            notes=notes.strip(),
            source_url=source_url.strip(),
            image_url=image_url.strip(),
            document_filename=document_filename.strip(),
            document_original_name=document_original_name.strip(),
            document_content_type=document_content_type.strip(),
            created_at=now,
            updated_at=now,
            )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def list_entries(
        session: Session,
        *,
        category_id: int | None = None,
        search: str = "",
        creator: str = "",
        tag: str = "",
        sort_by: str = "Title",
        ) -> list[Entry]:
    statement = select(Entry).join(Category)

    if category_id is not None:
        statement = statement.where(Entry.category_id == category_id)

    creator_term = creator.strip()
    if creator_term:
        statement = statement.where(col(Entry.creator).ilike(f"%{creator_term}%"))

    tag_term = tag.strip()
    if tag_term:
        statement = statement.where(col(Entry.tags).ilike(f"%{tag_term}%"))

    term = search.strip()
    if term:
        pattern = f"%{term}%"
        statement = statement.where(
                or_(
                    col(Entry.title).ilike(pattern),
                    col(Entry.creator).ilike(pattern),
                    col(Entry.tags).ilike(pattern),
                    col(Entry.notes).ilike(pattern),
                    col(Category.name).ilike(pattern),
                    )
                )

    sort_column = SORT_COLUMNS.get(sort_by, Entry.title)
    if sort_by == "Created":
        statement = statement.order_by(sort_column.desc())
    else:
        statement = statement.order_by(sort_column, Entry.title)

    return list(session.exec(statement))


def update_entry(
        session: Session,
        entry_id: int,
        *,
        category_id: int,
        title: str,
        creator: str,
        tags: str = "",
        notes: str = "",
        source_url: str = "",
        image_url: str = "",
        document_filename: str | None = None,
        document_original_name: str | None = None,
        document_content_type: str | None = None,
        ) -> Entry | None:
    entry = session.get(Entry, entry_id)
    if entry is None:
        return None

    entry.category_id = category_id
    entry.title = title.strip()
    entry.creator = creator.strip()
    entry.tags = tags.strip()
    entry.notes = notes.strip()
    entry.source_url = source_url.strip()
    entry.image_url = image_url.strip()
    if document_filename is not None:
        entry.document_filename = document_filename.strip()
    if document_original_name is not None:
        entry.document_original_name = document_original_name.strip()
    if document_content_type is not None:
        entry.document_content_type = document_content_type.strip()
    entry.updated_at = utc_now()

    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def get_entry(session: Session, entry_id: int) -> Entry | None:
    return session.get(Entry, entry_id)


def delete_entry(session: Session, entry_id: int) -> bool:
    entry = session.get(Entry, entry_id)
    if entry is None:
        return False
    session.delete(entry)
    session.commit()
    return True


def recent_entries(session: Session, limit: int = 8) -> list[Entry]:
    statement = select(Entry).order_by(Entry.created_at.desc()).limit(limit)
    return list(session.exec(statement))


def distinct_creators(session: Session, category_id: int | None = None) -> list[str]:
    statement = select(Entry.creator).where(Entry.creator != "")
    if category_id is not None:
        statement = statement.where(Entry.category_id == category_id)
    statement = statement.distinct().order_by(Entry.creator)
    return list(session.exec(statement))


def split_tags(tags: str) -> list[str]:
    return [tag.strip() for tag in tags.split(",") if tag.strip()]


def distinct_tags(session: Session, category_id: int | None = None) -> list[str]:
    statement = select(Entry.tags).where(Entry.tags != "")
    if category_id is not None:
        statement = statement.where(Entry.category_id == category_id)
    tags: set[str] = set()
    for value in session.exec(statement):
        tags.update(split_tags(value))
    return sorted(tags, key=str.lower)

def format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")
