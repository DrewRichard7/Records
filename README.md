Records
=======

Records is a small self-hosted cataloging app for personal collections. Use it to track things you own, want, made, found, or need to remember: vinyl records, books, recipes, knitting patterns, tools, parts, plants, games, supplies, and other collections.

The goal is a fast personal database that works like a searchable secondary memory. If you forget whether you own a book, pattern, record, tool, or recipe, search Records and find it quickly.

Records is designed to run locally on a normal computer or Raspberry Pi and be accessed from a phone, tablet, or laptop over your LAN or over Tailscale.

## Stack

- Python
- FastAPI
- SQLModel / SQLAlchemy
- SQLite
- Jinja2 templates
- HTMX for small interactive updates
- Hand-written CSS
- uv for dependency and project management
- systemd for Raspberry Pi startup

There is no React, Vue, Svelte, Node build step, Tailwind, Bootstrap, or NiceGUI interface.

## Features

- Create, edit, delete, and view categories.
- Create, edit, delete, and view entries.
- Store title, creator, notes, tags, source URL, and optional image URL/path.
- Search entries by title, creator, notes, tags, and category.
- Filter entries by category, creator, and tag.
- View dense database-style entry detail pages.
- Use from a desktop browser or phone browser.
- Add to iPhone home screen with the included app icon.
- Store data in a local SQLite database.

## Project layout

```text
src/records/
  __main__.py              # `python -m records` entrypoint
  main.py                  # FastAPI app, routes, template setup
  db.py                    # SQLite path, engine, startup migrations
  models.py                # SQLModel models
  repo.py                  # CRUD/search helper functions
  templates/               # Jinja2 pages and HTMX partials
  static/css/records.css   # hand-written dark UI CSS
  static/favicon.svg       # browser favicon
  static/apple-touch-icon.png
  static/site.webmanifest
```

## Data model

Records currently has two main tables.

### Category

- `id`
- `name`
- `description`
- `created_at`
- `updated_at`

Categories are broad buckets such as `Books`, `Records`, `Recipes`, `Knitting Patterns`, or `Tools`.

### Entry

- `id`
- `category_id`
- `title`
- `creator`
- `notes`
- `tags`
- `source_url`
- `image_url`
- `created_at`
- `updated_at`

Tags are stored as a comma-separated string for now. This keeps the app simple and fast for the rough local version.

## Requirements

- Python 3.13 or newer, as configured in `pyproject.toml`
- uv
- SQLite, included with Python on normal installs

Install uv using the official instructions:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then restart your shell or make sure uv is on your `PATH`.

## Run locally

Clone the repo and install dependencies:

```bash
uv sync
```

Start Records:

```bash
uv run python -m records
```

Open:

```text
http://127.0.0.1:8000
```

The startup output also prints a `Phone/LAN URL` such as `http://192.168.68.60:8000` when a LAN address can be detected.

You can also run the FastAPI app directly with uvicorn:

```bash
uv run uvicorn records.main:app --host 0.0.0.0 --port 8000
```

The app initializes the SQLite database automatically at startup.

## Database location

By default, Records stores data in `records.db` in the directory where you start the app.

To store the database somewhere else, set `RECORDS_DB_PATH`:

```bash
RECORDS_DB_PATH=/home/pi/.local/share/records/records.db uv run python -m records
```

For a Raspberry Pi or other always-on server, storing the database under `~/.local/share/records/` is cleaner than keeping it in the Git checkout.

Create that directory if needed:

```bash
mkdir -p /home/pi/.local/share/records
```

## Access from another device on your LAN

Start the app bound to all network interfaces:

```bash
uv run python -m records
```

Use the printed `Phone/LAN URL`. It should look like `192.168.x.x`, `10.x.x.x`, or `172.16.x.x` through `172.31.x.x`.

Example:

```text
http://192.168.68.60:8000
```

Open that URL from your phone or another computer on the same Wi-Fi/LAN.

If the page does not load:

- Make sure the app is running with `--host 0.0.0.0`, not only `127.0.0.1`.
- Make sure the phone is on the same Wi-Fi network, not cellular.
- Avoid guest Wi-Fi networks; they often block device-to-device LAN access.
- Make sure the browser is using `http://`, not `https://`.
- Allow port `8000` through the firewall.

On systems using UFW:

```bash
sudo ufw allow 8000/tcp
sudo ufw status
```

## Add to iPhone home screen

Records includes a favicon, Apple touch icon, and web manifest.

On iPhone:

1. Open Records in Safari, for example `http://192.168.68.60:8000` or your Tailscale URL.
2. Tap the Share button.
3. Tap `Add to Home Screen`.
4. Confirm the name `Records`.

The home-screen shortcut should use the included Records icon.

## Raspberry Pi deployment

These instructions assume:

- Raspberry Pi username: `pi`
- Repo path: `/home/pi/records`
- Database path: `/home/pi/.local/share/records/records.db`
- App port: `8000`

Adjust paths and username for your Pi.

### 1. Prepare the Pi

Update packages:

```bash
sudo apt update
sudo apt upgrade
```

Install Git and curl if needed:

```bash
sudo apt install git curl
```

Install uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your shell or source your profile so `/home/pi/.local/bin/uv` is available.

### 2. Clone Records

```bash
cd /home/pi
git clone <your-repo-url> records
cd /home/pi/records
```

If the repo already exists, update it instead:

```bash
cd /home/pi/records
git pull
```

### 3. Install dependencies

```bash
uv sync
```

### 4. Create the database directory

```bash
mkdir -p /home/pi/.local/share/records
```

### 5. Test manual startup

```bash
RECORDS_DB_PATH=/home/pi/.local/share/records/records.db uv run uvicorn records.main:app --host 0.0.0.0 --port 8000
```

From another device on the same LAN, open:

```text
http://<pi-lan-ip>:8000
```

Find the Pi LAN IP with:

```bash
hostname -I
```

Stop the manual server with `Ctrl+C` after confirming it works.

### 6. Create a systemd service

Create `/etc/systemd/system/records.service`:

```bash
sudo nano /etc/systemd/system/records.service
```

Example service:

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

If uv is installed somewhere else, find it with:

```bash
which uv
```

Then adjust `ExecStart`.

### 7. Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now records.service
sudo systemctl status records.service
```

View logs:

```bash
journalctl -u records.service -f
```

Restart after pulling updates:

```bash
sudo systemctl restart records.service
```

### 8. Open the firewall if needed

If UFW is enabled:

```bash
sudo ufw allow 8000/tcp
sudo ufw status
```

## Remote access with Tailscale

Tailscale lets you access Records remotely without exposing it to the public internet. This is the recommended remote-access option for a personal app without built-in authentication.

### 1. Install Tailscale on the Pi

Use Tailscale's official install command:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Start and authenticate:

```bash
sudo tailscale up
```

Follow the login URL shown in the terminal.

### 2. Install Tailscale on your phone/laptop

Install Tailscale on the devices you want to use remotely and sign into the same Tailnet account.

### 3. Find the Pi's Tailscale address

On the Pi:

```bash
tailscale ip -4
```

You will get an address similar to:

```text
100.x.y.z
```

Access Records from any device on your Tailnet:

```text
http://100.x.y.z:8000
```

### 4. Use MagicDNS if enabled

If MagicDNS is enabled in the Tailscale admin console, you can use the Pi hostname instead of the numeric Tailscale IP.

Example:

```text
http://raspberrypi:8000
```

Depending on your Tailnet DNS settings, the full name may look like:

```text
http://raspberrypi.<tailnet-name>.ts.net:8000
```

### 5. Security notes for Tailscale

- Records currently has no login screen.
- Anyone with network access to the app URL can use it.
- Tailscale access is usually appropriate for personal use because only devices in your Tailnet can reach the Pi.
- Do not port-forward Records directly from your router to the public internet unless you add authentication or place it behind a trusted auth proxy.

## Updating the app on the Pi

```bash
cd /home/pi/records
git pull
uv sync
sudo systemctl restart records.service
```

Check logs if it does not start:

```bash
journalctl -u records.service -n 100 --no-pager
```

## Backups

Records stores data in a SQLite database file. Back up that file regularly.

If using the example Pi path:

```bash
cp /home/pi/.local/share/records/records.db /home/pi/records-backup-$(date +%F).db
```

For safer backups while the app may be running, use SQLite's backup command:

```bash
sqlite3 /home/pi/.local/share/records/records.db ".backup '/home/pi/records-backup.db'"
```

Copy backups to another machine periodically.

## Troubleshooting

### The app works on the Pi but not from my phone

- Use `http://<pi-lan-ip>:8000`, not `https://`.
- Make sure the app is running with `--host 0.0.0.0`.
- Make sure the phone is on the same Wi-Fi network.
- Disable guest Wi-Fi or client isolation.
- Allow port `8000/tcp` through the firewall.

### `uv run uvicorn` does not start

Try the module form:

```bash
uv run python -m uvicorn records.main:app --host 0.0.0.0 --port 8000
```

If your shell has an old virtualenv active, deactivate it or run:

```bash
deactivate
uv sync --reinstall
```

### The service fails under systemd

Check logs:

```bash
journalctl -u records.service -n 100 --no-pager
```

Common causes:

- `WorkingDirectory` path is wrong.
- `ExecStart` uv path is wrong.
- `User` does not match the repo/database owner.
- `RECORDS_DB_PATH` parent directory does not exist.
- Port `8000` is already in use.

### Find what is listening on port 8000

```bash
ss -ltnp '( sport = :8000 )'
```

## Current limitations

- No authentication yet.
- No image upload handling yet; image field is URL/path only.
- Tags are comma-separated text, not a normalized many-to-many tag table.
- Search uses simple SQL matching rather than full-text search.
- Startup migrations are intentionally small and local-first, not Alembic migrations.

## Suggested future improvements

- Add optional login/password protection.
- Add image upload and thumbnail handling.
- Add export/import tools.
- Add SQLite full-text search.
- Add tag management and tag rename tools.
- Add per-category custom fields.
- Add backup/restore commands.
