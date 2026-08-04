"""
Custom-period (quarter / half-year / any arbitrary month range) aggregation
for the 12 "major" techno-economic parameters — the same set page 27 shows
(see page_techno.generate_major_techno_from_db), but computed fresh over any
set of months instead of only April-to-report-month YTD or a full FY.

Backs the /api/techno-custom-period* routes (the "Custom Period" mode of the
Techno Custom Report, under External Reports).

This module only ADDS a generalized-months variant of techno_cumulative.py's
weighted/harmonic/sum/average math — it never modifies techno_cumulative.py
itself, since that module backs the live "Calculate Cumulative" modal and
must stay stable. It reuses techno_cumulative's weight-resolution helpers
(_plant_production, _unit_production, get_rule, SHOP_UNITS,
PLANT_WEIGHT_ITEMS) and page_techno's plant/shop topology constants
(PLANT_ORDER, BF_UNITS, SMS_UNIT_MAP, SMS_N_SHOPS, BF_SAIL_SPECS,
SMS_PARAM_KEYS, KEY_ALIASES, _VERIFY_SMS_PRODUCTION_ITEMS) rather than
re-hardcoding a 3rd/4th copy of any of it.
"""

from typing import Dict, List, Optional

import db as _db
import page_techno as _pt
import techno_cumulative as _tc

PLANTS = list(_pt.PLANT_ORDER)  # ["BSP", "DSP", "RSP", "BSL", "ISP"]

# Display unit string per major parameter (cosmetic only — matches page 27's
# raw_sections unit_str args in page_techno.py).
_UNIT_STR = {
    "Coal to Hot Metal": "", "Coke Rate": "kg/thm", "Nut Coke Rate": "kg/thm",
    "CDI Rate": "kg/thm", "Fuel Rate": "kg/thm", "Sinter in Burden": "%",
    "Pellet in Burden": "%", "BF Productivity": "t/m³/day",
    "Hot Metal Consumption": "kg/tcs", "Scrap Consumption": "kg/tcs",
    "TMI": "kg/tcs", "Specific Energy Consumption": "Gcal/tcs",
}

# SMS-level param display name -> the CUMULATIVE_RULES key that governs its
# method/weight-basis (all three happen to be "weighted"/"crude_steel", but
# resolving through get_rule() keeps this in sync with techno_cumulative.py
# instead of hardcoding the method here too).
_SMS_RULE_KEY = {
    "Hot Metal Consumption": "specific_hm_consumption",
    "Scrap Consumption": "specific_scrap_consumption",
    "TMI": "tmi",
}

_HM_ALIASES = ["specific_hm_consumption", "hot_metal_consumption"]
_SCRAP_ALIASES = ["specific_scrap_consumption", "scrap_consumption"]
_TMI_ALIASES = ["tmi"]


# "Coal to Hot Metal" is the internal name (matches BF_SAIL_SPECS's key,
# and is what page_techno._fmt_param's precision rules are keyed on) but page
# 27 — and this module's own output — renames it to "Coal to Hot Metal
# Ratio" for display. `display_name` is what's shown/matched externally
# (build_period_report's params filter, the frontend's picker), so the two
# modes of the Techno Custom Report agree on one name for this parameter;
# `name` stays the internal identity used for _fmt_param/BF_SAIL_SPECS/caching.
_DISPLAY_RENAME = {"Coal to Hot Metal": "Coal to Hot Metal Ratio"}


def _build_major_params() -> List[Dict]:
    """The 12-row registry, built from page_techno's already-exported
    BF_SAIL_SPECS/SMS_PARAM_KEYS rather than a 4th hardcoded copy."""
    params = []
    for name, (key, src_units, _basis, _harm, zero_fill) in _pt.BF_SAIL_SPECS.items():
        params.append({
            "name": name, "display_name": _DISPLAY_RENAME.get(name, name),
            "key": key, "kind": "unit",
            "src_units": src_units, "unit_str": _UNIT_STR.get(name, ""),
            "zero_fill_plants": zero_fill or set(),
        })
    for name in _pt.SMS_PARAM_KEYS:
        params.append({
            "name": name, "display_name": _DISPLAY_RENAME.get(name, name),
            "key": _SMS_RULE_KEY[name], "kind": "sms",
            "src_units": None, "unit_str": _UNIT_STR.get(name, ""),
            "zero_fill_plants": set(),
        })
    return params


MAJOR_TECHNO_PARAMS = _build_major_params()
MAJOR_TECHNO_PARAM_NAMES = [p["display_name"] for p in MAJOR_TECHNO_PARAMS]


def _weighted_combine(method: str, items: List[tuple]):
    """items: [(value, weight_or_None), ...]. Returns (result, method_used).

    method_used differs from `method` only when a weighted/harmonic combine
    fell back to a plain average because one or more items had no usable
    weight — mirrors techno_cumulative.compute_cumulative_from_values's
    fallback semantics (real numbers where possible, never a silently
    dropped item)."""
    items = [(v, w) for v, w in items if v is not None]
    if not items:
        return None, method

    if method in ("weighted", "harmonic"):
        usable = [(v, w) for v, w in items
                  if w is not None and w > 0 and not (method == "harmonic" and v <= 0)]
        if len(usable) < len(items):
            vals = [v for v, _ in items]
            return round(sum(vals) / len(vals), 4), "average"
        sum_w = sum(w for _, w in usable)
        if sum_w <= 0:
            vals = [v for v, _ in items]
            return round(sum(vals) / len(vals), 4), "average"
        if method == "weighted":
            sum_p = sum(v * w for v, w in usable)
            return round(sum_p / sum_w, 4), "weighted"
        sum_t = sum(w / v for v, w in usable)
        return (round(sum_w / sum_t, 4) if sum_t else None), "harmonic"

    if method == "sum":
        return round(sum(v for v, _ in items), 4), "sum"

    vals = [v for v, _ in items]
    return round(sum(vals) / len(vals), 4), "average"


def _get_month_data(dcache: Optional[dict], plant: str, month: str) -> Dict:
    """All units' techno_data for one (plant, month) — cached across the
    whole build_period_report call so overlapping periods (H1 covers the
    exact same months as Q1+Q2) and every one of the 12 params never
    re-query the same (plant, month) row twice. Measured impact: a 6-plant,
    12-param, Q1-Q4+H1+H2 request went from ~40s (one DB round-trip per
    plant/month/candidate-unit, several hundred of them) to a couple of
    seconds — the difference between succeeding and hitting Next.js's own
    ~30s proxy timeout (which shows up to the frontend as a bare "HTTP 500"
    with no detail, since it's the proxy giving up, not the backend
    responding with one)."""
    key = (plant, month)
    if dcache is None:
        return _db.get_techno_data(plant, month)
    if key not in dcache:
        dcache[key] = _db.get_techno_data(plant, month)
    return dcache[key]


def _plant_month_values(plant: str, param_key: str, src_units: List[str],
                         months: List[str], _dcache: Optional[dict] = None) -> Dict[str, tuple]:
    """{month: (value, unit_used)} for a "unit"-kind param — tries each
    candidate unit in `src_units` in order, PER MONTH (a plant's value can
    legitimately resolve from a different candidate unit in different
    months — mirrors page_techno._gv_multi's per-month fallback), and checks
    KEY_ALIASES for legacy key spellings the same way page_techno._gv does."""
    aliases = [param_key] + _pt.KEY_ALIASES.get(param_key, [])
    out = {}
    for m in months:
        month_data = _get_month_data(_dcache, plant, m)
        for u in src_units:
            ud = month_data.get(u, {}).get("month", {})
            v = None
            for k in aliases:
                v = ud.get(k)
                if v is not None:
                    break
            if v is not None:
                try:
                    out[m] = (float(v), u)
                except (TypeError, ValueError):
                    pass
                break
    return out


def _sms_month_value(plant: str, shop: str, month: str, param_name: str,
                      _dcache: Optional[dict] = None) -> Optional[float]:
    """One SMS-shop's value for `param_name` in a single month — handles
    TMI's HM+Scrap fallback and DSP's alternate key spellings, mirroring
    page_techno.py's sms_section/_tmi helpers."""
    ud = _get_month_data(_dcache, plant, month).get(shop, {}).get("month", {})

    def pick(aliases):
        for k in aliases:
            v = ud.get(k)
            if v is not None:
                return v
        return None

    if param_name == "TMI":
        v = pick(_TMI_ALIASES)
        if v is not None:
            return v
        hm = pick(_HM_ALIASES)
        sc = pick(_SCRAP_ALIASES)
        if hm is not None and sc is not None:
            return hm + sc
        return hm if hm is not None else sc
    if param_name == "Hot Metal Consumption":
        return pick(_HM_ALIASES)
    if param_name == "Scrap Consumption":
        return pick(_SCRAP_ALIASES)
    return None


def _shop_period_weights(plant: str, shop: str, months: List[str]) -> Dict[str, float]:
    """{month: Crude Steel weight} for one SMS shop over `months` — that
    shop's own Crude Steel production_table item(s) (per
    page_techno._VERIFY_SMS_PRODUCTION_ITEMS), falling back to
    plant_CS_that_month / n_shops for months the shop-specific item doesn't
    cover. Generalizes page_techno._shop_weight's fallback from a single
    ref_month to an arbitrary month list."""
    items = _pt._VERIFY_SMS_PRODUCTION_ITEMS.get((plant, shop))
    own: Dict[str, float] = {}
    if items:
        conn = _db.connect()
        cur = conn.cursor()
        ph_m = ",".join("?" * len(months))
        ph_i = ",".join("?" * len(items))
        cur.execute(
            f"SELECT report_month, month_actual FROM production_table "
            f"WHERE plant_name=? AND item_name IN ({ph_i}) AND report_month IN ({ph_m})",
            [plant, *items, *months])
        for rm, v in cur.fetchall():
            if v is not None:
                own[rm] = own.get(rm, 0.0) + float(v)
        conn.close()

    plant_cs = _tc._plant_production(plant, _tc.PLANT_WEIGHT_ITEMS["crude_steel"], months)
    n = _pt.SMS_N_SHOPS.get(plant, 1)
    out = {}
    for m in months:
        if own.get(m, 0) > 0:
            out[m] = own[m]
        elif plant_cs.get(m, 0) > 0:
            out[m] = plant_cs[m] / n
    return out


def plant_period_value(plant: str, param_def: Dict, months: List[str],
                        _cache: Optional[dict] = None,
                        _dcache: Optional[dict] = None) -> Dict:
    """One plant's aggregated value for `param_def` over an arbitrary
    `months` list — the single-level (within-plant, month-to-plant) weighted/
    harmonic/sum/average combine, generalizing
    techno_cumulative.compute_cumulative_from_values from always-YTD to any
    period."""
    cache_key = (plant, param_def["name"], tuple(months))
    if _cache is not None and cache_key in _cache:
        return _cache[cache_key]

    key = param_def["key"]
    method, basis = _tc.get_rule(key)
    warnings: List[str] = []

    if param_def["kind"] == "sms":
        shops = _pt.SMS_UNIT_MAP.get(plant, [])
        items = []
        unit_used = set()
        for shop in shops:
            shop_weights = None
            for m in months:
                v = _sms_month_value(plant, shop, m, param_def["name"], _dcache=_dcache)
                if v is None:
                    continue
                if shop_weights is None:
                    shop_weights = _shop_period_weights(plant, shop, months)
                items.append((float(v), shop_weights.get(m)))
                unit_used.add(shop)
        if not items:
            result = {"value": None, "display": "", "method_used": method,
                       "unit_used": [], "warnings": ["No data in this period."]}
        else:
            value, method_used = _weighted_combine(method, items)
            if method_used != method and method in ("weighted", "harmonic"):
                warnings.append(
                    "Production weight missing for one or more shop-months "
                    "— used simple average instead.")
            result = {"value": value, "display": _pt._fmt_param(value, param_def["name"]),
                       "method_used": method_used,
                       "unit_used": sorted(unit_used), "warnings": warnings}
        if _cache is not None:
            _cache[cache_key] = result
        return result

    # kind == "unit"
    monthly = _plant_month_values(plant, key, param_def["src_units"], months, _dcache=_dcache)
    if not monthly:
        result = {"value": None, "display": "", "method_used": method,
                   "unit_used": [], "warnings": ["No data in this period."]}
        if _cache is not None:
            _cache[cache_key] = result
        return result

    weights: Dict[str, float] = {}
    if basis:
        item = _tc.PLANT_WEIGHT_ITEMS[basis]
        # Weight source depends on which unit each month's value actually
        # came from — group by resolved unit and use the matching source,
        # exactly like techno_cumulative.compute_cumulative_from_values'
        # `if unit in SHOP_UNITS` branch (BF_Shop/General -> plant-level
        # production; BF-5 -> furnace-wise, with its own SINGLE_BF_PLANTS
        # fallback to plant Hot Metal already built into _unit_production).
        by_unit: Dict[str, List[str]] = {}
        for m, (_v, u) in monthly.items():
            by_unit.setdefault(u, []).append(m)
        for u, u_months in by_unit.items():
            if u in _tc.SHOP_UNITS:
                weights.update(_tc._plant_production(plant, item, u_months))
            else:
                weights.update(_tc._unit_production(plant, u, u_months))

    items = [(v, weights.get(m)) for m, (v, _u) in monthly.items()]
    value, method_used = _weighted_combine(method, items)
    if method_used != method and method in ("weighted", "harmonic"):
        warnings.append(
            "Production weight missing for one or more months — used "
            "simple average instead.")
    result = {"value": value, "display": _pt._fmt_param(value, param_def["name"]),
               "method_used": method_used,
               "unit_used": sorted({u for _, u in monthly.values()}),
               "warnings": warnings}
    if _cache is not None:
        _cache[cache_key] = result
    return result


def sail_period_value(param_def: Dict, months: List[str],
                       _cache: Optional[dict] = None,
                       _dcache: Optional[dict] = None) -> Dict:
    """SAIL-wide rollup: plant_period_value() for each of the 5 plants,
    weighted by that plant's own HM/CS production summed over `months` —
    mirrors page_techno._bf_sail/_sms_sail's plant-level weighting. Unlike
    page 27's SAIL row, this is always computed fresh — there is no
    "published" SAIL figure for an arbitrary custom period to prefer."""
    key = param_def["key"]
    method, basis = _tc.get_rule(key)
    item = _tc.PLANT_WEIGHT_ITEMS[basis]

    zero_fill = param_def.get("zero_fill_plants") or set()
    items = []
    for plant in PLANTS:
        pv = plant_period_value(plant, param_def, months, _cache=_cache, _dcache=_dcache)
        val = pv["value"]
        if val is None:
            if plant not in zero_fill:
                continue
            # This plant structurally doesn't report this parameter (e.g.
            # DSP's sinter-only burden mix never carries a Pellet in Burden
            # figure) rather than merely "hasn't submitted it yet" — count it
            # as a real zero so its production still weighs down the SAIL
            # average, matching page_techno._bf_sail's zero_fill_plants.
            val = 0.0
        w = sum(_tc._plant_production(plant, item, months).values())
        items.append((val, w if w > 0 else None))

    if not items:
        return {"value": None, "display": "", "method_used": method,
                "warnings": ["No plant data in this period."]}

    value, method_used = _weighted_combine(method, items)
    warnings = []
    if method_used != method and method in ("weighted", "harmonic"):
        warnings.append(
            "Production weight missing for one or more plants — used "
            "simple average across plants instead.")
    return {"value": value, "display": _pt._fmt_param(value, param_def["name"]),
            "method_used": method_used, "warnings": warnings}


def build_period_report(plants: List[str], params: Optional[List[str]],
                         periods: List[Dict]) -> Dict:
    """Top-level orchestrator for the Custom Period mode.

    plants: plant codes and/or "SAIL".
    params: display names to include (subset of MAJOR_TECHNO_PARAM_NAMES);
            falsy/empty = all 12.
    periods: [{"label": str, "months": [str, ...]}, ...] — the frontend
             resolves quarter/half/custom month-lists client-side and posts
             the raw month lists here; this module stays agnostic of
             quarter/FY concepts.

    Returns {"periods": [label, ...],
             "sections": [{"parameter", "unit",
                            "rows": [{"plant", "values": {label: {...}}}]}]}
    """
    wanted = set(params) if params else None
    cache: dict = {}
    # Raw techno_data cache, keyed (plant, month) — shared across every
    # param/plant/period in this one request so Q1..Q4 and the H1/H2 that
    # duplicate their months never re-query the same row. See _get_month_data.
    dcache: dict = {}
    sections = []
    for pdef in MAJOR_TECHNO_PARAMS:
        if wanted is not None and pdef["display_name"] not in wanted:
            continue
        rows = []
        for plant in plants:
            values = {}
            for period in periods:
                months = period["months"]
                if plant == "SAIL":
                    values[period["label"]] = sail_period_value(pdef, months, _cache=cache, _dcache=dcache)
                else:
                    values[period["label"]] = plant_period_value(plant, pdef, months, _cache=cache, _dcache=dcache)
            rows.append({"plant": plant, "values": values})
        sections.append({
            "parameter": pdef["display_name"], "unit": pdef["unit_str"], "rows": rows,
        })
    return {"periods": [p["label"] for p in periods], "sections": sections}
