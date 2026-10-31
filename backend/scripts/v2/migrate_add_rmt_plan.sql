-- migrate_add_rmt_plan.sql -- 2026-10-31
-- Adds rmt_month, rmt_plan_note, rmt_ipt_row, rmt_stock_row: the manual parts
-- (remarks, coal requirement, IPT requirement / availability, stock) of the
-- RMT "Production Plan for <month>" report. schema_v2.sql has the same tables.
-- New, empty tables only: no data changes, so no data_version bump.
-- Run once on each machine's mis_reports_v2.
-- v2-only. RMT "Production Plan for <month>" report (/reports/production-analysis
-- ?tab=rmt-plan): the manual parts that no other table holds. The APP, OP and
-- actuals come from production_monthly / production_op_monthly. Entered at
-- /data-entry/production-techno?tab=rmt-plan; a save replaces the month's rows
-- in all four tables. rmt_month: the stock table's "as on" date and the footnote.
CREATE TABLE IF NOT EXISTS rmt_month (
    report_month CHAR(7)      NOT NULL,
    stock_as_on  DATE         NULL,
    note         VARCHAR(255) NULL,
    updated_by   VARCHAR(255) NULL,
    updated_at   DATETIME     NULL,
    -- repo.misc.rmt_plan_manual, save_rmt_plan_manual
    PRIMARY KEY (report_month),
    CONSTRAINT fk_rmt_month_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- One row of the RMT report's plan tables: section HM / CS / SS (page 1),
-- COKE / SINTER / PIG (page 2); row_label a plant code or a total ('SAIL',
-- '5 ISPs'), so not an FK. remarks may hold **bold** and line breaks. The coal
-- requirement (T/day) is entered for the COKE rows only.
CREATE TABLE IF NOT EXISTS rmt_plan_note (
    report_month CHAR(7)      NOT NULL,
    section      VARCHAR(8)   NOT NULL,
    row_label    VARCHAR(16)  NOT NULL,
    remarks      TEXT         NULL,
    coal_req_app DOUBLE       NULL,
    coal_req_op  DOUBLE       NULL,
    -- repo.misc.rmt_plan_manual, save_rmt_plan_manual
    PRIMARY KEY (report_month, section, row_label),
    CONSTRAINT fk_rmt_note_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- The RMT report's "IPT Requirement / Availability" table, in printed order.
-- availability / requirement are text ('8 Rakes', '20,000'); from / to plant
-- labels as printed ('VISL'), not FKs.
CREATE TABLE IF NOT EXISTS rmt_ipt_row (
    report_month CHAR(7)      NOT NULL,
    seq          SMALLINT     NOT NULL,
    item         VARCHAR(64)  NOT NULL,
    from_plant   VARCHAR(16)  NULL,
    to_plant     VARCHAR(16)  NULL,
    availability VARCHAR(40)  NULL,
    requirement  VARCHAR(40)  NULL,
    remarks      TEXT         NULL,
    -- repo.misc.rmt_plan_manual, save_rmt_plan_manual
    PRIMARY KEY (report_month, seq),
    CONSTRAINT fk_rmt_ipt_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- The RMT report's "Stock as on" table, in printed order; values are text
-- ('0(RSP), 1500(SSP)').
CREATE TABLE IF NOT EXISTS rmt_stock_row (
    report_month CHAR(7)      NOT NULL,
    seq          SMALLINT     NOT NULL,
    plant        VARCHAR(16)  NOT NULL,
    bf_coke      VARCHAR(80)  NULL,
    slab         VARCHAR(80)  NULL,
    bloom        VARCHAR(80)  NULL,
    -- repo.misc.rmt_plan_manual, save_rmt_plan_manual
    PRIMARY KEY (report_month, seq),
    CONSTRAINT fk_rmt_stock_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
