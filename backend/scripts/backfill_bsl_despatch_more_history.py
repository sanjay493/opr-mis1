"""
Second BSL despatch backfill pass: extends backfill_bsl_despatch_fy2526.py
to every other period BSL's archive (G:\\My Drive\\Report_format\\...\\BSL\\)
actually covers, per direct instruction to backfill "more previous months
... whatever sources available":

  Monthly "Production of Main Products" PDF bundle (Monthly\\BSL\\,
      Rev/Review <Month> <Year>.pdf) — covers June 2022 through March
      2025 continuously (35 files), plus a standalone June 2026 file. Each
      file is one month's own report; extracted via
      excel_extractor_bsl.extract_preview_main_products_pdf, same as the
      ongoing extractor, then just the 5 despatch rows are pulled out of
      its production_rows and written directly (bypassing the normal
      preview/confirm UI flow, appropriate for a one-off scripted backfill
      — see backfill_bsl_despatch_fy2526.py for the same pattern). Items
      not yet on the page this far back (Road Despatch, Export's own
      "-Finished" split — see excel_extractor_bsl.py's
      _parse_despatch_glance_page docstring) come back "no value" and are
      correctly skipped rather than written as 0.

  Month-end DPR Mail Excel (MONTHEND\\BSL\\) — only for the 2 months this
      pass found with NO other source at all (2026-05, 2026-08): every
      other DPR file on disk duplicates a month the Annual Statistics
      FY25-26 backfill or the monthly-PDF pass above already covers, or is
      a mid-month upload superseded by a month-end file for the same
      month (DPR Mail_18052026.xlsx vs the month-end BSL-DPR31052026.xlsx
      for May 2026) — both skipped rather than overwriting a better
      reading with a noisier or redundant one. 2026-08 has two candidate
      files (with/without "_Rev" suffix); the "_Rev" (revised) one is
      used. Only Saleable Steel Despatch is available via this route (see
      excel_extractor_bsl.py's _DPR_LABELS) — writes just that one item,
      not the DPR file's other ~19 production_table items, since those are
      out of scope for this despatch-only backfill.

Known remaining gaps after this pass — no source available for either:
  BSL: April 2026, July 2026 (no monthly PDF or DPR file for either month
       in the archive as of this backfill).

Usage:
  python scripts/backfill_bsl_despatch_more_history.py            # dry-run
  python scripts/backfill_bsl_despatch_more_history.py --apply     # writes to the live DB

Dry-run is the default on purpose — this touches the live MySQL DB
(DB_ENGINE=mysql), so the values should be reviewed before anything is
written.
"""
import sys
import os
import argparse
import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "excel_extractors"))

import openpyxl  # noqa: E402
import db  # noqa: E402
from excel_extractors.excel_extractor_bsl import (  # noqa: E402
    extract_preview_main_products_pdf, _dpr_config, _resolve_dpr_cells,
    _dpr_value_and_alert, _dpr_cum_cell, _dpr_is_mid_month, clean_val,
)
import calendar  # noqa: E402

PLANT = "BSL"
DESPATCH_ITEM_NAMES = [
    "Saleable Steel Despatch", "Direct Despatch", "Semis Export",
    "Finished Export", "Road Despatch",
]

MONTHLY_DIR = r"G:\My Drive\Report_format\Monthly\BSL"
MONTHEND_DIR = r"G:\My Drive\Report_format\MONTHEND\BSL"

# (filename, report_month) — every Rev/Review PDF on disk, June 2022
# through March 2025 continuously, plus the standalone June 2026 file.
PDF_FILES = [
    ("Rev June 2022.pdf", "2022-06"),
    ("Rev July 2022.pdf", "2022-07"),
    ("Rev Aug 2022.pdf", "2022-08"),
    ("Rev Sept 2022.pdf", "2022-09"),
    ("Rev Oct 2022.pdf", "2022-10"),
    ("Rev Nov 2022.pdf", "2022-11"),
    ("Rev Dec 2022.pdf", "2022-12"),
    ("Rev Jan 2023.pdf", "2023-01"),
    ("Rev Feb 23.pdf", "2023-02"),
    ("Rev March 2023.pdf", "2023-03"),
    ("Review April 2023.pdf", "2023-04"),
    ("Review May 2023.pdf", "2023-05"),
    ("Review June 2023.pdf", "2023-06"),
    ("Review July 2023.pdf", "2023-07"),
    ("Review August 2023.pdf", "2023-08"),
    ("Review Sept 2023.pdf", "2023-09"),
    ("Review Oct 2023.pdf", "2023-10"),
    ("Review Nov 2023.pdf", "2023-11"),
    ("Review Dec 2023.pdf", "2023-12"),
    ("Review Jan 2024.pdf", "2024-01"),
    ("Review Feb 2024.pdf", "2024-02"),
    ("Review March24.pdf", "2024-03"),
    ("Rev April 2024.pdf", "2024-04"),
    ("Rev May 2024.pdf", "2024-05"),
    ("Rev June 2024.pdf", "2024-06"),
    ("Rev July 2024.pdf", "2024-07"),
    ("Rev August 2024.pdf", "2024-08"),
    ("Rev Sept 2024.pdf", "2024-09"),
    ("Rev Oct 2024.pdf", "2024-10"),
    ("Rev Nov 2024.pdf", "2024-11"),
    ("Rev December 2024.pdf", "2024-12"),
    ("Rev Jan 2025.pdf", "2025-01"),
    ("Rev Feb 2025.pdf", "2025-02"),
    ("Rev March 2025.pdf", "2025-03"),
    ("Rev June26 (2).pdf", "2026-06"),
]

# (filename, report_month) — month-end DPR files with no other source.
DPR_ONLY_FILES = [
    ("BSL-DPR31052026.xlsx", "2026-05"),
    ("DPR Mail_31082026_Rev.xlsx", "2026-08"),
]


def extract_pdf_despatch(fname: str, report_month: str) -> dict:
    path = os.path.join(MONTHLY_DIR, fname)
    result = extract_preview_main_products_pdf(path, report_month)
    vals = {}
    for r in result["production_rows"]:
        if r["item_name"] in DESPATCH_ITEM_NAMES and r["status"] == "ok" and r["value"] is not None:
            vals[r["item_name"]] = r["value"]  # already in '000T
    return result["month"], vals


def extract_dpr_saleable_steel_despatch(fname: str) -> tuple:
    """(db_report_month, value_in_000T_or_None) for just the "Saleable
    Steel Despatch" item from a DPR Mail file — mirrors
    excel_extractor_bsl._extract_dpr_report's own logic for this one item
    without touching the file's other ~19 production_table items."""
    path = os.path.join(MONTHEND_DIR, fname)
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["DPR"]

    o1_raw = ws["O1"].value
    if isinstance(o1_raw, datetime.datetime):
        day, m_num, year = o1_raw.day, str(o1_raw.month).zfill(2), str(o1_raw.year)
    else:
        raise ValueError(f"{fname}: cell O1 isn't a date — cannot determine report month.")
    db_report_month = f"{year}-{m_num}"
    days_in_month = calendar.monthrange(int(year), int(m_num))[1]
    report_day = day

    defaults, _no_convert, _derived = _dpr_config()
    resolved = _resolve_dpr_cells(ws, defaults)
    cell = resolved.get("Saleable Steel Despatch")
    if not cell:
        return db_report_month, None

    mrate = clean_val(ws[cell].value)
    cum = clean_val(ws[_dpr_cum_cell(cell)].value)
    val, _basis, _alert = _dpr_value_and_alert(mrate, cum, report_day, days_in_month,
                                                label="Saleable Steel Despatch")
    stored = round(val / 1000.0, 3) if val is not None else None
    return db_report_month, stored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    all_months = {}
    errors = []

    for fname, guessed_month in PDF_FILES:
        try:
            db_month, vals = extract_pdf_despatch(fname, guessed_month)
        except Exception as exc:
            errors.append((fname, str(exc)))
            continue
        parts = "   ".join(f"{k}={v:,.3f} '000T" for k, v in vals.items())
        print(f"{db_month} ({fname}): {parts or '(no despatch items found)'}")
        all_months[db_month] = vals

    for fname, expected_month in DPR_ONLY_FILES:
        try:
            db_month, val = extract_dpr_saleable_steel_despatch(fname)
        except Exception as exc:
            errors.append((fname, str(exc)))
            continue
        if db_month != expected_month:
            errors.append((fname, f"expected month {expected_month}, file says {db_month}"))
            continue
        print(f"{db_month} ({fname}): Saleable Steel Despatch="
              f"{val:,.3f} '000T" if val is not None else f"{db_month} ({fname}): (no value)")
        all_months.setdefault(db_month, {})
        if val is not None:
            all_months[db_month]["Saleable Steel Despatch"] = val

    if errors:
        print("\n--- Files that raised errors (skipped) ---")
        for fname, msg in errors:
            print(f"  {fname}: {msg}")

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
            for item_name, value_000t in vals.items():
                cur.execute("""
                    INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(report_month, plant_name, item_name)
                    DO UPDATE SET month_actual = excluded.month_actual
                """, (report_month, PLANT, item_name, value_000t))
                saved += 1
        conn.commit()
    finally:
        conn.close()

    print(f"\nSaved {saved} values across {len(all_months)} months for {PLANT}.")


if __name__ == "__main__":
    main()
