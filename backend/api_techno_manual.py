"""
Techno Manual Entry & SAIL Aggregation API

Endpoints:
  GET  /api/techno/manual/entry           – fetch all unit data for plant+month
  POST /api/techno/manual/save            – upsert one unit's data
  POST /api/techno/manual/sail/calculate  – compute SAIL BF aggregate & save
  GET  /api/techno/manual/months          – list months that have data
"""

import json
import sqlite3
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import db as _db

router = APIRouter(prefix="/api/techno/manual", tags=["techno-manual"])

# ── Aggregation constants ────────────────────────────────────────────────────
_SAIL_PLANTS = ["RSP", "BSP", "ISP", "DSP", "BSL"]

# BF params that use harmonic mean (weighted by HM production)
_HARMONIC_KEYS = {"bf_productivity"}

# BF params that use simple arithmetic mean (not HM-weighted)
_ARITHMETIC_KEYS = {"hot_blast_temp", "blast_temperature", "hbt"}

# YTD cumulative rules live in techno_cumulative.CUMULATIVE_RULES (global,
# shared). Add new parameters there.
from techno_cumulative import compute_cumulative_preview


# ── Pydantic request bodies ──────────────────────────────────────────────────
class SaveRequest(BaseModel):
    plant: str
    report_month: str          # YYYY-MM
    unit: str
    month_data: Dict[str, Optional[float]] = {}
    till_month_data: Dict[str, Optional[float]] = {}


class SailCalcRequest(BaseModel):
    report_month: str          # YYYY-MM
    overwrite_manual: bool = False   # if True, overwrite user-entered SAIL values


# ── Helpers ──────────────────────────────────────────────────────────────────
def _validate_month(report_month: str):
    try:
        y, m = report_month.split('-')
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(400, "report_month must be YYYY-MM, e.g. '2026-05'")


def _get_hm_production(report_month: str, ytd: bool = False) -> Dict[str, float]:
    """Return {plant: HM_production} for the given month (or YTD sum)."""
    conn = sqlite3.connect(_db.DB_PATH)
    cur  = conn.cursor()
    try:
        if ytd:
            months = _db.get_ytd_months(report_month)
            if not months:
                return {}
            ph = ",".join("?" * len(months))
            cur.execute(
                f"SELECT plant_name, SUM(month_actual) FROM production_table "
                f"WHERE report_month IN ({ph}) AND item_name='Hot Metal' "
                f"GROUP BY plant_name",
                months,
            )
        else:
            cur.execute(
                "SELECT plant_name, month_actual FROM production_table "
                "WHERE report_month=? AND item_name='Hot Metal'",
                [report_month],
            )
        return {p: v for p, v in cur.fetchall() if v and v > 0}
    finally:
        conn.close()


def _get_bf_shop_data(report_month: str, period: str = "month") -> Dict[str, dict]:
    """Return {plant: {param_key: value}} for each plant's BF-shop-equivalent
    unit — 'BF_Shop' where a plant stores one, else 'BF-5' for a single-
    furnace plant (ISP) where the furnace IS the whole shop and no separate
    'BF_Shop' row is ever stored. Same BF_Shop-then-BF-5 convention as
    page_techno.py's _VERIFY_PARAMS/_resolve_unit — without this fallback,
    ISP was silently excluded from every SAIL BF aggregate."""
    conn = sqlite3.connect(_db.DB_PATH)
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT plant, unit, techno_json FROM techno_data "
            "WHERE report_month=? AND unit IN ('BF_Shop', 'BF-5')",
            [report_month],
        )
        by_plant_unit: Dict[str, Dict[str, dict]] = {}
        for plant, unit, tj in cur.fetchall():
            by_plant_unit.setdefault(plant, {})[unit] = json.loads(tj)
        result = {}
        for plant, units in by_plant_unit.items():
            d = units.get("BF_Shop") or units.get("BF-5")
            if d:
                result[plant] = d.get(period, {})
        return result
    finally:
        conn.close()


def _compute_sail_bf(report_month: str, period: str = "month") -> Dict[str, Optional[float]]:
    """
    Compute SAIL BF_Shop aggregates.
      - Most params  : weighted average by HM production
      - bf_productivity: harmonic mean  = Σhm / Σ(hm / val)
      - hot_blast_temp : arithmetic mean = Σval / N
    """
    hm      = _get_hm_production(report_month, ytd=(period == "till_month"))
    bf_data = _get_bf_shop_data(report_month, period)

    if not bf_data:
        return {}

    all_keys = set()
    for d in bf_data.values():
        all_keys.update(d.keys())

    result: Dict[str, Optional[float]] = {}
    for key in sorted(all_keys):
        # Plants that have this param AND have HM production weight
        plant_vals = [
            (bf_data[p][key], hm.get(p, 0))
            for p in _SAIL_PLANTS
            if p in bf_data and key in bf_data[p] and hm.get(p, 0) > 0
        ]
        if not plant_vals:
            # Fallback: no HM weights — simple average of available values
            vals = [bf_data[p][key] for p in _SAIL_PLANTS
                    if p in bf_data and key in bf_data[p]]
            result[key] = round(sum(vals) / len(vals), 4) if vals else None
            continue

        total_hm = sum(h for _, h in plant_vals)

        if key in _HARMONIC_KEYS:
            # Harmonic mean weighted by HM: Σhm / Σ(hm/val)
            denom = sum(h / v for v, h in plant_vals if v and v > 0)
            result[key] = round(total_hm / denom, 4) if denom else None

        elif key in _ARITHMETIC_KEYS:
            result[key] = round(sum(v for v, _ in plant_vals) / len(plant_vals), 4)

        else:
            # Weighted average
            w_sum = sum(v * h for v, h in plant_vals)
            result[key] = round(w_sum / total_hm, 4) if total_hm else None

    return result


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/entry")
async def get_entry(
    plant: str = Query(..., description="Plant code: RSP, BSP, ISP, DSP, BSL, SAIL"),
    report_month: str = Query(..., description="YYYY-MM"),
):
    """Fetch all unit data for a plant + month (for form pre-population)."""
    _validate_month(report_month)
    _db.init_db()
    data = _db.get_techno_data(plant.upper(), report_month)

    # FY-to-date history (Apr .. month before report_month) per unit, used by
    # the frontend to auto-calculate the YTD/cumulative box as the user types
    # the current month's value.
    ytd_months   = _db.get_ytd_months(report_month)
    prior_months = [m for m in ytd_months if m < report_month]
    history: Dict[str, Dict[str, dict]] = {}
    for m in prior_months:
        month_data = _db.get_techno_data(plant.upper(), m)
        for unit, ud in month_data.items():
            monthly_vals = ud.get("month", {})
            if monthly_vals:
                history.setdefault(unit, {})[m] = monthly_vals

    return {
        "plant": plant.upper(),
        "report_month": report_month,
        "units": data,          # {unit: {month: {...}, till_month: {...}}}
        "ytd_history": history, # {unit: {"2026-04": {param_key: val}, ...}}
        "ytd_months": prior_months,
        "has_data": bool(data),
    }


@router.post("/save")
async def save_entry(body: SaveRequest):
    """
    Upsert techno data for one unit.
    Sends month_data and till_month_data separately.
    Null values in the payload leave existing DB values unchanged
    (uses merge_upsert so other params in the same unit are preserved).
    """
    _validate_month(body.report_month)
    _db.init_db()

    # Build techno_json only from non-None values
    month_clean     = {k: v for k, v in body.month_data.items()      if v is not None}
    till_clean      = {k: v for k, v in body.till_month_data.items() if v is not None}

    if not month_clean and not till_clean:
        raise HTTPException(400, "No values provided — nothing to save.")

    techno_json = {
        "month":       month_clean,
        "till_month":  till_clean,
    }

    _db.merge_upsert_techno_data(
        plant=body.plant.upper(),
        report_month=body.report_month,
        unit=body.unit,
        new_techno_json=techno_json,
        source_file="manual",
    )

    return {"status": "ok", "plant": body.plant.upper(),
            "report_month": body.report_month, "unit": body.unit,
            "saved_month_params": len(month_clean),
            "saved_till_params": len(till_clean)}


def _apply_sail_bf(report_month: str, overwrite_manual: bool = False) -> Optional[Dict]:
    """
    Core SAIL BF_Shop compute-and-save logic — shared by the manual
    /sail/calculate endpoint and the automatic post-save refresh
    (auto_refresh_sail_bf below). Uses HM production from production_table
    as weights.

    By default preserves any manually-entered SAIL values (overwrite_manual=False).
    Set overwrite_manual=True to replace ALL SAIL BF_Shop values with calculated ones.

    Returns {"month": {...}, "till_month": {...}}, or None if no contributing
    plant has BF_Shop data for this month.
    """
    calc_month     = _compute_sail_bf(report_month, "month")
    calc_till      = _compute_sail_bf(report_month, "till_month")

    if not calc_month and not calc_till:
        return None

    if not overwrite_manual:
        # Preserve existing SAIL manual entries — only fill gaps
        existing = _db.get_techno_data("SAIL", report_month, "BF_Shop")
        ex_month = existing.get("BF_Shop", {}).get("month", {})
        ex_till  = existing.get("BF_Shop", {}).get("till_month", {})

        # Calculated values only for params NOT already in SAIL
        for k in list(calc_month.keys()):
            if k in ex_month:
                calc_month[k] = ex_month[k]   # keep manual value
        for k in list(calc_till.keys()):
            if k in ex_till:
                calc_till[k] = ex_till[k]

    _db.upsert_techno_data(
        plant="SAIL",
        report_month=report_month,
        unit="BF_Shop",
        techno_json={"month": calc_month, "till_month": calc_till},
        source_file="sail_calculated",
    )

    return {"month": calc_month, "till_month": calc_till}


def auto_refresh_sail_bf(report_month: str) -> None:
    """
    Called by db.upsert_techno_data whenever a contributing plant's BF-shop-
    equivalent unit (BF_Shop or ISP's BF-5) is saved, so the stored SAIL
    BF_Shop row never goes stale relative to the plant data it's built from.

    Always overwrites (overwrite_manual=True) rather than the manual
    endpoint's default preserve-existing behaviour: a "preserve" refresh
    would never actually update anything once a value already exists for a
    parameter, which is exactly the staleness this hook exists to eliminate.
    One consequence: a SAIL BF_Shop value hand-typed via the generic manual-
    entry form (as opposed to a prior "Apply SAIL" click) will also be
    overwritten the next time any contributing plant saves — the schema has
    no per-parameter way to tell "deliberately hand-typed" apart from
    "previously auto-computed" within the same stored row.
    """
    _apply_sail_bf(report_month, overwrite_manual=True)


@router.post("/sail/calculate")
async def calculate_sail(body: SailCalcRequest):
    """
    Calculate SAIL BF_Shop aggregate from all plant BF_Shop data.
    Uses HM production from production_table as weights.

    By default preserves any manually-entered SAIL values (overwrite_manual=False).
    Set overwrite_manual=True to replace ALL SAIL BF_Shop values with calculated ones.
    """
    _validate_month(body.report_month)
    _db.init_db()

    result = _apply_sail_bf(body.report_month, body.overwrite_manual)
    if result is None:
        raise HTTPException(
            404,
            f"No BF_Shop data found for any plant in {body.report_month}. "
            "Upload plant data first."
        )

    return {
        "status": "ok",
        "report_month": body.report_month,
        "sail_bf_month": result["month"],
        "sail_bf_till":  result["till_month"],
        "params_calculated": len(result["month"]),
    }


@router.get("/cumulative-preview")
async def cumulative_preview(
    plant: str = Query(..., description="Plant code"),
    unit: str = Query(..., description="Unit, e.g. BF-1, BF_Shop, SMS"),
    param_key: str = Query(..., description="Parameter key, e.g. coke_rate"),
    report_month: str = Query(..., description="YYYY-MM"),
    current_value: Optional[float] = Query(
        None, description="Month value currently typed in the form for report_month "
                          "(overrides the DB value, may be unsaved)"),
    current_production: Optional[float] = Query(
        None, description="Unsaved form 'production' Month Value — used as the "
                          "report_month weight for unit-wise weighting"),
):
    """
    Compute the YTD cumulative for ONE parameter with a step-by-step breakdown
    so the user can verify the calculation before applying it.

    Methods and weights come from the global techno_cumulative.CUMULATIVE_RULES:
    HM-weighted average (coke rate, slag rate, nut coke, CDI, fuel rate,
    coal-to-HM, O2 enrichment, sinter/pellet % in burden), HM-weighted harmonic
    mean (BF productivity), crude-steel-weighted average (specific HM/scrap
    consumption, TMI, specific energy consumption), sum for extensive totals,
    simple average otherwise. Shop-level units (BF_Shop, SMS) weight by total
    PLANT production; any other unit weights by its own monthly 'production'
    techno parameter — months without a weight are excluded, with a warning.
    """
    _validate_month(report_month)
    _db.init_db()
    try:
        return compute_cumulative_preview(
            plant=plant, unit=unit, param_key=param_key,
            report_month=report_month,
            current_value=current_value,
            current_production=current_production,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/months")
async def list_months(
    plant: Optional[str] = Query(None, description="Plant filter (optional)"),
):
    """List report months that have techno data."""
    _db.init_db()
    months = _db.get_techno_months(plant.upper() if plant else None)
    return {"months": months, "count": len(months)}


@router.get("/sail/preview")
async def preview_sail(
    report_month: str = Query(..., description="YYYY-MM"),
):
    """
    Preview what SAIL calculation would produce without saving.
    Shows calculated vs existing SAIL values side-by-side.
    """
    _validate_month(report_month)
    _db.init_db()

    calc_month = _compute_sail_bf(report_month, "month")
    calc_till  = _compute_sail_bf(report_month, "till_month")

    existing   = _db.get_techno_data("SAIL", report_month, "BF_Shop")
    ex_month   = existing.get("BF_Shop", {}).get("month", {})
    ex_till    = existing.get("BF_Shop", {}).get("till_month", {})

    hm_weights = _get_hm_production(report_month)

    return {
        "report_month": report_month,
        "hm_weights": hm_weights,
        "calculated": {"month": calc_month, "till_month": calc_till},
        "existing_sail": {"month": ex_month, "till_month": ex_till},
    }
