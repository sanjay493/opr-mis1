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

-- "Special Steel Plants Physical Performance" report (ASP/SSP/VISP multi-year
-- crude/saleable/stainless/carbon history + annual IPT-requirement list).
-- See backend/page_special_steel_physical.py and
-- backend/scripts/migrate_add_special_steel_physical.sql. Values in '000 T.
CREATE TABLE IF NOT EXISTS special_steel_phys_perf (
    financial_year CHAR(7)     NOT NULL,
    plant          VARCHAR(8)  NOT NULL,
    series         VARCHAR(16) NOT NULL,
    metric         VARCHAR(8)  NOT NULL,
    value_kt       DOUBLE,
    PRIMARY KEY (financial_year, plant, series, metric)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS special_steel_phys_meta (
    plant          VARCHAR(8)   NOT NULL,
    series         VARCHAR(16)  NOT NULL,
    capacity_kt    DOUBLE,
    best_actual_kt DOUBLE,
    best_year      CHAR(7),
    remark         VARCHAR(200),
    sort_order     INT NOT NULL DEFAULT 0,
    PRIMARY KEY (plant, series)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS special_steel_phys_note (
    financial_year CHAR(7)      NOT NULL,
    sort_order     INT          NOT NULL,
    note_text      VARCHAR(500) NOT NULL,
    PRIMARY KEY (financial_year, sort_order)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS special_steel_ipt_requirement (
    financial_year CHAR(7)     NOT NULL,
    item           VARCHAR(64) NOT NULL,
    from_plant     VARCHAR(8)  NOT NULL,
    to_plant       VARCHAR(8)  NOT NULL,
    plan_kt        DOUBLE,
    sort_order     INT NOT NULL DEFAULT 0,
    PRIMARY KEY (financial_year, item, from_plant, to_plant)
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

CREATE TABLE IF NOT EXISTS item_capacity_table (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    plant_name       VARCHAR(8)   NOT NULL,
    item_name        VARCHAR(64)  NOT NULL,
    effective_month  CHAR(7)      NOT NULL,
    annual_capacity  DOUBLE       NOT NULL,
    reason           VARCHAR(255) DEFAULT '',
    created_by       VARCHAR(190),
    created_at       VARCHAR(40),
    updated_by       VARCHAR(190),
    updated_at       VARCHAR(40),
    UNIQUE KEY uq_capacity_plant_item_month (plant_name, item_name, effective_month)
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

-- Cost Trend (Report_format/COST TREND.xlsx, sheets HM/CS/SS) — closed-FY
-- annual figures (entered once per FY, never revised monthly) and
-- current-FY monthly figures (month + till_month entered directly, same
-- convention as techno_data/Demurrage — a till_month figure isn't always a
-- clean sum of the monthly ones). product is 'HM'/'CS'/'SS' (Hot Metal/
-- Crude Steel/Saleable Steel); cost_type is 'TOTAL'/'VARIABLE'/'FIXED';
-- plant is BSP/DSP/RSP/BSL/ISP plus the workbook's own 'SAIL' aggregate row.
CREATE TABLE IF NOT EXISTS cost_trend_annual (
    fy         CHAR(7)     NOT NULL,
    product    VARCHAR(8)  NOT NULL,
    cost_type  VARCHAR(16) NOT NULL,
    plant      VARCHAR(16) NOT NULL,
    value      DOUBLE,
    PRIMARY KEY (fy, product, cost_type, plant)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cost_trend_monthly (
    report_month      CHAR(7)     NOT NULL,
    product           VARCHAR(8)  NOT NULL,
    cost_type         VARCHAR(16) NOT NULL,
    plant             VARCHAR(16) NOT NULL,
    month_value       DOUBLE,
    till_month_value  DOUBLE,
    PRIMARY KEY (report_month, product, cost_type, plant)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sail_mines_monthly (
    report_month  CHAR(7)     NOT NULL,
    section       VARCHAR(24) NOT NULL,
    item          VARCHAR(32) NOT NULL,
    month_actual  DOUBLE,
    month_plan    DOUBLE,
    PRIMARY KEY (report_month, section, item)
) ENGINE=InnoDB;

-- Iron Ore Mines Production & Despatch — mine-level detail (11 mines under
-- JGoM/OGoM/CGoM). Master tables are DB-backed (not a Python registry) so a
-- mine/material/end-use can be added/renamed/deactivated via a data change.
-- See backend/scripts/migrate_add_mines_production_despatch.sql for the
-- matching post-cutover migration and seed data.
CREATE TABLE IF NOT EXISTS mine_groups_master (
    group_code  VARCHAR(8)  PRIMARY KEY,
    group_name  VARCHAR(64) NOT NULL,
    sort_order  INT         NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mines_master (
    mine_code   VARCHAR(24) PRIMARY KEY,
    mine_name   VARCHAR(64) NOT NULL,
    group_code  VARCHAR(8)  NOT NULL,
    is_active   TINYINT(1)  NOT NULL DEFAULT 1,
    sort_order  INT         NOT NULL,
    FOREIGN KEY (group_code) REFERENCES mine_groups_master(group_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mine_materials_master (
    material_code               VARCHAR(16) PRIMARY KEY,
    material_name                VARCHAR(32) NOT NULL,
    material_category            VARCHAR(16) NOT NULL,
    has_production                TINYINT(1)  NOT NULL DEFAULT 0,
    counts_in_total_production    TINYINT(1)  NOT NULL DEFAULT 0,
    sort_order                    INT         NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mine_end_uses_master (
    end_use_code  VARCHAR(16) PRIMARY KEY,
    end_use_name  VARCHAR(48) NOT NULL,
    sort_order    INT         NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mines_production_monthly (
    report_month  CHAR(7)     NOT NULL,
    mine_code     VARCHAR(24) NOT NULL,
    material_code VARCHAR(16) NOT NULL,
    qty_actual    DOUBLE,
    qty_plan      DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code)
) ENGINE=InnoDB;

-- Despatch Actual and Plan are different grains (per direct instruction):
-- Actual is tracked per transport_mode (Rail/Road actually despatched);
-- Plan is a single target per material x end_use with NO Rail/Road split.
CREATE TABLE IF NOT EXISTS mines_despatch_actual_monthly (
    report_month    CHAR(7)     NOT NULL,
    mine_code       VARCHAR(24) NOT NULL,
    material_code   VARCHAR(16) NOT NULL,
    transport_mode  VARCHAR(8)  NOT NULL,
    end_use_code    VARCHAR(16) NOT NULL,
    qty_actual      DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code, transport_mode, end_use_code),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code),
    FOREIGN KEY (end_use_code) REFERENCES mine_end_uses_master(end_use_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mines_despatch_plan_monthly (
    report_month  CHAR(7)     NOT NULL,
    mine_code     VARCHAR(24) NOT NULL,
    material_code VARCHAR(16) NOT NULL,
    end_use_code  VARCHAR(16) NOT NULL,
    qty_plan      DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code, end_use_code),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code),
    FOREIGN KEY (end_use_code) REFERENCES mine_end_uses_master(end_use_code)
) ENGINE=InnoDB;

CREATE INDEX idx_mines_despatch_actual_material ON mines_despatch_actual_monthly (report_month, material_code);
CREATE INDEX idx_mines_despatch_actual_enduse   ON mines_despatch_actual_monthly (report_month, end_use_code);
CREATE INDEX idx_mines_despatch_plan_material   ON mines_despatch_plan_monthly (report_month, material_code);

-- Booked Quantity — Sales to 3rd Party. Implicitly SALES-only (no
-- end_use_code — booking a sale doesn't apply to Captive/Pellet
-- Conversion). Same Actual-per-mode / Plan-with-no-mode-split grain as
-- despatch. Replaces the old flat "Auction" item on the SAIL Mines Entry
-- form's Sales of Iron Ore table.
CREATE TABLE IF NOT EXISTS mines_booked_qty_actual_monthly (
    report_month    CHAR(7)     NOT NULL,
    mine_code       VARCHAR(24) NOT NULL,
    material_code   VARCHAR(16) NOT NULL,
    transport_mode  VARCHAR(8)  NOT NULL,
    qty_actual      DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code, transport_mode),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mines_booked_qty_plan_monthly (
    report_month  CHAR(7)     NOT NULL,
    mine_code     VARCHAR(24) NOT NULL,
    material_code VARCHAR(16) NOT NULL,
    qty_plan      DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code)
) ENGINE=InnoDB;

CREATE INDEX idx_mines_booked_qty_actual_material ON mines_booked_qty_actual_monthly (report_month, material_code);
CREATE INDEX idx_mines_booked_qty_plan_material   ON mines_booked_qty_plan_monthly (report_month, material_code);

INSERT IGNORE INTO mine_groups_master (group_code, group_name, sort_order) VALUES
 ('JGoM','Jharkhand Group of Mines',1), ('OGoM','Orissa Group of Mines',2), ('CGoM','Chhattisgarh Group of Mines',3);

INSERT IGNORE INTO mines_master (mine_code, mine_name, group_code, sort_order) VALUES
 ('KIRIBURU','Kiriburu','JGoM',1), ('MEGHAHATUBURU','Meghahatuburu','JGoM',2),
 ('GUA','Gua','JGoM',3), ('MANOHARPUR','Manoharpur','JGoM',4),
 ('BOLANI','Bolani','OGoM',5), ('BARSUA','Barsua','OGoM',6),
 ('TALDIH','Taldih','OGoM',7), ('KALTA','Kalta','OGoM',8),
 ('RAJHARA','Rajhara','CGoM',9), ('DALLI','Dalli','CGoM',10), ('ROWGHAT','Rowghat','CGoM',11);

INSERT IGNORE INTO mine_materials_master
 (material_code, material_name, material_category, has_production, counts_in_total_production, sort_order) VALUES
 ('LUMP','Lump','FRESH',1,1,1), ('FINES','Fines','FRESH',1,1,2),
 ('DUMP_FINES','Dump Fines','LEGACY',0,1,3), ('PELLETS','Pellets','LEGACY',0,1,4), ('TAILINGS','Tailings','LEGACY',0,1,5);

INSERT IGNORE INTO mine_end_uses_master (end_use_code, end_use_name, sort_order) VALUES
 ('CAPTIVE','Captive Plants',1), ('SALES','Sales to 3rd Party',2), ('PELLET_CONV','Pellet Conversion Agents',3);
