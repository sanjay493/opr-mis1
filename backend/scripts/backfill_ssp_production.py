"""
One-off backfill: extract every SSP DPR PDF in the MONTHEND/SSP archive and
merge its production figures into production_table.

Source files:
  C:\\opr-mis1\\Report_format\\MONTHEND\\SSP\\   DPR-DD.MM.YYYY.pdf / DPR_DD.MM.YYYY.pdf

Each file's own report_month is detected from its "REPORT FOR DD/MM/YYYY"
header (the LAST day of the data month — see pdf_extractor_ssp's module
docstring), not from the filename, since the filename carries the issue
date (typically the 1st of the *following* month) rather than the data
month.

Usage:
  python scripts/backfill_ssp_production.py            # dry-run: prints a diff, writes nothing
  python scripts/backfill_ssp_production.py --apply     # actually writes to production_table (live DB)

Dry-run is the default on purpose — this touches the live MySQL DB (DB_ENGINE=mysql), so the
diff should be reviewed before anything is written.
"""
import sys
import os
import glob
import argparse

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "excel_extractors"))

import db  # noqa: E402
from main import normalize_item_name  # noqa: E402
from excel_extractors.pdf_extractor_ssp import (  # noqa: E402
    _load_pdf_text, _detect_month_from_pdf_text, extract_preview,
)

ARCHIVE_DIR = r"C:\opr-mis1\Report_format\MONTHEND\SSP"
PLANT = "SSP"


def extract_file(path):
    """Return (rows, month, error). rows is a list of {item_name, value} for
    'ok' status rows only. error is set (rows/month empty) on any failure,
    including a report whose own header date can't be parsed at all."""
    fname = os.path.basename(path)
    try:
        full_text, _n_pages = _load_pdf_text(path)
        detected_month = _detect_month_from_pdf_text(full_text)
        if not detected_month:
            return [], None, "could not detect report month from PDF header"
        result = extract_preview(path, detected_month)
        rows = [
            {"item_name": r["item_name"], "value": r["value"]}
            for r in result["production_rows"]
            if r["status"] == "ok" and r["value"] is not None
        ]
        return rows, detected_month, None
    except Exception as exc:
        return [], None, str(exc)
    finally:
        pass


def current_db_values():
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT item_name, report_month, month_actual FROM production_table WHERE plant_name=?",
                (PLANT,))
    out = {(item, month): value for item, month, value in cur.fetchall()}
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

    files = sorted(glob.glob(os.path.join(ARCHIVE_DIR, "DPR*.pdf")))
    print(f"Archive: {len(files)} DPR PDF file(s) found.\n")

    # final[(item, report_month)] = (value, source_file)
    final = {}
    errors = []
    months_seen = {}

    for f in files:
        rows, month, err = extract_file(f)
        fname = os.path.basename(f)
        if err:
            errors.append((fname, err))
            continue
        prev = months_seen.get(month)
        if prev:
            print(f"  note: {month} appears in both {prev} and {fname} — {fname} will win (processed later, sorted by filename).")
        months_seen[month] = fname
        for r in rows:
            item = normalize_item_name(r["item_name"], PLANT)
            final[(item, month)] = (r["value"], fname)

    if errors:
        print(f"--- {len(errors)} file(s) failed to extract (skipped) ---")
        for fname, err in errors:
            print(f"  {fname}: {err}")
        print()

    cur_actual = current_db_values()

    print(f"--- production_table (actuals): {len(final)} (item, month) values from {len(months_seen)} month(s) ---")
    changed = 0
    for (item, month), (new_val, source) in sorted(final.items(), key=lambda x: (x[0][1], x[0][0])):
        old_val = cur_actual.get((item, month))
        if old_val is None or round(float(old_val), 3) != round(float(new_val), 3):
            changed += 1
            print(f"  {month}  {item:28s}  {str(old_val):>10s} -> {new_val:<10}  [{source}]")
    print(f"  ({changed} of {len(final)} differ from current DB values)\n")

    if not args.apply:
        print(f"DRY RUN — nothing written. {changed} value(s) would change. Re-run with --apply to write.")
        return

    for (item, month), (val, _src) in final.items():
        upsert(month, item, val)
    print(f"APPLIED — {changed} value(s) written to the DB.")


if __name__ == "__main__":
    main()
