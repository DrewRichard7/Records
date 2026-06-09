from pathlib import Path
import socket
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from records import repo
from records.db import DB_PATH, get_session, init_db


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Records")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["date"] = repo.format_datetime
templates.env.globals["split_tags"] = repo.split_tags


def get_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def print_startup_urls(host: str, port: int) -> None:
    print(f"Records running at: http://127.0.0.1:{port}")
    if host in {"0.0.0.0", "::"}:
        lan_ip = get_lan_ip()
        if lan_ip:
            print(f"Phone/LAN URL:      http://{lan_ip}:{port}")


def session_dep():
    with get_session() as session:
        yield session


SessionDep = Annotated[Session, Depends(session_dep)]


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def wants_partial(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


@app.get("/", response_class=HTMLResponse)
def home(request: Request, session: SessionDep):
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "db_path": DB_PATH,
            "categories": repo.list_categories_with_counts(session),
            "recent_entries": repo.recent_entries(session),
            "query": "",
        },
    )


@app.get("/categories", response_class=HTMLResponse)
def categories(request: Request, session: SessionDep):
    return templates.TemplateResponse(
        request,
        "categories.html",
        {"categories": repo.list_categories_with_counts(session)},
    )


@app.get("/categories/new", response_class=HTMLResponse)
def new_category(request: Request):
    return templates.TemplateResponse(request, "category_form.html", {"category": None, "error": ""})


@app.post("/categories")
def create_category(
    session: SessionDep,
    name: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Category name is required")
    category = repo.create_category(session, name=name, description=description)
    return redirect(f"/categories/{category.id}")


@app.get("/categories/{category_id}", response_class=HTMLResponse)
def category_detail(
    request: Request,
    session: SessionDep,
    category_id: int,
    creator: str = "",
    tag: str = "",
):
    category = repo.get_category(session, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    entries = repo.list_entries(session, category_id=category_id, creator=creator, tag=tag)
    context = {
        "category": category,
        "entries": entries,
        "creators": repo.distinct_creators(session, category_id),
        "tags": repo.distinct_tags(session, category_id),
        "selected_creator": creator,
        "selected_tag": tag,
    }
    template = "partials/entry_list.html" if wants_partial(request) else "category_detail.html"
    return templates.TemplateResponse(request, template, context)


@app.get("/categories/{category_id}/edit", response_class=HTMLResponse)
def edit_category(request: Request, session: SessionDep, category_id: int):
    category = repo.get_category(session, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return templates.TemplateResponse(request, "category_form.html", {"category": category, "error": ""})


@app.post("/categories/{category_id}")
def update_category(
    session: SessionDep,
    category_id: int,
    name: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
):
    category = repo.update_category(session, category_id, name=name, description=description)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return redirect(f"/categories/{category.id}")


@app.post("/categories/{category_id}/delete")
def delete_category(request: Request, session: SessionDep, category_id: int):
    repo.delete_category(session, category_id)
    if wants_partial(request):
        return Response(status_code=200)
    return redirect("/categories")


@app.get("/entries/new", response_class=HTMLResponse)
def new_entry(request: Request, session: SessionDep, category_id: int | None = None):
    return templates.TemplateResponse(
        request,
        "entry_form.html",
        {"entry": None, "categories": repo.list_categories(session), "category_id": category_id},
    )


@app.post("/entries")
def create_entry(
    session: SessionDep,
    category_id: Annotated[int, Form()],
    title: Annotated[str, Form()],
    creator: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    tags: Annotated[str, Form()] = "",
    source_url: Annotated[str, Form()] = "",
    image_url: Annotated[str, Form()] = "",
):
    if not title.strip():
        raise HTTPException(status_code=400, detail="Entry title is required")
    entry = repo.create_entry(
        session,
        category_id=category_id,
        title=title,
        creator=creator,
        notes=notes,
        tags=tags,
        source_url=source_url,
        image_url=image_url,
    )
    return redirect(f"/entries/{entry.id}")


@app.get("/entries/{entry_id}", response_class=HTMLResponse)
def entry_detail(request: Request, session: SessionDep, entry_id: int):
    entry = repo.get_entry(session, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return templates.TemplateResponse(request, "entry_detail.html", {"entry": entry})


@app.get("/entries/{entry_id}/edit", response_class=HTMLResponse)
def edit_entry(request: Request, session: SessionDep, entry_id: int):
    entry = repo.get_entry(session, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return templates.TemplateResponse(
        request,
        "entry_form.html",
        {"entry": entry, "categories": repo.list_categories(session), "category_id": entry.category_id},
    )


@app.post("/entries/{entry_id}")
def update_entry(
    session: SessionDep,
    entry_id: int,
    category_id: Annotated[int, Form()],
    title: Annotated[str, Form()],
    creator: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    tags: Annotated[str, Form()] = "",
    source_url: Annotated[str, Form()] = "",
    image_url: Annotated[str, Form()] = "",
):
    entry = repo.update_entry(
        session,
        entry_id,
        category_id=category_id,
        title=title,
        creator=creator,
        notes=notes,
        tags=tags,
        source_url=source_url,
        image_url=image_url,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return redirect(f"/entries/{entry.id}")


@app.post("/entries/{entry_id}/delete")
def delete_entry(request: Request, session: SessionDep, entry_id: int):
    entry = repo.get_entry(session, entry_id)
    category_id = entry.category_id if entry else None
    repo.delete_entry(session, entry_id)
    if wants_partial(request):
        return Response(status_code=200)
    return redirect(f"/categories/{category_id}" if category_id else "/")


@app.get("/search", response_class=HTMLResponse)
def search(
    request: Request,
    session: SessionDep,
    q: str = "",
    category_id: int | None = None,
    creator: str = "",
    tag: str = "",
):
    entries = repo.list_entries(
        session,
        category_id=category_id,
        search=q,
        creator=creator,
        tag=tag,
        sort_by="Title",
    )
    context = {
        "entries": entries,
        "categories": repo.list_categories(session),
        "creators": repo.distinct_creators(session),
        "tags": repo.distinct_tags(session),
        "query": q,
        "category_id": category_id,
        "selected_creator": creator,
        "selected_tag": tag,
    }
    template = "partials/search_results.html" if wants_partial(request) else "search.html"
    return templates.TemplateResponse(request, template, context)


def main() -> None:
    import uvicorn

    host = "0.0.0.0"
    port = 8000
    print_startup_urls(host, port)
    uvicorn.run("records.main:app", host=host, port=port, reload=False)
