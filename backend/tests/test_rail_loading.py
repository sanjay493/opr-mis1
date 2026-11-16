"""Monthly rail loading (Rail Logistics page 40.05): the repo save / read in a
throwaway database, the highlights-note parser against a copy of the real
note, and the page table on small hand-made figures."""
from pathlib import Path

import pytest

import rail_loading as rl
import rail_loading_highlights as rlh


@pytest.fixture(autouse=True)
def notes(monkeypatch):
    """rail_loading's report_text calls on a dict {month: {block: text}}, so no
    test below reads or writes the real database through them."""
    store = {}
    monkeypatch.setattr(rl.rtx, "get_texts", lambda m: dict(store.get(m, {})))
    monkeypatch.setattr(rl.rtx, "save_texts", lambda m, t: store.setdefault(m, {}).update(t) or len(t))
    return store


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
    assert len(rl.CODES) == 34 and len(set(rl.CODES)) == 34
    # the note has no OGOM / JGOM split and no mine-wise flux: those are entered by hand
    assert set(rl.CODES) - set(APR) == {
        "ore_ogom", "ore_jgom", "flux_ls_kuteswar", "flux_ls_nandini", "flux_ls_rsmml", "flux_ls_wonder",
        "flux_ls_other", "flux_dol_hirri", "flux_dol_other"}
    assert set(APR) <= set(rl.CODES)
    kinds = [k for k, _c, _l in rl.ITEMS]
    assert kinds.count("group") == 3 and kinds.count("sub") == 3
    assert rl.CODES[0] == "ore_ogom" and rl.CODES[-1] == "export_total"
    assert all(len(c) <= 32 for c in rl.CODES)


def test_iron_ore_and_flux_blocks_in_print_order():
    rows = [(k, c) for k, c, _l in rl.ITEMS]
    i = rows.index(("sub", "ore"))
    assert rows[i:i + 19] == [
        ("sub", "ore"), ("subitem", "ore_ogom"), ("subitem", "ore_jgom"), ("subitem", "ore_ogom_jgom"),
        ("subitem", "ore_bhilai"), ("total", "ore_total"),
        ("sub", "limestone"), ("subitem", "flux_ls_kuteswar"), ("subitem", "flux_ls_nandini"),
        ("subitem", "flux_ls_rsmml"), ("subitem", "flux_ls_wonder"), ("subitem", "flux_ls_other"),
        ("total", "flux_limestone"),
        ("sub", "dolomite"), ("subitem", "flux_dol_hirri"), ("subitem", "flux_dol_other"), ("total", "flux_dolomite"),
        ("total", "flux_total"), ("item", "port_coal")]
    assert rl.LABELS["ore_ogom_jgom"] == "EGOM (OGOM + JGOM)" and rl.LABELS["ore_bhilai"] == "CGOM"


def test_sub_heading_rows_carry_no_figures():
    t = rl.loading_table(_rows({"2026-04": {"ore_ogom": 400, "ore_jgom": 241, "flux_limestone": 120}}), "2026-04")
    by = {r["code"]: r for r in t["rows"]}
    assert by["ore"]["months"] == [None] * 12 and by["ore"]["fytd"] is None and by["ore"]["fytd_per_day"] is None
    assert by["ore_ogom"]["kind"] == "subitem" and by["ore_ogom"]["fytd"] == 400
    assert by["ore_ogom"]["fytd_per_day"] == round(400 / 30, 2)       # per day on every row with figures
    assert by["flux_limestone"]["kind"] == "total" and by["flux_limestone"]["fytd_per_day"] == 4.0


def test_with_derived():
    d = rl.with_derived({"ore_ogom": 400, "ore_jgom": 241.5, "ore_ogom_jgom": 1,
                         "flux_limestone": 120, "flux_ls_kuteswar": 50, "flux_ls_wonder": 20.5,
                         "flux_dolomite": 79, "flux_dol_hirri": 79, "misc_total": 108, "misc_pellets": 95})
    assert d["ore_ogom_jgom"] == 1                                      # EGOM is typed as reported, never summed
    assert d["flux_ls_other"] == 49.5 and d["flux_dol_other"] == 0 and d["misc_other"] == 13


def test_with_derived_leaves_what_it_cannot_work_out():
    # a month from before the mines were reported apart: EGOM stays as entered
    d = rl.with_derived({"ore_ogom_jgom": 641, "ore_ogom": 400, "flux_limestone": 120, "flux_ls_other": 7,
                         "flux_dol_hirri": 5})
    assert d["ore_ogom_jgom"] == 641
    assert d["flux_ls_other"] is None                                   # no named mine entered
    assert d["flux_dol_other"] is None and d["misc_other"] is None      # no total entered


def test_with_derived_refuses_rows_above_their_total():
    with pytest.raises(ValueError, match="Total limestone"):
        rl.with_derived({"flux_limestone": 100, "flux_ls_kuteswar": 60, "flux_ls_nandini": 41})


# ── entry API ────────────────────────────────────────────────────────────────

# uploaded mines rakes: October 2026 only (381 OGOM, 281 JGOM, CGOM ignored here)
RAKES = [{"report_month": "2026-10", "mine_code": mine, "wagon_code": "BS", "rakes": n}
         for mine, n in (("BOL", 300), ("KAL", 81), ("KRB", 281), ("DAL", 211))]

@pytest.fixture
def api(monkeypatch):
    import api_rail_loading as api
    store = {}
    monkeypatch.setattr(api.rrake, "rail_loading_rows", lambda a, b: [
        {"report_month": a, "item_code": c, "rakes": v} for c, v in store.get(a, {}).items()])
    monkeypatch.setattr(api.rail_loading.rrake, "save_rail_loading",
                        lambda m, v, u: store.__setitem__(m, dict(v, _user=u)) or len(v))
    monkeypatch.setattr(api.rail_loading.rrake, "iron_ore_rake_counts", lambda a, b: [
        c for c in RAKES if a <= c["report_month"] <= b])
    return api, store


def test_api_save_fills_derived_rows_and_skips_blanks(api):
    api, store = api
    out = api.rail_loading_save({"report_month": "2026-11", "values": {
        "ore_ogom": 400, "ore_jgom": 250, "ore_bhilai": 200, "ore_total": 850, "out_sinter": None, "out_coke": "",
        "flux_limestone": 120, "flux_ls_kuteswar": 50, "flux_ls_other": 999}}, {"email": "e@sail.in"})
    assert out["status"] == "ok" and out["saved"] == 7
    assert store["2026-11"] == {"ore_ogom": 400, "ore_jgom": 250, "ore_bhilai": 200, "ore_total": 850,
                                "flux_limestone": 120, "flux_ls_kuteswar": 50,
                                "flux_ls_other": 70, "_user": "e@sail.in"}


def test_api_get_lists_every_row_in_print_order(api):
    api, store = api
    store["2026-11"] = {"ore_ogom": 400.0}
    d = api.rail_loading_month("2026-11")
    assert [r["code"] for r in d["rows"]] == [c for k, c, _l in rl.ITEMS if k != "per_day"]
    by = {r["code"]: r for r in d["rows"]}
    assert by["ore_ogom"]["value"] == 400.0 and by["ore_jgom"]["value"] is None
    assert [c for c, r in by.items() if r["derived"]] == ["flux_ls_other", "flux_dol_other", "misc_other"]
    assert d["egom"] == "ore_ogom_jgom" and d["egom_parts"] == ["ore_ogom", "ore_jgom"]
    assert d["egom_file"] is None and not any(r["from_file"] for r in d["rows"])     # no rakes uploaded for November


def test_api_marks_rows_from_the_file(api):
    api, store = api
    store["2026-10"] = {"ore_ogom": 1.0, "ore_ogom_jgom": 660.0}
    d = api.rail_loading_month("2026-10")
    by = {r["code"]: r for r in d["rows"]}
    assert (by["ore_ogom"]["value"], by["ore_ogom"]["from_file"]) == (381, True)       # the file, not the typed 1
    assert (by["ore_jgom"]["value"], by["ore_jgom"]["from_file"]) == (281, True)
    assert by["ore_ogom_jgom"]["value"] == 660.0 and by["ore_ogom_jgom"]["from_file"] is False
    assert d["egom_file"] == 662


def test_api_save_drops_typed_ogom_when_the_month_has_rakes(api):
    api, store = api
    out = api.rail_loading_save({"report_month": "2026-10", "values": {
        "ore_ogom": 5, "ore_jgom": 6, "ore_ogom_jgom": 662, "ore_bhilai": 209}}, {"email": "e@sail.in"})
    assert out["saved"] == 2 and store["2026-10"] == {"ore_ogom_jgom": 662, "ore_bhilai": 209, "_user": "e@sail.in"}
    by = {r["code"]: r for r in out["rows"]}
    assert by["ore_ogom"]["value"] == 381 and by["ore_ogom"]["from_file"]


def test_overlay_wins_on_the_page(monkeypatch):
    stored = _rows({"2026-09": {"ore_ogom": 290, "ore_ogom_jgom": 529, "grand_total": 2115},
                    "2026-10": {"ore_ogom": 1, "ore_ogom_jgom": 662, "grand_total": 2293}})
    monkeypatch.setattr(rl.rrake, "rail_loading_rows", lambda a, b: stored)
    monkeypatch.setattr(rl.rrake, "iron_ore_rake_counts", lambda a, b: [c for c in RAKES if a <= c["report_month"] <= b])
    assert rl.mines_overlay("2026-04", "2026-10") == {"2026-10": {"ore_ogom": 381, "ore_jgom": 281}}
    by = {r["code"]: r for r in rl.build_page("2026-10")["rows"]}
    assert by["ore_ogom"]["months"][5:7] == [290, 381]      # September typed (no rakes uploaded), October from the file
    assert by["ore_jgom"]["months"][5:7] == [None, 281]
    assert by["ore_ogom_jgom"]["months"][6] == 662 and by["grand_total"]["months"][6] == 2293


def test_page_shows_ogom_jgom_from_the_file_even_with_nothing_typed(monkeypatch):
    monkeypatch.setattr(rl.rrake, "rail_loading_rows", lambda a, b: [])
    monkeypatch.setattr(rl.rrake, "iron_ore_rake_counts", lambda a, b: [c for c in RAKES if a <= c["report_month"] <= b])
    p = rl.build_page("2026-10")
    assert p["available"] and {r["code"]: r for r in p["rows"]}["ore_ogom"]["fytd"] == 381


@pytest.mark.parametrize("values, status", [
    ({"bogus": 1}, 422), ({"ore_ogom": "12"}, 422), ({"ore_ogom": -1}, 422), ({"ore_ogom": True}, 422),
    ({"flux_dolomite": 10, "flux_dol_hirri": 11}, 422)])
def test_api_refuses_bad_input_and_saves_nothing(api, values, status):
    from fastapi import HTTPException
    api, store = api
    with pytest.raises(HTTPException) as e:
        api.rail_loading_save({"report_month": "2026-11", "values": values}, {"email": None})
    assert e.value.status_code == status and store == {}
    with pytest.raises(HTTPException):
        api.rail_loading_save({"report_month": "Nov 2026", "values": {}}, {"email": None})


def test_api_save_needs_an_editor_login():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import api_rail_loading as api
    app = FastAPI()
    app.include_router(api.router)
    r = TestClient(app).post("/api/rail-loading", json={"report_month": "2026-11", "values": {}})
    assert r.status_code == 401


def test_fmt_rakes():
    assert [rl.fmt_rakes(v) for v in (None, 0, 2239.0, 46.3, 96.80000000000001)] == ["–", "0", "2239", "46.3", "96.8"]


def test_fytd_and_per_day():
    t = rl.loading_table(_rows({"2026-04": {"grand_total": 2239, "coal_coking": 46.3, "bogus": 9},
                                "2026-05": {"grand_total": 2302, "coal_coking": 50.5}}), "2026-05")
    by = {r["code"]: r for r in t["rows"]}
    assert t["fy"] == "2026-27" and t["has_data"] and t["month_labels"][0] == "Apr" and len(t["month_labels"]) == 12
    assert by["grand_total"]["months"][:3] == [2239, 2302, None] and by["grand_total"]["fytd"] == 4541
    assert by["grand_total"]["fytd_per_day"] == round(4541 / 61, 2)
    assert by["coal_coking"]["fytd"] == 96.8 and by["coal_coking"]["fytd_per_day"] == round(96.8 / 61, 2)
    assert by["per_day"]["months"][:3] == [74.63, 74.26, None] and by["per_day"]["fytd_per_day"] == round(4541 / 61, 2)
    assert by["ore_total"]["months"] == [None] * 12 and by["ore_total"]["fytd"] is None
    assert "bogus" not in by and [r["code"] for r in t["rows"] if r["kind"] not in ("group", "sub")][:1] == ["ore_ogom"]


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
    monkeypatch.setattr(rl.rrake, "iron_ore_rake_counts", lambda a, b: [])
    p = prl.generate_rail_logistics("2026-10", "loading")
    assert (p["type"], p["title"], p["available"]) == (
        "rail_logistics_loading", "Rail Logistics – Monthly Rail Loading", False)
    assert p["placeholder"] == "Monthly rail loading for FY 2026-27 not yet entered"
    assert list(prl.PAGE_IDS) == [40.05, 40.07, 40.1, 40.2, 40.3]


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

    every = [40.05, 40.07, 40.1, 40.2, 40.3]
    assert ids([{"page": 40}, {"page": 1026}]) == [40] + every + [1026]
    # a page list from before 40.05 / 40.07 existed (stale browser tab / old build)
    assert ids([{"page": 40}, {"page": 40.1}, {"page": 40.2}, {"page": 40.3}, {"page": 1026}]) == [40] + every + [1026]
    assert ids([{"page": 40}, {"page": 40.05}, {"page": 40.1}, {"page": 40.2}, {"page": 40.3}]) == [40] + every
    assert ids([{"page": 40}] + [{"page": pg} for pg in every]) == [40] + every
    assert ids([{"page": 5}]) == [5] + every


def test_a_partly_uploaded_month_keeps_the_typed_ogom_and_jgom(monkeypatch, api):
    """The file ended on 20 October, so October was not stored: it is typed, as before any upload."""
    api, store = api
    monkeypatch.setattr(rl.rrake, "iron_ore_rake_counts", lambda a, b: [])
    stored = _rows({"2026-10": {"ore_ogom": 380, "ore_jgom": 282, "ore_ogom_jgom": 662}})
    monkeypatch.setattr(rl.rrake, "rail_loading_rows", lambda a, b: stored)
    assert rl.mines_overlay("2026-04", "2026-10") == {}
    by = {r["code"]: r for r in rl.build_page("2026-10")["rows"]}
    assert by["ore_ogom"]["months"][6] == 380 and by["ore_jgom"]["months"][6] == 282
    d = api.rail_loading_month("2026-10")
    assert d["egom_file"] is None and not any(r["from_file"] for r in d["rows"])
    api.rail_loading_save({"report_month": "2026-10", "values": {"ore_ogom": 380, "ore_jgom": 282}}, {"email": None})
    assert store["2026-10"] == {"ore_ogom": 380, "ore_jgom": 282, "_user": None}        # typed values kept


def test_page_prints_rakes_per_day_and_export_in_total_rakes():
    rows = [{"report_month": m, "item_code": c, "rakes": v}
            for m, c, v in (("2026-04", "ore_ogom", 300), ("2026-05", "ore_ogom", 310),
                            ("2026-04", "export_port", 12), ("2026-05", "export_port", 9))]
    by = {r["code"]: r for r in rl.loading_table(rows, "2026-05")["rows"]}
    ogom = by["ore_ogom"]
    assert ogom["pd_months"][:3] == [10.0, 10.0, None] and ogom["pd_fytd"] == round(610 / 61, 2) and ogom["cum_total"] == 610
    exp = by["export_port"]
    assert exp["pd_months"][:2] == [12, 9] and exp["pd_fytd"] == 21 and exp["cum_total"] == 21


def test_note_round_trip_and_page(monkeypatch, notes):
    monkeypatch.setattr(rl.rrake, "rail_loading_rows", lambda a, b: [
        {"report_month": "2026-10", "item_code": "grand_total", "rakes": 2293}])
    monkeypatch.setattr(rl.rrake, "iron_ore_rake_counts", lambda a, b: [])
    assert rl.build_page("2026-10")["note"] == []
    rl.save_note("2026-10", "  Inward 53.3 rakes/day  \r\n\r\n Outward 20.7 rakes/day ")
    assert notes["2026-10"] == {rl.NOTE_KEY: "Inward 53.3 rakes/day\nOutward 20.7 rakes/day"}
    page = rl.build_page("2026-10")
    assert page["note"] == ["Inward 53.3 rakes/day", "Outward 20.7 rakes/day"]
    assert page["note_title"] == "Inward and Outward Rakes wrt Steel Plants"
    rl.save_note("2026-10", "  ")
    assert rl.build_page("2026-10")["note"] == []


def test_note_too_long_is_refused(notes):
    with pytest.raises(ValueError):
        rl.save_note("2026-10", "x" * (rl.NOTE_LINE_MAX + 1))
    assert notes == {}


def test_api_note_saved_with_the_month_and_read_back(api):
    api, store = api
    out = api.rail_loading_save({"report_month": "2026-11", "values": {"ore_bhilai": 200}, "note": "Inward up"},
                                {"email": "e@sail.in"})
    assert out["note"] == "Inward up" and out["note_lines"] == rl.NOTE_LINES
    assert api.rail_loading_month("2026-11")["note"] == "Inward up"
    # a save without a note key leaves the note alone
    api.rail_loading_save({"report_month": "2026-11", "values": {"ore_bhilai": 210}}, {"email": "e@sail.in"})
    assert api.rail_loading_month("2026-11")["note"] == "Inward up"


def test_api_too_long_note_saves_nothing(api):
    from fastapi import HTTPException
    api, store = api
    with pytest.raises(HTTPException) as e:
        api.rail_loading_save({"report_month": "2026-11", "values": {"ore_bhilai": 200},
                               "note": "x" * (rl.NOTE_LINE_MAX + 1)}, {"email": "e@sail.in"})
    assert e.value.status_code == 422 and store == {}


def test_note_over_two_lines_is_refused(notes):
    with pytest.raises(ValueError, match="3 lines"):
        rl.save_note("2026-10", "a\nb\nc")
    rl.save_note("2026-10", "a\nb")
    assert notes["2026-10"][rl.NOTE_KEY] == "a\nb"
