"""
MySQL connection layer: connect() returns a pooled PyMySQL connection
wrapped in ConnWrapper, which keeps the small DB-API surface the codebase
uses (cursor(), execute(), commit(), rollback(), close(), row_factory).

SQL is native MySQL (``%s`` placeholders). The wrapper always passes a
params tuple to PyMySQL (empty when there are none), so every literal ``%``
in SQL text is written ``%%``.

  conn.row_factory = Row             -> fetches return Row objects
                                        (row[0], row['col'], dict(row))
  pymysql ProgrammingError           -> pymysql OperationalError (callers
                                        catch OperationalError for missing
                                        tables, as they did before)
  DATETIME/DATE/TIMESTAMP results    -> ISO strings
"""
import os
import re

import pymysql
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

_MYSQL_CFG = {
    "host":     os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port":     int(os.environ.get("MYSQL_PORT", "3306")),
    "database": os.environ.get("MYSQL_DB", "mis_reports_v2"),
    "user":     os.environ.get("MYSQL_USER", "mis_app"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
}

IntegrityError = pymysql.err.IntegrityError
OperationalError = pymysql.err.OperationalError


# ── Result row ──────────────────────────────────────────────────────────────

class Row:
    """Supports row[0], row['col'] (case-insensitive fallback), iteration
    over values, len(), keys(), and dict(row)."""
    __slots__ = ("_keys", "_values", "_lower")

    def __init__(self, keys, values):
        self._keys = keys
        self._values = values
        self._lower = None

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        try:
            return self._values[self._keys.index(key)]
        except ValueError:
            if self._lower is None:
                self._lower = [k.lower() for k in self._keys]
            return self._values[self._lower.index(key.lower())]

    def keys(self):
        return list(self._keys)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"Row({dict(zip(self._keys, self._values))!r})"


# ── Connection / cursor wrappers ────────────────────────────────────────────

def _wrap_error(exc):
    """ProgrammingError (e.g. missing table) is raised as OperationalError so
    `except OperationalError` keeps catching both, as callers expect."""
    if isinstance(exc, pymysql.err.ProgrammingError):
        return OperationalError(*exc.args)
    return exc


class CursorWrapper:
    def __init__(self, cursor, conn_wrapper):
        self._cur = cursor
        self._conn = conn_wrapper

    # -- execution ----------------------------------------------------------
    def execute(self, sql, params=()):
        if _SESSION_STATE_RE.search(sql):
            self._conn._poolable = False
        try:
            self._cur.execute(sql, tuple(params))
        except pymysql.err.ProgrammingError as e:
            raise _wrap_error(e) from e
        return self

    def executemany(self, sql, seq_of_params):
        if _SESSION_STATE_RE.search(sql):
            self._conn._poolable = False
        try:
            self._cur.executemany(sql, [tuple(p) for p in seq_of_params])
        except pymysql.err.ProgrammingError as e:
            raise _wrap_error(e) from e
        return self

    # -- results ------------------------------------------------------------
    def _wrap(self, row):
        if row is None or self._conn.row_factory is None:
            return row
        keys = [d[0] for d in self._cur.description]
        return Row(keys, tuple(row))

    def fetchone(self):
        return self._wrap(self._cur.fetchone())

    def fetchall(self):
        rows = self._cur.fetchall()
        if self._conn.row_factory is None:
            return list(rows)
        keys = [d[0] for d in self._cur.description] if self._cur.description else []
        return [Row(keys, tuple(r)) for r in rows]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size else self._cur.fetchmany()
        if self._conn.row_factory is None:
            return list(rows)
        keys = [d[0] for d in self._cur.description] if self._cur.description else []
        return [Row(keys, tuple(r)) for r in rows]

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                return
            yield row

    # -- attributes ---------------------------------------------------------
    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def close(self):
        self._cur.close()


class ConnWrapper:
    """PyMySQL connection with the surface this codebase uses: cursor(),
    execute(), commit(), rollback(), close(), row_factory.

    close() hands the raw connection back to the pool (see below) instead of
    closing it, unless the connection picked up session state."""

    def __init__(self, conn):
        self._conn = conn
        self.row_factory = None
        self._poolable = True

    def cursor(self):
        if self._conn is None:
            raise pymysql.err.ProgrammingError("Cannot operate on a closed database.")
        return CursorWrapper(self._conn.cursor(), self)

    def execute(self, sql, params=()):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        raw, self._conn = self._conn, None
        if raw is not None:
            _pool_release(raw, self._poolable)


# ── Connection reuse (MySQL) ────────────────────────────────────────────────
# Callers open a fresh connection for nearly every query (db.py alone has ~110
# connect() sites; one report page can make hundreds of calls). A new MySQL
# connection costs ~3-4 ms (TCP + handshake + auth), which dominated slow
# pages. So close() returns the raw PyMySQL connection to a small idle pool
# and connect() reuses it. Semantics kept the same as a real close:
#   - rolled back on return, so uncommitted work is discarded and the next
#     user starts a new transaction (no stale REPEATABLE READ snapshot);
#   - a fresh ConnWrapper per connect(), so row_factory starts at None;
#   - connections that ran session-state SQL (GET_LOCK, SET ..., temporary
#     tables) are closed for real, never reused;
#   - an idle connection is pinged before reuse and replaced if dead.
# DB_POOL=0 in backend/.env turns reuse off (every close() is a real close).
import threading as _threading
import time as _time

_POOL_ENABLED = os.environ.get("DB_POOL", "1").strip() not in ("0", "false", "no", "off")
_POOL_MAX_IDLE = 8
_POOL_PING_AFTER = 30.0          # seconds idle before a liveness ping
_pool_lock = _threading.Lock()
_pool_idle = []                  # [(raw_conn, returned_at)], used LIFO
_SESSION_STATE_RE = re.compile(r"\bGET_LOCK\s*\(|^\s*SET\s|\bTEMPORARY\s+TABLE\b", re.I)


def _pool_clear():
    """Close every idle pooled connection (tests / shutdown)."""
    with _pool_lock:
        idle = list(_pool_idle)
        _pool_idle.clear()
    for raw, _ in idle:
        try:
            raw.close()
        except Exception:  # noqa: BLE001
            pass


def _pool_acquire():
    while True:
        with _pool_lock:
            if not _pool_idle:
                return None
            raw, returned_at = _pool_idle.pop()
        if _time.monotonic() - returned_at <= _POOL_PING_AFTER:
            return raw
        try:
            raw.ping(reconnect=False)
            return raw
        except Exception:  # noqa: BLE001 - dead connection, drop it and try the next
            try:
                raw.close()
            except Exception:  # noqa: BLE001
                pass


def _pool_release(raw, poolable):
    if _POOL_ENABLED and poolable:
        try:
            raw.rollback()
        except Exception:  # noqa: BLE001 - broken connection, don't reuse
            poolable = False
        else:
            with _pool_lock:
                if len(_pool_idle) < _POOL_MAX_IDLE:
                    _pool_idle.append((raw, _time.monotonic()))
                    return
    try:
        raw.close()
    except Exception:  # noqa: BLE001
        pass


def _open_raw():
    from pymysql import converters
    conv = converters.conversions.copy()
    # Timestamps come back as strings (the codebase was written for TEXT
    # timestamps), so callers never see datetime objects.
    for ft in (pymysql.constants.FIELD_TYPE.DATETIME,
               pymysql.constants.FIELD_TYPE.DATE,
               pymysql.constants.FIELD_TYPE.TIMESTAMP):
        conv[ft] = str
    try:
        return pymysql.connect(
            host=_MYSQL_CFG["host"], port=_MYSQL_CFG["port"],
            user=_MYSQL_CFG["user"], password=_MYSQL_CFG["password"],
            database=_MYSQL_CFG["database"], charset="utf8mb4",
            conv=conv, autocommit=False, ssl_disabled=True,
        )
    except Exception as e:  # noqa: BLE001
        raise _wrap_error(e) from e


# ── Shared rolled-back connection (repo.conn.rollback_tx) ──────────────────
# While set (per thread / asyncio task, via contextvars), every connect() in
# that context gets this one raw connection, so code that commits on its own
# connections can be dry-run and rolled back as a whole. Other threads and
# requests never see it.
import contextvars as _contextvars

_shared_raw = _contextvars.ContextVar("dbengine_shared_raw", default=None)


class _SharedConnWrapper(ConnWrapper):
    """connect() result inside rollback_tx: commit() is a no-op and close()
    only detaches; the owner of the shared connection rolls it back and
    closes it."""

    def __init__(self, conn):
        super().__init__(conn)
        self._poolable = False

    def commit(self):
        pass

    def close(self):
        self._conn = None


def _mysql_connect():
    shared = _shared_raw.get()
    if shared is not None:
        return _SharedConnWrapper(shared)
    raw = _pool_acquire() if _POOL_ENABLED else None
    return ConnWrapper(raw if raw is not None else _open_raw())


def connect(db_path=None):
    """Pooled MySQL connection (ConnWrapper). db_path is ignored; it is kept
    only so old call sites keep working."""
    return _mysql_connect()
