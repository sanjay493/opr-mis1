-- migrate_add_unique_activity.sql -- 2026-10-30
-- Adds unique_activity and unique_activity_tag (the Unique Activities record:
-- new unit start-ups, revivals after prolonged capital repair, ...).
-- schema_v2.sql has the same two tables. New, empty tables only: no data
-- changes, so no data_version bump. Run once on each machine's mis_reports_v2.
CREATE TABLE IF NOT EXISTS unique_activity (
    id             INT          NOT NULL AUTO_INCREMENT,
    activity_date  DATE         NOT NULL,
    plant_code     VARCHAR(8)   NULL,
    unit_name      VARCHAR(64)  NULL,
    title          VARCHAR(200) NOT NULL,
    description    TEXT         NOT NULL,
    created_by     VARCHAR(255) NULL,
    created_at     DATETIME     NULL,
    updated_by     VARCHAR(255) NULL,
    updated_at     DATETIME     NULL,
    PRIMARY KEY (id),
    KEY idx_unique_activity_date (activity_date),
    CONSTRAINT fk_unique_activity_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS unique_activity_tag (
    activity_id  INT         NOT NULL,
    tag          VARCHAR(48) NOT NULL,
    PRIMARY KEY (activity_id, tag),
    KEY idx_unique_activity_tag (tag),
    CONSTRAINT fk_unique_activity_tag_activity FOREIGN KEY (activity_id)
        REFERENCES unique_activity (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
