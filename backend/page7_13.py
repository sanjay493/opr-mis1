"""
Month-wise production trend tables for MIS report pages 7-13.

Each page shows one item across plant groups:
  - Individual plants + computed aggregates (5 Plants, SAIL)
  - Rows: Plan (current FY) + Actual current FY (capped at report_month) + 10 historical FYs
  - Historical FY rows with ALL-blank monthly values are hidden
  - SAIL and "5 Plants" are computed as sums from constituent plants

Data source: production_table (actuals) and production_plan_table (plans) in mis_reports.db
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "mis_reports.db")

# Each page config lists display groups as (label, [plants_to_sum]).
# A single-plant group sums only that plant; an aggregate sums all listed plants.
from constants import ALL_PLANTS as _SAIL_8

_PIG_IRON_CFG = {
    "display": "PIG IRON",
    "unit": "'000 T",
    "db_item": "Pig Iron",
    "is_nos": False,
    "show_all_rows": True,
    "groups": [("SAIL", _SAIL_8)],
}

_FINISHED_STEEL_CFG = {
    "display": "FINISHED STEEL",
    "unit": "'000 T",
    "db_item": "Finished Steel",
    "is_nos": False,
    "show_all_rows": True,
    "groups": [("SAIL", _SAIL_8)],
}

TREND_PAGES = {
    7: {
        "display": "OVEN PUSHING",
        "unit": "Nos./day",
        "db_item": "Oven Pushing (nos/day)",
        "is_nos": True,
        "groups": [
            ("BSP",  ["BSP"]),
            ("DSP",  ["DSP"]),
            ("RSP",  ["RSP"]),
            ("BSL",  ["BSL"]),
            ("ISP",  ["ISP"]),
            ("SAIL", ["BSP", "DSP", "RSP", "BSL", "ISP"]),
        ],
    },
    8: {
        "display": "SINTER",
        "unit": "'000 T",
        "db_item": "Total Sinter",
        "is_nos": False,
        "groups": [
            ("BSP",  ["BSP"]),
            ("DSP",  ["DSP"]),
            ("RSP",  ["RSP"]),
            ("BSL",  ["BSL"]),
            ("ISP",  ["ISP"]),
            ("SAIL", ["BSP", "DSP", "RSP", "BSL", "ISP"]),
        ],
    },
    9: {
        "display": "HOT METAL",
        "unit": "'000 T",
        "db_item": "Hot Metal",
        "is_nos": False,
        # Order: 5 individual plants → 5 Plants aggregate → VISL → SAIL (all 8 plants)
        "groups": [
            ("BSP",      ["BSP"]),
            ("DSP",      ["DSP"]),
            ("RSP",      ["RSP"]),
            ("BSL",      ["BSL"]),
            ("ISP",      ["ISP"]),
            ("5 Plants", ["BSP", "DSP", "RSP", "BSL", "ISP"]),
            ("VISL",     ["VISL"]),
            ("SAIL",     _SAIL_8),
        ],
    },
    10: {
        "display": "CRUDE STEEL",
        "unit": "'000 T",
        "db_item": "Total Crude Steel",
        "is_nos": False,
        # Order: 5 integrated plants → 5 Plants aggregate → 3 remaining plants → SAIL
        "groups": [
            ("BSP",      ["BSP"]),
            ("DSP",      ["DSP"]),
            ("RSP",      ["RSP"]),
            ("BSL",      ["BSL"]),
            ("ISP",      ["ISP"]),
            ("5 Plants", ["BSP", "DSP", "RSP", "BSL", "ISP"]),
            ("ASP",      ["ASP"]),
            ("SSP",      ["SSP"]),
            ("VISL",     ["VISL"]),
            ("SAIL",     _SAIL_8),
        ],
    },
    11: {
        # Combined page: Pig Iron + Finished Steel (SAIL only, full 12 rows each)
        "display": "PIG IRON & FINISHED STEEL",
        "combined_items": [_PIG_IRON_CFG, _FINISHED_STEEL_CFG],
    },
    12: {
        "display": "SALEABLE STEEL",
        "unit": "'000 T",
        "db_item": "Saleable Steel",
        "is_nos": False,
        # Order: 5 integrated plants → 5 Plants aggregate → 3 remaining plants → SAIL
        "groups": [
            ("BSP",      ["BSP"]),
            ("DSP",      ["DSP"]),
            ("RSP",      ["RSP"]),
            ("BSL",      ["BSL"]),
            ("ISP",      ["ISP"]),
            ("5 Plants", ["BSP", "DSP", "RSP", "BSL", "ISP"]),
            ("ASP",      ["ASP"]),
            ("SSP",      ["SSP"]),
            ("VISL",     ["VISL"]),
            ("SAIL",     _SAIL_8),
        ],
    },
}


def _fy_months(fy_start_year: int):
    """12 YYYY-MM strings for the FY starting April of fy_start_year."""
    months = [f"{fy_start_year}-{m:02d}" for m in range(4, 13)]
    months += [f"{fy_start_year + 1}-{m:02d}" for m in range(1, 4)]
    return months


def _compute_row(monthly_vals, is_nos: bool):
    """
    monthly_vals: list of 12 values (Apr..Mar), each may be None.
    Returns 17 formatted strings:
      Apr May Jun Q1  Jul Aug Sep Q2  Oct Nov Dec Q3  Jan Feb Mar Q4  Total

    Oven Pushing (is_nos=True):  quarters/Total = arithmetic average of available months.
    Tonnage      (is_nos=False): quarters/Total = sum of available months.
    """
    def agg(vals):
        nz = [v for v in vals if v is not None]
        if not nz:
            return None
        return sum(nz) / len(nz) if is_nos else sum(nz)

    def fmt(v):
        return "" if v is None else str(round(v))

    m = list(monthly_vals)
    q1, q2 = agg(m[0:3]), agg(m[3:6])
    q3, q4 = agg(m[6:9]), agg(m[9:12])
    tot = agg(m)

    return [
        fmt(m[0]),  fmt(m[1]),  fmt(m[2]),  fmt(q1),
        fmt(m[3]),  fmt(m[4]),  fmt(m[5]),  fmt(q2),
        fmt(m[6]),  fmt(m[7]),  fmt(m[8]),  fmt(q3),
        fmt(m[9]),  fmt(m[10]), fmt(m[11]), fmt(q4),
        fmt(tot),
    ]


def _agg_months(data_by_plant: dict, plant_list: list, month_list: list,
                cap: str = None) -> list:
    """
    Sum plant values for each month.  cap: if given, months after cap return None.
    """
    result = []
    for mo in month_list:
        if cap and mo > cap:
            result.append(None)
            continue
        pv = [data_by_plant.get(p, {}).get(mo) for p in plant_list]
        result.append(sum(v or 0 for v in pv) if any(v is not None for v in pv) else None)
    return result


def _sail_or_sum(sail_direct: dict, data_by_plant: dict, plant_list: list,
                 month_list: list, cap: str = None) -> list:
    """
    For each month prefer SAIL-level DB data; fall back to summing individual plants.
    sail_direct: {report_month: value} fetched with plant_name='SAIL'.
    """
    result = []
    for mo in month_list:
        if cap and mo > cap:
            result.append(None)
            continue
        direct = sail_direct.get(mo)
        if direct is not None:
            result.append(direct)
        else:
            pv = [data_by_plant.get(p, {}).get(mo) for p in plant_list]
            result.append(sum(v or 0 for v in pv) if any(v is not None for v in pv) else None)
    return result


def _is_blank(values: list) -> bool:
    """True when all 12 monthly values are empty or zero (no meaningful production)."""
    monthly_idx = [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]
    return all(values[i] in ("", "0") for i in monthly_idx)


def _generate_rows_for_config(report_month: str, config: dict) -> list:
    """
    Core row-builder for a single item config dict.
    Called by both generate_trend_page_rows() and generate_combined_trend_items().
    """
    y, m_num = int(report_month[:4]), int(report_month[5:7])
    cur_fy = y if m_num >= 4 else y - 1
    fy_lbl_cur      = f"{cur_fy}-{(cur_fy + 1) % 100:02d}"
    fy_lbl_cur_plan = f"{cur_fy % 100:02d}-{(cur_fy + 1) % 100:02d}"
    hist_fys = list(range(cur_fy - 1, cur_fy - 11, -1))

    db_item  = config["db_item"]
    is_nos   = config["is_nos"]
    groups   = config["groups"]
    show_all = config.get("show_all_rows", False)

    all_plants = sorted({p for _, pl in groups for p in pl})
    phs = ",".join("?" for _ in all_plants)

    min_act  = f"{cur_fy - 10}-04"
    max_act  = f"{cur_fy + 1}-03"
    plan_min = f"{cur_fy}-04"
    plan_max = f"{cur_fy + 1}-03"

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    cur.execute(
        f"SELECT plant_name, report_month, month_actual FROM production_table "
        f"WHERE item_name=? AND plant_name IN ({phs}) "
        f"AND report_month>=? AND report_month<=?",
        [db_item] + all_plants + [min_act, max_act],
    )
    act_data = {p: {} for p in all_plants}
    for plant, rm, val in cur.fetchall():
        if plant in act_data:
            act_data[plant][rm] = val

    # For Finished Steel: patch SSP/VISL from Saleable Steel where FS is absent.
    _FS_ALIAS = frozenset({"SSP", "VISL"})
    if db_item == "Finished Steel":
        alias_in_query = [p for p in all_plants if p in _FS_ALIAS]
        if alias_in_query:
            aphs = ",".join("?" for _ in alias_in_query)
            cur.execute(
                f"SELECT plant_name, report_month, month_actual FROM production_table "
                f"WHERE item_name='Saleable Steel' AND plant_name IN ({aphs}) "
                f"AND report_month>=? AND report_month<=?",
                alias_in_query + [min_act, max_act],
            )
            for plant, rm, val in cur.fetchall():
                if plant in act_data and rm not in act_data[plant]:
                    act_data[plant][rm] = val

    cur.execute(
        f"SELECT plant_name, report_month, month_actual FROM production_plan_table "
        f"WHERE item_name=? AND plant_name IN ({phs}) "
        f"AND report_month>=? AND report_month<=?",
        [db_item] + all_plants + [plan_min, plan_max],
    )
    plan_data = {p: {} for p in all_plants}
    for plant, rm, val in cur.fetchall():
        if plant in plan_data:
            plan_data[plant][rm] = val

    if db_item == "Finished Steel":
        alias_in_query = [p for p in all_plants if p in _FS_ALIAS]
        if alias_in_query:
            aphs = ",".join("?" for _ in alias_in_query)
            cur.execute(
                f"SELECT plant_name, report_month, month_actual FROM production_plan_table "
                f"WHERE item_name='Saleable Steel' AND plant_name IN ({aphs}) "
                f"AND report_month>=? AND report_month<=?",
                alias_in_query + [plan_min, plan_max],
            )
            for plant, rm, val in cur.fetchall():
                if plant in plan_data and rm not in plan_data[plant]:
                    plan_data[plant][rm] = val

    sail_act_direct  = {}
    sail_plan_direct = {}
    if show_all:
        cur.execute(
            "SELECT report_month, month_actual FROM production_table "
            "WHERE item_name=? AND plant_name='SAIL' "
            "AND report_month>=? AND report_month<=?",
            [db_item, min_act, max_act],
        )
        sail_act_direct = {rm: val for rm, val in cur.fetchall() if val is not None}
        cur.execute(
            "SELECT report_month, month_actual FROM production_plan_table "
            "WHERE item_name=? AND plant_name='SAIL' "
            "AND report_month>=? AND report_month<=?",
            [db_item, plan_min, plan_max],
        )
        sail_plan_direct = {rm: val for rm, val in cur.fetchall() if val is not None}

    conn.close()

    fy_months_cur = _fy_months(cur_fy)
    rows = []

    for label, plant_list in groups:
        group_rows = []
        use_sail_direct = show_all and label == "SAIL"

        # Plan row
        if use_sail_direct:
            plan_vals = _sail_or_sum(sail_plan_direct, plan_data, plant_list, fy_months_cur)
        else:
            plan_vals = _agg_months(plan_data, plant_list, fy_months_cur)
        plan_values = _compute_row(plan_vals, is_nos)
        if show_all or not _is_blank(plan_values):
            group_rows.append({
                "plant": label, "year_label": f"Plan {fy_lbl_cur_plan}",
                "is_plan": True, "values": plan_values,
            })

        # Actual current FY
        if use_sail_direct:
            act_cur = _sail_or_sum(sail_act_direct, act_data, plant_list, fy_months_cur, cap=report_month)
        else:
            act_cur = _agg_months(act_data, plant_list, fy_months_cur, cap=report_month)
        act_cur_values = _compute_row(act_cur, is_nos)
        if show_all or not _is_blank(act_cur_values):
            group_rows.append({
                "plant": label, "year_label": f"{fy_lbl_cur}",   # f"Actual {fy_lbl_cur}"
                "is_plan": False, "values": act_cur_values,
            })

        # 10 historical FYs
        for fy_start in hist_fys:
            fy_mo  = _fy_months(fy_start)
            fy_lbl = f"{fy_start}-{(fy_start + 1) % 100:02d}"
            if use_sail_direct:
                act_vals = _sail_or_sum(sail_act_direct, act_data, plant_list, fy_mo)
            else:
                act_vals = _agg_months(act_data, plant_list, fy_mo)
            values = _compute_row(act_vals, is_nos)
            if not show_all and _is_blank(values):
                continue
            group_rows.append({
                "plant": label, "year_label": f"{fy_lbl}",
                "is_plan": False, "values": values,
            })

        if not group_rows:
            continue

        n = len(group_rows)
        for i, r in enumerate(group_rows):
            r["is_first_in_plant"] = (i == 0)
            r["plant_row_count"]   = n

        rows.extend(group_rows)

    return rows


def generate_trend_page_rows(report_month: str, page_num: int) -> list:
    """Rows for a single-item trend page (pages 7-10, 12)."""
    config = TREND_PAGES.get(page_num)
    if not config or config.get("combined_items"):
        return []
    return _generate_rows_for_config(report_month, config)


def generate_combined_trend_items(report_month: str, page_num: int) -> list:
    """
    For a combined page (page 11: Pig Iron + Finished Steel), returns a list of
    {item_display, unit, rows} dicts — one per sub-item — for the frontend and PDF.
    """
    config = TREND_PAGES.get(page_num, {})
    sub_configs = config.get("combined_items", [])
    result = []
    for cfg in sub_configs:
        result.append({
            "item_display": cfg["display"],
            "unit":         cfg["unit"],
            "rows":         _generate_rows_for_config(report_month, cfg),
        })
    return result
