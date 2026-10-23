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

TRAILING SPACES (fit_char). MySQL stores a CHAR/VARCHAR value that is
longer than its column when every excess character is a space: the excess
is cut (silently for CHAR, with a note for VARCHAR, in any sql_mode), so
v1 stored '2025-04' for '2025-04 ' and an INSERT ... ON DUPLICATE KEY of
'2025-04 ' updated the stored '2025-04' row. Comparisons keep the spaces
(the collations are NO PAD): v1's WHERE report_month = '2025-04 ' matched
nothing. Every v2 writer that takes a month (CHAR(7)) or an FY (CHAR(7))
therefore writes fit_month(value) and looks up with it wherever the
lookup stands in for v1's duplicate-key check; a lookup that v1 ran as its
own SELECT (an activity-log 'old', a put()'s read) keeps the raw value, so
it finds nothing exactly when v1's did. check_month / ensure_month fit
the value themselves.

The ensure_* helpers write master rows, so they take `bump` like every repo
write: the caller passes bump=False only after its own _ver.bump(cur) on
the same cursor (one bump per repo write, as v1).

LOCKING READS. Every lookup a write decides on is a locking read (FOR SHARE
on master rows, FOR UPDATE on the fact row to be changed), taken after the
bump. Under REPEATABLE READ a plain SELECT reads the transaction's snapshot,
which can predate a concurrent writer's commit; a locking read sees the
latest committed row, so two concurrent writes cannot both decide "missing"
and create two ai_ci-equal rows. 7c-7f: do the same.
"""
import datetime as _dt
import re
from contextlib import contextmanager

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


def fit_char(value, length):
    """MySQL's trailing-space rule for a CHAR/VARCHAR(length) value: when
    `value` is longer than the column and every excess character is a
    space, the value cut to `length` (what MySQL stores); else `value`
    unchanged (a longer value then fails the caller's length check, as
    MySQL raises 1406)."""
    if isinstance(value, str) and len(value) > length and not value[length:].strip(" "):
        return value[:length]
    return value


def fit_month(value):
    """fit_char for a CHAR(7) report_month / fy value."""
    return fit_char(value, _CHAR7)


fit_fy = fit_month


def check_month(month, column="report_month") -> None:
    """Raise, before any write, for a month string v2 cannot store (see the
    module docstring); a well-formed month passes whether or not cal_month
    has it yet. Trailing spaces past CHAR(7) are cut first (fit_month).
    `column`: the v1 column named in the 1406 error."""
    month = fit_month(month)
    if month is None:       # v1's NOT NULL column, strict mode
        raise pymysql.err.IntegrityError(1048, f"Column '{column}' cannot be null")
    if not isinstance(month, str):
        raise OutOfModelError(f"report month {month!r} is not a 'YYYY-MM' string")
    if len(month) > _CHAR7:
        raise pymysql.err.DataError(1406, f"Data too long for column '{column}' at row 1")
    if not _MONTH_RE.fullmatch(month):
        raise OutOfModelError(f"report month {month!r} is not a 'YYYY-MM' month; v1 stored it as text, "
                              f"the v2 calendar (cal_month) cannot hold it")


def ensure_month(cur, month, *, bump) -> None:
    """cal_month holds `month` afterwards (created when missing)."""
    if bump:
        _ver.bump(cur)
    month = fit_month(month)
    check_month(month)
    if cur.execute("SELECT 1 FROM cal_month WHERE report_month = %s FOR SHARE", (month,)).fetchone() is None:
        cur.execute("INSERT INTO cal_month (report_month, month_start, fy, fy_month, quarter, half) "
                    "VALUES (%s, %s, %s, %s, %s, %s) AS new "
                    "ON DUPLICATE KEY UPDATE fy = cal_month.fy", cal_month_row(month))


def ensure_plant(cur, plant, *, bump) -> None:
    """The plant master holds `plant` (ai_ci) afterwards (created when missing)."""
    if bump:
        _ver.bump(cur)
    if cur.execute("SELECT 1 FROM plant WHERE plant_code = %s FOR SHARE", (plant,)).fetchone() is None:
        cur.execute("INSERT INTO plant (plant_code, plant_name, plant_kind, sort_order) "
                    "VALUES (%s, NULL, 'external', 0) AS new "
                    "ON DUPLICATE KEY UPDATE plant_code = plant.plant_code", (plant,))


_PLANT_CODE_LEN = 8


def fits(column, value, limit, *, nullable=True):
    """v1's strict-mode errors for `value` in a v1 VARCHAR/CHAR(limit)
    column: IntegrityError 1048 for a NULL in a NOT NULL column, DataError
    1406 (v1's column name) when it is longer than `limit` characters
    (after MySQL's trailing-space cut). Writers call it per column in v1's
    column order, before anything is written."""
    if value is None:
        if not nullable:
            raise pymysql.err.IntegrityError(1048, f"Column '{column}' cannot be null")
        return
    s = value if isinstance(value, str) else str(value)
    if len(fit_char(s, limit)) > limit:
        raise pymysql.err.DataError(1406, f"Data too long for column '{column}' at row 1")


def check_plant_model(plant, column, v1_limit):
    """OutOfModelError for a plant longer than the v2 plant master's 8
    characters, which v1's `column` (`v1_limit` characters) stored (see
    parity_exceptions.md §2). Writers call it after every v1 column check
    (fits), so a value v1 refused still raises v1's error."""
    if isinstance(plant, str) and len(plant) > _PLANT_CODE_LEN:
        raise OutOfModelError(f"plant {plant!r}: v1's {column} held up to {v1_limit} characters, "
                              f"the v2 plant master holds {_PLANT_CODE_LEN}")


_FK_FAILS = 1452
_FK_DETAIL_MAX = 191
_FK_MSG = re.compile(r"\(`([^`]*)`\.`[^`]*`, CONSTRAINT `([^`]*)`")


@contextmanager
def v1_fk_errors(v1_fks, first_failing=None):
    """Re-raise a foreign-key failure (IntegrityError 1452) of a v2
    constraint in `v1_fks` with v1's message: v1_fks maps the v2 constraint
    name to (v1 table, v1 constraint, column, referenced v1 table,
    referenced column), for the FKs v1 itself declared (the database name
    in the message is kept). InnoDB checks a row's constraints in name
    order, which differs between v1's and v2's names: `first_failing()`,
    when given, returns the v2 name of the constraint v1 would have
    reported (the first failing one in v1's order)."""
    try:
        yield
    except pymysql.err.IntegrityError as e:
        m = _FK_MSG.search(str(e.args[1])) if e.args and e.args[0] == _FK_FAILS and len(e.args) > 1 else None
        if m is None or m.group(2) not in v1_fks:
            raise
        failing = first_failing() if first_failing else m.group(2)
        table, name, col, ref, ref_col = v1_fks[failing or m.group(2)]
        detail = (f"`{m.group(1)}`.`{table}`, CONSTRAINT `{name}` FOREIGN KEY (`{col}`) "
                  f"REFERENCES `{ref}` (`{ref_col}`))")
        # InnoDB writes the constraint detail into a 192-byte buffer: at most
        # 191 characters, the closing parenthesis included (measured on v1)
        msg = "Cannot add or update a child row: a foreign key constraint fails (" + detail[:_FK_DETAIL_MAX]
        raise pymysql.err.IntegrityError(_FK_FAILS, msg) from None


def exact_item_id(cur, name, *, lock=False):
    """item_id of the item spelled exactly `name` (binary compare), or None.
    lock=True (every write path): a locking read (FOR SHARE), so it sees the
    latest committed master row, not the transaction's older snapshot."""
    row = cur.execute("SELECT item_id FROM item WHERE item_name = %s" + (" FOR SHARE" if lock else ""),
                      (name,)).fetchone()
    return None if row is None else row[0]
