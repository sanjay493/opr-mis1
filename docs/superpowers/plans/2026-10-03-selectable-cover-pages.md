# Selectable Cover Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an editor pick one of six report covers (Classic + 5 new Stitch-designed photo covers) per report month, with the photo picked from an in-app library or at random, shown in the /report preview and used by the PDF export.

**Architecture:** A new `cover_store.py` owns the photo library (files in `backend/cover_photos/`, table `cover_photos`) and the per-month choice (`report_cover_settings`). `page_cover.generate_cover()` reads the month's choice: Classic returns today's dict unchanged; a photo design adds `design`, `photo_data_uri` and `logo_data_uri`, and `cover.html` includes `cover_<design>.html`. The same template is rendered standalone by `cover_render.py` for the /report preview iframe (`/api/cover/html`). A new `api_cover.py` router serves settings, photos and the preview; the frontend adds a "Cover" sidebar card on /report and a "Cover Photos" data-entry tab.

**Tech Stack:** FastAPI, Jinja2, Pillow 12.3.0, Playwright (Chromium) + pypdf for render tests, MySQL/SQLite through `db.connect()`, Next.js 16 (React, CSS modules).

**Spec:** `docs/superpowers/specs/2026-10-03-selectable-cover-pages-design.md`

## Global Constraints

- Python: always `backend/venv/Scripts/python.exe -m <tool>` (pytest, py_compile, playwright). Never the system/anaconda Python, never `.exe` launchers.
- SQL: write sqlite-dialect SQL through `db.connect()`; new tables go in `backend/scripts/mysql_schema.sql`, a new `backend/scripts/migrate_add_cover_pages.sql`, and SQLite `init_db`.
- Months without a `report_cover_settings` row keep the Classic cover; Classic markup, `main.html` and `pdf.py` are not changed.
- New cover CSS lives only in its own `cover_<id>.html` `<style>` block, every class prefixed `cover-<id>`.
- New designs use only self-hosted fonts already embedded in every render: `IBM Plex Sans`, `IBM Plex Sans Condensed`, `Roboto`. No CDN, no Tailwind, no web requests (the PDF renders offline).
- Each design is a fixed box `width: 210mm; height: 296.5mm; overflow: hidden` (296.5mm, as Classic, so it never spills to a second page); the photo uses `object-fit: cover`.
- Uploads: JPEG or PNG only (decoded with Pillow), max 10 MB; stored as RGB JPEG, long side ≤ 1600 px (quality 82) plus a 400 px thumbnail.
- Writes (save setting, shuffle, upload, remove) require `auth.require_editor_or_admin`.
- Design ids: `classic`, `split`, `band`, `editorial`, `industrial`, `grid` (working names; renamed only in Task 3 if the user asks, and then everywhere).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. The `report_cover_settings` table is missing (MySQL migration not yet applied) or the DB errors → the report must still render the Classic cover, not fail page 1. Test in Task 4.
2. Extreme photo shapes (a tall phone portrait, a wide panorama) → every design still renders exactly one A4 page with no stretched photo. Test in Task 4/5 (parametrised photo shapes).
3. A WebP/GIF/HEIC file or a text file renamed `.jpg` → a clear 400 message naming JPEG/PNG; nothing stored. Test in Task 1.
4. A phone photo with EXIF rotation → stored upright. Test in Task 1.
5. A month with no figures yet (KPI values "—") → the cover still renders on one page with the dashes. Test in Task 4.

---

### Task 1: Cover-photo library store

**Files:**
- Create: `backend/cover_store.py`
- Create: `backend/scripts/migrate_add_cover_pages.sql`
- Modify: `backend/scripts/mysql_schema.sql` (append the two tables)
- Modify: `backend/db.py` (`init_db`, after the last `CREATE TABLE`)
- Modify: `.gitignore`
- Test: `backend/tests/test_cover_store.py`

**Interfaces:**
- Produces (used by Tasks 2, 4, 6):
  - `cover_store.PHOTO_DIR: str`, `BUNDLED_PHOTO: str`, `MAX_UPLOAD_BYTES = 10 * 1024 * 1024`, `FULL_LONG_SIDE = 1600`, `THUMB_LONG_SIDE = 400`
  - `cover_store.SQLITE_DDL: list[str]`
  - `class cover_store.CoverError(ValueError)` — user-facing problem → HTTP 400
  - `cover_store._connect()` — returns a DB connection (tests monkeypatch it)
  - `add_photo(data: bytes, original_name: str, uploaded_by: str) -> dict`
  - `get_photo(photo_id: int) -> dict | None` (inactive rows included)
  - `list_photos() -> list[dict]` (active only, newest first, each with `used_by: int`)
  - `deactivate_photo(photo_id: int) -> bool`
  - `photo_path(photo: dict, size: str = "full") -> str` (`size` is `"full"` or `"thumb"`)
  - Photo dict keys: `id, filename, thumb_filename, original_name, width, height, uploaded_by, uploaded_at, is_active`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_cover_store.py`:

```python
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
])
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `venv/Scripts/python.exe -m pytest tests/test_cover_store.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'cover_store'`.

- [ ] **Step 3: Implement `backend/cover_store.py` (library part)**

```python
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
```

(`random` and `re` are used by Task 2's functions in this same file.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_cover_store.py -v`
Expected: all PASS. If `test_bad_uploads...[GIF]` fails with a different message, check that the `fmt not in ("JPEG", "PNG")` branch runs after a successful `im.load()`.

- [ ] **Step 5: Schema for MySQL and SQLite**

Create `backend/scripts/migrate_add_cover_pages.sql`:

```sql
-- One-time migration: tables behind the selectable report covers
-- (docs/superpowers/specs/2026-10-03-selectable-cover-pages-design.md,
-- backend/cover_store.py). Additive only; safe to re-run.
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   then apply this file (see Task 1 Step 6 of the plan for the venv one-liner).

-- Cover-photo library. Files live in backend/cover_photos/; "Remove" sets
-- is_active = 0 and keeps the file for months that already used it.
CREATE TABLE IF NOT EXISTS cover_photos (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    filename       VARCHAR(64)  NOT NULL,
    thumb_filename VARCHAR(64)  NOT NULL,
    original_name  VARCHAR(255) NOT NULL,
    width          INT,
    height         INT,
    uploaded_by    VARCHAR(255),
    uploaded_at    CHAR(19),
    is_active      TINYINT(1)   NOT NULL DEFAULT 1
) ENGINE=InnoDB;

-- The cover chosen for one report month. No row = Classic cover.
-- photo_mode 'random' stores the photo it picked, so every export of the
-- month shows the same photo until someone presses Shuffle.
CREATE TABLE IF NOT EXISTS report_cover_settings (
    report_month CHAR(7)     NOT NULL PRIMARY KEY,
    design       VARCHAR(24) NOT NULL,
    photo_mode   VARCHAR(8)  NOT NULL DEFAULT 'random',
    photo_id     INT         NULL,
    updated_by   VARCHAR(255),
    updated_at   CHAR(19)
) ENGINE=InnoDB;
```

Append the same two `CREATE TABLE` statements (with a one-line comment pointing at `migrate_add_cover_pages.sql`) to the end of `backend/scripts/mysql_schema.sql`.

In `backend/db.py` `init_db()`, after the last `CREATE TABLE` executed there (before its final `conn.commit()`), add:

```python
    # Selectable report covers — DDL owned by cover_store (SQLite flavour
    # here; MySQL in scripts/mysql_schema.sql + migrate_add_cover_pages.sql).
    import cover_store
    for _ddl in cover_store.SQLITE_DDL:
        cursor.execute(_ddl)
```

Add to `.gitignore` (next to `backend/temp/`):

```
backend/cover_photos/
```

- [ ] **Step 6: Apply the migration to the local MySQL**

Run from `backend/`:

```bash
cmd //c "scripts\\backup_mysql.bat"
venv/Scripts/python.exe -c "import re,db; sql=open('scripts/migrate_add_cover_pages.sql',encoding='utf-8').read(); sql=re.sub(r'--[^\n]*','',sql); c=db.connect(); cur=c.cursor(); [cur.execute(s) for s in sql.split(';') if s.strip()]; c.commit(); c.close(); print('ok')"
venv/Scripts/python.exe -c "import db; c=db.connect(); cur=c.cursor(); cur.execute('SELECT COUNT(*) FROM report_cover_settings'); print(cur.fetchall()); cur.execute('SELECT COUNT(*) FROM cover_photos'); print(cur.fetchall())"
```

Expected: backup completes, `ok`, then `[(0,)]` twice.

- [ ] **Step 7: Compile, rerun, commit**

```bash
venv/Scripts/python.exe -m py_compile cover_store.py db.py
venv/Scripts/python.exe -m pytest tests/test_cover_store.py -q
cd .. && git add .gitignore backend/cover_store.py backend/db.py backend/scripts/mysql_schema.sql backend/scripts/migrate_add_cover_pages.sql backend/tests/test_cover_store.py
git commit -m "Cover photos: library store, upload processing, schema

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Per-month cover choice (settings, random, shuffle, fallbacks)

**Files:**
- Create: `backend/cover_designs.py`
- Modify: `backend/cover_store.py` (append)
- Test: `backend/tests/test_cover_store.py` (append)

**Interfaces:**
- Consumes: Task 1's `cover_store` functions and `CoverError`.
- Produces (used by Tasks 4, 6, 8):
  - `cover_designs.DESIGNS: list[dict]` (`{"id", "label"}`; Classic first), `DESIGN_IDS: tuple[str, ...]`, `PHOTO_DESIGN_IDS: tuple[str, ...]` (all but classic)
  - `cover_store.check_month(month: str) -> str` (raises `CoverError` unless `YYYY-MM`)
  - `cover_store.get_setting(month: str) -> dict | None` — keys `report_month, design, photo_mode, photo_id, updated_by, updated_at`
  - `cover_store.save_setting(month, design, photo_mode="random", photo_id=None, updated_by="") -> dict`
  - `cover_store.shuffle(month, updated_by="", design=None) -> dict`
  - `cover_store.resolve_photo(photo_id) -> tuple[dict | None, str]` — `(photo, file path)`; `(None, BUNDLED_PHOTO)` when the library is empty

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_cover_store.py`)

```python
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
    photo, path = store.resolve_photo(b["id"])
    assert photo["id"] == b["id"] and path == store.photo_path(b)


def test_resolve_falls_back_from_removed_or_missing_photo(store):
    a, b = _add(store, 2)
    store.deactivate_photo(a["id"])
    assert store.resolve_photo(a["id"])[0]["id"] == b["id"]
    os.remove(store.photo_path(b))
    photo, path = store.resolve_photo(b["id"])
    assert photo is None and path == store.BUNDLED_PHOTO


def test_resolve_with_empty_library_uses_bundled_photo(store):
    assert store.resolve_photo(None) == (None, store.BUNDLED_PHOTO)
    assert os.path.exists(store.BUNDLED_PHOTO)


def test_used_by_counts_months(store):
    (a,) = _add(store, 1)
    store.save_setting("2026-08", "split", "library", a["id"], "x")
    store.save_setting("2026-09", "band", "library", a["id"], "x")
    assert store.list_photos()[0]["used_by"] == 2
```

- [ ] **Step 2: Run to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_cover_store.py -v`
Expected: the new tests FAIL with `AttributeError: module 'cover_store' has no attribute 'get_setting'` (or `save_setting`, `shuffle`, `resolve_photo`); Task 1 tests still pass.

- [ ] **Step 3: Create `backend/cover_designs.py`**

```python
"""The report cover designs an editor can pick per month. 'classic' is the
original artwork cover (cover.html); every other id has its own
page_templates/cover_<id>.html with a photo area. Picker thumbnails are
frontend/public/cover/designs/<id>.png (scripts/render_cover_thumbs.py)."""

DESIGNS = [
    {"id": "classic", "label": "Classic"},
    {"id": "split", "label": "Split"},
    {"id": "band", "label": "Photo band"},
    {"id": "editorial", "label": "Editorial"},
    {"id": "industrial", "label": "Industrial"},
    {"id": "grid", "label": "Minimal grid"},
]
DESIGN_IDS = tuple(d["id"] for d in DESIGNS)
PHOTO_DESIGN_IDS = tuple(i for i in DESIGN_IDS if i != "classic")
```

- [ ] **Step 4: Append the settings functions to `backend/cover_store.py`**

Add `import cover_designs` to the imports at the top of the file (next to `import db`), then append:

```python
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
```

- [ ] **Step 5: Run the tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_cover_store.py -v`
Expected: all PASS.

- [ ] **Step 6: Check `INSERT OR REPLACE` against MySQL, then commit**

```bash
venv/Scripts/python.exe -c "import cover_store as c; print(c.save_setting('1999-01','classic','random',None,'plan-check')); print(c.save_setting('1999-01','classic','random',None,'plan-check-2')['updated_by']); import db; k=db.connect(); cur=k.cursor(); cur.execute(\"DELETE FROM report_cover_settings WHERE report_month='1999-01'\"); k.commit(); k.close(); print('cleaned')"
```

Expected: a dict with `design: 'classic'`, then `plan-check-2`, then `cleaned` (proves dbengine's upsert translation against the live MySQL).

```bash
venv/Scripts/python.exe -m py_compile cover_store.py cover_designs.py
cd .. && git add backend/cover_store.py backend/cover_designs.py backend/tests/test_cover_store.py
git commit -m "Cover settings: per-month design, random photo kept per month, shuffle, fallbacks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Design the five covers in Stitch (user approval gate)

No product code. The templates in Tasks 4–5 are built from the designs approved here.

**Files:**
- Create (scratchpad only, not committed): Stitch screenshots/HTML for each design.

- [ ] **Step 1: Check Stitch state**

Run: `stitch status --flow=design --json` — confirm signed in and project `16514915748983684874` bound.

- [ ] **Step 2: Generate the five screens**

For each direction run `stitch generate screen --project 16514915748983684874 --device DESKTOP --title "Cover – <Name>" --prompt "<prompt>"`, with this shared prompt text plus the direction line:

> A4 portrait (210 × 297 mm) printed cover page of a steel company's monthly operations report. Must contain, all visible: the SAIL logo (top), the title "Operations Monthly Informatics", the line "Operations Directorate", the report month large (e.g. "Sep-2026"), a heading "SAIL Performance at a Glance (Sep'26)", six KPI figures each with a label, a value in MT with 3 decimals, "APP 98%" and a small up/down growth % — Hot Metal 1.723 MT, Crude Steel 1.602 MT, Iron Ore Production 3.101 MT, Iron Ore Sales Despatch 0.412 MT, Finished Steel 1.398 MT, Saleable Steel 1.512 MT — "Prepared By: MIS Group", and a footer strip "MIS OPERATIONS | OMI – Sep'26 | FOR INTERNAL CIRCULATION ONLY". One clearly bounded photo area holding a steel-plant photograph (blast furnace / molten metal). Text never sits on the photo without a solid or strongly tinted backing. Fonts: IBM Plex Sans / IBM Plex Sans Condensed. Brand colours: navy #000c48, royal blue #0047c8, molten red #e8380d, ore rust #b4530a. Print-ready, no web UI elements, no buttons, no navigation.

Directions (id — line appended to the prompt):
- `split` — "Layout: vertical split; full-height photo on the left ~40% of the width, white content column on the right."
- `band` — "Layout: wide photo band across the top ~40% of the page, content below on white, KPIs as a 3×2 card grid."
- `editorial` — "Layout: magazine editorial; inset framed photo with a thin rule border, generous white space, serif-free large typographic month."
- `industrial` — "Layout: dark navy full page, photo in a large angled/clipped panel, KPIs as light outlined tiles; high contrast."
- `grid` — "Layout: minimal Swiss grid; photo occupies one grid block, thin hairlines separate blocks, KPIs as a 2×3 table-like grid."

- [ ] **Step 3: Show the five to the user and wait**

Print each screen link with `stitch url screen <screen-id> --project 16514915748983684874` and a screenshot (mcp chrome `save_to_disk`, since `stitch capture` needs headless Chrome which this machine lacks). Ask the user to approve or reject each. Regenerate rejected ones (`stitch generate variants --screen <id> --count 1 --creativeRange EXPLORE --aspects LAYOUT --prompt "<feedback>"`). Do not start Task 5 until all five are approved. If the user renames a design, update `cover_designs.DESIGNS` and every filename/test that uses the id.

- [ ] **Step 4: Save each approved design's HTML and screenshot to the scratchpad** as `cover_<id>.stitch.html` / `cover_<id>.stitch.png` for Tasks 4–5 (use the stitch CLI's screen export — `stitch --help` lists it; the screenshot from Step 3 is enough if export is unavailable).

---

### Task 4: Render pipeline + first design (`split`)

**Files:**
- Create: `backend/page_templates/cover_macros.html`
- Create: `backend/page_templates/cover_preview.html`
- Create: `backend/page_templates/cover_split.html`
- Create: `backend/cover_render.py`
- Modify: `backend/page_templates/cover.html` (wrap in a design dispatch)
- Modify: `backend/page_cover.py` (`generate_cover` signature + photo fields)
- Test: `backend/tests/test_cover_render.py`

**Interfaces:**
- Consumes: `cover_store.get_setting`, `cover_store.resolve_photo`, `cover_store.BUNDLED_PHOTO`, `cover_designs.DESIGN_IDS`.
- Produces (used by Tasks 5, 6, 7):
  - `page_cover.generate_cover(report_month: str, design: str | None = None, photo_id: int | None = None) -> dict` — Classic: exactly today's keys (`type, bg_data_uri, month_display, month_short, kpis`). Photo design: also `design, report_month, photo_id (int|None), photo_data_uri, logo_data_uri`.
  - `cover_render.render_cover_html(page: dict) -> str` — complete A4 HTML document
  - `cover_render.cover_document(month, design=None, photo_id=None) -> str | None` — `None` for Classic
  - `cover_render.sample_page(design: str, photo_uri: str | None = None, blank: bool = False) -> dict` — fixed figures for tests/thumbnails
  - Template contract for every `cover_<id>.html`: root `<div class="cover-<id>">`, own `<style>`, uses `page.photo_data_uri`, `page.logo_data_uri`, `page.month_display`, `page.month_short`, `page.kpis` via `kpi_cards(page.kpis, 'cover-<id>')`.

- [ ] **Step 1: Confirm the three fonts are in pdf's font map**

Run: `venv/Scripts/python.exe -c "import pdf; print([f in pdf._FONT_SLUGS for f in ('IBM Plex Sans','IBM Plex Sans Condensed','Roboto')])"`
Expected: `[True, True, True]`.

- [ ] **Step 2: Write the failing tests** — create `backend/tests/test_cover_render.py`:

```python
"""Photo cover designs: page data, dispatch, and a real one-page A4 render
per design (Playwright + pypdf), for normal, tall and wide photos and for a
month with no figures yet."""

import base64
import io

import pytest
from PIL import Image
from pypdf import PdfReader

import cover_designs
import cover_render
import cover_store
import page_cover

RENDERED_DESIGNS = ["split"]   # Task 5 replaces this with cover_designs.PHOTO_DESIGN_IDS


def _photo_uri(size):
    buf = io.BytesIO()
    Image.new("RGB", size, (180, 60, 20)).save(buf, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


def _pdf(browser, html):
    page = browser.new_page()
    page.set_content(html, wait_until="load")
    data = page.pdf(format="A4", print_background=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
    page.close()
    return PdfReader(io.BytesIO(data))


@pytest.mark.parametrize("design", RENDERED_DESIGNS)
@pytest.mark.parametrize("photo_size", [(1600, 1067), (900, 1600), (1600, 400)])
def test_design_renders_exactly_one_page(browser, design, photo_size):
    reader = _pdf(browser, cover_render.render_cover_html(
        cover_render.sample_page(design, photo_uri=_photo_uri(photo_size))))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    for needle in ("Sep-2026", "1.723", "Operations Monthly Informatics", "MIS Group"):
        assert needle in text, needle


@pytest.mark.parametrize("design", RENDERED_DESIGNS)
def test_month_without_figures_still_one_page(browser, design):
    reader = _pdf(browser, cover_render.render_cover_html(cover_render.sample_page(design, blank=True)))
    assert len(reader.pages) == 1
    assert "—" in reader.pages[0].extract_text()


def _stub_kpis(monkeypatch):
    monkeypatch.setattr(page_cover, "_kpi_row", lambda m, item: {"label": item.upper(), "kind": "steel", "mt": "1.000",
                                                                   "pct_ful": "99", "growth": 1, "growth_abs": 1, "growth_good": True})
    monkeypatch.setattr(page_cover, "_mines_kpi_row", lambda m, label, kind: {"label": label, "kind": "ore", "mt": "2.000",
                                                                               "pct_ful": "90", "growth": -1, "growth_abs": 1, "growth_good": False})


def test_month_without_setting_is_classic_unchanged(monkeypatch):
    _stub_kpis(monkeypatch)
    monkeypatch.setattr(cover_store, "get_setting", lambda m: None)
    page = page_cover.generate_cover("2026-09")
    assert set(page) == {"type", "bg_data_uri", "month_display", "month_short", "kpis"}


def test_settings_table_error_falls_back_to_classic(monkeypatch):
    _stub_kpis(monkeypatch)

    def boom(month):
        raise RuntimeError("Table 'mis_reports.report_cover_settings' doesn't exist")
    monkeypatch.setattr(cover_store, "get_setting", boom)
    assert "design" not in page_cover.generate_cover("2026-09")


def test_saved_photo_design_adds_photo_fields(monkeypatch):
    _stub_kpis(monkeypatch)
    monkeypatch.setattr(cover_store, "get_setting", lambda m: {"design": "split", "photo_mode": "random", "photo_id": 7})
    monkeypatch.setattr(cover_store, "resolve_photo", lambda pid: (None, cover_store.BUNDLED_PHOTO))
    page = page_cover.generate_cover("2026-09")
    assert page["design"] == "split" and page["report_month"] == "2026-09"
    assert page["photo_data_uri"].startswith("data:image/jpeg;base64,")
    assert page["logo_data_uri"].startswith("data:image/png;base64,")
    assert page["photo_id"] is None


def test_preview_override_beats_saved_setting(monkeypatch):
    _stub_kpis(monkeypatch)
    monkeypatch.setattr(cover_store, "get_setting", lambda m: {"design": "split", "photo_mode": "random", "photo_id": 7})
    seen = {}

    def fake_resolve(pid):
        seen["pid"] = pid
        return None, cover_store.BUNDLED_PHOTO
    monkeypatch.setattr(cover_store, "resolve_photo", fake_resolve)
    page = page_cover.generate_cover("2026-09", design="split", photo_id=3)
    assert seen["pid"] == 3 and page["design"] == "split"
    assert "design" not in page_cover.generate_cover("2026-09", design="classic")


def test_unknown_saved_design_renders_classic(monkeypatch):
    _stub_kpis(monkeypatch)
    monkeypatch.setattr(cover_store, "get_setting", lambda m: {"design": "retired", "photo_mode": "random", "photo_id": None})
    assert "design" not in page_cover.generate_cover("2026-09")


def test_cover_html_dispatch_includes_design_template():
    import pdf
    html = pdf._jinja_env.get_template("cover.html").render(page=cover_render.sample_page("split"), colors={})
    assert 'class="cover-split"' in html and "page1-container" not in html
```

- [ ] **Step 3: Run to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_cover_render.py -v`
Expected: `ModuleNotFoundError: No module named 'cover_render'`.

- [ ] **Step 4: Update `backend/page_cover.py`**

Add imports at the top (after `import db`):

```python
import cover_designs
import cover_store
```

Add after `_BG_PATH`:

```python
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "sail_logo.png")
_logo_cache = None


def _logo_data_uri() -> str:
    global _logo_cache
    if _logo_cache is None:
        _logo_cache = _file_data_uri(_LOGO_PATH, "image/png")
    return _logo_cache
```

Replace `generate_cover` with:

```python
def _saved_setting(report_month: str):
    """The month's saved cover choice, or None. Never fails the cover: if the
    settings table is missing (migration not applied) or the DB errors, the
    month simply keeps the Classic cover."""
    try:
        return cover_store.get_setting(report_month)
    except Exception as e:
        print(f"[cover] cover setting unavailable for {report_month} ({type(e).__name__}: {e}) - using Classic")
        return None


def generate_cover(report_month: str, design: str | None = None, photo_id: int | None = None) -> dict:
    """Page-1 data. `design`/`photo_id` override the saved choice (the /report
    preview of an unsaved pick); otherwise the month's saved setting is used,
    and a month with none keeps the Classic cover with exactly today's keys."""
    y, m = int(report_month[:4]), int(report_month[5:7])
    page = {
        "type": "cover",
        "bg_data_uri": _bg_data_uri(),
        "month_display": f"{_MON_ABBR[m]}-{y}",
        "month_short": f"{_MON_ABBR[m]}'{y % 100:02d}",
        # Honeycomb order = 3 columns of 2: left (Hot Metal / Crude Steel),
        # middle (the two Iron Ore Mines figures), right (Finished / Saleable
        # Steel). See .page1-hex-{0..5} in main.html.
        "kpis": [
            _kpi_row(report_month, "Hot Metal"),
            _kpi_row(report_month, "Crude Steel"),
            _mines_kpi_row(report_month, "IRON ORE PRODUCTION", "prod"),
            _mines_kpi_row(report_month, "IRON ORE SALES DESPATCH", "sales_despatch"),
            _kpi_row(report_month, "Finished Steel"),
            _kpi_row(report_month, "Saleable Steel"),
        ],
    }
    setting = _saved_setting(report_month)
    if design is None:
        design = setting["design"] if setting else "classic"
        photo_id = setting["photo_id"] if setting else None
    elif photo_id is None and setting:
        photo_id = setting["photo_id"]
    if design not in cover_designs.PHOTO_DESIGN_IDS:
        return page
    photo, path = cover_store.resolve_photo(photo_id)
    page.update({
        "design": design,
        "report_month": report_month,
        "photo_id": photo["id"] if photo else None,
        "photo_data_uri": _file_data_uri(path, "image/jpeg"),
        "logo_data_uri": _logo_data_uri(),
    })
    return page
```

Also add one paragraph to the module docstring: "Photo designs (cover_designs.PHOTO_DESIGN_IDS) are chosen per month in report_cover_settings (cover_store.py); they render page_templates/cover_<design>.html via cover.html, with the photo and logo embedded as data URIs for the same offline reason."

- [ ] **Step 5: Wrap `backend/page_templates/cover.html` in a dispatch**

Add as the first line:

```
{% if page.design and page.design != 'classic' %}{% include 'cover_' ~ page.design ~ '.html' %}{% else %}
```

and as the last line:

```
{% endif %}
```

Everything between stays byte-for-byte unchanged.

- [ ] **Step 6: Create `backend/page_templates/cover_macros.html`**

```
{# KPI cards shared by every photo cover design. `p` is the design's class
   prefix (e.g. 'cover-split'), so each design styles its own cards without
   any class shared across designs. #}
{% macro kpi_cards(kpis, p) -%}
{% for k in kpis %}
<div class="{{ p }}-kpi {{ p }}-kpi--{{ k.kind }}">
    <div class="{{ p }}-kpi-label">{{ k.label }}</div>
    <div class="{{ p }}-kpi-value">{{ k.mt }}<span class="{{ p }}-kpi-unit">MT</span></div>
    <div class="{{ p }}-kpi-sub">APP {{ k.pct_ful }}%{% if k.growth_good == true %} &middot; <span class="{{ p }}-up">&#9650;{{ k.growth_abs }}%</span>{% elif k.growth_good == false %} &middot; <span class="{{ p }}-down">&#9660;{{ k.growth_abs }}%</span>{% endif %}</div>
</div>
{% endfor %}
{%- endmacro %}
```

- [ ] **Step 7: Create `backend/page_templates/cover_preview.html`**

```html
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Cover {{ page.month_display }}</title>
<style>
{{ font_css }}
@page { size: A4 portrait; margin: 0; }
html, body { margin: 0; padding: 0; background: #ffffff; }
</style>
</head>
<body>{% include 'cover_' ~ page.design ~ '.html' %}</body>
</html>
```

- [ ] **Step 8: Create `backend/page_templates/cover_split.html`**

Start from this working layout; then restyle it to match the approved Stitch `split` screen (Task 3 Step 4), keeping the contract (root class, fixed box, fonts, every class prefixed `cover-split`, the KPI macro, the same text).

```html
{% from 'cover_macros.html' import kpi_cards %}
<style>
    .cover-split { position: relative; width: 210mm; height: 296.5mm; overflow: hidden; display: flex;
        background: #ffffff; color: #000c48; font-family: 'IBM Plex Sans', 'Roboto', Arial, sans-serif;
        font-size: 10pt; line-height: 1.3; }
    .cover-split-photo { position: relative; width: 84mm; height: 100%; flex: none; overflow: hidden; }
    .cover-split-photo img { display: block; width: 100%; height: 100%; object-fit: cover; }
    .cover-split-photo::after { content: ""; position: absolute; inset: 0;
        background: linear-gradient(180deg, rgba(0, 12, 72, 0) 55%, rgba(0, 12, 72, .55) 100%); }
    .cover-split-body { flex: 1; display: flex; flex-direction: column; padding: 18mm 14mm 9mm 14mm; }
    .cover-split-logo { height: 18mm; width: auto; align-self: flex-start; }
    .cover-split-title { margin-top: 14mm; font-family: 'IBM Plex Sans Condensed', 'IBM Plex Sans', sans-serif;
        font-size: 30pt; font-weight: 700; line-height: 1.05; }
    .cover-split-dir { margin-top: 3mm; font-size: 12pt; font-weight: 600; color: #0047c8;
        letter-spacing: .04em; text-transform: uppercase; }
    .cover-split-month { margin-top: 12mm; font-size: 40pt; font-weight: 700; line-height: 1; color: #e8380d; }
    .cover-split-heading { margin-top: 12mm; padding-bottom: 2mm; border-bottom: .5mm solid #0047c8;
        font-size: 10pt; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; }
    .cover-split-kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; margin-top: 5mm; }
    .cover-split-kpi { border-left: 1mm solid #0047c8; padding: 2mm 3mm; background: #f3f6fb; }
    .cover-split-kpi--ore { border-left-color: #b4530a; }
    .cover-split-kpi-label { font-size: 7.5pt; font-weight: 700; color: #4a5568; letter-spacing: .03em; }
    .cover-split-kpi-value { font-size: 17pt; font-weight: 700; }
    .cover-split-kpi-unit { margin-left: 1mm; font-size: 8pt; font-weight: 600; }
    .cover-split-kpi-sub { font-size: 8pt; color: #4a5568; }
    .cover-split-up { color: #064e3b; font-weight: 700; }
    .cover-split-down { color: #9a3412; font-weight: 700; }
    .cover-split-prepared { margin-top: auto; padding-bottom: 5mm; font-size: 10pt; }
    .cover-split-bar { position: absolute; left: 0; right: 0; bottom: 0; height: 9mm; display: flex;
        align-items: center; justify-content: center; gap: 3mm; background: #000c48; color: #ffffff;
        font-size: 7.5pt; letter-spacing: .08em; }
</style>
<div class="cover-split">
    <div class="cover-split-photo"><img src="{{ page.photo_data_uri }}" alt=""/></div>
    <div class="cover-split-body">
        {% if page.logo_data_uri %}<img class="cover-split-logo" src="{{ page.logo_data_uri }}" alt="SAIL"/>{% endif %}
        <div class="cover-split-title">Operations Monthly Informatics</div>
        <div class="cover-split-dir">Operations Directorate</div>
        <div class="cover-split-month">{{ page.month_display }}</div>
        <div class="cover-split-heading">SAIL Performance at a Glance ({{ page.month_short }})</div>
        <div class="cover-split-kpis">{{ kpi_cards(page.kpis, 'cover-split') }}</div>
        <div class="cover-split-prepared">Prepared By: <b>MIS Group</b></div>
    </div>
    <div class="cover-split-bar">
        <span>MIS OPERATIONS</span><span>|</span><span>OMI &ndash; {{ page.month_short }}</span><span>|</span><span>FOR INTERNAL CIRCULATION ONLY</span>
    </div>
</div>
```

- [ ] **Step 9: Create `backend/cover_render.py`**

```python
"""
Standalone HTML for a photo cover design (cover_designs.PHOTO_DESIGN_IDS):
the /report preview iframe (api_cover /api/cover/html), the per-design
render tests and the picker thumbnails. The PDF renders the very same
page_templates/cover_<design>.html inside main.html (via cover.html), so
preview and export can't drift apart.
"""
import functools

import cover_store
import page_cover
import pdf

# Every photo design uses only these (see the plan's Global Constraints);
# main.html already embeds all three for every PDF render.
_FONTS = ("IBM Plex Sans", "IBM Plex Sans Condensed", "Roboto")


@functools.lru_cache(maxsize=1)
def _font_css() -> str:
    return "\n".join(pdf._local_font_face_css(f) for f in _FONTS)


def render_cover_html(page: dict) -> str:
    return pdf._jinja_env.get_template("cover_preview.html").render(page=page, font_css=_font_css())


def cover_document(month: str, design=None, photo_id=None):
    """Full A4 HTML for the month's cover, or None when it is Classic."""
    page = page_cover.generate_cover(month, design=design, photo_id=photo_id)
    return render_cover_html(page) if page.get("design") else None


def _kpi(label, kind, mt, pct, growth):
    return {"label": label, "kind": kind, "mt": mt, "pct_ful": pct,
            "growth": growth, "growth_abs": abs(growth) if growth is not None else None,
            "growth_good": None if growth is None else growth >= 0}


def sample_page(design: str, photo_uri=None, blank: bool = False) -> dict:
    """Fixed Sep-2026 figures (or all '—' when blank) for tests/thumbnails."""
    rows = [("HOT METAL", "steel", "1.723", "98", 4), ("CRUDE STEEL", "steel", "1.602", "97", 3),
            ("IRON ORE PRODUCTION", "ore", "3.101", "101", 6), ("IRON ORE SALES DESPATCH", "ore", "0.412", "88", -5),
            ("FINISHED STEEL", "steel", "1.398", "95", 2), ("SALEABLE STEEL", "steel", "1.512", "96", -1)]
    kpis = [_kpi(lbl, kind, "—" if blank else mt, "—" if blank else pct, None if blank else g)
            for lbl, kind, mt, pct, g in rows]
    return {
        "type": "cover", "design": design, "report_month": "2026-09", "photo_id": None,
        "month_display": "Sep-2026", "month_short": "Sep'26", "kpis": kpis,
        "photo_data_uri": photo_uri or page_cover._file_data_uri(cover_store.BUNDLED_PHOTO, "image/jpeg"),
        "logo_data_uri": page_cover._logo_data_uri(),
    }
```

- [ ] **Step 10: Run the tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_cover_render.py -v`
Expected: all PASS. If the one-page test fails with 2 pages, the design box is taller than 296.5mm or something overflows outside it: fix the template's CSS, not the test.

- [ ] **Step 11: Check the PDF path for a photo design**

Classic is untouched; prove the include works inside `main.html` by rendering page 1 through the real exporter with a temporary setting:

```bash
venv/Scripts/python.exe -c "import cover_store; print(cover_store.save_setting('2026-08','split','random',None,'plan-check'))"
```

Open `http://localhost:3000/report`, choose Aug 2026, PDF export with only page 1 selected; confirm the downloaded PDF is one page, shows the split design with Aug-2026 figures, and the backend console shows no `LAYOUT WARNING` other than the changed-files notice. Then remove the temporary setting:

```bash
venv/Scripts/python.exe -c "import db; k=db.connect(); c=k.cursor(); c.execute(\"DELETE FROM report_cover_settings WHERE report_month='2026-08'\"); k.commit(); k.close(); print('removed')"
```

- [ ] **Step 12: Commit**

```bash
venv/Scripts/python.exe -m py_compile page_cover.py cover_render.py
cd .. && git add backend/page_cover.py backend/cover_render.py backend/page_templates/cover.html backend/page_templates/cover_macros.html backend/page_templates/cover_preview.html backend/page_templates/cover_split.html backend/tests/test_cover_render.py
git commit -m "Cover: photo design rendering (split), standalone preview HTML, Classic unchanged

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(The layout_guard pre-commit hook will list the new/changed templates as changed layout files; that is expected until Task 10 accepts the baseline. Classic's markup is unchanged.)

---

### Task 5: The other four designs + picker thumbnails

**Files:**
- Create: `backend/page_templates/cover_band.html`, `cover_editorial.html`, `cover_industrial.html`, `cover_grid.html`
- Create: `backend/scripts/render_cover_thumbs.py`
- Create: `frontend/public/cover/designs/{classic,split,band,editorial,industrial,grid}.png` (generated)
- Modify: `backend/tests/test_cover_render.py` (`RENDERED_DESIGNS`)

**Interfaces:**
- Consumes: Task 4's template contract, `cover_render.sample_page`, `cover_render.render_cover_html`, `page_cover._BG_PATH`.
- Produces: one template per id in `cover_designs.PHOTO_DESIGN_IDS`; thumbnails at `/cover/designs/<id>.png` (used by Task 6's `/designs` and Task 8's tiles).

- [ ] **Step 1: Make the render test cover every design**

In `backend/tests/test_cover_render.py` replace

```python
RENDERED_DESIGNS = ["split"]   # Task 5 replaces this with cover_designs.PHOTO_DESIGN_IDS
```

with

```python
RENDERED_DESIGNS = list(cover_designs.PHOTO_DESIGN_IDS)
```

Run: `venv/Scripts/python.exe -m pytest tests/test_cover_render.py -v`
Expected: `split` cases PASS; `band/editorial/industrial/grid` cases FAIL with `jinja2.exceptions.TemplateNotFound: cover_<id>.html`.

- [ ] **Step 2: Write each template from its approved Stitch design**

For each of `band`, `editorial`, `industrial`, `grid`, create `backend/page_templates/cover_<id>.html` with the same skeleton as `cover_split.html` (Task 4 Step 8): `{% from 'cover_macros.html' import kpi_cards %}`, a `<style>` block, root `<div class="cover-<id>">`, then the layout from `scratchpad/cover_<id>.stitch.html`/`.png`. Conversion rules:
- Rewrite every Tailwind utility as plain CSS under a `.cover-<id>-*` class; delete `<script>`/CDN `<link>` tags.
- Root: `position: relative; width: 210mm; height: 296.5mm; overflow: hidden;` plus explicit `font-size` and `line-height` (the PDF's `.cover-page` wrapper has `font-size: 0`).
- Units in `mm`/`pt` (it is a print page), fonts only `'IBM Plex Sans'`, `'IBM Plex Sans Condensed'`, `'Roboto'`.
- The photo is `<img src="{{ page.photo_data_uri }}">` in a fixed-size box with `object-fit: cover`; the logo is `{{ page.logo_data_uri }}`.
- KPIs via `{{ kpi_cards(page.kpis, 'cover-<id>') }}` styled with `.cover-<id>-kpi`, `-kpi--steel`, `-kpi--ore`, `-kpi-label`, `-kpi-value`, `-kpi-unit`, `-kpi-sub`, `-up`, `-down`.
- Text: "Operations Monthly Informatics", "Operations Directorate", `{{ page.month_display }}`, "SAIL Performance at a Glance ({{ page.month_short }})", "Prepared By: MIS Group", and the footer strip "MIS OPERATIONS | OMI – {{ page.month_short }} | FOR INTERNAL CIRCULATION ONLY".

After each template, run its cases: `venv/Scripts/python.exe -m pytest tests/test_cover_render.py -v -k <id>` — expected PASS (one page, all text found, all three photo shapes, blank month).

- [ ] **Step 3: Compare each render with its Stitch design**

Write the preview of each design to the scratchpad and look at it side by side with the Stitch screenshot:

```bash
venv/Scripts/python.exe -c "import cover_render,cover_designs; [open(rf'C:\Users\sanja\AppData\Local\Temp\claude\C--opr-mis1\43c0acc3-2b7a-4e01-ba75-5ecddfb532a3\scratchpad\preview_{d}.html','w',encoding='utf-8').write(cover_render.render_cover_html(cover_render.sample_page(d))) for d in cover_designs.PHOTO_DESIGN_IDS]"
```

Open each file in the browser (mcp chrome screenshot) and fix visible differences in the template CSS. Re-run the render tests after any change.

- [ ] **Step 4: Create `backend/scripts/render_cover_thumbs.py`**

```python
"""Writes frontend/public/cover/designs/<id>.png, the design tiles in the
/report Cover card: each photo design rendered with sample figures and the
bundled photo, plus Classic from its artwork. Re-run after editing any
page_templates/cover_<id>.html.

    backend\\venv\\Scripts\\python.exe -m scripts.render_cover_thumbs   (from backend/)
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

import cover_designs  # noqa: E402
import cover_render  # noqa: E402
import page_cover  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "public", "cover", "designs")
WIDTH = 300
HEIGHT = round(WIDTH * 297 / 210)


def _save(im: Image.Image, design: str) -> None:
    im.convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS).save(os.path.join(OUT_DIR, f"{design}.png"), optimize=True)
    print(f"wrote {design}.png")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    _save(Image.open(page_cover._BG_PATH), "classic")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 794, "height": 1123}, device_scale_factor=1)
        for design in cover_designs.PHOTO_DESIGN_IDS:
            page.set_content(cover_render.render_cover_html(cover_render.sample_page(design)), wait_until="load")
            _save(Image.open(io.BytesIO(page.screenshot(clip={"x": 0, "y": 0, "width": 794, "height": 1121}))), design)
        browser.close()


if __name__ == "__main__":
    main()
```

Run (from `backend/`): `venv/Scripts/python.exe -m scripts.render_cover_thumbs`
Expected: six `wrote <id>.png` lines; open two PNGs to check they show the designs.

- [ ] **Step 5: Full test run and commit**

```bash
venv/Scripts/python.exe -m pytest tests/test_cover_render.py tests/test_cover_store.py -q
cd .. && git add backend/page_templates/cover_band.html backend/page_templates/cover_editorial.html backend/page_templates/cover_industrial.html backend/page_templates/cover_grid.html backend/scripts/render_cover_thumbs.py backend/tests/test_cover_render.py frontend/public/cover/designs
git commit -m "Cover: band, editorial, industrial and grid designs from Stitch + picker thumbnails

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `/api/cover` router

**Files:**
- Create: `backend/api_cover.py`
- Modify: `backend/main.py` (import near line 434, `include_router` near line 894)
- Test: `backend/tests/test_api_cover.py`

**Interfaces:**
- Consumes: everything in `cover_store`, `cover_designs.DESIGNS/PHOTO_DESIGN_IDS`, `cover_render.cover_document`, `auth.require_editor_or_admin`.
- Produces (used by Tasks 7–9), all JSON unless noted:
  - `GET /api/cover/designs` → `[{id, label, thumb_url}]`
  - `GET /api/cover/settings?month=` → `{month, design, photo_mode, photo_id, photo, saved}` (`photo` = public photo dict or null)
  - `POST /api/cover/settings` body `{month, design, photo_mode, photo_id}` → same shape
  - `POST /api/cover/shuffle` body `{month, design?}` → same shape
  - `GET /api/cover/photos` → `[public photo]`; public photo = `{id, original_name, width, height, uploaded_by, uploaded_at, used_by, thumb_url, full_url}`
  - `POST /api/cover/photos` multipart field `files` (one or more) → `{created: [public photo], errors: [{name, detail}]}`; 400 when every file failed
  - `DELETE /api/cover/photos/{id}` → `{ok: true}`; 404 if unknown
  - `GET /api/cover/photos/{id}?size=thumb|full` → JPEG file; 404 if unknown/missing
  - `GET /api/cover/html?month=&design=&photo_id=` → HTML; 404 for Classic

- [ ] **Step 1: Write the failing tests** — create `backend/tests/test_api_cover.py`:

```python
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
    resp = api_cover.cover_html(month="2026-09", design="band", photo_id=None)
    body = resp.body.decode("utf-8")
    assert resp.media_type == "text/html" and 'class="cover-band"' in body and "Sep-2026" in body
    with pytest.raises(HTTPException) as e:
        api_cover.cover_html(month="2026-09", design=None, photo_id=None)   # no setting -> Classic
    assert e.value.status_code == 404
```

- [ ] **Step 2: Run to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_api_cover.py -v`
Expected: `ModuleNotFoundError: No module named 'api_cover'`.

- [ ] **Step 3: Create `backend/api_cover.py`**

```python
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
        usage = {p["id"]: p for p in cover_store.list_photos()}
        if s["photo_id"] in usage:
            photo = _public_photo(usage[s["photo_id"]])
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
```

- [ ] **Step 4: Register the router in `backend/main.py`**

After `from api_cost_trend_extract import router as cost_trend_extract_router` (≈ line 434) add:

```python
from api_cover import router as cover_router
```

After the last `app.include_router(...)` in that block add:

```python
app.include_router(cover_router)
```

- [ ] **Step 5: Run the tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_api_cover.py -v`
Expected: all PASS.

- [ ] **Step 6: Smoke-test the live dev backend** (uvicorn `--reload` picks the change up)

```bash
curl -s http://127.0.0.1:8082/api/cover/designs
curl -s "http://127.0.0.1:8082/api/cover/settings?month=2026-09"
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8082/api/cover/html?month=2026-09&design=split"
curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Content-Type: application/json" -d "{\"month\":\"2026-09\",\"design\":\"split\"}" http://127.0.0.1:8082/api/cover/settings
```

Expected: six designs; `{"month":"2026-09","design":"classic",...,"saved":false}`; `200`; `401` (not logged in — writes are protected).

- [ ] **Step 7: Commit**

```bash
venv/Scripts/python.exe -m py_compile api_cover.py main.py
cd .. && git add backend/api_cover.py backend/main.py backend/tests/test_api_cover.py
git commit -m "Cover: /api/cover router (designs, settings, shuffle, photo library, preview HTML)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Frontend API helper + cover preview iframe

**Files:**
- Create: `frontend/src/components/cover/coverApi.js`
- Modify: `frontend/src/components/CoverTemplate.js:82-92`

**Interfaces:**
- Consumes: Task 6 endpoints; page-1 data from `/api/data` now carrying `design`, `report_month`, `photo_id` for photo designs (Task 4).
- Produces (used by Tasks 8–9):
  - `coverApi.designs()`, `.settings(month)`, `.save({month, design, photo_mode, photo_id})`, `.shuffle(month, design)`, `.photos()`, `.upload(files)`, `.remove(id)` — each returns a Promise of parsed JSON and rejects with `Error(detail)` on non-2xx
  - `apiUrl(path) -> string`, `coverHtmlUrl(month, design, photoId) -> string`

- [ ] **Step 1: Create `frontend/src/components/cover/coverApi.js`**

```js
// Client for backend/api_cover.py (selectable report covers + photo library).
const API = process.env.NEXT_PUBLIC_API_URL || '';

export const apiUrl = (path) => `${API}${path}`;

async function call(path, options = {}) {
  const res = await fetch(apiUrl(path), { credentials: 'include', ...options });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const coverApi = {
  designs: () => call('/api/cover/designs'),
  settings: (month) => call(`/api/cover/settings?month=${encodeURIComponent(month)}`),
  save: (setting) => call('/api/cover/settings', json('POST', setting)),
  shuffle: (month, design) => call('/api/cover/shuffle', json('POST', { month, design })),
  photos: () => call('/api/cover/photos'),
  upload: (files) => {
    const form = new FormData();
    for (const f of files) form.append('files', f);
    return call('/api/cover/photos', { method: 'POST', body: form });
  },
  remove: (id) => call(`/api/cover/photos/${id}`, { method: 'DELETE' }),
};

export function coverHtmlUrl(month, design, photoId) {
  const q = new URLSearchParams({ month, design });
  if (photoId != null) q.set('photo_id', String(photoId));
  return apiUrl(`/api/cover/html?${q}`);
}
```

- [ ] **Step 2: Show photo designs in an iframe in `CoverTemplate.js`**

Confirm `CoverTemplate` uses no React hooks (it doesn't today; an early return before hooks would break the rules of hooks). Add the import at the top:

```js
import { coverHtmlUrl } from './cover/coverApi';
```

and make the start of the component:

```js
export default function CoverTemplate({ data }) {
  // Photo designs (cover_<design>.html) are rendered by the backend, the same
  // template the PDF uses — shown here as the cover document itself.
  if (data?.design && data.design !== 'classic' && data.report_month) {
    return (
      <iframe
        title={`Report cover (${data.design})`}
        src={coverHtmlUrl(data.report_month, data.design, data.photo_id)}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 0, display: 'block', background: '#fff' }}
      />
    );
  }

  const {
    bg_data_uri = '', month_display = '', month_short = '', kpis = [],
  } = data || {};
```

(the rest of the component is unchanged).

- [ ] **Step 3: Lint and check in the browser**

Run: `cd frontend && npm run lint` — expected: no new errors in these two files.

Temporarily save a photo design for Sep 2026 (`venv/Scripts/python.exe -c "import cover_store; cover_store.save_setting('2026-09','split','random',None,'plan-check')"` from `backend/`), open `http://localhost:3000/report`, choose September 2026, page 1: the split cover fills the A4 page at every zoom level, not cut off or offset. Then remove the row (same DELETE one-liner as Task 4 Step 11 with `'2026-09'`) and reload: Classic cover is back.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/cover/coverApi.js frontend/src/components/CoverTemplate.js
git commit -m "Report preview: show photo cover designs from the backend template

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: "Cover" card on the Report Engine sidebar

**Files:**
- Create: `frontend/src/components/cover/CoverCard.js`
- Create: `frontend/src/components/cover/PhotoGrid.js`
- Create: `frontend/src/components/cover/cover.module.css`
- Modify: `frontend/src/app/report/page.js` (state, effect, card placement before "PDF export")

**Interfaces:**
- Consumes: `coverApi`, `apiUrl` (Task 7); `useAuth()` from `@/providers/AuthProvider` (`user.role`); report sidebar classes from `@/app/report/report.module.css` (`card, cardHead, cardTitle, count, btn, seg, segBtn, segActive, row, linkBtn`).
- Produces:
  - `<CoverCard month canEdit onPreview />` — `onPreview({ design, photo_id, report_month })` is called whenever the shown cover changes
  - `<PhotoGrid photos selectedId onSelect onRemove compact />` — reused by Task 9

- [ ] **Step 1: Create `frontend/src/components/cover/cover.module.css`**

```css
.designs { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 10px; }
.design { padding: 0; border: 2px solid transparent; border-radius: 6px; background: none; cursor: pointer; text-align: center; font: inherit; }
.design img { display: block; width: 100%; aspect-ratio: 210 / 297; object-fit: cover; border-radius: 4px; border: 1px solid var(--ui-border); }
.design span { display: block; margin-top: 3px; font-size: 11px; color: var(--ui-text-secondary); }
.designActive { border-color: var(--ui-primary, #1a73e8); }
.designActive span { color: var(--ui-text, #202124); font-weight: 700; }
.design:disabled { cursor: default; }

.current { display: flex; gap: 8px; align-items: center; margin: 8px 0; font-size: 12px; color: var(--ui-text-secondary); }
.current img { width: 56px; height: 40px; object-fit: cover; border-radius: 4px; border: 1px solid var(--ui-border); }

.note { margin-top: 8px; font-size: 11.5px; color: #b06000; }
.error { margin-top: 8px; font-size: 11.5px; color: var(--ui-danger, #c5221f); }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.gridCompact { grid-template-columns: repeat(3, 1fr); gap: 6px; max-height: 240px; overflow: auto; margin-top: 8px; }
.tile { position: relative; padding: 0; border: 2px solid transparent; border-radius: 6px; background: var(--ui-surface, #fff); cursor: pointer; text-align: left; font: inherit; overflow: hidden; }
.tile img { display: block; width: 100%; aspect-ratio: 3 / 2; object-fit: cover; }
.tileActive { border-color: var(--ui-primary, #1a73e8); }
.meta { padding: 6px 8px; font-size: 11.5px; line-height: 1.4; color: var(--ui-text-secondary); }
.meta b { display: block; color: var(--ui-text, #202124); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.uploadTile { display: flex; align-items: center; justify-content: center; aspect-ratio: 3 / 2; border: 2px dashed var(--ui-border); border-radius: 6px; background: none; color: var(--ui-text-secondary); font: inherit; font-size: 12px; cursor: pointer; }
.remove { margin-top: 4px; }
```

- [ ] **Step 2: Create `frontend/src/components/cover/PhotoGrid.js`**

```js
'use client';

import { apiUrl } from './coverApi';
import c from './cover.module.css';

/** Thumbnails of library photos. `compact` = the small picker in the Cover
 *  card; otherwise the full grid with name/uploader/date/usage and Remove. */
export default function PhotoGrid({ photos, selectedId, onSelect, onRemove, compact = false, uploadTile = null }) {
  return (
    <div className={`${c.grid} ${compact ? c.gridCompact : ''}`}>
      {uploadTile}
      {photos.map((p) => (
        <div key={p.id}>
          <button type="button" className={`${c.tile} ${p.id === selectedId ? c.tileActive : ''}`}
                  aria-pressed={p.id === selectedId} title={p.original_name}
                  onClick={onSelect ? () => onSelect(p) : undefined} disabled={!onSelect}>
            {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API image, not a static asset */}
            <img src={apiUrl(p.thumb_url)} alt={p.original_name} loading="lazy" />
            {!compact && (
              <div className={c.meta}>
                <b>{p.original_name}</b>
                {p.uploaded_by} · {String(p.uploaded_at || '').slice(0, 10)}<br />
                {p.used_by ? `Used by ${p.used_by} month${p.used_by === 1 ? '' : 's'}` : 'Not used yet'}
              </div>
            )}
          </button>
          {onRemove && (
            <button type="button" className={c.remove} onClick={() => onRemove(p)}
                    style={{ border: 0, background: 'none', color: 'var(--ui-danger, #c5221f)', cursor: 'pointer', fontSize: 12, padding: 0 }}>
              Remove
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/cover/CoverCard.js`**

```js
'use client';

import { useEffect, useRef, useState } from 'react';
import s from '@/app/report/report.module.css';
import PhotoGrid from './PhotoGrid';
import { apiUrl, coverApi } from './coverApi';
import c from './cover.module.css';

const pickRandom = (photos, notId) => {
  const pool = photos.filter((p) => p.id !== notId);
  const from = pool.length ? pool : photos;
  return from.length ? from[Math.floor(Math.random() * from.length)].id : null;
};

const sameChoice = (a, b) =>
  a && b && a.design === b.design &&
  (a.design === 'classic' || (a.photo_mode === b.photo_mode && a.photo_id === b.photo_id));

/**
 * Report Engine sidebar card: pick the month's cover design and photo.
 * Changes preview immediately (onPreview); "Save cover" stores them and the
 * PDF export always uses the saved choice. Shuffle saves straight away.
 */
export default function CoverCard({ month, canEdit, onPreview }) {
  const [designs, setDesigns] = useState([]);
  const [photos, setPhotos] = useState([]);
  const [saved, setSaved] = useState(null);
  const [draft, setDraft] = useState(null);
  const [picker, setPicker] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    setPicker(false);
    Promise.all([coverApi.designs(), coverApi.settings(month), coverApi.photos()])
      .then(([d, st, ph]) => {
        if (!alive) return;
        setDesigns(d);
        setPhotos(ph);
        setSaved(st);
        setDraft({ design: st.design, photo_mode: st.photo_mode, photo_id: st.photo_id });
      })
      .catch((e) => alive && setError(e.message));
    return () => { alive = false; };
  }, [month]);

  const show = (next) => {
    setDraft(next);
    onPreview({ design: next.design, photo_id: next.photo_id, report_month: month });
  };

  const choose = (patch) => {
    const next = { ...draft, ...patch };
    if (next.design !== 'classic' && next.photo_mode === 'random' && next.photo_id == null) {
      next.photo_id = pickRandom(photos, null);
    }
    show(next);
  };

  const applySaved = (st) => {
    setSaved(st);
    show({ design: st.design, photo_mode: st.photo_mode, photo_id: st.photo_id });
  };

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  const save = () => run(async () => applySaved(await coverApi.save({ month, ...draft })));
  const shuffle = () => run(async () => applySaved(await coverApi.shuffle(month, draft.design)));
  const upload = (files) => run(async () => {
    const res = await coverApi.upload(files);
    setPhotos(await coverApi.photos());
    if (res.created.length) choose({ photo_mode: 'library', photo_id: res.created[0].id });
    if (res.errors.length) setError(res.errors.map((x) => `${x.name}: ${x.detail}`).join('; '));
  });

  if (!draft) {
    return (
      <section className={s.card}>
        <div className={s.cardHead}><h2 className={s.cardTitle}>Cover</h2></div>
        {error ? <div className={c.error}>{error}</div> : <div className={c.current}>Loading…</div>}
      </section>
    );
  }

  const label = designs.find((d) => d.id === draft.design)?.label || draft.design;
  const shownPhoto = photos.find((p) => p.id === draft.photo_id);
  const dirty = canEdit && !sameChoice(draft, saved);

  return (
    <section className={s.card}>
      <div className={s.cardHead}>
        <h2 className={s.cardTitle}>Cover</h2>
        <span className={s.count}>{label}</span>
      </div>

      <div className={c.designs} role="group" aria-label="Cover design">
        {designs.map((d) => (
          <button key={d.id} type="button" disabled={!canEdit}
                  className={`${c.design} ${d.id === draft.design ? c.designActive : ''}`}
                  aria-pressed={d.id === draft.design} onClick={() => choose({ design: d.id })}>
            {/* eslint-disable-next-line @next/next/no-img-element -- small static thumbnail */}
            <img src={d.thumb_url} alt="" />
            <span>{d.label}</span>
          </button>
        ))}
      </div>

      {draft.design !== 'classic' && (
        <>
          {canEdit && (
            <div className={s.seg} role="group" aria-label="Cover photo">
              {[['random', 'Random'], ['library', 'Choose from library']].map(([mode, text]) => (
                <button key={mode} type="button"
                        className={`${s.segBtn} ${draft.photo_mode === mode ? s.segActive : ''}`}
                        aria-pressed={draft.photo_mode === mode}
                        onClick={() => { choose({ photo_mode: mode }); setPicker(mode === 'library'); }}>
                  {text}
                </button>
              ))}
            </div>
          )}

          <div className={c.current}>
            {shownPhoto ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API image */}
                <img src={apiUrl(shownPhoto.thumb_url)} alt="" />
                <span>{shownPhoto.original_name}</span>
              </>
            ) : photos.length === 0 ? (
              <span>
                The photo library is empty, so the cover uses the built-in photo.{' '}
                <a href="/data-entry/reference?tab=cover-photos">Add photos</a>
              </span>
            ) : (
              <span>No photo chosen yet.</span>
            )}
          </div>

          {canEdit && draft.photo_mode === 'random' && photos.length > 1 && (
            <div className={s.row}>
              <button type="button" className={s.btn} onClick={shuffle} disabled={busy}
                      title="Pick and save another random photo for this month">🔀 Shuffle</button>
            </div>
          )}

          {canEdit && draft.photo_mode === 'library' && (
            <>
              {!picker && (
                <button type="button" className={s.linkBtn} onClick={() => setPicker(true)}>Change photo…</button>
              )}
              {picker && (
                <PhotoGrid compact photos={photos} selectedId={draft.photo_id}
                           onSelect={(p) => choose({ photo_id: p.id })}
                           uploadTile={(
                             <button type="button" className={c.uploadTile} onClick={() => fileRef.current?.click()} disabled={busy}>
                               + Upload new photo
                             </button>
                           )} />
              )}
              <input ref={fileRef} type="file" accept="image/jpeg,image/png" multiple hidden
                     onChange={(e) => { const f = [...e.target.files]; e.target.value = ''; if (f.length) upload(f); }} />
            </>
          )}
        </>
      )}

      {canEdit && (
        <div className={s.row} style={{ marginTop: 8 }}>
          <button type="button" className={s.btn} onClick={save} disabled={busy || !dirty}>
            {busy ? 'Saving…' : 'Save cover'}
          </button>
        </div>
      )}
      {dirty && <div className={c.note}>Not saved. The PDF uses the saved cover.</div>}
      {error && <div className={c.error}>{error}</div>}
    </section>
  );
}
```

- [ ] **Step 4: Wire the card into `frontend/src/app/report/page.js`**

Add imports with the others:

```js
import CoverCard from '@/components/cover/CoverCard';
import { useAuth } from '@/providers/AuthProvider';
```

Inside the component, next to the other `useState`s:

```js
  const { user } = useAuth();
  const canEditCover = user?.role === 'editor' || user?.role === 'admin';
  // Unsaved cover choice from the Cover card, merged into page 1's data so
  // the preview shows it; cleared when the month changes.
  const [coverPreview, setCoverPreview] = useState(null);
```

In the existing `useEffect` that runs `setPagesData([])` on `[selectedMonth]` (≈ line 357), also call `setCoverPreview(null);`.

After the `activePage` `useMemo`:

```js
  const coverLoaded = pagesData.some((p) => p.page === 1);
  useEffect(() => {
    if (!coverPreview || !coverLoaded) return;
    setPagesData((prev) => prev.map((p) => (p.page === 1 ? { ...p, ...coverPreview } : p)));
  }, [coverPreview, coverLoaded]);

  const handleCoverPreview = (preview) => {
    setCoverPreview(preview);
    setActivePageNum(1);
  };
```

In the sidebar JSX, directly before the `{/* PDF export */}` card:

```jsx
        {/* Cover design + photo */}
        <CoverCard month={selectedMonth} canEdit={canEditCover} onPreview={handleCoverPreview} />
```

Check `setActivePageNum` is the existing setter name for the active page (it is used by the page navigator's `onChange`); if `PAGE 1` uses a different key in `ALL_PAGE_NUMBERS`, pass that key.

- [ ] **Step 5: Lint, then check in the browser**

Run: `cd frontend && npm run lint` — expected: no new errors.

As an editor, on `http://localhost:3000/report` for September 2026:
1. Click each design tile → page 1 preview switches immediately; "Not saved" note appears.
2. Choose Random → a photo appears; Shuffle → a different photo and the note disappears (Shuffle saves).
3. Choose from library → picker; pick another photo → preview changes; "+ Upload new photo" with a JPEG → it appears and is selected.
4. Save cover → note disappears; reload the page → the saved cover is shown.
5. Select Classic and Save → Classic cover back (leave Sep 2026 on Classic unless the user wants to keep a design).
6. Log out (or use a viewer account): the card shows only the saved design, no controls.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/cover/CoverCard.js frontend/src/components/cover/PhotoGrid.js frontend/src/components/cover/cover.module.css frontend/src/app/report/page.js
git commit -m "Report Engine: Cover card to pick design and photo per month

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: "Cover Photos" library tab

**Files:**
- Create: `frontend/src/components/entry/cover-photos/Form.js`
- Modify: `frontend/src/components/entry/entryGroups.js` (reference group)
- Modify: `frontend/src/components/entry/EntryTabs.js` (`FORMS` map)

**Interfaces:**
- Consumes: `coverApi`, `PhotoGrid` (Tasks 7–8); `EntryPage, Section, Status, Loading, wb` from `../EntryUI`; `RequireEditor`.
- Produces: tab id `cover-photos` at `/data-entry/reference?tab=cover-photos` (linked from the Cover card's empty-library message).

- [ ] **Step 1: Create `frontend/src/components/entry/cover-photos/Form.js`**

```js
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import RequireEditor from '@/components/RequireEditor';
import PhotoGrid from '@/components/cover/PhotoGrid';
import { coverApi } from '@/components/cover/coverApi';
import { EntryPage, Section, Status, Loading, wb } from '../EntryUI';

function CoverPhotosInner() {
  const [photos, setPhotos] = useState(null);
  const [status, setStatus] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(() => (
    coverApi.photos().then(setPhotos).catch((e) => setStatus({ type: 'error', text: e.message }))
  ), []);

  useEffect(() => { load(); }, [load]);

  const upload = async (files) => {
    setUploading(true);
    setStatus(null);
    try {
      const res = await coverApi.upload(files);
      const bad = res.errors.map((x) => `${x.name}: ${x.detail}`).join('; ');
      setStatus(bad
        ? { type: 'error', text: `Added ${res.created.length}. Not added: ${bad}` }
        : { type: 'success', text: `Added ${res.created.length} photo${res.created.length === 1 ? '' : 's'}.` });
    } catch (e) {
      setStatus({ type: 'error', text: e.message });
    } finally {
      setUploading(false);
      load();
    }
  };

  const remove = async (p) => {
    if (p.used_by > 0 && !window.confirm(
      `"${p.original_name}" is the cover photo of ${p.used_by} month${p.used_by === 1 ? '' : 's'}. ` +
      'Those months keep it; it just leaves the library. Remove it?')) return;
    try {
      await coverApi.remove(p.id);
      setStatus({ type: 'success', text: `Removed "${p.original_name}".` });
    } catch (e) {
      setStatus({ type: 'error', text: e.message });
    }
    load();
  };

  return (
    <EntryPage
      title="Cover Photos"
      description="Photos for the report cover designs. The Cover card on the Report page picks one per month, or one at random. JPEG or PNG, up to 10 MB each; large photos are resized automatically."
    >
      <Status status={status} />
      <Section
        title="Library"
        sub={photos ? `${photos.length} photo${photos.length === 1 ? '' : 's'}` : ''}
        actions={(
          <>
            <button type="button" className={`${wb.btn} ${wb.btnPrimary}`} disabled={uploading}
                    onClick={() => fileRef.current?.click()}>
              {uploading ? 'Uploading…' : '⬆ Upload photos'}
            </button>
            <input ref={fileRef} type="file" accept="image/jpeg,image/png" multiple hidden
                   onChange={(e) => { const f = [...e.target.files]; e.target.value = ''; if (f.length) upload(f); }} />
          </>
        )}
        flush={false}
      >
        {photos === null ? <Loading /> : photos.length === 0 ? (
          <div className={wb.empty}>No photos yet. Upload plant photos to use them on report covers.</div>
        ) : (
          <PhotoGrid photos={photos} onRemove={remove} />
        )}
      </Section>
    </EntryPage>
  );
}

export default function CoverPhotosForm() {
  return (
    <RequireEditor>
      <CoverPhotosInner />
    </RequireEditor>
  );
}
```

Check `wb.empty`, `wb.btn`, `wb.btnPrimary` exist in `frontend/src/styles/wb.module.css` (they are used by the report views); if `Section` doesn't accept `flush`, drop that prop.

- [ ] **Step 2: Register the tab**

In `entryGroups.js`, in the `reference` group, change the description to `'BF benchmarking, rail, ready reckoner, major-unit daily records and cover photos.'` and append to its `tabs`:

```js
      { id: 'cover-photos', label: 'Cover Photos', description: 'Photo library for the report cover designs: upload, browse, remove.' },
```

In `EntryTabs.js` `FORMS`, after `'major-unit-daily'`:

```js
  'cover-photos': dynamic(() => import('./cover-photos/Form'), { loading }),
```

- [ ] **Step 3: Lint and check in the browser**

Run: `cd frontend && npm run lint` — expected: no new errors.

Open `http://localhost:3000/data-entry/reference?tab=cover-photos` as an editor: upload two JPEGs and one `.txt` (renamed `.jpg`) together → "Added 2. Not added: …JPEG or PNG"; the grid shows name, uploader, date, "Not used yet"; Remove an unused one → it disappears with no dialog. (Don't click Remove on a used photo during automated checks: it opens a confirm dialog that blocks the browser tools.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/entry/cover-photos/Form.js frontend/src/components/entry/entryGroups.js frontend/src/components/entry/EntryTabs.js
git commit -m "Data entry: Cover Photos library tab

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Whole-feature verification and layout baseline

**Files:**
- Modify: `backend/layout_baseline.json` (via `layout_guard.py --accept`)

- [ ] **Step 1: All backend tests**

Run (from `backend/`): `venv/Scripts/python.exe -m pytest tests -q`
Expected: all pass (existing golden tests unchanged).

- [ ] **Step 2: Classic is untouched in a real full render**

Confirm the reference month has no cover setting:

```bash
venv/Scripts/python.exe -c "import cover_store; print(cover_store.get_setting('2026-08'))"
```

Expected: `None`. Then run `venv/Scripts/python.exe layout_guard.py --render 2026-08`.
Expected: the only warnings are the changed/new layout files (`cover.html`, `cover_*.html`); the render comparison against the reference passes (same page count, no runtime layout warnings). If the comparison fails, stop: the Classic path changed and must be fixed before going on.

- [ ] **Step 3: Every design through the real PDF export**

For each id in `split band editorial industrial grid`: save it for 2026-08 (`cover_store.save_setting('2026-08', '<id>', 'random', None, 'plan-check')`), export page 1 only from `/report`, and check the PDF is one page with the design, the Aug-2026 month and figures. Finally delete the 2026-08 row (DELETE one-liner from Task 4 Step 11) so the reference month is Classic again.

- [ ] **Step 4: Accept the new layout baseline**

Run: `venv/Scripts/python.exe layout_guard.py --accept`
Then: `venv/Scripts/python.exe layout_guard.py` — expected `OK - all layout files match the baseline, no CSS class clashes.`

- [ ] **Step 5: Frontend lint**

Run: `cd frontend && npm run lint` — expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/layout_baseline.json
git commit -m "Layout baseline: accept new cover templates (Classic render verified unchanged)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Report to the user**

Summarise what shipped, that the `report_cover_settings`/`cover_photos` tables were added to the local MySQL (backup taken first), that the library is empty until photos are uploaded, and offer: push, rebuild the production frontend (`cd frontend && npm run build`), and restart the port-80 server.
