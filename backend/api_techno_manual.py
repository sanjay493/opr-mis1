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
    """Return {plant: {param_key: value}} for BF_Shop unit, all plants."""
    conn = sqlite3.connect(_db.DB_PATH)
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT plant, techno_json FROM techno_data WHERE report_month=? AND unit='BF_Shop'",
            [report_month],
        )
        result = {}
        for plant, tj in cur.fetchall():
            d = json.loads(tj)
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
    return {
        "plant": plant.upper(),
        "report_month": report_month,
        "units": data,          # {unit: {month: {...}, till_month: {...}}}
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

    calc_month     = _compute_sail_bf(body.report_month, "month")
    calc_till      = _compute_sail_bf(body.report_month, "till_month")

    if not calc_month and not calc_till:
        raise HTTPException(
            404,
            f"No BF_Shop data found for any plant in {body.report_month}. "
            "Upload plant data first."
        )

    if not body.overwrite_manual:
        # Preserve existing SAIL manual entries — only fill gaps
        existing = _db.get_techno_data("SAIL", body.report_month, "BF_Shop")
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
        report_month=body.report_month,
        unit="BF_Shop",
        techno_json={"month": calc_month, "till_month": calc_till},
        source_file="sail_calculated",
    )

    return {
        "status": "ok",
        "report_month": body.report_month,
        "sail_bf_month": calc_month,
        "sail_bf_till":  calc_till,
        "params_calculated": len(calc_month),
    }


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
