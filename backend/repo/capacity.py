"""Capacity repository: item_capacity_table (annual capacity per plant/item,
effective from a month). Functions moved verbatim from db.py."""
from typing import Any, Dict, List, Optional

import activity_context
from dbengine import Row, connect
from repo import version as _ver
from repo.conn import row_dict as _row_dict


def list_capacity_entries(plant: Optional[str] = None, item: Optional[str] = None) -> List[Dict[str, Any]]:
    """List capacity-change entries, optionally filtered. Newest effective_month first."""
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
        _ver.bump(conn)
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
        _ver.bump(conn)
        conn.commit()
    finally:
        conn.close()
    new = {**old, **{k: v for k, v in fields.items() if k in allowed}}
    activity_context.record(f"item_capacity_table/{old['plant_name']}/{old['item_name']}/{entry_id}", old, new)
    return True


def delete_capacity_entry(entry_id: int) -> bool:
    """Delete one capacity entry, recording its prior state. Returns False if not found."""
    conn = connect()
    old = _row_dict(conn, "SELECT * FROM item_capacity_table WHERE id=%s", (entry_id,))
    if old is None:
        conn.close()
        return False
    conn.execute("DELETE FROM item_capacity_table WHERE id=%s", (entry_id,))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    activity_context.record(f"item_capacity_table/{old['plant_name']}/{old['item_name']}/{entry_id}", old, None)
    return True


# ── Queries moved from page / api modules ──────────────────────────────────

def capacity_row_at(cur, plant, item_name, month):
    """fetchone() of the annual_capacity in effect at `month` (api_production_loss)."""
    return cur.execute("""SELECT annual_capacity FROM item_capacity_table
                              WHERE plant_name=%s AND item_name=%s AND effective_month<=%s
                              ORDER BY effective_month DESC LIMIT 1""", (plant, item_name, month)).fetchone()
