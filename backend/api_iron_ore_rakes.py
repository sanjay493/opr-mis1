"""
API for the mines' iron ore rake file (u_rakes_rmg.csv, one line per rake) —
see iron_ore_rakes.py for the parsing, the mines groups and the report page
(MIS PDF page 40.07; OGOM / JGOM on page 40.05). Uploaded on Data Entry >
Uploads; editors and admins only.

Flow (as /api/rake-despatch, except that the file itself is sent both times:
tens of thousands of rakes are not worth passing back and forth as JSON):
  1. POST /preview — read the file; returns its rakes, first and last date,
     and `months`: every month whose stored rake count the file changes.
     Nothing is saved.
  2. POST /insert  — save. The file replaces every rake stored between its
     first and last date. 409 when a month's count would fall unless
     confirm_replace=true.
"""
import traceback

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import auth as _auth
import iron_ore_rakes
from repo import rake as rrake

router = APIRouter(prefix="/api/iron-ore-rakes", tags=["iron-ore-rakes"])


async def _rakes(file: UploadFile) -> list:
    try:
        return iron_ore_rakes.parse_csv(iron_ore_rakes.read_file(await file.read()))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _summary(rows: list) -> dict:
    """What saving `rows` does to the stored month totals."""
    first, last = min(r["rpt_date"] for r in rows), max(r["rpt_date"] for r in rows)
    in_file = {}
    for r in rows:
        in_file[r["report_month"]] = in_file.get(r["report_month"], 0) + 1
    stored = rrake.iron_ore_rake_month_totals(first[:7], last[:7])
    kept = rrake.iron_ore_rake_totals_outside(first, last)       # stored rakes the file does not cover
    months = []
    for m in sorted(set(stored) | set(in_file)):
        after = kept.get(m, 0) + in_file.get(m, 0)
        if after != stored.get(m, 0):
            months.append({"report_month": m, "stored": stored.get(m, 0), "in_file": in_file.get(m, 0), "after": after})
    return {"rakes": len(rows), "first_date": first, "last_date": last, "months": months,
            "reduces": [m["report_month"] for m in months if m["after"] < m["stored"]]}


@router.post("/preview")
async def preview_iron_ore_rakes(file: UploadFile = File(..., description="u_rakes_rmg.csv"),
                                 user: dict = Depends(_auth.require_editor_or_admin)):
    rows = await _rakes(file)
    try:
        return {"status": "preview", "source_file": file.filename or "", **_summary(rows)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Could not check this file: {type(e).__name__}: {e}")


@router.post("/insert")
async def insert_iron_ore_rakes(file: UploadFile = File(..., description="u_rakes_rmg.csv"),
                                confirm_replace: str = Form(""),
                                user: dict = Depends(_auth.require_editor_or_admin)):
    rows = await _rakes(file)
    try:
        reduces = _summary(rows)["reduces"]
        if reduces and confirm_replace.lower() != "true":
            raise HTTPException(status_code=409, detail="This file has fewer rakes than are saved for: "
                                + ", ".join(reduces))
        return {"status": "ok", **rrake.save_iron_ore_rakes(rows, user.get("email"))}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Save failed: {type(e).__name__}: {e}")
