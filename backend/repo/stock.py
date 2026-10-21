"""Stock repository: stock_table (plant opening stock, '000T as on the 1st
of stock_month), sail_sales_table (SAIL 1-page report sales, data_json) and
sail_stock_snapshot_table (SAIL 1-page report stock snapshots).

save_stock_entry moved from db.py verbatim (re-exported from db.py). The
named cursor-level queries run on the caller's cursor and return the plain
fetchone() / fetchall() result.
"""
from typing import Optional

import activity_context
from dbengine import connect
from repo import version as _ver
from repo import conn as rc
from repo.conn import row_dict as _row_dict


# ── Moved from db.py ─────────────────────────────────────────────────────────

def save_stock_entry(stock_month: str, plant: str, item_type: str,
                     stock_type: str = "", stock: Optional[float] = None):
    """Upsert one opening-stock record ('000T, as on 1st of stock_month)."""
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM stock_table WHERE stock_month=%s AND plant_name=%s AND item_type=%s AND stock_type=%s",
        (stock_month, plant, item_type, stock_type))
    conn.execute("""
        INSERT INTO stock_table (stock_month, plant_name, item_type, stock_type, stock)
        VALUES (%s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE stock = new.stock
    """, (stock_month, plant, item_type, stock_type, stock))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    new = {"stock_month": stock_month, "plant_name": plant, "item_type": item_type,
           "stock_type": stock_type, "stock": stock}
    activity_context.record(f"stock_table/{plant}/{item_type}/{stock_month}", old, new)


# ── Named queries (moved verbatim from callers) ──────────────────────────────
# stock_table

def plant_month_rows(cur, plant, stock_month):
    """fetchall() of (item_type, stock_type, stock) for one plant/stock_month.
    main /api/stock-data."""
    cur.execute(
        "SELECT item_type, stock_type, stock FROM stock_table "
        "WHERE plant_name=%s AND stock_month=%s ORDER BY item_type, stock_type",
        (plant, stock_month),
    )
    return cur.fetchall()


def month_rows(cur, months):
    """fetchall() of (stock_month, plant_name, item_type, stock_type, stock)
    over months. page_opening_stock._load_stock."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
        SELECT stock_month, plant_name, item_type, stock_type, stock
        FROM stock_table WHERE stock_month IN ({ph})
    """, months)
    return cur.fetchall()


def plants_for_month(stock_month):
    """{plant_name} with any stock_table row for the month. page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT DISTINCT plant_name FROM stock_table WHERE stock_month = %s",
                    [stock_month])
        return {r[0] for r in cur.fetchall()}


# sail_sales_table / sail_stock_snapshot_table (SAIL 1-page report)

def upsert_sales(cur, month, item, data_json):
    """Upsert one sales row (data_json already serialised) on the caller's
    cursor; the caller commits. main /api/sail-1page/confirm."""
    _ver.bump(cur)
    cur.execute("""
                INSERT INTO sail_sales_table (report_month, item_name, data_json)
                VALUES (%s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE data_json = new.data_json
            """, (month, item, data_json))


def upsert_stock_snapshot(cur, snapshot_date, item, value):
    """Upsert one stock snapshot on the caller's cursor; the caller commits.
    main /api/sail-1page/confirm."""
    _ver.bump(cur)
    cur.execute("""
                INSERT INTO sail_stock_snapshot_table (snapshot_date, item_name, value)
                VALUES (%s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE value = new.value
            """, (snapshot_date, item, value))


def sales_data_row(cur, month, item):
    """fetchone() of (data_json,), or None. page_one_page_report._sales_data."""
    cur.execute("SELECT data_json FROM sail_sales_table WHERE report_month=%s AND item_name=%s", (month, item))
    return cur.fetchone()


def snapshot_value_row(cur, snapshot_date, item):
    """fetchone() of (value,), or None. page_one_page_report._stock_value."""
    cur.execute("SELECT value FROM sail_stock_snapshot_table WHERE snapshot_date=%s AND item_name=%s",
                (snapshot_date, item))
    return cur.fetchone()
