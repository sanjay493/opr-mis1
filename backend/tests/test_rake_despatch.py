"""Rake despatch (Despatch Summary Report): the PDF extractor against the
Oct'26 sample, the insight functions on small hand-made figures, and the
repo save / report build end to end in a throwaway database."""
import pytest

from conftest import find_sample

SAMPLE = "Miscellaneous/Despatch Summary Report 2026-10.pdf"


@pytest.fixture(scope="module")
def extracted():
    path = find_sample(SAMPLE)
    if not path:
        pytest.skip(f"sample not found: {SAMPLE}")
    from excel_extractors.pdf_extractor_rake_despatch import extract
    return extract(path)


# ── extractor ────────────────────────────────────────────────────────────────

def test_month_and_fy(extracted):
    assert (extracted["as_on"], extracted["report_month"], extracted["fy"]) == ("2026-11-01", "2026-10", "2026-27")


def test_page1_position(extracted):
    bsp = extracted["position"]["BSP"]
    assert (bsp["plan_avg_day"], bsp["cumm"], bsp["avg_day"], bsp["diff_plan"]) == (7, 198, 6.39, -0.61)
    # BSP's DMT sub-figures, printed under the main ones
    assert (bsp["empties_received_dmt"], bsp["made_over_dmt"], bsp["cumm_dmt"], bsp["empty_forecast_dmt"]) == (3, 3, 107, 4)
    rsp = extracted["position"]["RSP"]
    assert (rsp["made_over"], rsp["made_over_after_00"], rsp["under_loading"], rsp["empty_forecast"]) == (7, 1, 3, 3)
    assert (rsp["slag_cumm"], rsp["coke_on_date"]) == (23, 1)
    # BSL prints no sinter cells
    assert "sinter_cumm" not in extracted["position"]["BSL"]
    assert set(extracted["position"]) == {"BSP", "DSP", "RSP", "BSL", "ISP"}


def test_slab(extracted):
    assert extracted["slab"] == [{"from": "BSP", "to": "RSP", "rakes": 0, "qty_mt": 0.0},
                                 {"from": "BSL", "to": "RSP", "rakes": 3, "qty_mt": 7548.6}]
    assert extracted["slab_note"] == "A. no BRN rake under loading at BSL for RSP"


def test_wagon_types(extracted):
    types = extracted["types"]
    assert sorted(types) == [f"2026-{m:02d}" for m in range(4, 11)]
    assert types["2026-10"]["BSP"] == {"BOST": 19, "BRN": 3, "FOULAD": 62, "LRN": 3, "DMT": 107, "BOXN": 0, "BOSM": 4}
    assert types["2026-04"]["RSP"]["CONCOR"] == 46       # printed as CONCORD
    assert sum(types["2026-10"]["BSL"].values()) == 108


def test_history(extracted):
    h = extracted["history"]
    assert len(h) == 79 and min(h) == "2020-04" and max(h) == "2026-10"
    assert h["2025-10"] == {"BSP": 206, "DSP": 42, "RSP": 108, "BSL": 118, "ISP": 62}
    assert h["2020-04"]["BSP"] == 85


def test_export(extracted):
    rows = {(e["destination"], e["plant"]): e for e in extracted["export"]}
    assert len(extracted["export"]) == 45
    assert rows[("RAXAUL (RXL)", "BSL")]["prog"] == 2.0 and rows[("RAXAUL (RXL)", "BSL")]["actual"] == 2.0
    assert rows[("HALDIA (HDCG)", "BSP")]["group"] == "PORT"
    assert sum(e["actual"] for e in extracted["export"]) == 10.0


def test_checks_report_the_pdfs_own_inconsistencies(extracted):
    checks = extracted["checks"]
    assert "SAIL 2026-05: page 2 shows 489 rakes but page 5 shows 535." in checks
    assert "Page 5: ISP 2026-27 CUMM is printed as 399 but its months add up to 456." in checks
    assert not any(c.startswith("Page 1") for c in checks)


def test_not_a_despatch_report(tmp_path):
    from excel_extractors.pdf_extractor_rake_despatch import extract
    pdf = find_sample("Miscellaneous/Average Plant Detention Report for the period_(01-08-2026 to 31-08-2026.pdf")
    if not pdf:
        pytest.skip("detention sample not found")
    with pytest.raises(ValueError, match="Not a Despatch Summary Report"):
        extract(pdf)


# ── insights (pure) ──────────────────────────────────────────────────────────

def _totals():
    import rake_despatch_report as r
    hist = []
    for fy in (2024, 2025):
        for i, m in enumerate(r.fy_months(fy)):
            for p, base in (("BSP", 200), ("DSP", 50), ("RSP", 100), ("BSL", 120), ("ISP", 60)):
                hist.append({"report_month": m, "plant_code": p, "rakes": base + (fy - 2024) * 5 + i})
    types = []
    for m in r.fy_months(2026)[:7]:
        for p, (a, b) in (("BSP", (150, 50)), ("DSP", (30, 15)), ("RSP", (80, 30)), ("BSL", (90, 20)), ("ISP", (50, 10))):
            types += [{"report_month": m, "plant_code": p, "wagon_type": "BOST", "rakes": a},
                      {"report_month": m, "plant_code": p, "wagon_type": "BOSM", "rakes": b + (m >= "2026-10") * 10}]
    return types, r.monthly_totals(types, hist)


POS = {"BSP": {"plan_avg_day": 7.0}, "DSP": {"plan_avg_day": 1.5}, "RSP": {"plan_avg_day": 4.0},
       "BSL": {"plan_avg_day": 3.5}, "ISP": {"plan_avg_day": 2.0}}


def test_monthly_totals_prefer_wagon_types():
    import rake_despatch_report as r
    t = r.monthly_totals([{"report_month": "2026-05", "plant_code": "DSP", "wagon_type": "BOST", "rakes": 38}],
                         [{"report_month": "2026-05", "plant_code": "DSP", "rakes": 47},
                          {"report_month": "2026-05", "plant_code": "BSP", "rakes": 200}])
    assert t["2026-05"] == {"DSP": 38, "BSP": 200, "SAIL": 238}


def test_headline_and_ranking():
    import rake_despatch_report as r
    _types, totals = _totals()
    h = r.headline("2026-10", totals, POS, {})
    assert h["month_actual"] == 210 + 55 + 120 + 120 + 70           # 575 incl. +10 BOSM each
    assert h["month_plan"] == round(18.0 * 31, 1)
    assert h["month_attainment"] == round(100 * 575 / 558, 1)
    assert h["ly_month_actual"] == sum(b + 5 + 6 for b in (200, 50, 100, 120, 60))
    assert h["fytd_plan"] is None                                     # earlier months not uploaded
    rank = r.ranking("2026-10", totals, POS)
    assert rank[-1]["plant"] == "SAIL"
    atts = [x["attainment"] for x in rank[:-1]]
    assert atts == sorted(atts)
    dsp = next(x for x in rank if x["plant"] == "DSP")
    assert dsp["status"] == "ok" and dsp["attainment"] == round(100 * 55 / 46.5, 1)


def test_wagon_mix_falls_back_to_h1_vs_since():
    import rake_despatch_report as r
    types, _t = _totals()
    mix = r.wagon_mix("2026-10", types)
    assert mix["basis"] == "h1_vs_since"
    sail = next(p for p in mix["plants"] if p["plant"] == "SAIL")
    bosm = next(t for t in sail["types"] if t["type"] == "BOSM")
    assert bosm["shift_pp"] > 0 and sail["biggest_shift"]["type"] in ("BOSM", "BOST")


def test_records_and_run_rate():
    import rake_despatch_report as r
    _types, totals = _totals()
    rec = {x["plant"]: x for x in r.records("2026-10", totals)}
    # BSP Oct: 210 (2026), 211 (2025), 206 (2024)
    assert rec["BSP"]["same_month_rank"] == 2 and rec["BSP"]["same_month_count"] == 3
    assert rec["DSP"]["same_month_rank"] == 3                       # 55 vs 61 (2025), 56 (2024)
    assert rec["BSP"]["best_fy"]["fy"] == "2025-26"
    rate = {x["plant"]: x for x in r.run_rate("2026-10", totals, POS)}
    sail = rate["SAIL"]
    assert sail["remaining_days"] == 151
    assert sail["required_avg_day_ly"] == round((sail["ly_total"] - sail["fytd_actual"]) / 151, 2)


def test_export_watch_totals():
    import rake_despatch_report as r
    rows = [{"destination": "A", "plant_code": "BSP", "dest_group": "NEPAL", "sort_order": 1, "prog": 2.0, "actual": 1.0},
            {"destination": "A", "plant_code": "DSP", "dest_group": "NEPAL", "sort_order": 1, "prog": 0.0, "actual": 2.0},
            {"destination": "P", "plant_code": "BSP", "dest_group": "PORT", "sort_order": 2, "prog": 1.0, "actual": 0.0}]
    out = {x["destination"]: x for x in r.export_watch(rows)}
    assert (out["A"]["prog"], out["A"]["actual"], out["A"]["flag"]) == (2.0, 3.0, "excess")
    assert out["TOTAL PORT"]["flag"] == "shortfall"
    assert (out["GRAND TOTAL"]["prog"], out["GRAND TOTAL"]["actual"]) == (3.0, 3.0)


# ── save + report, end to end ────────────────────────────────────────────────

def test_save_and_build_report(mysql_db, extracted):
    import rake_despatch_report
    from repo import conn as rc
    from repo import rake as rrake

    def n():
        with rc.cursor() as cur:
            cur.execute("SELECT n FROM data_version WHERE id = 1")
            return cur.fetchone()[0]

    assert rake_despatch_report.build_report("2026-10")["available"] is False
    n0 = n()
    saved = rrake.save_rake_despatch(extracted, "Dispatch_report.pdf", "a@sail.in")
    assert n() > n0
    assert saved["report_month"] == "2026-10" and len(saved["history_months"]) == 79
    assert [m["report_month"] for m in rrake.rake_despatch_months()] == ["2026-10"]

    rep = rake_despatch_report.build_report("2026-10")
    assert rep["available"] and rep["fy"] == "2026-27"
    h = rep["headline"]
    assert h["month_actual"] == 533 and h["ly_month_actual"] == 536
    assert h["month_plan"] == round(19.48 * 31, 1)
    assert h["fytd_actual"] == 3739                    # page 2 (May 489), not page 5 (535)
    assert rep["source"]["position"]["SAIL"]["cumm"] == 533
    assert len(rep["key_points"]) >= 3
    assert [r["plant"] for r in rep["ranking"]][-1] == "SAIL"
    assert rep["export"][-1]["destination"] == "GRAND TOTAL" and rep["export"][-1]["actual"] == 10.0
    assert rep["trend"]["SAIL"][1]["total"] == 6579    # FY 2025-26 from page 5

    # re-saving the same file changes nothing; a revised month replaces its wagon types
    extracted2 = {**extracted, "types": {**extracted["types"], "2026-05": {"DSP": {"BOST": 47}}}}
    rrake.save_rake_despatch(extracted2, None, None)
    rows = rrake.rake_despatch_type_rows("2026-05", "2026-05")
    assert [(r["plant_code"], r["wagon_type"], r["rakes"]) for r in rows] == [("DSP", "BOST", 47)]
