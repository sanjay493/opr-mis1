"""Monthly rail loading (Rail Logistics page 40.05): the repo save / read in a
throwaway database, the highlights-note parser against a copy of the real
note, and the page table on small hand-made figures."""
from pathlib import Path

import pytest

import rail_loading_highlights as rlh


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


# ── highlights note parser ───────────────────────────────────────────────────

FIXTURE = Path(__file__).parent / "fixtures" / "rail_loading_highlights.txt"
APR = {"ore_ogom_jgom": 641, "ore_bhilai": 193, "ore_total": 834, "flux_limestone": 120, "flux_dolomite": 79,
       "flux_total": 199, "port_coal": 356, "port_limestone": 23, "port_total": 379, "coal_coking": 46.3,
       "coal_power": 79.7, "coal_total": 126, "misc_pellets": 95, "misc_other": 13, "misc_total": 108,
       "inward_total": 1623, "out_steel": 526, "out_slag": 79, "out_coke": 9, "out_sinter": 2,
       "outward_total": 616, "grand_total": 2239, "export_port": 0, "export_nepal": 4, "export_total": 4}
OCT = {"ore_ogom_jgom": 662, "ore_bhilai": 209, "ore_total": 871, "flux_limestone": 125, "flux_dolomite": 93,
       "flux_total": 218, "port_coal": 351, "port_limestone": 46, "port_total": 397, "coal_coking": 51.7,
       "coal_power": 55.3, "coal_total": 107, "misc_pellets": 100, "misc_other": 4, "misc_total": 104,
       "inward_total": 1651, "out_steel": 533, "out_slag": 95, "out_coke": 14, "out_sinter": 0,
       "outward_total": 642, "grand_total": 2293, "export_port": 0, "export_nepal": 10, "export_total": 10}


def _text():
    return FIXTURE.read_text(encoding="utf-8")


def test_april_and_october_goldens():
    months, _ = rlh.parse(_text())
    assert months["2026-04"] == APR and months["2026-10"] == OCT


def test_every_month_of_the_file_parses():
    months, problems = rlh.parse(_text())
    assert sorted(months) == [f"2026-{m:02d}" for m in range(4, 11)] and problems == []
    assert [months[m]["grand_total"] for m in sorted(months)] == [2239, 2302, 2332, 2328, 2298, 2115, 2293]
    assert months["2026-05"]["out_sinter"] == 0 and months["2026-07"]["export_nepal"] == 2   # "2rakes"


def test_damaged_block_is_skipped_whole():
    months, problems = rlh.parse(_text().replace("Total Flux loaded 195 rakes", "Total Flux loaded many rakes"))
    assert "2026-05" not in months and len(months) == 6
    assert problems == ["2026-05: not found: flux_total"]


def test_inward_cross_check_is_reported_but_loads():
    months, problems = rlh.parse(_text().replace("total inward was 1623 rakes", "total inward was 1600 rakes"))
    assert "2026-04" in months and len(problems) == 1 and "2026-04" in problems[0] and "1600" in problems[0]


def test_no_blocks():
    assert rlh.parse("nothing here") == ({}, [])
