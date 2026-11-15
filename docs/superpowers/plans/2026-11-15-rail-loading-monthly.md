# Monthly Rail Loading Page (40.05) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Print a new first Rail Logistics page (40.05) with SAIL's month-wise rail loading by commodity, fed by a new table loaded from the Rail Movement Cell's monthly highlights note.

**Architecture:** A pure text parser (`rail_loading_highlights.py`) turns the note into `{month: {item_code: rakes}}`; a script saves it through two new repo functions into `rail_loading_monthly`. `rail_loading.py` holds the item registry and builds the FY table; `page_rail_logistics.py` exposes it as part `"loading"` of the existing Rail Logistics pages, so `main.py`'s dispatch, page lists and export insertion pick it up through `RAIL_LOGISTICS_PAGES`.

**Tech Stack:** Python 3 / FastAPI, MySQL (`repo/`), Jinja2 + Playwright Chromium PDF, Next.js 16 / React.

**Spec:** `docs/superpowers/specs/2026-11-14-rail-loading-monthly-design.md`

## Global Constraints

- Python: `backend/venv/Scripts/python.exe`, tools as `python.exe -m <tool>`; commands below run from `backend/`.
- SQL only in `backend/repo/`, native MySQL, `%s` placeholders, `_ver.bump(cur)` before the first write.
- **Deviation from the spec:** the two repo functions go into the existing `backend/repo/rake.py` (as the rake despatch ones did), not a new `repo/rail_loading.py`. A new repo module must be in `repo_oracle.DOMAIN_MODULES`, and `test_modules_keep_the_v1_public_functions_and_signatures` then imports `_v1_frozen.<module>`, which may never be edited.
- Table `rail_loading_monthly`: `report_month CHAR(7)` FK `cal_month`, `item_code VARCHAR(32)`, `rakes DOUBLE NULL`, `updated_at DATETIME`, `updated_by VARCHAR(64)`; PK `(report_month, item_code)`.
- Item codes, labels and print order exactly as the spec's "Rows" tables. Totals are stored as the note reports them, never summed. `misc_other = misc_total − misc_pellets` at parse time. Blank sinter / port export = 0.
- Page id `40.05`, type `rail_logistics_loading`, title `"Rail Logistics – Monthly Rail Loading"`, portrait, badge group 10, first of the section. Index row "Rail Logistics – Rake Despatch" count 3 → 4.
- Placeholder: `"Monthly rail loading for FY <fy> not yet entered"` (fy like `2026-27`). Missing value prints `"–"`.
- Colours: existing `rail_log_*` / `perf_*` keys only; no new keys, no hex in templates. Table borders 1px. CSS class prefix `rll-`.
- Read `backend/docs/PDF_LAYOUT_GUARDRAILS.md` before Task 4. No change to pages 40.1–40.3.
- Out of scope: data-entry/upload screen, older history.
- The live database (`mis_reports_v2`) is touched only in Task 6, after a backup and the user's go-ahead. Keep code working before the table exists is not needed: the dev server is expected to error on 40.05 until Task 6 runs, so do Tasks 1–5 without relying on it.

## Review Focus

1. Formatting drift in a note block (`2rakes`, `*2298 rakes @ 74.13  Rakes*`, `–616 rakes`, `rake` singular, `( iii )` vs `(iii)`, Oct's reordered OGOM line) → all seven months of the real file parse with no problems. (Task 2 `test_every_month_of_the_file_parses`.)
2. A truncated / damaged block → that month is reported in `problems` and absent from the result; the other months still load. (Task 2 `test_damaged_block_is_skipped_whole`.)
3. Fractional coal summed over months (46.3 + 50.5 + …) → FYTD prints `96.8`, never `96.80000000000001`; whole numbers print without `.0`. (Task 3 `test_fmt_rakes`, `test_fytd_and_per_day`.)
4. A gap month inside the FY (Apr and Jun loaded, May not) → May prints "–", FYTD sums the months present, FYTD rakes/day divides by the days of the months present only. (Task 3 `test_gap_month`.)
5. Report month in Jan–Mar, or an FY with rows only after the report month → correct FY columns (2027-02 → FY 2026-27, Apr'26…Mar'27, Mar blank); later months never leak in; nothing at all → placeholder. (Task 3 `test_jan_mar_fy_and_future_months_blank`, `test_placeholder`.)

---

### Task 1: Storage

**Files:**
- Modify: `backend/scripts/v2/schema_v2.sql` (after the `rake_export_despatch` table), `backend/repo/rake.py` (new section at the end), `backend/tools/repo_oracle.py` (`WRITE_FUNCTIONS["rake"]` += `"save_rail_loading"`), `backend/tools/verify_v2.py` (`V2_ONLY_TABLES` += `"rail_loading_monthly"`), `backend/tests/test_schema_v2.py` (`NEW_DIMENSIONS` += same), `backend/docs/SETUP.md:147` and `backend/docs/DB_V2_CUTOVER.md:115` (75 → 76 tables), `docs/DATA_MODEL_AND_REPORT_PAGES.md` (repo/rake.py row ~190; new table row after the rake despatch one ~255: fed by `scripts/load_rail_loading_highlights.py`, prints on MIS PDF page 40.05)
- Create: `backend/scripts/v2/migrate_add_rail_loading.sql` (header as `migrate_add_rake_despatch.sql`; `CREATE TABLE IF NOT EXISTS`, constraint `fk_rail_loading_month`)
- Test: `backend/tests/test_rail_loading.py`

**Interfaces — Produces (in `repo.rake`):**
- `rail_loading_rows(first_month: str, last_month: str) -> List[dict]` — `[{report_month, item_code, rakes}]`, `ORDER BY report_month, item_code`.
- `save_rail_loading(report_month: str, values: Dict[str, Optional[float]], user: Optional[str]) -> int` — `_keys.check_month`, `_keys.fits("item_code", code, 32, nullable=False)`, `_keys.fits("updated_by", user, 64)`; bump, `ensure_month`, delete the month's rows, insert the given ones with `updated_at = NOW()`; returns the row count. An empty dict clears the month. `activity_context.record(f"rail_loading/{month}", None, {"items": n})`.

- [ ] **Step 1: Failing test** (`mysql_db` fixture, as `tests/test_rake_despatch.py::test_save_and_build_report`)

```python
def test_save_and_read_round_trip(mysql_db):
    from repo import conn as rc
    from repo import rake as rrake

    def n():
        with rc.cursor() as cur:
            cur.execute("SELECT n FROM data_version WHERE id = 1")
            return cur.fetchone()[0]

    assert rrake.rail_loading_rows("2026-04", "2027-03") == []
    n0 = n()
    assert rrake.save_rail_loading("2026-04", {"grand_total": 2239, "coal_coking": 46.3, "out_sinter": None}, "x@sail.in") == 3
    assert n() > n0
    rrake.save_rail_loading("2026-05", {"grand_total": 2302}, None)
    rows = rrake.rail_loading_rows("2026-04", "2026-04")
    assert [(r["report_month"], r["item_code"], r["rakes"]) for r in rows] == [
        ("2026-04", "coal_coking", 46.3), ("2026-04", "grand_total", 2239.0), ("2026-04", "out_sinter", None)]
    # a re-save replaces the month, other months untouched
    rrake.save_rail_loading("2026-04", {"grand_total": 2240}, None)
    assert [(r["report_month"], r["item_code"], r["rakes"]) for r in rrake.rail_loading_rows("2026-04", "2026-05")] == [
        ("2026-04", "grand_total", 2240.0), ("2026-05", "grand_total", 2302.0)]
    with pytest.raises(Exception):
        rrake.save_rail_loading("2026-04", {"x" * 33: 1}, None)
    assert len(rrake.rail_loading_rows("2026-04", "2026-04")) == 1      # nothing half-saved
```

- [ ] **Step 2:** `venv/Scripts/python.exe -m pytest tests/test_rail_loading.py -q` — FAIL (`AttributeError: rail_loading_rows`).
- [ ] **Step 3:** Schema, migration, repo functions, the four registration edits, the three doc edits.
- [ ] **Step 4:** `venv/Scripts/python.exe -m pytest tests/test_rail_loading.py tests/test_schema_v2.py tests/test_repo_boundary.py tests/test_repo_writes_bump.py tests/test_repo_oracle.py tests/test_no_unbound_local_imports.py -q` — PASS.
- [ ] **Step 5: Commit** "Rail loading monthly: table, migration, repo read/save".

---

### Task 2: Highlights parser and loader script

**Files:**
- Create: `backend/rail_loading_highlights.py`, `backend/scripts/load_rail_loading_highlights.py`, `backend/tests/fixtures/rail_loading_highlights.txt` (byte copy of `I:\My Drive\Report_format\Miscellaneous\Monthly Rail logistic highlights.txt`, UTF-8)
- Test: `backend/tests/test_rail_loading.py`

**Interfaces:**
- Consumes: `repo.rake.save_rail_loading` (Task 1); `rail_loading.CODES` is **not** needed here — the parser owns its own code → pattern table `PATTERNS` (ordered dict, the 23 stored codes minus `misc_other`).
- Produces: `rail_loading_highlights.parse(text: str) -> Tuple[Dict[str, Dict[str, float]], List[str]]` — `(months, problems)`. Blocks split on `Rail Transportation Performance of SAIL during <MONTH> <YEAR>`; month name → `YYYY-MM`.

Parsing rules (the spec's "from the note" column gives each anchor):
- Normalise each block first: drop `*`, turn `–`/`—` into `-`, collapse whitespace runs (including newlines) to one space. Match case-insensitively; number = `\d+(?:\.\d+)?`, optional spaces around `-`/`:` and before `rakes?`.
- `grand_total` = "during the month was N rakes". `out_sinter` and `export_port` accept a missing number → `0.0`. All other codes are required.
- `misc_other = round(misc_total - misc_pellets, 1)`.
- A block with any required code not found → `problems.append("<YYYY-MM>: not found: code, code")`, month not returned. An unrecognised month heading → problem too.
- Cross-check (problem text only, the month still loads): the opening sentence's "total inward was N" / "total outward was N" differ from `inward_total` / `outward_total`.

- [ ] **Step 1: Failing tests**

```python
FIXTURE = Path(__file__).parent / "fixtures" / "rail_loading_highlights.txt"
APR = {"ore_ogom_jgom": 641, "ore_bhilai": 193, "ore_total": 834, "flux_limestone": 120, "flux_dolomite": 79,
       "flux_total": 199, "port_coal": 356, "port_limestone": 23, "port_total": 379, "coal_coking": 46.3,
       "coal_power": 79.7, "coal_total": 126, "misc_pellets": 95, "misc_other": 13, "misc_total": 108,
       "inward_total": 1623, "out_steel": 526, "out_slag": 79, "out_coke": 9, "out_sinter": 2,
       "outward_total": 616, "grand_total": 2239, "export_port": 0, "export_nepal": 4, "export_total": 4}
OCT = {"ore_ogom_jgom": 662, "ore_bhilai": 209, "ore_total": 871, "flux_limestone": 125, "flux_dolomite": 93,
       "flux_total": 218, "port_coal": 351, "port_limestone": 46, "port_total": 397, "coal_coking": 51.7,
       "coal_power": 55.3, "coal_total": 107, "misc_pellets": 100, "misc_other": 4, "misc_total": 104,
       "inward_total": 1651, "out_steel": 533, "out_slag": 95, "out_coke": 14, "out_sinter": 0,
       "outward_total": 642, "grand_total": 2293, "export_port": 0, "export_nepal": 10, "export_total": 10}

def _parsed():
    return rlh.parse(FIXTURE.read_text(encoding="utf-8"))

def test_april_and_october_goldens():
    months, _ = _parsed()
    assert months["2026-04"] == APR and months["2026-10"] == OCT

def test_every_month_of_the_file_parses():
    months, problems = _parsed()
    assert sorted(months) == [f"2026-{m:02d}" for m in range(4, 11)] and problems == []
    assert [months[m]["grand_total"] for m in sorted(months)] == [2239, 2302, 2332, 2328, 2298, 2115, 2293]
    assert months["2026-05"]["out_sinter"] == 0 and months["2026-07"]["export_nepal"] == 2   # "2rakes"

def test_damaged_block_is_skipped_whole():
    text = FIXTURE.read_text(encoding="utf-8").replace("Total Flux loaded 195 rakes", "Total Flux loaded many rakes")
    months, problems = rlh.parse(text)
    assert "2026-05" not in months and len(months) == 6
    assert problems == ["2026-05: not found: flux_total"]

def test_inward_cross_check_is_reported_but_loads():
    text = FIXTURE.read_text(encoding="utf-8").replace("total inward was 1623 rakes", "total inward was 1600 rakes")
    months, problems = rlh.parse(text)
    assert "2026-04" in months and len(problems) == 1 and "2026-04" in problems[0] and "1600" in problems[0]

def test_no_blocks():
    assert rlh.parse("nothing here") == ({}, [])
```

- [ ] **Step 2:** run — FAIL (`ModuleNotFoundError`).
- [ ] **Step 3:** Implement `rail_loading_highlights.py`.
- [ ] **Step 4:** run — PASS.
- [ ] **Step 5:** Write `scripts/load_rail_loading_highlights.py <file> [--dry-run]` (sys.path bootstrap as the other `scripts/*.py`; no SQL): parse; for each month print the label and every code's figure in registry order, plus the problems; unless `--dry-run`, `save_rail_loading(month, values, "load_rail_loading_highlights")` per parsed month; exit code 1 if there were problems. Check: `venv/Scripts/python.exe scripts/load_rail_loading_highlights.py tests/fixtures/rail_loading_highlights.txt --dry-run` prints seven months and "0 problems", writes nothing.
- [ ] **Step 6: Commit** "Rail loading monthly: highlights note parser and loader script".

---

### Task 3: Item registry and page data

**Files:**
- Create: `backend/rail_loading.py`
- Modify: `backend/page_rail_logistics.py` (`PAGE_IDS`, `_TITLES`, `generate_rail_logistics`, docstring), `backend/tests/test_page_rail_logistics.py::test_page_ids`
- Test: `backend/tests/test_rail_loading.py`

**Interfaces:**
- Consumes: `repo.rake.rail_loading_rows`; `rake_despatch_report.fy_start_year / fy_label / fy_months / days_in / mlabel`.
- Produces (`rail_loading.py`):
  - `ITEMS: tuple` of `(kind, code, label)` in print order, `kind` ∈ `"group" | "item" | "total" | "grand" | "per_day"`: group "INWARD – RAW MATERIALS & COAL", the 16 inward rows (`*_total` rows `"total"`, `inward_total` `"total"`), group "OUTWARD – FROM SAIL PLANTS", 5 rows, `grand_total` (`"grand"`, "GRAND TOTAL (inward + outward)"), `("per_day", "per_day", "Rakes per day")`, group "EXPORT (memo, included in iron & steel)", 3 rows (`export_total` `"total"`). Labels verbatim from the spec.
  - `CODES: tuple` — the 25 stored codes in print order.
  - `fmt_rakes(v) -> str` — `"–"` for None, else `f"{round(v, 1):g}"`.
  - `loading_table(rows: list, month: str) -> dict` — pure. `{"fy", "month_labels" (Apr…Mar, 3 letters), "has_data": bool, "rows": [{"kind", "code", "label", "months": [12 × float|None], "fytd": float|None, "fytd_per_day": float|None}]}`. Only months of the report month's FY up to the report month count; unknown codes in `rows` are ignored. `fytd` = sum of present months rounded to 1 dp. `fytd_per_day` (for `total`/`grand` kinds only, else None) = fytd ÷ days of the months that row has, 2 dp. The `per_day` row: `months` = grand_total ÷ days in that month (2 dp), `fytd` = None, `fytd_per_day` = the grand row's. Group rows: `months` all None, `fytd` None.
  - `build_page(month: str) -> dict` — reads `rail_loading_rows(first FY month, month)`; returns `{"available": has_data, "subtitle": f"{mlabel(month)} · FY {fy}", "placeholder": None | f"Monthly rail loading for FY {fy} not yet entered", "fy", "month_labels", "rows"}`.
- `page_rail_logistics`: `PAGE_IDS = {40.05: "loading", 40.1: "summary", 40.2: "history", 40.3: "wagon"}` (40.05 first — `main.py` inserts in dict order); `_TITLES["loading"] = "Rail Logistics – Monthly Rail Loading"`; `generate_rail_logistics(month, "loading")` returns `{"type": "rail_logistics_loading", "title": …, **rail_loading.build_page(month)}` before touching `rdr.build_report`.

- [ ] **Step 1: Failing tests** (pure; `rows = [{"report_month", "item_code", "rakes"}]`)

```python
def _rows(d):
    return [{"report_month": m, "item_code": c, "rakes": v} for m, cv in d.items() for c, v in cv.items()]

def test_registry_matches_the_parser():
    assert len(rl.CODES) == 25 and len(set(rl.CODES)) == 25
    assert set(rl.CODES) == set(APR)
    assert [k for k, _c, _l in rl.ITEMS].count("group") == 3
    assert rl.CODES[0] == "ore_ogom_jgom" and rl.CODES[-1] == "export_total"

def test_fmt_rakes():
    assert [rl.fmt_rakes(v) for v in (None, 0, 2239.0, 46.3, 96.80000000000001)] == ["–", "0", "2239", "46.3", "96.8"]

def test_fytd_and_per_day():
    t = rl.loading_table(_rows({"2026-04": {"grand_total": 2239, "coal_coking": 46.3, "bogus": 9},
                                "2026-05": {"grand_total": 2302, "coal_coking": 50.5}}), "2026-05")
    by = {r["code"]: r for r in t["rows"]}
    assert t["fy"] == "2026-27" and t["has_data"] and t["month_labels"][0] == "Apr" and len(t["month_labels"]) == 12
    assert by["grand_total"]["months"][:3] == [2239, 2302, None] and by["grand_total"]["fytd"] == 4541
    assert by["grand_total"]["fytd_per_day"] == round(4541 / 61, 2)
    assert by["coal_coking"]["fytd"] == 96.8 and by["coal_coking"]["fytd_per_day"] is None
    assert by["per_day"]["months"][:3] == [74.63, 74.26, None] and by["per_day"]["fytd_per_day"] == round(4541 / 61, 2)
    assert by["ore_total"]["months"] == [None] * 12 and by["ore_total"]["fytd"] is None
    assert "bogus" not in by and [r["code"] for r in t["rows"] if r["kind"] != "group"][:1] == ["ore_ogom_jgom"]

def test_gap_month():
    t = rl.loading_table(_rows({"2026-04": {"grand_total": 2239}, "2026-06": {"grand_total": 2332}}), "2026-06")
    g = next(r for r in t["rows"] if r["code"] == "grand_total")
    assert g["months"][:3] == [2239, None, 2332] and g["fytd"] == 4571 and g["fytd_per_day"] == round(4571 / 60, 2)

def test_jan_mar_fy_and_future_months_blank():
    t = rl.loading_table(_rows({"2026-04": {"grand_total": 1}, "2027-02": {"grand_total": 5},
                                "2027-03": {"grand_total": 7}, "2027-04": {"grand_total": 9}}), "2027-02")
    g = next(r for r in t["rows"] if r["code"] == "grand_total")
    assert t["fy"] == "2026-27" and g["months"][0] == 1 and g["months"][10] == 5 and g["months"][11] is None and g["fytd"] == 6

def test_placeholder(monkeypatch):
    import page_rail_logistics as prl
    monkeypatch.setattr(rl.rrake, "rail_loading_rows", lambda a, b: [])
    p = prl.generate_rail_logistics("2026-10", "loading")
    assert (p["type"], p["title"], p["available"]) == ("rail_logistics_loading", "Rail Logistics – Monthly Rail Loading", False)
    assert p["placeholder"] == "Monthly rail loading for FY 2026-27 not yet entered"
    assert list(prl.PAGE_IDS) == [40.05, 40.1, 40.2, 40.3]
```

(`rail_loading` imports `from repo import rake as rrake`, as `rake_despatch_report` does.) Update `test_page_rail_logistics.py::test_page_ids` to the four-entry dict.

- [ ] **Step 2:** run — FAIL. **Step 3:** implement. **Step 4:** `venv/Scripts/python.exe -m pytest tests/test_rail_loading.py tests/test_page_rail_logistics.py -q` — PASS.
- [ ] **Step 5: Commit** "Rail loading monthly: item registry and page data (40.05)".

---

### Task 4: PDF template and report wiring

**Files:**
- Create: `backend/page_templates/rail_logistics_loading.html`
- Modify: `backend/page_templates/main.html:1955` (add `'rail_logistics_loading'` to the `content-page` tuple) and `:1997` (include line); `backend/pdf.py:389` (`_jinja_env.filters['rl_rakes'] = rail_loading.fmt_rakes`) and the badge comment at `:614` (40.05-40.3); `backend/main.py:398-401` (`("Rail Logistics – Rake Despatch", 4)` + comment: 40.05 monthly rail loading, then 40.1-40.3); `backend/report_utils.py` (`_CANONICAL_PAGE_ORDER`: `40.05` before `40.1`; `_DEPT_BADGE_EXPLICIT_GROUP`: `40.05: 10`; the comment at `:82`)

**Template** (structure and styles as `rail_logistics_wagon.html`; `coal-title` heading, right-aligned subtitle, placeholder branch): one table, `table-layout: fixed`, 7.5pt, 1px `border_dark` borders. Columns: Item (left, ~27%), 12 months, FYTD (`perf_act_bg`/`perf_act_text`), FYTD rakes/day. Rows by `kind`: `group` → one `colspan=15` cell, bold, `rail_log_section_title` text on `rail_log_card_bg`; `item` → label indented; `total` → bold on `rail_log_total_row_bg`; `grand` and `per_day` → bold, 8.5pt, on `perf_app_bg` with `perf_app_text` (use the actual gold key names in `colors_config.json`). Month/FYTD cells through `|rl_rakes`; rakes/day cells through `|rl_fmt(2)`; the FYTD rakes/day cell is empty (not "–") on `item` rows.

- [ ] **Step 1:** Make the edits; `grep -n "RAIL_LOGISTICS_PAGES\|40\.1" backend/main.py backend/pdf.py backend/report_utils.py` and confirm no other place lists the Rail Logistics ids by hand.
- [ ] **Step 2:** `venv/Scripts/python.exe -c "import pdf; print(pdf._pgclass(40.05), pdf._pgclass(40.1))"` — two different class names (if they collide, fix `_pgclass` minimally and say so).
- [ ] **Step 3:** Heed the layout_guard PostToolUse output (no `rll-` class clash); `venv/Scripts/python.exe -m pytest tests -q -k "rail or layout or report_utils or index"` — PASS.
- [ ] **Step 4: Commit** "Rail loading monthly: PDF page 40.05, Index row 4 pages".

---

### Task 5: Browser preview

**Files:**
- Modify: `frontend/src/components/RailLogisticsTemplates.js` (add `export function RailLogisticsLoadingTemplate({ data })`, same structure, placeholder and hex copies as the other three; number formatting mirrors `fmt_rakes`), `frontend/src/components/PageRenderer.js` (import, supported-types set `:61`, `case 'rail_logistics_loading'`), `frontend/src/app/report/page.js` (`PAGE_LABELS[40.05] = 'Rail Logistics – Monthly Rail Loading'` before 40.1; `SERVER_DATED_TYPES` += `'rail_logistics_loading'`)

- [ ] **Step 1:** Read `frontend/AGENTS.md`; make the edits.
- [ ] **Step 2:** `cd frontend && npm run lint` — no new errors in the three files.
- [ ] **Step 3: Commit** "Rail loading monthly: /report preview of page 40.05".

---

### Task 6: Live database, history load, real render

**Needs the user's go-ahead (live `mis_reports_v2`).** Procedure: `backend/docs/MYSQL_MODEL_CHANGES.md` Step 7.

- [ ] **Step 1:** Backup: `scripts\backup_mysql.bat`; confirm a new `mis_reports_v2_*.sql` in `Report_format\db_backup\`.
- [ ] **Step 2:** Apply `scripts\v2\migrate_add_rail_loading.sql` (Step 7.3 command); `SHOW CREATE TABLE mis_reports_v2.rail_loading_monthly` matches `schema_v2.sql`.
- [ ] **Step 3:** `venv/Scripts/python.exe scripts/load_rail_loading_highlights.py "I:\My Drive\Report_format\Miscellaneous\Monthly Rail logistic highlights.txt" --dry-run`, read the figures, then without `--dry-run` — seven months saved, 0 problems.
- [ ] **Step 4:** `curl -s "http://127.0.0.1:8082/api/data?month=2026-10"` → page ids around 40 are `[40, 40.05, 40.1, 40.2, 40.3, 1026]`; 40.05 has `available: true`, grand total Oct = 2293. Same for `2026-03` (FY 2025-26, nothing loaded) → placeholder text.
- [ ] **Step 5:** `venv/Scripts/python.exe layout_guard.py --render 2026-10` — success; page count grew by exactly 1; 40.05 has no `fit-to-page` line or ≥ 95%.
- [ ] **Step 6:** pypdfium2 → PNG of the 40.05 sheet and the Index page (scratchpad), look at them: one sheet, nothing clipped, Apr–Oct filled, Nov–Mar blank, coking coal shows decimals. pdfplumber: table rects 1px; total-row fill = `rail_log_total_row_bg`; Index row "Rail Logistics – Rake Despatch" starts at 40.05's sheet and the next section starts 4 sheets later.
- [ ] **Step 7:** `/report` in the browser, month 2026-10: 40.05 renders before 40.1, label in the page list, no "Unsupported page type".
- [ ] **Step 8:** `venv/Scripts/python.exe -m pytest tests -q` — only the known baseline failures. Commit any fixes. Tell the user that `layout_guard.py --accept --render 2026-08`, the baseline commit and the `pdf-layout-baseline-*` tag await their go-ahead, and that other machines must run the migration and the loader after pulling.
