-- migrate_add_rail_loading.sql -- 2026-11-15
-- Adds rail_loading_monthly (SAIL's monthly rail loading by commodity, MIS PDF
-- page 40.05; loaded by scripts/load_rail_loading_highlights.py). Applied to
-- mis_reports_v2. schema_v2.sql has the same table. New table only: no
-- existing data changes.
CREATE TABLE IF NOT EXISTS rail_loading_monthly (
    report_month CHAR(7)     NOT NULL,
    item_code    VARCHAR(32) NOT NULL,
    rakes        DOUBLE      NULL,
    updated_at   DATETIME    NOT NULL,
    updated_by   VARCHAR(64) NULL,
    PRIMARY KEY (report_month, item_code),
    CONSTRAINT fk_rail_loading_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
