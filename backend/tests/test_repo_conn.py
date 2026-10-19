"""repo.conn: native MySQL connection helper (cursor / tx / Row / errors)."""
import pytest

from repo import conn as rc


def _count(where="1=1"):
    with rc.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM mou_plan_table WHERE {where}")
        return cur.fetchone()["n"]


def test_tx_commits_on_success(mysql_db):
    with rc.tx() as cur:
        cur.execute("INSERT INTO mou_plan_table VALUES (%s, %s, %s, %s)",
                    ("2026-04", "BSP", "Hot Metal", 1.5))
    assert _count("plant_name='BSP'") == 1


def test_tx_rolls_back_on_exception(mysql_db):
    with pytest.raises(RuntimeError):
        with rc.tx() as cur:
            cur.execute("INSERT INTO mou_plan_table VALUES (%s, %s, %s, %s)",
                        ("2026-04", "BSP", "Hot Metal", 1.5))
            raise RuntimeError("boom")
    assert _count() == 0


def test_row_access_by_index_key_and_mixed_case(mysql_db):
    with rc.tx() as cur:
        cur.execute("INSERT INTO mou_plan_table VALUES (%s, %s, %s, %s)",
                    ("2026-04", "BSP", "Hot Metal", 1.5))
    with rc.cursor() as cur:
        cur.execute("SELECT plant_name, month_actual FROM mou_plan_table")
        row = cur.fetchone()
    assert isinstance(row, rc.Row)
    assert row[0] == "BSP" and row[1] == 1.5 and row[-1] == 1.5
    assert row["plant_name"] == "BSP"
    assert row["Plant_Name"] == "BSP" and row["MONTH_ACTUAL"] == 1.5
    assert row.keys() == ["plant_name", "month_actual"]
    assert dict(row) == {"plant_name": "BSP", "month_actual": 1.5}
    assert list(row) == ["BSP", 1.5] and len(row) == 2


def test_duplicate_pk_raises_integrity_error(mysql_db):
    sql = "INSERT INTO mou_plan_table VALUES (%s, %s, %s, %s)"
    with rc.tx() as cur:
        cur.execute(sql, ("2026-04", "BSP", "Hot Metal", 1.0))
    with pytest.raises(rc.IntegrityError):
        with rc.tx() as cur:
            cur.execute(sql, ("2026-04", "BSP", "Hot Metal", 2.0))
    assert _count() == 1


def test_error_classes_are_pymysql_classes():
    import pymysql
    assert rc.OperationalError is pymysql.err.OperationalError
    assert rc.IntegrityError is pymysql.err.IntegrityError


def test_double_percent_without_params_is_a_literal_percent(mysql_db):
    # Project rule: a literal % in SQL is always written %%, params or not.
    with rc.cursor() as cur:
        cur.execute("SELECT '50%%' AS v")
        assert cur.fetchone()["v"] == "50%"


def test_double_percent_in_executemany(mysql_db):
    with rc.tx() as cur:
        cur.executemany(
            "INSERT INTO mou_plan_table VALUES (%s, CONCAT(%s, '%%'), %s, %s)",
            [("2026-04", "BSP", "Hot Metal", 1.0), ("2026-04", "DSP", "Hot Metal", 2.0)])
    with rc.cursor() as cur:
        cur.execute("SELECT plant_name FROM mou_plan_table ORDER BY plant_name")
        assert [r[0] for r in cur.fetchall()] == ["BSP%", "DSP%"]


def test_rollback_tx_routes_all_connections_and_rolls_back(mysql_db):
    import threading

    import db
    ins = "INSERT INTO mou_plan_table VALUES (%s, %s, %s, %s)"

    def other_thread():
        c = db.connect()
        c.execute(ins, ("2026-04", "DSP", "Hot Metal", 3.0))
        c.commit()
        c.close()

    with rc.rollback_tx() as cur:
        # Code that commits on its own connections (like the plan extractors).
        c = db.connect()
        c.execute(ins, ("2026-04", "BSP", "Hot Metal", 1.0))
        c.commit()
        c.close()
        with rc.tx() as cur2:
            cur2.execute(ins, ("2026-04", "RSP", "Hot Metal", 2.0))
        cur.execute("SELECT COUNT(*) AS n FROM mou_plan_table")
        assert cur.fetchone()["n"] == 2          # sees its own writes
        # Other threads (other requests) are not routed into the shared tx.
        t = threading.Thread(target=other_thread)
        t.start()
        t.join()
    with rc.cursor() as cur:
        cur.execute("SELECT plant_name FROM mou_plan_table")
        assert [r[0] for r in cur.fetchall()] == ["DSP"]
    # Outside the block, connect() uses the pool again.
    c = db.connect()
    c.execute(ins, ("2026-05", "BSP", "Hot Metal", 4.0))
    c.commit()
    c.close()
    assert _count() == 2


def test_missing_table_raises_operational_error(mysql_db):
    with pytest.raises(rc.OperationalError):
        with rc.cursor() as cur:
            cur.execute("SELECT 1 FROM no_such_table_xyz")
    with pytest.raises(rc.OperationalError):
        with rc.tx() as cur:
            cur.executemany("INSERT INTO no_such_table_xyz VALUES (%s)", [(1,)])


# ── Carry-overs: session-dirty connections and shared-mode tx() ────────────

def _idle_raws():
    import dbengine
    return [r for r, _ in dbengine._pool_idle]


@pytest.mark.parametrize("ctx", ["cursor", "tx"])
@pytest.mark.parametrize("stmt", [
    "SET @repo_conn_x = 1",
    "SELECT GET_LOCK('repo_conn_test_lock', 0)",
    "CREATE TEMPORARY TABLE repo_conn_tmp (a INT)",
])
def test_session_state_sql_makes_connection_unpoolable(mysql_db, monkeypatch, ctx, stmt):
    import dbengine
    monkeypatch.setattr(dbengine, "_POOL_ENABLED", True)
    dbengine._pool_clear()
    with getattr(rc, ctx)() as cur:
        raw = cur._cur.connection
        cur.execute(stmt)
    assert raw not in _idle_raws()


@pytest.mark.parametrize("ctx", ["cursor", "tx"])
def test_session_state_sql_in_executemany_makes_connection_unpoolable(mysql_db, monkeypatch, ctx):
    import dbengine
    monkeypatch.setattr(dbengine, "_POOL_ENABLED", True)
    dbengine._pool_clear()
    with getattr(rc, ctx)() as cur:
        raw = cur._cur.connection
        cur.executemany("SET @repo_conn_y = %s", [(1,)])
    assert raw not in _idle_raws()


def test_plain_sql_connection_is_pooled(mysql_db, monkeypatch):
    import dbengine
    monkeypatch.setattr(dbengine, "_POOL_ENABLED", True)
    dbengine._pool_clear()
    with rc.cursor() as cur:
        raw = cur._cur.connection
        cur.execute("SELECT 1")
    assert raw in _idle_raws()


def test_shared_mode_tx_failure_undoes_only_its_own_statements(mysql_db):
    ins = "INSERT INTO mou_plan_table VALUES (%s, %s, %s, %s)"
    with rc.rollback_tx() as outer:
        outer.execute(ins, ("2026-04", "BSP", "Hot Metal", 1.0))
        with rc.tx() as cur:
            cur.execute(ins, ("2026-04", "DSP", "Hot Metal", 2.0))
        with pytest.raises(RuntimeError):
            with rc.tx() as cur:
                cur.execute(ins, ("2026-04", "RSP", "Hot Metal", 3.0))
                raise RuntimeError("boom")
        outer.execute("SELECT plant_name FROM mou_plan_table ORDER BY plant_name")
        assert [r[0] for r in outer.fetchall()] == ["BSP", "DSP"]
    assert _count() == 0


def test_shared_mode_nested_tx_failure_keeps_outer_tx_statements(mysql_db):
    ins = "INSERT INTO mou_plan_table VALUES (%s, %s, %s, %s)"
    with rc.rollback_tx() as outer:
        with rc.tx() as cur:
            cur.execute(ins, ("2026-04", "BSP", "Hot Metal", 1.0))
            with pytest.raises(RuntimeError):
                with rc.tx() as inner:
                    inner.execute(ins, ("2026-04", "RSP", "Hot Metal", 3.0))
                    raise RuntimeError("boom")
            cur.execute(ins, ("2026-04", "DSP", "Hot Metal", 2.0))
        outer.execute("SELECT plant_name FROM mou_plan_table ORDER BY plant_name")
        assert [r[0] for r in outer.fetchall()] == ["BSP", "DSP"]
    assert _count() == 0
