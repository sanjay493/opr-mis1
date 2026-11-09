"""Cost Trend extractor (excel_extractors/excel_extractor_cost_trend.py)
against the "ELHM CS SS <...>.xlsx" workbooks in Report_format/Cost.

Pins down the row-3 month header being written with a period after the
month ("Oct.'2026", "Upto Sept.'2026"), which failed with "could not
parse a report month from row 3" — and the same in the BF Coke
workbook ("Sept.'26": "could not find a month label") — plus the
cumulative workbooks' sheet named "SS." being skipped.
"""

import pytest

from conftest import find_sample
from excel_extractors.excel_extractor_cost_trend import (
    _parse_header, extract_bf_coke_workbook, extract_cost_trend_workbook,
)


@pytest.mark.parametrize("text, expected", [
    ("APRIL'2026", ("2026-04", False)),
    ("UPTO JULY'2026", ("2026-07", True)),
    ("Oct.'2026", ("2026-10", False)),
    ("Sept.'2026", ("2026-09", False)),
    ("Upto Sept.'2026", ("2026-09", True)),
    ("Upto Oct'2026", ("2026-10", True)),
    ("Oct. 2026", ("2026-10", False)),
])
def test_parse_header(text, expected):
    assert _parse_header(text) == expected


SAMPLES = {
    "ELHM CS SS APRIL26.xlsx": ("2026-04", False),
    "ELHM CS SS Sept..26.xlsx": ("2026-09", False),
    "ELHM CS SS APRIL-Sept..26.xlsx": ("2026-09", True),
    "ELHM CS SS Oct.26.xlsx": ("2026-10", False),
    "ELHM CS SS APRIL-OCT26.xlsx": ("2026-10", True),
}


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_workbook_extracts(name):
    path = find_sample(f"Cost/{name}")
    if path is None:
        pytest.skip(f"sample not present: {name}")
    r = extract_cost_trend_workbook(path)
    assert (r["report_month"], r["is_till_month"]) == SAMPLES[name]
    assert set(r["products"]) == {"HM", "CS", "SS"}
    for product, plants in r["products"].items():
        assert set(plants) == {"BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"}
        for plant, v in plants.items():
            assert isinstance(v["variable"], float) and isinstance(v["fixed"], float), (product, plant, v)


@pytest.mark.parametrize("name, month", [
    ("BF Coke-5ISPs-For Sept.  Upto Sept.26.xlsx", "2026-09"),
    ("BF Coke-5ISPs-For Oct.  Upto Oct.26.xlsx", "2026-10"),
])
def test_bf_coke_workbook_extracts(name, month):
    path = find_sample(f"Cost/{name}")
    if path is None:
        pytest.skip(f"sample not present: {name}")
    assert extract_bf_coke_workbook(path)["report_month"] == month
