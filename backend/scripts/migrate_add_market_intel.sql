-- One-time migration: adds the tables behind the two new "Movement of Key
-- Prices - International" (page 2.41) and "India Macro Economic
-- Indicators" (page 2.42) report pages, inserted right before "SAIL
-- Performance - At a Glance". Source: Report_format/work/
-- "DC-2 pages.pdf" (a BigMint market-intelligence snapshot). See
-- backend/page_market_prices.py, backend/page_macro_indicators.py,
-- backend/scripts/backfill_market_intel.py.
--
-- Additive only — no existing table, column, or report page is affected.
-- Safe to re-run (CREATE TABLE IF NOT EXISTS).
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_add_market_intel.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

-- One row per (report_month, series_code) — Raw Materials / Finished Steel
-- price series, USD/T. series_code registry: page_market_prices.py's
-- SERIES_CODES. Entered via /data-entry/market-intel going forward.
CREATE TABLE IF NOT EXISTS market_price_trend_monthly (
    report_month CHAR(7)     NOT NULL,   -- 'YYYY-MM'
    series_code  VARCHAR(48) NOT NULL,
    value        DOUBLE,
    PRIMARY KEY (report_month, series_code)
) ENGINE=InnoDB;

-- One row per (report_month, metric_code) — India macro-economic key
-- parameters. metric_code registry: page_macro_indicators.py's
-- METRIC_CODES. Entered via /data-entry/market-intel going forward.
CREATE TABLE IF NOT EXISTS macro_indicators_monthly (
    report_month CHAR(7)     NOT NULL,
    metric_code  VARCHAR(32) NOT NULL,
    value        DOUBLE,
    PRIMARY KEY (report_month, metric_code)
) ENGINE=InnoDB;
