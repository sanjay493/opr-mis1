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
