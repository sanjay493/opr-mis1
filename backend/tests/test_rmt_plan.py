"""RMT Production Plan report: repo.misc rmt_plan_manual / save_rmt_plan_manual,
rmt_plan.generate's totals and the calculated coal requirement."""
import pytest

from repo import conn as rc
from repo import misc as rmisc
from repo import production as rp


def _n():
    with rc.cursor() as cur:
        cur.execute("SELECT n FROM data_version WHERE id = 1")
        return cur.fetchone()[0]


def test_save_read_replace(mysql_db):
    assert rmisc.rmt_plan_manual("2026-11") is None
    n0 = _n()
    rmisc.save_rmt_plan_manual(
        "2026-11", "2026-10-30", "Note: figures are provisional",
        [{"section": "HM", "row_label": "BSP", "remarks": "**BF#7** shot creting"},
         {"section": "COKE", "row_label": "BSP", "remarks": "8 Rakes for IPT"}],
        [{"item": "BF Coke", "from_plant": "BSP", "availability": "8 Rakes"},
         {"item": "BF Coke", "to_plant": "RSP", "requirement": "16 Rakes"}],
        [{"plant": "BSP", "bf_coke": "22737", "slab": "0(RSP),\n1500(SSP)"}], "a@sail.in")
    assert _n() > n0
    m = rmisc.rmt_plan_manual("2026-11")
    assert (m["stock_as_on"], m["note"], m["updated_by"]) == ("2026-10-30", "Note: figures are provisional", "a@sail.in")
    assert [(r["section"], r["row_label"], r["remarks"]) for r in m["notes"]] == [
        ("COKE", "BSP", "8 Rakes for IPT"), ("HM", "BSP", "**BF#7** shot creting")]
    assert [(r["item"], r["from_plant"], r["to_plant"]) for r in m["ipt"]] == [("BF Coke", "BSP", None), ("BF Coke", None, "RSP")]
    assert m["stock"][0]["slab"] == "0(RSP),\n1500(SSP)"

    # a save replaces the month's rows
    rmisc.save_rmt_plan_manual("2026-11", None, None, [], [{"item": "Sinter", "to_plant": "RSP"}], [], None)
    m = rmisc.rmt_plan_manual("2026-11")
    assert (m["stock_as_on"], m["notes"], m["stock"]) == (None, [], [])
    assert [r["item"] for r in m["ipt"]] == ["Sinter"]


def test_generate_totals(mysql_db):
    import rmt_plan

    for plant, app, op in (("BSP", 558.0, 535.0), ("DSP", 229.0, 229.0)):
        rp.save_production_plan("2026-11", plant, "Hot Metal", app)
        rp.save_op_plan("2026-11", plant, [("Hot Metal", op)], None)
    rp.save_production_plan("2026-11", "ISP", "Hot Metal", 257.0)          # APP, no OP yet
    rp.save_production_plan("2026-11", "VISL", "Hot Metal", 0.0)           # zero APP needs no OP
    d = rmt_plan.generate("2026-11")
    hm = {r["row"]: r for r in d["page1"][0]["rows"]}
    assert (hm["BSP"]["app"], hm["BSP"]["app_tpd"], hm["BSP"]["op"]) == (558.0, 18600, 535.0)
    assert hm["SAIL"]["app"] == 558.0 + 229.0 + 257.0
    assert hm["SAIL"]["op"] is None                     # ISP has an APP but no OP

    rp.save_op_plan("2026-11", "ISP", [("Hot Metal", 265.0)], None)
    hm = {r["row"]: r for r in rmt_plan.generate("2026-11")["page1"][0]["rows"]}
    assert hm["SAIL"]["op"] == 535.0 + 229.0 + 265.0    # VISL's zero APP does not block the total


def test_coal_requirement(mysql_db):
    import rmt_plan
    from repo import techno as rtech

    # two norms (two batteries): the smaller is used; FY 2026-27 covers Nov'26
    rtech.save_techno_plan("RSP", "2026-27", "COB-new", {"dry_coal_charge_oven": {"unit": "t/oven", "value": 30.05}})
    rtech.save_techno_plan("RSP", "2026-27", "COB-old", {"dry_coal_charge_oven": {"unit": "t/oven", "value": 15.74}})
    rtech.save_techno_plan("DSP", "2026-27", "Coke Ovens", {"dry_coal_charge_oven": {"unit": "t/oven", "value": 16.9}})
    rtech.save_techno_plan("BSP", "2025-26", "COB", {"dry_coal_charge_batt_1_8": {"unit": "t/oven", "value": 16.5}})
    for plant, app, op in (("RSP", 502.7, 518.25), ("DSP", 330.34, 335.0)):
        rp.save_production_plan("2026-11", plant, "Oven Pushing (nos/day)", app)
        rp.save_op_plan("2026-11", plant, [("Oven Pushing (nos/day)", op)], None)

    d = rmt_plan.generate("2026-11")
    basis = {b["plant"]: b for b in d["coal_basis"]["plants"]}
    assert set(basis) == {"RSP", "DSP"}                   # BSP's target is for another FY
    assert basis["RSP"]["dcc"] == 15.74 and [n["value"] for n in basis["RSP"]["norms"]] == [30.05, 15.74]
    per = 15.74 / (0.98 * 0.90)
    assert basis["RSP"]["per_pushing"] == pytest.approx(per)
    coke = {r["row"]: r for r in d["page2"][0]["rows"]}
    assert coke["RSP"]["op_day"] == round(per * 518.25) == 9249
    assert coke["RSP"]["app_day"] == round(per * 502.7)
    assert coke["DSP"]["op_day"] == round(16.9 / (0.98 * 0.90) * 335.0) == 6419
    assert coke["5 ISPs"]["op_day"] == 9249 + 6419

    # a plant with pushings but no dry coal charge target blanks the total
    rp.save_production_plan("2026-11", "BSP", "Oven Pushing (nos/day)", 775.0)
    coke = {r["row"]: r for r in rmt_plan.generate("2026-11")["page2"][0]["rows"]}
    assert coke["BSP"]["app_day"] is None and coke["5 ISPs"]["app_day"] is None
