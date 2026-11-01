-- One-time migration: adds Iron Ore Mines Production & Despatch tables
-- (mine-level detail for the 11 mines under JGoM/OGoM/CGoM) needed by the
-- new /data-entry/mines-production-despatch entry form.
-- Additive only — no existing table, column, or report page is affected.
-- Safe to re-run (CREATE TABLE IF NOT EXISTS + INSERT IGNORE seeds).
--
-- Run against the live DB after a fresh backup:
--   D:\mysql\backup_mysql.bat
--   mysql -u root -p mis_reports < backend/scripts/migrate_add_mines_production_despatch.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

CREATE TABLE IF NOT EXISTS mine_groups_master (
    group_code  VARCHAR(8)  PRIMARY KEY,
    group_name  VARCHAR(64) NOT NULL,
    sort_order  INT         NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mines_master (
    mine_code   VARCHAR(24) PRIMARY KEY,
    mine_name   VARCHAR(64) NOT NULL,
    group_code  VARCHAR(8)  NOT NULL,
    is_active   TINYINT(1)  NOT NULL DEFAULT 1,
    sort_order  INT         NOT NULL,
    FOREIGN KEY (group_code) REFERENCES mine_groups_master(group_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mine_materials_master (
    material_code               VARCHAR(16) PRIMARY KEY,
    material_name                VARCHAR(32) NOT NULL,
    material_category            VARCHAR(16) NOT NULL,
    has_production                TINYINT(1)  NOT NULL DEFAULT 0,
    counts_in_total_production    TINYINT(1)  NOT NULL DEFAULT 0,
    sort_order                    INT         NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mine_end_uses_master (
    end_use_code  VARCHAR(16) PRIMARY KEY,
    end_use_name  VARCHAR(48) NOT NULL,
    sort_order    INT         NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mines_production_monthly (
    report_month  CHAR(7)     NOT NULL,
    mine_code     VARCHAR(24) NOT NULL,
    material_code VARCHAR(16) NOT NULL,
    qty_actual    DOUBLE,
    qty_plan      DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mines_despatch_monthly (
    report_month    CHAR(7)     NOT NULL,
    mine_code       VARCHAR(24) NOT NULL,
    material_code   VARCHAR(16) NOT NULL,
    transport_mode  VARCHAR(8)  NOT NULL,
    end_use_code    VARCHAR(16) NOT NULL,
    qty_actual      DOUBLE,
    qty_plan        DOUBLE,
    PRIMARY KEY (report_month, mine_code, material_code, transport_mode, end_use_code),
    FOREIGN KEY (mine_code) REFERENCES mines_master(mine_code),
    FOREIGN KEY (material_code) REFERENCES mine_materials_master(material_code),
    FOREIGN KEY (end_use_code) REFERENCES mine_end_uses_master(end_use_code)
) ENGINE=InnoDB;

CREATE INDEX idx_mines_despatch_material ON mines_despatch_monthly (report_month, material_code);
CREATE INDEX idx_mines_despatch_enduse   ON mines_despatch_monthly (report_month, end_use_code);

INSERT IGNORE INTO mine_groups_master (group_code, group_name, sort_order) VALUES
 ('JGoM','Jharkhand Group of Mines',1), ('OGoM','Orissa Group of Mines',2), ('CGoM','Chhattisgarh Group of Mines',3);

INSERT IGNORE INTO mines_master (mine_code, mine_name, group_code, sort_order) VALUES
 ('KIRIBURU','Kiriburu','JGoM',1), ('MEGHAHATUBURU','Meghahatuburu','JGoM',2),
 ('GUA','Gua','JGoM',3), ('MANOHARPUR','Manoharpur','JGoM',4),
 ('BOLANI','Bolani','OGoM',5), ('BARSUA','Barsua','OGoM',6),
 ('TALDIH','Taldih','OGoM',7), ('KALTA','Kalta','OGoM',8),
 ('RAJHARA','Rajhara','CGoM',9), ('DALLI','Dalli','CGoM',10), ('ROWGHAT','Rowghat','CGoM',11);

INSERT IGNORE INTO mine_materials_master
 (material_code, material_name, material_category, has_production, counts_in_total_production, sort_order) VALUES
 ('LUMP','Lump','FRESH',1,1,1), ('FINES','Fines','FRESH',1,1,2),
 ('DUMP_FINES','Dump Fines','LEGACY',0,1,3), ('PELLETS','Pellets','LEGACY',0,1,4), ('TAILINGS','Tailings','LEGACY',0,1,5);

INSERT IGNORE INTO mine_end_uses_master (end_use_code, end_use_name, sort_order) VALUES
 ('CAPTIVE','Captive Plants',1), ('SALES','Sales to 3rd Party',2), ('PELLET_CONV','Pellet Conversion Agents',3);
