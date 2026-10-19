"""page4.generate_page4_rows(basis=...): MoU reads mou_plan_table and keeps
only the 5 MoU items; APP output is unchanged."""
import pytest

import page4
from repo.conn import tx


@pytest.fixture
def p4(mysql_db, monkeypatch):
    with tx() as c:
        c.execute("INSERT INTO production_table VALUES ('2026-08','BSP','Hot Metal',500)")
        c.execute("INSERT INTO production_plan_table VALUES ('2026-08','BSP','Hot Metal',550)")
        c.execute("INSERT INTO mou_plan_table VALUES ('2026-08','BSP','Hot Metal',570)")
        c.execute("INSERT INTO production_plan_table VALUES ('2026-08','BSP','Total Sinter',900)")
    monkeypatch.setattr(page4.db, "get_effective_capacity", lambda *a, **k: None)
    return page4


def _row(rows, display, plant):
    return next(r for r in rows if r["label"] == f"{display} {plant}")


def test_mou_uses_mou_table_and_mou_items(p4):
    rows = p4.generate_page4_rows("2026-08", raw=True, basis="mou")
    displays = {r["display_name"] for r in rows if not r.get("is_conversion") and not r.get("is_sail_incl_conv")}
    assert displays == {"HOT METAL", "CRUDE STEEL", "SALEABLE STEEL", "PIG IRON", "FINISHED STEEL"}
    hm = _row(rows, "HOT METAL", "BSP")["values"]
    assert hm[1] == 570 and hm[2] == 500


def test_app_basis_equals_default(p4):
    assert p4.generate_page4_rows("2026-08", raw=True, basis="app") == p4.generate_page4_rows("2026-08", raw=True)
    assert p4.generate_page4_rows("2026-08", basis="app") == p4.generate_page4_rows("2026-08")
    hm = _row(p4.generate_page4_rows("2026-08", raw=True), "HOT METAL", "BSP")["values"]
    assert hm[1] == 550


def test_unknown_basis_raises(p4):
    with pytest.raises(ValueError):
        p4.generate_page4_rows("2026-08", basis="abp")
