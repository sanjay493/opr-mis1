"""
"Consumption of Coking Coal and CDI Coal" — landscape page reproducing
Report_format/Coal_co2/Coal Format.pdf's OIS-1 table exactly: per-plant
(BSP/DSP/RSP/BSL/ISP/SAIL) row groups, each with the report month's own
row and (except in April, the FY's first month) an "Apr-<Mon>'YY"
FY-cumulative row directly below it, under a compound column header
(Indigenous Coking Coal PCC/MCC/Total, Imported Coking Coal Hard/Soft/
Total, Total Coking Coal, CDI Coal, then the same two group breakdowns
again as Blend %).

Pure lookup/display, no computation — every value (including the totals
and blend%) was already computed by the source workbook and extracted
verbatim by techno_project/coal_omi_extractor.py's extract_ois1_detail
into techno_data (unit="Coal_Consumption", one row per plant/SAIL, keyed
by report_month like every other techno_data row). Data entry (the Excel
upload) and its own validation live entirely in api_coal_omi_techno.py —
this module only reads what's already been saved there.
"""
import db

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_UNIT = "Coal_Consumption"

# (label, key) — column order matches the sheet/PDF left-to-right.
QTY_COLS = [
    ("PCC", "pcc"), ("MCC", "mcc"), ("Total", "indigenous_total"),
    ("Hard", "hard"), ("Soft", "soft"), ("Total", "imported_total"),
]
PCT_COLS = [
    ("PCC", "pcc_pct"), ("MCC", "mcc_pct"), ("Total", "indigenous_total_pct"),
    ("Hard", "hard_pct"), ("Soft", "soft_pct"), ("Total", "imported_total_pct"),
]

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_label(report_month: str) -> str:
    y, m = report_month.split("-")
    return f"{_MON_ABBR[int(m)]}'{y[-2:]}"


def _till_month_label(report_month: str) -> str:
    y, m = report_month.split("-")
    m = int(m)
    if m == 4:
        return f"Apr'{y[-2:]}"
    return f"Apr-{_month_label(report_month)}"


def generate_coal_consumption(report_month: str) -> dict:
    is_april = report_month.endswith("-04")
    plants = PLANTS + ["SAIL"]

    groups = []
    for plant in plants:
        stored = db.get_techno_data(plant, report_month, unit=_UNIT).get(_UNIT, {})
        month_row = stored.get("month") or {}
        # NOT "values" — Jinja2's dot-notation resolves that to dict.values
        # (the built-in method) before falling back to item lookup, since
        # getattr succeeds first; "vals" avoids the collision.
        sub_rows = [{
            "label": month_row.get("label") or _month_label(report_month),
            "vals": month_row,
        }]
        if not is_april:
            till_row = stored.get("till_month") or {}
            sub_rows.append({
                "label": till_row.get("label") or _till_month_label(report_month),
                "vals": till_row,
            })
        groups.append({"plant": plant, "sub_rows": sub_rows})

    return {
        "type": "coal_consumption",
        "title": f"Consumption of Coking Coal and CDI Coal - {_month_label(report_month)}",
        "qty_cols": QTY_COLS,
        "pct_cols": PCT_COLS,
        "groups": groups,
    }
