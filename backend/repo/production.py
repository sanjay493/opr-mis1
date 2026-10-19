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
from typing import Iterable, Literal

from repo import conn

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
    with conn.cursor() as cur:
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
    with conn.tx() as cur:
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
    with conn.tx() as cur:
        cur.execute(sql, params)
