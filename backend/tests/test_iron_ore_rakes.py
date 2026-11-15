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


# ── upload API ───────────────────────────────────────────────────────────────

@pytest.fixture
def store(monkeypatch):
    """The repo's iron ore functions over an in-memory list of rakes."""
    import api_iron_ore_rakes as api
    rakes, users = [], []

    def totals(rows):
        out = {}
        for r in rows:
            out[r["report_month"]] = out.get(r["report_month"], 0) + 1
        return dict(sorted(out.items()))

    def save(rows, user):
        first, last = min(r["rpt_date"] for r in rows), max(r["rpt_date"] for r in rows)
        kept = [r for r in rakes if not first <= r["rpt_date"] <= last]
        deleted = len(rakes) - len(kept)
        rakes[:] = kept + list(rows)
        users.append(user)
        return {"rakes": len(rows), "deleted": deleted, "first_date": first, "last_date": last}

    monkeypatch.setattr(api.rrake, "iron_ore_rake_month_totals",
                        lambda a, b: totals(r for r in rakes if a <= r["report_month"] <= b))
    monkeypatch.setattr(api.rrake, "iron_ore_rake_totals_outside", lambda a, b: totals(
        r for r in rakes if a[:7] <= r["report_month"] <= b[:7] and not a <= r["rpt_date"] <= b))
    monkeypatch.setattr(api.rrake, "save_iron_ore_rakes", save)
    return rakes, users


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


def test_upload_needs_login(store):
    client = _client(logged_in=False)
    assert _upload(client, "preview").status_code == 401 and _upload(client, "insert").status_code == 401
    assert store[0] == []


def test_preview_saves_nothing(store):
    r = _upload(_client(), "preview")
    assert r.status_code == 200
    d = r.json()
    assert (d["status"], d["source_file"], d["rakes"]) == ("preview", "u_rakes_rmg.csv", 10)
    assert (d["first_date"], d["last_date"]) == ("2026-09-28", "2026-10-04")
    assert d["months"] == [{"report_month": "2026-09", "stored": 0, "in_file": 4, "after": 4},
                           {"report_month": "2026-10", "stored": 0, "in_file": 6, "after": 6}]
    assert d["reduces"] == [] and store[0] == []


def test_insert_saves(store):
    r = _upload(_client(), "insert")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "rakes": 10, "deleted": 0, "first_date": "2026-09-28",
                        "last_date": "2026-10-04"}
    assert len(store[0]) == 10 and store[1] == ["e@sail.in"]
    # the same file again changes nothing: no month listed, no confirmation asked
    d = _upload(_client(), "preview").json()
    assert d["months"] == [] and d["reduces"] == []
    assert _upload(_client(), "insert").status_code == 200 and len(store[0]) == 10


def test_reducing_a_month_needs_confirmation(store):
    client = _client()
    _upload(client, "insert")
    fewer = "\n".join(ln for ln in _text().splitlines() if not ln.startswith(("105,", "106,")))   # 2 October gone
    d = _upload(client, "preview", text=fewer).json()
    assert d["months"] == [{"report_month": "2026-10", "stored": 6, "in_file": 4, "after": 4}]
    assert d["reduces"] == ["2026-10"]
    r = _upload(client, "insert", text=fewer)
    assert r.status_code == 409 and "2026-10" in r.json()["detail"] and len(store[0]) == 10
    assert _upload(client, "insert", text=fewer, confirm_replace="true").status_code == 200 and len(store[0]) == 8


def test_a_narrow_file_leaves_other_dates_alone(store):
    client = _client()
    _upload(client, "insert")
    one_day = "\n".join(ln for ln in _text().splitlines() if ln.startswith(("id,", "105,", "106,")))
    d = _upload(client, "preview", text=one_day).json()
    assert d["months"] == [] and d["reduces"] == []            # same two rakes on 2 October
    assert _upload(client, "insert", text=one_day).status_code == 200 and len(store[0]) == 10


@pytest.mark.parametrize("text, message", [
    (None, "XYZ"), ("id,unit,rpt_date,rake_no,dest,type,l_wg,f_wg\n", "no rakes")])
def test_bad_file_is_422_and_saves_nothing(store, text, message):
    text = _text().replace(",BOL,", ",XYZ,") if text is None else text
    for path in ("preview", "insert"):
        r = _upload(_client(), path, text=text)
        assert r.status_code == 422 and message in r.json()["detail"]
    assert store[0] == []


def test_ansi_file_uploads(store):
    r = _upload(_client(), "preview", data=_text().encode("cp1252"))
    assert r.status_code == 200 and r.json()["rakes"] == 10
