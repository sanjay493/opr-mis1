"""Page configuration repository: page_configs, the per-month saved JSON blob
of each report page (main.py's /api/data reads it, /api/save-data writes it).

The db.py functions moved here verbatim (re-exported from db.py).
"""
import json
from typing import List, Optional

from dbengine import connect
from repo import version as _ver


def get_page_config(month: str, page_number: int) -> Optional[dict]:
    """Retrieves standard page configuration if saved in DB."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_configs WHERE report_month = %s AND page_number = %s", (month, page_number))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def get_all_page_configs(month: str) -> List[dict]:
    """Retrieves all standard page configurations for a month, ordered by page number."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_configs WHERE report_month = %s ORDER BY page_number ASC", (month,))
    rows = cursor.fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]


def save_page_config(month: str, page_number: int, page_data: dict):
    """Saves or updates a page configuration."""
    conn = connect()
    cursor = conn.cursor()
    _ver.bump(conn)
    cursor.execute("""
        INSERT INTO page_configs (report_month, page_number, page_data)
        VALUES (%s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE page_data = new.page_data
    """, (month, page_number, json.dumps(page_data)))
    conn.commit()
    conn.close()
