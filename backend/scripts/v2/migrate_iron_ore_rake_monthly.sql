-- migrate_iron_ore_rake_monthly.sql -- 2026-11-15
-- Revises iron_ore_rake from one row per rake to lump and fines rakes per
-- month, mine, wagon code and destination (schema_v2.sql has the same
-- table). Run after migrate_add_iron_ore_rake.sql.
--
-- THIS DROPS THE STORED RAKES. The per-rake rows cannot be converted in SQL
-- (the lump / fines split and the old CGOM rule are in
-- iron_ore_rakes.monthly_rows): after running this, upload u_rakes_rmg.csv
-- again on Data Entry > Uploads. Nothing else is touched.
DROP TABLE IF EXISTS iron_ore_rake;
CREATE TABLE iron_ore_rake (
    report_month CHAR(7)     NOT NULL,
    mine_code    VARCHAR(8)  NOT NULL,
    wagon_code   VARCHAR(4)  NOT NULL,
    dest         VARCHAR(8)  NOT NULL,
    lump_rakes   DOUBLE      NOT NULL,
    fines_rakes  DOUBLE      NOT NULL,
    updated_at   DATETIME    NOT NULL,
    updated_by   VARCHAR(64) NULL,
    PRIMARY KEY (report_month, mine_code, wagon_code, dest),
    CONSTRAINT fk_iron_ore_rake_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
UPDATE data_version SET n = n + 1;
