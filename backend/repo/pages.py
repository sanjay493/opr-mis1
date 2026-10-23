"""Page configuration repository on the v2 schema: page_config (v1
page_configs; month column unchanged).

Same public names, signatures, return shapes and exceptions as
repo/pages.py. page_data stays MEDIUMTEXT, written as the same
json.dumps text, so the stored JSON comes back byte for byte (a JSON
column would re-order object keys). Reads order get_all_page_configs by
page_number as v1 did.

WRITES. One bump first (skipped in a dry run). The month is cut to CHAR(7)
as MySQL cut it and created in cal_month when missing (_keys.ensure_month);
a month string that is not 'YYYY-MM' is refused (OutOfModelError,
parity_exceptions.md §2). The table's JSON_VALID check refuses the
non-standard JSON text json.dumps writes for NaN / Infinity, which v1
stored: refused up front the same way, before anything is written.
"""
import json
from typing import List, Optional

from dbengine import connect
from repo import version as _ver
from repo import _keys


def get_page_config(month: str, page_number: int) -> Optional[dict]:
    """Retrieves standard page configuration if saved in DB."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_config WHERE report_month = %s AND page_number = %s", (month, page_number))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def get_all_page_configs(month: str) -> List[dict]:
    """Retrieves all standard page configurations for a month, ordered by page number."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_config WHERE report_month = %s ORDER BY page_number ASC", (month,))
    rows = cursor.fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]


def save_page_config(month: str, page_number: int, page_data: dict):
    """Saves or updates a page configuration."""
    text = json.dumps(page_data)
    try:
        json.dumps(page_data, allow_nan=False)
    except ValueError:
        raise _keys.OutOfModelError("page_data holds NaN / Infinity: v1 stored that text, "
                                    "the v2 page_data must be valid JSON") from None
    stored_month = _keys.fit_month(month)
    _keys.check_month(stored_month)
    conn = connect()
    try:
        cursor = conn.cursor()
        _ver.bump(cursor)
        _keys.ensure_month(cursor, stored_month, bump=False)
        cursor.execute("""
            INSERT INTO page_config (report_month, page_number, page_data)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE page_data = new.page_data
        """, (stored_month, page_number, text))
        conn.commit()
    finally:
        conn.close()
