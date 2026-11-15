"""
API for the mines' iron ore rake file (u_rakes_rmg.csv) — see
iron_ore_rakes.py for the parsing, the lump / fines split, the mines groups
and the report page (MIS PDF page 40.07; OGOM / JGOM on page 40.05).
Uploaded on Data Entry > Uploads; editors and admins only.

Flow (as /api/rake-despatch, except that the file itself is sent both times:
tens of thousands of lines are not worth passing back and forth as JSON):
  1. POST /preview — read the file; returns its rakes, first and last date,
     `months`: every whole month whose stored rake total the file changes,
     `not_stored`: the months it holds only part of, and `skipped`: rakes
     left out for having no wagons. Nothing is saved.
  2. POST /insert  — save. The file replaces what is stored for each whole
     month it holds; other months stay. 409 when a month's total would fall
     unless confirm_replace=true.
"""
import traceback

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import auth as _auth
import iron_ore_rakes
from repo import rake as rrake

router = APIRouter(prefix="/api/iron-ore-rakes", tags=["iron-ore-rakes"])


async def _monthly(file: UploadFile) -> dict:
    try:
        return iron_ore_rakes.monthly_rows(iron_ore_rakes.parse_csv(iron_ore_rakes.read_file(await file.read())))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _summary(monthly: dict) -> dict:
    """What saving `monthly` (iron_ore_rakes.monthly_rows) does to the stored month totals."""
    in_file = {}
    for r in monthly["rows"]:
        in_file[r["report_month"]] = in_file.get(r["report_month"], 0) + r["lump_rakes"] + r["fines_rakes"]
    stored = rrake.iron_ore_rake_month_totals(monthly["months"][0], monthly["months"][-1])
    months = []
    for m in monthly["months"]:
        before, after = iron_ore_rakes.whole(stored.get(m, 0)), iron_ore_rakes.whole(in_file[m])
        if after != before:
            months.append({"report_month": m, "stored": before, "in_file": after, "after": after})
    return {"rakes": iron_ore_rakes.whole(sum(in_file.values())), "first_date": monthly["first_date"],
            "last_date": monthly["last_date"], "not_stored": monthly["not_stored"], "skipped": monthly["skipped"],
            "months": months, "reduces": [m["report_month"] for m in months if m["after"] < m["stored"]]}


@router.post("/preview")
async def preview_iron_ore_rakes(file: UploadFile = File(..., description="u_rakes_rmg.csv"),
                                 user: dict = Depends(_auth.require_editor_or_admin)):
    monthly = await _monthly(file)
    try:
        return {"status": "preview", "source_file": file.filename or "", **_summary(monthly)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Could not check this file: {type(e).__name__}: {e}")


@router.post("/insert")
async def insert_iron_ore_rakes(file: UploadFile = File(..., description="u_rakes_rmg.csv"),
                                confirm_replace: str = Form(""),
                                user: dict = Depends(_auth.require_editor_or_admin)):
    monthly = await _monthly(file)
    try:
        summary = _summary(monthly)
        if summary["reduces"] and confirm_replace.lower() != "true":
            raise HTTPException(status_code=409, detail="This file has fewer rakes than are saved for: "
                                + ", ".join(summary["reduces"]))
        saved = rrake.save_iron_ore_rakes(monthly["rows"], monthly["months"], user.get("email"))
        return {"status": "ok", "rakes": summary["rakes"], **saved}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Save failed: {type(e).__name__}: {e}")
