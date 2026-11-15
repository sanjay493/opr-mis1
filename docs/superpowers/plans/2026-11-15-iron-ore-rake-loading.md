# Iron Ore Rake Loading from Mines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upload the mines' rake-by-rake CSV, keep every rake, and print a new Rail Logistics page (40.07) with EGOM / CGOM / Total history, wagon-type table and wagon mix; fill page 40.05's OGOM and JGOM rows from it.

**Architecture:** `iron_ore_rakes.py` owns the mine-group and wagon-type registries, the CSV parser and the page builder. Rakes live one row each in `iron_ore_rake` (SQL only in `repo/rake.py`); monthly counts are worked out at read time and fed through `rake_despatch_report`'s existing `trend` / `wagon_mix`, which gain a group-list parameter. `page_rail_logistics.py` gains the page; `api_iron_ore_rakes.py` the two-step upload.

**Tech Stack:** FastAPI, MySQL (`%s` placeholders, `repo/`), Jinja2 page templates + Playwright PDF, Next.js frontend.

**Spec:** `docs/superpowers/specs/2026-11-15-iron-ore-rake-loading-design.md`

## Global Constraints

- Python: `backend/venv/Scripts/python.exe -m ...` only. Tests: `cd backend && venv/Scripts/python.exe -m pytest tests/<file> -q`.
- SQL only in `backend/repo/rake.py`, native MySQL, `%s`; every write bumps `data_version` first (`_ver.bump(cur)`), as `save_rail_loading` does.
- Mine groups: OGOM = BOL, BAR, KAL, TAL; JGOM = KRB, MBR, GUA, MPR; CGOM = BGM, DAL, RAJ, ROW; EGOM = OGOM + JGOM.
- Wagon names: BS → `BOBSNM1`; BY → `BOYEL`; BX and EL → `BOXN`; PR → `Private GPWIS`; GP → `SAIL BOXN GPWIS`; GS → `SAIL BOBSNM1 GPWIS`. Codes compared upper-cased and stripped.
- One CSV line = one rake, every destination counts.
- Page id `40.07`, part name `mines`, type `rail_logistics_mines`, title `Rail Logistics – Iron Ore Rake Loading from Mines`, template class prefix `rlm-`.
- No hex colours in templates: existing `colors.rail_log_*` / `colors.perf_*` keys only.
- Layout-guarded files (`page_templates/`, `pdf.py`): read `backend/docs/PDF_LAYOUT_GUARDRAILS.md` first. Commit after each task; do not push.
- Commit messages end with `Co-Authored-By: Claude <noreply@anthropic.com>`.

## Review Focus

1. A file re-saved from Excel with dates like `02-04-2021` or `2/4/2021`: refused whole with a message naming the line and the expected `YYYY-MM-DD`, never guessed. (Task 1)
2. A file with blank lines, space-padded codes, lower-case codes, or no BOM / saved as ANSI: read normally. (Tasks 1, 3)
3. A header-only or empty file: refused ("no rakes in the file"), nothing deleted. (Tasks 1, 3)
4. A narrower re-upload (one month): only that date range is replaced; a month whose count falls needs confirmation. (Tasks 2, 3)
5. The report month is later than the last uploaded rake (file not yet uploaded for the month): 40.07 prints that month as "–" and its key points speak of the last month that has rakes only if it is the report month — otherwise no month sentence; 40.05's OGOM/JGOM fall back to typed values. (Tasks 5, 7)

---

### Task 1: Registries and CSV parser

**Files:**
- Create: `backend/iron_ore_rakes.py`
- Create: `backend/tests/fixtures/iron_ore_rakes.csv`
- Test: `backend/tests/test_iron_ore_rakes.py`

**Interfaces:**
- Produces:
  - `MINE_GROUP: dict[str, str]` — mine code → `"OGOM" | "JGOM" | "CGOM"`.
  - `WAGON_NAME: dict[str, str]` — wagon code → printed name.
  - `GROUPS = ["EGOM", "CGOM"]`, `TOTAL = "Total"`, `ALL = GROUPS + [TOTAL]`.
  - `parse_csv(text: str) -> list[dict]` — rows `{id: int, rpt_date: "YYYY-MM-DD", report_month: "YYYY-MM", mine_code, rake_no, dest, wagon_code, l_wg: float|None, f_wg: float|None}`; raises `ValueError` (one message, all problems of one kind listed, at most 5 examples each) and returns nothing partial.
  - `read_file(data: bytes) -> str` — utf-8-sig, falling back to cp1252.

- [ ] **Step 1: Write the fixture** — 10 data lines under the header `id,unit,rpt_date,rake_no,dest,type,l_wg,f_wg` with a BOM: BOL/BX, KAL/BS, KRB/BY, GUA/`by`, MPR/EL, DAL/PR, RAJ/GP, ROW/GS, BGM/BS with `0.00,0.00` wagons, and a BOL line repeating an earlier (unit, date, rake_no) with a new id; one `dest` of `PRSP`; one blank line in the middle; dates across 2026-09 and 2026-10.

- [ ] **Step 2: Write the failing tests**

```python
def test_registries():
    assert {g: sorted(m for m, x in ior.MINE_GROUP.items() if x == g) for g in ("OGOM", "JGOM", "CGOM")} == {
        "OGOM": ["BAR", "BOL", "KAL", "TAL"], "JGOM": ["GUA", "KRB", "MBR", "MPR"], "CGOM": ["BGM", "DAL", "RAJ", "ROW"]}
    assert ior.WAGON_NAME == {"BS": "BOBSNM1", "BY": "BOYEL", "BX": "BOXN", "EL": "BOXN", "PR": "Private GPWIS",
                              "GP": "SAIL BOXN GPWIS", "GS": "SAIL BOBSNM1 GPWIS"}
    assert ior.ALL == ["EGOM", "CGOM", "Total"]

def test_parse_fixture():
    rows = ior.parse_csv(ior.read_file(FIXTURE.read_bytes()))
    assert len(rows) == 10 and all(isinstance(r["id"], int) for r in rows)
    assert {r["wagon_code"] for r in rows} == {"BX", "BS", "BY", "EL", "PR", "GP", "GS"}   # "by" upper-cased
    assert rows[0]["report_month"] == rows[0]["rpt_date"][:7]
    assert any(r["l_wg"] == 0 and r["f_wg"] == 0 for r in rows)        # zero-wagon rake kept

def test_ansi_and_padded_codes():
    text = FIXTURE.read_text(encoding="utf-8-sig").replace(",BOL,", ", bol ,")
    assert len(ior.parse_csv(ior.read_file(text.encode("cp1252")))) == 10

@pytest.mark.parametrize("change, message", [
    (("id,unit,", "id,mine,"), "column"),                 # header missing
    ((",BOL,", ",XYZ,"), "XYZ"),                          # unknown mine
    ((",GS,", ",QQ,"), "QQ"),                             # unknown wagon type
    (("2026-10-0", "0-10-2026"), "YYYY-MM-DD"),           # not an ISO date
])
def test_refusals(change, message): ...   # replace in the fixture text; pytest.raises(ValueError, match=message)

def test_refuses_repeated_id_future_date_and_empty():
    # a duplicated id line -> "id"; a 2099 date with today="2026-11-15" -> "future"; header only -> "no rakes"
```

`parse_csv(text, today: str | None = None)` — `today` defaults to the real date and exists for the future-date test.

- [ ] **Step 3: Run** `pytest tests/test_iron_ore_rakes.py -q` — expected: fails on import.
- [ ] **Step 4: Implement** `iron_ore_rakes.py` (registries, `read_file`, `parse_csv`) with `csv.DictReader`; header names compared stripped and lower-cased; blank lines skipped; line numbers in messages are file line numbers.
- [ ] **Step 5: Run** — expected: all pass.
- [ ] **Step 6: Commit** `Iron ore rakes: mine groups, wagon names, CSV parser`.

### Task 2: Table and repo

**Files:**
- Modify: `backend/scripts/v2/schema_v2.sql` (after `rail_loading_monthly`), create `backend/scripts/v2/migrate_add_iron_ore_rake.sql`
- Modify: `backend/repo/rake.py` (new section at the end)
- Modify: `backend/tests/test_schema_v2.py:27-29`, `backend/tools/verify_v2.py:65`, `backend/tools/repo_oracle.py:164`, `docs/DATA_MODEL_AND_REPORT_PAGES.md` (repo table row ~190, table list row ~256)
- Test: `backend/tests/test_iron_ore_rakes.py`

**Interfaces:**
- Consumes: Task 1 row shape.
- Produces (in `repo.rake`):
  - `iron_ore_rake_counts(first_month: str, last_month: str) -> List[dict]` — `[{report_month, mine_code, wagon_code, rakes}]`, `GROUP BY`, ordered.
  - `iron_ore_rake_month_totals(first_month: str, last_month: str) -> Dict[str, int]` — rakes per month.
  - `save_iron_ore_rakes(rows: List[dict], user: Optional[str]) -> dict` — `{"rakes", "deleted", "first_date", "last_date"}`. One transaction: bump, ensure every month, `DELETE ... WHERE rpt_date BETWEEN first AND last`, insert in batches of 1000. Empty `rows` → `ValueError` before connecting.

Table (follow `backend/docs/MYSQL_MODEL_CHANGES.md`):

```sql
CREATE TABLE iron_ore_rake (
    id           INT         NOT NULL,
    report_month CHAR(7)     NOT NULL,
    rpt_date     DATE        NOT NULL,
    mine_code    VARCHAR(8)  NOT NULL,
    rake_no      VARCHAR(24) NULL,
    dest         VARCHAR(8)  NULL,
    wagon_code   VARCHAR(4)  NOT NULL,
    l_wg         DOUBLE      NULL,
    f_wg         DOUBLE      NULL,
    updated_at   DATETIME    NOT NULL,
    updated_by   VARCHAR(64) NULL,
    PRIMARY KEY (id),
    KEY idx_iron_ore_rake_month (report_month, mine_code, wagon_code),
    KEY idx_iron_ore_rake_date (rpt_date),
    CONSTRAINT fk_iron_ore_rake_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

with the header comment style of its neighbours (what it holds, which repo functions use each key). Migration = the same statement with `IF NOT EXISTS`.

- [ ] **Step 1: Write the failing test** (uses the `mysql_db` fixture as `tests/test_rail_loading.py::test_save_and_read_round_trip`)

```python
def test_repo_round_trip(mysql_db):
    rows = ior.parse_csv(ior.read_file(FIXTURE.read_bytes()))
    n0 = data_version()
    out = rrake.save_iron_ore_rakes(rows, "x@sail.in")
    assert out["rakes"] == 10 and out["deleted"] == 0 and data_version() > n0
    assert sum(rrake.iron_ore_rake_month_totals("2026-04", "2027-03").values()) == 10
    counts = rrake.iron_ore_rake_counts("2026-09", "2026-10")
    assert sum(c["rakes"] for c in counts) == 10 and set(counts[0]) == {"report_month", "mine_code", "wagon_code", "rakes"}
    # a narrower re-upload replaces only its own date range
    oct_rows = [r for r in rows if r["report_month"] == "2026-10"][:1]
    out = rrake.save_iron_ore_rakes(oct_rows, None)
    sept = sum(1 for r in rows if r["report_month"] == "2026-09")
    assert rrake.iron_ore_rake_month_totals("2026-09", "2026-10")["2026-09"] == sept   # untouched
    with pytest.raises(ValueError):
        rrake.save_iron_ore_rakes([], None)
```

(The narrow file's range is that one rake's date; assert October's total equals October rakes on other dates + 1.)

- [ ] **Step 2: Run** — expected: fails (no table / function).
- [ ] **Step 3: Implement** schema, migration, repo functions; add the table and functions to the four lists/docs above.
- [ ] **Step 4: Run** `pytest tests/test_iron_ore_rakes.py tests/test_schema_v2.py tests/test_repo_boundary.py tests/test_repo_writes_bump.py tests/test_repo_oracle.py -q` — expected: pass.
- [ ] **Step 5: Apply the migration to the live `mis_reports_v2`** as `MYSQL_MODEL_CHANGES.md` describes; confirm with `SHOW CREATE TABLE iron_ore_rake`.
- [ ] **Step 6: Commit** `Iron ore rakes: iron_ore_rake table and repo`.

### Task 3: Upload API

**Files:**
- Create: `backend/api_iron_ore_rakes.py`
- Modify: `backend/main.py:496-497` (import), `:1040-1042` (`include_router`)
- Test: `backend/tests/test_iron_ore_rakes.py`

**Interfaces:**
- Consumes: `ior.read_file`, `ior.parse_csv`, the three repo functions.
- Produces: router prefix `/api/iron-ore-rakes`.
  - `POST /preview` (multipart `file`) → `{status: "preview", source_file, rakes, first_date, last_date, months: [{report_month, stored, in_file}], reduces: [report_month, ...]}`. `months` lists every month the file's date range touches whose stored total differs from what it will be after the save; `reduces` those where it falls.
  - `POST /insert` (multipart `file`, form field `confirm_replace` = `"true"`) → `{status: "ok", rakes, deleted, first_date, last_date}`; 409 with the months listed when `reduces` is non-empty and not confirmed.
  - Both `Depends(_auth.require_editor_or_admin)`; a `ValueError` from the parser → 422 with its message.
  - "Will be after the save" for a month = stored rakes outside the file's first..last date + rakes in the file. Add a repo read if needed: `iron_ore_rake_totals_outside(first_date, last_date, first_month, last_month) -> Dict[str, int]`.

- [ ] **Step 1: Write the failing tests** (FastAPI `TestClient` on an app with only this router; `app.dependency_overrides[_auth.require_editor_or_admin]` for the logged-in cases; repo functions monkeypatched to an in-memory store)

```python
def test_upload_needs_login(): ...            # no override: /preview and /insert -> 401
def test_preview_saves_nothing(client, store):  # rakes == 10, months lists both months with stored 0, store untouched
def test_insert_saves(client, store): ...     # 200, store has 10 rows, user email passed
def test_reducing_a_month_needs_confirmation(client, store):
    # store pre-filled with 9 October rakes inside the file's dates, file has fewer -> 409 naming 2026-10;
    # with confirm_replace=true -> 200
def test_bad_file_is_422_and_saves_nothing(client, store): ...   # unknown mine; header-only file
```

- [ ] **Step 2: Run** — expected: fail on import.
- [ ] **Step 3: Implement** the router and register it in `main.py` next to `rail_loading_router`.
- [ ] **Step 4: Run** `pytest tests/test_iron_ore_rakes.py tests/test_repo_boundary.py -q` — expected: pass.
- [ ] **Step 5: Commit** `Iron ore rakes: upload API (preview / insert)`.

### Task 4: Upload card

**Files:**
- Modify: `frontend/src/app/data-entry/uploads/page.js` (new card component after the Despatch Summary Report card, ~line 1200-1310; mirror that card's state, layout and wording)

**Interfaces:**
- Consumes: Task 3 endpoints. Read `frontend/AGENTS.md` first.

- [ ] **Step 1: Implement** the card "Iron ore rakes from mines (CSV)": choose file → Preview (shows rakes, first–last date, a table of months with Stored / In file, and the line "This file replaces every rake stored between <first> and <last>.") → Save. When `reduces` is non-empty the Save button reads "Replace and save" and sends `confirm_replace=true`. The file is sent again on Save. Server error `detail` is shown as text.
- [ ] **Step 2: Verify** `cd frontend && npx eslint src/app/data-entry/uploads/page.js` adds no error that the Despatch card's own code does not already have; open `http://localhost:3000/data-entry/uploads` and confirm the card renders.
- [ ] **Step 3: Commit** `Iron ore rakes: upload card`.

### Task 5: Report logic and page builder

**Files:**
- Modify: `backend/rake_despatch_report.py:180` (`wagon_mix`), `:237` (`trend`)
- Modify: `backend/iron_ore_rakes.py`
- Test: `backend/tests/test_iron_ore_rakes.py`, `backend/tests/test_rake_despatch.py` (must stay green unchanged)

**Interfaces:**
- Produces:
  - `rake_despatch_report.wagon_mix(month, type_rows, groups=PLANTS, total="SAIL")` and `trend(month, totals, rows=ALL)` — defaults keep today's behaviour exactly.
  - `iron_ore_rakes.type_rows(counts: list) -> list` — repo counts → `[{report_month, plant_code: "EGOM"|"CGOM", wagon_type: <printed name>, rakes}]`, summed (BX + EL, OGOM + JGOM).
  - `iron_ore_rakes.group_totals(counts: list) -> dict` — `{month: {"OGOM", "JGOM", "EGOM", "CGOM", "Total"}}`, zeros for a group with no rakes in a month that has rakes.
  - `iron_ore_rakes.key_points(month, totals, mix) -> list[str]`.
  - `iron_ore_rakes.build_page(month) -> dict` — `{available, subtitle, placeholder, month_label, fy, month_labels, key_points, trend, mix, blocks}`; `trend` / `mix` / `blocks` in the shapes `page_rail_logistics.trend_rows`, `mix_rows` and `wagon_type_blocks` produce today (make those three take the group lists as parameters and reuse them; no copies). Reads `iron_ore_rake_counts` from April of FY−6 (seven FYs) to `month`.
  - Not available (no rakes in the report month's FY up to `month`): `placeholder = "Iron ore rake file not uploaded for FY <fy>"`.

Key points, exact wording (each only when its figures exist):
1. `"Iron ore loading from mines in {Mon'YY}: EGOM {n} rakes ({±x.x}% vs {Mon'YY last year}), CGOM {n} rakes ({±x.x}%)."` — only when the report month itself has rakes.
2. `"FY to date the mines loaded {n} iron ore rakes, {x.x}% {ahead of|behind} the same period last year ({n})."`
3. `"Wagon mix ({mix label}): {type} share {up|down} {x.x} points to {x.x}%."` — the Total row's biggest shift, when ≥ 2 points.

- [ ] **Step 1: Write the failing tests**

```python
COUNTS = [  # (month, mine, wagon, rakes)
    ("2026-10", "BOL", "BX", 5), ("2026-10", "BOL", "EL", 2), ("2026-10", "KRB", "BS", 3), ("2026-10", "DAL", "BS", 4),
    ("2025-10", "BOL", "BX", 10), ("2025-10", "DAL", "PR", 2)]

def test_type_rows_merge_groups_and_wagons():
    rows = ior.type_rows(_counts(COUNTS))
    assert {(r["report_month"], r["plant_code"], r["wagon_type"]): r["rakes"] for r in rows}[("2026-10", "EGOM", "BOXN")] == 7

def test_group_totals():
    t = ior.group_totals(_counts(COUNTS))
    assert t["2026-10"] == {"OGOM": 7, "JGOM": 3, "EGOM": 10, "CGOM": 4, "Total": 14}

def test_build_page(monkeypatch):   # repo read patched to COUNTS
    p = ior.build_page("2026-10")
    assert p["available"] and p["fy"] == "2026-27" and len(p["month_labels"]) == 12
    assert [b["plant"] for b in p["blocks"]] == ["EGOM", "CGOM", "Total"]
    assert [r["plant"] for r in p["mix"]["rows"]] == ["EGOM", "CGOM", "Total"]
    assert len(p["trend"]) == 21 and p["trend"][0]["plant"] == "EGOM" and p["trend"][0]["months"][6] == 10
    assert p["key_points"][0].startswith("Iron ore loading from mines in Oct'26: EGOM 10 rakes (+0.0% vs Oct'25), CGOM 4 rakes (+100.0%)")

def test_month_without_rakes_yet(monkeypatch):   # report month 2026-11, rakes only to October
    p = ior.build_page("2026-11")
    assert p["available"] and p["trend"][0]["months"][7] is None
    assert not any(k.startswith("Iron ore loading from mines in") for k in p["key_points"])

def test_no_rakes_placeholder(monkeypatch):
    assert ior.build_page("2026-10")["placeholder"] == "Iron ore rake file not uploaded for FY 2026-27"
```

- [ ] **Step 2: Run** — expected: fail.
- [ ] **Step 3: Implement** — parameterise `wagon_mix`, `trend` and the three `page_rail_logistics` helpers; add the builder.
- [ ] **Step 4: Run** `pytest tests/test_iron_ore_rakes.py tests/test_rake_despatch.py tests/test_page_rail_logistics.py -q` — expected: pass.
- [ ] **Step 5: Commit** `Iron ore rakes: counts, mix, trend and page data`.

### Task 6: PDF page 40.07, wiring, preview

**Files:**
- Create: `backend/page_templates/rail_logistics_mines.html`
- Modify: `backend/page_rail_logistics.py` (`PAGE_IDS`, `_TITLES`, docstring, `generate_rail_logistics`)
- Modify: `backend/main.py:398-402` (Index row text → `"Rail Logistics – Rail Loading, Mines Loading & Rake Despatch"`, count 4 → 5, comment), `backend/report_utils.py:82-86,106,167`, `backend/pdf.py:616` (comment only)
- Modify: `frontend/src/components/RailLogisticsTemplates.js` (new `RailLogisticsMinesTemplate`), `frontend/src/app/report/page.js:74-77,258-261` and wherever the other four templates are mapped by type
- Test: `backend/tests/test_page_rail_logistics.py`, `backend/tests/test_rail_loading.py` (the export-insertion and `PAGE_IDS` tests)

**Interfaces:**
- Consumes: `iron_ore_rakes.build_page(month)`.
- Produces: `PAGE_IDS == {40.05: "loading", 40.07: "mines", 40.1: "summary", 40.2: "history", 40.3: "wagon"}`; `generate_rail_logistics(month, "mines")` → `{"type": "rail_logistics_mines", "title": ..., **build_page(month)}`.

Page content in order: title, subtitle; "Key points" list; "Seven-year monthly trend — iron ore rakes loaded per month, current FY first"; "Wagon-type mix" with 40.3's caption; "Rakes by wagon type, FY <fy> — mines group-wise, month by month". First column heading "Mines" where 40.2 / 40.3 say "Plant". Copy the table CSS of `rail_logistics_history.html` / `rail_logistics_wagon.html` under the `rlm-` prefix.

- [ ] **Step 1: Update the tests** — `test_page_ids`; the placeholder test's `list(prl.PAGE_IDS)`; every expected list in `test_export_gets_each_missing_rail_logistics_page_in_its_place` gains 40.07 after 40.05; add `test_mines_part(monkeypatch)` asserting type, title and that `build_page`'s keys pass through.
- [ ] **Step 2: Run** — expected: fail.
- [ ] **Step 3: Implement** backend wiring and template, then the React template and `/report` labels.
- [ ] **Step 4: Run** `pytest tests/test_page_rail_logistics.py tests/test_rail_loading.py tests/test_iron_ore_rakes.py -q` and `python layout_guard.py` (no CSS class clashes) — expected: pass.
- [ ] **Step 5: Commit** `Rail Logistics: page 40.07 Iron Ore Rake Loading from Mines`.

### Task 7: Page 40.05 OGOM / JGOM from the rakes

**Files:**
- Modify: `backend/rail_loading.py` (`build_page`, `with_derived`), `backend/api_rail_loading.py`, `frontend/src/components/entry/rail-loading/Form.js`
- Test: `backend/tests/test_rail_loading.py`

**Interfaces:**
- Consumes: `iron_ore_rakes.group_totals`, `repo.rake.iron_ore_rake_counts`.
- Produces:
  - `rail_loading.mines_overlay(first_month, last_month) -> dict` — `{month: {"ore_ogom": n, "ore_jgom": n}}` for months with uploaded rakes.
  - `build_page` applies the overlay before `loading_table` (overlay wins over stored rows for those two codes).
  - `with_derived` no longer sets EGOM from OGOM + JGOM (EGOM is typed as reported); the `EGOM` / `EGOM_PARTS` constants stay for the API.
  - `GET /api/rail-loading` rows gain `from_file: bool` (true for `ore_ogom` / `ore_jgom` in a month with rakes, their `value` then being the file's count) and the response gains `egom_file: number | null` (file OGOM + JGOM).
  - `POST` ignores submitted `ore_ogom` / `ore_jgom` for a month with rakes (the stored typed value is dropped).
  - Form: `from_file` rows read-only, tagged "(from the mines file)"; EGOM always typed; when `egom_file` is set and differs from the typed EGOM, a plain note under the row: "The mines file has {egom_file} rakes for OGOM + JGOM."; remove the client-side EGOM auto-sum.

- [ ] **Step 1: Write the failing tests** — `test_overlay_wins_on_the_page` (stored `ore_ogom` 1, overlay 376 → page row shows 376; a month without overlay shows the stored value); `test_with_derived` updated: EGOM stays as given; `test_api_marks_rows_from_the_file`; `test_api_save_drops_typed_ogom_when_the_month_has_rakes`.
- [ ] **Step 2: Run** — expected: fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/test_rail_loading.py -q` — expected: pass.
- [ ] **Step 5: Commit** `Monthly Rail Loading: OGOM and JGOM rows from the mines rake file`.

### Task 8: Real data, render, baseline

**Files:**
- Modify: `backend/layout_baseline.json`, `backend/docs/PDF_LAYOUT_GUARDRAILS.md` (tag name ×3, "113 pages" → 114, section list), `docs/DATA_MODEL_AND_REPORT_PAGES.md` (page 40.07 row), `CLAUDE.md` only if a rule changed (none expected)

- [ ] **Step 1:** Upload `D:\u_rakes_rmg.csv` to the dev database through the API's own code path (a short script calling `ior.parse_csv` + `rrake.save_iron_ore_rakes`, run with `-I` not required: it is our code reading the file as data). Expected: 50,980 rakes, 2020-04-01 → 2026-10-31.
- [ ] **Step 2:** Check `ior.group_totals` for 2026-04..2026-10: EGOM = 641, 668, 669, 607, 547, 529, 662; CGOM October = 211.
- [ ] **Step 3:** Render the five Rail Logistics pages for 2026-10 and look at each (pypdfium2 → PNG): 40.07 on one sheet, not scaled below 85%; 40.05 shows OGOM / JGOM filled.
- [ ] **Step 4:** `cd backend && venv/Scripts/python.exe -m pytest tests -q` (about 17 minutes) — expected: all pass.
- [ ] **Step 5:** `venv/Scripts/python.exe layout_guard.py --accept --render 2026-08` — expected: OK, 114 pages; update the guardrails doc; commit with `layout_baseline.json`; tag `pdf-layout-baseline-2026-11-15c` (or the next free name).
- [ ] **Step 6: Commit** `Layout baseline: Rail Logistics page 40.07 (Aug 2026 reference 114 pages)`.
