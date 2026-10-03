-- One-time migration: tables behind the selectable report covers
-- (docs/superpowers/specs/2026-10-03-selectable-cover-pages-design.md,
-- backend/cover_store.py). Additive only; safe to re-run.
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p mis_reports < backend/scripts/migrate_add_cover_pages.sql

-- Cover-photo library. Files live in backend/cover_photos/; "Remove" sets
-- is_active = 0 and keeps the file for months that already used it.
CREATE TABLE IF NOT EXISTS cover_photos (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    filename       VARCHAR(64)  NOT NULL,
    thumb_filename VARCHAR(64)  NOT NULL,
    original_name  VARCHAR(255) NOT NULL,
    width          INT,
    height         INT,
    uploaded_by    VARCHAR(255),
    uploaded_at    CHAR(19),
    is_active      TINYINT(1)   NOT NULL DEFAULT 1
) ENGINE=InnoDB;

-- The cover chosen for one report month. No row = Classic cover.
-- photo_mode 'random' stores the photo it picked, so every export of the
-- month shows the same photo until someone presses Shuffle.
CREATE TABLE IF NOT EXISTS report_cover_settings (
    report_month CHAR(7)     NOT NULL PRIMARY KEY,
    design       VARCHAR(24) NOT NULL,
    photo_mode   VARCHAR(8)  NOT NULL DEFAULT 'random',
    photo_id     INT         NULL,
    updated_by   VARCHAR(255),
    updated_at   CHAR(19)
) ENGINE=InnoDB;
