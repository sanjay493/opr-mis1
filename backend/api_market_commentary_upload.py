"""
Commentary & Market PDF upload API — see excel_extractors/
pdf_extractor_market_commentary.py for the PDF parsing itself. Consumed by
frontend/src/app/data-entry/commentary-market-upload (upload -> preview ->
save), the file-upload alternative to typing the Steel Sales bullets
(/data-entry/steel-sales-highlights) and the Key Prices grid
(/data-entry/market-intel) by hand.

Flow (preview/insert pattern):
  1. POST /preview — extract, and return alongside it what is stored now
     (the report month's bullets, every chart month's prices) so the page
     can show what will change. Writes nothing.
  2. POST /insert  — re-extracts nothing; saves what the client sends back
     (the previewed result): replaces the report month's month + YTD
     bullets and upserts every price value the chart showed (a later deck
     replaces last month's spot price with its full-month figure). Requires
     an editor/admin session.

The India Macro Economic Indicators table in the same deck is an image:
only its newest month column is OCR'd, shown for review (editable) with the
stored values alongside, and saved for that one month. The previous month
is OCR'd too, purely as a check that the right columns were read: if fewer
than half of its cells match what's stored (within 5% - the source revises
some figures), the preview warns.
"""
import os
import re
import tempfile
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

import auth
import db
import page_macro_indicators
import page_market_prices
from excel_extractors.pdf_extractor_market_commentary import extract_market_commentary_pdf

router = APIRouter(prefix="/api/market-commentary-upload", tags=["market-commentary-upload"])

_YM = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@router.post("/preview")
async def preview(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Upload the deck as a PDF file")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        result = extract_market_commentary_pdf(path)
    except Exception as e:
        raise HTTPException(422, f"Could not read the PDF: {e}")
    finally:
        os.unlink(path)

    month = result["report_month"]
    stored_bullets = db.get_steel_sales_highlights(month) if month else None
    months = result["market_prices"]["months"]
    stored_prices = db.get_market_price_trend(months) if months else {}

    macro = result.get("macro") or {}
    stored_macro, stored_macro_prev = {}, {}
    if macro.get("month"):
        got = db.get_macro_indicators([macro["month"], macro["prev_month"]])
        stored_macro, stored_macro_prev = got.get(macro["month"], {}), got.get(macro["prev_month"], {})
        pairs = [(v, stored_macro_prev.get(c)) for c, v in macro.get("prev_values", {}).items()
                 if v is not None and stored_macro_prev.get(c) is not None]
        if pairs:
            ok = sum(1 for v, st in pairs if abs(v - st) <= 0.05 * max(abs(st), 1e-9))
            if ok < len(pairs) / 2:
                result["warnings"].append(
                    f"Macro table: only {ok} of {len(pairs)} {macro['prev_month']} values OCR'd match "
                    f"what's stored - the newest-month column may be misread; check every value")
    return {
        **result,
        "file_name": file.filename,
        "series_labels": {c: page_market_prices.SERIES_LABEL[c] for c in page_market_prices.SERIES_CODES},
        "macro_metrics": [
            {"code": c, "label": page_macro_indicators.METRIC_LABEL[c], "unit": page_macro_indicators.METRIC_UNIT[c]}
            for c in page_macro_indicators.METRIC_CODES
        ],
        "series_order": page_market_prices.SERIES_CODES,
        "stored": {
            "month_items": (stored_bullets or {}).get("month_items", []),
            "ytd_items": (stored_bullets or {}).get("ytd_items", []),
            "prices": {m: stored_prices.get(m, {}) for m in months},
            "macro": stored_macro,
            "macro_prev": stored_macro_prev,
        },
    }


class InsertRequest(BaseModel):
    report_month: str
    file_name: str = ""
    month_items: List[str] = []
    ytd_items: List[str] = []
    # {series_code: {YYYY-MM: value}}
    prices: Dict[str, Dict[str, Optional[float]]] = {}
    # Reviewed newest-month macro column: macro_month + {metric_code: value}
    macro_month: Optional[str] = None
    macro: Dict[str, Optional[float]] = {}


@router.post("/insert")
async def insert(body: InsertRequest, user: dict = Depends(auth.require_editor_or_admin)):
    if not _YM.match(body.report_month):
        raise HTTPException(400, "report_month must be YYYY-MM")
    unknown = set(body.prices) - set(page_market_prices.SERIES_CODES)
    if unknown:
        raise HTTPException(400, f"Unknown price series: {sorted(unknown)}")
    bad = [m for vals in body.prices.values() for m in vals if not _YM.match(m)]
    if bad:
        raise HTTPException(400, f"Bad month(s): {sorted(set(bad))}")
    if body.macro:
        if not body.macro_month or not _YM.match(body.macro_month):
            raise HTTPException(400, "macro_month must be YYYY-MM")
        unknown_m = set(body.macro) - set(page_macro_indicators.METRIC_CODES)
        if unknown_m:
            raise HTTPException(400, f"Unknown macro metric(s): {sorted(unknown_m)}")

    month_items = [s.strip() for s in body.month_items if s.strip()]
    ytd_items = [s.strip() for s in body.ytd_items if s.strip()]
    saved_bullets = 0
    if month_items or ytd_items:
        db.save_steel_sales_highlights(body.report_month, month_items, ytd_items,
                                       updated_by=user.get("email", ""))
        saved_bullets = len(month_items) + len(ytd_items)

    rows = [{"report_month": m, "series_code": code, "value": v}
            for code, vals in body.prices.items() for m, v in vals.items() if v is not None]
    saved_prices = db.save_market_price_trend(rows) if rows else 0

    macro_rows = [{"report_month": body.macro_month, "metric_code": c, "value": v}
                  for c, v in body.macro.items() if v is not None]
    saved_macro = db.save_macro_indicators(macro_rows) if macro_rows else 0

    db.log_extraction("SAIL", body.report_month, body.file_name or "commentary-market.pdf",
                      "Key Performance Parameters / Key Prices", "Commentary & Market PDF",
                      saved_bullets + saved_prices + saved_macro)
    auth.log_activity(user, "update", "commentary_market_upload", body.report_month)
    return {"status": "ok", "report_month": body.report_month,
            "bullets": saved_bullets, "prices": saved_prices, "macro": saved_macro}
