"""v1 vs v2 equivalence of repo.techno (Task 7c).

Every write function runs through repo.techno on the v1 test schema and
through repo.v2.techno on the v2 test schema, seeded with the same logical
data; each side then reads back with its own module and the results must be
equal: blobs as dicts in key order with each leaf's type (canonical form of
tools/repo_oracle), the JSON TEXT the cursor helpers return byte for byte,
source_file, created_at as the v1 string, the activity-log old/new and the
extraction-log calls. The read functions the oracle never saw called (the
7a zero-call list) are called on both sides here too. Reads v1 served in
techno_data id order are compared strictly: v2's techno_upload.seq is that
id (equal in the test schemas too, both counters start at 1 and advance on
the same statements). The other reads whose v1 SQL has no ORDER BY are
compared as multisets: on these tiny schemas v1's access path is not the
one it takes on the real data, where tools/repo_oracle replay proves the
order.
"""
import datetime as dtmod
import re

import pymysql
import pytest

import activity_context
import dbengine
import report_context
from repo import conn as rc
from repo import techno as t1
from repo.v2 import _keys
from repo.v2 import techno as t2
from repo.v2codec import render_ts_flagged
from tools import repo_oracle as ro
from v2dual import multiset

ROW = dbengine.Row
M = ["2025-04", "2025-05"]
PL = ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]

SEED = [
    # ints vs floats, string / object / list / bool / explicit-null leaves,
    # -0.0 and an int beyond 2^53 (raw), created_at in the NOW() form
    ("2025-04", "BSP", "BF_Shop",
     {"month": {"coke_rate": 400.5, "bf_count": 7, "cdi": 120, "note": "ok", "meta": {"b": 1, "a": [1, 2.5]},
                "flag": True, "neg0": -0.0, "big": 2 ** 60, "nil": None, "unicode_é": 1.0},
      "till_month": {"coke_rate": 401.25, "five": 5.0}}, "a.xlsx", "2025-05-02 10:11:12"),
    # no till_month key; isoformat() with microseconds
    ("2025-04", "BSP", "General", {"month": {"sp_energy": 6.1}}, "b.xlsx", "2025-05-03T09:41:58.078837"),
    # empty till_month; isoformat() at microsecond 0
    ("2025-04", "DSP", "BF_Shop", {"month": {"coke_rate": 420}, "till_month": {}}, "", "2025-05-04T09:41:58"),
    # explicit nulls; created_at NULL
    ("2025-05", "BSP", "BF_Shop", {"month": {"coke_rate": None, "cdi": 120.0}, "till_month": {"cdi": None}}, "", None),
    # no month key; empty month elsewhere
    ("2025-05", "ISP", "BF-5", {"till_month": {"x": 1}}, "isp.pdf", "2025-06-01 08:00:00"),
    ("2025-04", "ISP", "BF-5", {"month": {}, "till_month": {"x": 2}}, "isp.pdf", "2025-05-01 08:00:00"),
    # tmi / fuel_rate inputs with stale derived values
    ("2025-05", "BSP", "BF-4", {"month": {"specific_hm_consumption": 900.5, "specific_scrap_consumption": 100,
                                          "tmi": 1.0, "coke_rate": 450, "cdi": 100.5, "fuel_rate": 3}},
     "bf4.xlsx", "2025-06-02 09:00:00"),
    ("2025-04", "SAIL", "Shop", {"month": {"coke_rate": 430.0}, "till_month": {"coke_rate": 431}}, "sail.xlsx",
     "2025-06-01T00:00:00.000001"),
    ("2025-05", "SAIL", "Shop", {"month": {"coke_rate": 431.5}, "till_month": {"coke_rate": 432}}, "sail.xlsx",
     "2025-06-03 00:00:00"),
    ("2025-04", "RSP", "General", {"month": {"rltifr": 0.5}}, "rsp.pdf", "2025-05-05 05:05:05"),
    ("2025-05", "RSP", "Coal_Consumption", {"month": {"indigenous_pcc": 12.5}}, "c.xlsx", "2025-06-05 05:05:05"),
]
PLAN_SEED = [
    ("BSP", "Shop", "2025-26", {"coke_rate": {"value": 410}, "cdi": 120.0}, 1, {"x": 1}, {"m": "avg"}),
    ("BSP", "BF-1", "2025-26", {"coke_rate": {"value": 415.5}}, 0, None, None),
    ("DSP", "Shop", "2025-26", {"coke_rate": 420}, 0, {}, {}),
    ("SAIL", "Shop", "2025-26", {"coke_rate": 425}, 1, {"coke_rate": 424.5}, {"coke_rate": "weighted"}),
    ("BSP", "Shop", "2024-25", {"coke_rate": 430}, 0, None, None),
]


@pytest.fixture
def seeded(dual):
    dual.seed_techno(SEED)
    dual.seed_techno_plan(PLAN_SEED)
    return dual


def canon(v):
    """Order- and type-preserving text (tools/repo_oracle canonical form)."""
    return ro.dumps(ro.canonical(v))


def _with_cur(fn, row_factory=None):
    """fn(module, cur) on a fresh db.connect() cursor."""
    def run(mod):
        conn = dbengine.connect()
        conn.row_factory = row_factory
        try:
            return fn(mod, conn.cursor())
        finally:
            conn.close()
    return run


def _same(dual, fn, unordered=False):
    r1, r2 = dual.both(fn, v1=t1, v2=t2)
    if unordered:
        assert multiset(ro.canonical(r1)) == multiset(ro.canonical(r2))
    else:
        assert canon(r1) == canon(r2)
    return r1


@pytest.fixture
def hooks(monkeypatch):
    """Record activity-log entries and extraction-log calls per side."""
    calls = {"activity": [], "log": []}
    monkeypatch.setattr(activity_context, "record",
                        lambda key, old, new: calls["activity"].append((key, canon(old), canon(new))))

    def log(**k):
        calls["log"].append({kk: vv for kk, vv in k.items() if kk != "conn"})
    import db
    from repo import ops
    monkeypatch.setattr(db, "log_extraction", log)
    monkeypatch.setattr(ops, "log_extraction", log)
    return calls


def _both_hooked(dual, hooks, fn):
    """fn on each side; the hook calls of each side must be equal."""
    got = []
    for side, mod in ((dual.v1, t1), (dual.v2, t2)):
        hooks["activity"].clear()
        hooks["log"].clear()
        with side():
            fn(mod)
        got.append((list(hooks["activity"]), list(hooks["log"])))
    assert got[0] == got[1]
    return got[0]


def _snapshot(mod, months=("2025-04", "2025-05", "2025-06", "2099-01"),
              plants=("BSP", "DSP", "RSP", "BSL", "ISP", "SAIL", "XYZ")):
    """Every blob read back through `mod`: get_techno_data per (plant, month)
    (dicts in key order with types) and the JSON text of every row."""
    out = {}
    for m in months:
        for p in plants:
            out[(m, p)] = canon(mod.get_techno_data(p, m))
    rows = _with_cur(lambda md, cur: md.rows_for_months(cur, list(months)))(mod)
    out["text"] = sorted(canon(r) for r in rows)
    # v1 id order == v2 seq order, also for rows written by the test
    out["all_json"] = canon(_with_cur(lambda md, cur: md.all_json(cur))(mod))
    for m in months:
        out[("month_rows", m)] = canon(_with_cur(lambda md, cur: md.month_rows(cur, m))(mod))
    out["signature"] = canon(tuple(_with_cur(lambda md, cur: md.months_signature_row(cur, list(months)))(mod))[:2])
    return out


_SQL_FORM = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d")
_ISO_FORM = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{6})?")


def _meta(dual):
    """{(month, plant, unit): (source_file, created_at v1 string)} per side."""
    v1 = {(r[0], r[1], r[2]): (r[3], r[4]) for r in dual.sql(
        1, "SELECT report_month, plant, unit, source_file, created_at FROM techno_data")}
    v2 = {(r[0], r[1], r[2]): (r[3], render_ts_flagged("techno_upload.created_at", r[4], r[5])) for r in dual.sql(
        2, "SELECT u.report_month, u.plant_code, pu.unit_code, u.source_file, u.created_at, u.created_at_iso "
           "FROM techno_upload u JOIN plant_unit pu ON pu.unit_id = u.unit_id")}
    return v1, v2


def _assert_same_data(dual, *, now_written=(), exact=()):
    """Blobs, texts and source_file equal; created_at: equal strings for the
    seeded rows and `exact` keys, the NOW() form and within a minute for
    `now_written` keys."""
    s1, s2 = dual.both(_snapshot, v1=t1, v2=t2)
    assert s1 == s2
    m1, m2 = _meta(dual)
    assert set(m1) == set(m2)
    for k in m1:
        assert m1[k][0] == m2[k][0], k
        a, b = m1[k][1], m2[k][1]
        if k in now_written:
            assert _SQL_FORM.fullmatch(a) and _SQL_FORM.fullmatch(b), (k, a, b)
            t_a, t_b = dtmod.datetime.fromisoformat(a), dtmod.datetime.fromisoformat(b)
            assert abs((t_a - t_b).total_seconds()) < 60, (k, a, b)
        else:
            assert a == b, (k, a, b)
    return m1, m2


def _seed_keys():
    return {(m, p, u) for m, p, u, *_ in SEED}


# ── merge_upsert / merge_upsert_techno_data ─────────────────────────────────

def test_merge_upsert_techno_data(seeded, hooks):
    """v1's merge rules, step by step, compared after every step (blobs in
    key order and types, the JSON text, source_file, created_at NOW() form,
    activity and extraction-log entries)."""
    written = set()
    steps = [
        # stored row: new non-null overwrites, a null keeps the stored value,
        # new keys are added, untouched keys survive; the tmi / fuel_rate
        # recompute runs (coke 399 + cdi 120 -> fuel_rate)
        ("BSP", "2025-04", "BF_Shop", {"month": {"coke_rate": 399.0, "bf_count": None, "sinter_rate": 130,
                                                 "brand_new": None}, "till_month": {}}, "c.xlsx", None),
        # clear_keys: a stored key is removed, a missing one is ignored, a
        # cleared key given a new value comes back with it
        ("BSP", "2025-04", "BF_Shop", {"month": {"note": "re-set"}, "till_month": {"five": None}}, "d.xlsx",
         {"month": ["note", "flag", "not_there"], "till_month": ["coke_rate"]}),
        # a stored blob without till_month gets till_month {} (both periods rebuilt)
        ("BSP", "2025-04", "General", {"month": {}}, "new-source.pdf", None),
        # a stored blob without month gets month {}
        ("ISP", "2025-05", "BF-5", {"till_month": {"y": 2.5}}, "", None),
        # no stored row: stored as given (None leaves kept as explicit nulls,
        # no till_month key stays missing), clear_keys ignored
        ("RSP", "2025-06", "BF_Shop", {"month": {"coke_rate": 410.0, "cdi": None}}, "x.xlsx", {"month": ["coke_rate"]}),
        # tmi and fuel_rate from stored inputs; ints stay ints
        ("BSP", "2025-05", "BF-4", {"month": {"coke_rate": 451}}, "bf4b.xlsx", None),
        # an ai_ci case variant of unit and plant updates the stored row (v1's
        # uq_techno), which keeps its spelling
        ("bsp", "2025-05", "bf_shop", {"month": {"cdi": 121}}, "variant.xlsx", None),
        # a brand-new unit of a known plant
        ("DSP", "2025-05", "SMS-1", {"month": {"tmi": 1050.0}}, "sms.xlsx", None),
    ]
    for plant, month, unit, blob, sf, clear in steps:
        acts, logs = _both_hooked(seeded, hooks,
                                  lambda m: m.merge_upsert_techno_data(plant, month, unit, blob, sf, clear_keys=clear))
        assert logs and logs[0]["source_type"] == "Techno Data"
        assert acts
        stored_key = (month, "BSP", "BF_Shop") if plant == "bsp" else (month, plant, unit)
        written.add(stored_key)
        _assert_same_data(seeded, now_written=written)
    # the primitive wrapper
    _both_hooked(seeded, hooks, lambda m: m.merge_upsert("2025-04", "DSP", "BF_Shop",
                                                         {"month": {"coke_rate": 1.5, "nut_coke_rate": None},
                                                          "till_month": {"x": 2}}, "s1"))
    written.add(("2025-04", "DSP", "BF_Shop"))
    _assert_same_data(seeded, now_written=written)
    # the recompute wrote the derived values (a second activity entry)
    got = seeded.both(lambda m: m.get_techno_data("BSP", "2025-05", "BF-4"), v1=t1, v2=t2)
    assert got[0]["BF-4"]["month"]["fuel_rate"] == 551.5 and got[0]["BF-4"]["month"]["tmi"] == 1000.5


def test_merge_upsert_on_a_caller_connection(seeded, hooks):
    """conn=...: the whole chain runs on the caller's transaction; nothing is
    committed by the repo (rollback leaves nothing; commit stores it)."""
    def run(commit):
        def fn(m):
            conn = dbengine.connect()
            try:
                m.merge_upsert_techno_data("BSP", "2025-04", "BF_Shop", {"month": {"coke_rate": 1.0}}, "conn.xlsx",
                                           conn=conn, clear_keys={"month": ["cdi"]})
                m.merge_upsert_techno_data("DSP", "2025-06", "BF-2", {"month": {"cdi": 2}}, "conn.xlsx", conn=conn)
                (conn.commit if commit else conn.rollback)()
            finally:
                conn.close()
        return fn
    before = seeded.both(_snapshot, v1=t1, v2=t2)
    _both_hooked(seeded, hooks, run(False))
    assert seeded.both(_snapshot, v1=t1, v2=t2) == before
    _both_hooked(seeded, hooks, run(True))
    _assert_same_data(seeded, now_written={("2025-04", "BSP", "BF_Shop"), ("2025-06", "DSP", "BF-2")})


def test_upsert_and_raw_upsert_replace_the_whole_blob(seeded, hooks):
    written = set()
    for fn in ("upsert_techno_data", "_raw_upsert_techno_data"):
        for plant, month, unit, blob in [
                ("BSP", "2025-04", "BF_Shop", {"month": {"coke_rate": 380, "cdi": 100.0}}),   # keys dropped
                ("RSP", "2025-04", "General", {"month": {"rltifr": None}, "till_month": {"r": "s"}}),
                ("BSL", "2025-05", "BF-1", {"month": {"specific_hm_consumption": 1, "specific_scrap_consumption": 2}}),
                ("SAIL", "2025-05", "Shop", {})]:
            _both_hooked(seeded, hooks, lambda m: getattr(m, fn)(plant, month, unit, blob, "up.xlsx"))
            written.add((month, plant, unit))
            _assert_same_data(seeded, now_written=written)


def test_iso_writers_store_the_isoformat_created_at(seeded, hooks, monkeypatch):
    """save_techno_json / save_techno_data_from_extraction /
    save_sail_techno_actuals: whole blob, created_at = datetime.now()
    rendered back as v1's isoformat() string (with and without a fraction),
    no activity-log or extraction-log entry (as v1)."""
    real = dtmod.datetime
    stamp = [real(2026, 10, 22, 9, 41, 58, 78837)]

    class FakeDT(real):
        @classmethod
        def now(cls, tz=None):
            return stamp[0]
    rows = [{"key": "coke_rate", "actual": 410.5, "cum_actual": 411},
            {"parameter": "Hot Blast Temp", "actual": 1100, "cum_actual": None},
            {"parameter": "Cdi", "actual": None, "cum_actual": 99.5}]
    exact = set()
    for us in (78837, 0):
        stamp[0] = real(2026, 10, 22, 9, 41, 58, us)
        with monkeypatch.context() as mp:
            mp.setattr(dtmod, "datetime", FakeDT)
            mp.setattr(t2, "datetime", FakeDT)
            acts, logs = _both_hooked(seeded, hooks, lambda m: (
                m.save_techno_json("BSP", "2025-04", "BF_Shop", {"month": {"x": 1}, "till_month": {}}, "j.json"),
                m.save_techno_json("BSL", "2025-06", "BF-2", {"till_month": {"y": None}}),
                m.save_techno_data_from_extraction("DSP", "2025-05", rows, source_file="ex.xlsx"),
                m.save_techno_data_from_extraction("ISP", "2025-05", rows, unit="BF-5"),
                m.save_sail_techno_actuals("2025-06", "Shop", {"month": {"coke_rate": 433.3}}, {"d": 1}, "calc"),
                m.save_sail_techno_actuals("2025-04", "Shop", {"month": {}})))
        assert acts == [] and logs == []
        exact |= {("2025-04", "BSP", "BF_Shop"), ("2025-06", "BSL", "BF-2"), ("2025-05", "DSP", "BF_Shop"),
                  ("2025-05", "ISP", "BF-5"), ("2025-06", "SAIL", "Shop"), ("2025-04", "SAIL", "Shop")}
        m1, m2 = _assert_same_data(seeded, exact=exact)
        want = "2026-10-22T09:41:58.078837" if us else "2026-10-22T09:41:58"
        assert all(m1[k][1] == want for k in exact)
    iso = seeded.sql(2, "SELECT COUNT(*) FROM techno_upload WHERE created_at_iso = 1 AND created_at >= '2026-10-22'")
    assert iso[0][0] == len(exact)


def test_recompute_standalone(seeded, hooks):
    """_maybe_recompute_derived_params (re-exported by db.py): writes only
    when a derived value changes (v2: no bump for a no-op), keeps the stored
    source_file, and matches v1's unit-spelling rule."""
    n = seeded.data_version(2)
    _both_hooked(seeded, hooks, lambda m: m._maybe_recompute_derived_params("BSP", "2025-04", "General"))
    assert seeded.data_version(2) == n                       # nothing derived: no write, no bump
    acts, _ = _both_hooked(seeded, hooks, lambda m: m._maybe_recompute_derived_params("BSP", "2025-05", "bf-4"))
    assert acts == []                                        # v1: .get(unit) misses a case variant
    acts, _ = _both_hooked(seeded, hooks, lambda m: m._maybe_recompute_derived_params("BSP", "2025-05", "BF-4"))
    assert len(acts) == 1
    assert seeded.data_version(2) > n
    _assert_same_data(seeded, now_written={("2025-05", "BSP", "BF-4")})
    m1, _ = _meta(seeded)
    assert m1[("2025-05", "BSP", "BF-4")][0] == "bf4.xlsx"


def test_recompute_failure_leaves_the_main_write_intact(seeded, hooks, monkeypatch):
    """A recompute that fails half-way (its leaves deleted, the new ones
    not inserted: a NaN leaf MySQL refuses) rolls back to its SAVEPOINT and
    is swallowed, as v1 swallowed it: the merged blob stays complete, on
    the chain's own transaction and on a caller's. A deadlock / lock wait
    timeout is re-raised and nothing is written."""
    seed = next(b for m, p, u, b, *_ in SEED if (m, p, u) == ("2025-04", "BSP", "BF_Shop"))
    new = {"month": {"coke_rate": 1.0}}
    def norm(v):        # MySQL JSON's normalised key order (byte length, then bytes), all levels
        if isinstance(v, dict):
            return {k: norm(v[k]) for k in sorted(v, key=lambda k: (len(k.encode()), k.encode()))}
        return [norm(x) for x in v] if isinstance(v, list) else v
    want = canon(norm(t2._merged(seed, new, None)))
    monkeypatch.setattr(t2, "_derived", lambda d: ({"month": {**d.get("month", {}), "bad": float("nan")},
                                                    "till_month": {}}, True))
    with seeded.v2():
        t2.merge_upsert_techno_data("BSP", "2025-04", "BF_Shop", new, "x")
        assert canon(t2.get_techno_data("BSP", "2025-04", "BF_Shop")["BF_Shop"]) == want
        conn = dbengine.connect()
        try:
            t2.merge_upsert_techno_data("BSP", "2025-04", "BF_Shop", new, "y", conn=conn)
            conn.commit()
        finally:
            conn.close()
        assert canon(t2.get_techno_data("BSP", "2025-04", "BF_Shop")["BF_Shop"]) == want
        assert seeded.sql(2, "SELECT source_file FROM techno_upload u JOIN plant_unit pu USING (unit_id) "
                             "WHERE u.report_month = '2025-04' AND u.plant_code = 'BSP' "
                             "AND pu.unit_code = 'BF_Shop'") == [("y",)]

        def deadlock(unit):
            def transform(stored):
                raise pymysql.err.OperationalError(1213, "Deadlock found when trying to get lock")
            return transform
        monkeypatch.setattr(t2, "_recompute", deadlock)
        before = _snapshot(t2)
        for conn_given in (False, True):
            conn = dbengine.connect() if conn_given else None
            try:
                with pytest.raises(pymysql.err.OperationalError) as e:
                    t2.merge_upsert_techno_data("BSP", "2025-04", "BF_Shop", {"month": {"coke_rate": 2.0}}, "z",
                                                conn=conn)
                assert e.value.args[0] == 1213
            finally:
                if conn is not None:
                    conn.rollback()
                    conn.close()
            assert _snapshot(t2) == before


def test_months_plants_and_units_outside_the_masters(seeded, hooks):
    """Unknown plant / month / unit: created as v1 stored them. A unit over
    v1's VARCHAR(32): the same DataError 1406 on both sides. A short
    non-month: v1 stored it, v2 refuses before the bump (as production)."""
    written = set()
    for plant, month, unit in [("XYZ", "2099-01", "BF_Shop"), ("BSP", "2099-01", "New Unit"),
                               ("XYZ", "2025-05", "General")]:
        _both_hooked(seeded, hooks, lambda m: m.merge_upsert_techno_data(plant, month, unit, {"month": {"a": 1}}, "o"))
        written.add((month, plant, unit))
    _assert_same_data(seeded, now_written=written)
    assert seeded.sql(2, "SELECT plant_kind FROM plant WHERE plant_code = 'XYZ'") == [("external",)]
    assert seeded.sql(2, "SELECT unit_type FROM plant_unit WHERE plant_code = 'BSP' AND unit_code = 'New Unit'") \
        == [(None,)]
    long_unit = "U" * 33
    for side, m in ((seeded.v1, t1), (seeded.v2, t2)):
        with side():
            conn = dbengine.connect()       # v1 would leak its own connection (and its bump's lock)
            try:
                with pytest.raises(pymysql.err.DataError) as e:
                    m.merge_upsert_techno_data("BSP", "2025-04", long_unit, {"month": {"a": 1}}, conn=conn)
                assert e.value.args == (1406, "Data too long for column 'unit' at row 1")
            finally:
                conn.rollback()
                conn.close()
    _assert_same_data(seeded, now_written=written)
    with seeded.v2():
        n = seeded.data_version(2)
        for bad in ("2025-4", "2025-13", ""):
            with pytest.raises(_keys.OutOfModelError):
                t2.merge_upsert_techno_data("BSP", bad, "BF_Shop", {"month": {"a": 1}})
            with pytest.raises(_keys.OutOfModelError):
                t2.save_techno_json("BSP", bad, "BF_Shop", {"month": {"a": 1}})
        assert seeded.data_version(2) == n


def test_unit_case_variants_match_v1(seeded, hooks):
    """unit_code is binary (fix round 1): a case variant of a unit in the
    SAME (month, plant) updates the stored row and keeps its spelling (v1's
    ON DUPLICATE KEY); in a month without a row for it, the caller's
    spelling is stored as a unit of its own, as v1 stored it per row. Reads
    match both under ai_ci, as v1."""
    written = set()
    for plant, month, unit, key in [("DSP", "2025-04", "bf_shop", ("2025-04", "DSP", "BF_Shop")),   # same month
                                    ("DSP", "2025-05", "bf_shop", ("2025-05", "DSP", "bf_shop")),   # other month
                                    ("DSP", "2025-05", "BF_SHOP", ("2025-05", "DSP", "bf_shop"))]:  # now stored
        _both_hooked(seeded, hooks, lambda m: m.merge_upsert_techno_data(plant, month, unit, {"month": {"a": 1}}))
        written.add(key)
        _assert_same_data(seeded, now_written=written)
    r1, r2 = seeded.both(lambda m: (m.get_techno_data("DSP", "2025-05"), m.get_techno_data("DSP", "2025-04"),
                                    m.get_techno_data("DSP", "2025-05", "Bf_Shop")), v1=t1, v2=t2)
    assert canon(r1) == canon(r2)
    assert list(r2[0]) == ["bf_shop"] and list(r2[1]) == ["BF_Shop"] and list(r2[2]) == ["bf_shop"]
    for fn in (lambda m, cur: m.distinct_units_for_plant(cur, "DSP"),
               lambda m, cur: m.units_for_plant_month(cur, "DSP", "2025-05"),
               lambda m, cur: m.bf_shop_rows(cur, "2025-05"),
               lambda m, cur: m.plant_unit_month_rows(cur, "DSP", "BF_Shop", M)):
        _same(seeded, _with_cur(fn))
    # no v1 ORDER BY: the small schema's access path differs from the real data's (replay proves it)
    _same(seeded, _with_cur(lambda m, cur: m.unit_plants_months_rows(cur, "bf_shop", PL, M)), True)
    assert {r[0] for r in seeded.sql(2, "SELECT unit_code FROM plant_unit WHERE plant_code = 'DSP'")} \
        == {"BF_Shop", "bf_shop", "Shop"}                     # 'Shop': the seeded plan's unit
    # the plans: a variant of a stored (plant, fy) plan updates it; in another fy it is its own unit
    for fy, unit in (("2025-26", "SHOP"), ("2026-27", "SHOP")):
        _both_hooked(seeded, hooks, lambda m: (_clear_plan_caches(m), m.save_techno_plan("DSP", fy, unit, {"v": fy})))
        p1, p2 = seeded.both(_plans, v1=t1, v2=t2)
        assert p1 == p2
    _same(seeded, _with_cur(lambda m, cur: m.plan_rows_for_fy(cur, "2026-27")))


def test_every_v2_write_bumps_and_a_dry_run_does_not(seeded):
    steps = [lambda: t2.merge_upsert("2025-04", "BSP", "BF_Shop", {"month": {"a": 1}}),
             lambda: t2.merge_upsert_techno_data("BSP", "2025-04", "BF_Shop", {"month": {"b": 1}}),
             lambda: t2.upsert_techno_data("BSP", "2025-04", "BF_Shop", {"month": {"c": 1}}),
             lambda: t2._raw_upsert_techno_data("BSP", "2025-04", "BF_Shop", {"month": {"c": 2}}),
             lambda: t2.save_techno_json("BSP", "2025-04", "BF_Shop", {"month": {"d": 1}}),
             lambda: t2.save_techno_data_from_extraction("BSP", "2025-04", [{"key": "e", "actual": 1}]),
             lambda: t2.save_sail_techno_actuals("2025-04", "Shop", {"month": {"f": 1}}),
             lambda: t2.save_techno_plan("BSP", "2025-26", "Shop", {"g": 1}),
             lambda: t2.save_techno_plant_plan("BSP", "2025-26", {"h": 1}),
             lambda: t2.save_sail_techno_plan("2025-26", {"i": 1})]
    with seeded.v2():
        for step in steps:
            n = seeded.data_version(2)
            step()
            assert seeded.data_version(2) > n
        before = _snapshot(t2)
        n = seeded.data_version(2)
        with rc.rollback_tx():
            for step in steps:
                step()
            t2.merge_upsert("2025-06", "XYZ", "Dry Unit", {"month": {"dry": 1}})
            assert _snapshot(t2) != before                  # the dry run sees its own writes
        assert seeded.data_version(2) == n
        assert _snapshot(t2) == before


# ── techno_plan_fy ──────────────────────────────────────────────────────────

def _clear_plan_caches(m):
    m._get_techno_plan_cached.cache_clear()
    m._get_techno_plant_plan_cached.cache_clear()
    m._get_sail_techno_plan_cached.cache_clear()


def _plans(m):
    _clear_plan_caches(m)
    out = {}
    for p in ("BSP", "DSP", "SAIL", "XYZ"):
        for fy in ("2024-25", "2025-26", "2026-27"):
            out[("plan", p, fy)] = canon(m.get_techno_plan(p, fy))
            for u in ("Shop", "BF-1", "shop", "NEW"):
                out[("plan", p, fy, u)] = canon(m.get_techno_plan(p, fy, u))
                out[("row", p, fy, u)] = canon(_with_cur(lambda md, cur: md.plan_json_row(cur, p, u, fy))(m))
            out[("plant", p, fy)] = canon(m.get_techno_plant_plan(p, fy))
        out[("fys", p)] = canon(m.list_techno_plan_fys(p))
    for fy in ("2024-25", "2025-26", "2026-27"):
        out[("sail", fy)] = canon(m.get_sail_techno_plan(fy))
        out[("fy", fy)] = canon(_with_cur(lambda md, cur: md.plan_rows_for_fy(cur, fy))(m))
        out[("plants", fy)] = canon(_with_cur(lambda md, cur: md.plan_plants_rows(cur, ["SAIL", "BSP", "DSP"],
                                                                                    fy, "Shop"))(m))
    out["fys"] = canon(m.list_techno_plan_fys())
    _clear_plan_caches(m)
    return out


def test_techno_plan_writes(seeded, hooks):
    steps = [lambda m: m.save_techno_plan("BSP", "2025-26", "Shop", {"coke_rate": {"value": 1}}, True,
                                          {"c": 2.0}, {"k": "v"}, "me@x"),                     # update
             lambda m: m.save_techno_plan("BSP", "2026-27", "BF-1", {"cdi": 5}),               # new row
             lambda m: m.save_techno_plan("bsp", "2025-26", "shop", {"coke_rate": 2}),         # ai_ci variant
             lambda m: m.save_techno_plant_plan("DSP", "2026-27", {"x": None}, False, None, None, "a"),
             lambda m: m.save_sail_techno_plan("2025-26", {"coke_rate": 426}, True, {"y": 1}),
             lambda m: m.save_techno_plan("XYZ", "2026-27", "NEW", {"n": 1})]                  # new plant / unit
    for step in steps:
        _both_hooked(seeded, hooks, lambda m: (_clear_plan_caches(m), step(m)))
        p1, p2 = seeded.both(_plans, v1=t1, v2=t2)
        assert p1 == p2


def test_month_and_fy_with_trailing_spaces(seeded, hooks):
    """Task 7e1 (_keys.fit_month / fit_fy): v1's merge read and activity
    'old' used the raw '2025-04 ' and found nothing, so the merge stored the
    new blob as given; its ON DUPLICATE KEY then replaced the stored
    '2025-04' row. A plan FY '2025-26 ' updates the stored '2025-26' plan
    the same way (activity old None)."""
    written = set()
    steps = [(lambda m: m.merge_upsert_techno_data("BSP", "2025-04 ", "BF_Shop", {"month": {"zz": 1}}, "t.x"),
              ("2025-04", "BSP", "BF_Shop")),
             (lambda m: m.upsert_techno_data("DSP", "2025-04  ", "BF_Shop", {"month": {"coke_rate": 9}}),
              ("2025-04", "DSP", "BF_Shop")),
             (lambda m: m.merge_upsert("2025-06 ", "RSP", "General", {"month": {"q": 2.5}}),
              ("2025-06", "RSP", "General"))]
    for step, key in steps:
        _both_hooked(seeded, hooks, step)
        written.add(key)
        _assert_same_data(seeded, now_written=written)
    for step in (lambda m: m.save_techno_plan("BSP", "2025-26 ", "Shop", {"coke_rate": 3}),
                 lambda m: m.save_techno_plan("BSP", "2027-28 ", "shop", {"coke_rate": 4})):
        _both_hooked(seeded, hooks, lambda m: (_clear_plan_caches(m), step(m)))
        p1, p2 = seeded.both(_plans, v1=t1, v2=t2)
        assert p1 == p2


def test_registry_writes_fail_alike(seeded):
    """The registry helpers name tables neither schema has: the same error."""
    def run(fn):
        def go(m):
            conn = dbengine.connect()
            try:
                fn(m, conn.cursor())
            except Exception as e:      # noqa: BLE001
                return type(e).__name__, e.args[0]
            finally:
                conn.close()
            return None
        return go
    for fn in (lambda m, cur: m.insert_ignore_plant_unit(cur, "BSP", "BF", "BF-1", "BF 1", 0, 1),
               lambda m, cur: m.insert_ignore_param_type(cur, "BF", "coke_rate", "kg/thm", "avg", 1),
               lambda m, cur: m.update_param_master_unit(cur, "BF-1", 7),
               lambda m, cur: m.param_master_unit_rows(cur)):
        r1, r2 = seeded.both(run(fn), v1=t1, v2=t2)
        assert r1 == r2 and r1 is not None and r1[1] == 1146


# ── reads the oracle never saw called (7a zero-call list) and the bulk path ─

@pytest.mark.parametrize("row_factory", [None, ROW])
def test_zero_call_cursor_reads(seeded, row_factory):
    def c(fn, unordered=False):
        return _same(seeded, _with_cur(fn, row_factory), unordered)

    assert c(lambda m, cur: m.distinct_plants(cur))
    for p in ("BSP", "bsp", "SAIL", "XYZ"):
        for month in M:
            c(lambda m, cur: m.units_for_plant_month(cur, p, month))
            for u in ("BF_Shop", "bf_shop", "General", "Shop", "nope"):
                c(lambda m, cur: m.json_cell(cur, p, month, u))
                c(lambda m, cur: m.json_row(cur, p, month, u))
    assert c(lambda m, cur: m.non_sail_rows(cur))                        # id order = seq
    assert c(lambda m, cur: m.general_rows_with_source(cur))
    rows = c(lambda m, cur: m.rows_for_plants(cur, ["BSP", "ISP", "SAIL"]))  # plant, month, then id
    assert len(rows) == 8
    assert c(lambda m, cur: m.sail_rows(cur))
    assert c(lambda m, cur: m.sail_unit_rows(cur, "Shop"))
    for fy in ("2025-26", "2024-25", "1999-00"):
        for p, u in (("BSP", "Shop"), ("BSP", "BF-1"), ("bsp", "SHOP"), ("SAIL", "Shop")):
            c(lambda m, cur: m.plan_json_row(cur, p, u, fy))
    c(lambda m, cur: m.distinct_units_for_plant(cur, "BSP"))
    c(lambda m, cur: m.distinct_report_months(cur), True)
    c(lambda m, cur: m.five_plant_first_month_row(cur))
    c(lambda m, cur: m.five_plant_first_months(cur))
    for unit in (["BF_Shop", "BF-5"], ["General"], ["BF-4", "bf_shop"]):
        c(lambda m, cur: m.plant_unit_month_rows(cur, "BSP", unit[0], M))
        c(lambda m, cur: m.plant_units_month_rows(cur, "BSP", unit, M), True)
        c(lambda m, cur: m.unit_plants_months_rows(cur, unit[0], PL, M), True)
        c(lambda m, cur: m.five_plant_unit_rows(cur, unit))              # id order = seq
    for month in M:
        c(lambda m, cur: m.month_rows(cur, month))                       # id order = seq
        c(lambda m, cur: m.bf_shop_rows(cur, month))
        c(lambda m, cur: m.coal_blend_rows(cur, month, PL), True)
        c(lambda m, cur: m.plants_month_rows(cur, month, PL))
    c(lambda m, cur: m.all_json(cur))


def test_months_signature_row(seeded):
    """(COUNT(*), MAX(id), MAX(created_at)): equal, MAX(seq) being v1's MAX(id)."""
    for rf in (None, ROW):
        for months in (M, ["2025-04"], ["2030-01"], ["2025-05", "2025-06"]):
            r1, r2 = seeded.both(_with_cur(lambda m, cur: m.months_signature_row(cur, months), rf), v1=t1, v2=t2)
            assert canon(r1) == canon(r2)


def test_zero_call_connection_reads(seeded):
    def c(fn):
        return _same(seeded, fn)

    months = ["2025-04", "2025-05", "2025-06"]
    for plants in (None, ["BSP"], ["bsp", "SAIL"], []):
        for units in (None, ["BF_Shop"], ["general", "BF-5"], []):
            r1, r2 = seeded.both(lambda m: m.blobs(months, plants, units), v1=t1, v2=t2)
            assert sorted(canon(kv) for kv in r1.items()) == sorted(canon(kv) for kv in r2.items())
    for month in months:
        c(lambda m: m.get_sail_techno_actuals(month))
        for p in ("BSP", "isp", "XYZ"):
            c(lambda m: m.get_techno_data(p, month))
            for u in ("BF_Shop", "bf-5", "General", None, ""):
                c(lambda m: m.get_techno_data(p, month, u))
            records = [{"unit": "BF_Shop", "v": 1}, {"unit": "BF-5"}, {"unit": "bf_shop"}, {}]
            c(lambda m: m.enrich_techno_records_with_db([dict(r) for r in records], p, month))
            c(lambda m: m.enrich_techno_records_with_db([], p, month))
    c(lambda m: m.get_techno_months())
    c(lambda m: m.get_techno_months("BSP"))
    c(lambda m: m.get_techno_months("XYZ"))
    c(lambda m: m.list_techno_plan_fys())


def test_report_context_bulk_reads(seeded):
    """Inside report_context.activate the reads are served by _bulk_load,
    whose rows (texts included) equal v1's in v1's ORDER BY."""
    def run(m):
        with report_context.activate("2025-05"):
            out = [m._bulk_load("2024-04", "2026-03"),
                   m.blobs(["2025-04", "2025-05"]), m.blobs(["2025-04"], ["bsp"], ["bf_shop", "General"]),
                   m.get_sail_techno_actuals("2025-04"), m.get_techno_data("BSP", "2025-04"),
                   m.get_techno_data("isp", "2025-05", "bf-5")]
            conn = dbengine.connect()
            try:
                out.append([m.json_cell(conn.cursor(), "BSP", "2025-04", u) for u in ("BF_Shop", "general", "x")])
            finally:
                conn.close()
            return out
    _same(seeded, run)
