# SAIL MIS Report Generator & Ingestion Portal

Operation Monthly Informatics (OMI) Management Information System for Steel Authority of India Limited (SAIL). A **Python FastAPI backend** handles data ingestion, storage and PDF generation (Playwright + headless Chromium); a **Next.js frontend** provides report preview, inline editing, and Excel/PDF data ingestion.

> **Setting up a new machine?** Follow [`backend/docs/SETUP.md`](backend/docs/SETUP.md) — Python, Node, MySQL, restoring data from backup, and `.env` settings.

---

## Architecture Overview

| Layer | Technology | Role |
|---|---|---|
| Frontend | Next.js 16 + React 19 (`/frontend`) | Report preview, inline editing, data upload UI |
| Backend | FastAPI + Python 3.11 (`/backend`) | REST API, extraction, Playwright/Chromium PDF generation |
| Database | MySQL (default on this deployment) or SQLite fallback | Production actuals/plan, techno-economic params, page configs |

The database engine is chosen by `DB_ENGINE` in `backend/.env` (`mysql` or `sqlite`). Backend code writes SQLite-style SQL; `backend/dbengine.py` translates it for MySQL. The MySQL schema lives in `backend/scripts/mysql_schema.sql` plus `backend/scripts/migrate_*.sql`.

Related docs: [`docs/DATA_MODEL_AND_REPORT_PAGES.md`](docs/DATA_MODEL_AND_REPORT_PAGES.md) (which table feeds which page), [`backend/docs/TECHNO_EXTRACTION_GUIDE.md`](backend/docs/TECHNO_EXTRACTION_GUIDE.md), [`backend/docs/PDF_LAYOUT_GUARDRAILS.md`](backend/docs/PDF_LAYOUT_GUARDRAILS.md).

---

## Report Coverage (Pages 1–35+)

Core monthly report pages are listed below. The backend also generates many additional pages and exports (key highlights, records, SAIL mines, coal, power, special steel trends, D.O. letter, etc.) — see `backend/page_*.py` and `docs/DATA_MODEL_AND_REPORT_PAGES.md`.

| Pages | Content |
|---|---|
| 1 | Cover Page |
| 2 | Index |
| 3 | Production Summary (SAIL-level) |
| 4 | Month-Wise Production (all plants, items, plan vs actual) |
| 5–6 | Plant-Wise Production Performance |
| 7–12 | Month-Wise Production Trends (item-wise) |
| 13 | Concast Production Performance |
| 14 | Production by Process |
| 15–17 | Category-Wise Saleable Steel (BSP / DSP+RSP / BSL+ISP) |
| 18 | Segment-Wise Production |
| 19–23 | Special Steel Performance — BSP, DSP, RSP, BSL, ISP |
| 24 | Special Steel — SAIL Consolidated |
| 25 | Opening Stock |
| 26 | IPT Status |
| 27 | Major Techno-Economic Parameters |
| 28 | Coke & Coal Chemicals, Sinter Plant (Techno) |
| 29 | Iron Making (Techno) |
| 30 | BOF Shop (Techno) |
| 31–35 | Mill-Wise Techno — BSP / DSP / RSP / BSL / ISP |

---

## Supported Plants & Data Sources

### Production Actuals (`/api/upload-excel`)

> API only — the `/upload` page no longer calls this endpoint directly; these files are uploaded through **Preview & Insert** below.

| Plant | File Type | Sheet / Detection |
|---|---|---|
| RSP | `.xlsx` Final Monthly | Sheets `page-9` + `page 1-8` — set month manually |
| RSP | `.xlsx` Morning Report | Sheet starts with `RSP Morning Report Data for-` — month from A2 |
| ISP | `.xlsx` Final Monthly | Sheet `Maj Production Summ` — set month manually |
| ISP | `.xlsx` Morning Report | Sheet `DAILYREPORT1` — month from K5 |
| BSP | `.xls` PPC MIS | Sheet `S1` — month from N1, auto-detected |
| BSL | `.xlsx` DPR Mail | Sheet `DPR` — month from O1, auto-detected |
| DSP | `.xls` MCR-I | Tab-separated text — month from header, auto-detected |

### Extract with Preview → Insert (`/api/extract-preview` + `/api/confirm-extraction`)

Extracts production, techno-economic parameters, and special steel data with a preview step before DB insertion.

| Plant | File Type | What is extracted |
|---|---|---|
| RSP | `.xlsx` (Final Monthly / Morning Report / Techno) | Production + techno params (auto-detected) |
| ISP | `.xlsx` (Final Monthly / Morning Report / Summarized Monthly) | Production (~17–19 items) + techno params (B-FCE sheet, ~37 params) |
| BSP | `.xlsx` `BSP_Spstl-*.xlsx` | Special Steel orders & loading → `special_steel_orders` |
| BSP | `.xlsx` `BSP-3-page-Tech.xlsx` | 62 techno params (Coke, Sinter, BF, SMS, Mills, Energy) |
| BSP-OISCO | `.xlsx` `OISCO_*.xlsx` | 35 OISCO techno params (BF CDI, Fuel Rate, O2, LD Gas, etc.) |
| DSP | `.pdf` OMI Report | Production + special steel + techno (3-step extraction) |
| DSP | `.xls` MCR-I | 21 production items |

### ABP Plan Targets (`/api/upload-excel-plan`)

Populates `production_plan_table` for all 12 months in a single upload.

| Plant | Sheet Name |
|---|---|
| RSP | `sheet1` |
| ISP | `SUMM PROD` |
| BSP | `Table 1` |
| DSP | `Monthwise` |
| BSL | `PLAN SUMMARY` |
| ASP / SSP / VISL | `APP 26-27` (combined file, all three plants in one upload) |

---

## Database Tables

| Table | Purpose |
|---|---|
| `production_table` | Monthly actual production (all plants, all items) |
| `production_plan_table` | ABP monthly plan targets |
| `techno_table` | Legacy techno-economic params (plant-level, from old RSP extraction) |
| `techno_param_master` | Master list of techno params (group, section, label, unit, sort_order) |
| `techno_monthly` | Monthly techno actuals + cumulative (linked to param_master via param_id) |
| `techno_target` | Annual techno targets by FY and param_id |
| `special_steel_orders` | Grade-wise special steel orders & actual despatch |
| `opening_stock` | Raw material stocks as on 1st of each month |
| `ipt_status` | Inter-plant transfer status |
| `page_configs` | Saved page configuration JSON per report month |
| `extraction_log` | Audit trail of every upload (plant, month, file, items extracted) |

---

## System Requirements

| Tool | Version |
|---|---|
| Python | **3.11** (venv at `backend/venv`) |
| Node.js | v20.9+ |
| MySQL | 8.0.19+ (9.x in use), unless running with `DB_ENGINE=sqlite` |
| Tesseract OCR | optional — only for ISP Special Steel image extraction |

No GTK/WeasyPrint system libraries are needed — PDFs are rendered by Playwright's headless Chromium.

Full step-by-step install (including MySQL and data restore): [`backend/docs/SETUP.md`](backend/docs/SETUP.md).

---

## 1. Backend Setup

```powershell
cd backend
py -3.11 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m playwright install chromium
copy .env.example .env      # then fill in secrets and DB settings
```

- Always invoke tools as `venv\Scripts\python.exe -m <tool>` (`pip`, `uvicorn`, `playwright`, `pytest`). The pip-generated `.exe` launchers are blocked by Device Guard on the deployment machine.
- `requirements.txt` is pinned to exact versions (full set in `requirements-lock.txt`). After any `pip install -r requirements.txt` on an existing machine, also run `venv\Scripts\python.exe -m playwright install --force chromium` — pip never updates the Chromium binary, and a stale one changes PDF pagination.
- CORS: set `FRONTEND_ORIGIN` if the frontend is served from a non-default origin.
- Two-step login is on by default: after the password, a 6-digit code is emailed (SMTP settings in `.env`) and must be entered before a session starts. Codes expire in 10 minutes, stop working after 5 wrong tries, and can be resent once a minute. Set `LOGIN_2FA=off` in `backend/.env` to fall back to password-only login if outbound mail is unavailable.

---

## 2. Frontend Setup

```powershell
cd frontend
npm install
copy .env.example .env.local
```

`NEXT_PUBLIC_API_URL` in `.env.local` is the base URL the **browser** uses; it is baked in at build time. The frontend runs through `frontend/server.js`, which proxies `/api/*` to the backend on port 8082.

---

## 3. Running

| Mode | Command | URLs |
|---|---|---|
| Development | `start-development.bat` | frontend `http://localhost:3000`, backend `http://127.0.0.1:8082` (both auto-reload) |
| Production (LAN) | `start-production.bat` | frontend on port 80; rebuild first with `cd frontend && npm run build` |

Both scripts free the ports, start MySQL if needed, sync pinned Python dependencies and Chromium, enable the git hooks in `.githooks/`, and launch backend and frontend in separate windows.

---

## 4. Application URLs

| URL | Description |
|---|---|
| `http://localhost:3000` | Dashboard — month selector, report preview navigation |
| `http://localhost:3000/upload` | Data ingestion — preview & insert actuals / techno / special steel, or ABP plan |
| `http://localhost:3000/report` | Full report viewer — multi-page A4 preview + PDF download |
| `http://localhost:8082/docs` | FastAPI Swagger UI for API exploration |

---

## 5. Upload Page — Data Upload Modes

The `/upload` page has a single **Data Upload** section with two modes selectable via tab. Every upload is previewed before it is written to the database; the old "direct extraction (no preview)" form has been removed from the UI. The "Guidelines for Ingestion" card is collapsed by default — click it to expand.

| Mode | Purpose | Endpoint |
|---|---|---|
| **Preview & Insert** | Extract production + techno + special steel, review before inserting | `POST /api/extract-preview` → `POST /api/confirm-extraction` |
| **ABP Plan** | Extract annual plan targets for all 12 months | `POST /api/upload-excel-plan` |

---

## 6. Backend Tests (Golden-File Extraction Tests)

Extraction regressions are guarded by golden-file tests: each plant extractor's
`extract_preview()` runs against a sample file committed under `Report_format/`
and its full output is compared to a JSON snapshot in `backend/tests/goldens/`.

```bash
cd backend
venv/Scripts/python -m pytest tests -q                    # run tests
venv/Scripts/python -m pytest tests -q --update-goldens   # regenerate after an intentional change
```

After `--update-goldens`, review the golden diff in git before committing —
the diff is the behaviour change. Add a new case in
`backend/tests/test_extraction_goldens.py` when a new extractor or sample
file format is introduced.

---

## 7. Report PDF Notes

The PDF layout is tuned to the millimetre. Read [`backend/docs/PDF_LAYOUT_GUARDRAILS.md`](backend/docs/PDF_LAYOUT_GUARDRAILS.md) before changing templates, CSS, `pdf.py` or `layout_config.json`. `backend/layout_guard.py` runs from the git pre-commit hook; check a real render with `venv\Scripts\python.exe layout_guard.py --render YYYY-MM` (from `backend/`).

- Pages 1–6: A4 Portrait with tight margins (10mm sides) for maximum table width.
- Pages 7–26: A4 Portrait, standard margins.
- Pages 27–35 (Techno): **A4 Landscape** — wide multi-column tables with month-wise actuals.
- Font: Arial Narrow on page 7 (trend), standard Arial elsewhere.
- All tonnage values stored and displayed as `'000 T` unless otherwise noted.
- Financial year convention: April–March. Format `YYYY-YY` (e.g. `2025-26`). Plan rows show short `YY-YY` format.

