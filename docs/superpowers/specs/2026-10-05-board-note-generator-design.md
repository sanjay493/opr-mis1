# Board Note Generator — Design Spec

Date: 2026-10-05
Status: Approved for planning

## 1. Intent

SAIL's board sub-committee/board production-performance note ("Board Note",
filename pattern `BN_ Production Q-<n> ...`) is currently hand-assembled
every quarter. We already built a one-off script
(`backend/_update_bn_board_report.py`) that regenerates the Q-2'26-27 note
from this app's DB, validated against the reference Q-2'25-26 document. This
spec turns that one-off into a permanent feature: a new tab under
`/reports/external` that can generate the Board Note for **any FY and any
quarter**, pulling every number from the DB, while leaving plant-specific
operational narrative (why production fell short, granular sub-unit
records) as persistently editable free text — never guessed, never silently
carried forward from a prior period.

Four reference documents (user-supplied, in `Report_format/`) define the
four document shapes this must produce:

| Quarter | Long period paired with it | Reference file |
|---|---|---|
| Q-1 | none (quarter-only) | `BN_ Production Q-1_26-27.docx` |
| Q-2 | H-1 (Apr-Sep) | `BN_ Production Q-2 and H-1'25-26 R-2.docx` |
| Q-3 | 9M (Apr-Dec) | `BN_ Production Q-3 and 9M'25-26.docx` |
| Q-4 | FY (Apr-Mar) | `BN_ Production Q-4 and FY'25-26.docx` |

All four share one skeleton: title → "Finished Steel w.r.t. MoU" opening
(absent in Q-1, which has no MoU milestone) → SAIL section (quarter +
long-period summary, table, best-ever highlights) → plant-wise sections
(same shape, one per plant) → techno-economic section. They differ in which
long period pairs with the quarter, and in exact table column counts (e.g.
Q-4's MoU table has no separate annual-MoU column; Q-1 has none at all).

## 2. Scope

**In scope**, computed from the DB, matching the already-validated Q-2
methodology:
- Every per-plant/SAIL production table (ABP, Actual, %Ful, CPLY Actual,
  %Growth) for Hot Metal, Crude Steel, Saleable Steel, Finished Steel, for
  the quarter and whichever long period applies.
- The Finished-Steel-vs-MoU opening table and narrative (MoU figures
  themselves are never computed — they're entered elsewhere/unavailable and
  stay whatever they already are; %Ful/growth derive from them).
- SAIL-level and **per-plant** "best ever" bullets for the same 4 core
  items, scanned against all-time history for that quarter-type and that
  long-period-type (e.g. all historical Q-3 sums, all historical 9M sums).
- The techno-economic table (Coke Rate, CDI Rate, Fuel Rate, BF
  Productivity — target, actual, CPLY) and its 4 SAIL-level
  improvement/decline sentences. Fuel Rate target falls back to Coke + Nut
  Coke + CDI when no direct target exists (per `techno_aggregates.py`'s own
  rule for actuals).
- All period-label headings/table headers tied to the above.

**Explicitly out of scope / manual**, per user decision:
- Sub-unit best-ever records (BF-8, SMS-3, specific mills, etc.) — scanning
  every tracked item per plant for records is real future work, not this
  pass.
- "Why production fell short" narrative (shutdown dates, capital-repair
  jobs, raw-material issues) — plant-specific operational knowledge with no
  DB source.
- MoU figures for periods where they're not yet available (left blank, like
  the Q-2 case).
- Board-meeting metadata (meeting number, date) — stays blank/manual, as in
  every reference document.

## 3. Generation engine

### 3.1 Shared helpers (promoted from the one-off script, generalized off hardcoded 2026-27 months)

- `_period_sum`, `_conv_sum`, `row_values` — period ABP/Actual/CPLY/%Ful/%Gr
  for one (plant, item, period) via `page4._p4_get` (already handles
  per-plant vs. SAIL-aggregate dispatch and the SSP/VISL
  Finished-Steel→Saleable-Steel fallback).
- `_best_ever` — all-time scan for one (plant, item, period-shape),
  generalized to accept any period-months function (quarter, half, 9-month,
  full-FY) instead of just Q2/H1. Finished Steel at **SAIL level only**
  always adds Conversion (confirmed correct by the Q-4 reference's own
  "SAIL figures include finished steel produced through conversion
  agents/WLA/JVC" footnote); individual-plant Finished Steel never does.
- `sail_best_ever_bullets` / a new `plant_best_ever_bullets` (per-plant
  variant, same 4 items, no Conversion) — generates the bullet list text in
  each quarter-type's own wording style (e.g. "Previous best : X MT in
  Q-3'YY-ZZ" vs "Prev. best : X MT in Apr-Dec'YY").
- Techno: `techno_period.build_period_report` for actual/CPLY per
  parameter/plant/period; `page_techno._get_plant_techno_plan_targets` /
  `compute_sail_targets` for targets, with the Fuel Rate fallback.
- Formatting: `fmt_mt`/`fmt_t` (prose, MT for big plants+SAIL vs. comma-T
  for ASP/SSP/VISL), `fmt_tbl` (table cells, whole number vs. 3-decimal for
  small plants).

### 3.2 Per-quarter adapters

One module per quarter shape — `board_note_q1.py`, `board_note_q2.py`,
`board_note_q4.py`, reusing the existing `page_do_letter.py`-style docx
mutation technique (`_set_paragraph_text`/`_set_cell_text`/
`_clone_paragraph_after` for variable-length bullet lists). Each adapter
encodes, as explicit constants: its template's path, its paragraph index
map (heading/summary-sentence indices per plant), its table index map, and
which long-period (if any) it pairs with the quarter. This hardcoded-index
approach matches `do_letter.py`'s and the validated one-off script's own
approach — safer than trying to parse the document structurally, since
these are fixed, hand-laid-out templates.

A thin dispatcher, `generate_board_note_docx_bytes(fy: str, quarter: int) ->
bytes`, picks the right adapter and runs it. `fy` is the FY-start year pair
string (e.g. `"2026-27"`); months are derived from `fy` + `quarter`
mechanically (Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar of the FY start
year +1 where applicable), reusing `page_do_letter.py`'s existing
`_quarter_months`-style helpers generalized off FY-relative quarter number
(1-4 in FY-order, not calendar order) rather than hardcoded year strings.

### 3.3 Manual/editable narrative

New table:

```sql
CREATE TABLE board_note_manual_text (
    report_fy CHAR(7)    NOT NULL,   -- 'YYYY-YY', e.g. '2026-27'
    quarter   TINYINT    NOT NULL,   -- 1-4
    plant     VARCHAR(16) NOT NULL,  -- 'SAIL','BSP',...,'VISL'
    field     VARCHAR(24) NOT NULL,  -- 'additional_highlights' | 'why_narrative'
    text      TEXT,
    PRIMARY KEY (report_fy, quarter, plant, field)
);
```

(Needs both `init_db`'s SQLite CREATE TABLE and `scripts/mysql_schema.sql`,
per project convention.)

- `additional_highlights`: appended, one line per paragraph, after the
  auto-generated core-4 best-ever bullets under that plant's "Highlights:"
  heading. Empty = nothing appended (template's bullet slots collapse to
  just the auto ones, same mechanism already used for the SAIL bullets).
- `why_narrative`: replaces the whole "why production fell short" paragraph
  block for that plant/period. Empty = leave the block's template
  placeholder text (a literal "[Add production narrative]" marker, not the
  old year's stale text — this is new for the generator; the one-off script
  left old text in place because it was editing the *old* document in
  place, but a from-scratch generation for a brand new period should never
  default to misleading inherited text).
- New periods always start blank. Nothing is ever auto-copied from a prior
  quarter.

Lines split on `\n` in the stored text each become one cloned bullet/body
paragraph, reusing the existing `_clone_paragraph_after`/`_set_paragraph_text`
mechanics.

## 4. API

Mirrors `do_letter`'s route shape in `main.py`:

- `GET /api/board-note/docx?fy=2026-27&quarter=2` → generates and streams
  the filled docx (`generate_board_note_docx_bytes`).
- `GET /api/board-note/manual-text?fy=...&quarter=...` → all stored
  `(plant, field) -> text` rows for that period (empty dict for a
  never-touched period).
- `POST /api/board-note/manual-text` → body `{report_fy, quarter, entries:
  [{plant, field, text}, ...]}`, upserts (empty text deletes the row, same
  convention as `do_letter`'s remarks save).

## 5. Frontend

`frontend/src/components/reports/board-note/View.js`, registered in
`reportGroups.js`/`ReportTabs.js` as a new tab under `/reports/external`
(`?tab=board-note`).

- FY text input (e.g. `2026-27`) + a Q1-Q4 selector.
- "Generate DOCX" button → downloads via the docx endpoint, same
  fetch-blob-and-save pattern as `do-letter`'s existing download buttons.
- Below it, one collapsible block per plant (+ SAIL) with two textareas
  (Additional highlights / Why narrative), loaded on FY/quarter change and
  saved with an explicit Save button + status message — same UX as
  `do-letter`'s remarks editor (`View.js` lines ~50-90).

## 6. Error handling / edge cases

- Missing production/techno data for the requested period (future or very
  old FY): table cells and prose figures that can't be computed render
  blank (`""`), matching every other generator in this codebase (`page4.py`,
  `page_do_letter.py`) — never a guess, never a crash.
- A best-ever check with insufficient history (period never occurred
  before) silently produces no bullet, not an error.
- Requesting a quarter/FY combination with literally no data at all still
  generates the docx — every numeric field blank, same template skeleton,
  so the user gets a clean starting point to fill in by hand rather than a
  500.

## 7. Testing

No golden-file extractor tests apply (this isn't an extractor). Verification
is a real render per quarter type, following the same validation method
already used for Q-2: generate each of the four quarters for a FY with full
DB data, and manually cross-check key paragraphs/tables against the
already-known-correct figures (the already-filled Q-2'26-27 table1, and the
Q-4 reference's explicit Conversion-inclusion footnote, serve as existing
ground truth).

## 8. Out of scope for this pass (explicitly deferred)

- Sub-unit best-ever scanning (BF-8, SMS-3, mills, etc.).
- Any attempt to auto-generate the shutdown/capital-repair "why" narrative.
- Carrying forward or templating manual text across periods.
- Annexure tables beyond what each reference document's `tables[]` actually
  contains in-body (any annexure referenced only by the index list but not
  physically present as a table is left alone, as already observed for the
  Q-2 document).
