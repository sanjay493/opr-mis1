# Board Note Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/reports/external?tab=board-note` page that generates SAIL's
quarterly Board Note (.docx) for any FY and any quarter (1-4) from this
app's DB, with per-plant "why it fell short" narrative and extra highlights
kept as persistently editable manual text.

**Architecture:** One dispatcher (`page_board_note.py`) picks one of four
per-quarter adapter modules (`board_note_q1..q4.py`), each mutating its own
fixed docx template in place (same technique as `page_do_letter.py`) using
two shared, generalized libraries: `board_note_common.py` (period math,
DB-backed figures, best-ever scanning, formatting) and
`board_note_docx_utils.py` (generic paragraph/table/cell mutation,
extracted so all four adapters use one proven implementation instead of
four copies). Manual narrative lives in a new `board_note_manual_text`
table, read/written through `board_note_manual_text.py`, and is merged into
the generated docx by the adapters at generation time — never baked into
the template, never carried over from a prior period.

**Tech Stack:** FastAPI + `python-docx` (backend, `backend/venv`), Next.js
15/16 app-router React (frontend) — both already used by the sibling
`do_letter` feature this mirrors.

**Spec:** `docs/superpowers/specs/2026-10-05-board-note-generator-design.md`

## Global Constraints

- Run all backend Python via `backend/venv/Scripts/python.exe -m ...` — never a bare `python`/`py`.
- New SQL table needs both `init_db`'s SQLite `CREATE TABLE` (`backend/db.py`) and the mirrored entry in `backend/scripts/mysql_schema.sql` — keep them column-for-column identical.
- Write all new SQL in sqlite dialect (`?` placeholders, `ON CONFLICT ... DO UPDATE`); `dbengine.py` translates for MySQL at runtime.
- Never guess a missing figure: blank cells (`""`) and no best-ever bullet, never a fabricated number — same rule every existing generator (`page4.py`, `page_do_letter.py`) already follows.
- Finished Steel at **SAIL level** always adds Conversion; **individual-plant** Finished Steel never does (spec §3.1).
- New `(fy, quarter)` manual-text periods start blank; nothing is ever auto-copied from a prior quarter (spec §3.3).
- Fuel Rate target = Coke Rate + Nut Coke Rate + CDI Rate target whenever a plant has no direct Fuel Rate target (spec §2, §3.1).
- Read `frontend/AGENTS.md` before writing the frontend task — Next 16 in this repo differs from training-data Next.js.
- This feature produces `.docx` only — it never touches `pdf.py`, `layout_guard.py`, or `colors_config.json`, so none of the PDF-layout-guardrail process applies.

## Review Focus

- A brand-new `(fy, quarter)` with zero production data anywhere in the DB must still generate a clean docx with every figure blank, not 500 — pinned in Task 4 (`row_values`/`best_ever` with an empty DB) and Task 9 (route-level smoke test).
- `quarter` outside 1-4, or `fy` not matching `\d{4}-\d{2}`, must be a clean 400 (mirrors `do_letter`'s own `re.fullmatch` check) — pinned in Task 9.
- A best-ever scan where the current period is the *only* data point in all of history (no prior years at all) must silently skip that bullet, not crash on an empty comparison set — pinned in Task 4 (`pick_best` unit test).
- Saving manual text with an empty string for a field that previously had one must **delete** the row, mirroring `do_letter_remark_table`'s exact convention, not leave a stale empty row — pinned in Task 3.
- Per-plant best-ever bullets must skip items a plant doesn't produce (no Hot Metal for ASP/SSP/VISL, no Crude Steel narrative for VISL) rather than emitting a bogus bullet or crashing on a missing config entry — pinned in Task 4 (`ITEMS_FOR_PLANT` test for ASP and VISL).

---

### Task 1: `board_note_manual_text` table

**Files:**
- Modify: `backend/db.py` (inside `init_db`, alongside the existing `do_letter_remark_table` CREATE TABLE at `db.py:282-289`)
- Modify: `backend/scripts/mysql_schema.sql` (alongside `do_letter_remark_table` at line 172-178)

**Interfaces:**
- Produces: a `board_note_manual_text` table with columns `report_fy CHAR(7)/TEXT`, `quarter TINYINT/INTEGER`, `plant VARCHAR(16)/TEXT`, `field VARCHAR(24)/TEXT`, `text TEXT`, `PRIMARY KEY (report_fy, quarter, plant, field)` — exact shape from spec §3.3.

- [ ] **Step 1: Add the SQLite `CREATE TABLE IF NOT EXISTS board_note_manual_text` statement to `init_db` in `backend/db.py`**, right after the `do_letter_remark_table` block, with a short comment (one line) saying it backs the Board Note generator's per-plant "Additional highlights"/"Why narrative" fields and that new periods start blank by convention (not migrated/copied by any code path).
- [ ] **Step 2: Add the matching `CREATE TABLE IF NOT EXISTS board_note_manual_text ... ENGINE=InnoDB;` to `backend/scripts/mysql_schema.sql`**, right after `do_letter_remark_table`, with `report_fy CHAR(7) NOT NULL`, `quarter TINYINT NOT NULL`, `plant VARCHAR(16) NOT NULL`, `field VARCHAR(24) NOT NULL`, `text TEXT`.
- [ ] **Step 3: Verify**

Run: `cd backend && venv/Scripts/python.exe -c "import db; db.init_db(); print('ok')"`
Expected: prints `ok` with no exception (confirms the new `CREATE TABLE` is valid SQLite syntax against the live dev DB path).

- [ ] **Step 4: Commit**

```bash
git add backend/db.py backend/scripts/mysql_schema.sql
git commit -m "Add board_note_manual_text table for Board Note editable narrative"
```

---

### Task 2: `board_note_docx_utils.py` — generic docx mutation helpers

**Files:**
- Create: `backend/board_note_docx_utils.py`
- Test: `backend/tests/test_board_note_docx_utils.py`

**Interfaces:**
- Produces: `set_cell(cell, text: str) -> None`, `set_para(paragraph, text: str) -> None`, `replace_in_para(paragraph, replacements: list[tuple[str, str]]) -> None`, `remove_paragraph(paragraph) -> None`, `clone_paragraph_after(ref_paragraph, text: str)` (returns the new `Paragraph`), `fill_variable_bullets(slots: list, lines: list[str]) -> None`.
- Consumes: only `python-docx` (`docx.Document`, `docx.text.paragraph.Paragraph`) — no DB, no other board_note module.

These are the same operations already proven in `page_do_letter.py`
(`_set_paragraph_text`, `_set_cell_text`, `_remove_paragraph`,
`_clone_paragraph_after`), pulled out standalone so all four adapters share
one implementation. `fill_variable_bullets` generalizes the "fill N
template slots, clone extras, delete unused slots" pattern already used
there for the best-ever bullets list.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_board_note_docx_utils.py`:

```python
import docx

import board_note_docx_utils as u


def _doc_with_paragraphs(*texts):
    d = docx.Document()
    paras = [d.add_paragraph(t) for t in texts]
    return d, paras


def test_set_para_keeps_first_run_formatting_and_clears_rest():
    d, [p] = _doc_with_paragraphs("old")
    p.add_run(" extra")
    u.set_para(p, "new")
    assert p.text == "new"


def test_replace_in_para_substring_swap():
    d, [p] = _doc_with_paragraphs("Q-2'25-26:")
    u.replace_in_para(p, [("Q-2'25-26", "Q-2'26-27")])
    assert p.text == "Q-2'26-27:"


def test_set_cell_clears_extra_paragraphs():
    d = docx.Document()
    t = d.add_table(rows=1, cols=1)
    cell = t.rows[0].cells[0]
    cell.add_paragraph("second line")
    u.set_cell(cell, "only line")
    assert [p.text for p in cell.paragraphs] == ["only line"]


def test_fill_variable_bullets_exact_fit():
    d, slots = _doc_with_paragraphs("a", "b", "c")
    u.fill_variable_bullets(slots, ["x", "y", "z"])
    assert [p.text for p in d.paragraphs] == ["x", "y", "z"]


def test_fill_variable_bullets_fewer_lines_removes_unused_slots():
    d, slots = _doc_with_paragraphs("a", "b", "c")
    u.fill_variable_bullets(slots, ["x"])
    assert [p.text for p in d.paragraphs] == ["x"]


def test_fill_variable_bullets_more_lines_clones_extra_paragraphs():
    d, slots = _doc_with_paragraphs("a")
    u.fill_variable_bullets(slots, ["x", "y", "z"])
    assert [p.text for p in d.paragraphs] == ["x", "y", "z"]


def test_fill_variable_bullets_empty_lines_removes_all_slots():
    d, slots = _doc_with_paragraphs("a", "b")
    u.fill_variable_bullets(slots, [])
    assert [p.text for p in d.paragraphs] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_docx_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'board_note_docx_utils'`

- [ ] **Step 3: Implement `backend/board_note_docx_utils.py`** — port `_set_paragraph_text`/`_set_cell_text`/`_remove_paragraph`/`_clone_paragraph_after` from `page_do_letter.py:348-377` verbatim under the new public names, then write `fill_variable_bullets(slots, lines)`: zip `slots` with `lines` calling `set_para` on each matched pair; if `lines` is longer, call `clone_paragraph_after` on the last slot (or last cloned paragraph) for each remaining line, in order; if `slots` is longer, call `remove_paragraph` on every unmatched trailing slot.
- [ ] **Step 4: Run to verify pass**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_docx_utils.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/board_note_docx_utils.py backend/tests/test_board_note_docx_utils.py
git commit -m "Add shared docx mutation helpers for Board Note adapters"
```

---

### Task 3: `board_note_manual_text.py` — manual narrative storage

**Files:**
- Create: `backend/board_note_manual_text.py`
- Test: `backend/tests/test_board_note_manual_text.py`

**Interfaces:**
- Consumes: `board_note_docx_utils.fill_variable_bullets` (Task 2), `db.connect()`.
- Produces: `FIELDS = ("additional_highlights", "why_narrative")`; `get_manual_text(fy: str, quarter: int) -> dict[tuple[str, str], str]` keyed `(plant, field)`; `save_manual_text(fy: str, quarter: int, entries: list[dict]) -> int` (returns count processed; entries shaped `{"plant": str, "field": str, "text": str}`); `additional_highlight_lines(manual: dict, plant: str) -> list[str]`; `why_narrative_lines(manual: dict, plant: str, placeholder: str) -> list[str]`.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_board_note_manual_text.py`, following `tests/test_cover_store.py`'s own fixture pattern (throwaway SQLite file, `monkeypatch` on the module's DB entry point):

```python
import sqlite3

import pytest

import board_note_manual_text as bnm


@pytest.fixture
def store(tmp_path, monkeypatch):
    dbfile = tmp_path / "board_note.db"
    conn = sqlite3.connect(dbfile)
    conn.execute("""
        CREATE TABLE board_note_manual_text (
            report_fy TEXT, quarter INTEGER, plant TEXT, field TEXT, text TEXT,
            PRIMARY KEY (report_fy, quarter, plant, field)
        )
    """)
    conn.commit()
    conn.close()

    class _Conn:
        def __init__(self):
            self._c = sqlite3.connect(dbfile)
        def cursor(self):
            return self._c.cursor()
        def commit(self):
            self._c.commit()
        def close(self):
            self._c.close()

    monkeypatch.setattr(bnm.db, "connect", _Conn)
    return bnm


def test_get_manual_text_empty_for_untouched_period(store):
    assert store.get_manual_text("2026-27", 2) == {}


def test_save_then_get_round_trip(store):
    store.save_manual_text("2026-27", 2, [
        {"plant": "BSP", "field": "additional_highlights", "text": "BF-8 record"},
    ])
    assert store.get_manual_text("2026-27", 2) == {("BSP", "additional_highlights"): "BF-8 record"}


def test_empty_text_deletes_existing_row(store):
    store.save_manual_text("2026-27", 2, [{"plant": "BSP", "field": "why_narrative", "text": "shutdown"}])
    store.save_manual_text("2026-27", 2, [{"plant": "BSP", "field": "why_narrative", "text": ""}])
    assert store.get_manual_text("2026-27", 2) == {}


def test_new_period_never_sees_another_periods_text(store):
    store.save_manual_text("2025-26", 2, [{"plant": "BSP", "field": "why_narrative", "text": "old year text"}])
    assert store.get_manual_text("2026-27", 2) == {}


def test_additional_highlight_lines_splits_and_strips_blanks():
    manual = {("BSP", "additional_highlights"): "line one\n\nline two  "}
    assert bnm.additional_highlight_lines(manual, "BSP") == ["line one", "line two"]


def test_why_narrative_lines_uses_placeholder_when_blank():
    assert bnm.why_narrative_lines({}, "BSP", "[Add narrative]") == ["[Add narrative]"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_manual_text.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'board_note_manual_text'`

- [ ] **Step 3: Implement `backend/board_note_manual_text.py`.** `get_manual_text` runs `SELECT plant, field, text FROM board_note_manual_text WHERE report_fy=? AND quarter=?` and returns `{(plant, field): text for ... if text}` (drop empty/NULL rows, same convention `do_letter_remark_table`'s reader uses). `save_manual_text` loops entries: non-empty `text.strip()` does an `INSERT ... ON CONFLICT(report_fy, quarter, plant, field) DO UPDATE SET text = excluded.text`; empty does `DELETE FROM board_note_manual_text WHERE report_fy=? AND quarter=? AND plant=? AND field=?` — same two-branch shape as `save_do_letter_remarks` in `main.py:5311-5346`. `additional_highlight_lines` returns `[ln.strip() for ln in manual.get((plant, "additional_highlights"), "").split("\n") if ln.strip()]`. `why_narrative_lines` returns the same split/stripped list, or `[placeholder]` if that list is empty.
- [ ] **Step 4: Run to verify pass**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_manual_text.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/board_note_manual_text.py backend/tests/test_board_note_manual_text.py
git commit -m "Add Board Note manual-narrative storage (get/save + line helpers)"
```

---

### Task 4: `board_note_common.py` — period math, figures, best-ever, formatting

**Files:**
- Create: `backend/board_note_common.py`
- Test: `backend/tests/test_board_note_common.py`

**Interfaces:**
- Consumes: `page4._p4_get`, `page4.PAGE4_ITEMS`, `page_do_letter._fetch_conversion`, `page_techno._get_plant_techno_plan_targets`, `page_techno.compute_sail_targets`.
- Produces (all used by every adapter, Tasks 5-8):
  - `quarter_months(fy_start: int, quarter: int) -> list[str]`
  - `long_period_months(fy_start: int, quarter: int) -> list[str] | None` (`None` for quarter 1; else the FY's first 6/9/12 months for quarter 2/3/4)
  - `fy_months(fy_start: int) -> list[str]` (all 12)
  - `quarter_label(fy_start: int, quarter: int) -> str` (e.g. `"Q-2’26-27"`)
  - `long_period_label(fy_start: int, quarter: int) -> str | None` (e.g. `"H-1’26-27"` / `"9M’26-27"` / `"FY’26-27"`)
  - `ITEMS_FOR_PLANT: dict[str, list[tuple[str, str]]]` mapping plant code -> `[(display_label, db_item), ...]` it reports (big-5 + SAIL: Hot Metal, Crude Steel, Saleable Steel, Finished Steel; ASP/SSP: Crude Steel, Saleable Steel, Finished Steel; VISL: Saleable Steel, Finished Steel)
  - `pick_best(totals: dict[int, float], cur_fy: int) -> tuple[float, float, int] | None`
  - `fmt_mt(v: float) -> str`, `fmt_t(v: float) -> str`, `fmt_tbl(v, plant: str) -> str`, `fmt_ann(v) -> str`, `fmt_pct(v) -> str`, `imp_phrase(v: int) -> str`
  - `period_sum(cur, table: str, months: list[str], plant: str, db_item: str) -> float | None`
  - `conv_sum(cur, months: list[str]) -> float | None`
  - `row_values(cur, plant: str, db_item: str, cur_months: list[str], cply_months: list[str], fy_start: int, add_conv: bool = False) -> tuple` (`ann, abp, act, pct, cply, gr`)
  - `best_ever(cur, plant: str, db_item: str, period_months_fn, cur_fy_start: int, add_conv: bool = False) -> tuple | None`
  - `best_ever_bullets(cur, plant: str, period_months_fn, cur_fy_start: int, style: str) -> list[str]` (`style` picks the wording — see Task 5-8 for the exact per-quarter phrasing each adapter needs)
  - `fuel_rate_fallback(tgt: dict[str, float | None]) -> dict[str, float | None]` (returns a new dict; sets `"Fuel Rate"` to `Coke Rate + Nut Coke Rate + CDI Rate` when `"Fuel Rate"` is `None` and all three are present)
  - `improvement_pct(cur_v: float, cply_v: float, higher_is_better: bool) -> int`

This is a straight generalization of the validated logic in
`backend/_update_bn_board_report.py` (keep that file as a reference while
porting — do not delete it until Task 5 passes) off the hardcoded
2026-27/Q2-H1 months, plus the per-plant extension `ITEMS_FOR_PLANT` for
`best_ever_bullets` (previously SAIL-only).

- [ ] **Step 1: Write the failing pure-logic tests** (no DB) in `backend/tests/test_board_note_common.py`:

```python
import board_note_common as bnc


def test_quarter_months_q2():
    assert bnc.quarter_months(2026, 2) == ["2026-07", "2026-08", "2026-09"]


def test_quarter_months_q4_wraps_into_next_calendar_year():
    assert bnc.quarter_months(2026, 4) == ["2027-01", "2027-02", "2027-03"]


def test_long_period_months_q1_is_none():
    assert bnc.long_period_months(2026, 1) is None


def test_long_period_months_q3_is_nine_months():
    assert bnc.long_period_months(2026, 3) == [f"2026-{m:02d}" for m in range(4, 13)]


def test_long_period_months_q4_is_full_fy():
    months = bnc.long_period_months(2026, 4)
    assert months[0] == "2026-04" and months[-1] == "2027-03" and len(months) == 12


def test_quarter_label_format():
    assert bnc.quarter_label(2026, 2) == "Q-2’26-27"


def test_long_period_label_variants():
    assert bnc.long_period_label(2026, 2) == "H-1’26-27"
    assert bnc.long_period_label(2026, 3) == "9M’26-27"
    assert bnc.long_period_label(2026, 4) == "FY’26-27"
    assert bnc.long_period_label(2026, 1) is None


def test_pick_best_new_record():
    assert bnc.pick_best({2023: 100.0, 2024: 110.0, 2025: 130.0}, 2025) == (130.0, 110.0, 2024)


def test_pick_best_not_a_record_returns_none():
    assert bnc.pick_best({2023: 100.0, 2024: 150.0, 2025: 130.0}, 2025) is None


def test_pick_best_only_data_point_in_history_returns_none():
    assert bnc.pick_best({2025: 130.0}, 2025) is None


def test_fuel_rate_fallback_fills_from_components():
    tgt = {"Coke Rate": 348.0, "Nut Coke Rate": 27.0, "CDI Rate": 150.0, "Fuel Rate": None}
    assert bnc.fuel_rate_fallback(tgt)["Fuel Rate"] == 525.0


def test_fuel_rate_fallback_leaves_existing_value_alone():
    tgt = {"Coke Rate": 348.0, "Nut Coke Rate": 27.0, "CDI Rate": 150.0, "Fuel Rate": 500.0}
    assert bnc.fuel_rate_fallback(tgt)["Fuel Rate"] == 500.0


def test_improvement_pct_lower_is_better():
    assert bnc.improvement_pct(cur_v=424, cply_v=418, higher_is_better=False) == -1


def test_improvement_pct_higher_is_better():
    assert bnc.improvement_pct(cur_v=2.04, cply_v=2.08, higher_is_better=True) == -2


def test_fmt_mt_returns_empty_for_none():
    assert bnc.fmt_mt(None) == ""


def test_fmt_t_returns_empty_for_none():
    assert bnc.fmt_t(None) == ""


def test_items_for_plant_skips_hot_metal_for_special_steel_plants():
    assert ("Hot Metal", "Hot Metal") not in bnc.ITEMS_FOR_PLANT["ASP"]
    assert ("Crude Steel", "Total Crude Steel") in bnc.ITEMS_FOR_PLANT["ASP"]


def test_items_for_plant_visl_is_saleable_and_finished_only():
    assert [label for label, _ in bnc.ITEMS_FOR_PLANT["VISL"]] == ["Saleable Steel", "Finished Steel"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_common.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'board_note_common'`

- [ ] **Step 3: Implement the pure-logic half of `backend/board_note_common.py`** (`quarter_months`/`long_period_months`/`fy_months`/`quarter_label`/`long_period_label`/`pick_best`/`fmt_*`/`imp_phrase`/`fuel_rate_fallback`/`improvement_pct`/`ITEMS_FOR_PLANT`) — port directly from the validated logic already in `_update_bn_board_report.py` (its `row_values`'s `ann = _period_sum(cur, "plan", FY_CUR, ...)` becomes `fy_months(fy_start)`; its hardcoded `Q2_CUR`/`H1_CUR` lists become `quarter_months`/`long_period_months` calls; `fmt_tbl`/`fmt_ann`/`fmt_pct`/`imp_phrase` port verbatim, already `None`-safe). `fmt_mt`/`fmt_t` additionally gain a `None` guard (`return ""` before the division/multiplication) that the one-off script's versions lacked — needed so a period with zero DB data renders a blank prose figure instead of crashing on `None / 1000.0`. `pick_best(totals, cur_fy)`: `others = {fy: v for fy, v in totals.items() if fy != cur_fy}`; return `None` if `cur_fy not in totals` or `others` is empty; `best_fy = max(others, key=others.get)`; return `(totals[cur_fy], others[best_fy], best_fy)` if `totals[cur_fy] > others[best_fy]` else `None`.
- [ ] **Step 4: Run to verify pass**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_common.py -v`
Expected: 15 passed

- [ ] **Step 5: Write the failing DB-backed tests**, appended to the same test file, seeding a throwaway SQLite `production_table`/`production_plan_table` exactly as `db.py:60-77` defines them:

```python
import sqlite3


def _seeded_cursor():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE production_table (report_month TEXT, plant_name TEXT,
        item_name TEXT, month_actual REAL, PRIMARY KEY (report_month, plant_name, item_name))""")
    conn.execute("""CREATE TABLE production_plan_table (report_month TEXT, plant_name TEXT,
        item_name TEXT, month_actual REAL, PRIMARY KEY (report_month, plant_name, item_name))""")
    rows_act = [
        ("2026-07", "BSP", "Hot Metal", 500.0), ("2026-08", "BSP", "Hot Metal", 520.0),
        ("2026-09", "BSP", "Hot Metal", 510.0),
        ("2025-07", "BSP", "Hot Metal", 480.0), ("2025-08", "BSP", "Hot Metal", 470.0),
        ("2025-09", "BSP", "Hot Metal", 460.0),
    ]
    rows_plan = [("2026-07", "BSP", "Hot Metal", 505.0), ("2026-08", "BSP", "Hot Metal", 505.0),
                 ("2026-09", "BSP", "Hot Metal", 505.0)]
    for m, p, i, v in rows_act:
        conn.execute("INSERT INTO production_table VALUES (?,?,?,?)", (m, p, i, v))
    for m, p, i, v in rows_plan:
        conn.execute("INSERT INTO production_plan_table VALUES (?,?,?,?)", (m, p, i, v))
    conn.commit()
    return conn.cursor()


def test_period_sum_adds_three_months():
    cur = _seeded_cursor()
    assert bnc.period_sum(cur, "act", ["2026-07", "2026-08", "2026-09"], "BSP", "Hot Metal") == 1530.0


def test_period_sum_returns_none_when_no_data_at_all():
    cur = _seeded_cursor()
    assert bnc.period_sum(cur, "act", ["2024-07", "2024-08", "2024-09"], "BSP", "Hot Metal") is None


def test_row_values_pct_and_growth():
    cur = _seeded_cursor()
    ann, abp, act, pct, cply, gr = bnc.row_values(
        cur, "BSP", "Hot Metal", ["2026-07", "2026-08", "2026-09"],
        ["2025-07", "2025-08", "2025-09"], fy_start=2026)
    assert (abp, act, cply) == (1515.0, 1530.0, 1410.0)
    assert pct == 101  # round(1530/1515*100)
    assert gr == 9     # round((1530-1410)/1410*100)


def test_best_ever_bullets_skips_items_plant_has_no_data_for():
    cur = _seeded_cursor()
    bullets = bnc.best_ever_bullets(cur, "BSP", lambda fy: [f"{fy}-07", f"{fy}-08", f"{fy}-09"], 2026, style="q2")
    assert any("Hot Metal" in b for b in bullets)
    assert not any("Crude Steel" in b for b in bullets)  # no Crude Steel rows seeded for BSP
```

- [ ] **Step 6: Run to verify failure**, then **implement the DB-backed half** of `board_note_common.py` (`period_sum`/`conv_sum`/`row_values`/`best_ever`/`best_ever_bullets`) by porting `_update_bn_board_report.py`'s `_period_sum`/`_conv_sum`/`row_values`/`_best_ever`/`sail_best_ever_bullets` verbatim, generalizing: `row_values` takes `fy_start` and calls `fy_months(fy_start)` instead of the module-level `FY_CUR` constant; `best_ever` takes any `plant` (not just `"SAIL"`) and loops `_fy_start_years` the same way; `best_ever_bullets` replaces the hardcoded `CORE_ITEMS` loop with `ITEMS_FOR_PLANT[plant]`, and only passes `add_conv=True` when `plant == "SAIL" and label == "Finished Steel"` (never for any other plant, per spec §3.1 — individual-plant Finished Steel never adds Conversion).
- [ ] **Step 7: Run full file to verify pass**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_common.py -v`
Expected: 19 passed

- [ ] **Step 8: Commit**

```bash
git add backend/board_note_common.py backend/tests/test_board_note_common.py
git commit -m "Add shared period/figures/best-ever/formatting library for Board Note"
```

---

### Task 5: `board_note_q2.py` adapter (Q-2 + H-1)

**Files:**
- Create: `backend/board_note_templates/board_note_q2_template.docx` (copy of `Report_format/BN_ Production Q-2 and H-1'25-26 R-2.docx`)
- Create: `backend/board_note_q2.py`
- Test: `backend/tests/test_board_note_q2.py` (requires the live MySQL dev DB — see Step 5)

**Interfaces:**
- Consumes: `board_note_common.*` (Task 4), `board_note_docx_utils.*` (Task 2), `board_note_manual_text.additional_highlight_lines`/`why_narrative_lines` (Task 3), `page_techno._get_plant_techno_plan_targets`, `page_techno.compute_sail_targets`, `techno_period.build_period_report`, `page_do_letter._fetch_conversion`.
- Produces: `generate(fy: str) -> bytes` — the only symbol Task 9's dispatcher imports.

This is the already-validated quarter shape: rebuild `_update_bn_board_report.py`'s logic as `generate(fy)`, replacing every hardcoded `2026-27`/`Q2_CUR`/`H1_CUR` with `board_note_common` calls parameterized by `fy_start = int(fy[:4])`, and replacing the per-plant "Highlights"/"why" paragraph blocks (which the one-off script left as the *old* document's literal 25-26 example text — fine for editing one real document in place, wrong for a from-scratch generator) with: auto-generated core-4 bullets (now via `board_note_common.best_ever_bullets(cur, plant, ...)` for **every** plant, not just SAIL) + `additional_highlight_lines` appended, via `fill_variable_bullets`; and the "why" block replaced entirely by `why_narrative_lines(manual, plant, "[Add production narrative for <plant> here]")` via `fill_variable_bullets`.

- [ ] **Step 1: Copy the template.** `cp "Report_format/BN_ Production Q-2 and H-1'25-26 R-2.docx" backend/board_note_templates/board_note_q2_template.docx` (create the `board_note_templates/` directory first).
- [ ] **Step 2: Re-derive and record the per-plant "Highlights"/"why" paragraph index ranges** for every one of the 9 units (SAIL + 8 plants), for both the Q-2 and H-1 sub-sections, using the same `document.element.body.iterchildren()` dump technique already used (and shown working) when this template was analyzed for the one-off script. Record each range as a constant block at the top of `board_note_q2.py`, e.g. `HIGHLIGHTS_BULLETS_START = {("SAIL", "q2"): 29, ...}` paired with a matching `..._END` or explicit slot-count — whatever shape `fill_variable_bullets` needs (a list of existing slot paragraphs to pass in). Comment each constant with the literal heading text it sits under, so a future reader can re-verify by eye.
- [ ] **Step 3: Implement `generate(fy: str) -> bytes` in `backend/board_note_q2.py`**, porting `_update_bn_board_report.py`'s `main()` body almost line-for-line: same table-filling order (table0 MoU, table1/2 SAIL, tables3-18 plants, table19 techno), same paragraph order (P9/P11 MoU narrative, P35/37/38 SAIL H-1, per-plant heading+summary pairs, techno section) — but every month list now comes from `board_note_common.quarter_months(fy_start, 2)` / `long_period_months(fy_start, 2)`; the techno target lookup now calls `board_note_common.fuel_rate_fallback(tgt)` per plant instead of the one-off script's inline fallback block, and the 4 SAIL improvement sentences now call `board_note_common.improvement_pct(cur_v, cply_v, higher_is_better)` instead of the one-off script's local `improvement_pct` closure; every best-ever call goes through `board_note_common.best_ever_bullets` for **all 9 units** (not just SAIL), and immediately after each unit's auto bullets are placed, call `fill_variable_bullets` again on that unit's recorded "why"-block slots with `why_narrative_lines(manual, plant, placeholder)`, and on its highlights slots with the auto bullets plus `additional_highlight_lines(manual, plant)` appended. Load `manual = board_note_manual_text.get_manual_text(fy, 2)` once at the top.
- [ ] **Step 4: Delete `backend/_update_bn_board_report.py`** now that its logic lives in the permanent modules (keep it out of the final diff — `git rm`).
- [ ] **Step 5: Verify against the live dev DB** (same validation already done manually for Q-2'26-27):

Run:
```bash
cd backend && venv/Scripts/python.exe -c "
import board_note_q2
open('_out.docx', 'wb').write(board_note_q2.generate('2026-27'))
"
venv/Scripts/python.exe -c "
import docx
d = docx.Document('_out.docx')
print(d.tables[1].rows[2].cells[3].text)   # SAIL Hot Metal Q-2 actual
print(d.paragraphs[9].text)                 # Finished-Steel-vs-MoU narrative
"
```
Expected: `d.tables[1].rows[2].cells[3].text == "5152"` and the paragraph 9 text contains `"4.360 MT"` and `"98%"` — the exact figures already hand-validated for Q-2'26-27 earlier in this project. Delete `_out.docx` afterward (it's a scratch artifact, not a test fixture).

- [ ] **Step 6: Commit**

```bash
git add backend/board_note_templates/board_note_q2_template.docx backend/board_note_q2.py
git rm backend/_update_bn_board_report.py
git commit -m "Add Q-2+H-1 Board Note adapter, retiring the one-off script it generalizes"
```

---

### Task 6: `board_note_q1.py` adapter (Q-1 only)

**Files:**
- Create: `backend/board_note_templates/board_note_q1_template.docx` (copy of `Report_format/BN_ Production Q-1_26-27.docx`)
- Create: `backend/board_note_q1.py`

**Interfaces:**
- Consumes: same as Task 5.
- Produces: `generate(fy: str) -> bytes`.

Q-1 has no Finished-Steel-vs-MoU opening (confirmed absent from the
reference doc) and no long-period pairing (`long_period_months(fy_start,
1)` is `None`) — only the quarter table/narrative/bullets per unit, plus
the techno section (confirmed present, 11 tables total vs. Q-2's 21).

- [ ] **Step 1: Copy the template** into `board_note_templates/board_note_q1_template.docx`.
- [ ] **Step 2: Dump the template's paragraph/table structure** (same `iterchildren()` technique) to build this adapter's own index maps: title/heading paragraphs, the per-unit quarter heading+summary+table triples (9 units), per-unit highlights/why slot ranges, and the techno section's table + 4 improvement-sentence paragraphs. Record as module-level constants, same shape as Task 5's.
- [ ] **Step 3: Implement `generate(fy: str) -> bytes`** reusing Task 5's adapter as the structural template: same per-unit loop (quarter-only, no H-1 pass), same techno section handling, same `fill_variable_bullets`-based highlights/why merge, same `manual = board_note_manual_text.get_manual_text(fy, 1)`. Skip the MoU table/narrative entirely (no table0 equivalent here).
- [ ] **Step 4: Verify against the live dev DB**, same shape as Task 5 Step 5, asserting SAIL's Q-1'26-27 Hot Metal actual table cell and the SAIL-level best-ever bullet text for whichever core item is a record for Q-1'26-27 (determine the expected value by running `board_note_common.best_ever(cur, "SAIL", "Hot Metal", lambda fy: board_note_common.quarter_months(fy, 1), 2026)` directly first and using its real output as the assertion, not a guessed number).
- [ ] **Step 5: Commit**

```bash
git add backend/board_note_templates/board_note_q1_template.docx backend/board_note_q1.py
git commit -m "Add Q-1 Board Note adapter (quarter-only shape)"
```

---

### Task 7: `board_note_q3.py` adapter (Q-3 + 9M)

**Files:**
- Create: `backend/board_note_templates/board_note_q3_template.docx` (copy of `Report_format/BN_ Production Q-3 and 9M'25-26.docx`)
- Create: `backend/board_note_q3.py`

**Interfaces:** same shape as Task 5/6; `generate(fy: str) -> bytes`.

Same skeleton as Q-2, long period is `long_period_months(fy_start, 3)` (9
months, Apr-Dec) instead of H-1; the MoU table has 8 columns (confirmed:
`Plant / MoU / Q-3 MoU / Act / % / Apr-Dec MoU / Act / %` — no separate
annual-ABP column distinct from Task 5's table0 shape, so re-check column
indices against this template directly rather than assuming Task 5's
offsets carry over).

- [ ] **Step 1: Copy the template** into `board_note_templates/board_note_q3_template.docx`.
- [ ] **Step 2: Dump the template's structure** and record this adapter's index maps (title/MoU section, per-unit Q-3/9M heading+summary+table triples, highlights/why slots, techno section), explicitly re-verifying the MoU table's column layout against this file (don't assume Task 5's table0 column offsets).
- [ ] **Step 3: Implement `generate(fy: str) -> bytes`**, same structure as Task 5/6 with `quarter=3`, `long_period_months(fy_start, 3)`, `long_period_label(fy_start, 3)` (`"9M'26-27"`), `manual = board_note_manual_text.get_manual_text(fy, 3)`.
- [ ] **Step 4: Verify against the live dev DB**, same shape as Task 5 Step 5, for `fy="2026-27"`.
- [ ] **Step 5: Commit**

```bash
git add backend/board_note_templates/board_note_q3_template.docx backend/board_note_q3.py
git commit -m "Add Q-3+9M Board Note adapter"
```

---

### Task 8: `board_note_q4.py` adapter (Q-4 + FY)

**Files:**
- Create: `backend/board_note_templates/board_note_q4_template.docx` (copy of `Report_format/BN_ Production Q-4 and FY'25-26.docx`)
- Create: `backend/board_note_q4.py`

**Interfaces:** same shape as Task 5/6/7; `generate(fy: str) -> bytes`.

Confirmed difference from Task 5/7: the MoU table here has **no** separate
annual-MoU column (7 columns: `Plant / Q-4 MoU / Act / % / Apr-Mar MoU /
Act / %`), and the opening narrative includes the extra sentence "SAIL
figures include finished steel produced through conversion agents/WLA/JVC"
— confirms (does not change) the Conversion-inclusion rule already in
`board_note_common.best_ever_bullets`/`row_values`.

- [ ] **Step 1: Copy the template** into `board_note_templates/board_note_q4_template.docx`.
- [ ] **Step 2: Dump the template's structure** and record this adapter's index maps, explicitly noting the 7-column MoU table layout (one fewer column than Task 5/7's table0) when recording cell offsets.
- [ ] **Step 3: Implement `generate(fy: str) -> bytes`**, same structure as the prior three adapters with `quarter=4`, `long_period_months(fy_start, 4)` (full 12 months), `long_period_label(fy_start, 4)` (`"FY'26-27"`), `manual = board_note_manual_text.get_manual_text(fy, 4)`.
- [ ] **Step 4: Verify against the live dev DB**, same shape as Task 5 Step 5, for `fy="2026-27"`.
- [ ] **Step 5: Commit**

```bash
git add backend/board_note_templates/board_note_q4_template.docx backend/board_note_q4.py
git commit -m "Add Q-4+FY Board Note adapter"
```

---

### Task 9: Dispatcher + API routes

**Files:**
- Create: `backend/page_board_note.py`
- Modify: `backend/main.py` (new section after the existing `do_letter` routes, `main.py:5247-5347`)
- Test: `backend/tests/test_page_board_note.py`

**Interfaces:**
- Consumes: `board_note_q1.generate`, `board_note_q2.generate`, `board_note_q3.generate`, `board_note_q4.generate` (Tasks 5-8), `board_note_manual_text.get_manual_text`/`save_manual_text` (Task 3).
- Produces: `page_board_note.generate_board_note_docx_bytes(fy: str, quarter: int) -> bytes` (raises `ValueError` for `quarter not in (1,2,3,4)` or `fy` not matching `\d{4}-\d{2}`); three new routes: `GET /api/board-note/docx`, `GET /api/board-note/manual-text`, `POST /api/board-note/manual-text`.

- [ ] **Step 1: Write the failing dispatcher tests** in `backend/tests/test_page_board_note.py`:

```python
import pytest

import page_board_note as pbn


def test_rejects_quarter_out_of_range():
    with pytest.raises(ValueError):
        pbn.generate_board_note_docx_bytes("2026-27", 5)


def test_rejects_malformed_fy():
    with pytest.raises(ValueError):
        pbn.generate_board_note_docx_bytes("2026", 2)


def test_dispatches_to_the_right_adapter(monkeypatch):
    calls = []
    monkeypatch.setattr(pbn.board_note_q3, "generate", lambda fy: calls.append(fy) or b"docx-bytes")
    assert pbn.generate_board_note_docx_bytes("2026-27", 3) == b"docx-bytes"
    assert calls == ["2026-27"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_page_board_note.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'page_board_note'`

- [ ] **Step 3: Implement `backend/page_board_note.py`**: import the four adapter modules; `QUARTER_ADAPTERS = {1: board_note_q1, 2: board_note_q2, 3: board_note_q3, 4: board_note_q4}`; `generate_board_note_docx_bytes` validates with `re.fullmatch(r"\d{4}-\d{2}", fy)` and `quarter in QUARTER_ADAPTERS`, raising `ValueError` with a message naming the bad input, then calls `QUARTER_ADAPTERS[quarter].generate(fy)`.
- [ ] **Step 4: Run to verify pass**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_page_board_note.py -v`
Expected: 3 passed

- [ ] **Step 5: Add the three routes to `backend/main.py`**, mirroring `do_letter`'s routes exactly (`main.py:5254-5346`):
  - `GET /api/board-note/docx?fy=...&quarter=...`: validate `fy`/`quarter` the same way (`re.fullmatch` for `fy`, `quarter` coerced to `int` with a 400 on failure or out-of-range), call `generate_board_note_docx_bytes`, catch any other exception into a 500 with its message (same `try/except` shape as `do_letter_docx`), return with `Content-Disposition: attachment; filename="BoardNote_{fy}_Q{quarter}.docx"`.
  - `GET /api/board-note/manual-text?fy=...&quarter=...`: validate inputs, return `board_note_manual_text.get_manual_text(fy, quarter)` reshaped to JSON-friendly `{plant: {field: text}}` (tuple dict keys aren't valid JSON — convert before returning, same reshape `get_do_letter_remarks` does for its own item/plant dict).
  - `POST /api/board-note/manual-text`: body `{"report_fy": str, "quarter": int, "entries": [{"plant": str, "field": str, "text": str}, ...]}`; validate `report_fy`/`quarter`, call `board_note_manual_text.save_manual_text`, return `{"saved": <count>}` — same shape as `save_do_letter_remarks`.
- [ ] **Step 6: Smoke-test against the running dev server** (per `CLAUDE.md`'s own verification convention):

Run (with `start-development.bat` already running):
```bash
curl -s "http://127.0.0.1:8082/api/board-note/manual-text?fy=2026-27&quarter=2"
curl -s -X POST http://127.0.0.1:8082/api/board-note/manual-text -H "Content-Type: application/json" -d "{\"report_fy\":\"2026-27\",\"quarter\":2,\"entries\":[{\"plant\":\"BSP\",\"field\":\"why_narrative\",\"text\":\"test\"}]}"
curl -s "http://127.0.0.1:8082/api/board-note/manual-text?fy=2026-27&quarter=2"
curl -s -o /tmp/bn.docx -w "%{http_code}\n" "http://127.0.0.1:8082/api/board-note/docx?fy=2026-27&quarter=2"
curl -s "http://127.0.0.1:8082/api/board-note/docx?fy=2026-27&quarter=9"
```
Expected: empty `{}`, then `{"saved": 1}`, then `{"BSP": {"why_narrative": "test"}}`, then `200`, then a 400 with a message naming quarter 9 as invalid.

- [ ] **Step 7: Commit**

```bash
git add backend/page_board_note.py backend/main.py backend/tests/test_page_board_note.py
git commit -m "Add Board Note dispatcher and /api/board-note routes"
```

---

### Task 10: Frontend tab

**Files:**
- Create: `frontend/src/components/reports/board-note/View.js`
- Modify: `frontend/src/components/reports/reportGroups.js` (`external` group's `tabs` array, alongside the `do-letter` entry at line 81)
- Modify: `frontend/src/components/reports/ReportTabs.js` (`VIEWS` map, alongside `'do-letter'` at line 33)

**Interfaces:**
- Consumes: `GET/POST /api/board-note/manual-text`, `GET /api/board-note/docx` (Task 9).
- Produces: the `/reports/external?tab=board-note` page.

Read `frontend/AGENTS.md` before writing this task. Mirror
`do-letter/View.js` closely (it already solves: fetch-on-param-change,
save-with-status-message, blob-download-as-file) with two differences: the
period selector is an FY text input (`placeholder="2026-27"`) + a Q1-Q4
radio/select instead of a month picker, and the editable area is one block
per plant (SAIL, BSP, DSP, RSP, BSL, ISP, ASP, SSP, VISL) with **two**
textareas each (Additional highlights / Why narrative) instead of
`do-letter`'s one-remark-per-item-per-plant grid.

- [ ] **Step 1: Read `frontend/AGENTS.md`** and skim `node_modules/next/dist/docs/` for anything relevant to a new dynamically-imported client page (check whether `do-letter/View.js`'s `'use client'` + `dynamic(() => import(...))` pattern, used elsewhere in `ReportTabs.js`, still applies as-is in this Next version — it should, since `do-letter` already uses it, but confirm before copying it).
- [ ] **Step 2: Create `frontend/src/components/reports/board-note/View.js`**, following `do-letter/View.js`'s structure: `fy` state (default: current FY as `"YYYY-YY"`, derived the same way `do-letter`'s `previousMonth()` derives its default) and `quarter` state (default 1-4 based on the current calendar month's FY quarter); `manualText` state shaped `{plant: {field: text}}`, loaded via `useEffect` on `[fy, quarter]` change from `GET /api/board-note/manual-text`; a "Generate DOCX" button using the same blob-download pattern as `handleDownload` in `do-letter/View.js:96-124`, pointed at `GET /api/board-note/docx`; a "Save narrative" button using the same save/status-message pattern as `handleSave` in `do-letter/View.js:70-94`, `POST`ing all 9 plants' 2 fields as one `entries` array; one collapsible section per plant with two `<textarea>`s, same visual style (`selectStyle`/`btnStyle` constants) as `do-letter/View.js:126-136`.
- [ ] **Step 3: Register the tab** — add `{ id: 'board-note', label: 'Quarterly Board Note', description: 'Quarterly Board Note (production performance) for any FY/quarter, with editable narrative.' }` to `reportGroups.js`'s `external` group `tabs` array, and `'board-note': dynamic(() => import('./board-note/View'), { loading }),` to `ReportTabs.js`'s `VIEWS` map.
- [ ] **Step 4: Manually verify in the browser** (per `CLAUDE.md`'s own convention — no automated frontend test harness exists in this repo for report tabs):
  1. With `start-development.bat` running, open `http://localhost:3000/reports/external?tab=board-note`.
  2. Confirm the tab renders with an FY input, quarter selector, and 9 plant blocks each with 2 textareas.
  3. Type text into BSP's "Why narrative" box, click Save, reload the page, confirm the text is still there.
  4. Click "Generate DOCX" for FY 2026-27, Q-2; confirm a file downloads and opens in Word/LibreOffice without corruption, and that BSP's "why" section shows the text just saved.
  5. Switch quarter to Q-1 and Q-4 for the same FY and regenerate; confirm both download without error.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/reports/board-note/View.js frontend/src/components/reports/reportGroups.js frontend/src/components/reports/ReportTabs.js
git commit -m "Add Quarterly Board Note tab under /reports/external"
```
