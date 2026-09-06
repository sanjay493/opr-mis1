"""
One-off backfill: DSP Saleable Steel Despatch / Direct Despatch / Semis
Despatch / Semis Export / Finished Export, from every monthly OMI PDF report
on disk, per direct instruction.

Unlike RSP/ISP (growing-FY tables) or BSL (a mix of routes), each DSP
monthly PDF covers exactly its own single report month — one file per
month, no FY-wide backfill shortcut — so this iterates every file in the
archive individually via excel_extractors/pdf_extractor_dsp.py's own
_block_despatch (the same function the ongoing single-month extractor
uses, reached through extract_preview -> Block 1b).

_block_despatch tries two possible source pages, per report vintage (see
pdf_extractor_dsp.py's own module docstring above _block_despatch):
  - "DESPATCH PERFORMANCE : <month>" pivot table — newer reports only
    (confirmed present 2026, confirmed absent 2016 — a report-format
    addition somewhere in between). Each category (Direct/Export/Total)
    already has its own column.
  - "SALEABLE STEEL DESPATCH PERFORMANCE" nested table — present on every
    vintage checked (2016 through 2026). Fixed 24-number-per-row layout,
    cross-checked via the grand-total identity (INTERNAL + IPT_Total +
    EXPORT_Total + CMO_SALES_TOTAL_Total + PLANT_SALES_Total == TOTAL
    SALEABLE STEEL's own Total) before trusting it — see
    _extract_despatch_nested's docstring.

Usage:
  python scripts/backfill_dsp_despatch_history.py            # dry-run
  python scripts/backfill_dsp_despatch_history.py --apply     # writes to the live DB

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

import db  # noqa: E402
import pdf_extractor_dsp as dsp  # noqa: E402

PLANT = "DSP"
ARCHIVE_DIR = r"G:\My Drive\Report_format\Monthly\DSP"


def extract_file(fname: str):
    path = os.path.join(ARCHIVE_DIR, fname)
    report_month = dsp._extract_pdf_report_month(path)
    page_index, page_texts_cache = dsp._scan_page_index(path)
    rows = dsp._block_despatch(path, page_texts_cache)
    vals = {r["item_name"]: r["value"] for r in rows if r["value"] is not None}
    return report_month, vals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    files = sorted(f for f in os.listdir(ARCHIVE_DIR) if f.lower().endswith(".pdf"))
    all_months = {}
    errors = []

    for fname in files:
        try:
            report_month, vals = extract_file(fname)
        except Exception as exc:
            errors.append((fname, str(exc)))
            continue
        parts = "   ".join(f"{k}={v:,.3f} '000T" for k, v in vals.items())
        print(f"{report_month} ({fname}): {parts or '(no despatch items found)'}")
        if vals:
            all_months[report_month] = vals

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
