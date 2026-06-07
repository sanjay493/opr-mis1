import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "mis_reports.db")
PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL']

def init_db():
    """Initializes the database and creates the production tables if they don't exist."""
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
    
    conn.commit()
    conn.close()

def get_ytd_months(report_month: str) -> List[str]:
    """
    Returns a list of month strings ('Month Year') from April of the 
    current financial year up to the report month.
    """
    months_order = [
        "April", "May", "June", "July", "August", "September",
        "October", "November", "December", "January", "February", "March"
    ]
    try:
        m_name, y_str = report_month.split()
        year = int(y_str)
    except ValueError:
        return [report_month]
        
    if m_name not in months_order:
        return [report_month]
        
    idx = months_order.index(m_name)
    
    # Determine starting year of the financial year
    if idx >= 9:  # Jan, Feb, Mar belong to the FY starting in previous calendar year
        fy_start_year = year - 1
    else:
        fy_start_year = year
        
    ytd_list = []
    for i in range(idx + 1):
        cur_m = months_order[i]
        cur_y = fy_start_year + 1 if i >= 9 else fy_start_year
        ytd_list.append(f"{cur_m} {cur_y}")
        
    return ytd_list

def get_cply_month(report_month: str) -> str:
    """Returns the month name for the previous year (e.g. November 2025 -> November 2024)."""
    try:
        m_name, y_str = report_month.split()
        year = int(y_str)
        return f"{m_name} {year - 1}"
    except ValueError:
        return report_month

def get_sail_production_actual(month: str, item: str) -> Optional[float]:
    """Calculates the sum of actuals across active plants. Falls back to explicit 'SAIL' record if none found."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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
