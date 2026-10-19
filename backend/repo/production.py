"""Production repository: actual / ABP plan / MoU plan production values.

Tables: production_table (actual), production_plan_table (ABP plan),
mou_plan_table (MoU plan). All three are
(report_month, plant_name, item_name) -> month_actual.

Primitives (the contract later tasks build on):
    values(months, plants, items, measure) -> {(month, plant, item): value}
    upsert(measure, rows)
    delete(measure, month, plant, items=None)

The named functions further down are the queries that used to live inline
in page / api / extractor modules, moved here verbatim.
"""
from typing import Any, Dict, Iterable, List, Literal, Optional

import activity_context
from constants import ALL_PLANTS as PLANTS
from dbengine import connect
from repo import conn as rc
from repo.conn import row_dict as _row_dict

Measure = Literal["actual", "abp", "mou"]

_TABLE = {
    "actual": "production_table",
    "abp": "production_plan_table",
    "mou": "mou_plan_table",
}


def _table(measure):
    try:
        return _TABLE[measure]
    except KeyError:
        raise ValueError(f"unknown production measure {measure!r}") from None


def _in(col, vals):
    return f"{col} IN ({', '.join(['%s'] * len(vals))})"


def values(months: Iterable[str], plants: Iterable[str] | None,
           items: Iterable[str] | None,
           measure: Measure) -> dict[tuple[str, str, str], float | None]:
    """{(report_month, plant_name, item_name): month_actual} for the given
    months, plants and items (None = all plants / all items). A missing key
    means there is no row; a NULL value is a present key with None."""
    table = _table(measure)
    months = list(months)
    plants = None if plants is None else list(plants)
    items = None if items is None else list(items)
    if not months or plants == [] or items == []:
        return {}
    where = [_in("report_month", months)]
    params = list(months)
    if plants is not None:
        where.append(_in("plant_name", plants))
        params += plants
    if items is not None:
        where.append(_in("item_name", items))
        params += items
    with rc.cursor() as cur:
        cur.execute(
            f"SELECT report_month, plant_name, item_name, month_actual FROM {table} "
            f"WHERE {' AND '.join(where)}", params)
        return {(r[0], r[1], r[2]): r[3] for r in cur.fetchall()}


def upsert(measure: Measure, rows: Iterable[tuple]) -> None:
    """Insert or update (report_month, plant_name, item_name, value) rows."""
    table = _table(measure)
    rows = [tuple(r) for r in rows]
    if not rows:
        return
    with rc.tx() as cur:
        cur.executemany(
            f"INSERT INTO {table} (report_month, plant_name, item_name, month_actual) "
            "VALUES (%s, %s, %s, %s) AS new "
            "ON DUPLICATE KEY UPDATE month_actual = new.month_actual", rows)


def delete(measure: Measure, month: str, plant: str, items: Iterable[str] | None = None) -> None:
    """Delete one plant's rows for a month: all items, or only `items`."""
    table = _table(measure)
    params = [month, plant]
    sql = f"DELETE FROM {table} WHERE report_month = %s AND plant_name = %s"
    if items is not None:
        items = list(items)
        if not items:
            return
        sql += f" AND {_in('item_name', items)}"
        params += items
    with rc.tx() as cur:
        cur.execute(sql, params)


# ── SAIL aggregates and single-row saves (moved from db.py) ────────────────

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


# ── Upload-preview lookups (moved from db.py) ──────────────────────────────

def get_production_actual_value(plant: str, item_name: str, report_month: str) -> Optional[float]:
    """Single plant/item/month lookup from production_table (no cross-plant
    aggregation) - used to show 'current DB value' next to a freshly-extracted
    figure during upload preview, so the user can compare before confirming."""
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



# ── Cursor-level helpers ────────────────────────────────────────────────────
# These run on the caller's cursor so they join the caller's transaction and
# return rows in the caller's row type (tuple or Row). Used where a caller
# mixes production SQL with other statements on one connection.

_UPSERT_ROW_SQL = """
    INSERT INTO {table} (report_month, plant_name, item_name, month_actual)
    VALUES (%s, %s, %s, %s)
    AS new ON DUPLICATE KEY UPDATE month_actual = new.month_actual
"""


def upsert_row(cur, measure: Measure, month, plant, item, value) -> None:
    """Insert or update one (month, plant, item) value on `cur`."""
    cur.execute(_UPSERT_ROW_SQL.format(table=_table(measure)), (month, plant, item, value))


def upsert_rows(cur, measure: Measure, rows) -> None:
    """executemany form of upsert_row on `cur` (rows of (month, plant, item, value))."""
    cur.executemany(_UPSERT_ROW_SQL.format(table=_table(measure)), rows)


def delete_row(cur, measure: Measure, month, plant, item) -> None:
    """Delete one (month, plant, item) row on `cur`."""
    cur.execute(f"DELETE FROM {_table(measure)} "
                "WHERE report_month=%s AND plant_name=%s AND item_name=%s",
                (month, plant, item))


def value_row(cur, measure: Measure, month, plant, item):
    """fetchone() of `SELECT month_actual` for one (month, plant, item)."""
    cur.execute(f"SELECT month_actual FROM {_table(measure)} "
                "WHERE report_month=%s AND plant_name=%s AND item_name=%s",
                (month, plant, item))
    return cur.fetchone()


# ── main.py ─────────────────────────────────────────────────────────────────

def month_has_actual_and_plan(cursor, month):
    """(has_actuals, has_plans) for a report month."""
    cursor.execute("SELECT COUNT(*) FROM production_table WHERE report_month = %s", (month,))
    has_actuals = cursor.fetchone()[0] > 0
    cursor.execute("SELECT COUNT(*) FROM production_plan_table WHERE report_month = %s", (month,))
    has_plans = cursor.fetchone()[0] > 0
    return has_actuals, has_plans


def ssp_despatch_basis(cur, month):
    """(Saleable Steel Despatch, Finished Carbon Steel Despatch) for SSP, '000 t."""
    cur.execute("""
        SELECT month_actual FROM production_table
        WHERE report_month=%s AND plant_name='SSP' AND item_name='Saleable Steel Despatch'
    """, (month,))
    row = cur.fetchone()
    saleable_000t = row[0] if row else None

    cur.execute("""
        SELECT month_actual FROM production_table
        WHERE report_month=%s AND plant_name='SSP' AND item_name='Finished Carbon Steel Despatch'
    """, (month,))
    row = cur.fetchone()
    carbon_000t = row[0] if row else None
    return saleable_000t, carbon_000t


def plan_preview_rows(run_extractor):
    """Dry-run a plan extractor and return the production_plan_table rows it
    wrote, as (plant_name, item_name, report_month, month_actual) Rows sorted
    in binary (code point) order.

    The extractors write production_plan_table and commit on their own
    db.connect() connections. Inside repo.conn.rollback_tx() all of those
    connections are this one connection, whose commits are no-ops and which
    is rolled back and closed at the end. A session TEMPORARY TABLE named
    production_plan_table shadows the real table on that connection, so the
    extractor writes into an empty private copy (exactly the rows it
    produced; no locks on the real table) and nothing reaches the real table.

    `run_extractor()` runs the extractor; its exception propagates unchanged.
    """
    import logging
    log = logging.getLogger(__name__)
    with rc.rollback_tx() as cur:
        # (LIKE cannot name the table it shadows, hence the rename.)
        # The ALTER must stay the first statement on this connection: ALTER
        # TABLE commits implicitly, which is harmless only while the shared
        # transaction is still empty (the extractor hasn't written yet).
        cur.execute("CREATE TEMPORARY TABLE _plan_preview LIKE production_plan_table")
        cur.execute("ALTER TABLE _plan_preview RENAME TO production_plan_table")
        try:
            run_extractor()
            cur.execute(
                "SELECT plant_name, item_name, report_month, month_actual "
                "FROM production_plan_table"
            )
            # Sorted in Python: binary (code point) order, as the old preview
            # gave; MySQL's collation would sort case-insensitively.
            return sorted(cur.fetchall(), key=lambda r: (r[0], r[1], r[2]))
        finally:
            # Never let cleanup mask the extractor's own exception.
            try:
                cur.execute("DROP TEMPORARY TABLE IF EXISTS production_plan_table")
            except Exception:  # noqa: BLE001
                log.exception("plan preview: dropping the temporary production_plan_table failed")


def bsl_bf_shop_production_sum(cur, month):
    """SUM of BSL's four furnaces' month production ('000 t) for a month."""
    return cur.execute(
        "SELECT SUM(month_actual) FROM production_table WHERE plant_name='BSL' "
        "AND report_month=%s AND item_name IN ('BF-1','BF-2','BF-4','BF-5')",
        (month,),
    ).fetchone()[0]


def upsert_bsl_furnace_production(cur, month, unit, value):
    cur.execute(
        """INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
           VALUES (%s, 'BSL', %s, %s)
           AS new ON DUPLICATE KEY UPDATE month_actual = new.month_actual""",
        (month, unit, value),
    )


def distinct_actual_items(cursor, plant):
    """fetchall() of DISTINCT item_name in production_table for a plant."""
    cursor.execute(
        "SELECT DISTINCT item_name FROM production_table WHERE plant_name = %s",
        (plant,)
    )
    return cursor.fetchall()


def plant_month_plan_items(cursor, plant, month):
    cursor.execute(
        "SELECT item_name, month_actual FROM production_plan_table WHERE plant_name = %s AND report_month = %s ORDER BY item_name",
        (plant, month),
    )
    return cursor.fetchall()


def plant_month_actual_items(cursor, plant, month):
    cursor.execute(
        "SELECT item_name, month_actual FROM production_table WHERE plant_name = %s AND report_month = %s",
        (plant, month),
    )
    return cursor.fetchall()


def sail_conversion_by_month(cur, months):
    phs = ",".join("%s" for _ in months)
    cur.execute(
        f"SELECT report_month, month_actual FROM production_table "
        f"WHERE plant_name='SAIL' AND item_name='Conversion' AND report_month IN ({phs})",
        months,
    )
    return cur.fetchall()


def production_report_months(cur):
    """fetchall() of DISTINCT well-formed report_months in actual UNION plan."""
    cur.execute("""
        SELECT DISTINCT report_month FROM production_table
        WHERE report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'
        UNION
        SELECT DISTINCT report_month FROM production_plan_table
        WHERE report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'
    """)
    return cur.fetchall()


def fy_rows_excluding_header(cur, measure: Measure, months):
    """(plant_name, item_name, report_month, month_actual) for `months`,
    skipping the stray 'plant_name' header row."""
    phs = ",".join("%s" for _ in months)
    cur.execute(
        f"SELECT plant_name, item_name, report_month, month_actual FROM {_table(measure)} "
        f"WHERE report_month IN ({phs}) AND plant_name != 'plant_name'",
        months,
    )
    return cur.fetchall()


def production_plants_and_months(cur):
    cur.execute("""
        SELECT plant_name, report_month FROM production_table
        WHERE report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'
          AND plant_name != 'plant_name'
        UNION
        SELECT plant_name, report_month FROM production_plan_table
        WHERE report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'
          AND plant_name != 'plant_name'
    """)
    return cur.fetchall()


def distinct_items(cur, measure: Measure, plant):
    """fetchall() of DISTINCT item_name for a plant in the measure's table."""
    cur.execute(
        f"SELECT DISTINCT item_name FROM {_table(measure)} WHERE plant_name = %s",
        (plant,),
    )
    return cur.fetchall()


def rows_for_months_plants(cur, measure: Measure, months, plants):
    """(plant_name, item_name, report_month, month_actual) for months x plants."""
    phs_m = ",".join("%s" for _ in months)
    phs_p = ",".join("%s" for _ in plants)
    cur.execute(
        f"SELECT plant_name, item_name, report_month, month_actual FROM {_table(measure)} "
        f"WHERE report_month IN ({phs_m}) AND plant_name IN ({phs_p})",
        months + plants,
    )
    return cur.fetchall()


def latest_actual_month(cur):
    """fetchone() of MAX(well-formed report_month) in production_table."""
    cur.execute("SELECT MAX(report_month) FROM production_table "
                "WHERE report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'")
    return cur.fetchone()


def plan_hm_by_plant(cur, months):
    """fetchall() of (plant_name, SUM ABP Hot Metal) over months, 5 ISPs."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT plant_name, SUM(month_actual)
            FROM production_plan_table
            WHERE report_month IN ({ph}) AND item_name = 'Hot Metal'
              AND plant_name IN ('BSP','DSP','RSP','BSL','ISP')
            GROUP BY plant_name
        """, months)
    return cur.fetchall()


def plan_crude_steel_by_plant(cur, months):
    """fetchall() of (plant_name, SUM ABP Total Crude Steel) over months, 5 ISPs."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT plant_name, SUM(month_actual)
            FROM production_plan_table
            WHERE report_month IN ({ph}) AND item_name = 'Total Crude Steel'
              AND plant_name IN ('BSP','DSP','RSP','BSL','ISP')
            GROUP BY plant_name
        """, months)
    return cur.fetchall()


def plan_sms_items_by_plant(cur, months):
    """fetchall() of (plant_name, item_name, SUM ABP) for items LIKE '%SMS%'."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT plant_name, item_name, SUM(month_actual)
            FROM production_plan_table
            WHERE report_month IN ({ph})
              AND item_name LIKE '%%SMS%%'
            GROUP BY plant_name, item_name
        """, months)
    return cur.fetchall()


def plan_sms_shop_sum(cur, months, sms_identifier, plant):
    """fetchone() of the ABP SUM for an SMS shop's exact or prefixed items."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
                SELECT SUM(month_actual)
                FROM production_plan_table
                WHERE report_month IN ({ph})
                  AND (item_name = %s OR item_name LIKE %s)
                  AND plant_name = %s
            """, months + [sms_identifier, sms_identifier + " %", plant])
    return cur.fetchone()


def plan_all_sms_sum(cur, months, plant):
    """fetchone() of the ABP SUM of a plant's items LIKE 'SMS%'."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
                        SELECT SUM(month_actual)
                        FROM production_plan_table
                        WHERE report_month IN ({ph})
                          AND item_name LIKE 'SMS%%'
                          AND plant_name = %s
                    """, months + [plant])
    return cur.fetchone()


# ── api_*.py ────────────────────────────────────────────────────────────────

def plant_item_value_row(cur, measure: Measure, plant, item_name, month):
    """fetchone() of month_actual for one plant/item/month (api_production_loss)."""
    return cur.execute(
        f"SELECT month_actual FROM {_table(measure)} WHERE plant_name=%s AND item_name=%s AND report_month=%s",
        (plant, item_name, month),
    ).fetchone()


def actual_history(cur, plant, item_name, start, end):
    """fetchall() of (report_month, month_actual) with start <= month < end."""
    return cur.execute("""SELECT report_month, month_actual FROM production_table
                               WHERE plant_name=%s AND item_name=%s AND report_month>=%s AND report_month<%s""",
                       (plant, item_name, start, end)).fetchall()


def hot_metal_by_plant(cur, report_month, months=None):
    """fetchall() of (plant_name, Hot Metal actual): the month's value, or
    SUM over `months` (YTD) when months is given."""
    if months is not None:
        ph = ",".join(["%s"] * len(months))
        cur.execute(
            f"SELECT plant_name, SUM(month_actual) FROM production_table "
            f"WHERE report_month IN ({ph}) AND item_name='Hot Metal' "
            f"GROUP BY plant_name",
            months,
        )
    else:
        cur.execute(
            "SELECT plant_name, month_actual FROM production_table "
            "WHERE report_month=%s AND item_name='Hot Metal'",
            [report_month],
        )
    return cur.fetchall()
