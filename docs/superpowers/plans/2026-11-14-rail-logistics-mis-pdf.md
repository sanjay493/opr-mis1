# Rail Logistics MIS PDF Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Print three portrait "Rail Logistics – Rake Despatch" pages (40.1 Summary, 40.2 Performance history, 40.3 Wagon types) in the MIS PDF between Capital Repair and Rake Detention.

**Architecture:** A new `page_rail_logistics.py` reshapes `rake_despatch_report.build_report(month)` per page (no new arithmetic, no SQL). Three Jinja templates render it; `main.py` / `report_utils.py` place the sentinel pages, Index row and badge; `RailLogisticsTemplates.js` mirrors them in the browser preview.

**Tech Stack:** Python 3 / FastAPI, Jinja2 + Playwright Chromium PDF, MySQL via `repo.rake` (read only), Next.js 16 / React.

**Spec:** `docs/superpowers/specs/2026-11-14-rail-logistics-mis-pdf-design.md`

## Global Constraints

- Python: `backend/venv/Scripts/python.exe`, tools as `python.exe -m <tool>`.
- No SQL outside `backend/repo/`; this feature adds none.
- Page ids exactly `40.1`, `40.2`, `40.3`; badge group `10`; Index row title `"Rail Logistics – Rake Despatch"`, 3 pages, between `"Status of Capital/Major Repairs Planned in ABP - Plant Wise"` and `"Details of Rakes Detention Plant Wise"`.
- Portrait only (no `_LANDSCAPE_TYPES` change). Tables 7.5–8pt, 1px borders.
- Every colour a `colors_config.json` key used as `{{ colors.<key> }}`, mirrored in `colors_loader._DEFAULTS`; new keys prefixed `rail_log_`; plan/actual columns reuse `perf_app_*` / `perf_act_*`.
- Plan attainment table has **no Status column**; attainment cell tinted by `rake_despatch_report.status_of` ("ok"/"watch"/"behind"/"na" → no tint).
- No upload for the month → each page prints title + `"Despatch Summary Report for <Mon'YY> not uploaded"` (Mon'YY from `rake_despatch_report.mlabel`).
- Read `backend/docs/PDF_LAYOUT_GUARDRAILS.md` before Task 2. Do not run `layout_guard.py --accept`, commit the baseline, or tag — the user asks for that separately.
- Simplification vs spec: no extra memoisation of `build_report`; `main._pc` already caches each page per month/data version, and three reads per uncached render are cheap.

## Review Focus

1. Plant missing from page-1 position (e.g. a plant with no slag line) → its cells print "–", the row still prints; never `None`/`nan` text. (Task 1 test `test_commodity_rows_missing_metrics`.)
2. A wagon type present for one plant only / months with no rows yet → blank cells, FYTD sums only present months; SAIL block sums across plants. (Task 1 `test_wagon_type_blocks_sparse`.)
3. Month without any upload → all three pages render the placeholder, no exception from template access to missing keys. (Task 1 `test_unavailable_placeholder`, Task 3 render check.)
4. Export with no rows for the month → section prints "No export programme for <Mon'YY>" instead of an empty table with only total rows of 0. (Task 1 `test_export_rows_empty`.)
5. Page overflow: a month with more wagon types (e.g. 8 at BSP) must still fit 40.3 on one sheet; verify `fit-to-page` for 40.1–40.3 is ≥ 95% in the 2026-10 render (Task 5).

---

### Task 1: Page data module

**Files:**
- Create: `backend/page_rail_logistics.py`
- Test: `backend/tests/test_page_rail_logistics.py`

**Interfaces:**
- Consumes: `rake_despatch_report.build_report(month) -> dict` (keys `available`, `headline`, `ranking`, `run_rate`, `records`, `trend`, `wagon_mix`, `export`, `key_points`, `fy`, `fy_months`, `source.position`, `source.slab`, `source.slab_note`, `source.types`), plus `PLANTS`, `ALL`, `mlabel`, `status_of`.
- Produces:
  - `PAGE_IDS = {40.1: "summary", 40.2: "history", 40.3: "wagon"}`
  - `generate_rail_logistics(month: str, part: str) -> dict` — always has `type = f"rail_logistics_{part}"`, `title`, `subtitle` (`f"{mlabel(month)} · FY {fy}"`, or `mlabel(month)` when unavailable), `available: bool`, `placeholder: str|None`. When available:
    - summary: `headline`, `commodity` (from `commodity_rows`), `slab`, `slab_note`, `key_points`, `ranking` (each row + `tint` = `status_of(attainment)`), `run_rate`
    - history: `records`, `trend` (from `trend_rows`), `month_labels` (Apr…Mar), `export` (from `export_rows`)
    - wagon: `mix` (from `mix_matrix`), `blocks` (from `wagon_type_blocks`), `month_labels`
  - Titles: `"Rail Logistics – Rake Despatch: Summary"`, `"… : Performance History"`, `"… : Wagon Types"`.
  - `commodity_rows(position: dict) -> list[dict]` — one row per `ALL` plant: `{"plant", "slag": {...}, "coke": {...}, "sinter": {...}}`, each `{"on_date","cumm","avg_day","plan_avg_day"}` from `<c>_on_date`, `<c>_cumm`, `<c>_avg_day`, `<c>_plan_avg_day`; missing → `None`.
  - `mix_matrix(wagon_mix: dict) -> dict` — `{"label", "plants": PLANTS, "rows": [{"type", "shares": {plant: fytd_share|None}, "sail_share", "sail_shift"}]}`, row order = SAIL entry's `types` order.
  - `wagon_type_blocks(types: dict, fy_months: list) -> list[dict]` — per `PLANTS` plant that has rows, then `"SAIL"` (sum over plants): `{"plant", "rows": [{"type", "months": [12 x int|None], "fytd": int|None}], "total": {"months": [...], "fytd": ...}}`; type rows sorted by FYTD desc.
  - `trend_rows(trend: dict) -> list[dict]` — flattened `ALL` order, newest FY first: `{"plant", "fy", "months", "total", "first_of_plant": bool}`.
  - `export_rows(export: list) -> list` — returns `[]` when no row has a non-zero prog or actual, else the list unchanged.
  - Jinja filter helper `fmt(v, nd=0) -> str` — `"–"` for `None`, else formatted with `nd` decimals.

- [ ] **Step 1: Write failing tests** (pure, no DB; build small dicts by hand)

```python
import page_rail_logistics as rl

def test_commodity_rows_missing_metrics():
    rows = rl.commodity_rows({"BSP": {"slag_cumm": 40.0, "slag_on_date": 1.0}})
    bsp = next(r for r in rows if r["plant"] == "BSP")
    assert bsp["slag"] == {"on_date": 1.0, "cumm": 40.0, "avg_day": None, "plan_avg_day": None}
    assert [r["plant"] for r in rows] == ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]
    assert next(r for r in rows if r["plant"] == "DSP")["coke"]["cumm"] is None

def test_mix_matrix_order_and_shares():
    mix = {"label": "Oct'26 vs H1", "plants": [
        {"plant": "BSP", "types": [{"type": "BOXN", "fytd_share": 60.0, "share_now": 0, "share_before": 0, "shift_pp": 1.0, "fytd_rakes": 6}]},
        {"plant": "SAIL", "types": [
            {"type": "BRN", "fytd_share": 55.0, "shift_pp": -2.0, "fytd_rakes": 11},
            {"type": "BOXN", "fytd_share": 45.0, "shift_pp": 2.0, "fytd_rakes": 9}]}]}
    m = rl.mix_matrix(mix)
    assert [r["type"] for r in m["rows"]] == ["BRN", "BOXN"]
    assert m["rows"][1]["shares"]["BSP"] == 60.0 and m["rows"][0]["shares"]["BSP"] is None
    assert m["rows"][1]["sail_share"] == 45.0 and m["rows"][1]["sail_shift"] == 2.0

def test_wagon_type_blocks_sparse():
    months = [f"2026-{m:02d}" for m in range(4, 13)] + [f"2027-{m:02d}" for m in (1, 2, 3)]
    types = {"BSP": {"BOXN": {"2026-04": 5, "2026-05": 7}, "DMT": {"2026-05": 1}},
             "DSP": {"BOXN": {"2026-04": 2}}}
    blocks = rl.wagon_type_blocks(types, months)
    assert [b["plant"] for b in blocks] == ["BSP", "DSP", "SAIL"]
    bsp = blocks[0]
    assert [r["type"] for r in bsp["rows"]] == ["BOXN", "DMT"]
    assert bsp["rows"][1]["months"][:3] == [None, 1, None] and bsp["rows"][1]["fytd"] == 1
    assert bsp["total"]["months"][:2] == [5, 8] and bsp["total"]["fytd"] == 13
    sail_boxn = next(r for r in blocks[-1]["rows"] if r["type"] == "BOXN")
    assert sail_boxn["months"][0] == 7 and sail_boxn["fytd"] == 14

def test_trend_rows_flatten():
    t = {p: [{"fy": "2026-27", "months": [1] + [None] * 11, "total": 1},
             {"fy": "2025-26", "months": [2] * 12, "total": 24}] for p in rl.ALL}
    rows = rl.trend_rows(t)
    assert len(rows) == 12 and rows[0]["first_of_plant"] and not rows[1]["first_of_plant"]
    assert rows[2]["plant"] == "DSP" and rows[2]["first_of_plant"]

def test_export_rows_empty():
    zero = [{"destination": "GRAND TOTAL", "prog": 0, "actual": 0, "is_total": True}]
    assert rl.export_rows(zero) == []
    assert rl.export_rows([{"destination": "X", "prog": 2, "actual": 1}]) != []

def test_unavailable_placeholder(monkeypatch):
    monkeypatch.setattr(rl.rdr, "build_report", lambda m: {"report_month": m, "available": False, "months": []})
    for part in ("summary", "history", "wagon"):
        p = rl.generate_rail_logistics("2026-10", part)
        assert p["type"] == f"rail_logistics_{part}" and p["available"] is False
        assert p["placeholder"] == "Despatch Summary Report for Oct'26 not uploaded"

def test_fmt():
    assert rl.fmt(None) == "–" and rl.fmt(12.345, 2) == "12.35" and rl.fmt(7) == "7"
```

- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_page_rail_logistics.py -v` (from `backend/`) — expect FAIL: `ModuleNotFoundError: page_rail_logistics`.
- [ ] **Step 3: Implement** `backend/page_rail_logistics.py` per the Interfaces block. Import `rake_despatch_report as rdr` (the test monkeypatches `rl.rdr.build_report`). Module docstring in the style of `page_rake_detention.py`: what it prints, where it sits, "no arithmetic beyond regrouping".
- [ ] **Step 4: Run** the same pytest — expect all PASS; then `venv/Scripts/python.exe -c "import page_rail_logistics as r, json; [print(k, sorted(r.generate_rail_logistics('2026-10', k))) for k in ('summary','history','wagon')]"` — expect three key lists with `available` and no exception.
- [ ] **Step 5: Commit** `git add backend/page_rail_logistics.py backend/tests/test_page_rail_logistics.py && git commit -m "Rail Logistics PDF pages: page data module"`.

---

### Task 2: Templates and colours

**Files:**
- Create: `backend/page_templates/rail_logistics_summary.html`, `rail_logistics_history.html`, `rail_logistics_wagon.html`
- Modify: `backend/colors_config.json`, `backend/colors_loader.py` (`_DEFAULTS`), `backend/page_templates/main.html:1955` (add the three types to the `content-page` tuple) and the include chain near `main.html:1995`, `backend/pdf.py` (register `fmt` as Jinja filter `rl_fmt` next to `_jinja_env.filters['pgclass']`)

**Interfaces:**
- Consumes: page dicts from Task 1 (`page.<key>`), `colors.*`.
- Produces: rendering for page types `rail_logistics_summary|history|wagon`.

Content per spec "Pages". Shared conventions: page heading `<div class="coal-title">{{ page.title }}</div>` + right-aligned italic subtitle (as `rake_detention_summary.html`); section headings small bold navy; CSS class prefix `rl-` (layout_guard flags clashes). When `not page.available`: heading + centred `page.placeholder` only.

New colour keys (values to pick, consistent with existing palette): `rail_log_card_bg`, `rail_log_card_border`, `rail_log_card_value`, `rail_log_section_title`, `rail_log_tint_ok`, `rail_log_tint_watch`, `rail_log_tint_behind`, `rail_log_total_row_bg`, `rail_log_plant_rule`, `rail_log_pos_text`, `rail_log_neg_text`.

- [ ] **Step 1:** Add the keys to both colour files; run `venv/Scripts/python.exe -m pytest tests -q -k color` — expect PASS (or no tests selected, then `python -c "import colors_loader as c; print(len(c.load_colors()))"` succeeds — use the actual loader function name in `colors_loader.py`).
- [ ] **Step 2:** Write the three templates and the `main.html`/`pdf.py` hooks.
- [ ] **Step 3:** Confirm the layout_guard PostToolUse hook prints no CSS class clash for `rl-`. Rendering is verified in Task 5 (pages are not reachable until Task 3).
- [ ] **Step 4: Commit** the templates, colour files, `main.html`, `pdf.py`.

---

### Task 3: Place the pages in the report

**Files:**
- Modify: `backend/main.py` — imports near line 83; constant block comment next to the Rake Detention one (~line 735); `_INDEX_SECTIONS` (row after Capital Repair, before Rake Detention); `_INDEX_SECTION_ANCHORS` (`40.1` after `36`); both sentinel tuples (~1120 and ~1258) — add `*RAIL_LOGISTICS_PAGES` handling as `or page_number in RAIL_LOGISTICS_PAGES` / `and p.get("page") not in RAIL_LOGISTICS_PAGES`; `pages_config.append` loop right before the `RAKE_DETENTION_DETAIL_PAGES` appends (~1350); dispatch in both page-data paths (~1450 and ~1885): `p.update(_pc(month, pg, generate_rail_logistics, month, RAIL_LOGISTICS_PAGES[pg]))`, `p["orientation"] = "portrait"`
- Modify: `backend/report_utils.py` — `_CANONICAL_PAGE_ORDER` add `40.1, 40.2, 40.3` after `*range(36, 41)`; `_DEPT_BADGE_EXPLICIT_GROUP` add `40.1: 10, 40.2: 10, 40.3: 10`; one comment entry in the sentinel-id list above it.
- Modify: `frontend/src/components/PageRenderer.js` is Task 4 — not here.

**Interfaces:**
- Consumes: `from page_rail_logistics import PAGE_IDS as RAIL_LOGISTICS_PAGES, generate_rail_logistics`.
- Produces: `/api/data?month=2026-10` page list containing 40.1, 40.2, 40.3 directly after 40 and before 1026.

- [ ] **Step 1:** Make the edits.
- [ ] **Step 2: Verify order:** `curl -s "http://127.0.0.1:8082/api/data?month=2026-10" | venv/Scripts/python.exe -c "import sys,json; d=json.load(sys.stdin); ps=[p['page'] for p in d.get('pages', d)]; i=ps.index(40); print(ps[i:i+5])"` — expect `[40, 40.1, 40.2, 40.3, 1026]` (adjust the key if the payload nests pages differently). Also check the Index page row text in the same payload shows "Rail Logistics – Rake Despatch".
- [ ] **Step 3: Verify placeholder month:** same curl for a month with no despatch upload (e.g. `2026-04`) — pages 40.1–40.3 present with `available: false`.
- [ ] **Step 4:** `venv/Scripts/python.exe -m pytest tests -q` — expect all PASS (incl. repo boundary, F823).
- [ ] **Step 5: Commit** `backend/main.py backend/report_utils.py`.

---

### Task 4: Browser preview

**Files:**
- Create: `frontend/src/components/RailLogisticsTemplates.js` — `export function RailLogisticsSummaryTemplate({ data })`, `RailLogisticsHistoryTemplate`, `RailLogisticsWagonTemplate`, structured like `RakeDetentionTemplates.js`; own copies of the Task 2 hex values.
- Modify: `frontend/src/components/PageRenderer.js` — add the three types to the supported-types set (line ~59) and three `case` lines beside `rake_detention_*`.

- [ ] **Step 1:** Write the components (same sections and placeholder as the templates; read-only).
- [ ] **Step 2:** `cd frontend && npm run lint` — expect no new errors in the two files.
- [ ] **Step 3:** Open `http://localhost:3000/report`, month 2026-10, scroll to the pages after Capital Repair ISP — the three pages render, no "Unsupported page type".
- [ ] **Step 4: Commit** the two frontend files.

---

### Task 5: Real render and layout check

**Files:** none new; template tweaks from Task 2 only if the checks fail.

- [ ] **Step 1:** From `backend/`: `venv/Scripts/python.exe layout_guard.py --render 2026-10` — expect render success; note `fit-to-page` lines for the new pages (must be absent or ≥ 95%) and that the total page count grew by exactly 3.
- [ ] **Step 2:** Render pages 40.1–40.3 of the produced PDF to PNG with pypdfium2 (scratchpad) and look at them: one sheet each, nothing clipped, Status column absent, placeholder-free.
- [ ] **Step 3:** pdfplumber on those pages: table rects 1px wide; tint colours equal the `rail_log_tint_*` values; Index page row "Rail Logistics – Rake Despatch" with the page number of 40.1 and the following sections' numbers +3.
- [ ] **Step 4:** Fix templates if any check fails; repeat Steps 1–3.
- [ ] **Step 5:** `venv/Scripts/python.exe -m pytest tests -q` — all PASS. Commit any template fixes. Report to the user that `--accept --render 2026-08`, baseline commit and tag await their go-ahead.
