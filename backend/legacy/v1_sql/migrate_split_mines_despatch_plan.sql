-- One-time migration: splits mines_despatch_monthly into two tables because
-- Despatch Actual and Plan turned out to be different grains (per direct
-- instruction, 2026-08-26): Actual is tracked per transport_mode (Rail/Road
-- actually despatched), but Plan is a single target per material x end_use
-- with NO Rail/Road split. mines_despatch_actual_monthly keeps the original
-- 5-column key (+ qty_actual); mines_despatch_plan_monthly drops
-- transport_mode from the key (+ qty_plan).
--
-- Existing rows in mines_despatch_monthly are migrated, not discarded:
-- qty_actual rows go to the new Actual table as-is; any non-null qty_plan
-- values are collapsed (MAX, since a real split value was never actually
-- entered under the old schema) into the new Plan table. The old table is
-- then dropped — safe only because every row is copied out first in this
-- same script.
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_split_mines_despatch_plan.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

CREATE TABLE IF NOT EXISTS mines_despatch_actual_monthly (
    report_month    CHAR(7)     NOT NULL,
    mine_code       VARCHAR(24) NOT NULL,
    material_code   VARCHAR(16) NOT NULL,
    transport_mode  VARCHAR(8)  NOT NULL,
    end_use_code    VARCHAR(16) NOT NULL,
    qty_actual      DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code, transport_mode, end_use_code),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code),
    FOREIGN KEY (end_use_code) REFERENCES mine_end_uses_master(end_use_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mines_despatch_plan_monthly (
    report_month  CHAR(7)     NOT NULL,
    mine_code     VARCHAR(24) NOT NULL,
    material_code VARCHAR(16) NOT NULL,
    end_use_code  VARCHAR(16) NOT NULL,
    qty_plan      DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code, end_use_code),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code),
    FOREIGN KEY (end_use_code) REFERENCES mine_end_uses_master(end_use_code)
) ENGINE=InnoDB;

CREATE INDEX idx_mines_despatch_actual_material ON mines_despatch_actual_monthly (report_month, material_code);
CREATE INDEX idx_mines_despatch_actual_enduse   ON mines_despatch_actual_monthly (report_month, end_use_code);
CREATE INDEX idx_mines_despatch_plan_material   ON mines_despatch_plan_monthly (report_month, material_code);

INSERT IGNORE INTO mines_despatch_actual_monthly
    (report_month, mine_code, material_code, transport_mode, end_use_code, qty_actual)
SELECT report_month, mine_code, material_code, transport_mode, end_use_code, qty_actual
FROM mines_despatch_monthly;

INSERT IGNORE INTO mines_despatch_plan_monthly
    (report_month, mine_code, material_code, end_use_code, qty_plan)
SELECT report_month, mine_code, material_code, end_use_code, MAX(qty_plan)
FROM mines_despatch_monthly
WHERE qty_plan IS NOT NULL
GROUP BY report_month, mine_code, material_code, end_use_code;

DROP TABLE IF EXISTS mines_despatch_monthly;
