"""data_version (write counter) and the caches keyed on it: main's page
cache and page_records.generate_group_records' memo.

Hazards covered: a write invalidates (cache_invalidated_by_write), a
rollback rolls the bump back (tx and the plan-preview dry run), a missing
table disables caching, an admin restore moves n to a never-used value and
clears the caches, a cached value can't be mutated through a returned copy,
and current() is read once per request.
"""
import json

import pytest

import data_version
from repo import conn as rc
from repo import production as rp
from repo import version as rv
from version_cache import VersionedCache

MONTH = "2026-08"


def _n():
    with rc.cursor() as cur:
        cur.execute("SELECT n FROM data_version WHERE id = 1")
        row = cur.fetchone()
    return None if row is None else row[0]


def _page4(main, month=MONTH):
    pages = main.get_data(month=month, page_number=4)
    assert len(pages) == 1
    return pages[0]


def _count_calls(monkeypatch, module, name):
    calls = []
    real = getattr(module, name)

    def spy(*a, **k):
        calls.append(a)
        return real(*a, **k)
    monkeypatch.setattr(module, name, spy)
    return calls


# ── the brief's invalidation test ──────────────────────────────────────────

def test_cache_invalidated_by_write(mysql_db, monkeypatch):
    import main
    calls = _count_calls(monkeypatch, main, "generate_page4_rows")
    rp.upsert("actual", [(MONTH, "BSP", "Hot Metal", 1111.0)])

    first = _page4(main)
    assert "1111" in json.dumps(first["rows"])
    again = _page4(main)                       # no write: served from the cache
    assert again == first and len(calls) == 1

    rp.upsert("actual", [(MONTH, "BSP", "Hot Metal", 2222.0)])
    rebuilt = _page4(main)
    assert len(calls) == 2
    text = json.dumps(rebuilt["rows"])
    assert "2222" in text and "1111" not in text


def test_pdf_enrichment_reuses_api_data_pages(mysql_db, monkeypatch):
    import main
    from models import PDFRequest
    calls = _count_calls(monkeypatch, main, "generate_page4_rows")
    rp.upsert("actual", [(MONTH, "BSP", "Hot Metal", 1111.0)])
    page = _page4(main)
    req = PDFRequest(month=MONTH, pages=[{"page": 4, "title": "t", "type": "page4_table"}])
    enriched, _ = main._enrich_pdf_pages(req)
    assert len(calls) == 1
    assert enriched[0]["rows"] == page["rows"]


# ── bump joins the writer's transaction ────────────────────────────────────

def test_repo_write_bumps(mysql_db):
    n0 = _n()
    rp.upsert("actual", [(MONTH, "BSP", "Hot Metal", 1.0)])
    assert _n() == n0 + 1
    rp.save_production_actual(MONTH, "BSP", "Hot Metal", 2.0)
    assert _n() == n0 + 2


def test_rollback_rolls_back_bump(mysql_db):
    n0 = _n()
    with pytest.raises(RuntimeError):
        with rc.tx() as cur:
            rp.upsert_row(cur, "actual", MONTH, "BSP", "Hot Metal", 1.0)
            raise RuntimeError("boom")
    assert _n() == n0
    assert rp.values([MONTH], None, None, "actual") == {}


def test_cursor_helper_bump_keeps_lastrowid(mysql_db):
    """bump runs before the write on a shared cursor, so the caller still
    reads the write's own lastrowid."""
    from repo import misc as rmisc
    with rc.tx() as cur:
        rmisc.insert_external_bf(cur, "BF-X", "Co", "Loc", "2026-10-19T00:00:00+00:00")  # api_bf_benchmark._now() form
        new_id = cur.lastrowid
    assert new_id and new_id > 0
    with rc.cursor() as cur:
        cur.execute("SELECT name FROM bf_benchmark_external_bf WHERE id = %s", (new_id,))
        assert cur.fetchone()[0] == "BF-X"


def test_dry_run_skips_bump(mysql_db):
    """The plan-preview dry run (rollback_tx + the _shared_raw contextvar):
    its writes don't bump (nothing to invalidate, no row lock held), and
    current() is None in there (caching off)."""
    n0 = _n()
    inside = []

    def extractor():
        rp.upsert("abp", [(MONTH, "BSP", "Hot Metal", 9.0)])
        inside.append((_n(), data_version.current()))   # same shared connection
    rows = rp.plan_preview_rows(extractor)
    assert [tuple(r) for r in rows] == [("BSP", "Hot Metal", MONTH, 9.0)]
    assert inside == [(n0, None)]
    assert _n() == n0
    assert rp.values([MONTH], None, None, "abp") == {}
    assert data_version.current() == n0


def test_nothing_cached_inside_dry_run(mysql_db):
    cache = VersionedCache(8)
    built = []
    with rc.rollback_tx():
        with data_version.pinned():
            for _ in range(2):
                cache.get_or_compute(("m", 1), "p", lambda: built.append(1) or "v")
    assert len(built) == 2 and len(cache) == 0
    cache.get_or_compute(("m", 1), "p", lambda: built.append(1) or "v")
    cache.get_or_compute(("m", 1), "p", lambda: built.append(1) or "v")
    assert len(built) == 3 and len(cache) == 1          # outside: cached again


# ── missing table: no caching, writes still work ───────────────────────────

@pytest.fixture
def no_data_version_table(mysql_db):
    from conftest import V1_MIGRATION_DIR
    with rc.tx() as cur:
        cur.execute("DROP TABLE data_version")
    try:
        yield
    finally:
        sql = (V1_MIGRATION_DIR / "migrate_add_data_version.sql").read_text(encoding="utf-8")
        with rc.tx() as cur:
            for stmt in sql.split(";"):
                body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
                if body:
                    cur.execute(body)


def test_missing_table_disables_cache(no_data_version_table, monkeypatch):
    import main
    assert data_version.current() is None
    with rc.tx() as cur:
        data_version.bump(cur)                 # tolerated: no-op
    rp.upsert("actual", [(MONTH, "BSP", "Hot Metal", 1111.0)])   # writes still work
    calls = _count_calls(monkeypatch, main, "generate_page4_rows")
    _page4(main)
    _page4(main)
    assert len(calls) == 2                     # always recomputed


# ── restore: fresh n, caches cleared ───────────────────────────────────────

def test_after_restore_moves_to_fresh_version_and_clears_caches(mysql_db):
    cache = VersionedCache(8)
    seen = []
    for _ in range(3):
        rp.upsert("actual", [(MONTH, "BSP", "Hot Metal", 1.0)])
        seen.append(data_version.current())
        cache.get_or_compute(("k",), "p", lambda: "v")
    assert len(cache) == 3
    # The dump brings back an old n, bypassing repo writes.
    with rc.tx() as cur:
        cur.execute("UPDATE data_version SET n = %s WHERE id = 1", (seen[0],))
    data_version.after_restore()
    n = data_version.current()
    assert n > max(seen)
    assert len(cache) == 0


def test_after_restore_recreates_missing_row(mysql_db):
    with rc.tx() as cur:
        cur.execute("DELETE FROM data_version")
    assert data_version.current() is None
    data_version.after_restore()
    assert data_version.current() is not None


def test_restore_route_calls_after_restore(monkeypatch, tmp_path):
    """The admin restore route runs the post-restore hook, also when the
    import fails part-way; the lock connection is untouched."""
    import subprocess
    import api_admin_backup as ab

    src = tmp_path / "x.sql"
    src.write_text("-- dump\n")
    ini = tmp_path / "c.ini"
    ini.write_text("")
    lock = object()
    events = []
    monkeypatch.setattr(ab, "_require_mysql", lambda: None)
    monkeypatch.setattr(ab, "_safe_path", lambda f: src)
    monkeypatch.setattr(ab, "_acquire_admin_lock", lambda: lock)
    monkeypatch.setattr(ab, "_release_admin_lock", lambda c: events.append(("release", c)))
    monkeypatch.setattr(ab, "_tables_at_risk", lambda s: [])
    monkeypatch.setattr(ab, "_live_is_v2", lambda: False)
    monkeypatch.setattr(ab, "_run_dump", lambda dest: None)
    monkeypatch.setattr(ab, "_mysql_bin_dir", lambda: tmp_path)
    monkeypatch.setattr(ab, "_client_ini", lambda: (ini.write_text(""), str(ini))[1])
    monkeypatch.setattr(ab, "_sanitize_for_restore", lambda s: tmp_path / "san.sql")
    (tmp_path / "san.sql").write_text("")
    monkeypatch.setattr(ab.auth, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(ab.data_version, "after_restore", lambda: events.append("after_restore"))

    rc_ = {"code": 0}
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, rc_["code"], b"", b"err"))
    ab.restore_backup("x.sql", admin={"email": "a"})
    assert events == ["after_restore", ("release", lock)]

    events.clear()
    (tmp_path / "san.sql").write_text("")
    rc_["code"] = 1
    with pytest.raises(Exception):
        ab.restore_backup("x.sql", admin={"email": "a"})
    assert events == ["after_restore", ("release", lock)]


def test_data_version_not_at_risk_on_restore(monkeypatch):
    """A dump taken before data_version existed has no rows for it; mysqldump
    import leaves the table alone, so the data-loss guard ignores it."""
    import api_admin_backup as ab
    monkeypatch.setattr(ab, "_source_table_counts", lambda p: {"production_table": 5})
    monkeypatch.setattr(ab, "_live_table_counts",
                        lambda: {"production_table": 5, "data_version": 1, "stock_table": 3})
    assert ab._tables_at_risk(None) == [("stock_table", 3)]


# ── cache mechanics (no DB) ────────────────────────────────────────────────

@pytest.fixture
def fixed_version(monkeypatch):
    box = {"n": 7}
    monkeypatch.setattr(data_version, "current", lambda: box["n"])
    return box


def test_mutating_returned_value_does_not_change_next_hit(fixed_version):
    cache = VersionedCache(8)
    built = []

    def build():
        built.append(1)
        return {"rows": [{"v": 1}], "nested": {"a": [1, 2]}}

    first = cache.get_or_compute(("m", 4), "p", build)      # miss: the original
    first["rows"][0]["v"] = 999
    first["nested"]["a"].append(3)
    second = cache.get_or_compute(("m", 4), "p", build)     # hit
    assert second == {"rows": [{"v": 1}], "nested": {"a": [1, 2]}}
    second["rows"].clear()
    third = cache.get_or_compute(("m", 4), "p", build)
    assert third == {"rows": [{"v": 1}], "nested": {"a": [1, 2]}}
    assert third is not second
    assert len(built) == 1


def test_version_change_misses_and_lru_evicts(fixed_version):
    cache = VersionedCache(2)
    assert cache.get_or_compute(("m", 1), "p", lambda: "a") == "a"
    fixed_version["n"] = 8
    assert cache.get_or_compute(("m", 1), "p", lambda: "b") == "b"
    assert cache.get_or_compute(("m", 2), "p", lambda: "c") == "c"
    assert ("m", 1, 7) not in cache.keys()          # evicted, oldest first
    assert cache.keys() == [("m", 1, 8), ("m", 2, 8)]


def test_exception_is_not_cached(fixed_version):
    cache = VersionedCache(2)
    with pytest.raises(ValueError):
        cache.get_or_compute(("m", 1), "p", lambda: (_ for _ in ()).throw(ValueError()))
    assert cache.get_or_compute(("m", 1), "p", lambda: "ok") == "ok"


def test_pinned_reads_version_once(monkeypatch):
    reads = []
    monkeypatch.setattr(rv, "read", lambda: reads.append(1) or 5)
    with data_version.pinned() as v:
        assert v == 5
        for _ in range(4):
            assert data_version.current() == 5
        with data_version.pinned():
            assert data_version.current() == 5
    assert len(reads) == 1


def test_get_data_reads_version_once_per_request(mysql_db, monkeypatch):
    import main
    reads = _count_calls(monkeypatch, rv, "read")
    rp.upsert("actual", [(MONTH, "BSP", "Hot Metal", 1.0)])
    for pg in (4, 5, 6):
        monkeypatch.setattr(main, {4: "generate_page4_rows", 5: "generate_page5_rows",
                                   6: "generate_page6_rows"}[pg], lambda m: [])
    main.get_data(month=MONTH, page_number=None)
    assert len(reads) == 1
    from models import PDFRequest
    reads.clear()
    req = PDFRequest(month=MONTH, pages=[{"page": p, "title": "t", "type": "x"} for p in (4, 5, 6)])
    main._enrich_pdf_pages(req)
    assert len(reads) == 1


# ── generate_group_records memo ────────────────────────────────────────────

def test_group_records_memoised_on_version(fixed_version, monkeypatch):
    import page_records
    page_records._group_records_cache.clear()
    built = []

    def fake(items, upto_month):
        built.append((tuple(items), upto_month))
        return {"rows": [list(items)], "upto": upto_month}
    monkeypatch.setattr(page_records, "_build_group_records", fake)

    a = page_records.generate_group_records(["Hot Metal"], upto_month="2026-08")
    a["rows"].append("mutated")
    b = page_records.generate_group_records(["Hot Metal"], upto_month="2026-08")
    assert b == {"rows": [["Hot Metal"]], "upto": "2026-08"}
    assert len(built) == 1
    page_records.generate_group_records(["Hot Metal"], upto_month="2026-07")
    page_records.generate_group_records(["Pig Iron"], upto_month="2026-08")
    assert len(built) == 3
    fixed_version["n"] = 8
    page_records.generate_group_records(["Hot Metal"], upto_month="2026-08")
    assert len(built) == 4
