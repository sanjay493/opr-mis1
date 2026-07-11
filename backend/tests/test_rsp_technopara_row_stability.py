"""Golden-rule self-check for the RSP Technopara extractor
(techno_project/rsp_technopara_extractor.py).

RSP has no single multi-month reference workbook like ISP's March-26 file —
each month is its own upload with its own file. So instead of ISP's
"one file, twelve synthetic months" test, this runs the real extractor
against every real sample file in Report_format/Monthly/RSP (34 files
spanning 2023-2026, with sheet names, column layouts, and row positions that
vary constantly between editions) and checks two invariants a code change or
a future report-template tweak could silently break:

  1. Every file extracts without raising, with a healthy unit count and a
     healthy amount of non-null data (catches wholesale sheet/column/row
     detection breakage).
  2. The month actually used for extraction matches the month implied by the
     filename (catches the header-column scan silently landing on the wrong
     month).

This does NOT assert exact values per parameter — the row-shift
self-healing (verified_row/find_label_row) trades exactness for resilience,
so the real safety net is "did it still find data," matching the label
verification's own warning-not-exception design.
"""
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
RSP_DIR = BACKEND_DIR.parent / "Report_format" / "Monthly" / "RSP"

# The 34 real technopara upload files, each with its report_month derived
# from the filename (matches how a user would pick the month in the upload
# form for that file).
REAL_TECHNOPARA_FILES = [
    ("TECHNOPARA APRIL-2024.xlsx", "2024-04"),
    ("TECHNOPARA APRIL-2025.xlsx", "2025-04"),
    ("TECHNOPARA AUG-2024.xlsx", "2024-08"),
    ("TECHNOPARA FEB-2024.xlsx", "2024-02"),
    ("TECHNOPARA FEB-2026.xlsx", "2026-02"),
    ("TECHNOPARA JAN-2025.xlsx", "2025-01"),
    ("TECHNOPARA JAN-2026.xlsx", "2026-01"),
    ("TECHNOPARA JULY-2024.xlsx", "2024-07"),
    ("TECHNOPARA JUNE-2025.xlsx", "2025-06"),
    ("TECHNOPARA JUNE-2026.xlsx", "2026-06"),
    ("TECHNOPARA JUNE-2026Rev.xlsx", "2026-06"),
    ("TECHNOPARA MARCH-2025.xlsx", "2025-03"),
    ("TECHNOPARA NOV-2023 Revised.xlsx", "2023-11"),
    ("TECHNOPARA NOV-2024.xlsx", "2024-11"),
    ("TECHNOPARA OCT-2025 (1).xlsx", "2025-10"),
    ("TECHNOPARA OCT-2025.xlsx", "2025-10"),
    ("TECHNOPARA OCT-23.xlsx", "2023-10"),
    ("TECHNOPARA SEP-2024.xlsx", "2024-09"),
    ("TECHNOPARA SEP-2025.xlsx", "2025-09"),
    ("TECHNOPARA_DEC25.xlsx", "2025-12"),
    ("Technopara -Aug25.xlsx", "2025-08"),
    ("Technopara Dec-2024.xlsx", "2024-12"),
    ("Technopara July -2025 (1).xlsx", "2025-07"),
    ("Technopara July -2025.xlsx", "2025-07"),
    ("Technopara MAY-2025.xlsx", "2025-05"),
    ("Technopara March-2024.xlsx", "2024-03"),
    ("Technopara OCT-2024.xlsx", "2024-10"),
    ("Technopara-Jun24.xlsx", "2024-06"),
    ("technopara APRIL-2026.xlsx", "2026-04"),
    ("technopara dec-2023.xlsx", "2023-12"),
    ("technopara feb -2025.xlsx", "2025-02"),
    ("technopara jan-2024.xlsx", "2024-01"),
    ("technopara march-2026 (1).xlsx", "2026-03"),
    ("technopara march-2026.xlsx", "2026-03"),
    ("technopara may-2024.xlsx", "2024-05"),
]

# rsp_technopara_map.json has 18 top-level units (BF-1/4/5/Shop, SMS-1/2,
# COB-old/new, General, SP-1/2/3, PM, NPM, HSM-2, SSM, SWP, ERW) — a file
# should extract data for nearly all of them; a handful of samples are down
# one unit some months (e.g. a mill with no data that period), so allow a
# little slack rather than requiring an exact match.
MIN_UNIT_COUNT = 15
# Out of 122 total mapped parameters, a generous floor (observed range on
# the real corpus is ~90-114).
MIN_NONNULL_VALUES = 60


def _extractor_class():
    import importlib
    mod = importlib.import_module("techno_project.rsp_technopara_extractor")
    return mod.TechnoExtractor


@pytest.mark.parametrize("fname,report_month", REAL_TECHNOPARA_FILES)
def test_real_files_extract_without_crashing(fname, report_month):
    path = RSP_DIR / fname
    if not path.exists():
        pytest.skip(f"sample file not present: {path}")

    TechnoExtractor = _extractor_class()
    extractor = TechnoExtractor(str(path), report_month=report_month)
    records = extractor.extract()

    assert extractor.report_month == report_month, (
        f"{fname}: month column scan resolved to {extractor.report_month}, "
        f"expected {report_month}"
    )
    assert len(records) >= MIN_UNIT_COUNT, (
        f"{fname}: expected >= {MIN_UNIT_COUNT} units, got {len(records)} "
        f"({[r['unit'] for r in records]})"
    )
    for rec in records:
        assert rec["report_month"] == report_month
        assert rec["plant"] == "RSP"

    total_nonnull = sum(
        1 for rec in records for v in rec["techno_json"]["month"].values() if v is not None
    )
    assert total_nonnull >= MIN_NONNULL_VALUES, (
        f"{fname}: only {total_nonnull} non-null month values across "
        f"{len(records)} units (floor {MIN_NONNULL_VALUES})"
    )
