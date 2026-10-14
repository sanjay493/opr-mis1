import board_note_annexures as A


def test_q2_periods_match_the_q2_annexure_headings():
    P = A.periods(2025, 2)
    assert P["months"] == ["2025-07", "2025-08", "2025-09"]
    assert P["q_cply"] == ["2024-07", "2024-08", "2024-09"]
    assert P["cum"] == ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]
    assert P["q_label"] == "Q-2'25-26"
    assert P["q_cply_label"] == "Q-2'24-25"
    assert P["cum_label"] == "Apr-Sep'25"
    assert P["cum_cply_label"] == "Apr-Sep'24"
    assert P["long_label"] == "H-1'25-26"
    assert P["prev_label"] == "Q-1'25-26"
    assert P["prev"] == ["2025-04", "2025-05", "2025-06"]


def test_q1_has_no_fy_to_date_or_previous_period():
    P = A.periods(2026, 1)
    assert P["cum"] is None and P["prev"] is None and P["long_label"] is None


def test_q4_crosses_the_calendar_year():
    P = A.periods(2026, 4)
    assert P["months"] == ["2027-01", "2027-02", "2027-03"]
    assert P["cum_label"] == "Apr-Mar'27"
    assert P["long_label"] == "FY'26-27"
    assert P["prev_label"] == "Apr-Dec'26"


def test_q3_labels():
    P = A.periods(2026, 3)
    assert P["long_label"] == "9M'26-27"
    assert P["prev_label"] == "Apr-Sep'26"


def test_header_breaks_only_period_labels():
    assert A._br("Q-2'25-26") == "Q-2<br>'25-26"
    assert A._br("Jul'25") == "Jul&#x27;25"
