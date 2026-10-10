# MoU plan table, upload, and APP/MoU performance report — design

Date: 2026-10-10

## Goal

Store SAIL's month-wise MoU production targets per plant, load them from the
yearly MoU workbook, and add a two-page "Plant Wise Performance of Main
Items" report on `/reports/excel`: page 1 against APP (as today), page 2
against MoU. Both pages can be downloaded as Excel and as PDF, with a
choice of 0–3 decimal places.

## What the user asked for, and what was assumed

Asked for:
- A separate table for the MoU month-wise plan (Hot Metal, Crude Steel,
  Saleable Steel, Pig Iron, Finished Steel, plant-wise).
- An upload page that extracts it from `Report_format/ABP/MoU 26-27.xlsx`.
- A two-page report: the existing "Plant Wise Performance of Main Items"
  page with APP columns, and the same page with MoU replacing APP and only
  the items that have a MoU target.
- Excel and PDF downloads, and a decimal-places option: one setting (0–3)
  for tonnage; percentages stay whole numbers (user chose option A).
- The report lives at `/reports/excel`.

Assumed (open to correction at spec review):
- Only per-plant rows are stored. SAIL and "5 Plants" totals are computed
  the same way page 4 computes them today.
- The MoU page keeps every other column of page 4: Ann. Cap., CPLY actual,
  %Gr., CU%, and the Conversion / SAIL incl. Conversion rows at the end.
- The existing tab "Plant Wise Performance (Excel)" becomes the two-page
  report (same tab id). No separate new tab.
- The main monthly PDF report (page 4) is not changed.

## Source workbook

`MoU 26-27.xlsx`, sheet `MoU 26-27`:
- Row 3: `Items`, `Plant`, then 12 month dates (Apr'26 … Mar'27) in C–N,
  then quarter and annual totals (ignored).
- Column A: item name, merged across its plant rows (Hot Metal, Crude
  Steel, Saleable Steel, Pig Iron, Finished Steel).
- Column B: plant. Plant rows: BSP, DSP, RSP, BSL, ISP, ASP, SSP, VISL.
  Total rows: `SAIL - 5PL`, `SAIL -5 PL`, `SAIL`, `SAIL ` (spellings vary).
- Unit: '000 T.

## Components

### 1. Table `mou_plan_table`

Same shape as `production_plan_table`:

```
report_month CHAR(7), plant_name VARCHAR(32), item_name VARCHAR(64),
month_actual DOUBLE, PRIMARY KEY (report_month, plant_name, item_name)
```

`item_name` uses page 4's names: `Hot Metal`, `Total Crude Steel`,
`Saleable Steel`, `Pig Iron`, `Finished Steel`. Added to
`scripts/mysql_schema.sql`, a new `scripts/migrate_*.sql`, and `db.init_db`
(SQLite). Documented in `docs/DATA_MODEL_AND_REPORT_PAGES.md`.

### 2. Extractor `excel_extractors/excel_extractor_mou_plan.py`

`extract_mou_plan(path) -> {records, months, items_found, warnings}`; no DB
writes.
- Finds the header row by its `Items`/`Plant` labels and the month columns
  by their date values (not by fixed positions).
- Carries the merged item name down; maps workbook item names to page-4
  names (Crude Steel → Total Crude Steel).
- Keeps plant rows; skips any plant label starting with `SAIL`.
- For each item and month, compares the file's own `SAIL` row against the
  sum of the plant rows, and warns when they differ by more than 0.01.
- Warns about text cells it could not read as numbers. Raises `ValueError`
  if nothing was recognised.

### 3. API `api_mou_plan.py`

Same flow as `/api/power-omi`:
- `POST /api/mou-plan/preview`: extract and report any existing values
  that would be overwritten.
- `POST /api/mou-plan/insert`: upsert; 409 on existing values unless
  `confirm_replace=true`; writes an `extraction_log` entry.

### 4. Upload UI

A "MoU Plan (Excel)" row on `/data-entry/uploads`, built like
`PowerOmiExtractRow`: choose file → preview (month × item × plant counts,
warnings) → insert, with a confirm step when values already exist.

### 5. Report data: `page4.py` gets a plan basis

- `generate_page4_rows(month, raw=False, basis="app")`. With
  `basis="mou"`, the plan source is `mou_plan_table` rather than
  `production_plan_table`, and only the 5 MoU items are included (Oven
  Pushing and Sinter are dropped). Every other calculation is shared.
- Default arguments keep the main PDF report output unchanged.

### 6. API `api_plant_performance.py`

- `GET /api/plant-performance-main-items?month=&basis=app|mou`: JSON rows,
  as today, plus labels that say APP or MoU.
- `GET …/xlsx?month=&decimals=0..3`: one workbook, two sheets
  ("w.r.t APP", "w.r.t MoU"). Tonnage cells use a number format with the
  chosen decimals. Values stay unrounded to 3 places, so Excel sums still
  work. Percentages use the format `0`.
- `GET …/pdf?month=&decimals=0..3`: A4 landscape, 2 pages (APP, then
  MoU), from its own small HTML template rendered with Playwright, the
  same way `page_production_fy_export.py` does. It is not part of the
  layout-guarded main report.

### 7. Frontend `components/reports/plant-performance-items/View.js`

- Controls: month picker, decimals selector (0/1/2/3, default 3, saved in
  `localStorage`), Download Excel, Download PDF.
- Shows both tables, APP above MoU, sharing one table component that
  formats tonnage with the chosen decimals.
- The tab label in `reportGroups.js` becomes "Plant Wise Performance (APP &
  MoU)".
- Production on port 80 needs `npm run build` before
  `http://localhost/reports/excel` shows the change.

## Error handling

- A missing MoU value for a month shows as a blank, the same as a missing
  APP value. If no MoU data exists for the FY at all, the MoU page shows a
  note saying so, plus a link to the upload page.
- Bad month or decimals parameters return 400.

## Testing

- Extractor: a test against a small synthetic workbook covering merged item
  cells, `SAIL` row skipping, the Crude Steel name mapping, and the
  SAIL-vs-sum warning. Plus a manual run against the real `MoU 26-27.xlsx`.
- `page4`: a test that `basis="mou"` returns only the 5 items and reads
  plan figures from `mou_plan_table`; existing goldens and tests stay green.
- `layout_guard.py --render 2026-08` stays OK, showing page 4 is
  unchanged.
- Manual: upload the real workbook, open `/reports/excel`, switch decimals,
  and download both files and look at them.
