from pathlib import Path
from email.message import EmailMessage
import os
import socket
import smtplib
import ssl
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from records.auth import (
    SESSION_MAX_AGE_SECONDS,
    create_password_reset_token,
    create_session_token,
    hash_password,
    password_reset_token_is_valid,
    session_token_is_valid,
    verify_password,
)
from records import repo
from records.db import DB_PATH, UPLOAD_DIR, get_session, init_db


BASE_DIR = Path(__file__).resolve().parent
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
}
PASSWORD_HASH = os.environ.get("RECORDS_PASSWORD_HASH", "")
SESSION_SECRET = os.environ.get("RECORDS_SESSION_SECRET", "")
PUBLIC_PATHS = {"/login", "/forgot-password", "/reset-password"}
SESSION_COOKIE_NAME = "records_session"
PASSWORD_SETTING_KEY = "password_hash"
RECOVERY_EMAIL = os.environ.get("RECORDS_RECOVERY_EMAIL", "").strip().lower()
SMTP_HOST = os.environ.get("RECORDS_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("RECORDS_SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("RECORDS_SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("RECORDS_SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.environ.get("RECORDS_SMTP_FROM_EMAIL", SMTP_USERNAME or RECOVERY_EMAIL)
SMTP_USE_TLS = os.environ.get("RECORDS_SMTP_TLS", "1") != "0"
SMTP_USE_SSL = os.environ.get("RECORDS_SMTP_SSL", "0") == "1"
SMTP_VERIFY_TLS = os.environ.get("RECORDS_SMTP_VERIFY_TLS", "1") != "0"
PUBLIC_URL = os.environ.get("RECORDS_PUBLIC_URL", "").rstrip("/")

app = FastAPI(title="Records")
if PASSWORD_HASH or RECOVERY_EMAIL:
    if not SESSION_SECRET:
        raise RuntimeError("RECORDS_SESSION_SECRET is required when auth or password reset email is configured")
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


def auth_is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith("/static/")


def safe_next_url(value: str | None) -> str:
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


def request_is_authenticated(request: Request) -> bool:
    return session_token_is_valid(request.cookies.get(SESSION_COOKIE_NAME), SESSION_SECRET)


def set_auth_cookie(response: Response) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(SESSION_SECRET),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="strict",
        secure=os.environ.get("RECORDS_COOKIE_SECURE", "0") == "1",
    )


def current_password_hash(session: Session) -> str:
    return repo.get_setting(session, PASSWORD_SETTING_KEY) or PASSWORD_HASH


def auth_is_enabled(session: Session) -> bool:
    return bool(current_password_hash(session))


def recovery_email_is_configured() -> bool:
    return bool(RECOVERY_EMAIL and SMTP_HOST and SMTP_FROM_EMAIL)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def absolute_url(request: Request, path: str) -> str:
    base_url = PUBLIC_URL or str(request.base_url).rstrip("/")
    return f"{base_url}{path}"


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Reset your Records password"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "Use this link to reset your Records password:",
                "",
                reset_url,
                "",
                "This link expires in 30 minutes.",
                "If you did not request this, you can ignore this email.",
            ]
        )
    )

    smtp_class = smtplib.SMTP_SSL if SMTP_USE_SSL else smtplib.SMTP
    with smtp_class(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
        if SMTP_USE_TLS and not SMTP_USE_SSL:
            context = ssl.create_default_context() if SMTP_VERIFY_TLS else ssl._create_unverified_context()
            smtp.starttls(context=context)
        if SMTP_USERNAME or SMTP_PASSWORD:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)


@app.middleware("http")
async def require_login(request: Request, call_next):
    if auth_is_public_path(request.url.path):
        return await call_next(request)
    with get_session() as session:
        if not auth_is_enabled(session):
            return await call_next(request)
    if request_is_authenticated(request):
        return await call_next(request)
    next_url = safe_next_url(str(request.url.path))
    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"
    return redirect(f"/login?next={quote(next_url, safe='')}")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    with get_session() as session:
        if auth_is_enabled(session) and not SESSION_SECRET:
            raise RuntimeError("RECORDS_SESSION_SECRET is required when auth or password reset email is configured")


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def is_image_attachment(entry) -> bool:
    return bool(entry.document_content_type and entry.document_content_type.startswith("image/"))


templates.env.globals["is_image_attachment"] = is_image_attachment


def save_upload(upload: UploadFile | None) -> tuple[str, str, str] | None:
    if upload is None or not upload.filename:
        return None

    content_type = upload.content_type or ""
    suffix = ALLOWED_UPLOAD_TYPES.get(content_type)
    if suffix is None:
        raise HTTPException(status_code=400, detail="Upload must be a JPG, PNG, WebP, GIF, or PDF file")

    stored_name = f"{uuid4().hex}{suffix}"
    target = UPLOAD_DIR / stored_name
    size = 0
    too_large = False
    try:
        with target.open("wb") as output:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    too_large = True
                    break
                output.write(chunk)
    finally:
        upload.file.close()
    if too_large:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Upload must be 10 MB or smaller")

    return stored_name, Path(upload.filename).name, content_type


def remove_upload(filename: str) -> None:
    if filename:
        (UPLOAD_DIR / filename).unlink(missing_ok=True)


def wants_partial(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, session: SessionDep, next: str = "/"):
    auth_enabled = auth_is_enabled(session)
    if auth_enabled and request_is_authenticated(request):
        return redirect(safe_next_url(next))
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": "", "next": safe_next_url(next), "auth_enabled": auth_enabled},
    )


@app.post("/login")
def login(request: Request, session: SessionDep, password: Annotated[str, Form()], next: Annotated[str, Form()] = "/"):
    password_hash = current_password_hash(session)
    if not password_hash:
        return redirect("/")
    if verify_password(password, password_hash):
        response = redirect(safe_next_url(next))
        set_auth_cookie(response)
        return response
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": "That password did not match.", "next": safe_next_url(next), "auth_enabled": True},
        status_code=401,
    )


@app.post("/logout")
def logout(request: Request):
    response = redirect("/login")
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        {"error": "", "sent": False, "email_configured": recovery_email_is_configured()},
    )


@app.post("/forgot-password", response_class=HTMLResponse)
def forgot_password(request: Request, email: Annotated[str, Form()]):
    requested_email = normalize_email(email)
    if recovery_email_is_configured() and requested_email == RECOVERY_EMAIL:
        token = create_password_reset_token(SESSION_SECRET, RECOVERY_EMAIL)
        reset_url = absolute_url(request, f"/reset-password?token={quote(token, safe='')}")
        try:
            send_password_reset_email(RECOVERY_EMAIL, reset_url)
        except (OSError, smtplib.SMTPException):
            return templates.TemplateResponse(
                request,
                "forgot_password.html",
                {
                    "error": "The reset email could not be sent. Check the server mail settings.",
                    "sent": False,
                    "email_configured": True,
                },
                status_code=500,
            )
    if recovery_email_is_configured():
        return templates.TemplateResponse(
            request,
            "forgot_password.html",
            {"error": "", "sent": True, "email_configured": True},
        )
    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        {
            "error": "Password reset email is not configured on this server.",
            "sent": False,
            "email_configured": False,
        },
        status_code=400,
    )


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(request: Request, token: str = ""):
    valid = bool(RECOVERY_EMAIL and password_reset_token_is_valid(token, SESSION_SECRET, RECOVERY_EMAIL))
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {"error": "" if valid else "This reset link is invalid or expired.", "token": token, "valid": valid},
        status_code=200 if valid else 400,
    )


@app.post("/reset-password", response_class=HTMLResponse)
def reset_password(
    request: Request,
    session: SessionDep,
    token: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
):
    valid = bool(RECOVERY_EMAIL and password_reset_token_is_valid(token, SESSION_SECRET, RECOVERY_EMAIL))
    if not valid:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"error": "This reset link is invalid or expired.", "token": token, "valid": False},
            status_code=400,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"error": "Use at least 8 characters.", "token": token, "valid": True},
            status_code=400,
        )
    if password != confirm_password:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"error": "The passwords did not match.", "token": token, "valid": True},
            status_code=400,
        )
    repo.set_setting(session, PASSWORD_SETTING_KEY, hash_password(password))
    response = redirect("/")
    set_auth_cookie(response)
    return response


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
    category = repo.get_category(session, category_id)
    document_filenames = [entry.document_filename for entry in category.entries if entry.document_filename] if category else []
    repo.delete_category(session, category_id)
    for filename in document_filenames:
        remove_upload(filename)
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
    document: Annotated[UploadFile | None, File()] = None,
):
    if not title.strip():
        raise HTTPException(status_code=400, detail="Entry title is required")
    saved_upload = save_upload(document)
    entry = repo.create_entry(
        session,
        category_id=category_id,
        title=title,
        creator=creator,
        notes=notes,
        tags=tags,
        source_url=source_url,
        image_url=image_url,
        document_filename=saved_upload[0] if saved_upload else "",
        document_original_name=saved_upload[1] if saved_upload else "",
        document_content_type=saved_upload[2] if saved_upload else "",
    )
    return redirect(f"/entries/{entry.id}")


@app.get("/entries/{entry_id}", response_class=HTMLResponse)
def entry_detail(request: Request, session: SessionDep, entry_id: int):
    entry = repo.get_entry(session, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return templates.TemplateResponse(request, "entry_detail.html", {"entry": entry})


@app.get("/entries/{entry_id}/document")
def entry_document(session: SessionDep, entry_id: int):
    entry = repo.get_entry(session, entry_id)
    if entry is None or not entry.document_filename:
        raise HTTPException(status_code=404, detail="Document not found")
    path = UPLOAD_DIR / entry.document_filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document file not found")
    return FileResponse(
        path,
        media_type=entry.document_content_type or "application/octet-stream",
        filename=entry.document_original_name or entry.document_filename,
        content_disposition_type="inline",
    )


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
    document: Annotated[UploadFile | None, File()] = None,
):
    current_entry = repo.get_entry(session, entry_id)
    if current_entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    old_document_filename = current_entry.document_filename
    saved_upload = save_upload(document)
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
        document_filename=saved_upload[0] if saved_upload else None,
        document_original_name=saved_upload[1] if saved_upload else None,
        document_content_type=saved_upload[2] if saved_upload else None,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    if saved_upload:
        remove_upload(old_document_filename)
    return redirect(f"/entries/{entry.id}")


@app.post("/entries/{entry_id}/delete")
def delete_entry(request: Request, session: SessionDep, entry_id: int):
    entry = repo.get_entry(session, entry_id)
    category_id = entry.category_id if entry else None
    document_filename = entry.document_filename if entry else ""
    repo.delete_entry(session, entry_id)
    remove_upload(document_filename)
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
