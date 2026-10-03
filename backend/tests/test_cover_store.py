"""Cover-photo library + per-month cover choice (cover_store.py).

Runs against a throwaway SQLite file and photo folder: cover_store._connect
and cover_store.PHOTO_DIR are monkeypatched, so no MySQL is needed.
"""

import io
import os
import sqlite3

import pytest
from PIL import Image

import cover_store


@pytest.fixture
def store(tmp_path, monkeypatch):
    dbfile = tmp_path / "cover.db"

    def _conn():
        return sqlite3.connect(dbfile)

    conn = _conn()
    for ddl in cover_store.SQLITE_DDL:
        conn.execute(ddl)
    conn.commit()
    conn.close()
    monkeypatch.setattr(cover_store, "_connect", _conn)
    monkeypatch.setattr(cover_store, "PHOTO_DIR", str(tmp_path / "photos"))
    return cover_store


def img_bytes(fmt="JPEG", size=(3000, 2000), color=(200, 80, 20), exif=None):
    buf = io.BytesIO()
    im = Image.new("RGB", size, color)
    if exif is not None:
        im.save(buf, fmt, exif=exif)
    else:
        im.save(buf, fmt)
    return buf.getvalue()


def test_upload_jpeg_is_resized_and_listed(store):
    p = store.add_photo(img_bytes(size=(3000, 2000)), "plant.jpg", "a@sail.in")
    assert p["width"] == 1600 and p["height"] in (1066, 1067)
    assert p["original_name"] == "plant.jpg" and p["uploaded_by"] == "a@sail.in" and p["is_active"] == 1
    with Image.open(store.photo_path(p)) as full:
        assert full.format == "JPEG" and max(full.size) == 1600
    with Image.open(store.photo_path(p, "thumb")) as thumb:
        assert max(thumb.size) == 400
    listed = store.list_photos()
    assert [x["id"] for x in listed] == [p["id"]] and listed[0]["used_by"] == 0


def test_small_png_is_converted_not_enlarged(store):
    p = store.add_photo(img_bytes("PNG", size=(800, 600)), "small.png", "a@sail.in")
    assert (p["width"], p["height"]) == (800, 600)
    with Image.open(store.photo_path(p)) as full:
        assert full.format == "JPEG"


def test_original_name_keeps_only_the_file_name(store):
    p = store.add_photo(img_bytes(), "C:\\Users\\x\\Pictures\\bf5.jpg", "a@sail.in")
    assert p["original_name"] == "bf5.jpg"


@pytest.mark.parametrize("data,msg", [
    (b"hello, not an image", "JPEG or PNG"),
    (img_bytes()[:200], "JPEG or PNG"),          # truncated / corrupt JPEG
    (img_bytes("GIF"), "JPEG or PNG"),
    (img_bytes("WEBP"), "JPEG or PNG"),
    (b"\xff" * (10 * 1024 * 1024 + 1), "10 MB"),
], ids=["text", "corrupt-jpeg", "gif", "webp", "over-10mb"])
def test_bad_uploads_are_rejected_and_nothing_stored(store, data, msg):
    with pytest.raises(store.CoverError, match=msg):
        store.add_photo(data, "x.jpg", "a@sail.in")
    assert store.list_photos() == []
    assert not os.path.isdir(store.PHOTO_DIR) or os.listdir(store.PHOTO_DIR) == []


def test_exif_rotated_phone_photo_is_stored_upright(store):
    exif = Image.Exif()
    exif[0x0112] = 6  # "rotate 90° CW to display"
    p = store.add_photo(img_bytes(size=(1200, 600), exif=exif), "phone.jpg", "a@sail.in")
    assert p["height"] > p["width"]


def test_deactivate_hides_photo_but_keeps_file(store):
    p = store.add_photo(img_bytes(), "a.jpg", "a@sail.in")
    assert store.deactivate_photo(p["id"]) is True
    assert store.list_photos() == []
    assert store.get_photo(p["id"])["is_active"] == 0
    assert os.path.exists(store.photo_path(p))
    assert store.deactivate_photo(999) is False
