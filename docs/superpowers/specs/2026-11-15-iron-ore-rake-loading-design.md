# Iron ore rake loading from mines (Rail Logistics) — design

Agreed with the user 2026-11-15. Follows
`2026-11-14-rail-loading-monthly-design.md` and the 2026-11-15 changes to
pages 40.05-40.3 (sub-group rows, entry tab, "Steel Rake Despatch from Plant"
titles).

## Intent

The Rail Logistics section shows the plants' steel rake despatch with seven
years of history and a wagon-type analysis, but iron ore loading at the mines
appears only as three monthly figures on page 40.05. The user has the mines'
rake-by-rake loading record since April 2020 and wants the same kind of
picture for iron ore: month-wise history for past years, wagon-type-wise
monthly loading, and wagon-mix analysis — for EGOM (OGOM + JGOM combined) and
CGOM, not mine by mine.

## Goals

- Upload the mines' rake file from a login-protected screen and keep every
  rake in the database.
- One new MIS PDF page, "Rail Logistics – Iron Ore Rake Loading from Mines".
- Fill page 40.05's OGOM and JGOM rows from the uploaded rakes.

## Non-goals

- Mine-by-mine tables, destination-wise or pellet-fines tables, lump/fines
  wagon analysis. The stored rakes make these possible later; none is built now.
- A web report under Reports > Rail Logistics.
- Typing rakes in by hand.

## Anti-goals

- A rake silently left out of a group because its mine or wagon code is not
  known. An unknown code stops the upload and names the code.
- Two sources for one printed figure drifting apart without anyone seeing.

## Source

`u_rakes_rmg.csv` (UTF-8 with BOM), a table export, one line per rake:
`id, unit, rpt_date, rake_no, dest, type, l_wg, f_wg`. 50,980 rakes,
2020-04-01 to 2026-10-31, ids unique. The user uploads a fresh export each
month; it may hold the whole history again or only recent months.

One line = one rake. Counted that way the file reproduces the stored EGOM
figure exactly for Apr-Oct 2026. CGOM differs in two months (Aug 205 vs 206
reported, Oct 211 vs 209); the user is checking which is right (see Open).

### Mine groups (confirmed by the user)

| Group | `unit` codes |
|---|---|
| OGOM | BOL, BAR, KAL, TAL |
| JGOM | KRB, MBR, GUA, MPR |
| CGOM | BGM, DAL, RAJ, ROW |

EGOM = OGOM + JGOM.

### Wagon types (given by the user)

| `type` code | Printed as |
|---|---|
| BS | BOBSNM1 |
| BY (also "by") | BOYEL |
| BX, EL | BOXN (added together) |
| PR | Private GPWIS |
| GP | SAIL BOXN GPWIS |
| GS | SAIL BOBSNM1 GPWIS |

Codes are compared in upper case. The user wrote "GWPIS" for GP; GPWIS is used
for all three (flagged to the user).

### Other columns

- `dest`: BSP, DSP, RSP, BSL, ISP; OTH; PRSP / PBSP / PISP / PBSL / PDSP =
  pellet fines rakes to a conversion agent on that plant's account. Every
  destination counts as an iron ore rake (needed to match the reported totals).
  Stored, not otherwise used yet; an unknown `dest` is accepted.
- `l_wg`, `f_wg`: two wagon counts, stored under the file's names. Their
  meaning is not confirmed and nothing prints them. 9 rakes have both at zero
  and still count as rakes.
- 16 repeated (unit, date, rake_no) combinations exist; each line still counts
  (that is what matches the reported totals).

## Approaches

1. **Keep every rake (chosen).** One row per rake keyed by the file's id;
   monthly counts are worked out at read time. Later analyses need no new
   upload or table; the upload preview can say exactly what changes. ~51,000
   rows, ~9,000 more a year.
2. Keep only monthly counts (month, mine, wagon type). Smaller, but any new cut
   means a schema change and re-uploading all history.
3. Type the figures in. Ruled out: seven years of mine x wagon type x month.

The user picked 1 because more analysis from this data is expected.

## Storage

New v2 table `iron_ore_rake` (`schema_v2.sql` + `scripts/v2/migrate_add_iron_ore_rake.sql`,
table lists in `tests/test_schema_v2.py`, `tools/verify_v2.py`, `tools/repo_oracle.py`,
`docs/DATA_MODEL_AND_REPORT_PAGES.md`; follow `backend/docs/MYSQL_MODEL_CHANGES.md`):

| column | type | from |
|---|---|---|
| id | INT, PK | `id` |
| report_month | CHAR(7), FK cal_month | month of `rpt_date` |
| rpt_date | DATE | `rpt_date` |
| mine_code | VARCHAR(8) | `unit` |
| rake_no | VARCHAR(24) | `rake_no` |
| dest | VARCHAR(8) | `dest` |
| wagon_code | VARCHAR(4) | `type`, upper-cased, as in the file (BX and EL stay apart) |
| l_wg, f_wg | DOUBLE NULL | `l_wg`, `f_wg` |

Index (report_month, mine_code, wagon_code) for the monthly count. The mine
groups and wagon-type names live in Python (a new `iron_ore_rakes.py`), not in
the database, as `rail_loading.py` does for its items.

SQL only in `repo/rake.py`:
- a monthly count read: rakes per (report_month, mine_code, wagon_code) between two months;
- stored rake counts per month (for the upload preview);
- a save that, in one transaction, bumps `data_version`, ensures the months,
  deletes every stored rake dated within the file's first..last date and
  inserts the file's rakes.

**Upload rule (builder's call, stated to the user in the preview):** the file
replaces everything stored between its first and last date. A rake corrected
or removed in the source therefore disappears here too; rakes outside the
file's dates are untouched.

## Upload

A card on Data Entry > Uploads, next to the Despatch Summary Report card, with
the same two steps as `api_rake_despatch.py`:

1. `POST /api/iron-ore-rakes/preview` (file) -> rakes read, first/last date,
   and per changed month: stored rakes vs rakes in the file. Nothing is saved.
2. `POST /api/iron-ore-rakes/insert` -> saves. Editors and admins only
   (`require_editor_or_admin`), on both steps. When the file lowers the rake
   count of a month already stored, the insert needs `confirm_replace` (409
   otherwise), as the despatch upload does.

The file is refused whole (422, nothing saved) when: a header is missing; an
id repeats or is not a number; a date is unreadable or in the future; a `unit`
or `type` code is not in the tables above (the message names the codes). The
browser sends the file itself to step 2 again rather than the parsed rows
(51,000 rows as JSON is needlessly heavy) — builder's call.

## New page

Page id **40.07**, portrait, "Rail Logistics – Iron Ore Rake Loading from
Mines", between Monthly Rail Loading (40.05) and the plant despatch pages
(40.1-40.3): inward first, then outward. Figures up to the report month only.

1. **Key points** — three or four sentences written from the figures: the
   month's rakes for EGOM and CGOM against the same month last year, FY to
   date against the same period last year, and the biggest wagon-mix move when
   it is 2 points or more. (Builder's call; the user asked for "analysis".)
2. **Seven-year monthly trend** — blocks EGOM, CGOM, Total; one row per FY,
   current FY first and bold, Apr..Mar, Total. Same look as the plant trend
   table on 40.2. The file starts Apr 2020, so the seven FYs 2020-21..2026-27
   are all there.
3. **Wagon-type mix** — rows EGOM, CGOM, Total: FY-to-date rakes, each type's
   share, and in brackets the move in percentage points against the same
   months of last FY (always available here), biggest move bold. Same look and
   caption as 40.3's mix table.
4. **Rakes by wagon type, FY** — blocks EGOM, CGOM, Total; one row per wagon
   type (largest first), Apr..Mar, FYTD, and a Total row. Same look as 40.3.

Reuse `rake_despatch_report`'s mix and trend logic by letting it take the
group list instead of the fixed plant list, rather than copying it. No rakes
stored for the report month's FY -> the page prints its title and "Iron ore
rake file not uploaded for FY <fy>".

Wiring as the other Rail Logistics pages: `PAGE_IDS` gains 40.07 (main.py's
dispatch, page lists and export insertion follow), Index row page count 4 -> 5,
`report_utils` canonical order + badge group 10, `/report` `PAGE_LABELS` and
`SERVER_DATED_TYPES`, a React preview template in
`RailLogisticsTemplates.js`, the 40.05 export-insertion test extended.
Colours: existing `rail_log_*` / `perf_*` keys; a new template class prefix
(`rlm-`).

## Page 40.05: OGOM and JGOM from the rakes

For a month that has uploaded rakes, the OGOM and JGOM rows print the rake
count of those groups; the typed value (if any) is ignored for those two rows.
Months with no uploaded rakes behave as now. EGOM, CGOM and Total iron ore
stay as typed/reported (totals on this page are always as reported).

The entry tab (Monthly Rail Loading) shows OGOM and JGOM read-only, marked
"from the mines file", for such a month, and no longer derives EGOM from them
there: EGOM is typed as reported. Where the typed EGOM differs from the file's
OGOM + JGOM, the form shows a plain note with both numbers (it does not block
the save).

## Layout

Layout-guarded change: read `backend/docs/PDF_LAYOUT_GUARDRAILS.md`; render
2026-10 and look at 40.07 and 40.05; then `--accept --render 2026-08`, commit
with `layout_baseline.json`, tag, update the tag name in the guardrails doc.
Reference page count goes 113 -> 114.

## Testing

- Parser: a small fixture CSV (BOM, "by", EL, a P-destination, zero-wagon
  rake, repeated rake_no) -> rows; each refusal case.
- Grouping and page builder on hand-made counts: EGOM = OGOM + JGOM, BX + EL
  = BOXN, trend FY rows, mix shifts, future months blank, placeholder.
- Repo round trip in the throwaway database: save, re-save a narrower date
  range (only that range replaced), counts; guard tests stay green.
- API: preview changes list, 409 without confirm, 401 without login.
- 40.05: OGOM/JGOM overlay for a month with rakes, typed value for one without.
- Real upload of the user's file on the dev database, then render 2026-10:
  EGOM Oct = 662, CGOM Oct = 211, 40.07 on one sheet.

## Left to the builder

Module and function names, the preview's exact wording, column widths and
font sizes on 40.07 (it must fit one sheet without scaling below 85%).

## Open (does not block building)

- CGOM Aug and Oct 2026: file vs reported note. Until the user decides, 40.05
  prints the reported figures and 40.07 prints the file's.
- "GPWIS" vs "GWPIS" for GP.
