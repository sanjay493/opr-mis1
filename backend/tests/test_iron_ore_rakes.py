"""Iron ore rakes from mines (Rail Logistics page 40.07): the registries and
the CSV parser on a small fixture, the lines summed to monthly lump / fines
rakes, the repo in a throwaway database, the upload API on an in-memory
store, and the page data on hand-made counts."""
from pathlib import Path

import pytest

import iron_ore_rakes as ior

FIXTURE = Path(__file__).parent / "fixtures" / "iron_ore_rakes.csv"


def _text():
    return FIXTURE.read_text(encoding="utf-8-sig")


# ── registries and parser ────────────────────────────────────────────────────

def test_registries():
    assert {g: sorted(m for m, x in ior.MINE_GROUP.items() if x == g) for g in ("OGOM", "JGOM", "CGOM")} == {
        "OGOM": ["BAR", "BOL", "KAL", "TAL"], "JGOM": ["GUA", "KRB", "MBR", "MPR"], "CGOM": ["BGM", "DAL", "RAJ", "ROW"]}
    assert ior.WAGON_NAME == {"BS": "BOBSNM1", "BY": "BOYEL", "BX": "BOXN", "EL": "BOXN", "PR": "Private GPWIS",
                              "GP": "SAIL BOXN GPWIS", "GS": "SAIL BOBSNM1 GPWIS"}
    assert ior.ALL == ["EGOM", "CGOM", "Total"]
    assert (ior.CGOM_TOTAL_MINE, ior.CGOM_IN_RAKES_UPTO) == ("BGM", "2024-04-30")


def test_parse_fixture():
    rows = ior.parse_csv(ior.read_file(FIXTURE.read_bytes()))
    assert len(rows) == 10 and all(isinstance(r["id"], int) for r in rows)
    assert {r["wagon_code"] for r in rows} == {"BX", "BS", "BY", "EL", "PR", "GP", "GS"}   # "by" upper-cased
    assert rows[0] == {"id": 101, "rpt_date": "2026-09-01", "report_month": "2026-09", "mine_code": "BOL",
                       "rake_no": "503", "dest": "DSP", "wagon_code": "BX", "l_wg": 25.0, "f_wg": 33.0}
    assert rows[-1]["dest"] == "PRSP" and rows[-1]["rake_no"] == rows[0]["rake_no"]   # repeated rake_no kept


def test_ansi_and_padded_codes():
    text = _text().replace(",BOL,", ", bol ,")
    rows = ior.parse_csv(ior.read_file(text.encode("cp1252")))
    assert len(rows) == 10 and rows[0]["mine_code"] == "BOL"


@pytest.mark.parametrize("change, message", [
    (("id,unit,", "id,mine,"), "column"),                 # header missing
    ((",BOL,", ",XYZ,"), "XYZ"),                          # unknown mine
    ((",GS,", ",QQ,"), "QQ"),                             # unknown wagon type
    (("2026-10-31", "31-10-2026"), "Date is not YYYY-MM-DD"),  # not an ISO date
    (("109,BGM", "x9,BGM"), "Id is not a number"),                        # id not a number
    (("25.00,33.00", "-25.00,33.00"), "Wagon count is negative"),
])
def test_refusals(change, message):
    with pytest.raises(ValueError, match=message):
        ior.parse_csv(_text().replace(*change))


def test_refusal_names_the_line():
    with pytest.raises(ValueError, match="line 11"):
        ior.parse_csv(_text().replace("2026-10-31", "31/10/2026"))


def test_refuses_repeated_id_future_date_and_empty():
    with pytest.raises(ValueError, match="more than once: 110"):
        ior.parse_csv(_text().replace("109,BGM", "110,BGM"))
    with pytest.raises(ValueError, match="Date is in the future"):
        ior.parse_csv(_text().replace("2026-10-31", "2099-10-31"), today="2026-11-15")
    assert len(ior.parse_csv(_text(), today="2026-10-31")) == 10
    with pytest.raises(ValueError, match="no rakes"):
        ior.parse_csv(_text().splitlines()[0] + "\n\n")
    with pytest.raises(ValueError, match="no rakes"):
        ior.parse_csv("")


# ── lines -> monthly lump / fines rakes ──────────────────────────────────────

def _line(date, mine, lump, fines, wagon="BS", dest="BSP"):
    return {"rpt_date": date, "report_month": date[:7], "mine_code": mine, "wagon_code": wagon, "dest": dest,
            "l_wg": lump, "f_wg": fines}


def _by(monthly, *key):
    return {tuple(r[k] for k in key): (r["lump_rakes"], r["fines_rakes"]) for r in monthly["rows"]}


def test_monthly_rows_split_each_rake_by_its_wagons():
    m = ior.monthly_rows(ior.parse_csv(_text()))
    assert (m["months"], m["not_stored"], m["skipped"]) == (["2026-09", "2026-10"], [], 0)
    assert (m["first_date"], m["last_date"]) == ("2026-09-01", "2026-10-31")
    by = _by(m, "report_month", "mine_code", "wagon_code", "dest")
    assert len(by) == 9
    assert by[("2026-09", "BOL", "BX", "DSP")] == pytest.approx((25 / 58, 33 / 58))    # 25 lump + 33 fines wagons
    assert by[("2026-09", "BOL", "BX", "PRSP")] == (0, 1) and by[("2026-10", "DAL", "PR", "BSP")] == (1, 0)
    assert ("2026-10", "BGM", "BS", "BSP") not in by                                    # a CGOM day total of nothing
    assert sum(a + b for a, b in by.values()) == pytest.approx(9)                      # every rake adds 1


def test_old_cgom_is_counted_from_its_day_totals():
    m = ior.monthly_rows([
        _line("2024-04-01", "BGM", 1, 0), _line("2024-04-30", "BGM", 3, 4),    # CGOM's day totals: already rakes
        _line("2024-04-30", "DAL", 55, 0), _line("2024-04-30", "RAJ", 0, 54),  # the same rakes again: left out
        _line("2024-04-30", "BOL", 20, 38),                                    # not CGOM: one rake, by wagons
        _line("2024-05-01", "DAL", 30, 40),                                    # CGOM afterwards: rake by rake
        _line("2024-05-02", "DAL", None, None, dest=None), _line("2024-05-31", "RAJ", 0, 58, dest=None)])
    by = _by(m, "report_month", "mine_code", "dest")
    assert by[("2024-04", "BGM", "BSP")] == (4, 4)
    assert by[("2024-04", "BOL", "BSP")] == pytest.approx((20 / 58, 38 / 58))
    assert by[("2024-05", "DAL", "BSP")] == pytest.approx((3 / 7, 4 / 7))
    assert by[("2024-05", "RAJ", "")] == (0, 1) and m["skipped"] == 1 and len(by) == 4   # blank dest stored as ''


def test_only_whole_months_are_kept():
    lines = [_line("2026-09-28", "BOL", 1, 1), _line("2026-10-01", "BOL", 1, 1), _line("2026-10-31", "BOL", 1, 1),
             _line("2026-11-04", "BOL", 1, 1)]
    m = ior.monthly_rows(lines)
    assert (m["months"], m["not_stored"]) == (["2026-10"], ["2026-09", "2026-11"])
    assert _by(m, "report_month") == {("2026-10",): (1, 1)}
    for part in (lines[:1], [_line("2026-10-01", "BOL", 1, 1), _line("2026-10-30", "BOL", 1, 1)]):
        with pytest.raises(ValueError, match="no whole month"):
            ior.monthly_rows(part)


def test_whole():
    assert ior.whole(661.9999999) == 662 and isinstance(ior.whole(662.0), int) and ior.whole(3.456) == 3.46


# ── repo ─────────────────────────────────────────────────────────────────────

def test_repo_round_trip(mysql_db):
    from repo import conn as rc
    from repo import rake as rrake

    def n():
        with rc.cursor() as cur:
            cur.execute("SELECT n FROM data_version WHERE id = 1")
            return cur.fetchone()[0]

    m = ior.monthly_rows(ior.parse_csv(ior.read_file(FIXTURE.read_bytes())))
    assert rrake.iron_ore_rake_month_totals("2026-04", "2027-03") == {}
    n0 = n()
    out = rrake.save_iron_ore_rakes(m["rows"], m["months"], "x@sail.in")
    assert out == {"rows": 9, "deleted": 0, "months": ["2026-09", "2026-10"]}
    assert n() > n0
    assert rrake.iron_ore_rake_month_totals("2026-04", "2027-03") == pytest.approx({"2026-09": 4, "2026-10": 5})
    counts = rrake.iron_ore_rake_counts("2026-09", "2026-10")
    assert {(c["report_month"], c["mine_code"], c["wagon_code"]): c["rakes"] for c in counts}[
        ("2026-09", "BOL", "BX")] == pytest.approx(2)                  # both destinations
    assert sum(c["rakes"] for c in counts) == pytest.approx(9) and len(rrake.iron_ore_rake_counts("2026-10", "2026-10")) == 5
    assert [c["rakes"] for c in ior.stored_counts("2026-09", "2026-09")] == [2, 1, 1]

    # October again with one row: October is replaced, September stays
    october = [dict(r, lump_rakes=2.0) for r in m["rows"] if r["mine_code"] == "DAL"]
    out = rrake.save_iron_ore_rakes(october, ["2026-10"], None)
    assert out == {"rows": 1, "deleted": 5, "months": ["2026-10"]}
    assert rrake.iron_ore_rake_month_totals("2026-09", "2026-10") == pytest.approx({"2026-09": 4, "2026-10": 2})
    for rows, months in (([], []), (m["rows"], ["2026-10"])):          # nothing to save; a row outside the months
        with pytest.raises(ValueError):
            rrake.save_iron_ore_rakes(rows, months, None)
    assert rrake.iron_ore_rake_month_totals("2026-09", "2026-10") == pytest.approx({"2026-09": 4, "2026-10": 2})


# ── upload API ───────────────────────────────────────────────────────────────

@pytest.fixture
def store(monkeypatch):
    """The repo's iron ore functions over an in-memory {month: rows}."""
    import api_iron_ore_rakes as api
    stored, users = {}, []

    def save(rows, months, user):
        deleted = sum(len(stored.pop(m, [])) for m in months)
        for r in rows:
            stored.setdefault(r["report_month"], []).append(r)
        users.append(user)
        return {"rows": len(rows), "deleted": deleted, "months": sorted(months)}

    monkeypatch.setattr(api.rrake, "iron_ore_rake_month_totals", lambda a, b: {
        m: sum(r["lump_rakes"] + r["fines_rakes"] for r in rows) for m, rows in sorted(stored.items()) if a <= m <= b})
    monkeypatch.setattr(api.rrake, "save_iron_ore_rakes", save)
    return stored, users


def _client(logged_in=True):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import api_iron_ore_rakes as api
    app = FastAPI()
    app.include_router(api.router)
    if logged_in:
        app.dependency_overrides[api._auth.require_editor_or_admin] = lambda: {"email": "e@sail.in", "role": "editor"}
    return TestClient(app)


def _upload(client, path, data=None, text=None, **form):
    body = FIXTURE.read_bytes() if text is None else text.encode("utf-8")
    return client.post(f"/api/iron-ore-rakes/{path}", files={"file": ("u_rakes_rmg.csv", data or body, "text/csv")},
                       data=form)


def _only(*ids):
    return "\n".join(ln for ln in _text().splitlines() if ln.startswith(("id,", *ids)))


def test_upload_needs_login(store):
    client = _client(logged_in=False)
    assert _upload(client, "preview").status_code == 401 and _upload(client, "insert").status_code == 401
    assert store[0] == {}


def test_preview_saves_nothing(store):
    r = _upload(_client(), "preview")
    assert r.status_code == 200
    d = r.json()
    assert (d["status"], d["source_file"], d["rakes"]) == ("preview", "u_rakes_rmg.csv", 9)
    assert (d["first_date"], d["last_date"], d["not_stored"], d["skipped"]) == ("2026-09-01", "2026-10-31", [], 0)
    assert d["months"] == [{"report_month": "2026-09", "stored": 0, "in_file": 4, "after": 4},
                           {"report_month": "2026-10", "stored": 0, "in_file": 5, "after": 5}]
    assert d["reduces"] == [] and store[0] == {}


def test_insert_saves(store):
    r = _upload(_client(), "insert")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "rakes": 9, "rows": 9, "deleted": 0, "months": ["2026-09", "2026-10"]}
    assert sorted(store[0]) == ["2026-09", "2026-10"] and store[1] == ["e@sail.in"]
    # the same file again changes nothing: no month listed, no confirmation asked
    d = _upload(_client(), "preview").json()
    assert d["months"] == [] and d["reduces"] == []
    assert _upload(_client(), "insert").status_code == 200 and len(store[0]["2026-10"]) == 5


def test_reducing_a_month_needs_confirmation(store):
    client = _client()
    _upload(client, "insert")
    fewer = "\n".join(ln for ln in _text().splitlines() if not ln.startswith(("105,", "106,")))   # 2 October gone
    d = _upload(client, "preview", text=fewer).json()
    assert d["months"] == [{"report_month": "2026-10", "stored": 5, "in_file": 3, "after": 3}]
    assert d["reduces"] == ["2026-10"]
    r = _upload(client, "insert", text=fewer)
    assert r.status_code == 409 and "2026-10" in r.json()["detail"] and len(store[0]["2026-10"]) == 5
    assert _upload(client, "insert", text=fewer, confirm_replace="true").status_code == 200
    assert len(store[0]["2026-10"]) == 3 and len(store[0]["2026-09"]) == 4


def test_a_file_of_one_month_leaves_the_other_months_alone(store):
    client = _client()
    _upload(client, "insert")
    october = _only("104,", "105,", "106,", "107,", "108,", "109,")
    d = _upload(client, "preview", text=october).json()
    assert d["months"] == [] and d["reduces"] == []            # the same October
    assert _upload(client, "insert", text=october).json()["months"] == ["2026-10"]
    assert len(store[0]["2026-09"]) == 4 and len(store[0]["2026-10"]) == 5


def test_a_part_month_is_reported_and_not_saved(store):
    """The export was taken on 3 November: September is saved, November's three days are not."""
    text = _only("101,", "102,", "103,", "110,") + "\n111,BOL,2026-11-03,7,DSP,BX,25.00,33.00\n"
    d = _upload(_client(), "preview", text=text).json()
    assert (d["rakes"], d["not_stored"]) == (4, ["2026-11"]) and [m["report_month"] for m in d["months"]] == ["2026-09"]
    assert _upload(_client(), "insert", text=text).json()["months"] == ["2026-09"] and sorted(store[0]) == ["2026-09"]


@pytest.mark.parametrize("text, message", [
    (None, "XYZ"), ("id,unit,rpt_date,rake_no,dest,type,l_wg,f_wg\n", "no rakes"),
    ("id,unit,rpt_date,rake_no,dest,type,l_wg,f_wg\n1,BOL,2026-10-02,7,DSP,BX,25,33\n", "no whole month")])
def test_bad_file_is_422_and_saves_nothing(store, text, message):
    text = _text().replace(",BOL,", ",XYZ,") if text is None else text
    for path in ("preview", "insert"):
        r = _upload(_client(), path, text=text)
        assert r.status_code == 422 and message in r.json()["detail"]
    assert store[0] == {}


def test_ansi_file_uploads(store):
    r = _upload(_client(), "preview", data=_text().encode("cp1252"))
    assert r.status_code == 200 and r.json()["rakes"] == 9


# ── counts, mix, trend and the page ──────────────────────────────────────────

COUNTS = [  # (month, mine, wagon, rakes)
    ("2026-10", "BOL", "BX", 5), ("2026-10", "BOL", "EL", 2), ("2026-10", "KRB", "BS", 3), ("2026-10", "DAL", "BS", 4),
    ("2026-04", "KAL", "BS", 6), ("2026-04", "RAJ", "PR", 1),
    ("2025-10", "BOL", "BX", 10), ("2025-10", "DAL", "PR", 2), ("2025-04", "GUA", "BS", 6), ("2025-04", "ROW", "BS", 1),
    # every month of last FY to date has rakes, as the real record does
    *[(f"2025-{m:02d}", "ROW", "BS", 1) for m in range(5, 10)]]


def _counts(rows=COUNTS):
    return [{"report_month": m, "mine_code": mine, "wagon_code": w, "rakes": n} for m, mine, w, n in rows]


@pytest.fixture
def counts(monkeypatch):
    """repo.rake.iron_ore_rake_counts answering from COUNTS."""
    stored = _counts()
    monkeypatch.setattr(ior.rrake, "iron_ore_rake_counts",
                        lambda a, b: [c for c in stored if a <= c["report_month"] <= b])
    return stored


def test_type_rows_merge_groups_and_wagons():
    rows = {(r["report_month"], r["plant_code"], r["wagon_type"]): r["rakes"] for r in ior.type_rows(_counts())}
    assert rows[("2026-10", "EGOM", "BOXN")] == 7                     # BX + EL
    assert rows[("2026-10", "EGOM", "BOBSNM1")] == 3 and rows[("2026-10", "CGOM", "BOBSNM1")] == 4
    assert rows[("2025-04", "EGOM", "BOBSNM1")] == 6                  # JGOM counts as EGOM
    assert {g for _m, g, _t in rows} == {"EGOM", "CGOM"}


def test_group_totals():
    t = ior.group_totals(_counts())
    assert t["2026-10"] == {"OGOM": 7, "JGOM": 3, "EGOM": 10, "CGOM": 4, "Total": 14}
    assert t["2026-04"] == {"OGOM": 6, "JGOM": 0, "EGOM": 6, "CGOM": 1, "Total": 7}
    assert "2026-05" not in t


def test_report(counts):
    r = ior.build_report("2026-10")
    assert r["available"] and r["fy"] == "2026-27" and len(r["fy_months"]) == 12 and r["month_label"] == "Oct'26"
    assert list(r["trend"]) == ["EGOM", "CGOM", "Total"] and len(r["trend"]["EGOM"]) == 7
    assert r["trend"]["EGOM"][0]["fy"] == "2026-27" and r["trend"]["EGOM"][0]["months"][6] == 10
    assert r["trend"]["Total"][0]["total"] == 21 and r["trend"]["Total"][1]["months"][0] == 7
    assert [p["plant"] for p in r["wagon_mix"]["plants"]] == ["EGOM", "CGOM", "Total"]
    assert r["wagon_mix"]["basis"] == "last_fy"
    egom = r["wagon_mix"]["plants"][0]
    assert egom["fytd_total"] == 16 and {t["type"]: t["fytd_rakes"] for t in egom["types"]} == {"BOBSNM1": 9, "BOXN": 7}
    assert r["types"]["CGOM"] == {"BOBSNM1": {"2026-10": 4}, "Private GPWIS": {"2026-04": 1}}
    assert set(r["types"]) == {"EGOM", "CGOM"}


def test_key_points(counts):
    pts = ior.build_report("2026-10")["key_points"]
    assert pts[0] == "Iron ore loading from mines in Oct'26: EGOM 10 rakes (+0.0% vs Oct'25), CGOM 4 rakes (+100.0%)."
    assert pts[1] == ("FY to date the mines loaded 21 iron ore rakes, 12.5% behind the same period last year (24).")
    assert pts[2].startswith("Wagon mix (2026-27 vs same months of 2025-26): ") and " points to " in pts[2]
    assert len(pts) == 3


def test_month_without_rakes_yet(counts):
    """The report month is later than the last uploaded rake."""
    r = ior.build_report("2026-11")
    assert r["available"] and r["trend"]["EGOM"][0]["months"][6:8] == [10, None]
    assert not any(k.startswith("Iron ore loading from mines in") for k in r["key_points"])
    assert r["key_points"][0].startswith("FY to date (to Oct'26) the mines loaded 21 iron ore rakes, 12.5% behind")
    # the mix compares the months that have rakes, not November of last year too
    assert r["wagon_mix"]["plants"] == ior.build_report("2026-10")["wagon_mix"]["plants"]


def test_no_rakes_for_the_fy(counts):
    r = ior.build_report("2027-05")
    assert r["available"] is False and r["fy"] == "2027-28"
    assert ior.build_report("2019-05")["available"] is False


def test_plant_report_helpers_keep_their_defaults():
    import rake_despatch_report as rdr
    rows = [{"report_month": "2026-10", "plant_code": "BSP", "wagon_type": "BOXN", "rakes": 4}]
    assert [p["plant"] for p in rdr.wagon_mix("2026-10", rows)["plants"]] == ["BSP", "SAIL"]
    assert list(rdr.trend("2026-10", {"2026-10": {"BSP": 4, "SAIL": 4}})) == rdr.ALL


def test_trend_prints_no_figure_for_a_group_the_record_does_not_cover(counts):
    """The record has no CGOM mines before a point in time: those months are
    unknown, not zero."""
    counts[:] = [c for c in counts if not (c["report_month"] == "2025-05")] + _counts([("2025-05", "BOL", "BS", 3)])
    r = ior.build_report("2026-10")
    cgom_ly, egom_ly = r["trend"]["CGOM"][1], r["trend"]["EGOM"][1]
    assert cgom_ly["months"][1] is None and egom_ly["months"][1] == 3      # May'25: EGOM only
    assert r["trend"]["Total"][1]["months"][1] == 3
    assert r["trend"]["CGOM"][2]["months"] == [None] * 12 and r["trend"]["CGOM"][2]["total"] is None


def test_coverage_note_names_mines_that_enter_the_record_late(counts):
    # COUNTS: DAL and ROW rakes from 2025, RAJ from 2026-04; the window starts 2020-04
    note = ior.build_report("2026-10")["coverage_note"]
    assert note == ("In the record from: CGOM Apr'25, GUA Apr'25, BOL Oct'25, KAL Apr'26, KRB Oct'26. "
                    "Figures before those months leave these mines out.")       # CGOM named as one


def test_no_coverage_note_when_every_mine_is_there_from_the_start(counts):
    counts[:] = _counts([("2020-04", "BOL", "BS", 1), ("2026-10", "BOL", "BS", 1)])
    assert ior.build_report("2026-10")["coverage_note"] is None


# ── whole months only ────────────────────────────────────────────────────────

@pytest.mark.parametrize("last_date, through", [
    ("2026-10-31", "2026-10"), ("2026-11-04", "2026-10"), ("2026-10-30", "2026-09"), ("2026-11-30", "2026-11"),
    ("2026-01-15", "2025-12"), ("2024-02-29", "2024-02"), ("2024-02-28", "2024-01")])
def test_complete_through(last_date, through):
    assert ior.complete_through(last_date) == through


def test_nothing_stored(counts):
    counts[:] = []
    assert ior.stored_counts("2020-04", "2026-10") == [] and ior.build_report("2026-10")["available"] is False
