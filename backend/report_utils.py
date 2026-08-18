import db
from typing import List, Dict, Any, Optional


# Page-number ranges -> corner-badge color group, matching the report's
# section boundaries in frontend/src/app/report/page.js's PAGE_LABELS.
# Group order also fixes which validated categorical hue each gets (see
# frontend/src/app/globals.css's .dept-badge.grp-N) — never reorder without
# re-validating the palette (dataviz skill: fixed hue order is the CVD-safety
# mechanism).
_DEPT_BADGE_GROUPS = [
    (3, 6, 1),    # SAIL Performance Summary / Production Performance
    (7, 12, 2),   # Month-Wise Production Trend
    (13, 14, 3),  # Concast / Production by Process
    (15, 18, 4),  # Category Wise / Segment Wise
    (19, 24, 5),  # Special Steel
    (25, 26, 6),  # Opening Stock / IPT Status
    (27, 30, 7),  # Techno-Economic Parameters
    (31, 35, 8),  # Mill-Wise Techno-Economic Parameters
    (36, 40, 9),  # Capital Repair
]


# Sentinel/non-range page ids -> corner-badge group (a pure function of the
# page's own id, same as _DEPT_BADGE_GROUPS above, just for pages outside
# every plain int range). Each rides along with the real section it's
# physically inserted next to:
#   2.5, 3, 3.5, 3.6 — "MIS at a Glance" / "SAIL Performance Summary" /
#     "Key Parameters" / "Large BFs" all sit in the front-of-report summary
#     cluster before real page 4, group 1 (same as _DEPT_BADGE_GROUPS'
#     (3, 6, 1)) — not yet a section of its own.
#   1024 — the Special Steel trend/performance-analysis page, inserted
#     right after page 24, same group (5) it had while still numbered 24.
#   29.5 — "Iron Making (contd.)", right after page 29, same group (7) as
#     Techno-Economic Parameters.
#   35.4, 35.5, 35.6, 35.7 — EPI, then "Coking Coal Receipts & Stock", then
#     "Monthly Summary of Power Data", right after page 35, same group (8)
#     as Mill-Wise Techno-Economic Parameters.
# 3.1 ("Key Highlights & Variances") would join the 2.5/3/3.5/3.6 group too
# if it's ever wired back into the report — see KEY_HIGHLIGHTS_PAGE_ID in
# main.py (currently built, not inserted).
#   2.1, 2.2, 2.3 — "Indian Steel Sector Performance", right after the
#     Index, ahead of "MIS at a Glance" — same group (1) as its neighbors.
#   4.5 — "SAIL Mines Production & Despatch Performance", right after
#     fixed page 4 — same group (1) as its 3.5/3.6 neighbors.
_DEPT_BADGE_EXPLICIT_GROUP = {
    2.1: 1, 2.2: 1, 2.3: 1,
    2.5: 1, 3: 1, 3.5: 1, 3.6: 1, 4.5: 1,
    1024: 5,
    29.5: 7,
    35.4: 8, 35.5: 8, 35.6: 8, 35.7: 8,
}


def dept_badge_group(page_num) -> Optional[int]:
    """Which corner-badge color group a page belongs to, or None for pages
    1-2 (cover/index are front matter — no header/footer/badge) and any
    page id outside every known range/sentinel. Pure function of the
    page's own id — see assign_dept_badges() for the (position-dependent)
    left/right side."""
    if page_num in _DEPT_BADGE_EXPLICIT_GROUP:
        return _DEPT_BADGE_EXPLICIT_GROUP[page_num]
    if not isinstance(page_num, int) or page_num < 3:
        return None
    for lo, hi, group in _DEPT_BADGE_GROUPS:
        if lo <= page_num <= hi:
            return group
    return None


# Canonical physical print order of every page id the report can contain,
# cover (1) and index (2) excluded — those are front matter with no
# header/footer/badge, so alternation starts at the first entry here. This
# list is STATIC: unlike pages_config/_pages_list (which vary per request —
# a single-page fetch's list literally contains just that one page), every
# sentinel here is unconditionally inserted at the same fixed spot on every
# render regardless of report month or data, so the position -> side
# mapping below can be (and must be, see next paragraph) precomputed once
# rather than re-derived from whatever page list happens to be at hand.
#
# An earlier version instead alternated over whatever list it was called
# with, correct for the full-report fetch but silently wrong for a
# single-page fetch (used by the web preview's page-selector navigation,
# see useReportPage in the frontend) — a list of just one page always
# "alternates" starting at "right", regardless of that page's true
# position in the full report. Before that, an even earlier version
# derived side from the page's own number's parity: correct only by
# coincidence, as long as exactly an EVEN count of sentinel pages sat
# before it — and flipped every page from wherever that count went odd
# onward, which is exactly what happened when BF_LARGE_ANNEXURE_PAGE_ID
# (3.6) shipped as a 3rd front-cluster sentinel without a matching fix (it
# also fell outside every range entirely — no badge at all, missing from
# the exported PDF too, since pdf.py only stamps where dept_badges has a
# truthy entry). A precomputed lookup keyed by page id sidesteps every
# variant of this bug at once: it doesn't matter what list, if any, this
# page happens to be fetched alongside.
_CANONICAL_PAGE_ORDER = [
    2.5, 3, 3.5, 3.6,
    *range(4, 25), 1024,
    25, 26,
    27, 28, 29, 29.5, 30,
    31, 32, 33, 34, 35, 35.4, 35.5, 35.6, 35.7,
    *range(36, 41),
]

_DEPT_BADGE_SIDE = {}
_side = "right"
for _pg in _CANONICAL_PAGE_ORDER:
    _DEPT_BADGE_SIDE[_pg] = _side
    _side = "left" if _side == "right" else "right"
del _pg, _side


def assign_dept_badges(pages: list) -> None:
    """Sets page["dept_badge"] = {"group", "side"} (or None) on every entry
    of `pages`, IN PLACE — safe to call with the full report's page list,
    a single-page list, or anything in between/out of order, since group
    and side are both looked up purely from each page's own id (see
    _DEPT_BADGE_SIDE above), never from position within `pages` itself.

    Side follows book-binding convention (recto/verso). This mirrors
    pdf.py's _apply_dept_badges, which independently recomputes each
    PHYSICAL PDF page's side the same way (right if (k+1) is odd) from the
    rendered page's own true position — this function exists so the live
    web preview (which has no equivalent post-render pass) shows the same
    alternation the exported PDF does.
    """
    for p in pages:
        pg = p.get("page")
        group = dept_badge_group(pg)
        p["dept_badge"] = {"group": group, "side": _DEPT_BADGE_SIDE.get(pg, "right")} if group is not None else None


def compute_item_row(month: str, item_name: str) -> list:
    """Computes a 12-value list for the SAIL summary production table.

    Index  Column
    -----  ------
    0      Monthly APP
    1      Monthly ACT
    2      Monthly VAR  (ACT - APP)
    3      Monthly %FUL
    4      CPLY Monthly ACT
    5      %GR vs CPLY month
    6      YTD APP
    7      YTD ACT
    8      YTD VAR  (ACT - APP)
    9      YTD %FUL
    10     YTD CPLY ACT
    11     %GR vs CPLY YTD
    """
    db_item = item_name
    if item_name == "Crude Steel":
        db_item = "Total Crude Steel"
    elif item_name in ("Finish Steel", "Finished Steel"):
        db_item = "Finished Steel"

    month_plan        = db.get_sail_production_plan(month, db_item)
    month_actual      = db.get_sail_production_actual(month, db_item)

    cply_month        = db.get_cply_month(month)
    month_cply_actual = db.get_sail_production_actual(cply_month, db_item)

    ytd_months        = db.get_ytd_months(month)
    ytd_plan          = db.get_sail_production_ytd_plan(ytd_months, db_item)
    ytd_actual        = db.get_sail_production_ytd_actual(ytd_months, db_item)

    ytd_cply_months   = db.get_ytd_months(cply_month)
    ytd_cply_actual   = db.get_sail_production_ytd_actual(ytd_cply_months, db_item)

    # Plain round() is banker's-rounding (round-half-to-even) — 1870.5
    # rounds to 1870, not 1871, purely because 1870 happens to be even.
    # page5_6.py's Plant-Wise Production Performance page (_fmt) already
    # uses round-half-up (floor(x+0.5)) for the exact same production_
    # plan_table figures, so a .5 total (as SAIL's summed Hot Metal plan
    # for Jul'26 genuinely was: 448+490+216.5+262+454) showed 1871 there
    # but 1870 here — same underlying number, two different rounding
    # rules. Matches page5_6.py's convention so both pages always agree.
    import math as _math

    def _round_half_up(v):
        # Unconditional floor(v + 0.5), matching page5_6.py's _fmt/_pct/
        # _growth exactly (including for negatives: floor(-0.5+0.5) = 0,
        # not -1) — a "round half up" that differs from "round half away
        # from zero" is still fine to match here, since consistency with
        # the other page is the actual goal, not picking the abstractly
        # "more correct" negative-rounding convention.
        return _math.floor(v + 0.5)

    def fmt(val):
        return "" if val is None else str(_round_half_up(val))

    def var(a, p):
        if a is None or p is None:
            return ""
        return str(_round_half_up(a - p))

    def pct(num, den):
        if num is None or den is None or den == 0:
            return ""
        return str(_round_half_up((num / den) * 100))

    def growth(num, den):
        if num is None or den is None or den == 0:
            return ""
        return str(_round_half_up(((num - den) / den) * 100))

    return [
        fmt(month_plan),                          # 0  Monthly APP
        fmt(month_actual),                        # 1  Monthly ACT
        var(month_actual, month_plan),            # 2  Monthly VAR
        pct(month_actual, month_plan),            # 3  Monthly %FUL
        fmt(month_cply_actual),                   # 4  CPLY Monthly ACT
        growth(month_actual, month_cply_actual),  # 5  %GR vs CPLY
        fmt(ytd_plan),                            # 6  YTD APP
        fmt(ytd_actual),                          # 7  YTD ACT
        var(ytd_actual, ytd_plan),                # 8  YTD VAR
        pct(ytd_actual, ytd_plan),                # 9  YTD %FUL
        fmt(ytd_cply_actual),                     # 10 YTD CPLY ACT
        growth(ytd_actual, ytd_cply_actual),      # 11 %GR vs YTD CPLY
    ]


def build_production_narrative(production_table: List[Dict[str, Any]]) -> str:
    """Page 3's top narrative sentence, computed from the same production_table
    rows/indices as the ACT (1) and %FUL (3) columns shown just below it —
    mirrors SummaryTemplate.js's client-side version so the live preview and
    the server-rendered PDF template always agree."""
    def find_row(item_name):
        return next((r for r in production_table if r.get("item") == item_name), None)

    def cell(row, idx):
        vals = (row or {}).get("values") or []
        return vals[idx] if len(vals) > idx else None

    def fmt_mt(val):
        try:
            return f"{float(val) / 1000:.3f}"
        except (TypeError, ValueError):
            return "—"

    def fmt_pct(val):
        return "—" if val in (None, "") else f"{val}%"

    hot_metal    = find_row("Hot Metal")
    crude_steel  = find_row("Crude Steel")
    saleable     = find_row("Saleable Steel")

    return (
        f"Hot Metal production during the month was {fmt_mt(cell(hot_metal, 1))} MT "
        f"({fmt_pct(cell(hot_metal, 3))} of APP), Crude Steel production was "
        f"{fmt_mt(cell(crude_steel, 1))} MT ({fmt_pct(cell(crude_steel, 3))} of APP) and "
        f"Saleable Steel production was {fmt_mt(cell(saleable, 1))} MT "
        f"({fmt_pct(cell(saleable, 3))} of APP)."
    )


def blank_out_page_data(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Blanks out mock/dummy numeric data and highlights from the template pages config."""
    blanked = []
    for page in pages:
        p = dict(page)

        if "highlights" in p:
            p["highlights"] = []

        if "production_table" in p and p["production_table"]:
            p["production_table"] = [
                {**row, "values": [""] * len(row.get("values", []))}
                for row in p["production_table"]
            ]

        if "te_table" in p and p["te_table"]:
            p["te_table"] = [
                {**row, "values": [""] * len(row.get("values", []))}
                for row in p["te_table"]
            ]

        if "rows" in p and p["rows"] and p.get("type") not in ("index", "cover"):
            p["rows"] = [
                {**row, "values": [""] * len(row.get("values", []))}
                for row in p["rows"]
            ]

        blanked.append(p)
    return blanked
