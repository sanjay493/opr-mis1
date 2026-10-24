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

- MySQL only (no SQLite, no `DB_ENGINE`): database **`mis_reports_v2`** on 127.0.0.1, port **3307**, set by `MYSQL_*` in `backend/.env`. The old v1 database `mis_reports` is read-only history after the cutover; the move is `backend/docs/DB_V2_CUTOVER.md`.
- All SQL lives only in `backend/repo/<module>.py` (import `repo.<module>` directly; month/FY helpers are in `month_utils.py`), written as **native MySQL with `%s` placeholders**. Connections come from `repo.conn` / `dbengine.connect()`. There is no dialect translation any more: do not write `?`, `ON CONFLICT` or `INSERT OR REPLACE`. No other file may contain SQL.
- The schema is `backend/scripts/v2/schema_v2.sql` (header = conventions and v1-to-v2 table map) plus `scripts/v2/seed_cal_month.sql`. A new table/column goes into `schema_v2.sql` **and** a `scripts/v2/migrate_<what>.sql` for the live database. The older `scripts/*.sql`, `mysql_schema.sql` and `backfill_*.py` hold v1 SQL: historical, never run against v2.
- Guard tests (keep green): `tests/test_repo_boundary.py` (no SQL outside `repo/`), `tests/test_repo_writes_bump.py` (every repo write bumps `data_version` first; after a manual SQL edit run `UPDATE data_version SET n=n+1` or restart, else stale cached pages), `tests/test_repo_oracle.py` (repo functions keep the frozen v1 signatures), `tests/test_no_unbound_local_imports.py` (pyflakes F823).
- Data model and which table feeds which report page: `docs/DATA_MODEL_AND_REPORT_PAGES.md`.

## Layout

- `backend/main.py` — FastAPI app and most routes; `api_*.py` — feature routers.
- `backend/page_*.py` + `backend/page_templates/` — one module per report page; `pdf.py` — assembles and renders the PDF.
- `backend/excel_extractors/` — per-plant Excel/PDF extractors. See `backend/docs/TECHNO_EXTRACTION_GUIDE.md`.
- `backend/techno_*.py` — techno-economic parameter registry, periods, cumulatives, aggregates.
- Manual-entry forms live in `frontend/src/components/entry/<slug>/Form.js` and are shown as tabs of five grouped pages (`/data-entry/production-techno`, `mines`, `special-steel-entry`, `commentary`, `reference`) — groups/tabs in `components/entry/entryGroups.js`, shell in `EntryTabs.js`. The old `/data-entry/<slug>` routes are redirects to `?tab=<slug>`. Add a new form by creating its folder there, adding it to `entryGroups.js` and the `FORMS` map in `EntryTabs.js`.
- Most `/reports/<slug>` pages likewise live in `frontend/src/components/reports/<slug>/View.js` and are shown as tabs of grouped pages (`/reports/production-analysis`, `special-steel-ipt`, `mines`, `loss-breakdown`, `highlights-records`, `external`) — groups/tabs in `components/reports/reportGroups.js`, shell in `ReportTabs.js`. Techno's reports are clubbed separately into `/reports/techno` (own tab pattern, `components/techno/`). Old `/reports/<slug>` routes redirect to `?tab=<slug>`. Add a new report by creating its folder there, adding it to `reportGroups.js` and the `VIEWS` map in `ReportTabs.js`.
- `frontend/src/app/` — Next.js app router pages (`report`, `data-entry`, `upload`, `admin`, …). Read `frontend/AGENTS.md` before frontend work: Next 16 differs from older versions; check `frontend/node_modules/next/dist/docs/`.
- Files named `_*`, `__*`, `debug_*`, `test_*.py` in `backend/` root are ad-hoc scratch scripts, not part of the app.

## PDF layout is fragile

The report layout is tuned to the millimetre. Before touching CSS, templates, `pdf.py`, `layout_config.json` or page modules, read `backend/docs/PDF_LAYOUT_GUARDRAILS.md`.
- `backend/layout_guard.py` runs as a Claude Code PostToolUse hook and as a git pre-commit hook (`.githooks/`); heed its warnings.
- Verify a real render: `python layout_guard.py --render YYYY-MM` (from `backend/`). After an intended layout change: `--accept`.
- Finishing a layout change: `--accept --render 2026-08`, commit (include `layout_baseline.json`), tag the next `pdf-layout-baseline-YYYY-MM-DD[b,c,…]`, and replace the old tag name in `PDF_LAYOUT_GUARDRAILS.md` (3 places). Push `main` plus the tag only when the user asks.
- Pages that come out a bit too tall get scaled to fit (the render log's `fit-to-page: 5 @ 97%`). Chromium rounds scaled border widths down, so a 2px border prints as 1px there. Use 1px, or declare 2.4px to get 2px.
- The Index page (2) prints with `main.html`'s default `@page` margin (12/15/12/15mm), not `_FRONT_MARGIN`. Its table is `data-vgrow`, so its rows stretch to fill the sheet.
- Check colours and borders against the PDF itself rather than by eye: render the page with pypdfium2 to look at it, and read the table lines with pdfplumber (`page.rects`: each one's width and `non_stroking_color`).

## Colours

- Every PDF colour is a named key in `backend/colors_config.json`, used as `{{ colors.<key> }}`. Never hard-code a hex value in a template. Edits apply on the next render.
- `colors_loader.py` `_DEFAULTS` mirrors every JSON key (same values) as a fallback. Add a new key to both files.
- `perf_*` keys are the table colours shared by pages 4, 5-6, Concast, Cat-wise and Segment-wise. Plan column: gold `perf_app_*`. Actual columns: green `perf_act_*`. %Gr columns: `perf_gr_bg`. Page 4's Ann. Cap. column: `perf_cap_*`. Don't retint the shared `highlight_*` keys for one page; other pages use them too.
- The frontend preview templates (`frontend/src/components/*Template.js`) keep their own copies of these hex values, so a colour change does not reach the browser preview automatically.

## Verifying changes

- Tests: `cd backend && venv/Scripts/python.exe -m pytest tests` — golden-file extractor tests; `--update-goldens` only when output is meant to change.
- Syntax check: `venv/Scripts/python.exe -m py_compile <file>`.
- API: `curl -s "http://127.0.0.1:8082/api/data?month=2026-04"`; UI: `http://localhost:3000/report`.
- Frontend lint: `cd frontend && npm run lint`.
