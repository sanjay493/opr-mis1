-- migrate_mining_leases_group.sql -- 2026-11-16
-- Adds the "Category" column after S.No. (Iron Ore & Manganese Ore / Flux /
-- Coal, merged down and printed vertically): grp plus its span. schema_v2.sql
-- has the columns. Run once, after migrate_mining_leases.sql.
ALTER TABLE mining_leases
    ADD COLUMN grp      VARCHAR(160) NOT NULL DEFAULT '' AFTER s_no,
    ADD COLUMN grp_span TINYINT      NOT NULL DEFAULT 1  AFTER status;
