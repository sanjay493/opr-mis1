-- One-time migration: adds the table behind the new "Ready Reckoner"
-- report sections (Annexure-1: 5 ISPs, Annexure-2: 3 SSPs — right after
-- Details of Rakes Detention Plant Wise, at the very end of the report).
-- Source: Report_format/"Ready Reckoner (Plant wise Details).pdf" and
-- "Ready Reckoner Special Steel Plant.docx". See backend/page_ready_
-- reckoner.py.
--
-- Additive only — no existing table, column, or report page is affected.
-- Safe to re-run (CREATE TABLE IF NOT EXISTS).
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p -P 3307 mis_reports < backend/scripts/migrate_add_ready_reckoner.sql
--
-- See backend/scripts/mysql_schema.sql for the matching fresh-install shape,
-- and backend/scripts/backfill_ready_reckoner.py for the one-time seed of
-- content + images from the two source documents.

-- One row per plant (not month-scoped — this content is the same
-- regardless of which report month is open). capacity_html/product_mix_
-- html are edited HTML (irregular merged cells/colors per plant, not worth
-- normalizing into rows given how rarely this content changes), edited
-- inline in the /report live preview and rendered with Jinja's |safe —
-- same trust level as other admin-entered free text (e.g.
-- rail_prod_despatch_note). The process-flow diagram is a file on disk
-- (backend/static/ready_reckoner/), base64-encoded into the PDF at render
-- time (no live network access then — see page_cover.py's own background
-- image handling for the same constraint).
CREATE TABLE IF NOT EXISTS ready_reckoner_pages (
    plant_code              VARCHAR(8)   PRIMARY KEY,
    plant_name               VARCHAR(64),
    plant_group              VARCHAR(4)   NOT NULL,   -- 'ISP' or 'SSP'
    process_flow_image_path  VARCHAR(255),
    capacity_html            LONGTEXT,
    product_mix_html         LONGTEXT,
    sort_order               INT          NOT NULL DEFAULT 0,
    updated_by               VARCHAR(128),
    updated_at               DATETIME
) ENGINE=InnoDB;
