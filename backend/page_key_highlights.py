"""
Key Highlights & Variances — narrative + snapshot summary page, inserted
right after "SAIL Performance Summary" (see KEY_HIGHLIGHTS_PAGE_ID in
main.py). Modeled on Report_format/Key highlights and variance.png.

The numeric sections (KPI strip, YTD comparison, Value Added Steel,
Techno-Economic Snapshot) are computed fresh from the same DB tables every
other report page reads from — same as page_at_a_glance.py/page 3. The
three narrative sections (Major Achievements, Major Shortfalls / Areas of
Concern, Focus Areas Going Forward) are deliberately NOT computed — they're
a human analyst's written read of the month, not something derivable from
numbers. They're entered via the Key Highlights — Manual Entry page
(/data-entry/key-highlights, editor/admin only — see api_key_highlights.py)
and read straight from key_highlights_narrative (db.get_key_highlights_
narrative) for report_month, never generated on the fly. Sections show
empty until an editor has entered something for that month.
"""
import datetime as _dt

import db
from report_utils import compute_item_row
from page_techno import generate_key_highlights_te_table
from page_special_steel import generate_special_steel_sail
from page_at_a_glance import _va_period_value, _just_ended_quarter, _quarter_months, _quarter_label

_PROD_ITEMS = ["Hot Metal", "Crude Steel", "Finished Steel", "Saleable Steel"]

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# "Better Direction" + Assessment color for the Techno-Economic Snapshot
# table, matching Report_format/Key highlights and variance.png's own
# legend: Coke/Fuel/Nut Coke Rate, Specific Energy Consumption, Sp. CO2
# Emission and TMI are all "lower is better"; BF Productivity, CDI Rate,
# Sinter/Pellet in Burden are "higher is better".
_LOWER_IS_BETTER = {
    "Coke Rate", "Fuel Rate", "Nut Coke Rate",
    "Specific Energy Consumption", "Sp. CO2 Emission", "TMI",
}


def _num(v):
    try:
        if v in (None, ""):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _ytd_label(months: list) -> str:
    s = _dt.datetime.strptime(months[0], "%Y-%m").strftime("%b")
    e = _dt.datetime.strptime(months[-1], "%Y-%m").strftime("%b'%y")
    return f"{s}-{e}" if len(months) > 1 else e


def _kpi_section(report_month: str) -> list:
    """Top KPI strip: Hot Metal / Crude Steel / Finished Steel / Saleable
    Steel for the report month, in MT (production_table stores '000T, so
    /1000 gets MT the same way the reference image shows it)."""
    out = []
    for item in _PROD_ITEMS:
        v = compute_item_row(report_month, item)
        act = _num(v[1])
        out.append({
            "item": item,
            "value_mt": f"{act / 1000:.3f}" if act is not None else None,
            "pct_app": v[3] or None,
            "growth_cply": v[5] or None,
            "growth_good": None if v[5] == "" else int(v[5]) >= 0,
        })
    return out


def _ytd_section(report_month: str) -> dict:
    """Year-to-date (Apr..report_month) vs the same window CPLY, per
    production item, in '000T (production_table's native unit — matches
    the reference chart's own "Quantity in '000 T" label)."""
    cply_month = db.get_cply_month(report_month)
    cur_months = db.get_ytd_months(report_month)
    cply_months = db.get_ytd_months(cply_month)

    # Key "rows" (not "items") — a dict with a plain "items" key hits the
    # same dict.items()-shadows-item-lookup Jinja gotcha documented
    # elsewhere in this codebase (see sub.values -> sub.vals convention).
    rows = []
    max_val = 0.0
    for item in _PROD_ITEMS:
        v = compute_item_row(report_month, item)
        cur, prev, growth = _num(v[7]), _num(v[10]), v[11]
        rows.append({
            "item": item, "cur": cur, "prev": prev,
            "growth_pct": growth or None,
            "growth_good": None if growth == "" else int(growth) >= 0,
        })
        max_val = max(max_val, cur or 0, prev or 0)

    for it in rows:
        it["cur_pct"] = round(it["cur"] / max_val * 100, 1) if it["cur"] is not None and max_val else 0
        it["prev_pct"] = round(it["prev"] / max_val * 100, 1) if it["prev"] is not None and max_val else 0
        it["cur_fmt"] = f"{it['cur']:,.0f}" if it["cur"] is not None else "—"
        it["prev_fmt"] = f"{it['prev']:,.0f}" if it["prev"] is not None else "—"

    return {"prev_label": _ytd_label(cply_months), "cur_label": _ytd_label(cur_months), "rows": rows}


def _value_added_section(report_month: str) -> dict:
    """Value Added (Special) Steel box: YTD % of Saleable Steel (+pp vs
    CPLY), the just-ended quarter's % transition, and the report month's
    own qty/%Fulfilment/vs CPLY — all reused from the same sources
    page_at_a_glance.py's Value Added Steel box already computes from."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur_months = db.get_ytd_months(report_month)
        cply_month = db.get_cply_month(report_month)
        cply_months = db.get_ytd_months(cply_month)
        _, ytd_pct = _va_period_value(cur, cur_months)
        _, ytd_pct_cply = _va_period_value(cur, cply_months)
        ytd_pp = round(ytd_pct - ytd_pct_cply, 1) if ytd_pct is not None and ytd_pct_cply is not None else None

        q_start, q_end = _just_ended_quarter(report_month)
        cply_q_start = f"{int(q_start[:4]) - 1}-{q_start[5:7]}"
        cply_q_end = f"{int(q_end[:4]) - 1}-{q_end[5:7]}"
        _, q_pct_cply = _va_period_value(cur, _quarter_months(cply_q_start, cply_q_end))
        _, q_pct_cur = _va_period_value(cur, _quarter_months(q_start, q_end))
        q_pp = round(q_pct_cur - q_pct_cply, 1) if q_pct_cur is not None and q_pct_cply is not None else None
    finally:
        conn.close()

    sail = generate_special_steel_sail(report_month)
    total = next((r for r in sail.get("rows", []) if r.get("type") == "sail-total"), {})
    month_qty = total.get("actual") or ""
    month_growth = total.get("pct_growth", "")

    return {
        "ytd_pct": round(ytd_pct, 1) if ytd_pct is not None else None,
        "ytd_pp": ytd_pp, "ytd_pp_abs": None if ytd_pp is None else abs(ytd_pp),
        "quarter_label": _quarter_label(q_start, q_end),
        "quarter_cply_pct": round(q_pct_cply, 1) if q_pct_cply is not None else None,
        "quarter_cur_pct": round(q_pct_cur, 1) if q_pct_cur is not None else None,
        "quarter_pp": q_pp, "quarter_pp_abs": None if q_pp is None else abs(q_pp),
        "month_label": _dt.datetime.strptime(report_month, "%Y-%m").strftime("%b'%y"),
        "month_qty": f"{int(month_qty):,}" if month_qty else None,
        "month_pct_ful": total.get("pct_ful") or None,
        "month_growth_cply": month_growth or None,
        "month_growth_good": None if month_growth in (None, "") else int(month_growth) >= 0,
    }


def _techno_section(report_month: str) -> list:
    rows = generate_key_highlights_te_table(report_month)
    out = []
    for row in rows:
        name = row["parameter"]
        target, actual = _num(row["values"][0]), _num(row["values"][1])
        lower_better = name in _LOWER_IS_BETTER

        variance = variance_pct = None
        tier, assessment = None, "—"
        if target and actual is not None:
            variance = round(actual - target, 2)
            raw_pct = (actual - target) / target * 100
            variance_pct = round(abs(raw_pct), 1)
            good_pct = -raw_pct if lower_better else raw_pct
            above = actual > target
            if abs(good_pct) < 1.0:
                tier, assessment = "within", "Within Target"
            elif good_pct >= 0:
                tier, assessment = "good", "Above Target" if above else "Below Target"
            elif abs(good_pct) < 3.0:
                tier, assessment = "amber", "Above Target" if above else "Below Target"
            else:
                tier, assessment = "bad", "Above Target" if above else "Below Target"

        out.append({
            "parameter": name, "unit": row["unit"],
            "better_direction": "Lower is better" if lower_better else "Higher is better",
            "target": row["values"][0] or "—",
            "actual": row["values"][1] or "—",
            "variance": variance, "variance_pct": variance_pct,
            "tier": tier, "assessment": assessment,
            "dot_color": {"within": "green", "good": "green", "amber": "amber", "bad": "red"}.get(tier),
        })
    return out


def generate_key_highlights(report_month: str) -> dict:
    dt = _dt.datetime.strptime(report_month, "%Y-%m")
    month_label = f"{_MON_ABBR[dt.month]}-{dt.year}"

    narrative = db.get_key_highlights_narrative(report_month) or {
        "achievements": [], "shortfalls": [], "focus_areas": [],
    }

    return {
        "type": "key_highlights",
        "title": "KEY HIGHLIGHTS & VARIANCES",
        "subtitle": f"Major Achievements, Exceptions & Focus Areas — {month_label}",
        "month_label": month_label,
        "kpi": _kpi_section(report_month),
        "ytd": _ytd_section(report_month),
        "value_added": _value_added_section(report_month),
        "techno": _techno_section(report_month),
        "achievements": narrative["achievements"],
        "shortfalls": narrative["shortfalls"],
        "focus_areas": narrative["focus_areas"],
    }
