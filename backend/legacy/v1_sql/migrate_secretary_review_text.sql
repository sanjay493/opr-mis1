-- Secretary Review deck narrative (secretary_review_text.py). 2026-10-07.
CREATE TABLE IF NOT EXISTS secretary_review_text (
    report_month CHAR(7)     NOT NULL,
    block_key    VARCHAR(32) NOT NULL,
    text         TEXT,
    updated_at   VARCHAR(19),
    PRIMARY KEY (report_month, block_key)
) ENGINE=InnoDB;
