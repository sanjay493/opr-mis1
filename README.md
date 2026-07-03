# SAIL MIS Report Generator & Ingestion Portal

Operation Monthly Informatics (OMI) Management Information System for Steel Authority of India Limited (SAIL). A **Python FastAPI backend** handles database storage and WeasyPrint PDF generation; a **Next.js frontend** provides report preview, inline editing, and Excel/PDF data ingestion.

---

## Architecture Overview

| Layer | Technology | Role |
|---|---|---|
| Frontend | Next.js 14 (`/frontend`) | Report preview, inline editing, data upload UI |
| Backend | FastAPI + Python 3.11 (`/backend`) | REST API, SQLite queries, WeasyPrint PDF generation |
| Database | SQLite (`mis_reports.db`) | Production actuals/plan, techno-economic params, page configs |

---

## Report Coverage (Pages 1–35+)

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

- **Node.js**: v18.x or v20.x (LTS)
- **Python**: 3.11.x (3.9–3.12 supported)
- **pip**: Python package manager

---

## 1. System-Specific Dependencies (WeasyPrint)

WeasyPrint requires Cairo, Pango, and GObject system libraries.

### Windows
1. Download and install the GTK3 runtime from [GTK-for-Windows-installer](https://github.com/tschoonj/GTK-for-Windows-installer/releases).
2. Add the GTK `bin` folder (e.g. `C:\Program Files\GTK3-Runtime\bin`) to `Path`.

### Linux (Ubuntu / Debian)
```bash
sudo apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

### macOS
```bash
brew install pango cairo gdk-pixbuf libffi
```

---

## 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# Linux/macOS:  source venv/bin/activate
# Windows CMD:  venv\Scripts\activate
# Windows PS:   .\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

> `mis_reports.db` is created automatically on first run.

### Start the Backend

```bash
# Development (auto-reload)
uvicorn main:app --host 127.0.0.1 --port 8082 --reload

# Windows PowerShell
$env:PORT="8082"; uvicorn main:app --host 127.0.0.1 --port 8082 --reload
```

Set `FRONTEND_PORT` or `FRONTEND_ORIGIN` env vars to configure CORS for non-default frontend ports:
```powershell
$env:PORT="8082"; $env:FRONTEND_PORT="3001"; uvicorn main:app --host 127.0.0.1 --port 8082 --reload
```

---

## 3. Frontend Setup

```bash
cd frontend
npm install
```

Create `frontend/.env.local` pointing to the backend:
```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8082
```

```bash
npm run dev        # development server on port 3000
npm run build      # production build
npm run start      # serve production build
```

---

## 4. Application URLs

| URL | Description |
|---|---|
| `http://localhost:3000` | Dashboard — month selector, report preview navigation |
| `http://localhost:3000/upload` | Data ingestion — upload actuals, techno files, or ABP plan |
| `http://localhost:3000/report` | Full report viewer — multi-page A4 preview + PDF download |
| `http://localhost:8082/docs` | FastAPI Swagger UI for API exploration |

---

## 5. Upload Page — Data Upload Modes

The `/upload` page has a single **Data Upload** section with three modes selectable via tab:

| Mode | Purpose | Endpoint |
|---|---|---|
| **Actuals** | Quick extract from production Excel — no preview, direct DB insert | `POST /api/upload-excel` |
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

- Pages 1–6: A4 Portrait with tight margins (10mm sides) for maximum table width.
- Pages 7–26: A4 Portrait, standard margins.
- Pages 27–35 (Techno): **A4 Landscape** — wide multi-column tables with month-wise actuals.
- Font: Arial Narrow on page 7 (trend), standard Arial elsewhere.
- All tonnage values stored and displayed as `'000 T` unless otherwise noted.
- Financial year convention: April–March. Format `YYYY-YY` (e.g. `2025-26`). Plan rows show short `YY-YY` format.

