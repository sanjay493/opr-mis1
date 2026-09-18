-- One-time migration: adds the steel_sales_highlights table, backing the
-- new "Steel Sales Performance" report page (inserted right after "SAIL
-- Performance - 1 Page Summary" — see STEEL_SALES_PAGE_ID in
-- backend/main.py). Stores the page's two bullet lists (report-month and
-- Apr-to-report-month YTD Key Performance Parameters — Cash Collection,
-- Total/LP/FP+PET Sales, despatch figures, etc., modeled on
-- Report_format/RMT_0109_partial.pdf), entered by an editor/admin via
-- /data-entry/steel-sales-highlights — nothing here is computed.
--
-- Purely additive — a brand-new, empty table. No existing table or row is
-- touched.
--
-- Run against the live DB after a fresh backup:
--   D:\mysql\backup_mysql.bat
--   mysql -u root -p mis_reports < backend/scripts/migrate_add_steel_sales_highlights.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

CREATE TABLE IF NOT EXISTS steel_sales_highlights (
    report_month   CHAR(7) NOT NULL PRIMARY KEY,
    month_items    TEXT,
    ytd_items      TEXT,
    updated_by     VARCHAR(190),
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
