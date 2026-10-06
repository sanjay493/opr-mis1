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

