import pytest

import db
import page_secretary_review as psr


def _has_month(month):
    try:
        c = db.connect()
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM production_table WHERE report_month=? AND item_name='Hot Metal'", (month,))
        n = cur.fetchone()[0]
        c.close()
        return n > 0
    except Exception:
        return False


live = pytest.mark.skipif(not _has_month("2026-09"), reason="needs live DB with 2026-09 data")


def _r(row):
    return [None if v is None else round(v) for v in
            (row["cap"], row["app_m"], row["act_m"], row["gr_m"], row["cu_m"],
             row["app_ytd"], row["act_ytd"], row["gr_ytd"], row["cu_ytd"])]


@live
def test_production_matches_reference_deck():
    c = db.connect()
    prod = psr.build_production(c.cursor(), "2026-09")
    c.close()
    assert _r(prod["HM"]["SAIL"]) == [21113, 1945, 1594, -1, 92, 11286, 10203, 2, 96]
    assert _r(prod["CS"]["BSP"]) == [5961, 530, 355, -21, 72, 3212, 2866, 1, 96]
    assert _r(prod["CS"]["SSPs"]) == [414, 31, 17, -9, 49, 179, 128, -10, 62]
    assert _r(prod["SS"]["SSPs"]) == [574, 45, 32, 16, 67, 262, 183, 1, 63]
    assert _r(prod["FS"]["SAIL"]) == [17500, 1546, 1328, -2, 92, 9230, 8156, 1, 93]
    conv = _r(prod["FS"]["TOTAL_CONV"])
    assert conv[2] in (1375, 1376) and conv[3] == -1 and conv[4] == 96 and conv[6] in (8388, 8389)


@live
def test_techno_matches_reference_deck():
    warnings = []
    t = psr.build_techno(psr.period_labels("2026-09"), warnings)
    coke = t["SAIL"]["coke"]
    assert (coke["fy_m2"], coke["fy_m1"], round(coke["target"]), coke["month"], coke["ytd"]) == (421, 419, 400, 432, 424)
    assert [a for a, _ in coke["trend"]] == ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    assert t["SAIL"]["bfprod"]["month"] == 1.91
    assert t["SAIL"]["energy"]["target"] == 6.03
    assert t["BSP"]["coke"]["target"] == 407
    co2 = t["SAIL"]["co2"]
    assert co2["month_used"] in ("2026-08", "2026-09")


def test_context_for_month_without_data_has_warnings_not_errors():
    ctx = psr.build_context("2030-01")
    assert ctx["labels"]["mon"] == "Jan’30"
    assert ctx["production"]["HM"]["SAIL"]["act_m"] is None
    assert any("No production" in w for w in ctx["warnings"])
