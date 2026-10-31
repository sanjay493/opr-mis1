"""RMT "Production Plan for <month>" report (/reports/production-analysis
?tab=rmt-plan; api_rmt_plan.py serves it as JSON, .xlsx and .pdf).

Three pages, as the RMT meeting's sample (Nov'26):
  1. Hot Metal / Crude Steel / Saleable Steel by plant: the same month last
     year's actual; the previous month's APP, OP, actual ("M/rate") and their
     % fulfilment; the report month's APP and OP, each as a total and per day
     (TPD); remarks.
  2. Oven Pushing (nos/day, with the coal requirement per day), Sinter and
     Pig Iron: the report month's APP and OP, totals and per day; remarks.
  3. IPT requirement / availability and the stock table.

APP, OP and actuals come from production_monthly / production_op_monthly
through main._op_cmp_cells (the OP vs APP vs Actual report's reader), so
the two reports agree. Remarks, coal requirement, IPT rows and stock are
manual (repo.misc.rmt_plan_manual), entered at
/data-entry/production-techno?tab=rmt-plan."""
import calendar
import datetime as _dt

import month_utils
from constants import ALL_PLANTS
from repo import misc as rmisc

FIVE_ISPS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
SPECIAL = ["ASP", "SSP", "VISL"]

# page 1: (section key, label, item name, rows). A row is a plant code or a
# total: "5 ISPs" (the five integrated plants) or "SAIL" (every plant).
PAGE1 = [
    ("HM", "Hot Metal", "Hot Metal", FIVE_ISPS + ["SAIL"]),
    ("CS", "Crude Steel", "Total Crude Steel", FIVE_ISPS + ["5 ISPs"] + SPECIAL + ["SAIL"]),
    ("SS", "Saleable Steel", "Saleable Steel", FIVE_ISPS + ["5 ISPs"] + SPECIAL + ["SAIL"]),
]
# page 2: (section key, label, item name, rate item: nos/day, not '000 T)
PAGE2 = [
    ("COKE", "Oven Pushing (nos./day)", "Oven Pushing (nos/day)", True),
    ("SINTER", "Sinter ('000T)", "Total Sinter", False),
    ("PIG", "Pig Iron ('000T)", "Pig Iron", False),
]
SECTIONS = {s[0] for s in PAGE1} | {s[0] for s in PAGE2}
PAGE2_ROWS = FIVE_ISPS + ["5 ISPs"]
TOTALS = {"5 ISPs": FIVE_ISPS, "SAIL": ALL_PLANTS}


def mon_label(month: str) -> str:
    """'2026-11' -> "Nov'26"."""
    return _dt.date(int(month[:4]), int(month[5:7]), 1).strftime("%b'%y")


def col_label(month: str) -> str:
    """'2026-11' -> 'Nov-26'."""
    return _dt.date(int(month[:4]), int(month[5:7]), 1).strftime("%b-%y")


def _days(month: str) -> int:
    return calendar.monthrange(int(month[:4]), int(month[5:7]))[1]


def _sum(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def _pct(a, b):
    return round(a / b * 100) if a is not None and b else None


def _tpd(v, days):
    return round(v * 1000 / days) if v is not None else None


def _values(cells, plants, item, key):
    return _sum([cells.get((p, item), {}).get(key) for p in plants])


def _value(cells, row, item, key):
    plants = TOTALS.get(row, [row])
    # a total OP is left blank while a plant with a non-zero APP has no OP, as the
    # OP vs APP vs Actual report's SAIL total
    if key == "op" and row in TOTALS and any(
            cells.get((p, item), {}).get("app") and cells.get((p, item), {}).get("op") is None
            for p in plants):
        return None
    return _values(cells, plants, item, key)


def _cells(months):
    import main   # lazy: main imports this module's router
    return {m: main._op_cmp_cells(ALL_PLANTS, [m]) for m in months}


def generate(month: str) -> dict:
    prev = month_utils.shift_month(month, -1)
    ly = month_utils.shift_month(month, -12)
    cells = _cells([month, prev, ly])
    days = _days(month)
    manual = rmisc.rmt_plan_manual(month) or {}
    notes = {(n["section"], n["row_label"]): n for n in manual.get("notes", [])}

    def note(section, row):
        return notes.get((section, row), {})

    page1 = []
    for key, label, item, rows in PAGE1:
        out = []
        for r in rows:
            m_rate = _value(cells[prev], r, item, "actual")
            p_app = _value(cells[prev], r, item, "app")
            p_op = _value(cells[prev], r, item, "op")
            app = _value(cells[month], r, item, "app")
            op = _value(cells[month], r, item, "op")
            out.append({
                "row": r, "total": r in TOTALS,
                "ly_actual": _value(cells[ly], r, item, "actual"),
                "prev_app": p_app, "prev_op": p_op, "prev_mrate": m_rate,
                "ful_app": _pct(m_rate, p_app), "ful_op": _pct(m_rate, p_op),
                "app": app, "app_tpd": _tpd(app, days), "op": op, "op_tpd": _tpd(op, days),
                "remarks": note(key, r).get("remarks"),
            })
        page1.append({"key": key, "label": label, "rows": out})

    page2 = []
    for key, label, item, rate in PAGE2:
        out = []
        for r in PAGE2_ROWS:
            app = _value(cells[month], r, item, "app")
            op = _value(cells[month], r, item, "op")
            if r in TOTALS:
                coal_app = _sum([note(key, p).get("coal_req_app") for p in TOTALS[r]])
                coal_op = _sum([note(key, p).get("coal_req_op") for p in TOTALS[r]])
            else:
                coal_app, coal_op = note(key, r).get("coal_req_app"), note(key, r).get("coal_req_op")
            out.append({
                "row": r, "total": r in TOTALS, "app": app, "op": op,
                # Oven Pushing: the coal requirement per day; Sinter / Pig Iron: TPD
                "app_day": coal_app if rate else _tpd(app, days),
                "op_day": coal_op if rate else _tpd(op, days),
                "coal_req_app": coal_app if rate else None,
                "coal_req_op": coal_op if rate else None,
                "remarks": note(key, r).get("remarks"),
            })
        page2.append({"key": key, "label": label, "rate": rate, "rows": out})

    return {
        "month": month, "days": days,
        "labels": {"month": mon_label(month), "month_col": col_label(month),
                   "prev_col": col_label(prev), "ly_col": col_label(ly)},
        "page1": page1, "page2": page2,
        "ipt": manual.get("ipt", []), "stock": manual.get("stock", []),
        "stock_as_on": manual.get("stock_as_on"),
        "note": manual.get("note"),
        "updated_by": manual.get("updated_by"), "updated_at": manual.get("updated_at"),
    }


def manual_form(month: str) -> dict:
    """The entry form's data: the saved manual rows, or, when the month has
    none, the previous month's IPT and stock rows as a starting point
    (copied_from set) with empty remarks."""
    manual = rmisc.rmt_plan_manual(month)
    if manual is not None:
        return {"month": month, "copied_from": None, **manual}
    prev = month_utils.shift_month(month, -1)
    last = rmisc.rmt_plan_manual(prev) or {}
    return {"month": month, "copied_from": prev if last else None, "stock_as_on": None,
            "note": last.get("note"), "updated_by": None, "updated_at": None, "notes": [],
            "ipt": last.get("ipt", []), "stock": last.get("stock", [])}


def form_rows():
    """The rows the entry form offers remarks for: [(section, label, rows,
    has_coal)]."""
    return ([(k, label, rows, False) for k, label, _, rows in PAGE1]
            + [(k, label, PAGE2_ROWS, rate) for k, label, _, rate in PAGE2])
