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

    # 8. Techno parameter master — normalised single-source (replaces techno_param_master).
    #    param_name : canonical parameter name ("Coke Rate", "Coal to Hot Metal")
    #    row_label  : entity label ("BSP", "BSP Plant Shop", "BSL BF-3", "BSP Merchant Mill")
    #    Migrate once: rename old techno_* tables to _old_* on first run.
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='techno_param'"
    )
    if not cursor.fetchone():
        # One-time migration: rename legacy tables so new schema can be created clean.
        for _old in ("techno_param_master", "techno_table", "techno_monthly", "techno_target",
                     "plant_units", "techno_param_types"):
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (_old,)
            )
            if cursor.fetchone():
                cursor.execute(f"ALTER TABLE {_old} RENAME TO _old_{_old}")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_param (
            param_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            param_name TEXT NOT NULL,
            row_label  TEXT NOT NULL,
            unit       TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            UNIQUE(param_name, row_label)
        )
    """)

    # 8b. Group membership (many-to-many param ↔ page group)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_param_group (
            param_id   INTEGER NOT NULL REFERENCES techno_param(param_id),
            group_code TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            PRIMARY KEY(param_id, group_code)
        )
    """)

    # 9. Techno monthly actuals (replaces techno_table + techno_monthly)
    #    actual            : monthly value only
    #    till_month_actual : plant-reported Apr→month cumulative; NULL = compute on fly
    #    source            : 'manual' | 'excel'
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_actuals (
            report_month      TEXT NOT NULL,
            param_id          INTEGER NOT NULL REFERENCES techno_param(param_id),
            actual            REAL,
            till_month_actual REAL,
            source            TEXT DEFAULT 'manual',
            PRIMARY KEY(report_month, param_id)
        )
    """)

    # 10. Techno annual targets per FY ('2026-27')
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techno_target (
            fy       TEXT,
            param_id INTEGER REFERENCES techno_param(param_id),
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


def save_techno_value(month: str, param_id: int, actual: Optional[float],
                      till_month_actual: Optional[float] = None,
                      source_priority: int = 5):
    """Upsert one monthly techno actual into techno_actuals.

    actual            : monthly value (last write wins).
    till_month_actual : plant-reported Apr→month cumulative; existing value
                        is preserved when None is passed (don't clear stored YTD).
    source_priority   : informational only (5=extractor/manual, 4=computed).
    """
    source = 'excel' if source_priority >= 5 else 'computed'
    init_db()
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
