"""SAIL mining leases (Annexure-1 page): the repo replace / read in a throwaway database."""
from repo import conn as rc


def _n():
    with rc.cursor() as cur:
        cur.execute("SELECT n FROM data_version WHERE id = 1")
        return cur.fetchone()[0]


def _row(**kw):
    base = {"s_no": "1", "mine": "Kiriburu Iron Ore Mine", "state": "Jharkhand", "lease": "Amalgamated lease- I, II & III",
            "mineral": "Iron Ore", "area": "2897.499", "reserves": "112", "status": "Operational",
            "mine_span": 1, "state_span": 1, "lease_span": 1, "mineral_span": 1, "area_span": 1,
            "reserves_span": 1, "status_span": 1, "grp": "", "grp_span": 1}
    base.update(kw)
    return base


def test_replace_then_list_round_trips(mysql_db):
    from repo import mines as ml
    assert ml.mining_leases_rows() == []
    rows = [_row(mine_span=2, state_span=2, grp="Iron Ore", grp_span=2, reserves="208( Broken area- 11MT)"),
            _row(s_no="2", mine="", state="", lease="Topailore", mineral="Iron Ore", reserves="Un-Explored",
                 mine_span=0, state_span=0)]
    assert ml.save_mining_leases(rows, "x@sail.in") == 2
    got = ml.mining_leases_rows()
    assert [r["s_no"] for r in got] == ["1", "2"] and [r["sort_order"] for r in got] == [1, 2]
    assert got[0]["reserves"] == "208( Broken area- 11MT)" and got[1]["reserves"] == "Un-Explored"
    assert (got[0]["mine_span"], got[1]["mine_span"]) == (2, 0)
    assert (got[0]["grp"], got[0]["grp_span"]) == ("Iron Ore", 2)


def test_replace_bumps_data_version(mysql_db):
    from repo import mines as ml
    n0 = _n()
    ml.save_mining_leases([_row()], None)
    assert _n() > n0


def test_replace_replaces_and_empty_clears(mysql_db):
    from repo import mines as ml
    ml.save_mining_leases([_row(), _row(s_no="2")], None)
    ml.save_mining_leases([_row(s_no="9")], None)
    assert [r["s_no"] for r in ml.mining_leases_rows()] == ["9"]
    assert ml.save_mining_leases([], None) == 0 and ml.mining_leases_rows() == []
