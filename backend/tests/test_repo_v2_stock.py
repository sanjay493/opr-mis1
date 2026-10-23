"""v1 vs v2 equivalence of repo.stock (Task 7e1).

The same rows are seeded into v1's stock_table / sail_sales_table /
sail_stock_snapshot_table and v2's stock_monthly / sail_sales_monthly /
sail_stock_snapshot (as the migration loads them). Every write runs
through _v1_frozen.stock on v1 and repo.stock (v2) on v2; after each step both
sides must agree on the outcome (result, or exception type and args), the
activity-log entries, every read (cursor helpers on tuple and Row cursors,
canonical form: order, key names and types count) and the stored rows
(v2 rendered back to v1 columns and spellings).
"""
import pytest

import dbengine
from repo import conn as rc
from _v1_frozen import stock as s1
from repo import _keys
from repo import stock as s2
from v2dual import on_cursor, record_activity, run_step

ROW = dbengine.Row
MONTHS = ["2025-03", "2025-04", "2025-05", "2099-01"]
PLANTS = ["BSP", "bsp", "DSP", "RSP", "XYZ"]
TABLES = ("stock_table", "sail_sales_table", "sail_stock_snapshot_table")

STOCK = [
    {"stock_month": "2025-04", "plant_name": "BSP", "item_type": "Coal", "stock_type": "", "stock": 100.5},
    {"stock_month": "2025-04", "plant_name": "BSP", "item_type": "Coal", "stock_type": "Imported", "stock": 7},
    {"stock_month": "2025-04", "plant_name": "BSP", "item_type": "Ore", "stock_type": "", "stock": None},
    {"stock_month": "2025-04", "plant_name": "DSP", "item_type": "Coal", "stock_type": "", "stock": 50.25},
    {"stock_month": "2025-05", "plant_name": "BSP", "item_type": "Coal", "stock_type": "", "stock": 99.0},
    {"stock_month": "2025-03", "plant_name": "RSP", "item_type": "Lime", "stock_type": "x", "stock": 1e-3},
]
SALES = [
    {"report_month": "2025-04", "item_name": "Fp Sales", "data_json": '{"b": [1, 2.5], "a": 1}'},
    {"report_month": "2025-04", "item_name": "Exports", "data_json": None},
    {"report_month": "2025-05", "item_name": "Fp Sales", "data_json": '{"month_actual": 746.0}'},
]
SNAPS = [
    {"snapshot_date": "2025-04-01", "item_name": "Plants", "value": 305.0},
    {"snapshot_date": "2025-04-01", "item_name": "Stockyards", "value": None},
    {"snapshot_date": "2025-05-01", "item_name": "Plants", "value": 290},
]
DATES = ["2025-04-01", "2025-05-01", "2025-04-01 ", "2025-4-1", "abc", None, "2026-01-01"]


@pytest.fixture
def seeded(dual):
    dual.seed_simple("stock_table", STOCK)
    dual.seed_simple("sail_sales_table", SALES)
    dual.seed_simple("sail_stock_snapshot_table", SNAPS)
    return dual


def _reads(m):
    out = {}
    for rf, name in ((None, "tuple"), (ROW, "row")):
        def c(fn):
            return on_cursor(fn, rf)(m)
        for mo in MONTHS + ["2025-04 "]:
            for p in PLANTS:
                out[("plant_month", name, mo, p)] = c(lambda md, cur: md.plant_month_rows(cur, p, mo))
            for item in ("Fp Sales", "fp sales", "Exports", "None"):
                out[("sales", name, mo, item)] = c(lambda md, cur: md.sales_data_row(cur, mo, item))
        for months in (MONTHS, ["2025-04"], ["2025-05", "2025-03"]):
            out[("month_rows", name, tuple(months))] = c(lambda md, cur: md.month_rows(cur, months))
        for d in DATES:
            for item in ("Plants", "plants", "Stockyards"):
                out[("snap", name, d, item)] = c(lambda md, cur: md.snapshot_value_row(cur, d, item))
    for mo in MONTHS:
        out[("plants", mo)] = sorted(m.plants_for_month(mo))
    return out


@pytest.fixture
def step(seeded, monkeypatch):
    activity = record_activity(monkeypatch)

    def go(fn):
        return run_step(seeded, s1, s2, fn, reads=_reads, tables=TABLES, activity=activity)
    return go


def test_seeded_reads_agree(seeded):
    from v2dual import assert_same_reads
    r = assert_same_reads(seeded, s1, s2, _reads)
    assert r[("snap", "tuple", "2025-04-01", "Plants")] != r[("snap", "tuple", "2025-4-1", "Plants")]


def test_save_stock_entry(step):
    for fn in (lambda m: m.save_stock_entry("2025-04", "BSP", "Coal", "", 1.5),            # update
               lambda m: m.save_stock_entry("2025-04", "bsp", "coal", "imported", 2.5),    # ai_ci: stored row
               lambda m: m.save_stock_entry("2025-05", "DSP", "Coal"),                     # new, stock NULL
               lambda m: m.save_stock_entry("2099-01", "XYZ", "Coal", "", 3.0),            # new month and plant
               lambda m: m.save_stock_entry("2025-04 ", "BSP", "Ore", "", 4.0),            # cut month; old None
               lambda m: m.save_stock_entry("2025-04x", "BSP", "Ore", "", 4.0),            # 1406 stock_month
               lambda m: m.save_stock_entry(None, "BSP", "Ore", "", 4.0),                  # 1048
               lambda m: m.save_stock_entry("2025-04", "P" * 33, "Ore", "", 4.0),          # 1406 plant_name
               lambda m: m.save_stock_entry("2025-04", "BSP", "O" * 65, "", 4.0),          # 1406 item_type
               lambda m: m.save_stock_entry("2025-04", "BSP", "Ore", None, 4.0),           # 1048 stock_type
               lambda m: m.save_stock_entry("2025-04", "BSP", "Ore", "", "abc")):          # 1265 stock
        step(fn)


def test_upsert_sales(step):
    for fn in (lambda m, c: m.upsert_sales(c, "2025-04", "Fp Sales", '{"z": 0, "a": [true, null]}'),
               lambda m, c: m.upsert_sales(c, "2025-04", "fp sales", '{"x": 1}'),          # ai_ci: stored row
               lambda m, c: m.upsert_sales(c, "2025-06", "New", None),
               lambda m, c: m.upsert_sales(c, "2099-02", "Fp Sales", "[]"),
               lambda m, c: m.upsert_sales(c, "2025-05   ", "Fp Sales", '{"cut": 1}'),
               lambda m, c: m.upsert_sales(c, "2025-05", "Fp Sales", "not json"),          # 3140
               lambda m, c: m.upsert_sales(c, "2025-05", "I" * 65, "{}"),                  # 1406
               lambda m, c: m.upsert_sales(c, "2025-055", "Fp Sales", "{}")):              # 1406
        step(on_cursor(fn, commit=True))


def test_upsert_stock_snapshot(step):
    for fn in (lambda m, c: m.upsert_stock_snapshot(c, "2025-04-01", "Plants", 1.0),
               lambda m, c: m.upsert_stock_snapshot(c, "2025-04-01", "plants", 2.0),        # ai_ci: stored row
               lambda m, c: m.upsert_stock_snapshot(c, "2025-06-01", "Stock In Transit", None),
               lambda m, c: m.upsert_stock_snapshot(c, "2025-05-01 ", "Plants", 3.0),       # cut date
               lambda m, c: m.upsert_stock_snapshot(c, "2025-05-011", "Plants", 3.0),       # 1406
               lambda m, c: m.upsert_stock_snapshot(c, None, "Plants", 3.0),                # 1048
               lambda m, c: m.upsert_stock_snapshot(c, "2025-05-01", None, 3.0),            # 1048
               lambda m, c: m.upsert_stock_snapshot(c, "2025-05-01", "I" * 33, 3.0)):       # 1406
        step(on_cursor(fn, commit=True))


def test_keys_v2_cannot_hold(seeded):
    """v1 stored a 9..32-character plant, a short non-month and a
    non-canonical snapshot date; v2 refuses them before writing anything
    (parity_exceptions.md §2)."""
    cases = [lambda m: m.save_stock_entry("2025-04", "LONGPLANT", "Coal", "", 1.0),
             lambda m: m.save_stock_entry("2025-4", "BSP", "Coal", "", 1.0),
             lambda m: on_cursor(lambda md, c: md.upsert_sales(c, "2025-4", "Fp Sales", "{}"), commit=True)(m),
             lambda m: on_cursor(lambda md, c: md.upsert_stock_snapshot(c, "2025-4-1", "Plants", 1.0),
                                 commit=True)(m)]
    for fn in cases:
        with seeded.v1():
            fn(s1)
        n = seeded.data_version(2)
        with seeded.v2():
            with pytest.raises(_keys.OutOfModelError):
                fn(s2)
        assert seeded.data_version(2) == n


V2_WRITES = [lambda: s2.save_stock_entry("2025-04", "BSP", "Coal", "", 9.0),
             lambda: on_cursor(lambda m, c: m.upsert_sales(c, "2025-04", "Fp Sales", "{}"), commit=True)(s2),
             lambda: on_cursor(lambda m, c: m.upsert_stock_snapshot(c, "2025-04-01", "Plants", 9.0),
                               commit=True)(s2)]


def test_every_v2_write_bumps_and_a_dry_run_does_not(seeded):
    with seeded.v2():
        for w in V2_WRITES:
            n = seeded.data_version(2)
            w()
            assert seeded.data_version(2) > n
        before = {k: repr(v) for k, v in _reads(s2).items()}
        n = seeded.data_version(2)
        with rc.rollback_tx():
            s2.save_stock_entry("2098-01", "DRY", "Coal", "", 1.0)
            on_cursor(lambda m, c: m.upsert_sales(c, "2025-04", "Fp Sales", '{"dry": 1}'))(s2)
            on_cursor(lambda m, c: m.upsert_stock_snapshot(c, "2025-04-01", "Plants", -1.0))(s2)
            assert {k: repr(v) for k, v in _reads(s2).items()} != before
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(s2).items()} == before
    assert seeded.sql(2, "SELECT COUNT(*) FROM plant WHERE plant_code = 'DRY'")[0][0] == 0
    assert seeded.sql(2, "SELECT COUNT(*) FROM cal_month WHERE report_month = '2098-01'")[0][0] == 0


def test_writes_on_a_caller_cursor_roll_back_with_it(seeded):
    def go(m):
        conn = dbengine.connect()
        try:
            cur = conn.cursor()
            m.upsert_sales(cur, "2025-04", "Fp Sales", '{"rolled": 1}')
            m.upsert_stock_snapshot(cur, "2025-04-01", "Plants", -5.0)
            conn.rollback()
        finally:
            conn.close()
    seeded.both(go, v1=s1, v2=s2)
    for t in TABLES:
        a, b = seeded.stored(t)
        assert a == b
