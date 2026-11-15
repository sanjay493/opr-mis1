"""Monthly rail loading (Rail Logistics page 40.05): the repo save / read in a
throwaway database, the highlights-note parser against a copy of the real
note, and the page table on small hand-made figures."""
from pathlib import Path

import pytest

import rail_loading as rl
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


# ── item registry and page table ─────────────────────────────────────────────

def _rows(d):
    return [{"report_month": m, "item_code": c, "rakes": v} for m, cv in d.items() for c, v in cv.items()]


def test_registry_matches_the_parser():
    assert len(rl.CODES) == 25 and len(set(rl.CODES)) == 25
    assert set(rl.CODES) == set(APR)
    assert [k for k, _c, _l in rl.ITEMS].count("group") == 3
    assert rl.CODES[0] == "ore_ogom_jgom" and rl.CODES[-1] == "export_total"


def test_fmt_rakes():
    assert [rl.fmt_rakes(v) for v in (None, 0, 2239.0, 46.3, 96.80000000000001)] == ["–", "0", "2239", "46.3", "96.8"]


def test_fytd_and_per_day():
    t = rl.loading_table(_rows({"2026-04": {"grand_total": 2239, "coal_coking": 46.3, "bogus": 9},
                                "2026-05": {"grand_total": 2302, "coal_coking": 50.5}}), "2026-05")
    by = {r["code"]: r for r in t["rows"]}
    assert t["fy"] == "2026-27" and t["has_data"] and t["month_labels"][0] == "Apr" and len(t["month_labels"]) == 12
    assert by["grand_total"]["months"][:3] == [2239, 2302, None] and by["grand_total"]["fytd"] == 4541
    assert by["grand_total"]["fytd_per_day"] == round(4541 / 61, 2)
    assert by["coal_coking"]["fytd"] == 96.8 and by["coal_coking"]["fytd_per_day"] is None
    assert by["per_day"]["months"][:3] == [74.63, 74.26, None] and by["per_day"]["fytd_per_day"] == round(4541 / 61, 2)
    assert by["ore_total"]["months"] == [None] * 12 and by["ore_total"]["fytd"] is None
    assert "bogus" not in by and [r["code"] for r in t["rows"] if r["kind"] != "group"][:1] == ["ore_ogom_jgom"]


def test_gap_month():
    t = rl.loading_table(_rows({"2026-04": {"grand_total": 2239}, "2026-06": {"grand_total": 2332}}), "2026-06")
    g = next(r for r in t["rows"] if r["code"] == "grand_total")
    assert g["months"][:3] == [2239, None, 2332] and g["fytd"] == 4571 and g["fytd_per_day"] == round(4571 / 60, 2)


def test_jan_mar_fy_and_future_months_blank():
    t = rl.loading_table(_rows({"2026-04": {"grand_total": 1}, "2027-02": {"grand_total": 5},
                                "2027-03": {"grand_total": 7}, "2027-04": {"grand_total": 9}}), "2027-02")
    g = next(r for r in t["rows"] if r["code"] == "grand_total")
    assert t["fy"] == "2026-27" and g["months"][0] == 1 and g["months"][10] == 5 and g["months"][11] is None
    assert g["fytd"] == 6


def test_no_rows_has_no_data():
    assert rl.loading_table([], "2026-10")["has_data"] is False
    assert rl.loading_table(_rows({"2027-04": {"grand_total": 9}}), "2026-10")["has_data"] is False


def test_placeholder(monkeypatch):
    import page_rail_logistics as prl
    monkeypatch.setattr(rl.rrake, "rail_loading_rows", lambda a, b: [])
    p = prl.generate_rail_logistics("2026-10", "loading")
    assert (p["type"], p["title"], p["available"]) == (
        "rail_logistics_loading", "Rail Logistics – Monthly Rail Loading", False)
    assert p["placeholder"] == "Monthly rail loading for FY 2026-27 not yet entered"
    assert list(prl.PAGE_IDS) == [40.05, 40.1, 40.2, 40.3]


def test_drifted_heading_is_reported_and_never_merged_into_the_month_before():
    text = _text().replace("during MAY 2026", "during the month of MAY'26")
    # April's own export total gone: May's must not be picked up in its place
    text = text.replace("Total export rakes : 4.0 rakes.", "", 1)
    months, problems = rlh.parse(text)
    assert "2026-05" not in months and "2026-04" not in months and len(months) == 5
    assert len(problems) == 2 and "2026-04: not found: export_total" in problems
    assert any(p.startswith("month heading not understood:") and "MAY'26" in p for p in problems)


# ── review hardening ─────────────────────────────────────────────────────────

def test_pellets_read_from_the_misc_section_only():
    text = _text().replace("(Vizag- 82, Gangavaram -34", "(Vizag- 82 incl Pellets-3, Gangavaram -34")
    assert "Pellets-3" in text
    months, problems = rlh.parse(text)
    assert months["2026-04"]["misc_pellets"] == 95 and months["2026-04"]["misc_other"] == 13 and problems == []


def test_month_typed_twice_is_reported_and_skipped():
    text = _text()
    october = text[text.index("*Rail Transportation Performance of SAIL during OCTOBER"):]
    months, problems = rlh.parse(text + "\n\n" + october.replace("2293 rakes", "9999 rakes"))
    assert "2026-10" not in months and len(months) == 6
    assert problems == ["2026-10: heading appears more than once; month skipped"]


def test_month_after_the_latest_possible_is_reported_and_skipped():
    months, problems = rlh.parse(_text().replace("OCTOBER 2026", "OCTOBER 2062"), latest="2026-11")
    assert "2062-10" not in months and len(months) == 6
    assert problems == ["2062-10: month is after 2026-11; skipped"]
    assert len(rlh.parse(_text(), latest="2026-10")[0]) == 7


def test_fmt_rakes_never_uses_an_exponent_or_minus_zero():
    assert rl.fmt_rakes(1234567) == "1234567" and rl.fmt_rakes(-0.04) == "0" and rl.fmt_rakes(15907.0) == "15907"


def test_save_month_refuses_unknown_codes(monkeypatch):
    saved = []
    monkeypatch.setattr(rl.rrake, "save_rail_loading", lambda *a: saved.append(a) or len(a[1]))
    with pytest.raises(ValueError, match="bogus"):
        rl.save_month("2026-04", {"grand_total": 1, "bogus": 2}, "u")
    assert saved == []
    assert rl.save_month("2026-04", {"grand_total": 1}, "u") == 1 and saved == [("2026-04", {"grand_total": 1}, "u")]


def test_repo_refuses_a_non_numeric_figure_before_connecting():
    from repo import rake as rrake
    with pytest.raises(ValueError, match="grand_total"):
        rrake.save_rail_loading("2026-04", {"grand_total": "abc"}, None)


# ── loader script ────────────────────────────────────────────────────────────

@pytest.fixture
def loader(monkeypatch):
    from scripts import load_rail_loading_highlights as script
    saved = []
    monkeypatch.setattr(script.rail_loading, "save_month", lambda m, v, u: saved.append(m) or len(v))
    return script, saved


def test_loader_dry_run_saves_nothing(loader, capsys):
    script, saved = loader
    assert script.main([str(FIXTURE), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "7 month(s) read, 0 problem(s)" in out and "Dry run: nothing saved." in out and saved == []


def test_loader_saves_every_month_or_only_the_ones_asked_for(loader):
    script, saved = loader
    assert script.main([str(FIXTURE)]) == 0 and saved == [f"2026-{m:02d}" for m in range(4, 11)]
    del saved[:]
    assert script.main([str(FIXTURE), "--month", "2026-10", "--month", "2026-04"]) == 0
    assert saved == ["2026-04", "2026-10"]
    assert script.main([str(FIXTURE), "--month", "2025-01"]) == 1          # not in the file


def test_loader_reads_a_note_saved_in_ansi(loader, tmp_path, capsys):
    script, saved = loader
    ansi = tmp_path / "note.txt"
    ansi.write_bytes(_text().encode("cp1252"))
    assert script.main([str(ansi), "--dry-run"]) == 0
    assert "7 month(s) read, 0 problem(s)" in capsys.readouterr().out


# ── export page list ─────────────────────────────────────────────────────────

def test_export_gets_each_missing_rail_logistics_page_in_its_place():
    import main

    def ids(pages):
        main._add_missing_rail_logistics_pages(pages)
        return [p["page"] for p in pages]

    assert ids([{"page": 40}, {"page": 1026}]) == [40, 40.05, 40.1, 40.2, 40.3, 1026]
    # a page list from before 40.05 existed (stale browser tab / old build)
    assert ids([{"page": 40}, {"page": 40.1}, {"page": 40.2}, {"page": 40.3}, {"page": 1026}]) == [
        40, 40.05, 40.1, 40.2, 40.3, 1026]
    assert ids([{"page": 40}, {"page": 40.05}, {"page": 40.1}, {"page": 40.2}, {"page": 40.3}]) == [
        40, 40.05, 40.1, 40.2, 40.3]
    assert ids([{"page": 5}]) == [5, 40.05, 40.1, 40.2, 40.3]
