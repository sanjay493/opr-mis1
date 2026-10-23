"""Stock repository on the v2 schema: stock_monthly (v1 stock_table),
sail_sales_monthly (v1 sail_sales_table) and sail_stock_snapshot (v1
sail_stock_snapshot_table).

Same public names, signatures, return shapes, row types and exceptions as
repo/stock.py. Renamed columns are aliased back to their v1 names
(stock_month <- report_month, plant_name <- plant_code).

ORDER. v1's month_rows had no ORDER BY; its WHERE stock_month IN (...) was
served by the primary key (stock_month, plant_name, item_type, stock_type),
which v2's primary key repeats: the order is explicit here.

SNAPSHOT DATES. v1 kept snapshot_date as CHAR(10) text, v2 as a DATE. A read
matches the stored date only for the canonical 'YYYY-MM-DD' spelling
(the only spelling any stored v1 value has; the migration checked it): any
other string matched nothing in v1 and returns None here without asking
MySQL, which would convert '2021-1-4' to a date and match. A write of a
string that is not a canonical date is refused (OutOfModelError, before
anything is written; parity_exceptions.md §2).

WRITES. Every write bumps first (skipped in a dry run) and checks the v1
column limits before anything is written, raising v1's own errors (1048 /
1406 with v1's column names). The month is cut to CHAR(7) as MySQL cut it
(_keys.fit_month); a month or plant the masters lack is created
(_keys.ensure_month / ensure_plant). save_stock_entry's activity 'old' is
v1's own SELECT, run with the raw month.
"""
from typing import Optional

import pymysql

import activity_context
from dbengine import connect
from repo import conn as rc
from repo import version as _ver
from repo.conn import row_dict as _row_dict
from repo import _keys
from repo.v2codec import CodecError, parse_date

_STOCK_V1 = ("SELECT report_month AS stock_month, plant_code AS plant_name, item_type, stock_type, stock "
             "FROM stock_monthly")
_INVALID_JSON = 3140


# ── Moved from db.py ─────────────────────────────────────────────────────────

def save_stock_entry(stock_month: str, plant: str, item_type: str,
                     stock_type: str = "", stock: Optional[float] = None):
    """Upsert one opening-stock record ('000T, as on 1st of stock_month)."""
    month = _keys.fit_month(stock_month)
    _keys.fits("stock_month", month, 7, nullable=False)
    _keys.fits("plant_name", plant, 32, nullable=False)
    _keys.fits("item_type", item_type, 64, nullable=False)
    _keys.fits("stock_type", stock_type, 64, nullable=False)
    _keys.check_month(month, "stock_month")
    _keys.check_plant_model(plant, "plant_name", 32)
    conn = connect()
    try:
        old = _row_dict(conn, _STOCK_V1 + " WHERE report_month=%s AND plant_code=%s AND item_type=%s "
                                          "AND stock_type=%s", (stock_month, plant, item_type, stock_type))
        cur = conn.cursor()
        _ver.bump(cur)
        _keys.ensure_month(cur, month, bump=False)
        _keys.ensure_plant(cur, plant, bump=False)
        cur.execute("""
            INSERT INTO stock_monthly (report_month, plant_code, item_type, stock_type, stock)
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE stock = new.stock
        """, (month, plant, item_type, stock_type, stock))
        conn.commit()
    finally:
        conn.close()
    new = {"stock_month": stock_month, "plant_name": plant, "item_type": item_type,
           "stock_type": stock_type, "stock": stock}
    activity_context.record(f"stock_table/{plant}/{item_type}/{stock_month}", old, new)


# ── Named queries ────────────────────────────────────────────────────────────
# stock_table

def plant_month_rows(cur, plant, stock_month):
    """fetchall() of (item_type, stock_type, stock) for one plant/stock_month.
    main /api/stock-data."""
    cur.execute(
        "SELECT item_type, stock_type, stock FROM stock_monthly "
        "WHERE plant_code=%s AND report_month=%s ORDER BY item_type, stock_type",
        (plant, stock_month),
    )
    return cur.fetchall()


def month_rows(cur, months):
    """fetchall() of (stock_month, plant_name, item_type, stock_type, stock)
    over months. page_opening_stock._load_stock."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
        {_STOCK_V1} WHERE report_month IN ({ph})
        ORDER BY report_month, plant_code, item_type, stock_type
    """, months)
    return cur.fetchall()


def plants_for_month(stock_month):
    """{plant_name} with any stock_table row for the month. page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT DISTINCT plant_code FROM stock_monthly WHERE report_month = %s",
                    [stock_month])
        return {r[0] for r in cur.fetchall()}


# sail_sales_table / sail_stock_snapshot_table (SAIL 1-page report)

def upsert_sales(cur, month, item, data_json):
    """Upsert one sales row (data_json already serialised) on the caller's
    cursor; the caller commits. main /api/sail-1page/confirm."""
    stored_month = _keys.fit_month(month)
    _keys.fits("report_month", stored_month, 7, nullable=False)
    _keys.check_month(stored_month)
    _ver.bump(cur)
    _keys.ensure_month(cur, stored_month, bump=False)
    try:
        cur.execute("""
                    INSERT INTO sail_sales_monthly (report_month, item_name, data_json)
                    VALUES (%s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE data_json = new.data_json
                """, (stored_month, item, data_json))
    except (pymysql.err.DataError, pymysql.err.OperationalError) as e:
        if e.args and e.args[0] == _INVALID_JSON:      # v1's message names v1's table
            raise type(e)(e.args[0], str(e.args[1]).replace("'sail_sales_monthly.", "'sail_sales_table.")) from None
        raise


def _snapshot_date(value):
    """The DATE for a v1 snapshot_date string (CHAR(10), trailing spaces cut
    as MySQL did), or None when it is not a canonical 'YYYY-MM-DD'."""
    try:
        return parse_date(_keys.fit_char(value, 10))
    except CodecError:
        return None


def upsert_stock_snapshot(cur, snapshot_date, item, value):
    """Upsert one stock snapshot on the caller's cursor; the caller commits.
    main /api/sail-1page/confirm."""
    _keys.fits("snapshot_date", snapshot_date, 10, nullable=False)
    _keys.fits("item_name", item, 32, nullable=False)
    day = _snapshot_date(snapshot_date)
    if day is None:
        raise _keys.OutOfModelError(f"snapshot_date {snapshot_date!r}: v1 stored it as text, the v2 DATE "
                                    "holds only a 'YYYY-MM-DD' date")
    _ver.bump(cur)
    cur.execute("""
                INSERT INTO sail_stock_snapshot (snapshot_date, item_name, value)
                VALUES (%s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE value = new.value
            """, (day, item, value))


def sales_data_row(cur, month, item):
    """fetchone() of (data_json,), or None. page_one_page_report._sales_data."""
    cur.execute("SELECT data_json FROM sail_sales_monthly WHERE report_month=%s AND item_name=%s", (month, item))
    return cur.fetchone()


def snapshot_value_row(cur, snapshot_date, item):
    """fetchone() of (value,), or None. page_one_page_report._stock_value."""
    if not isinstance(snapshot_date, str) or _snapshot_date(snapshot_date) is None \
            or _keys.fit_char(snapshot_date, 10) != snapshot_date:
        return None         # no stored v1 value is spelled that way (see the module docstring)
    cur.execute("SELECT value FROM sail_stock_snapshot WHERE snapshot_date=%s AND item_name=%s",
                (snapshot_date, item))
    return cur.fetchone()
