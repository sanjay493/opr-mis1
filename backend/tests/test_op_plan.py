"""Operating Plan (OP): repo.production's production_op_monthly functions."""
from repo import conn as rc
from repo import production as rp


def _n():
    with rc.cursor() as cur:
        cur.execute("SELECT n FROM data_version WHERE id = 1")
        return cur.fetchone()[0]


def test_save_read_update_clear(mysql_db):
    n0 = _n()
    assert rp.save_op_plan("2026-11", "BSP", [("Hot Metal", 520.5), ("Total Crude Steel", 470.0),
                                              ("  ", 1.0)], "a@sail.in") == (2, 0)
    assert _n() > n0
    assert [(n, v, by) for n, v, by, _ in rp.op_plan_items("BSP", "2026-11")] == [
        ("Hot Metal", 520.5, "a@sail.in"), ("Total Crude Steel", 470.0, "a@sail.in")]
    assert rp.op_plan_items("BSP", "2026-12") == [] and rp.op_plan_items("DSP", "2026-11") == []

    # update one, clear the other, clear an item that never had an OP
    assert rp.save_op_plan("2026-11", "BSP", [("Hot Metal", 530.0), ("Total Crude Steel", None),
                                              ("Never Entered", None)], "b@sail.in") == (1, 1)
    assert [(n, v, by) for n, v, by, _ in rp.op_plan_items("BSP", "2026-11")] == [("Hot Metal", 530.0, "b@sail.in")]

    rp.save_op_plan("2026-11", "RSP", [("Hot Metal", 300.0)], None)
    assert rp.op_plan_plant_counts("2026-11") == [("BSP", 1), ("RSP", 1)]


def test_op_does_not_touch_the_app(mysql_db):
    rp.save_production_plan("2026-11", "BSP", "Hot Metal", 500.0)
    rp.save_op_plan("2026-11", "BSP", [("Hot Metal", 530.0)], "a@sail.in")
    with rc.cursor() as cur:
        assert [tuple(r) for r in rp.plant_month_plan_items(cur, "BSP", "2026-11")] == [("Hot Metal", 500.0)]
