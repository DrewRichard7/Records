Records
=======

Records is a small local cataloging web app for tracking personal collections: vinyl records, recipes, knitting patterns, books, tools, and anything else worth remembering.

The refactored app is intentionally simple and Raspberry Pi friendly: FastAPI, SQLModel/SQLAlchemy, SQLite, Jinja2 templates, HTMX, and hand-written CSS. There is no Node, React, NiceGUI UI, or frontend build step.

## Run locally

Install dependencies with uv:

```bash
uv sync
```

Start the app with either command:

```bash
uv run python -m records
```

```bash
uv run uvicorn records.main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`.

By default, Records stores SQLite data in `records.db` in the current working directory. To choose another location:

```bash
RECORDS_DB_PATH=/path/to/records.db uv run python -m records
```

The database is initialized automatically at startup. The rough migration preserves older entries that used `category_name` by matching them to existing category names.

## Features

- Create, edit, delete, and view categories.
- Create, edit, delete, and view entries.
- Store title, creator, notes, comma-separated tags, source URL, and optional image URL/path.
- Search entries by title, creator, notes, tags, and category using simple SQL `LIKE` queries.
- Filter category/search views by category, creator, and tag.
- Dense dark server-rendered interface with small HTMX enhancements.

## Raspberry Pi deployment over Tailscale

1. Clone the repo onto the Raspberry Pi, for example `/home/pi/records`.
2. Install uv from <https://docs.astral.sh/uv/getting-started/installation/>.
3. Run `uv sync` in the repo directory.
4. Initialize or migrate the SQLite database by starting the app once. Set `RECORDS_DB_PATH` if you want the database outside the repo.
5. Start manually:

```bash
RECORDS_DB_PATH=/home/pi/.local/share/records/records.db uv run uvicorn records.main:app --host 0.0.0.0 --port 8000
```

6. Create a systemd service such as `/etc/systemd/system/records.service`:

```ini
[Unit]
Description=Records web app
After=network.target

[Service]
WorkingDirectory=/home/pi/records
ExecStart=/home/pi/.local/bin/uv run uvicorn records.main:app --host 0.0.0.0 --port 8000
Restart=always
User=pi
Environment=RECORDS_DB_PATH=/home/pi/.local/share/records/records.db

[Install]
WantedBy=multi-user.target
```

Adjust paths and username for your Pi.

7. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now records.service
sudo systemctl status records.service
```

8. Access Records over Tailscale at `http://<pi-tailscale-ip>:8000` or `http://<magicdns-hostname>:8000`.

## Notes

- This is a rough local-first version and has no authentication. Use it on a trusted LAN/Tailscale network.
- Tags are stored as a comma-separated string for simplicity.
- Images are referenced by URL/path only; uploads are not implemented yet.
- Database migrations are minimal startup migrations, not Alembic migrations.
