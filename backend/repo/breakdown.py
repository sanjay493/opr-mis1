"""Breakdown / capital repair repository: breakdown_table (ad hoc
unplanned-downtime events, full CRUD via /api/breakdown) and
capital_repair_table (the yearly capital repair schedule plus its actuals,
edited via main.py's /api/capital-repair-* routes).

The db.py functions moved here verbatim (re-exported from db.py). The named
queries further down are the statements that used to live inline in
main.py / api_breakdown.py / api_production_loss.py / page_capital_repair.py
/ page_secretary_review_texts.py, moved verbatim: each runs on the caller's
cursor or connection (so the caller's connection, transaction, commit point
and row type are unchanged) and returns the plain fetchone() / fetchall()
result.
"""
from typing import Any, Dict, List, Optional

import activity_context
from dbengine import Row, connect
from repo.conn import row_dict as _row_dict


# ── Moved from db.py ─────────────────────────────────────────────────────────

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


# ── Named queries (moved verbatim from their callers) ───────────────────────
# `conn` parameters take a db.connect() connection (conn.execute opens a
# fresh cursor, as the caller did); `cur` parameters take the caller's
# cursor. Nothing here commits: the caller keeps its commit point.

def breakdown_rows_for_plant(conn, plant):
    """fetchall() of the loss engine's breakdown columns for one plant.
    api_production_loss._bd_rows_for_plant."""
    cur = conn.execute("""
            SELECT id, unit_type, unit_name, sms_subtag, start_ts, end_ts, is_ongoing, cause,
                   hours_lost_override, capital_repair_id
            FROM breakdown_table
            WHERE plant=%s
        """, (plant,))
    return cur.fetchall()


def open_breakdown_rows(cur, end_day, start_day):
    """fetchall() of the unlinked breakdowns open at some point in
    [start_day, end_day). page_secretary_review_texts._fetch_breakdowns."""
    cur.execute(
        "SELECT plant, unit_type, unit_name, start_ts, end_ts, is_ongoing, cause, hours_lost_override "
        "FROM breakdown_table WHERE capital_repair_id IS NULL AND start_ts < %s "
        "AND (end_ts IS NULL OR end_ts >= %s OR is_ongoing = 1)",
        (end_day, start_day),
    )
    return cur.fetchall()


def cr_actual_rows(conn, cols, plant):
    """fetchall() of `cols` for the plant's capital repairs that have actual
    dates (linkable to a breakdown). api_breakdown._actual_crs."""
    cur = conn.execute(
            f"SELECT {', '.join(cols)} FROM capital_repair_table "
            "WHERE plant=%s AND actual_start IS NOT NULL AND actual_start<>''", (plant,))
    return cur.fetchall()


def cr_plant_row(cur, cr_id):
    """fetchone() of (plant,) for one capital repair, on a cursor or a
    connection. api_breakdown._validate_cr_link, main
    /api/capital-repair-entry."""
    return cur.execute("SELECT plant FROM capital_repair_table WHERE id=%s", (cr_id,)).fetchone()


def cr_rows_for_plant(conn, plant):
    """fetchall() of the loss engine's capital repair columns for one plant.
    api_production_loss._cr_rows_for_plant."""
    cur = conn.execute("""
            SELECT id, shop, equipment, activity, unit_type, unit_name, sms_subtag,
                   actual_start, actual_end, actual_ongoing, planned_days, period, schedule_days
            FROM capital_repair_table
            WHERE plant=%s
        """, (plant,))
    return cur.fetchall()


def cr_report_rows(cur, plant, fy):
    """fetchall() of one plant/FY's rows for the Capital Repair report page,
    in saved order. page_capital_repair.generate_capital_repair."""
    cur.execute("""
            SELECT id, shop, equipment, activity, schedule_days, period, actual,
                   actual_start, actual_end, actual_ongoing
            FROM capital_repair_table
            WHERE plant=%s AND fy=%s
            ORDER BY sort_order ASC, id ASC
        """, (plant, fy))
    return cur.fetchall()


def cr_calendar_rows(cur, plant, fy):
    """fetchall() of one plant/FY's rows for the capital repair calendar,
    in saved order. page_capital_repair.generate_capital_repair_calendar."""
    cur.execute("""
            SELECT shop, equipment, activity, period, actual,
                   actual_start, actual_end, actual_ongoing, schedule_days
            FROM capital_repair_table
            WHERE plant=%s AND fy=%s
            ORDER BY sort_order ASC, id ASC
        """, (plant, fy))
    return cur.fetchall()


def cr_started_rows(cur, plant, fy_label, upto_iso):
    """fetchall() of the plant/FY's capital repairs started by upto_iso,
    oldest first. page_secretary_review_texts._fetch_cr."""
    cur.execute(
        "SELECT shop, equipment, actual_start, actual_end, actual_ongoing FROM capital_repair_table "
        "WHERE plant=%s AND fy=%s AND actual_start IS NOT NULL AND actual_start <> '' AND actual_start <= %s "
        "ORDER BY actual_start",
        (plant, fy_label, upto_iso),
    )
    return cur.fetchall()


def cr_entry_rows(cur, plant, fy):
    """fetchall() of one plant/FY's rows for the data-entry grid, in saved
    order. main GET /api/capital-repair."""
    cur.execute("""
        SELECT id, shop, equipment, activity, schedule_days, period, actual,
               unit_type, unit_name, sms_subtag, actual_start, actual_end,
               actual_ongoing, planned_days
        FROM capital_repair_table
        WHERE plant=%s AND fy=%s
        ORDER BY sort_order ASC, id ASC
    """, (plant, fy))
    return cur.fetchall()


def cr_actual_and_start_row(cur, row_id):
    """fetchone() of (actual, actual_start). main /api/capital-repair-entry."""
    cur.execute("SELECT actual, actual_start FROM capital_repair_table WHERE id=%s", (row_id,))
    return cur.fetchone()


def cr_entry_old(conn, plan_fields, row_id):
    """The row's editable columns as a dict (activity-log "old" snapshot), or
    None. main /api/capital-repair-entry."""
    return _row_dict(conn,
        "SELECT unit_type, unit_name, sms_subtag, actual_start, actual_end, actual_ongoing, planned_days, actual, "
        + ", ".join(plan_fields) + " FROM capital_repair_table WHERE id=%s", (row_id,))


def update_cr_entry(cur, plan_sql, params):
    """Update one row's classification / actual (plus the plan columns in
    plan_sql, ", col=%s" each) on the caller's cursor; the caller commits.
    main /api/capital-repair-entry."""
    cur.execute(f"""
        UPDATE capital_repair_table
        SET unit_type=%s, unit_name=%s, sms_subtag=%s, actual_start=%s, actual_end=%s,
            actual_ongoing=%s, planned_days=%s, actual=%s{plan_sql}
        WHERE id=%s
    """, params)


def cr_renumber(cur, plant: str, fy: str, ids: list) -> None:
    """sort_order = position in `ids` for a plant/FY's rows; the caller
    commits. main (was _cr_renumber)."""
    for i, rid in enumerate(ids):
        cur.execute("UPDATE capital_repair_table SET sort_order=%s WHERE id=%s AND plant=%s AND fy=%s",
                    (i, rid, plant, fy))


def cr_ordered_ids(cur, plant: str, fy: str) -> list:
    """A plant/FY's row ids in saved order. main (was _cr_ordered_ids)."""
    cur.execute("SELECT id FROM capital_repair_table WHERE plant=%s AND fy=%s ORDER BY sort_order ASC, id ASC",
                (plant, fy))
    return [r[0] for r in cur.fetchall()]


def cr_copy_source(conn, copy_from, plant, fy):
    """The row to copy (shop/equipment/activity/unit classification) as a
    dict, or None. main /api/capital-repair-row."""
    return _row_dict(conn,
            "SELECT shop, equipment, activity, unit_type, unit_name, sms_subtag "
            "FROM capital_repair_table WHERE id=%s AND plant=%s AND fy=%s", (copy_from, plant, fy))


def insert_cr_row(cur, values):
    """Insert one row (sort_order 0, renumbered by the caller) on the
    caller's cursor; the caller reads cur.lastrowid and commits.
    main /api/capital-repair-row."""
    cur.execute("""
        INSERT INTO capital_repair_table
            (plant, fy, shop, equipment, activity, schedule_days, period, actual,
             unit_type, unit_name, sms_subtag, actual_ongoing, sort_order)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
    """, values)


def cr_row_dict(conn, row_id):
    """The whole row as a dict, or None. main DELETE /api/capital-repair-row."""
    return _row_dict(conn, "SELECT * FROM capital_repair_table WHERE id=%s", (row_id,))


def delete_cr_row(cur, row_id):
    """Delete one row on the caller's cursor; the caller renumbers and
    commits. main DELETE /api/capital-repair-row."""
    cur.execute("DELETE FROM capital_repair_table WHERE id=%s", (row_id,))
