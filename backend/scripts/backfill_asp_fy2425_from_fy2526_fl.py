"""
One-off backfill: ASP production_table for FY 2024-25, April 2024 - February
2025 (11 months; March 2025 deliberately excluded — see below), sourced from
the "last year, same month" column each FY 2025-26 monthly FL*.pdf report
already carries.

Why this works without a dedicated FY24-25 file: each FL report (e.g. a
Sept'25 report) prints its own report month's Plan/Actual, the immediately
preceding month's Actual, AND the corresponding month one year ago's Actual,
in one table (see excel_extractors/pdf_extractor_asp.py's module docstring
and its new parse_fl_last_year_column()) — e.g. FL25-26 SEPT'25.pdf's own
"SEPT'24" column gives Sept 2024 numbers directly, no FY24-25 file needed.
Because FY24-25's own March report isn't one of the 11 files below, March
2025 is only ever reachable as some FY25-26 file's "previous month" column
(April'25's), a different code path (_parse_fl_two_month, already covered
by the normal monthly-upload flow) — not this script's job.

Source files: D:\\opr-mis1\\Report_format\\MONTHEND\\ASP\\FL25-26 <MON>'25*.pdf
  (April'25 through Feb'26 — 11 files, one per target month; a report month
  is matched by the file's own "DETAILS <MON>'<YY>" header, not filename
  parsing, so odd naming (JUNE'25f.pdf, FEB'26F.pdf, JAN'26PROV.pdf, the
  double-extension AUG'25.pdff.pdf) doesn't matter. One true duplicate exists
  ("sept'25.pdf" and "sept'25 (1).pdf" — confirmed byte-for-byte identical
  extracted values) — only the plain-named copy is read.

Items extracted (same set _parse_fl_two_month already writes for the normal
monthly upload — see that function's item map): Ingot Steel, Total Caster,
Total Crude Steel, Ingot Semis, Billets, BARS, FS PRD, PLATES, Saleable
Steel, Saleable Steel Despatch, and computed Finished Steel (BARS+FS PRD+
PLATES). No Closing Stock — that's a REP*.pdf-only item, not on the FL
report at all.

Usage:
  python scripts/backfill_asp_fy2425_from_fy2526_fl.py            # dry-run: prints a diff, writes nothing
  python scripts/backfill_asp_fy2425_from_fy2526_fl.py --apply     # actually writes to production_table (live DB)

Dry-run is the default on purpose — this touches the live MySQL DB
(DB_ENGINE=mysql), and the user asked to see every value (new AND any that
disagrees with what's already stored) before anything is written.
"""
import sys
import os
import glob
import argparse

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import db  # noqa: E402
from excel_extractors.pdf_extractor_asp import (  # noqa: E402
    _load_pdf_word_rows, _detect_fl_report_month, parse_fl_last_year_column,
)

PLANT = "ASP"
SRC_DIR = os.path.join(BACKEND_DIR, "..", "Report_format", "MONTHEND", "ASP")
SRC_GLOB = os.path.join(SRC_DIR, "FL25-26*.pdf")

# Target range: Apr 2024 - Feb 2025 <=> source report months Apr 2025 - Feb 2026.
TARGET_MIN, TARGET_MAX = "2024-04", "2025-02"


def _collect_source_files():
    """{report_month: file_path} for every FY25-26 FL file whose own
    detected report month's prior-year counterpart falls in the target
    range. Skips the one confirmed duplicate (sept'25 (1).pdf)."""
    by_month = {}
    for f in sorted(glob.glob(SRC_GLOB)):
        base = os.path.basename(f)
        if "(1)" in base:
            continue  # confirmed duplicate of the plain-named file, same month
        try:
            rows, n_pages = _load_pdf_word_rows(f)
            month = _detect_fl_report_month(rows)
        except Exception as exc:
            print(f"  SKIP {base}: {exc}")
            continue
        if month is None:
            print(f"  SKIP {base}: could not detect report month")
            continue
        ly_month = f"{int(month[:4]) - 1}-{month[5:7]}"
        if not (TARGET_MIN <= ly_month <= TARGET_MAX):
            continue
        if month in by_month:
            print(f"  SKIP {base}: duplicate report month {month} "
                  f"(already have {os.path.basename(by_month[month])})")
            continue
        by_month[month] = f
    return by_month


def current_db_values(months):
    conn = db.connect()
    cur = conn.cursor()
    ph = ",".join("?" * len(months))
    cur.execute(
        f"SELECT report_month, item_name, month_actual FROM production_table "
        f"WHERE plant_name=? AND report_month IN ({ph})",
        (PLANT, *months),
    )
    out = {(m, item): val for m, item, val in cur.fetchall()}
    conn.close()
    return out


def upsert(report_month, item_name, value):
    conn = db.connect()
    conn.execute("""
        INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(report_month, plant_name, item_name)
        DO UPDATE SET month_actual = excluded.month_actual
    """, (report_month, PLANT, item_name, value))
    conn.commit()
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write to the DB (default: dry-run)")
    args = ap.parse_args()

    print("Scanning source files...")
    by_month = _collect_source_files()
    print(f"\nMatched {len(by_month)} source file(s) for report months "
          f"{sorted(by_month)[:1]}..{sorted(by_month)[-1:]}:")
    for m, f in sorted(by_month.items()):
        print(f"  {m} <- {os.path.basename(f)}")

    all_rows = []  # (ly_month, item_name, value)
    for report_month, f in sorted(by_month.items()):
        rows, n_pages = _load_pdf_word_rows(f)
        parsed = parse_fl_last_year_column(rows, report_month, n_pages)
        for r in parsed:
            if r["status"] == "ok" and r["value"] is not None:
                all_rows.append((r["report_month"], r["item_name"], r["value"]))

    months = sorted({m for m, _, _ in all_rows})
    print(f"\nExtracted {len(all_rows)} (month, item) values across "
          f"{len(months)} months ({months[0] if months else '-'}..{months[-1] if months else '-'}).\n")

    cur_vals = current_db_values(months)

    new_count = changed_count = same_count = 0
    for ly_month, item_name, new_val in sorted(all_rows, key=lambda r: (r[0], r[1])):
        old_val = cur_vals.get((ly_month, item_name))
        if old_val is None:
            new_count += 1
            print(f"  {ly_month}  {item_name:24s}  {'—':>10s} -> {new_val:<10}  [new]")
        elif round(float(old_val), 3) != round(float(new_val), 3):
            changed_count += 1
            print(f"  {ly_month}  {item_name:24s}  {old_val!s:>10s} -> {new_val:<10}  [DIFFERS FROM DB]")
        else:
            same_count += 1

    print(f"\n{new_count} new, {changed_count} differ from current DB, "
          f"{same_count} already match ({len(all_rows)} total).")

    if not args.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply to write.")
        return

    for ly_month, item_name, val in all_rows:
        upsert(ly_month, item_name, val)
    print(f"\nAPPLIED — {len(all_rows)} value(s) written to production_table.")


if __name__ == "__main__":
    main()
