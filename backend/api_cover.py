"""
Selectable report covers — per-month design + photo choice and the
cover-photo library (cover_store.py, cover_designs.py, cover_render.py).

Endpoints:
  GET    /api/cover/designs                         – designs, Classic first
  GET    /api/cover/settings?month=                  – the month's choice (Classic when unsaved)
  POST   /api/cover/settings                         – save the month's choice
  POST   /api/cover/shuffle                          – new random photo for the month (saved)
  GET    /api/cover/photos                           – active library photos with usage
  POST   /api/cover/photos                           – upload one or more photos
  DELETE /api/cover/photos/{id}                      – remove from the library (file kept)
  GET    /api/cover/photos/{id}?size=thumb|full      – the image
  GET    /api/cover/html?month=&design=&photo_id=    – standalone A4 cover (preview iframe)

Handlers are plain `def` (FastAPI runs them in its threadpool); writes need
an editor or admin.
"""
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

import auth
import cover_designs
import cover_render
import cover_store

router = APIRouter(prefix="/api/cover", tags=["cover"])


class SettingsBody(BaseModel):
    month: str
    design: str
    photo_mode: str = "random"
    photo_id: Optional[int] = None


class ShuffleBody(BaseModel):
    month: str
    design: Optional[str] = None


def _public_photo(p: dict, used_by: Optional[int] = None) -> dict:
    return {
        "id": p["id"], "original_name": p["original_name"], "width": p["width"], "height": p["height"],
        "uploaded_by": p["uploaded_by"], "uploaded_at": p["uploaded_at"],
        "used_by": p.get("used_by", 0) if used_by is None else used_by,
        "thumb_url": f"/api/cover/photos/{p['id']}?size=thumb",
        "full_url": f"/api/cover/photos/{p['id']}?size=full",
    }


def _setting_response(month: str) -> dict:
    s = cover_store.get_setting(month)
    if not s:
        return {"month": month, "design": "classic", "photo_mode": "random",
                "photo_id": None, "photo": None, "saved": False}
    photo = None
    if s["photo_id"] is not None:
        active = {p["id"]: p for p in cover_store.list_photos()}
        if s["photo_id"] in active:
            photo = _public_photo(active[s["photo_id"]])
    return {"month": month, "design": s["design"], "photo_mode": s["photo_mode"],
            "photo_id": s["photo_id"], "photo": photo, "saved": True}


def _bad_request(e: Exception):
    raise HTTPException(status_code=400, detail=str(e))


@router.get("/designs")
def list_designs():
    return [{**d, "thumb_url": f"/cover/designs/{d['id']}.png"} for d in cover_designs.DESIGNS]


@router.get("/settings")
def get_settings(month: str = Query(...)):
    try:
        cover_store.check_month(month)
    except cover_store.CoverError as e:
        _bad_request(e)
    return _setting_response(month)


@router.post("/settings")
def save_settings(body: SettingsBody, user: dict = Depends(auth.require_editor_or_admin)):
    try:
        cover_store.save_setting(body.month, body.design, body.photo_mode, body.photo_id, user.get("email", ""))
    except cover_store.CoverError as e:
        _bad_request(e)
    return _setting_response(body.month)


@router.post("/shuffle")
def shuffle(body: ShuffleBody, user: dict = Depends(auth.require_editor_or_admin)):
    if body.design is not None and body.design not in cover_designs.DESIGN_IDS:
        _bad_request(cover_store.CoverError(f"Unknown cover design '{body.design}'."))
    try:
        cover_store.shuffle(body.month, user.get("email", ""), body.design)
    except cover_store.CoverError as e:
        _bad_request(e)
    return _setting_response(body.month)


@router.get("/photos")
def list_photos():
    return [_public_photo(p) for p in cover_store.list_photos()]


@router.post("/photos")
def upload_photos(files: List[UploadFile] = File(...), user: dict = Depends(auth.require_editor_or_admin)):
    created, errors = [], []
    for f in files:
        data = f.file.read(cover_store.MAX_UPLOAD_BYTES + 1)
        try:
            created.append(_public_photo(cover_store.add_photo(data, f.filename or "", user.get("email", "")), used_by=0))
        except cover_store.CoverError as e:
            errors.append({"name": f.filename or "", "detail": str(e)})
    if errors and not created:
        raise HTTPException(status_code=400, detail="; ".join(f"{x['name']}: {x['detail']}" for x in errors))
    return {"created": created, "errors": errors}


@router.delete("/photos/{photo_id}")
def remove_photo(photo_id: int, user: dict = Depends(auth.require_editor_or_admin)):
    if not cover_store.deactivate_photo(photo_id):
        raise HTTPException(status_code=404, detail="Photo not found.")
    return {"ok": True}


@router.get("/photos/{photo_id}")
def get_photo_file(photo_id: int, size: str = Query("thumb")):
    p = cover_store.get_photo(photo_id)
    path = cover_store.photo_path(p, "full" if size == "full" else "thumb") if p else None
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Photo not found.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.get("/html")
def cover_html(month: str = Query(...), design: Optional[str] = Query(None), photo_id: Optional[int] = Query(None)):
    try:
        cover_store.check_month(month)
    except cover_store.CoverError as e:
        _bad_request(e)
    if design is not None and design not in cover_designs.DESIGN_IDS:
        _bad_request(cover_store.CoverError(f"Unknown cover design '{design}'."))
    html = cover_render.cover_document(month, design=design, photo_id=photo_id)
    if html is None:
        raise HTTPException(status_code=404, detail="The Classic cover has no HTML preview.")
    return HTMLResponse(html)
