"""
API for the Rail Movement Cell's monthly Despatch Summary Report (rake
loading / despatch) — see excel_extractors/pdf_extractor_rake_despatch.py
for the parsing and rake_despatch_report.py for the report and insights
(Reports > Rail Logistics > Rake Despatch; web page only).

Flow (as /api/coal-co2):
  1. POST /preview — extract the PDF; returns the data, the PDF's own
     consistency `checks`, and `changes`: stored figures this file would
     change (a re-upload, or earlier months the file revises).
  2. POST /insert  — save the previewed data. 409 when it changes stored
     figures unless confirm_replace=true.
  3. GET /report?month=YYYY-MM — the report page's data.
     GET /months — uploaded months, newest first.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

sys.path.insert(0, str(Path(__file__).parent / "excel_extractors"))
from pdf_extractor_rake_despatch import extract  # noqa: E402

from api_unified_techno import _validate_month  # noqa: E402
from auth import get_current_user_optional  # noqa: E402
from repo import rake as rrake  # noqa: E402
import rake_despatch_report  # noqa: E402

router = APIRouter(prefix="/api/rake-despatch", tags=["rake-despatch"])


def _user_email(request: Request) -> Optional[str]:
    try:
        from auth import COOKIE_NAME
        user = get_current_user_optional(request.cookies.get(COOKIE_NAME))
        return user["email"] if user else None
    except Exception:
        return None


def _changes(data: dict) -> list:
    """Human-readable list of stored figures this upload would change."""
    out = []
    month = data["report_month"]
    if rrake.rake_despatch_upload(month):
        out.append(f"{month} has already been uploaded; its month-end position, slab and export figures are replaced.")
    types = data.get("types") or {}
    if types:
        stored = {}
        for r in rrake.rake_despatch_type_rows(min(types), max(types)):
            stored.setdefault(r["report_month"], {}).setdefault(r["plant_code"], {})[r["wagon_type"]] = r["rakes"]
        for m in sorted(types):
            for plant, by_type in types[m].items():
                old = stored.get(m, {}).get(plant)
                if old is not None and old != by_type:
                    out.append(f"{plant} {m}: wagon-type figures differ from those saved.")
    history = data.get("history") or {}
    if history:
        stored = {(r["report_month"], r["plant_code"]): r["rakes"]
                  for r in rrake.rake_despatch_history_rows(min(history), max(history))}
        diff = [f"{p} {m} ({stored[(m, p)]} -> {v})" for m in sorted(history) for p, v in history[m].items()
                if (m, p) in stored and stored[(m, p)] != v]
        if diff:
            out.append(f"Monthly history changes for {len(diff)} plant-month(s): " + ", ".join(diff[:12])
                       + (" ..." if len(diff) > 12 else ""))
    return out


@router.post("/preview")
async def preview_rake_despatch(file: UploadFile = File(..., description="Despatch Summary Report (.pdf)")):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        tmp.write(await file.read())
        tmp.close()
        try:
            data = extract(tmp.name)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return {
            "status": "preview",
            "source_file": file.filename or "",
            "data": data,
            "changes": _changes(data),
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Could not read this file: {type(e).__name__}: {e}")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@router.post("/insert")
async def insert_rake_despatch(payload: dict, request: Request):
    """Body: {data: <preview's data>, source_file, confirm_replace}."""
    data = payload.get("data") or {}
    try:
        _validate_month(data.get("report_month", ""))
        changes = _changes(data)
        if changes and not payload.get("confirm_replace"):
            raise HTTPException(status_code=409, detail="This upload changes saved figures:\n- " + "\n- ".join(changes))
        saved = rrake.save_rake_despatch(data, payload.get("source_file"), _user_email(request))
        return {"status": "ok", **saved}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Save failed: {type(e).__name__}: {e}")


@router.get("/months")
def rake_despatch_months():
    return [{"report_month": u["report_month"], "as_on": str(u["as_on"]), "source_file": u["source_file"]}
            for u in rrake.rake_despatch_months()]


@router.get("/report")
def rake_despatch_report_data(month: str = Query(..., description="YYYY-MM")):
    _validate_month(month)
    return rake_despatch_report.build_report(month)
