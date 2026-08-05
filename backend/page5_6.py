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
# Page 6 trend heatmap — the space freed up by moving RSP to page 5 is filled
# with a 5-plant x period heatmap of Crude Steel / (Hot Metal - Pig Iron/0.85
# - Hot Metal to ASP).
#
# X-axis: the last 3 complete FYs as a single ANNUAL (whole-year) ratio point
# each — sum of that FY's Crude Steel over sum of that FY's Hot Metal, not an
# average of 12 monthly ratios — followed by the current FY's individual
# months (Apr..report_month), one point per month. Mirrors the same
# "closed years get one summary figure, the live year gets month-by-month
# detail" convention page7_13.py's trend tables already use for historical
# vs. current-FY rows.
# ---------------------------------------------------------------------------

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


def _ratio3(cs_v, hm_v, pig_v, hm_asp_v):
    """Crude Steel / (Hot Metal − Pig Iron/0.85 − Hot Metal sent to ASP) —
    HM sent to ASP is hot metal a plant (in practice, only DSP reports it)
    transfers out rather than converting to crude steel itself, so it's
    excluded from the denominator alongside the Pig Iron/0.85 adjustment.
    For every other plant hm_asp_v is None/0 and this reduces to the plain
    Pig-Iron-adjusted ratio."""
    if cs_v is None or hm_v is None:
        return None
    denom = hm_v - (pig_v or 0) / 0.85 - (hm_asp_v or 0)
    return round(cs_v / denom, 4) if denom else None


def _compute_ratio_series(report_month: str):
    """Returns (x_labels, fy_point_count, ratio3).
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
        cs, hm, pig, hm_asp = {}, {}, {}, {}
        for plant in _5P:
            cs[plant]     = _fetch_monthly_item(cur, plant, "Total Crude Steel", all_months)
            hm[plant]     = _fetch_monthly_item(cur, plant, "Hot Metal", all_months)
            pig[plant]    = _fetch_monthly_item(cur, plant, "Pig Iron", all_months)
            hm_asp[plant] = _fetch_monthly_item(cur, plant, "Hot Metal to ASP", all_months)
    finally:
        conn.close()

    x_labels = []
    ratio3 = {p: [] for p in _5P}

    for fy in hist_fys:
        x_labels.append(f"FY{fy % 100:02d}-{(fy + 1) % 100:02d}")
        fy_mo = _fy_months_p6(fy)
        for plant in _5P:
            cs_tot     = _sum_over(cs[plant], fy_mo)
            hm_tot     = _sum_over(hm[plant], fy_mo)
            pig_tot    = _sum_over(pig[plant], fy_mo)
            hm_asp_tot = _sum_over(hm_asp[plant], fy_mo)
            ratio3[plant].append(_ratio3(cs_tot, hm_tot, pig_tot, hm_asp_tot))

    for mo in cur_months:
        x_labels.append(f"{_MON_ABBR[int(mo[5:7])]}'{mo[2:4]}")
        for plant in _5P:
            ratio3[plant].append(_ratio3(
                cs[plant].get(mo), hm[plant].get(mo), pig[plant].get(mo), hm_asp[plant].get(mo),
            ))

    return x_labels, len(hist_fys), ratio3


# Sequential blue ramp (light -> dark) — see dataviz skill's references/
# palette.md. Heatmap cells snap to the nearest step rather than
# interpolating freehand, per that palette's "documented steps only" rule.
#
# Capped at step 500 (`#256abf`) rather than the full 100->700 range: this
# report is print-only (rendered straight to PDF, never viewed on screen —
# see generate_page6_trend_charts_html), and the dropped steps 550-700 are
# the ramp's heaviest-ink tones (near-navy, close to full toner coverage per
# cell). The palette doc calls print out explicitly as a case to economize
# ink for; since every cell here already prints its numeric value, the
# lighter capped ramp keeps the "darker = higher" read intact (still one
# hue, still monotonic, still the same documented steps) while every cell —
# including the hottest ones — stays well short of solid dark fill.
_SEQ_BLUE_STEPS = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
    "#5598e7", "#3987e5", "#2a78d6", "#256abf",
]


def _contrast_text(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0f172a" if luminance > 0.6 else "#ffffff"


def _heatmap_cell_color(v, lo, hi):
    if v is None:
        return None
    span = (hi - lo) or 1.0
    frac = max(0.0, min(1.0, (v - lo) / span))
    idx = round(frac * (len(_SEQ_BLUE_STEPS) - 1))
    return _SEQ_BLUE_STEPS[idx]


def _ratio_heatmap_html(x_labels: list, fy_point_count: int, series: dict, title: str) -> str:
    """Plants (rows) x periods (columns) grid, one cell per ratio value,
    shaded on a single sequential blue ramp (light = lower ratio, dark =
    higher) with the value itself printed in the cell — a heatmap reads a
    5-plant x ~15-period grid far more legibly than 5 overlapping lines
    fighting for the same label space (see dataviz skill: magnitude over a
    grid -> heatmap, sequential one-hue color)."""
    all_vals = [v for vals in series.values() for v in vals if v is not None]
    if not all_vals:
        return (
            f'<div style="text-align:center;font-size:8pt;color:#94a3b8;'
            f'font-family:Arial,sans-serif;padding:10px;">{title} – no data</div>'
        )
    lo, hi = min(all_vals), max(all_vals)

    # Grid border lightened to a hairline gray (dataviz palette's gridline
    # role, #e1e0d9) — a solid #cbd5e1 border on every one of the ~90 cell
    # edges in this grid adds up; the lighter hairline still separates cells
    # without itself being a meaningful ink cost. Row cells get more
    # vertical padding (taller, easier-to-scan rows) than before; that space
    # is paid for below by trimming the block's own margins/caption rather
    # than growing the block's total footprint on the page.
    _GRID_BORDER = "#e1e0d9"

    head_cells = "".join(
        f'<th style="padding:2.5px 4px;border:1px solid {_GRID_BORDER};font-size:6.8px;'
        f'font-weight:{"bold" if i < fy_point_count else "600"};'
        f'{"border-left:1px solid #1e293b;" if i == fy_point_count else ""}">{lbl}</th>'
        for i, lbl in enumerate(x_labels)
    )

    body_rows = []
    for plant, vals in series.items():
        cells = []
        for i, v in enumerate(vals):
            color = _heatmap_cell_color(v, lo, hi)
            bg = color or "#f8fafc"
            fg = _contrast_text(color) if color else "#94a3b8"
            text = f"{v:.3f}" if v is not None else "—"
            sep = "border-left:1px solid #1e293b;" if i == fy_point_count else ""
            cells.append(
                f'<td style="padding:3.5px 4px;border:1px solid {_GRID_BORDER};{sep}'
                f'background:{bg};color:{fg};text-align:center;font-size:7px;'
                f'font-weight:600;">{text}</td>'
            )
        body_rows.append(
            f'<tr><td style="padding:3.5px 4px;border:1px solid {_GRID_BORDER};'
            f'background:#eef2f6;font-weight:bold;font-size:7.5px;">{plant}</td>'
            + "".join(cells) + '</tr>'
        )

    return (
        '<div style="margin-top:2px;">'
        f'<div style="font-size:9px;font-weight:bold;font-family:Arial,sans-serif;'
        f'color:#1e293b;margin-bottom:1px;">{title}</div>'
        '<table style="width:100%;border-collapse:collapse;font-family:Arial,sans-serif;">'
        f'<thead><tr><th style="padding:2.5px 4px;border:1px solid {_GRID_BORDER};font-size:6.8px;">PLANT</th>'
        f'{head_cells}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        '</table>'
        '<div style="text-align:center;font-size:6.2px;color:#64748b;'
        'font-family:Arial,sans-serif;margin-top:1px;">'
        'Crude Steel / (Hot Metal − Pig Iron/0.85 − Hot Metal to ASP) — 5 Plants, last 3 FY annual '
        'ratios then current FY month-by-month to the report month. Darker = higher ratio.'
        '</div>'
        "</div>"
    )


def generate_page6_trend_charts_html(report_month: str) -> str:
    """Single heatmap table for the bottom of page 6 (replaces the former
    pair of stacked line graphs — see dataviz skill guidance: a 5-plant x
    ~15-period grid of a single ratio is a magnitude-over-a-grid job, which
    reads far better as a heatmap than as overlapping lines)."""
    x_labels, fy_point_count, ratio3 = _compute_ratio_series(report_month)
    return _ratio_heatmap_html(
        x_labels, fy_point_count, ratio3,
        "CRUDE STEEL / (HOT METAL − PIG IRON/0.85 − HOT METAL TO ASP)",
    )
