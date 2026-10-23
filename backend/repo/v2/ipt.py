"""IPT repository on the v2 schema: ipt_monthly (v1 ipt_table; from_plant /
to_plant -> from_plant_code / to_plant_code, aliased back here).

Same public names, signatures, return shapes, row types and exceptions as
repo/ipt.py. Aggregate columns keep v1's expressions, so a Row cursor sees
the same column labels ('MAX(unit)', 'SUM(plan)', ...).

ORDER. v1 reads without an ORDER BY were served by the primary key
(report_month, item, from_plant, to_plant), which v2's primary key repeats
under the same ai_ci collation; that order is explicit here
(plan_actual_rows, report_months, month_value_rows). cum_value_rows
reproduces v1's GROUP BY first-appearance order (a PARITY SHIM, see there).

WRITES. Bump first (skipped in a dry run); v1's column limits are checked
before anything is written (1048 / 1406 with v1's column names), then a
from / to plant longer than the v2 plant master's 8 characters is refused
(OutOfModelError; v1's VARCHAR(32) stored it). The month is cut to CHAR(7)
as MySQL cut it (_keys.fit_month); missing cal_month / plant rows are
created (_keys.ensure_month / ensure_plant). The activity 'old' and the
DELETE are v1's own statements, run with the raw month.
"""
from typing import Optional

import activity_context
from dbengine import connect
from repo import conn as rc
from repo import version as _ver
from repo.conn import row_dict as _row_dict
from repo.v2 import _keys

_V1_ROW = ("SELECT report_month, item, from_plant_code AS from_plant, to_plant_code AS to_plant, unit, "
           "sort_order, plan, actual, plan_tonnage, actual_tonnage FROM ipt_monthly")
_KEY = "report_month=%s AND item=%s AND from_plant_code=%s AND to_plant_code=%s"


# ── Moved from db.py ─────────────────────────────────────────────────────────

def save_ipt_entry(month: str, item: str, from_plant: str, to_plant: str,
                   unit: str = "T", sort_order: int = 0,
                   plan: Optional[float] = None, actual: Optional[float] = None,
                   plan_tonnage: Optional[float] = None,
                   actual_tonnage: Optional[float] = None):
    """Upsert one IPT route record for a month.
    For Rake routes, plan/actual are rake counts and
    plan_tonnage/actual_tonnage hold the tonnes equivalent."""
    stored_month = _keys.fit_month(month)
    _keys.fits("report_month", stored_month, 7, nullable=False)
    _keys.fits("item", item, 64, nullable=False)
    _keys.fits("from_plant", from_plant, 32, nullable=False)
    _keys.fits("to_plant", to_plant, 32, nullable=False)
    _keys.fits("unit", unit, 32)
    _keys.check_month(stored_month)
    _keys.check_plant_model(from_plant, "from_plant", 32)
    _keys.check_plant_model(to_plant, "to_plant", 32)
    conn = connect()
    try:
        old = _row_dict(conn, f"{_V1_ROW} WHERE {_KEY}", (month, item, from_plant, to_plant))
        cur = conn.cursor()
        _ver.bump(cur)
        _keys.ensure_month(cur, stored_month, bump=False)
        _keys.ensure_plant(cur, from_plant, bump=False)
        _keys.ensure_plant(cur, to_plant, bump=False)
        cur.execute("""
            INSERT INTO ipt_monthly
                (report_month, item, from_plant_code, to_plant_code, unit, sort_order,
                 plan, actual, plan_tonnage, actual_tonnage)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                unit = new.unit,
                sort_order = new.sort_order,
                plan = new.plan,
                actual = new.actual,
                plan_tonnage = new.plan_tonnage,
                actual_tonnage = new.actual_tonnage
        """, (stored_month, item, from_plant, to_plant, unit, sort_order,
              plan, actual, plan_tonnage, actual_tonnage))
        conn.commit()
    finally:
        conn.close()
    new = {"report_month": month, "item": item, "from_plant": from_plant, "to_plant": to_plant,
           "unit": unit, "sort_order": sort_order, "plan": plan, "actual": actual,
           "plan_tonnage": plan_tonnage, "actual_tonnage": actual_tonnage}
    activity_context.record(f"ipt_table/{item}/{from_plant}->{to_plant}/{month}", old, new)


def delete_ipt_entry(month: str, item: str, from_plant: str, to_plant: str) -> int:
    """Delete one IPT route record for a month, recording its prior state."""
    conn = connect()
    try:
        old = _row_dict(conn, f"{_V1_ROW} WHERE {_KEY}", (month, item, from_plant, to_plant))
        cur = conn.cursor()
        _ver.bump(cur)
        cur.execute(f"DELETE FROM ipt_monthly WHERE {_KEY}", (month, item, from_plant, to_plant))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    if old:
        activity_context.record(f"ipt_table/{item}/{from_plant}->{to_plant}/{month}", old, None)
    return deleted


# ── Named queries ────────────────────────────────────────────────────────────

def items(cur):
    """fetchall() of (item,), every non-blank item. main /api/ipt-items."""
    cur.execute("SELECT DISTINCT item FROM ipt_monthly WHERE item IS NOT NULL AND item <> '' ORDER BY item")
    return cur.fetchall()


def entry_rows(cur, month):
    """fetchall() of (item, from_plant, to_plant, unit, sort_order, plan,
    actual, plan_tonnage, actual_tonnage) for a month, in entry order.
    main /api/ipt-entries."""
    cur.execute("""
        SELECT item, from_plant_code AS from_plant, to_plant_code AS to_plant, unit, sort_order,
               plan, actual, plan_tonnage, actual_tonnage
        FROM ipt_monthly WHERE report_month = %s
        ORDER BY sort_order, item, from_plant_code, to_plant_code
    """, (month,))
    return cur.fetchall()


def routes(cur, months):
    """fetchall() of (item, from_plant, to_plant, MAX(unit), MIN(sort_order)),
    the union of routes over months in first-appearance order.
    main _ipt_fy_data, page_ipt.generate_ipt (same statement in both)."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT item, from_plant_code AS from_plant, to_plant_code AS to_plant, MAX(unit), MIN(sort_order)
            FROM ipt_monthly
            WHERE report_month IN ({ph})
            GROUP BY item, from_plant_code, to_plant_code
            ORDER BY MIN(sort_order), item, from_plant_code, to_plant_code
        """, months)
    return cur.fetchall()


def plan_actual_rows(cur, months):
    """fetchall() of (item, from_plant, to_plant, report_month, plan, actual)
    over months. main _ipt_fy_data."""
    phs = ",".join("%s" for _ in months)
    cur.execute(f"""
            SELECT item, from_plant_code AS from_plant, to_plant_code AS to_plant, report_month, plan, actual
            FROM ipt_monthly WHERE report_month IN ({phs})
            ORDER BY report_month, item, from_plant_code, to_plant_code
        """, months)
    return cur.fetchall()


def report_months(cur):
    """fetchall() of (report_month,), every well-formed YYYY-MM month with an
    ipt_table row. main /api/ipt-fys."""
    cur.execute("""
        SELECT DISTINCT report_month FROM ipt_monthly
        WHERE report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'
        ORDER BY report_month
    """)
    return cur.fetchall()


def month_value_rows(cur, report_month):
    """fetchall() of (item, from_plant, to_plant, plan, actual, plan_tonnage,
    actual_tonnage) for a month. page_ipt.generate_ipt."""
    cur.execute("""
            SELECT item, from_plant_code AS from_plant, to_plant_code AS to_plant,
                   plan, actual, plan_tonnage, actual_tonnage
            FROM ipt_monthly WHERE report_month=%s
            ORDER BY item, from_plant_code, to_plant_code
        """, (report_month,))
    return cur.fetchall()


def cum_value_rows(cur, months):
    """fetchall() of (item, from_plant, to_plant, SUM(plan), SUM(actual),
    SUM(plan_tonnage), SUM(actual_tonnage)) over months. page_ipt.generate_ipt."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT item, from_plant_code AS from_plant, to_plant_code AS to_plant,
                   SUM(plan), SUM(actual), SUM(plan_tonnage), SUM(actual_tonnage)
            FROM ipt_monthly
            WHERE report_month IN ({ph})
            GROUP BY item, from_plant_code, to_plant_code
            ORDER BY MIN(report_month), item, from_plant_code, to_plant_code
        """, months)
    # PARITY SHIM: v1 had no ORDER BY; its GROUP BY aggregated in a temporary
    # table, which returned the groups in their first-appearance order along
    # the primary-key scan (report_month, item, from, to), i.e. by first
    # month, then route. The ORDER BY above reproduces it (all 64 recorded
    # calls). Caller audit (page_ipt.generate_ipt, its only caller): the rows
    # become cum_map[(item, from, to)], read only with .get(); the order never
    # reaches output.
    return cur.fetchall()


def items_actual_sum_row(cur, months, item_names):
    """fetchone() of (SUM(actual) COALESCEd to 0,) over months and items, any
    route. page_prod_by_process._ipt_transfer_ytd."""
    ph_m = ",".join(["%s"] * len(months))
    ph_i = ",".join(["%s"] * len(item_names))
    cur.execute(
        f"SELECT COALESCE(SUM(actual),0) FROM ipt_monthly "
        f"WHERE report_month IN ({ph_m}) AND item IN ({ph_i})",
        (*months, *item_names),
    )
    return cur.fetchone()


def any_row_for_month(report_month):
    """True when ipt_table has any row for the month. page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM ipt_monthly WHERE report_month = %s LIMIT 1", [report_month])
        return bool(cur.fetchall())
