-- =============================================================================
-- schema_v2.sql -- the v2 (normalised) schema of the SAIL MIS database.
-- Single DDL source of truth for mis_reports_v2. Apply to an EMPTY schema,
-- then run seed_cal_month.sql. Task 6 (tools/migrate_v1_to_v2.py) loads the
-- v1 data into it, Task 7 points backend/repo/ at it.
--
--   mysql --defaults-extra-file=... mis_reports_v2 < backend/scripts/v2/schema_v2.sql
--   mysql --defaults-extra-file=... mis_reports_v2 < backend/scripts/v2/seed_cal_month.sql
--
-- Tests: backend/tests/test_schema_v2.py
--
-- -----------------------------------------------------------------------------
-- CONVENTIONS
-- * InnoDB, utf8mb4 / utf8mb4_0900_ai_ci, snake_case singular-noun table names.
-- * Every table has a PK, and every plant / item / unit / month reference is a
--   declared FK (ON DELETE RESTRICT unless stated). Indexes that exist only to
--   back an FK are created implicitly by InnoDB and are not listed here.
-- * Period keys stay strings: report_month CHAR(7) 'YYYY-MM' (FK cal_month on
--   the fact tables), fy CHAR(7) 'YYYY-YY' (no FK: there is no FY table and
--   cal_month.fy is not unique). extraction_log keeps a free report_month.
-- * Column names are uniform: plant_code, fy, created_at / updated_at,
--   created_by / updated_by. v1 column renames are noted on each table.
-- * Booleans are TINYINT(1). Dates are DATE. Instants are DATETIME.
-- * Each query index carries the repository query it serves, as
--   repo module.function, from the Task 3 repository SQL (backend/repo/*.py).
--   The (item, month) and (month, plant) production reads that Task 7 needs
--   are both served (PRIMARY and idx_production_item_month).
--
-- -----------------------------------------------------------------------------
-- TIMESTAMPS
-- This file defines column TYPES only. A DATETIME holds what the app writes,
-- as wall-clock time in the MySQL session time zone, which is IST (the app
-- uses NOW()). The v1 timestamps are VARCHARs in mixed formats (UTC ISO with
-- '+00:00', local ISO with microseconds, 'YYYY-MM-DD HH:MM:SS', 'YYYY-MM-DDTHH:MM:SS').
-- Converting them and rendering each column back in its original string
-- format is the repo/v2codec.py of Task 6 (ruling R5), not this file.
-- v1 VARCHAR timestamps become DATETIME(6), because most carry microseconds.
-- v1 columns that were already DATETIME stay DATETIME.
--
-- -----------------------------------------------------------------------------
-- MASTER STRINGS: EVIDENCE AND COLLATION DECISION (Review Focus #4)
-- Measured read-only on mis_reports_baseline (2026-10-21), across every v1
-- column that holds the value, compared as utf8mb4_0900_bin and grouped under
-- utf8mb4_0900_ai_ci (NO PAD):
--
--   plant  12 strings in the FK-ed plant columns: ASP BSL BSP CFP DSP ISP RSP
--          SAIL SSP SSPs VISL VISP (14 with the extraction_log-only tags
--          BSP_BF and TESTPLANT). Longest FK-ed value 4 chars ('TESTPLANT'
--          is 9). 0 collisions under ai_ci. All ASCII, no edge spaces.
--          --> plant_code VARCHAR(8), table collation (ai_ci), so plant
--              lookups keep v1 case-insensitive matching.
--   item   166 strings over production_table / production_plan_table /
--          mou_plan_table / item_capacity_table / pdf_item_alias /
--          do_letter_remark_table item_name. Longest 30 chars
--          ('Finished Carbon Steel Despatch'). All ASCII, no edge spaces.
--          2 collision groups under ai_ci:
--            'CC BILLET' / 'CC Billet'         (both in production_table)
--            'BILLET Caster' / 'Billet Caster' (pdf_item_alias / production)
--          0 collisions under utf8mb4_0900_bin.
--          --> item.item_name VARCHAR(64) COLLATE utf8mb4_0900_bin UNIQUE, so
--              each case variant is its own item and keeps its exact text.
--              HOW LOOKUPS MATCH (Task 7): v1 compared item_name under ai_ci,
--              so a v1 WHERE item_name = X matched every case variant of X,
--              GROUP BY item_name merged them, and an upsert of 'CC Billet'
--              onto a (month, plant) that held 'CC BILLET' updated that row.
--              The repository resolves names with
--              item_name COLLATE utf8mb4_0900_ai_ci = X (all matching
--              item_ids, item has ~170 rows) or with report_context fold(),
--              which reproduces ai_ci NO PAD, and groups on the folded name.
--              Writes reuse the item_id of an existing case variant in the
--              same (month, plant) before creating a new item.
--   unit   196 distinct (plant, unit) pairs over techno_data.unit,
--          techno_plan_fy.unit, breakdown_table.unit_name,
--          capital_repair_table.unit_name, bf_benchmark_sail_meta.unit,
--          major_unit_daily_record.unit_label. Longest 30 chars
--          ('Billet Casters (M/c-1 & M/c-2)'). 0 collisions under ai_ci
--          within a plant.
--          --> plant_unit.unit_code VARCHAR(64), table collation (ai_ci).
--              Widened from 32: major_unit_daily_record.unit_label is a
--              user-editable VARCHAR(64) in v1.
--   techno param keys: longest 37 chars, 0 case collisions within one
--          (blob, period). JSON object keys are case-sensitive, so
--          techno_value.param_key is utf8mb4_0900_bin.
--
-- -----------------------------------------------------------------------------
-- V1 -> V2 TABLE MAP (consumed by Task 6. Checked by
-- test_every_v1_table_is_mapped: every table of tests/fixtures/schema_v1.sql
-- plus the data_version of Task 4 appears exactly once.)
-- Format:  -- <v1 table> -> <v2 table>[, <v2 table>...] | <notes>
-- The plant master is seeded from every plant column listed in the
-- evidence above (except extraction_log), item and plant_unit from the
-- columns listed there. cal_month is generated (seed_cal_month.sql).
--
-- V1-TABLE-MAP BEGIN
-- activity_log                     -> activity_log | timestamp -> created_at
-- admin_notifications              -> admin_notification
-- allowed_emails                   -> allowed_email | added_by/added_at -> created_by/created_at
-- bf_benchmark_external_bf         -> bf_benchmark_external_bf
-- bf_benchmark_external_data       -> bf_benchmark_external_data | report_month (holds an FY) -> fy
-- bf_benchmark_sail_meta           -> bf_benchmark_sail_meta, plant_unit | unit -> unit_id
-- board_note_manual_text           -> report_text | scope board_note, period '<fy>:Q<n>', block_key = field
-- breakdown_table                  -> breakdown, plant_unit | unit_name -> unit_id, unit_type kept
-- capital_repair_table             -> capital_repair, plant_unit | unit_name -> unit_id, unit_type kept
-- cost_trend_annual                -> cost_trend_annual
-- cost_trend_monthly               -> cost_trend_monthly
-- cover_photos                     -> cover_photo | uploaded_by/uploaded_at -> created_by/created_at
-- daily_work_log                   -> daily_work_log
-- data_version                     -> data_version | Task 4 one-row write counter
-- do_letter_remark_table           -> report_text, item | scope do_letter, block_key 'remark'
-- extraction_log                   -> extraction_log | logged_at -> created_at
-- ipt_data_json                    -> DROPPED | dead JSON archive, frozen since 2026-06-26, no reader
-- ipt_table                        -> ipt_monthly
-- item_capacity_table              -> item_capacity, item
-- key_highlights_narrative         -> report_text | scope key_highlights, one block per column
-- macro_indicators_monthly         -> macro_indicator_monthly
-- major_unit_daily_record          -> major_unit_daily_record, plant_unit | unit_label -> unit_id
-- market_price_trend_monthly       -> market_price_monthly
-- mine_end_uses_master             -> mine_end_use
-- mine_groups_master               -> mine_group
-- mine_materials_master            -> mine_material
-- mines_booked_qty_actual_monthly  -> mine_booked_qty_actual_monthly
-- mines_booked_qty_plan_monthly    -> mine_booked_qty_plan_monthly
-- mines_despatch_actual_monthly    -> mine_despatch_actual_monthly
-- mines_despatch_plan_monthly      -> mine_despatch_plan_monthly
-- mines_master                     -> mine
-- mines_production_monthly         -> mine_production_monthly
-- mou_plan_table                   -> production_monthly, item | month_actual -> mou_plan, has_mou = 1
-- otp_codes                        -> otp_code
-- page3_narrative                  -> report_text | scope page3_narrative, one block per column
-- page_configs                     -> page_config
-- page_visits                      -> page_visit | timestamp -> created_at
-- pdf_item_alias                   -> pdf_item_alias, item
-- power_data_table                 -> power_monthly | item_name -> power_item (power-OIS codes, not items)
-- production_data_json             -> DROPPED | dead JSON archive, frozen since 2026-06-26, no reader
-- production_plan_json             -> DROPPED | dead JSON archive, frozen since 2026-06-26, no reader
-- production_plan_table            -> production_monthly, item | month_actual -> abp_plan, has_abp = 1
-- production_table                 -> production_monthly, item | month_actual -> actual, has_actual = 1, SAIL rows kept
-- rail_prod_despatch               -> rail_prod_despatch | financial_year -> fy
-- rail_prod_despatch_note          -> report_text | scope rail_note, period '', block_key 'note', seq = sort_order
-- rake_detention_annual            -> rake_detention_annual | financial_year -> fy
-- rake_detention_master            -> rake_detention_master
-- rake_detention_monthly           -> rake_detention_monthly
-- rake_detention_summary           -> rake_detention_summary
-- ready_reckoner_pages             -> ready_reckoner_page
-- report_cover_settings            -> report_cover_setting
-- sail_mines_monthly               -> sail_mines_monthly
-- sail_sales_note_table            -> report_text | scope sail_sales_note, block_key 'note'
-- sail_sales_table                 -> sail_sales_monthly | JSON archive of source figures, kept
-- sail_stock_snapshot_table        -> sail_stock_snapshot
-- secretary_review_text            -> report_text | scope secretary_review
-- special_steel_abp_table          -> special_steel_abp
-- special_steel_grade_clubs        -> special_steel_grade_club
-- special_steel_ipt_requirement    -> special_steel_ipt_requirement | financial_year -> fy
-- special_steel_json               -> DROPPED | dead JSON archive, frozen since 2026-06-26, no reader
-- special_steel_orders             -> special_steel_order
-- special_steel_phys_meta          -> special_steel_phys_meta
-- special_steel_phys_note          -> report_text | scope ss_phys_note, period = fy, block_key 'note', seq = sort_order
-- special_steel_phys_perf          -> special_steel_phys_perf | financial_year -> fy
-- steel_sales_highlights           -> report_text | scope steel_sales, one block per column
-- steel_sector_performance_table   -> steel_sector_performance | JSON archive of source figures, kept
-- stock_data_json                  -> DROPPED | dead JSON archive, frozen since 2026-06-26, no reader
-- stock_table                      -> stock_monthly | stock_month -> report_month
-- techno_data                      -> techno_upload, techno_value, plant_unit | one upload row per blob, one value row per leaf
-- techno_plan_fy                   -> techno_plan_fy, plant_unit | plant_name -> plant_code, unit -> unit_id
-- todo_jobs                        -> todo_job
-- users                            -> app_user | ruling R6
-- V1-TABLE-MAP END
--
-- Every v1 plant / plant_name / from_plant / to_plant column becomes
-- plant_code / from_plant_code / to_plant_code (FK plant), except
-- extraction_log.plant_name (see that table).
-- =============================================================================

SET NAMES utf8mb4;


-- =============================================================================
-- DIMENSIONS
-- =============================================================================

-- Every plant string stored in v1, verbatim (also the aggregates SAIL and
-- SSPs, CFP, and both VISL and VISP).
CREATE TABLE plant (
    plant_code  VARCHAR(8)  NOT NULL,
    plant_name  VARCHAR(64) NULL,
    plant_kind  ENUM('integrated','special','aggregate','external') NOT NULL,
    sort_order  SMALLINT    NOT NULL DEFAULT 0,
    PRIMARY KEY (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Every production / plan / MoU / capacity / pdf-alias / DO-letter item name,
-- verbatim. Binary collation: case variants are distinct (see the header).
CREATE TABLE item (
    item_id     SMALLINT    NOT NULL AUTO_INCREMENT,
    item_name   VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    uom         VARCHAR(16) NULL,
    PRIMARY KEY (item_id),
    -- name -> id resolution for every production / capacity / alias read and write
    UNIQUE KEY uq_item_name (item_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- The units of a plant, verbatim: techno units, breakdown / capital-repair
-- units, BF meta units and major-unit record labels.
-- unit_type is the category of the unit where it has a single one, else NULL.
-- breakdown and capital_repair keep their own row-level unit_type, because
-- v1 files one unit under several types (e.g. BSP 'Shop' under BF, COKE and
-- GENERAL), which a single plant_unit.unit_type cannot hold.
CREATE TABLE plant_unit (
    unit_id     SMALLINT    NOT NULL AUTO_INCREMENT,
    plant_code  VARCHAR(8)  NOT NULL,
    unit_code   VARCHAR(64) NOT NULL,
    unit_type   VARCHAR(16) NULL,
    PRIMARY KEY (unit_id),
    -- (plant, unit name) -> unit_id: repo.techno.get_techno_data / json_row /
    -- plant_unit_month_rows, repo.misc.bf_sail_working_volume_row,
    -- repo.misc.major_unit_daily_label_row, repo.breakdown.list_breakdown_entries
    UNIQUE KEY uq_plant_unit_code (plant_code, unit_code),
    -- target of the composite (plant_code, unit_id) FKs, which keep the
    -- plant_code consistent with its unit
    UNIQUE KEY uq_plant_unit_id (plant_code, unit_id),
    -- unit-first reads across plants: repo.techno.bf_shop_rows,
    -- unit_plants_months_rows, five_plant_unit_rows, general_rows_with_source
    KEY idx_plant_unit_code (unit_code),
    CONSTRAINT fk_plant_unit_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- One row per month, 1960-04 ... 2040-03 (seed_cal_month.sql). Replaces the
-- SUBSTR() financial-year arithmetic.
CREATE TABLE cal_month (
    report_month CHAR(7)  NOT NULL,
    month_start  DATE     NOT NULL,
    fy           CHAR(7)  NOT NULL,
    fy_month     TINYINT  NOT NULL,
    quarter      TINYINT  NOT NULL,
    half         TINYINT  NOT NULL,
    PRIMARY KEY (report_month),
    -- FY grouping / FY-window reads replacing SUBSTR(): repo.production.records_bucket_cells,
    -- records_fy_window_cells, records_calendar_month_totals
    KEY idx_cal_month_fy (fy, fy_month),
    CONSTRAINT ck_cal_month_fy_month CHECK (fy_month BETWEEN 1 AND 12)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- =============================================================================
-- PRODUCTION
-- =============================================================================

-- production_table + production_plan_table + mou_plan_table, merged.
-- has_* = 1 when the source table had a row for (month, plant, item), so a
-- missing v1 row (has_* = 0, value NULL) stays distinct from a v1 row that
-- held NULL (has_* = 1, value NULL). plant_code 'SAIL' rows are reported
-- figures, not sums, and are kept.
CREATE TABLE production_monthly (
    report_month CHAR(7)    NOT NULL,
    plant_code   VARCHAR(8) NOT NULL,
    item_id      SMALLINT   NOT NULL,
    actual       DOUBLE     NULL,
    abp_plan     DOUBLE     NULL,
    mou_plan     DOUBLE     NULL,
    has_actual   TINYINT(1) NOT NULL DEFAULT 0,
    has_abp      TINYINT(1) NOT NULL DEFAULT 0,
    has_mou      TINYINT(1) NOT NULL DEFAULT 0,
    -- (month), (month, plant) and (month, plant, item) reads:
    -- repo.production.fetch, plant_rows_for_months, plant_month_actual_items,
    -- plant_month_plan_items, five_plant_saleable_semis, ytd_sum_row,
    -- get_sail_production_actual / _plan / _ytd_actual / _ytd_plan,
    -- save_production_actual / _plan, month_has_actual_and_plan,
    -- actual_plants_for_month, mou_items_for_month
    PRIMARY KEY (report_month, plant_code, item_id),
    -- item-first history / range reads (no plant filter, or a plant IN list):
    -- repo.production.records_rows, records_bucket_cells, records_fy_window_cells,
    -- records_calendar_month_totals, item_alias_rows, item_alias_report_months,
    -- item_by_plant_month, items_by_plant_month, item_month_totals_upto,
    -- items_plants_all_months, items_plants_upto, hot_metal_by_plant,
    -- latest_hot_metal_month_row, hm_cs_signature_row (v1 idx_prod_item_month)
    KEY idx_production_item_month (item_id, report_month),
    -- (plant, item) series reads: repo.production.get_production_actual_value,
    -- get_production_actual_for_months, actual_history, plant_item_months,
    -- plant_items_month_values, plant_items_monthly_sum_upto,
    -- items_plant_all_months, sail_conversion_by_month (v1 idx_prod_plant_item)
    KEY idx_production_plant_item_month (plant_code, item_id, report_month),
    CONSTRAINT fk_production_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_production_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_production_item  FOREIGN KEY (item_id) REFERENCES item (item_id),
    CONSTRAINT ck_production_actual CHECK (has_actual = 1 OR actual IS NULL),
    CONSTRAINT ck_production_abp    CHECK (has_abp = 1 OR abp_plan IS NULL),
    CONSTRAINT ck_production_mou    CHECK (has_mou = 1 OR mou_plan IS NULL),
    CONSTRAINT ck_production_source CHECK (has_actual + has_abp + has_mou > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 item_capacity_table. plant_name -> plant_code, item_name -> item_id.
CREATE TABLE item_capacity (
    id               BIGINT       NOT NULL AUTO_INCREMENT,
    plant_code       VARCHAR(8)   NOT NULL,
    item_id          SMALLINT     NOT NULL,
    effective_month  CHAR(7)      NOT NULL,
    annual_capacity  DOUBLE       NOT NULL,
    reason           VARCHAR(255) NULL DEFAULT '',
    created_by       VARCHAR(190) NULL,
    created_at       DATETIME(6)  NULL,
    updated_by       VARCHAR(190) NULL,
    updated_at       DATETIME(6)  NULL,
    PRIMARY KEY (id),
    -- latest capacity at or before a month: repo.capacity.get_effective_capacity,
    -- capacity_row_at, list_capacity_entries
    UNIQUE KEY uq_item_capacity (plant_code, item_id, effective_month),
    CONSTRAINT fk_item_capacity_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_item_capacity_item  FOREIGN KEY (item_id) REFERENCES item (item_id),
    CONSTRAINT fk_item_capacity_month FOREIGN KEY (effective_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 pdf_item_alias. plant_name -> plant_code, item_name -> item_id.
CREATE TABLE pdf_item_alias (
    plant_code  VARCHAR(8)   NOT NULL,
    pdf_label   VARCHAR(160) NOT NULL,
    item_id     SMALLINT     NOT NULL,
    convert_t   TINYINT(1)   NULL DEFAULT 1,
    -- repo.misc.get_pdf_item_aliases (by plant), save_pdf_item_alias
    PRIMARY KEY (plant_code, pdf_label),
    CONSTRAINT fk_pdf_item_alias_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_pdf_item_alias_item  FOREIGN KEY (item_id) REFERENCES item (item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 power_data_table. power_item is a free key (power-OIS codes such as
-- 'actual_total_cum'), not an item.
CREATE TABLE power_monthly (
    report_month CHAR(7)     NOT NULL,
    plant_code   VARCHAR(8)  NOT NULL,
    power_item   VARCHAR(64) NOT NULL,
    value        DOUBLE      NULL,
    -- repo.misc.power_rows_for_months, power_value_row, power_plants_for_month
    PRIMARY KEY (report_month, plant_code, power_item),
    CONSTRAINT fk_power_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_power_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 stock_table. stock_month -> report_month.
CREATE TABLE stock_monthly (
    report_month CHAR(7)     NOT NULL,
    plant_code   VARCHAR(8)  NOT NULL,
    item_type    VARCHAR(64) NOT NULL,
    stock_type   VARCHAR(64) NOT NULL DEFAULT '',
    stock        DOUBLE      NULL,
    -- repo.stock.month_rows, plant_month_rows, plants_for_month, save_stock_entry
    PRIMARY KEY (report_month, plant_code, item_type, stock_type),
    CONSTRAINT fk_stock_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_stock_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 ipt_table. from_plant / to_plant -> from_plant_code / to_plant_code.
-- item is the IPT material label ('CC Slabs', 'BF Coke'), not an item.
CREATE TABLE ipt_monthly (
    report_month    CHAR(7)     NOT NULL,
    item            VARCHAR(64) NOT NULL,
    from_plant_code VARCHAR(8)  NOT NULL,
    to_plant_code   VARCHAR(8)  NOT NULL,
    unit            VARCHAR(32) NULL,
    sort_order      INT         NULL DEFAULT 0,
    plan            DOUBLE      NULL,
    actual          DOUBLE      NULL,
    plan_tonnage    DOUBLE      NULL,
    actual_tonnage  DOUBLE      NULL,
    -- repo.ipt.entry_rows, routes, plan_actual_rows, month_value_rows,
    -- cum_value_rows, items_actual_sum_row, save_ipt_entry, delete_ipt_entry
    PRIMARY KEY (report_month, item, from_plant_code, to_plant_code),
    CONSTRAINT fk_ipt_month      FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_ipt_from_plant FOREIGN KEY (from_plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_ipt_to_plant   FOREIGN KEY (to_plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- =============================================================================
-- TECHNO-ECONOMIC PARAMETERS
-- =============================================================================

-- One row per v1 techno_data blob (plant, month, unit): its metadata.
-- has_month / has_till_month record which top-level period keys the blob had,
-- so an empty period ({}) stays distinct from a missing one (v1 has 89 blobs
-- with "month": {}, 558 with "till_month": {} and 5 with no till_month key).
CREATE TABLE techno_upload (
    report_month   CHAR(7)      NOT NULL,
    plant_code     VARCHAR(8)   NOT NULL,
    unit_id        SMALLINT     NOT NULL,
    has_month      TINYINT(1)   NOT NULL DEFAULT 1,
    has_till_month TINYINT(1)   NOT NULL DEFAULT 1,
    source_file    VARCHAR(255) NULL DEFAULT '',
    created_at     DATETIME(6)  NULL,
    -- (month), (month, plant), (month, plant, unit) reads: repo.techno._bulk_load,
    -- blobs, get_techno_data, get_sail_techno_actuals, month_rows,
    -- plants_month_rows, rows_for_months, units_for_plant_month, json_row,
    -- months_signature_row, merge_upsert_techno_data
    PRIMARY KEY (report_month, plant_code, unit_id),
    -- (plant, unit) across months: repo.techno.plant_unit_month_rows,
    -- plant_units_month_rows, sail_unit_rows, sail_rows, rows_for_plants,
    -- get_techno_months, five_plant_first_months
    KEY idx_techno_upload_unit_month (plant_code, unit_id, report_month),
    CONSTRAINT fk_techno_upload_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_techno_upload_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_techno_upload_unit  FOREIGN KEY (plant_code, unit_id) REFERENCES plant_unit (plant_code, unit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- One row per leaf of a techno_data blob: {period: {param_key: value}}.
-- Exactly one of num / raw is set:
--   number   num = the value, is_int = 1 when the JSON value was an integer
--            (5 vs 5.0 must come back as int vs float), raw NULL
--   other    num NULL, raw = the JSON value: a string, an object, or an
--            explicit JSON null (stored as the JSON literal null, not SQL NULL,
--            so an explicit null key stays distinct from a missing key)
-- Rebuilding a blob's dict order is Task 7's job (v1 returned MySQL JSON
-- key order).
CREATE TABLE techno_value (
    report_month CHAR(7)      NOT NULL,
    plant_code   VARCHAR(8)   NOT NULL,
    unit_id      SMALLINT     NOT NULL,
    period       ENUM('month','till_month') NOT NULL,
    param_key    VARCHAR(190) COLLATE utf8mb4_0900_bin NOT NULL,
    num          DOUBLE       NULL,
    is_int       TINYINT(1)   NOT NULL DEFAULT 0,
    raw          JSON         NULL,
    -- a blob's leaves (same reads as techno_upload's PRIMARY)
    PRIMARY KEY (report_month, plant_code, unit_id, period, param_key),
    -- (plant, unit) across months (same reads as idx_techno_upload_unit_month)
    KEY idx_techno_value_unit_month (plant_code, unit_id, report_month),
    CONSTRAINT fk_techno_value_upload FOREIGN KEY (report_month, plant_code, unit_id)
        REFERENCES techno_upload (report_month, plant_code, unit_id) ON DELETE CASCADE,
    -- implied by fk_techno_value_upload, declared so every plant_code / unit_id
    -- column carries its own FK
    CONSTRAINT fk_techno_value_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_techno_value_unit  FOREIGN KEY (plant_code, unit_id) REFERENCES plant_unit (plant_code, unit_id),
    CONSTRAINT ck_techno_value_one_form CHECK ((num IS NULL) <> (raw IS NULL)),
    CONSTRAINT ck_techno_value_int      CHECK (is_int = 0 OR num IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 techno_plan_fy (FY techno plans), kept as JSON blobs.
-- plant_name -> plant_code, unit -> unit_id.
CREATE TABLE techno_plan_fy (
    plant_code         VARCHAR(8)   NOT NULL,
    unit_id            SMALLINT     NOT NULL,
    fy                 CHAR(7)      NOT NULL,
    techno_json        JSON         NOT NULL,
    is_user_supplied   TINYINT(1)   NULL DEFAULT 0,
    calculated_json    JSON         NULL,
    calculation_method JSON         NULL,
    created_at         DATETIME     NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME     NULL DEFAULT CURRENT_TIMESTAMP,
    created_by         VARCHAR(190) NULL,
    -- repo.techno._get_techno_plan_cached, save_techno_plan, plan_json_row,
    -- plan_plants_rows, _get_techno_plant_plan_cached, _get_sail_techno_plan_cached
    PRIMARY KEY (plant_code, unit_id, fy),
    -- repo.techno.plan_rows_for_fy, list_techno_plan_fys
    KEY idx_techno_plan_fy (fy),
    CONSTRAINT fk_techno_plan_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_techno_plan_unit  FOREIGN KEY (plant_code, unit_id) REFERENCES plant_unit (plant_code, unit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- =============================================================================
-- NARRATIVE TEXT
-- =============================================================================

-- The 9 v1 narrative / note tables in one. scope names the v1 table (the
-- scope names of repo/text.py get / put):
--   page3_narrative   page3_narrative           period report_month, block_key = column
--   key_highlights    key_highlights_narrative  period report_month, block_key = column
--   steel_sales       steel_sales_highlights    period report_month, block_key = column
--   secretary_review  secretary_review_text     period report_month, block_key
--   board_note        board_note_manual_text    period '<fy>:Q<n>', block_key = field, plant_code
--   do_letter         do_letter_remark_table    period report_month, block_key 'remark', plant_code, item_id
--   sail_sales_note   sail_sales_note_table     period report_month, block_key 'note'
--   rail_note         rail_prod_despatch_note   period '', block_key 'note', seq = sort_order
--   ss_phys_note      special_steel_phys_note   period fy, block_key 'note', seq = sort_order
-- A v1 row with several text columns becomes one row per column, each
-- carrying the updated_by / updated_at. text NULL is a v1 column
-- that held NULL (a missing v1 row has no report_text rows).
-- period is VARCHAR(10), not 7, to hold the board_note period '2026-27:Q1'.
-- plant_key / item_key fold NULL to ''/0 so the natural key is unique even
-- for the scopes without a plant or item.
CREATE TABLE report_text (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    scope       ENUM('page3_narrative','key_highlights','steel_sales','secretary_review',
                     'board_note','do_letter','sail_sales_note','rail_note','ss_phys_note') NOT NULL,
    period      VARCHAR(10)  NOT NULL DEFAULT '',
    block_key   VARCHAR(48)  NOT NULL,
    plant_code  VARCHAR(8)   NULL,
    item_id     SMALLINT     NULL,
    seq         SMALLINT     NOT NULL DEFAULT 0,
    text        MEDIUMTEXT   NULL,
    updated_by  VARCHAR(190) NULL,
    updated_at  DATETIME     NULL,
    plant_key   VARCHAR(8)   AS (IFNULL(plant_code, '')) STORED,
    item_key    SMALLINT     AS (IFNULL(item_id, 0)) STORED,
    PRIMARY KEY (id),
    -- every repo.text read / write is (scope, period[, block_key, plant, item]):
    -- get_page3_narrative, get_key_highlights_narrative, get_steel_sales_highlights,
    -- get_texts, delete_texts, get_manual_text, save_manual_text,
    -- do_letter_remark_rows, do_letter_item_remark_rows, delete_do_letter_remark,
    -- sail_sales_note_row, get_ss_phys_notes, get_rail_report_notes (ORDER BY seq)
    UNIQUE KEY uq_report_text (scope, period, block_key, plant_key, item_key, seq),
    -- repo.text.latest_saved_before (block_key across months, newest first)
    KEY idx_report_text_block (scope, block_key, period),
    CONSTRAINT fk_report_text_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_report_text_item  FOREIGN KEY (item_id) REFERENCES item (item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- =============================================================================
-- SPECIAL STEEL
-- =============================================================================

-- v1 special_steel_orders.
CREATE TABLE special_steel_order (
    report_month    CHAR(7)      NOT NULL,
    plant_code      VARCHAR(8)   NOT NULL,
    product         VARCHAR(160) NOT NULL,
    quality_grade   VARCHAR(160) NOT NULL,
    section         VARCHAR(160) NOT NULL DEFAULT '',
    sort_order      INT          NULL DEFAULT 0,
    order_qty       DOUBLE       NULL,
    actual_despatch DOUBLE       NULL,
    -- (month[, plant[, product]]) reads: repo.special_steel.manual_rows,
    -- fy_plant_month_sums, group_rows, cply_rows, plant_month_sums_row,
    -- plant_months_sums_row, isp_*_row, ssps_order_row, product_actual_sums,
    -- despatch_rows, plants_for_month, clear_special_steel_orders
    PRIMARY KEY (report_month, plant_code, product, quality_grade, section),
    -- (plant[, product]) across months: repo.special_steel.products_for_plant,
    -- grades_for_product, all_grade_rows, group_ytd_rows, cply_ytd_rows,
    -- rsp_prior_grade_rows
    KEY idx_special_steel_order_product (plant_code, product, report_month),
    CONSTRAINT fk_ss_order_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_ss_order_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 special_steel_abp_table (plant 'SSPs' is the special-steel-plants aggregate).
CREATE TABLE special_steel_abp (
    report_month CHAR(7)    NOT NULL,
    plant_code   VARCHAR(8) NOT NULL,
    abp_qty      DOUBLE     NULL,
    -- repo.special_steel.abp_rows, abp_sum_row, abp_any_row, upsert_abp
    PRIMARY KEY (report_month, plant_code),
    CONSTRAINT fk_ss_abp_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_ss_abp_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 special_steel_grade_clubs.
CREATE TABLE special_steel_grade_club (
    plant_code    VARCHAR(8)   NOT NULL,
    product       VARCHAR(160) NOT NULL,
    quality_grade VARCHAR(160) NOT NULL,
    club_label    VARCHAR(200) NOT NULL,
    created_at    DATETIME(6)  NULL,
    -- repo.special_steel.club_rows, ordered_club_rows, club_member_rows,
    -- grade_club_row, delete_club, delete_grade_club, upsert_grade_club
    PRIMARY KEY (plant_code, product, quality_grade),
    CONSTRAINT fk_ss_club_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 special_steel_phys_meta.
CREATE TABLE special_steel_phys_meta (
    plant_code      VARCHAR(8)   NOT NULL,
    series          VARCHAR(16)  NOT NULL,
    capacity_kt     DOUBLE       NULL,
    best_actual_kt  DOUBLE       NULL,
    best_year       CHAR(7)      NULL,
    remark          VARCHAR(200) NULL,
    sort_order      INT          NOT NULL DEFAULT 0,
    -- repo.special_steel.get_ss_phys_perf, save_ss_phys_meta
    PRIMARY KEY (plant_code, series),
    CONSTRAINT fk_ss_phys_meta_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 special_steel_phys_perf. financial_year -> fy.
CREATE TABLE special_steel_phys_perf (
    fy          CHAR(7)    NOT NULL,
    plant_code  VARCHAR(8) NOT NULL,
    series      VARCHAR(16) NOT NULL,
    metric      VARCHAR(8) NOT NULL,
    value_kt    DOUBLE     NULL,
    -- repo.special_steel.get_ss_phys_perf, save_ss_phys_perf
    PRIMARY KEY (fy, plant_code, series, metric),
    CONSTRAINT fk_ss_phys_perf_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 special_steel_ipt_requirement. financial_year -> fy. item is a
-- material label, not an item.
CREATE TABLE special_steel_ipt_requirement (
    fy              CHAR(7)     NOT NULL,
    item            VARCHAR(64) NOT NULL,
    from_plant_code VARCHAR(8)  NOT NULL,
    to_plant_code   VARCHAR(8)  NOT NULL,
    plan_kt         DOUBLE      NULL,
    sort_order      INT         NOT NULL DEFAULT 0,
    -- repo.special_steel.get_ss_ipt_requirement, list_ss_ipt_requirement_fys,
    -- save_ss_ipt_requirement, delete_ss_ipt_requirement
    PRIMARY KEY (fy, item, from_plant_code, to_plant_code),
    CONSTRAINT fk_ss_ipt_from_plant FOREIGN KEY (from_plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_ss_ipt_to_plant   FOREIGN KEY (to_plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- =============================================================================
-- COST TREND, RAKE DETENTION, MARKET
-- =============================================================================

CREATE TABLE cost_trend_annual (
    fy          CHAR(7)     NOT NULL,
    product     VARCHAR(8)  NOT NULL,
    cost_type   VARCHAR(16) NOT NULL,
    plant_code  VARCHAR(8)  NOT NULL,
    value       DOUBLE      NULL,
    -- repo.cost_trend.get_cost_trend_annual, save_cost_trend_annual
    PRIMARY KEY (fy, product, cost_type, plant_code),
    CONSTRAINT fk_cost_annual_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE cost_trend_monthly (
    report_month     CHAR(7)     NOT NULL,
    product          VARCHAR(8)  NOT NULL,
    cost_type        VARCHAR(16) NOT NULL,
    plant_code       VARCHAR(8)  NOT NULL,
    month_value      DOUBLE      NULL,
    till_month_value DOUBLE      NULL,
    -- repo.cost_trend.get_cost_trend_monthly, monthly_any_row, save_cost_trend_monthly*
    PRIMARY KEY (report_month, product, cost_type, plant_code),
    CONSTRAINT fk_cost_monthly_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_cost_monthly_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 rake_detention_master. freetime_effective_from stays CHAR(10): v1
-- holds '' in 2 rows and NULL in others, which a DATE cannot keep apart.
CREATE TABLE rake_detention_master (
    id                      INT         NOT NULL AUTO_INCREMENT,
    plant_code              VARCHAR(8)  NOT NULL,
    section                 VARCHAR(8)  NOT NULL,
    commodity               VARCHAR(48) NULL,
    wagon_type              VARCHAR(24) NULL,
    row_label               VARCHAR(48) NOT NULL,
    is_total                TINYINT(1)  NOT NULL DEFAULT 0,
    direction               VARCHAR(4)  NULL,
    freetime_hours          DOUBLE      NULL,
    freetime_effective_from CHAR(10)    NULL,
    sort_order              INT         NOT NULL DEFAULT 0,
    is_active               TINYINT(1)  NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    -- repo.rake.get_rake_detention_master (WHERE plant IN ... ORDER BY plant, section, sort_order, id)
    KEY idx_rake_master_order (plant_code, section, sort_order, id),
    CONSTRAINT fk_rake_master_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE rake_detention_monthly (
    report_month CHAR(7) NOT NULL,
    master_id    INT     NOT NULL,
    value_hours  DOUBLE  NULL,
    -- repo.rake.get_rake_detention_monthly, save_rake_detention_monthly
    PRIMARY KEY (report_month, master_id),
    -- repo.rake.get_rake_detention_trend (WHERE master_id IN ...)
    KEY idx_rake_monthly_master (master_id, report_month),
    CONSTRAINT fk_rake_monthly_month  FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_rake_monthly_master FOREIGN KEY (master_id) REFERENCES rake_detention_master (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE rake_detention_summary (
    report_month CHAR(7)     NOT NULL,
    period_row   VARCHAR(24) NOT NULL,
    plant_code   VARCHAR(8)  NOT NULL,
    value        DOUBLE      NULL,
    -- repo.rake.get_rake_detention_summary, save_rake_detention_summary
    PRIMARY KEY (report_month, period_row, plant_code),
    CONSTRAINT fk_rake_summary_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_rake_summary_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 rake_detention_annual. financial_year -> fy.
CREATE TABLE rake_detention_annual (
    plant_code VARCHAR(8) NOT NULL,
    fy         CHAR(7)    NOT NULL,
    avg_hours  DOUBLE     NULL,
    -- repo.rake.get_rake_detention_annual, save_rake_detention_annual
    PRIMARY KEY (plant_code, fy),
    CONSTRAINT fk_rake_annual_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 macro_indicators_monthly.
CREATE TABLE macro_indicator_monthly (
    report_month CHAR(7)     NOT NULL,
    metric_code  VARCHAR(32) NOT NULL,
    value        DOUBLE      NULL,
    -- repo.misc.get_macro_indicators, save_macro_indicators
    PRIMARY KEY (report_month, metric_code),
    CONSTRAINT fk_macro_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 market_price_trend_monthly.
CREATE TABLE market_price_monthly (
    report_month CHAR(7)     NOT NULL,
    series_code  VARCHAR(48) NOT NULL,
    value        DOUBLE      NULL,
    -- repo.misc.get_market_price_trend, save_market_price_trend
    PRIMARY KEY (report_month, series_code),
    CONSTRAINT fk_market_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 sail_sales_table: raw JSON archive of source figures, kept as is.
-- item_name is the sales head ('Total Sales'), not an item.
CREATE TABLE sail_sales_monthly (
    report_month CHAR(7)     NOT NULL,
    item_name    VARCHAR(64) NOT NULL,
    data_json    JSON        NULL,
    -- repo.stock.sales_data_row, upsert_sales
    PRIMARY KEY (report_month, item_name),
    CONSTRAINT fk_sail_sales_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 sail_stock_snapshot_table. snapshot_date CHAR(10) -> DATE.
-- item_name is the stock bucket ('Plants', 'Stockyards'), not an item.
CREATE TABLE sail_stock_snapshot (
    snapshot_date DATE        NOT NULL,
    item_name     VARCHAR(32) NOT NULL,
    value         DOUBLE      NULL,
    -- repo.stock.snapshot_value_row, upsert_stock_snapshot
    PRIMARY KEY (snapshot_date, item_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 steel_sector_performance_table: raw JSON archive, kept as is.
CREATE TABLE steel_sector_performance (
    report_month CHAR(7)      NOT NULL,
    data_json    JSON         NULL,
    source_file  VARCHAR(255) NULL,
    created_at   DATETIME(6)  NULL,
    -- repo.misc.steel_sector_latest_row (report_month <= X, newest first),
    -- steel_sector_data_json_rows, steel_sector_any_row
    PRIMARY KEY (report_month),
    CONSTRAINT fk_steel_sector_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 rail_prod_despatch. financial_year -> fy.
CREATE TABLE rail_prod_despatch (
    fy      CHAR(7)     NOT NULL,
    metric  VARCHAR(32) NOT NULL,
    value   DOUBLE      NULL,
    note    VARCHAR(64) NULL,
    -- repo.misc.get_rail_report_data, save_rail_report_data
    PRIMARY KEY (fy, metric)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- =============================================================================
-- MINES (already normalised in v1, renamed to singular nouns)
-- =============================================================================

CREATE TABLE mine_group (
    group_code  VARCHAR(8)  NOT NULL,
    group_name  VARCHAR(64) NOT NULL,
    sort_order  INT         NOT NULL,
    -- repo.mines.get_mines_masters, group_rows (ORDER BY sort_order, a handful of rows)
    PRIMARY KEY (group_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE mine (
    mine_code   VARCHAR(24) NOT NULL,
    mine_name   VARCHAR(64) NOT NULL,
    group_code  VARCHAR(8)  NOT NULL,
    is_active   TINYINT(1)  NOT NULL DEFAULT 1,
    sort_order  INT         NOT NULL,
    -- the JOIN mine ON mine_code of every repo.mines.get_iron_ore_* rollup
    PRIMARY KEY (mine_code),
    CONSTRAINT fk_mine_group FOREIGN KEY (group_code) REFERENCES mine_group (group_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE mine_material (
    material_code              VARCHAR(16) NOT NULL,
    material_name              VARCHAR(32) NOT NULL,
    material_category          VARCHAR(16) NOT NULL,
    has_production             TINYINT(1)  NOT NULL DEFAULT 0,
    counts_in_total_production TINYINT(1)  NOT NULL DEFAULT 0,
    sort_order                 INT         NOT NULL,
    -- repo.mines.get_mines_masters, material_rows
    PRIMARY KEY (material_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE mine_end_use (
    end_use_code  VARCHAR(16) NOT NULL,
    end_use_name  VARCHAR(48) NOT NULL,
    sort_order    INT         NOT NULL,
    tracks_actual TINYINT(1)  NOT NULL DEFAULT 1,
    -- repo.mines.get_mines_masters
    PRIMARY KEY (end_use_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE mine_production_monthly (
    report_month  CHAR(7)     NOT NULL,
    mine_code     VARCHAR(24) NOT NULL,
    material_code VARCHAR(16) NOT NULL,
    qty_actual    DOUBLE      NULL,
    qty_plan      DOUBLE      NULL,
    -- (month[, mine]) reads: repo.mines.get_mines_production_despatch_monthly,
    -- get_iron_ore_group_rollup_monthly, get_iron_ore_mines_series, production_rows
    PRIMARY KEY (report_month, mine_code, material_code),
    CONSTRAINT fk_mine_prod_month    FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_mine_prod_mine     FOREIGN KEY (mine_code) REFERENCES mine (mine_code),
    CONSTRAINT fk_mine_prod_material FOREIGN KEY (material_code) REFERENCES mine_material (material_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE mine_despatch_actual_monthly (
    report_month   CHAR(7)     NOT NULL,
    mine_code      VARCHAR(24) NOT NULL,
    material_code  VARCHAR(16) NOT NULL,
    transport_mode VARCHAR(8)  NOT NULL,
    end_use_code   VARCHAR(16) NOT NULL,
    qty_actual     DOUBLE      NULL,
    -- (month[, mine]) reads: repo.mines.get_mines_production_despatch_monthly,
    -- get_iron_ore_group_rollup_monthly, get_iron_ore_despatch_mix,
    -- get_iron_ore_mines_series, despatch_actual_rows
    PRIMARY KEY (report_month, mine_code, material_code, transport_mode, end_use_code),
    -- repo.mines.get_iron_ore_sales_group_rollup_monthly (end_use_code = 'SALES'),
    -- get_iron_ore_despatch_mix (GROUP BY end_use_code)
    KEY idx_mine_desp_actual_enduse (report_month, end_use_code),
    CONSTRAINT fk_mine_desp_act_month    FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_mine_desp_act_mine     FOREIGN KEY (mine_code) REFERENCES mine (mine_code),
    CONSTRAINT fk_mine_desp_act_material FOREIGN KEY (material_code) REFERENCES mine_material (material_code),
    CONSTRAINT fk_mine_desp_act_end_use  FOREIGN KEY (end_use_code) REFERENCES mine_end_use (end_use_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE mine_despatch_plan_monthly (
    report_month  CHAR(7)     NOT NULL,
    mine_code     VARCHAR(24) NOT NULL,
    material_code VARCHAR(16) NOT NULL,
    end_use_code  VARCHAR(16) NOT NULL,
    qty_plan      DOUBLE      NULL,
    -- (month[, mine]) reads: repo.mines.get_mines_production_despatch_monthly,
    -- get_iron_ore_group_rollup_monthly, get_iron_ore_mines_series, despatch_plan_rows
    PRIMARY KEY (report_month, mine_code, material_code, end_use_code),
    -- repo.mines.get_iron_ore_sales_group_rollup_monthly (end_use_code = 'SALES')
    KEY idx_mine_desp_plan_enduse (report_month, end_use_code),
    CONSTRAINT fk_mine_desp_plan_month    FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_mine_desp_plan_mine     FOREIGN KEY (mine_code) REFERENCES mine (mine_code),
    CONSTRAINT fk_mine_desp_plan_material FOREIGN KEY (material_code) REFERENCES mine_material (material_code),
    CONSTRAINT fk_mine_desp_plan_end_use  FOREIGN KEY (end_use_code) REFERENCES mine_end_use (end_use_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE mine_booked_qty_actual_monthly (
    report_month   CHAR(7)     NOT NULL,
    mine_code      VARCHAR(24) NOT NULL,
    material_code  VARCHAR(16) NOT NULL,
    transport_mode VARCHAR(8)  NOT NULL,
    qty_actual     DOUBLE      NULL,
    -- repo.mines.get_mines_production_despatch_monthly,
    -- get_iron_ore_sales_group_rollup_monthly, booked_actual_rows
    PRIMARY KEY (report_month, mine_code, material_code, transport_mode),
    CONSTRAINT fk_mine_booked_act_month    FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_mine_booked_act_mine     FOREIGN KEY (mine_code) REFERENCES mine (mine_code),
    CONSTRAINT fk_mine_booked_act_material FOREIGN KEY (material_code) REFERENCES mine_material (material_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE mine_booked_qty_plan_monthly (
    report_month  CHAR(7)     NOT NULL,
    mine_code     VARCHAR(24) NOT NULL,
    material_code VARCHAR(16) NOT NULL,
    qty_plan      DOUBLE      NULL,
    -- repo.mines.get_mines_production_despatch_monthly,
    -- get_iron_ore_sales_group_rollup_monthly, booked_plan_rows
    PRIMARY KEY (report_month, mine_code, material_code),
    CONSTRAINT fk_mine_booked_plan_month    FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_mine_booked_plan_mine     FOREIGN KEY (mine_code) REFERENCES mine (mine_code),
    CONSTRAINT fk_mine_booked_plan_material FOREIGN KEY (material_code) REFERENCES mine_material (material_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 sail_mines_monthly (SAIL-level mines figures entered by hand).
CREATE TABLE sail_mines_monthly (
    report_month CHAR(7)     NOT NULL,
    section      VARCHAR(24) NOT NULL,
    item         VARCHAR(32) NOT NULL,
    month_actual DOUBLE      NULL,
    month_plan   DOUBLE      NULL,
    -- repo.mines.get_sail_mines_monthly, sail_rows, sail_mines_any_row
    PRIMARY KEY (report_month, section, item),
    CONSTRAINT fk_sail_mines_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- =============================================================================
-- PLANT EQUIPMENT: BF BENCHMARK, BREAKDOWNS, CAPITAL REPAIRS, MAJOR UNITS
-- =============================================================================

CREATE TABLE bf_benchmark_external_bf (
    id                BIGINT       NOT NULL AUTO_INCREMENT,
    name              VARCHAR(190) NOT NULL,
    company           VARCHAR(190) NULL DEFAULT '',
    location          VARCHAR(190) NULL DEFAULT '',
    working_volume_m3 DOUBLE       NULL,
    active            TINYINT(1)   NOT NULL DEFAULT 1,
    created_at        DATETIME(6)  NOT NULL,
    -- 1 when the v1 string was 'YYYY-MM-DD HH:MM:SS' (6 legacy rows) instead
    -- of the UTC ISO form the app writes now. This column mixes both formats
    -- and GET /external-bfs returns it, so the per-column format rule of
    -- Task 6 cannot render it back without this per-row marker.
    created_at_plain  TINYINT(1)   NOT NULL DEFAULT 0,
    created_by        VARCHAR(190) NULL DEFAULT '',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 bf_benchmark_external_data. report_month (which held an FY) -> fy.
CREATE TABLE bf_benchmark_external_data (
    id               BIGINT      NOT NULL AUTO_INCREMENT,
    external_bf_id   BIGINT      NOT NULL,
    fy               CHAR(7)     NOT NULL,
    param_json       JSON        NOT NULL,
    created_at       DATETIME(6) NULL,
    updated_at       DATETIME(6) NULL,
    -- per-row format markers, as bf_benchmark_external_bf.created_at_plain
    -- (v1 mixes 'YYYY-MM-DD HH:MM:SS' and UTC ISO in both columns)
    created_at_plain TINYINT(1)  NOT NULL DEFAULT 0,
    updated_at_plain TINYINT(1)  NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    -- repo.misc.external_bf_data_row, update_external_bf_data,
    -- external_bf_list_rows (MAX(fy) per BF)
    UNIQUE KEY uq_bf_external_data (external_bf_id, fy),
    CONSTRAINT fk_bf_external_data_bf FOREIGN KEY (external_bf_id) REFERENCES bf_benchmark_external_bf (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 bf_benchmark_sail_meta. plant -> plant_code, unit -> unit_id.
CREATE TABLE bf_benchmark_sail_meta (
    plant_code        VARCHAR(8)  NOT NULL,
    unit_id           SMALLINT    NOT NULL,
    working_volume_m3 DOUBLE      NULL,
    updated_at        DATETIME(6) NULL,
    -- repo.misc.bf_sail_working_volume_row, upsert_bf_sail_meta, bf_sail_meta_rows
    PRIMARY KEY (plant_code, unit_id),
    CONSTRAINT fk_bf_sail_meta_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_bf_sail_meta_unit  FOREIGN KEY (plant_code, unit_id) REFERENCES plant_unit (plant_code, unit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 capital_repair_table. plant -> plant_code, unit_name -> unit_id
-- (NULL when v1 had none), unit_type kept per row (see plant_unit).
-- fy VARCHAR(8) -> CHAR(7). actual_start / actual_end CHAR(10) -> DATE.
CREATE TABLE capital_repair (
    id             BIGINT       NOT NULL AUTO_INCREMENT,
    plant_code     VARCHAR(8)   NOT NULL,
    fy             CHAR(7)      NOT NULL,
    shop           VARCHAR(64)  NULL,
    equipment      VARCHAR(64)  NULL,
    unit_type      VARCHAR(16)  NULL,
    unit_id        SMALLINT     NULL,
    sms_subtag     VARCHAR(16)  NULL,
    activity       VARCHAR(255) NULL,
    schedule_days  VARCHAR(64)  NULL,
    actual_start   DATE         NULL,
    actual_end     DATE         NULL,
    actual_ongoing TINYINT(1)   NOT NULL DEFAULT 0,
    planned_days   DOUBLE       NULL,
    period         VARCHAR(64)  NULL,
    actual         VARCHAR(128) NULL,
    sort_order     INT          NULL DEFAULT 0,
    PRIMARY KEY (id),
    -- repo.breakdown.cr_report_rows, cr_calendar_rows, cr_entry_rows,
    -- cr_ordered_ids, cr_started_rows, cr_renumber, cr_copy_source
    -- (WHERE plant AND fy ORDER BY sort_order, id), cr_rows_for_plant, cr_actual_rows
    KEY idx_capital_repair_plant_fy (plant_code, fy, sort_order),
    CONSTRAINT fk_capital_repair_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_capital_repair_unit  FOREIGN KEY (plant_code, unit_id) REFERENCES plant_unit (plant_code, unit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 breakdown_table. plant -> plant_code, unit_name -> unit_id, unit_type
-- kept per row (see plant_unit).
-- start_ts / end_ts stay VARCHAR(16): they are user-entered local times and
-- v1 holds both 'YYYY-MM-DD HH:MM' (156 / 148 rows) and a bare 'YYYY-MM-DD'
-- (70 / 68 rows). A DATETIME would turn '2026-08-02' into '2026-08-02 00:00',
-- which v1 also holds as a distinct value. The API validates only
-- "at least YYYY-MM-DD" and the repo compares them as strings.
-- capital_repair_id: ON DELETE SET NULL. v1 has no FK and leaves the id
-- dangling when a linked capital repair is deleted (no dangling id exists
-- in the v1 data).
CREATE TABLE breakdown (
    id                  BIGINT       NOT NULL AUTO_INCREMENT,
    plant_code          VARCHAR(8)   NOT NULL,
    unit_type           VARCHAR(16)  NOT NULL,
    unit_id             SMALLINT     NOT NULL,
    sms_subtag          VARCHAR(16)  NULL,
    start_ts            VARCHAR(16)  NOT NULL,
    end_ts              VARCHAR(16)  NULL,
    is_ongoing          TINYINT(1)   NOT NULL DEFAULT 0,
    cause               TEXT         NOT NULL,
    hours_lost_override DOUBLE       NULL,
    capital_repair_id   BIGINT       NULL,
    created_by          VARCHAR(190) NULL,
    created_at          DATETIME(6)  NULL,
    updated_by          VARCHAR(190) NULL,
    updated_at          DATETIME(6)  NULL,
    PRIMARY KEY (id),
    -- repo.breakdown.list_breakdown_entries (plant / unit_type / unit filters),
    -- breakdown_rows_for_plant
    KEY idx_breakdown_plant_unit (plant_code, unit_type, unit_id),
    -- repo.breakdown.open_breakdown_rows (start_ts < X), list_breakdown_entries
    -- (ORDER BY start_ts DESC, id DESC)
    KEY idx_breakdown_start (start_ts),
    CONSTRAINT fk_breakdown_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_breakdown_unit  FOREIGN KEY (plant_code, unit_id) REFERENCES plant_unit (plant_code, unit_id),
    CONSTRAINT fk_breakdown_capital_repair FOREIGN KEY (capital_repair_id) REFERENCES capital_repair (id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 major_unit_daily_record. unit_label -> unit_id (the label is the
-- plant_unit.unit_code). record_date VARCHAR(10) -> DATE.
CREATE TABLE major_unit_daily_record (
    plant_code      VARCHAR(8)   NOT NULL,
    unit_id         SMALLINT     NOT NULL,
    unit_of_measure VARCHAR(16)  NULL,
    value           DOUBLE       NULL,
    record_date     DATE         NULL,
    remarks         TEXT         NULL,
    sort_order      INT          NOT NULL DEFAULT 0,
    updated_by      VARCHAR(190) NULL,
    updated_at      DATETIME(6)  NULL,
    -- repo.misc.get_major_unit_daily_records (by plant, ORDER BY sort_order),
    -- major_unit_daily_values, major_unit_daily_label_row, save_major_unit_daily_record
    PRIMARY KEY (plant_code, unit_id),
    CONSTRAINT fk_major_unit_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_major_unit_unit  FOREIGN KEY (plant_code, unit_id) REFERENCES plant_unit (plant_code, unit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 ready_reckoner_pages. plant_name is the page heading text (kept),
-- plant_group the page group ('ISP' / 'SSP'), not a plant.
CREATE TABLE ready_reckoner_page (
    plant_code              VARCHAR(8)   NOT NULL,
    plant_name              VARCHAR(64)  NULL,
    plant_group             VARCHAR(4)   NOT NULL,
    process_flow_image_path VARCHAR(255) NULL,
    sort_order              INT          NOT NULL DEFAULT 0,
    updated_by              VARCHAR(128) NULL,
    updated_at              DATETIME     NULL,
    capacity_rows           LONGTEXT     NULL,
    product_mix_headers     LONGTEXT     NULL,
    product_mix_rows        LONGTEXT     NULL,
    product_mix_caption     VARCHAR(255) NULL,
    -- repo.misc.get_ready_reckoner_page, save_ready_reckoner_content,
    -- save_ready_reckoner_image (get_ready_reckoner_pages reads all 8 rows)
    PRIMARY KEY (plant_code),
    CONSTRAINT fk_ready_reckoner_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- =============================================================================
-- REPORT PAGES AND COVER
-- =============================================================================

-- v1 page_configs. page_data stays MEDIUMTEXT (with a JSON_VALID check)
-- rather than JSON: a JSON column re-orders object keys, and all 70 v1 rows
-- would come back in a different key order (json.loads then iterates them
-- differently). Measured on the baseline: 70 of 70 rows equal but re-ordered.
CREATE TABLE page_config (
    report_month CHAR(7)    NOT NULL,
    page_number  INT        NOT NULL,
    page_data    MEDIUMTEXT NULL,
    -- repo.pages.get_page_config, get_all_page_configs (ORDER BY page_number), save_page_config
    PRIMARY KEY (report_month, page_number),
    CONSTRAINT fk_page_config_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT ck_page_config_json  CHECK (page_data IS NULL OR JSON_VALID(page_data))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 cover_photos. uploaded_by / uploaded_at -> created_by / created_at.
CREATE TABLE cover_photo (
    id             INT          NOT NULL AUTO_INCREMENT,
    filename       VARCHAR(64)  NOT NULL,
    thumb_filename VARCHAR(64)  NOT NULL,
    original_name  VARCHAR(255) NOT NULL,
    width          INT          NULL,
    height         INT          NULL,
    created_by     VARCHAR(255) NULL,
    created_at     DATETIME(6)  NULL,
    is_active      TINYINT(1)   NOT NULL DEFAULT 1,
    -- repo.misc.cover_photo_rows, active_cover_photo_rows* (a few dozen rows)
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 report_cover_settings.
CREATE TABLE report_cover_setting (
    report_month CHAR(7)      NOT NULL,
    design       VARCHAR(24)  NOT NULL,
    photo_mode   VARCHAR(8)   NOT NULL DEFAULT 'random',
    photo_id     INT          NULL,
    updated_by   VARCHAR(255) NULL,
    updated_at   DATETIME(6)  NULL,
    -- repo.misc.cover_setting_rows, replace_cover_setting
    PRIMARY KEY (report_month),
    CONSTRAINT fk_cover_setting_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_cover_setting_photo FOREIGN KEY (photo_id) REFERENCES cover_photo (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- =============================================================================
-- OPS: USERS, AUTH, AUDIT, JOBS
-- user_email / user_name / created_by / updated_by in these and the tables
-- above are point-in-time records (deleted users stay in the logs), not FKs.
-- =============================================================================

-- v1 users (ruling R6: app_user, not user).
CREATE TABLE app_user (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    email         VARCHAR(190) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(190) NULL DEFAULT '',
    role          VARCHAR(32)  NULL,
    profile_pic   VARCHAR(255) NULL DEFAULT '',
    created_at    DATETIME(6)  NOT NULL,
    updated_at    DATETIME(6)  NULL,
    allowed_pages TEXT         NULL,
    can_delete    TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    -- repo.ops.get_user_by_email, update_password
    UNIQUE KEY uq_app_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 allowed_emails. added_by / added_at -> created_by / created_at.
CREATE TABLE allowed_email (
    email      VARCHAR(190) NOT NULL,
    created_by VARCHAR(190) NULL,
    created_at DATETIME(6)  NOT NULL,
    barred     TINYINT(1)   NOT NULL DEFAULT 0,
    barred_by  VARCHAR(190) NULL,
    barred_at  DATETIME(6)  NULL,
    -- repo.ops.is_email_allowed, allowed_email_exists_row, set_allowed_email_barred
    PRIMARY KEY (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 otp_codes. email is not an FK: codes are issued before sign-up.
CREATE TABLE otp_code (
    id         BIGINT       NOT NULL AUTO_INCREMENT,
    email      VARCHAR(190) NOT NULL,
    purpose    VARCHAR(32)  NOT NULL,
    code_hash  VARCHAR(255) NOT NULL,
    expires_at DATETIME(6)  NOT NULL,
    used       TINYINT(1)   NOT NULL DEFAULT 0,
    created_at DATETIME(6)  NOT NULL,
    PRIMARY KEY (id),
    -- repo.ops.otp_latest_created_row, otp_latest_unused_row (ORDER BY id DESC),
    -- otp_invalidate_unused
    KEY idx_otp_code_email (email, purpose, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 activity_log. timestamp -> created_at. The v1 index on timestamp is
-- not carried: no repository query filters or sorts on it.
CREATE TABLE activity_log (
    id         BIGINT       NOT NULL AUTO_INCREMENT,
    user_email VARCHAR(190) NULL,
    user_name  VARCHAR(190) NULL,
    action     VARCHAR(64)  NOT NULL,
    entity     VARCHAR(160) NULL,
    details    TEXT         NULL,
    created_at DATETIME(6)  NOT NULL,
    -- repo.ops.activity_log_rows (ORDER BY id DESC, no filter)
    PRIMARY KEY (id),
    -- repo.ops.activity_log_rows (WHERE user_email = X ORDER BY id DESC),
    -- activity_log_user_rows
    KEY idx_activity_log_user (user_email, id),
    -- repo.ops.activity_log_rows (WHERE action = X ORDER BY id DESC),
    -- activity_log_action_rows
    KEY idx_activity_log_action (action, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 page_visits. timestamp -> created_at. The v1 indexes on user_email and
-- ip_address are not carried: no repository query uses them.
CREATE TABLE page_visit (
    id         BIGINT       NOT NULL AUTO_INCREMENT,
    created_at DATETIME(6)  NOT NULL,
    ip_address VARCHAR(64)  NULL,
    user_email VARCHAR(190) NULL,
    user_name  VARCHAR(190) NULL,
    path       VARCHAR(255) NOT NULL,
    PRIMARY KEY (id),
    -- repo.ops.page_visit_rows_since (created_at >= X ORDER BY created_at), page_visit_rows
    KEY idx_page_visit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 admin_notifications.
CREATE TABLE admin_notification (
    id         BIGINT       NOT NULL AUTO_INCREMENT,
    created_at DATETIME(6)  NOT NULL,
    kind       VARCHAR(20)  NOT NULL,
    user_email VARCHAR(190) NULL,
    user_name  VARCHAR(190) NULL,
    ip_address VARCHAR(64)  NULL,
    path       VARCHAR(255) NULL,
    -- repo.ops.list_admin_notifications (ORDER BY id DESC)
    PRIMARY KEY (id),
    -- repo.ops._add_admin_notification (kind = 'anon_visit' AND ip_address = X AND created_at >= Y)
    KEY idx_admin_notification_kind_ip (kind, ip_address, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 extraction_log. logged_at -> created_at.
-- plant_name stays a free label, not a plant_code FK: it is a log of what an
-- upload was called with, and v1 holds source tags that are not plants
-- ('BSP_BF', 'TESTPLANT') and report months outside cal_month ('2099-01'),
-- so neither column is an FK.
CREATE TABLE extraction_log (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    created_at      DATETIME(6)  NOT NULL,
    plant_name      VARCHAR(32)  NOT NULL,
    report_month    CHAR(7)      NOT NULL,
    file_name       VARCHAR(255) NULL,
    sheet_name      VARCHAR(160) NULL,
    source_type     VARCHAR(160) NULL,
    items_extracted INT          NULL,
    -- repo.ops.get_extraction_logs (ORDER BY id DESC LIMIT n)
    PRIMARY KEY (id),
    -- repo.ops.production_month_status (WHERE report_month = X), v1 idx_extraction_month
    KEY idx_extraction_log_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 todo_jobs. due_date VARCHAR(10) -> DATE.
CREATE TABLE todo_job (
    id           BIGINT       NOT NULL AUTO_INCREMENT,
    subject      VARCHAR(255) NOT NULL,
    details      TEXT         NULL,
    recipient    VARCHAR(255) NULL,
    due_date     DATE         NOT NULL,
    priority     VARCHAR(16)  NOT NULL DEFAULT 'medium',
    status       VARCHAR(16)  NOT NULL DEFAULT 'pending',
    created_at   DATETIME(6)  NOT NULL,
    completed_at DATETIME(6)  NULL,
    remark       TEXT         NULL,
    -- repo.ops.todo_job_row, todo_all_jobs / todo_jobs_by_status (a few dozen rows)
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- v1 daily_work_log. work_date VARCHAR(10) -> DATE.
CREATE TABLE daily_work_log (
    id          BIGINT      NOT NULL AUTO_INCREMENT,
    work_date   DATE        NOT NULL,
    description TEXT        NOT NULL,
    remarks     TEXT        NULL,
    created_at  DATETIME(6) NOT NULL,
    -- repo.ops.worklog_entry_row, worklog_rows (a few rows)
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- The write counter of Task 4 (backend/repo/version.py): one row, id = 1, bumped
-- by every repository write. Page caches key on it.
CREATE TABLE data_version (
    id  TINYINT NOT NULL,
    n   BIGINT  NOT NULL,
    -- repo.version.read (WHERE id = 1), bump
    PRIMARY KEY (id),
    CONSTRAINT data_version_one_row CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO data_version (id, n) VALUES (1, 1);
