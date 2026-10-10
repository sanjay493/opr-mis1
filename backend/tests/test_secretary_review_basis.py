"""Secretary Review deck: production plan is MoU when mou_plan_table has the
report month for every deck item, else APP; the template's 'APP' header
cells follow the basis."""
import sqlite3

import pytest
from pptx import Presentation
from pptx.util import Inches

import page_secretary_review as psr

_ITEMS = [db_item for _, db_item in psr.ITEMS]


def _cursor(mou_rows):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE mou_plan_table (report_month TEXT, plant_name TEXT, item_name TEXT, month_actual REAL)")
    c.executemany("INSERT INTO mou_plan_table VALUES (?,?,?,?)", mou_rows)
    return c.cursor()


def test_basis_mou_when_every_item_has_mou_for_month():
    cur = _cursor([("2026-08", "BSP", it, 1.0) for it in _ITEMS])
    assert psr.plan_basis(cur, "2026-08") == "mou"


def test_basis_app_when_no_mou():
    assert psr.plan_basis(_cursor([]), "2026-08") == "app"


def test_basis_app_when_mou_missing_an_item_or_month():
    cur = _cursor([("2026-08", "BSP", it, 1.0) for it in _ITEMS[:-1]] + [("2026-09", "BSP", _ITEMS[-1], 1.0)])
    assert psr.plan_basis(cur, "2026-08") == "app"


def test_basis_app_when_table_missing():
    cur = sqlite3.connect(":memory:").cursor()
    assert psr.plan_basis(cur, "2026-08") == "app"


def test_plan_headers_relabelled():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    t = slide.shapes.add_table(2, 3, Inches(0), Inches(0), Inches(3), Inches(1)).table
    t.cell(0, 0).text, t.cell(0, 1).text, t.cell(0, 2).text = "Item", "APP", "Actual"
    t.cell(1, 0).text = "Hot Metal APP note"
    psr._relabel_plan_headers(t, "MoU")
    assert [t.cell(0, i).text for i in range(3)] == ["Item", "MoU", "Actual"]
    assert t.cell(1, 0).text == "Hot Metal APP note"


@pytest.mark.parametrize("basis,label", [("app", "APP"), ("mou", "MoU")])
def test_basis_label(basis, label):
    assert psr.BASIS_LABEL[basis] == label
