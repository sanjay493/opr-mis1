"""
Production-loss analysis API — thin DB-fetching wrapper around
production_loss_analysis.py's pure computation engine. Explains Hot Metal /
Crude Steel / Finished Steel shortfalls vs. ABP using Capital Repair overrun
+ Breakdown events (see that module's docstring for the full methodology).

  GET /api/production-loss-analysis
      ?plant=BSP&item=HM|CS|FS
      &period_a_kind=month|fy|range&period_a_value=2026-06   (month/fy)
                                    &period_a_start=2026-04&period_a_end=2026-06  (range — a quarter,
                                                                                   half-year, or any
                                                                                   N-month club)
      &period_b_kind=...&period_b_value=...|&period_b_start=...&period_b_end=...  (optional — comparison
                                                                                    period; the frontend
                                                                                    resolves CPLY/CPLM into
                                                                                    concrete month/fy/range
                                                                                    values before calling this)

Read-only — no PAGE_MODULES entry needed.
"""

import re
from calendar import monthrange
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import db as _db
from production_loss_analysis import ITEM_NAMES, MILL_ALIASES, build_report, _norm

router = APIRouter(prefix="/api/production-loss-analysis", tags=["production-loss-analysis"])


def _production_value(table: str, plant: str, month: str, item_name: str) -> Optional[float]:
    """Monthly plan/actual in TONNES. production_table / production_plan_table
    store this in '000 T (repo-wide convention); the loss engine and the
    frontend both work in plain tonnes (fields named *_t, axis/tiles labelled
    "T"), so scale up here — the one place the two units meet."""
    conn = _db.connect()
    try:
        cur = conn.execute(
            f"SELECT month_actual FROM {table} WHERE plant_name=? AND item_name=? AND report_month=?",
            (plant, item_name, month),
        )
        row = cur.fetchone()
        return round(float(row[0]) * 1000, 3) if row and row[0] is not None else None
    finally:
        conn.close()


def _cr_rows_for_plant(plant: str):
    conn = _db.connect()
    try:
        cur = conn.execute("""
            SELECT id, shop, equipment, activity, unit_type, unit_name, sms_subtag,
                   actual_start, actual_end, actual_ongoing, planned_days, period, schedule_days
            FROM capital_repair_table
            WHERE plant=?
        """, (plant,))
        cols = ["id", "shop", "equipment", "activity", "unit_type", "unit_name", "sms_subtag",
                "actual_start", "actual_end", "actual_ongoing", "planned_days", "abp_period", "schedule_days"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def _bd_rows_for_plant(plant: str):
    conn = _db.connect()
    try:
        cur = conn.execute("""
            SELECT id, unit_type, unit_name, sms_subtag, start_ts, end_ts, is_ongoing, cause,
                   hours_lost_override
            FROM breakdown_table
            WHERE plant=?
        """, (plant,))
        cols = ["id", "unit_type", "unit_name", "sms_subtag", "start_ts", "end_ts", "is_ongoing", "cause",
                "hours_lost_override"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Capacities (see production_loss_analysis.compute_loss_for_item)
# ---------------------------------------------------------------------------

_STAGE_ITEM = {"BF": "Hot Metal", "SMS": "Total Crude Steel", "MILL": "Finished Steel"}
_DEMONSTRATED_MONTHS = 36

_NOT_A_MILL = re.compile(
    r"sinter|^sp\b|cob|oven|pushing|hot metal|crude|saleable|finished steel|total|despatch|blast|^bf|"
    r"sms|steel melting|caster|brc|semis|prime", re.IGNORECASE)
_BF_LABEL = re.compile(r"^(?:BF|BLAST\s*FURNACE)\s*[#-]?\s*(\d+)$", re.IGNORECASE)
_SMS_LABEL = re.compile(r"^(?:SMS|STEEL\s*MELTING\s*SHOP)\s*-?\s*(IV|V|I{1,3}|\d+)$", re.IGNORECASE)
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def _unit_weights(plant: str) -> dict:
    """{'BF': {'BF-4': w, ...}, 'SMS': {'SMS-3': w}, 'MILL': {'PLATEMILL': w}}
    - each unit's best-ever day (major_unit_daily_record), used only as a
    relative weight for splitting its stage's capacity between units (so a
    plant storing them in '000 T, like ISP, works the same)."""
    conn = _db.connect()
    try:
        rows = conn.execute("SELECT unit_label, value FROM major_unit_daily_record WHERE plant_code=?",
                            (plant,)).fetchall()
    finally:
        conn.close()
    out = {"BF": {}, "SMS": {}, "MILL": {}}
    for label, value in rows:
        if value is None or float(value) <= 0:
            continue
        label = (label or "").strip()
        if m := _BF_LABEL.match(label):
            out["BF"][f"BF-{m.group(1)}"] = float(value)
        elif m := _SMS_LABEL.match(label):
            g = m.group(1).upper()
            out["SMS"][f"SMS-{_ROMAN.get(g, g)}"] = float(value)
        elif not _NOT_A_MILL.search(label):
            key = _norm(label)
            out["MILL"][MILL_ALIASES.get(key, key)] = float(value)
    return out


def _stage_capacity_tpd(plant: str, item_name: str, month: str) -> Optional[float]:
    """The stage's capacity in t/day: the higher of the rated capacity
    (item_capacity_table, '000 T/yr) and what the plant has demonstrated -
    its best month in the last 3 years. Plants routinely run above rated
    capacity, so rated alone would leave no headroom at all."""
    conn = _db.connect()
    try:
        row = conn.execute("""SELECT annual_capacity FROM item_capacity_table
                              WHERE plant_name=? AND item_name=? AND effective_month<=?
                              ORDER BY effective_month DESC LIMIT 1""", (plant, item_name, month)).fetchone()
        y, m = int(month[:4]), int(month[5:7])
        start = f"{y - 3:04d}-{m:02d}"
        hist = conn.execute("""SELECT report_month, month_actual FROM production_table
                               WHERE plant_name=? AND item_name=? AND report_month>=? AND report_month<?""",
                            (plant, item_name, start, month)).fetchall()
    finally:
        conn.close()
    rated = float(row[0]) * 1000 / 365 if row and row[0] else None
    shown = [float(v) * 1000 / monthrange(int(rm[:4]), int(rm[5:7]))[1] for rm, v in hist if v]
    demonstrated = max(shown) if shown else None
    vals = [v for v in (rated, demonstrated) if v]
    return max(vals) if vals else None


def _capacity_for_month(plant: str, month: str, weights: dict, cache: dict) -> dict:
    out = {}
    for stage, item_name in _STAGE_ITEM.items():
        key = (stage, month)
        if key not in cache:
            cache[key] = _stage_capacity_tpd(plant, item_name, month)
        tpd = cache[key]
        w = weights.get(stage) or {}
        total_w = sum(w.values())
        out[stage] = {"stage_tpd": tpd,
                      "units": {u: tpd * v / total_w for u, v in w.items()} if tpd and total_w else {}}
    return out


_PERIOD_KINDS = ("month", "fy", "range")


def _build_period(label: str, kind: Optional[str], value: Optional[str],
                   start: Optional[str], end: Optional[str]) -> dict:
    if kind not in _PERIOD_KINDS:
        raise HTTPException(400, f"{label}_kind must be one of {_PERIOD_KINDS}")
    if kind == "range":
        if not start or not end:
            raise HTTPException(400, f"{label}_start and {label}_end are required when {label}_kind is 'range'")
        if start > end:
            raise HTTPException(400, f"{label}_start must not be after {label}_end")
        return {"kind": "range", "start": start, "end": end, "value": f"{start} to {end}"}
    if not value:
        raise HTTPException(400, f"{label}_value is required when {label}_kind is '{kind}'")
    return {"kind": kind, "value": value}


@router.get("")
async def get_production_loss_analysis(
    plant: str = Query(...),
    item: str = Query(...),
    period_a_kind: str = Query(...),
    period_a_value: Optional[str] = Query(None),
    period_a_start: Optional[str] = Query(None),
    period_a_end: Optional[str] = Query(None),
    period_b_kind: Optional[str] = Query(None),
    period_b_value: Optional[str] = Query(None),
    period_b_start: Optional[str] = Query(None),
    period_b_end: Optional[str] = Query(None),
):
    if item not in ITEM_NAMES:
        raise HTTPException(400, "item must be one of HM, CS, FS")

    period_a = _build_period("period_a", period_a_kind, period_a_value, period_a_start, period_a_end)
    period_b = None
    if period_b_kind:
        period_b = _build_period("period_b", period_b_kind, period_b_value, period_b_start, period_b_end)

    item_name = ITEM_NAMES[item]
    # CR/breakdown rows don't vary by month — fetched once per report, not
    # once per month, then filtered/date-clipped inside the pure engine.
    cr_rows = _cr_rows_for_plant(plant)
    bd_rows = _bd_rows_for_plant(plant)

    weights = _unit_weights(plant)
    cap_cache: dict = {}

    def fetch_month_data(plant_: str, month: str):
        return {
            "plan": _production_value("production_plan_table", plant_, month, item_name),
            "actual": _production_value("production_table", plant_, month, item_name),
            "hm_plan": (_production_value("production_plan_table", plant_, month, ITEM_NAMES["HM"])
                        if item == "CS" else None),
            "cr_rows": cr_rows, "bd_rows": bd_rows,
            "capacity": _capacity_for_month(plant_, month, weights, cap_cache),
        }

    try:
        report = build_report(
            plant, item, period_a, period_b, fetch_month_data,
            today=date.today().isoformat(),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    report["item_label"] = item_name
    return report
