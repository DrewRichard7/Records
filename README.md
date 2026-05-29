# Records

A small local cataloging app for vinyl records, books, patterns, tools, and other collections.

## Run locally

```bash
uv run records
```

Then open:

```text
http://localhost:8080
```

By default, the app stores data in `records.db` in the directory where you run it.

To choose a different database path:

```bash
RECORDS_DB_PATH=~/.local/share/records/records.db uv run records
```
