"""
Cost Trend Excel extractor API — see excel_extractors/excel_extractor_cost_trend.py
for the workbook parsing itself. Consumed by frontend/src/app/data-entry/
cost-trend-extract (upload -> preview -> confirm), the automated alternative
to the manual Cost Trend Entry form for months a source workbook exists for.

Flow (preview/confirm pattern):
  1. POST /preview  — extract, diff every (product, plant, cost_type) cell
     against the current DB value for that field. Writes nothing.
  2. POST /confirm  — write the rows the client marked apply=true (re-
     validated server-side, not trusted from the client), into whichever
     single column (month_value or till_month_value) the source workbook
     was for.
"""
import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

import db
from excel_extractors.excel_extractor_cost_trend import PLANT_ORDER, extract_cost_trend_workbook

router = APIRouter(prefix="/api/cost-trend-extract", tags=["cost-trend-extract"])

_COST_TYPES = ["VARIABLE", "FIXED"]
_PRODUCTS = ["HM", "CS", "SS"]


@router.post("/preview")
async def cost_trend_extract_preview(file: UploadFile = File(...)):
    """Parse an uploaded Cost Trend workbook and diff every extracted
    (product, plant, cost_type) cell against the current DB value for
    whichever field (month_value/till_month_value) this workbook is for.
    Writes nothing."""
    raw = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        extracted = extract_cost_trend_workbook(tmp_path)
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        os.unlink(tmp_path)

    report_month = extracted["report_month"]
    is_till = extracted["is_till_month"]
    field = "till_month_value" if is_till else "month_value"
    db_key = "till_month" if is_till else "month"

    rows = []
    counts = {"new": 0, "changed": 0, "unchanged": 0, "blank": 0}
    for product in _PRODUCTS:
        plants = extracted["products"].get(product, {})
        existing = db.get_cost_trend_monthly(product, [report_month]).get(report_month, {})
        for plant in PLANT_ORDER:
            cell = plants.get(plant, {})
            for cost_type in _COST_TYPES:
                value = cell.get("variable" if cost_type == "VARIABLE" else "fixed")
                db_value = existing.get(cost_type, {}).get(plant, {}).get(db_key)
                if value is None:
                    status = "blank"
                elif db_value is None:
                    status = "new"
                elif abs(db_value - value) > 1e-6:
                    status = "changed"
                else:
                    status = "unchanged"
                counts[status] += 1
                rows.append({
                    "product": product, "plant": plant, "cost_type": cost_type,
                    "extracted_value": value, "db_value": db_value, "status": status,
                })

    return {
        "report_month": report_month,
        "is_till_month": is_till,
        "field": field,
        "rows": rows,
        "counts": counts,
        "filename": file.filename,
    }


@router.post("/confirm")
async def cost_trend_extract_confirm(payload: dict):
    """Write rows from a previewed Cost Trend extraction. Only rows the
    client marked apply=true AND that were classified 'new' or 'changed' at
    preview time are written; everything is re-validated server-side rather
    than trusting the client."""
    report_month = str(payload.get("report_month", "")).strip()
    field = payload.get("field")
    rows = payload.get("rows", [])

    if field not in ("month_value", "till_month_value"):
        raise HTTPException(400, "field must be 'month_value' or 'till_month_value'")
    if not report_month:
        raise HTTPException(400, "report_month is required")

    by_product: dict = {}
    skipped = 0
    for r in rows:
        if not r.get("apply") or r.get("status") not in ("new", "changed"):
            skipped += 1
            continue
        product = r.get("product")
        plant = r.get("plant")
        cost_type = r.get("cost_type")
        if product not in _PRODUCTS or plant not in PLANT_ORDER or cost_type not in _COST_TYPES:
            skipped += 1
            continue
        try:
            value = float(r.get("extracted_value"))
        except (TypeError, ValueError):
            skipped += 1
            continue
        by_product.setdefault(product, []).append({"cost_type": cost_type, "plant": plant, "value": value})

    saved = 0
    for product, entries in by_product.items():
        saved += db.save_cost_trend_monthly_field(report_month, product, entries, field)

    return {"status": "success", "saved": saved, "skipped": skipped}
