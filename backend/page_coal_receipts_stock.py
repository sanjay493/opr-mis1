"""
"Coking Coal Receipts & Stock" — two report pages sourced from techno_data,
populated by api_coal_omi_techno.py (see techno_project/coal_omi_extractor.py
for the source workbook). Both reuse the "key_parameters" page type/template
verbatim (KeyParametersTemplate.js / page_templates/key_parameters.html are
already fully generic over {title, plants, rows} — no new frontend code
needed) rather than page_techno.py's per-plant-param TECHNO_PAGES machinery,
which doesn't fit either page's shape (page 35.5 needs a SAIL column
alongside the 5 plants; page 35.6 is SAIL-only, no plant columns at all).

Page 35.5 — per-plant (BSP/DSP/RSP/BSL/ISP/SAIL) coking coal quantities,
  both "This Month" and "Till Month" (April->report_month, computed by
  techno_cumulative.py's "sum" rule at insert time — see api_coal_omi_techno.py)
  as two row sections sharing the same plant columns.

Page 35.6 — SAIL-only Receipt (Plan/Actual, TPD), Consumption (Actual/
  Average), and Stock (as of the report month's 1st) — unit="Coal_Receipt_Stock",
  a single "SAIL" column (the key_parameters template accepts any plants
  list, including a length-1 one).
"""
import db

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_GENERAL_UNIT = "General"
_RECEIPT_STOCK_UNIT = "Coal_Receipt_Stock"

_COAL_ROWS = [
    ("Indigenous PCC", "indigenous_pcc"),
    ("Indigenous MCC", "indigenous_mcc"),
    ("Imported Hard Coking Coal", "imported_hard_coal"),
    ("Imported Soft Coking Coal", "imported_soft_coal"),
]


def _fetch_general(report_month: str) -> dict:
    """{plant: {"month": {...}, "till_month": {...}}} for PLANTS + SAIL,
    unit="General"."""
    out = {}
    for plant in PLANTS + ["SAIL"]:
        d = db.get_techno_data(plant, report_month, unit=_GENERAL_UNIT)
        out[plant] = d.get(_GENERAL_UNIT, {})
    return out


def generate_coal_receipts_plants(report_month: str) -> dict:
    techno = _fetch_general(report_month)
    plants = PLANTS + ["SAIL"]

    rows = [{"type": "section", "label": "This Month"}]
    for label, key in _COAL_ROWS:
        rows.append({
            "type": "data", "parameter": label, "unit": "'000 T",
            "plant_values": {p: techno.get(p, {}).get("month", {}).get(key) for p in plants},
        })
    rows.append({"type": "spacer"})
    rows.append({"type": "section", "label": "Till Month (April onward)"})
    for label, key in _COAL_ROWS:
        rows.append({
            "type": "data", "parameter": label, "unit": "'000 T",
            "plant_values": {p: techno.get(p, {}).get("till_month", {}).get(key) for p in plants},
        })

    return {
        "title": f"Coking Coal Consumption — {report_month}",
        "plants": plants,
        "rows": rows,
    }


def generate_coal_receipts_sail(report_month: str) -> dict:
    d = db.get_techno_data("SAIL", report_month, unit=_RECEIPT_STOCK_UNIT)
    m = d.get(_RECEIPT_STOCK_UNIT, {}).get("month", {})

    def row(label, unit, key):
        return {"type": "data", "parameter": label, "unit": unit, "plant_values": {"SAIL": m.get(key)}}

    rows = [
        {"type": "section", "label": "Receipt at Plants"},
        row("Indigenous — Plan", "TPD", "receipt_plan_indigenous"),
        row("Indigenous — Actual", "TPD", "receipt_actual_indigenous"),
        row("Imported — Plan", "TPD", "receipt_plan_imported"),
        row("Imported — Actual", "TPD", "receipt_actual_imported"),
        row("Total — Plan", "TPD", "receipt_plan_total"),
        row("Total — Actual", "TPD", "receipt_actual_total"),
        {"type": "spacer"},
        {"type": "section", "label": "Consumption at Plants"},
        row("Indigenous — Actual", "'000 T", "consumption_actual_indigenous"),
        row("Indigenous — Average", "TPD", "consumption_avg_indigenous"),
        row("Imported — Actual", "'000 T", "consumption_actual_imported"),
        row("Imported — Average", "TPD", "consumption_avg_imported"),
        row("Total — Actual", "'000 T", "consumption_actual_total"),
        row("Total — Average", "TPD", "consumption_avg_total"),
        {"type": "spacer"},
        {"type": "section", "label": f"Stock as of {m.get('stock_as_of_month') or '1st of month'}"},
        row("Indigenous", "'000 T", "stock_indigenous"),
        row("Imported", "'000 T", "stock_imported"),
        row("Total", "'000 T", "stock_total"),
    ]

    return {
        "title": f"Coking Coal Receipts & Stock (SAIL) — {report_month}",
        "plants": ["SAIL"],
        "rows": rows,
    }
