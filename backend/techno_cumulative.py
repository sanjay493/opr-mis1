"""
Global YTD-cumulative calculation rules for techno-economic parameters.

Single source of truth for HOW a parameter's April→month cumulative is
computed. Import `compute_cumulative_preview` (full breakdown with steps)
or `CUMULATIVE_RULES` wherever a cumulative is needed.

Methods:
  weighted  — Σ(month value × weight) ÷ Σ(weight)
  harmonic  — Σ(weight) ÷ Σ(weight ÷ month value)      (e.g. BF productivity)
  sum       — Σ(month values)                            (extensive totals)
  (default) — simple average, for parameters not configured here

Weight basis:
  'hm'          — Hot Metal production
  'crude_steel' — Total Crude Steel production

Weight source per month:
  Shop-level units (SHOP_UNITS) — total PLANT production from production_table
  ('Hot Metal' / 'Total Crude Steel' item).
  Any other unit — furnace-wise production from production_table (item_name =
  unit name, 'BF-1' or 'BF#8' spelling), falling back to the unit's own
  monthly 'production' techno parameter for months not covered there, and —
  for a single-furnace plant (SINGLE_BF_PLANTS, e.g. ISP's BF-5, where the
  furnace IS the whole BF shop) — falling back once more to the plant's own
  'Hot Metal' item, since it's identical to that one furnace's production.

  The cumulative must always cover EVERY month (Apr→report_month) that has a
  value: if any valued month lacks a weight, the calculation falls back to the
  simple average of all monthly values (reported in warnings) rather than
  weighting a subset of months.
"""

import sqlite3
from typing import Dict, Optional

import db as _db
from plant_registry import PLANT_UNITS

# param_key -> (method, weight_basis). Add new parameters here.
CUMULATIVE_RULES = {
    # HM-production weighted average
    "coke_rate":        ("weighted", "hm"),
    "slag_rate":        ("weighted", "hm"),
    "nut_coke_rate":    ("weighted", "hm"),
    "cdi":              ("weighted", "hm"),
    "fuel_rate":        ("weighted", "hm"),
    "coal_to_hm":       ("weighted", "hm"),
    "o2_enrichment":    ("weighted", "hm"),
    "sinter_in_burden": ("weighted", "hm"),
    "pellet_in_burden": ("weighted", "hm"),
    # HM-weighted harmonic mean
    "bf_productivity":  ("harmonic", "hm"),
    # Crude-steel-production weighted average
    "specific_hm_consumption":     ("weighted", "crude_steel"),
    "specific_scrap_consumption":  ("weighted", "crude_steel"),
    "tmi":                         ("weighted", "crude_steel"),
    "specific_energy_consumption": ("weighted", "crude_steel"),
    # Extensive totals — plain sum
    "production":        ("sum", None),
    "coke_production":   ("sum", None),
    "sinter_production": ("sum", None),
    "water_consumption": ("sum", None),
}

# production_table item used when the weight comes from PLANT production
PLANT_WEIGHT_ITEMS = {"hm": "Hot Metal", "crude_steel": "Total Crude Steel"}

# Shop/plant-level aggregate units — cumulative uses total plant production
# (individual furnaces still weight by their own monthly 'production' param)
SHOP_UNITS = {"BF_Shop", "SMS", "SMS-1", "SMS-2", "SMS-3", "SMS-I", "SMS-II",
              "General"}

# Plants whose single registered BF *is* the whole shop (plant_registry.py:
# "single BF: furnace == shop" — currently just ISP's BF-5). Their furnace's
# production_table row is never populated separately from the plant-level
# 'Hot Metal' item, since there is nothing to distinguish it from — the two
# are the same number. Derived from PLANT_UNITS so a newly single-furnace
# plant is picked up automatically.
def _single_bf_plants() -> set:
    counts: Dict[str, int] = {}
    for plant, unit_type, _unit_name, is_shop, *_ in PLANT_UNITS:
        if unit_type == "BF" and not is_shop:
            counts[plant] = counts.get(plant, 0) + 1
    return {p for p, c in counts.items() if c == 1}


SINGLE_BF_PLANTS = _single_bf_plants()


def get_rule(param_key: str):
    """Return (method, weight_basis); default is simple average, no weight."""
    return CUMULATIVE_RULES.get(param_key, ("average", None))


def _plant_production(plant: str, item: str, months) -> Dict[str, float]:
    """{month: production} for a plant-level item from production_table."""
    conn = _db.connect()
    cur = conn.cursor()
    ph = ",".join("?" * len(months))
    cur.execute(
        f"SELECT report_month, month_actual FROM production_table "
        f"WHERE plant_name=? AND item_name=? AND report_month IN ({ph})",
        [plant, item, *months])
    weights = {m: v for m, v in cur.fetchall() if v is not None and v > 0}
    conn.close()
    return weights


def _unit_production(plant: str, unit: str, months,
                     current_production: Optional[float] = None,
                     report_month: str = "") -> Dict[str, float]:
    """{month: production ('000 t)} for a unit.

    Primary source: furnace-wise rows in production_table (item_name equal to
    the unit name — 'BF-1' or the 'BF#8' spelling), which the monthly
    production uploads populate for the whole FY. Months not covered there
    fall back to the unit's own techno 'production' parameter (tonnes,
    converted to '000 t so both sources weigh consistently). For a
    single-furnace plant (SINGLE_BF_PLANTS — e.g. ISP's BF-5), the furnace IS
    the whole BF shop, so any month still missing a weight after those two
    falls back once more to the plant's own 'Hot Metal' production_table
    item — the same source SHOP_UNITS already use, and identical to the
    furnace's own production since there is only one furnace.
    current_production (unsaved form value, tonnes) takes precedence for
    report_month."""
    candidates = [unit]
    if unit.startswith("BF-"):
        candidates.append("BF#" + unit[3:])

    conn = _db.connect()
    cur = conn.cursor()
    ph_m = ",".join("?" * len(months))
    ph_i = ",".join("?" * len(candidates))
    cur.execute(
        f"SELECT report_month, month_actual FROM production_table "
        f"WHERE plant_name=? AND item_name IN ({ph_i}) AND report_month IN ({ph_m})",
        [plant, *candidates, *months])
    weights = {m: v for m, v in cur.fetchall() if v is not None and v > 0}
    conn.close()

    for m in months:
        if m in weights:
            continue
        ud = _db.get_techno_data(plant, m, unit).get(unit, {})
        v = ud.get("month", {}).get("production")
        if v is not None and v > 0:
            weights[m] = v / 1000.0   # techno production is t; table is '000 t

    if unit.startswith("BF-") and plant in SINGLE_BF_PLANTS:
        missing = [m for m in months if m not in weights]
        if missing:
            weights.update(_plant_production(plant, "Hot Metal", missing))

    if current_production is not None and current_production > 0 and report_month:
        weights[report_month] = current_production / 1000.0
    return weights


def compute_cumulative_preview(
    plant: str,
    unit: str,
    param_key: str,
    report_month: str,
    current_value: Optional[float] = None,
    current_production: Optional[float] = None,
) -> Dict:
    """
    Compute the April→report_month cumulative for ONE parameter with a full
    step-by-step breakdown (rows, steps, warnings) so the user can verify it.
    Monthly values are read from techno_data (param_key must be stored
    directly under the unit's "month" dict).

    current_value       — unsaved form Month Value for report_month (overrides DB)
    current_production  — unsaved form 'production' Month Value (used as the
                          report_month weight for unit-wise weighting)

    Raises ValueError with a user-readable message when nothing can be computed.
    """
    plant = plant.upper()
    months = _db.get_ytd_months(report_month)   # Apr → report_month inclusive
    warnings = []

    # Monthly parameter values; the form value takes precedence for report_month
    values: Dict[str, float] = {}
    for m in months:
        if m == report_month and current_value is not None:
            v = current_value
        else:
            ud = _db.get_techno_data(plant, m, unit).get(unit, {})
            v = ud.get("month", {}).get(param_key)
        if v is None:
            continue
        try:
            values[m] = float(v)
        except (TypeError, ValueError):
            # Non-numeric stored value (e.g. a 'HH:MM' time) — cannot average
            warnings.append(f"{m}: non-numeric value {v!r} — excluded.")

    return compute_cumulative_from_values(
        plant, unit, param_key, report_month, values,
        current_production=current_production, warnings=warnings,
    )


def compute_cumulative_from_values(
    plant: str,
    unit: str,
    param_key: str,
    report_month: str,
    values: Dict[str, float],
    current_production: Optional[float] = None,
    warnings: Optional[list] = None,
) -> Dict:
    """
    Compute the April→report_month cumulative for ONE parameter from an
    already-assembled {month: value} dict, with the same step-by-step
    breakdown as compute_cumulative_preview (which is now a thin wrapper
    around this that reads `values` from techno_data directly).

    Use this instead of compute_cumulative_preview when param_key isn't
    stored under its own key in techno_data and the caller must assemble
    the monthly series itself — e.g. TMI, which is stored directly when
    reported but otherwise computed per-month as Hot Metal + Scrap
    Consumption.

    current_production — unsaved form 'production' Month Value (used as the
                         report_month weight for unit-wise weighting)
    warnings — pre-existing warnings to fold into the result (e.g. from the
              caller's own value assembly)

    Raises ValueError with a user-readable message when nothing can be computed.
    """
    plant = plant.upper()
    months = _db.get_ytd_months(report_month)   # Apr → report_month inclusive
    warnings = list(warnings) if warnings else []

    if report_month not in values:
        warnings.append(
            f"No Month Value for {report_month} — cumulative covers earlier months only.")
    skipped = [m for m in months if m not in values and m != report_month]
    if skipped:
        warnings.append(f"No monthly value in DB for: {', '.join(skipped)} — excluded.")

    if not values:
        raise ValueError(
            f"No monthly values found for {plant}/{unit}/{param_key} in "
            f"{months[0]}–{report_month}. Enter a Month Value first.")

    method, basis = get_rule(param_key)

    # Resolve weights
    weights: Dict[str, float] = {}
    weight_desc = None
    if basis:
        if unit in SHOP_UNITS:
            item = PLANT_WEIGHT_ITEMS[basis]
            weights = _plant_production(plant, item, months)
            weight_desc = f"total {plant} '{item}' production ('000 t, production data)"
        else:
            weights = _unit_production(plant, unit, months,
                                       current_production, report_month)
            weight_desc = (f"{unit} monthly production ('000 t — production "
                           f"data, else the unit's techno 'production' param)")
            if unit.startswith("BF-") and plant in SINGLE_BF_PLANTS:
                weight_desc += (
                    f", else {plant}'s plant-level 'Hot Metal' (its only "
                    "furnace, so the two are identical)"
                )

    rows, steps = [], []
    result = None
    method_used = method

    if method in ("weighted", "harmonic") and basis:
        # A weighted result must cover EVERY month that has a value — a
        # weighted subset silently drops months and misrepresents the YTD.
        # If any valued month lacks a production weight (or is unusable for
        # the harmonic mean), fall back to the simple average of ALL monthly
        # values so the cumulative always spans April→report_month.
        unusable = [
            m for m in months
            if values.get(m) is not None
            and (weights.get(m) is None
                 or (method == "harmonic" and values[m] <= 0))
        ]
        if unusable:
            label = ("production-weighted average" if method == "weighted"
                     else "production-weighted harmonic mean")
            warnings.append(
                f"Production weight missing/unusable ({weight_desc}) for: "
                f"{', '.join(unusable)} — used the simple average of all "
                f"monthly values instead of the {label}.")
            method_used = "average"

    if method_used in ("weighted", "harmonic") and basis:
        label = ("production-weighted average" if method == "weighted"
                 else "production-weighted harmonic mean")
        formula = ("Σ(month value × production) ÷ Σ(production)" if method == "weighted"
                   else "Σ(production) ÷ Σ(production ÷ month value)")
        steps.append(f"Method: {label} — Cumulative = {formula}. Weights = {weight_desc}.")

        usable = []
        for m in months:
            v = values.get(m)
            if v is None:
                continue
            w = weights[m]
            usable.append((m, v, w))
            term = round(v * w, 4) if method == "weighted" else round(w / v, 4)
            rows.append({"month": m, "value": v, "weight": w, "product": term})
            op = "×" if method == "weighted" else "÷"
            steps.append(f"{m}: {w} {op} {v} = {term}" if method == "harmonic"
                         else f"{m}: {v} × {w} = {term}")
        sum_w = sum(w for _, _, w in usable)
        if method == "weighted":
            sum_p = sum(v * w for _, v, w in usable)
            result = round(sum_p / sum_w, 4)
            steps.append(f"Σ(value × production) = {round(sum_p, 4)}")
            steps.append(f"Σ(production) = {round(sum_w, 4)}")
            steps.append(f"Cumulative = {round(sum_p, 4)} ÷ {round(sum_w, 4)} = {result}")
        else:
            sum_t = sum(w / v for _, v, w in usable)
            result = round(sum_w / sum_t, 4)
            steps.append(f"Σ(production) = {round(sum_w, 4)}")
            steps.append(f"Σ(production ÷ value) = {round(sum_t, 4)}")
            steps.append(f"Cumulative = {round(sum_w, 4)} ÷ {round(sum_t, 4)} = {result}")

    elif method == "sum":
        steps.append("Method: sum of monthly values (extensive total).")
        for m in months:
            if m in values:
                rows.append({"month": m, "value": values[m], "weight": None, "product": None})
        result = round(sum(values.values()), 4)
        steps.append(
            f"Cumulative = {' + '.join(str(values[m]) for m in months if m in values)} = {result}")

    else:  # simple average (unconfigured param, or weighted fallback)
        steps.append(
            "Method: simple average of monthly values "
            + ("(fallback — production weights incomplete for the valued months)."
               if method != method_used else
               "(parameter not configured for production weighting in CUMULATIVE_RULES)."))
        for m in months:
            if m in values:
                rows.append({"month": m, "value": values[m], "weight": None, "product": None})
        result = round(sum(values.values()) / len(values), 4)
        steps.append(
            f"Cumulative = ({' + '.join(str(values[m]) for m in months if m in values)}) "
            f"÷ {len(values)} = {result}")

    return {
        "plant": plant, "unit": unit, "param_key": param_key,
        "report_month": report_month, "fy_months": months,
        "method": {"weighted": "weighted_average", "harmonic": "harmonic_mean",
                   "sum": "sum"}.get(method_used, "simple_average"),
        "weight_basis": basis,
        "weight_item": weight_desc,
        "rows": rows, "result": result,
        "steps": steps, "warnings": warnings,
    }
