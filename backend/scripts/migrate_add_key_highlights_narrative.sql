-- One-time migration: adds the key_highlights_narrative table, backing the
-- new "Key Highlights & Variances" report page (inserted right after "SAIL
-- Performance Summary" — see KEY_HIGHLIGHTS_PAGE_ID in backend/main.py).
-- Stores the page's three narrative sections (Major Achievements, Major
-- Shortfalls / Areas of Concern, Focus Areas Going Forward), entered by an
-- editor/admin via /data-entry/key-highlights — nothing here is computed.
--
-- Purely additive — a brand-new, empty table. No existing table or row is
-- touched.
--
-- Run against the live DB after a fresh backup:
--   D:\mysql\backup_mysql.bat
--   mysql -u root -p mis_reports < backend/scripts/migrate_add_key_highlights_narrative.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape.

CREATE TABLE IF NOT EXISTS key_highlights_narrative (
    report_month   CHAR(7) NOT NULL PRIMARY KEY,
    achievements   TEXT,
    shortfalls     TEXT,
    focus_areas    TEXT,
    updated_by     VARCHAR(190),
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
