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
