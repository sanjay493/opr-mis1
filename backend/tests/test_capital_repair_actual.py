"""Capital Repair 'Actual' text: ranges, ongoing jobs and single-day jobs."""
import page_capital_repair as cr


def test_format_single_day_prints_one_date():
    assert cr.format_cr_actual("2026-09-22", "2026-09-22", False) == "22.9.26"


def test_format_range_and_ongoing_unchanged():
    assert cr.format_cr_actual("2026-07-06", "2026-07-17", False) == "6.7.26-17.7.26"
    assert cr.format_cr_actual("2026-07-16", None, True) == "16.7.26-cont.."


def test_cell_single_day_prints_one_date_as_of_a_later_month():
    assert cr._actual_cell("2026-10", "June'26", "2026-09-22", "2026-09-22", 0, "") == ("22.9.26", "actual")
    assert cr._actual_cell("2026-10", "June'26", "2026-09-22", None, 1, "") == ("22.9.26-cont..", "actual")
