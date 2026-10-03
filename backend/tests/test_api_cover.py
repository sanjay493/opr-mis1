"""api_cover handlers, called directly (no HTTP client is installed in this
venv): validation -> 400, upload results, preview HTML."""

import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

import api_cover
import page_cover
from test_cover_store import img_bytes, store  # noqa: F401  (fixture)

EDITOR = {"email": "ed@sail.in", "role": "editor"}


def _upload(data, name="p.jpg"):
    return UploadFile(file=io.BytesIO(data), filename=name)


def test_designs_classic_first():
    ds = api_cover.list_designs()
    assert ds[0]["id"] == "classic" and ds[0]["thumb_url"] == "/cover/designs/classic.png"
    assert len(ds) == 6


def test_settings_default_is_unsaved_classic(store):
    s = api_cover.get_settings("2026-09")
    assert s == {"month": "2026-09", "design": "classic", "photo_mode": "random",
                 "photo_id": None, "photo": None, "saved": False}


def test_bad_month_is_400(store):
    with pytest.raises(HTTPException) as e:
        api_cover.get_settings("Sept")
    assert e.value.status_code == 400


def test_unknown_design_is_400(store):
    with pytest.raises(HTTPException) as e:
        api_cover.save_settings(api_cover.SettingsBody(month="2026-09", design="nope"), user=EDITOR)
    assert e.value.status_code == 400


def test_upload_then_save_library_choice(store):
    res = api_cover.upload_photos(files=[_upload(img_bytes()), _upload(b"nope", "notes.txt")], user=EDITOR)
    assert len(res["created"]) == 1 and res["errors"][0]["name"] == "notes.txt"
    pid = res["created"][0]["id"]
    assert res["created"][0]["thumb_url"] == f"/api/cover/photos/{pid}?size=thumb"
    s = api_cover.save_settings(api_cover.SettingsBody(month="2026-09", design="split", photo_mode="library", photo_id=pid), user=EDITOR)
    assert s["saved"] is True and s["photo"]["id"] == pid and s["photo"]["used_by"] == 1


def test_upload_all_bad_is_400(store):
    with pytest.raises(HTTPException) as e:
        api_cover.upload_photos(files=[_upload(b"nope", "a.jpg")], user=EDITOR)
    assert e.value.status_code == 400 and "JPEG or PNG" in e.value.detail


def test_photo_file_and_removal(store):
    pid = api_cover.upload_photos(files=[_upload(img_bytes())], user=EDITOR)["created"][0]["id"]
    assert api_cover.get_photo_file(pid, size="thumb").media_type == "image/jpeg"
    assert api_cover.remove_photo(pid, user=EDITOR) == {"ok": True}
    assert api_cover.list_photos() == []
    with pytest.raises(HTTPException) as e:
        api_cover.remove_photo(9999, user=EDITOR)
    assert e.value.status_code == 404


def test_preview_html(store, monkeypatch):
    monkeypatch.setattr(page_cover, "_kpi_row", lambda m, item: {"label": item.upper(), "kind": "steel", "mt": "1.000",
                                                                   "pct_ful": "99", "growth": 1, "growth_abs": 1, "growth_good": True})
    monkeypatch.setattr(page_cover, "_mines_kpi_row", lambda m, label, kind: {"label": label, "kind": "ore", "mt": "2.000",
                                                                               "pct_ful": "90", "growth": None, "growth_abs": None, "growth_good": None})
    resp = api_cover.cover_html(month="2026-09", design="split", photo_id=None)
    body = resp.body.decode("utf-8")
    assert resp.media_type == "text/html" and 'class="cover-split"' in body and "Sep-2026" in body
    with pytest.raises(HTTPException) as e:
        api_cover.cover_html(month="2026-09", design=None, photo_id=None)   # no setting -> Classic
    assert e.value.status_code == 404
