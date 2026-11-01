-- One-time migration: adds the table behind the new "Annexure-III : 5 ISPs
-- Major Units Records" report section's Daily best-ever production
-- figures. Annual/Monthly bests are computed live from production_table
-- (never stored) — see backend/page_major_unit_records.py's module
-- docstring. Source: Report_format/Plants Best/{BSL,RSP,ISP,BSP}.xlsx
-- (DSP's file hasn't been provided yet).
--
-- Additive only — no existing table, column, or report page is affected.
-- Safe to re-run (CREATE TABLE IF NOT EXISTS).
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_add_major_unit_daily_record.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

CREATE TABLE IF NOT EXISTS major_unit_daily_record (
    plant_code      VARCHAR(8)  NOT NULL,
    unit_label      VARCHAR(64) NOT NULL,
    unit_of_measure VARCHAR(16),
    value           DOUBLE,
    record_date     VARCHAR(10),   -- 'YYYY-MM-DD' where cleanly parseable
    remarks         TEXT,
    sort_order      INT NOT NULL DEFAULT 0,
    updated_by      VARCHAR(128),
    updated_at      VARCHAR(32),
    PRIMARY KEY (plant_code, unit_label)
) ENGINE=InnoDB;
