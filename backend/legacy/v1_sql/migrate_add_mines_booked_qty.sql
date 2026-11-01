-- One-time migration: adds Booked Quantity — Sales to 3rd Party tables
-- (mine-level, per direct instruction 2026-08-26) — replaces the old flat
-- "Auction" item on the SAIL Mines Entry form's Sales of Iron Ore table.
-- Implicitly SALES-only (no end_use_code column — booking a sale doesn't
-- apply to Captive transfers or Pellet Conversion). Same Actual-per-mode /
-- Plan-with-no-mode-split grain as mines_despatch_actual_monthly /
-- mines_despatch_plan_monthly.
--
-- Additive only — no existing table, column, or report page is affected.
-- Safe to re-run (CREATE TABLE IF NOT EXISTS).
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_add_mines_booked_qty.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

CREATE TABLE IF NOT EXISTS mines_booked_qty_actual_monthly (
    report_month    CHAR(7)     NOT NULL,
    mine_code       VARCHAR(24) NOT NULL,
    material_code   VARCHAR(16) NOT NULL,
    transport_mode  VARCHAR(8)  NOT NULL,
    qty_actual      DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code, transport_mode),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mines_booked_qty_plan_monthly (
    report_month  CHAR(7)     NOT NULL,
    mine_code     VARCHAR(24) NOT NULL,
    material_code VARCHAR(16) NOT NULL,
    qty_plan      DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code)
) ENGINE=InnoDB;

CREATE INDEX idx_mines_booked_qty_actual_material ON mines_booked_qty_actual_monthly (report_month, material_code);
CREATE INDEX idx_mines_booked_qty_plan_material   ON mines_booked_qty_plan_monthly (report_month, material_code);
