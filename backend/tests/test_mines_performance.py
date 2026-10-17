"""mines_performance: period arithmetic, values, and (Task 2/3) the
block/row generator against a temp SQLite DB."""
import mines_performance as mp


def test_periods_mid_fy():
    P = mp.periods("2026-09")
    assert P["fy"][0] == "2026-04" and P["fy"][-1] == "2027-03" and len(P["fy"]) == 12
    assert P["ytd"] == ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    assert P["cply"] == "2025-09"
    assert P["cply_ytd"] == ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]


def test_periods_jan_crosses_calendar_year():
    P = mp.periods("2027-01")
    assert P["fy"][0] == "2026-04"
    assert P["ytd"][0] == "2026-04" and P["ytd"][-1] == "2027-01" and len(P["ytd"]) == 10
    assert P["cply"] == "2026-01"
    assert P["cply_ytd"][0] == "2025-04" and P["cply_ytd"][-1] == "2026-01"


def test_periods_april():
    P = mp.periods("2026-04")
    assert P["ytd"] == ["2026-04"] and P["cply_ytd"] == ["2025-04"]


def test_combine_is_blank_aware():
    s = mp.combine([{"2026-09": (10.0, None)}, {"2026-09": (None, None), "2026-08": (None, 5.0)}])
    assert s == {"2026-09": (10.0, None), "2026-08": (None, 5.0)}


def test_values_all_columns():
    P = mp.periods("2026-09")
    s = {"2026-04": (90.0, 100.0), "2026-09": (100.0, 110.0), "2027-03": (None, 50.0),
         "2025-09": (80.0, None), "2025-04": (70.0, None)}
    v = mp.values(s, P)
    assert v[0] == 260.0                      # FY plan: 100 + 110 + 50
    assert v[1:3] == [110.0, 100.0]           # month plan, actual
    assert round(v[3], 4) == round(100 / 110 * 100, 4)
    assert v[4] == 80.0 and v[5] == 25.0      # CPLY, %Gr
    assert v[6:8] == [210.0, 190.0]           # Apr-to-month plan, actual
    assert v[9] == 150.0                      # CPLY Apr-Sep'25
    assert round(v[10], 4) == round((190 - 150) / 150 * 100, 4)


def test_values_percent_blank_on_zero_or_missing():
    P = mp.periods("2026-09")
    v = mp.values({"2026-09": (20.0, 0.0)}, P)
    assert v[3] is None and v[5] is None and v[8] is None and v[10] is None
    assert mp.values({}, P) == [None] * 11


def test_labels():
    L = mp.labels("2026-09")
    assert L == {"title": "Mines Production Performance :Sep'26 and Apr-Sep'26", "fy": "26-27",
                 "month": "Sep'26", "cply": "Sep'25", "ytd": "Apr-Sep'26", "ytd_cply": "Apr-Sep'25"}


import sqlite3
from decimal import Decimal

import pytest

_SCHEMA = [
    "CREATE TABLE mine_groups_master (group_code TEXT, group_name TEXT, sort_order INTEGER)",
    "CREATE TABLE mines_master (mine_code TEXT, mine_name TEXT, group_code TEXT, is_active INTEGER, sort_order INTEGER)",
    "CREATE TABLE mine_materials_master (material_code TEXT, material_name TEXT, material_category TEXT, "
    "has_production INTEGER, counts_in_total_production INTEGER, sort_order INTEGER)",
    "CREATE TABLE mines_production_monthly (report_month TEXT, mine_code TEXT, material_code TEXT, qty_actual REAL, qty_plan REAL)",
    "CREATE TABLE mines_despatch_actual_monthly (report_month TEXT, mine_code TEXT, material_code TEXT, "
    "transport_mode TEXT, end_use_code TEXT, qty_actual REAL)",
    "CREATE TABLE mines_despatch_plan_monthly (report_month TEXT, mine_code TEXT, material_code TEXT, end_use_code TEXT, qty_plan REAL)",
    "CREATE TABLE mines_booked_qty_actual_monthly (report_month TEXT, mine_code TEXT, material_code TEXT, transport_mode TEXT, qty_actual REAL)",
    "CREATE TABLE mines_booked_qty_plan_monthly (report_month TEXT, mine_code TEXT, material_code TEXT, qty_plan REAL)",
    "CREATE TABLE sail_mines_monthly (report_month TEXT, section TEXT, item TEXT, month_actual REAL, month_plan REAL)",
]

_ROWS = {
    "mine_groups_master": [("JG", "J Group", 1), ("OG", "O Group", 2)],
    "mines_master": [("A", "Alpha", "JG", 1, 1), ("B", "Beta", "JG", 1, 2),
                     ("C", "Gamma", "OG", 1, 3), ("D", "Delta", "OG", 0, 4)],
    "mine_materials_master": [("LUMP", "Lump", "FRESH", 1, 1, 1), ("FINES", "Fines", "FRESH", 1, 1, 2),
                              ("DUMP_FINES", "Dump Fines", "LEGACY", 0, 1, 3), ("PELLETS", "Pellets", "LEGACY", 0, 1, 4),
                              ("TAILINGS", "Tailings", "LEGACY", 0, 1, 5)],
    "mines_production_monthly": [
        ("2026-09", "A", "LUMP", 100, 110), ("2026-09", "A", "FINES", 50, 40),
        ("2026-04", "A", "LUMP", 90, 100), ("2025-09", "A", "LUMP", 80, None),
        ("2026-09", "B", "LUMP", 10, 10), ("2026-09", "C", "FINES", 20, 0),
        ("2026-09", "D", "LUMP", 999, 999),          # inactive mine: never counted
    ],
    "mines_despatch_actual_monthly": [
        ("2026-09", "A", "LUMP", "RAIL", "CAPTIVE", 60), ("2026-09", "A", "LUMP", "ROAD", "CAPTIVE", 5),
        ("2026-09", "A", "FINES", "RAIL", "SALES", 30),
        ("2026-09", "A", "PELLETS", "ROAD", "SALES", 7), ("2026-09", "A", "PELLETS", "RAIL", "CAPTIVE", 3),
        ("2026-09", "A", "DUMP_FINES", "RAIL", "PELLET_CONV", 4), ("2026-09", "A", "DUMP_FINES", "RAIL", "SALES", 2),
        ("2026-09", "A", "TAILINGS", "RAIL", "CAPTIVE", 1), ("2026-09", "A", "TAILINGS", "RAIL", "SALES", 6),
        ("2025-09", "C", "TAILINGS", "RAIL", "SALES", 5),   # C: last year only
    ],
    "mines_despatch_plan_monthly": [("2026-09", "A", "LUMP", "CAPTIVE", 70)],
    "mines_booked_qty_actual_monthly": [("2026-09", "A", "FINES", "RAIL", 12), ("2026-09", "A", "FINES", "ROAD", 3)],
    "mines_booked_qty_plan_monthly": [("2026-09", "A", "FINES", 20)],
    "sail_mines_monthly": [],
}


@pytest.fixture
def gen(tmp_path, monkeypatch):
    dbfile = tmp_path / "mines.db"
    c = sqlite3.connect(dbfile)
    for sql in _SCHEMA:
        c.execute(sql)
    for table, rows in _ROWS.items():
        for r in rows:
            c.execute(f"INSERT INTO {table} VALUES ({','.join('?' * len(r))})", r)
    c.commit()
    c.close()
    monkeypatch.setattr(mp.db, "connect", lambda: sqlite3.connect(dbfile))
    return dbfile


def _block(data, name):
    return next(b for b in data["blocks"] if b["name"] == name)


def _rows(block):
    return [(r["kind"], r["label"]) for r in block["rows"]]


def _val(block, label, i=2):
    return next(r for r in block["rows"] if r["label"] == label)["values"][i]


def test_f_converts_decimal():
    assert mp._f(Decimal("1.5")) == 1.5 and mp._f(None) is None


def test_block_order_and_kinds(gen):
    d = mp.generate("2026-09")
    assert [(b["name"], b["kind"]) for b in d["blocks"]] == [
        ("Alpha", "mine"), ("Beta", "mine"), ("J Group", "group"),
        ("Gamma", "mine"), ("O Group", "group"), ("SAIL", "sail")]
    assert _block(d, "SAIL")["note"] == mp.SAIL_NOTE
    assert d["pct_idx"] == [3, 5, 8, 10] and d["labels"]["month"] == "Sep'26"


def test_mine_rows_structure(gen):
    a = _block(mp.generate("2026-09"), "Alpha")
    assert _rows(a) == [
        ("heading", "I/ORE FRESH PRODUCTION"), ("item", "Lump"), ("item", "Fines"),
        ("total", "Total Fresh Production"),
        ("heading", "I/ORE DESPATCH"),
        ("subheading", "Captive"), ("item", "Lump"), ("item", "Pellets"), ("item", "Tailings"),
        ("total", "Total Captive"),
        ("subheading", "Conversion Agent"), ("item", "Dump Fines"), ("total", "Total Conversion Agent"),
        ("subheading", "Sales"), ("item", "Fines"), ("item", "Dump Fines"), ("item", "Pellets"),
        ("item", "Tailings"), ("total", "Total Sales"),
        ("total", "Grand Total Despatch"),
        ("heading", "REPORTED PRODUCTION"), ("item", "Fresh Production (Lump+Fines)"),
        ("item", "Pellets Despatch"), ("item", "Dump Fines Despatch"), ("item", "Tailings Despatch"),
        ("total", "Reported Production"),
        ("heading", "BOOKED QUANTITY (SALES)"), ("item", "Fines"), ("total", "Total Booked"),
    ]
    assert all(r["values"] == [None] * 11 for r in a["rows"] if r["kind"] in ("heading", "subheading"))


def test_mine_values(gen):
    a = _block(mp.generate("2026-09"), "Alpha")
    assert _val(a, "Lump", 2) == 100 and _val(a, "Lump", 1) == 110
    assert _val(a, "Lump", 4) == 80 and _val(a, "Lump", 7) == 190 and _val(a, "Lump", 6) == 210
    assert _val(a, "Total Fresh Production") == 150
    assert _val(a, "Total Captive") == 69 and _val(a, "Total Captive", 1) == 70    # 65 + 3 + 1, plan 70
    assert _val(a, "Total Conversion Agent") == 4
    assert _val(a, "Total Sales") == 45                                            # 30 + 2 + 7 + 6
    assert _val(a, "Grand Total Despatch") == 118
    assert _val(a, "Pellets Despatch") == 10                                       # any end use
    assert _val(a, "Dump Fines Despatch") == 2                                     # not PELLET_CONV
    assert _val(a, "Tailings Despatch") == 6                                       # SALES only
    assert _val(a, "Reported Production") == 168                                   # 150 + 10 + 2 + 6
    assert _val(a, "Total Booked") == 15 and _val(a, "Total Booked", 3) == 75


def test_hidden_sections_and_always_shown_rows(gen):
    b = _block(mp.generate("2026-09"), "Beta")
    assert _rows(b) == [
        ("heading", "I/ORE FRESH PRODUCTION"), ("item", "Lump"), ("item", "Fines"),
        ("total", "Total Fresh Production"),
        ("heading", "REPORTED PRODUCTION"), ("item", "Fresh Production (Lump+Fines)"),
        ("total", "Reported Production"),
    ]
    assert _val(b, "Fines") is None


def test_cply_only_row_is_shown(gen):
    c = _block(mp.generate("2026-09"), "Gamma")
    assert ("item", "Tailings") in _rows(c)
    assert _val(c, "Tailings", 4) == 5 and _val(c, "Tailings", 2) is None


def test_plan_zero_gives_blank_percent(gen):
    c = _block(mp.generate("2026-09"), "Gamma")
    assert _val(c, "Fines", 2) == 20 and _val(c, "Fines", 3) is None


def test_group_and_sail_are_sums(gen):
    d = mp.generate("2026-09")
    assert _val(_block(d, "J Group"), "Lump") == 110
    assert _val(_block(d, "J Group"), "Total Fresh Production") == 160
    sail = _block(d, "SAIL")
    assert _val(sail, "Total Fresh Production") == 180          # inactive D excluded
    assert _val(sail, "Grand Total Despatch") == 118
    assert _val(sail, "Reported Production") == 198              # 180 + 10 + 2 + 6


def test_empty_month_has_no_blocks(gen):
    assert mp.generate("2030-05")["blocks"] == []


_SAIL_ROWS = [
    ("2026-09", "coal_prod", "Raw Coking Coal", 100, 120), ("2026-09", "coal_prod", "Thermal Coal", 50, 0),
    ("2026-09", "washery", "Input Raw Coal", 200, 250), ("2026-09", "washery", "Clean Coal", 90, 100),
    ("2025-09", "washery", "Input Raw Coal", 100, None), ("2025-09", "washery", "Clean Coal", 40, None),
    ("2026-09", "coal_despatch", "Clean Coal", 80, 85), ("2026-09", "coal_despatch", "Thermal", 30, 35),
    ("2026-09", "flux_prod", "Limestone", 60, 70), ("2026-09", "flux_prod", "Dolomite", 25, 30),
    ("2026-09", "flux_despatch", "Limestone", 55, 65), ("2026-09", "flux_despatch", "Dolomite", 20, 28),
]


@pytest.fixture
def gen_sail(gen):
    c = sqlite3.connect(gen)
    c.executemany("INSERT INTO sail_mines_monthly VALUES (?,?,?,?,?)", _SAIL_ROWS)
    c.commit()
    c.close()
    return gen


def _sail_tail(d):
    rows = _block(d, "SAIL")["rows"]
    start = next(i for i, r in enumerate(rows) if r["label"] == "COAL MINES PRODUCTION")
    return rows[start:]


def test_coal_flux_structure(gen_sail):
    tail = _sail_tail(mp.generate("2026-09"))
    assert [(r["kind"], r["label"]) for r in tail] == [
        ("heading", "COAL MINES PRODUCTION"), ("item", "Raw Coking Coal"), ("item", "Thermal Coal"), ("total", "Total"),
        ("heading", "WASHERY"), ("item", "Input Raw Coal"), ("item", "Clean Coal"), ("item", "Yield (%)"),
        ("heading", "COAL DESPATCH"), ("item", "Clean Coal"), ("item", "Thermal"), ("total", "Total"),
        ("heading", "FLUX PRODUCTION"), ("item", "Limestone"), ("item", "Dolomite"), ("total", "Total"),
        ("heading", "FLUX DESPATCH"), ("item", "Limestone"), ("item", "Dolomite"), ("total", "Total"),
    ]
    assert all(r["values"] == [None] * 11 for r in tail if r["kind"] == "heading")


def test_coal_total_and_yield(gen_sail):
    tail = _sail_tail(mp.generate("2026-09"))
    coal_total = tail[3]["values"]
    assert coal_total[2] == 150 and coal_total[1] == 120
    y = next(r for r in tail if r["label"] == "Yield (%)")
    assert y["decimals"] == 1
    assert y["values"][2] == 45.0 and y["values"][1] == 40.0          # 90/200, 100/250
    assert y["values"][3] == 112.5                                     # 45 / 40
    assert y["values"][4] == 40.0 and y["values"][5] == 12.5           # CPLY 40/100; (45-40)/40


def test_coal_flux_only_in_sail_block(gen_sail):
    d = mp.generate("2026-09")
    for b in d["blocks"]:
        if b["kind"] != "sail":
            assert "COAL MINES PRODUCTION" not in [r["label"] for r in b["rows"]]
