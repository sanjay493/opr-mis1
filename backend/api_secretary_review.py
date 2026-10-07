"""Secretary Review deck: month context, editable narrative and the .pptx
download. See page_secretary_review.py."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

import page_secretary_review as psr
import page_secretary_review_texts as pst
import secretary_review_text as srt
from secretary_review_layout import BLOCKS, validate_month

# Plain `def` handlers: building the context, defaults and the deck takes
# seconds, so FastAPI runs them in its threadpool instead of blocking the
# event loop. POST and DELETE /texts are gated by constants.PAGE_MODULES["secretary_review"].
router = APIRouter(prefix="/api/secretary-review", tags=["secretary-review"])

_KEYS = {k for k, _, _ in BLOCKS}
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _texts(payload):
    """Known block keys only; values coerced to str (None -> "")."""
    return {k: "" if v is None else str(v) for k, v in (payload.get("texts") or {}).items() if k in _KEYS}


def _month(month):
    if not validate_month(month or ""):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    return month


@router.get("/context")
def context(month: str = Query(None)):
    if month is None:
        month = psr.latest_month()
        if month is None:
            raise HTTPException(status_code=404, detail="No production data in the DB")
    _month(month)
    ctx = psr.build_context(month)
    summary = [{"item": name, **{k: ctx["production"][key]["SAIL"][k] for k in ("app_m", "act_m", "app_ytd", "act_ytd")}}
               for key, name in psr.ITEMS]
    return {"labels": ctx["labels"], "filename": ctx["labels"]["filename"],
            "warnings": ctx["warnings"], "summary": summary}


@router.get("/texts")
def get_texts(month: str = Query(...)):
    _month(month)
    eff = pst.effective_texts(month)
    return {"month": month,
            "blocks": [{"key": k, "section": s, "label": lbl, **eff[k]} for k, s, lbl in BLOCKS]}


@router.post("/texts")
def save_texts(payload: dict):
    month = _month(payload.get("month"))
    texts = _texts(payload)
    return {"saved": srt.save_texts(month, texts)}


@router.delete("/texts")
def unlink_text(month: str = Query(...), block: str = Query(...)):
    """"Reset from DB": drop the block's saved text so it follows the DB
    default again; returns that default."""
    _month(month)
    if block not in _KEYS:
        raise HTTPException(status_code=400, detail=f"unknown block {block!r}")
    srt.delete_texts(month, [block])
    return {"key": block, "text": pst.default_text(month, block), "saved": False}


@router.get("/default-text")
def default_text(month: str = Query(...), block: str = Query(...)):
    _month(month)
    if block not in _KEYS:
        raise HTTPException(status_code=400, detail=f"unknown block {block!r}")
    return {"key": block, "text": pst.default_text(month, block)}


@router.post("/pptx")
def pptx(payload: dict):
    month = _month(payload.get("month"))
    texts = _texts(payload)
    try:
        res = psr.render_pptx(month, texts)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Secretary Review template missing: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Secretary Review generation failed: {e}")
    return Response(content=res.content, media_type=_PPTX,
                    headers={"Content-Disposition": f'attachment; filename="{res.filename}"',
                             "X-Warnings-Count": str(len(res.warnings)),
                             "Access-Control-Expose-Headers": "Content-Disposition, X-Warnings-Count"})
