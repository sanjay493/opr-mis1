"""
One-off backfill: ISP Saleable Steel Despatch / Direct Despatch / Semis
Export / Finished Export / Road Despatch, from FY2021-22 through the
current FY2026-27 (partial), per direct instruction.

Like RSP (see backfill_rsp_despatch_more_history.py), ISP's monthly
"Summarized Monthly Report" workbook is itself a growing-FY table: the
'Maj Despatch Summ' and 'DETAIL DESP' sheets carry every month of that FY
so far in fixed, adjacent columns (confirmed identical to
excel_extractor_isp.py's own _PROD_COL_MAP, used for the production
sheet). So each FY is backfilled from just its own year-end (March) file
— see excel_extractor_isp.py's _extract_despatch for the actual per-item
extraction logic (shared with the ongoing single-month extractor).

FY2026-27 is the one exception: its own latest file (named "upto
July26") is NOT used wholesale despite every month's column having
*some* value all the way through March 2027 — confirmed those Aug'26
onward columns are stale carry-over, not real FY26-27 data (e.g. its own
"Mar27" column reads 231,379.602 T, byte-for-byte the same figure as
FY2025-26's own real March 2026 total from ISPSummarizedMonthlyReport-
March26.xlsx — the template evidently leaves last year's same-column
figure sitting there until a real month overwrites it). Only Apr-Jul
2026, the 4 months the filename itself claims, are trusted here.

No sheet named 'Maj Despatch Summ' exists at all in the FY2020-21 file
("Summarised monthly 2020-21 Final.xlsx") or earlier — a different
report format from this era, out of scope for this pass.

Source files (G:\\My Drive\\Report_format\\Monthly\\ISP\\):
  FY2021-22  Mar'22_Summarized Monthly Report.xlsx
  FY2022-23  Mar'23Summarized Monthly Report.xlsx
  FY2023-24  Mar'24Summarized Monthly Report.xlsx
  FY2024-25  Mar'25Summarized Monthly Report.xlsx
  FY2025-26  ISPSummarizedMonthlyReport-March26.xlsx
  FY2026-27  Summarized Monthly Report 2026-27 upto July26.xlsx (Apr-Jul only)

Usage:
  python scripts/backfill_isp_despatch_history.py            # dry-run
  python scripts/backfill_isp_despatch_history.py --apply     # writes to the live DB

Dry-run is the default on purpose — this touches the live MySQL DB
(DB_ENGINE=mysql), so the values should be reviewed before anything is
written.
"""
import sys
import os
import argparse

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "excel_extractors"))

import openpyxl  # noqa: E402
import db  # noqa: E402
from excel_extractors.excel_extractor_isp import (  # noqa: E402
    _extract_despatch, _fy_month_sequence, _PROD_COL_MAP,
)

PLANT = "ISP"
ARCHIVE_DIR = r"G:\My Drive\Report_format\Monthly\ISP"

SOURCES = [
    ("Mar'22_Summarized Monthly Report.xlsx", _fy_month_sequence("2022-03")),
    ("Mar'23Summarized Monthly Report.xlsx", _fy_month_sequence("2023-03")),
    ("Mar'24Summarized Monthly Report.xlsx", _fy_month_sequence("2024-03")),
    ("Mar'25Summarized Monthly Report.xlsx", _fy_month_sequence("2025-03")),
    ("ISPSummarizedMonthlyReport-March26.xlsx", _fy_month_sequence("2026-03")),
    ("Summarized Monthly Report 2026-27 upto July26.xlsx", _fy_month_sequence("2026-07")),
]


def extract_file(fname: str, months: list) -> dict:
    wb = openpyxl.load_workbook(os.path.join(ARCHIVE_DIR, fname), data_only=True)
    out = {}
    for report_month in months:
        month_num = report_month[-2:]
        col = _PROD_COL_MAP[month_num]
        vals = _extract_despatch(wb, col, report_month)
        out[report_month] = {k: v for k, v in vals.items() if v is not None}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    all_months = {}
    for fname, months in SOURCES:
        print(f"\n=== {fname} ===")
        by_month = extract_file(fname, months)
        for report_month, vals in by_month.items():
            parts = "   ".join(f"{k}={v:,.2f} T" for k, v in vals.items())
            print(f"{report_month}: {parts or '(no despatch items found)'}")
        all_months.update(by_month)

    total_vals = sum(len(v) for v in all_months.values())
    if not args.apply:
        print(f"\nDry-run only — {total_vals} values across {len(all_months)} months NOT written. "
              f"Re-run with --apply to save.")
        return

    conn = db.connect()
    cur = conn.cursor()
    saved = 0
    try:
        for report_month, vals in all_months.items():
            for item_name, value_tonnes in vals.items():
                stored = round(value_tonnes / 1000.0, 3)
                cur.execute("""
                    INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(report_month, plant_name, item_name)
                    DO UPDATE SET month_actual = excluded.month_actual
                """, (report_month, PLANT, item_name, stored))
                saved += 1
        conn.commit()
    finally:
        conn.close()

    print(f"\nSaved {saved} values across {len(all_months)} months for {PLANT}.")


if __name__ == "__main__":
    main()
