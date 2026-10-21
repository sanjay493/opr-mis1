-- One-time migration: two read indexes for the report build.
--   production_table (item_name, report_month): item-first history / range
--     queries (records, trends) that do not filter on plant.
--   extraction_log (report_month): production_month_status (page 4's
--     "tentative" flag) filters on report_month.
--
-- Additive only. Safe to re-run: each index is created only when missing.
--
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_add_perf_indexes.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

SET @s = (SELECT IF(COUNT(*) = 0,
    'CREATE INDEX idx_prod_item_month ON production_table (item_name, report_month)',
    'DO 0')
  FROM information_schema.statistics
  WHERE table_schema = DATABASE() AND table_name = 'production_table'
    AND index_name = 'idx_prod_item_month');
PREPARE stmt FROM @s;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @s = (SELECT IF(COUNT(*) = 0,
    'CREATE INDEX idx_extraction_month ON extraction_log (report_month)',
    'DO 0')
  FROM information_schema.statistics
  WHERE table_schema = DATABASE() AND table_name = 'extraction_log'
    AND index_name = 'idx_extraction_month');
PREPARE stmt FROM @s;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
