"""v1 vs v2 equivalence of repo.cost_trend (Task 7e1).

The same rows are seeded into v1's and v2's cost_trend_annual /
cost_trend_monthly (as the migration loads them). Every write runs through
_v1_frozen.cost_trend on v1 and repo.cost_trend (v2) on v2; after each step both
sides must agree on the outcome (result, or exception type and args), every
read (canonical form: dict key order and types count) and the stored rows.
"""
import pytest

from repo import conn as rc
from _v1_frozen import cost_trend as c1
from repo import _keys
from repo import cost_trend as c2
from v2dual import assert_same_reads, run_step

FYS = ["2023-24", "2024-25", "2025-26"]
MONTHS = ["2025-04", "2025-05", "2025-06", "2099-01"]
PRODUCTS = ["HM", "hm", "CS", "SS", "COKE"]
TABLES = ("cost_trend_annual", "cost_trend_monthly")


def _a(fy, product, ct, plant, value):
    return {"fy": fy, "product": product, "cost_type": ct, "plant": plant, "value": value}


def _m(month, product, ct, plant, mv, tmv):
    return {"report_month": month, "product": product, "cost_type": ct, "plant": plant, "month_value": mv,
            "till_month_value": tmv}


ANNUAL = [_a("2024-25", "HM", "VARIABLE", "SAIL", 20000.5), _a("2024-25", "HM", "VARIABLE", "BSP", 19000),
          _a("2024-25", "HM", "FIXED", "DSP", 3000.25), _a("2024-25", "HM", "OTHER", "ISP", 1.0),
          _a("2025-26", "HM", "VARIABLE", "RSP", None), _a("2023-24", "CS", "TOTAL", "BSL", 30000.0),
          _a("2024-25", "HM", "FIXED", "ZZPLANT", 7.0)]
MONTHLY = [_m("2025-04", "HM", "VARIABLE", "SAIL", 21000.0, 20500.5), _m("2025-04", "HM", "FIXED", "BSP", None, 3000),
           _m("2025-04", "HM", "VARIABLE", "BSP", 18000, None), _m("2025-05", "CS", "FIXED", "ISP", 1.5, 2.5),
           _m("2025-05", "HM", "VARIABLE", "DSP", 1e-3, None), _m("2025-06", "HM", "OTHER", "RSP", 4.0, 5.0)]


@pytest.fixture
def seeded(dual):
    dual.seed_simple("cost_trend_annual", ANNUAL)
    dual.seed_simple("cost_trend_monthly", MONTHLY)
    return dual


def _reads(m):
    out = {}
    for p in PRODUCTS:
        for fys in (FYS, ["2024-25"], ["2025-26", "2024-25"], [], ["2024-25", "2024-25"]):
            out[("annual", p, tuple(fys))] = m.get_cost_trend_annual(p, fys)
        for ms in (MONTHS, ["2025-04"], ["2025-05", "2025-04"], []):
            out[("monthly", p, tuple(ms))] = m.get_cost_trend_monthly(p, ms)
    for mo in MONTHS + ["2025-04 "]:
        out[("any", mo)] = m.monthly_any_row(mo)
    return out


@pytest.fixture
def step(seeded):
    def go(fn):
        return run_step(seeded, c1, c2, fn, reads=_reads, tables=TABLES)
    return go


def test_seeded_reads_agree(seeded):
    r = assert_same_reads(seeded, c1, c2, _reads)
    assert r[("annual", "HM", ("2024-25",))] != r[("annual", "CS", ("2024-25",))]


def _e(ct, plant, **v):
    return {"cost_type": ct, "plant": plant, **v}


def test_save_cost_trend_annual(step):
    for fn in (lambda m: m.save_cost_trend_annual("2024-25", "HM", [_e("VARIABLE", "SAIL", value=1.5),
                                                                   _e("variable", "bsp", value=2),   # ai_ci
                                                                   _e("FIXED", "VISL"), _e("NEW", "XYZ", value=3)]),
               lambda m: m.save_cost_trend_annual("2026-27", "SS", []),                 # bumps, writes nothing
               lambda m: m.save_cost_trend_annual("2025-26 ", "HM", [_e("VARIABLE", "RSP", value=9.0)]),  # cut fy
               lambda m: m.save_cost_trend_annual("2025-260", "HM", [_e("VARIABLE", "RSP", value=9.0)]),  # 1406
               lambda m: m.save_cost_trend_annual("2025-26", "HM", [_e("FIXED", "BSP", value=1.0),
                                                                   _e("FIXED", "P" * 17, value=1.0)]),  # rolled back
               lambda m: m.save_cost_trend_annual("2025-26", "PRODUCT_9", [_e("FIXED", "BSP")]),     # 1406 product
               lambda m: m.save_cost_trend_annual("2025-26", "HM", [_e("C" * 17, "BSP")]),           # 1406 cost_type
               lambda m: m.save_cost_trend_annual("2025-26", "HM", [_e(None, "BSP")]),               # 1048
               lambda m: m.save_cost_trend_annual("2025-26", "HM", [{"plant": "BSP"}]),              # KeyError
               lambda m: m.save_cost_trend_annual(None, "HM", [_e("FIXED", "BSP")]),                 # 1048 fy
               lambda m: m.save_cost_trend_annual("2025-26", "HM", [_e("FIXED", "BSP", value="x")])):  # 1265
        step(fn)


def test_save_cost_trend_monthly(step):
    for fn in (lambda m: m.save_cost_trend_monthly("2025-04", "HM", [
                   _e("VARIABLE", "SAIL", month_value=1.0, till_month_value=2.0),
                   _e("fixed", "bsp", month_value=None, till_month_value=4),                  # ai_ci, NULLs
                   _e("FIXED", "XYZ")]),
               lambda m: m.save_cost_trend_monthly("2099-03", "CS", [_e("TOTAL", "ISP", month_value=5.0)]),
               lambda m: m.save_cost_trend_monthly("2025-4", "HM", []),                       # never checked
               lambda m: m.save_cost_trend_monthly("2025-05  ", "CS", [_e("FIXED", "ISP", month_value=6.0)]),
               lambda m: m.save_cost_trend_monthly("2025-055", "CS", [_e("FIXED", "ISP")]),   # 1406
               lambda m: m.save_cost_trend_monthly(None, "CS", [_e("FIXED", "ISP")]),         # 1048
               lambda m: m.save_cost_trend_monthly("2025-05", "CS", [_e("FIXED", "P" * 17)])):  # 1406 plant
        step(fn)


def test_save_cost_trend_monthly_field(step):
    for fn in (lambda m: m.save_cost_trend_monthly_field("2025-04", "HM", [_e("VARIABLE", "SAIL", value=7.0),
                                                                          _e("NEW", "BSP", value=8.0)],
                                                         "till_month_value"),
               lambda m: m.save_cost_trend_monthly_field("2025-04", "HM", [_e("variable", "sail", value=None)],
                                                         "month_value"),
               lambda m: m.save_cost_trend_monthly_field("2025-06 ", "HM", [_e("OTHER", "RSP", value=1.0)],
                                                         "month_value"),
               lambda m: m.save_cost_trend_monthly_field("2025-04", "HM", [], "bogus"),        # ValueError
               lambda m: m.save_cost_trend_monthly_field("2025-04", "HM", [_e("X", "BSP", value=1.0)],
                                                         "month_value; DROP")):
        step(fn)


def test_keys_v2_cannot_hold(seeded):
    """v1 stored a 9..16-character plant and a short non-month; v2 refuses
    them before writing anything (parity_exceptions.md §2)."""
    for fn in (lambda m: m.save_cost_trend_annual("2025-26", "HM", [_e("FIXED", "LONGPLANT", value=1.0)]),
               lambda m: m.save_cost_trend_monthly("2025-04", "HM", [_e("FIXED", "LONGPLANT")]),
               lambda m: m.save_cost_trend_monthly("2025-4", "HM", [_e("FIXED", "BSP")]),
               lambda m: m.save_cost_trend_monthly_field("2025-4", "HM", [_e("FIXED", "BSP", value=1)],
                                                         "month_value")):
        with seeded.v1():
            fn(c1)
        before = seeded.stored("cost_trend_annual")[1], seeded.stored("cost_trend_monthly")[1]
        with seeded.v2():
            with pytest.raises(_keys.OutOfModelError):
                fn(c2)
        assert (seeded.stored("cost_trend_annual")[1], seeded.stored("cost_trend_monthly")[1]) == before


def test_every_v2_write_bumps_and_a_dry_run_does_not(seeded):
    writes = [lambda: c2.save_cost_trend_annual("2024-25", "HM", [_e("FIXED", "BSP", value=1.0)]),
              lambda: c2.save_cost_trend_annual("2024-25", "HM", []),
              lambda: c2.save_cost_trend_monthly("2025-04", "HM", [_e("FIXED", "BSP", month_value=1.0)]),
              lambda: c2.save_cost_trend_monthly_field("2025-04", "HM", [_e("FIXED", "BSP", value=2.0)],
                                                       "month_value")]
    with seeded.v2():
        for w in writes:
            n = seeded.data_version(2)
            w()
            assert seeded.data_version(2) > n
        before = {k: repr(v) for k, v in _reads(c2).items()}
        n = seeded.data_version(2)
        with rc.rollback_tx():
            c2.save_cost_trend_annual("2024-25", "HM", [_e("FIXED", "DRY", value=1.0)])
            c2.save_cost_trend_monthly("2025-04", "HM", [_e("FIXED", "BSP", month_value=-1.0)])
            c2.save_cost_trend_monthly_field("2098-01", "HM", [_e("FIXED", "BSP", value=-2.0)], "month_value")
            assert {k: repr(v) for k, v in _reads(c2).items()} != before
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(c2).items()} == before
    assert seeded.sql(2, "SELECT COUNT(*) FROM plant WHERE plant_code = 'DRY'")[0][0] == 0
    assert seeded.sql(2, "SELECT COUNT(*) FROM cal_month WHERE report_month = '2098-01'")[0][0] == 0
