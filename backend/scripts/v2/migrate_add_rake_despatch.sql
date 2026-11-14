-- migrate_add_rake_despatch.sql -- 2026-11-14
-- Adds the six rake despatch tables (Despatch Summary Report upload,
-- Reports > Rail Logistics). Applied to mis_reports_v2.
-- schema_v2.sql has the same tables. New tables only: no existing data changes.
CREATE TABLE IF NOT EXISTS rake_despatch_upload (
    report_month CHAR(7)      NOT NULL,
    as_on        DATE         NOT NULL,
    slab_note    VARCHAR(255) NULL,
    source_file  VARCHAR(255) NULL,
    created_at   DATETIME(6)  NOT NULL,
    created_by   VARCHAR(190) NULL,
    PRIMARY KEY (report_month),
    CONSTRAINT fk_rake_desp_upload_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS rake_despatch_type (
    report_month CHAR(7)     NOT NULL,
    plant_code   VARCHAR(8)  NOT NULL,
    wagon_type   VARCHAR(16) NOT NULL,
    rakes        INT         NOT NULL,
    PRIMARY KEY (report_month, plant_code, wagon_type),
    CONSTRAINT fk_rake_desp_type_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_rake_desp_type_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS rake_despatch_history (
    report_month CHAR(7)    NOT NULL,
    plant_code   VARCHAR(8) NOT NULL,
    rakes        INT        NOT NULL,
    PRIMARY KEY (report_month, plant_code),
    CONSTRAINT fk_rake_desp_hist_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_rake_desp_hist_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS rake_despatch_position (
    report_month CHAR(7)     NOT NULL,
    plant_code   VARCHAR(8)  NOT NULL,
    metric       VARCHAR(32) NOT NULL,
    value        DOUBLE      NULL,
    PRIMARY KEY (report_month, plant_code, metric),
    CONSTRAINT fk_rake_desp_pos_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_rake_desp_pos_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS rake_slab_despatch (
    report_month    CHAR(7)    NOT NULL,
    from_plant_code VARCHAR(8) NOT NULL,
    to_plant_code   VARCHAR(8) NOT NULL,
    rakes           INT        NOT NULL,
    qty_mt          DOUBLE     NULL,
    PRIMARY KEY (report_month, from_plant_code, to_plant_code),
    CONSTRAINT fk_rake_slab_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_rake_slab_from FOREIGN KEY (from_plant_code) REFERENCES plant (plant_code),
    CONSTRAINT fk_rake_slab_to   FOREIGN KEY (to_plant_code)   REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS rake_export_despatch (
    report_month CHAR(7)     NOT NULL,
    destination  VARCHAR(48) NOT NULL,
    plant_code   VARCHAR(8)  NOT NULL,
    dest_group   VARCHAR(8)  NOT NULL,
    sort_order   INT         NOT NULL DEFAULT 0,
    prog         DOUBLE      NULL,
    actual       DOUBLE      NULL,
    PRIMARY KEY (report_month, destination, plant_code),
    CONSTRAINT fk_rake_export_month FOREIGN KEY (report_month) REFERENCES cal_month (report_month),
    CONSTRAINT fk_rake_export_plant FOREIGN KEY (plant_code) REFERENCES plant (plant_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
