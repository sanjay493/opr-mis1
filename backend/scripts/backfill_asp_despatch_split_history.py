"""
One-off backfill: ASP "Finished Despatch" (BAR + FORG. + PLT, DESPATCH
section) and "Semis Despatch" (Saleable Steel Despatch - Finished
Despatch) — two new items added to excel_extractors/pdf_extractor_asp.py's
_parse_fl_two_month/parse_fl_last_year_column, per direct instruction
mirroring the existing Finished Steel = BARS+FS PRD+PL MILL pattern one
section over (Saleable Production -> DESPATCH).

Since these are computed inside the SAME two parsing functions every other
ASP FL item already goes through, every FL*.pdf file on disk is re-read
once and every month it can reach (its own report month, its previous
month, AND its "last year same month"/CPLY column) is captured — three
routes per file, giving the widest possible backfill from files already
on disk without needing a dedicated source per FY the way the older
BSL/RSP/ISP despatch backfills needed. Only "Finished Despatch"/"Semis
Despatch" are written here — every other FL item already has complete
history from the pre-existing backfill_asp_legacy_fl_excel.py (FY20-21
through FY23-24) and backfill_asp_fy2425_from_fy2526_fl.py (FY24-25)
scripts, so re-writing them here would be redundant (though harmless,
since the values would be identical) — kept out of scope to avoid
touching data outside what was actually asked for.

Where two files could reach the same month via different routes (e.g. a
report month is directly APR'26.pdf's own "report month" AND MAY'26.pdf's
"previous month"), the more direct route wins — own report month >
previous month (one file removed) > CPLY column (a full year removed,
most likely to accumulate rounding/layout drift) — enforced by only ever
recording a month once, first source wins, sources visited in that
priority order.

Confirmed FY20-21..FY23-24 (the legacy .xls-sourced years) are NOT
reachable this way — those workbooks are a different file format read by
a different extractor entirely (backfill_asp_legacy_fl_excel.py), which
does not parse the DESPATCH section's BAR/FORG./PLT rows; extending that
script was out of scope for this pass. Confirmed real, not a bug: FL
report files for those years are not part of this MONTHEND\\ASP archive
at all (only FY25-26 and FY26-27 FL*.pdf files exist there).

Usage:
  python scripts/backfill_asp_despatch_split_history.py            # dry-run
  python scripts/backfill_asp_despatch_split_history.py --apply     # writes to the live DB

Dry-run is the default on purpose — this touches the live MySQL DB
(DB_ENGINE=mysql), so the values should be reviewed before anything is
written.
"""
import sys
import os
import glob
import argparse

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import db  # noqa: E402
from excel_extractors.pdf_extractor_asp import (  # noqa: E402
    _load_pdf_word_rows, _detect_fl_report_month, _fl_prev_month,
    _parse_fl_two_month, parse_fl_last_year_column,
)

PLANT = "ASP"
ARCHIVE_DIR = r"G:\My Drive\Report_format\MONTHEND\ASP"
TARGET_ITEMS = ("Finished Despatch", "Semis Despatch")

# Known duplicate files (byte-for-byte identical to the plain-named copy,
# confirmed by backfill_asp_fy2425_from_fy2526_fl.py's own module docstring
# for the first; the 2nd follows the exact same "<name>FINAL.pdf" pattern).
_SKIP_SUBSTRINGS = ["(1)", "FINAL.pdf"]


def _iter_source_files():
    for f in sorted(glob.glob(os.path.join(ARCHIVE_DIR, "FL*.pdf")) +
                     glob.glob(os.path.join(ARCHIVE_DIR, "fl*.pdf"))):
        base = os.path.basename(f)
        if any(s in base for s in _SKIP_SUBSTRINGS):
            continue
        yield f


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    # (report_month, item_name) -> (value, source_desc)
    claimed = {}
    errors = []

    def _claim(report_month, item_name, value, source_desc):
        key = (report_month, item_name)
        if key in claimed:
            return  # already claimed by a higher-priority (more direct) route
        claimed[key] = (value, source_desc)

    files = list(_iter_source_files())

    # Pass 1 (highest priority): each file's OWN report month.
    file_info = {}  # path -> (rows, n_pages, report_month)
    for f in files:
        base = os.path.basename(f)
        try:
            rows, n_pages = _load_pdf_word_rows(f)
            report_month = _detect_fl_report_month(rows)
        except Exception as exc:
            errors.append((base, str(exc)))
            continue
        if report_month is None:
            errors.append((base, "could not detect report month"))
            continue
        file_info[f] = (rows, n_pages, report_month)

        try:
            prev_month = _fl_prev_month(report_month)
            two_month_rows = _parse_fl_two_month(rows, report_month, prev_month, n_pages)
        except Exception as exc:
            errors.append((base, f"_parse_fl_two_month failed: {exc}"))
            continue
        for r in two_month_rows:
            if r["item_name"] in TARGET_ITEMS and r["status"] == "ok" and r["value"] is not None:
                if r["report_month"] == report_month:
                    _claim(report_month, r["item_name"], r["value"], f"{base} (own report month)")

    # Pass 2: each file's PREVIOUS month (one file removed).
    for f, (rows, n_pages, report_month) in file_info.items():
        base = os.path.basename(f)
        prev_month = _fl_prev_month(report_month)
        try:
            two_month_rows = _parse_fl_two_month(rows, report_month, prev_month, n_pages)
        except Exception as exc:
            continue
        for r in two_month_rows:
            if r["item_name"] in TARGET_ITEMS and r["status"] == "ok" and r["value"] is not None:
                if r["report_month"] == prev_month:
                    _claim(prev_month, r["item_name"], r["value"], f"{base} (previous month)")

    # Pass 3 (lowest priority): each file's "last year same month"/CPLY column.
    for f, (rows, n_pages, report_month) in file_info.items():
        base = os.path.basename(f)
        try:
            ly_rows = parse_fl_last_year_column(rows, report_month, n_pages)
        except Exception as exc:
            errors.append((base, f"parse_fl_last_year_column failed: {exc}"))
            continue
        for r in ly_rows:
            if r["item_name"] in TARGET_ITEMS and r["status"] == "ok" and r["value"] is not None:
                _claim(r["report_month"], r["item_name"], r["value"], f"{base} (CPLY column)")

    if errors:
        print("--- Files that raised errors (skipped) ---")
        for base, msg in errors:
            print(f"  {base}: {msg}")
        print()

    months = sorted({m for m, _ in claimed})
    for m in months:
        fd = claimed.get((m, "Finished Despatch"))
        sd = claimed.get((m, "Semis Despatch"))
        parts = []
        if fd:
            parts.append(f"Finished Despatch={fd[0]:,.3f} '000T [{fd[1]}]")
        if sd:
            parts.append(f"Semis Despatch={sd[0]:,.3f} '000T [{sd[1]}]")
        print(f"{m}: " + "   ".join(parts))

    print(f"\n{len(claimed)} values across {len(months)} months.")

    if not args.apply:
        print("Dry-run only — nothing written. Re-run with --apply to save.")
        return

    conn = db.connect()
    cur = conn.cursor()
    saved = 0
    try:
        for (report_month, item_name), (value, _source) in claimed.items():
            cur.execute("""
                INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, plant_name, item_name)
                DO UPDATE SET month_actual = excluded.month_actual
            """, (report_month, PLANT, item_name, value))
            saved += 1
        conn.commit()
    finally:
        conn.close()

    print(f"\nSaved {saved} values for {PLANT}.")


if __name__ == "__main__":
    main()
