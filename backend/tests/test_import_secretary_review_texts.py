from pathlib import Path

from scripts.import_secretary_review_texts import extract_texts

REF = Path(__file__).parent / "fixtures" / "secretary_review_sep26_reference.pptx"


def test_extract_texts_from_reference():
    t = extract_texts(REF)
    assert t["hl_SAIL"].startswith("SAIL achieved best")
    assert "Hot Metal" in t["hl_SAIL"]
    assert t["hl_BSP"].startswith("BSP achieved best")
    assert "hl_DSP" not in t                          # no highlights table on the DSP slide
    assert "BF#4" in t["delay_hmcs"]
    assert "RSM" in t["delay_fs"]
    assert "SMS2" in t["cr_BSP_cur"] and t["cr_BSP_prev"]
    assert t["cr_ISP_cur"].startswith("BF-5")
    assert "BLT chute" in t["bd_BSP_BF"]
    assert "HSM-2" in t["bd_RSP_MILL"]
    assert "\n\n" not in t["hl_SAIL"]
