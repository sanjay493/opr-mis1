-- One-time migration: adds the tables behind the new "Special Steel Plants
-- Physical Performance" report page (ASP/SSP/VISP multi-year crude/saleable/
-- stainless/carbon history + the annual "IPT requirement" list), plus its
-- free-text notes. Source: Report_format/Special Steel Production history
-- comprehensive.pdf. See backend/page_special_steel_physical.py.
--
-- Additive only — no existing table, column, or report page is affected.
-- Safe to re-run (CREATE TABLE IF NOT EXISTS).
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_add_special_steel_physical.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

-- Per (FY, plant, series) history value. metric 'actual' = achieved,
-- 'plan' = that FY's annual plan (APP / ABP). Values in '000 T (repo-wide
-- convention). Crude/Saleable 'actual' rows are seeded/refreshed from
-- production_table by backfill_special_steel_physical.py; everything else is
-- manually maintained via /data-entry/special-steel-physical.
CREATE TABLE IF NOT EXISTS special_steel_phys_perf (
    financial_year CHAR(7)     NOT NULL,   -- 'YYYY-YY', e.g. '2014-15'
    plant          VARCHAR(8)  NOT NULL,   -- 'ASP' | 'SSP' | 'VISP'
    series         VARCHAR(16) NOT NULL,   -- 'CRUDE' | 'SALEABLE' | 'STAINLESS' | 'CARBON'
    metric         VARCHAR(8)  NOT NULL,   -- 'actual' | 'plan'
    value_kt       DOUBLE,
    PRIMARY KEY (financial_year, plant, series, metric)
) ENGINE=InnoDB;

-- Per (plant, series) static-ish header cells: installed Capacity and the
-- Best-Ever Achieved actual + the FY it was achieved in. best_* is seeded
-- from the PDF and bumped by the backfill if production_table shows a higher
-- FY total.
CREATE TABLE IF NOT EXISTS special_steel_phys_meta (
    plant          VARCHAR(8)   NOT NULL,
    series         VARCHAR(16)  NOT NULL,
    capacity_kt    DOUBLE,
    best_actual_kt DOUBLE,
    best_year      CHAR(7),
    remark         VARCHAR(200),
    sort_order     INT NOT NULL DEFAULT 0,
    PRIMARY KEY (plant, series)
) ENGINE=InnoDB;

-- Free-text footnotes shown under the grid, scoped to the FY the report is
-- being run for (so they can change year to year). sort_order = display order.
CREATE TABLE IF NOT EXISTS special_steel_phys_note (
    financial_year CHAR(7)      NOT NULL,
    sort_order     INT          NOT NULL,
    note_text      VARCHAR(500) NOT NULL,
    PRIMARY KEY (financial_year, sort_order)
) ENGINE=InnoDB;

-- The annual "Special Steel Plants IPT requirement" list — one row per
-- (FY, item, from, to). plan_kt in '000 T. Distinct from the monthly
-- ipt_table. Edited via /data-entry/special-steel-ipt.
CREATE TABLE IF NOT EXISTS special_steel_ipt_requirement (
    financial_year CHAR(7)     NOT NULL,
    item           VARCHAR(64) NOT NULL,
    from_plant     VARCHAR(8)  NOT NULL,
    to_plant       VARCHAR(8)  NOT NULL,
    plan_kt        DOUBLE,
    sort_order     INT NOT NULL DEFAULT 0,
    PRIMARY KEY (financial_year, item, from_plant, to_plant)
) ENGINE=InnoDB;
