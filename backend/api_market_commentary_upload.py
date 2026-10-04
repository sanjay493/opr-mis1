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

The India Macro Economic Indicators table in the same deck is an image and
is not extracted — its new month is entered in /data-entry/market-intel.
"""
import os
import re
import tempfile
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

import auth
import db
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
    return {
        **result,
        "file_name": file.filename,
        "series_labels": {c: page_market_prices.SERIES_LABEL[c] for c in page_market_prices.SERIES_CODES},
        "series_order": page_market_prices.SERIES_CODES,
        "stored": {
            "month_items": (stored_bullets or {}).get("month_items", []),
            "ytd_items": (stored_bullets or {}).get("ytd_items", []),
            "prices": {m: stored_prices.get(m, {}) for m in months},
        },
    }


class InsertRequest(BaseModel):
    report_month: str
    file_name: str = ""
    month_items: List[str] = []
    ytd_items: List[str] = []
    # {series_code: {YYYY-MM: value}}
    prices: Dict[str, Dict[str, Optional[float]]] = {}


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

    db.log_extraction("SAIL", body.report_month, body.file_name or "commentary-market.pdf",
                      "Key Performance Parameters / Key Prices", "Commentary & Market PDF",
                      saved_bullets + saved_prices)
    auth.log_activity(user, "update", "commentary_market_upload", body.report_month)
    return {"status": "ok", "report_month": body.report_month,
            "bullets": saved_bullets, "prices": saved_prices}
