"""
"Cost of Production" -- standalone report (/reports/cost-production): Rs/T
cost of production of BF Coke, Sinter, Hot Metal, Crude Steel and Saleable
Steel for every plant (BSP/DSP/RSP/BSL/ISP and SAIL 5 ISPs), monthly or
yearly. Not part of the monthly PDF (the Cost Trend pages were dropped from
it, 2026-10-29).

Reads the Cost Trend Entry tables (repo/cost_trend.py): cost_trend_monthly
(month and Apr-to-month "till month" figure per report month) and
cost_trend_annual (one figure per closed FY). Variable and Fixed cost are
entered; Total is Variable + Fixed, as on the old Cost Trend pages
(page_cost_trend.py). BF Coke and Sinter mostly carry one lump figure under
Variable.

  monthly: one column per month of the chosen FY, April to the last month
           with any entry, then that month's till-month figure.
  yearly:  one column per FY from _FIRST_FY on: cost_trend_annual's figure,
           or for an FY without one (the running FY) the till-month figure
           of its last month with an entry, labelled with that period.
"""
import datetime as _dt

import month_utils
from repo import cost_trend as rct

PRODUCTS = [
    ("COKE", "BF Coke"),
    ("SINTER", "Sinter"),
    ("HM", "Hot Metal"),
    ("CS", "Crude Steel"),
    ("SS", "Saleable Steel"),
]
PLANT_LABEL = {"BSP": "BSP", "DSP": "DSP", "RSP": "RSP", "BSL": "BSL", "ISP": "ISP", "SAIL": "SAIL 5 ISPs"}
COST_TYPE_LABEL = {"TOTAL": "Total Cost", "VARIABLE": "Variable Cost", "FIXED": "Fixed Cost"}

# Earliest FY with entered annual figures (Report_format/COST TREND.xlsx).
_FIRST_FY = 2020

_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fy_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _fy_start(fy: str) -> int:
    return int(fy[:4])


def _fy_months(fy: str) -> list:
    return month_utils.get_fy_months(f"{_fy_start(fy)}-04")


def fy_options(today: _dt.date = None) -> list:
    """Every FY from _FIRST_FY to the running one, newest first."""
    today = today or _dt.date.today()
    current = today.year if today.month >= 4 else today.year - 1
    return [fy_label(y) for y in range(current, _FIRST_FY - 1, -1)]


def month_label(m: str) -> str:
    return f"{_MON[int(m[5:7])]}'{m[2:4]}"


def till_label(last_month: str) -> str:
    """Apr-to-month label, e.g. "Apr-Sep'26" ("Apr'26" for April itself)."""
    if last_month[5:7] == "04":
        return month_label(last_month)
    return f"Apr-{_MON[int(last_month[5:7])]}'{last_month[2:4]}"


def _total(v, f):
    if v is None and f is None:
        return None
    return float(v or 0) + float(f or 0)


def _num(v):
    return None if v is None else float(v)


def _cells(get):
    """{cost_type: value} for one plant/period; get(cost_type) -> entered value."""
    v, f = _num(get("VARIABLE")), _num(get("FIXED"))
    return {"TOTAL": _total(v, f), "VARIABLE": v, "FIXED": f}


def _has_entry(month_data: dict, field: str) -> bool:
    return any(cell.get(field) is not None
               for by_plant in month_data.values() for cell in by_plant.values())


def _blocks(columns: list) -> list:
    """columns: [{plant: {cost_type: value}}] -> Total/Variable/Fixed blocks
    of one row per plant, one value per column."""
    return [{"cost_type": ct, "label": COST_TYPE_LABEL[ct],
             "rows": [{"plant": PLANT_LABEL[p], "values": [col.get(p, {}).get(ct) for col in columns]}
                      for p in rct.COST_TREND_PLANTS]}
            for ct in rct.COST_TREND_COST_TYPES]


def _last_month(monthly: dict, months: list, field: str = "month"):
    """Last of months with any entry (across products) in field."""
    with_data = [m for m in months if any(_has_entry(monthly[p].get(m, {}), field) for p in monthly)]
    return with_data[-1] if with_data else None


def _till_source(d: dict, till_m: str, months: list):
    """(month, note): the product's till-month figure at till_m, or, when it
    has none there, at its own last earlier month with one (noted)."""
    if _has_entry(d.get(till_m, {}), "till_month"):
        return till_m, None
    own = [m for m in months if m <= till_m and _has_entry(d.get(m, {}), "till_month")]
    if not own:
        return till_m, None
    return own[-1], f"{till_label(till_m)} column shows {till_label(own[-1])} (no {month_label(till_m)} entry yet)"


def monthly(fy: str) -> dict:
    months = _fy_months(fy)
    data = {code: rct.get_cost_trend_monthly(code, months) for code, _ in PRODUCTS}
    last = _last_month(data, months, "month")
    shown = [m for m in months if last and m <= last]
    till_m = _last_month(data, [m for m in months if not last or m <= last], "till_month")
    periods = [{"key": m, "label": month_label(m), "kind": "month"} for m in shown]
    if till_m:
        periods.append({"key": f"till:{till_m}", "label": till_label(till_m), "kind": "till"})
    products = []
    for code, name in PRODUCTS:
        d = data[code]
        cols, note = [], None
        for m in shown:
            cols.append({p: _cells(lambda ct, p=p, m=m: d.get(m, {}).get(ct, {}).get(p, {}).get("month"))
                         for p in rct.COST_TREND_PLANTS})
        if till_m:
            src, note = _till_source(d, till_m, months)
            cols.append({p: _cells(lambda ct, p=p: d.get(src, {}).get(ct, {}).get(p, {}).get("till_month"))
                         for p in rct.COST_TREND_PLANTS})
        products.append({"code": code, "name": name, "note": note, "blocks": _blocks(cols)})
    return {"periods": periods, "products": products}


def yearly(today: _dt.date = None) -> dict:
    fys = list(reversed(fy_options(today)))
    annual = {code: rct.get_cost_trend_annual(code, fys) for code, _ in PRODUCTS}
    all_months = [m for fy in fys for m in _fy_months(fy)]
    monthly_data = {code: rct.get_cost_trend_monthly(code, all_months) for code, _ in PRODUCTS}

    def has_annual(code, fy):
        return any(v is not None for by_plant in annual[code].get(fy, {}).values() for v in by_plant.values())

    # One source per FY for every product: its annual figure when any
    # product has one, else the till-month figure of its last month.
    periods, sources = [], []
    for fy in fys:
        if any(has_annual(code, fy) for code, _ in PRODUCTS):
            periods.append({"key": fy, "label": fy, "kind": "annual"})
            sources.append(("annual", fy))
            continue
        last = _last_month(monthly_data, _fy_months(fy), "till_month")
        if last:
            periods.append({"key": f"till:{last}", "label": f"{fy} ({till_label(last)})", "kind": "till"})
            sources.append(("till", last))
    products = []
    for code, name in PRODUCTS:
        cols, notes = [], []
        for kind, key in sources:
            if kind == "annual":
                a = annual[code].get(key, {})
                cols.append({p: _cells(lambda ct, p=p, a=a: a.get(ct, {}).get(p)) for p in rct.COST_TREND_PLANTS})
            else:
                src, note = _till_source(monthly_data[code], key, all_months)
                if note:
                    notes.append(note)
                md = monthly_data[code].get(src, {})
                cols.append({p: _cells(lambda ct, p=p, md=md: md.get(ct, {}).get(p, {}).get("till_month"))
                             for p in rct.COST_TREND_PLANTS})
        products.append({"code": code, "name": name, "note": "; ".join(notes) or None, "blocks": _blocks(cols)})
    return {"periods": periods, "products": products}


def generate(view: str, fy: str = None, products: list = None, today: _dt.date = None) -> dict:
    """view: "monthly" (needs fy, default the running FY) or "yearly";
    products: product codes to keep (default all, in PRODUCTS order)."""
    options = fy_options(today)
    if view == "monthly":
        fy = fy or options[0]
        out = monthly(fy)
        title = f"Cost of Production - Month-wise {fy}"
    else:
        fy = None
        out = yearly(today)
        title = "Cost of Production - Year-wise"
    if products:
        out["products"] = [p for p in out["products"] if p["code"] in products]
    return {"view": view, "fy": fy, "fy_options": options, "title": title, "unit": "Rs/T", **out}
