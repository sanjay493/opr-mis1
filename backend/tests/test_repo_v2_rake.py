"""v1 vs v2 equivalence of repo.rake (Task 7e1).

The same rows are seeded into v1's and v2's rake_detention_master /
_monthly / _summary / _annual (as the migration loads them, master ids
kept). Every write runs through _v1_frozen.rake on v1 and repo.rake (v2) on v2;
after each step both sides must agree on the outcome (result, or exception
type and args; the database name in an FK message is normalised), every
read (canonical form: list / dict order and types count) and the stored
rows ('' vs NULL freetime_effective_from included).
"""
import pytest

from repo import conn as rc
from _v1_frozen import rake as r1
from repo import rake as r2
from v2dual import assert_same_reads, run_step

TABLES = ("rake_detention_master", "rake_detention_monthly", "rake_detention_summary", "rake_detention_annual")
PLANTS = ["BSP", "bsp", "DSP", "RSP", "XYZ"]


def _master(id_, plant, section, commodity, wagon, label, total=0, direction="IN", hours=5.0, eff=None, so=0,
            active=1):
    return {"id": id_, "plant": plant, "section": section, "commodity": commodity, "wagon_type": wagon,
            "row_label": label, "is_total": total, "direction": direction, "freetime_hours": hours,
            "freetime_effective_from": eff, "sort_order": so, "is_active": active}


MASTER = [
    _master(1, "BSP", "Inward", "Ind.Coking Coal", "BOXN", "BOXN", so=1, eff="2024-04-01"),
    _master(2, "BSP", "Inward", "Ind.Coking Coal", "BOST", "BOST", so=2, eff=""),
    _master(3, "BSP", "Inward", "Imp.Coking Coal", "BOXN", "BOXN", so=4),
    _master(4, "BSP", "Inward", "Ind.Coking Coal", "BOSM", "BOSM", so=4),          # sort_order collision
    _master(5, "BSP", "Inward", None, None, "Overall Wagon", total=1, so=0, hours=None),
    _master(6, "DSP", "Outward", "Steel", "BCN", "BCN", so=1, direction=None, active=0),
    _master(7, "BSP", "Outward", "Steel", "BCN", "BCN", so=1),
    _master(8, "RSP", "Inward", "Coal", "BOXN", "BOXN", so=1, eff="2025-01-01"),
]
MONTHLY = [{"report_month": m, "master_id": i, "value_hours": v} for m, i, v in [
    ("2025-04", 1, 10.5), ("2025-04", 2, None), ("2025-04", 5, 7.0), ("2025-05", 1, 11.0), ("2025-05", 6, 3.0),
    ("2024-04", 5, 8.25), ("2023-04", 5, 9.0), ("2025-04", 8, 1.0)]]
SUMMARY = [{"report_month": m, "period_row": p, "plant": pl, "value": v} for m, p, pl, v in [
    ("2025-04", "UPTO 2025-04", "BSP", 12.0), ("2025-04", "UPTO 2025-04", "DSP", None),
    ("2025-04", "2024-25", "BSP", 13.5), ("2025-05", "UPTO 2025-05", "RSP", 1.0)]]
ANNUAL = [{"plant": p, "financial_year": fy, "avg_hours": v} for p, fy, v in [
    ("BSP", "2023-24", 10.0), ("BSP", "2024-25", None), ("DSP", "2024-25", 8.5), ("RSP", "2022-23", 1e-3)]]


@pytest.fixture
def seeded(dual):
    dual.seed_simple("rake_detention_master", MASTER)
    dual.seed_simple("rake_detention_monthly", MONTHLY)
    dual.seed_simple("rake_detention_summary", SUMMARY)
    dual.seed_simple("rake_detention_annual", ANNUAL)
    return dual


def _reads(m):
    out = {}
    for plants in (None, [], ["BSP"], ["bsp", "DSP"], ["XYZ"]):
        for active in (True, False):
            out[("master", repr(plants), active)] = m.get_rake_detention_master(plants, active)
    for mo in ("2023-04", "2024-04", "2025-04", "2025-05", "2099-01", "2025-04 "):
        for ids in (None, [], [5, 1], [99]):
            out[("monthly", mo, repr(ids))] = m.get_rake_detention_monthly(mo, ids)
        out[("summary", mo)] = m.get_rake_detention_summary(mo)
    for ids in ([], [5], [1, 5, 99], [6, 1]):
        out[("trend", repr(ids))] = m.get_rake_detention_trend(ids)
    for plants in ([], ["BSP"], ["bsp", "DSP", "RSP"], PLANTS):
        for fys in ([], ["2024-25"], ["2024-25", "2023-24", "2022-23"]):
            out[("annual", tuple(plants), tuple(fys))] = m.get_rake_detention_annual(plants, fys)
    return out


@pytest.fixture
def step(seeded):
    def go(fn):
        return run_step(seeded, r1, r2, fn, reads=_reads, tables=TABLES)
    return go


def test_seeded_reads_agree(seeded):
    r = assert_same_reads(seeded, r1, r2, _reads)
    assert r[("master", "None", False)] != r[("master", "None", True)]


def _row(**k):
    base = {"plant": "BSP", "section": "Inward", "commodity": "Imp.Coking Coal", "wagon_type": "BOBR",
            "row_label": "BOBR"}
    base.update(k)
    return base


def test_save_rake_detention_master_row(step):
    for fn in (lambda m: m.save_rake_detention_master_row(_row(sort_order=5)),                       # insert: id 9
               lambda m: m.save_rake_detention_master_row(_row(id=2, freetime_effective_from=None, is_total=None)),
               lambda m: m.save_rake_detention_master_row(_row(id=3, freetime_effective_from="",
                                                               is_active=False, sort_order="7")),
               lambda m: m.save_rake_detention_master_row(_row(plant="XYZ", section="Outward")),       # new plant
               lambda m: m.save_rake_detention_master_row(_row(id=99)),                                # no such id
               lambda m: m.save_rake_detention_master_row(_row(freetime_effective_from="2025-04-01   ")),
               lambda m: m.save_rake_detention_master_row(_row(plant="LONGPLANT")),                    # 1406 plant
               lambda m: m.save_rake_detention_master_row(_row(plant=None)),                           # 1048 plant
               lambda m: m.save_rake_detention_master_row(_row(id=1, plant="P" * 9)),                  # 1406 (update)
               lambda m: m.save_rake_detention_master_row(_row(section="S" * 9)),                      # 1406 section
               lambda m: m.save_rake_detention_master_row(_row(row_label=None)),                       # 1048
               lambda m: m.save_rake_detention_master_row({"plant": "BSP"}),                           # KeyError
               lambda m: m.save_rake_detention_master_row(_row())):                                    # next id
        step(fn)


def test_deactivate_rake_detention_master_row(step):
    for fn in (lambda m: m.deactivate_rake_detention_master_row(1),
               lambda m: m.deactivate_rake_detention_master_row(1),
               lambda m: m.deactivate_rake_detention_master_row(99)):
        step(fn)


def test_save_rake_detention_monthly(step):
    for fn in (lambda m: m.save_rake_detention_monthly("2025-04", [{"master_id": 1, "value_hours": 1.25},
                                                                   {"master_id": 3},
                                                                   {"master_id": 2, "value_hours": None}]),
               lambda m: m.save_rake_detention_monthly("2099-01", [{"master_id": 5, "value_hours": 2.0}]),
               lambda m: m.save_rake_detention_monthly("2025-4", []),                 # month never checked
               lambda m: m.save_rake_detention_monthly("2025-05 ", [{"master_id": 6, "value_hours": 4.0}]),
               lambda m: m.save_rake_detention_monthly("2025-05", [{"master_id": 99, "value_hours": 4.0}]),  # 1452
               lambda m: m.save_rake_detention_monthly("2025-05", [{"master_id": 1, "value_hours": 4.0},
                                                                   {"value_hours": 1.0}]),     # KeyError: rolled back
               lambda m: m.save_rake_detention_monthly("2025-055", [{"master_id": 1}]),        # 1406
               lambda m: m.save_rake_detention_monthly(None, [{"master_id": 1}]),              # 1048
               lambda m: m.save_rake_detention_monthly("2025-05", [{"master_id": None}])):     # 1048 master_id
        step(fn)


def test_save_rake_detention_summary(step):
    for fn in (lambda m: m.save_rake_detention_summary("2025-04", [
                   {"period_row": "UPTO 2025-04", "plant": "BSP", "value": 1.0},
                   {"period_row": "upto 2025-04", "plant": "dsp", "value": 2.0},              # ai_ci stored row
                   {"period_row": "2024-25", "plant": "XYZ"}]),
               lambda m: m.save_rake_detention_summary("2025-06  ", [{"period_row": "P", "plant": "RSP", "value": 3}]),
               lambda m: m.save_rake_detention_summary("2025-06", [{"period_row": "P" * 25, "plant": "RSP"}]),
               lambda m: m.save_rake_detention_summary("2025-06", [{"period_row": "P", "plant": "P" * 9}]),
               lambda m: m.save_rake_detention_summary("2025-06", [{"period_row": None, "plant": "P" * 9}]),
               lambda m: m.save_rake_detention_summary("2025-06", [])):
        step(fn)


def test_save_rake_detention_annual(step):
    for fn in (lambda m: m.save_rake_detention_annual([{"plant": "BSP", "financial_year": "2024-25", "avg_hours": 1.0},
                                                       {"plant": "dsp", "financial_year": "2024-25"},
                                                       {"plant": "XYZ", "financial_year": "2025-26", "avg_hours": 2}]),
               lambda m: m.save_rake_detention_annual([{"plant": "RSP", "financial_year": "2022-23 ", "avg_hours": 5.0}]),
               lambda m: m.save_rake_detention_annual([{"plant": "RSP", "financial_year": "2022-233"}]),   # 1406
               lambda m: m.save_rake_detention_annual([{"plant": "P" * 9, "financial_year": "2022-23"}]),  # 1406
               lambda m: m.save_rake_detention_annual([{"plant": "RSP", "financial_year": None}]),         # 1048
               lambda m: m.save_rake_detention_annual([{"plant": "RSP"}]),                                 # KeyError
               lambda m: m.save_rake_detention_annual([])):
        step(fn)


def test_every_v2_write_bumps_and_a_dry_run_does_not(seeded):
    writes = [lambda: r2.save_rake_detention_master_row(_row()),
              lambda: r2.deactivate_rake_detention_master_row(2),
              lambda: r2.save_rake_detention_monthly("2025-04", [{"master_id": 1, "value_hours": 9.0}]),
              lambda: r2.save_rake_detention_monthly("2025-04", []),
              lambda: r2.save_rake_detention_summary("2025-04", [{"period_row": "X", "plant": "BSP", "value": 1}]),
              lambda: r2.save_rake_detention_annual([{"plant": "BSP", "financial_year": "2024-25", "avg_hours": 3}])]
    with seeded.v2():
        for w in writes:
            n = seeded.data_version(2)
            w()
            assert seeded.data_version(2) > n
        before = {k: repr(v) for k, v in _reads(r2).items()}
        n = seeded.data_version(2)
        with rc.rollback_tx():
            r2.save_rake_detention_master_row(_row(plant="DRY"))
            r2.deactivate_rake_detention_master_row(1)
            r2.save_rake_detention_monthly("2098-01", [{"master_id": 1, "value_hours": -1.0}])
            r2.save_rake_detention_summary("2025-04", [{"period_row": "UPTO 2025-04", "plant": "BSP", "value": -2}])
            r2.save_rake_detention_annual([{"plant": "BSP", "financial_year": "2023-24", "avg_hours": -3.0}])
            assert {k: repr(v) for k, v in _reads(r2).items()} != before
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(r2).items()} == before
    assert seeded.sql(2, "SELECT COUNT(*) FROM plant WHERE plant_code = 'DRY'")[0][0] == 0
    assert seeded.sql(2, "SELECT COUNT(*) FROM cal_month WHERE report_month = '2098-01'")[0][0] == 0
