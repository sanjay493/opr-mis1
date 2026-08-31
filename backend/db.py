import sqlite3
import json
import os
import copy
import functools
from typing import List, Dict, Any, Optional
from constants import ALL_PLANTS as PLANTS
from techno_registry import canonical_unit as _canon_unit
import dbengine
import activity_context

DB_PATH = os.path.join(os.path.dirname(__file__), "mis_reports.db")


def connect():
    """Single connection factory for the whole backend. Returns a sqlite3
    connection or a MySQL sqlite-dialect wrapper depending on DB_ENGINE
    (see dbengine.py). Every module should use this instead of calling
    connect() directly."""
    return dbengine.connect(DB_PATH)


def _row_dict(conn, sql: str, params) -> Optional[dict]:
    """Fetch one row as a plain dict, regardless of sqlite/MySQL engine.
    Used to snapshot a row's 'old' state before an upsert/delete for the
    activity log (see activity_context.py)."""
    prev_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.row_factory = prev_factory


_INIT_DONE = False

def init_db():
    """Initializes the database and creates the production tables if they don't exist.
    Runs the DDL only once per process — subsequent calls are no-ops.

    Under MySQL this is a no-op: the DDL below is sqlite-flavored, and the
    MySQL schema is owned by scripts/mysql_schema.sql (applied once during
    migration/deploy), not created lazily at runtime."""
    global _INIT_DONE
    if _INIT_DONE:
        return
    _INIT_DONE = True
    if dbengine.DB_ENGINE == "mysql":
        return
    conn = connect()
    cursor = conn.cursor()
    
    # 1. Actuals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS production_table (
            report_month TEXT,
            plant_name TEXT,
            item_name TEXT,
            month_actual REAL,
            PRIMARY KEY (report_month, plant_name, item_name)
        )
    """)
    
    # 2. Plans table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS production_plan_table (
            report_month TEXT,
            plant_name TEXT,
            item_name TEXT,
            month_actual REAL, -- user requested month_actual as field name here too
            PRIMARY KEY (report_month, plant_name, item_name)
        )
    """)

    # 2c. Power-OIS monthly power data — same narrow (report_month,
    # plant_name, item_name, value) shape as production_table, its own
    # table since these aren't production tonnage items and item_name
    # values (plan_own, actual_total, wheeling_px, last_year_own_cpp_cum,
    # etc.) come from a different vocabulary. See excel_extractors/
    # excel_extractor_power_omi.py and page_power_data.py.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS power_data_table (
            report_month TEXT,
            plant_name TEXT,
            item_name TEXT,
            value REAL,
            PRIMARY KEY (report_month, plant_name, item_name)
        )
    """)

    # 2b. Special Steel ABP (Annual Business Plan) — one monthly target per
    # plant, entered for all 12 months of a FY at once via the Special Steel
    # ABP Entry page. plant_name matches special_steel_orders' values (the 5
    # integrated plants + the 'SSPs' aggregate row), not the broader plant list.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS special_steel_abp_table (
            report_month TEXT,
            plant_name TEXT,
            abp_qty REAL,
            PRIMARY KEY (report_month, plant_name)
        )
    """)

    # 3. Page configs table for other pages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS page_configs (
            report_month TEXT,
            page_number INTEGER,
            page_data TEXT,
            PRIMARY KEY (report_month, page_number)
        )
    """)
    
    # 4. (removed — techno_table replaced by techno_param + techno_actuals)

    # 5. Special steel orders / actual despatch table.
    # 'section' is optional (only some plants — e.g. DSP — report it); it is part
    # of the PK because DSP rows can differ only by section (same product+grade).
    # SQLite cannot ALTER a PK, so pre-section databases are rebuilt in place,
    # old rows getting section = ''.
    cursor.execute("PRAGMA table_info(special_steel_orders)")
    _ss_cols = [r[1] for r in cursor.fetchall()]
    if _ss_cols and "section" not in _ss_cols:
        cursor.execute("ALTER TABLE special_steel_orders RENAME TO special_steel_orders_presection")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS special_steel_orders (
            report_month    TEXT,
            plant_name      TEXT,
            product         TEXT,
            quality_grade   TEXT,
            section         TEXT NOT NULL DEFAULT '',
            sort_order      INTEGER DEFAULT 0,
            order_qty       REAL,
            actual_despatch REAL,
            PRIMARY KEY (report_month, plant_name, product, quality_grade, section)
        )
    """)
    if _ss_cols and "section" not in _ss_cols:
        cursor.execute("""
            INSERT INTO special_steel_orders
                (report_month, plant_name, product, quality_grade, section,
                 sort_order, order_qty, actual_despatch)
            SELECT report_month, plant_name, product, quality_grade, '',
                   sort_order, order_qty, actual_despatch
            FROM special_steel_orders_presection
        """)
        cursor.execute("DROP TABLE special_steel_orders_presection")

    # 5b. Special Steel grade clubbing — rows sharing (plant_name, product,
    # club_label) are members of one combined display row on the Special
    # Steel report. See page_special_steel.py's _resolve_clubs().
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS special_steel_grade_clubs (
            plant_name     TEXT,
            product        TEXT,
            quality_grade  TEXT,
            club_label     TEXT NOT NULL,
            created_at     TEXT,
            PRIMARY KEY (plant_name, product, quality_grade)
        )
    """)

    # 5c. "Special Steel Plants Physical Performance" report tables — see
    # page_special_steel_physical.py and scripts/migrate_add_special_steel_physical.sql.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS special_steel_phys_perf (
            financial_year TEXT,
            plant          TEXT,
            series         TEXT,
            metric         TEXT,
            value_kt       REAL,
            PRIMARY KEY (financial_year, plant, series, metric)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS special_steel_phys_meta (
            plant          TEXT,
            series         TEXT,
            capacity_kt    REAL,
            best_actual_kt REAL,
            best_year      TEXT,
            remark         TEXT,
            sort_order     INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (plant, series)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS special_steel_phys_note (
            financial_year TEXT,
            sort_order     INTEGER,
            note_text      TEXT NOT NULL,
            PRIMARY KEY (financial_year, sort_order)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS special_steel_ipt_requirement (
            financial_year TEXT,
            item           TEXT,
            from_plant     TEXT,
            to_plant       TEXT,
            plan_kt        REAL,
            sort_order     INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (financial_year, item, from_plant, to_plant)
        )
    """)

    # 6. Opening stock table — stock as on 1st of stock_month (tonnes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_table (
            stock_month TEXT,                -- 'YYYY-MM' → stock as on 1st of this month
            plant_name  TEXT,
            item_type   TEXT,                -- STEEL INGOTS / SLABS / BLOOM-BILLETS / FINISHED STEEL / PIG IRON
            stock_type  TEXT DEFAULT '',     -- INPROCESS / FOR SALE / '' for single-value items
            stock       REAL,                -- tonnes
            PRIMARY KEY (stock_month, plant_name, item_type, stock_type)
        )
    """)

    # 6b. SAIL sales — Table A of the "1 page report" (LP/FP/PET sales,
    # exports, etc.). Pure archive: data_json holds all 10 figures the
    # source department reports (month ABP/Actual/%Ful/CPLY/Growth, same
    # 5 for Apr-month cumulative) exactly as given — nothing here is
    # computed or re-derived, since the department's own cumulative
    # figures are provisional and revise between reports, and we have no
    # reliable way to reproduce their CPLY/growth from our own history.
    # See excel_extractors/sail_sales_stock_extractor.py.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sail_sales_table (
            report_month TEXT,
            item_name    TEXT,
            data_json    TEXT,
            PRIMARY KEY (report_month, item_name)
        )
    """)

    # 6c-note. Asterisked remark under Table A (Sales) of the "1 page
    # report", e.g. "*Jul25 & Apr-Jul25 fig incl NSL sales: 98 & 482
    # respectively" — extracted alongside sail_sales_table (see
    # sail_sales_stock_extractor.py) and reprinted verbatim under Table A
    # in the generated report.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sail_sales_note_table (
            report_month TEXT PRIMARY KEY,
            note         TEXT
        )
    """)

    # 6c-steel. "Indian Steel Sector Performance" — PIB Ministry of Steel
    # monthly release (Report_format/"Indian Steel Sector Performance in
    # <Mon>'<YY>.pdf"), reproduced verbatim as pages 2.1-2.4 of the report
    # (see page_steel_sector_performance.py). Pure archive, like
    # sail_sales_table: one row per report_month, the ENTIRE extracted
    # content (all numbered tables 1a/1b/1c/2/3a/4a/5 + narrative text
    # sections 6/7/8) as a single JSON blob, so the extractor stays generic
    # and any future consumer can walk sections without re-parsing the PDF.
    # See excel_extractors/pdf_extractor_steel_sector_performance.py for the
    # JSON shape.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS steel_sector_performance_table (
            report_month TEXT PRIMARY KEY,
            data_json    TEXT,
            source_file  TEXT,
            created_at   TEXT
        )
    """)

    # 6c-do. Plant-wise remarks for the Monthly DO Letter's Annexure-A
    # (Crude Steel) / Annexure-B (Finished Steel) tables, e.g. RSP's power-
    # interruption note explaining a Crude Steel shortfall. Entered ahead of
    # time (any day in the month, or after) so the letter — due on the 1st
    # of the following month — already has them when generated. Keyed by
    # (report_month, item_name, plant_name); item_name is 'Crude Steel' or
    # 'Finished Steel' (matches the two Annexure tables, not production_
    # table's own 'Total Crude Steel'/'Finished Steel' item names, since a
    # remark is about the letter's narrative, not a specific DB figure).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS do_letter_remark_table (
            report_month TEXT,
            item_name    TEXT,   -- 'Crude Steel' | 'Finished Steel'
            plant_name   TEXT,
            remark       TEXT,
            PRIMARY KEY (report_month, item_name, plant_name)
        )
    """)

    # 6c. SAIL stock snapshot — Table D of the "1 page report" (Plants /
    # Stockyards / Stock in Transit / Total, '000T). Keyed by the report's
    # own snapshot date, not report_month — a single upload backfills
    # several years of history at once (see sail_sales_stock_extractor.py).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sail_stock_snapshot_table (
            snapshot_date TEXT,               -- 'YYYY-MM-DD'
            item_name     TEXT,               -- Plants / Stockyards / Stock In Transit / Total
            value         REAL,
            PRIMARY KEY (snapshot_date, item_name)
        )
    """)

    # 6d. Capital Repair plan — page 36-40 (Report_format/CR.pdf format).
    # The plan columns (shop/equipment/activity/schedule/period) are the
    # annual CR plan and effectively static for the FY; "actual" is the only
    # field users update from the frontend as each repair executes (a free-
    # text date range like "7.6.26-cont.." or "19.4.26-30.4.26" — not a
    # clean date pair, so kept as text rather than forced into two DATE
    # columns). schedule_days/period are also free text (source data mixes
    # "9 days", "1 month", "3+3 (revival)", multi-month ranges, etc.).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS capital_repair_table (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            plant         TEXT,
            fy            TEXT,               -- '2026-27'
            shop          TEXT,               -- 'SP-2' / 'BFs' / 'SMS2' / 'Sinter Plant' / ...
            equipment     TEXT,               -- 'M/c-1' / 'No-4' / 'Conv-A' / 'BAND-3' / ...
            activity      TEXT,               -- 'Capital Repair' / 'BLT Chute Changing + Shot Creting'
            schedule_days TEXT,
            period        TEXT,
            actual        TEXT,
            sort_order    INTEGER DEFAULT 0
        )
    """)
    # 6d-1. Structured classification/date columns for production-loss
    # analysis (see production_loss_analysis.py). Additive/nullable — every
    # existing shop/equipment/activity/schedule_days/period/actual column
    # above is untouched so pages 36-40 keep printing exactly as before.
    # `actual` becomes a derived display string (written by
    # format_cr_actual() in main.py) once a row is edited through the
    # updated data-entry UI; unedited rows keep whatever free text they had.
    cursor.execute("PRAGMA table_info(capital_repair_table)")
    _cr_cols = [r[1] for r in cursor.fetchall()]
    for _col, _ddl in [
        ("unit_type",      "TEXT"),                              # BF/SMS/MILL/COKE/SINTER/GENERAL
        ("unit_name",      "TEXT"),                              # matches plant_registry.PLANT_UNITS
        ("sms_subtag",     "TEXT"),                               # 'CONVERTER' | 'CASTER' | NULL (unit_type='SMS' only)
        ("actual_start",   "TEXT"),                               # 'YYYY-MM-DD'
        ("actual_end",     "TEXT"),                               # 'YYYY-MM-DD', NULL if ongoing
        ("actual_ongoing", "INTEGER NOT NULL DEFAULT 0"),
        ("planned_days",   "REAL"),                                # manually confirmed, used for overrun math only
    ]:
        if _col not in _cr_cols:
            cursor.execute(f"ALTER TABLE capital_repair_table ADD COLUMN {_col} {_ddl}")

    # 6d-2. Breakdown log — plant/unit-wise unplanned-downtime events, entered
    # ad hoc (full CRUD, unlike capital_repair_table's pre-seeded annual
    # plan). Used alongside capital_repair_table by production_loss_analysis.py
    # to explain Hot Metal / Crude Steel / Finished Steel shortfalls vs ABP.
    # No `fy` column — always derived from start_ts via
    # page_capital_repair.fy_from_month() to avoid a second source of truth.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS breakdown_table (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            plant                TEXT NOT NULL,
            unit_type            TEXT NOT NULL,     -- BF/SMS/MILL/COKE/SINTER/GENERAL
            unit_name            TEXT NOT NULL,     -- matches plant_registry.PLANT_UNITS
            sms_subtag           TEXT,               -- 'CONVERTER' | 'CASTER' | NULL
            start_ts             TEXT NOT NULL,      -- 'YYYY-MM-DD HH:MM'
            end_ts               TEXT,               -- NULL = ongoing
            is_ongoing           INTEGER NOT NULL DEFAULT 0,
            cause                TEXT NOT NULL,
            hours_lost_override  REAL,
            created_by           TEXT,
            created_at           TEXT,
            updated_by           TEXT,
            updated_at           TEXT
        )
    """)

    # 6d-3. Annual rated capacity per plant/item, with mid-FY change history.
    # One row per (plant, item, effective_month): the capacity in effect for
    # a given report month is the row with the latest effective_month <= that
    # month (carries forward across FY boundaries and, within an FY, across
    # a commissioning/decommissioning change — see db.get_effective_capacity).
    # Absent any override, a single entry dated to FY-start covers the whole
    # FY, matching "FY capacity shall be same for a FY period otherwise".
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS item_capacity_table (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_name       TEXT NOT NULL,     -- BSP/DSP/RSP/BSL/ISP/ASP/SSP/VISL (individual plants only)
            item_name        TEXT NOT NULL,     -- matches page4's db_item, e.g. 'Hot Metal'
            effective_month  TEXT NOT NULL,      -- 'YYYY-MM'
            annual_capacity  REAL NOT NULL,      -- '000 T / year, rated
            reason           TEXT DEFAULT '',    -- e.g. commissioning/decommissioning note
            created_by       TEXT,
            created_at       TEXT,
            updated_by       TEXT,
            updated_at       TEXT,
            UNIQUE(plant_name, item_name, effective_month)
        )
    """)

    # 7. Inter-Plant Transfer (IPT) plan vs actual, per route per month
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ipt_table (
            report_month TEXT,               -- 'YYYY-MM'
            item         TEXT,               -- Screened Coke / Sinter / CC Slabs ...
            from_plant   TEXT,
            to_plant     TEXT,
            unit         TEXT,               -- 'Rake' or 'T'
            sort_order   INTEGER DEFAULT 0,
            plan         REAL,
            actual       REAL,
            plan_tonnage   REAL,             -- tonnes equivalent (for Rake routes)
            actual_tonnage REAL,
            PRIMARY KEY (report_month, item, from_plant, to_plant)
        )
    """)

    # (techno_param, techno_param_group, techno_actuals, techno_target removed —
    #  replaced by techno_data and the JSON-based techno tables)

    # 10a. Unified Techno Plan table — all levels (units, plants, SAIL) by FY
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_plan_fy (
            plant_name   TEXT NOT NULL,   -- "BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"
            unit         TEXT NOT NULL,   -- "BF-1", "SMS-2", "Shop" (for plant or SAIL level)
            fy           TEXT NOT NULL,   -- "2026-27" (FY format)

            techno_json  JSON NOT NULL,   -- {param: {value, unit, ...}, ...}
            is_user_supplied INTEGER DEFAULT 0,  -- 1: user entered, 0: calculated
            calculated_json JSON,         -- For SAIL: calculated values for comparison
            calculation_method JSON,      -- {param: method, ...}

            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_by   TEXT,

            PRIMARY KEY (plant_name, unit, fy)
        )
    """)

    # 11a. User-defined PDF label → item_name aliases (learned from preview edits)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pdf_item_alias (
            plant_name TEXT NOT NULL,
            pdf_label  TEXT NOT NULL,
            item_name  TEXT NOT NULL,
            convert_t  INTEGER DEFAULT 1,  -- 1: tonnes → '000T on extraction
            PRIMARY KEY (plant_name, pdf_label)
        )
    """)

    # 11. Extraction audit log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS extraction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            logged_at TEXT NOT NULL,
            plant_name TEXT NOT NULL,
            report_month TEXT NOT NULL,
            file_name TEXT,
            sheet_name TEXT,
            source_type TEXT,
            items_extracted INTEGER
        )
    """)

    # 11a. To-Do / upcoming jobs — subject, recipient, due date, priority
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS todo_jobs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            subject      TEXT NOT NULL,
            details      TEXT DEFAULT '',
            recipient    TEXT DEFAULT '',        -- "where to send it" (free text)
            due_date     TEXT NOT NULL,          -- YYYY-MM-DD
            priority     TEXT NOT NULL DEFAULT 'medium',  -- 'high' | 'medium' | 'low'
            status       TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'done'
            remark       TEXT DEFAULT '',        -- progress/completion notes, editable any time
            created_at   TEXT NOT NULL,
            completed_at TEXT
        )
    """)
    cursor.execute("PRAGMA table_info(todo_jobs)")
    if "remark" not in [r[1] for r in cursor.fetchall()]:
        cursor.execute("ALTER TABLE todo_jobs ADD COLUMN remark TEXT DEFAULT ''")

    # 11b. Daily work log — free-text record of work completed each day
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_work_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            work_date    TEXT NOT NULL,          -- YYYY-MM-DD (the day the work was done)
            description  TEXT NOT NULL,          -- what was done
            remarks      TEXT DEFAULT '',        -- optional extra notes
            created_at   TEXT NOT NULL
        )
    """)

    # 12. Technopara data — all plants (BSP, DSP, RSP, BSL, ISP), unit-wise JSON
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_data (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            plant        TEXT NOT NULL,   -- "BSP", "DSP", "RSP", "BSL", "ISP"
            report_month TEXT NOT NULL,   -- "2026-05" (YYYY-MM)
            unit         TEXT NOT NULL,   -- "BF-1", "BF_Shop", "SMS-1", "COB-old", etc.
            techno_json  TEXT NOT NULL,   -- {"month": {param_key: value}, "till_month": {param_key: value}}
            source_file  TEXT DEFAULT '',
            created_at   TEXT,
            UNIQUE(plant, report_month, unit)
        )
    """)

    # 13. User accounts — role is NULL until an administrator assigns 'editor'
    # or 'admin'; a freshly-registered user has no data-entry access at all.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            name          TEXT DEFAULT '',
            role          TEXT,                  -- NULL | 'editor' | 'admin'
            profile_pic   TEXT DEFAULT '',        -- filename under static/profile_pics/
            allowed_pages TEXT,                   -- NULL = unrestricted (all pages); else JSON array of module keys
            can_delete    INTEGER NOT NULL DEFAULT 1,  -- 0 = editor may enter/update but not delete
            created_at    TEXT NOT NULL,
            updated_at    TEXT
        )
    """)
    cursor.execute("PRAGMA table_info(users)")
    _users_cols = [r[1] for r in cursor.fetchall()]
    if "allowed_pages" not in _users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN allowed_pages TEXT")
    if "can_delete" not in _users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN can_delete INTEGER NOT NULL DEFAULT 1")

    # 14. Registration whitelist — only emails listed here (and not barred)
    # may register. Administrators add/remove/bar entries.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS allowed_emails (
            email      TEXT PRIMARY KEY,
            added_by   TEXT,
            added_at   TEXT NOT NULL,
            barred     INTEGER NOT NULL DEFAULT 0,
            barred_by  TEXT,
            barred_at  TEXT
        )
    """)

    # 15. One-time passcodes — used for both registration and any password
    # change (voluntary or forgotten), per spec: every password set/change
    # is completed by emailing a passcode, never by old-password alone.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_codes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL,
            purpose    TEXT NOT NULL,   -- 'register' | 'reset_password'
            code_hash  TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # 16. Activity log — every insert/update/delete performed through a
    # gated (editor/admin-only) endpoint, with who and when.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            user_name  TEXT,
            action     TEXT NOT NULL,   -- 'insert' | 'update' | 'delete'
            entity     TEXT,            -- e.g. 'production_table', 'upload-excel'
            details    TEXT DEFAULT '',
            timestamp  TEXT NOT NULL
        )
    """)

    # 17. Page 3 narrative — Production Narrative + Highlights text, kept
    # separate from page_configs so a save here never touches (or requires
    # touching) the other 34 pages' rows for the month.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS page3_narrative (
            report_month          TEXT PRIMARY KEY,
            production_narrative  TEXT,
            highlights            TEXT,
            updated_at            TEXT
        )
    """)

    # 17b. "Key Highlights & Variances" page (KEY_HIGHLIGHTS_PAGE_ID in
    # main.py) — Major Achievements / Major Shortfalls / Focus Areas Going
    # Forward, the three narrative sections of that page that can't be
    # derived from any numeric table (they're a human analyst's read of the
    # month, not a computed figure). Stored as JSON arrays, one row per
    # report_month, so the report page reads them back directly rather than
    # attempting any on-the-fly text generation. Kept in its own table (same
    # rationale as page3_narrative above) so saving it never risks touching
    # any other page's data for the month. See page_key_highlights.py and
    # api_key_highlights.py.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS key_highlights_narrative (
            report_month   TEXT PRIMARY KEY,
            achievements   TEXT,   -- JSON: [{"text": "...", "subs": ["...", ...]}, ...]
            shortfalls     TEXT,   -- JSON: ["...", "...", ...]
            focus_areas    TEXT,   -- JSON: [{"title": "...", "description": "..."}, ...]
            updated_by     TEXT,
            updated_at     TEXT
        )
    """)

    # 18. Large BF Benchmarking — static Working Volume for SAIL's 3 fixed
    # large BFs (BSP BF-8, RSP BF-5, ISP BF-5); their monthly operating data
    # already lives in techno_data, only Working Volume (an engineering spec
    # that rarely changes) is tracked here.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bf_benchmark_sail_meta (
            plant             TEXT NOT NULL,
            unit              TEXT NOT NULL,
            working_volume_m3 REAL,
            updated_at        TEXT,
            PRIMARY KEY (plant, unit)
        )
    """)

    # 19. Large BF Benchmarking — registry of non-SAIL large BFs an admin/
    # editor adds for comparison. Soft-deactivate via `active` (mirrors
    # allowed_emails.barred) — no hard delete. `company` (e.g. "JSW") and
    # `location` (e.g. "Vijaynagar") are separate so the comparison table can
    # group columns Company -> Location -> Furnace, matching how SAIL's own
    # BFs group under plant (Location) -> unit (Furnace), company always
    # "SAIL". Added after the table already existed in prod — see
    # scripts/migrate_add_bf_benchmark_location.sql for the live MySQL DDL.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bf_benchmark_external_bf (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT NOT NULL,
            company           TEXT DEFAULT '',
            location          TEXT DEFAULT '',
            working_volume_m3 REAL,
            active            INTEGER NOT NULL DEFAULT 1,
            created_at        TEXT NOT NULL,
            created_by        TEXT DEFAULT ''
        )
    """)
    cursor.execute("PRAGMA table_info(bf_benchmark_external_bf)")
    if "location" not in [r[1] for r in cursor.fetchall()]:
        cursor.execute("ALTER TABLE bf_benchmark_external_bf ADD COLUMN location TEXT DEFAULT ''")

    # 20. Large BF Benchmarking — one entered figure set per non-SAIL BF per
    # Financial Year (non-SAIL BFs only ever publish FY-level figures, not
    # monthly ones — unlike SAIL's own BFs, which read from techno_data's
    # monthly records). Despite the column name (kept as-is to avoid a
    # migration; CHAR(7) already fits both), `report_month` holds an FY
    # label here, e.g. "2025-26", not a calendar month. param_json holds
    # {param_key: value} for the dynamic params — new params later are just
    # another JSON key, no migration needed.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bf_benchmark_external_data (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            external_bf_id  INTEGER NOT NULL,
            report_month    TEXT NOT NULL,
            param_json      TEXT NOT NULL DEFAULT '{}',
            created_at      TEXT,
            updated_at      TEXT,
            UNIQUE(external_bf_id, report_month)
        )
    """)

    # 21. Cost Trend (Report_format/COST TREND.xlsx, sheets HM/CS/SS) — two
    # tables mirroring the workbook's two distinct granularities: closed-FY
    # annual figures (entered once per FY, never revised monthly) and
    # current-FY monthly figures (month + till_month entered directly, same
    # "both typed in, not auto-summed" convention as techno_data/Demurrage —
    # a till_month figure a plant reports isn't always a clean sum of its
    # own monthly figures). product is 'HM'/'CS'/'SS' (Hot Metal/Crude
    # Steel/Saleable Steel — the workbook's 3 sheets); cost_type is
    # 'TOTAL'/'VARIABLE'/'FIXED' (the workbook's 3 blocks per sheet); plant
    # is BSP/DSP/RSP/BSL/ISP plus the workbook's own 'SAIL' aggregate row
    # (SAIL 5 ISPs) — entered directly like every other row, not computed,
    # since the source doesn't state it's a simple average/sum of the 5.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_trend_annual (
            fy         TEXT,
            product    TEXT,
            cost_type  TEXT,
            plant      TEXT,
            value      REAL,
            PRIMARY KEY (fy, product, cost_type, plant)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_trend_monthly (
            report_month      TEXT,
            product           TEXT,
            cost_type         TEXT,
            plant             TEXT,
            month_value       REAL,
            till_month_value  REAL,
            PRIMARY KEY (report_month, product, cost_type, plant)
        )
    """)

    # SAIL Mines Production & Despatch — one shared monthly table across
    # every section (Iron Ore Production, Sales of Iron Ore, Coal Mines
    # Production, Washery, Coal Despatch, Flux Production, Flux Despatch).
    # See page_sail_mines.py's SAIL_MINES_SECTIONS for the section->item
    # registry and all derived rows (Total, Yield) — those are computed at
    # read time from these leaf items, never stored. month_plan is entered
    # for 'production'-kind sections only (APP/%Ful columns); 'flow'-kind
    # despatch/sales sections leave it NULL (no APP column on those tables).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sail_mines_monthly (
            report_month  TEXT,
            section       TEXT,
            item          TEXT,
            month_actual  REAL,
            month_plan    REAL,
            PRIMARY KEY (report_month, section, item)
        )
    """)

    # Iron Ore Mines Production & Despatch — mine-level detail (11 mines
    # under JGoM/OGoM/CGoM), a finer grain than sail_mines_monthly's
    # iron_ore_prod/iron_ore_despatch sections (which stay at group level).
    # Master tables (groups/mines/materials/end_uses) are DB-backed rather
    # than a Python registry (unlike plant_registry.py's PLANT_UNITS) so a
    # mine/material/end-use can be added, renamed, or deactivated later via
    # a data change, not a code change. mines_production_monthly holds
    # fresh production only (Lump/Fines — material rows with
    # has_production=1).
    #
    # Despatch Actual and Plan live at DIFFERENT grains (per direct
    # instruction): Actual is tracked per transport_mode (Rail/Road actually
    # despatched), but Plan is a single target per material x end_use with
    # no Rail/Road split (the target doesn't commit to a mode in advance).
    # So despatch is two tables, not one — mines_despatch_actual_monthly
    # (report_month, mine_code, material_code, transport_mode, end_use_code)
    # and mines_despatch_plan_monthly (report_month, mine_code,
    # material_code, end_use_code — no transport_mode). Both cover ALL five
    # materials (fresh + legacy Dump Fines/Pellets/Tailings). "Total
    # Production" (fresh Lump+Fines production + legacy despatch ACTUAL,
    # per direct instruction) is computed at read time from
    # mine_materials_master.counts_in_total_production, never stored.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mine_groups_master (
            group_code  TEXT PRIMARY KEY,
            group_name  TEXT NOT NULL,
            sort_order  INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mines_master (
            mine_code   TEXT PRIMARY KEY,
            mine_name   TEXT NOT NULL,
            group_code  TEXT NOT NULL,
            is_active   INTEGER NOT NULL DEFAULT 1,
            sort_order  INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mine_materials_master (
            material_code                TEXT PRIMARY KEY,
            material_name                TEXT NOT NULL,
            material_category            TEXT NOT NULL,
            has_production                INTEGER NOT NULL DEFAULT 0,
            counts_in_total_production    INTEGER NOT NULL DEFAULT 0,
            sort_order                    INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mine_end_uses_master (
            end_use_code  TEXT PRIMARY KEY,
            end_use_name  TEXT NOT NULL,
            sort_order    INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mines_production_monthly (
            report_month  TEXT,
            mine_code     TEXT,
            material_code TEXT,
            qty_actual    REAL,
            qty_plan      REAL,
            PRIMARY KEY (report_month, mine_code, material_code)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mines_despatch_actual_monthly (
            report_month    TEXT,
            mine_code       TEXT,
            material_code   TEXT,
            transport_mode  TEXT,
            end_use_code    TEXT,
            qty_actual      REAL,
            PRIMARY KEY (report_month, mine_code, material_code, transport_mode, end_use_code)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mines_despatch_plan_monthly (
            report_month    TEXT,
            mine_code       TEXT,
            material_code   TEXT,
            end_use_code    TEXT,
            qty_plan        REAL,
            PRIMARY KEY (report_month, mine_code, material_code, end_use_code)
        )
    """)

    # Booked Quantity — Sales to 3rd Party (per direct instruction,
    # 2026-08-26): replaces the old flat "Auction" item on the SAIL Mines
    # Entry form's Sales of Iron Ore table. Implicitly scoped to the SALES
    # end-use only (booking a sale doesn't apply to Captive transfers or
    # Pellet Conversion, so there's no end_use_code column here — unlike
    # despatch, which needs one). Same Actual/Plan grain split as despatch:
    # Actual is per transport_mode, Plan is a single target per material
    # with no Rail/Road split.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mines_booked_qty_actual_monthly (
            report_month    TEXT,
            mine_code       TEXT,
            material_code   TEXT,
            transport_mode  TEXT,
            qty_actual      REAL,
            PRIMARY KEY (report_month, mine_code, material_code, transport_mode)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mines_booked_qty_plan_monthly (
            report_month  TEXT,
            mine_code     TEXT,
            material_code TEXT,
            qty_plan      REAL,
            PRIMARY KEY (report_month, mine_code, material_code)
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM mines_master")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO mine_groups_master (group_code, group_name, sort_order) VALUES (?, ?, ?)",
            [
                ("JGoM", "Jharkhand Group of Mines", 1),
                ("OGoM", "Orissa Group of Mines", 2),
                ("CGoM", "Chhattisgarh Group of Mines", 3),
            ],
        )
        cursor.executemany(
            "INSERT INTO mines_master (mine_code, mine_name, group_code, sort_order) VALUES (?, ?, ?, ?)",
            [
                ("KIRIBURU", "Kiriburu", "JGoM", 1),
                ("MEGHAHATUBURU", "Meghahatuburu", "JGoM", 2),
                ("GUA", "Gua", "JGoM", 3),
                ("MANOHARPUR", "Manoharpur", "JGoM", 4),
                ("BOLANI", "Bolani", "OGoM", 5),
                ("BARSUA", "Barsua", "OGoM", 6),
                ("TALDIH", "Taldih", "OGoM", 7),
                ("KALTA", "Kalta", "OGoM", 8),
                ("RAJHARA", "Rajhara", "CGoM", 9),
                ("DALLI", "Dalli", "CGoM", 10),
                ("ROWGHAT", "Rowghat", "CGoM", 11),
            ],
        )
        cursor.executemany(
            "INSERT INTO mine_materials_master "
            "(material_code, material_name, material_category, has_production, counts_in_total_production, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("LUMP", "Lump", "FRESH", 1, 1, 1),
                ("FINES", "Fines", "FRESH", 1, 1, 2),
                ("DUMP_FINES", "Dump Fines", "LEGACY", 0, 1, 3),
                ("PELLETS", "Pellets", "LEGACY", 0, 1, 4),
                ("TAILINGS", "Tailings", "LEGACY", 0, 1, 5),
            ],
        )
        cursor.executemany(
            "INSERT INTO mine_end_uses_master (end_use_code, end_use_name, sort_order) VALUES (?, ?, ?)",
            [
                ("CAPTIVE", "Captive Plants", 1),
                ("SALES", "Sales to 3rd Party", 2),
                ("PELLET_CONV", "Pellet Conversion Agents", 3),
            ],
        )

    conn.commit()
    conn.close()

def get_ytd_months(report_month: str) -> List[str]:
    """Returns YYYY-MM strings from April of the current FY up to report_month."""
    try:
        y, m = int(report_month[:4]), int(report_month[5:7])
    except (ValueError, IndexError):
        return [report_month]
    fy_start_year = y if m >= 4 else y - 1
    result = []
    cur_y, cur_m = fy_start_year, 4
    while True:
        result.append(f"{cur_y}-{cur_m:02d}")
        if cur_y == y and cur_m == m:
            break
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1
    return result

def get_fy_months(report_month: str) -> List[str]:
    """Returns all 12 YYYY-MM strings of the financial year that contains report_month."""
    try:
        y, m = int(report_month[:4]), int(report_month[5:7])
    except (ValueError, IndexError):
        return []
    fy_start_year = y if m >= 4 else y - 1
    result = []
    cur_y, cur_m = fy_start_year, 4
    for _ in range(12):
        result.append(f"{cur_y}-{cur_m:02d}")
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1
    return result


def get_fy_for_month(report_month: str) -> str:
    """Returns FY string (e.g., '2026-27') for a given report_month (e.g., '2026-05')."""
    try:
        y, m = int(report_month[:4]), int(report_month[5:7])
    except (ValueError, IndexError):
        return report_month
    # FY starts Apr (month 4), so Apr-Dec of year Y → FY Y-(Y+1), Jan-Mar of year Y → FY (Y-1)-Y
    if m >= 4:
        return f"{y}-{(y+1) % 100:02d}"
    else:
        return f"{y-1}-{y % 100:02d}"


def get_cply_month(report_month: str) -> str:
    """Returns same month in the previous year (e.g. 2025-11 -> 2024-11)."""
    try:
        y, m = int(report_month[:4]), int(report_month[5:7])
        return f"{y - 1}-{m:02d}"
    except (ValueError, IndexError):
        return report_month

# For SSP and VISL, Finished Steel = Saleable Steel (same data, no separate BF/SMS).
# Whenever "Finished Steel" is queried for these plants and no dedicated row exists,
# the query falls back to "Saleable Steel".
_FS_ALIAS_PLANTS = ('SSP', 'VISL')


def _fs_alias_sum(cursor, tbl: str, month: str, plants: list) -> Optional[float]:
    """
    Sum 'Finished Steel' across plants with SSP/VISL fallback to 'Saleable Steel'.
    Regular plants use a single bulk query; SSP/VISL try FS first then SS.
    """
    regular = [p for p in plants if p not in _FS_ALIAS_PLANTS]
    alias   = [p for p in plants if p in _FS_ALIAS_PLANTS]

    total, found = 0.0, False

    if regular:
        phs = ",".join("?" for _ in regular)
        cursor.execute(
            f"SELECT SUM(month_actual) FROM {tbl} "
            f"WHERE report_month=? AND plant_name IN ({phs}) AND item_name='Finished Steel'",
            [month] + regular,
        )
        r = cursor.fetchone()
        if r and r[0] is not None:
            total += r[0]
            found = True

    for p in alias:
        cursor.execute(
            f"SELECT month_actual FROM {tbl} WHERE report_month=? AND plant_name=? AND item_name='Finished Steel'",
            (month, p),
        )
        r = cursor.fetchone()
        if r and r[0] is not None:
            total += r[0]
            found = True
        else:
            cursor.execute(
                f"SELECT month_actual FROM {tbl} WHERE report_month=? AND plant_name=? AND item_name='Saleable Steel'",
                (month, p),
            )
            r = cursor.fetchone()
            if r and r[0] is not None:
                total += r[0]
                found = True

    return total if found else None


def _sail_conversion_actual(cursor, month: str) -> Optional[float]:
    """SAIL-level 'Conversion' actual for a month (entered via /data-entry/conversion),
    stored as plant_name='SAIL' in production_table. Represents material converted
    outside the plants' own reported Finished Steel and must be added to the SAIL
    Finished Steel total, not just relied on as a plant-sum fallback."""
    cursor.execute(
        "SELECT month_actual FROM production_table WHERE report_month=? AND plant_name='SAIL' AND item_name='Conversion'",
        (month,),
    )
    row = cursor.fetchone()
    return row[0] if row and row[0] is not None else None


def get_sail_production_actual(month: str, item: str) -> Optional[float]:
    """Calculates the sum of actuals across active plants. Falls back to explicit 'SAIL' record if none found."""
    init_db()
    conn = connect()
    cursor = conn.cursor()

    if item == "Finished Steel":
        result = _fs_alias_sum(cursor, "production_table", month, PLANTS)
        conversion = _sail_conversion_actual(cursor, month)
        if result is not None or conversion is not None:
            conn.close()
            return (result or 0.0) + (conversion or 0.0)
        # Fallback to direct SAIL record
        cursor.execute(
            "SELECT month_actual FROM production_table WHERE report_month=? AND plant_name='SAIL' AND item_name='Finished Steel'",
            (month,),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    placeholders = ",".join("?" for _ in PLANTS)
    query = f"""
        SELECT SUM(month_actual)
        FROM production_table
        WHERE report_month = ?
          AND plant_name IN ({placeholders})
          AND item_name = ?
    """
    cursor.execute(query, [month] + PLANTS + [item])
    row = cursor.fetchone()
    if row and row[0] is not None:
        conn.close()
        return row[0]

    # Fallback to explicit 'SAIL' record
    cursor.execute("""
        SELECT month_actual
        FROM production_table
        WHERE report_month = ? AND plant_name = 'SAIL' AND item_name = ?
    """, (month, item))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_sail_production_plan(month: str, item: str) -> Optional[float]:
    """Calculates the sum of plans across active plants. Falls back to explicit 'SAIL' record if none found."""
    init_db()
    conn = connect()
    cursor = conn.cursor()

    if item == "Finished Steel":
        result = _fs_alias_sum(cursor, "production_plan_table", month, PLANTS)
        if result is not None:
            conn.close()
            return result
        cursor.execute(
            "SELECT month_actual FROM production_plan_table WHERE report_month=? AND plant_name='SAIL' AND item_name='Finished Steel'",
            (month,),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    placeholders = ",".join("?" for _ in PLANTS)
    query = f"""
        SELECT SUM(month_actual)
        FROM production_plan_table
        WHERE report_month = ?
          AND plant_name IN ({placeholders})
          AND item_name = ?
    """
    cursor.execute(query, [month] + PLANTS + [item])
    row = cursor.fetchone()
    if row and row[0] is not None:
        conn.close()
        return row[0]

    # Fallback to explicit 'SAIL' record
    cursor.execute("""
        SELECT month_actual
        FROM production_plan_table
        WHERE report_month = ? AND plant_name = 'SAIL' AND item_name = ?
    """, (month, item))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_sail_production_ytd_actual(months: List[str], item: str) -> Optional[float]:
    """Sums the actuals across active plants over a list of months (YTD). Falls back to 'SAIL' if no plant records exist."""
    if not months:
        return None
    init_db()
    conn = connect()
    cursor = conn.cursor()

    if item == "Finished Steel":
        total, found = 0.0, False
        for m in months:
            v = _fs_alias_sum(cursor, "production_table", m, PLANTS)
            c = _sail_conversion_actual(cursor, m)
            if v is not None or c is not None:
                total += (v or 0.0) + (c or 0.0)
                found = True
        conn.close()
        return total if found else None

    plant_placeholders = ",".join("?" for _ in PLANTS)
    month_placeholders = ",".join("?" for _ in months)
    query = f"""
        SELECT SUM(month_actual)
        FROM production_table
        WHERE report_month IN ({month_placeholders})
          AND plant_name IN ({plant_placeholders})
          AND item_name = ?
    """
    cursor.execute(query, months + PLANTS + [item])
    row = cursor.fetchone()
    if row and row[0] is not None:
        conn.close()
        return row[0]

    # Fallback: Sum explicit 'SAIL' records across months
    query = f"""
        SELECT SUM(month_actual)
        FROM production_table
        WHERE report_month IN ({month_placeholders})
          AND plant_name = 'SAIL'
          AND item_name = ?
    """
    cursor.execute(query, months + [item])
    row = cursor.fetchone()
    conn.close()
    return row[0] if (row and row[0] is not None) else None

def get_sail_production_ytd_plan(months: List[str], item: str) -> Optional[float]:
    """Sums the plans across active plants over a list of months (YTD). Falls back to 'SAIL' if no plant records exist."""
    if not months:
        return None
    init_db()
    conn = connect()
    cursor = conn.cursor()

    if item == "Finished Steel":
        total, found = 0.0, False
        for m in months:
            v = _fs_alias_sum(cursor, "production_plan_table", m, PLANTS)
            if v is not None:
                total += v
                found = True
        conn.close()
        return total if found else None

    plant_placeholders = ",".join("?" for _ in PLANTS)
    month_placeholders = ",".join("?" for _ in months)
    query = f"""
        SELECT SUM(month_actual)
        FROM production_plan_table
        WHERE report_month IN ({month_placeholders})
          AND plant_name IN ({plant_placeholders})
          AND item_name = ?
    """
    cursor.execute(query, months + PLANTS + [item])
    row = cursor.fetchone()
    if row and row[0] is not None:
        conn.close()
        return row[0]

    # Fallback: Sum explicit 'SAIL' records across months
    query = f"""
        SELECT SUM(month_actual)
        FROM production_plan_table
        WHERE report_month IN ({month_placeholders})
          AND plant_name = 'SAIL'
          AND item_name = ?
    """
    cursor.execute(query, months + [item])
    row = cursor.fetchone()
    conn.close()
    return row[0] if (row and row[0] is not None) else None

def save_production_actual(month: str, plant: str, item: str, value: Optional[float]):
    """Saves or updates an actual production record."""
    item = item.strip()
    init_db()
    conn = connect()
    cursor = conn.cursor()
    old = _row_dict(conn,
        "SELECT * FROM production_table WHERE report_month=? AND plant_name=? AND item_name=?",
        (month, plant, item))
    if value is None:
        cursor.execute("""
            DELETE FROM production_table
            WHERE report_month = ? AND plant_name = ? AND item_name = ?
        """, (month, plant, item))
    else:
        cursor.execute("""
            INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, item_name)
            DO UPDATE SET month_actual = excluded.month_actual
        """, (month, plant, item, value))
    conn.commit()
    conn.close()
    new = None if value is None else {"report_month": month, "plant_name": plant, "item_name": item, "month_actual": value}
    activity_context.record(f"production_table/{plant}/{item}/{month}", old, new)

def save_production_plan(month: str, plant: str, item: str, value: Optional[float]):
    """Saves or updates a planned production record."""
    item = item.strip()
    init_db()
    conn = connect()
    cursor = conn.cursor()
    old = _row_dict(conn,
        "SELECT * FROM production_plan_table WHERE report_month=? AND plant_name=? AND item_name=?",
        (month, plant, item))
    if value is None:
        cursor.execute("""
            DELETE FROM production_plan_table
            WHERE report_month = ? AND plant_name = ? AND item_name = ?
        """, (month, plant, item))
    else:
        cursor.execute("""
            INSERT INTO production_plan_table (report_month, plant_name, item_name, month_actual)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, item_name)
            DO UPDATE SET month_actual = excluded.month_actual
        """, (month, plant, item, value))
    conn.commit()
    conn.close()
    new = None if value is None else {"report_month": month, "plant_name": plant, "item_name": item, "month_actual": value}
    activity_context.record(f"production_plan_table/{plant}/{item}/{month}", old, new)

def get_page_config(month: str, page_number: int) -> Optional[dict]:
    """Retrieves standard page configuration if saved in DB."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_configs WHERE report_month = ? AND page_number = ?", (month, page_number))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

def get_all_page_configs(month: str) -> List[dict]:
    """Retrieves all standard page configurations for a month, ordered by page number."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_configs WHERE report_month = ? ORDER BY page_number ASC", (month,))
    rows = cursor.fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]

def save_page_config(month: str, page_number: int, page_data: dict):
    """Saves or updates a page configuration."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO page_configs (report_month, page_number, page_data)
        VALUES (?, ?, ?)
        ON CONFLICT(report_month, page_number)
        DO UPDATE SET page_data = excluded.page_data
    """, (month, page_number, json.dumps(page_data)))
    conn.commit()
    conn.close()

def get_page3_narrative(month: str) -> Optional[dict]:
    """Returns the saved Page 3 Production Narrative + Highlights for a month,
    or None if nothing has ever been saved (caller should keep whatever
    default/computed value it already has)."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT production_narrative, highlights FROM page3_narrative WHERE report_month = ?",
        (month,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    narrative, highlights_text = row[0] or "", row[1] or ""
    return {
        "production_narrative": narrative,
        "highlights": highlights_text.split("\n") if highlights_text else [],
    }

def save_page3_narrative(month: str, production_narrative: str, highlights: List[str]):
    """Saves/updates Page 3's Production Narrative + Highlights, keyed only by
    report_month — independent of page_configs so it never risks touching
    the other 34 pages' saved data for the month."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    highlights_text = "\n".join(highlights or [])
    cursor.execute("""
        INSERT INTO page3_narrative (report_month, production_narrative, highlights, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(report_month)
        DO UPDATE SET production_narrative = excluded.production_narrative,
                       highlights = excluded.highlights,
                       updated_at = excluded.updated_at
    """, (month, production_narrative or "", highlights_text))
    conn.commit()
    conn.close()

def get_key_highlights_narrative(month: str) -> Optional[dict]:
    """Returns the saved Key Highlights & Variances narrative (Major
    Achievements / Major Shortfalls / Focus Areas Going Forward) for a
    month, or None if nothing has ever been saved for it — the report page
    shows empty sections in that case rather than inventing text."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT achievements, shortfalls, focus_areas, updated_by, updated_at "
        "FROM key_highlights_narrative WHERE report_month = ?",
        (month,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    achievements, shortfalls, focus_areas, updated_by, updated_at = row
    return {
        "achievements": json.loads(achievements) if achievements else [],
        "shortfalls":   json.loads(shortfalls) if shortfalls else [],
        "focus_areas":  json.loads(focus_areas) if focus_areas else [],
        "updated_by":   updated_by or "",
        "updated_at":   updated_at or "",
    }

def save_key_highlights_narrative(month: str, achievements: list, shortfalls: list,
                                   focus_areas: list, updated_by: str = ""):
    """Saves/updates the Key Highlights & Variances narrative for a month,
    keyed only by report_month — independent of page_configs, same as
    save_page3_narrative above."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO key_highlights_narrative
            (report_month, achievements, shortfalls, focus_areas, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(report_month)
        DO UPDATE SET achievements = excluded.achievements,
                       shortfalls  = excluded.shortfalls,
                       focus_areas = excluded.focus_areas,
                       updated_by  = excluded.updated_by,
                       updated_at  = excluded.updated_at
    """, (month, json.dumps(achievements or []), json.dumps(shortfalls or []),
          json.dumps(focus_areas or []), updated_by or ""))
    conn.commit()
    conn.close()

def save_techno_parameter(month: str, plant: str, parameter: str, unit: str,
                          month_val: Optional[float], ytd_val: Optional[float] = None):
    """Upsert a techno actual by (row_label=plant, param_name=parameter).
    ytd_val is ignored — YTD is computed on the fly."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT param_id FROM techno_param WHERE row_label=? AND param_name=?",
        (plant, parameter),
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        return
    conn.execute("""
        INSERT INTO techno_actuals (report_month, param_id, actual, source)
        VALUES (?, ?, ?, 'manual')
        ON CONFLICT(report_month, param_id) DO UPDATE SET
            actual = excluded.actual,
            source = excluded.source
    """, (month, row[0], month_val))
    conn.commit()
    conn.close()


def clear_special_steel_orders(month: str, plant: str) -> int:
    """Delete all special_steel_orders rows for a given month + plant.
    Called once before a batch insert so stale grades/products don't linger."""
    init_db()
    conn = connect()
    conn.row_factory = sqlite3.Row
    old_rows = conn.execute(
        "SELECT * FROM special_steel_orders WHERE report_month=? AND plant_name=?",
        (month, plant),
    )
    olds = [dict(r) for r in old_rows.fetchall()]
    conn.row_factory = None
    cur = conn.execute(
        "DELETE FROM special_steel_orders WHERE report_month=? AND plant_name=?",
        (month, plant),
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    for old in olds:
        activity_context.record(
            f"special_steel_orders/{plant}/{old.get('product')}/{old.get('quality_grade')}/{month}",
            old, None,
        )
    return deleted


def save_special_steel_entry(month: str, plant: str, product: str, quality_grade: str,
                             sort_order: int = 0, order_qty: Optional[float] = None,
                             actual_despatch: Optional[float] = None,
                             section: str = ""):
    """Upsert one row into special_steel_orders. section stays '' for plants
    whose report has no section breakdown."""
    init_db()
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM special_steel_orders WHERE report_month=? AND plant_name=? AND product=? AND quality_grade=? AND section=?",
        (month, plant, product, quality_grade, section or ""))
    conn.execute("""
        INSERT INTO special_steel_orders
            (report_month, plant_name, product, quality_grade, section,
             sort_order, order_qty, actual_despatch)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(report_month, plant_name, product, quality_grade, section)
        DO UPDATE SET
            sort_order      = excluded.sort_order,
            order_qty       = excluded.order_qty,
            actual_despatch = excluded.actual_despatch
    """, (month, plant, product, quality_grade, section or "",
          sort_order, order_qty, actual_despatch))
    conn.commit()
    conn.close()
    new = {"report_month": month, "plant_name": plant, "product": product,
           "quality_grade": quality_grade, "section": section or "",
           "sort_order": sort_order, "order_qty": order_qty, "actual_despatch": actual_despatch}
    activity_context.record(f"special_steel_orders/{plant}/{product}/{quality_grade}/{month}", old, new)


def save_stock_entry(stock_month: str, plant: str, item_type: str,
                     stock_type: str = "", stock: Optional[float] = None):
    """Upsert one opening-stock record ('000T, as on 1st of stock_month)."""
    init_db()
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM stock_table WHERE stock_month=? AND plant_name=? AND item_type=? AND stock_type=?",
        (stock_month, plant, item_type, stock_type))
    conn.execute("""
        INSERT INTO stock_table (stock_month, plant_name, item_type, stock_type, stock)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(stock_month, plant_name, item_type, stock_type)
        DO UPDATE SET stock = excluded.stock
    """, (stock_month, plant, item_type, stock_type, stock))
    conn.commit()
    conn.close()
    new = {"stock_month": stock_month, "plant_name": plant, "item_type": item_type,
           "stock_type": stock_type, "stock": stock}
    activity_context.record(f"stock_table/{plant}/{item_type}/{stock_month}", old, new)


def save_ipt_entry(month: str, item: str, from_plant: str, to_plant: str,
                   unit: str = "T", sort_order: int = 0,
                   plan: Optional[float] = None, actual: Optional[float] = None,
                   plan_tonnage: Optional[float] = None,
                   actual_tonnage: Optional[float] = None):
    """Upsert one IPT route record for a month.
    For Rake routes, plan/actual are rake counts and
    plan_tonnage/actual_tonnage hold the tonnes equivalent."""
    init_db()
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM ipt_table WHERE report_month=? AND item=? AND from_plant=? AND to_plant=?",
        (month, item, from_plant, to_plant))
    conn.execute("""
        INSERT INTO ipt_table
            (report_month, item, from_plant, to_plant, unit, sort_order,
             plan, actual, plan_tonnage, actual_tonnage)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(report_month, item, from_plant, to_plant)
        DO UPDATE SET
            unit = excluded.unit,
            sort_order = excluded.sort_order,
            plan = excluded.plan,
            actual = excluded.actual,
            plan_tonnage = excluded.plan_tonnage,
            actual_tonnage = excluded.actual_tonnage
    """, (month, item, from_plant, to_plant, unit, sort_order,
          plan, actual, plan_tonnage, actual_tonnage))
    conn.commit()
    conn.close()
    new = {"report_month": month, "item": item, "from_plant": from_plant, "to_plant": to_plant,
           "unit": unit, "sort_order": sort_order, "plan": plan, "actual": actual,
           "plan_tonnage": plan_tonnage, "actual_tonnage": actual_tonnage}
    activity_context.record(f"ipt_table/{item}/{from_plant}->{to_plant}/{month}", old, new)


def delete_ipt_entry(month: str, item: str, from_plant: str, to_plant: str) -> int:
    """Delete one IPT route record for a month, recording its prior state."""
    init_db()
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM ipt_table WHERE report_month=? AND item=? AND from_plant=? AND to_plant=?",
        (month, item, from_plant, to_plant))
    cur = conn.execute(
        "DELETE FROM ipt_table WHERE report_month=? AND item=? AND from_plant=? AND to_plant=?",
        (month, item, from_plant, to_plant),
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if old:
        activity_context.record(f"ipt_table/{item}/{from_plant}->{to_plant}/{month}", old, None)
    return deleted


# ============================================================================
# Breakdown log — plant/unit-wise unplanned-downtime events (see
# api_breakdown.py). Unlike capital_repair_table (a pre-seeded annual plan
# where only "actual" is ever edited), breakdown_table rows are ad hoc
# events plant users create/edit/delete freely, so this is full CRUD.
# ============================================================================

def list_breakdown_entries(plant: Optional[str] = None, fy: Optional[str] = None,
                            unit_type: Optional[str] = None, unit_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """List breakdown events, optionally filtered. `fy` filters by the FY
    fy_from_month(start_ts) falls in (computed in Python — start_ts has no
    stored FY column, see breakdown_table's docstring in init_db())."""
    from page_capital_repair import fy_from_month
    init_db()
    conn = connect()
    sql = "SELECT * FROM breakdown_table WHERE 1=1"
    args = []
    if plant:
        sql += " AND plant=?"; args.append(plant)
    if unit_type:
        sql += " AND unit_type=?"; args.append(unit_type)
    if unit_name:
        sql += " AND unit_name=?"; args.append(unit_name)
    sql += " ORDER BY start_ts DESC, id DESC"
    prev_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.row_factory = prev_factory
        conn.close()
    if fy:
        rows = [r for r in rows if r.get("start_ts") and fy_from_month(r["start_ts"][:7]) == fy]
    return rows


def save_breakdown_entry(plant: str, unit_type: str, unit_name: str, sms_subtag: Optional[str],
                          start_ts: str, end_ts: Optional[str], is_ongoing: bool,
                          cause: str, hours_lost_override: Optional[float],
                          created_by: str) -> int:
    """Create one breakdown event. Returns the new row id."""
    from datetime import datetime
    init_db()
    conn = connect()
    now = datetime.now().isoformat()
    cur = conn.execute("""
        INSERT INTO breakdown_table
            (plant, unit_type, unit_name, sms_subtag, start_ts, end_ts, is_ongoing,
             cause, hours_lost_override, created_by, created_at, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (plant, unit_type, unit_name, sms_subtag, start_ts, end_ts, int(is_ongoing),
          cause, hours_lost_override, created_by, now, created_by, now))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    activity_context.record(f"breakdown_table/{plant}/{unit_name}/{new_id}", None, {
        "plant": plant, "unit_type": unit_type, "unit_name": unit_name, "sms_subtag": sms_subtag,
        "start_ts": start_ts, "end_ts": end_ts, "is_ongoing": is_ongoing, "cause": cause,
        "hours_lost_override": hours_lost_override,
    })
    return new_id


def update_breakdown_entry(breakdown_id: int, updated_by: str, **fields) -> bool:
    """Update the given fields (any subset of plant/unit_type/unit_name/sms_subtag/
    start_ts/end_ts/is_ongoing/cause/hours_lost_override) on one breakdown event.
    Returns False if the row doesn't exist."""
    from datetime import datetime
    init_db()
    conn = connect()
    old = _row_dict(conn, "SELECT * FROM breakdown_table WHERE id=?", (breakdown_id,))
    if old is None:
        conn.close()
        return False
    allowed = {"plant", "unit_type", "unit_name", "sms_subtag", "start_ts", "end_ts",
               "is_ongoing", "cause", "hours_lost_override"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k}=?")
        args.append(int(v) if k == "is_ongoing" else v)
    if not sets:
        conn.close()
        return True
    sets.append("updated_by=?"); args.append(updated_by)
    sets.append("updated_at=?"); args.append(datetime.now().isoformat())
    args.append(breakdown_id)
    conn.execute(f"UPDATE breakdown_table SET {', '.join(sets)} WHERE id=?", args)
    conn.commit()
    conn.close()
    new = {**old, **{k: v for k, v in fields.items() if k in allowed}}
    activity_context.record(f"breakdown_table/{old['plant']}/{old['unit_name']}/{breakdown_id}", old, new)
    return True


def delete_breakdown_entry(breakdown_id: int) -> bool:
    """Delete one breakdown event, recording its prior state. Returns False if not found."""
    init_db()
    conn = connect()
    old = _row_dict(conn, "SELECT * FROM breakdown_table WHERE id=?", (breakdown_id,))
    if old is None:
        conn.close()
        return False
    conn.execute("DELETE FROM breakdown_table WHERE id=?", (breakdown_id,))
    conn.commit()
    conn.close()
    activity_context.record(f"breakdown_table/{old['plant']}/{old['unit_name']}/{breakdown_id}", old, None)
    return True


def list_capacity_entries(plant: Optional[str] = None, item: Optional[str] = None) -> List[Dict[str, Any]]:
    """List capacity-change entries, optionally filtered. Newest effective_month first."""
    init_db()
    conn = connect()
    sql = "SELECT * FROM item_capacity_table WHERE 1=1"
    args = []
    if plant:
        sql += " AND plant_name=?"; args.append(plant)
    if item:
        sql += " AND item_name=?"; args.append(item)
    sql += " ORDER BY plant_name, item_name, effective_month DESC"
    prev_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.row_factory = prev_factory
        conn.close()
    return rows


def get_effective_capacity(plant: str, item: str, month: str) -> Optional[float]:
    """Annual capacity ('000 T/yr) in effect for `plant`/`item` at `month` —
    the latest entry with effective_month <= month, or None if the plant/item
    has never had a capacity entered at or before that month."""
    init_db()
    conn = connect()
    try:
        cur = conn.execute(
            "SELECT annual_capacity FROM item_capacity_table "
            "WHERE plant_name=? AND item_name=? AND effective_month<=? "
            "ORDER BY effective_month DESC LIMIT 1",
            (plant, item, month),
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def save_capacity_entry(plant: str, item: str, effective_month: str,
                         annual_capacity: float, reason: str, created_by: str) -> int:
    """Create one capacity entry. Returns the new row id. Raises
    sqlite3.IntegrityError if (plant, item, effective_month) already exists —
    callers should surface that as "an entry for this month already exists,
    edit it instead"."""
    from datetime import datetime
    init_db()
    conn = connect()
    now = datetime.now().isoformat()
    try:
        cur = conn.execute("""
            INSERT INTO item_capacity_table
                (plant_name, item_name, effective_month, annual_capacity, reason,
                 created_by, created_at, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (plant, item, effective_month, annual_capacity, reason,
              created_by, now, created_by, now))
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    activity_context.record(f"item_capacity_table/{plant}/{item}/{new_id}", None, {
        "plant_name": plant, "item_name": item, "effective_month": effective_month,
        "annual_capacity": annual_capacity, "reason": reason,
    })
    return new_id


def update_capacity_entry(entry_id: int, updated_by: str, **fields) -> bool:
    """Update any subset of item_name/plant_name/effective_month/annual_capacity/
    reason on one capacity entry. Returns False if the row doesn't exist.
    Raises sqlite3.IntegrityError on a resulting (plant, item, effective_month)
    clash with another row."""
    from datetime import datetime
    init_db()
    conn = connect()
    old = _row_dict(conn, "SELECT * FROM item_capacity_table WHERE id=?", (entry_id,))
    if old is None:
        conn.close()
        return False
    allowed = {"plant_name", "item_name", "effective_month", "annual_capacity", "reason"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k}=?")
        args.append(v)
    if not sets:
        conn.close()
        return True
    sets.append("updated_by=?"); args.append(updated_by)
    sets.append("updated_at=?"); args.append(datetime.now().isoformat())
    args.append(entry_id)
    try:
        conn.execute(f"UPDATE item_capacity_table SET {', '.join(sets)} WHERE id=?", args)
        conn.commit()
    finally:
        conn.close()
    new = {**old, **{k: v for k, v in fields.items() if k in allowed}}
    activity_context.record(f"item_capacity_table/{old['plant_name']}/{old['item_name']}/{entry_id}", old, new)
    return True


def delete_capacity_entry(entry_id: int) -> bool:
    """Delete one capacity entry, recording its prior state. Returns False if not found."""
    init_db()
    conn = connect()
    old = _row_dict(conn, "SELECT * FROM item_capacity_table WHERE id=?", (entry_id,))
    if old is None:
        conn.close()
        return False
    conn.execute("DELETE FROM item_capacity_table WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()
    activity_context.record(f"item_capacity_table/{old['plant_name']}/{old['item_name']}/{entry_id}", old, None)
    return True


def _techno_param_entity(group_code: str, section: str, row_label: str):
    """Compute (param_name, entity_label) for techno_param from the old-style triple.

    For MAJOR/COKE_SINTER/IRON_MAKING/SMS:
        param_name   = section   (cross-plant parameter, e.g. "Coke Rate")
        entity_label = row_label (plant/shop, e.g. "BSP", "BSP Plant Shop")
    For BSL group (per-furnace):
        param_name   = row_label (e.g. "BF Productivity")
        entity_label = "BSL " + section (e.g. "BSL BF-3")
    For MILL_* groups:
        param_name   = row_label (e.g. "Overall yield")
        entity_label = plant + " " + section (e.g. "BSP Rail & Structural Mill")
    """
    if group_code in ('MAJOR', 'COKE_SINTER', 'IRON_MAKING', 'SMS'):
        return section, row_label
    if group_code == 'BSL':
        return row_label, f'BSL {section}'
    if group_code.startswith('MILL_'):
        return row_label, f'{group_code[5:]} {section}'
    return section, row_label


def get_or_create_techno_param(group_code: str, section: str, row_label: str,
                               unit: str = "", sort_order: int = 0) -> int:
    """Return param_id in techno_param, creating/updating as needed.
    Also upserts the group membership in techno_param_group."""
    from techno_registry import canonical_unit, canonical_name
    param_name, entity_label = _techno_param_entity(group_code, section, row_label)
    param_name = canonical_name(param_name)
    unit = canonical_unit(unit, group_code, param_name)
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO techno_param (param_name, row_label, unit, sort_order)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(param_name, row_label) DO UPDATE SET
            unit       = CASE WHEN excluded.unit != '' THEN excluded.unit ELSE unit END,
            sort_order = CASE WHEN excluded.sort_order > 0 THEN excluded.sort_order ELSE sort_order END
    """, (param_name, entity_label, unit, sort_order))
    cur.execute(
        "SELECT param_id FROM techno_param WHERE param_name=? AND row_label=?",
        (param_name, entity_label),
    )
    pid = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO techno_param_group (param_id, group_code, sort_order)
        VALUES (?, ?, ?)
        ON CONFLICT(param_id, group_code) DO UPDATE SET
            sort_order = CASE WHEN excluded.sort_order > 0 THEN excluded.sort_order ELSE sort_order END
    """, (pid, group_code, sort_order))
    conn.commit()
    conn.close()
    return pid


def save_techno_data_from_extraction(plant: str, report_month: str, extracted_rows: List[Dict[str, Any]],
                                     unit: str = "BF_Shop", source_file: str = ""):
    """Save extracted techno data to techno_data table.

    Args:
        plant: Plant name (BSP, DSP, RSP, BSL, ISP)
        report_month: YYYY-MM format
        extracted_rows: List of dicts with keys like {'parameter', 'actual', 'cum_actual', 'key', ...}
        unit: Unit name (default "BF_Shop")
        source_file: Source file name for audit trail
    """
    import json
    from datetime import datetime

    init_db()

    # Build JSON structure from extracted rows
    month_data = {}
    till_month_data = {}

    for row in extracted_rows:
        if row.get('actual') is not None:
            key = row.get('key') or row.get('parameter', '').lower().replace(' ', '_')
            month_data[key] = row['actual']
        if row.get('cum_actual') is not None:
            key = row.get('key') or row.get('parameter', '').lower().replace(' ', '_')
            till_month_data[key] = row['cum_actual']

    techno_json = {
        "month": month_data,
        "till_month": till_month_data
    }

    conn = connect()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(plant, report_month, unit) DO UPDATE SET
            techno_json = excluded.techno_json,
            source_file = excluded.source_file,
            created_at = excluded.created_at
    """, (plant, report_month, unit, json.dumps(techno_json), source_file, now))

    conn.commit()
    conn.close()


def save_techno_json(plant: str, report_month: str, unit: str,
                     techno_json: dict, source_file: str = ""):
    """Save a pre-built techno_json dict directly to techno_data table."""
    import json
    from datetime import datetime
    init_db()
    conn = connect()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(plant, report_month, unit) DO UPDATE SET
            techno_json = excluded.techno_json,
            source_file = excluded.source_file,
            created_at  = excluded.created_at
    """, (plant, report_month, unit, json.dumps(techno_json), source_file, now))
    conn.commit()
    conn.close()


def save_techno_value(month: str, param_id: int, actual: Optional[float],
                      till_month_actual: Optional[float] = None,
                      source_priority: int = 5):
    """Upsert one monthly techno actual into techno_actuals.
    DEPRECATED: Use save_techno_data_from_extraction instead for new code.

    actual            : monthly value (last write wins).
    till_month_actual : plant-reported Apr→month cumulative; existing value
                        is preserved when None is passed (don't clear stored YTD).
    source_priority   : informational only (5=extractor/manual, 4=computed).
    """
    # Silently skip if techno_actuals table doesn't exist (new schema uses techno_data)
    source = 'excel' if source_priority >= 5 else 'computed'
    init_db()
    try:
        conn = connect()
        conn.execute("""
            INSERT INTO techno_actuals (report_month, param_id, actual, till_month_actual, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(report_month, param_id) DO UPDATE SET
                actual            = excluded.actual,
                till_month_actual = COALESCE(excluded.till_month_actual, till_month_actual),
                source            = excluded.source
        """, (month, param_id, actual, till_month_actual, source))
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        # techno_actuals table doesn't exist - skip
        pass


def save_techno_monthly(param_id: int, report_month: str, actual: Optional[float],
                        till_month_actual: Optional[float] = None,
                        source_priority: int = 5):
    """Alias for save_techno_value (param_id/month order used by techno_aggregates)."""
    save_techno_value(report_month, param_id, actual, till_month_actual, source_priority)


def save_techno_target(fy: str, param_id: int, target: Optional[float]):
    """Upsert annual target for a parameter ('2026-27' style fy)."""
    init_db()
    conn = connect()
    conn.execute("""
        INSERT INTO techno_target (fy, param_id, target)
        VALUES (?, ?, ?)
        ON CONFLICT(fy, param_id) DO UPDATE SET target = excluded.target
    """, (fy, param_id, target))
    conn.commit()
    conn.close()


def log_extraction(plant: str, report_month: str, file_name: str, sheet_name: str,
                   source_type: str, items_extracted: int, conn=None):
    """Appends a record to the extraction audit log.

    `conn`: see merge_upsert_techno_data's docstring — when reused, this
    does NOT commit; the caller owns the transaction boundary (see
    _raw_upsert_techno_data's docstring for why that matters here)."""
    init_db()
    from datetime import datetime
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    conn.execute("""
        INSERT INTO extraction_log (logged_at, plant_name, report_month, file_name, sheet_name, source_type, items_extracted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), plant, report_month, file_name, sheet_name, source_type, items_extracted))
    if owns_conn:
        conn.commit()
        conn.close()


def get_pdf_item_aliases(plant: str) -> Dict[str, Any]:
    """User-saved PDF label corrections for a plant: {pdf_label: (item_name, convert_t)}."""
    init_db()
    conn = connect()
    rows = conn.execute("""
        SELECT pdf_label, item_name, convert_t FROM pdf_item_alias WHERE plant_name = ?
    """, (plant,)).fetchall()
    conn.close()
    return {r[0]: (r[1], r[2]) for r in rows}


def save_pdf_item_alias(plant: str, pdf_label: str, item_name: str, convert_t: int = 1):
    """Upsert a PDF label → item_name correction so future extractions map it automatically."""
    # Count-type items (e.g. "Oven Pushing(nos/d)") are plain numbers, never
    # tonnes — force convert_t=0 so no caller (stale UI tab, mapping
    # suggestions, re-confirm) can re-poison the alias with a ÷1000 flag.
    if "(nos" in (item_name or "").lower():
        convert_t = 0
    init_db()
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM pdf_item_alias WHERE plant_name=? AND pdf_label=?",
        (plant, pdf_label))
    conn.execute("""
        INSERT INTO pdf_item_alias (plant_name, pdf_label, item_name, convert_t)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(plant_name, pdf_label)
        DO UPDATE SET item_name = excluded.item_name, convert_t = excluded.convert_t
    """, (plant, pdf_label, item_name, convert_t))
    conn.commit()
    conn.close()
    new = {"plant_name": plant, "pdf_label": pdf_label, "item_name": item_name, "convert_t": convert_t}
    activity_context.record(f"pdf_item_alias/{plant}/{pdf_label}", old, new)


def get_extraction_logs(limit: int = 60, plant: Optional[str] = None,
                         source_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns the most recent extraction log entries, newest first.
    Optional plant/source_type filters let a page (e.g. /data-entry/techno)
    show only its own entries from this shared log table."""
    init_db()
    conn = connect()
    conn.row_factory = sqlite3.Row
    clauses, params = [], []
    if plant:
        clauses.append("plant_name = ?")
        params.append(plant)
    if source_type:
        clauses.append("source_type = ?")
        params.append(source_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = conn.execute(f"""
        SELECT id, logged_at, plant_name, report_month, file_name, sheet_name, source_type, items_extracted
        FROM extraction_log
        {where}
        ORDER BY id DESC
        LIMIT ?
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================================
# NEW: Techno JSON-based Furnace/Plant Data Functions
# ============================================================================

def insert_techno_furnace_data(plant: str, furnace: str, report_month: str, data: Dict[str, Any]):
    """
    Insert or update furnace-level techno data (JSON format)

    Args:
        plant: "BSP", "DSP", "RSP", etc.
        furnace: "BF-1", "BF-2", "SMS-1", etc.
        report_month: "2026-06"
        data: {param: {value, unit, source, ...}}
    """
    init_db()
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO techno_furnace_data (plant, furnace, report_month, data, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        ON CONFLICT(plant, furnace, report_month)
        DO UPDATE SET
            data = excluded.data,
            updated_at = datetime('now')
    """, (plant, furnace, report_month, json.dumps(data)))

    conn.commit()
    conn.close()


def get_techno_furnace_data(plant: str, report_month: str, furnace: str = "") -> Dict[str, Any]:
    """
    Retrieve furnace-level techno data (all furnaces for a plant-month, or specific furnace)

    Returns: {furnace: {param: {value, unit, ...}}} or specific furnace data
    """
    init_db()
    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if furnace:
        cursor.execute("""
            SELECT furnace, data
            FROM techno_furnace_data
            WHERE plant = ? AND report_month = ? AND furnace = ?
        """, [plant, report_month, furnace])
        row = cursor.fetchone()
        conn.close()
        if row:
            return {row['furnace']: json.loads(row['data'])}
        return {}
    else:
        cursor.execute("""
            SELECT furnace, data
            FROM techno_furnace_data
            WHERE plant = ? AND report_month = ?
            ORDER BY furnace
        """, [plant, report_month])
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for row in rows:
            result[row['furnace']] = json.loads(row['data'])
        return result


def insert_techno_plant_data(plant: str, report_month: str, data: Dict[str, Any],
                              calculation_details: Dict[str, Any] = None):
    """
    Insert or update plant-level consolidated techno data (JSON format)

    Args:
        plant: "BSP", "DSP", "RSP", etc.
        report_month: "2026-06"
        data: {param: {value, unit, calculation_method, ...}}
        calculation_details: {param: {formula, furnaces_used, ...}}
    """
    init_db()
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO techno_plant_data (plant, report_month, data, calculation_details, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        ON CONFLICT(plant, report_month)
        DO UPDATE SET
            data = excluded.data,
            calculation_details = excluded.calculation_details,
            updated_at = datetime('now')
    """, (plant, report_month, json.dumps(data), json.dumps(calculation_details or {})))

    conn.commit()
    conn.close()


def get_techno_plant_data(plant: str, report_month: str) -> Dict[str, Any]:
    """
    Retrieve plant-level consolidated techno data

    Returns: {data: {param: {value, unit, ...}}, calculation_details: {...}}
    """
    init_db()
    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT data, calculation_details
        FROM techno_plant_data
        WHERE plant = ? AND report_month = ?
    """, [plant, report_month])

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'data': json.loads(row['data']),
            'calculation_details': json.loads(row['calculation_details']) if row['calculation_details'] else {}
        }
    return {'data': {}, 'calculation_details': {}}


def insert_techno_sail_consolidated(report_month: str, data: Dict[str, float],
                                     calculation_method: Dict[str, str] = None):
    """
    Insert or update SAIL consolidated techno data (JSON format)

    Args:
        report_month: "2026-06"
        data: {param: value}  (consolidated across 5 plants)
        calculation_method: {param: "SAIL_direct" | "avg_5_plants"}
    """
    init_db()
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO techno_sail_consolidated (report_month, data, calculation_method, last_updated)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(report_month)
        DO UPDATE SET
            data = excluded.data,
            calculation_method = excluded.calculation_method,
            last_updated = datetime('now')
    """, (report_month, json.dumps(data), json.dumps(calculation_method or {})))

    conn.commit()
    conn.close()


def get_techno_sail_consolidated(report_month: str) -> Dict[str, Any]:
    """
    Retrieve SAIL consolidated techno data

    Returns: {data: {param: value}, calculation_method: {param: "SAIL_direct" | "avg_5_plants"}}
    """
    init_db()
    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT data, calculation_method
        FROM techno_sail_consolidated
        WHERE report_month = ?
    """, [report_month])

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'data': json.loads(row['data']),
            'calculation_method': json.loads(row['calculation_method']) if row['calculation_method'] else {}
        }
    return {'data': {}, 'calculation_method': {}}


# ============================================================================
# Techno Data helpers  (techno_data table — all plants)
# ============================================================================

def _raw_upsert_techno_data(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str = '', conn=None):
    """Bare INSERT/UPDATE with no post-save hooks — used by upsert_techno_data
    itself and by _maybe_recompute_derived_params (which must write its
    recomputed values without re-triggering itself).

    This is the one function every techno_data write funnels through
    (extraction, manual entry, SAIL rollup, derived-param recompute), so it's
    the single hook point for activity-log old/new capture across all plant
    techno routers.

    `conn`, if given, is reused instead of opening a fresh connection (and
    left open for the caller to close) — see merge_upsert_techno_data's
    docstring for why. Every other caller passes nothing and gets the
    original open-write-close-per-call behavior, unchanged.

    When `conn` is reused, this does NOT call conn.commit() — the caller
    owns the transaction boundary and must commit explicitly. This matters:
    this MySQL instance has innodb_flush_log_at_trx_commit=1 + sync_binlog=1
    (full fsync-per-commit durability), measured at ~150ms per commit on
    this machine — a bulk save that committed after every single write (as
    this function did unconditionally before) spent most of its ~30 second
    duration on fsyncs, not connection or query overhead. Batching many
    writes under one commit (see /api/techno/insert-months) cuts that
    proportionally without touching the server's durability settings."""
    init_db()
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    old = _row_dict(conn,
        "SELECT techno_json, source_file FROM techno_data WHERE plant=? AND report_month=? AND unit=?",
        (plant, report_month, unit))
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(plant, report_month, unit) DO UPDATE SET
            techno_json = excluded.techno_json,
            source_file = excluded.source_file,
            created_at  = datetime('now')
    """, (plant, report_month, unit, json.dumps(techno_json), source_file))
    if owns_conn:
        conn.commit()
        conn.close()
    if old is not None:
        old = {**old, "techno_json": json.loads(old["techno_json"])}
    new = {"techno_json": techno_json, "source_file": source_file}
    activity_context.record(f"techno_data/{plant}/{unit}/{report_month}", old, new)


def upsert_techno_data(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str = '', conn=None):
    """Insert or replace techno data for one plant/unit/month.

    SAIL's BF_Shop rollup is no longer auto-refreshed here on every
    contributing plant's save (see api_techno_manual.py's _apply_sail_bf) —
    it's now a read-time fallback used wherever SAIL techno data is
    displayed, computed only when no row already exists in techno_data for
    plant='SAIL'. Call the /sail/calculate endpoint explicitly if you
    deliberately want to publish a calculated SAIL BF_Shop figure into the DB.

    `conn`: see merge_upsert_techno_data's docstring.
    """
    _raw_upsert_techno_data(plant, report_month, unit, techno_json, source_file, conn=conn)
    _maybe_recompute_derived_params(plant, report_month, unit, conn=conn)
    _log_techno_save(plant, report_month, unit, techno_json, source_file, conn=conn)


def _log_techno_save(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str, conn=None) -> None:
    """Audit-log every techno_data save through the extraction_log table, the
    same table /upload's log panel reads — the /data-entry/techno page had no
    equivalent trail before this, since none of its API routers ever called
    log_extraction. Hooked here (the one function every techno save path
    funnels through: extraction inserts, manual entry, and the SAIL BF_Shop
    auto-refresh) so it can't be missed by adding a new save path later."""
    try:
        items = len(techno_json.get("month", {})) + len(techno_json.get("till_month", {}))
        log_extraction(
            plant=plant,
            report_month=report_month,
            file_name=source_file or "(manual entry)",
            sheet_name=unit,
            source_type="Techno Data",
            items_extracted=items,
            conn=conn,
        )
    except Exception as e:
        print(f"[db] techno save logging failed for {plant}/{report_month}/{unit}: {e}")


# tmi and fuel_rate are physically derived, never independently measured:
#   tmi        = specific_hm_consumption + specific_scrap_consumption
#   fuel_rate  = coke_rate + nut_coke_rate + cdi   (nut_coke_rate may be 0/absent)
# Different extractors historically extracted these straight from whatever a
# source file happened to report under a "TMI"/"Fuel Rate" label — sometimes
# correctly recomputed (RSP's/BSP's excel extractors), sometimes a raw
# extracted figure that could disagree with the app's own HM/Scrap or
# Coke/Nut-Coke/CDI numbers, and sometimes silently absent altogether (BSL,
# ISP's month-end path, DSP's month-end path — DSP's PDF path even LOOKED
# computed but was a no-op since no placeholder row existed to overwrite).
# Recomputing centrally here, on every save, guarantees the stored value
# always matches the plant's own current inputs regardless of which
# extractor/path last touched this unit. Both periods ("month" and
# "till_month") are computed independently as plain sums — valid because
# fuel_rate's inputs (coke_rate/nut_coke_rate/cdi) and tmi's inputs
# (specific_hm_consumption/specific_scrap_consumption) share the same
# production-weighted cumulative basis in techno_cumulative.CUMULATIVE_RULES,
# so the weighted average of a sum equals the sum of the weighted averages —
# the stored till_month values for the inputs are already correct weighted
# cumulatives, so summing them needs no separate re-weighting.
_TMI_INPUT_KEYS = ("specific_hm_consumption", "specific_scrap_consumption")
_FUEL_RATE_INPUT_KEYS = ("coke_rate", "cdi")  # nut_coke_rate optional, defaults to 0


def _maybe_recompute_derived_params(plant: str, report_month: str, unit: str, conn=None) -> None:
    """Recompute tmi/fuel_rate for this (plant, report_month, unit) from
    whatever inputs are currently stored, and overwrite the stored value if
    it differs. Writes via _raw_upsert_techno_data (never upsert_techno_data)
    so this cannot re-trigger itself; safe to call unconditionally after
    every save since it's a no-op once the stored value already matches.

    `conn`: see merge_upsert_techno_data's docstring."""
    try:
        data = get_techno_data(plant, report_month, unit, conn=conn).get(unit, {})
        if not data:
            return
        owns_conn = conn is None
        if owns_conn:
            conn = connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT source_file FROM techno_data WHERE plant=? AND report_month=? AND unit=?",
                (plant, report_month, unit),
            )
            row = cur.fetchone()
            existing_source_file = row[0] if row else ''

            updated = {"month": dict(data.get("month", {})), "till_month": dict(data.get("till_month", {}))}
            changed = False
            for period in ("month", "till_month"):
                d = updated[period]
                hm, scrap = d.get(_TMI_INPUT_KEYS[0]), d.get(_TMI_INPUT_KEYS[1])
                if isinstance(hm, (int, float)) and isinstance(scrap, (int, float)):
                    new_tmi = round(hm + scrap, 4)
                    if d.get("tmi") != new_tmi:
                        d["tmi"] = new_tmi
                        changed = True
                coke, cdi = d.get(_FUEL_RATE_INPUT_KEYS[0]), d.get(_FUEL_RATE_INPUT_KEYS[1])
                if isinstance(coke, (int, float)) and isinstance(cdi, (int, float)):
                    nut_coke = d.get("nut_coke_rate")
                    nut_coke = nut_coke if isinstance(nut_coke, (int, float)) else 0
                    new_fuel = round(coke + nut_coke + cdi, 4)
                    if d.get("fuel_rate") != new_fuel:
                        d["fuel_rate"] = new_fuel
                        changed = True
            if changed:
                # conn is still open here regardless of owns_conn — closing
                # early (before this write) was the bug: _raw_upsert_techno_data
                # sees a non-None conn and assumes the caller owns/commits it,
                # so we must commit ourselves when we're the owner.
                _raw_upsert_techno_data(plant, report_month, unit, updated, source_file=existing_source_file, conn=conn)
                if owns_conn:
                    conn.commit()
        finally:
            if owns_conn:
                conn.close()
    except Exception as e:
        print(f"[db] tmi/fuel_rate recompute failed for {plant}/{report_month}/{unit}: {e}")


# unit names that feed the SAIL BF_Shop rollup — 'BF_Shop' for most plants,
# 'BF-5' for ISP (single-furnace plant, no separate BF_Shop row ever stored).
# No longer auto-refreshed on every contributing plant's save (removed from
# upsert_techno_data above) — see api_techno_manual.py's _apply_sail_bf for
# the explicit calculate-and-store path, and page_techno.py's
# calculate_sail_actuals for the read-time fallback.
_SAIL_BF_UNITS = ("BF_Shop", "BF-5")


def merge_upsert_techno_data(plant: str, report_month: str, unit: str, new_techno_json: Dict, source_file: str = '', conn=None):
    """Merge new_techno_json into any existing row (non-null values win; existing non-null kept if new value is null).
    Use this when multiple source files contribute different parameters to the same plant/unit/month.

    `conn`: pass an already-open connection to reuse it for this call (and
    every downstream upsert_techno_data/_raw_upsert_techno_data/
    _maybe_recompute_derived_params/_log_techno_save/log_extraction call)
    instead of opening a fresh one — the caller is then responsible for
    closing it. Every one of those functions defaults to `conn=None` and
    opens+closes its own connection exactly as before when not given one,
    so this is purely additive: existing single-call sites are unaffected.
    Added for bulk saves (dozens-to-hundreds of units in one request, e.g.
    /api/techno/insert-months' 12-month "backfill" feature) — each unit-save
    was opening 4-5 separate DB connections (one per SELECT/INSERT across
    this whole call chain), which measured as the actual cause of a ~30
    second request duration for a 12-month save; long enough that the
    Next.js dev server's proxy was resetting the connection before the
    (successfully completing) response could get back to it."""
    init_db()
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT techno_json FROM techno_data WHERE plant=? AND report_month=? AND unit=?",
        [plant, report_month, unit],
    )
    row = cursor.fetchone()
    if owns_conn:
        conn.close()

    if row:
        existing = json.loads(row[0])
        merged: Dict = {}
        for period in ("month", "till_month"):
            base = dict(existing.get(period, {}))
            for k, v in new_techno_json.get(period, {}).items():
                if v is not None:
                    base[k] = v        # new non-null overwrites
                # if v is None, keep existing value (base already has it)
            merged[period] = base
    else:
        merged = new_techno_json

    upsert_techno_data(plant, report_month, unit, merged, source_file, conn=(conn if not owns_conn else None))


def get_production_actual_value(plant: str, item_name: str, report_month: str) -> Optional[float]:
    """Single plant/item/month lookup from production_table (no cross-plant
    aggregation) - used to show 'current DB value' next to a freshly-extracted
    figure during upload preview, so the user can compare before confirming."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT month_actual FROM production_table WHERE plant_name=? AND item_name=? AND report_month=?",
        (plant, item_name, report_month),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else None


def enrich_rows_with_db_production(rows: List[Dict[str, Any]], plant: str, report_month: str) -> List[Dict[str, Any]]:
    """Attach 'db_value' (current production_table value, or None) to each
    preview row in-place, keyed by (the row's own report_month, item_name).
    Used by upload preview endpoints so the UI can show DB-vs-extracted side
    by side before insert.

    Multi-month previews (ASP's FL report-month + previous-month pair, BSL's
    all-months FY preview) carry their own per-row `report_month`, which can
    differ from the top-level *report_month* argument — falling back to a
    single lookup keyed by item_name alone (the previous version of this
    function) compared every row against the SAME month's DB value, so a
    previous-month row's "In DB" figure silently showed the report month's
    value instead of its own. That makes an already-successful previous-month
    insert look like it never took effect, even though production_table was
    updated correctly."""
    if not rows:
        return rows
    init_db()
    months = {r.get("report_month") or report_month for r in rows}
    conn = connect()
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(months))
    cursor.execute(
        f"SELECT report_month, item_name, month_actual FROM production_table "
        f"WHERE plant_name=? AND report_month IN ({placeholders})",
        (plant, *months),
    )
    current = {(rm, item): val for rm, item, val in cursor.fetchall()}
    conn.close()
    for r in rows:
        item = r.get("item_name") or r.get("pdf_label")
        rm = r.get("report_month") or report_month
        r["db_value"] = current.get((rm, item)) if item else None
    return rows


def enrich_techno_records_with_db(records: List[Dict[str, Any]], plant: str, report_month: str, conn=None) -> List[Dict[str, Any]]:
    """Attach 'db_json' (current techno_data {month:{}, till_month:{}} for the
    same plant/unit/report_month, or empty dicts if none exists yet) to each
    preview record in-place. Used by techno upload preview endpoints so the UI
    can show DB-vs-extracted side by side, for both month and cumulative
    values, before the user confirms the insert.

    `conn`: see merge_upsert_techno_data's docstring — lets a multi-month
    preview (e.g. /api/techno/preview-months) reuse one connection instead
    of opening a fresh one per month."""
    if not records:
        return records
    existing = get_techno_data(plant, report_month, conn=conn)
    for r in records:
        r["db_json"] = existing.get(r.get("unit"), {"month": {}, "till_month": {}})
    return records


def get_techno_data(plant: str, report_month: str, unit: str = None, conn=None) -> Dict:
    """Return {unit: {month: {...}, till_month: {...}}} for a given plant/month.

    `conn`: see merge_upsert_techno_data's docstring. When reusing a passed-in
    connection, its row_factory is saved and restored afterward rather than
    being permanently switched to sqlite3.Row, since a shared connection may
    be reused by other callers (plain tuple rows) later in the same batch."""
    init_db()
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    prev_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if unit:
        cursor.execute(
            "SELECT unit, techno_json FROM techno_data WHERE plant = ? AND report_month = ? AND unit = ?",
            [plant, report_month, unit]
        )
    else:
        cursor.execute(
            "SELECT unit, techno_json FROM techno_data WHERE plant = ? AND report_month = ? ORDER BY unit",
            [plant, report_month]
        )

    rows = cursor.fetchall()
    if owns_conn:
        conn.close()
    else:
        conn.row_factory = prev_factory

    result = {}
    for row in rows:
        try:
            result[row['unit']] = json.loads(row['techno_json'])
        except (json.JSONDecodeError, TypeError):
            result[row['unit']] = {}
    return result


def get_sail_techno_actuals(report_month: str) -> Dict[str, Any]:
    """Fetch SAIL consolidated techno actuals (stored, not calculated).
    Returns: {unit: {month: {...}, till_month: {...}}} where unit is typically 'Shop'
    """
    init_db()
    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT unit, techno_json FROM techno_data WHERE plant = 'SAIL' AND report_month = ? ORDER BY unit",
        [report_month]
    )
    rows = cursor.fetchall()
    conn.close()

    result = {}
    for row in rows:
        try:
            result[row['unit']] = json.loads(row['techno_json'])
        except (json.JSONDecodeError, TypeError):
            result[row['unit']] = {}
    return result


def save_sail_techno_actuals(report_month: str, unit: str, techno_json: Dict,
                             calculation_details: Dict = None, source_file: str = ""):
    """Save SAIL consolidated techno actuals with calculation metadata."""
    init_db()
    from datetime import datetime
    now = datetime.now().isoformat()

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(plant, report_month, unit)
        DO UPDATE SET
            techno_json = excluded.techno_json,
            source_file = excluded.source_file,
            created_at = excluded.created_at
    """, ("SAIL", report_month, unit, json.dumps(techno_json), source_file, now))

    # Store calculation details separately if provided
    if calculation_details:
        # Store in a JSON comment or separate table (for now embed in the unit name or metadata)
        # Alternative: Create techno_calc_metadata table
        pass

    conn.commit()
    conn.close()


def get_techno_months(plant: str = None) -> List[str]:
    """Return distinct report_month values in techno_data, newest first.
    Optionally filter by plant."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    if plant:
        cursor.execute(
            "SELECT DISTINCT report_month FROM techno_data WHERE plant = ? ORDER BY report_month DESC",
            [plant]
        )
    else:
        cursor.execute(
            "SELECT DISTINCT report_month FROM techno_data ORDER BY report_month DESC"
        )
    months = [row[0] for row in cursor.fetchall()]
    conn.close()
    return months


# ---------------------------------------------------------------------------
# Techno Plan (Targets) Functions - Uses techno_plan tables
# ---------------------------------------------------------------------------

def get_techno_plan(plant: str, fy: str, unit: str = "") -> Dict[str, Any]:
    """Fetch techno plan data from unified techno_plan_fy table.
    If unit specified, returns that specific unit's data.
    Otherwise returns all units for the plant.

    Cached per (plant, fy, unit) for the process lifetime - report generation
    (page_techno.py) calls this dozens of times per request with the same
    args (once per parameter row), which used to mean a fresh MySQL round
    trip each time. save_techno_plan() clears the cache on write. Returns a
    deep copy so callers can freely mutate their result without corrupting
    the cached entry."""
    return copy.deepcopy(_get_techno_plan_cached(plant, fy, unit))


@functools.lru_cache(maxsize=None)
def _get_techno_plan_cached(plant: str, fy: str, unit: str = "") -> Dict[str, Any]:
    init_db()
    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if unit:
        cur.execute(
            "SELECT techno_json, is_user_supplied, calculated_json FROM techno_plan_fy WHERE plant_name = ? AND fy = ? AND unit = ?",
            (plant, fy, unit)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            try:
                return {
                    'data': json.loads(row['techno_json']) if row['techno_json'] else {},
                    'is_user_supplied': bool(row['is_user_supplied']),
                    'calculated': json.loads(row['calculated_json']) if row['calculated_json'] else {}
                }
            except json.JSONDecodeError:
                return {'data': {}, 'is_user_supplied': False, 'calculated': {}}
        return {'data': {}, 'is_user_supplied': False, 'calculated': {}}
    else:
        cur.execute(
            "SELECT unit, techno_json, is_user_supplied, calculated_json FROM techno_plan_fy WHERE plant_name = ? AND fy = ? ORDER BY unit",
            (plant, fy)
        )
        rows = cur.fetchall()
        conn.close()
        result = {}
        for row in rows:
            try:
                result[row['unit']] = {
                    'data': json.loads(row['techno_json']) if row['techno_json'] else {},
                    'is_user_supplied': bool(row['is_user_supplied']),
                    'calculated': json.loads(row['calculated_json']) if row['calculated_json'] else {}
                }
            except json.JSONDecodeError:
                result[row['unit']] = {'data': {}, 'is_user_supplied': False, 'calculated': {}}
        return result


def save_techno_plan(plant: str, fy: str, unit: str, techno_json: Dict,
                    is_user_supplied: bool = False, calculated_json: Dict = None,
                    calculation_method: Dict = None, created_by: str = ""):
    """Save or update techno plan data for a plant/unit/FY in unified table.

    This is the only write path into techno_plan_fy (save_techno_plant_plan
    and save_sail_techno_plan both delegate here), so it's the single hook
    point for activity-log old/new capture across the whole techno-plan
    family (/api/techno-plan, /api/techno-plant-plan, /api/sail-techno-plan)."""
    init_db()
    conn = connect()
    old = _row_dict(conn,
        "SELECT techno_json, is_user_supplied, calculated_json, calculation_method FROM techno_plan_fy WHERE plant_name=? AND unit=? AND fy=?",
        (plant, unit, fy))
    cur = conn.cursor()
    from datetime import datetime
    now = datetime.now().isoformat()

    cur.execute("""
        INSERT INTO techno_plan_fy
            (plant_name, unit, fy, techno_json, is_user_supplied, calculated_json, calculation_method, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(plant_name, unit, fy)
        DO UPDATE SET
            techno_json = excluded.techno_json,
            is_user_supplied = excluded.is_user_supplied,
            calculated_json = excluded.calculated_json,
            calculation_method = excluded.calculation_method,
            updated_at = excluded.updated_at
    """, (plant, unit, fy, json.dumps(techno_json), int(is_user_supplied),
          json.dumps(calculated_json or {}), json.dumps(calculation_method or {}), created_by, now, now))
    conn.commit()
    conn.close()

    # This is the only write path into techno_plan_fy (save_techno_plant_plan
    # and save_sail_techno_plan both delegate here) - clear all three read
    # caches so the next request sees the update instead of a stale entry.
    _get_techno_plan_cached.cache_clear()
    _get_techno_plant_plan_cached.cache_clear()
    _get_sail_techno_plan_cached.cache_clear()

    if old is not None:
        for key in ("techno_json", "calculated_json", "calculation_method"):
            if old.get(key):
                old[key] = json.loads(old[key])
    new = {"techno_json": techno_json, "is_user_supplied": bool(is_user_supplied),
           "calculated_json": calculated_json or {}, "calculation_method": calculation_method or {}}
    activity_context.record(f"techno_plan_fy/{plant}/{unit}/{fy}", old, new)


def get_techno_plant_plan(plant: str, fy: str) -> Dict[str, Any]:
    """Fetch plant-level techno plan data (unit='Shop') for a FY.
    Cached - see get_techno_plan() docstring for why and invalidation."""
    return copy.deepcopy(_get_techno_plant_plan_cached(plant, fy))


@functools.lru_cache(maxsize=None)
def _get_techno_plant_plan_cached(plant: str, fy: str) -> Dict[str, Any]:
    init_db()
    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT techno_json, is_user_supplied, calculated_json, calculation_method FROM techno_plan_fy WHERE plant_name = ? AND fy = ? AND unit = 'Shop'",
        (plant, fy)
    )
    row = cur.fetchone()
    conn.close()

    if row:
        try:
            return {
                'data': json.loads(row['techno_json']) if row['techno_json'] else {},
                'is_user_supplied': bool(row['is_user_supplied']),
                'calculated': json.loads(row['calculated_json']) if row['calculated_json'] else {},
                'calculation_method': json.loads(row['calculation_method']) if row['calculation_method'] else {}
            }
        except json.JSONDecodeError:
            return {'data': {}, 'is_user_supplied': False, 'calculated': {}, 'calculation_method': {}}
    return {'data': {}, 'is_user_supplied': False, 'calculated': {}, 'calculation_method': {}}


def save_techno_plant_plan(plant: str, fy: str, data: Dict, is_user_supplied: bool = False,
                          calculated_json: Dict = None, calculation_method: Dict = None, created_by: str = ""):
    """Save or update plant-level techno plan data (unit='Shop') for a FY."""
    init_db()
    save_techno_plan(plant, fy, 'Shop', data, is_user_supplied, calculated_json, calculation_method, created_by)


def get_sail_techno_plan(fy: str) -> Dict[str, Any]:
    """Fetch SAIL consolidated techno plan data (plant_name='SAIL', unit='Shop') for a FY.
    Cached - see get_techno_plan() docstring for why and invalidation."""
    return copy.deepcopy(_get_sail_techno_plan_cached(fy))


@functools.lru_cache(maxsize=None)
def _get_sail_techno_plan_cached(fy: str) -> Dict[str, Any]:
    init_db()
    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT techno_json, is_user_supplied, calculated_json, calculation_method FROM techno_plan_fy WHERE plant_name = 'SAIL' AND fy = ? AND unit = 'Shop'",
        (fy,)
    )
    row = cur.fetchone()
    conn.close()

    if row:
        try:
            return {
                'data': json.loads(row['techno_json']) if row['techno_json'] else {},
                'is_user_supplied': bool(row['is_user_supplied']),
                'calculated': json.loads(row['calculated_json']) if row['calculated_json'] else {},
                'calculation_method': json.loads(row['calculation_method']) if row['calculation_method'] else {}
            }
        except json.JSONDecodeError:
            return {'data': {}, 'is_user_supplied': False, 'calculated': {}, 'calculation_method': {}}
    return {'data': {}, 'is_user_supplied': False, 'calculated': {}, 'calculation_method': {}}


def save_sail_techno_plan(fy: str, data: Dict, is_user_supplied: bool = False,
                         calculated_json: Dict = None, calculation_method: Dict = None, created_by: str = ""):
    """Save or update SAIL consolidated techno plan data (plant_name='SAIL', unit='Shop') for a FY."""
    init_db()
    save_techno_plan('SAIL', fy, 'Shop', data, is_user_supplied, calculated_json, calculation_method, created_by)


def list_techno_plan_fys(plant: str = None) -> List[str]:
    """List distinct FYs in techno_plan_fy table, optionally filtered by plant."""
    init_db()
    conn = connect()
    cursor = conn.cursor()

    if plant:
        cursor.execute(
            "SELECT DISTINCT fy FROM techno_plan_fy WHERE plant_name = ? ORDER BY fy DESC",
            (plant,)
        )
    else:
        cursor.execute(
            "SELECT DISTINCT fy FROM techno_plan_fy ORDER BY fy DESC"
        )
    fys = [row[0] for row in cursor.fetchall()]
    conn.close()
    return fys


COST_TREND_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]
COST_TREND_COST_TYPES = ["TOTAL", "VARIABLE", "FIXED"]

# Entry-only subset of COST_TREND_COST_TYPES: "TOTAL COST" is always
# VARIABLE + FIXED, computed by page_cost_trend.py, never entered directly.
# Every plant in COST_TREND_PLANTS (including SAIL 5 ISPs) is entered
# directly for VARIABLE/FIXED — SAIL is its own reported figure, not a sum
# of the other 5 plants (that was tried and reverted; a plant-level rollup
# doesn't necessarily match SAIL's own cost of production).
COST_TREND_ENTRY_PLANTS = COST_TREND_PLANTS
COST_TREND_ENTRY_COST_TYPES = ["VARIABLE", "FIXED"]


def get_cost_trend_annual(product: str, fys: List[str]) -> Dict[str, Any]:
    """{fy: {cost_type: {plant: value}}} for the given product ('HM'/'CS'/
    'SS') across the given FYs — used both by the report page (page_cost_
    trend.py) and the data-entry form's pre-fill."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {fy: {ct: {} for ct in COST_TREND_COST_TYPES} for fy in fys}
    if fys:
        ph = ",".join("?" * len(fys))
        cur.execute(
            f"SELECT fy, cost_type, plant, value FROM cost_trend_annual "
            f"WHERE product=? AND fy IN ({ph})",
            (product, *fys),
        )
        for fy, cost_type, plant, value in cur.fetchall():
            out.setdefault(fy, {}).setdefault(cost_type, {})[plant] = value
    conn.close()
    return out


def save_cost_trend_annual(fy: str, product: str, entries: List[Dict[str, Any]]) -> int:
    """Upsert a batch of {cost_type, plant, value} entries for one FY/product
    (the data-entry form's Annual tab submits every cell for the FY/product
    it's editing in one call)."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for e in entries:
        cur.execute("""
            INSERT INTO cost_trend_annual (fy, product, cost_type, plant, value)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(fy, product, cost_type, plant)
            DO UPDATE SET value = excluded.value
        """, (fy, product, e["cost_type"], e["plant"], e.get("value")))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def get_cost_trend_monthly(product: str, report_months: List[str]) -> Dict[str, Any]:
    """{report_month: {cost_type: {plant: {"month": v, "till_month": v}}}}
    for the given product across the given report_months."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {rm: {ct: {} for ct in COST_TREND_COST_TYPES} for rm in report_months}
    if report_months:
        ph = ",".join("?" * len(report_months))
        cur.execute(
            f"SELECT report_month, cost_type, plant, month_value, till_month_value "
            f"FROM cost_trend_monthly WHERE product=? AND report_month IN ({ph})",
            (product, *report_months),
        )
        for rm, cost_type, plant, mv, tmv in cur.fetchall():
            out.setdefault(rm, {}).setdefault(cost_type, {})[plant] = {"month": mv, "till_month": tmv}
    conn.close()
    return out


def save_cost_trend_monthly(report_month: str, product: str, entries: List[Dict[str, Any]]) -> int:
    """Upsert a batch of {cost_type, plant, month_value, till_month_value}
    entries for one report_month/product (the data-entry form's Monthly tab
    submits every cell for the month/product it's editing in one call).
    Either value may be None — same "only overwrite what's actually
    provided" wouldn't apply here since this is a full-grid submit, not a
    partial merge, so a blank cell is saved as NULL (matches how the grid's
    own blank state should round-trip)."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for e in entries:
        cur.execute("""
            INSERT INTO cost_trend_monthly (report_month, product, cost_type, plant, month_value, till_month_value)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_month, product, cost_type, plant)
            DO UPDATE SET month_value = excluded.month_value, till_month_value = excluded.till_month_value
        """, (report_month, product, e["cost_type"], e["plant"], e.get("month_value"), e.get("till_month_value")))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def save_cost_trend_monthly_field(report_month: str, product: str, entries: List[Dict[str, Any]], field: str) -> int:
    """Upsert a batch of {cost_type, plant, value} entries into ONE column
    (field: 'month_value' or 'till_month_value') of cost_trend_monthly,
    leaving the other column untouched on an existing row. Used by the Cost
    Trend Excel extractor (excel_extractors/excel_extractor_cost_trend.py),
    which reads the month figure and the till-month figure from two
    separate source workbooks — unlike save_cost_trend_monthly's full-grid
    submit, writing both columns unconditionally here would blank out
    whichever one wasn't part of this particular extraction."""
    if field not in ("month_value", "till_month_value"):
        raise ValueError(f"field must be 'month_value' or 'till_month_value', got {field!r}")
    init_db()
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for e in entries:
        cur.execute(f"""
            INSERT INTO cost_trend_monthly (report_month, product, cost_type, plant, {field})
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(report_month, product, cost_type, plant)
            DO UPDATE SET {field} = excluded.{field}
        """, (report_month, product, e["cost_type"], e["plant"], e.get("value")))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def get_sail_mines_monthly(report_months: List[str]) -> Dict[str, Any]:
    """{report_month: {section: {item: {"actual": v, "plan": v}}}} for the
    given months — used both by page_sail_mines.py (YTD/CPLY roll-up) and
    the data-entry form's pre-fill."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {m: {} for m in report_months}
    if report_months:
        ph = ",".join("?" * len(report_months))
        cur.execute(
            f"SELECT report_month, section, item, month_actual, month_plan "
            f"FROM sail_mines_monthly WHERE report_month IN ({ph})",
            report_months,
        )
        for rm, section, item, act, plan in cur.fetchall():
            out.setdefault(rm, {}).setdefault(section, {})[item] = {"actual": act, "plan": plan}
    conn.close()
    return out


def save_sail_mines_monthly(report_month: str, entries: List[Dict[str, Any]]) -> int:
    """Upsert a batch of {section, item, actual, plan} entries for one
    report_month (the data-entry form submits every cell it's editing in
    one call)."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for e in entries:
        cur.execute("""
            INSERT INTO sail_mines_monthly (report_month, section, item, month_actual, month_plan)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(report_month, section, item)
            DO UPDATE SET month_actual = excluded.month_actual, month_plan = excluded.month_plan
        """, (report_month, e["section"], e["item"], e.get("actual"), e.get("plan")))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def get_mines_masters() -> Dict[str, Any]:
    """Groups/mines/materials/end-uses (+ the fixed Rail/Road transport
    modes) for the Mines Production & Despatch entry form and reports.
    DB-backed (not a Python registry) so a mine/material/end-use can be
    added or deactivated later without a code change."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT group_code, group_name FROM mine_groups_master ORDER BY sort_order")
    groups = [{"group_code": r[0], "group_name": r[1]} for r in cur.fetchall()]
    cur.execute("SELECT mine_code, mine_name, group_code, is_active FROM mines_master ORDER BY sort_order")
    mines = [{"mine_code": r[0], "mine_name": r[1], "group_code": r[2], "is_active": bool(r[3])} for r in cur.fetchall()]
    cur.execute(
        "SELECT material_code, material_name, material_category, has_production, counts_in_total_production "
        "FROM mine_materials_master ORDER BY sort_order"
    )
    materials = [
        {
            "material_code": r[0], "material_name": r[1], "material_category": r[2],
            "has_production": bool(r[3]), "counts_in_total_production": bool(r[4]),
        }
        for r in cur.fetchall()
    ]
    cur.execute("SELECT end_use_code, end_use_name FROM mine_end_uses_master ORDER BY sort_order")
    end_uses = [{"end_use_code": r[0], "end_use_name": r[1]} for r in cur.fetchall()]
    conn.close()
    return {
        "groups": groups, "mines": mines, "materials": materials, "end_uses": end_uses,
        "transport_modes": [{"mode_code": "RAIL", "mode_name": "Rail"}, {"mode_code": "ROAD", "mode_name": "Road"}],
    }


def get_mines_production_despatch_monthly(report_month: str, mine_code: str) -> Dict[str, Any]:
    """{"production": {material_code: {"actual": v, "plan": v}},
        "despatch": {material_code: {mode_code: {end_use_code: {"actual": v}}}},
        "despatch_plan": {material_code: {end_use_code: v}},
        "booked_qty": {material_code: {mode_code: {"actual": v}}},
        "booked_qty_plan": {material_code: v}}
    for one mine/report_month — used to pre-fill the entry form. despatch
    (Actual) is per transport_mode; despatch_plan is per material x end_use
    only — Plan doesn't split Rail/Road, per direct instruction. booked_qty
    (Sales only — no end_use dimension, see mines_booked_qty_actual_monthly)
    follows the same Actual-per-mode / Plan-with-no-mode-split shape."""
    init_db()
    conn = connect()
    cur = conn.cursor()

    production = {}
    cur.execute(
        "SELECT material_code, qty_actual, qty_plan FROM mines_production_monthly WHERE report_month=? AND mine_code=?",
        (report_month, mine_code),
    )
    for material_code, actual, plan in cur.fetchall():
        production[material_code] = {"actual": actual, "plan": plan}

    despatch = {}
    cur.execute(
        "SELECT material_code, transport_mode, end_use_code, qty_actual "
        "FROM mines_despatch_actual_monthly WHERE report_month=? AND mine_code=?",
        (report_month, mine_code),
    )
    for material_code, mode, end_use, actual in cur.fetchall():
        despatch.setdefault(material_code, {}).setdefault(mode, {})[end_use] = {"actual": actual}

    despatch_plan = {}
    cur.execute(
        "SELECT material_code, end_use_code, qty_plan "
        "FROM mines_despatch_plan_monthly WHERE report_month=? AND mine_code=?",
        (report_month, mine_code),
    )
    for material_code, end_use, plan in cur.fetchall():
        despatch_plan.setdefault(material_code, {})[end_use] = plan

    booked_qty = {}
    cur.execute(
        "SELECT material_code, transport_mode, qty_actual "
        "FROM mines_booked_qty_actual_monthly WHERE report_month=? AND mine_code=?",
        (report_month, mine_code),
    )
    for material_code, mode, actual in cur.fetchall():
        booked_qty.setdefault(material_code, {})[mode] = {"actual": actual}

    booked_qty_plan = {}
    cur.execute(
        "SELECT material_code, qty_plan FROM mines_booked_qty_plan_monthly WHERE report_month=? AND mine_code=?",
        (report_month, mine_code),
    )
    for material_code, plan in cur.fetchall():
        booked_qty_plan[material_code] = plan

    conn.close()
    return {
        "production": production, "despatch": despatch, "despatch_plan": despatch_plan,
        "booked_qty": booked_qty, "booked_qty_plan": booked_qty_plan,
    }


def save_mines_production_despatch_monthly(
    report_month: str, mine_code: str,
    production_entries: List[Dict[str, Any]], despatch_entries: List[Dict[str, Any]],
    despatch_plan_entries: List[Dict[str, Any]],
    booked_qty_entries: List[Dict[str, Any]] = None,
    booked_qty_plan_entries: List[Dict[str, Any]] = None,
) -> int:
    """Upsert one mine/month's changed production rows ({material_code,
    actual, plan}), despatch Actual rows ({material_code, transport_mode,
    end_use_code, actual}), despatch Plan rows ({material_code,
    end_use_code, plan}), booked-quantity Actual rows ({material_code,
    transport_mode, actual}), and booked-quantity Plan rows ({material_code,
    plan}) in one call — the entry form submits every cell it's editing,
    mirroring save_sail_mines_monthly's batch shape. Actual and Plan are
    separate tables/params because they're different grains: Actual is per
    transport_mode, Plan has no Rail/Road split (true for both despatch and
    booked quantity)."""
    booked_qty_entries = booked_qty_entries or []
    booked_qty_plan_entries = booked_qty_plan_entries or []
    init_db()
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for e in production_entries:
        cur.execute("""
            INSERT INTO mines_production_monthly (report_month, mine_code, material_code, qty_actual, qty_plan)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(report_month, mine_code, material_code)
            DO UPDATE SET qty_actual = excluded.qty_actual, qty_plan = excluded.qty_plan
        """, (report_month, mine_code, e["material_code"], e.get("actual"), e.get("plan")))
        saved += 1
    for e in despatch_entries:
        cur.execute("""
            INSERT INTO mines_despatch_actual_monthly
                (report_month, mine_code, material_code, transport_mode, end_use_code, qty_actual)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_month, mine_code, material_code, transport_mode, end_use_code)
            DO UPDATE SET qty_actual = excluded.qty_actual
        """, (
            report_month, mine_code, e["material_code"], e["transport_mode"], e["end_use_code"], e.get("actual"),
        ))
        saved += 1
    for e in despatch_plan_entries:
        cur.execute("""
            INSERT INTO mines_despatch_plan_monthly
                (report_month, mine_code, material_code, end_use_code, qty_plan)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(report_month, mine_code, material_code, end_use_code)
            DO UPDATE SET qty_plan = excluded.qty_plan
        """, (report_month, mine_code, e["material_code"], e["end_use_code"], e.get("plan")))
        saved += 1
    for e in booked_qty_entries:
        cur.execute("""
            INSERT INTO mines_booked_qty_actual_monthly
                (report_month, mine_code, material_code, transport_mode, qty_actual)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(report_month, mine_code, material_code, transport_mode)
            DO UPDATE SET qty_actual = excluded.qty_actual
        """, (report_month, mine_code, e["material_code"], e["transport_mode"], e.get("actual")))
        saved += 1
    for e in booked_qty_plan_entries:
        cur.execute("""
            INSERT INTO mines_booked_qty_plan_monthly (report_month, mine_code, material_code, qty_plan)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(report_month, mine_code, material_code)
            DO UPDATE SET qty_plan = excluded.qty_plan
        """, (report_month, mine_code, e["material_code"], e.get("plan")))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def get_iron_ore_group_rollup_monthly(report_months: List[str]) -> Dict[str, Any]:
    """Group-level (JGoM/OGoM/CGoM) Iron Ore Production & Despatch, rolled
    up from the mine-level tables (mines_production_monthly,
    mines_despatch_actual_monthly, mines_despatch_plan_monthly) via
    mines_master.group_code. Returns the same
    {report_month: {section: {item: {"actual": v, "plan": v}}}} shape as
    get_sail_mines_monthly (item = group_code) so page_sail_mines.py's
    existing YTD/CPLY roll-up logic (_leaf_values/_ytd_sum) works
    unchanged against it.

    This REPLACES sail_mines_monthly as the source for the 'iron_ore_prod'
    and 'iron_ore_despatch' sections only (per direct instruction,
    2026-08-26 — the mine-level entry form is now the single source of
    truth for Iron Ore Production/Despatch; every other section still comes
    from sail_mines_monthly as before). Production = fresh Lump+Fines
    actual/plan, summed per group. Despatch = ALL materials' (fresh +
    legacy) despatch Actual summed per group (Rail+Road combined) and Plan
    summed per group (Plan has no Rail/Road split — see
    mines_despatch_plan_monthly)."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {m: {"iron_ore_prod": {}, "iron_ore_despatch": {}} for m in report_months}
    if not report_months:
        conn.close()
        return out
    ph = ",".join("?" * len(report_months))

    cur.execute(f"""
        SELECT p.report_month, mm.group_code, SUM(p.qty_actual), SUM(p.qty_plan)
        FROM mines_production_monthly p
        JOIN mines_master mm ON mm.mine_code = p.mine_code
        WHERE p.report_month IN ({ph})
        GROUP BY p.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual, plan in cur.fetchall():
        out[rm]["iron_ore_prod"][group_code] = {"actual": actual, "plan": plan}

    despatch_actual = {}
    cur.execute(f"""
        SELECT d.report_month, mm.group_code, SUM(d.qty_actual)
        FROM mines_despatch_actual_monthly d
        JOIN mines_master mm ON mm.mine_code = d.mine_code
        WHERE d.report_month IN ({ph})
        GROUP BY d.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual in cur.fetchall():
        despatch_actual.setdefault(rm, {})[group_code] = actual

    despatch_plan = {}
    cur.execute(f"""
        SELECT pl.report_month, mm.group_code, SUM(pl.qty_plan)
        FROM mines_despatch_plan_monthly pl
        JOIN mines_master mm ON mm.mine_code = pl.mine_code
        WHERE pl.report_month IN ({ph})
        GROUP BY pl.report_month, mm.group_code
    """, report_months)
    for rm, group_code, plan in cur.fetchall():
        despatch_plan.setdefault(rm, {})[group_code] = plan

    for rm in report_months:
        groups = set(despatch_actual.get(rm, {})) | set(despatch_plan.get(rm, {}))
        for group_code in groups:
            out[rm]["iron_ore_despatch"][group_code] = {
                "actual": despatch_actual.get(rm, {}).get(group_code),
                "plan": despatch_plan.get(rm, {}).get(group_code),
            }

    conn.close()
    return out


def get_iron_ore_sales_group_rollup_monthly(report_months: List[str]) -> Dict[str, Any]:
    """Group-level (JGoM/OGoM/CGoM) Sales of Iron Ore — Booked Quantity &
    Despatch, rolled up via mines_master.group_code. Same
    {report_month: {section: {item: {"actual": v, "plan": v}}}} shape as
    get_iron_ore_group_rollup_monthly (item = group_code).

    REPLACES the old flat sail_mines_monthly 'iron_ore_sales' section
    (which had 2 SAIL-wide rows, "Auction"/"Despatch", no per-group
    breakdown) with a per-group breakdown for both rows, per direct
    instruction (2026-08-26) — "Auction" is renamed "Booked Quantity" and
    now comes from mines_booked_qty_actual_monthly /
    mines_booked_qty_plan_monthly (all materials/modes summed per group).
    "Despatch" here means despatch to the SALES end-use specifically (NOT
    all end-uses like get_iron_ore_group_rollup_monthly's despatch section)
    — it's mines_despatch_actual_monthly/mines_despatch_plan_monthly
    filtered to end_use_code='SALES' and summed per group, reusing data
    already entered on the Despatch — Sales to 3rd Party table rather than
    needing any new input."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {m: {"iron_ore_sales": {}, "iron_ore_sales_despatch": {}} for m in report_months}
    if not report_months:
        conn.close()
        return out
    ph = ",".join("?" * len(report_months))

    booked_actual = {}
    cur.execute(f"""
        SELECT b.report_month, mm.group_code, SUM(b.qty_actual)
        FROM mines_booked_qty_actual_monthly b
        JOIN mines_master mm ON mm.mine_code = b.mine_code
        WHERE b.report_month IN ({ph})
        GROUP BY b.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual in cur.fetchall():
        booked_actual.setdefault(rm, {})[group_code] = actual

    booked_plan = {}
    cur.execute(f"""
        SELECT p.report_month, mm.group_code, SUM(p.qty_plan)
        FROM mines_booked_qty_plan_monthly p
        JOIN mines_master mm ON mm.mine_code = p.mine_code
        WHERE p.report_month IN ({ph})
        GROUP BY p.report_month, mm.group_code
    """, report_months)
    for rm, group_code, plan in cur.fetchall():
        booked_plan.setdefault(rm, {})[group_code] = plan

    for rm in report_months:
        groups = set(booked_actual.get(rm, {})) | set(booked_plan.get(rm, {}))
        for group_code in groups:
            out[rm]["iron_ore_sales"][group_code] = {
                "actual": booked_actual.get(rm, {}).get(group_code),
                "plan": booked_plan.get(rm, {}).get(group_code),
            }

    sales_desp_actual = {}
    cur.execute(f"""
        SELECT d.report_month, mm.group_code, SUM(d.qty_actual)
        FROM mines_despatch_actual_monthly d
        JOIN mines_master mm ON mm.mine_code = d.mine_code
        WHERE d.report_month IN ({ph}) AND d.end_use_code = 'SALES'
        GROUP BY d.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual in cur.fetchall():
        sales_desp_actual.setdefault(rm, {})[group_code] = actual

    sales_desp_plan = {}
    cur.execute(f"""
        SELECT pl.report_month, mm.group_code, SUM(pl.qty_plan)
        FROM mines_despatch_plan_monthly pl
        JOIN mines_master mm ON mm.mine_code = pl.mine_code
        WHERE pl.report_month IN ({ph}) AND pl.end_use_code = 'SALES'
        GROUP BY pl.report_month, mm.group_code
    """, report_months)
    for rm, group_code, plan in cur.fetchall():
        sales_desp_plan.setdefault(rm, {})[group_code] = plan

    for rm in report_months:
        groups = set(sales_desp_actual.get(rm, {})) | set(sales_desp_plan.get(rm, {}))
        for group_code in groups:
            out[rm]["iron_ore_sales_despatch"][group_code] = {
                "actual": sales_desp_actual.get(rm, {}).get(group_code),
                "plan": sales_desp_plan.get(rm, {}).get(group_code),
            }

    conn.close()
    return out


def get_iron_ore_mines_series(report_months: List[str]) -> Dict[str, Any]:
    """Flat month-wise mine-level Iron Ore rows for the reports page
    (/reports/iron-ore-mines) — no roll-up, the frontend groups by
    scope/material/mode itself. All quantities are '000 T.

      production:     [{report_month, mine_code, group_code, material_code,
                        actual, plan}]  — LUMP / FINES only
      despatch:       [{report_month, mine_code, group_code, material_code,
                        transport_mode, end_use_code, actual}]
                        — LUMP / FINES / DUMP_FINES / TAILINGS / PELLETS,
                          mode RAIL / ROAD
      despatch_plan:  [{report_month, mine_code, group_code, material_code,
                        end_use_code, plan}]  — Plan has no Rail/Road split
    """
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {"production": [], "despatch": [], "despatch_plan": []}
    if not report_months:
        conn.close()
        return out
    ph = ",".join("?" * len(report_months))

    cur.execute(f"""
        SELECT p.report_month, p.mine_code, mm.group_code, p.material_code,
               p.qty_actual, p.qty_plan
        FROM mines_production_monthly p
        JOIN mines_master mm ON mm.mine_code = p.mine_code
        WHERE p.report_month IN ({ph})
    """, report_months)
    for rm, mine, grp, mat, act, plan in cur.fetchall():
        out["production"].append({
            "report_month": rm, "mine_code": mine, "group_code": grp,
            "material_code": mat, "actual": act, "plan": plan,
        })

    cur.execute(f"""
        SELECT d.report_month, d.mine_code, mm.group_code, d.material_code,
               d.transport_mode, d.end_use_code, d.qty_actual
        FROM mines_despatch_actual_monthly d
        JOIN mines_master mm ON mm.mine_code = d.mine_code
        WHERE d.report_month IN ({ph})
    """, report_months)
    for rm, mine, grp, mat, mode, eu, act in cur.fetchall():
        out["despatch"].append({
            "report_month": rm, "mine_code": mine, "group_code": grp,
            "material_code": mat, "transport_mode": mode, "end_use_code": eu,
            "actual": act,
        })

    cur.execute(f"""
        SELECT pl.report_month, pl.mine_code, mm.group_code, pl.material_code,
               pl.end_use_code, pl.qty_plan
        FROM mines_despatch_plan_monthly pl
        JOIN mines_master mm ON mm.mine_code = pl.mine_code
        WHERE pl.report_month IN ({ph})
    """, report_months)
    for rm, mine, grp, mat, eu, plan in cur.fetchall():
        out["despatch_plan"].append({
            "report_month": rm, "mine_code": mine, "group_code": grp,
            "material_code": mat, "end_use_code": eu, "plan": plan,
        })

    conn.close()
    return out


# ── "Special Steel Plants Physical Performance" report ────────────────────────
# Backing store for page_special_steel_physical.py + its two data-entry pages.
# All physical figures are '000 T. See migrate_add_special_steel_physical.sql.

def get_ss_phys_perf():
    """-> (meta, perf):
      meta[(plant, series)] = {capacity_kt, best_actual_kt, best_year, remark, sort_order}
      perf[(financial_year, plant, series, metric)] = value_kt
    """
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT plant, series, capacity_kt, best_actual_kt, best_year, remark, sort_order "
                "FROM special_steel_phys_meta")
    meta = {
        (p, s): {"capacity_kt": cap, "best_actual_kt": ba, "best_year": by,
                 "remark": rm, "sort_order": so or 0}
        for p, s, cap, ba, by, rm, so in cur.fetchall()
    }
    cur.execute("SELECT financial_year, plant, series, metric, value_kt FROM special_steel_phys_perf")
    perf = {(fy, p, s, m): v for fy, p, s, m, v in cur.fetchall()}
    conn.close()
    return meta, perf


def save_ss_phys_meta(rows):
    """Upsert special_steel_phys_meta rows: {plant, series, capacity_kt,
    best_actual_kt, best_year, remark, sort_order}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO special_steel_phys_meta
                (plant, series, capacity_kt, best_actual_kt, best_year, remark, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plant, series) DO UPDATE SET
                capacity_kt = excluded.capacity_kt, best_actual_kt = excluded.best_actual_kt,
                best_year = excluded.best_year, remark = excluded.remark,
                sort_order = excluded.sort_order
        """, (r["plant"], r["series"], r.get("capacity_kt"), r.get("best_actual_kt"),
              r.get("best_year"), r.get("remark"), int(r.get("sort_order") or 0)))
    conn.commit()
    conn.close()
    return len(rows)


def save_ss_phys_perf(rows):
    """Upsert special_steel_phys_perf rows: {financial_year, plant, series,
    metric, value_kt}. value_kt None deletes the cell."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for r in rows:
        key = (r["financial_year"], r["plant"], r["series"], r["metric"])
        if r.get("value_kt") is None:
            cur.execute("DELETE FROM special_steel_phys_perf WHERE financial_year=? AND plant=? "
                        "AND series=? AND metric=?", key)
        else:
            cur.execute("""
                INSERT INTO special_steel_phys_perf
                    (financial_year, plant, series, metric, value_kt)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(financial_year, plant, series, metric)
                DO UPDATE SET value_kt = excluded.value_kt
            """, (*key, r["value_kt"]))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def get_ss_phys_notes(financial_year):
    """-> [(sort_order, note_text), ...] ordered."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT sort_order, note_text FROM special_steel_phys_note "
                "WHERE financial_year=? ORDER BY sort_order", (financial_year,))
    rows = cur.fetchall()
    conn.close()
    return [(so, t) for so, t in rows]


def save_ss_phys_notes(financial_year, rows):
    """Replace every note for a FY with `rows`: {sort_order, note_text}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM special_steel_phys_note WHERE financial_year=?", (financial_year,))
    for r in rows:
        text = (r.get("note_text") or "").strip()
        if not text:
            continue
        cur.execute("INSERT INTO special_steel_phys_note (financial_year, sort_order, note_text) "
                    "VALUES (?, ?, ?)", (financial_year, int(r.get("sort_order") or 0), text))
    conn.commit()
    conn.close()
    return len(rows)


def get_ss_ipt_requirement(financial_year):
    """-> [{item, from_plant, to_plant, plan_kt, sort_order}, ...] ordered."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT item, from_plant, to_plant, plan_kt, sort_order
        FROM special_steel_ipt_requirement WHERE financial_year=?
        ORDER BY sort_order, item, from_plant, to_plant
    """, (financial_year,))
    rows = [{"item": i, "from_plant": f, "to_plant": t, "plan_kt": p, "sort_order": so or 0}
            for i, f, t, p, so in cur.fetchall()]
    conn.close()
    return rows


def list_ss_ipt_requirement_fys():
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT financial_year FROM special_steel_ipt_requirement "
                "ORDER BY financial_year DESC")
    fys = [r[0] for r in cur.fetchall()]
    conn.close()
    return fys


def save_ss_ipt_requirement(financial_year, rows):
    """Upsert a batch of IPT-requirement rows for one FY. Each row:
    {item, from_plant, to_plant, plan_kt, sort_order} plus optional
    orig_item/orig_from_plant/orig_to_plant — if the natural key changed,
    the old row is deleted first (same rename handling as ipt_table)."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for r in rows:
        item = (r.get("item") or "").strip()
        frm, to = (r.get("from_plant") or "").strip(), (r.get("to_plant") or "").strip()
        if not item or not frm or not to or frm == to:
            continue
        oi, of, ot = r.get("orig_item"), r.get("orig_from_plant"), r.get("orig_to_plant")
        if oi and (oi != item or of != frm or ot != to):
            cur.execute("DELETE FROM special_steel_ipt_requirement WHERE financial_year=? "
                        "AND item=? AND from_plant=? AND to_plant=?", (financial_year, oi, of, ot))
        cur.execute("""
            INSERT INTO special_steel_ipt_requirement
                (financial_year, item, from_plant, to_plant, plan_kt, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(financial_year, item, from_plant, to_plant)
            DO UPDATE SET plan_kt = excluded.plan_kt, sort_order = excluded.sort_order
        """, (financial_year, item, frm, to, r.get("plan_kt"), int(r.get("sort_order") or 0)))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def delete_ss_ipt_requirement(financial_year, item, from_plant, to_plant):
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM special_steel_ipt_requirement WHERE financial_year=? AND item=? "
                "AND from_plant=? AND to_plant=?", (financial_year, item, from_plant, to_plant))
    conn.commit()
    conn.close()
