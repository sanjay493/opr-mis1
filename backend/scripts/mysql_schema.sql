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

CREATE TABLE IF NOT EXISTS page_configs (
    report_month CHAR(7) NOT NULL,
    page_number  INT     NOT NULL,
    page_data    MEDIUMTEXT,
    PRIMARY KEY (report_month, page_number)
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

CREATE TABLE IF NOT EXISTS stock_table (
    stock_month CHAR(7)     NOT NULL,
    plant_name  VARCHAR(32) NOT NULL,
    item_type   VARCHAR(64) NOT NULL,
    stock_type  VARCHAR(64) NOT NULL DEFAULT '',
    stock       DOUBLE,
    PRIMARY KEY (stock_month, plant_name, item_type, stock_type)
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
    details    TEXT,
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
