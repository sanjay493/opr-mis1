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


def get_dept_badge(page_num: Optional[int]) -> Optional[Dict[str, Any]]:
    """Corner-badge group + side for a page, or None for pages 1-2 (cover/
    index are front matter — no header/footer/badge, matching the existing
    convention) and any page number outside the known ranges.

    Side follows book-binding convention: odd pages are recto (right-hand
    when bound) and even pages are verso (left-hand) — so odd -> top-right,
    even -> top-left, alternating every page.
    """
    if not isinstance(page_num, int) or page_num < 3:
        return None
    for lo, hi, group in _DEPT_BADGE_GROUPS:
        if lo <= page_num <= hi:
            return {"group": group, "side": "right" if page_num % 2 == 1 else "left"}
    return None


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

    def fmt(val):
        return "" if val is None else str(round(val))

    def var(a, p):
        if a is None or p is None:
            return ""
        return str(round(a - p))

    def pct(num, den):
        if num is None or den is None or den == 0:
            return ""
        return str(round((num / den) * 100))

    def growth(num, den):
        if num is None or den is None or den == 0:
            return ""
        return str(round(((num - den) / den) * 100))

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
