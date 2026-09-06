"""
Second RSP despatch backfill pass: extends backfill_rsp_despatch_fy2526.py
backwards/forwards to every other period RSP's monthly TECHNOPARA archive
(G:\\My Drive\\Report_format\\Monthly\\RSP\\) actually covers, per direct
instruction to backfill "more previous months ... whatever sources
available":

  FY2023-24 (Apr'23-Mar'24) <- "Technopara March-2024.xlsx" (year-end file,
      carries the whole FY in one sheet, same growing-FY-table mechanism
      backfill_rsp_despatch_fy2526.py already relies on). Only Saleable
      Steel Despatch + Road Despatch are available this far back — no
      "CMO Direct despatch" row exists at all on this file's despatch
      sheet, and Export is only broken down by destination (Slabs-Export,
      Slabs-BSP, ...), never as one combined total the way later files
      have — so Direct Despatch/Finished Export (named "Total Export" at
      the time this script was written — see excel_extractor_rsp.py's
      DESPATCH_ITEMS) are correctly left unwritten for this FY, not guessed.
  FY2024-25 (Apr'24-Mar'25) <- "TECHNOPARA MARCH-2025.xlsx" (year-end
      file). Saleable Steel Despatch + Road Despatch + Finished Export (a
      bare "Export" row, not yet "TOTAL EXPORT") are available; Direct
      Despatch still isn't (same gap as FY23-24 — "CMO Direct despatch"
      is confirmed absent on every RSP file checked before ~Oct 2025).
  FY2026-27, Apr-Jul (partial, current FY) <- "TECHNOPARA JULY-2026.xlsx"
      (the latest available file at time of writing — its own despatch
      sheet, "PAGE-11" this time, not "page-10"/"Pg-10", confirmed via
      _find_despatch_sheet's title search). All 4 items available. Aug
      2026 onward is blank in this file (not yet occurred) and is
      correctly skipped rather than written as 0.

No FY2022-23 or earlier RSP file exists in the archive folder to backfill
further back than FY2023-24.

Usage:
  python scripts/backfill_rsp_despatch_more_history.py            # dry-run
  python scripts/backfill_rsp_despatch_more_history.py --apply     # writes to the live DB

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

PLANT = "RSP"

_FY_MONTHS = {
    "2023-24": [
        ("2023-04", "04"), ("2023-05", "05"), ("2023-06", "06"), ("2023-07", "07"),
        ("2023-08", "08"), ("2023-09", "09"), ("2023-10", "10"), ("2023-11", "11"),
        ("2023-12", "12"), ("2024-01", "01"), ("2024-02", "02"), ("2024-03", "03"),
    ],
    "2024-25": [
        ("2024-04", "04"), ("2024-05", "05"), ("2024-06", "06"), ("2024-07", "07"),
        ("2024-08", "08"), ("2024-09", "09"), ("2024-10", "10"), ("2024-11", "11"),
        ("2024-12", "12"), ("2025-01", "01"), ("2025-02", "02"), ("2025-03", "03"),
    ],
}

# (source file, {report_month: month_num}) — FY26-27 given explicitly
# (only Apr-Jul, not the full 12) since it's the current, still-incomplete
# FY; the two full-FY entries reuse _FY_MONTHS above.
SOURCES = [
    (r"G:\My Drive\Report_format\Monthly\RSP\Technopara March-2024.xlsx", _FY_MONTHS["2023-24"]),
    (r"G:\My Drive\Report_format\Monthly\RSP\TECHNOPARA MARCH-2025.xlsx", _FY_MONTHS["2024-25"]),
    (r"G:\My Drive\Report_format\Monthly\RSP\TECHNOPARA JULY-2026.xlsx", [
        ("2026-04", "04"), ("2026-05", "05"), ("2026-06", "06"), ("2026-07", "07"),
    ]),
]


def extract_despatch(file_path: str, months: list) -> dict:
    """{report_month: {item_name: value_in_tonnes}} for the given
    (report_month, month_num) pairs, reading each month's own column out
    of one workbook whose despatch sheet is located by title."""
    wb = openpyxl.load_workbook(file_path, data_only=True)
    despatch_name = _find_despatch_sheet(wb, wb.sheetnames)
    if not despatch_name:
        raise ValueError(f"No DESP.PERFORMANCE/DESPATCH PERFORMANCE sheet found in {file_path}.")
    ws = wb[despatch_name]

    out = {}
    for report_month, month_num in months:
        col = COL_MAP_P9[month_num]
        cells = _build_despatch_cells(ws, col)
        vals = {}
        for item_name, cell in cells.items():
            v = clean_val(ws[cell].value)
            if v:  # skip None and 0 — 0 here means "hasn't happened yet" on a growing-FY sheet, not a real zero month
                vals[item_name] = v
        out[report_month] = vals
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    all_months = {}
    for file_path, months in SOURCES:
        by_month = extract_despatch(file_path, months)
        print(f"\n=== {os.path.basename(file_path)} ===")
        for report_month, vals in by_month.items():
            parts = "   ".join(f"{k}={v:,.0f} T" for k, v in vals.items())
            print(f"{report_month}: {parts or '(no despatch data found)'}")
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
