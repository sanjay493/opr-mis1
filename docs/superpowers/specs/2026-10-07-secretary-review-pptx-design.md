# Secretary Review PPTX Generator — Design

Date: 2026-10-07
Status: approved in brainstorming, pending written-spec review

## Goal

A page in the app where the user picks a month/year and downloads the
"SECRETARY REVIEW Operations Inputs" deck, filled with that month's data
from the DB. The reference deck is
`G:\My Drive\Report_format\work\SECRETARY REVIEW Operations Inputs Sep26 update.pptx`
(30 slides, user-updated for Sep'26).

Success: for 2026-09 the generated deck reproduces the numbers in the
reference deck (tables and chart values), keeps its look, and charts stay
native/editable in PowerPoint. Narrative slides are pre-filled from the DB
and editable on the page before download.

## Decisions

- **Approach:** template mutation with `python-pptx`. The Sep'26 deck is copied
  into the repo as a fixed template; code rewrites table-cell text (keeping
  run formatting), replaces chart data with `chart.replace_data()`, and
  rewrites period labels. Same pattern as the DO Letter (`page_do_letter.py`).
- **Narrative:** pre-filled from DB, editable per block on the page, saved
  per month (option C).
- **Placement:** new tab `secretary-review` under `/reports/external`.
- **CO₂ lag:** CO₂ uses the latest month with data, no later than the
  selected month; its chart labels follow that month.
- **Period name:** H1 for Sep, Q1 for Jun, Q3 for Dec (9M Apr-Dec), FY for
  Mar; otherwise "Apr-Mon". Used in highlight wording; column headers
  always read "Mon'YY" and "Apr-Mon'YY".
- **Highlights table** is added to all five plant slides in the template;
  removed at render time when its text block is empty.

## Architecture

### Template

`backend/secretary_review_templates/secretary_review.pptx` — copy of the
Sep'26 deck with one prep change set (done once, by a script kept in
`backend/scripts/prep_secretary_review_template.py`):

- Every table and chart that gets filled is given a stable shape name.
  Code finds shapes by name, never by slide index.
  - Tables: `tbl_sail`, `tbl_sail_hl`, `tbl_plants_hm_cs` (slide 3),
    `tbl_plants_ss_fs` (slide 5), `tbl_delay_hmcs`, `tbl_delay_fs`,
    `tbl_<PLANT>`, `tbl_<PLANT>_hl`, `tbl_cr_1` / `tbl_cr_2`,
    `tbl_bd_<PLANT>`.
  - Charts: `ch_<SCOPE>_<kpi>` (bar, slides 7-17) and
    `trend_<SCOPE>_<kpi>` (slides 25-30), SCOPE ∈ SAIL, BSP, DSP, RSP,
    BSL, ISP; kpi ∈ coke, pci, fuel, bfprod, energy, co2.
  - Title text boxes holding period labels: `title_*`.
- A highlights table (cloned from BSP's) is added to the DSP, RSP and ISP
  plant slides.

### Backend

`backend/page_secretary_review.py`

- `build_context(month) -> dict`
  - `production`: for SAIL and each plant (+ SSPs, Total), items HM / CS /
    FS / SS → `cap, app_m, act_m, gr_m, cu_m, app_ytd, act_ytd, gr_ytd,
    cu_ytd`, using the same computation as page 4 (`page4.py` /
    `main.compute_item_row`) so numbers agree with the MIS report.
  - `techno`: per scope and kpi → `{fy_m2, fy_m1, target, month, ytd,
    trend: [(mon_label, val)…], month_used}` from `techno_data` /
    `techno_plan_fy`; Fuel-rate target via
    `board_note_common.fuel_rate_fallback`.
  - `labels`: month, ytd, cply-month, period name, FY labels.
  - `warnings`: list of strings (missing values, CO₂ lag in use, missing
    targets, shapes not found).
- `default_texts(month) -> dict[block_key, str]` — DB-derived narrative.
- `render_pptx(month, texts) -> bytes` — loads the template, fills it,
  returns bytes. Missing shapes are logged and added to warnings; they do
  not abort the render.

`backend/api_secretary_review.py` (router, registered in `main.py`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/secretary-review/context?month=` | labels, production summary, warnings |
| GET | `/api/secretary-review/texts?month=` | saved texts, falling back to defaults; each block flagged `saved: bool` |
| POST | `/api/secretary-review/texts` | body `{month, texts: {key: str}}`; upsert |
| GET | `/api/secretary-review/default-text?month=&block=` | one block regenerated from DB (for "Reset from DB") |
| POST | `/api/secretary-review/pptx` | body `{month, texts}`; returns the file (`SECRETARY REVIEW Operations Inputs <Mon><YY>.pptx`) |

The download is a POST so unsaved on-screen text is used. Invalid month →
400; missing template → 500 with a clear message.

### Database

New table `secretary_review_text`:

```
report_month TEXT, block_key TEXT, text TEXT, updated_at TEXT,
PRIMARY KEY (report_month, block_key)
```

Added to `init_db` (SQLite), `scripts/mysql_schema.sql`, and a new
`scripts/migrate_secretary_review_text.sql`. Written in sqlite dialect via
`db.connect()`.

### Text blocks

| Key | Slide | Default text source |
|---|---|---|
| `hl_SAIL` | 2 | `board_note_common.best_ever_bullets` for SAIL, YTD period |
| `hl_BSP` … `hl_ISP` | 8-16 | same, per plant |
| `delay_hmcs`, `delay_fs` | 4, 6 | `breakdown_table` grouped by plant; month events and YTD events, "BF#4: cause – N days" |
| `cr_BSP` … `cr_ISP` (two cells: current FY / previous FY) | 19-20 | `capital_repair_table` rows with actual dates, `format_cr_actual` style: "SMS2 Conv A (62 days in Jun-Aug'26)" |
| `bd_<PLANT>_<group>`, group ∈ BF, SMS, Mills | 21-24 | `breakdown_table` by plant and `unit_type` |

Each block is plain text, one bullet per line; each line becomes one
paragraph styled like the template cell's first paragraph.

## Slide mapping

| Slides | Content | Fill |
|---|---|---|
| 1, 18 | cover, image | unchanged |
| 2 | SAIL table + highlights | production + `hl_SAIL` |
| 3, 5 | plant-wise HM/CS, SS/FS incl. SSPs + Total | production |
| 4, 6 | delays HM&CS, FS | `delay_hmcs`, `delay_fs` |
| 7, 9, 11, 13, 15, 17 | 6 techno bar charts per scope: FY-2, FY-1, FY target, Mon, Apr-Mon | techno |
| 8, 10, 12, 14, 16 | plant table + highlights | production + `hl_<PLANT>` |
| 19, 20 | capital repairs, this FY vs last FY to same month | `cr_*` |
| 21-24 | breakdowns BSP, DSP, RSP, ISP | `bd_*` |
| 25-30 | monthly trend charts FY-2, FY-1, target, Apr→Mon | techno trend |

The "Good" direction markers on techno slides are static and untouched.

Empty handling: empty highlights → highlights table removed; empty
breakdown group → row removed; slide with all breakdown rows empty → one
row "No major breakdowns"; missing chart value → blank point (not 0) and a
warning.

## Frontend

`frontend/src/components/reports/secretary-review/View.js`, registered in
`reportGroups.js` (external group) and the `VIEWS` map in `ReportTabs.js`.

- Month picker (defaults to latest month with production) + **Download
  PPTX**.
- Data-check panel listing `warnings`.
- Text blocks grouped by slide section; each has a textarea, a badge
  ("Saved" / "From DB – not saved") and **Reset from DB**; a **Save all**
  button.
- Download posts the current on-screen texts.

Read `frontend/AGENTS.md` before writing it (Next 16).

## Testing

- `backend/tests/test_secretary_review.py`:
  - Render 2026-09 and compare table cells and chart values against the
    reference deck (a copy stored under `tests/fixtures/`), allowing ±1 on
    rounded values. Differences caused by DB data having been corrected
    since the Sep'26 update are reviewed by hand and listed in the test as
    known exceptions.
  - Render 2026-08: labels read Aug'26 / Apr-Aug'26 / Aug'25; CO₂ lag
    handled.
  - Rendered file opens with python-pptx; every named shape found.
- `py_compile`, `npm run lint`, browser check of the tab, render a few
  slides to images for a visual check (python-pptx → PDF is not available;
  use PowerPoint/LibreOffice if installed, otherwise inspect XML values).

## Dependencies

Add `python-pptx` (exact pin) to `backend/requirements.txt`, install, and
regenerate `requirements-lock.txt`. No Chromium/PDF impact.

## Risks

- `replace_data()` can drop per-point formatting (`c:dPt`). Verify on one
  chart first; if lost, write values into the chart XML caches and the
  embedded workbook directly instead.
- Free-text default wording will not match the hand-written deck exactly;
  the edit box is the remedy.
- Out of scope: generating slide 18's images, editing the "Good" markers,
  multiple deck variants.
