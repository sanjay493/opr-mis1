-- One-time migration: adds the `location` column to bf_benchmark_external_bf
-- (Large BF Benchmarking's non-SAIL BF registry), so each non-SAIL BF can
-- carry Company (e.g. "JSW") and Location (e.g. "Vijaynagar") separately —
-- needed for the comparison table's Company -> Location -> Furnace column
-- grouping. Additive/nullable only — no existing column or row is affected.
--
-- Existing rows get location='' (blank): any BF added before this migration
-- (e.g. company="JSW Vijaynagar" as one combined string) needs its Company
-- and Location re-split by hand via the /data-entry/bf-benchmark edit form
-- afterward — this migration does not attempt to parse/split existing data.
--
-- Run against the live DB after a fresh backup:
--   D:\mysql\backup_mysql.bat
--   mysql -u root -p mis_reports < backend/scripts/migrate_add_bf_benchmark_location.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

ALTER TABLE bf_benchmark_external_bf
  ADD COLUMN location VARCHAR(190) DEFAULT '' AFTER company;
