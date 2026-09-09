"""
Cost Trend Excel extractor API — see excel_extractors/excel_extractor_cost_trend.py
for the workbook parsing itself. Consumed by frontend/src/app/data-entry/
cost-trend-extract (upload -> preview -> confirm), the automated alternative
to the manual Cost Trend Entry form for months a source workbook exists for.

Two source workbook kinds are supported, auto-detected from sheet names:
  - "ELHM CS SS ..." (sheets HM/CS/SS) — one workbook is either a Month
    file or a separate cumulative "APRIL-<month>" till-month file, never
    both, so every row it produces targets the SAME field.
  - "BF Coke-5ISPs-For and Upto <Mon><YY>.xlsx" (sheets BSP/DSP/RSP/BSL/
    ISP, product COKE) — a single workbook prints BOTH the month and
    till-month blocks side by side, so its rows are a mix of both fields.
Both kinds return the same row shape, with each row carrying its OWN
"field" ('month_value'/'till_month_value') rather than the whole preview
sharing one — that's what lets a single BF Coke upload write both columns
in one confirm.

Flow (preview/confirm pattern):
  1. POST /preview  — extract, diff every (product, plant, cost_type,
     field) cell against the current DB value. Writes nothing.
  2. POST /confirm  — write the rows the client marked apply=true (re-
     validated server-side, not trusted from the client), each into its
     own row's field.
"""
import os
import tempfile

import openpyxl
from fastapi import APIRouter, File, HTTPException, UploadFile

import db
from excel_extractors.excel_extractor_cost_trend import (
    PLANT_ORDER,
    _BF_COKE_PLANTS,
    extract_bf_coke_workbook,
    extract_cost_trend_workbook,
)

router = APIRouter(prefix="/api/cost-trend-extract", tags=["cost-trend-extract"])

_COST_TYPES = ["VARIABLE", "FIXED"]
_PRODUCTS = ["HM", "CS", "SS", "COKE"]


def _classify(value, db_value):
    if value is None:
        return "blank"
    if db_value is None:
        return "new"
    if abs(db_value - value) > 1e-6:
        return "changed"
    return "unchanged"


def _detect_workbook_kind(tmp_path: str) -> str:
    """'elementwise' (HM/CS/SS sheets) or 'bf_coke' (plant-named sheets) —
    a cheap peek at sheet names before running the real (heavier) parse."""
    wb = openpyxl.load_workbook(tmp_path, read_only=True)
    try:
        names = {s.strip().upper() for s in wb.sheetnames}
    finally:
        wb.close()
    if names & {"HM", "CS", "SS"}:
        return "elementwise"
    if names & set(_BF_COKE_PLANTS):
        return "bf_coke"
    raise HTTPException(
        400,
        "Unrecognized workbook: expected an 'ELHM CS SS ...' workbook (sheets HM/CS/SS) "
        "or a 'BF Coke-5ISPs...' workbook (sheets BSP/DSP/RSP/BSL/ISP).",
    )


@router.post("/preview")
async def cost_trend_extract_preview(file: UploadFile = File(...)):
    """Parse an uploaded Cost Trend workbook and diff every extracted
    (product, plant, cost_type, field) cell against its current DB value.
    Writes nothing."""
    raw = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        kind = _detect_workbook_kind(tmp_path)
        if kind == "elementwise":
            rows, counts, report_month, extra_meta = _preview_elementwise(tmp_path)
        else:
            rows, counts, report_month, extra_meta = _preview_bf_coke(tmp_path)
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        os.unlink(tmp_path)

    return {
        "report_month": report_month,
        "rows": rows,
        "counts": counts,
        "filename": file.filename,
        **extra_meta,
    }


def _preview_elementwise(tmp_path):
    extracted = extract_cost_trend_workbook(tmp_path)
    report_month = extracted["report_month"]
    is_till = extracted["is_till_month"]
    field = "till_month_value" if is_till else "month_value"
    db_key = "till_month" if is_till else "month"

    rows = []
    counts = {"new": 0, "changed": 0, "unchanged": 0, "blank": 0}
    for product in ("HM", "CS", "SS"):
        plants = extracted["products"].get(product, {})
        existing = db.get_cost_trend_monthly(product, [report_month]).get(report_month, {})
        for plant in PLANT_ORDER:
            cell = plants.get(plant, {})
            for cost_type in _COST_TYPES:
                value = cell.get("variable" if cost_type == "VARIABLE" else "fixed")
                db_value = existing.get(cost_type, {}).get(plant, {}).get(db_key)
                status = _classify(value, db_value)
                counts[status] += 1
                rows.append({
                    "product": product, "plant": plant, "cost_type": cost_type, "field": field,
                    "extracted_value": value, "db_value": db_value, "status": status,
                })

    return rows, counts, report_month, {"is_till_month": is_till, "field": field, "dual_field": False}


def _preview_bf_coke(tmp_path):
    extracted = extract_bf_coke_workbook(tmp_path)
    report_month = extracted["report_month"]
    product = extracted["product"]
    existing = db.get_cost_trend_monthly(product, [report_month]).get(report_month, {})

    rows = []
    counts = {"new": 0, "changed": 0, "unchanged": 0, "blank": 0}
    for plant, blocks in extracted["plants"].items():
        for block_key, field in (("month", "month_value"), ("till_month", "till_month_value")):
            block = blocks[block_key]
            for cost_type, val_key in (("VARIABLE", "variable"), ("FIXED", "fixed")):
                value = block.get(val_key)
                db_value = existing.get(cost_type, {}).get(plant, {}).get(block_key)
                status = _classify(value, db_value)
                counts[status] += 1
                rows.append({
                    "product": product, "plant": plant, "cost_type": cost_type, "field": field,
                    "extracted_value": value, "db_value": db_value, "status": status,
                })

    return rows, counts, report_month, {"is_till_month": None, "field": None, "dual_field": True, "product": product}


@router.post("/confirm")
async def cost_trend_extract_confirm(payload: dict):
    """Write rows from a previewed Cost Trend extraction. Only rows the
    client marked apply=true AND that were classified 'new' or 'changed' at
    preview time are written; everything is re-validated server-side rather
    than trusting the client. Each row is written into its OWN field
    (month_value/till_month_value) — a single BF Coke upload's rows may
    target both."""
    report_month = str(payload.get("report_month", "")).strip()
    rows = payload.get("rows", [])

    if not report_month:
        raise HTTPException(400, "report_month is required")

    by_field_product: dict = {}
    skipped = 0
    for r in rows:
        if not r.get("apply") or r.get("status") not in ("new", "changed"):
            skipped += 1
            continue
        product = r.get("product")
        plant = r.get("plant")
        cost_type = r.get("cost_type")
        field = r.get("field")
        if (product not in _PRODUCTS or plant not in PLANT_ORDER or cost_type not in _COST_TYPES
                or field not in ("month_value", "till_month_value")):
            skipped += 1
            continue
        try:
            value = float(r.get("extracted_value"))
        except (TypeError, ValueError):
            skipped += 1
            continue
        by_field_product.setdefault((field, product), []).append({"cost_type": cost_type, "plant": plant, "value": value})

    saved = 0
    for (field, product), entries in by_field_product.items():
        saved += db.save_cost_trend_monthly_field(report_month, product, entries, field)

    return {"status": "success", "saved": saved, "skipped": skipped}
