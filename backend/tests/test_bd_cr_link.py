"""Breakdown -> capital repair link suggestions (bd_cr_link.suggest_cr).

A capital repair is often also logged in the breakdown log (exact
date-times + a remark naming it). The rule only SUGGESTS the link - the
stored breakdown_table.capital_repair_id is what reports use. Fixture rows
are copied from BSP's 2026-27 data (2026-10-05).
"""

import bd_cr_link

CRS = [  # capital_repair_table rows (BSP, 2026-27, with actual dates)
    {"id": 21, "plant": "BSP", "shop": "SMS3", "equipment": "CK-2", "activity": "Capital Repair",
     "actual_start": "2026-08-19", "actual_end": "2026-08-25", "actual_ongoing": 0},
    {"id": 18, "plant": "BSP", "shop": "SMS3", "equipment": "BOF-2", "activity": "BOF Relining",
     "actual_start": "2026-08-19", "actual_end": "2026-08-31", "actual_ongoing": 0},
    {"id": 5, "plant": "BSP", "shop": "SP-3", "equipment": "M/c-1", "activity": "Capital Repair",
     "actual_start": "2026-09-05", "actual_end": "2026-09-13", "actual_ongoing": 0},
    {"id": 17, "plant": "BSP", "shop": "SMS3", "equipment": "BOF-1*", "activity": "BOF Relining",
     "actual_start": "2026-09-06", "actual_end": None, "actual_ongoing": 1},
    {"id": 23, "plant": "BSP", "shop": "Mills", "equipment": "RSM", "activity": "Capital Repair",
     "actual_start": "2026-09-19", "actual_end": None, "actual_ongoing": 1},
    {"id": 22, "plant": "BSP", "shop": "SMS3", "equipment": "CV-1", "activity": "Capital Repair",
     "actual_start": "2026-09-21", "actual_end": "2026-09-28", "actual_ongoing": 0},
    {"id": 6, "plant": "BSP", "shop": "SP-3", "equipment": "M/c-2", "activity": "Capital Repair",
     "actual_start": "2026-09-22", "actual_end": "2026-09-26", "actual_ongoing": 0},
    {"id": 27, "plant": "BSP", "shop": "Mills", "equipment": "BRM", "activity": "Capital Repair",
     "actual_start": "2026-08-09", "actual_end": "2026-08-11", "actual_ongoing": 0},
    {"id": 28, "plant": "BSP", "shop": "Mills", "equipment": "Plate Mill", "activity": "Capital Repair",
     "actual_start": "2026-06-18", "actual_end": "2026-06-24", "actual_ongoing": 0},
]


def bd(id_, start, end, cause, ongoing=0, unit_type="SMS", unit_name="SMS-3", plant="BSP"):
    return {"id": id_, "plant": plant, "unit_type": unit_type, "unit_name": unit_name,
            "start_ts": start, "end_ts": end, "is_ongoing": ongoing, "cause": cause}


TRUE_PAIRS = [
    (bd(13, "2026-08-19 06:15", "2026-08-25 22:00",
        "CK-2 under CR wef 06:15 Hrs(19.08.2026)/2200 hrs 25.08.26 (Plan: 8 days)"), 21),
    (bd(86, "2026-09-05 02:30", "2026-09-13 13:49",
        "SP3(MC1): M/c-1 under CR wef 02:30\nHrs(5.9.2026)/13.09.26 (Plan: 6 days)",
        unit_type="SINTER", unit_name="Shop"), 5),
    (bd(135, "2026-09-19 04:00", None,
        "Capital repair for 10 days wef 04:00 Hrs(19.09.2026)/contd....RHF#3", ongoing=1,
        unit_type="MILL", unit_name="RSM"), 23),
    (bd(137, "2026-09-21 10:00", "2026-09-28 22:00",
        "CV1 under Capital repair w.e.f.10:00 Hrs.(21.09.2026)-22:00 hrs. (28.09.26) (Plan : 7 days)"), 22),
    (bd(138, "2026-09-22 12:00", "2026-09-26 16:50",
        "SP-3 M/c-2 Taken under Planned Repair in view of  low demand of sinter-12:00 Hrs (22.09.26)",
        unit_type="SINTER", unit_name="Shop"), 6),
]


def test_finds_each_true_pair():
    for row, cr_id in TRUE_PAIRS:
        got = bd_cr_link.suggest_cr(row, CRS)
        assert got is not None and got["id"] == cr_id, (row["id"], got and got["id"])


def test_same_day_other_equipment_not_confused():
    # BD #13 (CK-2) starts the same day as CR #18 (BOF-2 relining): must pick CK-2.
    assert bd_cr_link.suggest_cr(TRUE_PAIRS[0][0], CRS)["id"] == 21


def test_planned_shutdowns_without_a_cr_do_not_match():
    plate = bd(99, "2026-09-09 15:30", "2026-09-14 21:55",
               "Planned: RHF# 3- Skid repair job for 5 days wef 15:30 Hrs (09.09.2026)",
               unit_type="MILL", unit_name="Plate Mill")
    wrm = bd(18, "2026-08-10 19:00", "2026-08-12 16:00",
             "Planned Repair & c/over from plain to TMT 10/10/8 - 07:00 Hrs/16:00 hrs (12.08.26)",
             unit_type="MILL", unit_name="WRM")
    assert bd_cr_link.suggest_cr(plate, CRS) is None
    assert bd_cr_link.suggest_cr(wrm, CRS) is None


def test_ordinary_breakdown_does_not_match():
    tuyere = bd(5, "2026-08-05 07:15", "2026-08-06 06:50", "SSD for BLT chute Inspection, Tuyere change",
                unit_type="BF", unit_name="BF-8")
    assert bd_cr_link.suggest_cr(tuyere, CRS) is None


def test_other_plant_never_matches():
    row, _ = TRUE_PAIRS[0]
    assert bd_cr_link.suggest_cr({**row, "plant": "DSP"}, CRS) is None


def test_api_rejects_link_to_another_plants_capital_repair():
    # Live DB: a link is only valid to the same plant's capital repair.
    import pytest
    from fastapi import HTTPException
    import api_breakdown
    import db
    conn = db.connect()
    try:
        row = conn.execute("SELECT id, plant FROM capital_repair_table ORDER BY id LIMIT 1").fetchone()
    finally:
        conn.close()
    if row is None:
        pytest.skip("no capital repair rows")
    cr_id, plant = row
    api_breakdown._validate_cr_link(plant, cr_id)                    # same plant: fine
    api_breakdown._validate_cr_link(plant, None)                     # no link: fine
    other = next(p for p in ("BSP", "DSP", "RSP", "BSL", "ISP") if p != plant)
    with pytest.raises(HTTPException):
        api_breakdown._validate_cr_link(other, cr_id)
    with pytest.raises(HTTPException):
        api_breakdown._validate_cr_link(plant, 10 ** 9)              # no such CR
