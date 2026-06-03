from datetime import datetime

from sqlalchemy import or_
from sqlmodel import Session, col, select

from records.models import Category, Entry, utc_now


SORT_COLUMNS = {
    "Title": Entry.title,
    "Creator": Entry.creator,
    "Created": Entry.created_at,
}


def create_category(session: Session, name: str, description: str = "") -> Category:
    category = Category(name=name.strip(), description=description.strip())
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def list_categories(session: Session) -> list[Category]:
    statement = select(Category).order_by(Category.name)
    return list(session.exec(statement))


def create_entry(
    session: Session,
    *,
    category_name: str,
    title: str,
    creator: str = "",
    tags: str = "",
    notes: str = "",
) -> Entry:
    now = utc_now()
    entry = Entry(
        category_name=category_name,
        title=title.strip(),
        creator=creator.strip(),
        tags=tags.strip(),
        notes=notes.strip(),
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
    category_name: str | None,
    search: str = "",
    sort_by: str = "Title",
) -> list[Entry]:
    statement = select(Entry)

    if category_name is not None:
        statement = statement.where(Entry.category_name == category_name)

    term = search.strip()
    if term:
        pattern = f"%{term}%"
        statement = statement.where(
            or_(
                col(Entry.title).ilike(pattern),
                col(Entry.creator).ilike(pattern),
                col(Entry.tags).ilike(pattern),
                col(Entry.notes).ilike(pattern),
            )
        )

    sort_column = SORT_COLUMNS.get(sort_by, Entry.title)
    if sort_by == "Created":
        statement = statement.order_by(sort_column.desc())
    else:
        statement = statement.order_by(sort_column, Entry.title)

    return list(session.exec(statement))


def update_entry(
        session,
        entry_id:
        )

def format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")
