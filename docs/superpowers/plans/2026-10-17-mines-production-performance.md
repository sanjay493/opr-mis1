# Mines Production Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A standalone "Mines Production Performance" report (web tab + PDF + Excel) laid out like the monthly report's pages 5-6, with iron-ore mine / group / SAIL blocks and SAIL-level coal and flux.

**Architecture:** A pure generator `backend/mines_performance.py` (`generate(month)`) reads the existing mine-level iron-ore tables and `sail_mines_monthly` and returns blocks of rows with 11 unrounded values each. A FastAPI router `backend/api_mines_performance.py` serves it as JSON, `.xlsx` and `.pdf` (the PDF from a standalone template in `backend/mines_performance_pdf.py`). A new frontend tab in `/reports/mines` shows it. Same pattern as the existing Plant Wise Performance (APP & MoU) report.

**Tech Stack:** Python 3 / FastAPI / openpyxl / Playwright (Chromium) / pytest; Next.js 16 (React, client component).

**Spec:** `docs/superpowers/specs/2026-10-17-mines-production-performance-design.md`

## Global Constraints

- Python: always `backend/venv/Scripts/python.exe`, tools as `python.exe -m <tool>` (e.g. `-m pytest`). Run tests from `backend/`.
- SQL is written in sqlite dialect (`?` placeholders) and goes through `db.connect()`; `dbengine.py` translates for MySQL (the live engine).
- No schema changes: no new tables or columns.
- Do not touch the monthly report PDF: `pdf.py`, `page_templates/`, `layout_config.json`, `page_sail_mines.py`.
- Every PDF colour is a named key in `backend/colors_config.json`; a new key is added to both `colors_config.json` and `colors_loader._DEFAULTS` with the same value. No hard-coded hex in the PDF module's CSS except via those keys.
- Unit: '000 T. Row values: 11, in this order: 0 FY Plan | 1 Plan, 2 Actual, 3 %Ful, 4 CPLY Act., 5 %Gr (month) | 6 Plan, 7 Actual, 8 %Ful, 9 CPLY Act., 10 %Gr (Apr-to-month). Percent indices: 3, 5, 8, 10.
- Sums skip blanks; a sum is blank only when all parts are blank. %Ful / %Gr blank when the denominator is blank or 0 or the numerator is blank.
- Every total is a live sum of its parts.
- Reported Production = fresh Lump + Fines + Pellets despatch (any end use) + Dump Fines despatch (CAPTIVE, SALES) + Tailings despatch (SALES).
- Decimals 0–3 (default 0); percentages whole numbers; Washery Yield (%) quantity columns 1 decimal.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- Report month in Jan–Mar: the FY started the previous calendar year; FY Plan, Apr-to-month and CPLY must use the right FY (pinned in Task 1, `test_periods_jan_crosses_calendar_year`).
- Report month = April: Apr-to-month is that one month, CPLY is last April (pinned in Task 1, `test_periods_april`).
- A row with only last-year data (CPLY only) must still show, not be hidden as empty (pinned in Task 2, `test_cply_only_row_is_shown`).
- MySQL can return `Decimal` values; the generator must convert to float before arithmetic (pinned in Task 2, `test_f_converts_decimal`).
- A month with no mines data at all: JSON returns `blocks: []`, the PDF says "No mines data for …", the web tab says so too (pinned in Task 2 `test_empty_month_has_no_blocks`, Task 4 `test_pdf_html_empty`).

---

### Task 1: Period and value arithmetic

**Files:**
- Create: `backend/mines_performance.py`
- Test: `backend/tests/test_mines_performance.py`

**Interfaces:**
- Produces:
  - `periods(month: str) -> dict` with keys `fy` (12 `YYYY-MM`, Apr..Mar), `month`, `cply` (same month last year), `ytd` (Apr..month), `cply_ytd` (same span last year).
  - `combine(series_list: list[dict]) -> dict` — a series is `{month: (actual, plan)}`; adds per month, blank-aware.
  - `values(series: dict, P: dict) -> list` of 11 values.
  - `labels(month: str) -> dict` with keys `title, fy, month, cply, ytd, ytd_cply`.
  - `PCT_IDX = (3, 5, 8, 10)`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_mines_performance.py`:

```python
"""mines_performance: period arithmetic, values, and (Task 2/3) the
block/row generator against a temp SQLite DB."""
import mines_performance as mp


def test_periods_mid_fy():
    P = mp.periods("2026-09")
    assert P["fy"][0] == "2026-04" and P["fy"][-1] == "2027-03" and len(P["fy"]) == 12
    assert P["ytd"] == ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    assert P["cply"] == "2025-09"
    assert P["cply_ytd"] == ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]


def test_periods_jan_crosses_calendar_year():
    P = mp.periods("2027-01")
    assert P["fy"][0] == "2026-04"
    assert P["ytd"][0] == "2026-04" and P["ytd"][-1] == "2027-01" and len(P["ytd"]) == 10
    assert P["cply"] == "2026-01"
    assert P["cply_ytd"][0] == "2025-04" and P["cply_ytd"][-1] == "2026-01"


def test_periods_april():
    P = mp.periods("2026-04")
    assert P["ytd"] == ["2026-04"] and P["cply_ytd"] == ["2025-04"]


def test_combine_is_blank_aware():
    s = mp.combine([{"2026-09": (10.0, None)}, {"2026-09": (None, None), "2026-08": (None, 5.0)}])
    assert s == {"2026-09": (10.0, None), "2026-08": (None, 5.0)}


def test_values_all_columns():
    P = mp.periods("2026-09")
    s = {"2026-04": (90.0, 100.0), "2026-09": (100.0, 110.0), "2027-03": (None, 50.0),
         "2025-09": (80.0, None), "2025-04": (70.0, None)}
    v = mp.values(s, P)
    assert v[0] == 260.0                      # FY plan: 100 + 110 + 50
    assert v[1:3] == [110.0, 100.0]           # month plan, actual
    assert round(v[3], 4) == round(100 / 110 * 100, 4)
    assert v[4] == 80.0 and v[5] == 25.0      # CPLY, %Gr
    assert v[6:8] == [210.0, 190.0]           # Apr-to-month plan, actual
    assert v[9] == 150.0                      # CPLY Apr-Sep'25
    assert round(v[10], 4) == round((190 - 150) / 150 * 100, 4)


def test_values_percent_blank_on_zero_or_missing():
    P = mp.periods("2026-09")
    v = mp.values({"2026-09": (20.0, 0.0)}, P)
    assert v[3] is None and v[5] is None and v[8] is None and v[10] is None
    assert mp.values({}, P) == [None] * 11


def test_labels():
    L = mp.labels("2026-09")
    assert L == {"title": "Mines Production Performance :Sep'26 and Apr-Sep'26", "fy": "26-27",
                 "month": "Sep'26", "cply": "Sep'25", "ytd": "Apr-Sep'26", "ytd_cply": "Apr-Sep'25"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `venv/Scripts/python.exe -m pytest tests/test_mines_performance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mines_performance'`.

- [ ] **Step 3: Write the implementation**

Create `backend/mines_performance.py`:

```python
"""
Mines Production Performance -- a standalone report laid out like the
monthly report's pages 5-6 (Plant Wise Item Wise Production), with mines in
place of plants. Not part of the monthly PDF yet (some coal/flux figures are
only kept at SAIL level today). See
docs/superpowers/specs/2026-10-17-mines-production-performance-design.md.

generate(month) -> {"labels", "pct_idx", "blocks"}: one block per mine, per
group (JGoM/OGoM/CGoM) and for SAIL. Every row carries 11 unrounded values:
    0 FY Plan | 1 Plan  2 Actual  3 %Ful  4 CPLY Act.  5 %Gr    (month)
              | 6 Plan  7 Actual  8 %Ful  9 CPLY Act. 10 %Gr    (Apr-to-month)
Every total is a live sum of its parts -- nothing stored is a total.

A "series" is {report_month: (actual, plan)}; rows are built by combining
series and then deriving the 11 values, so totals' percentages come from
the summed quantities, never from averaging percentages.
"""
import db

PCT_IDX = (3, 5, 8, 10)

_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def periods(month: str) -> dict:
    y, m = int(month[:4]), int(month[5:7])
    fy = y if m >= 4 else y - 1
    fy_months = [f"{fy}-{k:02d}" for k in range(4, 13)] + [f"{fy + 1}-{k:02d}" for k in range(1, 4)]
    ytd = [mo for mo in fy_months if mo <= month]

    def prev(mo):
        return f"{int(mo[:4]) - 1}{mo[4:]}"

    return {"fy": fy_months, "month": month, "cply": prev(month),
            "ytd": ytd, "cply_ytd": [prev(mo) for mo in ytd]}


def labels(month: str) -> dict:
    y, m = int(month[:4]), int(month[5:7])
    fy = y if m >= 4 else y - 1
    sy, py = f"{y % 100:02d}", f"{(y - 1) % 100:02d}"
    return {
        "title": f"Mines Production Performance :{_MON[m]}'{sy} and Apr-{_MON[m]}'{sy}",
        "fy": f"{fy % 100:02d}-{(fy + 1) % 100:02d}",
        "month": f"{_MON[m]}'{sy}",
        "cply": f"{_MON[m]}'{py}",
        "ytd": f"Apr-{_MON[m]}'{sy}",
        "ytd_cply": f"Apr-{_MON[m]}'{py}",
    }


def _sum(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def combine(series_list) -> dict:
    out = {}
    for s in series_list:
        for mo, (a, p) in s.items():
            oa, op = out.get(mo, (None, None))
            out[mo] = (_sum([oa, a]), _sum([op, p]))
    return out


def _ratio(n, d):
    # n * 100 / d (not n / d * 100): 90 / 200 * 100 is 45.00000000000001
    return None if n is None or not d else n * 100 / d


def _growth(a, c):
    return None if a is None or not c else (a - c) * 100 / c


def values(series: dict, P: dict) -> list:
    def act(mo):
        return series.get(mo, (None, None))[0]

    def plan(mo):
        return series.get(mo, (None, None))[1]

    m_plan, m_act, m_cply = plan(P["month"]), act(P["month"]), act(P["cply"])
    y_plan = _sum(plan(mo) for mo in P["ytd"])
    y_act = _sum(act(mo) for mo in P["ytd"])
    y_cply = _sum(act(mo) for mo in P["cply_ytd"])
    return [_sum(plan(mo) for mo in P["fy"]),
            m_plan, m_act, _ratio(m_act, m_plan), m_cply, _growth(m_act, m_cply),
            y_plan, y_act, _ratio(y_act, y_plan), y_cply, _growth(y_act, y_cply)]
```

(`import db` is used from Task 2 on.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_mines_performance.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/mines_performance.py backend/tests/test_mines_performance.py
git commit -m "Mines Production Performance: period and value arithmetic

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Iron-ore blocks (mine, group, SAIL) and `generate()`

**Files:**
- Modify: `backend/mines_performance.py` (append)
- Test: `backend/tests/test_mines_performance.py` (append)

**Interfaces:**
- Consumes: `periods`, `combine`, `values`, `labels`, `PCT_IDX`, `_sum`, `_ratio`, `_growth` from Task 1.
- Produces:
  - `generate(month: str) -> {"labels": dict, "pct_idx": [3, 5, 8, 10], "blocks": list}`; each block `{"name", "kind": "mine"|"group"|"sail", "group": str|None, "note": str|None, "rows": list}`; each row `{"label", "kind": "heading"|"subheading"|"item"|"total", "values": [11], "decimals": None|int}`.
  - `SAIL_NOTE` (str) on the SAIL block.
  - `_f(v)` (float or None).
  - `coal_flux_rows(data, P) -> list` is called by `generate`; Task 3 implements it. In this task define it as returning `[]`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_mines_performance.py`:

```python
import sqlite3
from decimal import Decimal

import pytest

_SCHEMA = [
    "CREATE TABLE mine_groups_master (group_code TEXT, group_name TEXT, sort_order INTEGER)",
    "CREATE TABLE mines_master (mine_code TEXT, mine_name TEXT, group_code TEXT, is_active INTEGER, sort_order INTEGER)",
    "CREATE TABLE mine_materials_master (material_code TEXT, material_name TEXT, material_category TEXT, "
    "has_production INTEGER, counts_in_total_production INTEGER, sort_order INTEGER)",
    "CREATE TABLE mines_production_monthly (report_month TEXT, mine_code TEXT, material_code TEXT, qty_actual REAL, qty_plan REAL)",
    "CREATE TABLE mines_despatch_actual_monthly (report_month TEXT, mine_code TEXT, material_code TEXT, "
    "transport_mode TEXT, end_use_code TEXT, qty_actual REAL)",
    "CREATE TABLE mines_despatch_plan_monthly (report_month TEXT, mine_code TEXT, material_code TEXT, end_use_code TEXT, qty_plan REAL)",
    "CREATE TABLE mines_booked_qty_actual_monthly (report_month TEXT, mine_code TEXT, material_code TEXT, transport_mode TEXT, qty_actual REAL)",
    "CREATE TABLE mines_booked_qty_plan_monthly (report_month TEXT, mine_code TEXT, material_code TEXT, qty_plan REAL)",
    "CREATE TABLE sail_mines_monthly (report_month TEXT, section TEXT, item TEXT, month_actual REAL, month_plan REAL)",
]

_ROWS = {
    "mine_groups_master": [("JG", "J Group", 1), ("OG", "O Group", 2)],
    "mines_master": [("A", "Alpha", "JG", 1, 1), ("B", "Beta", "JG", 1, 2),
                     ("C", "Gamma", "OG", 1, 3), ("D", "Delta", "OG", 0, 4)],
    "mine_materials_master": [("LUMP", "Lump", "FRESH", 1, 1, 1), ("FINES", "Fines", "FRESH", 1, 1, 2),
                              ("DUMP_FINES", "Dump Fines", "LEGACY", 0, 1, 3), ("PELLETS", "Pellets", "LEGACY", 0, 1, 4),
                              ("TAILINGS", "Tailings", "LEGACY", 0, 1, 5)],
    "mines_production_monthly": [
        ("2026-09", "A", "LUMP", 100, 110), ("2026-09", "A", "FINES", 50, 40),
        ("2026-04", "A", "LUMP", 90, 100), ("2025-09", "A", "LUMP", 80, None),
        ("2026-09", "B", "LUMP", 10, 10), ("2026-09", "C", "FINES", 20, 0),
        ("2026-09", "D", "LUMP", 999, 999),          # inactive mine: never counted
    ],
    "mines_despatch_actual_monthly": [
        ("2026-09", "A", "LUMP", "RAIL", "CAPTIVE", 60), ("2026-09", "A", "LUMP", "ROAD", "CAPTIVE", 5),
        ("2026-09", "A", "FINES", "RAIL", "SALES", 30),
        ("2026-09", "A", "PELLETS", "ROAD", "SALES", 7), ("2026-09", "A", "PELLETS", "RAIL", "CAPTIVE", 3),
        ("2026-09", "A", "DUMP_FINES", "RAIL", "PELLET_CONV", 4), ("2026-09", "A", "DUMP_FINES", "RAIL", "SALES", 2),
        ("2026-09", "A", "TAILINGS", "RAIL", "CAPTIVE", 1), ("2026-09", "A", "TAILINGS", "RAIL", "SALES", 6),
        ("2025-09", "C", "TAILINGS", "RAIL", "SALES", 5),   # C: last year only
    ],
    "mines_despatch_plan_monthly": [("2026-09", "A", "LUMP", "CAPTIVE", 70)],
    "mines_booked_qty_actual_monthly": [("2026-09", "A", "FINES", "RAIL", 12), ("2026-09", "A", "FINES", "ROAD", 3)],
    "mines_booked_qty_plan_monthly": [("2026-09", "A", "FINES", 20)],
    "sail_mines_monthly": [],
}


@pytest.fixture
def gen(tmp_path, monkeypatch):
    dbfile = tmp_path / "mines.db"
    c = sqlite3.connect(dbfile)
    for sql in _SCHEMA:
        c.execute(sql)
    for table, rows in _ROWS.items():
        for r in rows:
            c.execute(f"INSERT INTO {table} VALUES ({','.join('?' * len(r))})", r)
    c.commit()
    c.close()
    monkeypatch.setattr(mp.db, "connect", lambda: sqlite3.connect(dbfile))
    return dbfile


def _block(data, name):
    return next(b for b in data["blocks"] if b["name"] == name)


def _rows(block):
    return [(r["kind"], r["label"]) for r in block["rows"]]


def _val(block, label, i=2):
    return next(r for r in block["rows"] if r["label"] == label)["values"][i]


def test_f_converts_decimal():
    assert mp._f(Decimal("1.5")) == 1.5 and mp._f(None) is None


def test_block_order_and_kinds(gen):
    d = mp.generate("2026-09")
    assert [(b["name"], b["kind"]) for b in d["blocks"]] == [
        ("Alpha", "mine"), ("Beta", "mine"), ("J Group", "group"),
        ("Gamma", "mine"), ("O Group", "group"), ("SAIL", "sail")]
    assert _block(d, "SAIL")["note"] == mp.SAIL_NOTE
    assert d["pct_idx"] == [3, 5, 8, 10] and d["labels"]["month"] == "Sep'26"


def test_mine_rows_structure(gen):
    a = _block(mp.generate("2026-09"), "Alpha")
    assert _rows(a) == [
        ("heading", "I/ORE FRESH PRODUCTION"), ("item", "Lump"), ("item", "Fines"),
        ("total", "Total Fresh Production"),
        ("heading", "I/ORE DESPATCH"),
        ("subheading", "Captive"), ("item", "Lump"), ("item", "Pellets"), ("item", "Tailings"),
        ("total", "Total Captive"),
        ("subheading", "Conversion Agent"), ("item", "Dump Fines"), ("total", "Total Conversion Agent"),
        ("subheading", "Sales"), ("item", "Fines"), ("item", "Dump Fines"), ("item", "Pellets"),
        ("item", "Tailings"), ("total", "Total Sales"),
        ("total", "Grand Total Despatch"),
        ("heading", "REPORTED PRODUCTION"), ("item", "Fresh Production (Lump+Fines)"),
        ("item", "Pellets Despatch"), ("item", "Dump Fines Despatch"), ("item", "Tailings Despatch"),
        ("total", "Reported Production"),
        ("heading", "BOOKED QUANTITY (SALES)"), ("item", "Fines"), ("total", "Total Booked"),
    ]
    assert all(r["values"] == [None] * 11 for r in a["rows"] if r["kind"] in ("heading", "subheading"))


def test_mine_values(gen):
    a = _block(mp.generate("2026-09"), "Alpha")
    assert _val(a, "Lump", 2) == 100 and _val(a, "Lump", 1) == 110
    assert _val(a, "Lump", 4) == 80 and _val(a, "Lump", 7) == 190 and _val(a, "Lump", 6) == 210
    assert _val(a, "Total Fresh Production") == 150
    assert _val(a, "Total Captive") == 69 and _val(a, "Total Captive", 1) == 70    # 65 + 3 + 1, plan 70
    assert _val(a, "Total Conversion Agent") == 4
    assert _val(a, "Total Sales") == 45                                            # 30 + 2 + 7 + 6
    assert _val(a, "Grand Total Despatch") == 118
    assert _val(a, "Pellets Despatch") == 10                                       # any end use
    assert _val(a, "Dump Fines Despatch") == 2                                     # not PELLET_CONV
    assert _val(a, "Tailings Despatch") == 6                                       # SALES only
    assert _val(a, "Reported Production") == 168                                   # 150 + 10 + 2 + 6
    assert _val(a, "Total Booked") == 15 and _val(a, "Total Booked", 3) == 75


def test_hidden_sections_and_always_shown_rows(gen):
    b = _block(mp.generate("2026-09"), "Beta")
    assert _rows(b) == [
        ("heading", "I/ORE FRESH PRODUCTION"), ("item", "Lump"), ("item", "Fines"),
        ("total", "Total Fresh Production"),
        ("heading", "REPORTED PRODUCTION"), ("item", "Fresh Production (Lump+Fines)"),
        ("total", "Reported Production"),
    ]
    assert _val(b, "Fines") is None


def test_cply_only_row_is_shown(gen):
    c = _block(mp.generate("2026-09"), "Gamma")
    assert ("item", "Tailings") in _rows(c)
    assert _val(c, "Tailings", 4) == 5 and _val(c, "Tailings", 2) is None


def test_plan_zero_gives_blank_percent(gen):
    c = _block(mp.generate("2026-09"), "Gamma")
    assert _val(c, "Fines", 2) == 20 and _val(c, "Fines", 3) is None


def test_group_and_sail_are_sums(gen):
    d = mp.generate("2026-09")
    assert _val(_block(d, "J Group"), "Lump") == 110
    assert _val(_block(d, "J Group"), "Total Fresh Production") == 160
    sail = _block(d, "SAIL")
    assert _val(sail, "Total Fresh Production") == 180          # inactive D excluded
    assert _val(sail, "Grand Total Despatch") == 118
    assert _val(sail, "Reported Production") == 198              # 180 + 10 + 2 + 6


def test_empty_month_has_no_blocks(gen):
    assert mp.generate("2030-05")["blocks"] == []
```

- [ ] **Step 2: Run the tests to verify the new ones fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_mines_performance.py -v`
Expected: the 7 Task 1 tests pass; the new ones FAIL with `AttributeError: module 'mines_performance' has no attribute '_f'` / `'generate'`.

- [ ] **Step 3: Write the implementation**

Append to `backend/mines_performance.py`:

```python
# Despatch sub-groups, in report order (not mine_end_uses_master's order).
END_USES = (("CAPTIVE", "Captive"), ("PELLET_CONV", "Conversion Agent"), ("SALES", "Sales"))

# Reported Production = fresh Lump + Fines + these despatches (None = any
# end use) -- the rule in db.get_iron_ore_group_rollup_monthly, applied per
# mine here so a group/SAIL block's figure equals the SAIL Mines page's.
REPORTED_PARTS = (
    ("Pellets Despatch", "PELLETS", None),
    ("Dump Fines Despatch", "DUMP_FINES", ("CAPTIVE", "SALES")),
    ("Tailings Despatch", "TAILINGS", ("SALES",)),
)

SAIL_NOTE = "Coal and flux are shown at SAIL level; mine-level figures will be added."


def _f(v):
    """MySQL can hand back Decimal; arithmetic here is all float."""
    return None if v is None else float(v)


def _row(label, kind, vals=None, decimals=None):
    return {"label": label, "kind": kind, "values": vals or [None] * 11, "decimals": decimals}


def _empty(vals) -> bool:
    return all(v is None for v in vals)


def _load(months: list) -> dict:
    """Masters plus every series needed, read once for the given months:
    prod[(mine, material)], desp[(mine, material, end_use)] (Rail + Road
    summed), booked[(mine, material)] (Rail + Road summed),
    sail[(section, item)]."""
    conn = db.connect()
    cur = conn.cursor()
    ph = ",".join("?" * len(months))
    stores = {"prod": {}, "desp": {}, "booked": {}, "sail": {}}

    def put(store, key, mo, a=None, p=None):
        s = stores[store].setdefault(key, {})
        oa, op = s.get(mo, (None, None))
        s[mo] = (_sum([oa, _f(a)]), _sum([op, _f(p)]))

    cur.execute("SELECT group_code, group_name FROM mine_groups_master ORDER BY sort_order")
    groups = cur.fetchall()
    cur.execute("SELECT mine_code, mine_name, group_code FROM mines_master "
                "WHERE is_active = 1 ORDER BY sort_order")
    mines = cur.fetchall()
    cur.execute("SELECT material_code, material_name FROM mine_materials_master ORDER BY sort_order")
    materials = cur.fetchall()

    cur.execute(f"SELECT mine_code, material_code, report_month, qty_actual, qty_plan "
                f"FROM mines_production_monthly WHERE report_month IN ({ph})", months)
    for mine, mat, mo, a, p in cur.fetchall():
        put("prod", (mine, mat), mo, a, p)
    cur.execute(f"SELECT mine_code, material_code, end_use_code, report_month, qty_actual "
                f"FROM mines_despatch_actual_monthly WHERE report_month IN ({ph})", months)
    for mine, mat, eu, mo, a in cur.fetchall():
        put("desp", (mine, mat, eu), mo, a=a)
    cur.execute(f"SELECT mine_code, material_code, end_use_code, report_month, qty_plan "
                f"FROM mines_despatch_plan_monthly WHERE report_month IN ({ph})", months)
    for mine, mat, eu, mo, p in cur.fetchall():
        put("desp", (mine, mat, eu), mo, p=p)
    cur.execute(f"SELECT mine_code, material_code, report_month, qty_actual "
                f"FROM mines_booked_qty_actual_monthly WHERE report_month IN ({ph})", months)
    for mine, mat, mo, a in cur.fetchall():
        put("booked", (mine, mat), mo, a=a)
    cur.execute(f"SELECT mine_code, material_code, report_month, qty_plan "
                f"FROM mines_booked_qty_plan_monthly WHERE report_month IN ({ph})", months)
    for mine, mat, mo, p in cur.fetchall():
        put("booked", (mine, mat), mo, p=p)
    cur.execute(f"SELECT section, item, report_month, month_actual, month_plan "
                f"FROM sail_mines_monthly WHERE report_month IN ({ph})", months)
    for section, item, mo, a, p in cur.fetchall():
        put("sail", (section, item), mo, a, p)
    conn.close()
    return {"groups": groups, "mines": mines, "materials": materials, **stores}


def _pick(store: dict, mines, *key) -> dict:
    return combine([store.get((m, *key), {}) for m in mines])


def _pick_any_end_use(store: dict, mines, material) -> dict:
    return combine([s for k, s in store.items() if k[0] in mines and k[1] == material])


def iron_ore_rows(data: dict, mines: list, P: dict) -> list:
    def V(s):
        return values(s, P)

    rows = [_row("I/ORE FRESH PRODUCTION", "heading")]
    lump, fines = _pick(data["prod"], mines, "LUMP"), _pick(data["prod"], mines, "FINES")
    fresh = combine([lump, fines])
    rows += [_row("Lump", "item", V(lump)), _row("Fines", "item", V(fines)),
             _row("Total Fresh Production", "total", V(fresh))]

    desp_rows, subtotals = [], []
    for eu, eu_label in END_USES:
        items = []
        for code, name in data["materials"]:
            s = _pick(data["desp"], mines, code, eu)
            v = V(s)
            if not _empty(v):
                items.append((name, s, v))
        if not items:
            continue
        sub = combine([s for _, s, _ in items])
        subtotals.append(sub)
        desp_rows.append(_row(eu_label, "subheading"))
        desp_rows += [_row(n, "item", v) for n, _, v in items]
        desp_rows.append(_row(f"Total {eu_label}", "total", V(sub)))
    if desp_rows:
        rows.append(_row("I/ORE DESPATCH", "heading"))
        rows += desp_rows
        rows.append(_row("Grand Total Despatch", "total", V(combine(subtotals))))

    parts = []
    for label, material, eus in REPORTED_PARTS:
        if eus is None:
            s = _pick_any_end_use(data["desp"], mines, material)
        else:
            s = combine([_pick(data["desp"], mines, material, eu) for eu in eus])
        parts.append((label, s, V(s)))
    rows.append(_row("REPORTED PRODUCTION", "heading"))
    rows.append(_row("Fresh Production (Lump+Fines)", "item", V(fresh)))
    rows += [_row(label, "item", v) for label, _, v in parts if not _empty(v)]
    rows.append(_row("Reported Production", "total", V(combine([fresh] + [s for _, s, _ in parts]))))

    booked = []
    for code, name in data["materials"]:
        s = _pick(data["booked"], mines, code)
        v = V(s)
        if not _empty(v):
            booked.append((name, s, v))
    if booked:
        rows.append(_row("BOOKED QUANTITY (SALES)", "heading"))
        rows += [_row(n, "item", v) for n, _, v in booked]
        rows.append(_row("Total Booked", "total", V(combine([s for _, s, _ in booked]))))
    return rows


def coal_flux_rows(data: dict, P: dict) -> list:
    """SAIL-only coal/washery/flux sections -- implemented in Task 3."""
    return []


def generate(month: str) -> dict:
    P = periods(month)
    data = _load(sorted(set(P["fy"] + P["cply_ytd"] + [P["cply"]])))
    blocks = []
    for gcode, gname in data["groups"]:
        gmines = [(code, name) for code, name, g in data["mines"] if g == gcode]
        for code, name in gmines:
            blocks.append({"name": name, "kind": "mine", "group": gcode, "note": None,
                           "rows": iron_ore_rows(data, [code], P)})
        if gmines:
            blocks.append({"name": gname, "kind": "group", "group": gcode, "note": None,
                           "rows": iron_ore_rows(data, [c for c, _ in gmines], P)})
    all_mines = [code for code, _, _ in data["mines"]]
    blocks.append({"name": "SAIL", "kind": "sail", "group": None, "note": SAIL_NOTE,
                   "rows": iron_ore_rows(data, all_mines, P) + coal_flux_rows(data, P)})
    has_data = any(r["kind"] in ("item", "total") and not _empty(r["values"])
                   for b in blocks for r in b["rows"])
    return {"labels": labels(month), "pct_idx": list(PCT_IDX), "blocks": blocks if has_data else []}
```

Note: group blocks are named by `group_name` from `mine_groups_master` (live: "Jharkhand Group of Mines" etc.); the test fixture uses "J Group".

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_mines_performance.py -v`
Expected: 16 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/mines_performance.py backend/tests/test_mines_performance.py
git commit -m "Mines Production Performance: iron-ore mine/group/SAIL blocks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: SAIL coal, washery and flux sections

**Files:**
- Modify: `backend/mines_performance.py` (replace the `coal_flux_rows` stub)
- Test: `backend/tests/test_mines_performance.py` (append)

**Interfaces:**
- Consumes: `values`, `combine`, `_row`, `_ratio`, `_growth` (Tasks 1-2); `data["sail"][(section, item)]` series from `_load`.
- Produces: `coal_flux_rows(data, P) -> list` of rows (the Washery Yield row has `"decimals": 1`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_mines_performance.py`:

```python
_SAIL_ROWS = [
    ("2026-09", "coal_prod", "Raw Coking Coal", 100, 120), ("2026-09", "coal_prod", "Thermal Coal", 50, 0),
    ("2026-09", "washery", "Input Raw Coal", 200, 250), ("2026-09", "washery", "Clean Coal", 90, 100),
    ("2025-09", "washery", "Input Raw Coal", 100, None), ("2025-09", "washery", "Clean Coal", 40, None),
    ("2026-09", "coal_despatch", "Clean Coal", 80, 85), ("2026-09", "coal_despatch", "Thermal", 30, 35),
    ("2026-09", "flux_prod", "Limestone", 60, 70), ("2026-09", "flux_prod", "Dolomite", 25, 30),
    ("2026-09", "flux_despatch", "Limestone", 55, 65), ("2026-09", "flux_despatch", "Dolomite", 20, 28),
]


@pytest.fixture
def gen_sail(gen):
    c = sqlite3.connect(gen)
    c.executemany("INSERT INTO sail_mines_monthly VALUES (?,?,?,?,?)", _SAIL_ROWS)
    c.commit()
    c.close()
    return gen


def _sail_tail(d):
    rows = _block(d, "SAIL")["rows"]
    start = next(i for i, r in enumerate(rows) if r["label"] == "COAL MINES PRODUCTION")
    return rows[start:]


def test_coal_flux_structure(gen_sail):
    tail = _sail_tail(mp.generate("2026-09"))
    assert [(r["kind"], r["label"]) for r in tail] == [
        ("heading", "COAL MINES PRODUCTION"), ("item", "Raw Coking Coal"), ("item", "Thermal Coal"), ("total", "Total"),
        ("heading", "WASHERY"), ("item", "Input Raw Coal"), ("item", "Clean Coal"), ("item", "Yield (%)"),
        ("heading", "COAL DESPATCH"), ("item", "Clean Coal"), ("item", "Thermal"), ("total", "Total"),
        ("heading", "FLUX PRODUCTION"), ("item", "Limestone"), ("item", "Dolomite"), ("total", "Total"),
        ("heading", "FLUX DESPATCH"), ("item", "Limestone"), ("item", "Dolomite"), ("total", "Total"),
    ]
    assert all(r["values"] == [None] * 11 for r in tail if r["kind"] == "heading")


def test_coal_total_and_yield(gen_sail):
    tail = _sail_tail(mp.generate("2026-09"))
    coal_total = tail[3]["values"]
    assert coal_total[2] == 150 and coal_total[1] == 120
    y = next(r for r in tail if r["label"] == "Yield (%)")
    assert y["decimals"] == 1
    assert y["values"][2] == 45.0 and y["values"][1] == 40.0          # 90/200, 100/250
    assert y["values"][3] == 112.5                                     # 45 / 40
    assert y["values"][4] == 40.0 and y["values"][5] == 12.5           # CPLY 40/100; (45-40)/40


def test_coal_flux_only_in_sail_block(gen_sail):
    d = mp.generate("2026-09")
    for b in d["blocks"]:
        if b["kind"] != "sail":
            assert "COAL MINES PRODUCTION" not in [r["label"] for r in b["rows"]]
```

- [ ] **Step 2: Run the tests to verify the new ones fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_mines_performance.py -v`
Expected: the 3 new tests FAIL (`StopIteration` — no "COAL MINES PRODUCTION" row); earlier tests pass.

- [ ] **Step 3: Write the implementation**

In `backend/mines_performance.py`, replace the stub `coal_flux_rows` with:

```python
# (heading, sail_mines_monthly section, items) -- summed into a "Total" row.
_SAIL_SIMPLE = {
    "coal_prod": ("COAL MINES PRODUCTION", ("Raw Coking Coal", "Thermal Coal")),
    "coal_despatch": ("COAL DESPATCH", ("Clean Coal", "Thermal")),
    "flux_prod": ("FLUX PRODUCTION", ("Limestone", "Dolomite")),
    "flux_despatch": ("FLUX DESPATCH", ("Limestone", "Dolomite")),
}

# Quantity indices of the 11 values (the rest are %Ful / %Gr).
_QTY_IDX = (0, 1, 2, 4, 6, 7, 9)


def _yield_values(clean: list, raw: list) -> list:
    """Washery Yield (%) = Clean Coal / Input Raw Coal x 100 for each
    quantity column, then %Ful / %Gr from those yields."""
    y = [None] * 11
    for i in _QTY_IDX:
        y[i] = _ratio(clean[i], raw[i])
    y[3], y[5] = _ratio(y[2], y[1]), _growth(y[2], y[4])
    y[8], y[10] = _ratio(y[7], y[6]), _growth(y[7], y[9])
    return y


def coal_flux_rows(data: dict, P: dict) -> list:
    """SAIL-only sections from sail_mines_monthly (coal and flux are not
    kept per mine yet): Coal Mines Production, Washery, Coal Despatch, Flux
    Production, Flux Despatch. Always shown."""
    def S(section, item):
        return data["sail"].get((section, item), {})

    def simple(section):
        heading, items = _SAIL_SIMPLE[section]
        series = [S(section, item) for item in items]
        return ([_row(heading, "heading")]
                + [_row(item, "item", values(s, P)) for item, s in zip(items, series)]
                + [_row("Total", "total", values(combine(series), P))])

    raw = values(S("washery", "Input Raw Coal"), P)
    clean = values(S("washery", "Clean Coal"), P)
    washery = [_row("WASHERY", "heading"), _row("Input Raw Coal", "item", raw),
               _row("Clean Coal", "item", clean),
               _row("Yield (%)", "item", _yield_values(clean, raw), decimals=1)]
    return (simple("coal_prod") + washery + simple("coal_despatch")
            + simple("flux_prod") + simple("flux_despatch"))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_mines_performance.py -v`
Expected: 19 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/mines_performance.py backend/tests/test_mines_performance.py
git commit -m "Mines Production Performance: SAIL coal, washery and flux sections

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: PDF template module

**Files:**
- Create: `backend/mines_performance_pdf.py`
- Modify: `backend/colors_config.json` (add key after `"perf_gr_bg"`), `backend/colors_loader.py:41` (add the same key to `_DEFAULTS`)
- Test: `backend/tests/test_mines_performance_pdf.py`

**Interfaces:**
- Consumes: the `generate()` dict shape from Task 2; `plant_performance_pdf._fonts()`, `_q(v, d)`, `_p(v)` (existing helpers: IBM Plex Sans @font-face CSS; quantity to `d` decimals; whole-number percent).
- Produces: `build_html(data: dict, decimals: int, colors: dict) -> str`; `render(html: str) -> bytes` (synchronous; call from a plain `def` route).

- [ ] **Step 1: Add the colour key**

In `backend/colors_config.json`, after the line `"perf_gr_bg":      "#e2e8f0",` add:

```json
  "mines_perf_total_bg": "#FEF3C7",
```

In `backend/colors_loader.py`, after the line `    "perf_gr_bg":      "#e2e8f0",` (line 41) add:

```python
    "mines_perf_total_bg": "#FEF3C7",
```

Check: `venv/Scripts/python.exe -c "import colors_loader as c; print(c.load_colors_config()['mines_perf_total_bg'])"` prints `#FEF3C7`.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_mines_performance_pdf.py`:

```python
"""mines_performance_pdf.build_html: block sections, SAIL page break, number
formatting, colours from the config, empty month."""
import mines_performance_pdf as mpp

COLORS = {"border_black": "#000000", "text_black": "#000000", "mines_perf_total_bg": "#ABCDEF",
          "perf_app_bg": "#FFF2CC", "perf_act_bg": "#C6EFCE", "perf_gr_bg": "#e2e8f0"}
LABELS = {"title": "Mines Production Performance :Sep'26 and Apr-Sep'26", "fy": "26-27",
          "month": "Sep'26", "cply": "Sep'25", "ytd": "Apr-Sep'26", "ytd_cply": "Apr-Sep'25"}


def _row(label, kind, vals=None, decimals=None):
    return {"label": label, "kind": kind, "values": vals or [None] * 11, "decimals": decimals}


DATA = {
    "labels": LABELS, "pct_idx": [3, 5, 8, 10],
    "blocks": [
        {"name": "Kiriburu", "kind": "mine", "group": "JGoM", "note": None, "rows": [
            _row("I/ORE FRESH PRODUCTION", "heading"),
            _row("Lump", "item", [1200.4, 100.0, 95.25, 95.25, 90.0, 5.8, 600.0, 570.0, 95.0, 550.0, 3.6]),
            _row("Total Fresh Production", "total", [1200.4, 100.0, 95.25, 95.25, 90.0, 5.8, 600.0, 570.0, 95.0, 550.0, 3.6]),
        ]},
        {"name": "SAIL", "kind": "sail", "group": None, "note": "Coal and flux note.", "rows": [
            _row("WASHERY", "heading"),
            _row("Yield (%)", "item", [40.0, 40.0, 45.0, 112.5, 40.0, 12.5, 41.0, 44.0, 107.3, 39.0, 12.8], decimals=1),
        ]},
    ],
}


def test_blocks_and_sail_break():
    html = mpp.build_html(DATA, 0, COLORS)
    assert html.count('<section class="blk') == 2
    assert '<section class="blk sail">' in html
    assert "break-before: page" in html
    assert "Coal and flux note." in html
    assert LABELS["title"] in html


def test_number_formatting():
    html = mpp.build_html(DATA, 2, COLORS)
    assert ">95.25<" in html            # quantity at 2 decimals
    assert ">95<" in html               # %Ful whole number
    assert ">45.0<" in html             # Yield quantity column at 1 decimal
    assert ">112<" in html or ">113<" in html


def test_colours_from_config():
    html = mpp.build_html(DATA, 0, COLORS)
    assert "#ABCDEF" in html


def test_pdf_html_empty():
    html = mpp.build_html({"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": []}, 0, COLORS)
    assert "No mines data for Sep'26" in html
    assert "<section" not in html
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_mines_performance_pdf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mines_performance_pdf'`.

- [ ] **Step 4: Write the implementation**

Create `backend/mines_performance_pdf.py`:

```python
"""A4 PDF of the Mines Production Performance report
(mines_performance.generate) for /reports/mines. Pages 5-6 columns, with the
fonts and border rules of plant_performance_pdf.py: separate borders, so the
table's own border is the black frame and each cell draws only its right
edge -- no light line between rows; black rules above section headings and
totals. One table per block, so each block carries the column header and is
never split across pages; the SAIL block starts a new page. Not part of the
layout-guarded monthly report. Colours come from colors_config.json."""
from html import escape

from plant_performance_pdf import _fonts, _p, _q

_MARGIN = {"top": "7mm", "right": "10mm", "bottom": "7mm", "left": "10mm"}

# value index -> column tint (pages 5-6: Plan gold, Actual green, %Gr grey)
_PLAN, _ACT, _GR = {0, 1, 6}, {2, 7}, {5, 10}


def _cls(vi: int) -> str:
    return "plan" if vi in _PLAN else "act" if vi in _ACT else "gr" if vi in _GR else ""


def _head(L: dict) -> str:
    return (
        '<thead><tr><th rowspan="2" class="ent"></th><th rowspan="2" class="l">Item</th>'
        f'<th rowspan="2" class="plan">{L["fy"]}<br>Plan</th><th colspan="3">{L["month"]}</th>'
        f'<th rowspan="2">{L["cply"]}<br>Act.</th><th rowspan="2" class="gr">%Gr.<br>{L["cply"]}</th>'
        f'<th colspan="3">{L["ytd"]}</th><th rowspan="2">{L["ytd_cply"]}<br>Act.</th>'
        f'<th rowspan="2" class="gr">%Gr.<br>{L["ytd_cply"]}</th></tr>'
        '<tr><th class="plan">Plan</th><th class="act">Actual</th><th>%Ful</th>'
        '<th class="plan">Plan</th><th class="act">Actual</th><th>%Ful</th></tr></thead>'
    )


_COLS = '<colgroup><col class="c-ent"><col class="c-lbl">' + '<col class="c-num">' * 11 + "</colgroup>"


def _block(b: dict, L: dict, pct: set, d: int) -> str:
    trs = []
    for i, r in enumerate(b["rows"]):
        cells = []
        if i == 0:
            cells.append(f'<td rowspan="{len(b["rows"])}" class="ent"><div>{escape(b["name"])}</div></td>')
        cells.append(f'<td class="lbl">{escape(r["label"])}</td>')
        qd = r["decimals"] if r["decimals"] is not None else d
        for vi, v in enumerate(r["values"]):
            text = _p(v) if vi in pct else _q(v, qd)
            cells.append(f'<td class="{_cls(vi)}">{text}</td>')
        trs.append(f'<tr class="{r["kind"]}">{"".join(cells)}</tr>')
    note = f'<p class="note">{escape(b["note"])}</p>' if b.get("note") else ""
    cls = "blk sail" if b["kind"] == "sail" else "blk"
    return (f'<section class="{cls}"><table>{_COLS}{_head(L)}<tbody>{"".join(trs)}</tbody></table>'
            f"{note}</section>")


def build_html(data: dict, decimals: int, colors: dict) -> str:
    """data: mines_performance.generate(); colors: colors_loader.load_colors_config()."""
    def c(k, dflt):  # defaults mirror colors_loader._DEFAULTS
        return colors.get(k, dflt)
    blk = c("border_black", "#000000")
    txt = c("text_black", "#000000")
    line = c("border_light", "#cbd5e1")
    L = data["labels"]
    pct = set(data["pct_idx"])
    css = f"""
  {_fonts()}
  @page {{ size: A4 portrait; margin: 7mm 10mm 7mm 10mm; }}
  body {{ font-family: 'IBM Plex Sans', Arial, sans-serif; margin: 0; color: {txt};
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .hd {{ display: flex; justify-content: space-between; align-items: flex-end;
         border-bottom: 1.5px solid {c("text_primary", "#0f172a")}; padding-bottom: 3px; margin-bottom: 4px; }}
  h2 {{ font-size: 10pt; font-weight: 700; color: rgb(0,0,255); margin: 0; }}
  .unit {{ font-size: 8.5pt; font-weight: 500; }}
  .empty {{ font-size: 10pt; font-weight: 700; margin-top: 12px; }}
  .blk {{ break-inside: avoid; margin-top: 6px; }}
  .blk.sail {{ break-before: page; }}
  .note {{ font-size: 8pt; font-style: italic; margin: 2px 0 0; }}
  table {{ table-layout: fixed; width: 100%; border-collapse: separate; border-spacing: 0;
           border: 1px solid {blk}; }}
  col.c-ent {{ width: 3.5%; }} col.c-lbl {{ width: 21%; }} col.c-num {{ width: 6.86%; }}
  th, td {{ color: {txt}; line-height: 1.1; white-space: nowrap; overflow: hidden; }}
  th {{ font-family: 'Arial Narrow', Arial, sans-serif; font-size: 8.2pt; font-weight: 700;
        text-transform: uppercase; text-align: center; padding: 1.8px 1px; border: none;
        border-right: 1px solid {c("border_medium", "#94a3b8")};
        background: {c("table_header_bg", "transparent")}; }}
  th.l {{ text-align: left; padding-left: 3px; }}
  th[colspan] {{ border-bottom: 1px solid {c("border_medium", "#94a3b8")}; }}
  thead tr:last-child th, thead tr:first-child th[rowspan] {{ border-bottom: 1px solid {blk}; }}
  td {{ font-size: 8.5pt; padding: 1.8px 2px; text-align: right; border: none; border-right: 1px solid {line}; }}
  thead tr:first-child > :last-child, tbody tr > :last-child {{ border-right: none; }}
  td.ent {{ border-right: 1px solid {blk}; text-align: center; vertical-align: middle; padding: 2px 0; }}
  td.ent div {{ writing-mode: vertical-rl; transform: rotate(180deg); margin: 0 auto;
                font-family: 'Arial Narrow', Arial, sans-serif; font-size: 8.5pt; font-weight: 700; }}
  td.lbl {{ text-align: left; white-space: normal; }}
  tr.heading td.lbl {{ font-family: 'Arial Narrow', Arial, sans-serif; font-weight: 700;
                       text-transform: uppercase; padding-left: 3px; }}
  tr.subheading td.lbl {{ font-weight: 700; font-style: italic; padding-left: 8px; }}
  tr.item td.lbl {{ padding-left: 14px; }}
  tr.total td {{ font-weight: 700; }}
  tr.total td.lbl {{ padding-left: 8px; }}
  tr.total td:not(.ent) {{ background: {c("mines_perf_total_bg", "#FEF3C7")}; }}
  td.plan, th.plan {{ background: {c("perf_app_bg", "#FFF2CC")}; }}
  td.act, th.act {{ background: {c("perf_act_bg", "#C6EFCE")}; }}
  td.gr, th.gr {{ background: {c("perf_gr_bg", "#e2e8f0")}; }}
  tr.heading td:not(.ent), tr.total td:not(.ent) {{ border-top: 1px solid {blk}; }}
  tbody tr:first-child td {{ border-top: none; }}
"""
    head = f'<div class="hd"><h2>{escape(L["title"])}</h2><span class="unit">Unit: \'000 T</span></div>'
    if data["blocks"]:
        body = "".join(_block(b, L, pct, decimals) for b in data["blocks"])
    else:
        body = f'<p class="empty">No mines data for {escape(L["month"])}.</p>'
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{head}{body}</body></html>'


def render(html: str) -> bytes:
    """Synchronous -- call from a plain `def` route (FastAPI threadpool)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.emulate_media(media="print")
        page.set_content(html, wait_until="load")
        page.evaluate("document.fonts.ready.then(() => true)")
        pdf = page.pdf(format="A4", landscape=False, print_background=True, margin=_MARGIN)
        browser.close()
    return pdf
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_mines_performance_pdf.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/mines_performance_pdf.py backend/tests/test_mines_performance_pdf.py backend/colors_config.json backend/colors_loader.py
git commit -m "Mines Production Performance: standalone PDF template

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: API router (JSON, xlsx, pdf) and wiring

**Files:**
- Create: `backend/api_mines_performance.py`
- Modify: `backend/main.py:410` (import), `backend/main.py:892` (include_router)
- Test: `backend/tests/test_api_mines_performance.py`

**Interfaces:**
- Consumes: `mines_performance.generate(month)` (Task 2/3); `mines_performance_pdf.build_html(data, decimals, colors)`, `render(html)` (Task 4); `colors_loader.load_colors_config()`; `db.init_db()`.
- Produces: routes `GET /api/mines-performance`, `/xlsx`, `/pdf` (query `month`, `decimals` 0–3, default 0); `write_sheet(ws, data, decimals)`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_api_mines_performance.py`:

```python
"""Mines performance API: validation, JSON, xlsx layout, pdf bytes."""
import io

import openpyxl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api_mines_performance as app_mod

LABELS = {"title": "Mines Production Performance :Sep'26 and Apr-Sep'26", "fy": "26-27",
          "month": "Sep'26", "cply": "Sep'25", "ytd": "Apr-Sep'26", "ytd_cply": "Apr-Sep'25"}


def _row(label, kind, vals=None, decimals=None):
    return {"label": label, "kind": kind, "values": vals or [None] * 11, "decimals": decimals}


V = [1200.4, 100.0, 95.25, 95.25, 90.0, 5.8, 600.0, 570.0, 95.0, 550.0, 3.6]
DATA = {"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": [
    {"name": "Kiriburu", "kind": "mine", "group": "JGoM", "note": None, "rows": [
        _row("I/ORE FRESH PRODUCTION", "heading"), _row("Lump", "item", V),
        _row("Total Fresh Production", "total", V)]},
    {"name": "SAIL", "kind": "sail", "group": None, "note": "note", "rows": [
        _row("Yield (%)", "item", V, decimals=1)]},
]}


@pytest.fixture
def tc(monkeypatch):
    monkeypatch.setattr(app_mod.mines_performance, "generate", lambda month: DATA)
    monkeypatch.setattr(app_mod.db, "init_db", lambda: None)
    app = FastAPI()
    app.include_router(app_mod.router)
    return TestClient(app)


def test_bad_month_and_decimals(tc):
    assert tc.get("/api/mines-performance?month=2026-13").status_code == 400
    assert tc.get("/api/mines-performance/xlsx?month=2026-09&decimals=5").status_code == 400
    assert tc.get("/api/mines-performance/pdf?month=26-09").status_code == 400


def test_json(tc):
    d = tc.get("/api/mines-performance?month=2026-09").json()
    assert d["month"] == "2026-09" and len(d["blocks"]) == 2 and d["pct_idx"] == [3, 5, 8, 10]


def test_xlsx_layout(tc):
    r = tc.get("/api/mines-performance/xlsx?month=2026-09&decimals=2")
    assert r.status_code == 200
    ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
    assert ws.title == "Mines Performance"
    assert ws.cell(1, 1).value == LABELS["title"]
    assert ws.cell(3, 4).value == "Sep'26" and ws.cell(4, 4).value == "Plan" and ws.cell(4, 5).value == "Actual"
    assert "A5:A7" in [str(m) for m in ws.merged_cells.ranges]        # Kiriburu block, 3 rows
    assert ws.cell(5, 1).value == "Kiriburu" and ws.cell(5, 2).value == "I/ORE FRESH PRODUCTION"
    assert ws.cell(6, 3).value == 1200.4 and ws.cell(6, 3).number_format == "#,##0.00"
    assert ws.cell(6, 6).number_format == "0"                        # %Ful
    assert ws.cell(8, 4).number_format == "0.0"                      # Yield quantity, 1 decimal
    assert ws.cell(8, 6).number_format == "0"                        # Yield %Ful stays whole
    assert ws.cell(7, 2).font.bold


def test_pdf(tc, monkeypatch):
    seen = {}
    monkeypatch.setattr(app_mod.mines_performance_pdf, "render",
                        lambda html: seen.setdefault("html", html) and b"%PDF-fake")
    r = tc.get("/api/mines-performance/pdf?month=2026-09&decimals=1")
    assert r.status_code == 200 and r.content == b"%PDF-fake"
    assert r.headers["content-type"] == "application/pdf"
    assert "Kiriburu" in seen["html"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_api_mines_performance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api_mines_performance'`.

- [ ] **Step 3: Write the implementation**

Create `backend/api_mines_performance.py`:

```python
"""
"Mines Production Performance" -- standalone report (mines_performance.py),
pages 5-6 layout with mines in place of plants. Not part of the monthly PDF.

  GET /api/mines-performance?month=YYYY-MM                 -> JSON
  GET /api/mines-performance/xlsx?month=YYYY-MM&decimals=N -> .xlsx
  GET /api/mines-performance/pdf?month=YYYY-MM&decimals=N  -> .pdf
"""
import io
import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

import db
import mines_performance
import mines_performance_pdf
from colors_loader import load_colors_config

router = APIRouter(prefix="/api/mines-performance", tags=["mines-performance"])


def _check_month(month: str):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month or ""):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")


def _check_decimals(decimals: int):
    if not 0 <= decimals <= 3:
        raise HTTPException(status_code=400, detail="decimals must be 0, 1, 2 or 3")


def _data(month: str) -> dict:
    db.init_db()
    return mines_performance.generate(month)


@router.get("")
def mines_performance_json(month: str = Query(...)):
    _check_month(month)
    return {"month": month, **_data(month)}


def _qty_fmt(decimals: int) -> str:
    return "#,##0" if decimals == 0 else "#,##0." + "0" * decimals


def write_sheet(ws, data: dict, decimals: int):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    L, pct = data["labels"], set(data["pct_idx"])
    ncols = 13
    thin = Side(style="thin", color="94A3B8")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hdr_fill = PatternFill("solid", fgColor="DBEAFE")
    total_fill = PatternFill("solid", fgColor="FEF3C7")
    bold = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.cell(1, 1, L["title"]).font = Font(bold=True, size=13, color="1E3A8A")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=10)
    ws.cell(2, ncols, "Unit: '000 T").alignment = Alignment(horizontal="right")

    h1, h2 = 3, 4
    top = [("", 1, 1), ("Item", 2, 2), (f"{L['fy']}\nPlan", 3, 3), (L["month"], 4, 6),
           (f"{L['cply']}\nAct.", 7, 7), (f"%Gr.\n{L['cply']}", 8, 8), (L["ytd"], 9, 11),
           (f"{L['ytd_cply']}\nAct.", 12, 12), (f"%Gr.\n{L['ytd_cply']}", 13, 13)]
    for text, c1, c2 in top:
        ws.cell(h1, c1, text)
        if c1 != c2:
            ws.merge_cells(start_row=h1, start_column=c1, end_row=h1, end_column=c2)
        else:
            ws.merge_cells(start_row=h1, start_column=c1, end_row=h2, end_column=c1)
    for i, t in enumerate(["Plan", "Actual", "%Ful"]):
        ws.cell(h2, 4 + i, t)
        ws.cell(h2, 9 + i, t)
    for r in (h1, h2):
        for c in range(1, ncols + 1):
            cell = ws.cell(r, c)
            cell.font, cell.fill, cell.alignment, cell.border = bold, hdr_fill, center, border

    qty = _qty_fmt(decimals)
    indent = {"heading": 0, "subheading": 1, "total": 1, "item": 2}
    r = h2 + 1
    for b in data["blocks"]:
        start = r
        for row in b["rows"]:
            kind = row["kind"]
            lbl = ws.cell(r, 2, row["label"])
            lbl.alignment = Alignment(indent=indent[kind])
            for vi, v in enumerate(row["values"]):
                c = ws.cell(r, 3 + vi, None if v is None else round(v, 3))
                if vi in pct:
                    c.number_format = "0"
                elif row["decimals"] is not None:
                    c.number_format = "0." + "0" * row["decimals"]
                else:
                    c.number_format = qty
            for col in range(1, ncols + 1):
                cell = ws.cell(r, col)
                cell.border = border
                if col >= 2 and kind in ("heading", "total"):
                    cell.font = bold
                if col >= 2 and kind == "total":
                    cell.fill = total_fill
            if kind == "subheading":
                lbl.font = Font(bold=True, italic=True)
            r += 1
        ws.cell(start, 1, b["name"])
        if r - 1 > start:
            ws.merge_cells(start_row=start, start_column=1, end_row=r - 1, end_column=1)
        ws.cell(start, 1).font = bold
        ws.cell(start, 1).alignment = Alignment(text_rotation=90, horizontal="center", vertical="center")

    for c, w in enumerate([6, 32] + [10] * 11, start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[h1].height = 30
    ws.freeze_panes = ws.cell(h2 + 1, 3)


@router.get("/xlsx")
def mines_performance_xlsx(month: str = Query(...), decimals: int = Query(0)):
    _check_month(month)
    _check_decimals(decimals)
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Mines Performance"
    write_sheet(ws, _data(month), decimals)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"Mines_Performance_{month}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/pdf")
def mines_performance_pdf_download(month: str = Query(...), decimals: int = Query(0)):
    # A plain def, so FastAPI runs it in its threadpool: the DB queries and
    # the synchronous Playwright render must not block the event loop.
    _check_month(month)
    _check_decimals(decimals)
    html = mines_performance_pdf.build_html(_data(month), decimals, load_colors_config())
    content = mines_performance_pdf.render(html)
    fname = f"Mines_Performance_{month}.pdf"
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
```

- [ ] **Step 4: Wire the router into `main.py`**

In `backend/main.py`, after line 410 (`from api_plant_performance import router as plant_performance_router`) add:

```python
from api_mines_performance import router as mines_performance_router
```

After line 892 (`app.include_router(plant_performance_router)`) add:

```python
app.include_router(mines_performance_router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_api_mines_performance.py tests/test_mines_performance.py tests/test_mines_performance_pdf.py -v`
Expected: 27 passed.

Then: `venv/Scripts/python.exe -m py_compile main.py` (no output), and against the running dev backend (auto-reloads):
`curl -s "http://127.0.0.1:8082/api/mines-performance?month=2026-09" | head -c 300`
Expected: JSON starting `{"month":"2026-09","labels":{"title":"Mines Production Performance :Sep'26 ...`.

- [ ] **Step 6: Commit**

```bash
git add backend/api_mines_performance.py backend/tests/test_api_mines_performance.py backend/main.py
git commit -m "Mines Production Performance: JSON, Excel and PDF endpoints

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Frontend tab

**Files:**
- Create: `frontend/src/components/reports/mines-performance/View.js`
- Modify: `frontend/src/components/reports/reportGroups.js` (the `mines` group's `tabs`), `frontend/src/components/reports/ReportTabs.js` (`VIEWS` map, after the `'iron-ore-mines'` line)

**Interfaces:**
- Consumes: `GET /api/mines-performance?month=` JSON (Task 5): `{labels, pct_idx, blocks: [{name, kind, note, rows: [{label, kind, values, decimals}]}]}`; download routes `/xlsx` and `/pdf` with `decimals`.
- Produces: tab id `mines-performance`.

- [ ] **Step 1: Register the tab**

In `frontend/src/components/reports/reportGroups.js`, in the group with `id: 'mines'`, add after the `iron-ore-mines` tab entry:

```js
      { id: 'mines-performance', label: 'Mines Production Performance', description: 'Mine, group and SAIL production, despatch, reported production and booked quantity against plan and last year (pages 5-6 layout); Excel and PDF download.' },
```

In `frontend/src/components/reports/ReportTabs.js`, after the `'iron-ore-mines': ...` line in `VIEWS` add:

```js
  'mines-performance': dynamic(() => import('./mines-performance/View'), { loading }),
```

- [ ] **Step 2: Create the view**

Create `frontend/src/components/reports/mines-performance/View.js`:

```jsx
'use client';

import React, { useEffect, useState } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Mines Production Performance (backend mines_performance.py): one block per
// mine, per group and for SAIL, pages 5-6 columns. Unrounded values from the
// API, shown to the chosen number of decimals; percentages whole numbers
// (Washery Yield's quantity columns use the row's own 1 decimal).

const DECIMALS_KEY = 'mp-decimals';

// Same type and rules as the Plant Wise Performance view and the PDF.
const FONT = "'IBM Plex Sans', sans-serif";
const NARROW = "'Arial Narrow', Arial, sans-serif";
const LINE = '1px solid #cbd5e1';
const RULE = '1px solid #000';
// pages 5-6 column tints (backend colors_config.json perf_* / mines_perf_total_bg)
const PLAN_BG = '#FFF2CC';
const ACT_BG = '#C6EFCE';
const GR_BG = '#e2e8f0';
const TOTAL_BG = '#FEF3C7';
const PLAN_IDX = new Set([0, 1, 6]);
const ACT_IDX = new Set([2, 7]);
const GR_IDX = new Set([5, 10]);
const LAST_COL = 10;

function previousMonth() {
  const now = new Date();
  const m = now.getMonth(); // 0-based == last month, 1-based
  const y = m === 0 ? now.getFullYear() - 1 : now.getFullYear();
  return `${y}-${String(m === 0 ? 12 : m).padStart(2, '0')}`;
}

function fmtQty(v, d) {
  if (v == null) return '';
  return Number(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
}

function fmtPct(v) {
  if (v == null) return '';
  const s = String(Math.round(v));
  return s === '-0' ? '0' : s;
}

const TH = {
  padding: '3px 4px', borderRight: LINE, background: '#dbeafe',
  fontFamily: NARROW, fontSize: '8.2pt', fontWeight: 700, lineHeight: 1.05,
  textTransform: 'uppercase', textAlign: 'center', whiteSpace: 'pre-line', verticalAlign: 'middle',
};
const TD = {
  padding: '2px 5px', borderRight: LINE, fontFamily: FONT, fontSize: '8.5pt',
  lineHeight: 1.15, textAlign: 'right', whiteSpace: 'nowrap',
};
const LABEL = {
  heading: { fontFamily: NARROW, fontWeight: 700, textTransform: 'uppercase', color: '#1e3a8a', paddingLeft: 4 },
  subheading: { fontWeight: 700, fontStyle: 'italic', paddingLeft: 12 },
  item: { paddingLeft: 22 },
  total: { fontWeight: 700, paddingLeft: 12 },
};

const btn = (disabled, primary) => ({
  padding: '8px 18px', fontSize: '10.5pt', fontWeight: 700, borderRadius: 6,
  cursor: disabled ? 'not-allowed' : 'pointer',
  border: primary ? 'none' : '1px solid #1a73e8',
  background: disabled ? '#dadce0' : primary ? '#1a73e8' : '#fff',
  color: primary ? '#fff' : '#1a73e8',
});

function cellBg(vi) {
  if (PLAN_IDX.has(vi)) return PLAN_BG;
  if (ACT_IDX.has(vi)) return ACT_BG;
  if (GR_IDX.has(vi)) return GR_BG;
  return undefined;
}

function MinesTable({ data, decimals }) {
  const L = data.labels;
  const pct = new Set(data.pct_idx);
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'separate', borderSpacing: 0, border: RULE, width: '100%', minWidth: 1100 }}>
        <thead>
          <tr>
            <th rowSpan={2} style={{ ...TH, width: 34, borderBottom: RULE }} />
            <th rowSpan={2} style={{ ...TH, textAlign: 'left', borderBottom: RULE }}>Item</th>
            <th rowSpan={2} style={{ ...TH, background: PLAN_BG, borderBottom: RULE }}>{`${L.fy}\nPlan`}</th>
            <th colSpan={3} style={{ ...TH, borderBottom: LINE }}>{L.month}</th>
            <th rowSpan={2} style={{ ...TH, borderBottom: RULE }}>{`${L.cply}\nAct.`}</th>
            <th rowSpan={2} style={{ ...TH, background: GR_BG, borderBottom: RULE }}>{`%Gr.\n${L.cply}`}</th>
            <th colSpan={3} style={{ ...TH, borderBottom: LINE }}>{L.ytd}</th>
            <th rowSpan={2} style={{ ...TH, borderBottom: RULE }}>{`${L.ytd_cply}\nAct.`}</th>
            <th rowSpan={2} style={{ ...TH, background: GR_BG, borderBottom: RULE, borderRight: 'none' }}>{`%Gr.\n${L.ytd_cply}`}</th>
          </tr>
          <tr>
            {['Plan', 'Actual', '%Ful', 'Plan', 'Actual', '%Ful'].map((h, i) => (
              <th key={i} style={{ ...TH, borderBottom: RULE, background: h === 'Plan' ? PLAN_BG : h === 'Actual' ? ACT_BG : TH.background }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.blocks.map((b, bi) => b.rows.map((r, ri) => {
            // Black rule above every block, section heading and total row
            // (none on the very first row: the header's rule is there).
            const ruled = (bi > 0 || ri > 0) && (ri === 0 || r.kind === 'heading' || r.kind === 'total');
            const top = ruled ? { borderTop: RULE } : {};
            const qd = r.decimals ?? decimals;
            const isTotal = r.kind === 'total';
            return (
              <tr key={`${bi}-${ri}`}>
                {ri === 0 && (
                  <td rowSpan={b.rows.length} style={{ ...TD, ...top, borderRight: RULE, textAlign: 'center', verticalAlign: 'middle', background: '#fff', padding: '2px 0' }}>
                    <div style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', margin: '0 auto', fontFamily: NARROW, fontWeight: 700, fontSize: '8.5pt' }}>
                      {b.name}
                    </div>
                  </td>
                )}
                <td style={{ ...TD, ...top, textAlign: 'left', whiteSpace: 'normal', ...LABEL[r.kind], ...(isTotal ? { background: TOTAL_BG } : {}) }}>
                  {r.label}
                </td>
                {r.values.map((v, vi) => (
                  <td key={vi} style={{
                    ...TD, ...top,
                    background: isTotal ? TOTAL_BG : cellBg(vi),
                    fontWeight: isTotal ? 700 : 400,
                    ...(vi === LAST_COL ? { borderRight: 'none' } : {}),
                  }}>
                    {pct.has(vi) ? fmtPct(v) : fmtQty(v, qd)}
                  </td>
                ))}
              </tr>
            );
          }))}
        </tbody>
      </table>
      {data.blocks.filter((b) => b.note).map((b) => (
        <p key={b.name} style={{ fontFamily: FONT, fontSize: '8.5pt', fontStyle: 'italic', color: '#475569', margin: '4px 0 0' }}>
          {b.name}: {b.note}
        </p>
      ))}
    </div>
  );
}

export default function MinesPerformanceView() {
  const [month, setMonth] = useState(previousMonth());
  const [decimals, setDecimals] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null); // null | 'xlsx' | 'pdf'

  // The saved choice is applied after mount (the server prerenders with 0).
  // Storage can be unavailable (private window), leaving the default.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(DECIMALS_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time sync from browser storage
      if (['0', '1', '2', '3'].includes(saved)) setDecimals(Number(saved));
    } catch { /* keep the default */ }
  }, []);

  const changeDecimals = (d) => {
    setDecimals(d);
    try { window.localStorage.setItem(DECIMALS_KEY, String(d)); } catch { /* not remembered */ }
  };

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/mines-performance?month=${encodeURIComponent(month)}`)
      .then((r) => (r.ok ? r.json() : r.json().then((b) => { throw new Error(b.detail || r.statusText); })))
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e) => { if (!cancelled) { setData(null); setError(e.message); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [month]);

  const changeMonth = (m) => {
    if (!m || m === month) return;
    setLoading(true);
    setMonth(m);
  };

  const download = async (kind) => {
    setDownloading(kind);
    try {
      const res = await fetch(`${API}/api/mines-performance/${kind}?month=${encodeURIComponent(month)}&decimals=${decimals}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Mines_Performance_${month}.${kind}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(null);
    }
  };

  const busy = downloading !== null || !data;

  return (
    <ReportPage
      maxWidth={1500}
      title={<>Mines Production Performance</>}
      description={<>Each iron-ore mine, its group and SAIL: fresh production, despatch by end use, reported production and booked quantity, against plan and last year. Coal and flux at SAIL level. Tonnage in &apos;000 T.</>}
    >
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        <label htmlFor="mp-month" style={{ fontSize: '10.5pt', fontWeight: 600, color: '#3c4043' }}>Report month</label>
        <input id="mp-month" type="month" value={month} onChange={(e) => changeMonth(e.target.value)}
               style={{ padding: '6px 8px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6 }} />
        <label htmlFor="mp-decimals" style={{ fontSize: '10.5pt', fontWeight: 600, color: '#3c4043' }}>Decimals</label>
        <select id="mp-decimals" value={decimals} onChange={(e) => changeDecimals(Number(e.target.value))}
                style={{ padding: '6px 8px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6 }}>
          {[0, 1, 2, 3].map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <button type="button" onClick={() => download('xlsx')} disabled={busy} style={btn(busy, true)}>
          {downloading === 'xlsx' ? 'Preparing…' : 'Download Excel'}
        </button>
        <button type="button" onClick={() => download('pdf')} disabled={busy} style={btn(busy, false)}>
          {downloading === 'pdf' ? 'Preparing…' : 'Download PDF'}
        </button>
      </div>

      {loading && <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>Loading…</div>}
      {error && (
        <div style={{ padding: '12px 16px', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, color: '#991b1b', fontSize: 13, marginBottom: 12 }}>
          {error}
        </div>
      )}

      {!loading && data && data.blocks.length === 0 && (
        <div style={{ padding: 24, textAlign: 'center', color: '#5f6368' }}>No mines data for {data.labels.month}.</div>
      )}
      {!loading && data && data.blocks.length > 0 && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderBottom: '1.5px solid #0f172a', paddingBottom: 3, marginBottom: 4, fontFamily: FONT }}>
            <h2 style={{ fontSize: '10pt', fontWeight: 700, color: '#1e3a8a', margin: 0 }}>{data.labels.title}</h2>
            <span style={{ fontSize: '8.5pt', fontWeight: 500 }}>Unit: &apos;000 T</span>
          </div>
          <MinesTable data={data} decimals={decimals} />
        </>
      )}
    </ReportPage>
  );
}
```

- [ ] **Step 3: Lint**

Run (from `frontend/`): `npx eslint src/components/reports/mines-performance/View.js src/components/reports/reportGroups.js src/components/reports/ReportTabs.js`
Expected: no output, exit 0 (this can take ~2-3 minutes on this machine; run it in the background if needed).

- [ ] **Step 4: Check it in the browser**

With dev servers running (`start-development.bat`), open `http://localhost:3000/reports/mines?tab=mines-performance`:
- The "Mines Production Performance" tab is listed after "Iron Ore Mines (Month-wise)".
- Sep'26 shows blocks Kiriburu … Manoharpur, "Jharkhand Group of Mines", … , SAIL; block names vertical; black outer frame; no light lines between rows; black rules above headings, totals and each new block.
- Changing Decimals reformats the figures; Download Excel and Download PDF each save a file.
- A month with no data (e.g. 2030-05) shows "No mines data for May'30."

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/reports/mines-performance/View.js frontend/src/components/reports/reportGroups.js frontend/src/components/reports/ReportTabs.js
git commit -m "Mines Production Performance: /reports/mines tab

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Live verification against the SAIL Mines page

**Files:** none changed (verification only; fix and re-run earlier tasks' tests if a check fails).

**Interfaces:**
- Consumes: `mines_performance.generate`, `mines_performance.periods`, `db.get_iron_ore_group_rollup_monthly(report_months)` (existing; returns `{month: {"iron_ore_prod": {group: {"actual", "plan"}}, "iron_ore_despatch": {...}}}`).

- [ ] **Step 1: Compare SAIL figures with the existing group roll-up (live MySQL)**

Run from `backend/`:

```bash
venv/Scripts/python.exe -c "
import db, mines_performance as mp
P = mp.periods('2026-09')
d = mp.generate('2026-09')
sail = next(b for b in d['blocks'] if b['kind'] == 'sail')
val = lambda label, i: next(r for r in sail['rows'] if r['label'] == label)['values'][i]
roll = db.get_iron_ore_group_rollup_monthly(P['ytd'])
tot = lambda sec, months: sum((roll[m][sec][g]['actual'] or 0) for m in months for g in roll[m][sec])
checks = [('Reported Production month', val('Reported Production', 2), tot('iron_ore_prod', ['2026-09'])),
          ('Reported Production YTD', val('Reported Production', 7), tot('iron_ore_prod', P['ytd'])),
          ('Grand Total Despatch month', val('Grand Total Despatch', 2), tot('iron_ore_despatch', ['2026-09'])),
          ('Grand Total Despatch YTD', val('Grand Total Despatch', 7), tot('iron_ore_despatch', P['ytd']))]
for name, a, b in checks:
    print(f'{name:28s} report={a:12.3f} rollup={b:12.3f}', 'OK' if abs(a - b) < 0.001 else 'MISMATCH')
"
```

Expected: four lines, each ending `OK`. A `MISMATCH` means the generator's rule differs from `db.get_iron_ore_group_rollup_monthly`: fix `mines_performance.py`, add a test reproducing it, re-run all tests.

- [ ] **Step 2: Look at the real PDF and Excel**

```bash
SP="<scratchpad dir>"
curl -s -o "$SP/mp.pdf" "http://127.0.0.1:8082/api/mines-performance/pdf?month=2026-09&decimals=0"
curl -s -o "$SP/mp.xlsx" "http://127.0.0.1:8082/api/mines-performance/xlsx?month=2026-09&decimals=0"
venv/Scripts/python.exe -c "
import sys, pypdfium2
d = pypdfium2.PdfDocument(sys.argv[1] + '/mp.pdf'); print('pages', len(d))
for i in range(len(d)):
    d[i].render(scale=1.6).to_pil().save(sys.argv[1] + f'/mp{i}.png')
" "$SP"
```

Open the PNGs: no block split across pages; SAIL block on its own page with the coal/flux sections and the note; black frame; no light lines between rows; numbers not clipped. Open `mp.xlsx` with openpyxl or Excel: block names in merged vertical cells, headings bold, totals filled.

- [ ] **Step 3: Full backend test run**

Run: `venv/Scripts/python.exe -m pytest tests -q`
Expected: all pass (the new 27 plus the existing suite).

- [ ] **Step 4: Commit (only if Step 1/2 needed a fix)**

```bash
git add backend/mines_performance.py backend/tests/test_mines_performance.py
git commit -m "Mines Production Performance: match the SAIL Mines roll-up

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
