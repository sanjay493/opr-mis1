-- One-time migration: adds the tables behind the new "Rail Production &
-- Dispatch from BSP" report page (page 18.5, right after Segment Wise
-- Production, before the Special Steel plant pages), plus its footer
-- remarks. Source: Report_format/"Rail Prod & Despatch Report for OMI.pdf".
-- See backend/page_rail_report.py.
--
-- Additive only — no existing table, column, or report page is affected.
-- Safe to re-run (CREATE TABLE IF NOT EXISTS).
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_add_rail_report.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

-- One row per (financial_year, metric). 9 metrics are entered directly via
-- /data-entry/rail-report; the FY containing the report month holds a
-- running Apr-<report month> cumulative in the same row (not auto-summed).
-- note is optional free text riding along a value (e.g. R350HT's "9 Rakes").
CREATE TABLE IF NOT EXISTS rail_prod_despatch (
    financial_year CHAR(7)     NOT NULL,   -- 'YYYY-YY', e.g. '2015-16'
    metric         VARCHAR(32) NOT NULL,   -- see page_rail_report.py's RAW_METRIC_CODES
    value          DOUBLE,
    note           VARCHAR(64),
    PRIMARY KEY (financial_year, metric)
) ENGINE=InnoDB;

-- Free-text footer remarks shown under the table — standing footnotes (not
-- scoped to a FY, since they document one-time events that stay relevant
-- regardless of which month the report is run for). sort_order = display
-- order.
CREATE TABLE IF NOT EXISTS rail_prod_despatch_note (
    sort_order INT          PRIMARY KEY,
    note_text  VARCHAR(500) NOT NULL
) ENGINE=InnoDB;

-- Seed the 3 standing remarks from the source PDF.
INSERT INTO rail_prod_despatch_note (sort_order, note_text) VALUES
    (1, 'During 2021-22, Rail Grade/Profile for 60-kg Rails was changed from 880-UIC60 to R260-60E1 wef 12.04.21 in URM & wef 07.05.21 in RSM. However, 52-kg Rails continue to be produced in Grade 880 only at RSM.'),
    (2, 'Commercial Rolling of 1175HT Rails started in 2023-24 (Oct''23).'),
    (3, 'Operations started at Sabarmati FBW Plant wef Sept''23.')
ON DUPLICATE KEY UPDATE note_text = VALUES(note_text);
