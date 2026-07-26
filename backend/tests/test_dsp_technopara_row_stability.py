"""Regression tests for DSP's "Average Blows Per Day" (average_blows_per_day)
extraction (techno_project/dsp_technopara_extractor.py via
excel_extractors/pdf_extractor_dsp.py).

DSP's monthly PDF report never carried this parameter before — it's sourced
from the CONTINUOUS CASTING PLANT page's "Total Caster-Heats per day" row
(NOT the per-machine "M/c-N Heats per day" rows, which are deliberately not
extracted), mapped to the same "average_blows_per_day" key RSP/BSP/ISP
already use for their SMS shop's blows/heats-per-day figure.

This row lives in the PRODUCTION section of the page, not under "TE
PARAMETERS" like the neighbouring Caster Yield rows — and its March/quarter-
end column count (19-20) collides with an unrelated special case in the
shared _te_values_techno() helper (built for a different DSP page's column
layout), which silently returned the wrong pair of columns. Confirmed by
reading the real column headers in each sample file below before trusting
any extracted number.
"""

import importlib
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
DSP_DIR = BACKEND_DIR.parent / "Report_format" / "Monthly" / "DSP"

# (filename, report_month, expected actual, expected cum) — each value
# independently verified against the real column header row in that file
# (see the "Total Caster-Heats per day" row's header-to-value mapping worked
# out by hand for each of these three files).
KNOWN_GOOD = [
    ("mis0525.pdf", "2025-05", 45.6, 48.8),   # non-quarter-end, 5 columns
    ("mis0825.pdf", "2025-08", 50.1, 49.6),   # non-quarter-end, 9 columns
    ("mis0326.pdf", "2026-03", 50.8, 49.9),   # quarter-end, 20 columns —
    # the exact case _te_values_techno's report_month==3 special case
    # (len(nums) in (19,20)) would have mis-picked as (49.9, 53.8) instead.
]

# Files confirmed to predate the "Heats per day" table's introduction into
# the report template (verified absent by direct text search) — extraction
# must return no data for this parameter, not raise or silently invent one.
PRE_FORMAT_FILES = [
    ("mis0117.pdf", "2017-01"),
]


def _extractor_class():
    mod = importlib.import_module("techno_project.dsp_technopara_extractor")
    return mod.DspTechnoExtractor


@pytest.mark.parametrize("filename,report_month,expected_actual,expected_cum", KNOWN_GOOD)
def test_average_blows_per_day_matches_verified_header(filename, report_month, expected_actual, expected_cum):
    sample = DSP_DIR / filename
    if not sample.exists():
        pytest.skip(f"sample file not present: {sample}")
    DspTechnoExtractor = _extractor_class()
    records = DspTechnoExtractor(str(sample), report_month).extract()
    sms = next((r for r in records if r["unit"] == "SMS"), None)
    assert sms is not None, f"{filename}: no SMS unit record extracted at all"

    actual = sms["techno_json"]["month"].get("average_blows_per_day")
    cum = sms["techno_json"]["till_month"].get("average_blows_per_day")
    assert actual == pytest.approx(expected_actual, abs=0.05), (
        f"{filename}: average_blows_per_day month={actual!r}, expected ~{expected_actual} "
        f"(verified against this file's own column header row)"
    )
    assert cum == pytest.approx(expected_cum, abs=0.05), (
        f"{filename}: average_blows_per_day till_month={cum!r}, expected ~{expected_cum}"
    )


@pytest.mark.parametrize("filename,report_month", PRE_FORMAT_FILES)
def test_average_blows_per_day_absent_before_format_introduced(filename, report_month):
    """Older reports (pre-2018) don't have the 'Heats per day' table at all —
    extraction must not crash, and must not invent a value from an unrelated
    row that happens to also match a loose keyword search."""
    sample = DSP_DIR / filename
    if not sample.exists():
        pytest.skip(f"sample file not present: {sample}")
    DspTechnoExtractor = _extractor_class()
    records = DspTechnoExtractor(str(sample), report_month).extract()
    sms = next((r for r in records if r["unit"] == "SMS"), None)
    if sms is not None:
        assert sms["techno_json"]["month"].get("average_blows_per_day") is None
