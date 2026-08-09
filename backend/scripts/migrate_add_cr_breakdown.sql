-- One-time migration: adds the structured Capital Repair columns and the
-- new breakdown_table needed by production_loss_analysis.py.
-- Additive/nullable only — no existing column, row, or report page is
-- affected. Safe to re-run (guarded with IF NOT EXISTS / a dynamic check
-- for MySQL 8, which lacks IF NOT EXISTS on ADD COLUMN before 8.0.29).
--
-- Run against the live DB after a fresh backup:
--   D:\mysql\backup_mysql.bat
--   mysql -u root -p mis_reports < backend/scripts/migrate_add_cr_breakdown.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

ALTER TABLE capital_repair_table
  ADD COLUMN unit_type      VARCHAR(16)  NULL AFTER equipment,
  ADD COLUMN unit_name      VARCHAR(32)  NULL AFTER unit_type,
  ADD COLUMN sms_subtag     VARCHAR(16)  NULL AFTER unit_name,
  ADD COLUMN actual_start   CHAR(10)     NULL AFTER schedule_days,
  ADD COLUMN actual_end     CHAR(10)     NULL AFTER actual_start,
  ADD COLUMN actual_ongoing TINYINT(1)   NOT NULL DEFAULT 0 AFTER actual_end,
  ADD COLUMN planned_days   DOUBLE       NULL AFTER actual_ongoing;

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
