-- One-time migration (2026-10-05): link a breakdown-log entry to the
-- capital repair it really is. Plants often log a capital repair in the
-- breakdown log too (exact date-times + a remark naming it); with the link
-- set, every report counts the event once, as the CR (see bd_cr_link.py).
-- Additive/nullable only - no existing column, row, or report page changes.
-- Safe to re-run: the column/index are only added when missing.
--
-- Run against the live DB after a fresh backup:
--   D:\mysql\backup_mysql.bat
--   mysql -u root -p mis_reports < backend/scripts/migrate_add_breakdown_cr_link.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'breakdown_table'
                     AND COLUMN_NAME = 'capital_repair_id');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE breakdown_table ADD COLUMN capital_repair_id BIGINT NULL AFTER hours_lost_override, ADD KEY idx_breakdown_cr (capital_repair_id)',
  'SELECT ''capital_repair_id already present''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
