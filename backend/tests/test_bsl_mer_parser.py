"""BSL BF month-end report parser: a furnace under capital repair must not
take the Shop row's figures down with it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "techno_project"))
from bsl_mer_parser import extract_bsl_mer, _is_repair_row  # noqa: E402

# Quality table from BlastFurnace-Oct'26.pdf (BF-5 under capital repair; the
# Shop row has short '****' overflow cells).
_QUALITY_OCT26 = """\
COKE RATE
| 4. |90.0/84.1| 100/88.7|14.64/14.80|7.99/8.10|1.09/1.08|1489/1482| 427/ 477|16/ 13| 101/ 61| 544/ 550| 449/ 454| 0/ 12| 632565|1094248| 453/ 451| 1.28|
| 5. |******************************************************** U N D E R C A P I T A L R E P A I R ******************| 529521| 915996|****************|
|SHOP|86.8/88.4|86.8/79.9|14.90/*****| 8.0/****|1.08/****|1489/1116| 421/ 458|15/ 12| 98/ 75| 534/ 545| 441/ 449| 0/ 12|2923042|5056447| 450/ 454| 0.97|
CAST DETAILS
"""


def test_repair_banner_detected_but_overflow_cells_are_not():
    lines = _QUALITY_OCT26.splitlines()
    assert _is_repair_row(lines[2])
    assert not _is_repair_row(lines[3])


def test_shop_quality_row_survives_furnace_under_repair():
    recs = {r["unit"]: r["techno_json"] for r in extract_bsl_mer(_QUALITY_OCT26, "2026-10")}
    shop = recs["BF_Shop"]
    assert shop["month"] == {"coke_rate": 458.0, "nut_coke_rate": 12.0, "cdi": 75.0, "fuel_rate": 545.0}
    assert shop["till_month"] == {"production": 2923042.0, "coke_rate": 450.0}
    assert "BF-5" not in recs
