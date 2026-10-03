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


def _add(store, n=1):
    return [store.add_photo(img_bytes(color=(10 * i, 80, 20)), f"p{i}.jpg", "a@sail.in") for i in range(n)]


def test_month_without_setting_has_none(store):
    assert store.get_setting("2026-09") is None


def test_random_picks_an_active_photo_and_keeps_it(store):
    photos = _add(store, 3)
    s = store.save_setting("2026-09", "split", "random", None, "a@sail.in")
    assert s["design"] == "split" and s["photo_mode"] == "random"
    assert s["photo_id"] in {p["id"] for p in photos}
    for _ in range(5):
        assert store.get_setting("2026-09")["photo_id"] == s["photo_id"]


def test_random_with_given_photo_keeps_that_photo(store):
    a, b = _add(store, 2)
    assert store.save_setting("2026-09", "band", "random", b["id"], "x")["photo_id"] == b["id"]


def test_library_requires_an_active_photo(store):
    (a,) = _add(store, 1)
    assert store.save_setting("2026-09", "grid", "library", a["id"], "x")["photo_id"] == a["id"]
    store.deactivate_photo(a["id"])
    with pytest.raises(store.CoverError, match="photo"):
        store.save_setting("2026-10", "grid", "library", a["id"], "x")
    with pytest.raises(store.CoverError, match="photo"):
        store.save_setting("2026-10", "grid", "library", None, "x")


@pytest.mark.parametrize("month,design,mode", [
    ("2026-9", "split", "random"),
    ("2026-13", "split", "random"),
    ("2026-09", "nope", "random"),
    ("2026-09", "split", "sometimes"),
])
def test_invalid_choice_is_rejected(store, month, design, mode):
    with pytest.raises(store.CoverError):
        store.save_setting(month, design, mode, None, "x")


def test_saving_again_replaces_the_row(store):
    _add(store, 1)
    store.save_setting("2026-09", "split", "random", None, "x")
    store.save_setting("2026-09", "classic", "random", None, "y")
    s = store.get_setting("2026-09")
    assert s["design"] == "classic" and s["updated_by"] == "y"


def test_shuffle_changes_photo_when_possible(store):
    _add(store, 2)
    first = store.save_setting("2026-09", "split", "random", None, "x")["photo_id"]
    second = store.shuffle("2026-09", "x")["photo_id"]
    assert second != first
    assert store.get_setting("2026-09")["photo_id"] == second


def test_shuffle_with_one_photo_keeps_it(store):
    (a,) = _add(store, 1)
    store.save_setting("2026-09", "split", "random", None, "x")
    assert store.shuffle("2026-09", "x")["photo_id"] == a["id"]


def test_shuffle_with_design_saves_design_too(store):
    _add(store, 2)
    s = store.shuffle("2026-11", "x", design="editorial")
    assert s["design"] == "editorial" and s["photo_mode"] == "random" and s["photo_id"] is not None


def test_shuffle_classic_is_rejected(store):
    with pytest.raises(store.CoverError):
        store.shuffle("2026-09", "x")          # no setting -> classic


def test_resolve_saved_photo(store):
    a, b = _add(store, 2)
    photo, path = store.resolve_photo(b["id"], "2026-09")
    assert photo["id"] == b["id"] and path == store.photo_path(b)


def test_removed_photo_still_shown_on_months_that_used_it(store):
    """"Remove" only takes a photo out of the library: a month that already
    has it keeps it (the Remove dialog promises this)."""
    a, b = _add(store, 2)
    store.save_setting("2026-08", "split", "library", a["id"], "x")
    store.deactivate_photo(a["id"])
    photo, path = store.resolve_photo(a["id"], "2026-08")
    assert photo["id"] == a["id"] and path == store.photo_path(a)


def test_missing_file_falls_back_to_bundled_when_library_empty(store):
    (a,) = _add(store, 1)
    os.remove(store.photo_path(a))
    assert store.resolve_photo(a["id"], "2026-09") == (None, store.BUNDLED_PHOTO)


def test_fallback_photo_is_stable_per_month(store):
    """No usable saved photo -> the stand-in must be the same on every render
    of that month (preview == export)."""
    _add(store, 5)
    picks = {store.resolve_photo(None, "2026-09")[0]["id"] for _ in range(20)}
    assert len(picks) == 1
    gone = store.resolve_photo(999, "2026-09")[0]["id"]
    assert gone in {p["id"] for p in store.list_photos()}
    assert store.resolve_photo(999, "2026-09")[0]["id"] == gone


def test_multi_picture_phone_jpeg_is_accepted(store):
    """Ultra HDR / MPO JPEGs from phones open in Pillow as format 'MPO'."""
    buf = io.BytesIO()
    first = Image.new("RGB", (1200, 900), (200, 80, 20))
    first.save(buf, "MPO", save_all=True, append_images=[Image.new("RGB", (300, 225), (0, 0, 0))])
    p = store.add_photo(buf.getvalue(), "pixel.jpg", "a@sail.in")
    assert (p["width"], p["height"]) == (1200, 900)


def test_huge_pixel_count_is_rejected_before_decoding(store):
    buf = io.BytesIO()
    Image.new("1", (9000, 9000)).save(buf, "PNG")         # tiny file, 81 MP
    assert len(buf.getvalue()) < store.MAX_UPLOAD_BYTES
    with pytest.raises(store.CoverError, match="too large"):
        store.add_photo(buf.getvalue(), "huge.png", "a@sail.in")
    assert store.list_photos() == []


def test_resolve_with_empty_library_uses_bundled_photo(store):
    assert store.resolve_photo(None, "2026-09") == (None, store.BUNDLED_PHOTO)
    assert os.path.exists(store.BUNDLED_PHOTO)


def test_used_by_counts_months(store):
    (a,) = _add(store, 1)
    store.save_setting("2026-08", "split", "library", a["id"], "x")
    store.save_setting("2026-09", "band", "library", a["id"], "x")
    assert store.list_photos()[0]["used_by"] == 2
