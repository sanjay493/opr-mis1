-- Migrates ready_reckoner_pages off capacity_html/product_mix_html (raw,
-- editor-authored HTML strings) onto plain-data JSON columns (per direct
-- instruction, 2026-09-21 — no HTML/markup/style stored in the DB;
-- presentation is applied entirely at render time instead). See backend/
-- db.py's own comment above _READY_RECKONER_COLS for the exact JSON shape.
--
-- Two-step, safe to re-run:
--   1. ADD the 3 new columns (capacity_rows/product_mix_headers/
--      product_mix_rows) if not already present.
--   2. Populate them by running backend/scripts/migrate_ready_reckoner_
--      structured.py (parses the existing capacity_html/product_mix_html
--      for all 8 plants into the new shape) — NOT done here in SQL, since
--      it needs an HTML parser.
-- Only once step 2 has been run and verified does a third, separate step
-- (this file's own trailing DROP, commented out below) actually remove the
-- old HTML columns — kept commented so a re-run of this file alone never
-- drops real data before the Python migration has had a chance to read it.
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_ready_reckoner_structured.sql
--   (from backend/scripts/, same venv as the rest of the backend:)
--   python migrate_ready_reckoner_structured.py apply
--   -- once verified, uncomment and run the DROP below (or run this file
--   -- again with it uncommented).
--
-- Already fully applied (all 3 steps, including the DROP) against this
-- project's own dev DB on 2026-09-21 — this file stays as the runbook for
-- any other environment (e.g. a fresh restore from an older backup) that
-- still has the old capacity_html/product_mix_html columns.

ALTER TABLE ready_reckoner_pages
    ADD COLUMN IF NOT EXISTS capacity_rows       LONGTEXT AFTER process_flow_image_path,
    ADD COLUMN IF NOT EXISTS product_mix_headers LONGTEXT AFTER capacity_rows,
    ADD COLUMN IF NOT EXISTS product_mix_rows    LONGTEXT AFTER product_mix_headers,
    ADD COLUMN IF NOT EXISTS product_mix_caption VARCHAR(255) AFTER product_mix_rows;

-- ALTER TABLE ready_reckoner_pages
--     DROP COLUMN capacity_html,
--     DROP COLUMN product_mix_html;
