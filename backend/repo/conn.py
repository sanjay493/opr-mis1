"""Native MySQL connection helper over the pool in dbengine.

    from repo import conn
    with conn.cursor() as cur:          # read-only; nothing is committed
        cur.execute("SELECT a, b FROM t WHERE k = %s", (k,))
        row = cur.fetchone()            # conn.Row or None
    with conn.tx() as cur:              # commit on success, rollback on error
        cur.execute("INSERT INTO t (a) VALUES (%s)", (1,))

SQL is native MySQL (``%s`` placeholders). Connections come from
dbengine's pool, so DB selection and pooling stay in one place.
"""
from contextlib import contextmanager

import itertools

import pymysql

import dbengine

IntegrityError = dbengine.IntegrityError
OperationalError = dbengine.OperationalError


# Same class as the rows db.connect() returns with row_factory set.
Row = dbengine.Row


class Cursor:
    """Thin wrapper over a pymysql cursor that returns Row objects."""

    def __init__(self, raw_cursor):
        self._cur = raw_cursor
        # Set once a statement leaves session state behind (SET, GET_LOCK,
        # TEMPORARY TABLE), so the connection is closed instead of pooled.
        self.session_dirty = False

    def _note_session_state(self, sql):
        if dbengine._SESSION_STATE_RE.search(sql):
            self.session_dirty = True

    # Params are always passed (an empty tuple when there are none), so
    # pymysql always %-formats and a literal % is always written %%.
    # ProgrammingError (e.g. a missing table) is raised as OperationalError,
    # as dbengine does, so `except OperationalError` catches it.
    def execute(self, sql, params=()):
        self._note_session_state(sql)
        try:
            self._cur.execute(sql, tuple(params))
        except pymysql.err.ProgrammingError as e:
            raise dbengine._wrap_error(e) from e
        return self

    def executemany(self, sql, seq_of_params):
        self._note_session_state(sql)
        try:
            self._cur.executemany(sql, [tuple(p) for p in seq_of_params])
        except pymysql.err.ProgrammingError as e:
            raise dbengine._wrap_error(e) from e
        return self

    def _keys(self):
        return [d[0] for d in self._cur.description] if self._cur.description else []

    def fetchone(self):
        row = self._cur.fetchone()
        return None if row is None else Row(self._keys(), tuple(row))

    def fetchall(self):
        keys = self._keys()
        return [Row(keys, tuple(r)) for r in self._cur.fetchall()]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size else self._cur.fetchmany()
        keys = self._keys()
        return [Row(keys, tuple(r)) for r in rows]

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                return
            yield row

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description


def _shared_cursor(raw):
    cur = raw.cursor()
    try:
        yield Cursor(cur)
    finally:
        cur.close()


_savepoint_ids = itertools.count(1)


def _shared_tx(raw):
    """tx() inside rollback_tx(): the shared transaction is never committed,
    so a SAVEPOINT stands in for it. On an exception the block's own
    statements are rolled back to the savepoint; earlier work stays."""
    name = f"repo_tx_{next(_savepoint_ids)}"
    cur = raw.cursor()
    try:
        cur.execute(f"SAVEPOINT {name}")
        try:
            yield Cursor(cur)
        except BaseException:
            try:
                cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
            except Exception:  # noqa: BLE001 - e.g. an implicit commit (DDL) dropped it
                pass
            raise
        try:
            cur.execute(f"RELEASE SAVEPOINT {name}")
        except pymysql.err.OperationalError:
            pass                    # savepoint already gone (implicit commit)
    finally:
        cur.close()


def _acquire():
    raw = dbengine._pool_acquire() if dbengine._POOL_ENABLED else None
    return raw if raw is not None else dbengine._open_raw()


@contextmanager
def cursor():
    """Read cursor on a pooled connection. Never commits: the pool rolls the
    connection back when it is released."""
    shared = dbengine._shared_raw.get()
    if shared is not None:          # inside rollback_tx(): use its connection
        yield from _shared_cursor(shared)
        return
    raw = _acquire()
    poolable = True
    try:
        cur = Cursor(raw.cursor())
        try:
            yield cur
        finally:
            if cur.session_dirty:
                poolable = False
            cur._cur.close()
    except BaseException:
        poolable = False
        raise
    finally:
        dbengine._pool_release(raw, poolable)


@contextmanager
def tx():
    """Cursor in a transaction: commit on success, rollback on exception.
    Inside rollback_tx() it is a SAVEPOINT instead: an exception rolls back
    only this block's statements."""
    shared = dbengine._shared_raw.get()
    if shared is not None:          # inside rollback_tx(): never commits
        yield from _shared_tx(shared)
        return
    raw = _acquire()
    poolable = True
    try:
        cur = Cursor(raw.cursor())
        try:
            yield cur
            raw.commit()
        except BaseException:
            try:
                raw.rollback()
            except Exception:  # noqa: BLE001
                poolable = False
            raise
        finally:
            if cur.session_dirty:
                poolable = False
            cur._cur.close()
    finally:
        dbengine._pool_release(raw, poolable)


@contextmanager
def rollback_tx():
    """Cursor in a transaction that is always rolled back, on a dedicated
    connection that is closed afterwards (never pooled).

    Inside the block, every db.connect() / dbengine.connect() and
    repo.conn.cursor() / tx() made in the same context (thread or asyncio
    task; contextvars) uses this same connection, with commit() and close()
    as no-ops. So code that writes and commits on its own connections (the
    plan extractors) can be dry-run: nothing it writes persists. Other
    threads and requests are unaffected.
    """
    raw = dbengine._open_raw()
    token = dbengine._shared_raw.set(raw)
    try:
        cur = raw.cursor()
        try:
            yield Cursor(cur)
        finally:
            cur.close()
    finally:
        dbengine._shared_raw.reset(token)
        try:
            raw.rollback()
        finally:
            raw.close()
