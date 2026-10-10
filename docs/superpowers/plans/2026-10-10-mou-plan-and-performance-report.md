# MoU Plan & APP/MoU Performance Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store SAIL's month-wise MoU targets per plant (uploaded from the
MoU workbook), and turn the `/reports/excel` "Plant Wise Performance" tab
into a two-page APP + MoU report with Excel/PDF download and a 0–3
decimal-places setting.

**Architecture:** A new `mou_plan_table` with the same shape as
`production_plan_table`. An extractor and preview/insert API feed it, the
same way Power-OIS does. `page4.generate_page4_rows` gains
`basis="app"|"mou"`: it switches the plan source table, and for MoU keeps
only the 5 MoU items. `api_plant_performance.py` serves both bases as JSON,
a two-sheet xlsx and a two-page PDF. The PDF uses its own HTML template,
rendered with Playwright, outside the layout-guarded main report.

**Tech Stack:** FastAPI, openpyxl, Playwright (Chromium), MySQL via
`db.connect()` (sqlite-dialect SQL), Next.js 16 client components.

**Spec:** `docs/superpowers/specs/2026-10-10-mou-plan-and-performance-report-design.md`

## Global Constraints

- Python only via `backend/venv/Scripts/python.exe`, tools as `python.exe -m <tool>`.
- Backend SQL stays sqlite-dialect (`?`, `ON CONFLICT … DO UPDATE`); `dbengine.py` translates it for MySQL.
- A new table needs `scripts/mysql_schema.sql` + a `scripts/migrate_*.sql` + `db.init_db` (SQLite).
- The main monthly PDF report (page 4) must render exactly as before: `layout_guard.py --render 2026-08` stays OK.
- PDF colours come from `colors_config.json` keys (`perf_app_*`, `perf_act_*`, `perf_gr_bg`, `perf_cap_*`), never hard-coded hex.
- Decimals: one setting 0–3 for tonnage; percentages always whole numbers.
- MoU item names stored as page-4 `db_item` names: `Hot Metal`, `Total Crude Steel`, `Saleable Steel`, `Pig Iron`, `Finished Steel`.
- Unit '000 T.

## Review Focus

- Re-uploading the same MoU file: the user expects a "values already exist, replace?" confirmation, then identical data (no duplicates). The test is in Task 3.
- A FY with no MoU uploaded (e.g. 2025-26 months): the MoU page should show blank MoU columns and a visible note, not crash or show zeros. The test is in Task 5 (`has_plan` false).
- The decimals parameter outside 0–3, or not a number: the user expects a 400, not a 500 or a silently clamped value. The test is in Task 5.
- The MoU workbook's own SAIL row disagreeing with the plant sum: the user expects a warning in the preview. The test is in Task 2.
- The APP page via the new code path must equal today's output exactly (same rows, same numbers). The test is in Task 4 (`basis="app"` equals the default call).

---

### Task 1: `mou_plan_table` schema

**Files:**
- Modify: `backend/scripts/mysql_schema.sql` (after the `production_plan_table` block, ~line 25)
- Create: `backend/scripts/migrate_mou_plan_table.sql`
- Modify: `backend/db.py` (in `init_db`, next to the `power_data_table` CREATE, ~line 86)
- Modify: `docs/DATA_MODEL_AND_REPORT_PAGES.md` (new subsection after "4.2 Power")

**Interfaces:**
- Produces: table `mou_plan_table(report_month, plant_name, item_name, month_actual)`, PK on the first three.

- [ ] **Step 1: Add to `mysql_schema.sql`** after `production_plan_table`:

```sql
-- MoU (Memorandum of Understanding) month-wise production targets, same
-- shape as production_plan_table. Fed by api_mou_plan.py from the yearly
-- "MoU YY-YY.xlsx" workbook; read by page4.generate_page4_rows(basis="mou").
CREATE TABLE IF NOT EXISTS mou_plan_table (
    report_month CHAR(7)      NOT NULL,
    plant_name   VARCHAR(32)  NOT NULL,
    item_name    VARCHAR(64)  NOT NULL,
    month_actual DOUBLE,
    PRIMARY KEY (report_month, plant_name, item_name)
) ENGINE=InnoDB;
```

- [ ] **Step 2: Create `scripts/migrate_mou_plan_table.sql`** containing
the comment line `-- MoU month-wise plan (api_mou_plan.py). 2026-10-10.`
followed by the same CREATE TABLE as Step 1.

- [ ] **Step 3: Add to `db.init_db`** right after the `power_data_table` CREATE:

```python
    # MoU month-wise production targets — see api_mou_plan.py.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mou_plan_table (
            report_month TEXT,
            plant_name TEXT,
            item_name TEXT,
            month_actual REAL,
            PRIMARY KEY (report_month, plant_name, item_name)
        )
    """)
```

- [ ] **Step 4: Apply to the live MySQL DB**

```bash
cd backend && venv/Scripts/python.exe -c "
import db, re
sql = open('scripts/migrate_mou_plan_table.sql', encoding='utf-8').read()
stmt = re.sub(r'--[^\n]*\n', '', sql).strip().rstrip(';')
c = db.connect(); cur = c.cursor(); cur.execute(stmt); c.commit()
cur.execute('SELECT COUNT(*) FROM mou_plan_table'); print(cur.fetchone())"
```
Expected: `(0,)`

- [ ] **Step 5: Document** in `DATA_MODEL_AND_REPORT_PAGES.md` under §4 a
`mou_plan_table` subsection: `(report_month, plant_name, item_name)` →
`month_actual` ('000 T). Populated by `excel_extractor_mou_plan.py` via
`api_mou_plan.py` (`POST /api/mou-plan/insert`, Uploads page). Read by
`page4.generate_page4_rows(basis="mou")` → `/reports/excel` Plant Wise
Performance (MoU page). Also add a row to the uploads table at line ~612.

- [ ] **Step 6: Syntax check and commit**

```bash
cd backend && venv/Scripts/python.exe -m py_compile db.py
git add backend/scripts/mysql_schema.sql backend/scripts/migrate_mou_plan_table.sql backend/db.py docs/DATA_MODEL_AND_REPORT_PAGES.md
git commit -m "Add mou_plan_table for month-wise MoU targets"
```

---

### Task 2: MoU workbook extractor

**Files:**
- Create: `backend/excel_extractors/excel_extractor_mou_plan.py`
- Test: `backend/tests/test_mou_plan_extractor.py`

**Interfaces:**
- Produces: `extract_mou_plan(file_path: str) -> dict` with keys
  `records` (list of `{"report_month","plant_name","item_name","value"}`),
  `months` (sorted list of str), `items_found` (list of str), `warnings`
  (list of str). Raises `ValueError` if no usable sheet.

- [ ] **Step 1: Write the failing tests** `tests/test_mou_plan_extractor.py`:

```python
"""MoU month-wise plan extractor (excel_extractor_mou_plan.py)."""
import datetime
import sys
from pathlib import Path

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "excel_extractors"))
from excel_extractor_mou_plan import extract_mou_plan  # noqa: E402

from conftest import find_sample

MONTHS = [datetime.datetime(2026 if m >= 4 else 2027, m, 1) for m in (4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3)]


def _build(path, sail_hm_apr=30.0):
    """Hot Metal: BSP 10/month, DSP 20/month, then 'SAIL - 5PL' and 'SAIL'
    totals (item name only on the first row, as in the merged original).
    Crude Steel: BSP 5, ASP 1, SAIL 6."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MoU 26-27"
    ws.cell(1, 1, "Monthwise Production MoU Target : 2026-27")
    ws.cell(3, 1, "Items")
    ws.cell(3, 2, "Plant")
    for i, d in enumerate(MONTHS):
        ws.cell(3, 3 + i, d)
    ws.cell(3, 15, "1st Qtr")
    rows = [
        ("Hot Metal", "BSP", 10.0), (None, "DSP", 20.0), (None, "SAIL - 5PL", 30.0), (None, "SAIL", 30.0),
        ("Crude Steel", "BSP", 5.0), (None, "ASP", 1.0), (None, "SAIL ", 6.0),
    ]
    for r, (item, plant, v) in enumerate(rows, start=4):
        if item:
            ws.cell(r, 1, item)
        ws.cell(r, 2, plant)
        for i in range(12):
            ws.cell(r, 3 + i, v)
        ws.cell(r, 15, v * 3)
    ws.cell(7, 3, sail_hm_apr)  # Hot Metal SAIL, Apr
    wb.save(path)


def test_plant_rows_only_with_page4_item_names(tmp_path):
    f = tmp_path / "mou.xlsx"
    _build(f)
    out = extract_mou_plan(str(f))
    keys = {(r["item_name"], r["plant_name"]) for r in out["records"]}
    assert keys == {("Hot Metal", "BSP"), ("Hot Metal", "DSP"),
                    ("Total Crude Steel", "BSP"), ("Total Crude Steel", "ASP")}
    assert len(out["months"]) == 12 and out["months"][0] == "2026-04" and out["months"][-1] == "2027-03"
    assert len(out["records"]) == 4 * 12
    assert out["items_found"] == ["Hot Metal", "Total Crude Steel"]
    assert out["warnings"] == []


def test_sail_row_mismatch_is_warned(tmp_path):
    f = tmp_path / "mou.xlsx"
    _build(f, sail_hm_apr=31.0)
    out = extract_mou_plan(str(f))
    assert any("Hot Metal" in w and "2026-04" in w for w in out["warnings"])


def test_no_header_raises(tmp_path):
    f = tmp_path / "empty.xlsx"
    openpyxl.Workbook().save(f)
    with pytest.raises(ValueError):
        extract_mou_plan(str(f))


def test_real_workbook():
    sample = find_sample("ABP/MoU 26-27.xlsx")
    if sample is None:
        pytest.skip("MoU 26-27.xlsx not available")
    out = extract_mou_plan(str(sample))
    assert out["items_found"] == ["Hot Metal", "Total Crude Steel", "Saleable Steel", "Pig Iron", "Finished Steel"]
    assert out["warnings"] == []
    bsp_hm_apr = [r["value"] for r in out["records"] if r["item_name"] == "Hot Metal"
                  and r["plant_name"] == "BSP" and r["report_month"] == "2026-04"]
    assert bsp_hm_apr == [pytest.approx(565.452483, abs=1e-5)]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_mou_plan_extractor.py -q`
Expected: FAIL — `ModuleNotFoundError: excel_extractor_mou_plan`

- [ ] **Step 3: Implement** `excel_extractors/excel_extractor_mou_plan.py`:

```python
"""MoU month-wise production target workbook — "MoU YY-YY.xlsx"
(Report_format/ABP/), sheet "MoU YY-YY":

    row 3   "Items" | "Plant" | 12 month dates (Apr..Mar) | quarter/annual totals
    col A   item name, merged down its plant rows (Hot Metal, Crude Steel,
            Saleable Steel, Pig Iron, Finished Steel)
    col B   plant (BSP, DSP, RSP, BSL, ISP, ASP, SSP, VISL) or a total row
            ("SAIL - 5PL", "SAIL -5 PL", "SAIL", "SAIL ")

Only plant rows are kept; page 4 computes "5 Plants"/SAIL itself. The
file's own SAIL row is used as a check: a month where it differs from the
plant sum is reported as a warning. Month columns are found by their date
values and the header row by its labels, never by fixed positions.
Unit '000 T.
"""
import datetime
from typing import Dict, List, Optional, Tuple

import openpyxl

# Workbook item label (upper-cased, single-spaced) -> page-4 db_item name
ITEM_MAP = {
    "HOT METAL": "Hot Metal",
    "CRUDE STEEL": "Total Crude Steel",
    "SALEABLE STEEL": "Saleable Steel",
    "PIG IRON": "Pig Iron",
    "FINISHED STEEL": "Finished Steel",
}
PLANTS = ("BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL")
_SUM_TOLERANCE = 0.01


def _num(v) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        try:
            return float(s) if s else None
        except ValueError:
            return None
    return None


def _find_header(ws) -> Tuple[Optional[int], Dict[str, int]]:
    for r in range(1, 21):
        a, b = ws.cell(r, 1).value, ws.cell(r, 2).value
        if (isinstance(a, str) and a.strip().upper() == "ITEMS"
                and isinstance(b, str) and b.strip().upper() == "PLANT"):
            cols = {}
            for c in range(3, ws.max_column + 1):
                v = ws.cell(r, c).value
                if isinstance(v, datetime.datetime):
                    cols[f"{v.year}-{v.month:02d}"] = c
            return r, cols
    return None, {}


def extract_mou_plan(file_path: str) -> dict:
    """Parse a MoU workbook — no DB writes. See module docstring."""
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws, hdr, month_cols = None, None, {}
    for sheet in wb.worksheets:
        hdr, month_cols = _find_header(sheet)
        if hdr and month_cols:
            ws = sheet
            break
    if ws is None:
        raise ValueError("No sheet with an 'Items' / 'Plant' header row and month columns was found.")

    warnings: List[str] = []
    if len(month_cols) != 12:
        warnings.append(f"Found {len(month_cols)} month columns, expected 12.")

    records: List[dict] = []
    items_found: List[str] = []
    sail_rows: Dict[str, int] = {}
    item = None
    for r in range(hdr + 1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        if isinstance(a, str) and a.strip():
            label = " ".join(a.split()).upper()
            item = ITEM_MAP.get(label)
            if item is None:
                warnings.append(f"Row {r}: item {a.strip()!r} not recognised; its rows were skipped.")
            elif item not in items_found:
                items_found.append(item)
        b = ws.cell(r, 2).value
        if item is None or not isinstance(b, str) or not b.strip():
            continue
        plant = b.strip().upper()
        if plant.startswith("SAIL"):
            if plant.replace(" ", "") == "SAIL":
                sail_rows[item] = r
            continue
        if plant not in PLANTS:
            warnings.append(f"Row {r}: plant {b.strip()!r} not recognised; skipped.")
            continue
        for month, col in month_cols.items():
            raw = ws.cell(r, col).value
            val = _num(raw)
            if val is None:
                if raw not in (None, ""):
                    warnings.append(f"{item} {plant} {month}: {raw!r} is not a number; skipped.")
                continue
            records.append({"report_month": month, "plant_name": plant, "item_name": item, "value": val})

    for it, r in sail_rows.items():
        for month, col in month_cols.items():
            file_total = _num(ws.cell(r, col).value)
            if file_total is None:
                continue
            plant_sum = sum(x["value"] for x in records if x["item_name"] == it and x["report_month"] == month)
            if abs(plant_sum - file_total) > _SUM_TOLERANCE:
                warnings.append(
                    f"{it} {month}: the file's SAIL row is {file_total:.3f} but its plants add up to "
                    f"{plant_sum:.3f}."
                )

    if not records:
        raise ValueError("No plant rows found under the 'Items' / 'Plant' header.")
    return {
        "records": records,
        "months": sorted(month_cols),
        "items_found": items_found,
        "warnings": warnings,
    }
```

- [ ] **Step 4: Run tests** — same command. Expected: 4 passed (or 3 passed, 1 skipped without the G: drive).

- [ ] **Step 5: Commit**

```bash
git add backend/excel_extractors/excel_extractor_mou_plan.py backend/tests/test_mou_plan_extractor.py
git commit -m "MoU plan workbook extractor"
```

---

### Task 3: MoU upload API and Uploads-page row

**Files:**
- Create: `backend/api_mou_plan.py`
- Modify: `backend/main.py` (import near line 421, `include_router` near line 902)
- Modify: `frontend/src/app/data-entry/uploads/page.js` (new `MouPlanExtractRow` after `PowerOmiExtractRow`; render it after `<PowerOmiExtractRow …/>` ~line 949)
- Test: `backend/tests/test_api_mou_plan.py`

**Interfaces:**
- Consumes: `extract_mou_plan` (Task 2), `mou_plan_table` (Task 1).
- Produces: `POST /api/mou-plan/preview` (multipart `file`) → `{status, source_file, records, months, items_found, warnings, record_count, has_existing, existing_conflicts_count}`; `POST /api/mou-plan/insert` JSON `{records, source_file, confirm_replace}` → `{status:"success", saved}` or 409.

- [ ] **Step 1: Write the failing test** `tests/test_api_mou_plan.py`:

```python
"""api_mou_plan insert: 409 on existing values, upsert on confirm."""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api_mou_plan


@pytest.fixture
def client(tmp_path, monkeypatch):
    dbfile = tmp_path / "mou.db"
    c = sqlite3.connect(dbfile)
    c.execute("CREATE TABLE mou_plan_table (report_month TEXT, plant_name TEXT, item_name TEXT, "
              "month_actual REAL, PRIMARY KEY (report_month, plant_name, item_name))")
    c.commit()
    c.close()

    class _Conn:
        def __init__(self):
            self._c = sqlite3.connect(dbfile)

        def cursor(self):
            return self._c.cursor()

        def commit(self):
            self._c.commit()

        def close(self):
            self._c.close()

    monkeypatch.setattr(api_mou_plan.db, "connect", _Conn)
    monkeypatch.setattr(api_mou_plan.db, "log_extraction", lambda **kw: None)
    app = FastAPI()
    app.include_router(api_mou_plan.router)
    return TestClient(app), dbfile


REC = [{"report_month": "2026-04", "plant_name": "BSP", "item_name": "Hot Metal", "value": 565.45}]


def test_insert_then_conflict_then_replace(client):
    tc, dbfile = client
    assert tc.post("/api/mou-plan/insert", json={"records": REC}).json()["saved"] == 1
    r = tc.post("/api/mou-plan/insert", json={"records": [dict(REC[0], value=600.0)]})
    assert r.status_code == 409
    r = tc.post("/api/mou-plan/insert", json={"records": [dict(REC[0], value=600.0)], "confirm_replace": True})
    assert r.status_code == 200
    rows = sqlite3.connect(dbfile).execute("SELECT month_actual FROM mou_plan_table").fetchall()
    assert rows == [(600.0,)]


def test_insert_without_records_is_400(client):
    tc, _ = client
    assert tc.post("/api/mou-plan/insert", json={"records": []}).status_code == 400
```

- [ ] **Step 2: Run to verify failure** — `venv/Scripts/python.exe -m pytest tests/test_api_mou_plan.py -q`. Expected: `ModuleNotFoundError: api_mou_plan`.

- [ ] **Step 3: Implement** `backend/api_mou_plan.py`:

```python
"""
API endpoints for the MoU month-wise production target workbook — see
excel_extractors/excel_extractor_mou_plan.py for the parsing and the
workbook layout. Same preview/insert/conflict flow as /api/power-omi:
  1. POST /preview — extract (no DB writes), flag values already stored.
  2. POST /insert — upsert into mou_plan_table; 409 on existing values
     unless confirm_replace=true.
"""
import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).parent / "excel_extractors"))
from excel_extractor_mou_plan import extract_mou_plan  # noqa: E402

import db  # noqa: E402

router = APIRouter(prefix="/api/mou-plan", tags=["mou-plan"])


def _existing_conflicts(records: list) -> list:
    conn = db.connect()
    cur = conn.cursor()
    conflicts = []
    try:
        for rec in records:
            cur.execute(
                "SELECT month_actual FROM mou_plan_table "
                "WHERE report_month = ? AND plant_name = ? AND item_name = ?",
                (rec["report_month"], rec["plant_name"], rec["item_name"]),
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                conflicts.append(rec)
    finally:
        conn.close()
    return conflicts


@router.post("/preview")
async def preview_mou_plan(file: UploadFile = File(..., description="MoU plan workbook (.xlsx)")):
    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.close()
        try:
            result = extract_mou_plan(tmp.name)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        conflicts = _existing_conflicts(result["records"])
        return {
            "status": "preview",
            "source_file": file.filename or "",
            "records": result["records"],
            "months": result["months"],
            "items_found": result["items_found"],
            "warnings": result["warnings"],
            "record_count": len(result["records"]),
            "has_existing": bool(conflicts),
            "existing_conflicts_count": len(conflicts),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@router.post("/insert")
async def insert_mou_plan(payload: dict):
    """Body: { records: [{report_month, plant_name, item_name, value}, ...],
               source_file, confirm_replace: bool }"""
    records = payload.get("records", [])
    if not records:
        raise HTTPException(status_code=400, detail="No records to insert")
    conflicts = _existing_conflicts(records)
    if conflicts and not payload.get("confirm_replace"):
        months = sorted({c["report_month"] for c in conflicts})
        raise HTTPException(
            status_code=409,
            detail=(f"{len(conflicts)} MoU value(s) already exist for {months[0]} to {months[-1]}. "
                    "Confirm to overwrite them with the newly extracted figures."),
        )
    conn = db.connect()
    cur = conn.cursor()
    saved = 0
    try:
        for rec in records:
            cur.execute("""
                INSERT INTO mou_plan_table (report_month, plant_name, item_name, month_actual)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, plant_name, item_name)
                DO UPDATE SET month_actual = excluded.month_actual
            """, (rec["report_month"], rec["plant_name"], rec["item_name"], rec["value"]))
            saved += 1
        conn.commit()
    finally:
        conn.close()
    db.log_extraction(
        plant="SAIL", report_month=max(r["report_month"] for r in records),
        file_name=payload.get("source_file", ""), sheet_name="",
        source_type="MoU Plan", items_extracted=saved,
    )
    return {"status": "success", "saved": saved}
```

- [ ] **Step 4: Register in `main.py`**: next to `from api_power_omi import router as power_omi_router` add
`from api_mou_plan import router as mou_plan_router`; next to `app.include_router(power_omi_router)` add `app.include_router(mou_plan_router)`.

- [ ] **Step 5: Run tests** — Expected: 2 passed. Then `curl -s -X POST http://127.0.0.1:8082/api/mou-plan/insert -H "Content-Type: application/json" -d "{\"records\":[]}"` → `{"detail":"No records to insert"}` (uvicorn has reloaded).

- [ ] **Step 6: Add `MouPlanExtractRow`** to `uploads/page.js` right after `PowerOmiExtractRow`. Copy `PowerOmiExtractRow` exactly. Change: the endpoint paths to `/api/mou-plan/preview` and `/api/mou-plan/insert`; the title to `MoU Plan (Excel): month-wise MoU production targets, all plants, whole FY`; the description to `The yearly "MoU YY-YY.xlsx" workbook (Report_format/ABP): Hot Metal, Crude Steel, Saleable Steel, Pig Iron and Finished Steel targets per plant for each month. Plant rows are stored; SAIL totals are calculated. Feeds the MoU page of Plant Wise Performance on /reports/excel.`; the preview summary to a table of `items_found` × months showing, for each item and month, the sum of `value` over plants (3 decimals); and warnings listed in an amber box when `preview.warnings.length`. Render `<MouPlanExtractRow apiBase={API_BASE_URL} onSuccess={() => {}} />` after `<PowerOmiExtractRow …/>`.

- [ ] **Step 7: Lint and commit**

```bash
cd frontend && npm run lint
git add backend/api_mou_plan.py backend/main.py backend/tests/test_api_mou_plan.py frontend/src/app/data-entry/uploads/page.js
git commit -m "MoU plan upload: preview/insert API and Uploads-page row"
```

---

### Task 4: `page4` plan basis (APP or MoU)

**Files:**
- Modify: `backend/page4.py` (`_p4_query_one` ~104, `_p4_query_sum` ~123, `_p4_ytd_nos_plan` ~179, `_p4_row_values` ~242, `generate_page4_rows` ~402)
- Test: `backend/tests/test_page4_basis.py`

**Interfaces:**
- Produces: `generate_page4_rows(month: str, raw: bool = False, basis: str = "app") -> list` (raises `ValueError` for another basis); `MOU_DB_ITEMS: frozenset[str]`.

- [ ] **Step 1: Write the failing test** `tests/test_page4_basis.py`:

```python
"""page4.generate_page4_rows(basis=...): MoU reads mou_plan_table and keeps
only the 5 MoU items; APP output is unchanged."""
import sqlite3

import pytest

import page4


@pytest.fixture
def p4(tmp_path, monkeypatch):
    dbfile = tmp_path / "p4.db"
    c = sqlite3.connect(dbfile)
    for t in ("production_table", "production_plan_table", "mou_plan_table"):
        c.execute(f"CREATE TABLE {t} (report_month TEXT, plant_name TEXT, item_name TEXT, month_actual REAL, "
                  "PRIMARY KEY (report_month, plant_name, item_name))")
    c.execute("INSERT INTO production_table VALUES ('2026-08','BSP','Hot Metal',500)")
    c.execute("INSERT INTO production_plan_table VALUES ('2026-08','BSP','Hot Metal',550)")
    c.execute("INSERT INTO mou_plan_table VALUES ('2026-08','BSP','Hot Metal',570)")
    c.execute("INSERT INTO production_plan_table VALUES ('2026-08','BSP','Total Sinter',900)")
    c.commit()
    c.close()

    class _Conn:
        def __init__(self):
            self._c = sqlite3.connect(dbfile)

        def cursor(self):
            return self._c.cursor()

        def close(self):
            self._c.close()

    monkeypatch.setattr(page4.db, "connect", _Conn)
    monkeypatch.setattr(page4.db, "get_effective_capacity", lambda *a, **k: None)
    return page4


def _row(rows, display, plant):
    return next(r for r in rows if r["label"] == f"{display} {plant}")


def test_mou_uses_mou_table_and_mou_items(p4):
    rows = p4.generate_page4_rows("2026-08", raw=True, basis="mou")
    displays = {r["display_name"] for r in rows if not r.get("is_conversion") and not r.get("is_sail_incl_conv")}
    assert displays == {"HOT METAL", "CRUDE STEEL", "SALEABLE STEEL", "PIG IRON", "FINISHED STEEL"}
    hm = _row(rows, "HOT METAL", "BSP")["values"]
    assert hm[1] == 570 and hm[2] == 500


def test_app_basis_equals_default(p4):
    assert p4.generate_page4_rows("2026-08", raw=True, basis="app") == p4.generate_page4_rows("2026-08", raw=True)
    assert p4.generate_page4_rows("2026-08", basis="app") == p4.generate_page4_rows("2026-08")
    hm = _row(p4.generate_page4_rows("2026-08", raw=True), "HOT METAL", "BSP")["values"]
    assert hm[1] == 550


def test_unknown_basis_raises(p4):
    with pytest.raises(ValueError):
        p4.generate_page4_rows("2026-08", basis="abp")
```

- [ ] **Step 2: Run to verify failure** — `venv/Scripts/python.exe -m pytest tests/test_page4_basis.py -q`. Expected: `TypeError: … unexpected keyword argument 'basis'`.

- [ ] **Step 3: Implement in `page4.py`**

After `CAPACITY_DB_ITEMS` add:

```python
# Items that have a MoU target (excel_extractor_mou_plan.ITEM_MAP values) —
# the MoU page of the Plant Wise Performance report shows only these.
MOU_DB_ITEMS = frozenset({"Hot Metal", "Total Crude Steel", "Saleable Steel", "Pig Iron", "Finished Steel"})

# _p4_get's `table` argument -> DB table. "plan" is APP; "mou" is the MoU target.
_TABLES = {"act": "production_table", "plan": "production_plan_table", "mou": "mou_plan_table"}
```

In `_p4_query_one` and `_p4_query_sum`, replace both
`tbl = "production_table" if table == "act" else "production_plan_table"` with `tbl = _TABLES[table]`.

`_p4_ytd_nos_plan(cur, months, plant, db_item, five_plants, sail_set, plan="plan")` — use `_p4_get(cur, plan, …)` inside.

`_p4_row_values(…, raw=False, plan="plan")` — replace the `"plan"` literal in
the `plan_m` line, both `_p4_ytd_nos_plan` calls (pass `plan=plan`), and both
`_p4_ytd_sum(cur, "plan", …)` calls with `plan`.

`generate_page4_rows(month: str, raw: bool = False, basis: str = "app")`:
- Docstring: add "basis='mou' takes the plan columns from mou_plan_table and keeps only MOU_DB_ITEMS."
- First lines: `if basis not in ("app", "mou"): raise ValueError(f"basis must be 'app' or 'mou', not {basis!r}")` and `plan = "mou" if basis == "mou" else "plan"`.
- In `for cfg in PAGE4_ITEMS:` first line: `if basis == "mou" and cfg["db_item"] not in MOU_DB_ITEMS: continue`.
- Pass `plan=plan` to all three `_p4_row_values(...)` calls (item loop, raw SAIL-incl-conv, non-raw SAIL-incl-conv).

- [ ] **Step 4: Run tests** — Expected: 3 passed. Then the full suite: `venv/Scripts/python.exe -m pytest tests -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/page4.py backend/tests/test_page4_basis.py
git commit -m "page4: plan basis (APP or MoU) for the plant performance rows"
```

---

### Task 5: Performance API — basis, decimals, two-sheet Excel, two-page PDF

**Files:**
- Modify: `backend/api_plant_performance.py`
- Create: `backend/plant_performance_pdf.py`
- Test: `backend/tests/test_api_plant_performance.py`

**Interfaces:**
- Consumes: `generate_page4_rows(month, raw=True, basis=…)` (Task 4).
- Produces:
  - `GET /api/plant-performance-main-items?month=&basis=app|mou` → `{month, basis, labels, pct_idx, has_plan, rows}`. `labels` gains `"basis": "APP"|"MoU"`. `has_plan` is true when any row has a non-null annual plan (`values[0]`).
  - `GET …/xlsx?month=&decimals=0..3` → workbook with sheets `w.r.t APP` and `w.r.t MoU`.
  - `GET …/pdf?month=&decimals=0..3` → `application/pdf`, 2 pages.
  - `plant_performance_pdf.build_html(sections: list[dict], decimals: int, colors: dict) -> str` where each section is `{labels, pct_idx, rows, has_plan}`; `plant_performance_pdf.render(html: str) -> bytes`.

- [ ] **Step 1: Write the failing test** `tests/test_api_plant_performance.py`:

```python
"""Plant performance API: basis/decimals validation and the two-sheet xlsx."""
import io

import openpyxl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api_plant_performance as app_mod

ROW = {"item": "HOT METAL", "plant": "BSP", "capacity": 7000.0,
       "values": [6688.1476, 565.4525, 500.12345, -65.33, 88.4, 520.0, -3.8, 85.0,
                  2800.0, 2700.5, -99.5, 96.4, 2600.0, 3.9, 90.0],
       "is_conversion": False, "is_sail_incl_conv": False}


@pytest.fixture
def tc(monkeypatch):
    monkeypatch.setattr(app_mod, "_rows", lambda month, basis: [dict(ROW)])
    monkeypatch.setattr(app_mod.db, "init_db", lambda: None)
    app = FastAPI()
    app.include_router(app_mod.router)
    return TestClient(app)


def test_json_basis(tc):
    d = tc.get("/api/plant-performance-main-items?month=2026-08&basis=mou").json()
    assert d["labels"]["basis"] == "MoU" and d["has_plan"] is True


@pytest.mark.parametrize("q", ["basis=abp", "decimals=4", "decimals=x", "decimals=-1"])
def test_bad_params_400(tc, q):
    path = "" if q.startswith("basis") else "/xlsx"
    assert tc.get(f"/api/plant-performance-main-items{path}?month=2026-08&{q}").status_code in (400, 422)


def test_xlsx_two_sheets_with_decimals(tc):
    r = tc.get("/api/plant-performance-main-items/xlsx?month=2026-08&decimals=1")
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["w.r.t APP", "w.r.t MoU"]
    ws = wb["w.r.t MoU"]
    assert ws.cell(3, 4).value.startswith("MoU")
    assert ws.cell(5, 6).number_format == "#,##0.0"
    assert ws.cell(5, 8).number_format == "0"


def test_pdf_html_has_both_pages():
    import plant_performance_pdf as ppdf
    sec = {"labels": {**app_mod._labels("2026-08", "app")}, "pct_idx": sorted(app_mod.PCT_IDX),
           "rows": [dict(ROW)], "has_plan": True}
    sec2 = {**sec, "labels": app_mod._labels("2026-08", "mou")}
    html = ppdf.build_html([sec, sec2], 2, {"perf_app_bg": "#111111"})
    assert html.count('class="sheet"') == 2 and "w.r.t MoU" in html and "500.12" in html and "#111111" in html
```

- [ ] **Step 2: Run to verify failure.** Expected: failures on `_rows(month, basis)` signature / missing `plant_performance_pdf`.

- [ ] **Step 3: Implement in `api_plant_performance.py`**
- `_BASIS = {"app": "APP", "mou": "MoU"}`.
- `_labels(month, basis="app")`: add `"basis": _BASIS[basis]` to the dict.
- `_rows(month, basis="app")`: call `generate_page4_rows(month, raw=True, basis=basis)`.
- `_check_basis(basis)`: 400 unless in `_BASIS`. `_check_decimals(decimals: int)`: 400 unless `0 <= decimals <= 3` (declare the query parameter as `decimals: int = Query(3)` so non-integers give 422).
- `_qty_fmt(decimals)`: `"#,##0" if decimals == 0 else "#,##0." + "0" * decimals`.
- `_section(month, basis)`: returns `{"labels": _labels(month, basis), "pct_idx": sorted(PCT_IDX), "rows": rows, "has_plan": any(r["values"][0] is not None for r in rows)}`.
- `GET ""`: add `basis: str = Query("app")`, validate, and return `{"month": month, "basis": basis, **_section(month, basis)}`.
- Move today's sheet-building body into `_write_sheet(ws, month, basis, decimals)`, changing:
  `"w.r.t APP"` → `f"w.r.t {L['basis']}"`; `f"APP\n{L['fy']}"` → `f"{L['basis']}\n{L['fy']}"`; the sub-header list `["APP", "Act.", "Var", "%Ful."]` → `[L["basis"], "Act.", "Var", "%Ful."]`; `qty_fmt = _qty_fmt(decimals)`; and when `not has_plan`, a note in row 2, column 4: `f"No {L['basis']} data uploaded for FY {L['fy']}"`. Cell values stay `round(v, 3)`.
- `GET /xlsx`: `decimals: int = Query(3)`, validate; `ws = wb.active; ws.title = "w.r.t APP"; _write_sheet(ws, month, "app", decimals); _write_sheet(wb.create_sheet("w.r.t MoU"), month, "mou", decimals)`. Filename `Plant_Performance_APP_MoU_{month}.xlsx`.
- `GET /pdf`: `decimals: int = Query(3)`, validate; `sections = [_section(month, "app"), _section(month, "mou")]`; `html = plant_performance_pdf.build_html(sections, decimals, load_colors_config())`, using `from colors_loader import load_colors_config` (check that the returned dict is flat key → hex; if colours are nested, pass the flat mapping that templates use as `colors`). Render in a thread executor exactly like `/api/production-fy/pdf` (`loop.run_in_executor(pool, plant_performance_pdf.render, html)`). Return a `Response(content, media_type="application/pdf")` with `Content-Disposition: attachment; filename="Plant_Performance_APP_MoU_{month}.pdf"`.

- [ ] **Step 4: Implement `backend/plant_performance_pdf.py`**

```python
"""Two-page (APP, MoU) PDF of the Plant Wise Performance of Main Items
report for /reports/excel — its own small template, not part of the
layout-guarded monthly report. Each page is scaled with CSS zoom to fit one
A4 landscape sheet. Colours come from colors_config.json (perf_* keys)."""
from html import escape

_W_PX, _H_PX = 1047, 703   # A4 landscape minus 10mm/12mm margins, at 96 dpi


def _q(v, d):
    return "" if v is None else f"{v:,.{d}f}"


def _p(v):
    return "" if v is None else f"{v:.0f}"


def _sheet(sec, d, c):
    L, pct, rows = sec["labels"], set(sec["pct_idx"]), sec["rows"]
    B = L["basis"]
    head = (
        f'<tr><th rowspan="2" class="l">Items</th><th rowspan="2">Plant</th>'
        f'<th rowspan="2" class="cap">Ann.<br>Cap.</th><th rowspan="2" class="pl">{B}<br>{L["fy"]}</th>'
        f'<th colspan="4">{L["month"]}</th><th rowspan="2">{L["cply"]}<br>Act.</th>'
        f'<th rowspan="2" class="gr">%Gr.<br>{L["cply"]}</th><th rowspan="2">CU%</th>'
        f'<th colspan="4">{L["ytd"]}</th><th rowspan="2">{L["ytd_cply"]}<br>Act.</th>'
        f'<th rowspan="2" class="gr">%Gr.<br>{L["ytd_cply"]}</th><th rowspan="2">CU%</th></tr><tr>'
        + "".join(f'<th class="{k}">{t}</th>' for k, t in
                  [("pl", B), ("ac", "Act."), ("", "Var"), ("", "%Ful."), ("pl", B), ("ac", "Act."), ("", "Var"), ("", "%Ful.")])
        + "</tr>"
    )
    body, i = [], 0
    while i < len(rows):
        r = rows[i]
        j = i
        if not (r["is_conversion"] or r["is_sail_incl_conv"]):
            while j + 1 < len(rows) and rows[j + 1]["item"] == r["item"] and not rows[j + 1]["is_conversion"] \
                    and not rows[j + 1]["is_sail_incl_conv"]:
                j += 1
        for k in range(i, j + 1):
            row = rows[k]
            sail = row["plant"] in ("SAIL", "5 Plants") or row["is_conversion"] or row["is_sail_incl_conv"]
            cells = []
            if row["is_conversion"]:
                cells.append('<td colspan="3" class="l b">Conversion</td>')
            elif row["is_sail_incl_conv"]:
                cells.append('<td colspan="2" class="l b">SAIL incl. conversion</td>')
            else:
                if k == i:
                    cells.append(f'<td rowspan="{j - i + 1}" class="l b item">{escape(row["item"])}</td>')
                cells.append(f'<td class="c b">{escape(row["plant"])}</td>')
            if not row["is_conversion"]:
                cells.append(f'<td class="cap">{_q(row["capacity"], d)}</td>')
            for vi, v in enumerate(row["values"]):
                cls = {0: "pl", 1: "pl", 8: "pl", 2: "ac", 9: "ac", 6: "gr", 13: "gr"}.get(vi, "")
                cells.append(f'<td class="{cls}">{_p(v) if vi in pct else _q(v, d)}</td>')
            body.append(f'<tr class="{"sail" if sail else ""}">{"".join(cells)}</tr>')
        i = j + 1
    note = "" if sec["has_plan"] else f'<p class="note">No {B} data uploaded for FY {L["fy"]}.</p>'
    return (
        f'<section class="sheet"><div class="hd"><h1>{escape(L["title"])}</h1><h1>w.r.t {B}</h1></div>'
        f'<div class="sub"><span>Tentative</span><span>Unit: \'000 T</span></div>{note}'
        f'<table><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></section>'
    )


def build_html(sections, decimals, colors):
    c = lambda k, dflt: colors.get(k, dflt)  # noqa: E731 — defaults mirror colors_loader._DEFAULTS
    css = f"""
  @page {{ size: A4 landscape; margin: 12mm 10mm; }}
  body {{ font-family: Arial, sans-serif; margin: 0; color: #0f172a; }}
  .sheet {{ page-break-after: always; width: {_W_PX}px; }}
  .sheet:last-child {{ page-break-after: auto; }}
  .hd {{ display: flex; justify-content: space-between; border-bottom: 1.5px solid #0f172a; }}
  h1 {{ font-size: 12pt; margin: 0 0 2px; }}
  .sub {{ display: flex; justify-content: space-between; font-size: 8pt; font-style: italic; margin: 2px 0 4px; }}
  .note {{ font-size: 9pt; font-weight: 700; margin: 2px 0 4px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 7.5pt; }}
  th, td {{ border: 1px solid #94a3b8; padding: 1px 4px; text-align: right; white-space: nowrap; }}
  th {{ text-align: center; font-weight: 700; }}
  .l {{ text-align: left; }} .c {{ text-align: center; }} .b {{ font-weight: 700; }}
  .item {{ white-space: normal; vertical-align: middle; }}
  .pl {{ background: {c("perf_app_bg", "#FFF2CC")}; color: {c("perf_app_text", "#7F6000")}; }}
  .ac {{ background: {c("perf_act_bg", "#C6EFCE")}; color: {c("perf_act_text", "#006100")}; font-weight: 700; }}
  .gr {{ background: {c("perf_gr_bg", "#e2e8f0")}; }}
  .cap {{ background: {c("perf_cap_bg", "#F8CBAD")}; color: {c("perf_cap_text", "#843C0C")}; }}
  tr.sail td {{ font-weight: 700; }}
"""
    pages = "".join(_sheet(s, decimals, colors) for s in sections)
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{pages}</body></html>'


def render(html: str) -> bytes:
    """Synchronous — call via a threadpool executor from async code."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="domcontentloaded")
        page.evaluate(f"""() => document.querySelectorAll('.sheet').forEach(s => {{
            const z = Math.min(1, {_H_PX} / s.scrollHeight, {_W_PX} / s.scrollWidth);
            if (z < 1) s.style.zoom = z; }})""")
        pdf = page.pdf(format="A4", landscape=True, print_background=True,
                       margin={"top": "12mm", "right": "10mm", "bottom": "12mm", "left": "10mm"})
        browser.close()
    return pdf
```

- [ ] **Step 5: Run tests** — Expected: all pass. Then check against the live backend:
`curl -s -o /tmp/pp.pdf "http://127.0.0.1:8082/api/plant-performance-main-items/pdf?month=2026-08&decimals=2"`, then use pypdfium2 to check it has 2 pages and render each to PNG to look at them.

- [ ] **Step 6: Commit**

```bash
git add backend/api_plant_performance.py backend/plant_performance_pdf.py backend/tests/test_api_plant_performance.py
git commit -m "Plant performance API: APP/MoU basis, decimals, two-sheet Excel, two-page PDF"
```

---

### Task 6: Frontend — two-page view with decimals, Excel and PDF

**Files:**
- Modify: `frontend/src/components/reports/plant-performance-items/View.js`
- Modify: `frontend/src/components/reports/reportGroups.js:80`

**Interfaces:**
- Consumes: the Task 5 endpoints.

- [ ] **Step 1: Rewrite `View.js`** keeping today's styling constants (`TH`, `TD`, `btn`, `previousMonth`):
- State: `month`, `decimals` (initial 3; read and write `localStorage['pp-decimals']` inside try/catch in a `useEffect`), `data = {app, mou}`, `loading`, `error`, `downloading` (`null | 'xlsx' | 'pdf'`).
- Fetch both bases with `Promise.all` on `month` change.
- `fmtQty(v, d)` → `Number(v).toLocaleString('en-IN', {minimumFractionDigits: d, maximumFractionDigits: d})`.
- Extract today's table JSX into `function PerfTable({ section, decimals })`. In it, replace the literal `APP` header texts with `section.labels.basis`, and the right-hand heading with `w.r.t {section.labels.basis}`. When `!section.has_plan`, show `No {basis} data uploaded for FY {fy}. Upload the MoU workbook on the Uploads page.` with a `<Link href="/data-entry/uploads">` (`next/link`).
- Render `<PerfTable section={data.app}/>`, a 24px gap, then `<PerfTable section={data.mou}/>`.
- Controls row: month input, `<select>` Decimals 0/1/2/3, the **Download Excel** button (`/xlsx?month=&decimals=` → `Plant_Performance_APP_MoU_{month}.xlsx`) and the **Download PDF** button (`/pdf?…` → `.pdf`). Both use one `download(kind)` helper (today's blob → anchor code).
- Update `description`: `Page 1 against APP, page 2 against MoU (only items with a MoU target). Tonnage in '000 T with the chosen decimals; percentages are whole numbers. Download both pages as Excel (two sheets) or PDF.`

- [ ] **Step 2: Update `reportGroups.js:80`**: `label: 'Plant Wise Performance (APP & MoU)'`, `description: 'Plant Wise Performance of Main Items against APP and MoU; Excel and PDF download.'`; and the group `description` (line 77): `'Reports with Excel downloads: plant-wise performance of main items (APP & MoU) and the product-mix report.'`

- [ ] **Step 3: Lint** — `cd frontend && npm run lint`. Expected: no new errors in these files.

- [ ] **Step 4: Check in the browser** at `http://localhost:3000/reports/excel?tab=plant-performance-items`: both tables render, changing decimals reformats immediately, and both downloads work.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/reports/plant-performance-items/View.js frontend/src/components/reports/reportGroups.js
git commit -m "Excel report: Plant Wise Performance against APP and MoU, decimals, PDF download"
```

---

### Task 7: Load the real MoU data and verify end to end

- [ ] **Step 1: Upload** `G:\My Drive\Report_format\ABP\MoU 26-27.xlsx` through `/api/mou-plan/preview` and then `/insert` (curl, or the Uploads page). Expected: the preview has 0 warnings, 5 items and 12 months; the insert saves about 5 items × 6–8 plants × 12 values.
- [ ] **Step 2: Cross-check** against the file: `SELECT SUM(month_actual) FROM mou_plan_table WHERE item_name='Finished Steel'` ≈ 18839.000.
- [ ] **Step 3: Check that page 4 of the main report is unchanged**: `cd backend && venv/Scripts/python.exe layout_guard.py --render 2026-08` → OK, matches the reference render.
- [ ] **Step 4: Download the Aug'26 PDF** (decimals 0 and 3) and the Excel file. Render the PDF pages to PNG and look at them: 2 pages, each fits one sheet, and MoU page 2 has only the 5 items.
- [ ] **Step 5: Production**: `cd frontend && npm run build` so that `http://localhost/reports/excel` (port 80) serves the change; tell the user that a production restart is needed if it is running.
- [ ] **Step 6: Full test suite** `venv/Scripts/python.exe -m pytest tests -q`. Expected: all pass. Commit anything left over. Do not push unless asked.
