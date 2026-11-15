"""Monthly rail loading (Rail Logistics page 40.05): the repo save / read in a
throwaway database, the highlights-note parser against a copy of the real
note, and the page table on small hand-made figures."""
import pytest


# ── repo ─────────────────────────────────────────────────────────────────────

def test_save_and_read_round_trip(mysql_db):
    from repo import conn as rc
    from repo import rake as rrake

    def n():
        with rc.cursor() as cur:
            cur.execute("SELECT n FROM data_version WHERE id = 1")
            return cur.fetchone()[0]

    assert rrake.rail_loading_rows("2026-04", "2027-03") == []
    n0 = n()
    assert rrake.save_rail_loading("2026-04", {"grand_total": 2239, "coal_coking": 46.3, "out_sinter": None},
                                   "x@sail.in") == 3
    assert n() > n0
    rrake.save_rail_loading("2026-05", {"grand_total": 2302}, None)
    rows = rrake.rail_loading_rows("2026-04", "2026-04")
    assert [(r["report_month"], r["item_code"], r["rakes"]) for r in rows] == [
        ("2026-04", "coal_coking", 46.3), ("2026-04", "grand_total", 2239.0), ("2026-04", "out_sinter", None)]
    # a re-save replaces the month, other months untouched
    rrake.save_rail_loading("2026-04", {"grand_total": 2240}, None)
    assert [(r["report_month"], r["item_code"], r["rakes"])
            for r in rrake.rail_loading_rows("2026-04", "2026-05")] == [
        ("2026-04", "grand_total", 2240.0), ("2026-05", "grand_total", 2302.0)]
    with pytest.raises(Exception):
        rrake.save_rail_loading("2026-04", {"x" * 33: 1}, None)
    assert len(rrake.rail_loading_rows("2026-04", "2026-04")) == 1      # nothing half-saved
