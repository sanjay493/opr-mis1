"""Rake detention report pages must show nothing after the report month:
an Aug'26 report printed while Sep'26 figures were already entered showed
Sep'26 on "Commodity Wise Average Plant Detention" (2026-10-04) - the pages
lay out the whole FY (Apr-Mar) and filled every month that had data.

Uses the live DB's rake detention history; skipped if a month after the
report month has no stored figures to leak (nothing to test then).
"""

import pytest

import db
import page_rake_detention as rd

REPORT_MONTH = "2026-08"


def _later_month_has_data():
    master = db.get_rake_detention_master(plants=rd.SUMMARY_PLANTS)
    history = db.get_rake_detention_trend([r["id"] for r in master])
    return any(m > REPORT_MONTH for h in history.values() for m in h)


def test_detail_pages_blank_after_report_month():
    if not _later_month_has_data():
        pytest.skip("no stored month after the report month")
    for plants in rd.DETAIL_PAGES.values():
        page = rd.generate_rake_detention_detail(REPORT_MONTH, plants)
        cut = page["month_labels"].index("Aug'26") + 1
        for plant in page["plants"]:
            for section in plant["sections"]:
                for row in section["rows"]:
                    later = [c["text"] for c in row["vals"][cut:]]
                    assert all(t == "" for t in later), (plant["plant"], row["row_label"], later)


def test_trend_page_blank_after_report_month():
    page = rd.generate_rake_detention_trend(REPORT_MONTH)
    for plant in page["plants"]:
        for fy_row in plant["fy_rows"]:
            if fy_row["fy"] == "2026-27":
                assert all(v == "" for v in fy_row["vals"][5:]), (plant["plant"], fy_row["vals"])
