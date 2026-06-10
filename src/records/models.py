"""Database models for Records."""

from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel

def utc_now() -> datetime:
    """define timezone"""
    return datetime.now(timezone.utc)


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str = ""
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)

    entries: list["Entry"] = Relationship(back_populates="category")


class Entry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    title: str = Field(index=True)
    creator: str = Field(default="", index=True)
    notes: str = ""
    tags: str = Field(default="", index=True)
    source_url: str = ""
    image_url: str = ""
    document_filename: str = ""
    document_original_name: str = ""
    document_content_type: str = ""
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)

    category: Category | None = Relationship(back_populates="entries")
