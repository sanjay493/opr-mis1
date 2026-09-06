"""
One-off backfill: BSP Semis breakdown — "CC SLAB"/"CC BILLET"/"CC BLOOM"
(displayed as "SEMIS SLABS"/"SEMIS BilletS"/"SEMIS BLOOM" everywhere that
reads through main.py's normalize_item_name — see that function's BSP
branch, added because these 3 items were landing on separate rows from
their own ABP plan figures on both the Production Data Entry page and
/api/production-fy) — from every "BSP PPC MIS_<Month><Year>.xls[x]"
month-end report on disk, per direct instruction.

These 3 items are already extracted by the SAME resolver
(_resolve_ppc_mis_cells, in excel_extractor_bsp.py) that BSP's daily/
month-end upload flow always has — this script just calls
excel_extractor_bsp.extract_preview() file-by-file (identical pattern to
backfill_bsp_despatch_history.py) and pulls out these 3 items instead of
the despatch ones. Written to the DB under their raw extractor names ("CC
SLAB"/"CC BILLET"/"CC BLOOM"), NOT the normalized "SEMIS ..." names — this
matches what the live daily-upload path (extract_and_save_excel) already
writes going forward, and what page_jpc_report.py's Pmix report queries
directly (raw SQL, no normalization) — writing under "SEMIS ..." instead
would make this historical backfill invisible to that report.

Usage:
  python scripts/backfill_bsp_semis_breakdown_history.py            # dry-run
  python scripts/backfill_bsp_semis_breakdown_history.py --apply     # writes to the live DB

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
SEMIS_ITEMS = ("CC SLAB", "CC BILLET", "CC BLOOM")


def extract_file(fname: str):
    path = os.path.join(ARCHIVE_DIR, fname)
    result = bsp.extract_preview(path, None)
    vals = {r["item_name"]: r["value"]
            for r in result["production_rows"]
            if r["item_name"] in SEMIS_ITEMS and r["status"] == "ok" and r["value"] is not None}
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
        print(f"{report_month} ({fname}): {parts or '(no semis-breakdown items found)'}")
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
