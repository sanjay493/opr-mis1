-- One-time migration: adds a `tracks_actual` flag to mine_end_uses_master
-- and seeds a new "Unallocated" despatch end-use (per direct instruction,
-- 2026-10-17) -- a despatch-PLAN quantity per mine/material/month that has
-- no destination yet, entered so it still counts toward a mine's Total
-- Despatch Plan without being attributed to Captive/Sales/Pellet Conversion.
-- tracks_actual=0 tells the entry form to show only a Plan field for it (no
-- Rail/Road Actual columns, unlike the other three end-uses).
--
-- No new table: UNALLOCATED's Plan values live in the existing
-- mines_despatch_plan_monthly table like any other end_use_code. It never
-- gets an Actual row (the entry form won't render Actual inputs for it), so
-- mines_despatch_actual_monthly is untouched.
--
-- Additive only -- no existing table, column, or report page is affected;
-- Captive/Sales/Pellet Conversion rows just get tracks_actual=1 explicitly.
-- Safe to re-run: the column is only added when missing, and the new row
-- uses INSERT IGNORE.
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_add_mines_despatch_unallocated.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mine_end_uses_master'
                     AND COLUMN_NAME = 'tracks_actual');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE mine_end_uses_master ADD COLUMN tracks_actual TINYINT(1) NOT NULL DEFAULT 1',
  'SELECT ''tracks_actual already present''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE mine_end_uses_master SET tracks_actual = 1
  WHERE end_use_code IN ('CAPTIVE', 'SALES', 'PELLET_CONV');

INSERT IGNORE INTO mine_end_uses_master (end_use_code, end_use_name, sort_order, tracks_actual) VALUES
 ('UNALLOCATED', 'Unallocated', 4, 0);
