"""v1 vs v2 equivalence of repo.ipt (Task 7e1).

The same rows are seeded into v1's ipt_table and v2's ipt_monthly (as the
migration loads them). Every write runs through repo.ipt on v1 and
repo.v2.ipt on v2; after each step both sides must agree on the outcome
(result, or exception type and args), the activity-log entries, every read
(cursor helpers on tuple and Row cursors, canonical form: order, key names
and types count) and the stored rows.
"""
import pytest

import dbengine
from repo import conn as rc
from repo import ipt as i1
from repo.v2 import _keys
from repo.v2 import ipt as i2
from v2dual import assert_same_reads, on_cursor, record_activity, run_step

ROW = dbengine.Row
MONTHS = ["2025-03", "2025-04", "2025-05", "2025-06", "2099-01"]


def _r(month, item, frm, to, unit="T", so=0, plan=None, actual=None, pt=None, at=None):
    return {"report_month": month, "item": item, "from_plant": frm, "to_plant": to, "unit": unit,
            "sort_order": so, "plan": plan, "actual": actual, "plan_tonnage": pt, "actual_tonnage": at}


SEED = [
    _r("2025-04", "CC Slabs", "BSP", "RSP", "T", 2, 100.0, 90.5),
    _r("2025-04", "BF Coke", "DSP", "ISP", "Rake", 1, 10, 13, 29583.0, 30000.5),
    _r("2025-04", "BF Coke", "BSL", "RSP", "Rake", 1, 2.0, None),
    _r("2025-05", "BF Coke", "BSP", "RSP", "Rake", 1, 2.0, 3.0),          # first seen in May
    _r("2025-05", "BF Coke", "DSP", "ISP", "Rake", 1, 4.0, 3.0, None, 7310.0),
    _r("2025-05", "CC Slabs", "BSP", "RSP", None, None, None, None),
    _r("2025-06", "Blooms", "BSP", "DSP", "T", 0, 1e-3, 0.1),
    _r("2025-03", "", "RSP", "BSP", "T", 5, 1.0, 1.0),                     # blank item
]
MONTH_SETS = [["2025-04"], ["2025-04", "2025-05"], ["2025-05", "2025-04", "2025-06"], MONTHS, ["2024-01"]]


@pytest.fixture
def seeded(dual):
    dual.seed_simple("ipt_table", SEED)
    return dual


def _reads(m):
    out = {}
    for rf, name in ((None, "tuple"), (ROW, "row")):
        def c(fn):
            return on_cursor(fn, rf)(m)
        out[("items", name)] = c(lambda md, cur: md.items(cur))
        out[("report_months", name)] = c(lambda md, cur: md.report_months(cur))
        for mo in MONTHS + ["2025-04 "]:
            out[("entry", name, mo)] = c(lambda md, cur: md.entry_rows(cur, mo))
            out[("month_values", name, mo)] = c(lambda md, cur: md.month_value_rows(cur, mo))
        for ms in MONTH_SETS:
            out[("routes", name, tuple(ms))] = c(lambda md, cur: md.routes(cur, ms))
            out[("plan_actual", name, tuple(ms))] = c(lambda md, cur: md.plan_actual_rows(cur, ms))
            out[("cum", name, tuple(ms))] = c(lambda md, cur: md.cum_value_rows(cur, ms))
            for its in (["BF Coke"], ["bf coke", "CC Slabs"], ["None"]):
                out[("items_sum", name, tuple(ms), tuple(its))] = c(
                    lambda md, cur: md.items_actual_sum_row(cur, ms, its))
    for mo in MONTHS:
        out[("any", mo)] = m.any_row_for_month(mo)
    return out


@pytest.fixture
def step(seeded, monkeypatch):
    activity = record_activity(monkeypatch)

    def go(fn):
        return run_step(seeded, i1, i2, fn, reads=_reads, tables=("ipt_table",), activity=activity)
    return go


def test_seeded_reads_agree(seeded):
    r = assert_same_reads(seeded, i1, i2, _reads)
    assert r[("cum", "tuple", ("2025-04", "2025-05"))] != r[("cum", "tuple", ("2025-04",))]


def test_save_ipt_entry(step):
    for fn in (lambda m: m.save_ipt_entry("2025-04", "CC Slabs", "BSP", "RSP", "T", 3, 1.0, 2.0),  # update
               lambda m: m.save_ipt_entry("2025-04", "bf coke", "dsp", "isp", "Rake", 1, 5, 6, 7.5, 8.5),
               lambda m: m.save_ipt_entry("2025-06", "Pig Iron", "RSP", "BSP"),                    # defaults
               lambda m: m.save_ipt_entry("2099-01", "New", "XYZ", "QQ", None, None),               # new plants
               lambda m: m.save_ipt_entry("2025-05  ", "BF Coke", "BSP", "RSP", "Rake", 9),         # cut; old None
               lambda m: m.save_ipt_entry("2025-05x", "BF Coke", "BSP", "RSP"),                     # 1406
               lambda m: m.save_ipt_entry(None, "BF Coke", "BSP", "RSP"),                           # 1048
               lambda m: m.save_ipt_entry("2025-05", None, "BSP", "RSP"),                           # 1048 item
               lambda m: m.save_ipt_entry("2025-05", "I" * 65, "BSP", "RSP"),                       # 1406 item
               lambda m: m.save_ipt_entry("2025-05", "X", "P" * 33, "RSP"),                         # 1406 from
               lambda m: m.save_ipt_entry("2025-05", "X", "BSP", None),                             # 1048 to
               lambda m: m.save_ipt_entry("2025-05", "X", "BSP", "RSP", "U" * 33),                  # 1406 unit
               lambda m: m.save_ipt_entry("2025-05", "X", "BSP", "RSP", "T", 0, "abc")):            # 1265 plan
        step(fn)


def test_delete_ipt_entry(step):
    for fn in (lambda m: m.delete_ipt_entry("2025-04", "CC Slabs", "BSP", "RSP"),
               lambda m: m.delete_ipt_entry("2025-04", "CC Slabs", "BSP", "RSP"),        # gone: 0
               lambda m: m.delete_ipt_entry("2025-05", "bf coke", "dsp", "ISP"),         # ai_ci
               lambda m: m.delete_ipt_entry("2025-04 ", "BF Coke", "BSL", "RSP"),        # raw month: nothing
               lambda m: m.delete_ipt_entry("1999-01", "BF Coke", "XYZ", "RSP")):
        step(fn)


def test_keys_v2_cannot_hold(seeded):
    """v1 stored a 9..32-character plant and a short non-month; v2 refuses
    them before writing anything (parity_exceptions.md §2)."""
    for fn in (lambda m: m.save_ipt_entry("2025-04", "X", "LONGPLANT", "RSP"),
               lambda m: m.save_ipt_entry("2025-04", "X", "BSP", "LONGPLANT"),
               lambda m: m.save_ipt_entry("2025-4", "X", "BSP", "RSP")):
        with seeded.v1():
            fn(i1)
        n = seeded.data_version(2)
        with seeded.v2():
            with pytest.raises(_keys.OutOfModelError):
                fn(i2)
        assert seeded.data_version(2) == n


def test_every_v2_write_bumps_and_a_dry_run_does_not(seeded):
    writes = [lambda: i2.save_ipt_entry("2025-04", "CC Slabs", "BSP", "RSP", "T", 0, 9.0),
              lambda: i2.delete_ipt_entry("2025-06", "Blooms", "BSP", "DSP"),
              lambda: i2.delete_ipt_entry("2025-06", "Nothing", "BSP", "DSP")]       # bumps even when 0
    with seeded.v2():
        for w in writes:
            n = seeded.data_version(2)
            w()
            assert seeded.data_version(2) > n
        before = {k: repr(v) for k, v in _reads(i2).items()}
        n = seeded.data_version(2)
        with rc.rollback_tx():
            i2.save_ipt_entry("2098-01", "Dry", "DRY", "DRY2")
            i2.delete_ipt_entry("2025-04", "BF Coke", "DSP", "ISP")
            assert {k: repr(v) for k, v in _reads(i2).items()} != before
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(i2).items()} == before
    assert seeded.sql(2, "SELECT COUNT(*) FROM plant WHERE plant_code IN ('DRY', 'DRY2')")[0][0] == 0
