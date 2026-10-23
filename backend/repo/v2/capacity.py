"""Capacity repository on the v2 schema (item_capacity + item).

Same public names, signatures, return shapes and exceptions as
repo/capacity.py (v1 item_capacity_table: id, plant_name, item_name,
effective_month, annual_capacity, reason, created_by, created_at,
updated_by, updated_at; the timestamps were datetime.now().isoformat()
strings). v2 keeps the row id, plant_code -> plant_name, item_id -> the
item's exact name, and DATETIME(6) timestamps rendered back to the v1 ISO
strings (repo.v2codec, ISO_LOCAL).

Item names (see repo/v2/_keys.py): v1's uq_capacity_plant_item_month was
unique under ai_ci, so 'hot metal' clashed with a stored 'Hot Metal' entry
for the same plant and month. v2's unique key is on item_id (one id per
exact spelling), so the clash is checked in code and raised as the same
IntegrityError (1062). A write stores the caller's exact spelling (the item
is created when missing), as v1 stored it verbatim.

Months / plants: a write creates the cal_month / plant master row it needs
(repo/v2/_keys.py), as for production; only a month string that is not a
'YYYY-MM' at all is refused (api_capacity already rejects those with 400).
"""
from typing import Any, Dict, List, Optional

import activity_context
import report_context
from dbengine import Row, connect
from report_context import fold
from repo import conn as rc
from repo import version as _ver
from repo.conn import IntegrityError
from repo.conn import row_dict as _row_dict
from repo.v2 import _keys
from repo.v2codec import ISO_LOCAL, render_ts

# The v1 row, column for column.
_V1_SELECT = ("SELECT ic.id, ic.plant_code AS plant_name, i.item_name, ic.effective_month, "
              "ic.annual_capacity, ic.reason, ic.created_by, ic.created_at, ic.updated_by, ic.updated_at "
              "FROM item_capacity ic JOIN item i ON i.item_id = ic.item_id")
_ITEM_CI = "i.item_name COLLATE utf8mb4_0900_ai_ci"


def _v1_row(row) -> Dict[str, Any]:
    d = dict(row)
    d["created_at"] = render_ts(ISO_LOCAL, d["created_at"])
    d["updated_at"] = render_ts(ISO_LOCAL, d["updated_at"])
    return d


def _old(conn, entry_id):
    row = _row_dict(conn, _V1_SELECT + " WHERE ic.id=%s", (entry_id,))
    return None if row is None else _v1_row(row)


def list_capacity_entries(plant: Optional[str] = None, item: Optional[str] = None) -> List[Dict[str, Any]]:
    """List capacity-change entries, optionally filtered. Newest effective_month first."""
    conn = connect()
    sql = _V1_SELECT + " WHERE 1=1"
    args = []
    if plant:
        sql += " AND ic.plant_code=%s"; args.append(plant)
    if item:
        sql += f" AND {_ITEM_CI}=%s"; args.append(item)
    sql += f" ORDER BY ic.plant_code, {_ITEM_CI}, ic.effective_month DESC"
    prev_factory = conn.row_factory
    conn.row_factory = Row
    try:
        cur = conn.execute(sql, args)
        rows = [_v1_row(r) for r in cur.fetchall()]
    finally:
        conn.row_factory = prev_factory
        conn.close()
    return rows


def _capacity_load(_first, _last):
    """{(fold(plant), fold(item)): [(effective_month, annual_capacity), ...]}
    for every capacity row (the report_context window is not needed:
    capacity entries apply from their month onward)."""
    out = {}
    with rc.cursor() as cur:
        cur.execute("SELECT ic.plant_code, i.item_name, ic.effective_month, ic.annual_capacity "
                    "FROM item_capacity ic JOIN item i ON i.item_id = ic.item_id")
        for r in cur.fetchall():
            out.setdefault((fold(r[0]), fold(r[1])), []).append((r[2], r[3]))
    return out


_AT_SQL = ("SELECT ic.annual_capacity FROM item_capacity ic JOIN item i ON i.item_id = ic.item_id "
           f"WHERE ic.plant_code=%s AND {_ITEM_CI}=%s AND ic.effective_month<=%s "
           "ORDER BY ic.effective_month DESC LIMIT 1")


def get_effective_capacity(plant: str, item: str, month: str) -> Optional[float]:
    """Annual capacity ('000 T/yr) in effect for `plant`/`item` at `month` —
    the latest entry with effective_month <= month, or None.

    Inside report_context.activate() it is served from one load of the
    whole (small) table."""
    ctx = report_context.current()
    if ctx is not None:
        entries = ctx.load("capacity", _capacity_load).get((fold(plant), fold(item)), ())
        best = None
        for effective_month, annual_capacity in entries:
            if effective_month <= month and (best is None or effective_month > best[0]):
                best = (effective_month, annual_capacity)
        return best[1] if best else None
    conn = connect()
    try:
        row = conn.execute(_AT_SQL, (plant, item, month)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _item_id_for_write(cur, item, *, bump):
    """item_id of the item spelled exactly `item`, created when missing."""
    if bump:
        _ver.bump(cur)
    item_id = _keys.exact_item_id(cur, item, lock=True)
    if item_id is None:
        cur.execute("INSERT INTO item (item_name) VALUES (%s) AS new "
                    "ON DUPLICATE KEY UPDATE item_name = item.item_name", (item,))
        item_id = _keys.exact_item_id(cur, item, lock=True)
    return item_id


def _check_unique(cur, plant, item, effective_month, entry_id=None):
    """v1's uq_capacity_plant_item_month (ai_ci): IntegrityError 1062. A
    locking read (FOR SHARE, after the writer's bump), so a clash committed
    by a concurrent writer is seen, not an older snapshot."""
    sql = ("SELECT ic.id FROM item_capacity ic JOIN item i ON i.item_id = ic.item_id "
           f"WHERE ic.plant_code=%s AND {_ITEM_CI}=%s AND ic.effective_month=%s")
    args = [plant, item, effective_month]
    if entry_id is not None:
        sql += " AND ic.id<>%s"
        args.append(entry_id)
    sql += " FOR SHARE"
    if cur.execute(sql, args).fetchone() is not None:
        raise IntegrityError(1062, f"Duplicate entry '{plant}-{item}-{effective_month}' for key "
                                   "'item_capacity_table.uq_capacity_plant_item_month'")


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
        cur = conn.cursor()
        stored_month = _keys.fit_month(effective_month)     # what v1's CHAR(7) stored
        _keys.check_month(stored_month, "effective_month")
        _ver.bump(cur)
        _keys.ensure_month(cur, stored_month, bump=False)
        _keys.ensure_plant(cur, plant, bump=False)
        item_id = _item_id_for_write(cur, item, bump=False)
        _check_unique(cur, plant, item, stored_month)
        cur.execute("""
            INSERT INTO item_capacity
                (plant_code, item_id, effective_month, annual_capacity, reason,
                 created_by, created_at, updated_by, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (plant, item_id, stored_month, annual_capacity, reason,
              created_by, now, created_by, now))
        new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    activity_context.record(f"item_capacity_table/{plant}/{item}/{new_id}", None, {
        "plant_name": plant, "item_name": item, "effective_month": effective_month,
        "annual_capacity": annual_capacity, "reason": reason,
    })
    return new_id


_COLUMN = {"plant_name": "plant_code", "effective_month": "effective_month",
           "annual_capacity": "annual_capacity", "reason": "reason"}


def update_capacity_entry(entry_id: int, updated_by: str, **fields) -> bool:
    """Update any subset of item_name/plant_name/effective_month/annual_capacity/
    reason on one capacity entry. Returns False if the row doesn't exist.
    Raises IntegrityError on a resulting (plant, item, effective_month)
    clash with another row."""
    from datetime import datetime
    conn = connect()
    old = _old(conn, entry_id)
    if old is None:
        conn.close()
        return False
    allowed = {"plant_name", "item_name", "effective_month", "annual_capacity", "reason"}
    given = {k: v for k, v in fields.items() if k in allowed}
    if not given:
        conn.close()
        return True
    try:
        cur = conn.cursor()
        # what v1's CHAR(7) stored (the activity entry below keeps the raw value, as v1's did)
        stored = dict(given)
        if "effective_month" in given:
            stored["effective_month"] = _keys.fit_month(given["effective_month"])
            _keys.check_month(stored["effective_month"], "effective_month")
        _ver.bump(cur)
        if "effective_month" in given:
            _keys.ensure_month(cur, stored["effective_month"], bump=False)
        if "plant_name" in given:
            _keys.ensure_plant(cur, given["plant_name"], bump=False)
        sets, args = [], []
        for k, v in stored.items():
            if k == "item_name":
                sets.append("item_id=%s")
                args.append(_item_id_for_write(cur, v, bump=False))
            else:
                sets.append(f"{_COLUMN[k]}=%s")
                args.append(v)
        sets.append("updated_by=%s"); args.append(updated_by)
        sets.append("updated_at=%s"); args.append(datetime.now().isoformat())
        after = {**old, **stored}
        _check_unique(cur, after["plant_name"], after["item_name"], after["effective_month"], entry_id)
        args.append(entry_id)
        cur.execute(f"UPDATE item_capacity SET {', '.join(sets)} WHERE id=%s", args)
        conn.commit()
    finally:
        conn.close()
    new = {**old, **given}
    activity_context.record(f"item_capacity_table/{old['plant_name']}/{old['item_name']}/{entry_id}", old, new)
    return True


def delete_capacity_entry(entry_id: int) -> bool:
    """Delete one capacity entry, recording its prior state. Returns False if not found."""
    conn = connect()
    old = _old(conn, entry_id)
    if old is None:
        conn.close()
        return False
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        cur.execute("DELETE FROM item_capacity WHERE id=%s", (entry_id,))
        conn.commit()
    finally:
        conn.close()
    activity_context.record(f"item_capacity_table/{old['plant_name']}/{old['item_name']}/{entry_id}", old, None)
    return True


# ── Queries moved from page / api modules ──────────────────────────────────

def capacity_row_at(cur, plant, item_name, month):
    """fetchone() of the annual_capacity in effect at `month` (api_production_loss)."""
    return cur.execute(_AT_SQL, (plant, item_name, month)).fetchone()
