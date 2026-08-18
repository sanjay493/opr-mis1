"""
"Monthly Summary of Power Data" — portrait page reproducing Report_format/
Power-OIS/*.xlsx's own full-FY grid (all 12 months x all plants), inserted
right after "Receipt, Consumption and Stocks of Coking Coal at Plants" (see
main.py's POWER_DATA_PAGE_ID). Sourced from the dedicated power_data_table
(plant_name, item_name, value per report_month), populated by api_power_omi.py
/ excel_extractors/excel_extractor_power_omi.py — see that extractor's
module docstring for the source workbook's own column layout, which this
page's grouping mirrors (PLAN / ACTUAL / grid & consumption / last-year).

Pure lookup/display: the whole FY's rows are read at once (like page_coal_
receipts_stock.py's stock table), so switching the report month within the
same FY shows the same 12-month grid: only the "Cum." row (the latest
available cumulative snapshot at-or-before the selected month) actually
depends on which month is selected.
"""
import db

_UNIT_TABLE = "power_data_table"

_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP", "SSP", "VISP", "CFP", "SAIL"]

_MON_ABBR = {
    4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep",
    10: "Oct", 11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb", 3: "Mar",
}

# (group, sub-key, display label) — display order matches the source
# workbook's own column order left-to-right.
_PLAN_ITEMS = [
    ("own", "Own(OLD)"), ("new_pbs", "New P&BS"), ("jv_pp2", "JV-PP-II"),
    ("drawal_jv_pp3", "Drawal JV PP3"), ("total", "Total"),
]
_ACTUAL_ITEMS = _PLAN_ITEMS
_GRID_ITEMS = [
    ("wheeling_px", "Wheeling"), ("purchase_px", "Purchase PX"),
    ("renewable_gdam", "Renewable+GDAM"), ("drawal_grid", "Drawal Grid"),
    ("export_grid", "Export Grid"), ("total_power_consump", "Total Power Consump"),
    ("decarbon_nos", "Decarbon Nos"), ("decarbon_hrs", "Decarbon Hrs"),
    ("specific_power_cons", "Sp. Power Cons"),
]
_LAST_YEAR_ITEMS = [
    ("own_cpp", "Own CPP"), ("jv_cpp", "JV CPP"), ("drawal_pp3", "Drawal PP3"),
    ("total_gen", "Total Gen"), ("total_power_consump", "Total Power Consump"),
]


def _month_label(report_month: str) -> str:
    y, m = report_month.split("-")
    return _MON_ABBR[int(m)]


def _title_month_label(report_month: str) -> str:
    y, m = report_month.split("-")
    return f"{_MON_ABBR[int(m)]}'{y[-2:]}"


def _row_dict(vals: dict, items: list, prefix: str = "") -> dict:
    """items carry the same bare sub-keys (own, new_pbs, ...) for both the
    plan and actual groups — the DB item_name distinguishes them with a
    group prefix (plan_own vs actual_own), added here rather than baked
    into _PLAN_ITEMS/_ACTUAL_ITEMS so the two groups can keep sharing one
    list. Grid items already store their full item_name as the key (no
    prefix needed); last-year items need "last_year_" prepended the same
    way plan/actual do."""
    return {key: vals.get(f"{prefix}{key}") for key, _ in items}


def generate_power_data(report_month: str) -> dict:
    fy_months = db.get_fy_months(report_month)
    if not fy_months:
        fy_months = [report_month]

    conn = db.connect()
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(fy_months))
        cur.execute(
            f"SELECT report_month, plant_name, item_name, value FROM {_UNIT_TABLE} "
            f"WHERE report_month IN ({ph})",
            fy_months,
        )
        all_rows = cur.fetchall()
    finally:
        conn.close()

    # month rows: {(plant, month): {item_name: value}}
    month_vals: dict = {}
    # cum candidates: {(plant, item_base): [(report_month, value), ...]}
    cum_candidates: dict = {}

    for rm, plant, item, value in all_rows:
        if item.endswith("_cum"):
            base = item[: -len("_cum")]
            cum_candidates.setdefault((plant, base), []).append((rm, value))
        else:
            month_vals.setdefault((plant, rm), {})[item] = value

    # Freshest cum snapshot at-or-before the selected report_month (falls
    # back to the latest available in the FY if none is at-or-before yet —
    # e.g. viewing April before April's own upload has happened).
    cum_vals: dict = {}
    for (plant, base), points in cum_candidates.items():
        eligible = [p for p in points if p[0] <= report_month]
        chosen = max(eligible, key=lambda p: p[0]) if eligible else max(points, key=lambda p: p[0])
        cum_vals.setdefault(plant, {})[base] = chosen[1]

    fy_start_year = fy_months[0].split("-")[0]
    fy_end_year = fy_months[-1].split("-")[0][-2:]
    fy_label = f"{fy_start_year}-{fy_end_year}"

    plants_out = []
    for plant in _PLANTS:
        rows = []
        for rm in fy_months:
            vals = month_vals.get((plant, rm), {})
            rows.append({
                "month": _month_label(rm),
                "plan": _row_dict(vals, _PLAN_ITEMS, "plan_"),
                "actual": _row_dict(vals, _ACTUAL_ITEMS, "actual_"),
                "grid": _row_dict(vals, _GRID_ITEMS),
                "last_year": _row_dict(vals, _LAST_YEAR_ITEMS, "last_year_"),
                "has_data": bool(vals),
            })
        cvals = cum_vals.get(plant, {})
        cum_row = {
            "plan": _row_dict(cvals, _PLAN_ITEMS, "plan_"),
            "actual": _row_dict(cvals, _ACTUAL_ITEMS, "actual_"),
            "grid": _row_dict(cvals, _GRID_ITEMS),
            "last_year": _row_dict(cvals, _LAST_YEAR_ITEMS, "last_year_"),
            "has_data": bool(cvals),
        }
        plants_out.append({"name": plant, "rows": rows, "cum": cum_row})

    return {
        "type": "power_data",
        "title": f"Plant Wise Power Data for {_title_month_label(report_month)} and FY {fy_label}",
        "plan_items": [label for _, label in _PLAN_ITEMS],
        "actual_items": [label for _, label in _ACTUAL_ITEMS],
        "grid_items": [label for _, label in _GRID_ITEMS],
        "last_year_items": [label for _, label in _LAST_YEAR_ITEMS],
        "plants": plants_out,
    }
