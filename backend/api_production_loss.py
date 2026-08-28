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

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import db as _db
from production_loss_analysis import ITEM_NAMES, build_report

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
                   actual_start, actual_end, actual_ongoing, planned_days
            FROM capital_repair_table
            WHERE plant=?
        """, (plant,))
        cols = ["id", "shop", "equipment", "activity", "unit_type", "unit_name", "sms_subtag",
                "actual_start", "actual_end", "actual_ongoing", "planned_days"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def _bd_rows_for_plant(plant: str):
    conn = _db.connect()
    try:
        cur = conn.execute("""
            SELECT id, unit_type, unit_name, sms_subtag, start_ts, end_ts, is_ongoing, cause
            FROM breakdown_table
            WHERE plant=?
        """, (plant,))
        cols = ["id", "unit_type", "unit_name", "sms_subtag", "start_ts", "end_ts", "is_ongoing", "cause"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


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

    def fetch_month_data(plant_: str, month: str):
        plan = _production_value("production_plan_table", plant_, month, item_name)
        actual = _production_value("production_table", plant_, month, item_name)
        return plan, actual, cr_rows, bd_rows

    try:
        report = build_report(
            plant, item, period_a, period_b, fetch_month_data,
            today=date.today().isoformat(),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    report["item_label"] = item_name
    return report
