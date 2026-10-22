"""Shared v2 key rules: months, plants and item names (read-only helpers).

MONTHS. Every v2 fact table's report_month is a declared FK to cal_month,
which holds 1960-04 .. 2040-03. v1 stored any string. A v2 write for a month
cal_month does not hold is refused BEFORE anything is written (and before
the data_version bump) with OutOfModelError, a ValueError. Deletes are not
checked: a delete for such a month matches no row, as it did in v1.

PLANTS. plant_code is a declared FK to the plant master (the 12 plant
strings v1 ever stored). A write for any other plant string is refused the
same way. The plant master is utf8mb4_0900_ai_ci, as v1's columns were, so
'bsp' still matches 'BSP'.

ITEM NAMES. item.item_name is utf8mb4_0900_bin: every case variant is its
own item row, with its exact text. v1 compared names under ai_ci, so reads
match with `item_name COLLATE utf8mb4_0900_ai_ci = %s` (every case variant),
or report_context.fold() on the Python side. Writes resolve the item master
row by the EXACT string the caller passed and create it when missing (v1
stored the caller's string verbatim, so a new case variant becomes a new
item row); each domain module documents how it reuses an existing variant
where v1's ai_ci unique key would have updated an existing row instead.
"""


class OutOfModelError(ValueError):
    """A write whose month or plant the v2 model cannot hold (v1 stored it)."""


def check_month(cur, month) -> None:
    """Raise OutOfModelError unless cal_month holds `month` exactly."""
    row = cur.execute("SELECT report_month FROM cal_month WHERE report_month = %s",
                      (month,)).fetchone()
    if row is None or row[0] != month:
        raise OutOfModelError(
            f"report month {month!r} is outside the calendar the database holds "
            f"(YYYY-MM, 1960-04 .. 2040-03)")


def check_plant(cur, plant) -> None:
    """Raise OutOfModelError unless the plant master holds `plant` (ai_ci)."""
    row = cur.execute("SELECT plant_code FROM plant WHERE plant_code = %s", (plant,)).fetchone()
    if row is None:
        raise OutOfModelError(f"unknown plant {plant!r}")


def exact_item_id(cur, name):
    """item_id of the item spelled exactly `name` (binary compare), or None."""
    row = cur.execute("SELECT item_id FROM item WHERE item_name = %s", (name,)).fetchone()
    return None if row is None else row[0]
