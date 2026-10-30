"""Production repository on the v2 schema (production_monthly + item + cal_month).

Same public names, signatures, return shapes and exceptions as
repo/production.py (v1: production_table / production_plan_table /
mou_plan_table, each (report_month, plant_name, item_name) -> month_actual).
v2 holds the three in one production_monthly row per (month, plant, item_id):
actual / abp_plan / mou_plan, each with its has_* flag (repo.v2codec
PRODUCTION_SOURCES). A v1 row of a table is a v2 row whose flag is 1; its
value may be NULL (has_* = 1, value NULL), which stays distinct from "no v1
row" (has_* = 0).

READS
  Every read selects from _SRC[measure], a derived table that gives the v1
  table back under its v1 column names (report_month, plant_name, item_name,
  month_actual), with item_name under utf8mb4_0900_ai_ci, so WHERE / GROUP
  BY / DISTINCT / LIKE on item_name match case variants exactly as v1 did.
  - Row order. v1 queries without ORDER BY returned rows in the order of
    the index MySQL read (PRIMARY (report_month, plant_name, item_name),
    idx_prod_plant_item (plant_name, item_name[, report_month]) or
    idx_prod_item_month (item_name, report_month[, plant_name]); the plan /
    MoU tables only have the PRIMARY KEY). v2 ids are not in that order, so
    every multi-row read here has an explicit ORDER BY that reproduces the
    v1 order, proven by tools/repo_oracle replay.
  - SUM. MySQL's SUM(double) adds in read order. Every SUM here fetches the
    rows in the v1 read order and adds them in Python (_msum: NULLs skipped,
    NULL when nothing is left, else 0.0 + v1 + v2 ...), the same definition
    _cells_sum uses on the report_context bulk data. GROUP BY output keeps
    MySQL's temp-table order: groups in the order their first row is read,
    each group showing its first row's spelling.
  - FY / quarter / half / days come from cal_month, not from SUBSTR().

WRITES (every write bumps data_version first; none in a dry run)
  - upsert of one measure: sets that measure's value and flag, never touches
    the other two measures of the row.
  - Item names (see repo/_keys.py): v1's unique key compared item_name
    under ai_ci, so an upsert of 'CC Billet' onto a (month, plant) whose
    table already held 'CC BILLET' updated that row and kept 'CC BILLET'.
    v2 does the same: if a row of that (month, plant) has the measure's flag
    set for a case variant of the name, that row is updated. Otherwise the
    item is resolved by the EXACT string (created when missing) and that
    (month, plant, item) row gets the measure (inserted, or completed when
    the row already holds other measures).
  - Concurrency: every writer takes the data_version row lock first (the
    bump), and every lookup a write decides on (the case-variant row, the
    item / plant / cal_month master rows) is a locking read (FOR UPDATE /
    FOR SHARE), so it sees the latest committed rows, never an older
    snapshot: two concurrent writes cannot create two ai_ci-equal rows.
  - delete of one measure: clears its flag and sets its value to NULL;
    a row left with no flag is deleted (ck_production_source).
  - Months / plants: a write creates the cal_month / plant master row it
    needs (repo/_keys.py ensure_month / ensure_plant), so every month
    and plant v1 stored is stored; only a month string that is not a
    'YYYY-MM' at all is refused (_keys.check_month). Deletes resolve
    nothing (they match nothing, as in v1).
"""
from typing import Any, Dict, Iterable, List, Literal, Optional

import activity_context
import dbengine
import report_context
from constants import ALL_PLANTS as PLANTS
from dbengine import connect
from report_context import fold
from repo import version as _ver
from repo import conn as rc
from repo.conn import row_dict as _row_dict
from repo import _keys
from repo._mysqlsort import mysql_sort
from repo.v2codec import PRODUCTION_SOURCES

Measure = Literal["actual", "abp", "mou"]

_TABLE = {
    "actual": "production_table",
    "abp": "production_plan_table",
    "mou": "mou_plan_table",
}
# measure -> (value column, has_* flag)
_COLS = {measure: PRODUCTION_SOURCES[table] for measure, table in _TABLE.items()}


def _table(measure):
    try:
        return _TABLE[measure]
    except KeyError:
        raise ValueError(f"unknown production measure {measure!r}") from None


def _cols(measure):
    _table(measure)
    return _COLS[measure]


def _src_sql(col, flag, extra=""):
    return ("(SELECT pm.report_month AS report_month, pm.plant_code AS plant_name, "
            "i.item_name COLLATE utf8mb4_0900_ai_ci AS item_name, "
            f"pm.{col} AS month_actual, pm.item_id AS item_id{extra} "
            "FROM production_monthly pm JOIN item i ON i.item_id = pm.item_id "
            + ("JOIN cal_month cm ON cm.report_month = pm.report_month " if extra else "")
            + f"WHERE pm.{flag} = 1) AS t")


# The v1 table of each measure, under its v1 column names.
_SRC = {measure: _src_sql(*_COLS[measure]) for measure in _TABLE}
# production_table plus the cal_month columns the records queries need.
_REC_SRC = _src_sql(*_COLS["actual"],
                    extra=", cm.fy AS cal_fy, cm.fy_month AS cal_fy_month, cm.quarter AS cal_quarter, "
                          "cm.half AS cal_half, DAY(LAST_DAY(cm.month_start)) AS cal_days")

# v1 read orders (see the module docstring).
_O_MPI = " ORDER BY report_month, plant_name, item_name"     # PRIMARY KEY
_O_PIM = " ORDER BY plant_name, item_name, report_month"     # idx_prod_plant_item
_O_IMP = " ORDER BY item_name, report_month, plant_name"     # idx_prod_item_month


def _src(measure):
    _table(measure)
    return _SRC[measure]


def _in(col, vals):
    return f"{col} IN ({', '.join(['%s'] * len(vals))})"


def _ph(vals):
    return ",".join(["%s"] * len(vals))


def _item_ids(cur, names):
    """item_ids of every item whose name equals one of `names` under ai_ci
    (all case variants), [0] when none does (no item has id 0). Item-first
    reads filter `item_id IN (...)` with these, so idx_production_item_month
    drives them (a COLLATE'd name filter cannot use an index)."""
    names = list(names)
    rows = cur.execute("SELECT item_id FROM item WHERE item_name COLLATE utf8mb4_0900_ai_ci "
                       f"IN ({_ph(names)}) ORDER BY item_id", names).fetchall()
    return [r[0] for r in rows] or [0]


def _iw(cur, names):
    """(\"item_id IN (%s, ...)\", ids) for the item names `names` (see _item_ids)."""
    ids = _item_ids(cur, names)
    return f"item_id IN ({_ph(ids)})", ids


def _fetchall(cur, sql, params=()):
    return cur.execute(sql, list(params)).fetchall()


def _fetchone(cur, sql, params=()):
    return cur.execute(sql, list(params)).fetchone()


def _wants_row(cur) -> bool:
    """True when `cur` returns dbengine.Row rows (repo.conn cursors, and
    db.connect() cursors / connections with row_factory set)."""
    if isinstance(cur, rc.Cursor):
        return True
    if isinstance(cur, dbengine.CursorWrapper):
        return cur._conn.row_factory is not None
    if isinstance(cur, dbengine.ConnWrapper):
        return cur.row_factory is not None
    return False


def _rows_like(cur, keys, rows):
    """Python-built result rows in `cur`'s row type, with v1's column names."""
    if _wants_row(cur):
        keys = list(keys)
        return [dbengine.Row(keys, tuple(r)) for r in rows]
    return [tuple(r) for r in rows]


def _row_like(cur, keys, values):
    return _rows_like(cur, keys, [values])[0]


def _msum(values):
    """MySQL SUM(double) over `values` in order: NULLs skipped, None when
    nothing is left, else 0.0 + v1 + v2 + ..."""
    total = None
    for v in values:
        if v is not None:
            total = (0.0 if total is None else total) + v
    return total


def _coalesce0(total):
    return 0.0 if total is None else total


def _groups(rows, key):
    """MySQL GROUP BY over rows in read order: {folded key: [rows]}, in the
    order each group's first row was read."""
    out = {}
    for r in rows:
        out.setdefault(key(r), []).append(r)
    return out


def _distinct_first(rows, key=lambda r: fold(r[0])):
    """SELECT DISTINCT over rows in read order: the first row of each value
    (ai_ci: case variants are one value, shown with the first spelling)."""
    seen, out = set(), []
    for r in rows:
        k = key(r)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def values(months: Iterable[str], plants: Iterable[str] | None,
           items: Iterable[str] | None,
           measure: Measure) -> dict[tuple[str, str, str], float | None]:
    """{(report_month, plant_name, item_name): month_actual} for the given
    months, plants and items (None = all plants / all items). A missing key
    means there is no row; a NULL value is a present key with None. The
    dict's order is unspecified."""
    src = _src(measure)
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
            f"SELECT report_month, plant_name, item_name, month_actual FROM {src} "
            f"WHERE {' AND '.join(where)}" + _O_MPI, params)
        return {(r[0], r[1], r[2]): r[3] for r in cur.fetchall()}


# ── writes ──────────────────────────────────────────────────────────────────

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


def _put(cur, measure, month, plant, item, value, *, bump=True):
    """Set one measure of (month, plant, item) to `value` (a v1 upsert of one
    row). `bump`: False only when the caller has already bumped on `cur`."""
    col, flag = _cols(measure)
    month = _keys.fit_month(month)      # v1's ON DUPLICATE KEY saw the cut month
    _keys.check_month(month)
    if bump:
        _ver.bump(cur)
    _keys.ensure_month(cur, month, bump=False)
    _keys.ensure_plant(cur, plant, bump=False)
    hit = cur.execute(
        "SELECT pm.item_id FROM production_monthly pm JOIN item i ON i.item_id = pm.item_id "
        f"WHERE pm.report_month = %s AND pm.plant_code = %s AND pm.{flag} = 1 "
        "AND i.item_name COLLATE utf8mb4_0900_ai_ci = %s LIMIT 1 FOR UPDATE OF pm",
        (month, plant, item)).fetchone()
    if hit is not None:
        cur.execute(f"UPDATE production_monthly SET {col} = %s "
                    "WHERE report_month = %s AND plant_code = %s AND item_id = %s",
                    (value, month, plant, hit[0]))
        return
    item_id = _item_id_for_write(cur, item, bump=False)
    cur.execute(
        f"INSERT INTO production_monthly (report_month, plant_code, item_id, {col}, {flag}) "
        "VALUES (%s, %s, %s, %s, 1) AS new "
        f"ON DUPLICATE KEY UPDATE {col} = new.{col}, {flag} = 1",
        (month, plant, item_id, value))


def _clear(cur, measure, month, plant, items=None, *, bump=True):
    """Remove one measure from (month, plant[, items]) rows (a v1 DELETE):
    rows holding only that measure are deleted, the others lose its flag
    and value. Items match under ai_ci, as v1's DELETE did."""
    col, flag = _cols(measure)
    others = [f for f in ("has_actual", "has_abp", "has_mou") if f != flag]
    params = [month, plant]
    item_sql = ""
    if items is not None:
        item_sql = " AND " + _in("i.item_name COLLATE utf8mb4_0900_ai_ci", items)
        params += list(items)
    if bump:
        _ver.bump(cur)
    cur.execute(
        "DELETE pm FROM production_monthly pm JOIN item i ON i.item_id = pm.item_id "
        f"WHERE pm.report_month = %s AND pm.plant_code = %s AND pm.{flag} = 1 "
        f"AND pm.{others[0]} = 0 AND pm.{others[1]} = 0{item_sql}", params)
    cur.execute(
        "UPDATE production_monthly pm JOIN item i ON i.item_id = pm.item_id "
        f"SET pm.{col} = NULL, pm.{flag} = 0 "
        f"WHERE pm.report_month = %s AND pm.plant_code = %s AND pm.{flag} = 1{item_sql}", params)


def upsert(measure: Measure, rows: Iterable[tuple]) -> None:
    """Insert or update (report_month, plant_name, item_name, value) rows."""
    _table(measure)
    rows = [tuple(r) for r in rows]
    if not rows:
        return
    with rc.tx() as cur:
        for r in rows:
            _keys.check_month(r[0])
        # one bump for the batch (as v1's executemany), taken by the first row
        for i, (month, plant, item, value) in enumerate(rows):
            _put(cur, measure, month, plant, item, value, bump=i == 0)


def delete(measure: Measure, month: str, plant: str, items: Iterable[str] | None = None) -> None:
    """Delete one plant's rows for a month: all items, or only `items`."""
    _table(measure)
    if items is not None:
        items = list(items)
        if not items:
            return
    with rc.tx() as cur:
        _clear(cur, measure, month, plant, items)


# ── report_context bulk load ────────────────────────────────────────────────
# Inside report_context.activate(), reads whose months all fall in the
# context's window are served from one load of every measure's rows for
# that window; anything else runs its SQL. Same contract as v1's (see
# repo/production.py): names match as ai_ci does (fold), an absent key is
# "no row", a None value a row holding NULL, sums are _cells_sum's.

_BULK_SQL = ("SELECT pm.report_month, pm.plant_code, i.item_name, pm.actual, pm.abp_plan, pm.mou_plan, "
             "pm.has_actual, pm.has_abp, pm.has_mou "
             "FROM production_monthly pm JOIN item i ON i.item_id = pm.item_id "
             "WHERE pm.report_month BETWEEN %s AND %s")


def _bulk_load(first, last):
    """{measure: {(report_month, fold(plant), fold(item)): (plant, item, value)}}
    for every row with first <= report_month <= last, all three measures."""
    out = {measure: {} for measure in _TABLE}
    actual, abp, mou = out["actual"], out["abp"], out["mou"]
    with rc.cursor() as cur:
        cur.execute(_BULK_SQL, (first, last))
        for m, p, i, a, b, u, ha, hb, hu in cur.fetchall():
            key = (m, fold(p), fold(i))
            if ha:
                actual[key] = (p, i, a)
            if hb:
                abp[key] = (p, i, b)
            if hu:
                mou[key] = (p, i, u)
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
    return _msum(hit[2] for hit in (cells.get((m, fp, fi)) for m in sorted(set(months)) for fp in fplants)
                 if hit is not None)


def _cells_value(cells, month, plant, item):
    """month_actual of one row (None when absent or NULL)."""
    hit = cells.get((month, fold(plant), fold(item)))
    return None if hit is None else hit[2]


def cell(cur, measure: Measure, month, plant, item):
    """value_row(), served from the active report_context when it covers
    `month`: (month_actual,) when the row exists (month_actual may be
    None), else None. Outside a context it is value_row() on `cur`.

    Read-only helper. Inside a context it ignores `cur` and reads the
    committed snapshot the context loaded (never `cur`'s own uncommitted
    writes); a repo write switches the context off for the rest of the
    request, after which it reads on `cur` again."""
    _table(measure)
    cells = _bulk(measure, (month,))
    if cells is None:
        return value_row(cur, measure, month, plant, item)
    hit = cells.get((month, fold(plant), fold(item)))
    return None if hit is None else (hit[2],)


def sum_plants_cell(cur, measure: Measure, month, plants, item):
    """sum_plants_row(), served from the active report_context when it
    covers `month`: (SUM,) with SUM None when no non-NULL row matched.

    Read-only helper; see cell()."""
    _table(measure)
    cells = _bulk(measure, (month,))
    if cells is None:
        return sum_plants_row(cur, measure, month, plants, item)
    return (_cells_sum(cells, (month,), plants, item),)


def sum_months_cell(cur, measure: Measure, plant, item, months):
    """sum_months_row(), served from the active report_context when it
    covers every month: (SUM,) with SUM None when no non-NULL row matched.

    Read-only helper; see cell()."""
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


# ── SQL building blocks shared by the SQL fall-throughs ─────────────────────

def _values_sql(cur, measure, where, params, order):
    """month_actual of every row of `measure` matching `where`, in `order`."""
    return [r[0] for r in _fetchall(
        cur, f"SELECT month_actual FROM {_src(measure)} WHERE {where}{order}", params)]


def _sum_sql(cur, measure, where, params, order):
    return _msum(_values_sql(cur, measure, where, params, order))


def _value_or_none(cur, measure, month, plant, item):
    """fetchone() of SELECT month_actual for one row: (v,) or None."""
    return _fetchone(cur, f"SELECT month_actual FROM {_src(measure)} "
                          "WHERE report_month=%s AND plant_name=%s AND item_name=%s",
                     (month, plant, item))


# ── SAIL aggregates and single-row saves ───────────────────────────────────

# For SSP and VISL, Finished Steel = Saleable Steel (same data, no separate BF/SMS).
_FS_ALIAS_PLANTS = ('SSP', 'VISL')


def _fs_alias_sum(cursor, measure, month: str, plants: list) -> Optional[float]:
    """Sum 'Finished Steel' across plants with SSP/VISL fallback to
    'Saleable Steel' (v1's _fs_alias_sum, by measure instead of table)."""
    regular = [p for p in plants if p not in _FS_ALIAS_PLANTS]
    alias = [p for p in plants if p in _FS_ALIAS_PLANTS]

    total, found = 0.0, False

    if regular:
        s = _sum_sql(cursor, measure,
                     f"report_month=%s AND plant_name IN ({_ph(regular)}) AND item_name='Finished Steel'",
                     [month] + regular, " ORDER BY plant_name")
        if s is not None:
            total += s
            found = True

    for p in alias:
        r = _value_or_none(cursor, measure, month, p, "Finished Steel")
        if r and r[0] is not None:
            total += r[0]
            found = True
        else:
            r = _value_or_none(cursor, measure, month, p, "Saleable Steel")
            if r and r[0] is not None:
                total += r[0]
                found = True

    return total if found else None


def _sail_conversion_actual(cursor, month: str) -> Optional[float]:
    """SAIL-level 'Conversion' actual for a month (plant 'SAIL')."""
    row = _value_or_none(cursor, "actual", month, "SAIL", "Conversion")
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


def _sail_month_sql(measure, month, item, with_conversion):
    conn = connect()
    try:
        cursor = conn.cursor()
        if item == "Finished Steel":
            result = _fs_alias_sum(cursor, measure, month, PLANTS)
            conversion = _sail_conversion_actual(cursor, month) if with_conversion else None
            if result is not None or conversion is not None:
                return (result or 0.0) + (conversion or 0.0) if with_conversion else result
            row = _value_or_none(cursor, measure, month, "SAIL", "Finished Steel")
            return row[0] if row else None
        total = _sum_sql(cursor, measure,
                         f"report_month = %s AND plant_name IN ({_ph(PLANTS)}) AND item_name = %s",
                         [month] + PLANTS + [item], " ORDER BY plant_name")
        if total is not None:
            return total
        row = _value_or_none(cursor, measure, month, "SAIL", item)
        return row[0] if row else None
    finally:
        conn.close()


def _sail_ytd_sql(measure, months, item, with_conversion):
    conn = connect()
    try:
        cursor = conn.cursor()
        if item == "Finished Steel":
            total, found = 0.0, False
            for m in months:
                v = _fs_alias_sum(cursor, measure, m, PLANTS)
                c = _sail_conversion_actual(cursor, m) if with_conversion else None
                if v is not None or c is not None:
                    total += (v or 0.0) + (c or 0.0) if with_conversion else v
                    found = True
            return total if found else None
        total = _sum_sql(cursor, measure,
                         f"report_month IN ({_ph(months)}) AND plant_name IN ({_ph(PLANTS)}) "
                         "AND item_name = %s",
                         list(months) + PLANTS + [item], " ORDER BY report_month, plant_name")
        if total is not None:
            return total
        return _sum_sql(cursor, measure,
                        f"report_month IN ({_ph(months)}) AND plant_name = 'SAIL' AND item_name = %s",
                        list(months) + [item], " ORDER BY report_month")
    finally:
        conn.close()


def get_sail_production_actual(month: str, item: str) -> Optional[float]:
    """Calculates the sum of actuals across active plants. Falls back to explicit 'SAIL' record if none found."""
    cells = _bulk("actual", (month,))
    if cells is not None:
        return _sail_month_cells(cells, month, item, with_conversion=True)
    return _sail_month_sql("actual", month, item, with_conversion=True)


def get_sail_production_plan(month: str, item: str) -> Optional[float]:
    """Calculates the sum of plans across active plants. Falls back to explicit 'SAIL' record if none found."""
    cells = _bulk("abp", (month,))
    if cells is not None:
        return _sail_month_cells(cells, month, item, with_conversion=False)
    return _sail_month_sql("abp", month, item, with_conversion=False)


def get_sail_production_ytd_actual(months: List[str], item: str) -> Optional[float]:
    """Sums the actuals across active plants over a list of months (YTD). Falls back to 'SAIL' if no plant records exist."""
    if not months:
        return None
    cells = _bulk("actual", months)
    if cells is not None:
        return _sail_ytd_cells(cells, months, item, with_conversion=True)
    return _sail_ytd_sql("actual", months, item, with_conversion=True)


def get_sail_production_ytd_plan(months: List[str], item: str) -> Optional[float]:
    """Sums the plans across active plants over a list of months (YTD). Falls back to 'SAIL' if no plant records exist."""
    if not months:
        return None
    cells = _bulk("abp", months)
    if cells is not None:
        return _sail_ytd_cells(cells, months, item, with_conversion=False)
    return _sail_ytd_sql("abp", months, item, with_conversion=False)


def _old_row(conn, measure, month, plant, item):
    """The v1 `SELECT *` row of (month, plant, item) as a dict, or None."""
    return _row_dict(conn,
                     f"SELECT report_month, plant_name, item_name, month_actual FROM {_src(measure)} "
                     "WHERE report_month=%s AND plant_name=%s AND item_name=%s",
                     (month, plant, item))


def _save_one(measure, month, plant, item, value):
    item = item.strip()
    conn = connect()
    try:
        old = _old_row(conn, measure, month, plant, item)
        cursor = conn.cursor()
        if value is None:
            _clear(cursor, measure, month, plant, [item])
        else:
            _put(cursor, measure, month, plant, item, value)
        conn.commit()
    finally:
        conn.close()
    new = None if value is None else {"report_month": month, "plant_name": plant, "item_name": item, "month_actual": value}
    activity_context.record(f"{_TABLE[measure]}/{plant}/{item}/{month}", old, new)


def save_production_actual(month: str, plant: str, item: str, value: Optional[float]):
    """Saves or updates an actual production record."""
    _save_one("actual", month, plant, item, value)


def save_production_plan(month: str, plant: str, item: str, value: Optional[float]):
    """Saves or updates a planned production record."""
    _save_one("abp", month, plant, item, value)


# ── Upload-preview lookups ─────────────────────────────────────────────────

def get_production_actual_value(plant: str, item_name: str, report_month: str) -> Optional[float]:
    """Single plant/item/month lookup (no cross-plant aggregation), for the
    upload preview's 'current DB value'."""
    cells = _bulk("actual", (report_month,))
    if cells is not None:
        return _cells_value(cells, report_month, plant, item_name)
    conn = connect()
    try:
        row = _value_or_none(conn.cursor(), "actual", report_month, plant, item_name)
    finally:
        conn.close()
    return row[0] if row and row[0] is not None else None


def get_production_actual_for_months(plant: str, item_name: str, months: List[str]) -> Dict[str, float]:
    """-> {report_month: month_actual} for one plant/item across an explicit
    list of report_months (only months with a saved non-NULL row)."""
    if not months:
        return {}
    conn = connect()
    try:
        rows = _fetchall(conn.cursor(),
                         f"SELECT report_month, month_actual FROM {_src('actual')} "
                         f"WHERE plant_name = %s AND item_name = %s AND report_month IN ({_ph(months)})"
                         " ORDER BY report_month",
                         [plant, item_name] + list(months))
    finally:
        conn.close()
    return {rm: v for rm, v in rows if v is not None}


def enrich_rows_with_db_production(rows: List[Dict[str, Any]], plant: str, report_month: str) -> List[Dict[str, Any]]:
    """Attach 'db_value' (current actual, or None) to each preview row
    in-place, keyed by (the row's own report_month, item_name); see v1."""
    if not rows:
        return rows
    months = {r.get("report_month") or report_month for r in rows}
    conn = connect()
    try:
        fetched = _fetchall(conn.cursor(),
                            f"SELECT report_month, item_name, month_actual FROM {_src('actual')} "
                            f"WHERE plant_name=%s AND report_month IN ({_ph(months)})" + _O_MPI,
                            (plant, *months))
    finally:
        conn.close()
    current = {(rm, item): val for rm, item, val in fetched}
    for r in rows:
        item = r.get("item_name") or r.get("pdf_label")
        rm = r.get("report_month") or report_month
        r["db_value"] = current.get((rm, item)) if item else None
    return rows


# ── Cursor-level helpers ────────────────────────────────────────────────────

def upsert_row(cur, measure: Measure, month, plant, item, value) -> None:
    """Insert or update one (month, plant, item) value on `cur`."""
    _put(cur, measure, month, plant, item, value)


def value_row(cur, measure: Measure, month, plant, item):
    """fetchone() of `SELECT month_actual` for one (month, plant, item)."""
    return _value_or_none(cur, measure, month, plant, item)


# ── main.py ─────────────────────────────────────────────────────────────────

def month_has_actual_and_plan(cursor, month):
    """(has_actuals, has_plans) for a report month."""
    row = _fetchone(cursor, "SELECT COALESCE(MAX(has_actual), 0), COALESCE(MAX(has_abp), 0) "
                            "FROM production_monthly WHERE report_month = %s", (month,))
    return row[0] > 0, row[1] > 0


def ssp_despatch_basis(cur, month):
    """(Saleable Steel Despatch, Finished Carbon Steel Despatch) for SSP, '000 t."""
    row = _value_or_none(cur, "actual", month, "SSP", "Saleable Steel Despatch")
    saleable_000t = row[0] if row else None
    row = _value_or_none(cur, "actual", month, "SSP", "Finished Carbon Steel Despatch")
    carbon_000t = row[0] if row else None
    return saleable_000t, carbon_000t


_PREVIEW_SQL = ("SELECT pm.plant_code AS plant_name, i.item_name, pm.report_month, pm.abp_plan AS month_actual "
                "FROM production_monthly pm JOIN item i ON i.item_id = pm.item_id WHERE pm.has_abp = 1")


def plan_preview_rows(run_extractor):
    """Dry-run a plan extractor and return the ABP plan rows it wrote, as
    (plant_name, item_name, report_month, month_actual) Rows sorted in
    binary (code point) order.

    The extractors write through upsert_row and commit on their own
    db.connect() connections. Inside repo.conn.rollback_tx() all of those
    connections are this one connection, whose commits are no-ops and which
    is rolled back and closed at the end. A session TEMPORARY TABLE named
    production_monthly shadows the real table on that connection, so the
    extractor writes into an empty private copy (exactly the rows it
    produced; no locks on the real table) and nothing reaches it. New item
    names go into the real item master inside the same rolled-back
    transaction, so they never persist either.

    `run_extractor()` runs the extractor; its exception propagates unchanged.
    """
    import logging
    log = logging.getLogger(__name__)
    with rc.rollback_tx() as cur:
        # The ALTER must stay the first statement on this connection: ALTER
        # TABLE commits implicitly, which is harmless only while the shared
        # transaction is still empty (the extractor hasn't written yet).
        cur.execute("CREATE TEMPORARY TABLE _plan_preview LIKE production_monthly")
        cur.execute("ALTER TABLE _plan_preview RENAME TO production_monthly")
        try:
            run_extractor()
            cur.execute(_PREVIEW_SQL)
            return sorted(cur.fetchall(), key=lambda r: (r[0], r[1], r[2]))
        finally:
            try:
                cur.execute("DROP TEMPORARY TABLE IF EXISTS production_monthly")
            except Exception:  # noqa: BLE001
                log.exception("plan preview: dropping the temporary production_monthly failed")


def bsl_bf_shop_production_sum(cur, month):
    """SUM of BSL's four furnaces' month production ('000 t) for a month."""
    return _sum_sql(cur, "actual",
                    "plant_name='BSL' AND report_month=%s AND item_name IN ('BF-1','BF-2','BF-4','BF-5')",
                    (month,), " ORDER BY item_name")


def upsert_bsl_furnace_production(cur, month, unit, value):
    _put(cur, "actual", month, "BSL", unit, value)


def plant_month_plan_items(cursor, plant, month):
    return _fetchall(cursor,
                     f"SELECT item_name, month_actual FROM {_src('abp')} "
                     "WHERE plant_name = %s AND report_month = %s ORDER BY item_name",
                     (plant, month))


def plant_month_actual_items(cursor, plant, month):
    return _fetchall(cursor,
                     f"SELECT item_name, month_actual FROM {_src('actual')} "
                     "WHERE plant_name = %s AND report_month = %s ORDER BY item_name",
                     (plant, month))


def sail_conversion_by_month(cur, months):
    return _fetchall(cur,
                     f"SELECT report_month, month_actual FROM {_src('actual')} "
                     f"WHERE plant_name='SAIL' AND item_name='Conversion' AND report_month IN ({_ph(months)})"
                     " ORDER BY report_month",
                     months)


def production_report_months(cur):
    """fetchall() of DISTINCT report_months in actual UNION plan: the actual
    months in order, then the plan-only months in order (v1's UNION)."""
    rows = _fetchall(cur, "SELECT report_month, MAX(has_actual) AS a, MAX(has_abp) AS b "
                          "FROM production_monthly GROUP BY report_month ORDER BY report_month")
    out = [(r[0],) for r in rows if r[1]] + [(r[0],) for r in rows if r[2] and not r[1]]
    return _rows_like(cur, ["report_month"], out)


def fy_rows_excluding_header(cur, measure: Measure, months):
    """(plant_name, item_name, report_month, month_actual) for `months`,
    skipping the stray 'plant_name' header row."""
    return _fetchall(cur,
                     f"SELECT plant_name, item_name, report_month, month_actual FROM {_src(measure)} "
                     f"WHERE report_month IN ({_ph(months)}) AND plant_name != 'plant_name'" + _O_MPI,
                     months)


def production_plants_and_months(cur):
    """DISTINCT (plant_name, report_month) of actual UNION plan: the actual
    pairs in v1's read order, then the plan-only pairs."""
    seen, out = set(), []
    for measure, order in (("actual", _O_IMP), ("abp", _O_MPI)):
        for r in _fetchall(cur, f"SELECT plant_name, report_month FROM {_src(measure)} "
                                "WHERE plant_name != 'plant_name'" + order):
            k = (fold(r[0]), r[1])
            if k not in seen:
                seen.add(k)
                out.append((r[0], r[1]))
    return _rows_like(cur, ["plant_name", "report_month"], out)


def distinct_items(cur, measure: Measure, plant):
    """fetchall() of DISTINCT item_name for a plant in the measure's table."""
    order = _O_PIM if measure == "actual" else _O_MPI
    rows = _fetchall(cur, f"SELECT item_name FROM {_src(measure)} WHERE plant_name = %s" + order, (plant,))
    return _distinct_first(rows)


def rows_for_months_plants(cur, measure: Measure, months, plants):
    """(plant_name, item_name, report_month, month_actual) for months x plants."""
    return _fetchall(cur,
                     f"SELECT plant_name, item_name, report_month, month_actual FROM {_src(measure)} "
                     f"WHERE report_month IN ({_ph(months)}) AND plant_name IN ({_ph(plants)})" + _O_MPI,
                     list(months) + list(plants))


def latest_actual_month(cur):
    """fetchone() of MAX(report_month) of the actuals."""
    return _fetchone(cur, "SELECT MAX(report_month) FROM production_monthly WHERE has_actual = 1")


def _sum_by_plant(cur, measure, months, item):
    iw, ids = _iw(cur, [item])
    rows = _fetchall(cur,
                     f"SELECT plant_name, month_actual FROM {_src(measure)} "
                     f"WHERE report_month IN ({_ph(months)}) AND {iw} "
                     "AND plant_name IN ('BSP','DSP','RSP','BSL','ISP')" + _O_MPI,
                     list(months) + ids)
    groups = _groups(rows, lambda r: fold(r[0]))
    return _rows_like(cur, ["plant_name", "SUM(month_actual)"],
                      [(g[0][0], _msum(r[1] for r in g)) for g in groups.values()])


def plan_hm_by_plant(cur, months):
    """fetchall() of (plant_name, SUM ABP Hot Metal) over months, 5 ISPs."""
    return _sum_by_plant(cur, "abp", months, "Hot Metal")


def plan_crude_steel_by_plant(cur, months):
    """fetchall() of (plant_name, SUM ABP Total Crude Steel) over months, 5 ISPs."""
    return _sum_by_plant(cur, "abp", months, "Total Crude Steel")


def plan_sms_items_by_plant(cur, months):
    """fetchall() of (plant_name, item_name, SUM ABP) for items LIKE '%SMS%'."""
    rows = _fetchall(cur,
                     f"SELECT plant_name, item_name, month_actual FROM {_src('abp')} "
                     f"WHERE report_month IN ({_ph(months)}) AND item_name LIKE '%%SMS%%'" + _O_MPI,
                     months)
    groups = _groups(rows, lambda r: (fold(r[0]), fold(r[1])))
    return _rows_like(cur, ["plant_name", "item_name", "SUM(month_actual)"],
                      [(g[0][0], g[0][1], _msum(r[2] for r in g)) for g in groups.values()])


def plan_sms_shop_sum(cur, months, sms_identifier, plant):
    """fetchone() of the ABP SUM for an SMS shop's exact or prefixed items."""
    total = _sum_sql(cur, "abp",
                     f"report_month IN ({_ph(months)}) AND (item_name = %s OR item_name LIKE %s) "
                     "AND plant_name = %s",
                     list(months) + [sms_identifier, sms_identifier + " %", plant], _O_MPI)
    return _row_like(cur, ["SUM(month_actual)"], (total,))


def plan_all_sms_sum(cur, months, plant):
    """fetchone() of the ABP SUM of a plant's items LIKE 'SMS%'."""
    total = _sum_sql(cur, "abp",
                     f"report_month IN ({_ph(months)}) AND item_name LIKE 'SMS%%' AND plant_name = %s",
                     list(months) + [plant], _O_MPI)
    return _row_like(cur, ["SUM(month_actual)"], (total,))


# ── api_*.py ────────────────────────────────────────────────────────────────

def plant_item_value_row(cur, measure: Measure, plant, item_name, month):
    """fetchone() of month_actual for one plant/item/month (api_production_loss)."""
    return _value_or_none(cur, measure, month, plant, item_name)


def actual_history(cur, plant, item_name, start, end):
    """fetchall() of (report_month, month_actual) with start <= month < end."""
    iw, ids = _iw(cur, [item_name])
    return _fetchall(cur,
                     f"SELECT report_month, month_actual FROM {_src('actual')} "
                     f"WHERE plant_name=%s AND {iw} AND report_month>=%s AND report_month<%s"
                     " ORDER BY report_month",
                     (plant, *ids, start, end))


def hot_metal_by_plant(cur, report_month, months=None):
    """fetchall() of (plant_name, Hot Metal actual): the month's value, or
    SUM over `months` (YTD) when months is given."""
    iw, ids = _iw(cur, ["Hot Metal"])
    if months is not None:
        rows = _fetchall(cur,
                         f"SELECT plant_name, month_actual FROM {_src('actual')} "
                         f"WHERE report_month IN ({_ph(months)}) AND {iw}"
                         " ORDER BY report_month, plant_name",
                         list(months) + ids)
        groups = _groups(rows, lambda r: fold(r[0]))
        return _rows_like(cur, ["plant_name", "SUM(month_actual)"],
                          [(g[0][0], _msum(r[1] for r in g)) for g in groups.values()])
    return _fetchall(cur,
                     f"SELECT plant_name, month_actual FROM {_src('actual')} "
                     f"WHERE report_month=%s AND {iw} ORDER BY plant_name",
                     [report_month] + ids)


def sum_plants_row(cur, measure: Measure, month, plants, item):
    """fetchone() of SUM(month_actual) over `plants` for one month/item."""
    total = _sum_sql(cur, measure,
                     f"report_month=%s AND plant_name IN ({_ph(plants)}) AND item_name=%s",
                     [month] + list(plants) + [item], " ORDER BY plant_name")
    return _row_like(cur, ["SUM(month_actual)"], (total,))


def month_values(cur, measure: Measure, plant, item, months):
    """fetchall() of (report_month, month_actual) for one plant/item over `months`."""
    iw, ids = _iw(cur, [item])
    return _fetchall(cur,
                     f"SELECT report_month, month_actual FROM {_src(measure)} "
                     f"WHERE plant_name=%s AND {iw} AND report_month IN ({_ph(months)})"
                     " ORDER BY report_month",
                     (plant, *ids, *months))


# ── page3_highlights.py ─────────────────────────────────────────────────────

def item_month_totals_upto(cur, item_names, plants, month):
    """fetchall() of (item_name, report_month, SUM) over plants, months <= month."""
    iw, ids = _iw(cur, item_names)
    rows = _fetchall(cur,
                     f"SELECT item_name, report_month, month_actual FROM {_src('actual')} "
                     f"WHERE {iw} AND plant_name IN ({_ph(plants)}) "
                     "AND report_month <= %s" + _O_MPI,
                     ids + list(plants) + [month])
    groups = _groups(rows, lambda r: (fold(r[0]), r[1]))
    return _rows_like(cur, ["item_name", "report_month", "total"],
                      [(g[0][0], g[0][1], _msum(r[2] for r in g)) for g in groups.values()])


def sail_conversion_totals_upto(cur, month):
    """fetchall() of (report_month, SUM) of SAIL 'Conversion', months <= month."""
    iw, ids = _iw(cur, ["Conversion"])
    rows = _fetchall(cur,
                     f"SELECT report_month, month_actual FROM {_src('actual')} "
                     f"WHERE {iw} AND plant_name='SAIL' AND report_month <= %s"
                     " ORDER BY report_month",
                     (*ids, month))
    return _rows_like(cur, ["report_month", "total"], [(r[0], _msum([r[1]])) for r in rows])


def sum_months_row(cur, measure: Measure, plant, item, months):
    """fetchone() of SUM(month_actual) for one plant/item over `months`."""
    iw, ids = _iw(cur, [item])
    total = _sum_sql(cur, measure,
                     f"plant_name=%s AND {iw} AND report_month IN ({_ph(months)})",
                     (plant, *ids, *months), " ORDER BY report_month")
    return _row_like(cur, ["SUM(month_actual)"], (total,))


def item_plants_range(cur, measure: Measure, item, plants, start, end):
    """fetchall() of (plant_name, report_month, month_actual) for one item,
    `plants`, start <= report_month <= end."""
    iw, ids = _iw(cur, [item])
    return _fetchall(cur,
                     f"SELECT plant_name, report_month, month_actual FROM {_src(measure)} "
                     f"WHERE {iw} AND plant_name IN ({_ph(plants)}) "
                     "AND report_month>=%s AND report_month<=%s ORDER BY report_month, plant_name",
                     ids + list(plants) + [start, end])


def item_plant_range(cur, measure: Measure, item, plant, start, end):
    """fetchall() of (report_month, month_actual) for one item/plant,
    start <= report_month <= end."""
    iw, ids = _iw(cur, [item])
    return _fetchall(cur,
                     f"SELECT report_month, month_actual FROM {_src(measure)} "
                     f"WHERE {iw} AND plant_name=%s "
                     "AND report_month>=%s AND report_month<=%s ORDER BY report_month",
                     ids + [plant, start, end])


def item_month_by_plant(cur, item, month, plants):
    """fetchall() of (plant_name, month_actual) actuals for one item/month."""
    iw, ids = _iw(cur, [item])
    return _fetchall(cur,
                     f"SELECT plant_name, month_actual FROM {_src('actual')} "
                     f"WHERE {iw} AND report_month=%s AND plant_name IN ({_ph(plants)})"
                     " ORDER BY plant_name",
                     ids + [month] + list(plants))


def item_all_months_by_plant(cur, item, plants):
    """fetchall() of (report_month, plant_name, month_actual) actuals, all months."""
    iw, ids = _iw(cur, [item])
    return _fetchall(cur,
                     f"SELECT report_month, plant_name, month_actual FROM {_src('actual')} "
                     f"WHERE {iw} AND plant_name IN ({_ph(plants)})"
                     " ORDER BY report_month, plant_name",
                     ids + list(plants))


# ── page_finished_steel_report.py ───────────────────────────────────────────

def item_alias_rows(cur, aliases, months=None):
    """fetchall() of (report_month, plant_name, item_name, month_actual) for
    any of `aliases`, optionally limited to `months`, ORDER BY report_month."""
    where, params = _iw(cur, aliases)
    if months is not None:
        where += f" AND report_month IN ({_ph(months)})"
        params += list(months)
    return _fetchall(cur,
                     f"SELECT report_month, plant_name, item_name, month_actual FROM {_src('actual')} "
                     f"WHERE {where}" + _O_MPI,
                     params)


def item_alias_report_months(cur, aliases):
    """fetchall() of DISTINCT report_month for any of `aliases`."""
    iw, ids = _iw(cur, aliases)
    rows = _fetchall(cur,
                     f"SELECT report_month FROM {_src('actual')} WHERE {iw}" + _O_IMP,
                     ids)
    return _distinct_first(rows, key=lambda r: r[0])


# ── page_major_unit_records.py ──────────────────────────────────────────────

def plant_items_monthly_sum_upto(cur, plant, item_names, upto_month):
    """fetchall() of (report_month, SUM) over item_names for a plant, months
    <= upto_month (all months when upto_month is None)."""
    upto = "" if upto_month is None else " AND report_month <= %s"
    iw, ids = _iw(cur, item_names)
    rows = _fetchall(cur,
                     f"SELECT report_month, month_actual FROM {_src('actual')} "
                     f"WHERE plant_name = %s AND {iw}{upto}" + _O_PIM,
                     [plant] + ids + ([] if upto_month is None else [upto_month]))
    groups = _groups(rows, lambda r: r[0])
    return _rows_like(cur, ["report_month", "SUM(month_actual)"],
                      [(k, _msum(r[1] for r in g)) for k, g in groups.items()])


# ── page_records.py (record statistics) ─────────────────────────────────────

def _records_ph(lst):
    return ','.join(['%s'] * len(lst))


def _scope_where(nitems, nplants, upto):
    """records_scope's WHERE text for a scope shape (nitems None: no item
    filter). records_scope builds it; _scope_shape inverts it."""
    ph = ','.join(['%s'] * nplants)
    where = f"plant_name IN ({ph})" if nitems is None else \
        f"item_name IN ({','.join(['%s'] * nitems)}) AND plant_name IN ({ph})"
    return where + (" AND report_month <= %s" if upto else "")


def records_scope(plants, items=None, upto_month=None):
    """(where, args) selecting `plants` (and `items`, when given; and months
    <= upto_month, when given) for the records queries below. Opaque to
    callers: pass it straight back to them. Kept a plain (where, args)
    tuple, byte for byte v1's (the oracle compares it, and replays v1's
    recorded scopes into the readers below)."""
    plants = list(plants)
    items = None if items is None else list(items)
    where = _scope_where(None if items is None else len(items), len(plants), bool(upto_month))
    args = (items or []) + plants + ([upto_month] if upto_month else [])
    return where, args


_SHAPES = {}


def _scope_shape(scope):
    """(nitems or None, nplants, upto) of a records_scope (where, args): the
    shape whose _scope_where is this where (no parsing of the SQL text; the
    argument count bounds the search). A where records_scope cannot have
    built raises ValueError."""
    where, args = scope
    key = (where, len(args))
    shape = _SHAPES.get(key)
    if shape is None:
        for upto in (False, True):
            for nitems in [None] + list(range(len(args) + 1)):
                nplants = len(args) - (nitems or 0) - upto
                if nplants >= 0 and _scope_where(nitems, nplants, upto) == where:
                    shape = (nitems, nplants, upto)
                    break
            if shape is not None:
                break
        if shape is None:
            raise ValueError(f"not a records_scope: {where!r}")
        _SHAPES[key] = shape
    return shape


def _scope_sql(cur, scope):
    """(v2 WHERE, params, shape) for a records scope: the items become an
    item_id IN (...) filter (idx_production_item_month)."""
    nitems, nplants, upto = shape = _scope_shape(scope)
    args = list(scope[1])
    items, rest = (args[:nitems], args[nitems:]) if nitems is not None else ([], args)
    where = f"plant_name IN ({_ph(rest[:nplants])})" if nplants else "plant_name IN ()"
    params = rest[:nplants]
    if nitems is not None:
        iw, ids = _iw(cur, items)
        where = f"{iw} AND {where}"
        params = ids + params
    if upto:
        where += " AND report_month <= %s"
        params.append(rest[nplants])
    return where, params, shape


# The order v1's records queries read their rows in. v1 had no ORDER BY, so
# the order was the access path MySQL's cost model picked for each scope
# shape page_records builds (EXPLAIN on the v1 data, proven by the oracle
# replay of every recorded scope). PARITY SHIM: these rules reproduce v1's
# optimizer choice; remove after the 7g gate with an announced order change.
#   records_rows (and the zero-call bucket / FY-window cells, which v1 said
#   share its access path):
#     upto month                      PRIMARY range        (month, plant, item)
#     items x plants >= 35            table scan           (month, plant, item)
#     otherwise (one plant; items x   idx_prod_plant_item  (plant, item, month)
#       plants < 35)
#   records_calendar_month_totals (its GROUP BY changes the pick):
#     upto month                      PRIMARY range        (month, plant, item)
#     items + 8 or more plants        idx_prod_item_month  (item, month, plant)
#     otherwise                       idx_prod_plant_item  (plant, item, month)

def _records_order(shape):
    nitems, nplants, upto = shape
    # v1 scanned the table once the (plant, item) ranges reached 35
    # (6 items x 5 plants: range scan; 7 x 5 and 6 x 8: table scan).
    if upto or (nitems or 0) * nplants >= 35:
        return _O_MPI
    return _O_PIM


def _calendar_order(shape):
    nitems, nplants, upto = shape
    if upto:
        return _O_MPI
    if nitems and nplants >= 8:
        return _O_IMP
    return _O_PIM


def _records_fetch(cur, scope, extra_where="", extra_args=()):
    """(item_name, plant_name, report_month, month_actual, fy, fy_month,
    quarter, half, days) rows of `scope`, in v1's read order."""
    where, params, shape = _scope_sql(cur, scope)
    return _fetchall(cur,
                     "SELECT item_name, plant_name, report_month, month_actual, "
                     "cal_fy, cal_fy_month, cal_quarter, cal_half, cal_days "
                     f"FROM {_REC_SRC} WHERE {where}{extra_where}" + _records_order(shape),
                     params + list(extra_args))


def _fy_start(fy):
    return int(fy[:4])


# bucket -> ([column names], row -> bucket values)
_RECORDS_BUCKETS = {
    "quarter": (["qnum", "fy_start"], lambda r: (r[6], _fy_start(r[4]))),
    "half":    (["hnum", "fy_start"], lambda r: (r[7], _fy_start(r[4]))),
    "fy":      (["fy_start"],         lambda r: (_fy_start(r[4]),)),
    "cy":      (["yr"],               lambda r: (r[2][:4],)),
}


def _records_cells(cur, rows, bucket_cols, bucket_of):
    groups = _groups(rows, lambda r: (fold(r[0]), bucket_of(r), fold(r[1]), r[2]))
    out = []
    for g in groups.values():
        first = g[0]
        out.append((first[0], *bucket_of(first), first[1], first[2],
                    _msum(r[3] for r in g), max(r[8] for r in g)))
    return _rows_like(cur, ["item_name", *bucket_cols, "plant_name", "report_month", "v", "days"], out)


def records_bucket_cells(cur, scope, bucket):
    """fetchall() of (item_name, *bucket columns, plant_name, report_month,
    v, days) per (item, period bucket, plant, month). bucket: 'quarter'
    (qnum, fy_start) | 'half' (hnum, fy_start) | 'fy' (fy_start) | 'cy' (yr)."""
    cols, bucket_of = _RECORDS_BUCKETS[bucket]
    return _records_cells(cur, _records_fetch(cur, scope), cols, bucket_of)


def records_calendar_month_totals(cur, scope):
    """fetchall() of (item_name, mon_num, report_month, total), ordered by
    item, month number, total DESC. v1 grouped in its read order and then
    filesorted the groups, so groups with equal (item, mon_num, total)
    come out in MySQL's std::sort order (repo._mysqlsort).

    When this scope's read order is records_rows' (the same ORDER BY, a total
    order: (month, plant, item) and (plant, item, month) are unique among the
    actual rows), its rows are records_rows' rows (memoised per request) plus
    each item's WEIGHT_STRING, looked up once per distinct name."""
    shape = _scope_shape(scope)
    if _calendar_order(shape) == _records_order(shape):
        base = records_rows(cur, scope)
        names = list(dict.fromkeys(r[0] for r in base))
        weights = {r[0]: r[1] for r in _fetchall(
            cur,
            "SELECT item_name, WEIGHT_STRING(item_name COLLATE utf8mb4_0900_ai_ci) FROM item "
            f"WHERE item_name IN ({_ph(names)})", names)} if names else {}
        rows = [(r[0], r[1], r[2], r[3], weights[r[0]]) for r in base]
    else:
        where, params, shape = _scope_sql(cur, scope)
        rows = _fetchall(cur,
                         "SELECT item_name, plant_name, report_month, month_actual, "
                         "WEIGHT_STRING(item_name) AS w "
                         f"FROM {_SRC['actual']} WHERE {where}" + _calendar_order(shape),
                         params)
    groups = _groups(rows, lambda r: (fold(r[0]), r[2]))
    totals = []
    for g in groups.values():
        first = g[0]
        totals.append((first[4], (first[0], int(first[2][5:7]), first[2], _msum(r[3] for r in g))))
    # ORDER BY item_name, mon_num, total DESC (NULL lowest, so last)
    totals = mysql_sort(totals, key=lambda t: (t[0], t[1][1], t[1][3] is None, -(t[1][3] or 0.0)))
    return _rows_like(cur, ["item_name", "mon_num", "report_month", "total"], [t[1] for t in totals])


def records_latest_month(cur):
    """Latest report_month of the actuals."""
    return _fetchone(cur, "SELECT MAX(report_month) FROM production_monthly WHERE has_actual = 1")[0]


def records_plants_items_in(cur, plants):
    """fetchall() of DISTINCT item_name over `plants` (always the IN form)."""
    rows = _fetchall(cur,
                     f"SELECT item_name FROM {_src('actual')} "
                     f"WHERE plant_name IN ({_records_ph(plants)})" + _O_PIM,
                     list(plants))
    return _distinct_first(rows)


def records_rows(cur, scope):
    """[(item_name, plant_name, report_month, month_actual)] for every row
    in `scope`, in the order v1's MySQL read them (explicit ORDER BY here),
    which is the order of v1's records GROUP BY queries' output; page_records
    aggregates them in Python. Memoised per scope in the active
    report_context (the result is shared: do not mutate)."""
    where, args = scope

    def fetch():
        v2_where, params, shape = _scope_sql(cur, scope)
        return [tuple(r) for r in _fetchall(
            cur,
            f"SELECT item_name, plant_name, report_month, month_actual FROM {_SRC['actual']} "
            f"WHERE {v2_where}" + _records_order(shape),
            params)]

    ctx = report_context.current()
    if ctx is None:
        return fetch()
    return ctx.memo(("records_rows", where, tuple(args)), fetch)


def records_fy_window_cells(cur, scope, s_pos, e_pos):
    """fetchall() of (item_name, fy_start, plant_name, report_month, v, days)
    for months whose FY position (0 = Apr) is within [s_pos, e_pos]."""
    rows = _records_fetch(cur, scope, " AND (cal_fy_month - 1) BETWEEN %s AND %s", (s_pos, e_pos))
    cols, bucket_of = _RECORDS_BUCKETS["fy"]
    return _records_cells(cur, rows, cols, bucket_of)


# ── page_prod_by_process.py ─────────────────────────────────────────────────

def five_plant_saleable_semis(cur, months, plants):
    """fetchone() of COALESCE(SUM) of 'Saleable Semis' over months x plants."""
    total = _sum_sql(cur, "actual",
                     f"report_month IN ({_ph(months)}) AND plant_name IN ({_ph(plants)}) "
                     "AND item_name='Saleable Semis'",
                     (*months, *plants), " ORDER BY report_month, plant_name")
    return _row_like(cur, ["COALESCE(SUM(month_actual),0)"], (_coalesce0(total),))


def asp_saleable_finished_by_month(cur, months):
    """fetchall() of (report_month, item_name, month_actual) for ASP's
    Saleable Steel and Finished Steel."""
    return _fetchall(cur,
                     f"SELECT report_month, item_name, month_actual FROM {_src('actual')} "
                     f"WHERE report_month IN ({_ph(months)}) AND plant_name='ASP' "
                     "AND item_name IN ('Saleable Steel','Finished Steel')" + _O_MPI,
                     months)


def dsp_bottom_pouring_ingot_sum(cur, months):
    """fetchone() of COALESCE(SUM) of DSP 'Bottom Pouring Ingot' over months."""
    total = _sum_sql(cur, "actual",
                     f"report_month IN ({_ph(months)}) AND plant_name='DSP' AND item_name='Bottom Pouring Ingot'",
                     months, " ORDER BY report_month")
    return _row_like(cur, ["COALESCE(SUM(month_actual),0)"], (_coalesce0(total),))


# ── page_production_trend.py ────────────────────────────────────────────────

def items_plants_all_months(cur, items, plants):
    """fetchall() of (plant_name, item_name, report_month, month_actual)."""
    iw, ids = _iw(cur, items)
    return _fetchall(cur,
                     f"SELECT plant_name, item_name, report_month, month_actual FROM {_src('actual')} "
                     f"WHERE {iw} AND plant_name IN ({_ph(plants)})" + _O_PIM,
                     ids + list(plants))


def item_plants_all_months(cur, item, plants):
    """fetchall() of (plant_name, report_month, month_actual) for one item."""
    iw, ids = _iw(cur, [item])
    return _fetchall(cur,
                     f"SELECT plant_name, report_month, month_actual FROM {_src('actual')} "
                     f"WHERE {iw} AND plant_name IN ({_ph(plants)}) ORDER BY report_month, plant_name",
                     ids + list(plants))


def items_plant_all_months(cur, items, plant):
    """fetchall() of (item_name, report_month, month_actual) for one plant."""
    iw, ids = _iw(cur, items)
    return _fetchall(cur,
                     f"SELECT item_name, report_month, month_actual FROM {_src('actual')} "
                     f"WHERE {iw} AND plant_name=%s" + _O_PIM,
                     ids + [plant])


# ── page_sail8_trend_annexure.py ────────────────────────────────────────────

def items_plants_upto(cur, items, plants, month):
    """fetchall() of (plant_name, item_name, report_month, month_actual),
    report_month <= month."""
    iw, ids = _iw(cur, items)
    return _fetchall(cur,
                     f"SELECT plant_name, item_name, report_month, month_actual FROM {_src('actual')} "
                     f"WHERE {iw} AND plant_name IN ({_ph(plants)}) "
                     "AND report_month <= %s" + _O_MPI,
                     ids + list(plants) + [month])


def items_sail_upto(cur, items, month):
    """fetchall() of (item_name, report_month, month_actual) for the stored
    SAIL rows, report_month <= month."""
    iw, ids = _iw(cur, items)
    return _fetchall(cur,
                     f"SELECT item_name, report_month, month_actual FROM {_src('actual')} "
                     f"WHERE {iw} AND plant_name='SAIL' AND report_month <= %s" + _O_PIM,
                     ids + [month])


# ── page_secretary_review.py ────────────────────────────────────────────────

def latest_hot_metal_month_row(cur):
    """fetchone() of the latest month with a non-NULL Hot Metal actual."""
    iw, ids = _iw(cur, ["Hot Metal"])
    return _fetchone(cur, f"SELECT MAX(report_month) FROM {_src('actual')} "
                          f"WHERE {iw} AND month_actual IS NOT NULL", ids)


def mou_items_for_month(cur, month):
    """fetchall() of DISTINCT item_name with a non-NULL MoU value for month."""
    rows = _fetchall(cur, f"SELECT item_name FROM {_src('mou')} "
                          "WHERE report_month=%s AND month_actual IS NOT NULL" + _O_MPI, (month,))
    return _distinct_first(rows)


# ── page_special_steel_trend.py ─────────────────────────────────────────────

def ssp_saleable_despatch_count_row(cur, months):
    """fetchone() of COUNT(*) of SSP 'Saleable Steel Despatch' rows in months."""
    return _fetchone(cur, f"SELECT COUNT(*) FROM {_src('actual')} "
                          f"WHERE report_month IN ({_ph(months)}) AND plant_name='SSP' "
                          "AND item_name='Saleable Steel Despatch'", months)


# ── page_missing_data.py ────────────────────────────────────────────────────

def actual_plants_for_month(report_month):
    """{plant_name} with any actual row for the month."""
    with rc.cursor() as cur:
        cur.execute("SELECT DISTINCT plant_code FROM production_monthly "
                    "WHERE report_month = %s AND has_actual = 1", [report_month])
        return {r[0] for r in cur.fetchall()}


def fs_alias_sum(cur, measure: Measure, month, plants):
    """_fs_alias_sum by measure: SAIL-style Finished Steel sum over `plants`
    for one month (SSP/VISL fall back to Saleable Steel)."""
    _table(measure)
    return _fs_alias_sum(cur, measure, month, plants)


def sail_conversion_actual(cur, month):
    """SAIL-level 'Conversion' actual for a month (see _sail_conversion_actual)."""
    return _sail_conversion_actual(cur, month)


# ── page_special_steel.py ───────────────────────────────────────────────────

def ytd_sum_row(cur, ytd_months, plant, item):
    """fetchone() of COALESCE(SUM) for one plant/item over ytd_months (actual)."""
    total = _sum_sql(cur, "actual",
                     f"report_month IN ({_ph(ytd_months)}) AND plant_name=%s AND item_name=%s",
                     (*ytd_months, plant, item), " ORDER BY report_month")
    return _row_like(cur, ["COALESCE(SUM(month_actual),0)"], (_coalesce0(total),))


def ssp_despatch_minus_carbon_000t(cur, months, item="Saleable Steel Despatch"):
    """(SSP `item` total, SSP Finished Carbon Steel Despatch total) over
    months, '000 T (COALESCE'd to 0)."""
    where = f"report_month IN ({_ph(months)}) AND plant_name='SSP' AND item_name=%s"
    total = _coalesce0(_sum_sql(cur, "actual", where, (*months, item), " ORDER BY report_month"))
    carbon = _coalesce0(_sum_sql(cur, "actual", where, (*months, "Finished Carbon Steel Despatch"),
                                 " ORDER BY report_month"))
    return total, carbon


# ── page_special_steel_donut.py ─────────────────────────────────────────────

def sum_count_row(cur, measure: Measure, months, plants, item):
    """fetchone() of (COALESCE(SUM),0), COUNT(*)) over months x plants for item."""
    vals = _values_sql(cur, measure,
                       f"report_month IN ({_ph(months)}) AND plant_name IN ({_ph(plants)}) AND item_name=%s",
                       (*months, *plants, item), " ORDER BY report_month, plant_name")
    return _row_like(cur, ["COALESCE(SUM(month_actual),0)", "COUNT(*)"],
                     (_coalesce0(_msum(vals)), len(vals)))


def saleable_steel_sum_row(cur, measure: Measure, months, plants):
    """fetchone() of COALESCE(SUM) of 'Saleable Steel' over months x plants."""
    total = _sum_sql(cur, measure,
                     f"report_month IN ({_ph(months)}) AND plant_name IN ({_ph(plants)}) "
                     "AND item_name='Saleable Steel'",
                     (*months, *plants), " ORDER BY report_month, plant_name")
    return _row_like(cur, ["COALESCE(SUM(month_actual),0)"], (_coalesce0(total),))


# ── page_special_steel_physical.py ──────────────────────────────────────────

def plant_item_sum_counts(cur, measure: Measure, plants, items, months):
    """fetchall() of (plant_name, item_name, COALESCE(SUM), COUNT(DISTINCT
    report_month)) over non-NULL rows in plants x items x months.

    v1 read the PRIMARY KEY range (month, plant, item), filesorted it on
    (plant, item) and aggregated each run of equal keys: each group's SUM
    adds its rows in MySQL's std::sort order (repo._mysqlsort)."""
    rows = _fetchall(cur,
                     f"SELECT plant_name, item_name, report_month, month_actual, "
                     f"WEIGHT_STRING(plant_name) AS wp, WEIGHT_STRING(item_name) AS wi FROM {_src(measure)} "
                     f"WHERE plant_name IN ({_ph(plants)}) AND item_name IN ({_ph(items)}) "
                     f"AND report_month IN ({_ph(months)}) AND month_actual IS NOT NULL" + _O_MPI,
                     [*plants, *items, *months])
    out, group, gkey = [], [], None
    for r in mysql_sort(rows, key=lambda r: (r[4], r[5])) + [None]:
        k = None if r is None else (r[4], r[5])
        if group and k != gkey:
            out.append((group[0][0], group[0][1], _coalesce0(_msum(x[3] for x in group)),
                        len({x[2] for x in group})))
            group = []
        if r is not None:
            group.append(r)
            gkey = k
    return _rows_like(cur, ["plant_name", "item_name", "COALESCE(SUM(month_actual), 0)",
                            "COUNT(DISTINCT report_month)"], out)


def plant_item_rows_from(cur, measure: Measure, plants, items, from_month):
    """fetchall() of (report_month, plant_name, item_name, month_actual), non-NULL,
    report_month >= from_month."""
    order = _O_PIM if measure == "actual" else _O_MPI
    return _fetchall(cur,
                     f"SELECT report_month, plant_name, item_name, month_actual FROM {_src(measure)} "
                     f"WHERE plant_name IN ({_ph(plants)}) AND item_name IN ({_ph(items)}) "
                     "AND month_actual IS NOT NULL AND report_month >= %s" + order,
                     [*plants, *items, from_month])


# ── page_techno.py / page_techno_records.py ────────────────────────────────

def plan_hm_cs_by_plant_item(cur, months):
    """fetchall() of (plant_name, item_name, SUM ABP) for Hot Metal and Total
    Crude Steel over months, 5 ISPs."""
    iw, ids = _iw(cur, ["Hot Metal", "Total Crude Steel"])
    rows = _fetchall(cur,
                     f"SELECT plant_name, item_name, month_actual FROM {_src('abp')} "
                     f"WHERE report_month IN ({_ph(months)}) AND {iw} "
                     "AND plant_name IN ('BSP','DSP','RSP','BSL','ISP')" + _O_MPI,
                     list(months) + ids)
    groups = _groups(rows, lambda r: (fold(r[0]), fold(r[1])))
    return _rows_like(cur, ["plant_name", "item_name", "SUM(month_actual)"],
                      [(g[0][0], g[0][1], _msum(r[2] for r in g)) for g in groups.values()])


def item_by_plant_month(cur, item, months):
    """fetchall() of (plant_name, report_month, month_actual) actuals for one
    item over months, every plant."""
    iw, ids = _iw(cur, [item])
    return _fetchall(cur,
                     f"SELECT plant_name, report_month, month_actual FROM {_src('actual')} "
                     f"WHERE report_month IN ({_ph(months)}) AND {iw} ORDER BY report_month, plant_name",
                     list(months) + ids)


def items_by_plant_month(cur, items, months):
    """fetchall() of (plant_name, item_name, report_month, month_actual)
    actuals for items over months, every plant."""
    iw, ids = _iw(cur, items)
    return _fetchall(cur,
                     f"SELECT plant_name, item_name, report_month, month_actual FROM {_src('actual')} "
                     f"WHERE report_month IN ({_ph(months)}) AND {iw}" + _O_IMP,
                     [*months, *ids])


def hm_cs_signature_row(cur, months):
    """fetchone() of (COUNT(*), SUM) of Hot Metal + Total Crude Steel actuals
    over months (page_techno_records' cache signature)."""
    iw, ids = _iw(cur, ["Hot Metal", "Total Crude Steel"])
    vals = _values_sql(cur, "actual", f"report_month IN ({_ph(months)}) AND {iw}",
                       list(months) + ids, _O_IMP)
    return _row_like(cur, ["COUNT(*)", "SUM(month_actual)"], (len(vals), _msum(vals)))


# ── techno_cumulative.py / techno_period.py ────────────────────────────────

def plant_items_month_values(cur, plant, items, months):
    """fetchall() of (report_month, month_actual) actuals for one plant, any
    of `items`, over months (one row per matching item)."""
    iw, ids = _iw(cur, items)
    return _fetchall(cur,
                     f"SELECT report_month, month_actual FROM {_src('actual')} "
                     f"WHERE plant_name=%s AND {iw} AND report_month IN ({_ph(months)})" + _O_PIM,
                     [plant, *ids, *months])


# ── scripts/ (one-off backfills / validators) ──────────────────────────────

def plant_rows_for_months(cur, plant, months):
    """fetchall() of (report_month, item_name, month_actual) actuals for one
    plant over months."""
    return _fetchall(cur,
                     f"SELECT report_month, item_name, month_actual FROM {_src('actual')} "
                     f"WHERE plant_name=%s AND report_month IN ({_ph(months)})" + _O_MPI,
                     (plant, *months))


def plant_item_months(cur, plant, item_name):
    """fetchall() of (report_month,) actual rows for one plant/item."""
    iw, ids = _iw(cur, [item_name])
    return _fetchall(cur,
                     f"SELECT report_month FROM {_src('actual')} "
                     f"WHERE plant_name=%s AND {iw} ORDER BY report_month",
                     (plant, *ids))


def plant_all_rows(cur, measure: Measure, plant):
    """fetchall() of (item_name, report_month, month_actual) for one plant."""
    order = _O_PIM if measure == "actual" else _O_MPI
    return _fetchall(cur,
                     f"SELECT item_name, report_month, month_actual FROM {_src(measure)} WHERE plant_name=%s"
                     + order,
                     (plant,))


# ── production_op_monthly: the month's Operating Plan (api_op_plan) ──────────
# v2-only (no v1 counterpart). Items are matched by their exact name, the same
# names production_monthly holds for the APP.

def op_plan_items(plant: str, month: str):
    """[(item_name, op_plan, updated_by, updated_at 'YYYY-MM-DD HH:MM')] of one
    plant's OP for the month, by item name."""
    conn = connect()
    try:
        return [tuple(r) for r in _fetchall(
            conn.cursor(),
            "SELECT i.item_name, o.op_plan, o.updated_by, DATE_FORMAT(o.updated_at, '%%Y-%%m-%%d %%H:%%i') "
            "FROM production_op_monthly o JOIN item i ON i.item_id = o.item_id "
            "WHERE o.plant_code = %s AND o.report_month = %s ORDER BY i.item_name",
            (plant, month))]
    finally:
        conn.close()


def op_plan_plant_counts(month: str):
    """[(plant_code, number of items with an OP)] for the month."""
    conn = connect()
    try:
        return [tuple(r) for r in _fetchall(
            conn.cursor(),
            "SELECT plant_code, COUNT(*) FROM production_op_monthly WHERE report_month = %s "
            "GROUP BY plant_code ORDER BY plant_code", (month,))]
    finally:
        conn.close()


def op_plan_month_rows(months, plants):
    """[(report_month, plant_code, item_name, op_plan)] of the OP over months
    for the given plants."""
    if not months or not plants:
        return []
    conn = connect()
    try:
        return [tuple(r) for r in _fetchall(
            conn.cursor(),
            "SELECT o.report_month, o.plant_code, i.item_name, o.op_plan "
            "FROM production_op_monthly o JOIN item i ON i.item_id = o.item_id "
            f"WHERE o.report_month IN ({_ph(months)}) AND o.plant_code IN ({_ph(plants)}) "
            "ORDER BY o.report_month, o.plant_code, i.item_name",
            list(months) + list(plants))]
    finally:
        conn.close()


def save_op_plan(month: str, plant: str, entries, user: Optional[str]):
    """Set one plant's OP for the month in one transaction. entries =
    [(item_name, value)]; value None removes that item's OP. Returns
    (saved, cleared) counts."""
    month = _keys.fit_month(month)
    _keys.check_month(month)
    _keys.fits("updated_by", user, 255)
    entries = [(item.strip(), value) for item, value in entries if item and item.strip()]
    for item, _ in entries:
        _keys.fits("item_name", item, 64, nullable=False)
    saved = cleared = 0
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        _keys.ensure_month(cur, month, bump=False)
        _keys.ensure_plant(cur, plant, bump=False)
        for item, value in entries:
            if value is None:
                item_id = _keys.exact_item_id(cur, item, lock=True)
                if item_id is not None:
                    cur.execute("DELETE FROM production_op_monthly "
                                "WHERE report_month = %s AND plant_code = %s AND item_id = %s",
                                (month, plant, item_id))
                    cleared += cur.rowcount
                continue
            item_id = _item_id_for_write(cur, item, bump=False)
            cur.execute("INSERT INTO production_op_monthly (report_month, plant_code, item_id, op_plan,"
                        " updated_by, updated_at) VALUES (%s, %s, %s, %s, %s, NOW()) AS new"
                        " ON DUPLICATE KEY UPDATE op_plan = new.op_plan, updated_by = new.updated_by,"
                        " updated_at = new.updated_at",
                        (month, plant, item_id, float(value), user))
            saved += 1
        conn.commit()
    finally:
        conn.close()
    activity_context.record(f"production_op_monthly/{plant}/{month}", None,
                            {item: value for item, value in entries})
    return saved, cleared
