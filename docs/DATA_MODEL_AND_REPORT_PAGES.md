# SAIL MIS Portal — Data Model & Report Pages (Developer Reference)

Practical map of **every DB table**, **where its data comes from**, **which report
pages consume it**, and **which source files** you edit to change a page's UI or
to map a new item into it.

- Backend: FastAPI, `backend/`. All SQL is centralised in `backend/repo/<module>.py`.
- Frontend: Next.js 16 (Turbopack), `frontend/`.
- DB engine: MySQL only, database `mis_reports_v2` (schema v2). The DDL source of
  truth is `backend/scripts/v2/schema_v2.sql`; see §4.
- `report_month` / `report_month`-like keys are `'YYYY-MM'` strings throughout.
  Financial year = April–March, formatted `'YYYY-YY'` (e.g. `2026-27`).
- Tonnage is stored and shown as `'000 T` unless a column says otherwise.

---

## 1. The two data flows

```
INGESTION                                              REPORTING
─────────                                              ─────────
Excel / PDF upload                                     GET /api/data?month=YYYY-MM[&page_number=N]
  → backend/excel_extractors/*.py                        → main.py  (page-list assembly + dispatch)
  → /api/extract-preview  (preview)                       → backend/page_*.py  generate_*()  (one per page/type)
  → /api/confirm-extraction                               → returns list[ {page, type, ...pageData} ]
      ↘ repo.<module>  (writes)                     ↙                        ↘
Manual data-entry pages                          Frontend preview                 PDF
  frontend/src/app/data-entry/<x>/page.js        frontend/src/components/         backend/pdf.py
  → /api/<x>  (backend api_*.py or main.py)      PageRenderer.js → *Template.js   → Jinja: page_templates/*.html
      ↘ repo.<module>  (writes)                 (Chromium via Playwright)        (Chromium via Playwright)
                         ↘  DB tables  ↙
```

Key rule: **the frontend `*Template.js` component and the backend `page_templates/*.html`
Jinja partial render the *same* `pageData` dict** produced by one `generate_*()`
function. If you add a field, add it in the generator and in *both* renderers.

### Editable overrides
Any cell edited on `/report` and saved is persisted per page as JSON in
`page_config` (`/api/data` POST). On the next generation the stored JSON is
merged over the freshly computed page. So "the number is wrong on the report but
right in the DB" often means a stale `page_config` row — clear it for that
`(report_month, page_number)`.

---

## 2. Rendering pipeline — the files involved

| Concern | File(s) |
|---|---|
| Page-list assembly, sentinel-page insertion, per-page dispatch | `backend/main.py` (`/api/data` handler, ~line 660–980) |
| Page-number constants (sentinel float ids like `KEY_PARAMS_PAGE_ID = 3.5`) | `backend/main.py` (~line 320–480) |
| Per-page data builders | `backend/page_*.py` — `generate_<page>()` |
| PDF: HTML shell + per-type `{% include %}` dispatch | `backend/page_templates/main.html` (~line 1620–1660) |
| PDF: per-page-type markup | `backend/page_templates/<type>.html` |
| PDF: Chromium render, pagination, headers/footers, landscape splicing | `backend/pdf.py` |
| PDF: global stylesheet | `backend/page_templates/main.html` `<style>` + `frontend/src/app/globals.css` (shared classes) |
| Preview: page-type → component switch | `frontend/src/components/PageRenderer.js` |
| Preview: per-page-type markup | `frontend/src/components/<Type>Template.js` |
| Preview: viewer shell, month picker, page nav, PDF button | `frontend/src/app/report/page.js` |
| Preview data fetch hook | `frontend/src/hooks/useReportAPI.js` (`useReportData` → `/api/data`) |
| Colours (PDF templates) | `backend/colors_config.json` + `backend/colors_loader.py` |
| Per-page font size / margins (PDF) | `backend/layout_config.json` + `backend/layout_loader.py` |
| Report figures with no DB source yet | `backend/hardcoded_config.json` + `backend/hardcoded_loader.py` |
| Techno param key ↔ label ↔ area (data-entry UIs) | `frontend/src/lib/technoParamRegistry.js` |
| Techno param registry / aggregation (backend) | `backend/plant_registry.py`, `backend/techno_registry.py`, `backend/techno_cumulative.py` |

---

## 3. Report pages → source files → tables

`Page` is the display number; sentinel pages are inserted relative to a fixed
page (see `main.py`). `type` is the `pageData.type` string that drives both
renderers. **The per-template `page.*` data contract is in §8.**

| Page(s) | Title | `type` | Backend generator | PDF template | Preview component | Primary tables |
|---|---|---|---|---|---|---|
| 1 | Cover | `cover` | `page_cover.py:generate_cover` | `cover.html` | `CoverTemplate.js` | — (month/date only) |
| 2 | Index | `index` | `main.py:_index_rows` | `index.html` | `PageRenderer.js:IndexTemplate` | — (static + `page_config` edits) |
| *2.1–2.3* | Indian Steel Sector Performance | `steel_sector_performance` | `page_steel_sector_performance.py` | `steel_sector_performance.html` | `SteelSectorPerformanceTemplate.js` | `steel_sector_performance` |
| *1 (2.5)* | MIS at a Glance | `at_a_glance` | `page_at_a_glance.py:generate_at_a_glance` | `at_a_glance.html` | `AtAGlanceTemplate.js` | `production_monthly` (actual + ABP), `techno_upload` / `techno_value`, `item_capacity` |
| 3 | Production Summary (SAIL) | `summary` | `page3_highlights.py:generate_page3_highlights` + `main.py:compute_item_row` + `_safe_te_table` (`page_techno.generate_summary_te_table`) | `summary.html` | `SummaryTemplate.js` | `production_monthly` (actual + ABP), `techno_upload` / `techno_value`, `report_text` |
| *3.2* | Best Ever Highlights | `best_ever_highlights` | `page_best_ever.py:generate_best_ever_highlights` | `best_ever_highlights.html` | `BestEverHighlightsTemplate.js` | `production_monthly` (full history) |
| *3.3* | Best Calendar Month | `best_calendar_month` | `page_best_calendar_month.py` | `best_calendar_month.html` | `BestCalendarMonthTemplate.js` | `production_monthly` |
| *3.5* | **Inter Plant Performance Comparison** ("Key Parameters") | `key_parameters` | `page_key_parameters.py:generate_key_parameters` | `key_parameters.html` | `KeyParametersTemplate.js` | `techno_upload` / `techno_value` (BF/Coke/General incl. `rltifr`), `production_monthly`, `cost_trend_monthly` (HM/CS/SS + `COKE`/`SINTER`), `hardcoded_config.json` (`ss_in_finished`) |
| *3.6* | SAIL Large BFs — Performance Snapshot | `bf_large_annexure` | `page_bf_large_annexure.py` | `bf_large_annexure.html` | `BfLargeAnnexureTemplate.js` | `techno_upload` / `techno_value` (BF-8/BF-5 units), `bf_benchmark_sail_meta`, `production_monthly` (ABP) |
| *3.61–3.63* | Cost Trend (HM / CS / SS) | `cost_trend` | `page_cost_trend.py:generate_cost_trend` | `cost_trend.html` (`cost_trend_macro.html`) | `CostTrendTemplate.js` | `cost_trend_annual`, `cost_trend_monthly` |
| 4 | Month-Wise Production | `page4_table` | `page4.py:generate_page4_rows` | `page4_table.html` | `MonthWiseProductionTemplate.js` | `production_monthly` (actual + ABP), `item_capacity` |
| *4.5* | SAIL Mines Production & Despatch | `sail_mines` | `page_sail_mines.py:generate_sail_mines` | `sail_mines.html` | `SailMinesTemplate.js` | `sail_mines_monthly`, `mine_*` masters + monthly, `hardcoded_config.json` (`sail_mines` — trend charts + iron-ore group table) |
| 5–6 | Plant-Wise Production Performance | `performance_summary_table` | `page5_6.py:generate_page5_rows` / `generate_page6_rows` | `performance_summary_table.html` | `PlantWisePerformanceTemplate.js` | `production_monthly` (actual + ABP) |
| 7–12 | 10-Year Month-Wise Production Trends | `trend_yearly` / `trend_combined` | `page7_13.py:generate_trend_page_rows` / `generate_combined_trend_items` | `trend_yearly.html`, `trend.html`, `trend_section.html` | `TrendYearlyTemplate.js`, `TrendTemplate.js` | `production_monthly` |
| 13 | Concast Production Performance | `concast_performance` | `page17_concast.py:generate_concast_data` | `concast_performance.html` | `ConcastPerformanceTemplate.js` | `production_monthly` |
| 14 | Production by Process | `prod_by_process` | `page_prod_by_process.py:generate_prod_by_process` | `prod_by_process.html` | `ProductionByProcessTemplate.js` | `production_monthly` |
| 15–17 | Category-Wise Saleable Steel | `catwise_saleable` | `page_catwise_saleable.py:generate_catwise_saleable` | `catwise_saleable.html` | `CatWiseSaleableTemplate.js` | `production_monthly` |
| 18 | Segment-Wise Production | `segment_wise` | `page_segment_wise.py:generate_segment_wise` | `segment_wise.html` | `SegmentWiseTemplate.js` | `production_monthly` |
| 19–23 | Special Steel — BSP/DSP/RSP/BSL/ISP | `special_steel` | `page_special_steel.py:generate_special_steel_plant` | `special_steel.html` | `SpecialSteelTemplate.js` | `special_steel_order`, `special_steel_abp`, `special_steel_grade_club` |
| 24 | Special Steel — SAIL Consolidated | `special_steel` | `page_special_steel.py:generate_special_steel_sail` | `special_steel.html` | `SpecialSteelTemplate.js` | same as 19–23 |
| *(after 24)* | Special Steel Trend | `special_steel_trend` | `page_special_steel_trend.py` | `special_steel_trend.html` | (uses `SpecialSteelTemplate.js` family) | `special_steel_order`, `production_monthly` |
| *1025 (after 24)* | Special Steel Plants Physical Performance (ASP/SSP/VISP) | `special_steel_physical` | `page_special_steel_physical.py` | `special_steel_physical.html` | `SpecialSteelPhysicalTemplate.js` | `special_steel_phys_perf` / `_meta`, `report_text`, `special_steel_ipt_requirement`, `production_monthly`, `hardcoded_config.json` (`ytd_actual_override`) |
| 25 | Opening Stock | `opening_stock` | `page_opening_stock.py:generate_opening_stock` | `opening_stock.html` | `OpeningStockTemplate.js` | `stock_monthly` |
| 26 | IPT Status | `ipt_status` | `page_ipt.py:generate_ipt` | `ipt_status.html` | `IptStatusTemplate.js` | `ipt_monthly` |
| 27 | Major Techno-Economic Parameters | `techno_params` | `page_techno.py:generate_major_techno_from_db` | `techno_params.html` | `TechnoParamsTemplate.js` | `techno_upload` / `techno_value`, `techno_plan_fy`, `production_monthly` |
| 28 | Coke & Coal Chemicals, Sinter Plant (Techno) | `techno_params` | `page_techno.py:generate_techno_from_db` | `techno_params.html` | `TechnoParamsTemplate.js` | `techno_upload` / `techno_value`, `techno_plan_fy` |
| 29 (+ *29.5*) | Iron Making (Techno) (+ contd.) | `techno_params` | `page_techno.py:generate_techno_from_db` | `techno_params.html` | `TechnoParamsTemplate.js` | `techno_upload` / `techno_value`, `techno_plan_fy` |
| 30 | BOF Shop (Techno) | `techno_params` | `page_techno.py:generate_techno_from_db` | `techno_params.html` | `TechnoParamsTemplate.js` | `techno_upload` / `techno_value`, `techno_plan_fy` |
| 31–35 | Mill-Wise Techno — BSP/DSP/RSP/BSL/ISP | `techno_params` | `page_techno.py:generate_techno_from_db` | `techno_params.html` | `TechnoParamsTemplate.js` | `techno_upload` / `techno_value`, `techno_plan_fy` (mill norms) |
| *35.4* | EPI (CO₂ / Water / PM) | `epi` | `page_epi.py:generate_epi` | `epi.html` | `EpiTemplate.js` | `techno_upload` / `techno_value` (General/EPI keys) |
| *35.5* | Coal Consumption | `coal_consumption` | `page_coal_consumption.py:generate_coal_consumption` | `coal_consumption.html` | `CoalConsumptionTemplate.js` | `techno_upload` / `techno_value` (coal keys), `production_monthly` |
| *35.6* | Coking Coal Receipts & Stock (SAIL) | `coal_receipt_stock` | `page_coal_receipts_stock.py:generate_coal_receipts_sail` | `coal_receipt_stock.html` | `CoalReceiptStockTemplate.js` | `techno_upload` / `techno_value` (coal receipt/stock keys) |
| *35.7* | Power Data | `power_data` | `page_power_data.py:generate_power_data` | `power_data.html` | `PowerDataTemplate.js` | `power_monthly` |
| *36–40* | Capital Repair (per plant) | `capital_repair` | `page_capital_repair.py:generate_capital_repair` | `capital_repair.html` | `CapitalRepairTemplate.js` | `capital_repair` |
| *(built, not wired)* | Key Highlights & Variances | `key_highlights` | `page_key_highlights.py:generate_key_highlights` | `key_highlights.html` | `KeyHighlightsTemplate.js` | `report_text`, `production_monthly`, `techno_upload` / `techno_value` |

### Standalone report routes

21 of these are grouped into 3 tabbed pages (like the manual-entry pages, see
§ above): body lives in `frontend/src/components/reports/<x>/View.js`, the old
`frontend/src/app/reports/<x>/page.js` is now a redirect to
`<group route>?tab=<x>` (`frontend/src/components/reports/reportGroups.js`
lists the groups/tabs; `ReportTabs.js` renders them). Techno's 5 reports were
already clubbed the same way into `/reports/techno` (its own tab pattern, see
`components/techno/`). Own backend endpoints — not part of `/api/data`.

| Tab (old route) | Group route | Backend | Tables |
|---|---|---|---|
| `one-page-report` | `/reports/external` | `page_one_page_report.py` | `sail_sales_monthly`, `report_text`, `sail_stock_snapshot`, `production_monthly` |
| `do-letter` | `/reports/external` | `page_do_letter.py` (`/api/do-letter…`) | `production_monthly` (actual + ABP), `report_text` |
| `jpc-report` | `/reports/external` | `page_jpc_report.py` (`/api/jpc-report` → xlsx) | `production_monthly` (actual + MoU) |
| `production-items` | `/reports/production-analysis` | `page_finished_steel_report.py` (`/api/finished-steel-report…`; Oven Pushing / Sinter / Hot Metal / Crude Steel / Pig Iron / Finished Steel / Saleable Steel) | `production_monthly` |
| `records-matrix` | `/reports/highlights-records` | `page_records.py` (`/api/records`) | `production_monthly` |
| `pmix-fy` | `/reports/external` | `page_pmix_fy_report.py` | `production_monthly` |
| `production-fy`, `production-query`; `major-production` (own tab) | `/reports/production-analysis`; `/reports/highlights-records` | `page_production_fy_export.py`, `page_production_query_export.py` | `production_monthly` (actual + ABP) |
| `special-steel-fy` | `/reports/special-steel-ipt` | `page_special_steel_fy_export.py` | `special_steel_order` |
| `reports/techno-custom`, `reports/techno-verification`, `reports/techno-monthly`, `reports/techno-dashboard` | `/reports/techno` (clubbed separately, see above) | `page_techno_custom_export.py`, `page_techno_verification_export.py`, `page_techno.py` | `techno_upload` / `techno_value`, `techno_plan_fy` |
| `bf-benchmark` | `/reports/special-steel-ipt` | `api_bf_benchmark.py`, `page_bf_benchmark_export.py` | `bf_benchmark_external_bf`, `bf_benchmark_external_data`, `bf_benchmark_sail_meta`, `techno_upload` / `techno_value` |
| `production-loss-analysis` | `/reports/loss-breakdown` | `production_loss_analysis.py`, `api_production_loss.py` | `production_monthly` (actual + ABP), `capital_repair`, `breakdown`, `item_capacity`, `major_unit_daily_record` (capacities for the headroom model) |
| `capital-repair-calendar` | `/reports/loss-breakdown` | `page_capital_repair.py:generate_capital_repair_calendar` (`/api/capital-repair-calendar…`), `page_capital_repair_calendar_export.py` | `capital_repair` |
| `bd-cr-log` | `/reports/loss-breakdown` | frontend-only: merges `/api/breakdown` + `/api/capital-repair` (per plant/FY) into one table per unit, month-grouped in date order; CRs only once they have actual dates; a CR-linked breakdown (`capital_repair_id`) is shown once, as the CR, timed by the breakdown's date-times | `breakdown`, `capital_repair` |
| `breakdown-analysis` | `/reports/loss-breakdown` | frontend-only (recharts); client-side aggregation over `GET /api/breakdown` (`api_breakdown.py`) | `breakdown` |
| `ipt-fy` | `/reports/special-steel-ipt` | `page_ipt.py` | `ipt_monthly` |
| `new-facilities` | `/reports/external` | (frontend-only / static) | — |
| `highlights` | `/reports/highlights-records` | frontend-only | — |
| `special-steel-physical` | `/reports/production-analysis` | `page_special_steel_physical.py` | `special_steel_phys_perf`, `special_steel_phys_meta`, `special_steel_phys_note` |
| `iron-ore-mines` | `/reports/mines` | `page_sail_mines.py` (mine-level) | `mine_production_monthly`, `mine_despatch_*`, `mine_booked_qty_*` |
| `sefi`, `steel-bulletin` | `/reports/external` | frontend-only | `production_monthly` |
| `secretary-review` | `/reports/external` | `page_secretary_review.py` (+ `_texts`, `secretary_review_pptx.py`, `secretary_review_layout.py`), `api_secretary_review.py` (`/api/secretary-review/*`); template `secretary_review_templates/secretary_review.pptx` (built by `scripts/prep_secretary_review_template.py`) | `production_monthly` (actual + ABP), `production_monthly` (MoU), `item_capacity`, `techno_upload` / `techno_value`, `techno_plan_fy`, `breakdown`, `capital_repair`, `report_text` |

---

## 4. Database tables reference (schema v2)

The database is `mis_reports_v2` (MySQL 9.x, port 3307). Its single DDL source of
truth is `backend/scripts/v2/schema_v2.sql`: the header carries the conventions, the
collation evidence and the v1 to v2 table map (the `V1-TABLE-MAP` block), and
`scripts/v2/seed_cal_month.sql` fills the month calendar. All SQL lives in
`backend/repo/<module>.py` (native MySQL, `%s` placeholders); no other file may
contain SQL (guard test `tests/test_repo_boundary.py`).

**Keys and conventions.**
- Master tables: `plant` (`plant_code` VARCHAR(8) PK, `plant_kind` in integrated /
  special / aggregate / external), `item` (`item_id`; `item_name` is unique under a
  binary collation, so case variants such as `CC BILLET` / `CC Billet` are separate
  items, and the repo matches names case-insensitively), `plant_unit` (`unit_id`, one
  row per plant + unit) and `cal_month` (`report_month` CHAR(7) `'YYYY-MM'`, 1960-04
  to 2040-03, with `month_start`, `fy`, `fy_month`, `quarter`, `half`).
- Fact tables reference those masters by foreign key (`plant_code`, `item_id`,
  `unit_id`, `report_month`). Column names are uniform: `plant_code`, `fy`
  (`'YYYY-YY'`, no FK), `created_at` / `updated_at`, `created_by` / `updated_by`.
- Writing an unknown plant creates a `plant_kind = 'external'` master row, and a
  case-variant item or unit creates one more spelling. This matches v1 behaviour.
  Filter by `plant_kind` when building display lists.
- `data_version` is a one-row write counter. Every repo write bumps it first, and the
  page cache is keyed on it (see the notes in `backend/docs/DB_V2_CUTOVER.md`).

### 4.1 Which repo module reads what

| Repo module | Tables |
|---|---|
| `repo/production.py` | `production_monthly`, `production_op_monthly` (Operating Plan, entry tab `op-plan`, file upload tab `op-plan-upload` via `op_plan_extract.py`; report tab `op-comparison`, OP vs APP vs Actual, via `/api/op-comparison`), `item`, `plant`, `cal_month` (+ `data_version`) |
| `repo/capacity.py` | `item_capacity`, `item`, `plant`, `cal_month` |
| `repo/techno.py` | `techno_upload`, `techno_value`, `techno_plan_fy`, `plant_unit`, `extraction_log` |
| `repo/text.py` | `report_text` (all narrative scopes) |
| `repo/special_steel.py` | `special_steel_order`, `special_steel_abp`, `special_steel_grade_club`, `special_steel_phys_meta`, `special_steel_phys_perf`, `special_steel_ipt_requirement`, `report_text` |
| `repo/stock.py` | `stock_monthly`, `sail_sales_monthly`, `sail_stock_snapshot` |
| `repo/ipt.py` | `ipt_monthly` |
| `repo/cost_trend.py` | `cost_trend_annual`, `cost_trend_monthly` |
| `repo/rake.py` | `rake_detention_master`, `rake_detention_monthly`, `rake_detention_summary`, `rake_detention_annual` |
| `repo/mines.py` | `mine_group`, `mine`, `mine_material`, `mine_end_use`, `mine_production_monthly`, `mine_despatch_actual_monthly`, `mine_despatch_plan_monthly`, `mine_booked_qty_actual_monthly`, `mine_booked_qty_plan_monthly`, `sail_mines_monthly` |
| `repo/breakdown.py` | `breakdown`, `capital_repair`, `plant_unit` |
| `repo/misc.py` | `power_monthly`, `pdf_item_alias`, `macro_indicator_monthly`, `market_price_monthly`, `steel_sector_performance`, `rail_prod_despatch`, `bf_benchmark_external_bf`, `bf_benchmark_external_data`, `bf_benchmark_sail_meta`, `major_unit_daily_record`, `ready_reckoner_page`, `cover_photo`, `report_cover_setting`, `unique_activity`, `unique_activity_tag`, `rmt_month`, `rmt_plan_note`, `rmt_ipt_row`, `rmt_stock_row` (RMT Production Plan manual rows) |
| `repo/pages.py` | `page_config` |
| `repo/ops.py` | `app_user`, `allowed_email`, `otp_code`, `activity_log`, `page_visit`, `admin_notification`, `extraction_log`, `todo_job`, `daily_work_log`, `data_version` |
| `repo/version.py`, `repo/conn.py`, `repo/_keys.py`, `repo/v2codec.py` | the write counter, connections, key resolution (`ensure_plant`, `check_month`), and the techno / timestamp codecs |

### 4.2 Production, plan and capacity

| Table | Key and content | Populated by | Read by |
|---|---|---|---|
| `production_monthly` | PK `(report_month, plant_code, item_id)`. One row holds the three v1 measures: `actual` (v1 `production_table`), `abp_plan` (v1 `production_plan_table`) and `mou_plan` (v1 `mou_plan_table`), each with a `has_*` flag so a missing value differs from zero. `'000 T` unless an item is a rate | Actuals: `/upload` → `POST /api/upload-excel` (per-plant extractors in `excel_extractors/`), Preview → `POST /api/confirm-extraction`, `entry/production/Form.js` → `POST /api/production-entry`, `data-entry/conversion`. ABP: `POST /api/upload-excel-plan`, `data-entry/targets`. MoU: `api_mou_plan.py` (`POST /api/mou-plan/insert`) | almost every `page_*.py` (see §3); `main.py:compute_item_row`, `production_utils.py`, `report_utils.py`. MoU basis: `page4.generate_page4_rows(basis="mou")`, `board_note_common.fs_mou`, `page_jpc_report`, `page_secretary_review.plan_basis` |
| `item_capacity` | `(plant_code, item_id, effective_month)` → `annual_capacity` (`'000 T/yr`); effective capacity = latest row at or before the month | `data-entry/annual-capacity` → `/api/capacity` | `page4.py`, `page_at_a_glance.py` |
| `pdf_item_alias` | `(plant_code, pdf_label)` → `item_id`, `convert_t`; learned when a user renames a row on the extraction preview | Preview rename | every extractor's label mapping |
| `power_monthly` | `(report_month, plant_code, power_item)` → `value` (power-OIS codes, not items) | `api_power_omi.py` | `page_power_data.py` (35.7) |

### 4.3 Stock, IPT and SAIL sales

| Table | Holds | Read by |
|---|---|---|
| `stock_monthly` | `(report_month, plant_code, item_type, stock_type)` → `stock` | `page_opening_stock.py` (25) |
| `sail_sales_monthly` | `(report_month, item_name)` → the 10 source figures (JSON) | `page_one_page_report.py` |
| `sail_stock_snapshot` | `(snapshot_date, item_name)` → `value`; `snapshot_date` is a DATE | `page_one_page_report.py` |
| `ipt_monthly` | `(report_month, item, from_plant_code, to_plant_code)` → plan / actual / unit / tonnage / `sort_order` | `page_ipt.py` (26), `reports/special-steel-ipt?tab=ipt-fy` |

Written by `data-entry/opening-stock`, `sail_sales_stock_extractor.py` and `data-entry/ipt` (`/api/ipt-entry`, `/api/ipt-entries/bulk`).

### 4.4 Techno-economic

The v1 `techno_data` JSON blob is split in two, and the plan table is renamed:

| Table | Key and content |
|---|---|
| `techno_upload` | PK `(report_month, plant_code, unit_id)`; one row per v1 blob: metadata (source, who / when, `seq` = the v1 row id, continued by new rows) |
| `techno_value` | PK `(report_month, plant_code, unit_id, period, param_key)`; one row per leaf, with `period` month or till_month and exactly one of `num` / `raw` set. `param_key` is at most 190 characters |
| `techno_plan_fy` | `(plant_code, unit_id, fy)` → targets / plan, `is_user_supplied`, calculated values and method |

`repo/v2codec.py` converts between the `{"month": {...}, "till_month": {...}}` blob shape the
pages use and these rows. `till_month` is April to report month, stored directly, not
auto-summed. Units include `BF_Shop`, `BF-1..BF-8`, `SMS`, `COB`, `Sinter`, mill units and `General`.

- **Populated by:** the Preview → Insert techno extractors (`excel_extractor_*`, `techno_project/*`), the techno APIs (`api_*_techno.py`, `api_coal_*`, `api_unified_techno.py`), the manual forms (`entry/techno-manual`, `techno-correction`, `key-parameters-manual`, `co2-water-pm-manual`, `bf-large-snapshot` → `POST /api/techno/manual/save`) and the SAIL BF aggregate (`POST /api/techno/manual/sail/calculate`). Plan: `data-entry/techno`, `annual-target` → `/api/techno-plan`, `/api/sail-techno-plan` and the other techno plan / target routes in `main.py`. Cumulative rules: `techno_cumulative.py:CUMULATIVE_RULES`.
- **Read by:** `page_techno.py` (27-35), `page_key_parameters.py`, `page_bf_large_annexure.py`, `page_epi.py`, `page_coal_consumption.py`, `page_coal_receipts_stock.py`, `page_at_a_glance.py`, `api_bf_benchmark.py`, `page3_highlights.py`.
- Param keys, labels and areas: `frontend/src/lib/technoParamRegistry.js`; backend `plant_registry.py`, `techno_registry.py`.

### 4.5 Special steel

| Table | Key and content | Read by |
|---|---|---|
| `special_steel_order` | `(report_month, plant_code, product, quality_grade, section)` → order qty, despatch, `sort_order` | `page_special_steel.py` (19-24), trend, FY export |
| `special_steel_abp` | `(report_month, plant_code)` → `abp_qty` | `page_special_steel.py` |
| `special_steel_grade_club` | `(plant_code, product, quality_grade)` → `club_label` | `page_special_steel.py` |
| `special_steel_phys_perf`, `special_steel_phys_meta` | history by `(fy, plant_code, series, metric)`; capacity / best-year metadata by `(plant_code, series)` | `page_special_steel_physical.py` |
| `special_steel_ipt_requirement` | `(fy, item, from_plant_code, to_plant_code)` → plan | `page_special_steel_physical.py` |

The physical-performance notes are `report_text` rows with scope `ss_phys_note`.

### 4.6 Cost trend, rake detention, market

| Table | Key and content | Read by |
|---|---|---|
| `cost_trend_annual` | `(fy, product, cost_type, plant_code)` → value. Products HM, CS, SS, COKE, SINTER; COKE and SINTER only feed the Inter Plant page | `page_cost_trend.py`, `page_key_parameters.py` |
| `cost_trend_monthly` | `(report_month, product, cost_type, plant_code)` → month / till-month value | same |
| `rake_detention_master`, `rake_detention_monthly`, `rake_detention_summary`, `rake_detention_annual` | rake-detention reference rows and the monthly, period and annual figures | `page_rake_detention.py` |
| `macro_indicator_monthly`, `market_price_monthly` | market-intelligence series by `(report_month, metric_code / series_code)` | market commentary views |

### 4.7 SAIL Mines

| Table | Holds |
|---|---|
| `sail_mines_monthly` | `(report_month, section, item)` → actual / plan (sections in `page_sail_mines.py:SAIL_MINES_SECTIONS`) |
| `mine_group`, `mine`, `mine_material`, `mine_end_use` | reference data (v1 `mine_groups_master`, `mines_master`, ...) |
| `mine_production_monthly` | `(report_month, mine_code, material_code)` → actual / plan |
| `mine_despatch_actual_monthly` | `(report_month, mine_code, material_code, transport_mode, end_use_code)` |
| `mine_despatch_plan_monthly` | `(report_month, mine_code, material_code, end_use_code)` |
| `mine_booked_qty_actual_monthly`, `mine_booked_qty_plan_monthly` | mine-level booked quantity (third-party sales) |

Entered through `entry/mines-production-despatch/Form.js`; read through `repo/mines.py` by `page_sail_mines.py` and `reports/mines`. The Iron Ore group tables and trend charts on the SAIL Mines page are still hard-coded in `hardcoded_config.json` (`sail_mines`).

### 4.8 Narrative text and other page tables

All free-text blocks share one table, `report_text`: unique key `(scope, period, block_key, plant, item, seq)` plus the text. The scope names the v1 table it replaces:

| scope | v1 table | Read by |
|---|---|---|
| `page3_narrative` | `page3_narrative` | page 3 (`page3_highlights.py`) |
| `key_highlights` | `key_highlights_narrative` | `page_key_highlights.py` (built, not wired) |
| `secretary_review` | `secretary_review_text` | `page_secretary_review.py` |
| `board_note` | `board_note_manual_text` (period `'<fy>:Q<n>'`) | board notes |
| `do_letter` | `do_letter_remark_table` | `page_do_letter.py` |
| `sail_sales_note`, `steel_sales`, `rail_note`, `ss_phys_note` | `sail_sales_note_table`, `steel_sales_highlights`, `rail_prod_despatch_note`, `special_steel_phys_note` | one-page report, steel sales highlights, rail report, special steel physical |

Other page tables: `steel_sector_performance` (one PIB release per month, pages 2.1-2.3), `rail_prod_despatch` (rail report), `page_config` (below), `cover_photo` and `report_cover_setting` (cover), `ready_reckoner_page` (ready reckoner), `unique_activity` + `unique_activity_tag` (Unique Activities: entry tab under Reference & Records, view tab under Highlights & Records; not in the PDF), `rmt_month` + `rmt_plan_note` + `rmt_ipt_row` + `rmt_stock_row` (RMT Production Plan: remarks, IPT requirement / availability and stock, entry tab `rmt-plan` under Production & Techno Entry; report tab `rmt-plan` under Production Reports with its own PDF / Excel via `/api/rmt-plan`, APP / OP / actual from `production_monthly` / `production_op_monthly`, coal requirement calculated from `techno_plan_fy` dry coal charge × pushing plan; not in the monthly PDF).

### 4.9 Capital repair, breakdown, BF benchmarking, major units

| Table | Holds |
|---|---|
| `capital_repair` | annual CR plan rows per plant / FY, with `unit_id`, `unit_type` and actual start / end dates |
| `breakdown` | unplanned-downtime events; `capital_repair_id` is a deliberate non-FK (v1 leaves dangling ids and output depends on that) |
| `major_unit_daily_record` | `(plant_code, unit_id)` best-record rows (`record_date` stays free text) |
| `bf_benchmark_sail_meta` | `(plant_code, unit_id)` → working volume of SAIL's large BFs |
| `bf_benchmark_external_bf`, `bf_benchmark_external_data` | non-SAIL BF registry and its figures per FY (`fy`) |

Read by `page_capital_repair.py` (36-40), `api_breakdown.py`, `api_bf_benchmark.py`, `page_bf_large_annexure.py`.

### 4.10 System / operational (not on any report page)

| Table | Holds | Populated by |
|---|---|---|
| `page_config` | `(report_month, page_number)` → `page_data` JSON: inline-edit overrides and cached page output | `POST /api/data` on `/report` |
| `app_user` | accounts, `role` (`NULL` / `editor` / `admin`), `allowed_pages`, `can_delete` (v1 `users`) | registration / login, `/admin/users` |
| `allowed_email`, `otp_code` | registration whitelist, one-time codes | `/admin/users`, `api_auth.py` |
| `activity_log` | every gated insert / update / delete (who / when / what) | `main.py` middleware (`activity_context.py`) |
| `extraction_log` | upload audit; `plant_name` and `report_month` are free values, not FKs | every extractor upload |
| `page_visit`, `admin_notification`, `todo_job`, `daily_work_log` | usage log, admin alerts, To-Do items, daily work log | middleware, `api_todo.py`, `api_worklog.py` |
| `data_version` | one-row write counter that keys the page cache | every `repo` write |

Write-route to module gate mapping (which `role='editor'` users may hit which
endpoint): `backend/constants.py:PAGE_MODULES`, enforced by
`main.py:EditorAdminGateMiddleware`.

---

## 5. Recipes — common changes

### 5.1 Add a new item/row to an existing report page
1. **Backend generator** (`page_<x>.py`): add the row to whatever registry/list
   the generator iterates (e.g. `page_key_parameters.py:_ROWS`,
   `page_sail_mines.py:SAIL_MINES_SECTIONS`, `page4.py`'s item list). Make sure the
   value is produced in the returned `pageData` dict.
2. **PDF template** (`page_templates/<type>.html`): if the template hard-codes row
   labels/order, add the new row there; if it loops `pageData.rows`, nothing to do.
3. **Preview component** (`frontend/src/components/<Type>Template.js`): mirror the
   template change (same loop or same hard-coded list).
4. If the value should be **editable** on `/report`, ensure the component renders an
   `<input>`/`editor-input` bound through `onCellChange` and that the generator
   merges `page_config` overrides.
5. Regenerate for a test month and diff (see §6).

### 5.2 Map a new item to a DB column that already exists
- New **production item**: add its source label to `pdf_item_alias` (or the
  extractor's label map in `excel_extractors/<plant>*.py`), then it flows into
  `production_monthly` and any page that lists that item.
- New **techno param**: add the key to `frontend/src/lib/technoParamRegistry.js`
  (`PARAM_TEMPLATES.<area>` + `_LABEL_MAP`), optionally a cumulative rule in
  `backend/techno_cumulative.py:CUMULATIVE_RULES`, then reference the key from the
  consuming `page_*.py` (e.g. add a `_ROWS` entry in `page_key_parameters.py` with
  `kind="general"`/`"bf"`/`"coke_unit"`). `POST /api/techno/manual/save` accepts any
  key — no backend whitelist.
- New **cost-trend product**: add to `main.py:COST_TREND_PRODUCTS`,
  `frontend/.../cost-trend/page.js:PRODUCTS`, and (if it should feed the Inter Plant
  page) `page_key_parameters.py:_COP_PRODUCTS` + a `_ROWS` entry `kind="cop"`.

### 5.3 Add a brand-new DB-backed field/section
1. Add the table / columns to `backend/scripts/v2/schema_v2.sql` and write a
   `backend/scripts/v2/migrate_<x>.sql` for the live database.
2. Add `get_<x>()` / `save_<x>()` functions in the matching `backend/repo/<module>.py`
   (native MySQL, `%s` placeholders; writes must bump `data_version` first).
3. Add an API endpoint (`api_<x>.py` or `main.py`) and register the router in
   `main.py`; add its write routes to `constants.py:PAGE_MODULES` for gating.
4. Add a data-entry page under `frontend/src/app/data-entry/<x>/page.js` (copy the
   closest existing one — they follow a load/edit/`countChanges`/save pattern) and
   link it from `frontend/src/app/data-entry/page.js`.
5. Consume it in the relevant `page_<x>.py` generator + both renderers (§5.1).

### 5.4 Add a whole new report page
1. Define a sentinel id constant in `main.py` (float that sorts into place, e.g.
   `3.7`) and add it to: the strip-tuple, the insertion block (anchored to a fixed
   page), and a dispatch `if pg == <ID>:` that calls your `generate_*()` and sets
   `page["type"]`.
2. Create `backend/page_<x>.py` with `generate_<x>(report_month) -> dict`.
3. Create `backend/page_templates/<type>.html` and add an `{% elif page.type ==
   '<type>' %}{% include '<type>.html' %}` line in `page_templates/main.html`
   (both the class block ~line 1624 and the include block ~line 1657).
4. Create `frontend/src/components/<Type>Template.js` and add a `case '<type>':`
   in `frontend/src/components/PageRenderer.js`.
5. Add the id to `frontend/src/app/report/page.js`'s page-number/label lists.
6. If landscape, set `page["orientation"] = "landscape"` in `main.py` and add the
   type to the landscape lists in `pdf.py` (`_LANDSCAPE_TYPES`) and `main.html`.

### 5.5 Change only styling / layout (no data change)
- Colours used in PDF templates: edit `backend/colors_config.json` (no restart).
- Per-page font sizes / margins: edit `backend/layout_config.json` (no restart).
- Structural CSS: `page_templates/main.html` `<style>` (PDF) and
  `frontend/src/app/globals.css` (preview) — keep the two in sync for shared classes.

### 5.6 Update a figure that has no DB source yet
Edit `backend/hardcoded_config.json` (sections `sail_mines`,
`special_steel_physical`, `key_parameters`). Read via
`backend/hardcoded_loader.py`; changes apply on next generation, no restart. Do
**not** re-scatter these back into `page_*.py`.

---

## 6. Verifying a change

```bash
cd backend
venv/Scripts/python -m pytest tests -q            # golden-file extractor tests
venv/Scripts/python -c "import page_key_parameters as k; import json; \
  print(json.dumps(k.generate_key_parameters('2026-07'), indent=2, default=str))"
```

- Preview: `npm run dev` in `frontend/`, open `/report`, pick the month.
- PDF: `/report` → "Download PDF" (or `POST /api/generate-pdf/start`).
- `scripts/backfill_*.py` hold v1 SQL and are historical: do not run them against v2.
  Scripts that write must go through `repo.<module>`.

---

## 7. File index (quick lookup)

| You want to change… | Edit |
|---|---|
| What a report page shows | `backend/page_<x>.py` (generator) |
| How it looks in the PDF | `backend/page_templates/<type>.html` (+ `main.html` dispatch) |
| How it looks in the browser preview | `frontend/src/components/<Type>Template.js` (+ `PageRenderer.js`) |
| Page order / insertion / numbering | `backend/main.py` (sentinel ids + `/api/data` assembly) |
| A data-entry form | `frontend/src/app/data-entry/<x>/page.js` (+ its `api_<x>.py`) |
| An Excel/PDF importer | `backend/excel_extractors/<plant>*.py` |
| DB schema / accessors | `backend/repo/<module>.py` (+ `scripts/v2/schema_v2.sql`, `scripts/v2/migrate_*.sql`) |
| Endpoint routing / gating | `backend/main.py`, `backend/constants.py:PAGE_MODULES` |
| Techno param labels/areas | `frontend/src/lib/technoParamRegistry.js`, `backend/plant_registry.py` |
| Report colours / fonts / margins | `backend/colors_config.json`, `backend/layout_config.json` |
| Figures with no DB source | `backend/hardcoded_config.json` |
| PDF rendering / pagination | `backend/pdf.py` |

---

## 8. PDF template reference — `backend/page_templates/*.html`

Every template is a **Jinja2 partial** `{% include %}`d by `main.html` (dispatch at
`main.html` ~line 1622–1658), wrapped by `main.html` in the `.page` div with the
`pg-<n>` class, header, footer and corner dept-badge. Each partial receives:

- `page` — the `pageData` dict from the matching `generate_*()` (§3). Access with
  `page.foo` or `page['foo']`.
- `colors` — `colors_config.json` map (`{{ colors.text_primary }}` etc.). **Never
  hard-code a hex in a template** — add a key to `colors_config.json`.
- `page_layouts` / `_pl` — per-page font/margin overrides from `layout_config.json`.
- date/label helpers injected globally by `pdf.py`: `short_m`, `short_y`,
  `short_prev_y`, `prev_y`, `m_name`, `target_header`, `fy_str`,
  `total_report_pages`.
- custom Jinja filters (registered in `pdf.py`): `pgclass`, `split_label`,
  `subscript_co2`.

The **preview counterpart** for each is `frontend/src/components/<X>Template.js`,
switched in `PageRenderer.js` on `page.type`. Keep the two visually in sync; they
consume the identical `page` dict.

### Shared / structural templates

| Template | Role |
|---|---|
| `main.html` | The whole document shell: `<head>` CSS (the bulk of PDF styling), `@page` rules, `page_layouts` → CSS-var block, the `{% for page in pages %}` loop, per-`type` class assignment and `{% include %}` dispatch, `@@PGSTART_n@@` pagination markers. **Add a new page type here** (class block ~1624 + include block ~1657). |
| `trend_section.html` | Not include-dispatched by type-name like the others — handled as its own branch (`{% if page.type == 'trend_section' %}`) because `pdf.py` measures/splits it row-by-row. Emits `@@TROW_i_j@@` markers. |
| `cost_trend_macro.html` | `{% macro cost_trend_product(page, colors) %}` — the actual Cost Trend table; `cost_trend.html` is a 3-line wrapper that imports and calls it. |
| `performance_summary_table.html` | Shared by pages 5 and 6 (`type = performance_summary_table`). |
| `trend.html` / `trend_yearly.html` | Pages 7–12; `trend_yearly` = the 10-year Apr…Mar + Q/H/Total grid, `trend` = the simpler header/rows table. |

### Per-page templates — data contract

`page.*` = the keys the template reads. Cross-check against the generator's return
dict when adding a field.

| Template | `type` | Renders | Key `page.*` fields |
|---|---|---|---|
| `cover.html` | `cover` | Page 1 KPI cards + month banner | `bg_data_uri`, `month_display`, `month_short`, `kpis[]` (`label`, `mt`, `pct_ful`, `growth`, `growth_good`) |
| `index.html` | `index` | Contents table | `title`, `rows[]` (`sno`, `title`, `page_range`) |
| `summary.html` | `summary` | Page 3: narrative + 12-col production table + Highlights + TE-parameter table + bar charts | `title`, `production_narrative`, `production_table[]` (`item`, `values[12]`), `highlights[]` (strings; `:-` suffix = heading), `te_table[]` (`parameter`, `unit`, `values[5]`), `_chart_html` (raw) |
| `page4_table.html` | `page4_table` | Page 4: item×plant grid, Ann.Cap / APP / month block / CPLY / CU% / YTD block | `rows[]` (`item`, `plant`, `capacity`, `values[]`, `is_first_in_group`, `group_size`, `is_conversion`, `is_sail_incl_conv`) |
| `performance_summary_table.html` | `performance_summary_table` | Pages 5–6: plant→item rows, plan/act/%ful month + YTD | `rows[]` (`plant`, `label`, `bold`, `values[]`), `_page6_charts_html` (page 6 only) |
| `trend_yearly.html` | `trend_yearly` / `trend_combined` | Pages 7–12: 10-yr month grid w/ best-ever & best-month cell flags | `item_display`, `unit`, `rows[]` (`values[19]`, `cell_flags[19]`, `plant`, `year_label`, `is_plan`, `rowspan_start`, `plant_row_count`, `is_first_in_plant`) |
| `trend_section.html` | `trend_section` | Same grid, multi-item, row-split aware | `items[]` each with `item_display`, `unit`, `rows[]` (as above + `break_before`) |
| `concast_performance.html` | `concast_performance` | Page 13: monthly + YTD concast tables (plant × plan/act/%ful/CPLY/growth) | `monthly[]`, `ytd[]` (`plant`, `ann_plan`, `m_plan`/`ytd_plan`, `m_act`/`ytd_act`, `m_pct`/`ytd_pct`, `cply_act`/`ytd_cply`, `m_growth`/`ytd_growth`, `bold`) |
| `prod_by_process.html` | `prod_by_process` | Page 14: BOF/EAF/CC/CS split, monthly + YTD + HM→SS sankey | `monthly[]`, `monthly_prev[]`, `ytd[]`, `ytd_prev[]` (`plant`, `bof`, `eaf`, `cc`, `cs`, `bof_pct`, `cc_pct`, `bold`), `sankey_svg` (raw) |
| `catwise_saleable.html` | `catwise_saleable` | Pages 15–17: per-plant category→item, month + cum blocks | `title`, `month_label`, `cply_label`, `sections[]` → `label`, `rows[]` (`type`: `separator`/`section-hdr`/data; `category`, `cat_first`, `cat_rowspan`, `label`, `ann_plan`, `m_*`, `cum_*`) |
| `segment_wise.html` | `segment_wise` | Page 18: group→plant→item segment table | `title`, `month_label`, `cply_label`, `rows[]` (`type`: `separator`/`seg-total`/`seg-pct`/`grand-total`/data; `group`, `plant`, `show_group`, `group_span`, `show_plant`, `plant_span`, `label`, `ann_plan`, `m_*`, `cum_*`) |
| `special_steel.html` | `special_steel` | Pages 19–24: 3 variants — `plant_detail` (Product+Grade, BSP/DSP/RSP/BSL), `isp_summary` (one row/mill), `sail_summary` (consolidated). Density auto-tiered. | `variant`, `density` (`pad`, `label_fs`, `table_fs`, `lh`, `split_at`, `tail_scale`), `title_prefix`/`plant_display`/`title`, `month_label`, `cply_label`, `cum_label`, `cum_cply_label`, `fy_label`, `rows[]` (`type`: `separator`/`grand-total`/`subtotal`/`product-total`/data; `label`, `product_name`, `prod_first`, `prod_rowspan`, `orders`, `actual`, `pct_ful`, `cply`, `pct_growth`, `cum_*`), `saleable_production`, `special_pct` |
| `special_steel_trend.html` | `special_steel_trend` | After 24: SVG trend charts | `title`, `fy_range_label`, `month_svg`, `till_month_svg`, `annual_svgs[]` (all raw SVG) |
| `special_steel_physical.html` | `special_steel_physical` | ASP/SSP/VISP physical perf, landscape | `title`, `unit`, `cur_fy`, `prev_fy`, `ytd_label`, `history_fys[]`, `sections[]` → `plant`, `rows[]` (`series_label`, `capacity`, `best_actual`, `best_year`, `history{}`, `prev_actual`, `cur_abp`, `ytd_app`, `ytd_actual`, `ytd_pct_ful`, `ytd_cply`, `ytd_growth`), `notes[]`, `ipt_title`, `ipt_rows[]` |
| `opening_stock.html` | `opening_stock` | Page 25: section→plant→item stock grid (fixed 258mm table height for page-fill) | `title`, `unit`, `col_labels[]`, `var_label`, `sections[]` → `label`, `code`, `rows[]` (`sub`, `plant`, `plant_rowspan`, `values[]`, `var`, `sail`, `bold`) |
| `ipt_status.html` | `ipt_status` | Page 26: IPT routes, month + cum | `title`, `month_label`, `cum_label`, `sections[]` |
| `techno_params.html` | `techno_params` | Pages 27–35: Parameter / Unit / Norm(Target) / month cols / cum / CPLY, grouped by section | `title`, `subtitle`, `group`, `fy`, `month_labels[]`, `cum_label`, `cply_label`, `cum_cply_label`, `target_label`, `sections[]` (each with rows of param/unit/values) |
| `key_parameters.html` | `key_parameters` | Inter Plant Performance Comparison — Parameter / UoM / BSP..ISP; section & spacer rows; min/max cell highlight | `title`, `plants[]`, `rows[]` (`type`: `section`/`spacer`/`data`; `parameter`, `unit`, `note`, `label_rowspan`, `continuation`, `highlight`, `plant_values{plant: str}`, `max_plants[]`, `min_plants[]`) |
| `key_highlights.html` | `key_highlights` | (built, not wired) landscape: Achievements / Shortfalls / Focus Areas + KPI/techno/YTD blocks | `title`, `subtitle`, `month_label`, `achievements[]`, `shortfalls[]`, `focus_areas[]`, `kpi`, `techno`, `ytd`, `value_added` |
| `at_a_glance.html` | `at_a_glance` | "MIS at a Glance" infographic (page 1) | `title`, `month_label`, `production`, `special_steel`, `techno`, `trend`, `ytd_trend` (mostly pre-rendered sub-structures / SVG) |
| `best_ever_highlights.html` | `best_ever_highlights` | Records: per-group best-ever cards | `title`, `month_label`, `unit_note`, `groups[]` |
| `best_calendar_month.html` | `best_calendar_month` | Best-for-this-calendar-month records | `title`, `month_label`, `unit`, `month_names[]`, `groups[]` |
| `bf_large_annexure.html` | `bf_large_annexure` | SAIL large-BF snapshot, landscape | `title`, `periods[]`, `sail_cols[]`, `rows[]` |
| `cost_trend.html` → `cost_trend_macro.html` | `cost_trend` | Cost Trend HM/CS/SS: annual FY cols + current-FY months + till-month, Total/Variable/Fixed blocks, landscape | `title`, `unit`, `periods[]`, `blocks[]` (Total/Variable/Fixed, each plant × period) |
| `sail_mines.html` | `sail_mines` | SAIL Mines: 7 section tables (APP/Act/%FF/CPLY/%Grth) via `{% macro sail_mines_table %}` + `mines_charts_html` | `title`, `period_label`, `unit`, `tables[]` (`title`, `kind`, `columns[]` or `column_groups[]`, `rows[]`), `mines_charts_html` (raw) |
| `coal_consumption.html` | `coal_consumption` | Coal consumption: qty & % column groups | `title`, `qty_cols[]`, `pct_cols[]`, `groups[]` |
| `coal_receipt_stock.html` | `coal_receipt_stock` | Coking-coal receipts + consumption + stock history, landscape | `title`, `receipt_rows[]`, `consumption_rows[]`, `stock_history_tables[]`, `stock_history_month_names[]`, `stock_cols_*`, `stock_gap_after` |
| `power_data.html` | `power_data` | Power OMI per plant | `title`, `plants[]` |
| `epi.html` | `epi` | Environmental Performance Index (CO₂/Water/PM), landscape | `title`, `fy`, `month_labels[]`, `cum_label`, `cply_label`, `cum_cply_label`, `target_label`, `sections[]` |
| `steel_sector_performance.html` | `steel_sector_performance` | PIB steel-sector release, pages 2.1–2.3, via `{% macro generic_table / value_cell / text_section %}` | `title`, `section`, `report_month`, `data_month`, `posted_on`, `footer_note`, `available`, `tables[]`, `text_sections[]` |
| `capital_repair.html` | `capital_repair` | CR plan per plant, shop→equipment→activity→schedule→period→actual | `title`, `subtitle`, `sections[]` → `shop`, `rows[]` |

### Adding a field to an existing page (template side)
1. Produce it in `generate_<x>()` → the returned dict.
2. `page_templates/<type>.html`: render `{{ page.<field> }}` (or loop it). If it's
   HTML/SVG you built in Python, output with `| safe`.
3. `frontend/src/components/<X>Template.js`: render the same field the same way.
4. If it needs a colour, add a key to `colors_config.json` and use
   `{{ colors.<key> }}` — the JS component keeps its own hex copy (see the
   comment at the top of each `*Template.js`).
5. Regenerate a test month (both `/report` preview and PDF) and diff.

---

## 9. Data-entry pages — `frontend/src/app/data-entry/<x>/page.js`

These are the manual-entry / file-upload UIs. They are the **only** way to
populate the tables that have no extractor (Demurrage, CAPEX, RLTIFR, ABP,
capital-repair, breakdown, SAIL mines, cost trend, narratives, …) and the
correction path for tables that do.

### 9.1 The common pattern

Every page is a client component wrapped like:

```jsx
export default function XPage() {
  return <RequireEditor><XPageInner/></RequireEditor>;   // components/RequireEditor.js
}
```

- **`RequireEditor`** gates the whole page to `role ∈ {editor, admin}`.
  Per-*module* restriction (an editor limited to e.g. only "techno") is enforced
  **server-side** by `main.py:EditorAdminGateMiddleware` against
  `constants.py:PAGE_MODULES` — the client gate is UX only.
- **`GlobalNavbar`** (`components/GlobalNavbar.js`) at the top; content in a
  `flex:1; overflow:auto` scroll container (because `globals.css` sets
  `html,body{overflow:hidden}`).
- **Load → edit → save** loop: `load()` fetches current values into `saved` +
  `edits` state; a `countChanges()` / `isChanged()` helper drives a changed-cell
  highlight (amber border/bg) and the `Save (N changes)` button label; `save()`
  POSTs only the changed cells, then re-loads to reset the baseline.
- Period pickers use **FY-ordered** month lists (April first) and a
  `getDefaultPeriod()` = last calendar month.
- No React Router state — the month/plant/FY selectors are local `useState`.
- Backend endpoints live in `main.py` or a dedicated `backend/api_<x>.py` router
  (registered in `main.py`); each write route is listed in
  `constants.py:PAGE_MODULES` under its module key.

### 9.2 Shared building blocks

| File | Used by | Role |
|---|---|---|
| `components/RequireEditor.js` / `RequireAdmin.js` / `RequireAuth.js` | all | client-side role gate |
| `components/GlobalNavbar.js` | all | top nav; also the canonical link list to every data-entry & report route |
| `hooks/useDataEntryAPI.js` | opening-stock, ipt, conversion, targets | thin fetch wrappers (`/api/opening-stock`, `/api/stock-entry`, `/api/ipt`, `/api/conversion-data`, `/api/targets`) |
| `hooks/useReportAPI.js` | (report viewer) | `useReportData` → `/api/data` |
| `components/SpecialSteelManualEntry.js` | `special-steel/` | the actual grade grid (ISP + corrections) → `/api/special-steel-manual/save` |
| `components/TechnoExtractedParams.js` | `co2-water-pm/` | generic "N params × 5 plants, month + till-month" grid over `techno_upload` / `techno_value` General unit; the page just passes `paramRows` |
| `components/BSLBFTechnoExtractor.jsx` | `techno/` | BSL blast-furnace techno sheet parse/preview |
| `components/HotMetalConsumptionEntry.js` | `techno-manual/` | HM-consumption sub-form |
| `components/SailSmsParamsDisplay.js`, `TechnoPerformanceCharts.js`, `TechnoExtractedParams.js` | techno pages | display helpers |
| `lib/technoParamRegistry.js` | techno-manual, techno-correction, key-parameters-manual | param key ↔ label ↔ shop-area registry (single source of truth for the forms) |

### 9.3 Per-page reference

| Route (`/data-entry/…`) | Purpose | Endpoint(s) | Target table(s) |
|---|---|---|---|
| `production` | Enter/correct monthly actual (and plan) production per item/plant; item-name alias suggestions | `/api/production-entry`, `/api/production-items`, `/api/item-mapping-suggestions` | `production_monthly` (actual + ABP), `pdf_item_alias` |
| `opening-stock` | Opening stock per plant/item/type as-on 1st of month | `/api/opening-stock`, `/api/stock-entry`, `/api/stock-data` (via `useDataEntryAPI`) | `stock_monthly` |
| `ipt` | Inter-plant transfer plan/actual per route; bulk paste; delete | `/api/ipt-entries`, `/api/ipt-entries/bulk`, `/api/ipt-delete`, `/api/ipt-items` | `ipt_monthly` |
| `conversion` | Monthly conversion figures (SAIL consolidated) | `/api/conversion-data`, `/api/conversion-entry` | `production_monthly` (conversion items) |
| `targets` | Annual TE targets by plant (BF / SMS / major params); SAIL weighted recompute | `/api/techno-plant-targets`, `/api/techno-sail-targets`, `/api/techno-sms-targets`, `/api/techno-major-parameters`, `/api/techno-recalculate-sail-weighted` | `techno_plan_fy` |
| `annual-target` | Per-page techno Norm/Target columns (pages 27–35) + coal-blend targets | `/api/techno-page-targets`, `/api/coal-blend-targets` | `techno_plan_fy` |
| `annual-capacity` | Rated annual capacity per plant/item with mid-FY effective-dated changes | `/api/capacity`, `/api/capacity/{id}` (PATCH/DELETE) | `item_capacity` |
| `techno` | Multi-plant techno **file** extraction: BSP flash-PDF / OISCO / 3-page-Tech, DSP MCR, generic techno preview + insert, 12-month backfill | `/api/bsp-techno/*`, `/api/mcr-techno/*`, `/api/techno/{preview,insert,preview-months,insert-months,data}`, `/api/extraction-log` | `techno_upload` / `techno_value` |
| `techno-manual` | Full manual techno grid per plant/unit/month, auto YTD-cumulative preview, SAIL BF aggregate calculate/preview | `/api/techno/manual/{entry,save,cumulative-preview,sail/calculate,sail/preview}` | `techno_upload` / `techno_value` |
| `bf-large-snapshot` | Month + Till Month grid for BSP BF-8 / RSP BF-5 / ISP BF-5 in "SAIL Large BFs — Performance Snapshot" (page 3.6) row order; same rows/keys as `techno-manual` (row list + aliases from `/api/bf-benchmark/params`) | `/api/bf-benchmark/params`, `/api/techno/manual/{entry,save,cumulative-preview}` | `techno_upload` / `techno_value` |
| `techno-correction` | Find one param across a plant + month range, inline-edit | `/api/techno/manual/param-history`, `/api/techno/manual/save` | `techno_upload` / `techno_value` |
| `key-parameters-manual` | The Inter-Plant-page fields with no extractor: CAPEX, Labour Productivity, Demurrage, HM-to-PCM, **RLTIFR**, Sinter Fe override. Avg Rake Detention is here only as a fallback; the page reads `rake_detention_summary` `YTD_TY` first | `/api/techno/manual/{entry,save}` | `techno_upload` / `techno_value` (`General` unit; RSP `SP-1/2/3` for Sinter Fe) |
| `co2-water-pm` | Sp. CO₂ / Water / PM emission, 5 plants, month + till-month (wraps `TechnoExtractedParams`) | `/api/techno/data`, `/api/techno/manual/save` (via component) | `techno_upload` / `techno_value` (`General`) |
| `co2-water-pm-manual` | Same three params, plain manual grid | `/api/techno/manual/{entry,save}` | `techno_upload` / `techno_value` (`General`) |
| `coal-consumption` | Coal blend / consumption + coal-OMI opening stock | `/api/techno/data`, `/api/coal-omi/opening-stock` | `techno_upload` / `techno_value` (coal keys) |
| `uploads` | Coal-CO₂, Coal-OMI, Power-OMI and MoU Plan **file** extraction (preview + insert) | `/api/coal-co2/{preview,insert}`, `/api/coal-omi/{preview,insert}`, `/api/power-omi/{preview,insert}`, `/api/mou-plan/{preview,insert}` | `techno_upload` / `techno_value`, `power_monthly`, `production_monthly` (MoU) |
| `special-steel` | ISP special-steel manual entry + corrections (grade grid) | `/api/special-steel-manual/save` (+ grades/products) | `special_steel_order` |
| `special-steel-abp` | Special-steel ABP, 12 months per plant at once | `/api/special-steel-abp` | `special_steel_abp` |
| `special-steel-grade-clubs` | Combine near-duplicate quality grades into one report row | `/api/special-steel/grade-clubs`, `/api/special-steel/{grades,products}` | `special_steel_grade_club` |
| `special-steel-ipt` | Special-steel IPT requirement per FY (item/from/to/plan), bulk + delete | `/api/special-steel-ipt-requirement`, `.../bulk`, `.../delete`, `.../fys` | `special_steel_ipt_requirement` |
| `special-steel-physical` | ASP/SSP/VISP physical-performance grid (history, capacity, best, ABP, notes) | `/api/special-steel-physical/grid` | `special_steel_phys_perf` / `_meta`, `report_text` |
| `cost-trend` | Cost of Production — HM/CS/SS/COKE/SINTER × Variable/Fixed × plant; Annual + Monthly(+till-month) tabs | `/api/cost-trend/annual`, `/api/cost-trend/monthly` | `cost_trend_annual`, `cost_trend_monthly` |
| `cost-trend-extract` | Extract cost trend from an "ELHM CS SS" workbook (preview + confirm) | `/api/cost-trend-extract/{preview,confirm}` | `cost_trend_monthly` |
| `commentary-market-upload` | Extract the monthly CMO / BigMint deck PDF (preview + insert): "Key Performance Parameters" month + April-to-month bullets, and every month of the "Movement of Key Prices-International" chart. The deck's macro-indicators table is an image: its newest month column is OCR'd (Tesseract) into an editable review grid | `/api/market-commentary-upload/{preview,insert}` (`api_market_commentary_upload.py` → `excel_extractors/pdf_extractor_market_commentary.py`) | `steel_sales_highlights`, `market_price_trend_monthly`, `macro_indicators_monthly` |
| `sail-mines` | SAIL Mines monthly actual + plan per section/item (Coal, Washery, Flux, …) | `/api/sail-mines/monthly` | `sail_mines_monthly` |
| `mines-production-despatch` | Mine-level fresh production (Lump/Fines) + despatch (Rail/Road × end-use) + booked qty | `/api/mines-production-despatch/monthly`, `/api/mines-master` | `mine_production_monthly`, `mine_despatch_actual_monthly`, `mine_despatch_plan_monthly`, `mine_booked_qty_*` |
| `steel-sector-performance` | Extract the PIB steel-sector-performance PDF (preview + confirm) | `/api/steel-sector-performance/{preview,confirm}` | `steel_sector_performance` |
| `capital-repair` | Annual capital-repair plan rows per plant/FY; `actual` progress; unit classification | `/api/capital-repair`, `/api/capital-repair-entry`, `/api/plant-units` | `capital_repair` |
| `breakdown` | Ad-hoc unplanned-downtime events (plant/unit/start/end/cause), full CRUD; optional link to the capital repair an entry really is | `/api/breakdown`, `/api/breakdown/{id}`, `/api/breakdown/cr-candidates`, `/api/plant-units` | `breakdown` |
| `bf-benchmark` | Non-SAIL BF registry + per-FY figures + SAIL working-volume meta; compare | `/api/bf-benchmark/{external-bfs,external-bfs/{id},params,sail-meta,compare}` | `bf_benchmark_external_bf`, `bf_benchmark_external_data`, `bf_benchmark_sail_meta` |
| `key-highlights` | Major Achievements / Shortfalls / Focus Areas narrative for the month | `/api/key-highlights`, `/api/key-highlights/save` | `report_text` |
| `techno-summary` | Read-only techno performance summary dashboard | `/api/techno-summary` | (reads `techno_upload` / `techno_value`) |

### Not under `data-entry/` but same family

| Route | Purpose | Endpoint | Table |
|---|---|---|---|
| `/upload` (`frontend/src/app/upload/page.js`) | The primary production Excel/PDF ingestion: Actuals / Preview & Insert / ABP Plan tabs | `/api/upload-excel`, `/api/extract-preview` → `/api/confirm-extraction`, `/api/upload-excel-plan` | `production_monthly` (actual + ABP), `techno_upload` / `techno_value`, `special_steel_order` |
| `/reports/external?tab=do-letter` | Also lets the user enter Annexure remarks | `/api/do-letter/remarks` | `report_text` |
| `/report` (page 3 inline edit) | Production narrative + highlights text | `/api/page3-narrative` | `report_text` |
| `/report` (any cell) | Inline override of a computed value | `/api/data` (POST) | `page_config` |

### 9.4 Adding a new data-entry page
1. `scripts/v2/schema_v2.sql` + `scripts/v2/migrate_*.sql`, and `get_*`/`save_*` functions in `backend/repo/<module>.py` (§5.3).
2. `backend/api_<x>.py`: an `APIRouter`; register it in `main.py`
   (`app.include_router(...)`).
3. `backend/constants.py:PAGE_MODULES`: add each write route under a module key
   (existing or new) so editor gating works.
4. `frontend/src/app/data-entry/<x>/page.js`: copy the closest existing page
   (they share the load/edit/`countChanges`/save shape); wrap in `RequireEditor`.
5. `frontend/src/components/GlobalNavbar.js`: add the nav link. Optionally add a
   card to `frontend/src/app/data-entry/page.js` (the hub — it currently lists
   only a curated subset).
6. Consume the new table in the relevant `page_<x>.py` generator (§5.1).

