"""v1 vs v2 equivalence of repo.pages (Task 7e2): the same page_configs rows
seeded on both sides; every write and read must agree, the stored page_data
text byte for byte (key order, escapes)."""
import json

import pytest

from repo import conn as rc
from repo import pages as p1
from repo.v2 import pages as p2
from v2dual import assert_same_reads, run_step

ROWS = [
    {"report_month": "2026-04", "page_number": 2, "page_data": json.dumps({"z": 1, "a": {"y": [1, 2.5, None], "b": "é"}})},
    {"report_month": "2026-04", "page_number": 10, "page_data": json.dumps({"page": 10, "title": "ten"})},
    {"report_month": "2026-04", "page_number": 3, "page_data": json.dumps({"page": 3, "unicode": "₹ क"})},
    {"report_month": "2026-05", "page_number": 2, "page_data": json.dumps([1, {"k": True}])},
]


@pytest.fixture
def seeded(dual):
    dual.seed_simple("page_configs", ROWS)
    return dual


def _reads(m):
    out = {}
    for mo in ("2026-04", "2026-05", "2026-06", "2099-01", "2026-04 "):
        out[("all", mo)] = m.get_all_page_configs(mo)
        for n in (2, 3, 10, 11):
            out[("one", mo, n)] = m.get_page_config(mo, n)
    return out


@pytest.fixture
def step(seeded):
    def go(fn):
        return run_step(seeded, p1, p2, fn, reads=_reads, tables=("page_configs",))
    return go


def test_seeded_reads_agree(seeded):
    r = assert_same_reads(seeded, p1, p2, _reads)
    assert r[("all", "2026-04")].count("$dict") >= 3


def test_save_page_config(step):
    big = {"rows": [{"i": i, "text": "x" * 40} for i in range(3000)], "z": 1, "a": 2}
    for fn in (lambda m: m.save_page_config("2026-04", 2, {"b": 1, "a": [3, 2, 1], "c": "ü"}),    # overwrite
               lambda m: m.save_page_config("2026-04", 4, {"new": True}),
               lambda m: m.save_page_config("2026-06", 2, big),                                   # > 64 KB
               lambda m: m.save_page_config("2099-01", 1, {"far": 1}),                            # new month
               lambda m: m.save_page_config("1950-01", 1, {"old": 1}),
               lambda m: m.save_page_config("2026-07 ", 5, {"cut": 1}),                           # trailing space
               lambda m: m.save_page_config("2026-07", 5, {"cut": 2}),
               lambda m: m.save_page_config("2026-08 x", 5, {}),                                  # 1406
               lambda m: m.save_page_config(None, 5, {}),                                         # 1048
               lambda m: m.save_page_config("2026-08", None, {}),                                 # 1048
               lambda m: m.save_page_config("2026-08", "abc", {}),                                # 1366
               lambda m: m.save_page_config("2026-08", 6, {"bad": object()}),                     # TypeError
               lambda m: m.save_page_config("2026-08", 7, None),                                  # JSON null
               lambda m: m.save_page_config("2026-08", 8, {})):
        step(fn)


def test_out_of_model_inputs_are_refused_before_any_write(seeded):
    from repo.v2._keys import OutOfModelError
    with seeded.v2():
        n = seeded.data_version(2)
        before = {k: repr(v) for k, v in _reads(p2).items()}
        for month, data in (("2026-4", {}), ("2026-13", {}), ("abc", {}), ("", {}),
                            ("2026-08", {"nan": float("nan")}), ("2026-08", [float("inf")])):
            with pytest.raises(OutOfModelError):
                p2.save_page_config(month, 1, data)
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(p2).items()} == before


def test_every_v2_write_bumps_and_a_dry_run_does_not(seeded):
    with seeded.v2():
        n = seeded.data_version(2)
        p2.save_page_config("2026-04", 2, {"x": 1})
        assert seeded.data_version(2) > n
        before = {k: repr(v) for k, v in _reads(p2).items()}
        n = seeded.data_version(2)
        with rc.rollback_tx():
            p2.save_page_config("2098-01", 9, {"dry": 1})
            p2.save_page_config("2026-04", 3, {"dry": 2})
            assert {k: repr(v) for k, v in _reads(p2).items()} != before
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(p2).items()} == before
    assert seeded.sql(2, "SELECT COUNT(*) FROM cal_month WHERE report_month = '2098-01'")[0][0] == 0
