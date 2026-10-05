import pytest

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


def test_row_values_rejects_add_conv_for_non_sail_plant():
    cur = _seeded_cursor()
    with pytest.raises(ValueError):
        bnc.row_values(cur, "BSP", "Finished Steel", ["2026-07", "2026-08", "2026-09"],
                        ["2025-07", "2025-08", "2025-09"], fy_start=2026, add_conv=True)


def test_best_ever_rejects_add_conv_for_non_finished_steel_item():
    cur = _seeded_cursor()
    with pytest.raises(ValueError):
        bnc.best_ever(cur, "SAIL", "Hot Metal", lambda fy: [f"{fy}-07", f"{fy}-08", f"{fy}-09"], 2026, add_conv=True)


def _seeded_cursor_finished_steel_no_conversion():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE production_table (report_month TEXT, plant_name TEXT,
        item_name TEXT, month_actual REAL, PRIMARY KEY (report_month, plant_name, item_name))""")
    conn.execute("""CREATE TABLE production_plan_table (report_month TEXT, plant_name TEXT,
        item_name TEXT, month_actual REAL, PRIMARY KEY (report_month, plant_name, item_name))""")
    rows_act = [
        ("2026-07", "BSP", "Finished Steel", 400.0), ("2026-08", "BSP", "Finished Steel", 410.0),
        ("2026-09", "BSP", "Finished Steel", 420.0),
    ]
    for m, p, i, v in rows_act:
        conn.execute("INSERT INTO production_table VALUES (?,?,?,?)", (m, p, i, v))
    conn.commit()
    return conn.cursor()


def test_row_values_blanks_act_when_conversion_missing_for_sail_finished_steel():
    cur = _seeded_cursor_finished_steel_no_conversion()
    ann, abp, act, pct, cply, gr = bnc.row_values(
        cur, "SAIL", "Finished Steel", ["2026-07", "2026-08", "2026-09"],
        ["2025-07", "2025-08", "2025-09"], fy_start=2026, add_conv=True)
    assert act is None  # Finished Steel actuals exist but no Conversion rows -> blank, not understated


def test_improvement_pct_returns_none_for_missing_cur_v():
    assert bnc.improvement_pct(cur_v=None, cply_v=418, higher_is_better=False) is None


def test_improvement_pct_returns_none_for_zero_cply_v():
    assert bnc.improvement_pct(cur_v=424, cply_v=0, higher_is_better=False) is None


def test_imp_phrase_returns_empty_for_none():
    assert bnc.imp_phrase(None) == ""
