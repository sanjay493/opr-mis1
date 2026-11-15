-- migrate_add_iron_ore_rake.sql -- 2026-11-15
-- Adds iron_ore_rake (iron ore rakes loaded at the mines, one row per rake;
-- MIS PDF page 40.07 and the OGOM / JGOM rows of page 40.05; uploaded on
-- Data Entry > Uploads). Applied to mis_reports_v2. schema_v2.sql has the
-- same table. New table only: no existing data changes.
CREATE TABLE IF NOT EXISTS iron_ore_rake (
    id           INT         NOT NULL,
    report_month CHAR(7)     NOT NULL,
    rpt_date     DATE        NOT NULL,
    mine_code    VARCHAR(8)  NOT NULL,
    rake_no      VARCHAR(24) NULL,
    dest         VARCHAR(8)  NULL,
    wagon_code   VARCHAR(4)  NOT NULL,
    l_wg         DOUBLE      NULL,
    f_wg         DOUBLE      NULL,
    updated_at   DATETIME    NOT NULL,
    updated_by   VARCHAR(64) NULL,
    PRIMARY KEY (id),
    KEY idx_iron_ore_rake_month (report_month, mine_code, wagon_code),
    KEY idx_iron_ore_rake_date (rpt_date),
    CONSTRAINT fk_iron_ore_rake_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
