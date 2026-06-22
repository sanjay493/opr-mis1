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
    
    # 4. Techno-Economic table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_table (
            report_month TEXT,
            plant_name TEXT,
            parameter_name TEXT,
            unit TEXT,
            month_actual REAL,
            ytd_actual REAL,
            PRIMARY KEY (report_month, plant_name, parameter_name)
        )
    """)

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

    # 8. Techno-economic parameter master (one row per group/section/row-label)
    #    group_code : MAJOR / COKE_SINTER / IRON_MAKING / BOF / MILL_* / BSL / BSP ...
    #    section    : parameter name (cross-plant) or unit name (plant-specific legacy)
    #    row_label  : 'PLANT UNIT' (cross-plant) or parameter name (legacy)
    #    unit_type  : BF / SMS / MILL / COKE / SINTER / GENERAL (from plant_registry.py)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_param_master (
            param_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            group_code TEXT NOT NULL,
            section    TEXT NOT NULL,
            row_label  TEXT NOT NULL,
            unit       TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            unit_type  TEXT DEFAULT NULL,
            UNIQUE (group_code, section, row_label)
        )
    """)
    try:
        cursor.execute("ALTER TABLE techno_param_master ADD COLUMN unit_type TEXT DEFAULT NULL")
    except Exception:
        pass  # column already exists

    # A. Plant unit registry — all physical units (furnaces, converters, mills) at each plant
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plant_units (
            unit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_code    TEXT NOT NULL,      -- 'BSP', 'DSP', 'RSP', 'BSL', 'ISP'
            unit_type     TEXT NOT NULL,      -- 'BF', 'SMS', 'MILL', 'COKE', 'SINTER', 'GENERAL'
            unit_name     TEXT NOT NULL,      -- 'BF-4', 'SMS-2', 'HSM', 'Shop'
            display_label TEXT NOT NULL,      -- 'BSP BF-4' used as cross-plant row_label
            is_shop       INTEGER DEFAULT 0,  -- 1 = plant-level average, not a physical unit
            is_active     INTEGER DEFAULT 1,  -- 0 = decommissioned
            sort_order    INTEGER DEFAULT 0,
            UNIQUE(plant_code, unit_type, unit_name)
        )
    """)

    # B. Standard techno-economic parameters per unit type with aggregation rules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_param_types (
            type_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_type    TEXT NOT NULL,      -- 'BF', 'SMS', 'MILL', 'COKE', 'SINTER', 'GENERAL'
            param_name   TEXT NOT NULL,      -- canonical parameter name
            unit_of_meas TEXT DEFAULT '',    -- 'Kg/THM', 'T/m³/day', '%'
            agg_method   TEXT DEFAULT 'weighted_avg',  -- how to compute shop average
            sort_order   INTEGER DEFAULT 0,
            UNIQUE(unit_type, param_name)
        )
    """)

    # 9. Techno monthly actuals (FK techno_param_master)
    #    cum_actual = plant-reported cumulative Apr → this month
    #    source_priority: higher number = more authoritative (default 5 = extractor)
    #      4 = computed aggregate (techno_aggregates.py)
    #      3 = secondary/fallback source
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_monthly (
            report_month    TEXT,
            param_id        INTEGER REFERENCES techno_param_master(param_id),
            actual          REAL,
            cum_actual      REAL,
            source_priority INTEGER DEFAULT 5,
            PRIMARY KEY (report_month, param_id)
        )
    """)
    # Add source_priority column to existing databases that predate this schema
    try:
        cursor.execute("ALTER TABLE techno_monthly ADD COLUMN source_priority INTEGER DEFAULT 5")
    except Exception:
        pass  # column already exists

    # 10. Techno annual targets per FY ('2026-27')
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_target (
            fy       TEXT,
            param_id INTEGER REFERENCES techno_param_master(param_id),
            target   REAL,
            PRIMARY KEY (fy, param_id)
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

    conn.commit()

    # Seed plant_units and techno_param_types from plant_registry.py (idempotent)
    try:
        from plant_registry import seed_plant_registry
        seed_plant_registry(conn)
    except Exception:
        pass  # non-critical — only affects registry metadata, not core data tables

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


def get_sail_production_actual(month: str, item: str) -> Optional[float]:
    """Calculates the sum of actuals across active plants. Falls back to explicit 'SAIL' record if none found."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if item == "Finished Steel":
        result = _fs_alias_sum(cursor, "production_table", month, PLANTS)
        if result is not None:
            conn.close()
            return result
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
            if v is not None:
                total += v
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

def save_techno_parameter(month: str, plant: str, parameter: str, unit: str, month_val: Optional[float], ytd_val: Optional[float]):
    """Saves or updates a techno-economic parameter record."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO techno_table (report_month, plant_name, parameter_name, unit, month_actual, ytd_actual)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(report_month, plant_name, parameter_name)
        DO UPDATE SET
            unit = excluded.unit,
            month_actual = excluded.month_actual,
            ytd_actual = excluded.ytd_actual
    """, (month, plant, parameter, unit, month_val, ytd_val))
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


def get_or_create_techno_param(group_code: str, section: str, row_label: str,
                               unit: str = "", sort_order: int = 0) -> int:
    """Return param_id for the master row, creating/updating it as needed."""
    unit = _canon_unit(unit, group_code, section)
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO techno_param_master (group_code, section, row_label, unit, sort_order)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(group_code, section, row_label)
        DO UPDATE SET unit = excluded.unit,
            sort_order = CASE WHEN excluded.sort_order > 0 THEN excluded.sort_order ELSE sort_order END
    """, (group_code, section, row_label, unit, sort_order))
    cur.execute("""
        SELECT param_id FROM techno_param_master
        WHERE group_code=? AND section=? AND row_label=?
    """, (group_code, section, row_label))
    pid = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return pid


def _techno_flat_key(group_code: str, section: str, row_label: str):
    """Derive (plant_name, parameter_name) for techno_table from param_master fields."""
    if group_code in ('MAJOR', 'COKE_SINTER', 'IRON_MAKING', 'SMS'):
        return (row_label, section)
    if group_code == 'BSL':
        return (f'BSL {section}', row_label)
    if group_code.startswith('MILL_'):
        return (f'{group_code[5:]} {section}', row_label)
    return (row_label, section)


def save_techno_value(month: str, param_id: int, actual: Optional[float],
                      cum_actual: Optional[float] = None,
                      source_priority: int = 5):
    """Upsert one monthly techno actual.

    Dual-writes to:
      techno_monthly  — legacy normalized store, used by manual-entry UI.
                        source_priority controls which write wins on conflict.
      techno_table    — canonical flat store, used by page_techno.py for display.
                        Always overwrites (source_priority enforced via techno_monthly).

    source_priority:
      5 = direct extractor write (default)
      4 = computed shop aggregate (techno_aggregates.py)
      3 = secondary/fallback source
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)

    # ── techno_monthly (priority-aware) ──────────────────────────────────────
    conn.execute("""
        INSERT INTO techno_monthly (report_month, param_id, actual, cum_actual, source_priority)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(report_month, param_id) DO UPDATE SET
            actual          = CASE WHEN excluded.source_priority >= source_priority
                                   THEN excluded.actual ELSE actual END,
            cum_actual      = CASE WHEN excluded.source_priority >= source_priority
                                   THEN COALESCE(excluded.cum_actual, cum_actual)
                                   ELSE cum_actual END,
            source_priority = CASE WHEN excluded.source_priority >= source_priority
                                   THEN excluded.source_priority ELSE source_priority END
    """, (month, param_id, actual, cum_actual, source_priority))

    # ── techno_table (flat display store) ────────────────────────────────────
    cur = conn.cursor()
    cur.execute(
        "SELECT group_code, section, row_label, unit FROM techno_param_master WHERE param_id=?",
        (param_id,),
    )
    master = cur.fetchone()
    if master:
        group_code, section, row_label, unit = master
        plant_name, parameter_name = _techno_flat_key(group_code, section, row_label)
        conn.execute("""
            INSERT INTO techno_table
                (report_month, plant_name, parameter_name, unit, month_actual, ytd_actual)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, parameter_name) DO UPDATE SET
                unit         = excluded.unit,
                month_actual = excluded.month_actual,
                ytd_actual   = excluded.ytd_actual
        """, (month, plant_name, parameter_name, unit or "", actual, cum_actual))

    conn.commit()
    conn.close()


def save_techno_monthly(param_id: int, report_month: str, actual: Optional[float],
                        cum_actual: Optional[float] = None,
                        source_priority: int = 5):
    """Alias for save_techno_value with param_id/month argument order used by techno_aggregates."""
    save_techno_value(report_month, param_id, actual, cum_actual, source_priority)


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


def get_extraction_logs(limit: int = 60) -> List[Dict[str, Any]]:
    """Returns the most recent extraction log entries, newest first."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, logged_at, plant_name, report_month, file_name, sheet_name, source_type, items_extracted
        FROM extraction_log
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
