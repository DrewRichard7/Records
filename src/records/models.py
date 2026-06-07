"""Create sql model for schema/tables"""

from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel

def utc_now() -> datetime:
    """define timezone"""
    return datetime.now(timezone.utc)


# Create the SQLModel Model for the "Category" table
class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str = ""

    entries: list["Entry"] = Relationship(back_populates="category")

# Create the SQLModel Model for the "Entry" Table
class Entry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category_name: str = Field(foreign_key="category.name", index=True)
    title: str = Field(index=True)
    creator: str = Field(default="", index=True)
    notes: str = ""
    tags: str = Field(default="", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)

    category: Category | None = Relationship(back_populates="entries")
