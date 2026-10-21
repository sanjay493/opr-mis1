"""report_context: request-scoped bulk loads (task 4b).

    test_page4_query_count      page 4 issues <= 10 queries
    test_bulk_equals_single     every value served from the bulk load equals
                                the per-month SQL function's, bit for bit
                                (absent vs NULL, SUM order, case-insensitive
                                names, months outside the window)
    test_write_invalidates_*    a repo write inside an active context drops
                                its bulk data; the next read sees the write
    test_lazy_*                 nothing is loaded until a covered read; a
                                page-cache hit loads nothing
"""
import random

import pymysql.cursors
import pytest

import report_context
from dbengine import Row
from constants import ALL_PLANTS, FIVE_PLANTS
from repo import capacity as rcap
from repo import conn as rc
from repo import production as rp

MONTH = "2026-08"
ITEMS = ["Oven Pushing (nos/day)", "Total Sinter", "Hot Metal", "Total Crude Steel",
         "Saleable Steel", "Pig Iron", "Finished Steel"]
WINDOW = [f"{y}-{m:02d}" for y in (2025, 2026, 2027) for m in range(1, 13)
          if "2025-04" <= f"{y}-{m:02d}" <= "2027-03"]
OUTSIDE = ["2024-08", "2025-03", "2027-04"]


@pytest.fixture
def query_count(monkeypatch):
    """Counts every statement sent to MySQL (all paths end in pymysql)."""
    count = [0]
    real = pymysql.cursors.Cursor.execute

    def counting(self, query, args=None):
        count[0] += 1
        return real(self, query, args)
    monkeypatch.setattr(pymysql.cursors.Cursor, "execute", counting)
    return count


def _seed(seed=7):
    """Production rows for every measure over the window and a few months
    outside it: floats with several decimals (so summation order shows in
    the last bit), NULL values, absent rows, SAIL rows, the SSP/VISL
    Saleable Steel fallback, and a lower-case spelling (MySQL matches
    names case-insensitively)."""
    rnd = random.Random(seed)
    rows = {"actual": [], "abp": [], "mou": []}
    for measure in rows:
        for month in WINDOW + OUTSIDE:
            for plant in ALL_PLANTS + ["SAIL"]:
                for item in ITEMS + ["Conversion"]:
                    r = rnd.random()
                    if r < 0.12:
                        continue                                  # no row
                    value = None if r < 0.18 else round(rnd.uniform(0.1, 900.0), rnd.choice((1, 2, 3)))
                    if plant in ("SSP", "VISL") and item == "Finished Steel" and r < 0.5:
                        continue                                  # SS fallback
                    name = item.lower() if (item == "Pig Iron" and plant == "DSP") else item
                    rows[measure].append((month, plant, name, value))
    for measure, rs in rows.items():
        rp.upsert(measure, rs)
    with rc.tx() as cur:
        for plant in ALL_PLANTS:
            for item, months in (("Hot Metal", ("2020-04", "2026-06")), ("Saleable Steel", ("2025-01",)),
                                 ("Finished Steel", ("2019-04", "2026-09"))):
                for i, em in enumerate(months):
                    cur.execute("INSERT INTO item_capacity_table (plant_name, item_name, effective_month, "
                                "annual_capacity) VALUES (%s, %s, %s, %s)",
                                (plant.lower() if plant == "ISP" else plant, item, em,
                                 round(rnd.uniform(500, 9000), 2) + i))


def _plant_lists():
    return [FIVE_PLANTS, FIVE_PLANTS + ["VISL"], ALL_PLANTS, list(reversed(ALL_PLANTS)),
            ["SSP", "ASP"], ["SAIL"], ["bsp", "DSP"]]


def _snapshot():
    """Every value the served functions can return, computed by whatever
    path is active (bulk inside a context, SQL outside)."""
    out = {}
    months = WINDOW + OUTSIDE
    ytds = [WINDOW[i:i + n] for i in (0, 3, 12) for n in (1, 5, 12)] + [["2025-04", "2024-08"], OUTSIDE]
    items = ITEMS + ["Conversion", "pig iron", "Absent Item"]
    with rc.cursor() as cur:
        for measure in ("actual", "abp", "mou"):
            out[("values", measure)] = rp.values(months, None, None, measure)
            out[("values-f", measure)] = rp.values(WINDOW[:7], ["BSP", "ssp"], ["Hot Metal", "pig iron"], measure)
            for month in months:
                for item in items:
                    for plant in ALL_PLANTS + ["SAIL", "dsp"]:
                        out[("cell", measure, month, plant, item)] = rp.cell(cur, measure, month, plant, item)
                    for i, plants in enumerate(_plant_lists()):
                        out[("sum", measure, month, i, item)] = rp.sum_plants_cell(cur, measure, month, plants, item)
        for month in months:
            for item in items:
                out[("sail-act", month, item)] = rp.get_sail_production_actual(month, item)
                out[("sail-plan", month, item)] = rp.get_sail_production_plan(month, item)
                for plant in ALL_PLANTS:
                    out[("one", month, plant, item)] = rp.get_production_actual_value(plant, item, month)
            for plant in ALL_PLANTS + ["isp"]:
                for item in ("Hot Metal", "Saleable Steel", "Finished Steel", "Pig Iron"):
                    out[("cap", month, plant, item)] = rcap.get_effective_capacity(plant, item, month)
        for i, ms in enumerate(ytds):
            for item in items:
                out[("ytd-act", i, item)] = rp.get_sail_production_ytd_actual(ms, item)
                out[("ytd-plan", i, item)] = rp.get_sail_production_ytd_plan(ms, item)
    return out


def _same(a, b):
    """Equal, bit for bit and type for type (1.0 != 1, NaN-free data). A
    fetchone() row compares as the tuple of its values (a repo.conn cursor
    returns Row, a db.connect() cursor a tuple; callers only index it)."""
    if isinstance(a, Row):
        a = tuple(a)
    if isinstance(b, Row):
        b = tuple(b)
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, (tuple, list)):
        return type(a) is type(b) and len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def test_bulk_equals_single(mysql_db, query_count):
    _seed()
    single = _snapshot()
    sql_queries = query_count[0]
    query_count[0] = 0
    with report_context.activate(MONTH) as ctx:
        bulk = _snapshot()
    assert ctx.loads == 2                          # production + capacity, once each
    assert query_count[0] < sql_queries / 5        # only months outside the window use SQL
    diffs = [k for k in single if not _same(single[k], bulk[k])]
    assert not diffs, diffs[:10]
    # The seed really exercises the cases the bulk path must reproduce.
    assert any(v is not None and tuple(v) == (None,) for k, v in single.items() if k[0] == "cell")  # NULL row
    assert any(v is None for k, v in single.items() if k[0] == "cell")         # no row
    assert single[("cell", "actual", "2025-05", "DSP", "Pig Iron")] is not None or \
        single[("cell", "actual", "2025-06", "DSP", "Pig Iron")] is not None   # lower-case name found


def test_page4_query_count(mysql_db, query_count):
    from page4 import generate_page4_rows
    _seed()
    query_count[0] = 0
    rows = generate_page4_rows(MONTH)
    assert rows and any(v not in ("", None) for r in rows for v in r["values"])
    assert query_count[0] <= 10, query_count[0]


def test_page4_same_with_and_without_shared_context(mysql_db):
    """page 4 inside the request's context (shared load) equals page 4 on
    its own (its own load), and the raw / MoU variants build too."""
    from page4 import generate_page4_rows
    _seed()
    alone = generate_page4_rows(MONTH)
    with report_context.activate(MONTH) as ctx:
        shared = generate_page4_rows(MONTH)
        generate_page4_rows(MONTH, raw=True)
        generate_page4_rows(MONTH, basis="mou")
    assert ctx.loads == 2
    assert shared == alone


def test_write_invalidates_active_context(mysql_db):
    rp.upsert("actual", [(MONTH, "BSP", "Hot Metal", 1.5)])
    with report_context.activate(MONTH) as ctx:
        with rc.cursor() as cur:
            assert rp.cell(cur, "actual", MONTH, "BSP", "Hot Metal") == (1.5,)
            rp.upsert("actual", [(MONTH, "BSP", "Hot Metal", 2.5)])
            assert rp.cell(cur, "actual", MONTH, "BSP", "Hot Metal") == (2.5,)
            rp.save_production_actual(MONTH, "BSP", "Hot Metal", None)     # delete
            assert rp.cell(cur, "actual", MONTH, "BSP", "Hot Metal") is None
        assert rp.get_sail_production_actual(MONTH, "Hot Metal") is None
    assert ctx.loads == 3                         # reloaded after each write


def test_write_invalidates_memo(mysql_db):
    with report_context.activate(MONTH) as ctx:
        assert ctx.memo(("k",), lambda: 1) == 1
        assert ctx.memo(("k",), lambda: 2) == 1
        rp.upsert("abp", [(MONTH, "BSP", "Hot Metal", 1.0)])
        assert ctx.memo(("k",), lambda: 3) == 3


def test_lazy_load_and_window(mysql_db, query_count):
    query_count[0] = 0
    with report_context.activate(MONTH) as ctx:
        assert ctx.loads == 0 and query_count[0] == 0          # nothing until a covered read
        assert ctx.first == "2025-04" and ctx.last == "2027-03"
        with rc.cursor() as cur:
            rp.cell(cur, "actual", "2025-03", "BSP", "Hot Metal")   # outside: plain SQL
            assert ctx.loads == 0
            rp.cell(cur, "actual", "2027-03", "BSP", "Hot Metal")
            assert ctx.loads == 1
        with report_context.activate(MONTH) as inner:        # same month: reused
            assert inner is ctx
        with report_context.activate("2016-03") as other:    # another month: its own
            assert other is not ctx and other.first == "2014-04"
    assert report_context.current() is None


def test_page_cache_hit_does_no_bulk_load(mysql_db, monkeypatch):
    import main
    _seed()
    loads = []
    real = rp._bulk_load
    monkeypatch.setattr(rp, "_bulk_load", lambda a, b: loads.append(a) or real(a, b))
    first = main.get_data(month=MONTH, page_number=4)
    assert len(loads) == 1
    again = main.get_data(month=MONTH, page_number=4)
    assert again == first and len(loads) == 1


def test_cached_full_request_does_no_bulk_load(mysql_db, monkeypatch):
    """A second full /api/data for the month (every page from the page
    cache, the cover's KPI rows from compute_item_row's memo) loads
    nothing; after a write, the rows show the new value."""
    import main
    from report_utils import compute_item_row
    _seed()
    loads = []
    real = rp._bulk_load
    monkeypatch.setattr(rp, "_bulk_load", lambda a, b: loads.append(a) or real(a, b))
    main.get_data(month=MONTH)
    assert loads
    loads.clear()
    main.get_data(month=MONTH)
    assert loads == []
    before = compute_item_row(MONTH, "Hot Metal")
    rp.upsert("abp", [(MONTH, "BSP", "Hot Metal", 99999.0)])
    assert compute_item_row(MONTH, "Hot Metal")[0] != before[0]


def test_no_context_inside_dry_run(mysql_db):
    with report_context.activate(MONTH):
        assert report_context.current() is not None
        with rc.rollback_tx():
            assert report_context.current() is None


def test_fold_matches_mysql_collation():
    assert report_context.fold("Pig Iron") == report_context.fold("pig iron")
    assert report_context.fold("Pig Iron ") != report_context.fold("Pig Iron")   # NO PAD
    assert report_context.fold("Café") == report_context.fold("cafe")


def test_records_rows_reproduce_group_by(mysql_db, monkeypatch):
    """page_records aggregates rp.records_rows in Python; every row the old
    GROUP BY queries return comes back identical, in the same order, and
    the built records are identical (order-sensitive)."""
    import json

    import page_records as pr
    _seed()
    scopes = [rp.records_scope(pr.SAIL5, pr.HIGHLIGHT_ITEMS, MONTH), rp.records_scope(pr.ALL8, pr.ITEMS),
              rp.records_scope(["DSP"]), rp.records_scope(pr.ALL8, pr.MAJOR_ITEMS, "2025-12")]
    with rc.cursor() as cur:
        for sc in scopes:
            for bucket in ("quarter", "half", "fy", "cy"):
                old = [tuple(r) for r in rp.records_bucket_cells(cur, sc, bucket)]
                assert old and list(pr._bucket_cells(cur, sc, bucket)) == old
            for s, e in ((0, 2), (6, 10), (9, 11)):
                old = [tuple(r) for r in rp.records_fy_window_cells(cur, sc, s, e)]
                assert old and list(pr._fy_window_cells(cur, sc, s, e)) == old

    def built():
        return json.dumps([pr._build_group_records(pr.HIGHLIGHT_ITEMS, MONTH), pr.generate_records(),
                           pr.generate_best_period(10, 2, "plants", "all")], default=str)
    new = built()
    with report_context.activate(MONTH):
        assert built() == new
    monkeypatch.setattr(pr, "_bucket_cells", rp.records_bucket_cells)        # the old GROUP BY path
    monkeypatch.setattr(pr, "_fy_window_cells", rp.records_fy_window_cells)
    assert built() == new


def _seed_techno(seed=11):
    """techno_data rows over the window and outside it: several units per
    plant / month (inserted out of unit order), ints / floats / nulls,
    a row holding only "month", a lower-case plant spelling."""
    import json
    rnd = random.Random(seed)
    rows = []
    for month in WINDOW[:6] + OUTSIDE:
        for plant in ["BSP", "DSP", "isp", "SAIL"]:
            for unit in ["SMS-2", "BF_Shop", "General", "BF#1", "bf-5", "Shop"]:
                if rnd.random() < 0.2:
                    continue
                body = {"month": {"coke_rate": rnd.choice([None, 412, round(rnd.uniform(300, 500), 2)]),
                                  "cdi": round(rnd.uniform(50, 200), 3)}}
                if rnd.random() < 0.7:
                    body["till_month"] = {"coke_rate": rnd.randint(300, 500)}
                rows.append((plant, month, unit, json.dumps(body)))
    with rc.tx() as cur:
        cur.executemany("INSERT INTO techno_data (plant, report_month, unit, techno_json) "
                        "VALUES (%s, %s, %s, %s)", rows)


def _techno_snapshot():
    from repo import techno as rt
    out = {}
    months = WINDOW[:6] + OUTSIDE
    out["blobs"] = rt.blobs(months)
    out["blobs-f"] = rt.blobs(months[:3], ["bsp", "ISP"], ["bf_shop", "General"])
    with rc.cursor() as cur:
        for month in months:
            out[("sail", month)] = rt.get_sail_techno_actuals(month)
            for plant in ["BSP", "DSP", "ISP", "isp", "SAIL", "RSP"]:
                d = rt.get_techno_data(plant, month)
                out[("all", month, plant)] = (list(d), d)             # unit order too
                for unit in ["BF_Shop", "bf_shop", "BF-5", "Missing", None, ""]:
                    out[("one", month, plant, unit)] = rt.get_techno_data(plant, month, unit)
                    if unit:
                        out[("json", month, plant, unit)] = rt.json_cell(cur, plant, month, unit)
        for plant in ALL_PLANTS:
            for ms in (WINDOW[:5], WINDOW[2:3], ["2024-08", "2025-04"]):
                out[("summ", plant, tuple(ms))] = rp.sum_months_cell(cur, "actual", plant, "Hot Metal", ms)
    return out


def test_techno_bulk_equals_single(mysql_db, query_count):
    """repo.techno reads (blobs, get_techno_data in unit order, SAIL actuals,
    json_cell) and sum_months_cell from the bulk load equal their SQL."""
    from repo import techno as rt
    _seed()
    _seed_techno()
    single = _techno_snapshot()
    sql_queries = query_count[0]
    query_count[0] = 0
    with report_context.activate(MONTH) as ctx:
        bulk = _techno_snapshot()
    assert ctx.loads == 2                          # techno + production
    assert query_count[0] < sql_queries / 2
    diffs = [k for k in single if not _same(single[k], bulk[k])]
    assert not diffs, diffs[:10]
    assert any(len(v[0]) > 2 for k, v in single.items() if k[0] == "all")
    # Each read gets its own objects: mutating one never reaches the next.
    with report_context.activate(MONTH):
        d = rt.get_techno_data("BSP", WINDOW[0])
        unit = next(iter(d))
        d[unit]["month"]["coke_rate"] = "mutated"
        assert rt.get_techno_data("BSP", WINDOW[0])[unit]["month"]["coke_rate"] != "mutated"
