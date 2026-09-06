"""
One-off backfill: BSP Saleable Steel Despatch / Semis Despatch / Road
Despatch, from every "BSP PPC MIS_<Month><Year>.xls[x]" month-end report on
disk, per direct instruction.

Each file is BSP's own month-end PPC MIS report (sheet S1) — the same
report shape excel_extractor_bsp.py's extract_preview() already routes to
_extract_ppc_mis_preview() for (detected by the presence of an "S1" sheet).
This script just calls that same preview function file-by-file and pulls
out the 3 despatch items from its production_rows, exactly the same
extraction the ongoing single-month upload flow uses (Section
"BSP PPC MIS despatch items" in excel_extractor_bsp.py, immediately after
_resolve_ppc_mis_cells).

Confirmed present (via _resolve_bsp_despatch_cells's own "DESPATCH" section
+ double-"Cuml"-header search, tolerant of the row drift already seen
between report eras) from some point in the report's history onward;
confirmed ABSENT / different incompatible layout on older files (e.g. "BSP
PPC MIS_Apr'16.xls", "BSP PPC MIS_Jun'12.xls" — a "DESPATCHES" section
exists but not in the "Total Semis"/"Saleable Steel" + Cuml-columns shape
this reads) — those are skipped gracefully (no despatch rows), not guessed.

Usage:
  python scripts/backfill_bsp_despatch_history.py            # dry-run
  python scripts/backfill_bsp_despatch_history.py --apply     # writes to the live DB

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
import excel_extractor_bsp as bsp  # noqa: E402

PLANT = "BSP"
ARCHIVE_DIR = r"G:\My Drive\Report_format\MONTHEND\BSP"
DESPATCH_ITEMS = ("Saleable Steel Despatch", "Semis Despatch", "Road Despatch")


def extract_file(fname: str):
    path = os.path.join(ARCHIVE_DIR, fname)
    result = bsp.extract_preview(path, None)
    vals = {r["item_name"]: r["value"]
            for r in result["production_rows"]
            if r["item_name"] in DESPATCH_ITEMS and r["status"] == "ok" and r["value"] is not None}
    return result["month"], vals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    files = sorted(f for f in os.listdir(ARCHIVE_DIR)
                   if "PPC MIS" in f.upper() and f.lower().endswith((".xls", ".xlsx", ".xlsm")))
    all_months = {}
    errors = []

    for fname in files:
        try:
            report_month, vals = extract_file(fname)
        except Exception as exc:
            errors.append((fname, str(exc)))
            continue
        if report_month == "unknown":
            errors.append((fname, "could not determine report month"))
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
