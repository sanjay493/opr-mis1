"""repo.production primitives: values() / upsert() / delete() over the
actual / ABP / MoU production tables."""
import pytest

from repo import conn as rc
from repo import production as rp

_TABLES = {"actual": "production_table", "abp": "production_plan_table",
           "mou": "mou_plan_table"}
MEASURES = list(_TABLES)


def _insert(table, rows):
    with rc.tx() as cur:
        cur.executemany(f"INSERT INTO {table} (report_month, plant_name, item_name, month_actual) "
                        "VALUES (%s, %s, %s, %s)", rows)


def _all(table):
    with rc.cursor() as cur:
        cur.execute(f"SELECT report_month, plant_name, item_name, month_actual FROM {table}")
        return {(r[0], r[1], r[2]): r[3] for r in cur.fetchall()}


_SEED = [
    ("2026-04", "BSP", "Hot Metal", 10.0),
    ("2026-04", "BSP", "Crude Steel", 8.0),
    ("2026-04", "DSP", "Hot Metal", 5.0),
    ("2026-05", "BSP", "Hot Metal", 11.0),
    ("2026-05", "DSP", "Hot Metal", None),
]


@pytest.mark.parametrize("measure", MEASURES)
def test_values_absent_row_is_absent_key(mysql_db, measure):
    _insert(_TABLES[measure], _SEED)
    got = rp.values(["2026-04"], ["BSP"], ["Saleable Steel"], measure)
    assert got == {}
    got = rp.values(["2026-06"], None, None, measure)
    assert got == {}


@pytest.mark.parametrize("measure", MEASURES)
def test_values_null_value_is_present_key_with_none(mysql_db, measure):
    _insert(_TABLES[measure], _SEED)
    got = rp.values(["2026-05"], ["DSP"], ["Hot Metal"], measure)
    assert got == {("2026-05", "DSP", "Hot Metal"): None}
    assert ("2026-05", "DSP", "Hot Metal") in got


@pytest.mark.parametrize("measure", MEASURES)
def test_values_filters(mysql_db, measure):
    _insert(_TABLES[measure], _SEED)
    # plants/items None = all
    assert rp.values(["2026-04", "2026-05"], None, None, measure) == {
        (m, p, i): v for m, p, i, v in _SEED}
    assert rp.values(["2026-04"], None, None, measure) == {
        ("2026-04", "BSP", "Hot Metal"): 10.0,
        ("2026-04", "BSP", "Crude Steel"): 8.0,
        ("2026-04", "DSP", "Hot Metal"): 5.0,
    }
    assert rp.values(["2026-04", "2026-05"], ["BSP"], None, measure) == {
        ("2026-04", "BSP", "Hot Metal"): 10.0,
        ("2026-04", "BSP", "Crude Steel"): 8.0,
        ("2026-05", "BSP", "Hot Metal"): 11.0,
    }
    assert rp.values(["2026-04", "2026-05"], None, ["Hot Metal"], measure) == {
        ("2026-04", "BSP", "Hot Metal"): 10.0,
        ("2026-04", "DSP", "Hot Metal"): 5.0,
        ("2026-05", "BSP", "Hot Metal"): 11.0,
        ("2026-05", "DSP", "Hot Metal"): None,
    }
    assert rp.values(iter(["2026-04"]), iter(["DSP"]), iter(["Hot Metal"]), measure) == {
        ("2026-04", "DSP", "Hot Metal"): 5.0}
    # Empty filters select nothing (not "all").
    assert rp.values([], None, None, measure) == {}
    assert rp.values(["2026-04"], [], None, measure) == {}
    assert rp.values(["2026-04"], None, [], measure) == {}


def test_values_measures_read_their_own_table(mysql_db):
    _insert("production_table", [("2026-04", "BSP", "Hot Metal", 1.0)])
    _insert("production_plan_table", [("2026-04", "BSP", "Hot Metal", 2.0)])
    _insert("mou_plan_table", [("2026-04", "BSP", "Hot Metal", 3.0)])
    key = ("2026-04", "BSP", "Hot Metal")
    assert rp.values(["2026-04"], None, None, "actual") == {key: 1.0}
    assert rp.values(["2026-04"], None, None, "abp") == {key: 2.0}
    assert rp.values(["2026-04"], None, None, "mou") == {key: 3.0}


def test_unknown_measure_raises(mysql_db):
    with pytest.raises(ValueError):
        rp.values(["2026-04"], None, None, "plan")
    with pytest.raises(ValueError):
        rp.upsert("plan", [("2026-04", "BSP", "Hot Metal", 1.0)])
    with pytest.raises(ValueError):
        rp.delete("plan", "2026-04", "BSP")


@pytest.mark.parametrize("measure", MEASURES)
def test_upsert_inserts_and_updates(mysql_db, measure):
    table = _TABLES[measure]
    _insert(table, [("2026-04", "BSP", "Hot Metal", 10.0)])
    rp.upsert(measure, [
        ("2026-04", "BSP", "Hot Metal", 12.5),       # update
        ("2026-04", "BSP", "Crude Steel", 9.0),      # insert
        ("2026-04", "DSP", "Hot Metal", None),       # insert NULL
    ])
    assert _all(table) == {
        ("2026-04", "BSP", "Hot Metal"): 12.5,
        ("2026-04", "BSP", "Crude Steel"): 9.0,
        ("2026-04", "DSP", "Hot Metal"): None,
    }
    rp.upsert(measure, iter([("2026-04", "DSP", "Hot Metal", 4.0)]))
    assert _all(table)[("2026-04", "DSP", "Hot Metal")] == 4.0
    rp.upsert(measure, [])                          # no-op
    assert len(_all(table)) == 3
    # Other measures' tables are untouched.
    for other, t in _TABLES.items():
        if other != measure:
            assert _all(t) == {}


@pytest.mark.parametrize("measure", MEASURES)
def test_delete_without_items_deletes_month_plant(mysql_db, measure):
    table = _TABLES[measure]
    _insert(table, _SEED)
    rp.delete(measure, "2026-04", "BSP")
    assert set(_all(table)) == {
        ("2026-04", "DSP", "Hot Metal"),
        ("2026-05", "BSP", "Hot Metal"),
        ("2026-05", "DSP", "Hot Metal"),
    }


@pytest.mark.parametrize("measure", MEASURES)
def test_delete_with_items_deletes_only_those_items(mysql_db, measure):
    table = _TABLES[measure]
    _insert(table, _SEED)
    rp.delete(measure, "2026-04", "BSP", items=["Crude Steel", "Not There"])
    assert set(_all(table)) == {
        ("2026-04", "BSP", "Hot Metal"),
        ("2026-04", "DSP", "Hot Metal"),
        ("2026-05", "BSP", "Hot Metal"),
        ("2026-05", "DSP", "Hot Metal"),
    }
    rp.delete(measure, "2026-04", "BSP", items=[])   # empty list deletes nothing
    assert len(_all(table)) == 4
