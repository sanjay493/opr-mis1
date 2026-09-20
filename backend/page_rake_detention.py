"""
"Details of Rakes Detention Plant Wise" — SAIL Rail Movement Cell's
"Average Plant Detention Report" (Report_format's sample: Aug'26).

Pure lookup/display, no computation (same convention as
special_steel_phys_perf / page_coal_consumption's OIS-1 table): every
figure — including each section's own "Total Inward"/"Total Outward"/
"Overall Wagon" summary row, page 4's per-FY "APR-MAR" average, and the
whole "Improvement" comparison table — is a value entered directly via
/data-entry/rake-detention or scripts/backfill_rake_detention.py. The
source report's own totals are rake-count-weighted (a figure this report
doesn't have) and its per-FY averages don't always reduce to a plain mean
of the displayed monthly figures (deeper internal precision than what's
printed) — recomputing either here risks a silently wrong number in an
official-looking report.

7 pages: one portrait detail page per plant (BSP/DSP/RSP/BSL/ISP — split
out from the source PDF's own 3-plant/2-plant page groupings, which
crammed 60-70+ rows onto a single landscape page at 6.5pt font; one plant
per page instead leaves each page with at most ~35 rows, legible at a much
larger size). Portrait per direct instruction (2026-09-20) — was landscape
until then; see pdf.py's _LANDSCAPE_TYPES and main.html's content-page
wrapper-class group, both updated alongside this page's own template.
Plus the two summary/trend pages:
  - DETAIL_PAGES[page_id] -> plant list: commodity/wagon-type detail,
    portrait, one full-FY row (Apr-Mar, current FY) per wagon type/total.
    Each entry here is a single-plant list (not the old 3-plant/2-plant
    groupings) — purely a page-layout choice, unrelated to
    rake_detention_master's own plant/section/commodity grouping.
  - generate_rake_detention_summary(): "Improvement in Average Detention
    per Wagon in Hrs" — a 3-period (current month / YTD / full FY) CPLY
    comparison, portrait.
  - generate_rake_detention_trend(): "Average Detention per Wagons in
    Hours" — the "Overall Wagon" master row's multi-year monthly history,
    portrait.

Row registry (which plant/section/commodity/wagon-type rows exist, and
each one's freetime) lives in rake_detention_master, edited via
/data-entry/rake-detention — adding a new wagon type for a plant later is
a data change there, never a code change here. See db.py's matching
comment and scripts/migrate_add_rake_detention.sql.
"""
import db
from page_coal_consumption import PLANTS  # ["BSP", "DSP", "RSP", "BSL", "ISP"]
from page_special_steel_trend import _last_n_fys, _fy_months

# Page id -> plant subset shown on that portrait detail page — one plant
# per page (see module docstring for why: BSP alone runs 31 rows, and the
# old 3-plant/2-plant groupings needed 6.5pt font to fit at all). New ids
# 1038-1040 sit outside the already-claimed 1026-1037 range (Rake
# Detention summary/trend + Ready Reckoner) — see report_utils.py's
# _CANONICAL_PAGE_ORDER/_DEPT_BADGE_EXPLICIT_GROUP and the frontend's
# _PAGE_SORT_POS for the matching display-order overrides this requires.
DETAIL_PAGES = {
    1026: ["BSP"],
    1027: ["DSP"],
    1038: ["RSP"],
    1039: ["BSL"],
    1040: ["ISP"],
}
SUMMARY_PAGE_ID = 1028
TREND_PAGE_ID = 1029

_SECTIONS = ["INWARD", "OUTWARD", "OVERALL"]
_SECTION_HEADING = {"INWARD": "Inward", "OUTWARD": "Outward Despatch", "OVERALL": "Over all"}

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# (code, ty_label, ly_label, pct_label) triples, in display order — the
# source PDF's 3 stacked period blocks (current month, YTD, full FY), each
# a This-Year / Last-Year / CPLY% row.
PERIOD_ROWS = [
    ("CUR_MON_TY", "TY"), ("CUR_MON_LY", "LY"), ("CUR_MON_CPLY_PCT", "Changes CPLY"),
    ("YTD_TY", "TY"), ("YTD_LY", "LY"), ("YTD_CPLY_PCT", "Changes CPLY"),
    ("FY_TY", "TY"), ("FY_LY", "LY"), ("FY_CPLY_PCT", "Changes CPLY"),
]
SUMMARY_PLANTS = PLANTS + ["SAIL"]

# History back to FY2016-17 by default (page 4's own sample goes back to
# 2021-22; a few extra years costs nothing when there's no data for them —
# get_rake_detention_trend/get_rake_detention_annual just come back empty).
TREND_HISTORY_FYS = 10


def _month_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{_MON_ABBR[int(m)]}'{y[-2:]}"


def _fmt1(v):
    """1-decimal figure — pages 1/2/4's own convention (e.g. '7.4')."""
    return "" if v is None else f"{v:.1f}"


def _fmt2(v):
    """2-decimal figure — page 3's own convention (e.g. '11.41')."""
    return "" if v is None else f"{v:.2f}"


def _fmt_pct(v):
    return "" if v is None else f"{v:.1f}%"


def _upto_label(report_month: str) -> str:
    y, m = report_month.split("-")
    return f"Upto {_MON_ABBR[int(m)]}'{y[-2:]}"


def _heatmap_bg(value, freetime):
    """Background color for one month's detention-hours cell, keyed to
    that row's OWN Freetime — the natural reference point for whether a
    figure represents good or poor performance (per direct instruction):
    a white/near-white mid-point right at the freetime threshold itself,
    shading toward green the further a value sits BELOW it (well within
    the allowed free time) and toward red the further it sits ABOVE it
    (detention beyond the free time — the thing this whole report exists
    to track). None (no color) whenever there's nothing meaningful to
    compare: a blank cell, a row with no freetime at all (e.g. a couple
    of Over all rows that don't carry one), or a 0.0 figure — this
    report's own 0.0 means no rake moved that month, not "zero
    detention", and grading it would otherwise paint it the deepest green
    on the scale, the most misleading reading a blank month could get
    (per direct instruction)."""
    if not value or freetime is None or freetime <= 0:
        return None
    ratio = value / freetime
    ratio = max(0.0, min(ratio, 2.5))  # cap how far the gradient has to stretch
    if ratio <= 1.0:
        t = 1.0 - ratio                      # 0 at the threshold, 1 at ratio=0
        end = (56, 161, 105)                 # a clear green
    else:
        t = min((ratio - 1.0) / 1.5, 1.0)    # 0 at the threshold, 1 at ratio>=2.5
        end = (217, 48, 37)                  # a clear red
    r = round(255 + (end[0] - 255) * t)
    g = round(255 + (end[1] - 255) * t)
    b = round(255 + (end[2] - 255) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _rows_with_commodity_rowspan(sec_rows: list, history: dict, months: list, heatmap: bool = True) -> list:
    """Builds one section's row dicts, merging the Commodity column across
    consecutive rows that share the same commodity (e.g. BSP Inward's
    "Ind.Coking Coal" spans its BOXN/BOST/BOSM rows) into a single spanned
    cell, per direct instruction — rather than the earlier blank-on-repeat
    convention. A row's own total row (is_total) or a row with no
    commodity at all (Overall's wagon-only rows) never merges — each keeps
    its own single-row cell, exactly as before.

    heatmap=False (Over all — see generate_rake_detention_detail) skips
    _heatmap_bg entirely, per direct instruction: Over all combines
    Inward + Outward movements of the same wagon type, so its own
    Freetime figure isn't a plain sum of theirs (confirmed: BSP's Inward
    BOST 8.0 + Outward BOST 16.0 = 24.0, but Over all's own BOST freetime
    is 34.0) — not a like-for-like reference to grade Over all's own
    monthly figures against, which is also why that column isn't even
    shown there (see rake_detention_detail.html)."""
    out = []
    i, n = 0, len(sec_rows)
    while i < n:
        r = sec_rows[i]
        commodity = r["commodity"]
        span = 1
        if not r["is_total"] and commodity:
            while i + span < n and not sec_rows[i + span]["is_total"] and sec_rows[i + span]["commodity"] == commodity:
                span += 1
        for k in range(span):
            rr = sec_rows[i + k]
            freetime = rr["freetime_hours"]
            month_vals = [history.get(rr["id"], {}).get(m) for m in months]
            out.append({
                "commodity": commodity if k == 0 else None,
                "commodity_rowspan": span if k == 0 else 0,
                "wagon_type": rr["wagon_type"],
                "row_label": rr["row_label"],
                "is_total": bool(rr["is_total"]),
                "freetime_hours": _fmt1(freetime),
                # NOT "values" — Jinja2's dot-notation resolves that to
                # dict.values (the built-in method) before falling back to
                # item lookup, same collision page_coal_consumption.py's
                # sub_rows hit first. Each entry carries its own heatmap
                # background (None for a section's own total row — see
                # _heatmap_bg — total figures aren't a per-wagon-type
                # detention figure to grade against a freetime).
                "vals": [
                    {"text": _fmt1(v), "bg": _heatmap_bg(v, freetime) if heatmap and not rr["is_total"] else None}
                    for v in month_vals
                ],
            })
        i += span
    return out


def generate_rake_detention_detail(report_month: str, plants: list) -> dict:
    """One detail page's worth of data for `plants`: full current-FY row
    (Apr-Mar) per wagon type/commodity, grouped Inward / Outward / Overall,
    each ending in its section's own directly-entered total row."""
    fy_label = db.get_fy_for_month(report_month)
    months = _fy_months(fy_label)

    master_rows = db.get_rake_detention_master(plants=plants)
    ids = [r["id"] for r in master_rows]
    history = db.get_rake_detention_trend(ids)  # {master_id: {report_month: value}}

    by_plant = {}
    for r in master_rows:
        by_plant.setdefault(r["plant"], []).append(r)

    out_plants = []
    for plant in plants:
        rows = by_plant.get(plant, [])
        sections = []
        for section in _SECTIONS:
            sec_rows = [r for r in rows if r["section"] == section]
            if not sec_rows:
                continue
            direction = next((r["direction"] for r in sec_rows if r["direction"]), None)
            sections.append({
                "section": section,
                "heading": _SECTION_HEADING[section],
                "direction": direction,
                "rows": _rows_with_commodity_rowspan(sec_rows, history, months, heatmap=(section != "OVERALL")),
            })
        out_plants.append({"plant": plant, "sections": sections})

    return {
        "type": "rake_detention_detail",
        "title": "Commodity Wise Average Plant Detention at Steel Plants",
        "subtitle": f"During {fy_label}",
        "plants": out_plants,
        "month_labels": [_month_label(m) for m in months],
    }


def _shift_year(ym: str, delta_years: int) -> str:
    y, m = ym.split("-")
    return f"{int(y) + delta_years:04d}-{m}"


def _period_row_labels(report_month: str) -> dict:
    """{code: display_label} for PERIOD_ROWS, e.g. 'AUG'26', 'APR'26-AUG'26',
    'APR'25-MAR'26' — computed from report_month, not stored (the label is
    always a pure function of which month the report is for)."""
    fy_label = db.get_fy_for_month(report_month)
    fy_months_cur = _fy_months(fy_label)
    apr_cur = fy_months_cur[0]
    ly_month = _shift_year(report_month, -1)
    apr_ly = _shift_year(apr_cur, -1)

    prev_fy = _last_n_fys(report_month, 2)[0]
    prev_fy_months = _fy_months(prev_fy)
    prev2_fy = _last_n_fys(report_month, 3)[0]
    prev2_fy_months = _fy_months(prev2_fy)

    mon = _month_label(report_month)
    mon_ly = _month_label(ly_month)
    ytd = f"{_month_label(apr_cur)}-{mon}"
    ytd_ly = f"{_month_label(apr_ly)}-{mon_ly}"
    fy_cur_closed = f"{_month_label(prev_fy_months[0])}-{_month_label(prev_fy_months[-1])}"
    fy_prev_closed = f"{_month_label(prev2_fy_months[0])}-{_month_label(prev2_fy_months[-1])}"

    return {
        "CUR_MON_TY": mon, "CUR_MON_LY": mon_ly, "CUR_MON_CPLY_PCT": "Changes CPLY",
        "YTD_TY": ytd, "YTD_LY": ytd_ly, "YTD_CPLY_PCT": "Changes CPLY",
        "FY_TY": fy_cur_closed, "FY_LY": fy_prev_closed, "FY_CPLY_PCT": "Changes CPLY",
    }


def generate_rake_detention_summary(report_month: str) -> dict:
    """"Improvement in Average Detention per Wagon in Hrs" — 9 period rows
    (3 This-Year/Last-Year/CPLY% triples) x plant columns, straight from
    rake_detention_summary (never derived from the monthly detail)."""
    data = db.get_rake_detention_summary(report_month)  # {period_row: {plant: value}}
    labels = _period_row_labels(report_month)
    rows = [
        {
            "code": code,
            "label": labels[code],
            "is_pct": row_kind == "Changes CPLY",
            "vals": [
                _fmt_pct(data.get(code, {}).get(p)) if row_kind == "Changes CPLY"
                else _fmt2(data.get(code, {}).get(p))
                for p in SUMMARY_PLANTS
            ],
        }
        for code, row_kind in PERIOD_ROWS
    ]
    return {
        "type": "rake_detention_summary",
        "title": "Improvement in Average Detention per Wagon in Hrs",
        "subtitle": _upto_label(report_month),
        "plants": SUMMARY_PLANTS,
        "rows": rows,
    }


def generate_rake_detention_trend(report_month: str) -> dict:
    """"Average Detention per Wagons in Hours" — each plant's "Overall
    Wagon" master row, one line per FY going back TREND_HISTORY_FYS years,
    12 months + the directly-entered "APR-MAR" full-FY average."""
    fys = _last_n_fys(report_month, TREND_HISTORY_FYS)[::-1]  # newest first, matches source PDF
    plants = SUMMARY_PLANTS

    master_rows = db.get_rake_detention_master(plants=plants)
    overall_id_by_plant = {
        r["plant"]: r["id"] for r in master_rows
        if r["section"] == "OVERALL" and r["is_total"]
    }
    ids = list(overall_id_by_plant.values())
    history = db.get_rake_detention_trend(ids)  # {master_id: {report_month: value}}
    annual = db.get_rake_detention_annual(plants, fys)  # {plant: {fy: avg_hours}}

    out_plants = []
    for plant in plants:
        mid = overall_id_by_plant.get(plant)
        plant_hist = history.get(mid, {}) if mid is not None else {}
        fy_rows = []
        for fy in fys:
            months = _fy_months(fy)
            raw_vals = [plant_hist.get(m) for m in months]
            raw_annual = annual.get(plant, {}).get(fy)
            # Skip an FY entirely for this plant when there's nothing at
            # all to show for it (no monthly figure, no annual average) —
            # per direct instruction: older FYs this plant has no history
            # for (e.g. 2017-18 through 2020-21, before this report's own
            # backfill starts) were printing as fully blank rows.
            if raw_annual is None and not any(v is not None for v in raw_vals):
                continue
            fy_rows.append({
                "fy": fy,
                "vals": [_fmt1(v) for v in raw_vals],
                "annual": _fmt1(raw_annual),
            })
        out_plants.append({"plant": plant, "fy_rows": fy_rows})

    return {
        "type": "rake_detention_trend",
        "title": "Average Detention per Wagons in Hours",
        "subtitle": _upto_label(report_month),
        "month_labels": ["Apr", "May", "Jun", "Jul", "Aug", "Sep",
                          "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"],
        "plants": out_plants,
    }
