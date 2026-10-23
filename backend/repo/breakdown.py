"""Breakdown / capital repair repository on the v2 schema: breakdown and
capital_repair (v1 breakdown_table, capital_repair_table).

Same public names, signatures, return shapes, row types and exceptions as
repo/breakdown.py. Renamed columns are aliased back to their v1 names
(plant <- plant_code, unit_name <- plant_unit.unit_code); timestamps are
rendered back to the v1 ISO strings (repo.v2codec, ISO_LOCAL); the capital
repair dates are DATEs, which dbengine hands back as 'YYYY-MM-DD' text.

UNITS. plant_unit.unit_code is utf8mb4_0900_bin: each spelling is its own
unit row. Reads compare units under `COLLATE utf8mb4_0900_ai_ci`, as v1's
column did. v1 stored the caller's unit_name verbatim on every row (no
unique key), so a write resolves the unit by the EXACT string (created
when missing, unit_type NULL) and reads it back unchanged. breakdown
and capital_repair keep their own row-level unit_type.

capital_repair.unit_id is NULL when v1's unit_name was NULL.
breakdown.capital_repair_id is a deliberate non-FK: a dangling id stays
verbatim.

DATES. capital_repair.actual_start / actual_end were CHAR(10) text in v1
and are DATEs in v2. A write of a string that is not a canonical
'YYYY-MM-DD' date is refused (OutOfModelError, before anything is written;
parity_exceptions.md §2); v1's `actual_start <> ''` filter is `IS NOT NULL`
(an empty string cannot be stored). An FY longer than CHAR(7) (v1 held 8)
is refused the same way.

ORDER. Reads v1 served without an ORDER BY from an index have an explicit
ORDER BY reproducing that index order.

WRITES. Every write bumps first (skipped in a dry run); lookups that
decide the write are locking reads taken after the bump; v1 column limits
are checked in v1's column order (_keys.fits: 1048 / 1406 with v1's column
names) before anything is written.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import activity_context
from dbengine import Row, connect
from repo import version as _ver
from repo.conn import row_dict as _row_dict
from repo import _keys
from repo.v2codec import CodecError, ISO_LOCAL, parse_date, render_ts

_UC = "pu.unit_code COLLATE utf8mb4_0900_ai_ci"

# breakdown_table's columns in v1 order (SELECT * order)
_BD_SELECT = ("SELECT b.id, b.plant_code AS plant, b.unit_type, pu.unit_code AS unit_name, b.sms_subtag, "
              "b.start_ts, b.end_ts, b.is_ongoing, b.cause, b.hours_lost_override, b.capital_repair_id, "
              "b.created_by, b.created_at, b.updated_by, b.updated_at "
              "FROM breakdown b JOIN plant_unit pu ON pu.unit_id = b.unit_id")
_BD_LOCK = " FOR UPDATE OF b FOR SHARE OF pu"

# capital_repair_table: v1 column -> v2 expression
_CR_FROM = "FROM capital_repair c LEFT JOIN plant_unit pu ON pu.unit_id = c.unit_id"
_CR_EXPR = {
    "id": "c.id", "plant": "c.plant_code AS plant", "fy": "c.fy", "shop": "c.shop",
    "equipment": "c.equipment", "unit_type": "c.unit_type", "unit_name": "pu.unit_code AS unit_name",
    "sms_subtag": "c.sms_subtag", "activity": "c.activity", "schedule_days": "c.schedule_days",
    "actual_start": "c.actual_start", "actual_end": "c.actual_end", "actual_ongoing": "c.actual_ongoing",
    "planned_days": "c.planned_days", "period": "c.period", "actual": "c.actual", "sort_order": "c.sort_order",
}
_CR_ALL = ("id", "plant", "fy", "shop", "equipment", "unit_type", "unit_name", "sms_subtag", "activity",
           "schedule_days", "actual_start", "actual_end", "actual_ongoing", "planned_days", "period",
           "actual", "sort_order")


def _cr_cols(cols):
    return ", ".join(_CR_EXPR[c] for c in cols)


def _v1_bd(row) -> Dict[str, Any]:
    d = dict(row)
    d["created_at"] = render_ts(ISO_LOCAL, d["created_at"])
    d["updated_at"] = render_ts(ISO_LOCAL, d["updated_at"])
    return d


def _bd_old(conn, breakdown_id, lock=False):
    row = _row_dict(conn, _BD_SELECT + " WHERE b.id=%s" + (_BD_LOCK if lock else ""), (breakdown_id,))
    return None if row is None else _v1_bd(row)


# ── Moved from db.py ─────────────────────────────────────────────────────────

def list_breakdown_entries(plant: Optional[str] = None, fy: Optional[str] = None,
                            unit_type: Optional[str] = None, unit_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """List breakdown events, optionally filtered. `fy` filters by the FY
    fy_from_month(start_ts) falls in (computed in Python — start_ts has no
    stored FY column, see breakdown_table's docstring in init_db())."""
    from page_capital_repair import fy_from_month
    conn = connect()
    sql = _BD_SELECT + " WHERE 1=1"
    args = []
    if plant:
        sql += " AND b.plant_code=%s"; args.append(plant)
    if unit_type:
        sql += " AND b.unit_type=%s"; args.append(unit_type)
    if unit_name:
        sql += f" AND {_UC}=%s"; args.append(unit_name)
    sql += " ORDER BY b.start_ts DESC, b.id DESC"
    prev_factory = conn.row_factory
    conn.row_factory = Row
    try:
        cur = conn.execute(sql, args)
        rows = [_v1_bd(r) for r in cur.fetchall()]
    finally:
        conn.row_factory = prev_factory
        conn.close()
    if fy:
        rows = [r for r in rows if r.get("start_ts") and fy_from_month(r["start_ts"][:7]) == fy]
    return rows


def _fits_breakdown(plant, unit_type, unit_name, sms_subtag, start_ts, end_ts):
    _keys.fits("plant", plant, 8, nullable=False)
    _keys.fits("unit_type", unit_type, 16, nullable=False)
    _keys.fits("unit_name", unit_name, 32, nullable=False)
    _keys.fits("sms_subtag", sms_subtag, 16)
    _keys.fits("start_ts", start_ts, 16, nullable=False)
    _keys.fits("end_ts", end_ts, 16)


def save_breakdown_entry(plant: str, unit_type: str, unit_name: str, sms_subtag: Optional[str],
                          start_ts: str, end_ts: Optional[str], is_ongoing: bool,
                          cause: str, hours_lost_override: Optional[float],
                          created_by: str, capital_repair_id: Optional[int] = None) -> int:
    """Create one breakdown event. Returns the new row id. capital_repair_id
    links it to the capital repair it really is (see bd_cr_link)."""
    conn = connect()
    now = datetime.now()
    try:
        cur = conn.cursor()
        _fits_breakdown(plant, unit_type, unit_name, sms_subtag, start_ts, end_ts)
        ongoing = int(is_ongoing)
        _keys.fits("cause", cause, 1 << 30, nullable=False)
        _keys.fits("created_by", created_by, 190)
        _keys.check_plant_model(plant, "plant", 8)
        _ver.bump(cur)
        _keys.ensure_plant(cur, plant, bump=False)
        unit_id = _keys.exact_unit_id(cur, plant, unit_name, bump=False)
        cur.execute("""
            INSERT INTO breakdown
                (plant_code, unit_type, unit_id, sms_subtag, start_ts, end_ts, is_ongoing,
                 cause, hours_lost_override, capital_repair_id, created_by, created_at, updated_by, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (plant, unit_type, unit_id, sms_subtag, start_ts, end_ts, ongoing,
              cause, hours_lost_override, capital_repair_id, created_by, now, created_by, now))
        new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    activity_context.record(f"breakdown_table/{plant}/{unit_name}/{new_id}", None, {
        "plant": plant, "unit_type": unit_type, "unit_name": unit_name, "sms_subtag": sms_subtag,
        "start_ts": start_ts, "end_ts": end_ts, "is_ongoing": is_ongoing, "cause": cause,
        "hours_lost_override": hours_lost_override, "capital_repair_id": capital_repair_id,
    })
    return new_id


_BD_LIMITS = {"plant": (8, False), "unit_type": (16, False), "unit_name": (32, False), "sms_subtag": (16, True),
              "start_ts": (16, False), "end_ts": (16, True), "cause": (1 << 30, False)}


def update_breakdown_entry(breakdown_id: int, updated_by: str, **fields) -> bool:
    """Update the given fields (any subset of plant/unit_type/unit_name/sms_subtag/
    start_ts/end_ts/is_ongoing/cause/hours_lost_override/capital_repair_id) on one breakdown event.
    Returns False if the row doesn't exist."""
    conn = connect()
    try:
        old = _bd_old(conn, breakdown_id)
        if old is None:
            return False
        allowed = {"plant", "unit_type", "unit_name", "sms_subtag", "start_ts", "end_ts",
                   "is_ongoing", "cause", "hours_lost_override", "capital_repair_id"}
        given = {k: v for k, v in fields.items() if k in allowed}
        if not given:
            return True
        sets, args = [], []
        for k, v in given.items():
            if k in _BD_LIMITS:
                _keys.fits(k, v, _BD_LIMITS[k][0], nullable=_BD_LIMITS[k][1])
            if k == "is_ongoing":
                v = int(v)
            if k not in ("plant", "unit_name"):
                sets.append(f"{k}=%s")
                args.append(v)
        _keys.fits("updated_by", updated_by, 190)
        if "plant" in given:
            _keys.check_plant_model(given["plant"], "plant", 8)
        cur = conn.cursor()
        _ver.bump(cur)
        old = _bd_old(conn, breakdown_id, lock=True) or old
        if "plant" in given or "unit_name" in given:
            plant = given.get("plant", old["plant"])
            unit = given.get("unit_name", old["unit_name"])
            if "plant" in given:
                _keys.ensure_plant(cur, plant, bump=False)
            sets.append("plant_code=%s"); args.append(plant)
            sets.append("unit_id=%s"); args.append(_keys.exact_unit_id(cur, plant, unit, bump=False))
        sets.append("updated_by=%s"); args.append(updated_by)
        sets.append("updated_at=%s"); args.append(datetime.now())
        args.append(breakdown_id)
        cur.execute(f"UPDATE breakdown SET {', '.join(sets)} WHERE id=%s", args)
        conn.commit()
    finally:
        conn.close()
    new = {**old, **given}
    activity_context.record(f"breakdown_table/{old['plant']}/{old['unit_name']}/{breakdown_id}", old, new)
    return True


def delete_breakdown_entry(breakdown_id: int) -> bool:
    """Delete one breakdown event, recording its prior state. Returns False if not found."""
    conn = connect()
    try:
        old = _bd_old(conn, breakdown_id)
        if old is None:
            return False
        cur = conn.cursor()
        _ver.bump(cur)
        old = _bd_old(conn, breakdown_id, lock=True) or old
        cur.execute("DELETE FROM breakdown WHERE id=%s", (breakdown_id,))
        conn.commit()
    finally:
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
    cur = conn.execute(f"""
            SELECT b.id, b.unit_type, pu.unit_code AS unit_name, b.sms_subtag, b.start_ts, b.end_ts,
                   b.is_ongoing, b.cause, b.hours_lost_override, b.capital_repair_id
            FROM breakdown b JOIN plant_unit pu ON pu.unit_id = b.unit_id
            WHERE b.plant_code=%s
            ORDER BY b.unit_type, {_UC}, b.id
        """, (plant,))
    return cur.fetchall()


def open_breakdown_rows(cur, end_day, start_day):
    """fetchall() of the unlinked breakdowns open at some point in
    [start_day, end_day). page_secretary_review_texts._fetch_breakdowns."""
    cur.execute(
        "SELECT b.plant_code AS plant, b.unit_type, pu.unit_code AS unit_name, b.start_ts, b.end_ts, "
        "b.is_ongoing, b.cause, b.hours_lost_override "
        "FROM breakdown b JOIN plant_unit pu ON pu.unit_id = b.unit_id "
        "WHERE b.capital_repair_id IS NULL AND b.start_ts < %s "
        "AND (b.end_ts IS NULL OR b.end_ts >= %s OR b.is_ongoing = 1) ORDER BY b.id",
        (end_day, start_day),
    )
    return cur.fetchall()


def cr_actual_rows(conn, cols, plant):
    """fetchall() of `cols` for the plant's capital repairs that have actual
    dates (linkable to a breakdown). api_breakdown._actual_crs."""
    cur = conn.execute(
            f"SELECT {_cr_cols(cols)} {_CR_FROM} "
            "WHERE c.plant_code=%s AND c.actual_start IS NOT NULL ORDER BY c.fy, c.id", (plant,))
    return cur.fetchall()


def cr_plant_row(cur, cr_id):
    """fetchone() of (plant,) for one capital repair, on a cursor or a
    connection. api_breakdown._validate_cr_link, main
    /api/capital-repair-entry."""
    return cur.execute("SELECT plant_code AS plant FROM capital_repair WHERE id=%s", (cr_id,)).fetchone()


def cr_rows_for_plant(conn, plant):
    """fetchall() of the loss engine's capital repair columns for one plant.
    api_production_loss._cr_rows_for_plant."""
    cur = conn.execute("""
            SELECT c.id, c.shop, c.equipment, c.activity, c.unit_type, pu.unit_code AS unit_name, c.sms_subtag,
                   c.actual_start, c.actual_end, c.actual_ongoing, c.planned_days, c.period, c.schedule_days
            FROM capital_repair c LEFT JOIN plant_unit pu ON pu.unit_id = c.unit_id
            WHERE c.plant_code=%s
            ORDER BY c.fy, c.id
        """, (plant,))
    return cur.fetchall()


def cr_report_rows(cur, plant, fy):
    """fetchall() of one plant/FY's rows for the Capital Repair report page,
    in saved order. page_capital_repair.generate_capital_repair."""
    cur.execute("""
            SELECT id, shop, equipment, activity, schedule_days, period, actual,
                   actual_start, actual_end, actual_ongoing
            FROM capital_repair
            WHERE plant_code=%s AND fy=%s
            ORDER BY sort_order ASC, id ASC
        """, (plant, fy))
    return cur.fetchall()


def cr_calendar_rows(cur, plant, fy):
    """fetchall() of one plant/FY's rows for the capital repair calendar,
    in saved order. page_capital_repair.generate_capital_repair_calendar."""
    cur.execute("""
            SELECT shop, equipment, activity, period, actual,
                   actual_start, actual_end, actual_ongoing, schedule_days
            FROM capital_repair
            WHERE plant_code=%s AND fy=%s
            ORDER BY sort_order ASC, id ASC
        """, (plant, fy))
    return cur.fetchall()


def cr_started_rows(cur, plant, fy_label, upto_iso):
    """fetchall() of the plant/FY's capital repairs started by upto_iso,
    oldest first. page_secretary_review_texts._fetch_cr."""
    cur.execute(
        "SELECT shop, equipment, actual_start, actual_end, actual_ongoing FROM capital_repair "
        "WHERE plant_code=%s AND fy=%s AND actual_start IS NOT NULL AND actual_start <= %s "
        "ORDER BY actual_start, id",
        (plant, fy_label, upto_iso),
    )
    return cur.fetchall()


def cr_entry_rows(cur, plant, fy):
    """fetchall() of one plant/FY's rows for the data-entry grid, in saved
    order. main GET /api/capital-repair."""
    cur.execute("""
        SELECT c.id, c.shop, c.equipment, c.activity, c.schedule_days, c.period, c.actual,
               c.unit_type, pu.unit_code AS unit_name, c.sms_subtag, c.actual_start, c.actual_end,
               c.actual_ongoing, c.planned_days
        FROM capital_repair c LEFT JOIN plant_unit pu ON pu.unit_id = c.unit_id
        WHERE c.plant_code=%s AND c.fy=%s
        ORDER BY c.sort_order ASC, c.id ASC
    """, (plant, fy))
    return cur.fetchall()


def cr_actual_and_start_row(cur, row_id):
    """fetchone() of (actual, actual_start). main /api/capital-repair-entry."""
    cur.execute("SELECT actual, actual_start FROM capital_repair WHERE id=%s", (row_id,))
    return cur.fetchone()


def cr_entry_old(conn, plan_fields, row_id):
    """The row's editable columns as a dict (activity-log "old" snapshot), or
    None. main /api/capital-repair-entry."""
    cols = ["unit_type", "unit_name", "sms_subtag", "actual_start", "actual_end", "actual_ongoing",
            "planned_days", "actual", *plan_fields]
    return _row_dict(conn, f"SELECT {_cr_cols(cols)} {_CR_FROM} WHERE c.id=%s", (row_id,))


_CR_FITS = (("unit_type", 16), ("unit_name", 32), ("sms_subtag", 16), ("actual_start", 10), ("actual_end", 10))
_PLAN_LIMITS = {"shop": 64, "equipment": 64, "activity": 255, "schedule_days": 64, "period": 64}


def _day(column, value):
    """The DATE for a v1 CHAR(10) date string (trailing spaces cut as MySQL
    cut them), None for NULL; OutOfModelError when it is not a canonical
    'YYYY-MM-DD' (parity_exceptions.md §2)."""
    if value is None:
        return None
    try:
        return parse_date(_keys.fit_char(value, 10))
    except (CodecError, TypeError):
        raise _keys.OutOfModelError(f"{column} {value!r}: v1 stored it as text, the v2 DATE holds only "
                                    "a 'YYYY-MM-DD' date") from None


def update_cr_entry(cur, plan_sql, params):
    """Update one row's classification / actual (plus the plan columns in
    plan_sql, ", col=%s" each) on the caller's cursor; the caller commits.
    main /api/capital-repair-entry."""
    (unit_type, unit_name, sms_subtag, actual_start, actual_end, actual_ongoing, planned_days, actual,
     *rest) = params
    row_id = rest[-1]
    plan_cols = [s.strip().split("=")[0] for s in plan_sql.split(", ") if s.strip()]
    plan_vals = rest[:-1]
    for col, limit in _CR_FITS:
        _keys.fits(col, {"unit_type": unit_type, "unit_name": unit_name, "sms_subtag": sms_subtag,
                         "actual_start": actual_start, "actual_end": actual_end}[col], limit)
    _keys.fits("actual", actual, 128)
    for col, val in zip(plan_cols, plan_vals):
        _keys.fits(col, val, _PLAN_LIMITS[col])
    start, end = _day("actual_start", actual_start), _day("actual_end", actual_end)
    _ver.bump(cur)
    row = cur.execute("SELECT plant_code FROM capital_repair WHERE id=%s FOR UPDATE", (row_id,)).fetchone()
    unit_id = None
    if unit_name is not None and row is not None:
        unit_id = _keys.exact_unit_id(cur, row[0], unit_name, bump=False)
    cur.execute(f"""
        UPDATE capital_repair
        SET unit_type=%s, unit_id=%s, sms_subtag=%s, actual_start=%s, actual_end=%s,
            actual_ongoing=%s, planned_days=%s, actual=%s{plan_sql}
        WHERE id=%s
    """, (unit_type, unit_id, sms_subtag, start, end, actual_ongoing, planned_days, actual, *rest))


def cr_renumber(cur, plant: str, fy: str, ids: list) -> None:
    """sort_order = position in `ids` for a plant/FY's rows; the caller
    commits. main (was _cr_renumber)."""
    _ver.bump(cur)
    for i, rid in enumerate(ids):
        cur.execute("UPDATE capital_repair SET sort_order=%s WHERE id=%s AND plant_code=%s AND fy=%s",
                    (i, rid, plant, fy))


def cr_ordered_ids(cur, plant: str, fy: str) -> list:
    """A plant/FY's row ids in saved order. main (was _cr_ordered_ids)."""
    cur.execute("SELECT id FROM capital_repair WHERE plant_code=%s AND fy=%s ORDER BY sort_order ASC, id ASC",
                (plant, fy))
    return [r[0] for r in cur.fetchall()]


def cr_copy_source(conn, copy_from, plant, fy):
    """The row to copy (shop/equipment/activity/unit classification) as a
    dict, or None. main /api/capital-repair-row."""
    return _row_dict(conn,
            "SELECT c.shop, c.equipment, c.activity, c.unit_type, pu.unit_code AS unit_name, c.sms_subtag "
            "FROM capital_repair c LEFT JOIN plant_unit pu ON pu.unit_id = c.unit_id "
            "WHERE c.id=%s AND c.plant_code=%s AND c.fy=%s", (copy_from, plant, fy))


def insert_cr_row(cur, values):
    """Insert one row (sort_order 0, renumbered by the caller) on the
    caller's cursor; the caller reads cur.lastrowid and commits.
    main /api/capital-repair-row."""
    (plant, fy, shop, equipment, activity, schedule_days, period, actual,
     unit_type, unit_name, sms_subtag) = values
    _keys.fits("plant", plant, 8, nullable=False)
    _keys.fits("fy", fy, 8, nullable=False)
    for col, val, limit in (("shop", shop, 64), ("equipment", equipment, 64), ("activity", activity, 255),
                            ("schedule_days", schedule_days, 64), ("period", period, 64),
                            ("actual", actual, 128), ("unit_type", unit_type, 16),
                            ("unit_name", unit_name, 32), ("sms_subtag", sms_subtag, 16)):
        _keys.fits(col, val, limit)
    _keys.check_plant_model(plant, "plant", 8)
    if len(fy) > 7:        # v1's VARCHAR(8) kept all of it (a trailing space too)
        raise _keys.OutOfModelError(f"fy {fy!r}: v1's capital_repair_table.fy held 8 characters, "
                                    "the v2 column holds 7")
    _ver.bump(cur)
    _keys.ensure_plant(cur, plant, bump=False)
    unit_id = None if unit_name is None else _keys.exact_unit_id(cur, plant, unit_name, bump=False)
    cur.execute("""
        INSERT INTO capital_repair
            (plant_code, fy, shop, equipment, activity, schedule_days, period, actual,
             unit_type, unit_id, sms_subtag, actual_ongoing, sort_order)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
    """, (plant, fy, shop, equipment, activity, schedule_days, period, actual,
          unit_type, unit_id, sms_subtag))


def cr_row_dict(conn, row_id):
    """The whole row as a dict, or None. main DELETE /api/capital-repair-row."""
    return _row_dict(conn, f"SELECT {_cr_cols(_CR_ALL)} {_CR_FROM} WHERE c.id=%s", (row_id,))


def delete_cr_row(cur, row_id):
    """Delete one row on the caller's cursor; the caller renumbers and
    commits. main DELETE /api/capital-repair-row."""
    _ver.bump(cur)
    cur.execute("DELETE FROM capital_repair WHERE id=%s", (row_id,))
