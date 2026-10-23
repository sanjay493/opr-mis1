"""Pure-helper tests for tools/parity_snapshot.py (no database, no app import)."""

import pytest

from tools import parity_snapshot as ps


def test_parse_months_ranges_and_singles():
    ms = ps.parse_months("2025-11..2026-02,2016-03,2026-01")
    assert ms == ["2016-03", "2025-11", "2025-12", "2026-01", "2026-02"]


def test_default_month_spec_size():
    assert len(ps.parse_months(ps.DEFAULT_MONTHS)) == 30 + 2


def test_fy_helpers():
    assert ps.fy_start_year("2026-03") == 2025 and ps.fy_start_year("2026-04") == 2026
    assert ps.fy_label(2026) == "2026-27" and ps.fy_label(1999) == "1999-00"
    assert [ps.quarter_of(m) for m in ("2026-04", "2026-07", "2026-10", "2027-01", "2027-03")] == [1, 2, 3, 4, 4]


@pytest.mark.parametrize("name", ["mis_reports", "MIS_REPORTS", "mis_reports_v2", "MIS_Reports_V2"])
def test_snapshot_refuses_live_database(tmp_path, name):
    with pytest.raises(SystemExit, match="live database"):
        ps.snapshot(["2026-08"], tmp_path, name)
    assert not any(tmp_path.iterdir())


def test_expand_calls_plant_month_and_fy():
    scope, calls = ps.expand_calls("/api/stock-data", [("plant", "query", True), ("stock_month", "query", True)],
                                   "2026-08", [2025, 2026], {})
    assert scope == "month" and len(calls) == len(ps.PLANTS)
    assert {c["stock_month"] for c in calls} == {"2026-08"}
    scope, calls = ps.expand_calls("/api/sail-techno-plan", [("fy", "query", True)], "2026-08", [2025, 2026], {})
    assert scope == "fy" and [c["fy"] for c in calls] == ["2025-26", "2026-27"]
    scope, calls = ps.expand_calls("/api/needs-item", [("item", "query", True)], "2026-08", [2026], {})
    assert calls is None


def test_slug_is_filesystem_safe_and_stable():
    s = ps.slug("/api/major-unit-daily/{plant_code}", {"plant_code": "BSP"})
    assert s == "api_major-unit-daily__plant_code--plant_code=BSP"
    assert ps.slug("/api/data", {"month": "2026-08"}, drop={"month"}) == "api_data"


def test_best_period_window_is_valid_for_every_month():
    # page_records.generate_best_period reads calendar months inside the Apr->Mar
    # FY, so April..report-month must never run backwards (incl. Jan-Mar).
    params = [("start_mon", "query", True), ("end_mon", "query", True)]

    def pos(x):
        return x - 4 if x >= 4 else x + 8

    for mm in range(1, 13):
        scope, calls = ps.expand_calls("/api/best-period-records", params, f"2026-{mm:02d}", [2026], {})
        assert scope == "month" and len(calls) == 1
        s, e = calls[0]["start_mon"], calls[0]["end_mon"]
        assert s == 4 and e == mm and pos(e) >= pos(s)


def test_post_exports_build_payloads():
    ctx = {"sail_bf_keys": ["BSP:BF-8"], "furnace_keys": ["BSP:BF-8"]}
    payloads = {p: make("2026-08", ctx) for p, make in ps.POST_EXPORTS}
    assert payloads["/api/secretary-review/pptx"] == {"month": "2026-08"}
    assert payloads["/api/bf-benchmark/excel"]["months"] == ["2026-08"]


def test_summarise_counts_and_always_failing(tmp_path):
    d = tmp_path / "2026-08"
    d.mkdir()
    (d / "api_a.json").write_text('{"x":1}')
    (d / "api_b.json").write_text('{"_detail":"boom","_status":500}')
    (d / "api_c--plant=BSP.json").write_text('{"x":1}')
    (d / "api_c--plant=ASP.json").write_text('{"_detail":{"detail":"none"},"_status":404}')
    (tmp_path / "report.pdf.txt").write_text("page")
    s = ps.summarise(tmp_path)
    assert s["status_counts"] == {"200": 2, "404": 1, "500": 1}
    assert s["endpoints_failing_every_time"] == {"api_b": [500]}
    assert s["variants_failing_every_time"] == {"api_c--plant=ASP": [404]}
    assert (tmp_path / "_summary.json").exists()


def _date_and_datetime(obj, attr):
    """The (date class, datetime class) a pinned module attribute exposes."""
    if attr == "date":
        return obj, None
    if attr == "datetime":
        return None, obj
    return obj.date, obj.datetime          # a datetime-module stand-in


def test_pin_today_patches_every_listed_module_and_restores():
    """--today pins date.today() / datetime.now() / datetime.today() in every
    listed module, and puts the real objects back afterwards."""
    import datetime as real_dt
    import importlib

    pinned = real_dt.date(2026, 10, 19)
    listed = dict(ps.TODAY_PINNED_MODULES)
    assert {"page_capital_repair", "page_techno_records", "main",
            "api_production_loss", "production_loss_analysis"} <= set(listed)
    mods = {name: importlib.import_module(name) for name in listed}
    before = {(n, a): getattr(mods[n], a) for n, attrs in listed.items() for a in attrs}

    with ps.pin_today(pinned):
        for (n, a), orig in before.items():
            obj = getattr(mods[n], a)
            assert obj is not orig, (n, a)
            dcls, dtcls = _date_and_datetime(obj, a)
            if dcls is not None:
                t = dcls.today()
                assert t == pinned and type(t) is real_dt.date
                d = dcls(2026, 1, 2)       # constructors still build real dates
                assert type(d) is real_dt.date and isinstance(d, dcls)
                assert dcls.fromisoformat("2026-01-02") == d
            if dtcls is not None:
                for n_ in (dtcls.now(), dtcls.today(), dtcls.now(real_dt.timezone.utc)):
                    assert n_.date() == pinned and type(n_) is real_dt.datetime
                assert type(dtcls(2026, 1, 2, 3)) is real_dt.datetime
        assert mods["main"]._dt.timedelta is real_dt.timedelta

    for (n, a), orig in before.items():
        assert getattr(mods[n], a) is orig, (n, a)


def test_pin_today_reaches_main_default_month_helpers(monkeypatch):
    import datetime as real_dt
    import main

    monkeypatch.setattr(main.rt, "get_techno_months", lambda: ["2026-11", "2026-09"])
    with ps.pin_today(real_dt.date(2026, 10, 19)):
        assert main._radar_default_month() == "2026-09"
    with ps.pin_today(real_dt.date(2026, 12, 5)):
        assert main._radar_default_month() == "2026-11"


def test_today_cli_option_is_passed_to_snapshot(monkeypatch, tmp_path):
    import datetime as real_dt

    seen = {}
    monkeypatch.setattr(ps, "snapshot", lambda *a, **k: seen.update(k))
    ps.main_cli(["--db", "x", "--out", str(tmp_path), "--months", "2026-08",
                 "--pdf-months", "", "--today", "2026-10-19"])
    assert seen["today"] == real_dt.date(2026, 10, 19)
    ps.main_cli(["--db", "x", "--out", str(tmp_path), "--months", "2026-08", "--pdf-months", ""])
    assert seen["today"] is None
