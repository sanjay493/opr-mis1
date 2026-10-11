"""BSL DPR: the "- CHQ COIL" sub-line under H R COIL (first seen on the
30/09/2026 report) is saved as "Checkered Coil" and taken back out of
"HSM HR Coil (Sale)", which counts it in -- the same rule as "- CHQ PLATE"
under H R PLATE. Report total check (30/09/2026): every sales-side line
except the two CHQ sub-lines and Pig Iron adds up to SAL.STEEL(P) exactly."""
import pytest

from conftest import find_sample
from excel_extractors import excel_extractor_bsl as bsl


def _values(path, month):
    rows = bsl.extract_preview(str(path), month)["production_rows"]
    out = {}
    for r in rows:
        if r.get("status") == "ok":
            out[r["item_name"]] = r["value"]  # later rows (derived) win
    return out


def test_sep26_chequered_coil_split_out_of_hr_coil():
    sample = find_sample("MONTHEND/BSL/DPR Mail_300926.xlsx")
    if sample is None:
        pytest.skip("BSL DPR 30/09/2026 not available")
    v = _values(sample, "2026-09")
    assert v["Checkered Coil"] == pytest.approx(24.179)
    assert v["HSM HR Coil (Sale)"] == pytest.approx(184.317 - 24.179)
    assert v["Checkered plate"] == pytest.approx(2.801)
    assert v["HSM HR Plate"] == pytest.approx(34.876 - 2.801)


def test_aug26_without_chq_coil_line_keeps_hr_coil():
    sample = find_sample("MONTHEND/BSL/DPR MAIL Aug'26.xlsx")
    if sample is None:
        pytest.skip("BSL DPR Aug'26 not available")
    v = _values(sample, "2026-08")
    assert "Checkered Coil" not in v
    assert v["HSM HR Coil (Sale)"] == pytest.approx(196.453)
