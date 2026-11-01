-- One-time migration: adds the tables behind the new "Details of Rakes
-- Detention Plant Wise" report section (4 pages, right after Status of
-- Capital/Major Repairs Planned in ABP, before the Annexures). Source:
-- SAIL Rail Movement Cell's "Average Plant Detention Report" (sample month:
-- Aug'26). See backend/page_rake_detention.py.
--
-- Additive only — no existing table, column, or report page is affected.
-- Safe to re-run (CREATE TABLE IF NOT EXISTS).
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_add_rake_detention.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape,
-- and backend/scripts/backfill_rake_detention.py for the one-time seed of
-- master rows + Aug'26 (and historical trend) values from the sample PDF.

-- Row registry: which (plant, section, commodity, wagon type) rows exist.
-- Split out from the actual monthly figures (rake_detention_monthly) so a
-- new wagon type can be added for a plant later without a code change —
-- same split as special_steel_phys_meta / special_steel_phys_perf.
CREATE TABLE IF NOT EXISTS rake_detention_master (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    plant                   VARCHAR(8)  NOT NULL,
    section                 VARCHAR(8)  NOT NULL,   -- INWARD / OUTWARD / OVERALL
    commodity               VARCHAR(48),            -- NULL for Outward/Overall/total rows
    wagon_type              VARCHAR(24),            -- NULL for a section's own total row
    row_label               VARCHAR(48) NOT NULL,   -- display label: wagon_type, or "Total Inward" etc.
    is_total                TINYINT(1)  NOT NULL DEFAULT 0,
    direction               VARCHAR(4),             -- L-E / E-L
    freetime_hours          DOUBLE,
    freetime_effective_from CHAR(10),               -- 'YYYY-MM-DD'
    sort_order              INT         NOT NULL DEFAULT 0,
    is_active               TINYINT(1)  NOT NULL DEFAULT 1
) ENGINE=InnoDB;

-- One row per (report_month, master row) — a master row with no entry for
-- a given month simply renders blank, matching the source PDF's blank
-- not-yet-reported months. The "Overall Wagon" master row alone carries
-- page 4's multi-year trend back to 2021-22 even though the granular
-- commodity/wagon breakdown (pages 1-2) only realistically exists for
-- recent months.
CREATE TABLE IF NOT EXISTS rake_detention_monthly (
    report_month CHAR(7) NOT NULL,
    master_id    INT     NOT NULL,
    value_hours  DOUBLE,
    PRIMARY KEY (report_month, master_id),
    FOREIGN KEY (master_id) REFERENCES rake_detention_master(id)
) ENGINE=InnoDB;

-- "Improvement in Average Detention per Wagon in Hrs" — the source
-- report's own 3-period (current month / YTD / full FY) CPLY comparison
-- table, entered directly per its "UPTO <report_month>" heading rather
-- than derived from rake_detention_monthly (its totals are rake-count-
-- weighted, a figure we don't have).
CREATE TABLE IF NOT EXISTS rake_detention_summary (
    report_month CHAR(7)     NOT NULL,
    period_row   VARCHAR(24) NOT NULL,   -- see page_rake_detention.py's PERIOD_ROWS
    plant        VARCHAR(8)  NOT NULL,
    value        DOUBLE,
    PRIMARY KEY (report_month, period_row, plant)
) ENGINE=InnoDB;

-- Page 4's own "APR-MAR" full-FY average column, per plant per FY — a 13th
-- figure alongside that row's 12 months, entered directly rather than
-- averaged from them (the source PDF's own figure doesn't always equal a
-- straight mean of its already-rounded displayed monthly values).
CREATE TABLE IF NOT EXISTS rake_detention_annual (
    plant          VARCHAR(8) NOT NULL,
    financial_year CHAR(7)    NOT NULL,
    avg_hours      DOUBLE,
    PRIMARY KEY (plant, financial_year)
) ENGINE=InnoDB;
