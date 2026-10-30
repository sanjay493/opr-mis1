-- migrate_add_production_op.sql -- 2026-10-30
-- Adds production_op_monthly: the month's Operating Plan (OP) per plant and
-- production item, entered before the month starts. schema_v2.sql has the same
-- table. New, empty table only: no data changes, so no data_version bump.
-- Run once on each machine's mis_reports_v2.
CREATE TABLE IF NOT EXISTS production_op_monthly (
    report_month CHAR(7)      NOT NULL,
    plant_code   VARCHAR(8)   NOT NULL,
    item_id      SMALLINT     NOT NULL,
    op_plan      DOUBLE       NOT NULL,
    updated_by   VARCHAR(255) NULL,
    updated_at   DATETIME     NULL,
    PRIMARY KEY (report_month, plant_code, item_id),
    CONSTRAINT fk_production_op_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_production_op_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_production_op_item  FOREIGN KEY (item_id) REFERENCES item (item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
