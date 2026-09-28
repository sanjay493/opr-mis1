# SAIL MIS Report Generator

Monthly MIS report for SAIL: a FastAPI backend that ingests plant Excel/PDF files and renders the report PDF, and a Next.js frontend for preview, data entry and uploads.

## Running

- Dev: `start-development.bat` — backend `http://127.0.0.1:8082` (uvicorn `--reload`), frontend `http://localhost:3000` (via `frontend/server.js`, proxies `/api/*` to 8082). Both auto-reload; no restart needed after edits.
- Prod: `start-production.bat` — frontend on port 80; rebuild with `cd frontend && npm run build` after frontend changes.

## Python

- Always use the venv: `backend/venv/Scripts/python.exe`. Not anaconda, `py`, or the system Python.
- Run tools as `python.exe -m <tool>` (`-m pip`, `-m uvicorn`, `-m playwright`, `-m pytest`). The pip-generated `.exe` launchers are blocked by Device Guard on this machine.
- `backend/requirements.txt` is pinned exactly. After changing it: `pip install -r requirements.txt`, regenerate `requirements-lock.txt` with `pip freeze`, and run `python -m playwright install --force chromium` (pip never updates the Chromium binary; a stale one changes PDF pagination).

## Database

- Engine is chosen by `DB_ENGINE` in `backend/.env`; **this machine runs `mysql`** (`mis_reports` on 127.0.0.1:3306). `backend/mis_reports.db` (SQLite) is only the fallback/legacy engine — don't assume queries against it reflect live data.
- All code goes through `db.connect()` → `dbengine.py`, which translates sqlite-dialect SQL (`?`, `ON CONFLICT`, `INSERT OR REPLACE`) to MySQL. Keep writing sqlite-dialect SQL in the backend.
- MySQL schema lives in `backend/scripts/mysql_schema.sql` plus `scripts/migrate_*.sql`; `init_db`'s CREATE TABLEs only run under SQLite. A new table/column needs both.
- Data model and which table feeds which report page: `docs/DATA_MODEL_AND_REPORT_PAGES.md`.

## Layout

- `backend/main.py` — FastAPI app and most routes; `api_*.py` — feature routers.
- `backend/page_*.py` + `backend/page_templates/` — one module per report page; `pdf.py` — assembles and renders the PDF.
- `backend/excel_extractors/` — per-plant Excel/PDF extractors. See `backend/docs/TECHNO_EXTRACTION_GUIDE.md`.
- `backend/techno_*.py` — techno-economic parameter registry, periods, cumulatives, aggregates.
- `frontend/src/app/` — Next.js app router pages (`report`, `data-entry`, `upload`, `admin`, …). Read `frontend/AGENTS.md` before frontend work: Next 16 differs from older versions; check `frontend/node_modules/next/dist/docs/`.
- Files named `_*`, `__*`, `debug_*`, `test_*.py` in `backend/` root are ad-hoc scratch scripts, not part of the app.

## PDF layout is fragile

The report layout is tuned to the millimetre. Before touching CSS, templates, `pdf.py`, `layout_config.json` or page modules, read `backend/docs/PDF_LAYOUT_GUARDRAILS.md`.
- `backend/layout_guard.py` runs as a Claude Code PostToolUse hook and as a git pre-commit hook (`.githooks/`); heed its warnings.
- Verify a real render: `python layout_guard.py --render YYYY-MM` (from `backend/`). After an intended layout change: `--accept`.

## Verifying changes

- Tests: `cd backend && venv/Scripts/python.exe -m pytest tests` — golden-file extractor tests; `--update-goldens` only when output is meant to change.
- Syntax check: `venv/Scripts/python.exe -m py_compile <file>`.
- API: `curl -s "http://127.0.0.1:8082/api/data?month=2026-04"`; UI: `http://localhost:3000/report`.
- Frontend lint: `cd frontend && npm run lint`.
