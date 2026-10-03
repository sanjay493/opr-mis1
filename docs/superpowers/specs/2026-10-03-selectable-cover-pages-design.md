# Selectable cover pages with a cover-photo library

Date: 2026-10-03
Status: approved design (brainstorming), pending spec review

## Goal

Give the monthly OMI report a choice of cover. Five new cover designs are
created with Stitch; for any report month an editor picks one of six covers
(today's "Classic" cover plus the five new ones). New covers carry a photo
area whose image is either picked from an in-app cover-photo library
(including a freshly uploaded photo) or chosen at random from that library.

### What the user asked for

- 5 more cover pages, designed with Stitch.
- The user selects any one cover for generating any month's PDF.
- The cover image can be a custom user selection or a random image.

### Decisions taken during brainstorming

| Topic | Decision |
|---|---|
| Role of the image | A photo panel inside each new design (logo, title, month and KPIs are drawn by the design itself, so text stays readable on any photo) |
| Photo source | An in-app cover-photo library; uploads add to it |
| Random behaviour | Picked once and saved per month (preview = every export); a Shuffle button picks again |
| Cover content | Same as today on all 5 new designs (logo, "Operations Monthly Informatics", Operations Directorate, "Prepared By: MIS Group", report month, the 6 KPI figures with APP % and growth) |
| Build approach | One Jinja template per new design, used by the PDF and shown in the /report preview as server-rendered HTML (no duplicate React version) |

### Success criteria

1. Every existing month renders exactly as before (Classic cover, unchanged
   layout, `layout_guard` baseline untouched).
2. For any month an editor can choose a design and a photo (library pick,
   new upload, or random), see it in the /report preview, save it, and the
   exported PDF uses that cover.
3. Random is stable: the same month always shows the same random photo
   until someone presses Shuffle.
4. Each new design always renders as exactly one A4 page, with any photo
   shape (cropped to fill, never stretched or overflowing).
5. The PDF still renders offline (photo and fonts embedded, no network).

## Out of scope

- Changing the Classic cover or any other report page.
- Editing cover text (title, "Prepared By") per month.
- Per-design colour themes chosen by the user.
- Image editing (crop/position controls) beyond automatic cover-crop.

## Data model

Both tables are added to `backend/scripts/mysql_schema.sql`, a new
`backend/scripts/migrate_cover_pages.sql`, and `db.init_db()`'s SQLite
CREATE TABLEs (CLAUDE.md: a new table needs both). Code keeps writing
sqlite-dialect SQL through `db.connect()`.

### `cover_photos`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK autoincrement | |
| filename | TEXT | stored file name in `backend/cover_photos/` (generated, e.g. `cp_<id>_<hash>.jpg`) |
| original_name | TEXT | uploaded file's name, for display |
| width, height | INTEGER | after processing |
| uploaded_by | TEXT | user email |
| uploaded_at | TEXT | `YYYY-MM-DD HH:MM:SS` |
| is_active | INTEGER | 1 = in library; "Remove" sets 0 (file kept) |

### `report_cover_settings`

| Column | Type | Notes |
|---|---|---|
| report_month | TEXT PK | `YYYY-MM` |
| design | TEXT | `classic` or one of the 5 new design ids |
| photo_mode | TEXT | `library` or `random` |
| photo_id | INTEGER NULL | the photo shown; for `random`, the photo picked and saved |
| updated_by, updated_at | TEXT | |

A month with no row = `design='classic'` (current behaviour).

### Photo files

- Stored under `backend/cover_photos/` (gitignored), served only through the
  API.
- On upload: accept JPEG/PNG only (checked by decoding with Pillow, not by
  extension), max 10 MB; convert to RGB JPEG, resize so the long side is at
  most 1600 px, quality ~82. Keeps an embedded photo to a few hundred KB.
- A 400 px thumbnail is generated alongside (`..._thumb.jpg`) for the
  library and picker grids.
- Pillow (already pinned at 12.3.0 in `requirements.txt`) does the
  processing; no new dependency.
- `backend/cover_photos/` is added to `.gitignore`.

## Designs

### Ids

`classic` (existing) plus five new ids, finalised after the Stitch review,
working names: `split`, `band`, `editorial`, `industrial`, `grid`.

### Creation with Stitch

1. Generate 5 A4-portrait screens in the bound Stitch project
   (16514915748983684874), one per direction, each with all cover content
   listed above and a clearly bounded photo area, using a real plant photo
   as the placeholder.
2. Show all five to the user; regenerate any that are rejected. No template
   is built until the user approves the set.
3. Save a PNG thumbnail of each approved design to
   `frontend/public/cover/designs/<id>.png` for the picker tiles.

### Templates

- One template per new design: `backend/page_templates/cover_<id>.html`.
- `cover.html` dispatches on `page.design`: `classic` keeps today's markup
  unchanged; any other id includes `cover_<id>.html`.
- Each new template carries its own CSS in a `<style>` block scoped under
  `.cover-<id>` — nothing is added to `main.html`, so the millimetre-tuned
  page CSS is untouched.
- Stitch's HTML uses the Tailwind CDN; it is rewritten as plain CSS, since
  the PDF renders offline. Fonts come only from the self-hosted set in
  `backend/fonts/` (IBM Plex Sans / Condensed, Roboto, Lato, Noto Sans,
  Source Sans 3).
- The cover box is fixed at A4 (210 × 297 mm) with `overflow: hidden`; the
  photo uses `object-fit: cover` inside its fixed-size area.
- KPI markup reuses the existing `page.kpis` list (label, mt, pct_ful,
  growth_good, growth_abs, kind) already produced by `page_cover.py`.

## Rendering

### `page_cover.py`

- Reads the month's `report_cover_settings` row (absent → `classic`).
- `classic`: unchanged output.
- Other designs: adds `design` and `photo_data_uri` (base64 JPEG) to the
  same page dict; KPI computation unchanged.
- Photo resolution order: saved `photo_id` if its file exists and it is
  active → else a random active library photo → else the bundled
  `frontend/public/cover/hotmetal_bg.jpg`. A missing saved photo is logged,
  not an error.

### Preview

- `GET /api/cover/html?month=YYYY-MM[&design=&photo_id=]` returns the cover
  page alone as a complete A4 HTML document, built with the same Jinja
  environment, fonts and template as the PDF. The optional parameters
  preview an unsaved choice.
- On `/report`, when page 1 uses a non-Classic design, `CoverTemplate`
  renders an `<iframe>` (A4-sized, no border) pointing at that endpoint;
  Classic keeps today's React rendering.
- The full-report PDF export already sends page 1 through `page_cover.py`,
  so the exported cover follows the saved setting with no export changes.

## API

All under `/api/cover`. Writes require `require_editor_or_admin`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/settings?month=` | `{design, photo_mode, photo_id, photo, saved}`; `photo` is the resolved photo or null, `saved` is false when the month has no row |
| POST | `/settings` | body `{month, design, photo_mode, photo_id?}`; `random` with no photo_id picks one and stores it |
| POST | `/shuffle?month=` | picks a different random active photo (if more than one exists), saves, returns the setting |
| GET | `/photos` | active library photos with usage count (months using each) |
| POST | `/photos` | multipart upload of one or more files; returns created photos; rejects non-images / >10 MB with 400 |
| DELETE | `/photos/{id}` | sets `is_active = 0` |
| GET | `/photos/{id}?size=` | serves the image file; `size` is `thumb` (default) or `full` |
| GET | `/html?month=&design=&photo_id=` | standalone cover HTML (preview) |
| GET | `/designs` | `[{id, label, thumb_url}]` — Classic first |

## UI

### Report Engine sidebar (`/report`) — new "Cover" card

- Design: 6 thumbnail tiles (Classic + 5); selecting one previews page 1
  immediately.
- Photo (hidden for Classic): `Random` | `Choose from library`.
  - Random shows the picked photo's thumbnail and a Shuffle button.
  - Choose from library opens a picker grid of library thumbnails plus an
    "Upload new photo" tile.
- "Save cover" stores the month's setting. While the shown choice differs
  from the saved one, the card shows "Not saved — PDF uses the saved cover".
- Non-editors see the saved cover only (controls hidden).

### Cover Photos library — new tab under Data Entry → Reference & Records

- Upload area (multiple files), using the shared EntryUI components.
- Grid of thumbnails: original name, uploader, date, "used by N months",
  Remove (soft delete, with confirmation when N > 0).
- Added via `components/entry/cover-photos/Form.js`, `entryGroups.js` and
  the `FORMS` map in `EntryTabs.js` (CLAUDE.md).

## Error handling

- Upload of a non-image, corrupt image or > 10 MB file → 400 with a clear
  message; nothing stored.
- Settings with an unknown design id → 400.
- Missing photo at render time → fallback chain above, never a broken cover.
- Empty library + Random → bundled photo, and the Cover card says the
  library is empty with a link to the Cover Photos tab.

## Testing

Backend (`backend/tests/test_cover_pages.py`, DB-backed like the other
tests, temp photo dir):

- Month without a setting → `classic`, page dict identical to today's.
- Saving `random` picks an active photo and stores it; reading again
  returns the same photo; Shuffle changes it when ≥ 2 photos exist.
- Hidden or missing-file photo → falls back to another active photo; empty
  library → bundled photo.
- Upload: valid JPEG/PNG stored and resized (long side ≤ 1600 px); text
  file / corrupt image / oversized file rejected.
- Unknown design → 400.
- Render: for each new design, build a cover-only PDF with Playwright and
  assert it has exactly 1 page and contains the month text.

PDF layout:

- `python layout_guard.py --render 2026-09` with no cover settings saved:
  output unchanged against the current baseline (Classic untouched).

Browser:

- Cover card: switch designs, pick/upload/shuffle, save, export page 1.
- Cover Photos tab: upload, list, remove.

## Rollout

- No data migration needed: months without settings keep Classic.
- After deployment, upload a starter set of plant photos to the library so
  Random has variety.
