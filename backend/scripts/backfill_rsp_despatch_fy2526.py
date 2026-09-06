"""
One-off backfill: RSP Saleable Steel Despatch / Direct Despatch / Road
Despatch / Finished Export (named "Total Export" at the time this script
was written — renamed since; see excel_extractor_rsp.py's DESPATCH_ITEMS)
for FY 2025-26 (Apr'25-Mar'26).

Unlike BSL's equivalent (see backfill_bsl_despatch_fy2526.py, which needed
a separate Annual Statistics PDF), RSP's monthly TECHNOPARA workbook is
itself a "growing FY table" — every month's file already carries ALL of
that FY's months so far in adjacent columns (see COL_MAP_P9 /
excel_extractor_rsp.py's module docstring). The March 2026 file (FY25-26's
last month) therefore already holds all 12 months' figures at once, in its
own despatch sheet (DESP.PERFORMANCE/DESPATCH PERFORMANCE title) — no
separate historical source needed, just every month column of that one
file, reusing the exact same DESPATCH_ITEMS/_build_despatch_cells/
_find_despatch_sheet the ongoing monthly extractor uses (see
excel_extractor_rsp.py's _extract_monthly_report).

Source file:
  G:\\My Drive\\Report_format\\Monthly\\RSP\\technopara march-2026 (1).xlsx
  (identical content to "technopara march-2026.xlsx" — confirmed row-by-row
  for the 4 despatch rows before picking one)

Usage:
  python scripts/backfill_rsp_despatch_fy2526.py            # dry-run: prints the 12 months, writes nothing
  python scripts/backfill_rsp_despatch_fy2526.py --apply     # actually writes to production_table (live DB)

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
from excel_extractors.excel_extractor_rsp import (  # noqa: E402
    _find_despatch_sheet, _build_despatch_cells, clean_val, COL_MAP_P9,
)

SOURCE_FILE = r"G:\My Drive\Report_format\Monthly\RSP\technopara march-2026 (1).xlsx"
PLANT = "RSP"

_FY2526_MONTHS = [
    ("2025-04", "04"), ("2025-05", "05"), ("2025-06", "06"), ("2025-07", "07"),
    ("2025-08", "08"), ("2025-09", "09"), ("2025-10", "10"), ("2025-11", "11"),
    ("2025-12", "12"), ("2026-01", "01"), ("2026-02", "02"), ("2026-03", "03"),
]


def extract_fy2526_despatch() -> dict:
    """{report_month: {item_name: value_in_tonnes}} for all 12 FY25-26
    months, reading each month's own column out of the single March-2026
    workbook (see module docstring)."""
    wb = openpyxl.load_workbook(SOURCE_FILE, data_only=True)
    despatch_name = _find_despatch_sheet(wb, wb.sheetnames)
    if not despatch_name:
        raise ValueError(
            f"No DESP.PERFORMANCE/DESPATCH PERFORMANCE sheet found in {SOURCE_FILE}."
        )
    ws = wb[despatch_name]

    out = {}
    for report_month, month_num in _FY2526_MONTHS:
        col = COL_MAP_P9[month_num]
        cells = _build_despatch_cells(ws, col)
        vals = {}
        for item_name, cell in cells.items():
            v = clean_val(ws[cell].value)
            if v is not None:
                vals[item_name] = v
        out[report_month] = vals
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    by_month = extract_fy2526_despatch()

    total_vals = 0
    for report_month, vals in by_month.items():
        parts = "   ".join(f"{k}={v:,.0f} T" for k, v in vals.items())
        print(f"{report_month}: {parts or '(no despatch data found)'}")
        total_vals += len(vals)

    if not args.apply:
        print(f"\nDry-run only — {total_vals} values NOT written. Re-run with --apply to save.")
        return

    conn = db.connect()
    cur = conn.cursor()
    saved = 0
    try:
        for report_month, vals in by_month.items():
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

    print(f"\nSaved {saved} values across {len(by_month)} months for {PLANT}.")


if __name__ == "__main__":
    main()
