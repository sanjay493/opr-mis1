"""
Page 5 & 6 – Plant-Wise Production Performance.
Page 5: SAIL + BSP + DSP + RSP
Page 6: BSL + ISP + ASP + SSP + VISP
"""
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
        ("Oven Pushing (nos/day)", ("AGG_NOS", "Oven Pushing (nos/day)", _5P),  False, True),
        ("Sinter",              ("AGG",     "Total Sinter",         _5P),  False, False),
        ("Hot Metal",           ("AGG",     "Hot Metal",            _5PV), True,  False),
        # Ingot route is only used by DSP ("Bottom Pouring Ingot") and ASP
        # ("Ingot Steel") — the other plants cast everything via Concast.
        ("Ingot",               ("AGG",     {"DSP": "Bottom Pouring Ingot", "ASP": "Ingot Steel"},
                                             _5P + ["ASP"]),               False, False),
        # Concast is derived as Crude Steel(Tot) - Ingot rather than summed
        # per-plant: Total Crude Steel = Ingot + Concast, and Crude Steel(Tot)
        # is the authoritative, directly-tracked figure.
        ("Concast",             ("AGG_DIFF",
                                     ("AGG", "Total Crude Steel", _ALL),
                                     ("AGG", {"DSP": "Bottom Pouring Ingot", "ASP": "Ingot Steel"}, _5P + ["ASP"]),
                                 ),                                        False, False),
        ("Crude Steel(Tot)",    ("AGG",     "Total Crude Steel",    _ALL), True,  False),
        ("Saleable Steel",      ("AGG",     "Saleable Steel",       _ALL), True,  False),
        ("Finished Steel",      ("AGG",     "Finished Steel",       _ALL), True,  False),
        # Five main plants' own "Saleable Semis" item, plus ASP's semi-finished
        # steel (which ASP doesn't track directly — derived as Saleable - Finished).
        ("Semi-finished steel", ("AGG",     {
                                     "BSP": "Saleable Semis",
                                     "DSP": "Saleable Semis",
                                     "RSP": "Saleable Semis",
                                     "BSL": "Saleable Semis",
                                     "ISP": "Saleable Semis",
                                     "ASP": ("SUB", "Saleable Steel", "Finished Steel"),
                                 }, _5P + ["ASP"]),                        False, False),
        ("HR Coils rolling(Tot)", ("AGG",     ["HSM-2 Total HR Coil","HSM Total HR Coil"], _ALL), False, False),
        ("Pig Iron",            ("AGG",     "Pig Iron",             _5PV), False, False),
    ]),
    ("BSP", [
        ("Oven Pushing (nos/day)", "Oven Pushing (nos/day)",   False, True),
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
        ("Oven Pushing (nos/day)", "Oven Pushing (nos/day)",   False, True),
        ("SP-I",                "SP-1",                  False, False),
        ("SP-II",               "SP-2",                  False, False),
        ("Sinter (Tot)",        "Total Sinter",          True,  False),
        ("Hot Metal",           "Hot Metal",             True,  False),
        ("Ingot",               "Bottom Pouring Ingot",  False, False),
        ("Concast",             "SMS Total Caster",      False, False),
        ("Crude Steel(Tot)",    "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
        ("Finished Steel",      "Finished Steel",        False, False),
        ("Semi-finished steel", "Saleable Semis",        False, False),
        ("Pig Iron",            "Pig Iron",              False, False),
    ]),
    ("RSP", [
        ("Oven Pushing (nos/day)", "Oven Pushing (nos/day)",   False, True),
        ("SP-I",                "SP-1",                  False, False),
        ("SP-II",               "SP-2",                  False, False),
        ("SP-III",              "SP-3",                  False, False),
        ("Sinter (Tot)",        "Total Sinter",          True,  False),
        ("Hot Metal",           "Hot Metal",             True,  False),
        ("SMS-1 CCM(CC Slab)",       "SMS-1 CCM-1",           False, False),
        ("SMS-2 CCM-1&2(CC Slab)",   "SMS-2 CCM-1&2",         False, False),
        ("SMS-2 CCM-3(CC Slab)",     "SMS-2 CCM-3",           False, False),
        ("SMS-2 CCM-4(CC Slab)",     "SMS-2 CCM-4",           False, False),
        ("Concast (Tot)",       ["SMS-1 CCM-1", "SMS-2 CCM-1&2", "SMS-2 CCM-3", "SMS-2 CCM-4"], False, False),
        ("Crude Steel(Tot)",    "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
        ("Finished Steel",      "Finished Steel",        False, False),
        ("Semi-finished steel", None,                    False, False),
        ("HR Coils Rolling(Tot)", "HSM-2 Total HR Coil", False, False),
        ("Pig Iron",            "Pig Iron",              False, False),
    ]),
]

PAGE6_PLANTS = [
    ("BSL", [
        ("Oven Pushing (nos/day)", "Oven Pushing (nos/day)",   False, True),
        ("Sinter",              "Total Sinter",          False, False),
        ("Hot Metal",           "Hot Metal",             True,  False),
        ("SMS-1(CC slab)",      "SMS-1 CCM-1",           False, False),
        ("SMS-2 (CC Slab)",     "SMS-2 CCM-1&2",         False, False),
        ("Crude Steel (Tot)",   "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
        ("Finished Steel",      "Finished Steel",        False, False),
        ("Semi-finished steel", "Saleable Semis",        False, False),
        ("HSM rolling",         "HSM Total HR Coil",     False, False),
        ("Pig Iron",            "Pig Iron",              False, False),
    ]),
    ("ISP", [
        ("Oven Pushing (nos/day)", "Oven Pushing (nos/day)",   False, True),
        ("Sinter",              "Total Sinter",          False, False),
        ("Hot Metal",           "Hot Metal",             True,  False),
        ("Crude Steel (Total)", "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
        ("Finished Steel",      "Finished Steel",        False, False),
        ("Semi-finished steel", "Saleable Semis",        False, False),
        ("Pig Iron",            "Pig Iron",              False, False),
    ]),
    ("ASP", [
        ("Ingot steel",         "Ingot Steel",           False, False),
        ("Concast (total)",     "Total Caster",          False, False),
        ("Crude Steel(Tot)",    "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
        ("Finished Steel",      "Finished Steel",        False, False),
        # ASP has no separate "Saleable Semis" item — semi-finished steel is
        # the portion of Saleable Steel that isn't yet Finished Steel.
        ("Semi-finished steel", ("SUB", "Saleable Steel", "Finished Steel"), False, False),
    ]),
    ("SSP", [
        ("Crude Steel",         "Total Crude Steel",     True,  False),
        ("Saleable Steel",      "Saleable Steel",        True,  False),
    ]),
    ("VISL", [
        ("Saleable Steel",           "Saleable Steel",           True,  False),
        ("Finished Steel",           "Finished Steel",           False, False),
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
    """Sum across multiple item names for one plant/month.

    Uses _get_single (not the plain _one lookup) so that each item name
    still benefits from alias/derived-value fallback — needed e.g. when a
    per-plant item list mixes a plant's regular item names with one that
    has a _PLAN_ALIASES/_ITEM_ALT_NAMES entry (like BSP's "SMS-2"/"SMS-3").
    """
    total, found = 0.0, False
    for it in items:
        v = _get_single(cur, table, plant, it, month)
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


_FS_ALIAS = frozenset({"SSP", "VISL"})

# Plan table uses different (more granular) item names for some BSP SMS items.
# Maps (plant, actual_item_name) -> list of plan item names to sum.
_PLAN_ALIASES = {
    ("BSP", "SMS-2"): ["SMS-2 BLOOM", "SMS-2 SLAB"],
    # canonical casing per normalize_item_name (BILLET -> Billet)
    ("BSP", "SMS-3"): ["SMS-3 Billet105", "SMS-3 Billet150", "SMS-3 BLOOM(CV1&2)"],
}

# Some months were entered under a differently-cased/spelled item name.
# Maps (plant, item) -> alternate names to try (fallback, not summed — only
# used when the primary name has no data for that month).
_ITEM_ALT_NAMES = {
    ("DSP", "Bottom Pouring Ingot"): ["BOTTOM_POURING_INGOT"],
    ("ASP", "Total Caster"): ["Concast"],
}

# Some (plant, item) combos aren't tracked directly — derive them as
# (item_a - item_b) using items that ARE tracked. Used as a last-resort
# fallback (e.g. ASP's plan table has "Total Crude Steel" and "Concast"
# but no "Ingot Steel"; Total Crude Steel = Ingot + Concast, so
# Ingot = Total Crude Steel - Concast).
_ITEM_DERIVED_DIFF = {
    ("ASP", "Ingot Steel"): ("Total Crude Steel", "Concast"),
}


def _get_single(cur, table, plant, item, month):
    """Single plant, single item. SSP/VISL fall back to Saleable Steel for Finished Steel."""
    tbl = "production_table" if table == "act" else "production_plan_table"

    # Plan table may use different item names for certain plant/item combos
    if table != "act":
        alias_items = _PLAN_ALIASES.get((plant, item))
        if alias_items:
            return _sum_items(cur, table, plant, alias_items, month)

    cur.execute(
        f"SELECT month_actual FROM {tbl} WHERE plant_name=? AND item_name=? AND report_month=?",
        (plant, item, month),
    )
    r = cur.fetchone()
    if r and r[0] is not None:
        return r[0]
    for alt in _ITEM_ALT_NAMES.get((plant, item), []):
        cur.execute(
            f"SELECT month_actual FROM {tbl} WHERE plant_name=? AND item_name=? AND report_month=?",
            (plant, alt, month),
        )
        r = cur.fetchone()
        if r and r[0] is not None:
            return r[0]
    if item == "Finished Steel" and plant in _FS_ALIAS:
        cur.execute(
            f"SELECT month_actual FROM {tbl} WHERE plant_name=? AND item_name='Saleable Steel' AND report_month=?",
            (plant, month),
        )
        r = cur.fetchone()
        return r[0] if r and r[0] is not None else None
    diff = _ITEM_DERIVED_DIFF.get((plant, item))
    if diff:
        item_a, item_b = diff
        va = _get_single(cur, table, plant, item_a, month)
        vb = _get_single(cur, table, plant, item_b, month)
        return (va - vb) if (va is not None and vb is not None) else None
    return None


def _get_agg(cur, table, item, plants, month):
    """Sum across multiple plants.

    item may be:
      str            – same item name for every plant
      list[str]      – sum of these item names, for every plant
      dict           – {plant: item_or_list_or_sub}, a different spec per
                       plant (used where plants store the same production
                       metric under different item names/granularity).
                       A dict value may itself be a ("SUB", item_a, item_b)
                       tuple for a plant whose figure is derived as a
                       difference of two of its own items.
    """
    total, found = 0.0, False
    for p in plants:
        it = item.get(p) if isinstance(item, dict) else item
        if it is None:
            continue
        if isinstance(it, tuple) and it[0] == "SUB":
            _, item_a, item_b = it
            va = _get_single(cur, table, p, item_a, month)
            vb = _get_single(cur, table, p, item_b, month)
            v = (va - vb) if (va is not None and vb is not None) else None
        elif isinstance(it, list):
            v = _sum_items(cur, table, p, it, month)
        else:
            v = _get_single(cur, table, p, it, month)
        if v is not None:
            total += v
            found = True
    return total if found else None


def _get(cur, table, plant, db_spec, month):
    """Dispatch based on db_spec type."""
    if db_spec is None:
        return None
    if isinstance(db_spec, tuple):
        kind = db_spec[0]
        if kind == "SUB":
            # Single-plant derived difference: (item_a - item_b) for `plant`.
            _, item_a, item_b = db_spec
            va = _get_single(cur, table, plant, item_a, month)
            vb = _get_single(cur, table, plant, item_b, month)
            return (va - vb) if (va is not None and vb is not None) else None
        if kind == "AGG_DIFF":
            # Difference of two other db_specs (each may itself be an AGG).
            _, spec_a, spec_b = db_spec
            va = _get(cur, table, plant, spec_a, month)
            vb = _get(cur, table, plant, spec_b, month)
            return (va - vb) if (va is not None and vb is not None) else None
        _, item, plants = db_spec
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


def _ytd_nos(cur, table, plant, db_spec, months):
    """Weighted average of nos/day over the given months, day-weighted."""
    tw, td = 0.0, 0
    for m in months:
        v = _get(cur, table, plant, db_spec, m)
        if v is not None:
            days = _days(m)
            tw += v * days
            td += days
    return tw / td if td > 0 else None


_ONE_DP_LABELS  = {"Pig Iron", "Ingot", "Ingot steel"}
_ONE_DP_PLANTS  = frozenset({"ASP", "SSP", "VISL"})


def _is_one_dp(label: str, plant: str = "") -> bool:
    return label in _ONE_DP_LABELS or plant in _ONE_DP_PLANTS


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

    # Annual plan: sum of all 12 monthly plans, or day-weighted average for nos/day items
    if is_nos_day:
        ann_plan = _ytd_nos(cur, "plan", plant, db_item, all_fy)
    else:
        ann_plan = _ytd_sum(cur, "plan", plant, db_item, all_fy)

    # Monthly plan & actual
    m_plan = _get(cur, "plan", plant, db_item, report_month)
    m_actual = _get(cur, "act", plant, db_item, report_month)

    # CPLY (previous year same month actual)
    cply = _get(cur, "act", plant, db_item, prev_month)

    # YTD plan and actual
    if is_nos_day:
        ytd_plan   = _ytd_nos(cur, "plan", plant, db_item, ytd_months)
        ytd_actual = _ytd_nos(cur, "act",  plant, db_item, ytd_months)
        ytd_cply   = _ytd_nos(cur, "act",  plant, db_item, prev_ytd_months)
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
    conn = db.connect()
    cur = conn.cursor()
    rows = []
    try:
        for plant, items in plant_defs:
            for label, db_item, is_bold, is_nos_day in items:
                values = _compute_row(cur, plant, db_item, is_nos_day, report_month, _is_one_dp(label, plant))
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


# ---------------------------------------------------------------------------
# Page 6 trend charts — the space freed up by moving RSP to page 5 is filled
# with two line graphs (5 Plants, one line each) tracking:
#   1) Crude Steel / Hot Metal
#   2) Crude Steel / (Hot Metal - Pig Iron/0.85)
#
# X-axis: the last 3 complete FYs as a single ANNUAL (whole-year) ratio point
# each — sum of that FY's Crude Steel over sum of that FY's Hot Metal, not an
# average of 12 monthly ratios — followed by the current FY's individual
# months (Apr..report_month), one point per month. Mirrors the same
# "closed years get one summary figure, the live year gets month-by-month
# detail" convention page7_13.py's trend tables already use for historical
# vs. current-FY rows.
#
# Colors reuse page 3's bar-chart palette family (generate_summary_chart_html
# in page_techno.py: _C_FY="#FFC000", _C_TARGET="#70AD47", _C_MONTHLY="#4472C4")
# extended with the same Office theme's other two accents for the two extra
# plants, so all five stay visually consistent with page 3.
# ---------------------------------------------------------------------------

_TREND_PLANT_COLORS = {
    "BSP": "#4472C4",   # = page 3's _C_MONTHLY
    "DSP": "#ED7D31",
    "RSP": "#FFC000",   # = page 3's _C_FY
    "BSL": "#70AD47",   # = page 3's _C_TARGET
    "ISP": "#A5A5A5",
}

_MON_ABBR = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _fy_months_p6(fy_start_year: int) -> list:
    months = [f"{fy_start_year}-{m:02d}" for m in range(4, 13)]
    months += [f"{fy_start_year + 1}-{m:02d}" for m in range(1, 4)]
    return months


def _fetch_monthly_item(cur, plant: str, item: str, months: list) -> dict:
    ph = ",".join("?" for _ in months)
    cur.execute(
        f"SELECT report_month, month_actual FROM production_table "
        f"WHERE plant_name=? AND item_name=? AND report_month IN ({ph})",
        (plant, item, *months),
    )
    return {rm: v for rm, v in cur.fetchall() if v is not None}


def _sum_over(item_dict: dict, months: list):
    vals = [item_dict.get(m) for m in months]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def _ratios(cs_v, hm_v, pig_v):
    r1 = round(cs_v / hm_v, 4) if (cs_v is not None and hm_v) else None
    if cs_v is not None and hm_v is not None:
        denom = hm_v - (pig_v or 0) / 0.85
        r2 = round(cs_v / denom, 4) if denom else None
    else:
        r2 = None
    return r1, r2


def _compute_ratio_series(report_month: str):
    """Returns (x_labels, fy_point_count, ratio_cs_hm, ratio_cs_hm_adj).
    fy_point_count is how many of the leading x_labels are annual FY points
    (always 3) — the rest are current-FY month labels."""
    y, m_num = int(report_month[:4]), int(report_month[5:7])
    cur_fy     = y if m_num >= 4 else y - 1
    hist_fys   = [cur_fy - 3, cur_fy - 2, cur_fy - 1]
    cur_months = [mo for mo in _fy_months_p6(cur_fy) if mo <= report_month]

    all_months = sorted({mo for fy in hist_fys for mo in _fy_months_p6(fy)} | set(cur_months))

    conn = db.connect()
    cur  = conn.cursor()
    try:
        cs, hm, pig = {}, {}, {}
        for plant in _5P:
            cs[plant]  = _fetch_monthly_item(cur, plant, "Total Crude Steel", all_months)
            hm[plant]  = _fetch_monthly_item(cur, plant, "Hot Metal", all_months)
            pig[plant] = _fetch_monthly_item(cur, plant, "Pig Iron", all_months)
    finally:
        conn.close()

    x_labels = []
    ratio_cs_hm     = {p: [] for p in _5P}
    ratio_cs_hm_adj = {p: [] for p in _5P}

    for fy in hist_fys:
        x_labels.append(f"FY{fy % 100:02d}-{(fy + 1) % 100:02d}")
        fy_mo = _fy_months_p6(fy)
        for plant in _5P:
            cs_tot  = _sum_over(cs[plant], fy_mo)
            hm_tot  = _sum_over(hm[plant], fy_mo)
            pig_tot = _sum_over(pig[plant], fy_mo)
            r1, r2 = _ratios(cs_tot, hm_tot, pig_tot)
            ratio_cs_hm[plant].append(r1)
            ratio_cs_hm_adj[plant].append(r2)

    for mo in cur_months:
        x_labels.append(f"{_MON_ABBR[int(mo[5:7])]}'{mo[2:4]}")
        for plant in _5P:
            r1, r2 = _ratios(cs[plant].get(mo), hm[plant].get(mo), pig[plant].get(mo))
            ratio_cs_hm[plant].append(r1)
            ratio_cs_hm_adj[plant].append(r2)

    return x_labels, len(hist_fys), ratio_cs_hm, ratio_cs_hm_adj


def _line_chart_svg(x_labels: list, fy_point_count: int, series: dict,
                    title: str, vw: int = 980, vh: int = 270) -> str:
    """x_labels: one label per plotted point — the first `fy_point_count` are
    annual FY summaries, the rest are current-FY month labels (Apr'26, ...).
    A dashed separator marks the FY/month boundary. Title sits top-left,
    legend top-right, on the same row — clear of each other since the title
    is short and left-anchored rather than centered across the full width."""
    mt, mb, ml, mr = 34, 28, 40, 15
    cw, ch = vw - ml - mr, vh - mt - mb

    all_vals = [v for vals in series.values() for v in vals if v is not None]
    if not all_vals:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
            f'style="width:100%;height:auto;display:block;">'
            f'<rect width="{vw}" height="{vh}" fill="#f8fafc" rx="3"/>'
            f'<text x="{vw // 2}" y="{vh // 2}" text-anchor="middle" '
            f'font-size="8" font-family="Arial,sans-serif" fill="#94a3b8">'
            f'{title} – no data</text></svg>'
        )

    ylo_v, yhi_v = min(all_vals), max(all_vals)
    rng = yhi_v - ylo_v
    pad = rng * 0.2 if rng > 0 else max(abs(yhi_v) * 0.1, 0.02)
    ylo, yhi = ylo_v - pad, yhi_v + pad
    yspan = (yhi - ylo) or 1.0

    n = len(x_labels)

    def xs(i):
        return ml + (cw * i / max(n - 1, 1))

    def ys(v):
        return mt + ch * (1.0 - (v - ylo) / yspan)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']

    # Title (left) and legend (right) share the same header row, clear of
    # each other by construction — title is left-anchored/short, legend is
    # right-anchored, and the gap between them spans most of the width.
    lines.append(
        f'<text x="{ml}" y="14" text-anchor="start" '
        f'font-size="11" font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">'
        f'{title}</text>'
    )
    lx = vw - mr - 5 * 74
    for plant in series:
        color = _TREND_PLANT_COLORS.get(plant, "#888")
        lines.append(f'<rect x="{lx:.1f}" y="6" width="9" height="9" fill="{color}" rx="1.5"/>')
        lines.append(f'<text x="{lx + 12:.1f}" y="14" font-size="8.5" font-weight="bold" '
                     f'font-family="Arial,sans-serif" fill="#374151">{plant}</text>')
        lx += 74

    # Y gridlines + value labels (4 bands)
    for frac in (0.0, 0.33, 0.67, 1.0):
        yv = ylo + yspan * frac
        y  = ys(yv)
        lines.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{vw - mr}" y2="{y:.1f}" '
                     f'stroke="#e5e7eb" stroke-width="0.5"/>')
        lines.append(f'<text x="{ml - 5}" y="{y + 2.5:.1f}" text-anchor="end" '
                     f'font-size="7.5" font-family="Arial,sans-serif" fill="#64748b">{yv:.2f}</text>')

    # Separator between the 3 annual FY points and the current-FY monthly points
    if 0 < fy_point_count < n:
        sep_x = xs(fy_point_count - 0.5)
        lines.append(f'<line x1="{sep_x:.1f}" y1="{mt}" x2="{sep_x:.1f}" y2="{mt + ch}" '
                     f'stroke="#94a3b8" stroke-width="0.8" stroke-dasharray="2.5,2"/>')

    # X labels — one per point (annual FY labels bold, month labels plain)
    for i, label in enumerate(x_labels):
        x = xs(i)
        weight = 'font-weight="bold" ' if i < fy_point_count else ''
        lines.append(f'<text x="{x:.1f}" y="{mt + ch + 13:.1f}" text-anchor="middle" '
                     f'font-size="7.5" font-family="Arial,sans-serif" {weight}'
                     f'fill="#334155">{label}</text>')

    # One polyline per plant, with a marker dot and its value labelled at
    # each point (broken at gaps so a missing value doesn't silently join
    # two unrelated points)
    for plant, vals in series.items():
        color = _TREND_PLANT_COLORS.get(plant, "#888")
        seg, segments = [], []
        for i, v in enumerate(vals):
            if v is None:
                if seg:
                    segments.append(seg)
                    seg = []
                continue
            seg.append((xs(i), ys(v), v))
        if seg:
            segments.append(seg)
        for s in segments:
            path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y, _ in s)
            lines.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.4"/>')
            for x, y, v in s:
                lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{color}"/>')
                lines.append(f'<text x="{x:.1f}" y="{y - 6:.1f}" text-anchor="middle" '
                             f'font-size="6.5" font-weight="bold" font-family="Arial,sans-serif" '
                             f'fill="{color}">{v:.3f}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def generate_page6_trend_charts_html(report_month: str) -> str:
    """Two full-width line-graph SVGs, stacked one above the other, for the
    bottom of page 6. Titles stay short (left-aligned, matched by a
    right-aligned legend on the same row) — the "5 Plants / last 3 FY
    annual + current FY monthly" context they'd otherwise repeat is stated
    once in the shared caption below instead."""
    x_labels, fy_point_count, ratio1, ratio2 = _compute_ratio_series(report_month)
    svg1 = _line_chart_svg(x_labels, fy_point_count, ratio1, "CRUDE STEEL / HOT METAL")
    svg2 = _line_chart_svg(x_labels, fy_point_count, ratio2,
                           "CRUDE STEEL / (HOT METAL − PIG IRON/0.85)")
    caption = (
        '<div style="text-align:center;font-size:6.5px;color:#64748b;'
        'font-family:Arial,sans-serif;margin-top:2px;">'
        '5 Plants — last 3 FY annual ratios, then current FY month-by-month to the report month'
        '</div>'
    )
    return (
        '<div style="margin-top:6px;">'
        f'<div style="border:0.5px solid #e2e8f0;border-radius:3px;padding:3px;margin-bottom:6px;">{svg1}</div>'
        f'<div style="border:0.5px solid #e2e8f0;border-radius:3px;padding:3px;">{svg2}</div>'
        f'{caption}'
        "</div>"
    )
