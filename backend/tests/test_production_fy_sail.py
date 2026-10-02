"""SAIL rows on /api/production-fy (Month-wise Production report).

Hot Metal / Crude Steel / Saleable Steel's SAIL row must be the sum of the
8 plants for every month any plant reported — as on the PDF trend pages
(page7_13._agg_months) — not only the separately stored, often stale or
missing 'SAIL' snapshot rows. The stored value is kept only for months with
no plant data at all.
"""

import main


def _data(item, plant_vals, stored=None, kind="actual"):
    data = {p: {item: {"actual": {}, "plan": {}}} for p in plant_vals}
    for p, by_month in plant_vals.items():
        data[p][item][kind].update(by_month)
    if stored:
        data.setdefault("SAIL", {}).setdefault(item, {"actual": {}, "plan": {}})[kind].update(stored)
    return data


def test_sail_is_live_sum_of_reporting_plants():
    months = ["2026-07"]
    data = _data("Hot Metal", {"BSP": {"2026-07": 500.0}, "DSP": {"2026-07": 200.0}, "ISP": {"2026-07": 100.0}})
    main._fill_sail_sum_rows(data, months)
    assert data["SAIL"]["Hot Metal"]["actual"]["2026-07"] == 800.0


def test_stale_stored_sail_value_is_replaced_by_live_sum():
    months = ["2026-04"]
    data = _data("Total Crude Steel", {"BSP": {"2026-04": 1000.0}, "RSP": {"2026-04": 615.0}},
                 stored={"2026-04": 1594.0})
    main._fill_sail_sum_rows(data, months)
    assert data["SAIL"]["Total Crude Steel"]["actual"]["2026-04"] == 1615.0


def test_stored_sail_kept_when_no_plant_reported():
    months = ["2012-05"]
    data = _data("Saleable Steel", {}, stored={"2012-05": 1100.0})
    main._fill_sail_sum_rows(data, months)
    assert data["SAIL"]["Saleable Steel"]["actual"]["2012-05"] == 1100.0


def test_month_without_any_data_stays_blank():
    months = ["2026-12"]
    data = _data("Hot Metal", {"BSP": {"2026-07": 1.0}})
    main._fill_sail_sum_rows(data, months)
    assert data.get("SAIL", {}).get("Hot Metal", {}).get("actual", {}).get("2026-12") is None


def test_plan_rows_are_summed_too():
    months = ["2026-09"]
    data = _data("Saleable Steel", {"BSP": {"2026-09": 300.0}, "ASP": {"2026-09": 20.0}}, kind="plan")
    main._fill_sail_sum_rows(data, months)
    assert data["SAIL"]["Saleable Steel"]["plan"]["2026-09"] == 320.0


def test_finished_steel_is_not_touched():
    months = ["2026-07"]
    data = _data("Finished Steel", {"BSP": {"2026-07": 300.0}}, stored={"2026-07": 999.0})
    main._fill_sail_sum_rows(data, months)
    assert data["SAIL"]["Finished Steel"]["actual"]["2026-07"] == 999.0


def test_finished_steel_plan_uses_live_sum_when_all_8_plants_have_plan(monkeypatch):
    from constants import ALL_PLANTS
    months = ["2026-07", "2026-08"]
    plan = {p: {"2026-07": 10.0} for p in ALL_PLANTS}          # all 8 for July
    plan[ALL_PLANTS[0]]["2026-08"] = 50.0                      # only one plant for Aug
    data = _data("Finished Steel", plan, kind="plan")
    data.setdefault("SAIL", {})["Finished Steel"] = {"actual": {}, "plan": {"2026-07": 1.0, "2026-08": 77.0}}
    main._fill_sail_fs_plan(data, months)
    assert data["SAIL"]["Finished Steel"]["plan"]["2026-07"] == 10.0 * len(ALL_PLANTS)
    assert data["SAIL"]["Finished Steel"]["plan"]["2026-08"] == 77.0   # partial -> stored value


def test_no_sail_section_created_without_any_data():
    data = {"BSP": {"Oven Pushing (nos/day)": {"actual": {"2026-07": 780.0}, "plan": {}}}}
    main._fill_sail_sum_rows(data, ["2026-07"])
    assert "SAIL" not in data
