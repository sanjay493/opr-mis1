"""page_rail_logistics: regrouping of the Rake Despatch report for its three
MIS PDF pages (40.1-40.3; 40.05 is tested in test_rail_loading.py). Pure helpers only — no database."""
import page_rail_logistics as rl

FY_MONTHS = [f"2026-{m:02d}" for m in range(4, 13)] + [f"2027-{m:02d}" for m in (1, 2, 3)]


def test_mix_rows_per_plant():
    boxn = {"type": "BOXN", "fytd_share": 45.0, "shift_pp": 2.0, "fytd_rakes": 9}
    mix = {"label": "Oct'26 vs H1", "plants": [
        {"plant": "BSP", "fytd_total": 6, "biggest_shift": {"type": "BOXN"}, "types": [
            {"type": "BOXN", "fytd_share": 100.0, "shift_pp": 1.0, "fytd_rakes": 6},
            {"type": "LRN", "fytd_share": 0.0, "shift_pp": 0.0, "fytd_rakes": 0}]},
        {"plant": "SAIL", "fytd_total": 20, "biggest_shift": boxn, "types": [
            {"type": "BRN", "fytd_share": 55.0, "shift_pp": 0.04, "fytd_rakes": 11}, boxn]}]}
    m = rl.mix_rows(mix)
    assert m["label"] == "Oct'26 vs H1"
    assert [r["plant"] for r in m["rows"]] == ["BSP", "SAIL"]
    assert m["rows"][0]["fytd_total"] == 6
    assert m["rows"][0]["types"] == [{"type": "BOXN", "share": 100.0, "shift": 1.0, "biggest": True}]
    assert m["rows"][1]["types"] == [{"type": "BRN", "share": 55.0, "shift": None, "biggest": False},
                                     {"type": "BOXN", "share": 45.0, "shift": 2.0, "biggest": True}]


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


def test_unavailable_placeholder(monkeypatch):
    monkeypatch.setattr(rl.rdr, "build_report", lambda m: {"report_month": m, "available": False, "months": []})
    for part in ("summary", "history", "wagon"):
        p = rl.generate_rail_logistics("2026-10", part)
        assert p["type"] == f"rail_logistics_{part}" and p["available"] is False
        assert p["placeholder"] == "Despatch Summary Report for Oct'26 not uploaded"
        assert p["title"].startswith("Rail Logistics – Steel Rake Despatch from Plant: ")


def test_ranking_tint(monkeypatch):
    report = {"report_month": "2026-10", "available": True, "fy": "2026-27", "fy_months": FY_MONTHS,
              "headline": {}, "key_points": [], "run_rate": [],
              "ranking": [{"plant": "BSP", "attainment": 96.0}, {"plant": "SAIL", "attainment": None}],
              "source": {"position": {}, "slab": [], "slab_note": None, "types": {}}}
    monkeypatch.setattr(rl.rdr, "build_report", lambda m: report)
    p = rl.generate_rail_logistics("2026-10", "summary")
    assert [r["tint"] for r in p["ranking"]] == ["watch", "na"]
    assert "commodity" not in p and p["title"] == "Rail Logistics – Steel Rake Despatch from Plant: Summary"
    assert p["subtitle"] == "Oct'26 · FY 2026-27" and p["placeholder"] is None


def test_page_ids():
    assert rl.PAGE_IDS == {40.05: "loading", 40.07: "mines", 40.1: "summary", 40.2: "history", 40.3: "wagon"}
    assert list(rl.PAGE_IDS) == sorted(rl.PAGE_IDS)                      # print order


def test_fmt():
    assert rl.fmt(None) == "–" and rl.fmt(12.345, 2) == "12.35" and rl.fmt(7) == "7"


def _mines_report(month):
    import iron_ore_rakes as ior
    counts = [{"report_month": m, "mine_code": mine, "wagon_code": w, "rakes": n} for m, mine, w, n in (
        ("2026-10", "BOL", "BX", 5), ("2026-10", "KRB", "BS", 3), ("2026-10", "DAL", "BS", 4),
        ("2025-10", "BOL", "BX", 10), ("2025-10", "DAL", "PR", 2))]
    return counts, ior


def test_mines_page(monkeypatch):
    counts, ior = _mines_report("2026-10")
    monkeypatch.setattr(ior.rrake, "iron_ore_rake_counts", lambda a, b: [c for c in counts if a <= c["report_month"] <= b])
    p = rl.generate_rail_logistics("2026-10", "mines")
    assert (p["type"], p["title"]) == ("rail_logistics_mines", "Rail Logistics – Iron Ore Rake Loading from Mines")
    assert p["available"] and p["placeholder"] is None and p["subtitle"] == "Oct'26 · FY 2026-27"
    assert p["fy"] == "2026-27" and p["month_labels"][0] == "Apr" and len(p["month_labels"]) == 12
    assert p["key_points"][0].startswith("Iron ore loading from mines in Oct'26: EGOM 8 rakes")
    # trend: EGOM, CGOM, Total x 7 FYs, flat, current FY first
    assert len(p["trend"]) == 21 and [r["plant"] for r in p["trend"][::7]] == ["EGOM", "CGOM", "Total"]
    assert p["trend"][0]["first_of_plant"] and p["trend"][0]["months"][6] == 8 and p["trend"][15]["months"][6] == 12
    assert [r["plant"] for r in p["mix"]["rows"]] == ["EGOM", "CGOM", "Total"]
    assert [b["plant"] for b in p["blocks"]] == ["EGOM", "CGOM", "Total"]
    total = p["blocks"][-1]
    assert {r["type"]: r["fytd"] for r in total["rows"]} == {"BOBSNM1": 7, "BOXN": 5} and total["total"]["fytd"] == 12


def test_mines_page_placeholder(monkeypatch):
    _counts, ior = _mines_report("2026-10")
    monkeypatch.setattr(ior.rrake, "iron_ore_rake_counts", lambda a, b: [])
    p = rl.generate_rail_logistics("2026-10", "mines")
    assert p["available"] is False and p["subtitle"] == "Oct'26"
    assert p["placeholder"] == "Iron ore rake file not uploaded for FY 2026-27"


def test_plant_helpers_keep_their_defaults():
    assert [b["plant"] for b in rl.wagon_type_blocks({"BSP": {"BOXN": {"2026-04": 5}}}, FY_MONTHS)] == ["BSP", "SAIL"]
