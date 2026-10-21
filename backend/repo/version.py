"""data_version: one-row counter (id=1, n BIGINT) that every repo write
bumps inside its own transaction, so a cache keyed on n can never serve a
page built from older data. See backend/data_version.py.

    bump(cur)       on the writer's cursor or db.connect() connection, so a
                    rollback (including repo.conn.rollback_tx's dry run)
                    also rolls back the bump
    read()          current n, or None (no table / no row)
    set_fresh(n)    n := GREATEST(n + 1, floor); after an admin restore

A missing data_version table (a database the migration has not reached) is
tolerated everywhere: bump() is a no-op and read() returns None.
"""
import time

import pymysql

from repo import conn as rc

_NO_TABLE = 1146          # ER_NO_SUCH_TABLE

# A first bump on an empty table starts from a fresh value (microseconds
# since the epoch), never from a small n an earlier row may already have used.
_BUMP_SQL = ("INSERT INTO data_version (id, n) VALUES (1, %s) AS new "
             "ON DUPLICATE KEY UPDATE n = data_version.n + 1")
_FRESH_SQL = ("INSERT INTO data_version (id, n) VALUES (1, %s) AS new "
              "ON DUPLICATE KEY UPDATE n = GREATEST(data_version.n + 1, new.n)")


def _no_table(exc) -> bool:
    return bool(getattr(exc, "args", None)) and exc.args[0] == _NO_TABLE


def now_us() -> int:
    return time.time_ns() // 1000


def bump(cur) -> None:
    """n := n + 1 on `cur` (a repo.conn Cursor, a db.connect() cursor or
    connection): it joins that transaction. Call it before the write's own
    statement on a shared cursor, so the caller still reads the write's
    lastrowid / rowcount."""
    try:
        cur.execute(_BUMP_SQL, (now_us(),))
    except (pymysql.err.OperationalError, pymysql.err.ProgrammingError) as e:
        if not _no_table(e):
            raise


def read():
    """Current n, or None when the table or its row is missing."""
    try:
        with rc.cursor() as cur:
            cur.execute("SELECT n FROM data_version WHERE id = 1")
            row = cur.fetchone()
    except (pymysql.err.OperationalError, pymysql.err.ProgrammingError) as e:
        if _no_table(e):
            return None
        raise
    return None if row is None else int(row[0])


def set_fresh(floor: int) -> None:
    """n := GREATEST(n + 1, floor), committed (or the row created at floor).
    No-op without the table."""
    try:
        with rc.tx() as cur:
            cur.execute(_FRESH_SQL, (floor,))
    except (pymysql.err.OperationalError, pymysql.err.ProgrammingError) as e:
        if not _no_table(e):
            raise
