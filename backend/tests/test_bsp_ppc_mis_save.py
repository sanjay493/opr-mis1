"""excel_extractor_bsp.extract_and_save_excel writes BSP PPC MIS actuals to
production_table (regression: a function-local `from repo import production
as rp` placed after the upsert loop made `rp` unbound there, so every upload
failed and wrote nothing).

Building a real .xls fixture needs xlwt, which isn't installed, so the
workbook is a minimal in-memory stand-in for xlrd's (sheet 'S1' with a date
serial in row 0 and one labelled production row). That still runs the whole
function: cell resolution, the upsert loop over every resolved item, the
commit and the extraction log."""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "excel_extractors"))
import excel_extractor_bsp as bsp  # noqa: E402

REPORT_DATE = dt.date(2026, 8, 31)          # last day: no month-to-date projection
SP2_ROW = 10


class _Sheet:
    def __init__(self, cells):
        self._cells = cells
        self.nrows = 60
        self.ncols = 20

    def cell_value(self, r, c):
        return self._cells.get((r, c), "")


class _Book:
    datemode = 0

    def __init__(self, sheet):
        self._sheet = sheet

    def sheet_names(self):
        return ["S1"]

    def sheet_by_name(self, name):
        assert name == "S1"
        return self._sheet


@pytest.fixture
def fake_ppc_mis(monkeypatch):
    serial = float((REPORT_DATE - dt.date(1899, 12, 30)).days)
    cells = {
        (0, 13): serial,
        (SP2_ROW, 0): "SP-2",
        (SP2_ROW, 5): 150000.0,              # tonnes, month cumulative
    }
    monkeypatch.setattr(bsp.xlrd, "open_workbook", lambda path: _Book(_Sheet(cells)))


def _rows():
    from v2dual import production_rows
    return {r[2]: r[3] for r in production_rows("production_table") if r[0] == "2026-08" and r[1] == "BSP"}


def test_extract_and_save_excel_writes_production_rows(mysql_db, fake_ppc_mis):
    assert bsp.extract_and_save_excel("ppc_mis.xls", source_file_name="ppc_mis.xls") is True
    rows = _rows()
    # Only SP-2 is resolvable on this sheet (every other item is found by its
    # own label or guarded by an anchor label that isn't there).
    assert rows == {"SP-2": pytest.approx(150.0)}
