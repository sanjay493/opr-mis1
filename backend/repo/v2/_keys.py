"""Shared v2 key rules: months, plants and item names (for every repo/v2 module).

MONTHS. Every v2 fact table's report_month is a declared FK to cal_month
(seeded 1960-04 .. 2040-03). v1 stored any string that fit its CHAR(7).
A v2 write resolves the month first (ensure_month):
  - a cal_month row exists: nothing to do;
  - a well-formed 'YYYY-MM' (month 01..12) cal_month lacks, e.g. '1950-01'
    or '2099-01': the row is created with seed_cal_month.sql's rules
    (cal_month_row), so the write is stored as v1 stored it;
  - longer than 7 characters: pymysql DataError 1406 "Data too long for
    column 'report_month'", exactly v1's error (strict sql_mode);
  - any other string of at most 7 characters ('2025-4', '2025-13', 'abc',
    ''): v1 stored it, v2 cannot (cal_month needs a real month_start), so
    OutOfModelError (a ValueError) is raised before anything is written.
  Deletes never resolve: a month without a row matches nothing, as in v1.

PLANTS. plant_code is a declared FK to the plant master. A write for a
plant the master lacks creates it (ensure_plant): plant_kind 'external',
sort_order 0, plant_name NULL. The master is utf8mb4_0900_ai_ci, as v1's
columns were, so 'bsp' resolves to 'BSP' and the fact row stores the
caller's spelling, as v1 did. A plant code longer than plant_code's 8
characters (v1 allowed 32) raises MySQL's DataError 1406.

ITEM NAMES. item.item_name is utf8mb4_0900_bin: every case variant is its
own item row, with its exact text. v1 compared names under ai_ci, so reads
match with `item_name COLLATE utf8mb4_0900_ai_ci = %s` (every case variant),
or report_context.fold() on the Python side. Writes resolve the item master
row by the EXACT string the caller passed and create it when missing (v1
stored the caller's string verbatim, so a new case variant becomes a new
item row); each domain module documents how it reuses an existing variant
where v1's ai_ci unique key would have updated an existing row instead.

The ensure_* helpers write master rows, so they take `bump` like every repo
write: the caller passes bump=False only after its own _ver.bump(cur) on
the same cursor (one bump per repo write, as v1).
"""
import datetime as _dt
import re

import pymysql

from repo import version as _ver

_MONTH_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
_CHAR7 = 7


class OutOfModelError(ValueError):
    """A write whose key the v2 model cannot hold (v1 stored it)."""


def cal_month_row(month):
    """(report_month, month_start, fy, fy_month, quarter, half) for a
    well-formed 'YYYY-MM', by seed_cal_month.sql's rules."""
    y, m = int(month[:4]), int(month[5:7])
    fy_start = y - (m < 4)
    fy_month = (m + 8) % 12 + 1
    return (month, _dt.date(y, m, 1).isoformat() if y >= 1 else f"{y:04d}-{m:02d}-01",
            f"{fy_start}-{(fy_start + 1) % 100:02d}", fy_month,
            (fy_month - 1) // 3 + 1, (fy_month - 1) // 6 + 1)


def check_month(month) -> None:
    """Raise, before any write, for a month string v2 cannot store (see the
    module docstring); a well-formed month passes whether or not cal_month
    has it yet."""
    if not isinstance(month, str):
        raise OutOfModelError(f"report month {month!r} is not a 'YYYY-MM' string")
    if len(month) > _CHAR7:
        raise pymysql.err.DataError(1406, "Data too long for column 'report_month' at row 1")
    if not _MONTH_RE.fullmatch(month):
        raise OutOfModelError(f"report month {month!r} is not a 'YYYY-MM' month; v1 stored it as text, "
                              f"the v2 calendar (cal_month) cannot hold it")


def ensure_month(cur, month, *, bump) -> None:
    """cal_month holds `month` afterwards (created when missing)."""
    if bump:
        _ver.bump(cur)
    check_month(month)
    if cur.execute("SELECT 1 FROM cal_month WHERE report_month = %s", (month,)).fetchone() is None:
        cur.execute("INSERT INTO cal_month (report_month, month_start, fy, fy_month, quarter, half) "
                    "VALUES (%s, %s, %s, %s, %s, %s) AS new "
                    "ON DUPLICATE KEY UPDATE fy = cal_month.fy", cal_month_row(month))


def ensure_plant(cur, plant, *, bump) -> None:
    """The plant master holds `plant` (ai_ci) afterwards (created when missing)."""
    if bump:
        _ver.bump(cur)
    if cur.execute("SELECT 1 FROM plant WHERE plant_code = %s", (plant,)).fetchone() is None:
        cur.execute("INSERT INTO plant (plant_code, plant_name, plant_kind, sort_order) "
                    "VALUES (%s, NULL, 'external', 0) AS new "
                    "ON DUPLICATE KEY UPDATE plant_code = plant.plant_code", (plant,))


def exact_item_id(cur, name):
    """item_id of the item spelled exactly `name` (binary compare), or None."""
    row = cur.execute("SELECT item_id FROM item WHERE item_name = %s", (name,)).fetchone()
    return None if row is None else row[0]
