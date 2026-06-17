"""
Page 5 & 6 – Plant-Wise Production Performance.
Page 5: SAIL + BSP + DSP
Page 6: RSP + BSL + ISP + ASP + SSP + VISP
"""
import sqlite3
import db

# ---------------------------------------------------------------------------
# Plant / item structure
# Each item: (display_label, db_spec, is_bold, is_nos_day)
#
# db_spec may be:
#   str           – single DB item for the plant
#   list[str]     – sum of multiple DB items for the same plant
#   None          – not in DB; always blank
#   ("AGG", item, [plants]) – aggregate item across multiple plants
#   ("AGG_NOS", item, [plants]) – weighted-average aggregate for nos/day
# ---------------------------------------------------------------------------

from constants import FIVE_PLANTS as _5P, FIVE_PLANTS_VISL as _5PV, ALL_PLANTS as _ALL

PAGE5_PLANTS = [
    ("SAIL", [
        ("Oven Pushing(nos/d)", ("AGG_NOS", "Oven Pushing(nos/d)", _5P),  False, True),
        ("Sinter",              ("AGG",     "Total Sinter",         _5P),  False, False),
        ("Hot Metal",           ("AGG",     "Hot Metal",            _5PV), True,  False),
        ("Ingot",               ("AGG",     "BOTTOM_POURING_INGOT", _5P),  False, False),
        ("Concast",             ("AGG",     "Total Caster",         _5P),  False, False),
        ("Crude Steel(Tot)",    ("AGG",     "Total Crude Steel",    _ALL), True,  False),
        ("Saleable Steel",      ("AGG",     "Saleable Steel",       _ALL), True,  False),
        ("Finished Steel",      ("AGG",     "Finished Steel",       _ALL), True,  False),
        ("Semi-finished steel", ("AGG",     "Saleable Semis",       _ALL), False, False),
        ("HR Coils rolling(Tot)", ("AGG",     ["HSM-2 Total HR Coil","HSM Total HR Coil"], _ALL), False, False),
        ("Pig Iron",            ("AGG",     "Pig Iron",             _5PV), False, False),
    ]),
    ("BSP", [
        ("Oven Pushing(nos/d)", "Oven Pushing(nos/d)",   False, True),
        ("Sinter Plant-II",     "SP-2",                  False, False),
        ("Sinter plant-III",    "SP-3",                  False, False),
        ("Sinter (Tot)",        "Total Sinter",          True,  False),
        ("Hot Metal",           "Hot Metal",             True,  False),
        ("SMS-2/Concast",       "SMS-2",                 False, False),
        ("SMS-3/Concast",       "SMS-3",                 False, False),
        ("Crude Steel(Tot)",    "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
        ("Finished Steel",      "Finished Steel",        False, False),
        ("Semi-finished steel", "Saleable Semis",        False, False),
        ("Pig Iron",            "Pig Iron",              False, False),
    ]),
    ("DSP", [
        ("Oven Pushing(nos/d)", "Oven Pushing(nos/d)",   False, True),
        ("SP-I",                "SP-1",                  False, False),
        ("SP-II",               "SP-2",                  False, False),
        ("Sinter (Tot)",        "Total Sinter",          True,  False),
        ("Hot Metal",           "Hot Metal",             True,  False),
        ("Ingot",               "BOTTOM_POURING_INGOT",  False, False),
        ("Concast",             "Total Caster",          False, False),
        ("Crude Steel(Tot)",    "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
        ("Finished Steel",      "Finished Steel",        False, False),
        ("Semi-finished steel", "Saleable Semis",        False, False),
        ("Pig Iron",            "Pig Iron",              False, False),
    ]),
]

PAGE6_PLANTS = [
    ("RSP", [
        ("Oven Pushing(nos/d)", "Oven Pushing(nos/d)",   False, True),
        ("SP-I",                "SP-1",                  False, False),
        ("SP-II",               "SP-2",                  False, False),
        ("SP-III",              "SP-3",                  False, False),
        ("Sinter (Tot)",        "Total Sinter",          True,  False),
        ("Hot Metal",           "Hot Metal",             True,  False),
        ("CCM-1(CC Slab)",      "SMS-1 CCM-1",           False, False),
        ("CCM-2(CC Slab)",      "SMS-2 CCM-1&2",         False, False),
        ("CCM-3(CC Slab)",      "SMS-2 CCM-3",           False, False),
        ("CCM-4(CC Slab)",      "SMS-2 CCM-4",           False, False),
        ("Concast (Tot)",       ["SMS-1 CCM-1", "SMS-2 CCM-1&2", "SMS-2 CCM-3", "SMS-2 CCM-4"], False, False),
        ("Crude Steel(Tot)",    "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
        ("Finished Steel",      "Finished Steel",        False, False),
        ("Semi-finished steel", None,                    False, False),
        ("HR Coils Rolling(Tot)", "HSM-2 Total HR Coil", False, False),
        ("Pig Iron",            "Pig Iron",              False, False),
    ]),
    ("BSL", [
        ("Oven Pushing(nos/d)", "Oven Pushing(nos/d)",   False, True),
        ("Sinter",              "Total Sinter",          False, False),
        ("Hot Metal",           "Hot Metal",             True,  False),
        ("SMS-1(CC slab)",      "SMS-1 CCM-1",           False, False),
        ("SMS-2",               "SMS-2 CCM-1&2",         False, False),
        ("Crude Steel (Tot)",   "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
        ("Finished Steel",      "Finished Steel",        False, False),
        ("Semi-finished steel", "Saleable Semis",        False, False),
        ("HSM rolling",         "HSM Total HR Coil",     False, False),
        ("Pig Iron",            "Pig Iron",              False, False),
    ]),
    ("ISP", [
        ("Oven Pushing(nos/d)", "Oven Pushing(nos/d)",   False, True),
        ("Sinter",              "Total Sinter",          False, False),
        ("Hot Metal",           "Hot Metal",             True,  False),
        ("Crude Steel (Total)", "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
        ("Finished Steel",      "Finished Steel",        False, False),
        ("Semi-finished steel", "Saleable Semis",        False, False),
        ("Pig Iron",            "Pig Iron",              False, False),
    ]),
    ("ASP", [
        ("Ingot steel",         None,                    False, False),
        ("Concast (total)",     None,                    False, False),
        ("Crude Steel(Tot)",    "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
    ]),
    ("SSP", [
        ("Crude Steel",         "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
    ]),
    ("VISL", [
        ("Saleable Steel",      "Saleable Steel",        True,  False),
    ]),
]

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _one(cur, table, plant, item, month):
    tbl = "production_table" if table == "act" else "production_plan_table"
    cur.execute(
        f"SELECT month_actual FROM {tbl} WHERE plant_name=? AND item_name=? AND report_month=?",
        (plant, item, month),
    )
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None


def _sum_items(cur, table, plant, items, month):
    """Sum across multiple item names for one plant/month."""
    total, found = 0.0, False
    for it in items:
        v = _one(cur, table, plant, it, month)
        if v is not None:
            total += v
            found = True
    return total if found else None


import calendar as _cal
import math as _math

def _days(month_str):
    try:
        y, m = int(month_str[:4]), int(month_str[5:7])
        return _cal.monthrange(y, m)[1]
    except Exception:
        return 30


def _get_single(cur, table, plant, item, month):
    """Single plant, single item."""
    tbl = "production_table" if table == "act" else "production_plan_table"
    cur.execute(
        f"SELECT month_actual FROM {tbl} WHERE plant_name=? AND item_name=? AND report_month=?",
        (plant, item, month),
    )
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None


def _get_agg(cur, table, item, plants, month):
    """Sum across multiple plants. item may be a string or list of strings."""
    total, found = 0.0, False
    for p in plants:
        if isinstance(item, list):
            v = _sum_items(cur, table, p, item, month)
        else:
            v = _get_single(cur, table, p, item, month)
        if v is not None:
            total += v
            found = True
    return total if found else None


def _get(cur, table, plant, db_spec, month):
    """Dispatch based on db_spec type."""
    if db_spec is None:
        return None
    if isinstance(db_spec, tuple):
        kind, item, plants = db_spec
        return _get_agg(cur, table, item, plants, month)
    if isinstance(db_spec, list):
        return _sum_items(cur, table, plant, db_spec, month)
    return _get_single(cur, table, plant, db_spec, month)


def _ytd_sum(cur, table, plant, db_spec, months):
    total, found = 0.0, False
    for m in months:
        v = _get(cur, table, plant, db_spec, m)
        if v is not None:
            total += v
            found = True
    return total if found else None


def _ytd_nos(cur, plant, db_spec, months):
    """Weighted average of nos/day over YTD months."""
    tw, td = 0.0, 0
    for m in months:
        v = _get(cur, "act", plant, db_spec, m)
        if v is not None:
            days = _days(m)
            tw += v * days
            td += days
    return tw / td if td > 0 else None


_ONE_DP_LABELS = {"Pig Iron", "Ingot", "Ingot steel"}


def _is_one_dp(label: str) -> bool:
    return label in _ONE_DP_LABELS


def _fmt(v, one_dp: bool = False):
    if v is None:
        return ""
    try:
        f = float(v)
        if one_dp:
            one_dec = int(_math.floor(f * 10 + 0.5)) / 10
            return f"{one_dec:.1f}"
        return str(int(_math.floor(f + 0.5)))
    except Exception:
        return ""


def _pct(a, p):
    if a is None or p is None or p == 0:
        return ""
    try:
        return str(int(_math.floor(float(a) / float(p) * 100 + 0.5)))
    except Exception:
        return ""


def _growth(curr, prev):
    if curr is None or prev is None or prev == 0:
        return ""
    try:
        return str(int(_math.floor((float(curr) - float(prev)) / abs(float(prev)) * 100 + 0.5)))
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Row computation
# ---------------------------------------------------------------------------

def _compute_row(cur, plant, db_item, is_nos_day, report_month, one_dp: bool = False):
    """
    Returns 11 values:
    [annual_plan, m_plan, m_actual, m_pct_ful,
     cply_act, pct_growth,
     ytd_plan, ytd_actual, ytd_pct_ful, ytd_cply, ytd_growth]
    """
    ytd_months = db.get_ytd_months(report_month)
    all_fy = db.get_fy_months(report_month)
    prev_month = db.get_cply_month(report_month)
    prev_ytd_months = db.get_ytd_months(prev_month)

    # Annual plan: sum or weighted-avg of all 12 monthly plans
    if is_nos_day:
        ann_plan = None  # not meaningful to show annual avg here; leave blank
    else:
        ann_plan = _ytd_sum(cur, "plan", plant, db_item, all_fy)

    # Monthly plan & actual
    m_plan = _get(cur, "plan", plant, db_item, report_month)
    if is_nos_day:
        m_actual = _get(cur, "act", plant, db_item, report_month)
    else:
        m_actual = _get(cur, "act", plant, db_item, report_month)

    # CPLY (previous year same month actual)
    cply = _get(cur, "act", plant, db_item, prev_month)

    # YTD plan and actual
    if is_nos_day:
        ytd_plan   = _ytd_nos(cur, plant, db_item, ytd_months)
        ytd_actual = _ytd_nos(cur, plant, db_item, ytd_months)
        ytd_cply   = _ytd_nos(cur, plant, db_item, prev_ytd_months)
    else:
        ytd_plan   = _ytd_sum(cur, "plan", plant, db_item, ytd_months)
        ytd_actual = _ytd_sum(cur, "act",  plant, db_item, ytd_months)
        ytd_cply   = _ytd_sum(cur, "act",  plant, db_item, prev_ytd_months)

    return [
        _fmt(ann_plan, one_dp),
        _fmt(m_plan, one_dp),
        _fmt(m_actual, one_dp),
        _pct(m_actual, m_plan),
        _fmt(cply, one_dp),
        _growth(m_actual, cply),
        _fmt(ytd_plan, one_dp),
        _fmt(ytd_actual, one_dp),
        _pct(ytd_actual, ytd_plan),
        _fmt(ytd_cply, one_dp),
        _growth(ytd_actual, ytd_cply),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _build_rows(plant_defs, report_month):
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    rows = []
    try:
        for plant, items in plant_defs:
            for label, db_item, is_bold, is_nos_day in items:
                values = _compute_row(cur, plant, db_item, is_nos_day, report_month, _is_one_dp(label))
                rows.append({
                    "plant": plant,
                    "label": label,
                    "bold": is_bold,
                    "values": values,
                })
    finally:
        conn.close()
    return rows


def generate_page5_rows(report_month: str) -> list:
    return _build_rows(PAGE5_PLANTS, report_month)


def generate_page6_rows(report_month: str) -> list:
    return _build_rows(PAGE6_PLANTS, report_month)
