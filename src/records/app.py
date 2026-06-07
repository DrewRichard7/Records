from nicegui import ui
from records.models import Category
from records.db import DB_PATH, init_db


def _category_options(categories: list[Category]) -> dict[str, str]:
    return {category.name: category.name for category in categories}

def render_index() -> None:
    ui.page_title("Records")

    state: dict[str, str | None] = {"category_name": None}

    # make dark mode by default
    ui.dark_mode().enable()

    with ui.header().classes("bg-slate-900 text-white"):
        ui.label("Records").classes("text-xl font-semibold")
        ui.space()
        ui.label(f"SQLite: {DB_PATH}").classes("text-xs opacity-70")

def build_ui() -> None:
    init_db()

def main(reload: bool =False, show: bool = False) -> None:
    build_ui()
    ui.run(render_index, host="0.0.0.0", port=8080, reload=reload, show=show, title="Records")

if __name__ in {"__main__", "__mp_main__"}:
    main(reload=True, show=True)
