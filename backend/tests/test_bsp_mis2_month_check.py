"""BSP MIS-2: a report whose header date is not the selected month is refused."""
import openpyxl
import pytest

from excel_extractors import excel_extractor_bsp as bsp


def _mis2_wb(day, mon, year):
    wb = openpyxl.Workbook()
    ws = wb.active
    for c, v in enumerate(["BSP MIS-2", "Date:", day, mon, year], start=1):
        ws.cell(2, c, v)
    return wb


def test_mis2_wrong_month_refused():
    with pytest.raises(ValueError, match="select 2026-10"):
        bsp._extract_mis2_furnace_preview(_mis2_wb(31, "OCT", 2026), "2026-09")


def test_mis2_right_month_accepted():
    r = bsp._extract_mis2_furnace_preview(_mis2_wb(31, "OCT", 2026), "2026-10")
    assert r["month"] == "2026-10" and r["month_mismatch"] is False
