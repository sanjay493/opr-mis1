"""v1 vs v2 equivalence of repo.mines (Task 7e1).

The same masters and monthly rows are seeded into v1's mine*_master /
mines_*_monthly / sail_mines_monthly and their v2 tables (as the migration
loads them). Every write runs through repo.mines on v1 and repo.v2.mines
on v2; after each step both sides must agree on the outcome (result, or
exception type and args; the database name in an FK message normalised),
every read (canonical form; the cursor helpers on tuple and Row cursors)
and the stored rows.

Reads whose v1 SQL has no ORDER BY follow the access path MySQL picks,
which on these tiny test tables can differ from the real data's (the
oracle replay proves the order on the real data): their lists are compared
as multisets here (get_iron_ore_mines_series' lists, the named row
readers). Everything else, including the group rollups' set-built dicts,
is compared strictly.
"""
import pytest

import dbengine
from repo import conn as rc
from repo import mines as m1
from repo.v2 import _keys
from repo.v2 import mines as m2
from v2dual import assert_same_reads, multiset, on_cursor, run_step

ROW = dbengine.Row
MONTHS = ["2025-04", "2025-05", "2025-06", "2099-01"]
TABLES = ("mines_production_monthly", "mines_despatch_actual_monthly", "mines_despatch_plan_monthly",
          "mines_booked_qty_actual_monthly", "mines_booked_qty_plan_monthly", "sail_mines_monthly")

GROUPS = [{"group_code": "JGoM", "group_name": "Jharkhand", "sort_order": 1},
          {"group_code": "OGoM", "group_name": "Orissa", "sort_order": 2},
          {"group_code": "CGoM", "group_name": "Chhattisgarh", "sort_order": 3}]
MINES = [{"mine_code": "BARSUA", "mine_name": "Barsua", "group_code": "OGoM", "is_active": 1, "sort_order": 3},
         {"mine_code": "DALLI", "mine_name": "Dalli", "group_code": "CGoM", "is_active": 1, "sort_order": 5},
         {"mine_code": "GUA", "mine_name": "Gua", "group_code": "JGoM", "is_active": 1, "sort_order": 1},
         {"mine_code": "OLD", "mine_name": "Old", "group_code": "JGoM", "is_active": 0, "sort_order": 9}]
MATERIALS = [{"material_code": m, "material_name": m.title(), "material_category": c, "has_production": hp,
              "counts_in_total_production": ct, "sort_order": i}
             for i, (m, c, hp, ct) in enumerate([("LUMP", "FRESH", 1, 1), ("FINES", "FRESH", 1, 1),
                                                 ("DUMP_FINES", "LEGACY", 0, 0), ("TAILINGS", "LEGACY", 0, 0),
                                                 ("PELLETS", "PELLET", 0, 1)])]
END_USES = [{"end_use_code": e, "end_use_name": e.title(), "sort_order": i, "tracks_actual": t}
            for i, (e, t) in enumerate([("CAPTIVE", 1), ("SALES", 1), ("PELLET_CONV", 1), ("UNALLOCATED", 0)])]


def _p(mo, mine, mat, a, p):
    return {"report_month": mo, "mine_code": mine, "material_code": mat, "qty_actual": a, "qty_plan": p}


PROD = [_p("2025-04", "GUA", "LUMP", 100.5, 110.0), _p("2025-04", "GUA", "FINES", 50.25, None),
        _p("2025-04", "BARSUA", "FINES", 0.1, 0.2), _p("2025-05", "DALLI", "LUMP", None, 10.0),
        _p("2025-06", "OLD", "LUMP", 1.0, 1.0)]
DESP = [{"report_month": mo, "mine_code": mi, "material_code": ma, "transport_mode": tm, "end_use_code": eu,
         "qty_actual": q} for mo, mi, ma, tm, eu, q in [
    ("2025-04", "GUA", "LUMP", "RAIL", "CAPTIVE", 40.1), ("2025-04", "GUA", "LUMP", "ROAD", "CAPTIVE", 0.2),
    ("2025-04", "GUA", "DUMP_FINES", "ROAD", "SALES", 5.5), ("2025-04", "BARSUA", "TAILINGS", "RAIL", "SALES", 1.1),
    ("2025-04", "DALLI", "PELLETS", "RAIL", "PELLET_CONV", 7.0), ("2025-05", "DALLI", "PELLETS", "ROAD", "SALES", None),
    ("2025-05", "BARSUA", "DUMP_FINES", "RAIL", "CAPTIVE", 3.3), ("2025-05", "GUA", "TAILINGS", "RAIL", "CAPTIVE", 9.9)]]
DESP_PLAN = [{"report_month": mo, "mine_code": mi, "material_code": ma, "end_use_code": eu, "qty_plan": q}
             for mo, mi, ma, eu, q in [
    ("2025-04", "GUA", "LUMP", "CAPTIVE", 45.0), ("2025-04", "DALLI", "FINES", "CAPTIVE", 130.0),
    ("2025-04", "BARSUA", "DUMP_FINES", "UNALLOCATED", 2.5), ("2025-05", "GUA", "TAILINGS", "SALES", None),
    ("2025-05", "DALLI", "PELLETS", "SALES", 8.0)]]
BOOKED = [{"report_month": mo, "mine_code": mi, "material_code": ma, "transport_mode": tm, "qty_actual": q}
          for mo, mi, ma, tm, q in [("2025-04", "GUA", "FINES", "RAIL", 12.0), ("2025-04", "GUA", "FINES", "ROAD", 1.5),
                                    ("2025-05", "BARSUA", "LUMP", "RAIL", None)]]
BOOKED_PLAN = [{"report_month": mo, "mine_code": mi, "material_code": ma, "qty_plan": q}
               for mo, mi, ma, q in [("2025-04", "GUA", "FINES", 15.0), ("2025-04", "DALLI", "LUMP", 3.0)]]
SAIL = [{"report_month": mo, "section": s, "item": i, "month_actual": a, "month_plan": p}
        for mo, s, i, a, p in [("2025-04", "clean_coal", "Total", 1.0, 2.0), ("2025-04", "flux", "Lime", None, 3.5),
                               ("2025-05", "clean_coal", "Total", 4.0, None)]]


@pytest.fixture
def seeded(dual):
    for t, rows in (("mine_groups_master", GROUPS), ("mines_master", MINES), ("mine_materials_master", MATERIALS),
                    ("mine_end_uses_master", END_USES), ("mines_production_monthly", PROD),
                    ("mines_despatch_actual_monthly", DESP), ("mines_despatch_plan_monthly", DESP_PLAN),
                    ("mines_booked_qty_actual_monthly", BOOKED), ("mines_booked_qty_plan_monthly", BOOKED_PLAN),
                    ("sail_mines_monthly", SAIL)):
        dual.seed_simple(t, rows)
    return dual


_UNORDERED_CUR = ("production_rows", "despatch_actual_rows", "despatch_plan_rows", "booked_actual_rows",
                  "booked_plan_rows", "sail_rows")


def _reads(m):
    out = {}
    out["masters"] = m.get_mines_masters()
    for ms in (MONTHS, ["2025-04"], ["2025-05", "2025-04"], [], ["2024-01"]):
        k = tuple(ms)
        out[("sail", k)] = m.get_sail_mines_monthly(ms)
        out[("rollup", k)] = m.get_iron_ore_group_rollup_monthly(ms)
        out[("mix", k)] = m.get_iron_ore_despatch_mix(ms)
        out[("sales", k)] = m.get_iron_ore_sales_group_rollup_monthly(ms)
        series = m.get_iron_ore_mines_series(ms)
        out[("series", k)] = {key: multiset(rows) for key, rows in series.items()}
        for rf, name in ((None, "tuple"), (ROW, "row")):
            if ms:
                for fn in _UNORDERED_CUR:
                    out[(fn, name, k)] = multiset(on_cursor(lambda md, cur: getattr(md, fn)(cur, ms), rf)(m))
    for rf, name in ((None, "tuple"), (ROW, "row")):
        for fn in ("group_rows", "mine_rows", "material_rows"):
            out[(fn, name)] = on_cursor(lambda md, cur: getattr(md, fn)(cur), rf)(m)
    for mo in MONTHS + ["2025-04 "]:
        out[("any", mo)] = m.sail_mines_any_row(mo)
        for mine in ("GUA", "gua", "DALLI", "BARSUA", "NONE"):
            out[("pd", mo, mine)] = m.get_mines_production_despatch_monthly(mo, mine)
    return out


@pytest.fixture
def step(seeded):
    def go(fn):
        return run_step(seeded, m1, m2, fn, reads=_reads, tables=TABLES)
    return go


def test_seeded_reads_agree(seeded):
    r = assert_same_reads(seeded, m1, m2, _reads)
    assert r[("mix", tuple(MONTHS))] != r[("mix", ("2025-04",))]


def test_save_sail_mines_monthly(step):
    for fn in (lambda m: m.save_sail_mines_monthly("2025-04", [{"section": "clean_coal", "item": "Total", "actual": 9.0},
                                                               {"section": "FLUX", "item": "lime", "plan": 1.0},
                                                               {"section": "new", "item": "x"}]),
               lambda m: m.save_sail_mines_monthly("2099-02", [{"section": "s", "item": "i", "actual": 1}]),
               lambda m: m.save_sail_mines_monthly("2025-4", []),                       # month never checked
               lambda m: m.save_sail_mines_monthly("2025-05 ", [{"section": "clean_coal", "item": "Total",
                                                                 "actual": 2.0}]),
               lambda m: m.save_sail_mines_monthly("2025-055", [{"section": "s", "item": "i"}]),   # 1406
               lambda m: m.save_sail_mines_monthly(None, [{"section": "s", "item": "i"}]),         # 1048
               lambda m: m.save_sail_mines_monthly("2025-05", [{"section": "S" * 25, "item": "i"}]),
               lambda m: m.save_sail_mines_monthly("2025-05", [{"section": "s"}])):                # KeyError
        step(fn)


def _save(month, mine, prod=(), desp=(), plan=(), booked=None, booked_plan=None):
    return lambda m: m.save_mines_production_despatch_monthly(month, mine, list(prod), list(desp), list(plan),
                                                              booked, booked_plan)


def test_save_mines_production_despatch_monthly(step):
    for fn in (_save("2025-04", "GUA", [{"material_code": "LUMP", "actual": 1.0, "plan": 2.0},
                                        {"material_code": "lump", "actual": 3.0}],               # ai_ci stored row
                     [{"material_code": "LUMP", "transport_mode": "RAIL", "end_use_code": "CAPTIVE", "actual": 4.0},
                      {"material_code": "PELLETS", "transport_mode": "ROAD", "end_use_code": "SALES"}],
                     [{"material_code": "FINES", "end_use_code": "SALES", "plan": 5.0}],
                     [{"material_code": "FINES", "transport_mode": "RAIL", "actual": 6.0}],
                     [{"material_code": "LUMP", "plan": 7.0}]),
               _save("2099-03", "DALLI", [{"material_code": "FINES", "actual": 1.5}]),
               _save("2025-4", "GUA"),                                                         # nothing written
               _save("2025-05  ", "BARSUA", [{"material_code": "FINES", "actual": 2.5}]),
               _save("2025-05", "NOPE", [{"material_code": "FINES", "actual": 1.0}]),           # 1452 mine
               _save("2025-05", "GUA", [], [{"material_code": "NOPE", "transport_mode": "RAIL",
                                             "end_use_code": "SALES"}]),                        # 1452 material
               _save("2025-05", "GUA", [], [], [{"material_code": "LUMP", "end_use_code": "NOPE"}]),  # 1452 end use
               _save("2025-05", "GUA", [], [], [], [{"material_code": "NOPE", "transport_mode": "RAIL"}]),
               _save("2025-05", "GUA", [], [], [], None, [{"material_code": "NOPE"}]),
               _save("2025-05", "NOPE", [{"material_code": "NOPE2"}]),                          # both FKs bad
               _save("2025-05", "NOPE", [], [], [{"material_code": "NOPE2", "end_use_code": "NOPE3"}]),
               _save("2025-05", "GUA", [{"material_code": "LUMP", "actual": 1.0}, {"actual": 2.0}]),  # KeyError
               _save("2025-05", "GUA", [{"material_code": "M" * 17}]),                         # 1406
               _save("2025-055", "GUA", [{"material_code": "LUMP"}]),                          # 1406 month
               _save(None, "GUA", [{"material_code": "LUMP"}])):                               # 1048
        step(fn)


def test_short_non_month_is_refused(seeded):
    """v1 stored '2025-4' as text; v2 refuses it before writing anything
    (parity_exceptions.md §2a)."""
    for fn in (lambda m: m.save_sail_mines_monthly("2025-4", [{"section": "s", "item": "i"}]),
               _save("2025-4", "GUA", [{"material_code": "LUMP", "actual": 1.0}])):
        with seeded.v1():
            fn(m1)
        n = seeded.data_version(2)
        with seeded.v2():
            with pytest.raises(_keys.OutOfModelError):
                fn(m2)
        assert seeded.data_version(2) == n


def test_every_v2_write_bumps_and_a_dry_run_does_not(seeded):
    writes = [lambda: m2.save_sail_mines_monthly("2025-04", [{"section": "s", "item": "i", "actual": 1.0}]),
              lambda: m2.save_sail_mines_monthly("2025-04", []),
              lambda: m2.save_mines_production_despatch_monthly(
                  "2025-04", "GUA", [{"material_code": "LUMP", "actual": 1.0}], [], []),
              lambda: m2.save_mines_production_despatch_monthly("2025-04", "GUA", [], [], [])]
    with seeded.v2():
        for w in writes:
            n = seeded.data_version(2)
            w()
            assert seeded.data_version(2) > n
        before = {k: repr(v) for k, v in _reads(m2).items()}
        n = seeded.data_version(2)
        with rc.rollback_tx():
            m2.save_sail_mines_monthly("2098-01", [{"section": "dry", "item": "i", "actual": 1.0}])
            m2.save_mines_production_despatch_monthly("2025-04", "GUA", [{"material_code": "FINES", "actual": -1.0}],
                                                      [], [], [{"material_code": "LUMP", "transport_mode": "RAIL"}])
            assert {k: repr(v) for k, v in _reads(m2).items()} != before
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(m2).items()} == before
    assert seeded.sql(2, "SELECT COUNT(*) FROM cal_month WHERE report_month = '2098-01'")[0][0] == 0
