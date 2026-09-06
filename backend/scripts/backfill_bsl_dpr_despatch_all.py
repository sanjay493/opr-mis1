"""
One-off backfill: BSL "Saleable Steel Despatch"/"Semis Despatch" from every
DPR Mail Excel report on disk at G:\\My Drive\\Report_format\\MONTHEND\\BSL\\
(both the "DPR Mail_<date>.xlsx" and "BSL-DPR<date>.xlsx"/"BSL_DPR_<date>.
xlsx" naming families), per direct instruction.

These 2 items are already extracted by excel_extractor_bsl.py's DPR route
(_DPR_LABELS' "SAL.STEEL"/"SLAB" rows in the DESPATCH table, added earlier
this session) — this script just calls extract_preview() on every DPR file
already on disk and writes the 2 despatch items, same pattern as every
other backfill script this session.

When more than one DPR file exists for the same report month (a mid-month
upload alongside a later month-end one, or a revised "_Rev" file), the file
whose own report date is CLOSEST TO / AT month-end wins — a mid-month
figure is a month-to-date-projected estimate, less reliable than a true
month-end read of the same month (same precedent as
backfill_bsl_despatch_more_history.py's own DPR-file selection).

Usage:
  python scripts/backfill_bsl_dpr_despatch_all.py            # dry-run
  python scripts/backfill_bsl_dpr_despatch_all.py --apply     # writes to the live DB

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
import excel_extractor_bsl as bsl  # noqa: E402

PLANT = "BSL"
ARCHIVE_DIR = r"G:\My Drive\Report_format\MONTHEND\BSL"
TARGET_ITEMS = ("Saleable Steel Despatch", "Semis Despatch")


def _iter_dpr_files():
    for fn in sorted(os.listdir(ARCHIVE_DIR)):
        low = fn.lower()
        if not low.endswith((".xlsx", ".xls")):
            continue
        if "dpr" in low:
            yield os.path.join(ARCHIVE_DIR, fn)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    # report_month -> (values_dict, completeness, source_desc)
    # completeness = report_day if a true month-end file, else -1 * (days_in_month - report_day)
    # (higher completeness = closer to / at month-end = preferred)
    best = {}
    errors = []

    for path in _iter_dpr_files():
        fname = os.path.basename(path)
        try:
            result = bsl.extract_preview(path, None)
        except Exception as exc:
            errors.append((fname, str(exc)))
            continue

        report_month = result.get("month")
        if not report_month:
            errors.append((fname, "could not determine report month"))
            continue

        vals = {r["item_name"]: r["value"] for r in result.get("production_rows", [])
                if r["item_name"] in TARGET_ITEMS and r["status"] == "ok" and r["value"] is not None}
        if not vals:
            continue

        report_day = result.get("morning_report_day")
        days_in_month = result.get("morning_days_in_month")
        is_month_end = result.get("morning_is_month_end")
        if is_month_end:
            completeness = 1000 + (report_day or 0)
        else:
            completeness = report_day or 0

        prev = best.get(report_month)
        if prev is None or completeness > prev[1]:
            best[report_month] = (vals, completeness, fname)

    if errors:
        print("--- Files that raised errors (skipped) ---")
        for fname, msg in errors:
            print(f"  {fname}: {msg}")
        print()

    for report_month in sorted(best):
        vals, _completeness, fname = best[report_month]
        parts = "   ".join(f"{k}={v:,.3f} '000T" for k, v in vals.items())
        print(f"{report_month} ({fname}): {parts}")

    total_vals = sum(len(v) for v, _, _ in best.values())
    print(f"\n{total_vals} values across {len(best)} months.")

    if not args.apply:
        print("Dry-run only — nothing written. Re-run with --apply to save.")
        return

    conn = db.connect()
    cur = conn.cursor()
    saved = 0
    try:
        for report_month, (vals, _completeness, _fname) in best.items():
            for item_name, value in vals.items():
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
