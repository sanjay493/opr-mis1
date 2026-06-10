import calendar
import sqlite3
import db
from constants import FIVE_PLANTS as _5P

PAGE4_ITEMS = [
    {
        "display": "OVEN PUSHING (Nos./day)",
        "db_item": "Oven Pushing(nos/d)",
        "plants": ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"],
        "sail_set": _5P,
        "is_nos_day": True,
    },
    {
        "display": "SINTER",
        "db_item": "Total Sinter",
        "plants": ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"],
        "sail_set": _5P,
    },
    {
        "display": "HOT METAL",
        "db_item": "Hot Metal",
        "plants": ["BSP", "DSP", "RSP", "BSL", "ISP", "5 Plants", "VISL", "SAIL"],
        "five_plants": _5P,
        "sail_set": _5P + ["VISL"],
    },
    {
        "display": "CRUDE STEEL",
        "db_item": "Total Crude Steel",
        "plants": ["BSP", "DSP", "RSP", "BSL", "ISP", "5 Plants", "ASP", "SSP", "VISL", "SAIL"],
        "five_plants": _5P,
        "sail_set": _5P + ["ASP", "SSP", "VISL"],
    },
    {
        "display": "SALEABLE STEEL",
        "db_item": "Saleable Steel",
        "plants": ["BSP", "DSP", "RSP", "BSL", "ISP", "5 Plants", "ASP", "SSP", "VISL", "SAIL"],
        "five_plants": _5P,
        "sail_set": _5P + ["ASP", "SSP", "VISL"],
    },
    {
        "display": "PIG IRON",
        "db_item": "Pig Iron",
        "plants": ["BSP", "DSP", "RSP", "BSL", "ISP", "5 Plants", "VISL", "SAIL"],
        "five_plants": _5P,
        "sail_set": _5P + ["VISL"],
    },
    {
        "display": "FINISHED STEEL",
        "db_item": "Finished Steel",
        "plants": ["BSP", "DSP", "RSP", "BSL", "ISP", "5 Plants", "ASP", "SSP", "VISL", "SAIL"],
        "five_plants": _5P,
        "sail_set": _5P + ["ASP", "SSP", "VISL"],
    },
]

def _days_in_month(month_str: str) -> int:
    try:
        y, m = int(month_str[:4]), int(month_str[5:7])
        return calendar.monthrange(y, m)[1]
    except Exception:
        return 30


def _fy_months(month: str) -> list:
    """All 12 YYYY-MM strings of the financial year that contains `month`."""
    try:
        y, m = int(month[:4]), int(month[5:7])
    except Exception:
        return []
    fy_start = y if m >= 4 else y - 1
    result = []
    cur_y, cur_m = fy_start, 4
    for _ in range(12):
        result.append(f"{cur_y}-{cur_m:02d}")
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1
    return result


def _p4_query_one(cur, table, month, plant, db_item):
    """Single plant, single month."""
    tbl = "production_table" if table == "act" else "production_plan_table"
    cur.execute(
        f"SELECT month_actual FROM {tbl} WHERE report_month=? AND plant_name=? AND item_name=?",
        (month, plant, db_item),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _p4_query_sum(cur, table, month, plants, db_item):
    """Sum across a list of plants for one month."""
    if not plants:
        return None
    tbl = "production_table" if table == "act" else "production_plan_table"
    phs = ",".join("?" for _ in plants)
    cur.execute(
        f"SELECT SUM(month_actual) FROM {tbl} WHERE report_month=? AND plant_name IN ({phs}) AND item_name=?",
        [month] + list(plants) + [db_item],
    )
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def _p4_get(cur, table, month, plant, db_item, five_plants, sail_set):
    """Dispatch to single or aggregated query based on plant code."""
    if plant == "5 Plants":
        return _p4_query_sum(cur, table, month, five_plants, db_item)
    if plant == "SAIL":
        return _p4_query_sum(cur, table, month, sail_set, db_item)
    return _p4_query_one(cur, table, month, plant, db_item)


def _p4_ytd_sum(cur, table, months, plant, db_item, five_plants, sail_set):
    """Sum (for tonnage) across YTD months."""
    total = 0.0
    found = False
    for m in months:
        v = _p4_get(cur, table, m, plant, db_item, five_plants, sail_set)
        if v is not None:
            total += v
            found = True
    return total if found else None


def _p4_ytd_nos(cur, months, plant, db_item, five_plants, sail_set):
    """Weighted average (for nos/day) across YTD months."""
    tw = 0.0
    td = 0
    for m in months:
        v = _p4_get(cur, "act", m, plant, db_item, five_plants, sail_set)
        if v is not None:
            days = _days_in_month(m)
            tw += v * days
            td += days
    return tw / td if td > 0 else None


def _p4_ytd_nos_plan(cur, months, plant, db_item, five_plants, sail_set):
    """Weighted average plan (for nos/day) across YTD months."""
    tw = 0.0
    td = 0
    for m in months:
        v = _p4_get(cur, "plan", m, plant, db_item, five_plants, sail_set)
        if v is not None:
            days = _days_in_month(m)
            tw += v * days
            td += days
    return tw / td if td > 0 else None


def _p4_row_values(cur, month, plant, db_item, is_nos_day, five_plants, sail_set):
    """Compute the 13 display values for one page-4 row."""
    def fmt(v):
        return "" if v is None else str(round(v))

    def var(a, p):
        return "" if (a is None or p is None) else str(round(a - p))

    def pct(a, p):
        return "" if (a is None or p is None or p == 0) else str(round(a / p * 100))

    def gr(c, p):
        return "" if (c is None or p is None or p == 0) else str(round((c - p) / p * 100))

    ytd_m = db.get_ytd_months(month)
    prev = db.get_cply_month(month)
    ytd_prev = db.get_ytd_months(prev)

    plan_m   = _p4_get(cur, "plan", month, plant, db_item, five_plants, sail_set)
    act_m    = _p4_get(cur, "act",  month, plant, db_item, five_plants, sail_set)
    act_cply = _p4_get(cur, "act",  prev,  plant, db_item, five_plants, sail_set)

    if is_nos_day:
        ann          = _p4_ytd_nos_plan(cur, _fy_months(month), plant, db_item, five_plants, sail_set)
        plan_ytd     = _p4_ytd_nos_plan(cur, ytd_m,    plant, db_item, five_plants, sail_set)
        act_ytd      = _p4_ytd_nos(cur, ytd_m,    plant, db_item, five_plants, sail_set)
        act_ytd_cply = _p4_ytd_nos(cur, ytd_prev, plant, db_item, five_plants, sail_set)
    else:
        ann          = _p4_ytd_sum(cur, "plan", _fy_months(month), plant, db_item, five_plants, sail_set)
        plan_ytd     = _p4_ytd_sum(cur, "plan", ytd_m,    plant, db_item, five_plants, sail_set)
        act_ytd      = _p4_ytd_sum(cur, "act",  ytd_m,    plant, db_item, five_plants, sail_set)
        act_ytd_cply = _p4_ytd_sum(cur, "act", ytd_prev, plant, db_item, five_plants, sail_set)

    return [
        fmt(ann),                   # 0  Annual APP
        fmt(plan_m),                # 1  Monthly APP
        fmt(act_m),                 # 2  Monthly Actual
        var(act_m, plan_m),         # 3  Monthly Var
        pct(act_m, plan_m),         # 4  Monthly % Ful.
        fmt(act_cply),              # 5  CPLY Monthly Actual
        gr(act_m, act_cply),        # 6  % Growth CPLY
        fmt(plan_ytd),              # 7  YTD APP
        fmt(act_ytd),               # 8  YTD Actual
        var(act_ytd, plan_ytd),     # 9  YTD Var
        pct(act_ytd, plan_ytd),     # 10 YTD % Ful.
        fmt(act_ytd_cply),          # 11 YTD CPLY Actual
        gr(act_ytd, act_ytd_cply),  # 12 % Growth YTD CPLY
    ]


def generate_page4_rows(month: str) -> list:
    """Build all page-4 rows for `month`."""
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    rows = []
    try:
        for cfg in PAGE4_ITEMS:
            display  = cfg["display"]
            db_item  = cfg["db_item"]
            is_nos   = cfg.get("is_nos_day", False)
            five_p   = cfg.get("five_plants", [])
            sail_set = cfg.get("sail_set", [])

            for plant in cfg["plants"]:
                values = _p4_row_values(cur, month, plant, db_item, is_nos, five_p, sail_set)
                rows.append({
                    "label":        f"{display} {plant}",
                    "display_name": display,
                    "values":       values,
                })
    finally:
        conn.close()
    return rows
