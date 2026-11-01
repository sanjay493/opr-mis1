-- One-time migration: adds data_version, a one-row counter (id = 1) that
-- every repo write bumps inside its own transaction (backend/repo/version.py).
-- In-process caches (the /api/data page cache, generate_group_records) key on
-- it, so any write invalidates them. The app tolerates the table being absent
-- (no caching, always recompute).
--
-- Additive only. Safe to re-run (CREATE TABLE IF NOT EXISTS, INSERT IGNORE).
--
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_add_data_version.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

CREATE TABLE IF NOT EXISTS data_version (
    id  TINYINT NOT NULL,
    n   BIGINT  NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT data_version_one_row CHECK (id = 1)
) ENGINE=InnoDB;

INSERT IGNORE INTO data_version (id, n) VALUES (1, 1);
