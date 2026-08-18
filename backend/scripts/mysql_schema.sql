-- MySQL 8.x schema for mis_reports — converted from SQLite per
-- docs/MYSQL_MIGRATION_PLAN.md §4. Timestamps kept as VARCHAR to preserve
-- the string semantics the code expects; _old_plant_units intentionally
-- dropped. Apply once with an admin user:
--   mysql -u root -p mis_reports < scripts/mysql_schema.sql

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS production_table (
    report_month CHAR(7)      NOT NULL,
    plant_name   VARCHAR(32)  NOT NULL,
    item_name    VARCHAR(64)  NOT NULL,
    month_actual DOUBLE,
    PRIMARY KEY (report_month, plant_name, item_name),
    KEY idx_prod_plant_item (plant_name, item_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS production_plan_table (
    report_month CHAR(7)      NOT NULL,
    plant_name   VARCHAR(32)  NOT NULL,
    item_name    VARCHAR(64)  NOT NULL,
    month_actual DOUBLE,
    PRIMARY KEY (report_month, plant_name, item_name)
) ENGINE=InnoDB;

-- Power-OIS monthly power data — same narrow shape as production_table,
-- its own table since item_name values (plan_own, actual_total,
-- wheeling_px, last_year_own_cpp_cum, etc.) come from a different
-- vocabulary. See excel_extractors/excel_extractor_power_omi.py and
-- page_power_data.py.
CREATE TABLE IF NOT EXISTS power_data_table (
    report_month CHAR(7)      NOT NULL,
    plant_name   VARCHAR(32)  NOT NULL,
    item_name    VARCHAR(64)  NOT NULL,
    value        DOUBLE,
    PRIMARY KEY (report_month, plant_name, item_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS page_configs (
    report_month CHAR(7) NOT NULL,
    page_number  INT     NOT NULL,
    page_data    MEDIUMTEXT,
    PRIMARY KEY (report_month, page_number)
) ENGINE=InnoDB;

-- Special Steel ABP (Annual Business Plan) — one monthly target per plant,
-- entered for all 12 months of a FY at once via the Special Steel ABP Entry
-- page. plant_name matches special_steel_orders' values (the 5 integrated
-- plants + the 'SSPs' aggregate row), not the broader plant list.
CREATE TABLE IF NOT EXISTS special_steel_abp_table (
    report_month CHAR(7)     NOT NULL,
    plant_name   VARCHAR(32) NOT NULL,
    abp_qty      DOUBLE,
    PRIMARY KEY (report_month, plant_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS special_steel_orders (
    report_month    CHAR(7)      NOT NULL,
    plant_name      VARCHAR(32)  NOT NULL,
    product         VARCHAR(160) NOT NULL,
    quality_grade   VARCHAR(160) NOT NULL,
    section         VARCHAR(160) NOT NULL DEFAULT '',
    sort_order      INT DEFAULT 0,
    order_qty       DOUBLE,
    actual_despatch DOUBLE,
    PRIMARY KEY (report_month, plant_name, product, quality_grade, section)
) ENGINE=InnoDB;

-- Rows sharing (plant_name, product, club_label) are members of one combined
-- display row on the Special Steel report — see page_special_steel.py's
-- _resolve_clubs(). A grade can belong to at most one club per plant+product.
CREATE TABLE IF NOT EXISTS special_steel_grade_clubs (
    plant_name     VARCHAR(32)  NOT NULL,
    product        VARCHAR(160) NOT NULL,
    quality_grade  VARCHAR(160) NOT NULL,
    club_label     VARCHAR(200) NOT NULL,
    created_at     VARCHAR(40),
    PRIMARY KEY (plant_name, product, quality_grade)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS stock_table (
    stock_month CHAR(7)     NOT NULL,
    plant_name  VARCHAR(32) NOT NULL,
    item_type   VARCHAR(64) NOT NULL,
    stock_type  VARCHAR(64) NOT NULL DEFAULT '',
    stock       DOUBLE,
    PRIMARY KEY (stock_month, plant_name, item_type, stock_type)
) ENGINE=InnoDB;

-- Pure archive of Table A (Sales) exactly as the source department
-- reports it — data_json holds all 10 figures (month ABP/Actual/%Ful/
-- CPLY/Growth + the same 5 for Apr-month cumulative), never computed
-- or re-derived here (see excel_extractors/sail_sales_stock_extractor.py).
CREATE TABLE IF NOT EXISTS sail_sales_table (
    report_month CHAR(7)      NOT NULL,
    item_name    VARCHAR(64)  NOT NULL,
    data_json    JSON,
    PRIMARY KEY (report_month, item_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sail_stock_snapshot_table (
    snapshot_date CHAR(10)    NOT NULL,
    item_name     VARCHAR(32) NOT NULL,
    value         DOUBLE,
    PRIMARY KEY (snapshot_date, item_name)
) ENGINE=InnoDB;

-- Asterisked remark under Table A (Sales), e.g. "*Jul25 & Apr-Jul25 fig
-- incl NSL sales: 98 & 482 respectively" — extracted alongside
-- sail_sales_table and reprinted verbatim under Table A in the generated
-- report (see excel_extractors/sail_sales_stock_extractor.py).
CREATE TABLE IF NOT EXISTS sail_sales_note_table (
    report_month CHAR(7)  NOT NULL PRIMARY KEY,
    note         TEXT
) ENGINE=InnoDB;

-- "Indian Steel Sector Performance" — PIB Ministry of Steel monthly release,
-- archived verbatim (all tables + text sections) as one JSON blob per
-- report_month. See excel_extractors/pdf_extractor_steel_sector_performance.py
-- and page_steel_sector_performance.py (pages 2.1-2.4 of the report).
CREATE TABLE IF NOT EXISTS steel_sector_performance_table (
    report_month CHAR(7)  NOT NULL PRIMARY KEY,
    data_json    JSON,
    source_file  VARCHAR(255),
    created_at   VARCHAR(32)
) ENGINE=InnoDB;

-- Plant-wise remarks for the Monthly DO Letter's Annexure-A (Crude Steel) /
-- Annexure-B (Finished Steel) tables — entered ahead of time so the letter
-- (due the 1st of the following month) already has them when generated.
CREATE TABLE IF NOT EXISTS do_letter_remark_table (
    report_month CHAR(7)     NOT NULL,
    item_name    VARCHAR(32) NOT NULL,   -- 'Crude Steel' | 'Finished Steel'
    plant_name   VARCHAR(8)  NOT NULL,
    remark       TEXT,
    PRIMARY KEY (report_month, item_name, plant_name)
) ENGINE=InnoDB;

-- Capital Repair plan (pages 36-40, Report_format/CR.pdf format). "actual"
-- is derived/written by format_cr_actual() from actual_start/actual_end/
-- actual_ongoing once a row is edited through the updated data-entry UI;
-- shop/equipment/activity/schedule_days/period stay free text (print
-- source of truth). unit_type/unit_name/sms_subtag/planned_days feed
-- production_loss_analysis.py — see backend/scripts/migrate_add_cr_breakdown.sql
-- for the ALTER TABLE that added these columns to the already-live DB.
CREATE TABLE IF NOT EXISTS capital_repair_table (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    plant         VARCHAR(8)   NOT NULL,
    fy            VARCHAR(8)   NOT NULL,
    shop          VARCHAR(64),
    equipment     VARCHAR(64),
    activity      VARCHAR(255),
    schedule_days VARCHAR(64),
    period        VARCHAR(64),
    actual        VARCHAR(128),
    sort_order    INT DEFAULT 0,
    unit_type     VARCHAR(16)  NULL,
    unit_name     VARCHAR(32)  NULL,
    sms_subtag    VARCHAR(16)  NULL,
    actual_start  CHAR(10)     NULL,
    actual_end    CHAR(10)     NULL,
    actual_ongoing TINYINT(1)  NOT NULL DEFAULT 0,
    planned_days  DOUBLE       NULL,
    KEY idx_cr_plant_fy (plant, fy)
) ENGINE=InnoDB;

-- Breakdown log — plant/unit-wise unplanned-downtime events, full CRUD (see
-- api_breakdown.py). No `fy` column — derived from start_ts via
-- page_capital_repair.fy_from_month() to avoid a second source of truth.
CREATE TABLE IF NOT EXISTS breakdown_table (
    id                   BIGINT AUTO_INCREMENT PRIMARY KEY,
    plant                VARCHAR(8)   NOT NULL,
    unit_type            VARCHAR(16)  NOT NULL,
    unit_name            VARCHAR(32)  NOT NULL,
    sms_subtag           VARCHAR(16)  NULL,
    start_ts             VARCHAR(16)  NOT NULL,
    end_ts               VARCHAR(16)  NULL,
    is_ongoing           TINYINT(1)   NOT NULL DEFAULT 0,
    cause                TEXT         NOT NULL,
    hours_lost_override  DOUBLE       NULL,
    created_by           VARCHAR(190),
    created_at           VARCHAR(40),
    updated_by           VARCHAR(190),
    updated_at           VARCHAR(40),
    KEY idx_breakdown_plant_unit (plant, unit_type, unit_name),
    KEY idx_breakdown_start (start_ts)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ipt_table (
    report_month CHAR(7)     NOT NULL,
    item         VARCHAR(64) NOT NULL,
    from_plant   VARCHAR(32) NOT NULL,
    to_plant     VARCHAR(32) NOT NULL,
    unit         VARCHAR(32),
    sort_order   INT DEFAULT 0,
    plan         DOUBLE,
    actual       DOUBLE,
    plan_tonnage DOUBLE,
    actual_tonnage DOUBLE,
    PRIMARY KEY (report_month, item, from_plant, to_plant)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pdf_item_alias (
    plant_name VARCHAR(32)  NOT NULL,
    pdf_label  VARCHAR(160) NOT NULL,
    item_name  VARCHAR(64)  NOT NULL,
    convert_t  INT DEFAULT 1,
    PRIMARY KEY (plant_name, pdf_label)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS techno_data (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    plant        VARCHAR(32) NOT NULL,
    report_month CHAR(7)     NOT NULL,
    unit         VARCHAR(32) NOT NULL,
    techno_json  JSON        NOT NULL,
    source_file  VARCHAR(255) DEFAULT '',
    created_at   VARCHAR(40),
    UNIQUE KEY uq_techno (plant, report_month, unit),
    KEY idx_techno_month (report_month)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS techno_plan_fy (
    plant_name       VARCHAR(32) NOT NULL,
    unit             VARCHAR(32) NOT NULL,
    fy               CHAR(7)     NOT NULL,
    techno_json      JSON        NOT NULL,
    is_user_supplied INT DEFAULT 0,
    calculated_json  JSON,
    calculation_method JSON,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by       VARCHAR(190),
    PRIMARY KEY (plant_name, unit, fy)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS extraction_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    logged_at    VARCHAR(40) NOT NULL,
    plant_name   VARCHAR(32) NOT NULL,
    report_month CHAR(7)     NOT NULL,
    file_name    VARCHAR(255),
    sheet_name   VARCHAR(160),
    source_type  VARCHAR(160),
    items_extracted INT,
    KEY idx_extraction_logged (logged_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(190) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(190) DEFAULT '',
    role          VARCHAR(32),
    profile_pic   VARCHAR(255) DEFAULT '',
    allowed_pages TEXT,
    can_delete    TINYINT NOT NULL DEFAULT 1,
    created_at    VARCHAR(40) NOT NULL,
    updated_at    VARCHAR(40)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS allowed_emails (
    email     VARCHAR(190) NOT NULL PRIMARY KEY,
    added_by  VARCHAR(190),
    added_at  VARCHAR(40) NOT NULL,
    barred    INT NOT NULL DEFAULT 0,
    barred_by VARCHAR(190),
    barred_at VARCHAR(40)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS otp_codes (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    email      VARCHAR(190) NOT NULL,
    purpose    VARCHAR(32)  NOT NULL,
    code_hash  VARCHAR(255) NOT NULL,
    expires_at VARCHAR(40)  NOT NULL,
    used       INT NOT NULL DEFAULT 0,
    created_at VARCHAR(40)  NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS activity_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_email VARCHAR(190),
    user_name  VARCHAR(190),
    action     VARCHAR(64) NOT NULL,
    entity     VARCHAR(160),
    details    MEDIUMTEXT,  -- old/new JSON snapshots of what an editor changed; can be large for bulk uploads
    timestamp  VARCHAR(40) NOT NULL,
    KEY idx_activity_ts (timestamp)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS todo_jobs (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    subject      VARCHAR(255) NOT NULL,
    details      TEXT,
    recipient    VARCHAR(255),
    due_date     VARCHAR(10) NOT NULL,
    priority     VARCHAR(16) NOT NULL DEFAULT 'medium',
    status       VARCHAR(16) NOT NULL DEFAULT 'pending',
    created_at   VARCHAR(40) NOT NULL,
    completed_at VARCHAR(40),
    remark       TEXT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS daily_work_log (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    work_date   VARCHAR(10) NOT NULL,
    description TEXT NOT NULL,
    remarks     TEXT,
    created_at  VARCHAR(40) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ipt_data_json (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    report_month CHAR(7) NOT NULL UNIQUE,
    data JSON NOT NULL,
    source VARCHAR(32) DEFAULT 'excel',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS production_data_json (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    report_month CHAR(7) NOT NULL UNIQUE,
    data JSON NOT NULL,
    source VARCHAR(32) DEFAULT 'excel',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS production_plan_json (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    report_month CHAR(7) NOT NULL UNIQUE,
    data JSON NOT NULL,
    source VARCHAR(32) DEFAULT 'excel',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS special_steel_json (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    report_month CHAR(7) NOT NULL UNIQUE,
    data JSON NOT NULL,
    source VARCHAR(32) DEFAULT 'excel',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS stock_data_json (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_month CHAR(7) NOT NULL UNIQUE,
    data JSON NOT NULL,
    source VARCHAR(32) DEFAULT 'excel',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Page 3 Production Narrative + Highlights, keyed only by report_month —
-- independent of page_configs so saving it never touches the other 34
-- pages' saved data for the month.
CREATE TABLE IF NOT EXISTS page3_narrative (
    report_month          CHAR(7) NOT NULL PRIMARY KEY,
    production_narrative  TEXT,
    highlights            TEXT,
    updated_at            DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- "Key Highlights & Variances" page narrative — Major Achievements / Major
-- Shortfalls / Focus Areas Going Forward, keyed only by report_month, same
-- independent-of-page_configs rationale as page3_narrative above. See
-- page_key_highlights.py / api_key_highlights.py.
CREATE TABLE IF NOT EXISTS key_highlights_narrative (
    report_month   CHAR(7) NOT NULL PRIMARY KEY,
    achievements   TEXT,
    shortfalls     TEXT,
    focus_areas    TEXT,
    updated_by     VARCHAR(190),
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Large BF Benchmarking — static Working Volume for SAIL's 3 fixed large
-- BFs (BSP BF-8, RSP BF-5, ISP BF-5). Their monthly operating data already
-- lives in techno_data; only Working Volume (rarely changes) is here.
CREATE TABLE IF NOT EXISTS bf_benchmark_sail_meta (
    plant             VARCHAR(32) NOT NULL,
    unit              VARCHAR(32) NOT NULL,
    working_volume_m3 DOUBLE,
    updated_at        VARCHAR(40),
    PRIMARY KEY (plant, unit)
) ENGINE=InnoDB;

-- Large BF Benchmarking — registry of non-SAIL large BFs added for
-- comparison. Soft-deactivate via `active` (mirrors allowed_emails.barred)
-- — no hard delete. `company` (e.g. "JSW") and `location` (e.g.
-- "Vijaynagar") are separate so the comparison table can group columns
-- Company -> Location -> Furnace. NOTE: `location` was added after this
-- table already existed in prod — for an existing live DB, run
-- scripts/migrate_add_bf_benchmark_location.sql instead of relying on this
-- CREATE TABLE (IF NOT EXISTS is a no-op against an existing table).
CREATE TABLE IF NOT EXISTS bf_benchmark_external_bf (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    name              VARCHAR(190) NOT NULL,
    company           VARCHAR(190) DEFAULT '',
    location          VARCHAR(190) DEFAULT '',
    working_volume_m3 DOUBLE,
    active            TINYINT NOT NULL DEFAULT 1,
    created_at        VARCHAR(40) NOT NULL,
    created_by        VARCHAR(190) DEFAULT ''
) ENGINE=InnoDB;

-- Large BF Benchmarking — one entered figure set per non-SAIL BF per
-- Financial Year (non-SAIL BFs only ever publish FY-level figures, not
-- monthly ones). Despite the column name (kept as-is; CHAR(7) already fits
-- both), `report_month` holds an FY label here, e.g. "2025-26", not a
-- calendar month. param_json holds {param_key: value} for the dynamic
-- params — new params later are just another JSON key, no migration needed.
CREATE TABLE IF NOT EXISTS bf_benchmark_external_data (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    external_bf_id  BIGINT NOT NULL,
    report_month    CHAR(7) NOT NULL,
    param_json      JSON NOT NULL,
    created_at      VARCHAR(40),
    updated_at      VARCHAR(40),
    UNIQUE KEY uq_bf_benchmark_ext (external_bf_id, report_month)
) ENGINE=InnoDB;
