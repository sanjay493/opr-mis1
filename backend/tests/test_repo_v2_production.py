"""v1 vs v2 equivalence of repo.production / repo.capacity (Task 7b).

Every write function runs through repo.<module> on the v1 test schema and
through repo.v2.<module> on the v2 test schema, seeded with the same logical
data; each side then reads back with its own module and the results must be
equal. The read functions the oracle never saw called (the 7a zero-call
list) are called on both sides here too. Reads whose v1 SQL has no ORDER BY
are compared as multisets (tests/v2dual.multiset): their v1 order is the
access path MySQL picks, which the oracle replay proves on the real data.
"""
import pytest

import activity_context
from _v1_frozen import capacity as cap1
from repo import conn as rc
from _v1_frozen import production as p1
from repo import _keys
from repo import capacity as cap2
from repo import production as p2
from v2dual import as_plain, multiset

M = ["2025-04", "2025-05", "2025-06"]
PL = ["BSP", "DSP", "RSP", "BSL", "ISP"]

SEED = [
    ("actual", "2025-04", "BSP", "Hot Metal", 1500.5),
    ("actual", "2025-05", "BSP", "Hot Metal", 1490.25),
    ("actual", "2025-06", "BSP", "Hot Metal", None),
    ("actual", "2025-04", "DSP", "Hot Metal", 300.1),
    ("actual", "2025-05", "DSP", "Hot Metal", 310.2),
    ("actual", "2025-04", "BSP", "Total Crude Steel", 1200.0),
    ("actual", "2025-04", "BSL", "BF-1", 100.1),
    ("actual", "2025-04", "BSL", "BF-2", 200.2),
    ("actual", "2025-04", "BSL", "BF-5", None),
    ("actual", "2025-04", "BSP", "CC BILLET", 7.7),
    ("actual", "2025-05", "BSP", "CC Billet", 8.8),
    ("actual", "2025-04", "SAIL", "Conversion", 55.5),
    ("actual", "2025-05", "SAIL", "Conversion", None),
    ("actual", "2025-04", "SSP", "Saleable Steel", 20.0),
    ("abp", "2025-04", "BSP", "Hot Metal", 1600.0),
    ("abp", "2025-05", "BSP", "Hot Metal", 1610.0),
    ("abp", "2025-04", "DSP", "Total Crude Steel", 330.0),
    ("abp", "2025-04", "BSP", "Total Crude Steel", 1300.0),
    ("abp", "2025-04", "BSP", "SMS-1 Steel", 500.0),
    ("abp", "2025-05", "BSP", "SMS 2", 600.0),
    ("abp", "2025-04", "BSP", "CC Billet", 9.9),
    ("abp", "2025-04", "ISP", "Hot Metal", None),
    ("mou", "2025-04", "BSP", "Hot Metal", 1700.0),
    ("mou", "2025-04", "DSP", "Hot Metal", None),
]


@pytest.fixture
def seeded(dual):
    dual.seed_production(SEED)
    return dual


def _same(dual, fn, unordered=False):
    r1, r2 = dual.both(fn, v1=p1, v2=p2)
    if unordered:
        assert multiset(r1) == multiset(r2)
    else:
        assert as_plain(r1) == as_plain(r2)
    return r1


def _with_cur(fn, row_factory=None):
    """fn(module, cur) on a fresh db.connect() cursor."""
    def run(mod):
        import dbengine
        conn = dbengine.connect()
        conn.row_factory = row_factory
        try:
            return fn(mod, conn.cursor())
        finally:
            conn.close()
    return run


def _snapshot(mod):
    """Every row of every measure, read back through `mod`."""
    out = {}
    for measure in ("actual", "abp", "mou"):
        for plant in ("BSP", "DSP", "RSP", "BSL", "ISP", "SSP", "SAIL", "XYZ", "xyz2", ""):
            rows = _with_cur(lambda m, cur: m.plant_all_rows(cur, measure, plant))(mod)
            out[(measure, plant)] = sorted(tuple(r) for r in rows)
    return out


def _assert_same_data(dual):
    s1, s2 = dual.both(_snapshot, v1=p1, v2=p2)
    assert s1 == s2


# ── writes ──────────────────────────────────────────────────────────────────

def test_upsert(seeded):
    rows = [("2025-04", "BSP", "Hot Metal", 1.0),           # update an existing actual
            ("2025-06", "RSP", "Hot Metal", 2.0),           # new row
            ("2025-05", "BSP", "cc billet", 3.0),           # ai_ci match: keeps 'CC Billet'
            ("2025-04", "BSP", "Total Crude Steel", None)]  # a row holding NULL
    for measure in ("actual", "abp", "mou"):
        seeded.both(lambda m: m.upsert(measure, rows), v1=p1, v2=p2)
    _assert_same_data(seeded)
    seeded.both(lambda m: m.upsert("actual", []), v1=p1, v2=p2)
    _assert_same_data(seeded)


def test_upsert_of_one_measure_leaves_the_others(seeded):
    seeded.both(lambda m: m.upsert("abp", [("2025-04", "BSP", "Hot Metal", 42.0)]), v1=p1, v2=p2)
    _assert_same_data(seeded)
    row = seeded.sql(2, "SELECT actual, abp_plan, mou_plan, has_actual, has_abp, has_mou "
                        "FROM production_monthly pm JOIN item i USING (item_id) "
                        "WHERE report_month='2025-04' AND plant_code='BSP' AND item_name='Hot Metal'")
    assert list(row) == [(1500.5, 42.0, 1700.0, 1, 1, 1)]


def test_delete(seeded):
    # one sequence, compared after every step: [], two items (one by a case
    # variant), one item, then the whole (month, plant)
    for items in ([], ["cc billet", "Total Crude Steel"], ["Hot Metal"], None):
        for measure in ("actual", "abp", "mou"):
            seeded.both(lambda m: m.delete(measure, "2025-04", "BSP", items), v1=p1, v2=p2)
            _assert_same_data(seeded)
        # ck_production_source: no v2 row is left without a measure
        assert seeded.sql(2, "SELECT COUNT(*) FROM production_monthly "
                             "WHERE has_actual + has_abp + has_mou = 0")[0][0] == 0


def test_delete_of_one_measure_keeps_the_others_and_absent_vs_null(seeded):
    seeded.both(lambda m: m.delete("actual", "2025-04", "BSP", ["Hot Metal"]), v1=p1, v2=p2)
    _assert_same_data(seeded)
    row = seeded.sql(2, "SELECT actual, abp_plan, has_actual, has_abp FROM production_monthly pm "
                        "JOIN item i USING (item_id) "
                        "WHERE report_month='2025-04' AND plant_code='BSP' AND item_name='Hot Metal'")
    assert list(row) == [(None, 1600.0, 0, 1)]
    # absent (no row) vs a row holding NULL, through value_row
    for args in (("actual", "2025-04", "BSP", "Hot Metal"), ("actual", "2025-06", "BSP", "Hot Metal")):
        r = _same(seeded, _with_cur(lambda m, cur: m.value_row(cur, *args)))
        assert r == (None if args[1] == "2025-04" else (None,))


def test_save_production(seeded, monkeypatch):
    calls = []
    monkeypatch.setattr(activity_context, "record", lambda *a: calls.append(a))
    for fn in ("save_production_actual", "save_production_plan"):
        for item in ("Hot Metal", " hot metal ", "New Item", "CC BILLET"):
            for value in (123.4, None, 5.0):
                calls.clear()
                seeded.both(lambda m: getattr(m, fn)("2025-05", "BSP", item, value), v1=p1, v2=p2)
                _assert_same_data(seeded)
                assert len(calls) == 2 and calls[0] == calls[1], (fn, item, value)


def test_upsert_row_and_bsl_furnace(seeded):
    def write(m):
        _with_cur(lambda mod, cur: (mod.upsert_row(cur, "mou", "2025-05", "DSP", "Hot Metal", 9.5),
                                    mod.upsert_row(cur, "actual", "2025-06", "BSP", "cc billet", 1.25),
                                    mod.upsert_row(cur, "abp", "2025-06", "SSP", "Saleable Steel", None),
                                    mod.upsert_bsl_furnace_production(cur, "2025-04", "BF-1", 99.9),
                                    mod.upsert_bsl_furnace_production(cur, "2025-05", "BF-4", 11.0),
                                    cur.execute("COMMIT")))(m)
    seeded.both(write, v1=p1, v2=p2)
    _assert_same_data(seeded)


def test_every_v2_write_bumps_data_version(seeded):
    with seeded.v2():
        steps = [lambda: p2.upsert("actual", [("2025-04", "BSP", "Hot Metal", 1.0)]),
                 lambda: p2.delete("abp", "2025-04", "BSP"),
                 lambda: p2.save_production_actual("2025-04", "BSP", "X", 1.0),
                 lambda: p2.save_production_plan("2025-04", "BSP", "X", None)]
        for step in steps:
            n = seeded.data_version(2)
            step()
            assert seeded.data_version(2) > n


def test_months_outside_the_seeded_calendar_and_unknown_plants_are_stored_as_v1(seeded):
    """v1 stored any month / plant string; v2 creates the cal_month / plant
    master row it needs (repo/v2/_keys.py), so the read-back is equal."""
    rows = [("1950-01", "BSP", "Hot Metal", 1.0), ("2099-01", "BSP", "Hot Metal", 2.0),
            ("2025-04", "XYZ", "Hot Metal", 3.0), ("2099-12", "xyz2", "New", None),
            ("2025-05", "", "Hot Metal", 4.0)]
    for measure in ("actual", "abp"):
        seeded.both(lambda m: m.upsert(measure, rows), v1=p1, v2=p2)
        _assert_same_data(seeded)
    seeded.both(lambda m: m.save_production_actual("1950-02", "XYZ", "Hot Metal", 5.0), v1=p1, v2=p2)
    seeded.both(lambda m: m.save_production_plan("2099-01", "XYZ", "Hot Metal", None), v1=p1, v2=p2)
    seeded.both(lambda m: m.delete("actual", "2099-01", "BSP"), v1=p1, v2=p2)
    _assert_same_data(seeded)
    for args in (("actual", "1950-01", "BSP", "Hot Metal"), ("actual", "2025-04", "xyz", "hot metal"),
                 ("abp", "2099-12", "XYZ2", "new")):
        _same(seeded, _with_cur(lambda m, cur: m.value_row(cur, *args)))
    cm = seeded.sql(2, "SELECT report_month, month_start, fy, fy_month, quarter, half FROM cal_month "
                       "WHERE report_month IN ('1950-01', '2099-12') ORDER BY report_month")
    assert [tuple(r) for r in cm] == [("1950-01", "1950-01-01", "1949-50", 10, 4, 2),
                                      ("2099-12", "2099-12-01", "2099-00", 9, 3, 2)]
    assert [tuple(r) for r in seeded.sql(2, "SELECT plant_code, plant_name, plant_kind FROM plant "
                                            "WHERE plant_kind = 'external' ORDER BY plant_code")] ==         [("", None, "external"), ("XYZ", None, "external"), ("xyz2", None, "external")]


def test_month_strings_that_are_not_months(seeded):
    """Longer than CHAR(7): the same DataError 1406 on both. A short non-month
    ('2025-4'): v1 stored it as text; v2 cannot (cal_month needs a real
    month) and refuses before the bump - the one remaining divergence."""
    import pymysql
    for m in (p1, p2):
        with (seeded.v1() if m is p1 else seeded.v2()):
            with pytest.raises(pymysql.err.DataError) as e:
                m.upsert("actual", [("2025-04-01", "BSP", "Hot Metal", 1.0)])
            assert e.value.args[0] == 1406
    with seeded.v2():
        n = seeded.data_version(2)
        for bad in ("2025-4", "2025-13", "abc", ""):
            with pytest.raises(_keys.OutOfModelError):
                p2.upsert("actual", [(bad, "BSP", "Hot Metal", 1.0)])
            with pytest.raises(_keys.OutOfModelError):
                p2.save_production_actual(bad, "BSP", "Hot Metal", 1.0)
        assert seeded.data_version(2) == n
        p2.save_production_actual("2025-4", "BSP", "Hot Metal", None)   # a delete: matches nothing


def test_cal_month_row_matches_the_seed(seeded):
    rows = seeded.sql(2, "SELECT report_month, month_start, fy, fy_month, quarter, half FROM cal_month "
                         "ORDER BY report_month")
    assert len(rows) >= 960
    for r in rows:
        assert _keys.cal_month_row(r[0]) == tuple(r), r


def test_new_case_variant_creates_its_own_item(seeded):
    """No row of that (month, plant, measure) holds a variant: the caller's
    exact spelling is stored (v1 stored it verbatim)."""
    seeded.both(lambda m: m.upsert("actual", [("2025-06", "BSP", "Cc BiLLeT", 1.0)]), v1=p1, v2=p2)
    _assert_same_data(seeded)
    names = {r[0] for r in seeded.sql(2, "SELECT item_name FROM item WHERE item_name COLLATE utf8mb4_0900_ai_ci LIKE 'cc%%'")}
    assert names == {"CC BILLET", "CC Billet", "Cc BiLLeT"}


def test_plan_preview_rows_dry_runs_the_extractor(seeded):
    def run(m):
        import dbengine

        def extractor():
            conn = dbengine.connect()
            cur = conn.cursor()
            m.upsert_row(cur, "abp", "2025-06", "BSP", "Hot Metal", 1.5)
            m.upsert_row(cur, "abp", "2025-06", "BSP", "brand new item", 2.5)
            m.upsert_row(cur, "abp", "2025-06", "DSP", "CC BILLET", None)
            conn.commit()
            conn.close()
        return m.plan_preview_rows(extractor)
    before = seeded.both(_snapshot, v1=p1, v2=p2)
    n2 = seeded.data_version(2)
    _same(seeded, run)
    assert seeded.both(_snapshot, v1=p1, v2=p2) == before
    assert seeded.data_version(2) == n2
    assert seeded.sql(2, "SELECT COUNT(*) FROM item WHERE item_name = 'brand new item'")[0][0] == 0


# ── reads the oracle never saw called (7a zero-call list) ───────────────────

ROW = __import__("dbengine").Row


@pytest.mark.parametrize("row_factory", [None, ROW])
def test_zero_call_cursor_reads(seeded, row_factory):
    def c(fn, unordered=False):
        return _same(seeded, _with_cur(fn, row_factory), unordered)

    assert c(lambda m, cur: m.actual_history(cur, "BSP", "hot metal", "2025-04", "2025-06"), True)
    assert c(lambda m, cur: m.bsl_bf_shop_production_sum(cur, "2025-04")) == pytest.approx(300.3)
    assert c(lambda m, cur: m.bsl_bf_shop_production_sum(cur, "2025-05")) is None
    assert c(lambda m, cur: m.item_plants_all_months(cur, "Hot Metal", PL), True)
    assert c(lambda m, cur: m.items_plant_all_months(cur, ["Hot Metal", "cc billet"], "BSP"), True)
    assert c(lambda m, cur: m.latest_hot_metal_month_row(cur))[0] == "2025-05"
    assert c(lambda m, cur: m.plan_crude_steel_by_plant(cur, M), True)
    assert c(lambda m, cur: m.plan_sms_items_by_plant(cur, M), True)
    for measure in ("actual", "abp", "mou"):
        assert c(lambda m, cur: m.plant_all_rows(cur, measure, "BSP"), True)
        assert c(lambda m, cur: m.plant_item_value_row(cur, measure, "BSP", "HOT METAL", "2025-04"))
    assert c(lambda m, cur: m.plant_item_value_row(cur, "abp", "RSP", "Hot Metal", "2025-04")) is None
    assert c(lambda m, cur: m.plant_item_months(cur, "BSP", "Hot Metal"), True)
    assert c(lambda m, cur: m.plant_rows_for_months(cur, "BSP", M), True)
    assert c(lambda m, cur: m.sail_conversion_actual(cur, "2025-04")) == 55.5
    assert c(lambda m, cur: m.sail_conversion_actual(cur, "2025-05")) is None
    assert c(lambda m, cur: m.sum_months_cell(cur, "actual", "BSP", "Hot Metal", M))[0] == pytest.approx(2990.75)
    assert c(lambda m, cur: m.sum_months_cell(cur, "abp", "RSP", "Hot Metal", M)) is not None
    scopes = [p1.records_scope(PL), p1.records_scope(PL, ["Hot Metal", "BF-1"]),
              p1.records_scope(["BSP"], None, "2025-04")]
    for scope in scopes:
        assert p2.records_scope(*([PL] if scope is scopes[0] else
                                  [PL, ["Hot Metal", "BF-1"]] if scope is scopes[1] else
                                  [["BSP"], None, "2025-04"])) == scope
        for bucket in ("quarter", "half", "fy", "cy"):
            assert c(lambda m, cur: m.records_bucket_cells(cur, scope, bucket), True)
        assert c(lambda m, cur: m.records_fy_window_cells(cur, scope, 0, 1), True)
    assert c(lambda m, cur: m.records_plants_items_in(cur, PL), True)


def test_zero_call_connection_reads(seeded):
    assert _same(seeded, lambda m: m.get_production_actual_for_months("BSP", "hot metal", M + ["2025-07"]))
    assert _same(seeded, lambda m: m.get_production_actual_for_months("BSP", "Hot Metal", [])) == {}
    rows = [{"item_name": "Hot Metal"}, {"pdf_label": "CC BILLET"}, {"item_name": "Hot Metal",
                                                                     "report_month": "2025-05"},
            {"item_name": "hot metal"}, {}]
    r1, r2 = seeded.both(lambda m: m.enrich_rows_with_db_production([dict(r) for r in rows], "BSP", "2025-04"),
                         v1=p1, v2=p2)
    assert r1 == r2 and r1[0]["db_value"] == 1500.5
    for months, plants, items in ((M, None, None), (M, ["bsp"], ["hot metal"]), (M, [], None), ([], None, None)):
        for measure in ("actual", "abp", "mou"):
            v1, v2 = seeded.both(lambda m: m.values(months, plants, items, measure), v1=p1, v2=p2)
            assert v1 == v2


# ── capacity ────────────────────────────────────────────────────────────────

CAP_SEED = [
    (1, "BSP", "Hot Metal", "2024-04", 7000.0, "", "a@x", "2026-08-19T11:02:50.043984", "a@x",
     "2026-08-19T11:02:50.043984"),
    (2, "BSP", "Hot Metal", "2025-10", 7500.0, "BF-8", "a@x", "2026-08-19T11:03:23", "b@x",
     "2026-09-01T10:00:00.000001"),
    (3, "DSP", "Finished Steel", "2024-04", 2000.0, None, None, None, None, None),
]


@pytest.fixture
def cap_seeded(dual):
    dual.seed_capacity(CAP_SEED)
    return dual


def _cap_same(dual, fn):
    r1, r2 = dual.both(fn, v1=cap1, v2=cap2)
    assert as_plain(r1) == as_plain(r2)
    return r1


def _cap_all(m):
    return m.list_capacity_entries()


def test_capacity_reads(cap_seeded):
    assert len(_cap_same(cap_seeded, _cap_all)) == 3
    _cap_same(cap_seeded, lambda m: m.list_capacity_entries("bsp", "HOT METAL"))
    for month in ("2024-03", "2024-04", "2025-09", "2025-10", "2030-01"):
        _cap_same(cap_seeded, lambda m: m.get_effective_capacity("BSP", "hot metal", month))
        for rf in (None, ROW):
            _cap_same(cap_seeded, _with_cur(lambda m, cur: m.capacity_row_at(cur, "BSP", "Hot Metal", month), rf))


def test_save_capacity_entry(cap_seeded, monkeypatch):
    calls = []
    monkeypatch.setattr(activity_context, "record", lambda *a: calls.append(a))
    ids = _cap_same(cap_seeded, lambda m: m.save_capacity_entry("RSP", "Saleable Steel", "2025-04", 3.5,
                                                                 "new", "c@x"))
    assert ids == 4 and calls[0] == calls[1]
    for item in ("hot metal", "Hot Metal"):     # ai_ci clash with entry 1
        r = []
        for side, mod in ((1, cap1), (2, cap2)):
            with (cap_seeded.v1() if side == 1 else cap_seeded.v2()):
                with pytest.raises(rc.IntegrityError) as e:
                    mod.save_capacity_entry("BSP", item, "2024-04", 1.0, "", "c@x")
                r.append(e.value.args[0])
        assert r == [1062, 1062]
    a, b = cap_seeded.both(_cap_all, v1=cap1, v2=cap2)
    strip = lambda rows: [{k: v for k, v in r.items() if k not in ("created_at", "updated_at")} for r in rows]
    assert strip(a) == strip(b)


def test_update_capacity_entry(cap_seeded, monkeypatch):
    calls = []
    monkeypatch.setattr(activity_context, "record", lambda *a: calls.append(a))
    strip = lambda rows: [{k: v for k, v in r.items() if k != "updated_at"} for r in rows]
    for fields in ({"annual_capacity": 1.5, "reason": "x"},
                   {"item_name": "hot metal"},                            # new exact spelling, same row
                   {"plant_name": "DSP", "item_name": "Finished Steel"},  # clash with entry 3 (ai_ci)
                   {"effective_month": "2024-04"},                        # clash with entry 1
                   {"effective_month": "2025-11", "plant_name": "BSP"},
                   {"unknown": 1},
                   {}):
        calls.clear()
        out = []
        for side, mod in ((1, cap1), (2, cap2)):
            with (cap_seeded.v1() if side == 1 else cap_seeded.v2()):
                try:
                    out.append(mod.update_capacity_entry(2, "u@x", **fields))
                except rc.IntegrityError as e:
                    out.append(("IntegrityError", e.args[0]))
                out.append(mod.update_capacity_entry(99, "u@x", **fields))
        assert out[:2] == out[2:], fields
        assert len(calls) in (0, 2), fields
        if calls:      # old / new rows equal but for updated_at
            (k1, o1, n1), (k2, o2, n2) = calls
            assert k1 == k2 and strip([o1, n1]) == strip([o2, n2]), fields
        a, b = cap_seeded.both(_cap_all, v1=cap1, v2=cap2)
        assert strip(a) == strip(b), fields


def test_delete_capacity_entry(cap_seeded, monkeypatch):
    calls = []
    monkeypatch.setattr(activity_context, "record", lambda *a: calls.append(a))
    assert _cap_same(cap_seeded, lambda m: m.delete_capacity_entry(2)) is True
    assert _cap_same(cap_seeded, lambda m: m.delete_capacity_entry(2)) is False
    assert calls[0] == calls[1]
    _cap_same(cap_seeded, _cap_all)


def test_capacity_months_and_plants_outside_the_masters(cap_seeded):
    ids = _cap_same(cap_seeded, lambda m: m.save_capacity_entry("XYZ", "Hot Metal", "2099-04", 1.0, "", "c@x"))
    assert ids == 4
    _cap_same(cap_seeded, lambda m: m.update_capacity_entry(1, "u@x", effective_month="1950-04", plant_name="QQ"))
    strip = lambda rows: [{k: v for k, v in r.items() if k not in ("created_at", "updated_at")} for r in rows]
    a, b = cap_seeded.both(_cap_all, v1=cap1, v2=cap2)
    assert strip(a) == strip(b)
    _cap_same(cap_seeded, lambda m: m.get_effective_capacity("xyz", "hot metal", "2100-01"))


# ── trailing spaces past CHAR(7) (Task 7e1, _keys.fit_month) ────────────────

def _committed(fn):
    """fn(module, cur) on a db.connect() cursor, committed."""
    def run(mod):
        import dbengine
        conn = dbengine.connect()
        try:
            out = fn(mod, conn.cursor())
            conn.commit()
            return out
        finally:
            conn.close()
    return run


def _outcomes(dual, v1, v2, step):
    out = []
    for side, mod in ((1, v1), (2, v2)):
        with (dual.v1() if side == 1 else dual.v2()):
            try:
                out.append(("ok", as_plain(step(mod))))
            except Exception as e:      # noqa: BLE001
                out.append((type(e).__name__, e.args))
    return out


def test_month_with_trailing_spaces_is_cut_as_v1_stored_it(seeded, monkeypatch):
    """v1 stored '2025-04' for '2025-04 ' (its ON DUPLICATE KEY updated the
    stored row) while its own SELECT / DELETE with '2025-04 ' matched
    nothing; '2025-04 x' is still too long (1406)."""
    calls = []
    monkeypatch.setattr(activity_context, "record", lambda *a: calls.append(a))
    steps = [lambda m: m.upsert("actual", [("2025-04 ", "BSP", "Hot Metal", 11.0),
                                           ("2025-06   ", "RSP", "New One", 12.0)]),
             lambda m: m.save_production_actual("2025-05  ", "BSP", "Hot Metal", 13.0),
             lambda m: m.save_production_plan("2025-04 ", "BSP", "Hot Metal", None),    # DELETE matches nothing
             lambda m: m.delete("actual", "2025-04 ", "BSP", None),                     # matches nothing
             _committed(lambda m, cur: m.upsert_row(cur, "mou", "2025-04 ", "BSP", "cc billet", 1.0)),
             lambda m: m.upsert("actual", [("2025-04 x", "BSP", "Hot Metal", 1.0)])]
    for step in steps:
        calls.clear()
        out = _outcomes(seeded, p1, p2, step)
        assert out[0] == out[1]
        assert len(calls) in (0, 2) and (not calls or calls[0] == calls[1])
        _assert_same_data(seeded)


def test_capacity_month_with_trailing_spaces(cap_seeded, monkeypatch):
    calls = []
    monkeypatch.setattr(activity_context, "record", lambda *a: calls.append(a))
    strip = lambda rows: [{k: v for k, v in r.items() if k not in ("created_at", "updated_at")} for r in rows]
    # (the new id first: v1's refused INSERT burns an AUTO_INCREMENT value, v2 refuses before inserting)
    steps = [lambda m: m.save_capacity_entry("RSP", "Hot Metal", "2026-01  ", 1.0, "", "c@x"),
             lambda m: m.save_capacity_entry("BSP", "Hot Metal", "2024-04 ", 1.0, "", "c@x"),   # clash (1062)
             lambda m: m.update_capacity_entry(2, "u@x", effective_month="2024-04 "),           # clash
             lambda m: m.update_capacity_entry(3, "u@x", effective_month="2027-02 "),
             lambda m: m.save_capacity_entry("RSP", "Hot Metal", "2026-01 1", 1.0, "", "c@x")]   # 1406
    for step in steps:
        calls.clear()
        out = _outcomes(cap_seeded, cap1, cap2, step)
        assert out[0] == out[1]
        assert len(calls) in (0, 2)
        if calls:
            (k1, o1, n1), (k2, o2, n2) = calls
            assert k1 == k2 and strip([o1 or {}, n1]) == strip([o2 or {}, n2])
        a, b = cap_seeded.both(_cap_all, v1=cap1, v2=cap2)
        assert strip(a) == strip(b)
