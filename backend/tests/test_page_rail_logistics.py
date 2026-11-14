"""page_rail_logistics: regrouping of the Rake Despatch report for the three
MIS PDF pages. Pure helpers only — no database."""
import page_rail_logistics as rl

FY_MONTHS = [f"2026-{m:02d}" for m in range(4, 13)] + [f"2027-{m:02d}" for m in (1, 2, 3)]


def test_commodity_rows_missing_metrics():
    rows = rl.commodity_rows({"BSP": {"slag_cumm": 40.0, "slag_on_date": 1.0}}, [], "2026-10")
    bsp = next(r for r in rows if r["plant"] == "BSP")
    assert bsp["slag"] == {"plan_avg_day": None, "avg_day": None, "cumm": 40.0}
    assert [r["plant"] for r in rows] == ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]
    assert next(r for r in rows if r["plant"] == "DSP")["coke"]["cumm"] is None


def test_commodity_rows_slab_from_despatch_rows():
    slab = [{"from_plant_code": "BSL", "to_plant_code": "RSP", "rakes": 3, "qty_mt": 7548.6},
            {"from_plant_code": "BSL", "to_plant_code": "ISP", "rakes": 1, "qty_mt": 2500.0},
            {"from_plant_code": "BSP", "to_plant_code": "RSP", "rakes": 0, "qty_mt": 0.0}]
    rows = {r["plant"]: r for r in rl.commodity_rows({}, slab, "2026-10")}
    assert rows["BSL"]["slab"] == {"plan_avg_day": None, "avg_day": round(4 / 31, 2), "cumm": 4}
    assert rows["BSP"]["slab"] == {"plan_avg_day": None, "avg_day": 0.0, "cumm": 0}
    assert rows["DSP"]["slab"] == {"plan_avg_day": None, "avg_day": None, "cumm": None}
    assert rows["SAIL"]["slab"]["cumm"] == 4


def test_mix_matrix_order_and_shares():
    mix = {"label": "Oct'26 vs H1", "plants": [
        {"plant": "BSP", "types": [{"type": "BOXN", "fytd_share": 60.0, "shift_pp": 1.0, "fytd_rakes": 6}]},
        {"plant": "SAIL", "types": [
            {"type": "BRN", "fytd_share": 55.0, "shift_pp": -2.0, "fytd_rakes": 11},
            {"type": "BOXN", "fytd_share": 45.0, "shift_pp": 2.0, "fytd_rakes": 9}]}]}
    m = rl.mix_matrix(mix)
    assert m["label"] == "Oct'26 vs H1" and m["plants"] == rl.PLANTS
    assert [r["type"] for r in m["rows"]] == ["BRN", "BOXN"]
    assert m["rows"][1]["shares"]["BSP"] == 60.0 and m["rows"][0]["shares"]["BSP"] is None
    assert m["rows"][1]["sail_share"] == 45.0 and m["rows"][1]["sail_shift"] == 2.0


def test_wagon_type_blocks_sparse():
    types = {"BSP": {"BOXN": {"2026-04": 5, "2026-05": 7}, "DMT": {"2026-05": 1}},
             "DSP": {"BOXN": {"2026-04": 2}}}
    blocks = rl.wagon_type_blocks(types, FY_MONTHS)
    assert [b["plant"] for b in blocks] == ["BSP", "DSP", "SAIL"]
    bsp = blocks[0]
    assert [r["type"] for r in bsp["rows"]] == ["BOXN", "DMT"]
    assert bsp["rows"][1]["months"][:3] == [None, 1, None] and bsp["rows"][1]["fytd"] == 1
    assert bsp["total"]["months"][:3] == [5, 8, None] and bsp["total"]["fytd"] == 13
    sail_boxn = next(r for r in blocks[-1]["rows"] if r["type"] == "BOXN")
    assert sail_boxn["months"][0] == 7 and sail_boxn["fytd"] == 14


def test_trend_rows_flatten():
    t = {p: [{"fy": "2026-27", "months": [1] + [None] * 11, "total": 1},
             {"fy": "2025-26", "months": [2] * 12, "total": 24}] for p in rl.ALL}
    rows = rl.trend_rows(t)
    assert len(rows) == 12 and rows[0]["first_of_plant"] and not rows[1]["first_of_plant"]
    assert rows[2]["plant"] == "DSP" and rows[2]["first_of_plant"]
    assert rows[1]["fy"] == "2025-26" and rows[1]["total"] == 24


def test_export_rows_empty():
    zero = [{"destination": "GRAND TOTAL", "prog": 0, "actual": 0, "is_total": True}]
    assert rl.export_rows(zero) == []
    assert rl.export_rows([]) == []
    rows = [{"destination": "X", "prog": 2, "actual": 1}]
    assert rl.export_rows(rows) == rows


def test_unavailable_placeholder(monkeypatch):
    monkeypatch.setattr(rl.rdr, "build_report", lambda m: {"report_month": m, "available": False, "months": []})
    for part in ("summary", "history", "wagon"):
        p = rl.generate_rail_logistics("2026-10", part)
        assert p["type"] == f"rail_logistics_{part}" and p["available"] is False
        assert p["placeholder"] == "Despatch Summary Report for Oct'26 not uploaded"
        assert p["title"].startswith("Rail Logistics – Rake Despatch")


def test_ranking_tint(monkeypatch):
    report = {"report_month": "2026-10", "available": True, "fy": "2026-27", "fy_months": FY_MONTHS,
              "headline": {}, "key_points": [], "run_rate": [],
              "ranking": [{"plant": "BSP", "attainment": 96.0}, {"plant": "SAIL", "attainment": None}],
              "source": {"position": {}, "slab": [], "slab_note": None, "types": {}}}
    monkeypatch.setattr(rl.rdr, "build_report", lambda m: report)
    p = rl.generate_rail_logistics("2026-10", "summary")
    assert [r["tint"] for r in p["ranking"]] == ["watch", "na"]
    assert p["subtitle"] == "Oct'26 · FY 2026-27" and p["placeholder"] is None


def test_page_ids():
    assert rl.PAGE_IDS == {40.1: "summary", 40.2: "history", 40.3: "wagon"}


def test_fmt():
    assert rl.fmt(None) == "–" and rl.fmt(12.345, 2) == "12.35" and rl.fmt(7) == "7"


def test_records_rows_labels():
    rec = [{"plant": "BSP", "actual": 120, "same_month_rank": 2, "same_month_count": 7,
            "same_month_best": ("2025-10", 130), "same_month_worst": ["2020-10", 90],
            "best_month": {"month": "2024-03", "rakes": 150}, "is_best_month_ever": False,
            "best_fy": {"fy": "2024-25", "rakes": 1500}},
           {"plant": "DSP", "actual": None, "same_month_rank": None, "same_month_count": 0,
            "same_month_best": (None, None), "same_month_worst": (None, None),
            "best_month": {"month": None, "rakes": None}, "is_best_month_ever": False,
            "best_fy": {"fy": None, "rakes": None}}]
    rows = rl.records_rows(rec)
    assert rows[0]["rank"] == "2 of 7"
    assert rows[0]["same_best"] == "130 (Oct'25)" and rows[0]["same_worst"] == "90 (Oct'20)"
    assert rows[0]["best_month"] == "150 (Mar'24)" and rows[0]["best_fy"] == "1500 (2024-25)"
    assert rows[1] == {"plant": "DSP", "actual": None, "rank": "–", "same_best": "–", "same_worst": "–",
                       "best_month": "–", "best_fy": "–", "is_best_month_ever": False}
