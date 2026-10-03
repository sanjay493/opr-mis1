"""
Cover-photo library and the per-month cover choice behind the selectable
report covers (docs/superpowers/specs/2026-10-03-selectable-cover-pages-
design.md).

Photos are stored as processed JPEGs in backend/cover_photos/ (gitignored,
served only through api_cover.py), one row each in cover_photos. "Remove"
only clears is_active, so a month that already used a photo keeps its file.
The month's cover (design + photo) lives in report_cover_settings; a month
with no row keeps the Classic cover (page_cover.py).

All SQL is sqlite-dialect through db.connect() (dbengine translates it for
MySQL). _connect and PHOTO_DIR are module attributes so tests can point
them at a temp SQLite file / folder.
"""
import io
import os
import random
import re
import uuid
from datetime import datetime

from PIL import Image, ImageOps

import cover_designs
import db

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTO_DIR = os.path.join(_BACKEND_DIR, "cover_photos")
# Shown when the library is empty (or every saved photo has gone missing).
BUNDLED_PHOTO = os.path.join(_BACKEND_DIR, "..", "frontend", "public", "cover", "hotmetal_bg.jpg")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
FULL_LONG_SIDE = 1600
THUMB_LONG_SIDE = 400
_FULL_QUALITY = 82
_THUMB_QUALITY = 78

SQLITE_DDL = [
    """CREATE TABLE IF NOT EXISTS cover_photos (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        filename       TEXT    NOT NULL,
        thumb_filename TEXT    NOT NULL,
        original_name  TEXT    NOT NULL,
        width          INTEGER,
        height         INTEGER,
        uploaded_by    TEXT,
        uploaded_at    TEXT,
        is_active      INTEGER NOT NULL DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS report_cover_settings (
        report_month TEXT PRIMARY KEY,
        design       TEXT NOT NULL,
        photo_mode   TEXT NOT NULL DEFAULT 'random',
        photo_id     INTEGER,
        updated_by   TEXT,
        updated_at   TEXT
    )""",
]

_PHOTO_COLS = ("id", "filename", "thumb_filename", "original_name", "width", "height",
               "uploaded_by", "uploaded_at", "is_active")


class CoverError(ValueError):
    """A user-facing problem with an upload or a cover choice (HTTP 400)."""


def _connect():
    db.init_db()
    return db.connect()


def _query(sql: str, args=()) -> list:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, args)
        return cur.fetchall()
    finally:
        conn.close()


def _execute(sql: str, args=()):
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _photo_dict(row) -> dict:
    d = dict(zip(_PHOTO_COLS, row))
    d["id"] = int(d["id"])
    d["is_active"] = int(d["is_active"])
    return d


# ── Photo library ────────────────────────────────────────────────────────────
def _jpeg(im: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def _process_image(data: bytes):
    """-> (full_jpeg, thumb_jpeg, width, height). Raises CoverError."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise CoverError("Photo is larger than 10 MB.")
    try:
        im = Image.open(io.BytesIO(data))
        fmt = im.format
        im.load()
    except Exception:
        raise CoverError("Not a readable image. Upload a JPEG or PNG photo.")
    if fmt not in ("JPEG", "PNG"):
        raise CoverError(f"{fmt} images aren't supported. Upload a JPEG or PNG photo.")
    im = ImageOps.exif_transpose(im).convert("RGB")
    full = im.copy()
    full.thumbnail((FULL_LONG_SIDE, FULL_LONG_SIDE), Image.LANCZOS)
    thumb = im.copy()
    thumb.thumbnail((THUMB_LONG_SIDE, THUMB_LONG_SIDE), Image.LANCZOS)
    return _jpeg(full, _FULL_QUALITY), _jpeg(thumb, _THUMB_QUALITY), full.width, full.height


def add_photo(data: bytes, original_name: str, uploaded_by: str) -> dict:
    full, thumb, width, height = _process_image(data)
    os.makedirs(PHOTO_DIR, exist_ok=True)
    stem = f"cp_{uuid.uuid4().hex[:16]}"
    fname, tname = f"{stem}.jpg", f"{stem}_thumb.jpg"
    paths = [os.path.join(PHOTO_DIR, fname), os.path.join(PHOTO_DIR, tname)]
    for path, content in zip(paths, (full, thumb)):
        with open(path, "wb") as f:
            f.write(content)
    name = os.path.basename((original_name or "").replace("\\", "/")) or "photo.jpg"
    try:
        new_id = _execute(
            "INSERT INTO cover_photos (filename, thumb_filename, original_name, width, height,"
            " uploaded_by, uploaded_at, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (fname, tname, name[:255], width, height, uploaded_by, _now()),
        )
    except Exception:
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                pass
        raise
    return get_photo(new_id)


def get_photo(photo_id: int):
    rows = _query(f"SELECT {', '.join(_PHOTO_COLS)} FROM cover_photos WHERE id = ?", (int(photo_id),))
    return _photo_dict(rows[0]) if rows else None


def list_photos() -> list:
    rows = _query(f"SELECT {', '.join(_PHOTO_COLS)} FROM cover_photos WHERE is_active = 1 ORDER BY id DESC")
    usage = {int(pid): int(n) for pid, n in _query(
        "SELECT photo_id, COUNT(*) FROM report_cover_settings WHERE photo_id IS NOT NULL GROUP BY photo_id")}
    out = []
    for row in rows:
        d = _photo_dict(row)
        d["used_by"] = usage.get(d["id"], 0)
        out.append(d)
    return out


def deactivate_photo(photo_id: int) -> bool:
    if get_photo(photo_id) is None:
        return False
    _execute("UPDATE cover_photos SET is_active = 0 WHERE id = ?", (int(photo_id),))
    return True


def photo_path(photo: dict, size: str = "full") -> str:
    return os.path.join(PHOTO_DIR, photo["thumb_filename"] if size == "thumb" else photo["filename"])


# ── Per-month cover choice ───────────────────────────────────────────────────
PHOTO_MODES = ("library", "random")
_SETTING_COLS = ("report_month", "design", "photo_mode", "photo_id", "updated_by", "updated_at")
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def check_month(month: str) -> str:
    if not isinstance(month, str) or not _MONTH_RE.match(month):
        raise CoverError("Month must look like YYYY-MM.")
    return month


def _active_photo_ids() -> list:
    """Active photos whose file is still on disk."""
    rows = _query(f"SELECT {', '.join(_PHOTO_COLS)} FROM cover_photos WHERE is_active = 1")
    return [p["id"] for p in map(_photo_dict, rows) if os.path.exists(photo_path(p))]


def _usable(photo_id) -> bool:
    if photo_id is None:
        return False
    p = get_photo(int(photo_id))
    return bool(p and p["is_active"] and os.path.exists(photo_path(p)))


def get_setting(month: str):
    rows = _query(f"SELECT {', '.join(_SETTING_COLS)} FROM report_cover_settings WHERE report_month = ?",
                  (check_month(month),))
    if not rows:
        return None
    d = dict(zip(_SETTING_COLS, rows[0]))
    d["photo_id"] = int(d["photo_id"]) if d["photo_id"] is not None else None
    return d


def save_setting(month: str, design: str, photo_mode: str = "random", photo_id=None, updated_by: str = "") -> dict:
    check_month(month)
    if design not in cover_designs.DESIGN_IDS:
        raise CoverError(f"Unknown cover design '{design}'.")
    if photo_mode not in PHOTO_MODES:
        raise CoverError("Photo choice must be 'library' or 'random'.")
    if photo_mode == "library":
        if not _usable(photo_id):
            raise CoverError("Choose a photo from the library.")
    elif not _usable(photo_id):
        ids = _active_photo_ids()
        photo_id = random.choice(ids) if ids else None
    _execute(
        "INSERT OR REPLACE INTO report_cover_settings"
        " (report_month, design, photo_mode, photo_id, updated_by, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (month, design, photo_mode, int(photo_id) if photo_id is not None else None, updated_by, _now()),
    )
    return get_setting(month)


def shuffle(month: str, updated_by: str = "", design=None) -> dict:
    """Pick a different random photo (when there is more than one) and save
    it in 'random' mode — with `design` if given, else the saved design."""
    current = get_setting(month)
    design = design or (current["design"] if current else "classic")
    if design == "classic":
        raise CoverError("The Classic cover has no photo to shuffle.")
    current_id = current["photo_id"] if current else None
    others = [i for i in _active_photo_ids() if i != current_id]
    photo_id = random.choice(others) if others else current_id
    return save_setting(month, design, "random", photo_id, updated_by)


def resolve_photo(photo_id):
    """-> (photo dict or None, file path) for rendering. A removed or missing
    saved photo falls back to a random active one, then to the bundled photo."""
    if _usable(photo_id):
        p = get_photo(int(photo_id))
        return p, photo_path(p)
    if photo_id is not None:
        print(f"[cover] photo {photo_id} is removed or missing on disk - using another photo")
    ids = _active_photo_ids()
    if ids:
        p = get_photo(random.choice(ids))
        return p, photo_path(p)
    return None, BUNDLED_PHOTO
