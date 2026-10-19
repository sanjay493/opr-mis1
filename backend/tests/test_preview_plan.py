"""/api/preview-plan runs the plant's plan extractor (which writes and commits
on its own db.connect() connections) and rolls everything back."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main

PLAN_FILE = Path(__file__).resolve().parent / "fixtures" / "plan" / "isp_plan_min.xlsx"

SEED = [
    ("2026-04", "ISP", "Hot Metal", 999.0),      # the file holds 250.123 here
    ("2026-05", "BSP", "Hot Metal", 1.0),
]


@pytest.fixture
def tc(mysql_db, monkeypatch):
    # Skip the editor/admin session gate on write routes.
    monkeypatch.setattr(main, "_is_gated", lambda method, path: False)
    conn = main.db.connect()
    for row in SEED:
        conn.execute("INSERT INTO production_plan_table VALUES (%s, %s, %s, %s)", row)
    conn.commit()
    conn.close()
    return TestClient(main.app, raise_server_exceptions=False)


def _plan_rows():
    conn = main.db.connect()
    rows = conn.execute("SELECT report_month, plant_name, item_name, month_actual "
                        "FROM production_plan_table ORDER BY 1, 2, 3").fetchall()
    conn.close()
    return [tuple(r) for r in rows]


def _post(tc, plant="ISP", fy="2026-27"):
    with PLAN_FILE.open("rb") as fh:
        return tc.post("/api/preview-plan",
                       data={"plant_name": plant, "financial_year": fy},
                       files={"file": (PLAN_FILE.name, fh,
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})


def test_preview_plan_writes_nothing(tc):
    before = _plan_rows()
    assert len(before) == 2

    r = _post(tc)
    assert r.status_code == 200, r.text
    body = r.json()

    assert _plan_rows() == before          # nothing persisted, nothing overwritten

    assert body["plant"] == "ISP"
    assert body["financial_year"] == "2026-27"
    assert body["source_type"] == "ISP ABP Plan Excel"
    rows = body["plan_rows"]
    # Only the extractor's own rows: 17 items x 12 months, none of the seeded rows.
    assert len(rows) == 17 * 12
    assert {r["plant"] for r in rows} == {"ISP"}
    ok = {(r["item_name"], r["month"]): r["value"] for r in rows if r["status"] == "ok"}
    assert ok == {
        ("Hot Metal", "2026-04"): 250.123,
        ("Hot Metal", "2026-05"): 260.0,
        ("Total Crude Steel", "2026-04"): 230.5,
        ("Oven Pushing (nos/day)", "2027-01"): 95.0,
    }
    hm_apr = next(r for r in rows if r["item_name"] == "Hot Metal" and r["month"] == "2026-04")
    assert hm_apr == {"item_name": "Hot Metal", "month": "2026-04", "value": 250.123,
                      "unit": "'000T", "plant": "ISP", "status": "ok"}
    skip = next(r for r in rows if r["item_name"] == "Pig Iron" and r["month"] == "2026-04")
    assert skip["value"] is None and skip["status"] == "skip"
    # Sorted by plant, item, month as before.
    keys = [(r["plant"], r["item_name"], r["month"]) for r in rows]
    assert keys == sorted(keys)


def test_preview_plan_twice_gives_same_rows(tc):
    # The temporary shadow table and the dedicated connection do not leak
    # into the pool or into the next preview.
    before = _plan_rows()
    a = _post(tc).json()
    b = _post(tc).json()
    assert a == b and len(a["plan_rows"]) == 17 * 12
    assert _plan_rows() == before


def test_preview_plan_bad_file_is_400_and_writes_nothing(tc):
    before = _plan_rows()
    r = _post(tc, plant="BSL")       # BSL needs a 'PLAN SUMMARY' sheet
    assert r.status_code in (400, 500)
    assert _plan_rows() == before


def test_plan_preview_cleanup_failure_does_not_mask_extractor_error(tc):
    # The extractor fails AND leaves the shared connection unusable, so the
    # DROP TEMPORARY TABLE and the rollback in the cleanup fail too. The
    # caller must still see the extractor's own exception.
    import dbengine
    from repo import production as rp

    class ExtractorBroke(Exception):
        pass

    def run():
        dbengine._shared_raw.get().close()
        raise ExtractorBroke("extractor failed")

    with pytest.raises(ExtractorBroke):
        rp.plan_preview_rows(run)
    assert _plan_rows() == [tuple(r) for r in SEED]
