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
  Any other unit — that unit's own monthly 'production' parameter from techno
  data (furnace-wise production; being added plant by plant). Months without a
  weight are EXCLUDED from the calculation and reported as warnings.
"""

import sqlite3
from typing import Dict, Optional

import db as _db

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
    "oxygen_enrichment": ("weighted", "hm"),   # RSP key for the same parameter
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


def get_rule(param_key: str):
    """Return (method, weight_basis); default is simple average, no weight."""
    return CUMULATIVE_RULES.get(param_key, ("average", None))


def _plant_production(plant: str, item: str, months) -> Dict[str, float]:
    """{month: production} for a plant-level item from production_table."""
    conn = sqlite3.connect(_db.DB_PATH)
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
    """{month: production} from the unit's own techno 'production' param.
    current_production (unsaved form value) takes precedence for report_month."""
    weights: Dict[str, float] = {}
    for m in months:
        ud = _db.get_techno_data(plant, m, unit).get(unit, {})
        v = ud.get("month", {}).get("production")
        if v is not None and v > 0:
            weights[m] = v
    if current_production is not None and current_production > 0 and report_month:
        weights[report_month] = current_production
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
            weight_desc = f"{unit}'s own monthly 'production' (t, techno data)"

    rows, steps = [], []
    result = None

    if method in ("weighted", "harmonic") and basis:
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
            w = weights.get(m)
            if w is None or (method == "harmonic" and v <= 0):
                reason = ("production weight missing" if w is None
                          else "non-positive value (harmonic mean undefined)")
                warnings.append(f"{m}: value {v} present but {reason} — month excluded.")
                rows.append({"month": m, "value": v, "weight": None, "product": None})
                continue
            usable.append((m, v, w))
            term = round(v * w, 4) if method == "weighted" else round(w / v, 4)
            rows.append({"month": m, "value": v, "weight": w, "product": term})
            op = "×" if method == "weighted" else "÷"
            steps.append(f"{m}: {w} {op} {v} = {term}" if method == "harmonic"
                         else f"{m}: {v} × {w} = {term}")
        if not usable:
            raise ValueError(
                f"No months have both a value and a production weight "
                f"({weight_desc}) — cannot compute {label}. "
                f"Enter the monthly production first, or exclude weighting.")
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

    else:  # simple average (parameter not configured in CUMULATIVE_RULES)
        steps.append(
            "Method: simple average of monthly values "
            "(parameter not configured for production weighting in CUMULATIVE_RULES).")
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
                   "sum": "sum"}.get(method, "simple_average"),
        "weight_basis": basis,
        "weight_item": weight_desc,
        "rows": rows, "result": result,
        "steps": steps, "warnings": warnings,
    }
