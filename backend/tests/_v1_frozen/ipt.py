"""IPT repository: ipt_table (inter-plant transfer plan / actual per month,
item and from->to route).

save_ipt_entry / delete_ipt_entry moved from db.py verbatim (re-exported
from db.py). The named cursor-level queries run on the caller's cursor and
return the plain fetchone() / fetchall() result.
"""
from typing import Optional

import activity_context
from dbengine import connect
from repo import version as _ver
from repo import conn as rc
from repo.conn import row_dict as _row_dict


# ── Moved from db.py ─────────────────────────────────────────────────────────

def save_ipt_entry(month: str, item: str, from_plant: str, to_plant: str,
                   unit: str = "T", sort_order: int = 0,
                   plan: Optional[float] = None, actual: Optional[float] = None,
                   plan_tonnage: Optional[float] = None,
                   actual_tonnage: Optional[float] = None):
    """Upsert one IPT route record for a month.
    For Rake routes, plan/actual are rake counts and
    plan_tonnage/actual_tonnage hold the tonnes equivalent."""
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM ipt_table WHERE report_month=%s AND item=%s AND from_plant=%s AND to_plant=%s",
        (month, item, from_plant, to_plant))
    _ver.bump(conn)
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
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM ipt_table WHERE report_month=%s AND item=%s AND from_plant=%s AND to_plant=%s",
        (month, item, from_plant, to_plant))
    _ver.bump(conn)
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


# ── Named queries (moved verbatim from callers) ──────────────────────────────

def items(cur):
    """fetchall() of (item,), every non-blank item. main /api/ipt-items."""
    cur.execute("SELECT DISTINCT item FROM ipt_table WHERE item IS NOT NULL AND item <> '' ORDER BY item")
    return cur.fetchall()


def entry_rows(cur, month):
    """fetchall() of (item, from_plant, to_plant, unit, sort_order, plan,
    actual, plan_tonnage, actual_tonnage) for a month, in entry order.
    main /api/ipt-entries."""
    cur.execute("""
        SELECT item, from_plant, to_plant, unit, sort_order,
               plan, actual, plan_tonnage, actual_tonnage
        FROM ipt_table WHERE report_month = %s
        ORDER BY sort_order, item, from_plant, to_plant
    """, (month,))
    return cur.fetchall()


def routes(cur, months):
    """fetchall() of (item, from_plant, to_plant, MAX(unit), MIN(sort_order)),
    the union of routes over months in first-appearance order.
    main _ipt_fy_data, page_ipt.generate_ipt (same statement in both)."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT item, from_plant, to_plant, MAX(unit), MIN(sort_order)
            FROM ipt_table
            WHERE report_month IN ({ph})
            GROUP BY item, from_plant, to_plant
            ORDER BY MIN(sort_order), item, from_plant, to_plant
        """, months)
    return cur.fetchall()


def plan_actual_rows(cur, months):
    """fetchall() of (item, from_plant, to_plant, report_month, plan, actual)
    over months. main _ipt_fy_data."""
    phs = ",".join("%s" for _ in months)
    cur.execute(f"""
            SELECT item, from_plant, to_plant, report_month, plan, actual
            FROM ipt_table WHERE report_month IN ({phs})
        """, months)
    return cur.fetchall()


def report_months(cur):
    """fetchall() of (report_month,), every well-formed YYYY-MM month with an
    ipt_table row. main /api/ipt-fys."""
    cur.execute("""
        SELECT DISTINCT report_month FROM ipt_table
        WHERE report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'
    """)
    return cur.fetchall()


def month_value_rows(cur, report_month):
    """fetchall() of (item, from_plant, to_plant, plan, actual, plan_tonnage,
    actual_tonnage) for a month. page_ipt.generate_ipt."""
    cur.execute("""
            SELECT item, from_plant, to_plant, plan, actual, plan_tonnage, actual_tonnage
            FROM ipt_table WHERE report_month=%s
        """, (report_month,))
    return cur.fetchall()


def cum_value_rows(cur, months):
    """fetchall() of (item, from_plant, to_plant, SUM(plan), SUM(actual),
    SUM(plan_tonnage), SUM(actual_tonnage)) over months. page_ipt.generate_ipt."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT item, from_plant, to_plant,
                   SUM(plan), SUM(actual), SUM(plan_tonnage), SUM(actual_tonnage)
            FROM ipt_table
            WHERE report_month IN ({ph})
            GROUP BY item, from_plant, to_plant
        """, months)
    return cur.fetchall()


def items_actual_sum_row(cur, months, item_names):
    """fetchone() of (SUM(actual) COALESCEd to 0,) over months and items, any
    route. page_prod_by_process._ipt_transfer_ytd."""
    ph_m = ",".join(["%s"] * len(months))
    ph_i = ",".join(["%s"] * len(item_names))
    cur.execute(
        f"SELECT COALESCE(SUM(actual),0) FROM ipt_table "
        f"WHERE report_month IN ({ph_m}) AND item IN ({ph_i})",
        (*months, *item_names),
    )
    return cur.fetchone()


def any_row_for_month(report_month):
    """True when ipt_table has any row for the month. page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM ipt_table WHERE report_month = %s LIMIT 1", [report_month])
        return bool(cur.fetchall())
