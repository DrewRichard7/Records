from nicegui import ui
from sqlalchemy.exc import IntegrityError

from records.db import DB_PATH, get_session, init_db
from records.models import Category
from records.repo import create_category, create_entry, format_datetime, list_categories, list_entries


def _category_options(categories: list[Category]) -> dict[int, str]:
    return {category.id: category.name for category in categories if category.id is not None}


def render_index() -> None:
    ui.page_title("Records")

    state: dict[str, int | None] = {"category_id": None}

    with ui.header().classes("bg-slate-900 text-white"):
        ui.label("Records").classes("text-xl font-semibold")
        ui.space()
        ui.label(f"SQLite: {DB_PATH}").classes("text-xs opacity-70")

    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        ui.label("Catalog").classes("text-3xl font-semibold")

        with ui.expansion("Create category", icon="create_new_folder").classes("w-full"):
            with ui.row().classes("w-full items-end gap-3"):
                category_name = ui.input("Name").props("outlined dense").classes("min-w-64")
                category_description = ui.input("Description").props("outlined dense").classes("flex-1")

                def save_category() -> None:
                    name = category_name.value.strip()
                    if not name:
                        ui.notify("Category name is required.", type="warning")
                        return
                    try:
                        with get_session() as session:
                            category = create_category(session, name, category_description.value or "")
                            state["category_id"] = category.id
                    except IntegrityError:
                        ui.notify("A category with that name already exists.", type="warning")
                        return
                    category_name.value = ""
                    category_description.value = ""
                    refresh_categories()
                    refresh_entries()
                    ui.notify("Category saved.", type="positive")

                ui.button("Save", icon="save", on_click=save_category).props("color=primary")

        with ui.row().classes("w-full items-end gap-3"):
            category_select = ui.select(
                {},
                label="Category",
                on_change=lambda event: select_category(event.value),
            ).props("outlined dense").classes("min-w-72")
            search_input = ui.input(
                "Search",
                placeholder="Title, creator, tags, notes",
                on_change=lambda: refresh_entries(),
            ).props("outlined dense clearable").classes("flex-1")
            sort_select = ui.select(
                ["Title", "Creator", "Created"],
                value="Title",
                label="Sort",
                on_change=lambda: refresh_entries(),
            ).props("outlined dense").classes("min-w-44")

        columns = [
            {"name": "title", "label": "Title", "field": "title", "align": "left"},
            {"name": "creator", "label": "Creator", "field": "creator", "align": "left"},
            {"name": "tags", "label": "Tags", "field": "tags", "align": "left"},
            {"name": "notes", "label": "Notes", "field": "notes", "align": "left"},
            {"name": "created_at", "label": "Created", "field": "created_at", "align": "left"},
        ]
        entries_table = ui.table(columns=columns, rows=[], row_key="id").classes("w-full")

        with ui.card().classes("w-full"):
            ui.label("Add entry").classes("text-lg font-medium")
            with ui.grid(columns=2).classes("w-full gap-3"):
                title_input = ui.input("Title").props("outlined dense").classes("w-full")
                creator_input = ui.input("Creator").props("outlined dense").classes("w-full")
                tags_input = ui.input("Tags").props("outlined dense").classes("w-full")
                notes_input = ui.textarea("Notes").props("outlined dense").classes("w-full")

            def save_entry() -> None:
                category_id = state["category_id"]
                title = title_input.value.strip()
                if category_id is None:
                    ui.notify("Create or select a category first.", type="warning")
                    return
                if not title:
                    ui.notify("Entry title is required.", type="warning")
                    return
                with get_session() as session:
                    create_entry(
                        session,
                        category_id=category_id,
                        title=title,
                        creator=creator_input.value or "",
                        tags=tags_input.value or "",
                        notes=notes_input.value or "",
                    )
                title_input.value = ""
                creator_input.value = ""
                tags_input.value = ""
                notes_input.value = ""
                refresh_entries()
                ui.notify("Entry saved.", type="positive")

            ui.button("Save entry", icon="save", on_click=save_entry).props("color=primary")

    def select_category(category_id: int | None) -> None:
        state["category_id"] = category_id
        refresh_entries()

    def refresh_categories() -> None:
        with get_session() as session:
            categories = list_categories(session)
        category_select.options = _category_options(categories)
        if state["category_id"] not in category_select.options:
            state["category_id"] = next(iter(category_select.options), None)
        category_select.value = state["category_id"]
        category_select.update()

    def refresh_entries() -> None:
        with get_session() as session:
            entries = list_entries(
                session,
                category_id=state["category_id"],
                search=search_input.value or "",
                sort_by=sort_select.value or "Title",
            )
        entries_table.rows = [
            {
                "id": entry.id,
                "title": entry.title,
                "creator": entry.creator,
                "tags": entry.tags,
                "notes": entry.notes,
                "created_at": format_datetime(entry.created_at),
            }
            for entry in entries
        ]
        entries_table.update()

    refresh_categories()
    refresh_entries()


def build_ui() -> None:
    init_db()


def main(reload: bool = False, show: bool = False) -> None:
    build_ui()
    ui.run(render_index, host="0.0.0.0", port=8080, reload=reload, show=show, title="Records")


if __name__ in {"__main__", "__mp_main__"}:
    main(reload=True, show=True)
