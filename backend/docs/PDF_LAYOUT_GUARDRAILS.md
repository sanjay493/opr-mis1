# PDF Report Layout — Guardrails & Recovery

The monthly MIS PDF is laid out to the millimetre. Small, innocent-looking
changes have broken it before, in ways that only show up in a **full**
export. This document lists what controls the layout, what goes wrong, how
it's detected, and how to put it back.

**Known-good layout:** git tag `pdf-layout-baseline-2026-09-25`
(full report for Aug 2026: 103 pages incl. Annexure-III, sequential
footers, trend section 12 pages, no layout warnings).

---

## 1. Quick recovery

Something looks wrong in the PDF (pages shrunk with empty space at the
bottom, trend tables breaking oddly, one page's styling suddenly different)?

```bat
cd C:\opr-mis1\backend

rem 1. What changed since the known-good layout?
venv\Scripts\python.exe layout_guard.py

rem 2. Restore one file to the known-good version (repeat per file listed)
git checkout pdf-layout-baseline-2026-09-25 -- backend/page_templates/main.html

rem 3. ...or restore EVERY layout file at once
git checkout pdf-layout-baseline-2026-09-25 -- backend/pdf.py backend/layout_config.json backend/chart_utils.py backend/page_at_a_glance.py backend/page_special_steel_donut.py backend/page_coal_consumption.py backend/page_templates

rem 4. Verify with a real render (about 1-2 minutes)
venv\Scripts\python.exe layout_guard.py --render 2026-08
```

`--render 2026-08` compares against the recorded reference render. Any other
month runs every layout check but skips the page-count comparison (page
counts legitimately vary with each month's data).

The dev server reloads by itself after a restore. A production server needs
a restart (`start-production.bat`).

---

## 2. What warns you, and when

| When | What you see | Where |
|---|---|---|
| **Every PDF render** | `[pdf] LAYOUT WARNING: ...` lines, then a summary at the end of the render | Backend console window |
| **Every `git commit`** that touches a layout file | A boxed "PDF LAYOUT WARNING" listing the files (never blocks the commit) | Git output |
| **Claude Code edits** a layout file | "PDF LAYOUT WARNING: backend/... controls the PDF layout" | Claude Code UI (also tells Claude to warn you and verify) |
| **On demand** | Full report of changed files + CSS class clashes | `venv\Scripts\python.exe layout_guard.py` |

What each runtime warning means:

| Warning (starts with) | Meaning | What to do |
|---|---|---|
| `... is changed since the layout baseline` | A layout-critical file differs from the recorded baseline | Intended change: verify (`--render`) then `--accept`. Accidental: restore it (section 1) |
| `content is still Npx wider than the printable area` | Something is wider than the page and isn't inside a `.page` block, so **Chromium will shrink every page in the report** | Find the element (usually new markup outside the per-page wrapper) and make it fit the width |
| `page X had to be shrunk to NN% to fit` | One page's content outgrew the page; it's legible below 85% only with difficulty | Tighten that page (fonts, padding, column widths) instead of relying on the automatic shrink |
| `trend section: ... split leaves only N row(s)` | A plant group split with fewer than 3 rows on one page | Should never happen; a code change broke `_plan_trend_layout` — restore `pdf.py` / `trend_section.html` |
| `trend section: ... span a page break inside one block` | One unbreakable row block is taller than a page | A group grew past one page (font/padding growth in `production_trend.css`?) |
| `page-split planning did not settle` | Trend pages kept changing between checks | Restore the trend files; report if it persists |
| `no layout baseline recorded` | `backend/layout_baseline.json` is missing | Restore it from git, or run `layout_guard.py --accept --render <month>` |

---

## 3. What controls the layout (the protected files)

Every file below is fingerprinted in `backend/layout_baseline.json`.
Changing any of them triggers the warnings in section 2. The guard section
names in brackets match what the warnings print.

### Render pipeline (pdf.py)

| Setting | Value | Why it matters |
|---|---|---|
| `_MAIN_MARGIN` | 10 / 15 / 9 / 15 mm (top/right/bottom/left) | Printable area for report pages; every probe print must use the same value |
| `_FRONT_MARGIN` | 8 / 13 / 8 / 13 mm | Index page |
| Landscape print margin | 12 / 10 / 10 / 10 mm | `_render_landscape_page_pdf` |
| `_PRINTABLE_PORTRAIT_MM` / `_LANDSCAPE_MM` | 180 x 278 mm / 277 x 188 mm | Must equal page size minus the margins above |
| `prefer_css_page_size=True` | on | Off lets one overflowing page shrink the whole document |
| `_VFIT_MAX_OVERFLOW` | 1.10 | A single page up to 10% too tall is scaled to fit one sheet |
| `_MIN_LEGIBLE_ZOOM` | 0.85 | Below this, a legibility warning is raised |
| Width fit margin | 1% (`W * 0.99` in `_FIT_PAGES_JS`) | Rounding can otherwise land a pixel over the edge |
| `_TREND_MIN_SPLIT_ROWS` | 3 | Minimum rows of a plant group on each side of a page break |
| `_TREND_MIN_TOP/BOTTOM_MARGIN_MM` | 4 / 2 mm | Tightest trend-section margins tried (only kept if they save a page) |
| `_LANDSCAPE_TYPES` | bf_large_annexure, cost_trend, special_steel_physical, epi, rail_report, market_prices, macro_indicators | These print in separate landscape runs |
| `_page_texts_many` | pdfium in a **child process** | pdfium in-process crashed the server twice; keep it isolated |

**Per-page fit-to-page** (`_fit_pages_for_print`): just before every print,
each `.page` block is measured at the real printable width. Too wide gets
scaled to fit that page only; up to 10% too tall gets scaled to fit one
sheet (unless the page has `data-vfit="off"`). Everything else prints at
100%. As of the baseline (2026-08 render) these pages are fitted: 2.2
(96%), 24 (92%), 38 (96%); landscape 2.41, 2.42, 1025 (95–97%).

**Vertical fill** (techno pages 27–30/29.5, Power Data 35.7): a table marked `data-vgrow`
(with `data-vgrow-mm` / `data-vgrow-wmm`, its real usable height/width on
paper) gets its body-cell padding bisected up until the page fills its
sheet, laid out at that real width while measuring. `data-vgrow-step`
snaps the growth to a multiple (Power Data: 0.5px, so its whole-px rows stay
whole - fractional rows print with an uneven baseline rhythm). Page 27 can still need
width-shrinking late in the FY (March: ~83%, 21 columns).

### Global CSS (main.html)

- **`@page` rules and `.page`**: every report page is one
  `<div class="page ...">` with `break-after: page`. **Do not** add
  `break-inside: avoid` to `.page`. It made overflowing pages break at
  arbitrary points.
- **`data-vfit="off"`** on Ready Reckoner pages (split onto 2 pages instead of
  shrinking their 12pt text) and page 3 (has its own overflow handling).
- **`.ssp-*` classes belong to Steel Sector Performance** (pages 2.1–2.3).
  `.ssp-table` has `table-layout: fixed`; those pages were tuned against it.

### Page templates & per-page `<style>` blocks

All `page_templates/*.html`. **The rule that matters:** every page is
rendered into ONE HTML document, so a class styled in one template's own
`<style>` block restyles every other page using that class, **but only in
exports that include both pages**. That's why a full export looked different
from a single-page export (Steel Sales `.ssp-table` leaking onto Steel Sector,
fixed 2026-09-23 by renaming Steel Sales to `sls-*`).

- Give each template's classes a unique prefix (`sls-`, `rdd-`, `mi-`, ...).
- `layout_guard.py` scans every template for such clashes on each run.

### Production trend pages

`page_templates/trend_section.html` and `page_templates/css/production_trend.css`:

- Each plant/SAIL group is one or more `<tbody class="plant-group">` blocks
  with `break-inside: avoid`. Chromium only breaks pages **between** blocks
  and repeats the table header.
- `pdf.py`'s `_plan_trend_layout` decides the blocks. A test print of the
  trend section cuts each group into its first 3 rows, single middle rows,
  and its last 3 rows, so Chromium can only break a group where at least 3
  rows land on each page. Each resulting piece then gets its own plant label,
  and a second test print verifies. About 5 seconds, cached per data set.
- `.page7-13-legend` has `break-before: avoid` (never alone on a page).
- **Don't** reintroduce forced `break_before` rows or a whole-report
  probe/correct loop. That old approach took ~20 minutes and left stray
  breaks.

### Per-page margins & fonts (layout_config.json)

Global: IBM Plex Sans, title 13pt, heading 12pt, table th 11 / td 11.5pt.
Per-page margins (mm, top/bottom/sides): 3: 7/5/7 · 4: 5/3/7 · 5–6: 7/5/7 ·
7–13 (trend): 7/5/0.18 · 17: 0/0/3 fit · 27: 3/1.5/4 fit · 28–30: 4/3/4 fit ·
31–35: 4/3/6 fit · 18.5: 5/3/6 fit · 2.41: 6/4/8 fit · 2.42: 6/4/8.

### Charts

| File | Chart | Key settings |
|---|---|---|
| `chart_utils.py` | shared | `own_scale()` per-series scale; `axis_break_svg()` zig-zag break mark |
| `page_at_a_glance.py` | Production Trend — Last 4 Years | each item on its own scale, bars 55%–90% of plot height |
| `page_at_a_glance.py` | Value Added Steel (5 years, quarter) | % bars 38%–70%; qty line spans its full band |
| `page_coal_consumption.py` | % Imported Coking Coal in Blend | each plant 35%–88%, half-size break marks |
| `page_special_steel_donut.py` | Value-Addition bubble chart (page 24) | `vh=750` (page fits one sheet), axis text `axis_fs = 23` units = 11pt |

Close-range charts deliberately **don't start at zero**, so each one has a
break mark and a "not from 0" note. Keep both if you touch them.

---

## 4. Failure modes seen before (and their causes)

| Symptom | Cause | Guard |
|---|---|---|
| Every page slightly smaller, empty band at the bottom | One page wider than the printable area; Chromium shrinks the **whole** print job (was 94.7% for months) | Per-page fit + "wider than the printable area" warning |
| A page's tables look different only in the full report | CSS class defined in one template's `<style>` leaking into another page | CSS clash scan in `layout_guard.py` |
| Trend tables: plant label alone on a page, stray half-empty pages | Old forced-break correction loop | `tbody` blocks + `_plan_trend_layout` + trend warnings |
| Full report took 20+ minutes | Old trend loop printed the whole report ~20 times; pypdf text extraction | Trend planning on the trend section only; pdfium text extraction |
| Export hangs forever, server stops answering | pdfium crashed the server process (not thread-safe) | pdfium runs in a child process with pypdf fallback |
| Backend won't start: "blocked by Device Guard" | Unsigned `uvicorn.exe` / `pip.exe` launchers | Start scripts use `python.exe -m ...` |

---

## 5. Changing the layout on purpose

1. Make the change.
2. `venv\Scripts\python.exe layout_guard.py --render 2026-08`: no layout
   warnings, and read any page-count differences it lists (expected ones only).
3. Look at the affected pages in the PDF.
4. Record the new known-good state:
   ```bat
   venv\Scripts\python.exe layout_guard.py --accept --render 2026-08
   ```
   (refuses if the render has layout problems)
5. Commit, then tag it:
   ```bat
   git tag pdf-layout-baseline-YYYY-MM-DD
   git push origin main --tags
   ```
6. Update the tag name at the top of this document and in section 1.

## 6. How the guard is wired

| Piece | File |
|---|---|
| Guard script (check / render / accept / hook) | `backend/layout_guard.py` |
| Baseline fingerprints + reference render | `backend/layout_baseline.json` |
| Runtime layout warnings | `backend/pdf.py` (`_layout_warn`, `_LAYOUT_WARNINGS`) |
| Git pre-commit warning | `.githooks/pre-commit` (enabled by `start-development.bat` / `start-production.bat` via `git config core.hooksPath .githooks`) |
| Claude Code warning | `.claude/settings.json` → `PostToolUse` hook → `layout_guard.py --hook` |
