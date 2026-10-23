"""v1 vs v2 equivalence of repo.breakdown (Task 7e2).

The same rows are seeded into v1's breakdown_table / capital_repair_table
and v2's breakdown / capital_repair (+ plant_unit, as the migration loads
them, ids kept). Every write runs through repo.breakdown on v1 and
repo.v2.breakdown on v2 with datetime.now() frozen; after each step both
sides must agree on the outcome (result, or exception type and args), the
activity-log entries, every read (canonical form) and the stored rows
(unit names, DATE columns and timestamps rendered back to v1's strings).
"""
import datetime as dt

import pytest

import dbengine
from repo import breakdown as b1
from repo import conn as rc
from repo.v2 import breakdown as b2
from v2dual import FrozenNow, assert_same_reads, multiset, on_cursor, record_activity, run_step

TABLES = ("breakdown_table", "capital_repair_table")
T0 = "2026-04-10T08:15:30.123456"


def _bd(id_, plant, utype, unit, start, end=None, ongoing=0, cause="c", hours=None, cr=None, tag=None,
        created=T0, by="u"):
    return {"id": id_, "plant": plant, "unit_type": utype, "unit_name": unit, "sms_subtag": tag,
            "start_ts": start, "end_ts": end, "is_ongoing": ongoing, "cause": cause,
            "hours_lost_override": hours, "capital_repair_id": cr, "created_by": by, "created_at": created,
            "updated_by": by, "updated_at": created}


def _cr(id_, plant, fy, shop, unit, utype="BF", start=None, end=None, ongoing=0, so=0, tag=None, **k):
    row = {"id": id_, "plant": plant, "fy": fy, "shop": shop, "equipment": k.get("equipment", "eq"),
           "unit_type": utype, "unit_name": unit, "sms_subtag": tag, "activity": k.get("activity", "act"),
           "schedule_days": "30", "actual_start": start, "actual_end": end, "actual_ongoing": ongoing,
           "planned_days": k.get("planned", 30.5), "period": "Apr", "actual": k.get("actual", "x"),
           "sort_order": so}
    return row


BREAKDOWN = [
    _bd(1, "BSP", "BF", "BF-8", "2026-04-15 01:00", "2026-04-16 01:25", cause="choke", hours=3.5),
    _bd(2, "BSP", "BF", "BF-8", "2026-04-15 01:00", None, ongoing=1, cr=2),
    _bd(3, "DSP", "SMS", "Shop", "2026-04-19", "2026-04-21", tag="CONVERTER", created="2026-04-10T08:15:30"),
    _bd(4, "BSP", "GENERAL", "shop", "2026-07-04 10:00", None, ongoing=1, cr=999),       # dangling link
    _bd(5, "bsp", "MILL", "WRM", "2025-12-31 23:59", "2026-01-01 00:30"),
    _bd(6, "RSP", "BF", "BF-1", "2026-08-02", "2026-08-02", by=None, created=None),
]
CR = [
    _cr(1, "BSP", "2026-27", "Blast Furnace", "BF-8", start="2026-04-01", end="2026-04-20", so=0),
    _cr(2, "BSP", "2026-27", "Blast Furnace", "BF-8", start="2026-05-01", ongoing=1, so=1),
    _cr(3, "BSP", "2026-27", "SMS", None, utype=None, so=2),
    _cr(4, "DSP", "2026-27", "SMS", "Shop", utype="SMS", tag="CASTER", start="2026-04-19", so=0),
    _cr(5, "BSP", "2025-26", "Mill", "WRM", utype="MILL", start="2025-12-01", end="2025-12-31", so=0),
    _cr(6, "BSP", "2026-27", "Gen", "SHOP", utype="GENERAL", so=3),                      # ai_ci twin of 'shop'
]


@pytest.fixture
def seeded(dual, monkeypatch):
    dual.seed_simple("capital_repair_table", CR)
    dual.seed_simple("breakdown_table", BREAKDOWN)
    FrozenNow(monkeypatch, b2, value=dt.datetime(2026, 10, 23, 14, 30, 5, 250000))
    return dual


def _conn(fn):
    def run(mod):
        conn = dbengine.connect()
        try:
            return fn(mod, conn)
        finally:
            conn.close()
    return run


def _reads(m):
    out = {}
    for kw in ({}, {"plant": "bsp"}, {"plant": "DSP"}, {"unit_type": "bf"}, {"unit_name": "shop"},
               {"unit_name": "BF-8", "plant": "BSP"}, {"fy": "2026-27"}, {"fy": "2025-26", "plant": "BSP"},
               {"plant": "ZZZ"}):
        out[("list", repr(kw))] = m.list_breakdown_entries(**kw)
    out["rows_bsp"] = multiset(_conn(lambda mod, c: mod.breakdown_rows_for_plant(c, "bsp"))(m))
    out["rows_dsp"] = multiset(_conn(lambda mod, c: mod.breakdown_rows_for_plant(c, "DSP"))(m))
    for end, start in (("2026-05-01", "2026-04-01"), ("2026-09-01", "2026-08-01"), ("2026-02-01", "2026-01-01")):
        out[("open", end)] = multiset(on_cursor(lambda mod, cur: mod.open_breakdown_rows(cur, end, start))(m))
    cols = ("id", "plant", "fy", "shop", "equipment", "activity", "actual_start", "actual_end", "actual_ongoing")
    for plant in ("BSP", "dsp", "RSP"):
        out[("actual", plant)] = _conn(lambda mod, c: mod.cr_actual_rows(c, cols, plant))(m)
        out[("crplant", plant)] = multiset(_conn(lambda mod, c: mod.cr_rows_for_plant(c, plant))(m))
        for fy in ("2026-27", "2025-26", "2024-25"):
            for fn in ("cr_report_rows", "cr_calendar_rows", "cr_entry_rows", "cr_ordered_ids"):
                out[(fn, plant, fy)] = on_cursor(lambda mod, cur: getattr(mod, fn)(cur, plant, fy))(m)
            out[("started", plant, fy)] = on_cursor(
                lambda mod, cur: mod.cr_started_rows(cur, plant, fy, "2026-06-30"))(m)
    for rid in (1, 2, 3, 4, 99):
        out[("plant_row", rid)] = on_cursor(lambda mod, cur: mod.cr_plant_row(cur, rid))(m)
        out[("actual_start", rid)] = on_cursor(lambda mod, cur: mod.cr_actual_and_start_row(cur, rid))(m)
        out[("entry_old", rid)] = _conn(lambda mod, c: mod.cr_entry_old(
            c, ("shop", "equipment", "activity", "schedule_days", "period"), rid))(m)
        out[("row_dict", rid)] = _conn(lambda mod, c: mod.cr_row_dict(c, rid))(m)
    for src, plant, fy in ((1, "BSP", "2026-27"), (4, "DSP", "2026-27"), (3, "BSP", "2026-27"), (1, "DSP", "2026-27")):
        out[("copy", src, plant)] = _conn(lambda mod, c: mod.cr_copy_source(c, src, plant, fy))(m)
    return out


@pytest.fixture
def step(seeded, monkeypatch):
    acts = record_activity(monkeypatch)

    def go(fn):
        return run_step(seeded, b1, b2, fn, reads=_reads, tables=TABLES, activity=acts)
    return go


def test_seeded_reads_agree(seeded):
    r = assert_same_reads(seeded, b1, b2, _reads)
    assert r[("list", "{}")].count(chr(34) + "id" + chr(34)) == 6 and "BF-8" in r[("actual", "BSP")] + r[("list", "{}")]


def _save(**k):
    base = dict(plant="BSP", unit_type="BF", unit_name="BF-8", sms_subtag=None, start_ts="2026-09-01 10:00",
                end_ts=None, is_ongoing=True, cause="trip", hours_lost_override=2.5, created_by="alice")
    base.update(k)
    return lambda m: m.save_breakdown_entry(**base)


def test_save_breakdown_entry(step):
    for fn in (_save(),
               _save(plant="bsp", unit_name="bf-8", capital_repair_id=2),         # ai_ci twins stay as typed
               _save(plant="DSP", unit_type="SMS", unit_name="Caster 3", sms_subtag="CASTER", end_ts="2026-09-02",
                     is_ongoing=False, hours_lost_override=None, capital_repair_id=12345),    # dangling id
               _save(plant="NEW", unit_name="Fresh"),                                  # new plant
               _save(unit_name="SHOP"),                                                # third spelling
               _save(unit_name="Ünit ñ"),
               _save(plant="P" * 9),                                                   # 1406 plant
               _save(plant=None),                                                      # 1048
               _save(unit_type="T" * 17),
               _save(unit_type=None),
               _save(unit_name="U" * 33),
               _save(unit_name=None),
               _save(sms_subtag="S" * 17),
               _save(start_ts="2026-09-01 10:00:00x"),                                 # 17 chars
               _save(start_ts=None),
               _save(end_ts="E" * 17),
               _save(is_ongoing=None),                                                 # TypeError
               _save(cause=None),                                                      # 1048
               _save(created_by="c" * 191),
               _save(cause="x" * 70000),                                               # TEXT too long
               _save(created_by=None, cause="", hours_lost_override=0.0)):
        step(fn)


def test_update_breakdown_entry(step):
    for fn in (lambda m: m.update_breakdown_entry(1, "bob", cause="new cause", hours_lost_override=None),
               lambda m: m.update_breakdown_entry(1, "bob", unit_name="BF-9"),
               lambda m: m.update_breakdown_entry(1, "bob", unit_name="bf-9", plant="DSP"),     # plant + unit
               lambda m: m.update_breakdown_entry(2, "bob", plant="DSP"),                      # plant only
               lambda m: m.update_breakdown_entry(3, "bob", is_ongoing=True, end_ts=None, capital_repair_id=5),
               lambda m: m.update_breakdown_entry(3, "bob", capital_repair_id=None, sms_subtag=None),
               lambda m: m.update_breakdown_entry(4, "bob", unit_type="MILL", unit_name="SHOP"),
               lambda m: m.update_breakdown_entry(5, "bob", plant="BRAND"),                    # new plant
               lambda m: m.update_breakdown_entry(1, "bob", nope=1),                           # no allowed field
               lambda m: m.update_breakdown_entry(1, "bob"),
               lambda m: m.update_breakdown_entry(999, "bob", cause="x"),                      # no row
               lambda m: m.update_breakdown_entry(1, "bob", plant="P" * 9),
               lambda m: m.update_breakdown_entry(1, "bob", plant=None),
               lambda m: m.update_breakdown_entry(1, "bob", unit_name="U" * 33, plant="P" * 9),
               lambda m: m.update_breakdown_entry(1, "bob", unit_type=None),
               lambda m: m.update_breakdown_entry(1, "bob", start_ts="s" * 17),
               lambda m: m.update_breakdown_entry(1, "bob", end_ts="s" * 17, sms_subtag="t" * 17),
               lambda m: m.update_breakdown_entry(1, "bob", cause=None),
               lambda m: m.update_breakdown_entry(1, "b" * 191, cause="x"),
               lambda m: m.update_breakdown_entry(6, None, cause="by nobody", is_ongoing=0)):
        step(fn)


def test_delete_breakdown_entry(step):
    for fn in (lambda m: m.delete_breakdown_entry(4), lambda m: m.delete_breakdown_entry(4),
               lambda m: m.delete_breakdown_entry(999), lambda m: m.delete_breakdown_entry(6)):
        step(fn)


def _entry(row_id, plan=None, **k):
    plan = plan or {}
    base = dict(unit_type="BF", unit_name="BF-8", sms_subtag=None, start="2026-06-01", end="2026-06-30",
                ongoing=0, planned=12.5, actual="1 - 30 Jun")
    base.update(k)
    plan_sql = "".join(f", {f}=%s" for f in plan)
    params = (base["unit_type"], base["unit_name"], base["sms_subtag"], base["start"], base["end"],
              base["ongoing"], base["planned"], base["actual"], *plan.values(), row_id)
    return lambda m: on_cursor(lambda mod, cur: mod.update_cr_entry(cur, plan_sql, params), commit=True)(m)


def test_update_cr_entry(step):
    for fn in (_entry(1),
               _entry(1, plan={"shop": "New shop", "period": "Jun"}),
               _entry(2, unit_name=None, unit_type=None),                              # unit cleared
               _entry(3, unit_name="Fresh unit", unit_type="GENERAL"),                 # NULL unit now set
               _entry(3, unit_name="fresh unit"),                                      # other spelling
               _entry(4, start=None, end=None, ongoing=1, actual=None),
               _entry(5, plan={"shop": "s", "equipment": "e", "activity": "a", "schedule_days": "9",
                               "period": "p"}),
               _entry(99),                                                             # no such id
               _entry(1, unit_type="T" * 17),
               _entry(1, unit_name="U" * 33, unit_type="T" * 17),
               _entry(1, start="2026-06-011"),                                         # 1406 actual_start
               _entry(1, end="2026-06-30 12:00"),
               _entry(1, actual="a" * 129),
               _entry(1, plan={"shop": "s" * 65}),
               _entry(1, plan={"activity": "s" * 256})):
        step(fn)


def test_cr_renumber_and_ordered_ids(step):
    for fn in (lambda m: on_cursor(lambda mod, cur: mod.cr_renumber(cur, "BSP", "2026-27", [6, 3, 2, 1]),
                                   commit=True)(m),
               lambda m: on_cursor(lambda mod, cur: mod.cr_renumber(cur, "bsp", "2026-27", [1, 99, 2]),
                                   commit=True)(m),
               lambda m: on_cursor(lambda mod, cur: mod.cr_renumber(cur, "BSP", "2026-27", []),
                                   commit=True)(m),
               lambda m: on_cursor(lambda mod, cur: mod.cr_renumber(cur, "DSP", "2026-27", [1]),
                                   commit=True)(m)):          # id 1 is another plant's row
        step(fn)


def _insert(values):
    return lambda m: on_cursor(lambda mod, cur: (mod.insert_cr_row(cur, values), cur.lastrowid)[1], commit=True)(m)


def test_insert_and_delete_cr_row(step):
    base = ["BSP", "2026-27", "Shop", "Equip", "Act", "", "", "", "BF", "BF-8", None]
    for fn in (_insert(tuple(base)),
               _insert(("bsp", "2026-28", "", "", "", "", "", "", None, None, None)),      # no unit
               _insert(("NEWP", "2026-27", "s", "e", "a", "", "", "", "GENERAL", "Shop", None)),
               _insert(("BSP", "2026-27", "s", "e", "a", "", "", "", "SMS", "SHOP", "CASTER")),
               _insert(("BSP", "2026-27", "s", "e", "a", "", "", "", "BF", "", None)),     # empty unit name
               _insert(("P" * 9, "2026-27") + tuple(base[2:])),                            # 1406 plant
               _insert((None, "2026-27") + tuple(base[2:])),                               # 1048 plant
               _insert(("BSP", "2026-2799") + tuple(base[2:])),                            # 1406 fy
               _insert(("BSP", None) + tuple(base[2:])),                                   # 1048 fy
               _insert(("BSP", "2026-27", "s" * 65) + tuple(base[3:])),
               _insert(("BSP", "2026-27", "s", "e", "a", "d" * 65) + tuple(base[6:])),
               _insert(("BSP", "2026-27", "s", "e", "a", "", "", "a" * 129, "BF", "BF-8", None)),
               _insert(("BSP", "2026-27", "s", "e", "a", "", "", "", "T" * 17, "BF-8", None)),
               _insert(("BSP", "2026-27", "s", "e", "a", "", "", "", "BF", "U" * 33, "S" * 17)),
               lambda m: on_cursor(lambda mod, cur: mod.delete_cr_row(cur, 2), commit=True)(m),
               lambda m: on_cursor(lambda mod, cur: mod.delete_cr_row(cur, 2), commit=True)(m),
               lambda m: on_cursor(lambda mod, cur: mod.delete_cr_row(cur, 99), commit=True)(m)):
        step(fn)


def test_inputs_v2_cannot_store_are_refused_before_any_write(seeded):
    """parity_exceptions.md §2: v1 stored these as text; v2's DATE / CHAR(7)
    cannot hold them. Nothing is written, not even the data_version bump."""
    from repo.v2._keys import OutOfModelError
    tried = [lambda cur: b2.update_cr_entry(cur, "", ("BF", "BF-8", None, "2026-6-1", None, 0, 1.0, "a", 1)),
             lambda cur: b2.update_cr_entry(cur, "", ("BF", "BF-8", None, None, "soon", 0, 1.0, "a", 1)),
             lambda cur: b2.update_cr_entry(cur, "", ("BF", "BF-8", None, "", None, 0, 1.0, "a", 1)),
             lambda cur: b2.update_cr_entry(cur, "", ("BF", "BF-8", None, "2026-02-30", None, 0, 1.0, "a", 1)),
             lambda cur: b2.insert_cr_row(cur, ("BSP", "2026-278", "s", "e", "a", "", "", "", "BF", "BF-8", None)),
             lambda cur: b2.insert_cr_row(cur, ("BSP", "2026-27 ", "s", "e", "a", "", "", "", "BF", "BF-8", None))]
    with seeded.v2():
        n, before = seeded.data_version(2), {k: repr(v) for k, v in _reads(b2).items()}
        for t in tried:
            with pytest.raises(OutOfModelError):
                on_cursor(lambda mod, cur: t(cur), commit=True)(b2)
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(b2).items()} == before


def test_stored_timestamps_keep_v1_forms(seeded):
    """created_at / updated_at come back as datetime.now().isoformat() did,
    microseconds kept, and none when the microsecond is 0."""
    seeded.both(lambda m: m.save_breakdown_entry("BSP", "BF", "BF-8", None, "2026-09-01", None, False, "c",
                                                 None, "u"), v1=b1, v2=b2)
    rows = seeded.both(lambda m: m.list_breakdown_entries(plant="BSP", unit_type="BF")[0], v1=b1, v2=b2)
    assert rows[0] == rows[1] and rows[0]["created_at"] == "2026-10-23T14:30:05.250000"


def test_dangling_capital_repair_link_survives_the_cr_delete(step, seeded):
    step(lambda m: on_cursor(lambda mod, cur: mod.delete_cr_row(cur, 2), commit=True)(m))
    rows = seeded.both(lambda m: [r["capital_repair_id"] for r in m.list_breakdown_entries(plant="BSP")],
                       v1=b1, v2=b2)
    assert rows[0] == rows[1] and 2 in rows[0]


def test_every_v2_write_bumps_and_a_dry_run_does_not(seeded):
    writes = [lambda: b2.save_breakdown_entry("BSP", "BF", "BF-8", None, "2026-09-01", None, False, "c", None, "u"),
              lambda: b2.update_breakdown_entry(1, "bob", cause="y"),
              lambda: b2.delete_breakdown_entry(2),
              lambda: on_cursor(lambda mod, cur: mod.update_cr_entry(
                  cur, "", ("BF", "BF-8", None, "2026-06-01", None, 0, 1.0, "a", 1)), commit=True)(b2),
              lambda: on_cursor(lambda mod, cur: mod.cr_renumber(cur, "BSP", "2026-27", [1, 2]), commit=True)(b2),
              lambda: on_cursor(lambda mod, cur: mod.insert_cr_row(
                  cur, ("BSP", "2026-27", "s", "e", "a", "", "", "", "BF", "BF-8", None)), commit=True)(b2),
              lambda: on_cursor(lambda mod, cur: mod.delete_cr_row(cur, 3), commit=True)(b2),
              lambda: b2.delete_breakdown_entry(999)]
    with seeded.v2():
        for i, w in enumerate(writes):
            n = seeded.data_version(2)
            w()
            if i != len(writes) - 1:
                assert seeded.data_version(2) > n, i
            else:
                assert seeded.data_version(2) == n          # a missing row bumps nothing, as v1
        before = {k: repr(v) for k, v in _reads(b2).items()}
        n = seeded.data_version(2)
        with rc.rollback_tx():
            b2.save_breakdown_entry("DRY", "BF", "DRY-1", None, "2026-09-01", None, False, "c", None, "u")
            b2.update_breakdown_entry(1, "bob", cause="dry")
            on_cursor(lambda mod, cur: mod.cr_renumber(cur, "BSP", "2026-27", [2, 1]), commit=True)(b2)
            assert {k: repr(v) for k, v in _reads(b2).items()} != before
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(b2).items()} == before
    assert seeded.sql(2, "SELECT COUNT(*) FROM plant WHERE plant_code = 'DRY'")[0][0] == 0
    assert seeded.sql(2, "SELECT COUNT(*) FROM plant_unit WHERE unit_code = 'DRY-1'")[0][0] == 0
