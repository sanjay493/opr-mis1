-- migrate_mining_leases.sql -- 2026-11-16
-- Adds mining_leases (Details of SAIL Mining Leases, MIS PDF Annexure-1 "SAIL
-- Mining at a Glance"; seeded by scripts/seed_mining_leases.py, edited on Data
-- Entry > Reference > Mining Leases). schema_v2.sql has the same table. New
-- table only: no existing data changes.
CREATE TABLE IF NOT EXISTS mining_leases (
    id            INT          NOT NULL AUTO_INCREMENT,
    sort_order    INT          NOT NULL,
    s_no          VARCHAR(8)   NOT NULL DEFAULT '',
    mine          VARCHAR(160) NOT NULL DEFAULT '',
    state         VARCHAR(160) NOT NULL DEFAULT '',
    lease         VARCHAR(160) NOT NULL DEFAULT '',
    mineral       VARCHAR(160) NOT NULL DEFAULT '',
    area          VARCHAR(160) NOT NULL DEFAULT '',
    reserves      VARCHAR(160) NOT NULL DEFAULT '',
    status        VARCHAR(255) NOT NULL DEFAULT '',
    mine_span     TINYINT      NOT NULL DEFAULT 1,
    state_span    TINYINT      NOT NULL DEFAULT 1,
    lease_span    TINYINT      NOT NULL DEFAULT 1,
    mineral_span  TINYINT      NOT NULL DEFAULT 1,
    area_span     TINYINT      NOT NULL DEFAULT 1,
    reserves_span TINYINT      NOT NULL DEFAULT 1,
    status_span   TINYINT      NOT NULL DEFAULT 1,
    updated_at    DATETIME     NOT NULL,
    updated_by    VARCHAR(64)  NULL,
    PRIMARY KEY (id),
    KEY idx_mining_leases_order (sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
