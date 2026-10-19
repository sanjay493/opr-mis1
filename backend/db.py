import json
import os
import copy
import functools
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from constants import ALL_PLANTS as PLANTS
from techno_registry import canonical_unit as _canon_unit
import dbengine
from dbengine import Row, IntegrityError, OperationalError
import activity_context


def connect():
    """Single connection factory for the whole backend: a pooled MySQL
    connection (see dbengine.py). Deprecated alias kept for existing call
    sites; new code uses repo.conn.cursor() / repo.conn.tx()."""
    return dbengine.connect()


def _row_dict(conn, sql: str, params) -> Optional[dict]:
    """Fetch one row as a plain dict. Used to snapshot a row's 'old' state
    before an upsert/delete for the activity log (see activity_context.py)."""
    prev_factory = conn.row_factory
    conn.row_factory = Row
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.row_factory = prev_factory


def init_db():
    """No-op kept for existing callers. The MySQL schema is owned by
    scripts/mysql_schema.sql (plus scripts/migrate_*.sql), not created
    lazily at runtime."""
    return None

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


def shift_month(month: str, delta: int) -> str:
    """'YYYY-MM' shifted by `delta` calendar months (negative = earlier)."""
    y, m = int(month[:4]), int(month[5:7])
    idx = y * 12 + (m - 1) + delta
    return f"{idx // 12}-{idx % 12 + 1:02d}"


def get_trailing_months(end_month: str, n: int) -> List[str]:
    """n calendar months ending at end_month (inclusive), oldest first —
    a plain rolling window, unlike get_ytd_months/get_fy_months which reset
    at the April FY boundary. Used by pages whose source data is a rolling
    snapshot rather than an FY-aligned series (e.g. page_market_prices.py /
    page_macro_indicators.py's BigMint market-intelligence pages)."""
    return [shift_month(end_month, -i) for i in range(n - 1, -1, -1)]


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
        phs = ",".join("%s" for _ in regular)
        cursor.execute(
            f"SELECT SUM(month_actual) FROM {tbl} "
            f"WHERE report_month=%s AND plant_name IN ({phs}) AND item_name='Finished Steel'",
            [month] + regular,
        )
        r = cursor.fetchone()
        if r and r[0] is not None:
            total += r[0]
            found = True

    for p in alias:
        cursor.execute(
            f"SELECT month_actual FROM {tbl} WHERE report_month=%s AND plant_name=%s AND item_name='Finished Steel'",
            (month, p),
        )
        r = cursor.fetchone()
        if r and r[0] is not None:
            total += r[0]
            found = True
        else:
            cursor.execute(
                f"SELECT month_actual FROM {tbl} WHERE report_month=%s AND plant_name=%s AND item_name='Saleable Steel'",
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
        "SELECT month_actual FROM production_table WHERE report_month=%s AND plant_name='SAIL' AND item_name='Conversion'",
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
            "SELECT month_actual FROM production_table WHERE report_month=%s AND plant_name='SAIL' AND item_name='Finished Steel'",
            (month,),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    placeholders = ",".join("%s" for _ in PLANTS)
    query = f"""
        SELECT SUM(month_actual)
        FROM production_table
        WHERE report_month = %s
          AND plant_name IN ({placeholders})
          AND item_name = %s
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
        WHERE report_month = %s AND plant_name = 'SAIL' AND item_name = %s
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
            "SELECT month_actual FROM production_plan_table WHERE report_month=%s AND plant_name='SAIL' AND item_name='Finished Steel'",
            (month,),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    placeholders = ",".join("%s" for _ in PLANTS)
    query = f"""
        SELECT SUM(month_actual)
        FROM production_plan_table
        WHERE report_month = %s
          AND plant_name IN ({placeholders})
          AND item_name = %s
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
        WHERE report_month = %s AND plant_name = 'SAIL' AND item_name = %s
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

    plant_placeholders = ",".join("%s" for _ in PLANTS)
    month_placeholders = ",".join("%s" for _ in months)
    query = f"""
        SELECT SUM(month_actual)
        FROM production_table
        WHERE report_month IN ({month_placeholders})
          AND plant_name IN ({plant_placeholders})
          AND item_name = %s
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
          AND item_name = %s
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

    plant_placeholders = ",".join("%s" for _ in PLANTS)
    month_placeholders = ",".join("%s" for _ in months)
    query = f"""
        SELECT SUM(month_actual)
        FROM production_plan_table
        WHERE report_month IN ({month_placeholders})
          AND plant_name IN ({plant_placeholders})
          AND item_name = %s
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
          AND item_name = %s
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
        "SELECT * FROM production_table WHERE report_month=%s AND plant_name=%s AND item_name=%s",
        (month, plant, item))
    if value is None:
        cursor.execute("""
            DELETE FROM production_table
            WHERE report_month = %s AND plant_name = %s AND item_name = %s
        """, (month, plant, item))
    else:
        cursor.execute("""
            INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE month_actual = new.month_actual
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
        "SELECT * FROM production_plan_table WHERE report_month=%s AND plant_name=%s AND item_name=%s",
        (month, plant, item))
    if value is None:
        cursor.execute("""
            DELETE FROM production_plan_table
            WHERE report_month = %s AND plant_name = %s AND item_name = %s
        """, (month, plant, item))
    else:
        cursor.execute("""
            INSERT INTO production_plan_table (report_month, plant_name, item_name, month_actual)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE month_actual = new.month_actual
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
    cursor.execute("SELECT page_data FROM page_configs WHERE report_month = %s AND page_number = %s", (month, page_number))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

def get_all_page_configs(month: str) -> List[dict]:
    """Retrieves all standard page configurations for a month, ordered by page number."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_configs WHERE report_month = %s ORDER BY page_number ASC", (month,))
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
        VALUES (%s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE page_data = new.page_data
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
        "SELECT production_narrative, highlights FROM page3_narrative WHERE report_month = %s",
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
        VALUES (%s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE production_narrative = new.production_narrative,
                       highlights = new.highlights,
                       updated_at = new.updated_at
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
        "FROM key_highlights_narrative WHERE report_month = %s",
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
        VALUES (%s, %s, %s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE achievements = new.achievements,
                       shortfalls  = new.shortfalls,
                       focus_areas = new.focus_areas,
                       updated_by  = new.updated_by,
                       updated_at  = new.updated_at
    """, (month, json.dumps(achievements or []), json.dumps(shortfalls or []),
          json.dumps(focus_areas or []), updated_by or ""))
    conn.commit()
    conn.close()

def get_steel_sales_highlights(month: str) -> Optional[dict]:
    """Saved Steel Sales Performance bullets (report-month + YTD lists) for
    a month, or None if nothing has ever been saved for it — the report
    page shows empty sections in that case rather than inventing text."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT month_items, ytd_items, updated_by, updated_at "
        "FROM steel_sales_highlights WHERE report_month = %s",
        (month,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    month_items, ytd_items, updated_by, updated_at = row
    return {
        "month_items": json.loads(month_items) if month_items else [],
        "ytd_items":   json.loads(ytd_items) if ytd_items else [],
        "updated_by":  updated_by or "",
        "updated_at":  updated_at or "",
    }

def save_steel_sales_highlights(month: str, month_items: list, ytd_items: list, updated_by: str = ""):
    """Saves/updates the Steel Sales Performance bullets for a month, keyed
    only by report_month — independent of page_configs, same as
    save_key_highlights_narrative above."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO steel_sales_highlights
            (report_month, month_items, ytd_items, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE month_items = new.month_items,
                       ytd_items   = new.ytd_items,
                       updated_by  = new.updated_by,
                       updated_at  = new.updated_at
    """, (month, json.dumps(month_items or []), json.dumps(ytd_items or []), updated_by or ""))
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
        "SELECT param_id FROM techno_param WHERE row_label=%s AND param_name=%s",
        (plant, parameter),
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        return
    conn.execute("""
        INSERT INTO techno_actuals (report_month, param_id, actual, source)
        VALUES (%s, %s, %s, 'manual')
        AS new ON DUPLICATE KEY UPDATE
            actual = new.actual,
            source = new.source
    """, (month, row[0], month_val))
    conn.commit()
    conn.close()


def clear_special_steel_orders(month: str, plant: str) -> int:
    """Delete all special_steel_orders rows for a given month + plant.
    Called once before a batch insert so stale grades/products don't linger."""
    init_db()
    conn = connect()
    conn.row_factory = Row
    old_rows = conn.execute(
        "SELECT * FROM special_steel_orders WHERE report_month=%s AND plant_name=%s",
        (month, plant),
    )
    olds = [dict(r) for r in old_rows.fetchall()]
    conn.row_factory = None
    cur = conn.execute(
        "DELETE FROM special_steel_orders WHERE report_month=%s AND plant_name=%s",
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
        "SELECT * FROM special_steel_orders WHERE report_month=%s AND plant_name=%s AND product=%s AND quality_grade=%s AND section=%s",
        (month, plant, product, quality_grade, section or ""))
    conn.execute("""
        INSERT INTO special_steel_orders
            (report_month, plant_name, product, quality_grade, section,
             sort_order, order_qty, actual_despatch)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            sort_order      = new.sort_order,
            order_qty       = new.order_qty,
            actual_despatch = new.actual_despatch
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
        "SELECT * FROM stock_table WHERE stock_month=%s AND plant_name=%s AND item_type=%s AND stock_type=%s",
        (stock_month, plant, item_type, stock_type))
    conn.execute("""
        INSERT INTO stock_table (stock_month, plant_name, item_type, stock_type, stock)
        VALUES (%s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE stock = new.stock
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
        "SELECT * FROM ipt_table WHERE report_month=%s AND item=%s AND from_plant=%s AND to_plant=%s",
        (month, item, from_plant, to_plant))
    conn.execute("""
        INSERT INTO ipt_table
            (report_month, item, from_plant, to_plant, unit, sort_order,
             plan, actual, plan_tonnage, actual_tonnage)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            unit = new.unit,
            sort_order = new.sort_order,
            plan = new.plan,
            actual = new.actual,
            plan_tonnage = new.plan_tonnage,
            actual_tonnage = new.actual_tonnage
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
        "SELECT * FROM ipt_table WHERE report_month=%s AND item=%s AND from_plant=%s AND to_plant=%s",
        (month, item, from_plant, to_plant))
    cur = conn.execute(
        "DELETE FROM ipt_table WHERE report_month=%s AND item=%s AND from_plant=%s AND to_plant=%s",
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
        sql += " AND plant=%s"; args.append(plant)
    if unit_type:
        sql += " AND unit_type=%s"; args.append(unit_type)
    if unit_name:
        sql += " AND unit_name=%s"; args.append(unit_name)
    sql += " ORDER BY start_ts DESC, id DESC"
    prev_factory = conn.row_factory
    conn.row_factory = Row
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
                          created_by: str, capital_repair_id: Optional[int] = None) -> int:
    """Create one breakdown event. Returns the new row id. capital_repair_id
    links it to the capital repair it really is (see bd_cr_link)."""
    from datetime import datetime
    init_db()
    conn = connect()
    now = datetime.now().isoformat()
    cur = conn.execute("""
        INSERT INTO breakdown_table
            (plant, unit_type, unit_name, sms_subtag, start_ts, end_ts, is_ongoing,
             cause, hours_lost_override, capital_repair_id, created_by, created_at, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (plant, unit_type, unit_name, sms_subtag, start_ts, end_ts, int(is_ongoing),
          cause, hours_lost_override, capital_repair_id, created_by, now, created_by, now))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    activity_context.record(f"breakdown_table/{plant}/{unit_name}/{new_id}", None, {
        "plant": plant, "unit_type": unit_type, "unit_name": unit_name, "sms_subtag": sms_subtag,
        "start_ts": start_ts, "end_ts": end_ts, "is_ongoing": is_ongoing, "cause": cause,
        "hours_lost_override": hours_lost_override, "capital_repair_id": capital_repair_id,
    })
    return new_id


def update_breakdown_entry(breakdown_id: int, updated_by: str, **fields) -> bool:
    """Update the given fields (any subset of plant/unit_type/unit_name/sms_subtag/
    start_ts/end_ts/is_ongoing/cause/hours_lost_override/capital_repair_id) on one breakdown event.
    Returns False if the row doesn't exist."""
    from datetime import datetime
    init_db()
    conn = connect()
    old = _row_dict(conn, "SELECT * FROM breakdown_table WHERE id=%s", (breakdown_id,))
    if old is None:
        conn.close()
        return False
    allowed = {"plant", "unit_type", "unit_name", "sms_subtag", "start_ts", "end_ts",
               "is_ongoing", "cause", "hours_lost_override", "capital_repair_id"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k}=%s")
        args.append(int(v) if k == "is_ongoing" else v)
    if not sets:
        conn.close()
        return True
    sets.append("updated_by=%s"); args.append(updated_by)
    sets.append("updated_at=%s"); args.append(datetime.now().isoformat())
    args.append(breakdown_id)
    conn.execute(f"UPDATE breakdown_table SET {', '.join(sets)} WHERE id=%s", args)
    conn.commit()
    conn.close()
    new = {**old, **{k: v for k, v in fields.items() if k in allowed}}
    activity_context.record(f"breakdown_table/{old['plant']}/{old['unit_name']}/{breakdown_id}", old, new)
    return True


def delete_breakdown_entry(breakdown_id: int) -> bool:
    """Delete one breakdown event, recording its prior state. Returns False if not found."""
    init_db()
    conn = connect()
    old = _row_dict(conn, "SELECT * FROM breakdown_table WHERE id=%s", (breakdown_id,))
    if old is None:
        conn.close()
        return False
    conn.execute("DELETE FROM breakdown_table WHERE id=%s", (breakdown_id,))
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
        sql += " AND plant_name=%s"; args.append(plant)
    if item:
        sql += " AND item_name=%s"; args.append(item)
    sql += " ORDER BY plant_name, item_name, effective_month DESC"
    prev_factory = conn.row_factory
    conn.row_factory = Row
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
            "WHERE plant_name=%s AND item_name=%s AND effective_month<=%s "
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
    IntegrityError if (plant, item, effective_month) already exists —
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
    Raises IntegrityError on a resulting (plant, item, effective_month)
    clash with another row."""
    from datetime import datetime
    init_db()
    conn = connect()
    old = _row_dict(conn, "SELECT * FROM item_capacity_table WHERE id=%s", (entry_id,))
    if old is None:
        conn.close()
        return False
    allowed = {"plant_name", "item_name", "effective_month", "annual_capacity", "reason"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k}=%s")
        args.append(v)
    if not sets:
        conn.close()
        return True
    sets.append("updated_by=%s"); args.append(updated_by)
    sets.append("updated_at=%s"); args.append(datetime.now().isoformat())
    args.append(entry_id)
    try:
        conn.execute(f"UPDATE item_capacity_table SET {', '.join(sets)} WHERE id=%s", args)
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
    old = _row_dict(conn, "SELECT * FROM item_capacity_table WHERE id=%s", (entry_id,))
    if old is None:
        conn.close()
        return False
    conn.execute("DELETE FROM item_capacity_table WHERE id=%s", (entry_id,))
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
        VALUES (%s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            unit       = CASE WHEN new.unit != '' THEN new.unit ELSE unit END,
            sort_order = CASE WHEN new.sort_order > 0 THEN new.sort_order ELSE sort_order END
    """, (param_name, entity_label, unit, sort_order))
    cur.execute(
        "SELECT param_id FROM techno_param WHERE param_name=%s AND row_label=%s",
        (param_name, entity_label),
    )
    pid = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO techno_param_group (param_id, group_code, sort_order)
        VALUES (%s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            sort_order = CASE WHEN new.sort_order > 0 THEN new.sort_order ELSE sort_order END
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
        VALUES (%s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            techno_json = new.techno_json,
            source_file = new.source_file,
            created_at = new.created_at
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
        VALUES (%s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            techno_json = new.techno_json,
            source_file = new.source_file,
            created_at  = new.created_at
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
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                actual            = new.actual,
                till_month_actual = COALESCE(new.till_month_actual, till_month_actual),
                source            = new.source
        """, (month, param_id, actual, till_month_actual, source))
        conn.commit()
        conn.close()
    except OperationalError:
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
        VALUES (%s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE target = new.target
    """, (fy, param_id, target))
    conn.commit()
    conn.close()


def log_page_visit(ip_address: str, user: Optional[dict], path: str) -> None:
    """Appends one row to page_visits — a frontend navigation to `path`,
    from `ip_address`, by `user` (the get_current_user_optional dict) or
    anonymously if `user` is None. See api_visits.py's POST /api/log-visit."""
    init_db()
    conn = connect()
    conn.execute("""
        INSERT INTO page_visits (timestamp, ip_address, user_email, user_name, path)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        datetime.now(timezone.utc).isoformat(),
        ip_address or None,
        user.get("email") if user else None,
        user.get("name") if user else None,
        path,
    ))
    conn.commit()
    conn.close()


ANON_VISIT_NOTIFY_WINDOW_MINUTES = 30


def add_admin_notification(kind: str, ip_address: str = "", user: Optional[dict] = None,
                           path: Optional[str] = None) -> None:
    """Records one event for the admin notification bell. kind is 'sign_in'
    or 'anon_visit'. An 'anon_visit' is skipped when the same IP already
    raised one in the last ANON_VISIT_NOTIFY_WINDOW_MINUTES, so a visitor
    clicking around doesn't produce one alert per page.

    Best-effort: a failure here is logged and swallowed — it must never
    break the sign-in or visit request that triggered it."""
    try:
        _add_admin_notification(kind, ip_address, user, path)
    except Exception as e:
        print(f"[admin_notifications] could not record {kind}: {e}")


def _add_admin_notification(kind, ip_address, user, path) -> None:
    from datetime import timedelta
    init_db()
    now = datetime.now(timezone.utc)
    conn = connect()
    try:
        if kind == "anon_visit":
            since = (now - timedelta(minutes=ANON_VISIT_NOTIFY_WINDOW_MINUTES)).isoformat()
            row = conn.execute(
                "SELECT 1 FROM admin_notifications WHERE kind = 'anon_visit' AND ip_address = %s AND created_at >= %s LIMIT 1",
                (ip_address or None, since),
            ).fetchone()
            if row:
                return
        conn.execute("""
            INSERT INTO admin_notifications (created_at, kind, user_email, user_name, ip_address, path)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            now.isoformat(),
            kind,
            user.get("email") if user else None,
            user.get("name") if user else None,
            ip_address or None,
            path,
        ))
        conn.commit()
    finally:
        conn.close()


def list_admin_notifications(limit: int = 30) -> List[Dict[str, Any]]:
    """Newest-first admin notification events (see add_admin_notification)."""
    init_db()
    conn = connect()
    conn.row_factory = Row
    try:
        rows = conn.execute(
            "SELECT id, created_at, kind, user_email, user_name, ip_address, path "
            "FROM admin_notifications ORDER BY id DESC LIMIT %s",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Is a month's production data final? (page 4's "Tentative" label) ──────
# A month is final once each of these plants has its FINAL monthly report in
# extraction_log for that month; interim uploads (daily/morning reports, DSP's
# pcontrep/mcr1, BSL's DPR mail) don't count. BSP/ASP/SSP/VISL aren't
# checked (per direct instruction, 2026-10-04: BSP re-uploads the same PPC MIS
# workbook through and after the month, so no upload marks it final).
# Months before _FINAL_STATUS_FROM predate the log tracking these uploads
# (their final figures came from backfills), so they always count as final.
_FINAL_STATUS_FROM = "2026-04"
_FINAL_REPORT_RULES = {
    "RSP": lambda src, fname, ym: src.startswith("Final Monthly Report"),
    "ISP": lambda src, fname, ym: src.startswith(("Final Monthly Report", "Summarized Monthly Report")),
    "BSL": lambda src, fname, ym: src.startswith("BSL Production of Main Products (PDF)"),
    # DSP's monthly MIS PDF is named for its month: mis0826.pdf = Aug'26.
    "DSP": lambda src, fname, ym: src == "DSP OMI PDF Report" and re.match(
        rf"(?i)mis{ym[5:7]}{ym[2:4]}\b", fname or "") is not None,
}


def _production_month_status(report_month: str, log_rows) -> dict:
    """Pure rule: log_rows = [(plant_name, source_type, file_name), ...] for
    report_month -> {"tentative": bool, "missing": [plants without a final
    monthly report]}."""
    if report_month < _FINAL_STATUS_FROM:
        return {"tentative": False, "missing": []}
    missing = [plant for plant, rule in _FINAL_REPORT_RULES.items()
               if not any(p == plant and rule(src or "", fname, report_month) for p, src, fname in log_rows)]
    return {"tentative": bool(missing), "missing": missing}


def production_month_status(report_month: str) -> dict:
    """{"tentative", "missing"} for report_month from extraction_log — see
    _production_month_status."""
    init_db()
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT plant_name, source_type, file_name FROM extraction_log WHERE report_month = %s",
                    (report_month,))
        return _production_month_status(report_month, cur.fetchall())
    finally:
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
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), plant, report_month, file_name, sheet_name, source_type, items_extracted))
    if owns_conn:
        conn.commit()
        conn.close()


def get_pdf_item_aliases(plant: str) -> Dict[str, Any]:
    """User-saved PDF label corrections for a plant: {pdf_label: (item_name, convert_t)}."""
    init_db()
    conn = connect()
    rows = conn.execute("""
        SELECT pdf_label, item_name, convert_t FROM pdf_item_alias WHERE plant_name = %s
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
        "SELECT * FROM pdf_item_alias WHERE plant_name=%s AND pdf_label=%s",
        (plant, pdf_label))
    conn.execute("""
        INSERT INTO pdf_item_alias (plant_name, pdf_label, item_name, convert_t)
        VALUES (%s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE item_name = new.item_name, convert_t = new.convert_t
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
    conn.row_factory = Row
    clauses, params = [], []
    if plant:
        clauses.append("plant_name = %s")
        params.append(plant)
    if source_type:
        clauses.append("source_type = %s")
        params.append(source_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = conn.execute(f"""
        SELECT id, logged_at, plant_name, report_month, file_name, sheet_name, source_type, items_extracted
        FROM extraction_log
        {where}
        ORDER BY id DESC
        LIMIT %s
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
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        AS new ON DUPLICATE KEY UPDATE
            data = new.data,
            updated_at = NOW()
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
    conn.row_factory = Row
    cursor = conn.cursor()

    if furnace:
        cursor.execute("""
            SELECT furnace, data
            FROM techno_furnace_data
            WHERE plant = %s AND report_month = %s AND furnace = %s
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
            WHERE plant = %s AND report_month = %s
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
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        AS new ON DUPLICATE KEY UPDATE
            data = new.data,
            calculation_details = new.calculation_details,
            updated_at = NOW()
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
    conn.row_factory = Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT data, calculation_details
        FROM techno_plant_data
        WHERE plant = %s AND report_month = %s
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
        VALUES (%s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE
            data = new.data,
            calculation_method = new.calculation_method,
            last_updated = NOW()
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
    conn.row_factory = Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT data, calculation_method
        FROM techno_sail_consolidated
        WHERE report_month = %s
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
        "SELECT techno_json, source_file FROM techno_data WHERE plant=%s AND report_month=%s AND unit=%s",
        (plant, report_month, unit))
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE
            techno_json = new.techno_json,
            source_file = new.source_file,
            created_at  = NOW()
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
                "SELECT source_file FROM techno_data WHERE plant=%s AND report_month=%s AND unit=%s",
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


def merge_upsert_techno_data(plant: str, report_month: str, unit: str, new_techno_json: Dict, source_file: str = '', conn=None, clear_keys: Optional[Dict[str, list]] = None):
    """Merge new_techno_json into any existing row (non-null values win; existing non-null kept if new value is null).
    Use this when multiple source files contribute different parameters to the same plant/unit/month.

    clear_keys: optional {"month": [key, ...], "till_month": [key, ...]} —
    keys to actually DELETE from the existing stored row before applying
    new_techno_json, for a caller that needs to distinguish "this key
    wasn't part of the request" (leave alone, the normal null-keeps-
    existing rule below) from "this key was explicitly cleared" (remove
    it). Without this, a manual-entry form clearing a field to blank had
    no way to ever delete a previously-saved value — the null-keeps-
    existing rule made the old value silently reappear on next load (see
    api_techno_manual.py's SaveRequest.clear_month_keys/clear_till_keys,
    the only caller that passes this today).

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
        "SELECT techno_json FROM techno_data WHERE plant=%s AND report_month=%s AND unit=%s",
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
            for k in (clear_keys or {}).get(period, []):
                base.pop(k, None)
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
        "SELECT month_actual FROM production_table WHERE plant_name=%s AND item_name=%s AND report_month=%s",
        (plant, item_name, report_month),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else None


def get_production_actual_for_months(plant: str, item_name: str, months: List[str]) -> Dict[str, float]:
    """-> {report_month: month_actual} for one plant/item across an explicit
    list of report_months (only months with a saved row come back) — used
    by the /data-entry/production-range bulk editor (see main.py's
    /api/production-item-range) to pre-fill a whole month range in one
    query rather than one lookup per month."""
    if not months:
        return {}
    init_db()
    conn = connect()
    cursor = conn.cursor()
    placeholders = ",".join(["%s"] * len(months))
    cursor.execute(
        f"SELECT report_month, month_actual FROM production_table "
        f"WHERE plant_name = %s AND item_name = %s AND report_month IN ({placeholders})",
        [plant, item_name] + months,
    )
    out = {rm: v for rm, v in cursor.fetchall() if v is not None}
    conn.close()
    return out


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
    placeholders = ",".join(["%s"] * len(months))
    cursor.execute(
        f"SELECT report_month, item_name, month_actual FROM production_table "
        f"WHERE plant_name=%s AND report_month IN ({placeholders})",
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
    being permanently switched to Row, since a shared connection may
    be reused by other callers (plain tuple rows) later in the same batch."""
    init_db()
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    prev_factory = conn.row_factory
    conn.row_factory = Row
    cursor = conn.cursor()

    if unit:
        cursor.execute(
            "SELECT unit, techno_json FROM techno_data WHERE plant = %s AND report_month = %s AND unit = %s",
            [plant, report_month, unit]
        )
    else:
        cursor.execute(
            "SELECT unit, techno_json FROM techno_data WHERE plant = %s AND report_month = %s ORDER BY unit",
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
    conn.row_factory = Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT unit, techno_json FROM techno_data WHERE plant = 'SAIL' AND report_month = %s ORDER BY unit",
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
        VALUES (%s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            techno_json = new.techno_json,
            source_file = new.source_file,
            created_at = new.created_at
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
            "SELECT DISTINCT report_month FROM techno_data WHERE plant = %s ORDER BY report_month DESC",
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
    conn.row_factory = Row
    cur = conn.cursor()

    if unit:
        cur.execute(
            "SELECT techno_json, is_user_supplied, calculated_json FROM techno_plan_fy WHERE plant_name = %s AND fy = %s AND unit = %s",
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
            "SELECT unit, techno_json, is_user_supplied, calculated_json FROM techno_plan_fy WHERE plant_name = %s AND fy = %s ORDER BY unit",
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
        "SELECT techno_json, is_user_supplied, calculated_json, calculation_method FROM techno_plan_fy WHERE plant_name=%s AND unit=%s AND fy=%s",
        (plant, unit, fy))
    cur = conn.cursor()
    from datetime import datetime
    now = datetime.now().isoformat()

    cur.execute("""
        INSERT INTO techno_plan_fy
            (plant_name, unit, fy, techno_json, is_user_supplied, calculated_json, calculation_method, created_by, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            techno_json = new.techno_json,
            is_user_supplied = new.is_user_supplied,
            calculated_json = new.calculated_json,
            calculation_method = new.calculation_method,
            updated_at = new.updated_at
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
    conn.row_factory = Row
    cur = conn.cursor()
    cur.execute(
        "SELECT techno_json, is_user_supplied, calculated_json, calculation_method FROM techno_plan_fy WHERE plant_name = %s AND fy = %s AND unit = 'Shop'",
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
    conn.row_factory = Row
    cur = conn.cursor()
    cur.execute(
        "SELECT techno_json, is_user_supplied, calculated_json, calculation_method FROM techno_plan_fy WHERE plant_name = 'SAIL' AND fy = %s AND unit = 'Shop'",
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
            "SELECT DISTINCT fy FROM techno_plan_fy WHERE plant_name = %s ORDER BY fy DESC",
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
        ph = ",".join(["%s"] * len(fys))
        cur.execute(
            f"SELECT fy, cost_type, plant, value FROM cost_trend_annual "
            f"WHERE product=%s AND fy IN ({ph})",
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
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value = new.value
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
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(
            f"SELECT report_month, cost_type, plant, month_value, till_month_value "
            f"FROM cost_trend_monthly WHERE product=%s AND report_month IN ({ph})",
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
            VALUES (%s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE month_value = new.month_value, till_month_value = new.till_month_value
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
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE {field} = new.{field}
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
        ph = ",".join(["%s"] * len(report_months))
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
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE month_actual = new.month_actual, month_plan = new.month_plan
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
    cur.execute("SELECT end_use_code, end_use_name, tracks_actual FROM mine_end_uses_master ORDER BY sort_order")
    end_uses = [{"end_use_code": r[0], "end_use_name": r[1], "tracks_actual": bool(r[2])} for r in cur.fetchall()]
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
        "SELECT material_code, qty_actual, qty_plan FROM mines_production_monthly WHERE report_month=%s AND mine_code=%s",
        (report_month, mine_code),
    )
    for material_code, actual, plan in cur.fetchall():
        production[material_code] = {"actual": actual, "plan": plan}

    despatch = {}
    cur.execute(
        "SELECT material_code, transport_mode, end_use_code, qty_actual "
        "FROM mines_despatch_actual_monthly WHERE report_month=%s AND mine_code=%s",
        (report_month, mine_code),
    )
    for material_code, mode, end_use, actual in cur.fetchall():
        despatch.setdefault(material_code, {}).setdefault(mode, {})[end_use] = {"actual": actual}

    despatch_plan = {}
    cur.execute(
        "SELECT material_code, end_use_code, qty_plan "
        "FROM mines_despatch_plan_monthly WHERE report_month=%s AND mine_code=%s",
        (report_month, mine_code),
    )
    for material_code, end_use, plan in cur.fetchall():
        despatch_plan.setdefault(material_code, {})[end_use] = plan

    booked_qty = {}
    cur.execute(
        "SELECT material_code, transport_mode, qty_actual "
        "FROM mines_booked_qty_actual_monthly WHERE report_month=%s AND mine_code=%s",
        (report_month, mine_code),
    )
    for material_code, mode, actual in cur.fetchall():
        booked_qty.setdefault(material_code, {})[mode] = {"actual": actual}

    booked_qty_plan = {}
    cur.execute(
        "SELECT material_code, qty_plan FROM mines_booked_qty_plan_monthly WHERE report_month=%s AND mine_code=%s",
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
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE qty_actual = new.qty_actual, qty_plan = new.qty_plan
        """, (report_month, mine_code, e["material_code"], e.get("actual"), e.get("plan")))
        saved += 1
    for e in despatch_entries:
        cur.execute("""
            INSERT INTO mines_despatch_actual_monthly
                (report_month, mine_code, material_code, transport_mode, end_use_code, qty_actual)
            VALUES (%s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE qty_actual = new.qty_actual
        """, (
            report_month, mine_code, e["material_code"], e["transport_mode"], e["end_use_code"], e.get("actual"),
        ))
        saved += 1
    for e in despatch_plan_entries:
        cur.execute("""
            INSERT INTO mines_despatch_plan_monthly
                (report_month, mine_code, material_code, end_use_code, qty_plan)
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE qty_plan = new.qty_plan
        """, (report_month, mine_code, e["material_code"], e["end_use_code"], e.get("plan")))
        saved += 1
    for e in booked_qty_entries:
        cur.execute("""
            INSERT INTO mines_booked_qty_actual_monthly
                (report_month, mine_code, material_code, transport_mode, qty_actual)
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE qty_actual = new.qty_actual
        """, (report_month, mine_code, e["material_code"], e["transport_mode"], e.get("actual")))
        saved += 1
    for e in booked_qty_plan_entries:
        cur.execute("""
            INSERT INTO mines_booked_qty_plan_monthly (report_month, mine_code, material_code, qty_plan)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE qty_plan = new.qty_plan
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
    from sail_mines_monthly as before). Despatch = ALL materials' (fresh +
    legacy) despatch Actual summed per group (Rail+Road combined) and Plan
    summed per group (Plan has no Rail/Road split — see
    mines_despatch_plan_monthly).

    Production = fresh Lump+Fines actual/plan (the only materials
    mine_materials_master flags has_production=1 for) PLUS despatch-only
    components that have no production entry of their own, so they're
    counted at the point they leave the mine instead: Dump Fines despatched
    to SALES, CAPTIVE or UNALLOCATED end_use (currently only GUA sends Dump
    Fines CAPTIVE — per direct instruction, 2026-09-17, that tonnage is now
    counted as production too, reversing the 2026-09-12 exclusion), Tailings
    despatched to end_use SALES or UNALLOCATED (legacy recovered material
    sold off, not part of planned Lump/Fines output — no CAPTIVE flow
    exists for Tailings), and Pellets despatch of any end_use (SAIL's
    pellet plants, currently only DALLI, have no separate "production"
    entry at all — their despatch figure, to SALES or CAPTIVE alike, IS
    their production). UNALLOCATED (a despatch-PLAN quantity with no
    destination yet, per direct instruction 2026-10-17) counts toward Dump
    Fines/Tailings here the same as a real destination would — it's
    despatch that hasn't been attributed to Captive/Sales yet, not
    despatch that didn't happen."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {m: {"iron_ore_prod": {}, "iron_ore_despatch": {}} for m in report_months}
    if not report_months:
        conn.close()
        return out
    ph = ",".join(["%s"] * len(report_months))

    prod_actual, prod_plan = {}, {}
    cur.execute(f"""
        SELECT p.report_month, mm.group_code, SUM(p.qty_actual), SUM(p.qty_plan)
        FROM mines_production_monthly p
        JOIN mines_master mm ON mm.mine_code = p.mine_code
        WHERE p.report_month IN ({ph})
        GROUP BY p.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual, plan in cur.fetchall():
        prod_actual.setdefault(rm, {})[group_code] = actual
        prod_plan.setdefault(rm, {})[group_code] = plan

    cur.execute(f"""
        SELECT d.report_month, mm.group_code, SUM(d.qty_actual)
        FROM mines_despatch_actual_monthly d
        JOIN mines_master mm ON mm.mine_code = d.mine_code
        WHERE d.report_month IN ({ph})
          AND (d.material_code = 'PELLETS'
               OR (d.material_code = 'DUMP_FINES' AND d.end_use_code IN ('SALES', 'CAPTIVE', 'UNALLOCATED'))
               OR (d.material_code = 'TAILINGS' AND d.end_use_code IN ('SALES', 'UNALLOCATED')))
        GROUP BY d.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual in cur.fetchall():
        prod_actual.setdefault(rm, {})[group_code] = (prod_actual.get(rm, {}).get(group_code) or 0) + (actual or 0)

    cur.execute(f"""
        SELECT pl.report_month, mm.group_code, SUM(pl.qty_plan)
        FROM mines_despatch_plan_monthly pl
        JOIN mines_master mm ON mm.mine_code = pl.mine_code
        WHERE pl.report_month IN ({ph})
          AND (pl.material_code = 'PELLETS'
               OR (pl.material_code = 'DUMP_FINES' AND pl.end_use_code IN ('SALES', 'CAPTIVE', 'UNALLOCATED'))
               OR (pl.material_code = 'TAILINGS' AND pl.end_use_code IN ('SALES', 'UNALLOCATED')))
        GROUP BY pl.report_month, mm.group_code
    """, report_months)
    for rm, group_code, plan in cur.fetchall():
        prod_plan.setdefault(rm, {})[group_code] = (prod_plan.get(rm, {}).get(group_code) or 0) + (plan or 0)

    for rm in report_months:
        groups = set(prod_actual.get(rm, {})) | set(prod_plan.get(rm, {}))
        for group_code in groups:
            out[rm]["iron_ore_prod"][group_code] = {
                "actual": prod_actual.get(rm, {}).get(group_code),
                "plan": prod_plan.get(rm, {}).get(group_code),
            }

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


def get_iron_ore_despatch_mix(report_months: List[str]) -> Dict[str, float]:
    """SAIL-wide Iron Ore despatch actual summed across every mine, material
    and transport mode, grouped by end_use_code (CAPTIVE / SALES /
    PELLET_CONV) — the source for page_sail_mines.py's despatch-mix donuts
    (per direct instruction, 2026-09-17, replacing the earlier hand-
    maintained hardcoded_config.json snapshot). Returns {end_use_code:
    total_qty_actual} in '000 T; an end_use_code with no despatch at all
    across these months is simply omitted rather than returned as 0."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out: Dict[str, float] = {}
    if not report_months:
        conn.close()
        return out
    ph = ",".join(["%s"] * len(report_months))
    cur.execute(f"""
        SELECT end_use_code, SUM(qty_actual)
        FROM mines_despatch_actual_monthly
        WHERE report_month IN ({ph})
        GROUP BY end_use_code
    """, report_months)
    for end_use, total in cur.fetchall():
        if total is not None:
            out[end_use] = total
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
    ph = ",".join(["%s"] * len(report_months))

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
    ph = ",".join(["%s"] * len(report_months))

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
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                capacity_kt = new.capacity_kt, best_actual_kt = new.best_actual_kt,
                best_year = new.best_year, remark = new.remark,
                sort_order = new.sort_order
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
            cur.execute("DELETE FROM special_steel_phys_perf WHERE financial_year=%s AND plant=%s "
                        "AND series=%s AND metric=%s", key)
        else:
            cur.execute("""
                INSERT INTO special_steel_phys_perf
                    (financial_year, plant, series, metric, value_kt)
                VALUES (%s, %s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE value_kt = new.value_kt
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
                "WHERE financial_year=%s ORDER BY sort_order", (financial_year,))
    rows = cur.fetchall()
    conn.close()
    return [(so, t) for so, t in rows]


def save_ss_phys_notes(financial_year, rows):
    """Replace every note for a FY with `rows`: {sort_order, note_text}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM special_steel_phys_note WHERE financial_year=%s", (financial_year,))
    for r in rows:
        text = (r.get("note_text") or "").strip()
        if not text:
            continue
        cur.execute("INSERT INTO special_steel_phys_note (financial_year, sort_order, note_text) "
                    "VALUES (%s, %s, %s)", (financial_year, int(r.get("sort_order") or 0), text))
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
        FROM special_steel_ipt_requirement WHERE financial_year=%s
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
            cur.execute("DELETE FROM special_steel_ipt_requirement WHERE financial_year=%s "
                        "AND item=%s AND from_plant=%s AND to_plant=%s", (financial_year, oi, of, ot))
        cur.execute("""
            INSERT INTO special_steel_ipt_requirement
                (financial_year, item, from_plant, to_plant, plan_kt, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE plan_kt = new.plan_kt, sort_order = new.sort_order
        """, (financial_year, item, frm, to, r.get("plan_kt"), int(r.get("sort_order") or 0)))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def delete_ss_ipt_requirement(financial_year, item, from_plant, to_plant):
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM special_steel_ipt_requirement WHERE financial_year=%s AND item=%s "
                "AND from_plant=%s AND to_plant=%s", (financial_year, item, from_plant, to_plant))
    conn.commit()
    conn.close()


# ── "Rail Production & Dispatch from BSP" (page 18.5) ──────────────────────
# Backing store for page_rail_report.py + /data-entry/rail-report. See
# scripts/migrate_add_rail_report.sql.

def get_rail_report_data(fys: List[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """-> {financial_year: {metric: {"value": v, "note": n}}}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {fy: {} for fy in fys}
    if fys:
        ph = ",".join(["%s"] * len(fys))
        cur.execute(f"SELECT financial_year, metric, value, note FROM rail_prod_despatch "
                    f"WHERE financial_year IN ({ph})", fys)
        for fy, metric, value, note in cur.fetchall():
            out.setdefault(fy, {})[metric] = {"value": value, "note": note}
    conn.close()
    return out


def save_rail_report_data(rows: List[Dict[str, Any]]) -> int:
    """Upsert rail_prod_despatch rows: {financial_year, metric, value, note}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO rail_prod_despatch (financial_year, metric, value, note)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                value = new.value, note = new.note
        """, (r["financial_year"], r["metric"], r.get("value"), r.get("note")))
    conn.commit()
    conn.close()
    return len(rows)


def get_rail_report_notes() -> List[tuple]:
    """-> [(sort_order, note_text), ...] ordered."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT sort_order, note_text FROM rail_prod_despatch_note ORDER BY sort_order")
    rows = cur.fetchall()
    conn.close()
    return [(so, t) for so, t in rows]


def save_rail_report_notes(rows: List[Dict[str, Any]]) -> int:
    """Replace every footer remark with `rows`: {sort_order, note_text}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM rail_prod_despatch_note")
    for r in rows:
        text = (r.get("note_text") or "").strip()
        if not text:
            continue
        cur.execute("INSERT INTO rail_prod_despatch_note (sort_order, note_text) VALUES (%s, %s)",
                    (int(r.get("sort_order") or 0), text))
    conn.commit()
    conn.close()
    return len(rows)


# ── "Movement of Key Prices - International" (page 2.41) ───────────────────
# Backing store for page_market_prices.py + /data-entry/market-intel. See
# scripts/migrate_add_market_intel.sql.

def get_market_price_trend(report_months: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {report_month: {series_code: value}}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {m: {} for m in report_months}
    if report_months:
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(f"SELECT report_month, series_code, value FROM market_price_trend_monthly "
                    f"WHERE report_month IN ({ph})", report_months)
        for rm, series, value in cur.fetchall():
            out.setdefault(rm, {})[series] = value
    conn.close()
    return out


def save_market_price_trend(rows: List[Dict[str, Any]]) -> int:
    """Upsert market_price_trend_monthly rows: {report_month, series_code, value}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO market_price_trend_monthly (report_month, series_code, value)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value = new.value
        """, (r["report_month"], r["series_code"], r.get("value")))
    conn.commit()
    conn.close()
    return len(rows)


# ── "India Macro Economic Indicators" (page 2.42) ───────────────────────────
# Backing store for page_macro_indicators.py + /data-entry/market-intel. See
# scripts/migrate_add_market_intel.sql.

def get_macro_indicators(report_months: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {report_month: {metric_code: value}}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {m: {} for m in report_months}
    if report_months:
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(f"SELECT report_month, metric_code, value FROM macro_indicators_monthly "
                    f"WHERE report_month IN ({ph})", report_months)
        for rm, metric, value in cur.fetchall():
            out.setdefault(rm, {})[metric] = value
    conn.close()
    return out


def save_macro_indicators(rows: List[Dict[str, Any]]) -> int:
    """Upsert macro_indicators_monthly rows: {report_month, metric_code, value}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO macro_indicators_monthly (report_month, metric_code, value)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value = new.value
        """, (r["report_month"], r["metric_code"], r.get("value")))
    conn.commit()
    conn.close()
    return len(rows)


# ── "Details of Rakes Detention Plant Wise" (RAKE_DETENTION_* pages) ───────
# Backing store for page_rake_detention.py + /data-entry/rake-detention. See
# scripts/migrate_add_rake_detention.sql / scripts/backfill_rake_detention.py.

_RAKE_MASTER_COLS = (
    "id", "plant", "section", "commodity", "wagon_type", "row_label",
    "is_total", "direction", "freetime_hours", "freetime_effective_from",
    "sort_order", "is_active",
)


def get_rake_detention_master(plants: Optional[List[str]] = None, active_only: bool = True) -> List[dict]:
    """-> list of master rows (dicts, _RAKE_MASTER_COLS keys), ordered for
    display. active_only=False is for the data-entry UI, which also needs
    to show/reactivate a retired wagon type."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    where, args = [], []
    if plants:
        where.append(f"plant IN ({','.join(['%s'] * len(plants))})")
        args.extend(plants)
    if active_only:
        where.append("is_active = 1")
    sql = f"SELECT {','.join(_RAKE_MASTER_COLS)} FROM rake_detention_master"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY plant, section, sort_order, id"
    cur.execute(sql, args)
    rows = [dict(zip(_RAKE_MASTER_COLS, r)) for r in cur.fetchall()]
    conn.close()
    return _group_rake_master_rows(rows)


def _group_rake_master_rows(rows: List[dict]) -> List[dict]:
    """Regroups rows so every row sharing the same (plant, section,
    commodity) is always contiguous, at that commodity's first-seen slot
    within its section — commodity grouping, not sort_order alone, is
    what the printed report's rowspan-merged Commodity column (see
    rake_detention_detail.html) actually depends on, and a bare
    "ORDER BY sort_order" can't guarantee that on its own: a newly added
    row can only be given a sort_order that's safely between its OWN
    commodity's neighbours, never one that's also guaranteed to fall
    outside every OTHER commodity's own range in the same section —
    collide with the very next commodity's own starting value (confirmed
    by a real add: e.g. Ind.Coking Coal's rows 1-3, Imp.Coking Coal's rows
    4-6 — a new Ind.Coking Coal row given sort_order 4 lands ON Imp.Coking
    Coal's own first row, splitting Imp.Coking Coal's group in two on the
    printed page) and there's no sort_order value that avoids every
    possible future collision like that. Grouping by the commodity value
    itself has no such blind spot, and self-heals any row that already
    landed in the wrong spot for this same reason (its commodity string
    still matches, so it rejoins that group here regardless of its own
    sort_order). Sort_order still decides ordering WITHIN one commodity's
    own rows (e.g. BSP Inward's Ind.Coking Coal group still prints
    BOXN/BOST/BOSM, its own original order, not alphabetical); is_total
    rows always sort last within their section, same as before."""
    section_buckets = {}  # (plant, section) -> {"totals": [...], "by_commodity": {commodity: [rows]}}
    for r in rows:
        bucket = section_buckets.setdefault((r["plant"], r["section"]), {"totals": [], "by_commodity": {}})
        if r["is_total"]:
            bucket["totals"].append(r)
        else:
            bucket["by_commodity"].setdefault(r["commodity"], []).append(r)

    out = []
    for bucket in section_buckets.values():
        for commodity_rows in bucket["by_commodity"].values():
            out.extend(commodity_rows)
        out.extend(bucket["totals"])
    return out


def save_rake_detention_master_row(row: Dict[str, Any]) -> int:
    """Insert (row.get('id') falsy) or update (id given) one master row.
    Returns the row's id. This is the "add a wagon type later" provision —
    called from /data-entry/rake-detention, never needs a code change."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    if row.get("id"):
        cur.execute("""
            UPDATE rake_detention_master SET
                plant = %s, section = %s, commodity = %s, wagon_type = %s, row_label = %s,
                is_total = %s, direction = %s, freetime_hours = %s, freetime_effective_from = %s,
                sort_order = %s, is_active = %s
            WHERE id = %s
        """, (
            row["plant"], row["section"], row.get("commodity"), row.get("wagon_type"), row["row_label"],
            int(bool(row.get("is_total"))), row.get("direction"), row.get("freetime_hours"),
            row.get("freetime_effective_from"), int(row.get("sort_order") or 0),
            int(bool(row.get("is_active", True))), row["id"],
        ))
        row_id = row["id"]
    else:
        cur.execute("""
            INSERT INTO rake_detention_master
                (plant, section, commodity, wagon_type, row_label, is_total, direction,
                 freetime_hours, freetime_effective_from, sort_order, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row["plant"], row["section"], row.get("commodity"), row.get("wagon_type"), row["row_label"],
            int(bool(row.get("is_total"))), row.get("direction"), row.get("freetime_hours"),
            row.get("freetime_effective_from"), int(row.get("sort_order") or 0),
            int(bool(row.get("is_active", True))),
        ))
        row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def deactivate_rake_detention_master_row(master_id: int) -> None:
    """Retires a wagon type without deleting its history (is_active=0 —
    get_rake_detention_master's default active_only=True then skips it on
    future months, but every already-saved rake_detention_monthly value
    stays intact)."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("UPDATE rake_detention_master SET is_active = 0 WHERE id = %s", (master_id,))
    conn.commit()
    conn.close()


def get_rake_detention_monthly(report_month: str, master_ids: Optional[List[int]] = None) -> Dict[int, float]:
    """-> {master_id: value_hours} for one report_month."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    sql = "SELECT master_id, value_hours FROM rake_detention_monthly WHERE report_month = %s"
    args = [report_month]
    if master_ids:
        sql += f" AND master_id IN ({','.join(['%s'] * len(master_ids))})"
        args.extend(master_ids)
    cur.execute(sql, args)
    out = {mid: val for mid, val in cur.fetchall()}
    conn.close()
    return out


def save_rake_detention_monthly(report_month: str, rows: List[Dict[str, Any]]) -> int:
    """Upsert rake_detention_monthly rows: {master_id, value_hours} for report_month."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO rake_detention_monthly (report_month, master_id, value_hours)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value_hours = new.value_hours
        """, (report_month, r["master_id"], r.get("value_hours")))
    conn.commit()
    conn.close()
    return len(rows)


def get_rake_detention_trend(master_ids: List[int]) -> Dict[int, Dict[str, float]]:
    """-> {master_id: {report_month: value_hours}} across every month on
    record — used for page 4's multi-year "Overall Wagon" trend, where the
    granular per-plant "Overall Wagon" master row is the only one that
    realistically has years of history behind it."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out: Dict[int, Dict[str, float]] = {mid: {} for mid in master_ids}
    if master_ids:
        ph = ",".join(["%s"] * len(master_ids))
        cur.execute(
            f"SELECT master_id, report_month, value_hours FROM rake_detention_monthly "
            f"WHERE master_id IN ({ph})", master_ids,
        )
        for mid, rm, val in cur.fetchall():
            out.setdefault(mid, {})[rm] = val
    conn.close()
    return out


def get_rake_detention_summary(report_month: str) -> Dict[str, Dict[str, float]]:
    """-> {period_row: {plant: value}} for one 'UPTO <report_month>' snapshot."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT period_row, plant, value FROM rake_detention_summary WHERE report_month = %s",
        (report_month,),
    )
    out: Dict[str, Dict[str, float]] = {}
    for period_row, plant, value in cur.fetchall():
        out.setdefault(period_row, {})[plant] = value
    conn.close()
    return out


def save_rake_detention_summary(report_month: str, rows: List[Dict[str, Any]]) -> int:
    """Upsert rake_detention_summary rows: {period_row, plant, value} for report_month."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO rake_detention_summary (report_month, period_row, plant, value)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value = new.value
        """, (report_month, r["period_row"], r["plant"], r.get("value")))
    conn.commit()
    conn.close()
    return len(rows)


def get_rake_detention_annual(plants: List[str], fys: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {plant: {financial_year: avg_hours}} — page 4's per-FY "APR-MAR" column."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {p: {} for p in plants}
    if plants and fys:
        ph_p, ph_f = ",".join(["%s"] * len(plants)), ",".join(["%s"] * len(fys))
        cur.execute(
            f"SELECT plant, financial_year, avg_hours FROM rake_detention_annual "
            f"WHERE plant IN ({ph_p}) AND financial_year IN ({ph_f})", plants + fys,
        )
        for plant, fy, val in cur.fetchall():
            out.setdefault(plant, {})[fy] = val
    conn.close()
    return out


def save_rake_detention_annual(rows: List[Dict[str, Any]]) -> int:
    """Upsert rake_detention_annual rows: {plant, financial_year, avg_hours}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO rake_detention_annual (plant, financial_year, avg_hours)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE avg_hours = new.avg_hours
        """, (r["plant"], r["financial_year"], r.get("avg_hours")))
    conn.commit()
    conn.close()
    return len(rows)


# ── "Ready Reckoner" (Annexure-1: 5 ISPs / Annexure-2: 3 SSPs) ─────────────
# Backing store for page_ready_reckoner.py + its editor (/data-entry/ready-
# reckoner). See scripts/migrate_ready_reckoner_structured.sql. Not month-
# scoped — see this table's own comment in init_db().
#
# capacity_rows/product_mix_headers/product_mix_rows store PLAIN DATA only
# (JSON, no HTML/markup/style of any kind) — per direct instruction,
# 2026-09-21: the previous design (capacity_html/product_mix_html, raw
# editor-authored HTML strings rendered with Jinja's |safe) let formatting
# leak into the stored content itself. All presentation (colors, bold
# totals, line breaks) is now applied at render time instead — React in the
# live preview/editor, Jinja+CSS in the PDF template (ready_reckoner_
# plant.html) — never stored. See scripts/migrate_ready_reckoner_
# structured.py for the one-time migration that parsed the old HTML into
# this shape.
#
# Shapes (all json.dumps'd into TEXT columns, json.loads'd back out below):
#   capacity_rows:       [{"item": str, "details": str, "capacity": str, "is_total": bool}, ...]
#   product_mix_headers: [str, ...]                 -- this plant's own column titles
#   product_mix_rows:    [{"cells": [str, ...], "is_total": bool}, ...]  -- len(cells) == len(headers)
# product_mix_caption is plain TEXT (not JSON) — a one-line note some plants
# carry above their Product Mix table (e.g. BSL's "representative grade
# families per product — see full spec sheet for exhaustive list"); most
# plants leave it blank.
# A cell's "\n" means a line break (rendered as <br> at display time), never
# literal HTML.

_READY_RECKONER_COLS = (
    "plant_code", "plant_name", "plant_group", "process_flow_image_path",
    "capacity_rows", "product_mix_headers", "product_mix_rows", "product_mix_caption",
    "sort_order", "updated_by", "updated_at",
)

_READY_RECKONER_JSON_COLS = ("capacity_rows", "product_mix_headers", "product_mix_rows")


def _decode_ready_reckoner_row(row: tuple) -> dict:
    d = dict(zip(_READY_RECKONER_COLS, row))
    for col in _READY_RECKONER_JSON_COLS:
        d[col] = json.loads(d[col]) if d.get(col) else []
    d["product_mix_caption"] = d.get("product_mix_caption") or ""
    return d


def get_ready_reckoner_pages() -> List[dict]:
    """-> every plant's row (dict, _READY_RECKONER_COLS keys, JSON columns
    already decoded to lists), ordered for display (ISPs then SSPs, each
    group in its own sort_order)."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {','.join(_READY_RECKONER_COLS)} FROM ready_reckoner_pages "
        f"ORDER BY plant_group, sort_order, plant_code"
    )
    rows = [_decode_ready_reckoner_row(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_ready_reckoner_page(plant_code: str) -> Optional[dict]:
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {','.join(_READY_RECKONER_COLS)} FROM ready_reckoner_pages WHERE plant_code = %s",
        (plant_code,),
    )
    row = cur.fetchone()
    conn.close()
    return _decode_ready_reckoner_row(row) if row else None


def upsert_ready_reckoner_master(row: Dict[str, Any]) -> None:
    """Insert or update the non-editable identity fields of one plant's row
    (plant_name/plant_group/sort_order) — used by the one-time backfill, not
    the inline editor (which only ever touches content via the functions
    below)."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ready_reckoner_pages (plant_code, plant_name, plant_group, sort_order)
        VALUES (%s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            plant_name = new.plant_name, plant_group = new.plant_group,
            sort_order = new.sort_order
    """, (row["plant_code"], row.get("plant_name"), row["plant_group"], int(row.get("sort_order") or 0)))
    conn.commit()
    conn.close()


def save_ready_reckoner_content(
    plant_code: str, capacity_rows: Optional[list] = None,
    product_mix_headers: Optional[list] = None, product_mix_rows: Optional[list] = None,
    product_mix_caption: Optional[str] = None, updated_by: str = "",
) -> None:
    """Updates one or more of the plain-data fields for one plant, from the
    /data-entry/ready-reckoner form's Save action. None (not just an empty
    list) means "leave this field alone" — the capacity editor's Save action
    only ever sends capacity_rows, and must NOT blank out product_mix_*
    just because those fields weren't part of this particular payload.
    product_mix_headers and product_mix_rows are always sent together by
    the editor (changing column count means both change), but are still
    independently optional here for the same reason. A plain UPDATE, not an
    upsert: the row always already exists by this point (created by the
    one-time backfill via upsert_ready_reckoner_master, which owns
    plant_name/plant_group/sort_order) — MySQL's ON DUPLICATE KEY UPDATE
    still validates every column in the INSERT list against NOT NULL
    constraints even when it ends up taking the UPDATE branch, so a
    partial insert (omitting plant_group here) fails outright rather than
    falling through."""
    import datetime as _dt
    sets, args = [], []
    if capacity_rows is not None:
        sets.append("capacity_rows = %s")
        args.append(json.dumps(capacity_rows))
    if product_mix_headers is not None:
        sets.append("product_mix_headers = %s")
        args.append(json.dumps(product_mix_headers))
    if product_mix_rows is not None:
        sets.append("product_mix_rows = %s")
        args.append(json.dumps(product_mix_rows))
    if product_mix_caption is not None:
        sets.append("product_mix_caption = %s")
        args.append(product_mix_caption)
    if not sets:
        return
    sets += ["updated_by = %s", "updated_at = %s"]
    args += [updated_by, _dt.datetime.now().isoformat(timespec="seconds"), plant_code]
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(f"UPDATE ready_reckoner_pages SET {', '.join(sets)} WHERE plant_code = %s", args)
    conn.commit()
    conn.close()


def save_ready_reckoner_image(plant_code: str, image_path: str, updated_by: str) -> None:
    """Updates just the process-flow diagram's file path for one plant, from
    the inline editor's image-upload control. Same plain-UPDATE reasoning
    as save_ready_reckoner_content."""
    import datetime as _dt
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        UPDATE ready_reckoner_pages
        SET process_flow_image_path = %s, updated_by = %s, updated_at = %s
        WHERE plant_code = %s
    """, (image_path, updated_by, _dt.datetime.now().isoformat(timespec="seconds"), plant_code))
    conn.commit()
    conn.close()


# ── Annexure-3 : 5 ISPs Major Units Records — Daily best (see
# major_unit_daily_record's own comment above and page_major_unit_records.py) ──

_MAJOR_UNIT_DAILY_COLS = (
    "plant_code", "unit_label", "unit_of_measure", "value",
    "record_date", "remarks", "sort_order", "updated_by", "updated_at",
)


def get_major_unit_daily_records(plant_code: str) -> List[dict]:
    """-> every unit row for one plant, in display order."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {','.join(_MAJOR_UNIT_DAILY_COLS)} FROM major_unit_daily_record "
        f"WHERE plant_code = %s ORDER BY sort_order",
        (plant_code,),
    )
    rows = [dict(zip(_MAJOR_UNIT_DAILY_COLS, r)) for r in cur.fetchall()]
    conn.close()
    return rows


def get_major_unit_daily_records_all() -> Dict[str, Dict[str, dict]]:
    """-> {plant_code: {unit_label: row_dict}} for every plant — used by
    page_major_unit_records.generate_major_unit_page to look up one plant's
    Daily figures alongside its live-computed Annual/Monthly bests."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(f"SELECT {','.join(_MAJOR_UNIT_DAILY_COLS)} FROM major_unit_daily_record")
    out: Dict[str, Dict[str, dict]] = {}
    for r in cur.fetchall():
        d = dict(zip(_MAJOR_UNIT_DAILY_COLS, r))
        out.setdefault(d["plant_code"], {})[d["unit_label"]] = d
    conn.close()
    return out


def save_major_unit_daily_record(plant_code: str, unit_label: str, value: Optional[float],
                                  unit_of_measure: Optional[str], record_date: Optional[str],
                                  remarks: Optional[str], sort_order: int, updated_by: str = "") -> None:
    """Upsert one unit's Daily best — used by both the one-time backfill
    (scripts/backfill_major_unit_daily_records.py) and the
    /data-entry/major-unit-daily editor (see main.py's
    /api/major-unit-daily/{plant_code} POST)."""
    import datetime as _dt
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO major_unit_daily_record
            (plant_code, unit_label, unit_of_measure, value, record_date,
             remarks, sort_order, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            unit_of_measure = new.unit_of_measure, value = new.value,
            record_date = new.record_date, remarks = new.remarks,
            sort_order = new.sort_order, updated_by = new.updated_by,
            updated_at = new.updated_at
    """, (plant_code, unit_label, unit_of_measure, value, record_date, remarks,
          sort_order, updated_by, _dt.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
