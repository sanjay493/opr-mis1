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


def test_missing_table_raises_operational_error(mysql_db):
    with pytest.raises(rc.OperationalError):
        with rc.cursor() as cur:
            cur.execute("SELECT 1 FROM no_such_table_xyz")
    with pytest.raises(rc.OperationalError):
        with rc.tx() as cur:
            cur.executemany("INSERT INTO no_such_table_xyz VALUES (%s)", [(1,)])
