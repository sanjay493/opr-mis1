"""op_plan_extract: plan-file lines -> proposed OP per production item."""
import io

import openpyxl
import pytest

import op_plan_extract as ox


def _rows(plant, lines, db):
    return {r["item"]: r for r in ox.map_lines(plant, lines, db) if r["selected"]}


def test_bsp_layout_totals_picked_by_app():
    lines = [{"label": lab, "app": a, "op": o} for lab, a, o in [
        ("1 Eq. Oven Pushing(Nos/Day)", 766, 810), ("3 SINTER SP - II", 258, 254), ("SP - III", 588, 588),
        ("4 Hot Metal BF:4-7", 311, 296), ("Total HM", 577, 562),
        ("6 Crude Steel SMS-II", 216, 222), ("SMS-III", 348, 326), ("Total", 564, 548),
        ("7 SMS-II Cast Blooms", 68, 60), ("Total", 216, 222), ("Total finished Rails", 151, 138), ("Total", 137, 126),
        ("Prime RSM", 44, 44)]]
    db = {"Oven Pushing (nos/day)": 766.0, "SP-2": 258.0, "SP-3": 588.4, "BF#1-7": 311.0, "Hot Metal": 577.0,
          "SMS-2": 216.0, "SMS-3": 348.0, "Total Crude Steel": 564.0, "SMS-2 BLOOM": 68.0, "RSMPRIME": 43.8}
    got = _rows("BSP", lines, db)
    assert {k: v["op_value"] for k, v in got.items()} == {
        "Oven Pushing (nos/day)": 810, "SP-2": 254, "SP-3": 588, "BF#1-7": 296, "Hot Metal": 562, "SMS-2": 222,
        "SMS-3": 326, "Total Crude Steel": 548, "SMS-2 BLOOM": 60, "RSMPRIME": 44}
    assert all(v["status"] == "matched" for v in got.values())
    statuses = [r["status"] for r in ox.map_lines("BSP", lines, db)]
    assert statuses.count("duplicate") == 1 and statuses.count("unmatched") == 2   # 2nd SMS-II total; rails / prime totals


def test_rsp_tonnes_scaled_per_line_and_copy():
    lines = [{"label": "Oven Pushing (Nos/day)", "app": 341, "op": 345},
             {"label": "SP- I", "app": 121000, "op": 125000},
             {"label": "- Plates", "app": 85000, "op": 103000}, {"label": "- Plates", "app": 49000, "op": 49000},
             {"label": "Saleable Steel", "app": 359000, "op": 391000}]
    db = {"COB#1-5": 341.0, "SP-1": 121.0, "NPM Plate": 85.0, "OPM Plate": 49.0, "Saleable Steel": 359.0,
          "Finished Steel": 359.0, "Oven Pushing (nos/day)": 502.7}
    got = _rows("RSP", lines, db)
    assert {k: v["op_value"] for k, v in got.items()} == {
        "COB#1-5": 345, "SP-1": 125, "NPM Plate": 103, "OPM Plate": 49, "Saleable Steel": 391, "Finished Steel": 391}


def test_dsp_hindi_labels_and_composites():
    lines = [{"label": "हॉट मेटऱ / HOT METAL", "app": 204, "op": 240},
             {"label": "पबऱेट म ीन-1 / Billet M/C-1", "app": 47.3, "op": 48},
             {"label": "पबऱेट म ीन-2 / Billet M/C-2", "app": 47.3, "op": 48},
             {"label": "i) फिनी ड / Finished", "app": 117.2, "op": 120.5}]
    got = _rows("DSP", lines, {"Hot Metal": 204.0, "Billet Caster": 94.5, "Finished Steel": 117.2})
    assert {k: v["op_value"] for k, v in got.items()} == {"Hot Metal": 240, "Billet Caster": 96, "Finished Steel": 120.5}


def test_far_off_app_is_proposed_but_not_ticked():
    # ISP's figures read against RSP's APP (wrong plant chosen)
    rows = ox.map_lines("RSP", [{"label": "Hot Metal", "app": 257, "op": 265}], {"Hot Metal": 385.0})
    assert rows[0]["item"] == "Hot Metal" and rows[0]["status"] == "check" and rows[0]["selected"] is False


def test_xlsx_header_and_unlabelled_total():
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in [["Plan for October 2026"], ["Item", "APP", None, "Operating Plan"], [None, "Month", "Daily", "Month"],
              ["Hot Metal", 437, 14400, 450], ["   - Slab", 42, 1350, 10], [None, 381, None, 357],
              ["Coke Rate", 419, None, 435]]:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    lines, _ = ox.read_lines(buf.getvalue(), "BSL PLAN OCT 2026.xlsx")
    assert [(l["label"], l["app"], l["op"]) for l in lines] == [
        ("Hot Metal", 437, 450), ("- Slab", 42, 10), ("", 381, 357), ("Coke Rate", 419, 435)]
    got = _rows("BSL", lines, {"Hot Metal": 437.0, "Saleable Semis": 42.0, "Finished Steel": 381.0})
    assert {k: (v["op_value"], v["status"]) for k, v in got.items()} == {
        "Hot Metal": (450, "matched"), "Saleable Semis": (10, "matched"), "Finished Steel": (357, "app-only")}


@pytest.mark.parametrize("name, text, want", [
    ("BSP Tentative Plan - Nov26.pdf", "", {"plant": "BSP", "month": "2026-11"}),
    ("Monthly Plan Nov 2026 R2.pdf", "Monthly Production Plan : Nov-2026\nSAIL/DSP", {"plant": "DSP", "month": "2026-11"}),
    ("ISP RMT Meeting, Nov 2026.pdf", "RSP CGM SERVICES", {"plant": "ISP", "month": "2026-11"}),
    ("RSP Production Plan Nove26.xlsx", "", {"plant": "RSP", "month": "2026-11"}),
    ("BSL PLAN OCT 2026 (2).xlsx", "", {"plant": "BSL", "month": "2026-10"}),
])
def test_detect(name, text, want):
    assert ox.detect(text, name) == want


def test_photo_refused():
    with pytest.raises(ValueError, match="photo or scan"):
        ox.read_lines(b"\xff\xd8", "ISP.jpeg")
