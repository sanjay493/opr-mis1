-- MoU month-wise plan (api_mou_plan.py). 2026-10-10.
CREATE TABLE IF NOT EXISTS mou_plan_table (
    report_month CHAR(7)      NOT NULL,
    plant_name   VARCHAR(32)  NOT NULL,
    item_name    VARCHAR(64)  NOT NULL,
    month_actual DOUBLE,
    PRIMARY KEY (report_month, plant_name, item_name)
) ENGINE=InnoDB;
