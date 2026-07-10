"""Golden-rule self-check for the ISP Technopara extractor
(techno_project/isp_technopara_extractor.py).

`ISPSummarizedMonthlyReport-March26.xlsx` is unique among the sample files:
its COKE OVENS/B-FCE/etc. sheets carry EVERY month of FY2025-26 as its own
'ACT' column in one workbook (Apr'25 .. Mar'26), interspersed with
cumulative columns. That lets us run the extractor 12 times against a
SINGLE, known-good file and check two invariants that a code change or a
future report-template tweak could silently break:

  1. Every month extracts without raising, and returns a stable number of
     units with a healthy amount of non-null data (catches wholesale
     column/row-detection breakage).
  2. Twelve different report_months resolve to twelve DIFFERENT Excel
     columns for the same parameter (catches _get_cum_column_offset or
     month-header matching accidentally aliasing two months onto the same
     column).

This does NOT catch row-position drift between files (the row numbers are
fixed within one workbook) — that's what the label-verification fallback in
_verified_row()/_find_label_row() is for, and what the per-real-file sanity
loop below (using the 15 actual monthly report files) guards against
instead: those are the real upload artifacts, so if SAIL ever changes the
template, extraction from one of them should still return data, not raise.
"""

import importlib
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
ISP_DIR = BACKEND_DIR.parent / "Report_format" / "Monthly" / "ISP"
MARCH_FILE = ISP_DIR / "ISPSummarizedMonthlyReport-March26.xlsx"

FY2025_26_MONTHS = [f"2025-{m:02d}" for m in range(4, 13)] + [f"2026-{m:02d}" for m in range(1, 4)]

# The 15 real monthly upload files, each with its own report_month.
REAL_MONTHLY_FILES = [
    ("Summarized Monthly Report Apr'25.xlsx", "2025-04"),
    ("Summarized Monthly Report May'25.xlsx", "2025-05"),
    ("Summarized Monthly Report Jun'25.xlsx", "2025-06"),
    ("Summarized Monthly Report Jul'25.xlsx", "2025-07"),
    ("Summarized Monthly Report Aug'25.xlsx", "2025-08"),
    ("Summarized Monthly Report Sep'25.xlsx", "2025-09"),
    ("Summarized Monthly Report Oct'25.xlsx", "2025-10"),
    ("Summarized Monthly Report Nov'25.xlsx", "2025-11"),
    ("Summarized Monthly Report Dec'25.xlsx", "2025-12"),
    ("Summarized Monthly Report Jan'26.xlsx", "2026-01"),
    ("Summarized Monthly Report Feb'26.xlsx", "2026-02"),
    ("Summarized Monthly Report Mar'25.xlsx", "2025-03"),
    ("Summarized Monthly Report Apr'26.xlsx", "2026-04"),
    ("Summarized Monthly Report May'26.xlsx", "2026-05"),
]

# Expected unit count (B-FCE: BF-5 [absorbs the former stray SP/General
# sub-groups — see below], SMS, SINTER: SP, WRM, BM, USM,
# COKE OVENS: COB-old/COB-new, Maj Techno Summ: General = 9) — a change here
# signals a sheet/unit went from "some data" to "no data" (or vice versa)
# somewhere.
#
# B-FCE used to also define its own "SP" (return_fines) and "General"
# (coal_to_hm, coke_screen_loss) sub-groups, which collided with SINTER's
# "SP" and Maj Techno Summ's "General" on the same techno_data row key
# (plant, report_month, unit) — two unrelated parameter sets silently
# sharing one DB row. Those three params were folded into "BF-5" instead.
EXPECTED_UNIT_COUNT = 9
MIN_NONNULL_VALUES = 30  # out of 81 mapped params total, a generous floor


def _extractor_class():
    mod = importlib.import_module("techno_project.isp_technopara_extractor")
    return mod.IspTechnoExtractor


@pytest.mark.parametrize("report_month", FY2025_26_MONTHS)
def test_all_fy2025_26_months_extract_cleanly(report_month):
    if not MARCH_FILE.exists():
        pytest.skip(f"sample file not present: {MARCH_FILE}")
    IspTechnoExtractor = _extractor_class()
    records = IspTechnoExtractor(str(MARCH_FILE), report_month).extract()

    assert len(records) == EXPECTED_UNIT_COUNT, (
        f"{report_month}: expected {EXPECTED_UNIT_COUNT} units, got {len(records)} "
        f"({[r['unit'] for r in records]})"
    )
    for rec in records:
        assert rec["report_month"] == report_month
        assert rec["plant"] == "ISP"

    total_nonnull = sum(
        1 for rec in records for v in rec["techno_json"]["month"].values() if v is not None
    )
    assert total_nonnull >= MIN_NONNULL_VALUES, (
        f"{report_month}: only {total_nonnull} non-null month values extracted "
        f"(expected >= {MIN_NONNULL_VALUES}) — likely a column-detection regression"
    )


def test_all_fy2025_26_months_resolve_distinct_columns():
    """Same B-FCE 'coke_rate' parameter, 12 different report_months against
    the SAME file, must resolve to 12 different Excel columns."""
    if not MARCH_FILE.exists():
        pytest.skip(f"sample file not present: {MARCH_FILE}")
    IspTechnoExtractor = _extractor_class()

    columns = set()
    for report_month in FY2025_26_MONTHS:
        ex = IspTechnoExtractor(str(MARCH_FILE), report_month)
        ex.open_workbook()
        ws = ex.workbook["B-FCE"]
        header_row, header = ex._find_month_column(ws)
        assert header_row is not None, f"{report_month}: no month header row found"
        month_num = int(report_month.split("-")[1])
        from techno_project.isp_technopara_extractor import _MONTH_NUM_TO_ABBR
        target_abbr = _MONTH_NUM_TO_ABBR[month_num]
        month_col = next(i for i, h in enumerate(header) if target_abbr in h)
        act_col = ex._get_actual_column(ws, month_col)
        columns.add(act_col)

    assert len(columns) == 12, (
        f"Expected 12 distinct ACT columns across FY2025-26, got {len(columns)}: {sorted(columns)}"
    )


@pytest.mark.parametrize("filename,report_month", REAL_MONTHLY_FILES)
def test_real_monthly_files_extract_without_crashing(filename, report_month):
    """Sanity check against the real per-month upload files (not the
    multi-month March file) — catches genuine file-to-file template drift
    that a single multi-month workbook can't, since row positions don't vary
    across columns within one file."""
    sample = ISP_DIR / filename
    if not sample.exists():
        pytest.skip(f"sample file not present: {sample}")
    IspTechnoExtractor = _extractor_class()
    records = IspTechnoExtractor(str(sample), report_month).extract()
    assert records, f"{filename} ({report_month}): no units extracted at all"
    total_nonnull = sum(
        1 for rec in records for v in rec["techno_json"]["month"].values() if v is not None
    )
    assert total_nonnull >= MIN_NONNULL_VALUES, (
        f"{filename} ({report_month}): only {total_nonnull} non-null month values"
    )
