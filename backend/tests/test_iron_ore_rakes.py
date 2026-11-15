"""Iron ore rakes from mines (Rail Logistics page 40.07): the registries and
the CSV parser on a small fixture, the repo in a throwaway database, the
upload API on an in-memory store, and the page data on hand-made counts."""
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


def test_parse_fixture():
    rows = ior.parse_csv(ior.read_file(FIXTURE.read_bytes()))
    assert len(rows) == 10 and all(isinstance(r["id"], int) for r in rows)
    assert {r["wagon_code"] for r in rows} == {"BX", "BS", "BY", "EL", "PR", "GP", "GS"}   # "by" upper-cased
    assert rows[0] == {"id": 101, "rpt_date": "2026-09-28", "report_month": "2026-09", "mine_code": "BOL",
                       "rake_no": "503", "dest": "DSP", "wagon_code": "BX", "l_wg": 25.0, "f_wg": 33.0}
    assert any(r["l_wg"] == 0 and r["f_wg"] == 0 for r in rows)        # zero-wagon rake kept
    assert rows[-1]["dest"] == "PRSP" and rows[-1]["rake_no"] == rows[0]["rake_no"]   # repeated rake_no kept


def test_ansi_and_padded_codes():
    text = _text().replace(",BOL,", ", bol ,")
    rows = ior.parse_csv(ior.read_file(text.encode("cp1252")))
    assert len(rows) == 10 and rows[0]["mine_code"] == "BOL"


@pytest.mark.parametrize("change, message", [
    (("id,unit,", "id,mine,"), "column"),                 # header missing
    ((",BOL,", ",XYZ,"), "XYZ"),                          # unknown mine
    ((",GS,", ",QQ,"), "QQ"),                             # unknown wagon type
    (("2026-10-04", "04-10-2026"), "Date is not YYYY-MM-DD"),  # not an ISO date
    (("109,BGM", "x9,BGM"), "Id is not a number"),                        # id not a number
])
def test_refusals(change, message):
    with pytest.raises(ValueError, match=message):
        ior.parse_csv(_text().replace(*change))


def test_refusal_names_the_line():
    with pytest.raises(ValueError, match="line 11"):
        ior.parse_csv(_text().replace("2026-10-04", "4/10/2026"))


def test_refuses_repeated_id_future_date_and_empty():
    with pytest.raises(ValueError, match="more than once: 110"):
        ior.parse_csv(_text().replace("109,BGM", "110,BGM"))
    with pytest.raises(ValueError, match="Date is in the future"):
        ior.parse_csv(_text().replace("2026-10-04", "2099-10-04"), today="2026-11-15")
    assert len(ior.parse_csv(_text(), today="2026-10-04")) == 10
    with pytest.raises(ValueError, match="no rakes"):
        ior.parse_csv(_text().splitlines()[0] + "\n\n")
    with pytest.raises(ValueError, match="no rakes"):
        ior.parse_csv("")


# ── repo ─────────────────────────────────────────────────────────────────────

def test_repo_round_trip(mysql_db):
    from repo import conn as rc
    from repo import rake as rrake

    def n():
        with rc.cursor() as cur:
            cur.execute("SELECT n FROM data_version WHERE id = 1")
            return cur.fetchone()[0]

    rows = ior.parse_csv(ior.read_file(FIXTURE.read_bytes()))
    assert rrake.iron_ore_rake_month_totals("2026-04", "2027-03") == {}
    n0 = n()
    out = rrake.save_iron_ore_rakes(rows, "x@sail.in")
    assert out == {"rakes": 10, "deleted": 0, "first_date": "2026-09-28", "last_date": "2026-10-04"}
    assert n() > n0
    assert rrake.iron_ore_rake_month_totals("2026-04", "2027-03") == {"2026-09": 4, "2026-10": 6}
    counts = rrake.iron_ore_rake_counts("2026-09", "2026-10")
    assert {(c["report_month"], c["mine_code"], c["wagon_code"]): c["rakes"] for c in counts}[
        ("2026-09", "BOL", "BX")] == 2
    assert sum(c["rakes"] for c in counts) == 10 and len(rrake.iron_ore_rake_counts("2026-10", "2026-10")) == 6
    # stored rakes dated outside a date range, per month (what an upload of that range leaves alone)
    assert rrake.iron_ore_rake_totals_outside("2026-10-02", "2026-10-03") == {"2026-10": 2}
    assert rrake.iron_ore_rake_totals_outside("2026-09-29", "2026-10-03") == {"2026-09": 2, "2026-10": 1}

    # a narrower re-upload replaces only its own dates: 2 October (2 rakes) -> 1 rake
    narrow = [dict(r, id=900) for r in rows if r["id"] == 105]
    out = rrake.save_iron_ore_rakes(narrow, None)
    assert out == {"rakes": 1, "deleted": 2, "first_date": "2026-10-02", "last_date": "2026-10-02"}
    assert rrake.iron_ore_rake_month_totals("2026-09", "2026-10") == {"2026-09": 4, "2026-10": 5}
    with pytest.raises(ValueError):
        rrake.save_iron_ore_rakes([], None)
    assert sum(rrake.iron_ore_rake_month_totals("2026-09", "2026-10").values()) > 0       # nothing cleared
