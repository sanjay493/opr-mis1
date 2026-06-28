import calendar
import sqlite3
import db
from constants import FIVE_PLANTS as _5P

PAGE4_ITEMS = [
    {
        "display": "OVEN PUSHING (Nos./day)",
        "db_item": "Oven Pushing (nos/day)",
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
    """All 12 YY-MM strings of the financial year that contains `month`."""
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


_FS_ALIAS = frozenset({"SSP", "VISL"})


def _p4_query_one(cur, table, month, plant, db_item):
    """Single plant, single month. SSP/VISL fall back to Saleable Steel for Finished Steel."""
    tbl = "production_table" if table == "act" else "production_plan_table"
    cur.execute(
        f"SELECT month_actual FROM {tbl} WHERE report_month=? AND plant_name=? AND item_name=?",
        (month, plant, db_item),
    )
    row = cur.fetchone()
    if row and row[0] is not None:
        return row[0]
    if db_item == "Finished Steel" and plant in _FS_ALIAS:
        cur.execute(
            f"SELECT month_actual FROM {tbl} WHERE report_month=? AND plant_name=? AND item_name='Saleable Steel'",
            (month, plant),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None
    return None


def _p4_query_sum(cur, table, month, plants, db_item):
    """Sum across a list of plants for one month."""
    if not plants:
        return None
    if db_item == "Finished Steel":
        # Per-plant loop so SSP/VISL can apply their Saleable Steel fallback.
        total, found = 0.0, False
        for p in plants:
            v = _p4_query_one(cur, table, month, p, db_item)
            if v is not None:
                total += v
                found = True
        return total if found else None
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


_EXTRA_PLANTS = {"ASP", "SSP", "VISL"}


def _p4_conv_actuals(cur, month: str):
    """Fetch Conversion (SAIL) actuals: current month, CPLY month, YTD, YTD CPLY."""
    prev = db.get_cply_month(month)
    ytd_m = db.get_ytd_months(month)
    ytd_prev = db.get_ytd_months(prev)

    def fetch(m):
        cur.execute(
            "SELECT month_actual FROM production_table "
            "WHERE report_month=? AND plant_name='SAIL' AND item_name='Conversion'",
            (m,)
        )
        r = cur.fetchone()
        return r[0] if r and r[0] is not None else None

    def ytd_sum(months):
        vals = [v for m in months if (v := fetch(m)) is not None]
        return sum(vals) if vals else None

    return fetch(month), fetch(prev), ytd_sum(ytd_m), ytd_sum(ytd_prev)


def _fmt3(v):
    if v is None:
        return ""
    r = round(v, 3)
    return str(int(r)) if r == int(r) else str(r)


def _gr_vals(c, p):
    return "" if (c is None or p is None or p == 0) else str(round((c - p) / p * 100))


def _safe_add(s, v):
    if v is None:
        return s
    try:
        return _fmt3(float(s) + v) if s != "" else _fmt3(v)
    except (ValueError, TypeError):
        return s


def _safe_var(a_s, p_s):
    try:
        return str(round(float(a_s) - float(p_s)))
    except (ValueError, TypeError):
        return ""


def _safe_pct(a_s, p_s):
    try:
        a, p = float(a_s), float(p_s)
        return str(round(a / p * 100)) if p != 0 else ""
    except (ValueError, TypeError):
        return ""


def _safe_gr(c_s, p_s):
    try:
        c, p = float(c_s), float(p_s)
        return str(round((c - p) / p * 100)) if p != 0 else ""
    except (ValueError, TypeError):
        return ""


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

            # First pass: build group rows, apply per-plant hide rules
            group = []          # list of (plant, row_dict)
            visible_extra = False

            for plant in cfg["plants"]:
                values = _p4_row_values(cur, month, plant, db_item, is_nos, five_p, sail_set)
                # Hide VISL in HOT METAL when all key actuals are nil
                if display == "HOT METAL" and plant == "VISL":
                    if all(values[i] == "" for i in [2, 5, 8, 11]):
                        continue
                if plant in _EXTRA_PLANTS:
                    visible_extra = True
                group.append((plant, {
                    "label":        f"{display} {plant}",
                    "display_name": display,
                    "values":       values,
                }))

            # Second pass: hide "5 Plants" when none of ASP/SSP/VISL are visible
            for plant, row in group:
                if plant == "5 Plants" and not visible_extra:
                    continue
                rows.append(row)

        # ── Conversion & SAIL incl. Conversion (appended after Finished Steel) ─
        fs_sail_set = _5P + ["ASP", "SSP", "VISL"]
        conv_m, conv_cply, conv_ytd, conv_ytd_cply = _p4_conv_actuals(cur, month)

        rows.append({
            "label": "CONVERSION SAIL",
            "display_name": "CONVERSION",
            "is_conversion": True,
            "values": [
                "", "",                                      # 0 Annual APP, 1 Monthly APP
                _fmt3(conv_m),                               # 2 Monthly Actual
                "", "",                                      # 3 Var, 4 %Ful
                _fmt3(conv_cply),                            # 5 CPLY Actual
                _gr_vals(conv_m, conv_cply),                 # 6 %Growth
                "",                                          # 7 YTD APP
                _fmt3(conv_ytd),                             # 8 YTD Actual
                "", "",                                      # 9 YTD Var, 10 YTD %Ful
                _fmt3(conv_ytd_cply),                        # 11 YTD CPLY
                _gr_vals(conv_ytd, conv_ytd_cply),           # 12 YTD %Growth
            ],
        })

        sail_fs_vals = _p4_row_values(cur, month, "SAIL", "Finished Steel", False, _5P, fs_sail_set)
        iv = list(sail_fs_vals)
        iv[2]  = _safe_add(iv[2],  conv_m)
        iv[5]  = _safe_add(iv[5],  conv_cply)
        iv[8]  = _safe_add(iv[8],  conv_ytd)
        iv[11] = _safe_add(iv[11], conv_ytd_cply)
        iv[3]  = _safe_var(iv[2],  iv[1])
        iv[4]  = _safe_pct(iv[2],  iv[1])
        iv[6]  = _safe_gr(iv[2],   iv[5])
        iv[9]  = _safe_var(iv[8],  iv[7])
        iv[10] = _safe_pct(iv[8],  iv[7])
        iv[12] = _safe_gr(iv[8],   iv[11])
        # Round all numeric values to zero decimal places
        iv = [str(round(float(v))) if v not in ("", None) else v for v in iv]

        rows.append({
            "label": "SAIL INCL. CONV. SAIL",
            "display_name": "SAIL INCL. CONV.",
            "is_sail_incl_conv": True,
            "values": iv,
        })

    finally:
        conn.close()
    return rows
