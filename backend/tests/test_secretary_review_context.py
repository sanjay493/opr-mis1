import pytest

import board_note_common as bnc
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


def _db_up():
    try:
        db.connect().close()
        return True
    except Exception:
        return False


live = pytest.mark.skipif(not _has_month("2026-09"), reason="needs live DB with 2026-09 data")
db_up = pytest.mark.skipif(not _db_up(), reason="needs a reachable DB")


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


@db_up
def test_context_for_month_without_data_has_warnings_not_errors():
    ctx = psr.build_context("2030-01")
    assert ctx["labels"]["mon"] == "Jan’30"
    assert ctx["production"]["HM"]["SAIL"]["act_m"] is None
    assert any("No production" in w for w in ctx["warnings"])


def _fake_period_report(missing):
    """build_period_report stand-in: every KPI/scope/period is 100 except the
    (scope, kpi name, period label) triples in `missing`."""
    def fake(scopes, params, periods):
        return {"periods": [p["label"] for p in periods],
                "sections": [{"parameter": name, "unit": "", "rows": [
                    {"plant": sc, "values": {p["label"]: {"display": "" if (sc, name, p["label"]) in missing else "100"}
                                             for p in periods}} for sc in scopes]} for name in params]}
    return fake


def test_co2_lag_uses_previous_month(monkeypatch):
    co2 = dict((k, nm) for k, nm, _ in psr.KPIS)["co2"]
    monkeypatch.setattr(psr.tp, "build_period_report",
                        _fake_period_report({("SAIL", co2, "2026-09"), ("SAIL", co2, "ytd:2026-09")}))
    monkeypatch.setattr(psr.tp, "_build_major_params", lambda: [])
    monkeypatch.setattr(psr.pt, "compute_sail_targets", lambda fy: {})
    monkeypatch.setattr(psr.pt, "_get_plant_techno_plan_targets", lambda p, m: {})
    warnings = []
    t = psr.build_techno(psr.period_labels("2026-09"), warnings)
    sail = t["SAIL"]["co2"]
    assert sail["month_used"] == "2026-08"
    assert [a for a, _ in sail["trend"]] == ["Apr", "May", "Jun", "Jul", "Aug"]
    assert sail["month"] == 100 and sail["ytd"] == 100
    assert any("CO₂ for Sep’26 not loaded yet" in w and "Aug" in w for w in warnings)
    assert t["SAIL"]["coke"]["month_used"] == "2026-09"
    assert [a for a, _ in t["SAIL"]["coke"]["trend"]][-1] == "Sep"


def test_target_read_errors_become_warnings(monkeypatch):
    def boom(fy):
        raise RuntimeError("techno_plan_fy missing")
    monkeypatch.setattr(psr.pt, "compute_sail_targets", boom)
    monkeypatch.setattr(psr.pt, "_get_plant_techno_plan_targets", lambda p, m: {})
    warnings = []
    out = psr._targets(psr.period_labels("2026-09"), warnings)
    assert out["SAIL"] == bnc.fuel_rate_fallback({})
    assert warnings == ["SAIL techno targets could not be read: techno_plan_fy missing"]
