"""
Blast Furnace Techno Report — furnace-wise export for an arbitrary custom
month range (each month plus the range's cumulative) or one or more full
financial years (Apr->March).

Reuses:
  - bf_benchmark_registry's furnace roster (SAIL_BF_UNITS_BY_PLANT) and
    parameter registry (BF_BENCHMARK_PARAMS/DYNAMIC_PARAM_KEYS) — the same
    ones the BF Benchmarking feature and Techno Manual Entry's BF-8/BF-5
    tabs already read/write, so this report's furnace list and parameter
    set/units/formatting stay identical to that feature with no 2nd copy.
  - api_bf_benchmark._sail_period_values for the two periods techno_data
    itself already stores pre-aggregated (a month's own actual, and
    Apr->that-month cumulative, via db._maybe_recompute_derived_params) —
    "annual" mode is just this, called once per FY.
  - techno_cumulative's per-parameter weighting rules (get_rule) and
    furnace-wise production weights (_unit_production) for "range" mode,
    which is NOT YTD-aligned so techno_data has no pre-computed figure for
    it — the same math the "Calculate Cumulative" modal and
    techno_period.py's plant-level custom-period report already use, just
    applied to one furnace directly instead of combined across a plant's
    candidate units.
  - techno_period._weighted_combine for the actual value/weight -> result
    math — pure, plant/furnace-agnostic, no reason to re-implement it.
"""
import calendar as _cal
import datetime as _dt
from typing import Dict, List, Optional

import db as _db
import techno_cumulative as _tc
from techno_period import _weighted_combine
from bf_benchmark_registry import BF_BENCHMARK_PARAMS, DYNAMIC_PARAM_KEYS, PARAM_BY_KEY, SAIL_BF_UNITS_BY_PLANT
from api_bf_benchmark import _sail_period_values
from page_bf_benchmark_export import _fmt as _fmt_bf_value

FURNACES = [
    {"key": f"{plant}:{unit}", "plant": plant, "unit": unit, "label": f"{plant} {unit}"}
    for plant, units in SAIL_BF_UNITS_BY_PLANT.items()
    for unit in units
]
FURNACE_BY_KEY = {f["key"]: f for f in FURNACES}

# Display-only param list for the frontend's picker — dynamic (monthly)
# params only; working_volume_m3 is a static per-furnace spec, not
# something a report over a time period computes.
# Production and Avg. Daily Prod aren't read from techno_data here: both come
# from the furnace's own rows in production_table (the monthly production
# uploads), Production shown in tonnes (the BF Benchmarking registry's unit is
# Million T) and Avg. Daily Prod = that production / calendar days.
_PRODUCTION_KEYS = {"production", "avg_daily_rate"}
_UNIT_OVERRIDES = {"production": "in T"}


def _report_param(p: Dict) -> Dict:
    return {**p, "unit": _UNIT_OVERRIDES.get(p["key"], p["unit"])}


REPORT_PARAMS = [
    {"key": p["key"], "label": p["label"], "unit": _UNIT_OVERRIDES.get(p["key"], p["unit"])}
    for p in BF_BENCHMARK_PARAMS if not p["static"]
]


def resolve_furnaces(keys: List[str]) -> List[Dict]:
    out = []
    for k in keys:
        f = FURNACE_BY_KEY.get(k)
        if f is None:
            raise ValueError(f"Unknown furnace: {k}")
        out.append(f)
    return out


def resolve_params(keys: Optional[List[str]]) -> List[Dict]:
    if not keys:
        return [_report_param(PARAM_BY_KEY[k]) for k in DYNAMIC_PARAM_KEYS]
    out = []
    for k in keys:
        p = PARAM_BY_KEY.get(k)
        if p is None or p.get("static"):
            raise ValueError(f"Unknown/unsupported parameter: {k}")
        out.append(_report_param(p))
    return out


def _month_label(ym: str) -> str:
    dt = _dt.datetime.strptime(ym, "%Y-%m")
    return dt.strftime("%b %Y")


def months_in_range(start_month: str, end_month: str) -> List[str]:
    """Inclusive [start_month, end_month] month list, both "YYYY-MM"."""
    start = _dt.datetime.strptime(start_month, "%Y-%m")
    end = _dt.datetime.strptime(end_month, "%Y-%m")
    if end < start:
        raise ValueError("end_month must not be before start_month")
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def fy_march_month(fy_end_year: int) -> str:
    """The March report_month for the FY ending calendar year `fy_end_year`
    (e.g. 2026 -> "2026-03", FY 2025-26) — techno_data's own "till_month" at
    that report_month already IS the full-FY Apr->Mar cumulative, per
    db._maybe_recompute_derived_params, so no separate annual aggregation
    is needed here."""
    return f"{fy_end_year}-03"


def _fy_start_year(ym: str) -> int:
    y, m = int(ym[:4]), int(ym[5:7])
    return y if m >= 4 else y - 1


def _furnace_range_values(plant: str, unit: str, param_keys: List[str], months: List[str],
                          month_cache: Optional[Dict[tuple, Dict]] = None) -> Dict[str, Dict]:
    """{param_key: {month: value}} for one furnace over `months` — one
    _sail_period_values call per month (it already returns every
    DYNAMIC_PARAM_KEYS figure for that month in one DB round-trip, plus the
    HM-Sulphur/Coke-Ash cross-unit fallbacks), so this costs len(months)
    round-trips total regardless of how many params are requested."""
    by_param: Dict[str, Dict[str, float]] = {k: {} for k in param_keys}
    for m in months:
        if month_cache is None:
            month_vals = _sail_period_values(plant, unit, m, "month")
        else:
            ck = (plant, unit, m)
            if ck not in month_cache:
                month_cache[ck] = _sail_period_values(plant, unit, m, "month")
            month_vals = month_cache[ck]
        for k in param_keys:
            v = month_vals.get(k)
            if v is not None:
                by_param[k][m] = v
    return by_param


def _range_cell(plant: str, unit: str, key: str, months: List[str],
                weight_cache: Dict[tuple, Dict[str, float]],
                month_cache: Optional[Dict[tuple, Dict]] = None) -> Dict:
    """One furnace/parameter combined over `months` — the cell dict
    (value/display/method_used/warnings) build_range_report shows."""
    method, basis = _tc.get_rule(key)
    monthly = _furnace_range_values(plant, unit, [key], months, month_cache)[key]
    if not monthly:
        return {"value": None, "display": "", "warnings": ["No data in this period."]}
    wkey = (plant, unit, tuple(months))
    if wkey not in weight_cache:
        weight_cache[wkey] = _tc._unit_production(plant, unit, months)
    production = weight_cache[wkey]
    # A month with no production that reports 0 is a shutdown month, not
    # data — left out, as techno_cumulative's YTD cumulative does.
    running = {m: v for m, v in monthly.items() if not (v == 0 and not production.get(m))}
    if running:
        monthly = running
    weights = production if basis else {}
    items = [(v, weights.get(m)) for m, v in monthly.items()]
    value, method_used = _weighted_combine(method, items)
    warnings = []
    if method_used != method and method in ("weighted", "harmonic"):
        warnings.append(
            "Production weight missing for one or more months — used simple average instead.")
    return {"value": value, "display": _fmt_bf_value(value, key), "method_used": method_used,
            "warnings": warnings}


def _furnace_production_t(plant: str, unit: str, months: List[str],
                          cache: Dict[tuple, Dict[str, float]]) -> Dict[str, float]:
    """{month: production in tonnes} for one furnace — production_table's
    furnace-wise month_actual ('000 t) via techno_cumulative._unit_production,
    which also covers a month missing there from the furnace's techno
    'production' figure (and, for a single-BF plant, the plant's Hot Metal)."""
    ck = (plant, unit, tuple(months))
    if ck not in cache:
        cache[ck] = {m: v * 1000.0 for m, v in _tc._unit_production(plant, unit, months).items()}
    return cache[ck]


def _production_cell(plant: str, unit: str, key: str, months: List[str],
                     cache: Dict[tuple, Dict[str, float]]) -> Dict:
    """Production (t, summed over `months`) or Avg. Daily Prod (that sum /
    the calendar days of every month in `months`, whether or not the furnace
    produced in it) for one furnace."""
    prod = _furnace_production_t(plant, unit, months, cache)
    if not prod:
        return {"value": None, "display": "", "warnings": ["No production data in this period."]}
    total = sum(prod.values())
    value = total if key == "production" else total / sum(_days(m) for m in months)
    warnings = []
    missing = [m for m in months if m not in prod]
    if missing:
        warnings.append("No production data for " + ", ".join(_month_label(m) for m in missing) + ".")
    return {"value": value, "display": int(round(value)), "warnings": warnings}


def _days(ym: str) -> int:
    return _cal.monthrange(int(ym[:4]), int(ym[5:7]))[1]


def build_range_report(furnaces: List[Dict], params: List[Dict], months: List[str]) -> Dict:
    """Custom (non-YTD-aligned) month range — one column per month (that
    month's own figure, read straight from techno_data), then, for a range of
    more than one month, a cumulative column over exactly these months:
    weighted/harmonic/summed/averaged per parameter's own techno_cumulative
    rule, using that furnace's own production during exactly these months
    as the weight (falls back to a plain average, with a warning, for any
    month the weight can't be resolved for — same fallback semantics as
    every other cumulative calc in this app)."""
    month_labels = [_month_label(m) for m in months]
    cum_label = f"{month_labels[0]} - {month_labels[-1]} (Cumulative)" if len(months) > 1 else None
    weight_cache: Dict[tuple, Dict[str, float]] = {}
    month_cache: Dict[tuple, Dict] = {}
    prod_cache: Dict[tuple, Dict[str, float]] = {}
    sections = []
    for pdef in params:
        key = pdef["key"]
        rows = []
        for f in furnaces:
            if key in _PRODUCTION_KEYS:
                values = {
                    label: _production_cell(f["plant"], f["unit"], key, [m], prod_cache)
                    for m, label in zip(months, month_labels)
                }
                if cum_label:
                    values[cum_label] = _production_cell(f["plant"], f["unit"], key, months, prod_cache)
                rows.append({"furnace": f["label"], "values": values})
                continue
            monthly = _furnace_range_values(f["plant"], f["unit"], [key], months, month_cache)[key]
            values = {
                label: {"value": monthly.get(m), "display": _fmt_bf_value(monthly.get(m), key), "warnings": []}
                for m, label in zip(months, month_labels)
            }
            if cum_label:
                values[cum_label] = _range_cell(f["plant"], f["unit"], key, months, weight_cache, month_cache)
            rows.append({"furnace": f["label"], "values": values})
        sections.append({"parameter": pdef["label"], "unit": pdef["unit"], "rows": rows})
    periods = month_labels + ([cum_label] if cum_label else [])
    return {"periods": periods, "furnaces": [f["label"] for f in furnaces], "sections": sections}


def build_direct_report(furnaces: List[Dict], params: List[Dict], periods: List[Dict]) -> Dict:
    """annual mode — every period here is a single
    (report_month, period) pair techno_data already has pre-aggregated
    (see _sail_period_values), so this is a straight read, no combining.

    periods: [{"label": str, "report_month": "YYYY-MM", "period": "month"|"till_month"}, ...]
    """
    cache: Dict[tuple, Dict[str, Optional[float]]] = {}
    weight_cache: Dict[tuple, Dict[str, float]] = {}
    month_cache: Dict[tuple, Dict] = {}

    def _values(plant, unit, report_month, period):
        ck = (plant, unit, report_month, period)
        if ck not in cache:
            cache[ck] = _sail_period_values(plant, unit, report_month, period)
        return cache[ck]

    prod_cache: Dict[tuple, Dict[str, float]] = {}

    def _period_months(p):
        if p["period"] == "month":
            return [p["report_month"]]
        return months_in_range(f"{_fy_start_year(p['report_month'])}-04", p["report_month"])

    sections = []
    for pdef in params:
        key = pdef["key"]
        rows = []
        for f in furnaces:
            values = {}
            for p in periods:
                if key in _PRODUCTION_KEYS:
                    values[p["label"]] = _production_cell(f["plant"], f["unit"], key, _period_months(p), prod_cache)
                    continue
                v = _values(f["plant"], f["unit"], p["report_month"], p["period"]).get(key)
                if v is None and p["period"] == "till_month":
                    # No stored Apr->month cumulative for this furnace/param
                    # (e.g. the plant's upload only carried month figures) —
                    # compute it from the monthly values the same way
                    # "range" mode does, instead of showing a blank.
                    ytd = months_in_range(f"{_fy_start_year(p['report_month'])}-04", p["report_month"])
                    cellv = _range_cell(f["plant"], f["unit"], key, ytd, weight_cache, month_cache)
                    if cellv["value"] is not None:
                        cellv["warnings"] = cellv["warnings"] + [
                            "No stored cumulative — computed from the monthly values."]
                        values[p["label"]] = cellv
                        continue
                values[p["label"]] = {"value": v, "display": _fmt_bf_value(v, key), "warnings": []}
            rows.append({"furnace": f["label"], "values": values})
        sections.append({"parameter": pdef["label"], "unit": pdef["unit"], "rows": rows})
    return {"periods": [p["label"] for p in periods], "furnaces": [f["label"] for f in furnaces], "sections": sections}
