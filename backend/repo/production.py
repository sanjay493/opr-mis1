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
import report_context
from constants import ALL_PLANTS as PLANTS
from dbengine import connect
from report_context import fold
from repo import version as _ver
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
    cells = _bulk(measure, months)
    if cells is not None:
        mset = set(months)
        pset = None if plants is None else {fold(p) for p in plants}
        iset = None if items is None else {fold(i) for i in items}
        return {(m, plant, item): v
                for (m, fp, fi), (plant, item, v) in cells.items()
                if m in mset and (pset is None or fp in pset) and (iset is None or fi in iset)}
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
        _ver.bump(cur)
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
        _ver.bump(cur)
        cur.execute(sql, params)


# ── report_context bulk load ────────────────────────────────────────────────
# Inside report_context.activate(), reads whose months all fall in the
# context's window are served from one load of every measure's rows for
# that window; anything else runs its SQL as before. The served functions
# reproduce their SQL exactly:
#   - names match as MySQL's utf8mb4_0900_ai_ci does (report_context.fold);
#   - an absent key is "no row", a None value is a row holding NULL;
#   - SUM(month_actual) is MySQL's: NULLs skipped, NULL when nothing is
#     left, else 0.0 + v1 + v2 + ... in the order InnoDB reads the rows
#     (report_month, then plant_name, for every query shape served here:
#     the PRIMARY KEY and idx_prod_item_month both yield that order).

_BULK_SQL = " UNION ALL ".join(
    f"SELECT '{measure}', report_month, plant_name, item_name, month_actual "
    f"FROM {table} WHERE report_month BETWEEN %s AND %s"
    for measure, table in _TABLE.items())


def _bulk_load(first, last):
    """{measure: {(report_month, fold(plant), fold(item)): (plant, item, value)}}
    for every row with first <= report_month <= last, all three measures."""
    out = {measure: {} for measure in _TABLE}
    with rc.cursor() as cur:
        cur.execute(_BULK_SQL, (first, last) * len(_TABLE))
        for r in cur.fetchall():
            out[r[0]][(r[1], fold(r[2]), fold(r[3]))] = (r[2], r[3], r[4])
    return out


def _bulk(measure, months):
    """The active context's cells for `measure` when its window covers
    every month in `months`, else None (the caller runs its SQL)."""
    ctx = report_context.covering(months)
    if ctx is None:
        return None
    return ctx.load("production", _bulk_load)[measure]


def _cells_sum(cells, months, plants, item):
    """MySQL SUM(month_actual) over months x plants for one item, from cells."""
    fi = fold(item)
    fplants = sorted({fold(p) for p in plants})
    total = None
    for m in sorted(set(months)):
        for fp in fplants:
            hit = cells.get((m, fp, fi))
            if hit is not None and hit[2] is not None:
                total = (0.0 if total is None else total) + hit[2]
    return total


def _cells_value(cells, month, plant, item):
    """month_actual of one row (None when absent or NULL)."""
    hit = cells.get((month, fold(plant), fold(item)))
    return None if hit is None else hit[2]


def cell(cur, measure: Measure, month, plant, item):
    """value_row(), served from the active report_context when it covers
    `month`: (month_actual,) when the row exists (month_actual may be
    None), else None. Outside a context it is value_row() on `cur`."""
    _table(measure)
    cells = _bulk(measure, (month,))
    if cells is None:
        return value_row(cur, measure, month, plant, item)
    hit = cells.get((month, fold(plant), fold(item)))
    return None if hit is None else (hit[2],)


def sum_plants_cell(cur, measure: Measure, month, plants, item):
    """sum_plants_row(), served from the active report_context when it
    covers `month`: (SUM,) with SUM None when no non-NULL row matched."""
    _table(measure)
    cells = _bulk(measure, (month,))
    if cells is None:
        return sum_plants_row(cur, measure, month, plants, item)
    return (_cells_sum(cells, (month,), plants, item),)


def sum_months_cell(cur, measure: Measure, plant, item, months):
    """sum_months_row(), served from the active report_context when it
    covers every month: (SUM,) with SUM None when no non-NULL row matched."""
    _table(measure)
    cells = _bulk(measure, months)
    if cells is None:
        return sum_months_row(cur, measure, plant, item, months)
    return (_cells_sum(cells, months, (plant,), item),)


def _fs_alias_sum_cells(cells, month: str, plants: list) -> Optional[float]:
    """_fs_alias_sum from cells (same arithmetic, same order)."""
    regular = [p for p in plants if p not in _FS_ALIAS_PLANTS]
    alias = [p for p in plants if p in _FS_ALIAS_PLANTS]
    total, found = 0.0, False
    if regular:
        s = _cells_sum(cells, (month,), regular, "Finished Steel")
        if s is not None:
            total += s
            found = True
    for p in alias:
        v = _cells_value(cells, month, p, "Finished Steel")
        if v is not None:
            total += v
            found = True
        else:
            v = _cells_value(cells, month, p, "Saleable Steel")
            if v is not None:
                total += v
                found = True
    return total if found else None


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


def _sail_month_cells(cells, month, item, with_conversion):
    """get_sail_production_actual (with_conversion) / _plan from cells."""
    if item == "Finished Steel":
        result = _fs_alias_sum_cells(cells, month, PLANTS)
        conversion = _cells_value(cells, month, "SAIL", "Conversion") if with_conversion else None
        if result is not None or conversion is not None:
            return (result or 0.0) + (conversion or 0.0) if with_conversion else result
        return _cells_value(cells, month, "SAIL", "Finished Steel")
    total = _cells_sum(cells, (month,), PLANTS, item)
    if total is not None:
        return total
    return _cells_value(cells, month, "SAIL", item)


def _sail_ytd_cells(cells, months, item, with_conversion):
    """get_sail_production_ytd_actual (with_conversion) / _plan from cells."""
    if item == "Finished Steel":
        total, found = 0.0, False
        for m in months:
            v = _fs_alias_sum_cells(cells, m, PLANTS)
            c = _cells_value(cells, m, "SAIL", "Conversion") if with_conversion else None
            if v is not None or c is not None:
                total += (v or 0.0) + (c or 0.0) if with_conversion else v
                found = True
        return total if found else None
    total = _cells_sum(cells, months, PLANTS, item)
    if total is not None:
        return total
    return _cells_sum(cells, months, ["SAIL"], item)


def get_sail_production_actual(month: str, item: str) -> Optional[float]:
    """Calculates the sum of actuals across active plants. Falls back to explicit 'SAIL' record if none found."""
    cells = _bulk("actual", (month,))
    if cells is not None:
        return _sail_month_cells(cells, month, item, with_conversion=True)
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
    cells = _bulk("abp", (month,))
    if cells is not None:
        return _sail_month_cells(cells, month, item, with_conversion=False)
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
    cells = _bulk("actual", months)
    if cells is not None:
        return _sail_ytd_cells(cells, months, item, with_conversion=True)
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
    cells = _bulk("abp", months)
    if cells is not None:
        return _sail_ytd_cells(cells, months, item, with_conversion=False)
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
    _ver.bump(conn)
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
    _ver.bump(conn)
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
    cells = _bulk("actual", (report_month,))
    if cells is not None:
        return _cells_value(cells, report_month, plant, item_name)
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
    _ver.bump(cur)
    cur.execute(_UPSERT_ROW_SQL.format(table=_table(measure)), (month, plant, item, value))


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
    _ver.bump(cur)
    cur.execute(
        """INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
           VALUES (%s, 'BSL', %s, %s)
           AS new ON DUPLICATE KEY UPDATE month_actual = new.month_actual""",
        (month, unit, value),
    )


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


def sum_plants_row(cur, measure: Measure, month, plants, item):
    """fetchone() of SUM(month_actual) over `plants` for one month/item."""
    phs = ",".join("%s" for _ in plants)
    cur.execute(
        f"SELECT SUM(month_actual) FROM {_table(measure)} WHERE report_month=%s AND plant_name IN ({phs}) AND item_name=%s",
        [month] + list(plants) + [item],
    )
    return cur.fetchone()


def month_values(cur, measure: Measure, plant, item, months):
    """fetchall() of (report_month, month_actual) for one plant/item over `months`."""
    ph = ",".join("%s" for _ in months)
    cur.execute(
        f"SELECT report_month, month_actual FROM {_table(measure)} "
        f"WHERE plant_name=%s AND item_name=%s AND report_month IN ({ph})",
        (plant, item, *months),
    )
    return cur.fetchall()


# ── page3_highlights.py ─────────────────────────────────────────────────────

def item_month_totals_upto(cur, item_names, plants, month):
    """fetchall() of (item_name, report_month, SUM) over plants, months <= month."""
    ph_items = ",".join(["%s"] * len(item_names))
    ph_plants = ",".join(["%s"] * len(plants))
    cur.execute(f"""
            SELECT item_name, report_month, SUM(month_actual) AS total
            FROM production_table
            WHERE item_name IN ({ph_items}) AND plant_name IN ({ph_plants})
              AND report_month <= %s
            GROUP BY item_name, report_month
        """, list(item_names) + list(plants) + [month])
    return cur.fetchall()


def sail_conversion_totals_upto(cur, month):
    """fetchall() of (report_month, SUM) of SAIL 'Conversion', months <= month."""
    cur.execute("""
            SELECT report_month, SUM(month_actual) AS total
            FROM production_table
            WHERE item_name='Conversion' AND plant_name='SAIL' AND report_month <= %s
            GROUP BY report_month
        """, (month,))
    return cur.fetchall()


def sum_months_row(cur, measure: Measure, plant, item, months):
    """fetchone() of SUM(month_actual) for one plant/item over `months`."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(
        f"SELECT SUM(month_actual) FROM {_table(measure)} "
        f"WHERE plant_name=%s AND item_name=%s AND report_month IN ({ph})",
        (plant, item, *months),
    )
    return cur.fetchone()


def item_plants_range(cur, measure: Measure, item, plants, start, end):
    """fetchall() of (plant_name, report_month, month_actual) for one item,
    `plants`, start <= report_month <= end."""
    phs = ",".join("%s" for _ in plants)
    cur.execute(
        f"SELECT plant_name, report_month, month_actual FROM {_table(measure)} "
        f"WHERE item_name=%s AND plant_name IN ({phs}) "
        f"AND report_month>=%s AND report_month<=%s",
        [item] + list(plants) + [start, end],
    )
    return cur.fetchall()


def item_plant_range(cur, measure: Measure, item, plant, start, end):
    """fetchall() of (report_month, month_actual) for one item/plant,
    start <= report_month <= end."""
    cur.execute(
        f"SELECT report_month, month_actual FROM {_table(measure)} "
        "WHERE item_name=%s AND plant_name=%s "
        "AND report_month>=%s AND report_month<=%s",
        [item, plant, start, end],
    )
    return cur.fetchall()


def item_month_by_plant(cur, item, month, plants):
    """fetchall() of (plant_name, month_actual) actuals for one item/month."""
    phs = ",".join("%s" for _ in plants)
    cur.execute(
        f"SELECT plant_name, month_actual FROM production_table "
        f"WHERE item_name=%s AND report_month=%s AND plant_name IN ({phs})",
        [item, month] + list(plants),
    )
    return cur.fetchall()


def item_all_months_by_plant(cur, item, plants):
    """fetchall() of (report_month, plant_name, month_actual) actuals, all months."""
    phs = ",".join("%s" for _ in plants)
    cur.execute(
        f"SELECT report_month, plant_name, month_actual FROM production_table "
        f"WHERE item_name=%s AND plant_name IN ({phs})",
        [item] + list(plants),
    )
    return cur.fetchall()


# ── page_finished_steel_report.py ───────────────────────────────────────────

def item_alias_rows(cur, aliases, months=None):
    """fetchall() of (report_month, plant_name, item_name, month_actual) for
    any of `aliases`, optionally limited to `months`, ORDER BY report_month."""
    alias_phs = ",".join("%s" for _ in aliases)
    if months is not None:
        month_phs = ",".join("%s" for _ in months)
        cur.execute(f"""
                SELECT report_month, plant_name, item_name, month_actual
                FROM production_table
                WHERE item_name IN ({alias_phs}) AND report_month IN ({month_phs})
                ORDER BY report_month
            """, list(aliases) + list(months))
    else:
        cur.execute(f"""
                SELECT report_month, plant_name, item_name, month_actual
                FROM production_table
                WHERE item_name IN ({alias_phs})
                ORDER BY report_month
            """, list(aliases))
    return cur.fetchall()


def item_alias_report_months(cur, aliases):
    """fetchall() of DISTINCT well-formed report_month for any of `aliases`."""
    alias_phs = ",".join("%s" for _ in aliases)
    cur.execute(f"""
        SELECT DISTINCT report_month FROM production_table
        WHERE item_name IN ({alias_phs})
          AND report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'
    """, list(aliases))
    return cur.fetchall()


# ── page_major_unit_records.py ──────────────────────────────────────────────

def plant_items_monthly_sum_upto(cur, plant, item_names, upto_month):
    """fetchall() of (report_month, SUM) over item_names for a plant, months
    <= upto_month (all months when upto_month is None)."""
    ph = ",".join(["%s"] * len(item_names))
    cur.execute(f"""
        SELECT report_month, SUM(month_actual)
        FROM production_table
        WHERE plant_name = %s AND item_name IN ({ph})
          AND (%s IS NULL OR report_month <= %s)
        GROUP BY report_month
    """, [plant] + list(item_names) + [upto_month, upto_month])
    return cur.fetchall()


# ── page_records.py (record statistics; SQL moved verbatim) ─────────────────

def _records_ph(lst):
    return ','.join(['%s'] * len(lst))


def _fy_pos_expr():
    """report_month's position within its financial year: 0 = April … 11 = March."""
    return ("CASE WHEN CAST(SUBSTR(report_month,6,2) AS SIGNED) >= 4 "
            "THEN CAST(SUBSTR(report_month,6,2) AS SIGNED) - 4 "
            "ELSE CAST(SUBSTR(report_month,6,2) AS SIGNED) + 8 END")


def _fy_expr():
    return ("CASE WHEN CAST(SUBSTR(report_month,6,2) AS SIGNED)>=4 "
            "THEN CAST(SUBSTR(report_month,1,4) AS SIGNED) "
            "ELSE CAST(SUBSTR(report_month,1,4) AS SIGNED)-1 END")


def _q_expr():
    return ("CASE "
            "WHEN CAST(SUBSTR(report_month,6,2) AS SIGNED) IN (4,5,6)    THEN 1 "
            "WHEN CAST(SUBSTR(report_month,6,2) AS SIGNED) IN (7,8,9)    THEN 2 "
            "WHEN CAST(SUBSTR(report_month,6,2) AS SIGNED) IN (10,11,12) THEN 3 "
            "ELSE 4 END")


def _days_expr():
    """Days in report_month's calendar month — used to weight rate items
    (Oven Pushing (nos/day), COB#* battery counts) by days-in-month when
    combining months into a quarter/half/FY/CY, instead of summing an
    already-daily-average figure like it was tonnage."""
    return ("CASE CAST(SUBSTR(report_month,6,2) AS SIGNED) "
            "WHEN 1 THEN 31 WHEN 3 THEN 31 WHEN 5 THEN 31 WHEN 7 THEN 31 "
            "WHEN 8 THEN 31 WHEN 10 THEN 31 WHEN 12 THEN 31 "
            "WHEN 4 THEN 30 WHEN 6 THEN 30 WHEN 9 THEN 30 WHEN 11 THEN 30 "
            "ELSE CASE WHEN CAST(SUBSTR(report_month,1,4) AS SIGNED) %% 4 = 0 "
            "AND (CAST(SUBSTR(report_month,1,4) AS SIGNED) %% 100 != 0 "
            "OR CAST(SUBSTR(report_month,1,4) AS SIGNED) %% 400 = 0) "
            "THEN 29 ELSE 28 END END")


_H_EXPR = ("CASE WHEN CAST(SUBSTR(report_month,6,2) AS SIGNED) BETWEEN 4 AND 9 "
           "THEN 1 ELSE 2 END")

# Period buckets for records_bucket_cells(): [(sql_expr, alias), ...]
_RECORDS_BUCKETS = {
    "quarter": lambda: [(_q_expr(), 'qnum'), (_fy_expr(), 'fy_start')],
    "half":    lambda: [(_H_EXPR, 'hnum'), (_fy_expr(), 'fy_start')],
    "fy":      lambda: [(_fy_expr(), 'fy_start')],
    "cy":      lambda: [('SUBSTR(report_month,1,4)', 'yr')],
}


def records_scope(plants, items=None, upto_month=None):
    """(where, args) selecting `plants` (and `items`, when given; and months
    <= upto_month, when given) for the records queries below. Opaque to
    callers: pass it straight back to them."""
    ph = _records_ph(plants)
    if items is None:
        where = f"plant_name IN ({ph})"
        args = list(plants)
    else:
        where = f"item_name IN ({_records_ph(items)}) AND plant_name IN ({ph})"
        args = list(items) + list(plants)
    if upto_month:
        where += " AND report_month <= %s"
        args = args + [upto_month]
    return where, args


def records_bucket_cells(cur, scope, bucket):
    """fetchall() of (item_name, *bucket columns, plant_name, report_month,
    v, days) per (item, period bucket, plant, month). bucket: 'quarter'
    (qnum, fy_start) | 'half' (hnum, fy_start) | 'fy' (fy_start) | 'cy' (yr)."""
    where, args = scope
    bucket_exprs = _RECORDS_BUCKETS[bucket]()
    sel = ", ".join(f"{e} AS {a}" for e, a in bucket_exprs)
    grp = ", ".join(a for _e, a in bucket_exprs)
    cur.execute(f"""
        SELECT item_name, {sel}, plant_name, report_month,
               SUM(month_actual)   AS v,
               MAX({_days_expr()}) AS days
        FROM production_table
        WHERE {where}
        GROUP BY item_name, {grp}, plant_name, report_month
    """, list(args))
    return cur.fetchall()


def records_calendar_month_totals(cur, scope):
    """fetchall() of (item_name, mon_num, report_month, total), ordered by
    item, month number, total DESC."""
    where, args = scope
    cur.execute(f"""
        SELECT item_name,
               CAST(SUBSTR(report_month,6,2) AS SIGNED) AS mon_num,
               report_month,
               SUM(month_actual) AS total
        FROM production_table
        WHERE {where}
        GROUP BY item_name, report_month
        ORDER BY item_name, mon_num, total DESC
    """, args)
    return cur.fetchall()


def records_latest_month(cur):
    """Latest well-formed report_month in production_table."""
    cur.execute("""
        SELECT MAX(report_month) FROM production_table
        WHERE report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'
    """)
    return cur.fetchone()[0]


def records_plants_items_in(cur, plants):
    """fetchall() of DISTINCT item_name over `plants` (always the IN form)."""
    ph = _records_ph(plants)
    cur.execute(
        f"SELECT DISTINCT item_name FROM production_table WHERE plant_name IN ({ph})",
        list(plants))
    return cur.fetchall()


def records_rows(cur, scope):
    """[(item_name, plant_name, report_month, month_actual)] for every row
    in `scope`, in the order MySQL reads them: the same WHERE as the
    records GROUP BY queries above and no ORDER BY, so the same access
    path. Those queries group one row per (item, period, plant, month), so
    their output is these rows in this order; page_records aggregates them
    in Python (one fetch instead of one GROUP BY per period kind).
    Memoised per scope in the active report_context (the result is shared:
    do not mutate)."""
    where, args = scope

    def fetch():
        cur.execute(f"""
            SELECT item_name, plant_name, report_month, month_actual
            FROM production_table
            WHERE {where}
        """, list(args))
        return [tuple(r) for r in cur.fetchall()]

    ctx = report_context.current()
    if ctx is None:
        return fetch()
    return ctx.memo(("records_rows", where, tuple(args)), fetch)


def records_fy_window_cells(cur, scope, s_pos, e_pos):
    """fetchall() of (item_name, fy_start, plant_name, report_month, v, days)
    for months whose FY position (0 = Apr) is within [s_pos, e_pos]."""
    where, args = scope
    cur.execute(f"""
        SELECT item_name, {_fy_expr()} AS fy_start, plant_name, report_month,
               SUM(month_actual)     AS v,
               MAX({_days_expr()})   AS days
        FROM production_table
        WHERE {where} AND ({_fy_pos_expr()}) BETWEEN %s AND %s
        GROUP BY item_name, fy_start, plant_name, report_month
    """, list(args) + [s_pos, e_pos])
    return cur.fetchall()


# ── page_prod_by_process.py ─────────────────────────────────────────────────

def five_plant_saleable_semis(cur, months, plants):
    """fetchone() of COALESCE(SUM) of 'Saleable Semis' over months x plants."""
    ph_m = ",".join(["%s"] * len(months))
    ph_p = ",".join(["%s"] * len(plants))
    cur.execute(
        f"SELECT COALESCE(SUM(month_actual),0) FROM production_table "
        f"WHERE report_month IN ({ph_m}) AND plant_name IN ({ph_p}) "
        f"AND item_name='Saleable Semis'",
        (*months, *plants),
    )
    return cur.fetchone()


def asp_saleable_finished_by_month(cur, months):
    """fetchall() of (report_month, item_name, month_actual) for ASP's
    Saleable Steel and Finished Steel."""
    ph_m = ",".join(["%s"] * len(months))
    cur.execute(
        f"SELECT report_month, item_name, month_actual FROM production_table "
        f"WHERE report_month IN ({ph_m}) AND plant_name='ASP' "
        f"AND item_name IN ('Saleable Steel','Finished Steel')",
        months,
    )
    return cur.fetchall()


def dsp_bottom_pouring_ingot_sum(cur, months):
    """fetchone() of COALESCE(SUM) of DSP 'Bottom Pouring Ingot' over months."""
    ph_m = ",".join(["%s"] * len(months))
    cur.execute(
        f"SELECT COALESCE(SUM(month_actual),0) FROM production_table "
        f"WHERE report_month IN ({ph_m}) AND plant_name='DSP' AND item_name='Bottom Pouring Ingot'",
        months,
    )
    return cur.fetchone()


# ── page_production_trend.py ────────────────────────────────────────────────

def items_plants_all_months(cur, items, plants):
    """fetchall() of (plant_name, item_name, report_month, month_actual)."""
    phs_items = ",".join("%s" for _ in items)
    phs_plants = ",".join("%s" for _ in plants)
    cur.execute(
        f"SELECT plant_name, item_name, report_month, month_actual FROM production_table "
        f"WHERE item_name IN ({phs_items}) AND plant_name IN ({phs_plants})",
        list(items) + list(plants),
    )
    return cur.fetchall()


def item_plants_all_months(cur, item, plants):
    """fetchall() of (plant_name, report_month, month_actual) for one item."""
    aphs = ",".join("%s" for _ in plants)
    cur.execute(
        f"SELECT plant_name, report_month, month_actual FROM production_table "
        f"WHERE item_name=%s AND plant_name IN ({aphs})",
        [item] + list(plants),
    )
    return cur.fetchall()


def items_plant_all_months(cur, items, plant):
    """fetchall() of (item_name, report_month, month_actual) for one plant."""
    phs_items = ",".join("%s" for _ in items)
    cur.execute(
        f"SELECT item_name, report_month, month_actual FROM production_table "
        f"WHERE item_name IN ({phs_items}) AND plant_name=%s",
        list(items) + [plant],
    )
    return cur.fetchall()


# ── page_sail8_trend_annexure.py ────────────────────────────────────────────

def items_plants_upto(cur, items, plants, month):
    """fetchall() of (plant_name, item_name, report_month, month_actual),
    report_month <= month."""
    ph_i = ",".join("%s" for _ in items)
    ph_p = ",".join("%s" for _ in plants)
    cur.execute(
        f"SELECT plant_name, item_name, report_month, month_actual FROM production_table "
        f"WHERE item_name IN ({ph_i}) AND plant_name IN ({ph_p}) AND report_month <= %s",
        list(items) + list(plants) + [month],
    )
    return cur.fetchall()


def items_sail_upto(cur, items, month):
    """fetchall() of (item_name, report_month, month_actual) for the stored
    SAIL rows, report_month <= month."""
    ph_d = ",".join("%s" for _ in items)
    cur.execute(
        f"SELECT item_name, report_month, month_actual FROM production_table "
        f"WHERE item_name IN ({ph_d}) AND plant_name='SAIL' AND report_month <= %s",
        list(items) + [month],
    )
    return cur.fetchall()


# ── page_secretary_review.py ────────────────────────────────────────────────

def latest_hot_metal_month_row(cur):
    """fetchone() of the latest month with a non-NULL Hot Metal actual."""
    cur.execute("SELECT MAX(report_month) FROM production_table "
                "WHERE item_name='Hot Metal' AND month_actual IS NOT NULL")
    return cur.fetchone()


def mou_items_for_month(cur, month):
    """fetchall() of DISTINCT item_name with a non-NULL MoU value for month."""
    cur.execute("SELECT DISTINCT item_name FROM mou_plan_table "
                "WHERE report_month=%s AND month_actual IS NOT NULL", (month,))
    return cur.fetchall()


# ── page_special_steel_trend.py ─────────────────────────────────────────────

def ssp_saleable_despatch_count_row(cur, months):
    """fetchone() of COUNT(*) of SSP 'Saleable Steel Despatch' rows in months."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
                SELECT COUNT(*) FROM production_table
                WHERE report_month IN ({ph}) AND plant_name='SSP'
                  AND item_name='Saleable Steel Despatch'
            """, (*months,))
    return cur.fetchone()


# ── page_missing_data.py ────────────────────────────────────────────────────

def actual_plants_for_month(report_month):
    """{plant_name} with any production_table row for the month."""
    with rc.cursor() as cur:
        cur.execute("SELECT DISTINCT plant_name FROM production_table WHERE report_month = %s",
                    [report_month])
        return {r[0] for r in cur.fetchall()}


def fs_alias_sum(cur, measure: Measure, month, plants):
    """_fs_alias_sum by measure: SAIL-style Finished Steel sum over `plants`
    for one month (SSP/VISL fall back to Saleable Steel)."""
    return _fs_alias_sum(cur, _table(measure), month, plants)


def sail_conversion_actual(cur, month):
    """SAIL-level 'Conversion' actual for a month (see _sail_conversion_actual)."""
    return _sail_conversion_actual(cur, month)


# ── page_special_steel.py ───────────────────────────────────────────────────

def ytd_sum_row(cur, ytd_months, plant, item):
    """fetchone() of COALESCE(SUM) for one plant/item over ytd_months (actual)."""
    ph = ",".join(["%s"] * len(ytd_months))
    cur.execute(f"""
        SELECT COALESCE(SUM(month_actual),0)
        FROM production_table
        WHERE report_month IN ({ph}) AND plant_name=%s AND item_name=%s
    """, (*ytd_months, plant, item))
    return cur.fetchone()


def ssp_despatch_minus_carbon_000t(cur, months, item="Saleable Steel Despatch"):
    """(SSP `item` total, SSP Finished Carbon Steel Despatch total) over
    months, '000 T (COALESCE'd to 0)."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
        SELECT COALESCE(SUM(month_actual),0) FROM production_table
        WHERE report_month IN ({ph}) AND plant_name='SSP' AND item_name=%s
    """, (*months, item))
    total = (cur.fetchone() or [0])[0]
    cur.execute(f"""
        SELECT COALESCE(SUM(month_actual),0) FROM production_table
        WHERE report_month IN ({ph}) AND plant_name='SSP' AND item_name='Finished Carbon Steel Despatch'
    """, (*months,))
    carbon = (cur.fetchone() or [0])[0]
    return total, carbon


# ── page_special_steel_donut.py ─────────────────────────────────────────────

def sum_count_row(cur, measure: Measure, months, plants, item):
    """fetchone() of (COALESCE(SUM),0), COUNT(*)) over months x plants for item."""
    ph_m = ",".join(["%s"] * len(months))
    ph_p = ",".join(["%s"] * len(plants))
    cur.execute(f"""
            SELECT COALESCE(SUM(month_actual),0), COUNT(*)
            FROM {_table(measure)}
            WHERE report_month IN ({ph_m}) AND plant_name IN ({ph_p}) AND item_name=%s
        """, (*months, *plants, item))
    return cur.fetchone()


def saleable_steel_sum_row(cur, measure: Measure, months, plants):
    """fetchone() of COALESCE(SUM) of 'Saleable Steel' over months x plants."""
    ph_m = ",".join(["%s"] * len(months))
    ph_p = ",".join(["%s"] * len(plants))
    cur.execute(f"""
        SELECT COALESCE(SUM(month_actual),0)
        FROM {_table(measure)}
        WHERE report_month IN ({ph_m}) AND plant_name IN ({ph_p}) AND item_name='Saleable Steel'
    """, (*months, *plants))
    return cur.fetchone()


# ── page_special_steel_physical.py ──────────────────────────────────────────

def plant_item_sum_counts(cur, measure: Measure, plants, items, months):
    """fetchall() of (plant_name, item_name, COALESCE(SUM), COUNT(DISTINCT
    report_month)) over non-NULL rows in plants x items x months."""
    ph_p = ",".join(["%s"] * len(plants))
    ph_i = ",".join(["%s"] * len(items))
    ph_m = ",".join(["%s"] * len(months))
    cur.execute(
        f"SELECT plant_name, item_name, COALESCE(SUM(month_actual), 0), "
        f"       COUNT(DISTINCT report_month) "
        f"FROM {_table(measure)} "
        f"WHERE plant_name IN ({ph_p}) AND item_name IN ({ph_i}) AND report_month IN ({ph_m}) "
        f"  AND month_actual IS NOT NULL "
        f"GROUP BY plant_name, item_name",
        [*plants, *items, *months],
    )
    return cur.fetchall()


def plant_item_rows_from(cur, measure: Measure, plants, items, from_month):
    """fetchall() of (report_month, plant_name, item_name, month_actual), non-NULL,
    report_month >= from_month."""
    ph_p = ",".join(["%s"] * len(plants))
    ph_i = ",".join(["%s"] * len(items))
    cur.execute(
        f"SELECT report_month, plant_name, item_name, month_actual FROM {_table(measure)} "
        f"WHERE plant_name IN ({ph_p}) AND item_name IN ({ph_i}) "
        f"  AND month_actual IS NOT NULL AND report_month >= %s",
        [*plants, *items, from_month],
    )
    return cur.fetchall()


# ── page_techno.py / page_techno_records.py ────────────────────────────────

def plan_hm_cs_by_plant_item(cur, months):
    """fetchall() of (plant_name, item_name, SUM ABP) for Hot Metal and Total
    Crude Steel over months, 5 ISPs."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
        SELECT plant_name, item_name, SUM(month_actual)
        FROM production_plan_table
        WHERE report_month IN ({ph})
          AND item_name IN ('Hot Metal', 'Total Crude Steel')
          AND plant_name IN ('BSP','DSP','RSP','BSL','ISP')
        GROUP BY plant_name, item_name
    """, months)
    return cur.fetchall()


def item_by_plant_month(cur, item, months):
    """fetchall() of (plant_name, report_month, month_actual) actuals for one
    item over months, every plant."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(
        f"SELECT plant_name, report_month, month_actual FROM production_table "
        f"WHERE report_month IN ({ph}) AND item_name=%s",
        list(months) + [item],
    )
    return cur.fetchall()


def items_by_plant_month(cur, items, months):
    """fetchall() of (plant_name, item_name, report_month, month_actual)
    actuals for items over months, every plant."""
    ph_m = ",".join(["%s"] * len(months))
    ph_i = ",".join(["%s"] * len(items))
    cur.execute(
        f"SELECT plant_name, item_name, report_month, month_actual FROM production_table "
        f"WHERE report_month IN ({ph_m}) AND item_name IN ({ph_i})",
        [*months, *items],
    )
    return cur.fetchall()


def hm_cs_signature_row(cur, months):
    """fetchone() of (COUNT(*), SUM) of Hot Metal + Total Crude Steel actuals
    over months (page_techno_records' cache signature)."""
    ph = ",".join(["%s"] * len(months))
    return cur.execute(f"SELECT COUNT(*), SUM(month_actual) FROM production_table "
                       f"WHERE report_month IN ({ph}) AND item_name IN ('Hot Metal','Total Crude Steel')",
                       months).fetchone()


# ── techno_cumulative.py / techno_period.py ────────────────────────────────

def plant_items_month_values(cur, plant, items, months):
    """fetchall() of (report_month, month_actual) actuals for one plant, any
    of `items`, over months (one row per matching item)."""
    ph_m = ",".join(["%s"] * len(months))
    ph_i = ",".join(["%s"] * len(items))
    cur.execute(
        f"SELECT report_month, month_actual FROM production_table "
        f"WHERE plant_name=%s AND item_name IN ({ph_i}) AND report_month IN ({ph_m})",
        [plant, *items, *months])
    return cur.fetchall()


# ── scripts/ (one-off backfills / validators) ──────────────────────────────

def plant_rows_for_months(cur, plant, months):
    """fetchall() of (report_month, item_name, month_actual) actuals for one
    plant over months."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(
        f"SELECT report_month, item_name, month_actual FROM production_table "
        f"WHERE plant_name=%s AND report_month IN ({ph})",
        (plant, *months),
    )
    return cur.fetchall()


def plant_item_months(cur, plant, item_name):
    """fetchall() of (report_month,) actual rows for one plant/item."""
    cur.execute(
        "SELECT report_month FROM production_table WHERE plant_name=%s AND item_name=%s",
        (plant, item_name),
    )
    return cur.fetchall()


def plant_all_rows(cur, measure: Measure, plant):
    """fetchall() of (item_name, report_month, month_actual) for one plant."""
    cur.execute(f"SELECT item_name, report_month, month_actual FROM {_table(measure)} WHERE plant_name=%s",
                (plant,))
    return cur.fetchall()
