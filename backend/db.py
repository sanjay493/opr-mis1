import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from constants import ALL_PLANTS as PLANTS
from techno_registry import canonical_unit as _canon_unit

DB_PATH = os.path.join(os.path.dirname(__file__), "mis_reports.db")

_INIT_DONE = False

def init_db():
    """Initializes the database and creates the production tables if they don't exist.
    Runs the DDL only once per process — subsequent calls are no-ops."""
    global _INIT_DONE
    if _INIT_DONE:
        return
    _INIT_DONE = True
    conn = sqlite3.connect(DB_PATH)
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
            created_at    TEXT NOT NULL,
            updated_at    TEXT
        )
    """)

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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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

def save_production_plan(month: str, plant: str, item: str, value: Optional[float]):
    """Saves or updates a planned production record."""
    item = item.strip()
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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

def get_page_config(month: str, page_number: int) -> Optional[dict]:
    """Retrieves standard page configuration if saved in DB."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_configs WHERE report_month = ? AND page_number = ?", (month, page_number))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

def get_all_page_configs(month: str) -> List[dict]:
    """Retrieves all standard page configurations for a month, ordered by page number."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_configs WHERE report_month = ? ORDER BY page_number ASC", (month,))
    rows = cursor.fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]

def save_page_config(month: str, page_number: int, page_data: dict):
    """Saves or updates a page configuration."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO page_configs (report_month, page_number, page_data)
        VALUES (?, ?, ?)
        ON CONFLICT(report_month, page_number) 
        DO UPDATE SET page_data = excluded.page_data
    """, (month, page_number, json.dumps(page_data)))
    conn.commit()
    conn.close()

def save_techno_parameter(month: str, plant: str, parameter: str, unit: str,
                          month_val: Optional[float], ytd_val: Optional[float] = None):
    """Upsert a techno actual by (row_label=plant, param_name=parameter).
    ytd_val is ignored — YTD is computed on the fly."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "DELETE FROM special_steel_orders WHERE report_month=? AND plant_name=?",
        (month, plant),
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def save_special_steel_entry(month: str, plant: str, product: str, quality_grade: str,
                             sort_order: int = 0, order_qty: Optional[float] = None,
                             actual_despatch: Optional[float] = None,
                             section: str = ""):
    """Upsert one row into special_steel_orders. section stays '' for plants
    whose report has no section breakdown."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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


def save_stock_entry(stock_month: str, plant: str, item_type: str,
                     stock_type: str = "", stock: Optional[float] = None):
    """Upsert one opening-stock record ('000T, as on 1st of stock_month)."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO stock_table (stock_month, plant_name, item_type, stock_type, stock)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(stock_month, plant_name, item_type, stock_type)
        DO UPDATE SET stock = excluded.stock
    """, (stock_month, plant, item_type, stock_type, stock))
    conn.commit()
    conn.close()


def save_ipt_entry(month: str, item: str, from_plant: str, to_plant: str,
                   unit: str = "T", sort_order: int = 0,
                   plan: Optional[float] = None, actual: Optional[float] = None,
                   plan_tonnage: Optional[float] = None,
                   actual_tonnage: Optional[float] = None):
    """Upsert one IPT route record for a month.
    For Rake routes, plan/actual are rake counts and
    plan_tonnage/actual_tonnage hold the tonnes equivalent."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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

    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
        conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO techno_target (fy, param_id, target)
        VALUES (?, ?, ?)
        ON CONFLICT(fy, param_id) DO UPDATE SET target = excluded.target
    """, (fy, param_id, target))
    conn.commit()
    conn.close()


def log_extraction(plant: str, report_month: str, file_name: str, sheet_name: str,
                   source_type: str, items_extracted: int):
    """Appends a record to the extraction audit log."""
    init_db()
    from datetime import datetime
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO extraction_log (logged_at, plant_name, report_month, file_name, sheet_name, source_type, items_extracted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), plant, report_month, file_name, sheet_name, source_type, items_extracted))
    conn.commit()
    conn.close()


def get_pdf_item_aliases(plant: str) -> Dict[str, Any]:
    """User-saved PDF label corrections for a plant: {pdf_label: (item_name, convert_t)}."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO pdf_item_alias (plant_name, pdf_label, item_name, convert_t)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(plant_name, pdf_label)
        DO UPDATE SET item_name = excluded.item_name, convert_t = excluded.convert_t
    """, (plant, pdf_label, item_name, convert_t))
    conn.commit()
    conn.close()


def get_extraction_logs(limit: int = 60, plant: Optional[str] = None,
                         source_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns the most recent extraction log entries, newest first.
    Optional plant/source_type filters let a page (e.g. /data-entry/techno)
    show only its own entries from this shared log table."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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

def _raw_upsert_techno_data(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str = ''):
    """Bare INSERT/UPDATE with no post-save hooks — used by upsert_techno_data
    itself and by _maybe_recompute_derived_params (which must write its
    recomputed values without re-triggering itself)."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(plant, report_month, unit) DO UPDATE SET
            techno_json = excluded.techno_json,
            source_file = excluded.source_file,
            created_at  = datetime('now')
    """, (plant, report_month, unit, json.dumps(techno_json), source_file))
    conn.commit()
    conn.close()


def upsert_techno_data(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str = ''):
    """Insert or replace techno data for one plant/unit/month.

    SAIL's BF_Shop rollup is no longer auto-refreshed here on every
    contributing plant's save (see api_techno_manual.py's _apply_sail_bf) —
    it's now a read-time fallback used wherever SAIL techno data is
    displayed, computed only when no row already exists in techno_data for
    plant='SAIL'. Call the /sail/calculate endpoint explicitly if you
    deliberately want to publish a calculated SAIL BF_Shop figure into the DB.
    """
    _raw_upsert_techno_data(plant, report_month, unit, techno_json, source_file)
    _maybe_recompute_derived_params(plant, report_month, unit)
    _log_techno_save(plant, report_month, unit, techno_json, source_file)


def _log_techno_save(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str) -> None:
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


def _maybe_recompute_derived_params(plant: str, report_month: str, unit: str) -> None:
    """Recompute tmi/fuel_rate for this (plant, report_month, unit) from
    whatever inputs are currently stored, and overwrite the stored value if
    it differs. Writes via _raw_upsert_techno_data (never upsert_techno_data)
    so this cannot re-trigger itself; safe to call unconditionally after
    every save since it's a no-op once the stored value already matches."""
    try:
        data = get_techno_data(plant, report_month, unit).get(unit, {})
        if not data:
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT source_file FROM techno_data WHERE plant=? AND report_month=? AND unit=?",
            (plant, report_month, unit),
        )
        row = cur.fetchone()
        conn.close()
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
            _raw_upsert_techno_data(plant, report_month, unit, updated, source_file=existing_source_file)
    except Exception as e:
        print(f"[db] tmi/fuel_rate recompute failed for {plant}/{report_month}/{unit}: {e}")


# unit names that feed the SAIL BF_Shop rollup — 'BF_Shop' for most plants,
# 'BF-5' for ISP (single-furnace plant, no separate BF_Shop row ever stored).
# No longer auto-refreshed on every contributing plant's save (removed from
# upsert_techno_data above) — see api_techno_manual.py's _apply_sail_bf for
# the explicit calculate-and-store path, and page_techno.py's
# calculate_sail_actuals for the read-time fallback.
_SAIL_BF_UNITS = ("BF_Shop", "BF-5")


def merge_upsert_techno_data(plant: str, report_month: str, unit: str, new_techno_json: Dict, source_file: str = ''):
    """Merge new_techno_json into any existing row (non-null values win; existing non-null kept if new value is null).
    Use this when multiple source files contribute different parameters to the same plant/unit/month."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT techno_json FROM techno_data WHERE plant=? AND report_month=? AND unit=?",
        [plant, report_month, unit],
    )
    row = cursor.fetchone()
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

    upsert_techno_data(plant, report_month, unit, merged, source_file)


def get_production_actual_value(plant: str, item_name: str, report_month: str) -> Optional[float]:
    """Single plant/item/month lookup from production_table (no cross-plant
    aggregation) - used to show 'current DB value' next to a freshly-extracted
    figure during upload preview, so the user can compare before confirming."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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
    preview row in-place, keyed by its item_name. Used by upload preview
    endpoints so the UI can show DB-vs-extracted side by side before insert."""
    if not rows:
        return rows
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT item_name, month_actual FROM production_table WHERE plant_name=? AND report_month=?",
        (plant, report_month),
    )
    current = {item: val for item, val in cursor.fetchall()}
    conn.close()
    for r in rows:
        item = r.get("item_name") or r.get("pdf_label")
        r["db_value"] = current.get(item) if item else None
    return rows


def enrich_techno_records_with_db(records: List[Dict[str, Any]], plant: str, report_month: str) -> List[Dict[str, Any]]:
    """Attach 'db_json' (current techno_data {month:{}, till_month:{}} for the
    same plant/unit/report_month, or empty dicts if none exists yet) to each
    preview record in-place. Used by techno upload preview endpoints so the UI
    can show DB-vs-extracted side by side, for both month and cumulative
    values, before the user confirms the insert."""
    if not records:
        return records
    existing = get_techno_data(plant, report_month)
    for r in records:
        r["db_json"] = existing.get(r.get("unit"), {"month": {}, "till_month": {}})
    return records


def get_techno_data(plant: str, report_month: str, unit: str = None) -> Dict:
    """Return {unit: {month: {...}, till_month: {...}}} for a given plant/month."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
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

    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    Otherwise returns all units for the plant."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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
    """Save or update techno plan data for a plant/unit/FY in unified table."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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


def get_techno_plant_plan(plant: str, fy: str) -> Dict[str, Any]:
    """Fetch plant-level techno plan data (unit='Shop') for a FY."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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
    """Fetch SAIL consolidated techno plan data (plant_name='SAIL', unit='Shop') for a FY."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
