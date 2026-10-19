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


def test_snapshot_refuses_live_database(tmp_path):
    with pytest.raises(SystemExit, match="live database"):
        ps.snapshot(["2026-08"], tmp_path, "mis_reports")
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
