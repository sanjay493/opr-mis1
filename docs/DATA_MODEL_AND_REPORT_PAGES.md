# SAIL MIS Portal — Data Model & Report Pages (Developer Reference)

Practical map of **every DB table**, **where its data comes from**, **which report
pages consume it**, and **which source files** you edit to change a page's UI or
to map a new item into it.

- Backend: FastAPI, `backend/`. DB access is centralised in `backend/db.py`.
- Frontend: Next.js 16 (Turbopack), `frontend/`.
- DB engine: MySQL in production (`DB_ENGINE=mysql`), SQLite file otherwise.
  Schema is created/migrated in `db.py:init_db()` (the DDL there is the source of
  truth; the `## Database Tables` section of the root `README.md` is **stale**).
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
      ↘ db.py  upsert_* / merge_upsert_*                     ↙                        ↘
Manual data-entry pages                          Frontend preview                 PDF
  frontend/src/app/data-entry/<x>/page.js        frontend/src/components/         backend/pdf.py
  → /api/<x>  (backend api_*.py or main.py)      PageRenderer.js → *Template.js   → Jinja: page_templates/*.html
      ↘ db.py  save_* / upsert_*                 (Chromium via Playwright)        (Chromium via Playwright)
                         ↘  DB tables  ↙
```

Key rule: **the frontend `*Template.js` component and the backend `page_templates/*.html`
Jinja partial render the *same* `pageData` dict** produced by one `generate_*()`
function. If you add a field, add it in the generator and in *both* renderers.

### Editable overrides
Any cell edited on `/report` and saved is persisted per page as JSON in
`page_configs` (`/api/data` POST). On the next generation the stored JSON is
merged over the freshly computed page. So "the number is wrong on the report but
right in the DB" often means a stale `page_configs` row — clear it for that
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
renderers.

| Page(s) | Title | `type` | Backend generator | PDF template | Preview component | Primary tables |
|---|---|---|---|---|---|---|
| 1 | Cover | `cover` | `page_cover.py:generate_cover` | `cover.html` | `CoverTemplate.js` | — (month/date only) |
| 2 | Index | `index` | `main.py:_index_rows` | `index.html` | `PageRenderer.js:IndexTemplate` | — (static + `page_configs` edits) |
| *2.1–2.3* | Indian Steel Sector Performance | `steel_sector_performance` | `page_steel_sector_performance.py` | `steel_sector_performance.html` | `SteelSectorPerformanceTemplate.js` | `steel_sector_performance_table` |
| *1 (2.5)* | MIS at a Glance | `at_a_glance` | `page_at_a_glance.py:generate_at_a_glance` | `at_a_glance.html` | `AtAGlanceTemplate.js` | `production_table`, `production_plan_table`, `techno_data`, `item_capacity_table` |
| 3 | Production Summary (SAIL) | `summary` | `page3_highlights.py:generate_page3_highlights` + `main.py:compute_item_row` + `_safe_te_table` (`page_techno.generate_summary_te_table`) | `summary.html` | `SummaryTemplate.js` | `production_table`, `production_plan_table`, `techno_data`, `page3_narrative` |
| *3.2* | Best Ever Highlights | `best_ever_highlights` | `page_best_ever.py:generate_best_ever_highlights` | `best_ever_highlights.html` | `BestEverHighlightsTemplate.js` | `production_table` (full history) |
| *3.3* | Best Calendar Month | `best_calendar_month` | `page_best_calendar_month.py` | `best_calendar_month.html` | `BestCalendarMonthTemplate.js` | `production_table` |
| *3.5* | **Inter Plant Performance Comparison** ("Key Parameters") | `key_parameters` | `page_key_parameters.py:generate_key_parameters` | `key_parameters.html` | `KeyParametersTemplate.js` | `techno_data` (BF/Coke/General incl. `rltifr`), `production_table`, `cost_trend_monthly` (HM/CS/SS + `COKE`/`SINTER`), `hardcoded_config.json` (`ss_in_finished`) |
| *3.6* | SAIL Large BFs — Performance Snapshot | `bf_large_annexure` | `page_bf_large_annexure.py` | `bf_large_annexure.html` | `BfLargeAnnexureTemplate.js` | `techno_data` (BF-8/BF-5 units), `bf_benchmark_sail_meta`, `production_plan_table` |
| *3.61–3.63* | Cost Trend (HM / CS / SS) | `cost_trend` | `page_cost_trend.py:generate_cost_trend` | `cost_trend.html` (`cost_trend_macro.html`) | `CostTrendTemplate.js` | `cost_trend_annual`, `cost_trend_monthly` |
| 4 | Month-Wise Production | `page4_table` | `page4.py:generate_page4_rows` | `page4_table.html` | `MonthWiseProductionTemplate.js` | `production_table`, `production_plan_table`, `item_capacity_table` |
| *4.5* | SAIL Mines Production & Despatch | `sail_mines` | `page_sail_mines.py:generate_sail_mines` | `sail_mines.html` | `SailMinesTemplate.js` | `sail_mines_monthly`, `mines_*` masters + monthly, `hardcoded_config.json` (`sail_mines` — trend charts + iron-ore group table) |
| 5–6 | Plant-Wise Production Performance | `performance_summary_table` | `page5_6.py:generate_page5_rows` / `generate_page6_rows` | `performance_summary_table.html` | `PlantWisePerformanceTemplate.js` | `production_table`, `production_plan_table` |
| 7–12 | 10-Year Month-Wise Production Trends | `trend_yearly` / `trend_combined` | `page7_13.py:generate_trend_page_rows` / `generate_combined_trend_items` | `trend_yearly.html`, `trend.html`, `trend_section.html` | `TrendYearlyTemplate.js`, `TrendTemplate.js` | `production_table` |
| 13 | Concast Production Performance | `concast_performance` | `page17_concast.py:generate_concast_data` | `concast_performance.html` | `ConcastPerformanceTemplate.js` | `production_table` |
| 14 | Production by Process | `prod_by_process` | `page_prod_by_process.py:generate_prod_by_process` | `prod_by_process.html` | `ProductionByProcessTemplate.js` | `production_table` |
| 15–17 | Category-Wise Saleable Steel | `catwise_saleable` | `page_catwise_saleable.py:generate_catwise_saleable` | `catwise_saleable.html` | `CatWiseSaleableTemplate.js` | `production_table` |
| 18 | Segment-Wise Production | `segment_wise` | `page_segment_wise.py:generate_segment_wise` | `segment_wise.html` | `SegmentWiseTemplate.js` | `production_table` |
| 19–23 | Special Steel — BSP/DSP/RSP/BSL/ISP | `special_steel` | `page_special_steel.py:generate_special_steel_plant` | `special_steel.html` | `SpecialSteelTemplate.js` | `special_steel_orders`, `special_steel_abp_table`, `special_steel_grade_clubs` |
| 24 | Special Steel — SAIL Consolidated | `special_steel` | `page_special_steel.py:generate_special_steel_sail` | `special_steel.html` | `SpecialSteelTemplate.js` | same as 19–23 |
| *(after 24)* | Special Steel Trend | `special_steel_trend` | `page_special_steel_trend.py` | `special_steel_trend.html` | (uses `SpecialSteelTemplate.js` family) | `special_steel_orders`, `production_table` |
| *1025 (after 24)* | Special Steel Plants Physical Performance (ASP/SSP/VISP) | `special_steel_physical` | `page_special_steel_physical.py` | `special_steel_physical.html` | `SpecialSteelPhysicalTemplate.js` | `special_steel_phys_perf` / `_meta` / `_note`, `special_steel_ipt_requirement`, `production_table`/`production_plan_table`, `hardcoded_config.json` (`ytd_actual_override`) |
| 25 | Opening Stock | `opening_stock` | `page_opening_stock.py:generate_opening_stock` | `opening_stock.html` | `OpeningStockTemplate.js` | `stock_table` |
| 26 | IPT Status | `ipt_status` | `page_ipt.py:generate_ipt` | `ipt_status.html` | `IptStatusTemplate.js` | `ipt_table` |
| 27 | Major Techno-Economic Parameters | `techno_params` | `page_techno.py:generate_major_techno_from_db` | `techno_params.html` | `TechnoParamsTemplate.js` | `techno_data`, `techno_plan_fy`, `production_table` |
| 28 | Coke & Coal Chemicals, Sinter Plant (Techno) | `techno_params` | `page_techno.py:generate_techno_from_db` | `techno_params.html` | `TechnoParamsTemplate.js` | `techno_data`, `techno_plan_fy` |
| 29 (+ *29.5*) | Iron Making (Techno) (+ contd.) | `techno_params` | `page_techno.py:generate_techno_from_db` | `techno_params.html` | `TechnoParamsTemplate.js` | `techno_data`, `techno_plan_fy` |
| 30 | BOF Shop (Techno) | `techno_params` | `page_techno.py:generate_techno_from_db` | `techno_params.html` | `TechnoParamsTemplate.js` | `techno_data`, `techno_plan_fy` |
| 31–35 | Mill-Wise Techno — BSP/DSP/RSP/BSL/ISP | `techno_params` | `page_techno.py:generate_techno_from_db` | `techno_params.html` | `TechnoParamsTemplate.js` | `techno_data`, `techno_plan_fy` (mill norms) |
| *35.4* | EPI (CO₂ / Water / PM) | `epi` | `page_epi.py:generate_epi` | `epi.html` | `EpiTemplate.js` | `techno_data` (General/EPI keys) |
| *35.5* | Coal Consumption | `coal_consumption` | `page_coal_consumption.py:generate_coal_consumption` | `coal_consumption.html` | `CoalConsumptionTemplate.js` | `techno_data` (coal keys), `production_table` |
| *35.6* | Coking Coal Receipts & Stock (SAIL) | `coal_receipt_stock` | `page_coal_receipts_stock.py:generate_coal_receipts_sail` | `coal_receipt_stock.html` | `CoalReceiptStockTemplate.js` | `techno_data` (coal receipt/stock keys) |
| *35.7* | Power Data | `power_data` | `page_power_data.py:generate_power_data` | `power_data.html` | `PowerDataTemplate.js` | `power_data_table` |
| *36–40* | Capital Repair (per plant) | `capital_repair` | `page_capital_repair.py:generate_capital_repair` | `capital_repair.html` | `CapitalRepairTemplate.js` | `capital_repair_table` |
| *(built, not wired)* | Key Highlights & Variances | `key_highlights` | `page_key_highlights.py:generate_key_highlights` | `key_highlights.html` | `KeyHighlightsTemplate.js` | `key_highlights_narrative`, `production_table`, `techno_data` |

### Standalone report routes (`frontend/src/app/reports/<x>/page.js`, own endpoints — not part of `/api/data`)

| Route | Backend | Tables |
|---|---|---|
| `reports/one-page-report` | `page_one_page_report.py` | `sail_sales_table`, `sail_sales_note_table`, `sail_stock_snapshot_table`, `production_table` |
| `reports/do-letter` | `page_do_letter.py` (`/api/do-letter…`) | `production_table`, `production_plan_table`, `do_letter_remark_table` |
| `reports/jpc-report` | `page_jpc_report.py` (`/api/jpc-report` → xlsx) | `production_table` |
| `reports/finished-steel` | `page_finished_steel_report.py` | `production_table` |
| `reports/records-matrix` | `page_records.py` (`/api/records`) | `production_table` |
| `reports/pmix-fy` | `page_pmix_fy_report.py` | `production_table` |
| `reports/production-fy`, `reports/production-query`, `reports/major-production` | `page_production_fy_export.py`, `page_production_query_export.py` | `production_table`, `production_plan_table` |
| `reports/special-steel-fy` | `page_special_steel_fy_export.py` | `special_steel_orders` |
| `reports/techno-custom`, `reports/techno-verification`, `reports/techno-monthly`, `reports/techno-dashboard` | `page_techno_custom_export.py`, `page_techno_verification_export.py`, `page_techno.py` | `techno_data`, `techno_plan_fy` |
| `reports/bf-benchmark` | `api_bf_benchmark.py`, `page_bf_benchmark_export.py` | `bf_benchmark_external_bf`, `bf_benchmark_external_data`, `bf_benchmark_sail_meta`, `techno_data` |
| `reports/production-loss-analysis` | `production_loss_analysis.py`, `api_production_loss.py` | `production_table`, `production_plan_table`, `capital_repair_table`, `breakdown_table` |
| `reports/ipt-fy` | `page_ipt.py` | `ipt_table` |
| `reports/new-facilities` | (frontend-only / static) | — |

---

## 4. Database tables reference

For each table: what it holds, **populated by** (extractor / data-entry page / API
/ script), and **read by** (report pages / generators). db.py accessor functions
are named `get_*` (read) and `save_* / upsert_* / merge_upsert_*` (write).

### 4.1 Production & plan

#### `production_table`  — monthly ACTUAL production
`(report_month, plant_name, item_name)` → `month_actual` REAL. `'000 T`
(a few items are rates/nos — see `page4.py`).
- **Populated by:**
  - `/upload` → *Actuals* mode → `POST /api/upload-excel` → per-plant extractors:
    `excel_extractor_bsp.py` (`.xls` PPC MIS), `excel_extractor_bsl.py` (DPR),
    `excel_extractor_rsp.py`, `excel_extractor_isp.py`,
    `excel_extractors/pdf_extractor_dsp.py` / `pdf_extractor_dsp_pcontrep.py` (MCR / OMI),
    `pdf_extractor_asp.py`, `pdf_extractor_ssp.py`, `pdf_extractor_visl.py`,
    `pdf_extractor_bsp_flash.py`.
  - `/upload` → *Preview & Insert* → `POST /api/extract-preview` → `POST /api/confirm-extraction`.
  - `frontend/src/app/data-entry/production/page.js` → `POST /api/production-entry`.
  - `frontend/src/app/data-entry/legacy-sms-crude/page.js`, `.../conversion/page.js`.
  - Backfill scripts: `scripts/backfill_asp_ingot.py`, `backfill_ssp_production.py`,
    `backfill_rspbsl_ingot.py`, `backfill_asp_legacy_fl_excel.py`,
    `backfill_asp_fy2425_from_fy2526_fl.py`, `backfill_special_steel_2022_23.py`.
  - Item-name normalisation: `pdf_item_alias` table + `db.get_item_alias`.
- **Read by:** almost every `page_*.py` (see §3). Central helper: `main.py:compute_item_row`,
  `production_utils.py`, `report_utils.py`.

#### `production_plan_table` — ABP monthly PLAN (same shape as above)
- **Populated by:** `/upload` → *ABP Plan* → `POST /api/upload-excel-plan` →
  `excel_extractor_{bsp,bsl,rsp,isp,dsp}_plan.py`, `excel_extractor_asp_ssp_visl_plan.py`
  (one file loads all 12 months); `frontend/src/app/data-entry/targets/page.js`.
- **Read by:** same pages as `production_table` (ABP / APP / %FF columns).

### 4.2 Power

#### `power_data_table`
`(report_month, plant_name, item_name)` → `value`. Non-tonnage power-OIS items
(`plan_own`, `actual_total`, `wheeling_px`, …).
- **Populated by:** `excel_extractor_power_omi.py` via `api_power_omi.py`
  (`POST /api/power-omi/insert`); data-entry `co2-water-pm` / power OMI upload.
- **Read by:** `page_power_data.py` (Power Data page, id 35.7).

### 4.3 Stock & SAIL sales (one-page report)

| Table | Holds | Populated by | Read by |
|---|---|---|---|
| `stock_table` | `(stock_month, plant_name, item_type, stock_type)` → `stock` (tonnes) | `data-entry/opening-stock`; some plant extractors during Preview→Insert | `page_opening_stock.py` (page 25) |
| `sail_sales_table` | `(report_month, item_name)` → `data_json` (10 figures verbatim) | `sail_sales_stock_extractor.py` (upload) | `page_one_page_report.py` (Table A) |
| `sail_sales_note_table` | `(report_month)` → `note` (asterisk remark) | `sail_sales_stock_extractor.py` | `page_one_page_report.py` |
| `sail_stock_snapshot_table` | `(snapshot_date, item_name)` → `value` (`'000 T`) | `sail_sales_stock_extractor.py` (one upload backfills years) | `page_one_page_report.py` (Table D) |

### 4.4 Techno-economic

#### `techno_data`  — the big one
`(plant, report_month, unit)` → `techno_json` = `{"month": {key: val}, "till_month": {key: val}}`.
`unit` ∈ `BF_Shop, BF-1..BF-8, SMS, SMS-1..3, SMS-I/II, COB, Coke Ovens, SP, SP-1..3,
Sinter, <mill units>, General`. `till_month` = April→report_month cumulative,
**entered/stored directly**, not auto-summed.
- **Populated by:**
  - Preview→Insert techno extractors: `excel_extractor_bsp.py` + `excel_extractor_bsp_oisco.py`,
    `excel_extractor_bsl.py`, `excel_extractor_rsp.py`, `excel_extractor_isp.py`,
    `pdf_extractor_dsp.py`; `techno_project/*` (bsp_oisco, coal_omi, isp_technopara,
    rsp_technopara).
  - Techno APIs: `api_bsp_techno.py`, `api_dsp_techno.py`, `api_isp_techno.py`,
    `api_rsp_techno.py`, `api_mcr_techno.py`, `api_coal_co2_techno.py`,
    `api_coal_omi_techno.py`, `api_unified_techno.py`.
  - Manual: `data-entry/techno-manual/page.js`, `data-entry/techno-correction/page.js`,
    `data-entry/key-parameters-manual/page.js`, `data-entry/co2-water-pm-manual/page.js`
    → `POST /api/techno/manual/save` (`api_techno_manual.py`) → `db.merge_upsert_techno_data`.
  - SAIL BF aggregate computed from the 5 plants: `POST /api/techno/manual/sail/calculate`.
  - Cumulative rules for the manual form's auto-YTD: `techno_cumulative.py:CUMULATIVE_RULES`.
  - Backfill: `scripts/backfill_rltifr_202607.py`.
- **Read by:** `page_techno.py` (pages 27–35), `page_key_parameters.py` (3.5),
  `page_bf_large_annexure.py` (3.6), `page_epi.py`, `page_coal_consumption.py`,
  `page_coal_receipts_stock.py`, `page_at_a_glance.py`, `api_bf_benchmark.py`,
  `page3_highlights.py` (summary TE table).
- **Param key ↔ label ↔ shop-area:** `frontend/src/lib/technoParamRegistry.js`
  (`PARAM_TEMPLATES`, `_LABEL_MAP`); backend `plant_registry.py` (`PLANT_UNITS`,
  `PARAM_TYPES`), `techno_registry.py`.

#### `techno_plan_fy`  — techno targets / plan (all levels) by FY
`(plant_name, unit, fy)` → `techno_json` + `is_user_supplied` + `calculated_json` + `calculation_method`.
- **Populated by:** `data-entry/techno/page.js` (plan), `data-entry/annual-target/page.js`,
  mill-norm entry (reuses the techno-page-targets table UI) → `/api/techno-plan`,
  `/api/sail-techno-plan`, `/api/techno-plant-plan`, `/api/techno-page-targets`,
  `/api/techno-sms-targets`, `/api/techno-plant-targets`, `/api/techno-sail-targets`
  (all in `main.py`).
- **Read by:** `page_techno.py` (Norm / Target / ABP columns on pages 27–35).

#### `pdf_item_alias`
`(plant_name, pdf_label)` → `item_name`, `convert_t`. Learned when a user renames a
row on the extraction preview. Read by every extractor's label→item mapping.

### 4.5 Special steel

| Table | Holds | Populated by | Read by |
|---|---|---|---|
| `special_steel_orders` | `(report_month, plant_name, product, quality_grade, section)` → `order_qty`, `actual_despatch`, `sort_order` | Preview→Insert (`BSP_Spstl-*.xlsx`, DSP OMI PDF, `image_extractor_isp_special_steel.py`, `pdf_extractor_ssp/visl`); `data-entry/special-steel/page.js` → `/api/special-steel-manual/save`; `scripts/backfill_special_steel_2022_23.py` | `page_special_steel.py` (19–24), `page_special_steel_trend.py`, `page_special_steel_fy_export.py` |
| `special_steel_abp_table` | `(report_month, plant_name)` → `abp_qty` (12 months at once) | `data-entry/special-steel-abp/page.js` → `/api/special-steel-abp` | `page_special_steel.py` (ABP column) |
| `special_steel_grade_clubs` | `(plant_name, product, quality_grade)` → `club_label` | `data-entry/special-steel-grade-clubs/page.js` → `/api/special-steel/grade-clubs` (`api_special_steel_clubs.py`) | `page_special_steel.py:_resolve_clubs` |
| `special_steel_phys_perf` | `(financial_year, plant, series, metric)` → `value_kt` (history) | `data-entry/special-steel-physical/page.js`; `scripts/backfill_special_steel_physical.py` | `page_special_steel_physical.py` |
| `special_steel_phys_meta` | `(plant, series)` → `capacity_kt`, `best_actual_kt`, `best_year`, `remark`, `sort_order` | same data-entry page | `page_special_steel_physical.py` |
| `special_steel_phys_note` | `(financial_year, sort_order)` → `note_text` | same data-entry page | `page_special_steel_physical.py` |
| `special_steel_ipt_requirement` | `(financial_year, item, from_plant, to_plant)` → `plan_kt` | `data-entry/special-steel-ipt/page.js` | `page_special_steel_physical.py` (IPT block) |

### 4.6 Cost trend

| Table | Holds | Populated by | Read by |
|---|---|---|---|
| `cost_trend_annual` | `(fy, product, cost_type, plant)` → `value`. `product` ∈ `HM,CS,SS,COKE,SINTER`; `cost_type` ∈ `TOTAL,VARIABLE,FIXED`; `plant` ∈ BSP/DSP/RSP/BSL/ISP/SAIL | `data-entry/cost-trend/page.js` (Annual tab); `scripts/backfill_cost_trend*.py` | `page_cost_trend.py` (3.61–3.63, HM/CS/SS only) |
| `cost_trend_monthly` | as above + `month_value`, `till_month_value` | `data-entry/cost-trend/page.js` (Monthly tab); `data-entry/cost-trend-extract/page.js` → `excel_extractor_cost_trend.py` (`api_cost_trend_extract.py`); `scripts/backfill_cost_trend_202608.py`, `scripts/backfill_cop_coke_sinter_202607.py` | `page_cost_trend.py` (HM/CS/SS); `page_key_parameters.py` (CoP rows: HM/CS/SS + `COKE`/`SINTER` via `_fetch_cop`) |

`COKE` / `SINTER` products have **no** `page_cost_trend.py` report page — they exist
only to feed the Inter Plant Performance Comparison page. `main.py:COST_TREND_PRODUCTS`
and `frontend/.../cost-trend/page.js:PRODUCTS` list all five.

### 4.7 SAIL Mines

| Table | Holds | Populated by | Read by |
|---|---|---|---|
| `sail_mines_monthly` | `(report_month, section, item)` → `month_actual`, `month_plan`. Sections/items registry in `page_sail_mines.py:SAIL_MINES_SECTIONS` (Coal, Washery, Coal Despatch, Flux). Derived rows (Total, Yield) computed at read time. | `data-entry/sail-mines/page.js` → `/api/sail-mines/monthly` | `page_sail_mines.py` |
| `mine_groups_master`, `mines_master`, `mine_materials_master`, `mine_end_uses_master` | Reference data (11 mines under JGoM/OGoM/CGoM, materials, end-uses) | Seeded in `db.init_db()`; editable as data | `page_sail_mines.py` (labels/grouping) |
| `mines_production_monthly` | `(report_month, mine_code, material_code)` → `qty_actual`, `qty_plan` (Lump/Fines) | `data-entry/mines-production-despatch/page.js`; `scripts/backfill_iron_ore_mines_production.py` | `page_sail_mines.py` (mine-level → group rollup) |
| `mines_despatch_actual_monthly` | `(report_month, mine_code, material_code, transport_mode, end_use_code)` → `qty_actual` | same data-entry page | `page_sail_mines.py` |
| `mines_despatch_plan_monthly` | `(report_month, mine_code, material_code, end_use_code)` → `qty_plan` (no transport split) | same; `scripts/backfill_iron_ore_mines_despatch_plan.py` | `page_sail_mines.py` |
| `mines_booked_qty_actual_monthly` / `mines_booked_qty_plan_monthly` | mine-level "Booked Quantity" (sales to 3rd party), SALES end-use only | `data-entry/mines-production-despatch/page.js` | `page_sail_mines.py` |

> **Current caveat:** the Iron Ore Production/Despatch and Sales group tables on the
> SAIL Mines page are **hard-coded** in `hardcoded_config.json` (`sail_mines →
> iron_ore_group_kt`) because mine-level despatch/sales actuals were never entered.
> The trend mini-charts + despatch-mix donuts are likewise hard-coded there. To go
> live, populate the `mines_*` tables and restore the rollup calls in
> `generate_sail_mines()`.

### 4.8 Steel sector, DO letter

| Table | Holds | Populated by | Read by |
|---|---|---|---|
| `steel_sector_performance_table` | `(report_month)` → `data_json` (entire PIB release: tables 1a…5 + narrative 6/7/8) | `data-entry/steel-sector-performance/page.js` → `pdf_extractor_steel_sector_performance.py` | `page_steel_sector_performance.py` (2.1–2.3) |
| `do_letter_remark_table` | `(report_month, item_name, plant_name)` → `remark`. `item_name` ∈ `Crude Steel`, `Finished Steel` | `POST /api/do-letter/remarks` (from `reports/do-letter` page) | `page_do_letter.py` |

### 4.9 Capital repair & breakdown

| Table | Holds | Populated by | Read by |
|---|---|---|---|
| `capital_repair_table` | annual CR plan rows per plant/FY (`shop`, `equipment`, `activity`, `schedule_days`, `period`, `actual` free-text) + structured cols (`unit_type`, `unit_name`, `actual_start/end`, `planned_days`) | `data-entry/capital-repair/page.js` → `/api/capital-repair-entry`; plan pre-seeded from `Report_format/CR.pdf`; `actual` display string built by `main.py:format_cr_actual` | `page_capital_repair.py` (CR pages 36–40); `production_loss_analysis.py` |
| `breakdown_table` | ad-hoc unplanned-downtime events (`plant`, `unit_type`, `unit_name`, `start_ts`, `end_ts`, `is_ongoing`, `cause`, `hours_lost_override`) | `data-entry/breakdown/page.js` → `/api/breakdown` (`api_breakdown.py`, full CRUD) | `production_loss_analysis.py` (explains HM/CS/FS shortfall vs ABP) |

### 4.10 Annual capacity

#### `item_capacity_table`
`(plant_name, item_name, effective_month)` → `annual_capacity` (`'000 T/yr`), with
mid-FY change history (`db.get_effective_capacity` = latest row ≤ month).
- **Populated by:** `data-entry/annual-capacity/page.js` → `/api/capacity` (`api_capacity.py`).
- **Read by:** `page4.py` (capacity %), `page_at_a_glance.py`, capacity-utilisation calcs.

### 4.11 IPT

#### `ipt_table`
`(report_month, item, from_plant, to_plant)` → `plan`, `actual`, `unit` (`Rake`/`T`),
`plan_tonnage`, `actual_tonnage`, `sort_order`.
- **Populated by:** `data-entry/ipt/page.js` → `/api/ipt-entry`, `/api/ipt-entries/bulk`, `/api/ipt-delete`.
- **Read by:** `page_ipt.py` (page 26), `reports/ipt-fy`.

### 4.12 Narrative

| Table | Holds | Populated by | Read by |
|---|---|---|---|
| `page3_narrative` | `(report_month)` → `production_narrative`, `highlights` | `/api/page3-narrative` (inline edit on `/report` page 3) | `page3_highlights.py` / page 3 assembly |
| `key_highlights_narrative` | `(report_month)` → `achievements`, `shortfalls`, `focus_areas` (JSON) | `data-entry/key-highlights/page.js` (`api_key_highlights.py`) | `page_key_highlights.py` (built, not currently in the report) |

### 4.13 BF benchmarking

| Table | Holds | Populated by | Read by |
|---|---|---|---|
| `bf_benchmark_sail_meta` | `(plant, unit)` → `working_volume_m3` (SAIL's 3 large BFs) | `data-entry/bf-benchmark/page.js` → `PATCH /api/bf-benchmark/sail-meta` | `api_bf_benchmark.py`, `page_bf_large_annexure.py` |
| `bf_benchmark_external_bf` | non-SAIL BF registry (`name`, `company`, `location`, `working_volume_m3`, `active`) | `data-entry/bf-benchmark/page.js` → `POST/PATCH /api/bf-benchmark/external-bfs` | `api_bf_benchmark.py`, `reports/bf-benchmark` |
| `bf_benchmark_external_data` | `(external_bf_id, report_month)` → `param_json` (`report_month` holds an **FY label** here, e.g. `2025-26`) | same page → `POST /api/bf-benchmark/external-bfs/{id}/entry` | `api_bf_benchmark.py` |

Benchmark param registry: `backend/bf_benchmark_registry.py` (`BF_BENCHMARK_PARAMS`,
`SAIL_BFS`).

### 4.14 System / operational (not on any report page)

| Table | Holds | Populated by |
|---|---|---|
| `page_configs` | `(report_month, page_number)` → `page_data` JSON — inline-edit overrides + cached page output | `POST /api/data` when a user saves edits on `/report` |
| `users` | accounts, `role` (`NULL`/`editor`/`admin`), `allowed_pages` (module gate), `can_delete` | registration/login, `/admin/users` (`api_admin.py`) |
| `allowed_emails` | registration whitelist | `/admin/users` |
| `otp_codes` | one-time codes for register / password reset | `api_auth.py` |
| `activity_log` | every gated insert/update/delete (who/when/what) | written by `main.py` middleware + gated endpoints (`activity_context.py`) |
| `extraction_log` | upload audit (plant, month, file, sheet, item count) | every extractor upload (`db.log_extraction`) |
| `todo_jobs` | To-Do items (`subject`, `due_date`, `priority`, `status`, `remark`) | `/api/todo/*` (`api_todo.py`) |
| `daily_work_log` | free-text daily work record | `/api/worklog/*` (`api_worklog.py`) |

Write-route → module gate mapping (which `role='editor'` users may hit which
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
   merges `page_configs` overrides.
5. Regenerate for a test month and diff (see §6).

### 5.2 Map a new item to a DB column that already exists
- New **production item**: add its source label to `pdf_item_alias` (or the
  extractor's label map in `excel_extractors/<plant>*.py`), then it flows into
  `production_table` and any page that lists that item.
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
1. Add columns/table in `db.py:init_db()` (idempotent `CREATE TABLE IF NOT EXISTS`
   / `ALTER TABLE ADD COLUMN` guarded by `PRAGMA table_info`). Add the matching
   DDL to `backend/scripts/mysql_schema.sql` and a `scripts/migrate_*.sql` for prod.
2. Add `db.get_<x>()` / `db.save_<x>()` accessors.
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
- DB writes from scripts hit the **live MySQL prod DB** when `DB_ENGINE=mysql` —
  always dry-run first (`scripts/backfill_*.py` default to dry-run; pass `--apply`).

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
| DB schema / accessors | `backend/db.py` (+ `scripts/mysql_schema.sql`, `scripts/migrate_*.sql`) |
| Endpoint routing / gating | `backend/main.py`, `backend/constants.py:PAGE_MODULES` |
| Techno param labels/areas | `frontend/src/lib/technoParamRegistry.js`, `backend/plant_registry.py` |
| Report colours / fonts / margins | `backend/colors_config.json`, `backend/layout_config.json` |
| Figures with no DB source | `backend/hardcoded_config.json` |
| PDF rendering / pagination | `backend/pdf.py` |
```
