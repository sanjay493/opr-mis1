"""MySQL connection reuse in dbengine (pool of raw PyMySQL connections).

Uses a fake raw connection so no MySQL server is needed: dbengine._open_raw
is monkeypatched to hand out FakeRaw objects, and the pool is reset around
each test.
"""

import threading
import time

import pytest

import dbengine


class FakeCursor:
    def __init__(self, raw):
        self.raw = raw
        self.description = None
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        self.raw.executed.append(sql)

    def fetchone(self):
        return (1,)

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeRaw:
    def __init__(self):
        self.executed = []
        self.rollbacks = 0
        self.closed = False
        self.ping_ok = True

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        self.rollbacks += 1

    def ping(self, reconnect=False):
        if not self.ping_ok:
            raise ConnectionError("gone away")

    def close(self):
        self.closed = True


@pytest.fixture
def fake_pool(monkeypatch):
    opened = []

    def _open():
        raw = FakeRaw()
        opened.append(raw)
        return raw

    monkeypatch.setattr(dbengine, "_open_raw", _open)
    monkeypatch.setattr(dbengine, "_POOL_ENABLED", True)
    dbengine._pool_clear()
    yield opened
    dbengine._pool_clear()


def test_closed_connection_is_reused(fake_pool):
    c1 = dbengine._mysql_connect()
    raw1 = c1._conn
    c1.close()
    c2 = dbengine._mysql_connect()
    assert c2._conn is raw1
    assert len(fake_pool) == 1


def test_close_rolls_back_before_pooling(fake_pool):
    c = dbengine._mysql_connect()
    raw = c._conn
    c.execute("SELECT 1")
    c.close()
    assert raw.rollbacks == 1
    assert not raw.closed


def test_double_close_does_not_pool_twice(fake_pool):
    c = dbengine._mysql_connect()
    c.close()
    c.close()
    a = dbengine._mysql_connect()
    b = dbengine._mysql_connect()
    assert a._conn is not b._conn


def test_use_after_close_raises(fake_pool):
    c = dbengine._mysql_connect()
    c.close()
    with pytest.raises(Exception):
        c.execute("SELECT 1")


def test_row_factory_is_fresh_per_connect(fake_pool):
    import sqlite3
    c = dbengine._mysql_connect()
    c.row_factory = sqlite3.Row
    c.close()
    c2 = dbengine._mysql_connect()
    assert c2.row_factory is None


@pytest.mark.parametrize("sql", [
    "SELECT GET_LOCK(?, 0)",
    "SET FOREIGN_KEY_CHECKS = 0",
    "CREATE TEMPORARY TABLE t (x INT)",
])
def test_session_state_connections_are_not_pooled(fake_pool, sql):
    c = dbengine._mysql_connect()
    raw = c._conn
    c.execute(sql)
    c.close()
    assert raw.closed
    c2 = dbengine._mysql_connect()
    assert c2._conn is not raw


def test_stale_idle_connection_is_replaced(fake_pool, monkeypatch):
    c = dbengine._mysql_connect()
    raw = c._conn
    c.close()
    raw.ping_ok = False
    # Make the pooled connection look idle past the ping threshold.
    monkeypatch.setattr(dbengine, "_POOL_PING_AFTER", 0.0)
    time.sleep(0.01)
    c2 = dbengine._mysql_connect()
    assert c2._conn is not raw
    assert raw.closed


def test_concurrent_checkouts_get_distinct_connections(fake_pool):
    held = []
    lock = threading.Lock()
    barrier = threading.Barrier(4)

    def worker():
        c = dbengine._mysql_connect()
        with lock:
            held.append(c._conn)
        barrier.wait()
        c.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({id(r) for r in held}) == 4


def test_pool_keeps_at_most_max_idle(fake_pool, monkeypatch):
    monkeypatch.setattr(dbengine, "_POOL_MAX_IDLE", 2)
    conns = [dbengine._mysql_connect() for _ in range(4)]
    raws = [c._conn for c in conns]
    for c in conns:
        c.close()
    assert sum(r.closed for r in raws) == 2


def test_pool_disabled_closes_for_real(fake_pool, monkeypatch):
    monkeypatch.setattr(dbengine, "_POOL_ENABLED", False)
    c = dbengine._mysql_connect()
    raw = c._conn
    c.close()
    assert raw.closed
    c2 = dbengine._mysql_connect()
    assert c2._conn is not raw
