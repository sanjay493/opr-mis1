# Rail Logistics pages in the MIS PDF — design

Agreed with the user 2026-11-14. Extends
`2026-11-14-rake-despatch-report-design.md`, whose "MIS PDF page" was out of
scope: a selection of that web report (`/reports/logistics`, Rake Despatch)
now also prints in the monthly MIS PDF.

## Goal

Three portrait pages, "Rail Logistics – Rake Despatch", right after Capital
Repair (pages 36-40) and before Details of Rakes Detention. Figures come from
`rake_despatch_report.build_report(month)` unchanged — no new upload, data
entry or arithmetic; the PDF and the web report always agree.

## Pages

**40.1 — Summary**
1. Four headline cards: SAIL month vs plan (rakes, attainment %, avg/day vs
   plan/day), vs same month last year, FY to date (vs plan and vs last year),
   FY projection at current pace vs last FY.
2. Commodity-wise rakes per plant + SAIL: slag, coke, sinter (on date,
   cumulative, avg/day, plan avg/day, from `source.position`), and slab
   despatch rows from→to with rakes and MT (`source.slab`), plus the slab
   note when present.
3. Key points (`key_points`, bulleted).
4. Plan attainment (`ranking`) — **without the Status column**; the
   attainment % cell is tinted instead (same thresholds, `PLAN_STATUS`).
5. Run-rate to FY end (`run_rate`): FYTD and month avg/day, plan avg/day,
   needed/day to match last FY, lift needed %, FY total at plan rate and at
   current pace.

**40.2 — Performance history**
6. Records & seasonality (`records`): month actual, rank among the same
   calendar month of stored FYs, best/worst same month, best month ever,
   best FY.
7. Seven-year monthly trend (`trend`) as a table: rows = plant × FY (BSP,
   DSP, RSP, BSL, ISP, SAIL; newest FY first), columns Apr…Mar + Total; the
   current FY's future months blank; heavier rule between plant blocks.
8. Export (`export`): destination × plant programme/actual + SAIL
   programme/actual/fulfilment, with TOTAL NEPAL, TOTAL PORT, GRAND TOTAL.

**40.3 — Wagon types**
9. Wagon-type mix, compacted to one matrix: rows = wagon types (SAIL FYTD
   order), columns BSP…ISP FYTD share %, SAIL share %, SAIL shift (pp); the
   shift basis (`wagon_mix.label`) in the section subtitle. The web view's
   per-plant blocks (~40 rows) do not fit a page.
10. Rakes by wagon type, FY (`source.types`): one block per plant (type rows
    + plant total), then a SAIL block (types summed), columns Apr…Mar + FYTD.

No upload for the month (`available: False`) → each of the three pages
prints its title and "Despatch Summary Report for <Mon'YY> not uploaded".

## Wiring

- Page ids: sentinel floats **40.1, 40.2, 40.3** (after 40, clear of every
  other sentinel range).
- `main.py`: constants beside the Rake Detention block; dispatch in both
  page-building paths (the full-report loop and the single-page fetch);
  appended to `pages_config` right before the Rake Detention pages; listed in
  the sentinel tuple that skips the generic page handling; Index row
  ("Rail Logistics – Rake Despatch", 3) in `_INDEX_SECTIONS` with anchor
  40.1 in `_INDEX_SECTION_ANCHORS`, between Capital Repair and Rake
  Detention.
- `report_utils.py`: 40.1-40.3 in `_CANONICAL_PAGE_ORDER` after
  `range(36, 41)`; `_DEPT_BADGE_EXPLICIT_GROUP` group **10** (Rake
  Detention's — same Rail Movement Cell subject, so later badge colours do
  not shift).
- `pdf.py`: portrait, so no `_LANDSCAPE_TYPES` change; page type
  `rail_logistics` mapped to its templates like other sentinel pages.

## Code

- `backend/page_rail_logistics.py`: `PAGE_IDS = {40.1: "summary", 40.2:
  "history", 40.3: "wagon"}`; `generate_rail_logistics(month, part)` calls
  `build_report` and reshapes for that page. Pure helpers (unit-tested):
  `commodity_rows(position, slab)`, `mix_matrix(wagon_mix)`,
  `wagon_type_blocks(types, fy_months)`, `trend_rows(trend)`.
  `build_report` is memoised per month for the duration of one render so the
  three pages read the database once.
- Templates `backend/page_templates/rail_logistics_summary.html`,
  `rail_logistics_history.html`, `rail_logistics_wagon.html`, portrait,
  7.5-8pt tables, 1px borders (see PDF_LAYOUT_GUARDRAILS.md).
- Colours: new `rail_log_*` keys in `colors_config.json` and
  `colors_loader._DEFAULTS`; plan/actual columns reuse `perf_app_*` /
  `perf_act_*`. No hex in templates.
- Browser preview: `frontend/src/components/RailLogisticsTemplates.js`
  (three templates, own copies of the hex values) wired into
  `PageRenderer.js`, as `RakeDetentionTemplates.js` is.

## Testing

- `backend/tests/test_page_rail_logistics.py`: helper outputs on fixed
  inputs; placeholder payload when the month is unavailable.
- Guard tests stay green (repo boundary, writes-bump, oracle, F823); full
  `pytest tests`.
- Real render `python layout_guard.py --render 2026-10`: each new page one
  sheet, fit-to-page not below ~95%, Index shows the row with correct page
  numbers, later sections' numbers shift by 3; page images checked with
  pypdfium2, borders/colours with pdfplumber.
- Baseline `--accept`, commit and tag only when the user asks.

## Out of scope

Excel download of these pages; any change to the web report; pages 3-4 of
the source PDF.
