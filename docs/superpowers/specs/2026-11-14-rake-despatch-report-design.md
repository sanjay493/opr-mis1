# Rake Despatch Report — design

Agreed with the user 2026-11-14.

## Goal

A web report page under Reports showing SAIL's monthly rake loading/despatch
position from the Despatch Summary Report PDF (Rail Movement Cell), keeping
all of the source data and adding management insight on top. Web page only —
the monthly MIS PDF is unchanged.

## Source

`Dispatch_report.pdf`, "REPORT AS ON 1.11.2026" (closes October). Uploaded
once a month, the month-end file. Units: number of rakes (slab despatch also
in MT).

- Page 1 — Despatch Summary: per plant plan avg/day, yesterday's empties
  received / rakes made over, cumulative, average/day, difference with plan,
  made over after 00.00, rakes under loading, empty forecast; slab despatch
  (from/to, rakes, MT) and today's slab rake position note; slag/coke/sinter
  (plan avg/day, on date, cumulative, average).
- Page 2 — Month-wise steel despatch by wagon type (BOST, BRN, SHRN, DMT,
  BOSM, BOXN, FMP, LRN, BFNS, CONCOR, FOULAD…), plant × month for the FY;
  export despatch programme vs actual per plant and destination (Nepal
  border points, ports).
- Pages 3-4 — date-wise empty received / loading grid: **not extracted**.
- Page 5 — month-wise rakes per plant for 7 FYs.

Pages are found by title, not position.

## Data checks at upload

The preview reports, without blocking the save:
- page 2 plant month total ≠ page 5 same month (seen: May 2026, SAIL 489 vs 535);
- page 2 type rows not summing to the plant TOTAL;
- page 2 plant totals not summing to SAIL.

## Storage (new tables, `schema_v2.sql` + `scripts/v2/migrate_add_rake_despatch.sql`)

- `rake_despatch_type` (report_month, plant_code, wagon_type, rakes) — page 2.
  Every upload refreshes all FY months it carries.
- `rake_despatch_history` (report_month, plant_code, rakes) — page 5, plant
  totals; page 2's month totals are authoritative for the current FY when
  both exist (the mismatch is reported, not merged).
- `rake_despatch_position` (report_month, plant_code, metric, value) — page 1
  month-end figures, incl. slag/coke/sinter.
- `rake_slab_despatch` (report_month, from_plant, to_plant, rakes, qty_mt).
- `rake_export_despatch` (report_month, plant_code, destination, prog, actual).
- `rake_despatch_note` (report_month, note) — today's slab rake position text.

All SQL in `backend/repo/rake_despatch.py`; every write bumps `data_version`.

## Insights (backend, unit-tested)

1. Headline cards: SAIL month vs plan, FY-to-date vs plan, vs same month last
   year, FY projection vs last FY.
2. Plan-attainment ranking per plant (month and FYTD), colour-coded.
3. Wagon-mix shift: share by type vs last FY; until last FY's type data exists,
   H1 vs months since, labelled as such.
4. Seven-year monthly trend per plant / SAIL (chart).
5. Record & seasonality flags: best month / FY ever, this month's rank among
   the same month in past years.
6. Run-rate to FY end: rakes/day needed for the rest of the FY to match last
   FY's total, vs current pace. Option: page 1 plan avg/day instead.
7. Export watch: programme vs actual by destination, shortfall/excess.
8. Auto-written key points (3-5 sentences).

## UI

- Upload: new card on `/data-entry/uploads` (preview → compare → confirm → save,
  409 on changed values unless confirmed), like the EPI upload.
- Report: new Reports group "Rail Logistics" (`/reports/logistics`), tab
  "Rake Despatch", month picker. Cards → key points → ranking → run-rate →
  records → trend chart (recharts) → wagon mix → export → full source tables.

## Out of scope

MIS PDF page, Excel download, pages 3-4.
