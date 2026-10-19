"""repo.techno primitives: blobs() / merge_upsert() over techno_data."""
import json

from repo import conn as rc
from repo import techno as rt


def _insert(rows):
    """rows: (month, plant, unit, blob_or_raw_json_text, source_file)."""
    with rc.tx() as cur:
        cur.executemany(
            "INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW())",
            [(p, m, u, b if isinstance(b, str) else json.dumps(b), sf) for m, p, u, b, sf in rows])


def _row(month, plant, unit):
    with rc.cursor() as cur:
        cur.execute("SELECT techno_json, source_file FROM techno_data "
                    "WHERE report_month=%s AND plant=%s AND unit=%s", (month, plant, unit))
        r = cur.fetchone()
        return None if r is None else (json.loads(r[0]), r[1])


_SEED = [
    ("2026-04", "BSP", "BF_Shop", {"month": {"coke_rate": 400.5, "bf_count": 7},
                                   "till_month": {"coke_rate": 401.25}}, "a.xlsx"),
    ("2026-04", "BSP", "General", {"month": {"sp_energy": 6.1}}, "b.xlsx"),
    ("2026-04", "DSP", "BF_Shop", {"month": {"coke_rate": 420}, "till_month": {}}, ""),
    ("2026-05", "BSP", "BF_Shop", {"month": {"coke_rate": None, "cdi": 120.0},
                                   "till_month": {"cdi": None}}, ""),
]


def test_blobs_absent_row_has_no_key(mysql_db):
    _insert(_SEED)
    got = rt.blobs(["2026-04"], ["ISP"])
    assert got == {}
    got = rt.blobs(["2026-06"])
    assert got == {}
    got = rt.blobs(["2026-04"], ["DSP"], ["General"])
    assert ("2026-04", "DSP", "General") not in got
    assert got == {}


def test_blobs_month_only_row_stays_as_stored(mysql_db):
    _insert(_SEED)
    got = rt.blobs(["2026-04"], ["BSP"], ["General"])
    assert got == {("2026-04", "BSP", "General"): {"month": {"sp_energy": 6.1}}}
    assert "till_month" not in got[("2026-04", "BSP", "General")]


def test_blobs_int_and_float_keep_their_types(mysql_db):
    _insert(_SEED)
    blob = rt.blobs(["2026-04"], ["BSP", "DSP"], ["BF_Shop"])
    bsp = blob[("2026-04", "BSP", "BF_Shop")]["month"]
    assert bsp["coke_rate"] == 400.5 and type(bsp["coke_rate"]) is float
    assert bsp["bf_count"] == 7 and type(bsp["bf_count"]) is int
    dsp = blob[("2026-04", "DSP", "BF_Shop")]["month"]
    assert type(dsp["coke_rate"]) is int


def test_blobs_explicit_null_kept_as_none(mysql_db):
    _insert(_SEED)
    blob = rt.blobs(["2026-05"])[("2026-05", "BSP", "BF_Shop")]
    assert "coke_rate" in blob["month"] and blob["month"]["coke_rate"] is None
    assert blob["till_month"] == {"cdi": None}


def test_blobs_filters(mysql_db):
    _insert(_SEED)
    every = {(m, p, u): b for m, p, u, b, _ in _SEED}
    assert rt.blobs(["2026-04", "2026-05"]) == every
    assert rt.blobs(["2026-04"]) == {k: v for k, v in every.items() if k[0] == "2026-04"}
    assert rt.blobs(["2026-04", "2026-05"], plants=["DSP"]) == {
        ("2026-04", "DSP", "BF_Shop"): every[("2026-04", "DSP", "BF_Shop")]}
    assert rt.blobs(["2026-04", "2026-05"], units=["BF_Shop"]) == {
        k: v for k, v in every.items() if k[2] == "BF_Shop"}
    assert rt.blobs(["2026-04"], plants=["BSP"], units=["General", "BF_Shop"]) == {
        k: v for k, v in every.items() if k[0] == "2026-04" and k[1] == "BSP"}
    # iterables (not only lists) are accepted; empty filters select nothing
    assert rt.blobs(iter(["2026-05"]), plants=("BSP",)) == {
        ("2026-05", "BSP", "BF_Shop"): every[("2026-05", "BSP", "BF_Shop")]}
    assert rt.blobs([]) == {}
    assert rt.blobs(["2026-04"], plants=[]) == {}
    assert rt.blobs(["2026-04"], units=[]) == {}


def test_blobs_matches_get_techno_data(mysql_db):
    import db
    _insert(_SEED)
    for (m, p, u), blob in rt.blobs(["2026-04", "2026-05"]).items():
        assert db.get_techno_data(p, m, u) == {u: blob}


def test_merge_upsert_inserts_new_row(mysql_db):
    rt.merge_upsert("2026-07", "RSP", "BF_Shop",
                    {"month": {"coke_rate": 410.0}, "till_month": {"coke_rate": 409}}, "x.xlsx")
    blob, src = _row("2026-07", "RSP", "BF_Shop")
    assert blob == {"month": {"coke_rate": 410.0}, "till_month": {"coke_rate": 409}}
    assert src == "x.xlsx"


def test_merge_upsert_merges_into_existing(mysql_db):
    _insert(_SEED)
    rt.merge_upsert("2026-04", "BSP", "BF_Shop",
                    {"month": {"coke_rate": 399.0, "bf_count": None, "sinter_rate": 130},
                     "till_month": {}}, "c.xlsx")
    blob, src = _row("2026-04", "BSP", "BF_Shop")
    # new non-null overwrites, null keeps existing, untouched keys survive
    assert blob["month"] == {"coke_rate": 399.0, "bf_count": 7, "sinter_rate": 130}
    assert blob["till_month"] == {"coke_rate": 401.25}
    assert src == "c.xlsx"


def test_merge_upsert_updates_source_file(mysql_db):
    _insert(_SEED)
    rt.merge_upsert("2026-04", "BSP", "General", {"month": {}}, "new-source.pdf")
    blob, src = _row("2026-04", "BSP", "General")
    assert src == "new-source.pdf"
    assert blob["month"] == {"sp_energy": 6.1}


def test_merge_upsert_matches_db_merge(mysql_db):
    import db
    _insert(_SEED)
    new = {"month": {"coke_rate": 1.5, "nut_coke_rate": None}, "till_month": {"x": 2}}
    rt.merge_upsert("2026-04", "DSP", "BF_Shop", new, "s1")
    via_repo = _row("2026-04", "DSP", "BF_Shop")
    with rc.tx() as cur:
        cur.execute("DELETE FROM techno_data WHERE plant='DSP'")
    _insert([s for s in _SEED if s[1] == "DSP"])
    db.merge_upsert_techno_data("DSP", "2026-04", "BF_Shop", new, "s1")
    assert _row("2026-04", "DSP", "BF_Shop") == via_repo


def test_merge_upsert_logs_extraction_and_recomputes(mysql_db):
    """The moved write chain still runs its post-save hooks: the tmi /
    fuel_rate recompute and the extraction_log entry (db.log_extraction,
    bound at call time from repo.techno)."""
    rt.merge_upsert("2026-08", "BSL", "BF_Shop",
                    {"month": {"coke_rate": 400, "cdi": 100}, "till_month": {}}, "bsl.xlsx")
    blob, _ = _row("2026-08", "BSL", "BF_Shop")
    assert blob["month"]["fuel_rate"] == 500
    with rc.cursor() as cur:
        cur.execute("SELECT plant_name, report_month, file_name, sheet_name, source_type, items_extracted "
                    "FROM extraction_log")
        rows = [tuple(r) for r in cur.fetchall()]
    assert rows == [("BSL", "2026-08", "bsl.xlsx", "BF_Shop", "Techno Data", 2)]


def test_techno_plan_save_clears_cache_and_returns_copies(mysql_db):
    import db
    db._get_techno_plan_cached.cache_clear()
    assert db.get_techno_plan("BSP", "2026-27", "Shop") == {
        "data": {}, "is_user_supplied": False, "calculated": {}}
    db.save_techno_plan("BSP", "2026-27", "Shop", {"coke_rate": {"value": 410}})
    got = db.get_techno_plan("BSP", "2026-27", "Shop")
    assert got["data"] == {"coke_rate": {"value": 410}}
    got["data"]["coke_rate"]["value"] = 0          # caller mutation ...
    assert db.get_techno_plant_plan("BSP", "2026-27")["data"] == {"coke_rate": {"value": 410}}
    assert db.get_techno_plan("BSP", "2026-27", "Shop")["data"] == {"coke_rate": {"value": 410}}
    assert db.list_techno_plan_fys("BSP") == ["2026-27"]
