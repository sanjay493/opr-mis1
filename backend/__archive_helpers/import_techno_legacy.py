"""
Import legacy techno data from a CSV into techno_table.

Usage (run from h:/opr-mis1/backend):
    python import_techno_legacy.py --csv PATH [--dry-run]

CSV must have columns:
    report_month, plant_name, parameter_name, unit, month_actual, ytd_actual

report_month format: YYYY-MM  (e.g. 2024-04)
Rows are upserted — existing records are updated, new ones inserted.
"""

import os
import sys
import csv
import sqlite3

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB = os.path.join(_SCRIPT_DIR, "mis_reports.db")

REQUIRED_COLS = {"report_month", "plant_name", "parameter_name", "unit", "month_actual", "ytd_actual"}


def clean_float(val):
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "-", "N/A", "nan", "None"):
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def main():
    dry_run = "--dry-run" in sys.argv
    csv_path = None

    if "--csv" in sys.argv:
        i = sys.argv.index("--csv")
        csv_path = sys.argv[i + 1]

    if not csv_path:
        print("ERROR: Provide the CSV path with --csv PATH")
        print("Example: python import_techno_legacy.py --csv C:/data/techno_legacy.csv")
        sys.exit(1)

    if not os.path.exists(csv_path):
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    print(f"Source : {csv_path}")
    print(f"DB     : {_DEFAULT_DB}")
    print(f"Mode   : {'DRY RUN (no writes)' if dry_run else 'LIVE INSERT'}")
    print()

    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLS - set(reader.fieldnames or [])
        if missing:
            print(f"ERROR: CSV is missing columns: {missing}")
            print(f"Found columns: {reader.fieldnames}")
            sys.exit(1)

        for i, row in enumerate(reader, start=2):
            month_actual = clean_float(row["month_actual"])
            ytd_actual   = clean_float(row["ytd_actual"])
            report_month = row["report_month"].strip()
            plant_name   = row["plant_name"].strip()
            parameter    = row["parameter_name"].strip()
            unit         = row["unit"].strip()

            if not report_month or not plant_name or not parameter:
                print(f"  [SKIP row {i}] missing key field: {row}")
                continue

            rows.append((report_month, plant_name, parameter, unit, month_actual, ytd_actual))

    print(f"Rows parsed: {len(rows)}")

    if dry_run:
        print()
        print(f"{'report_month':<13} {'plant':<8} {'parameter':<35} {'unit':<12} {'actual':<10} {'ytd'}")
        print("-" * 95)
        for r in rows:
            print(f"{r[0]:<13} {r[1]:<8} {r[2]:<35} {r[3]:<12} {str(r[4]):<10} {r[5]}")
        return

    conn = sqlite3.connect(_DEFAULT_DB)
    cur  = conn.cursor()
    inserted = updated = skipped = 0

    for report_month, plant, param, unit, month_actual, ytd_actual in rows:
        cur.execute(
            "SELECT month_actual FROM techno_table "
            "WHERE report_month=? AND plant_name=? AND parameter_name=?",
            (report_month, plant, param),
        )
        existing = cur.fetchone()

        cur.execute("""
            INSERT INTO techno_table (report_month, plant_name, parameter_name, unit, month_actual, ytd_actual)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, parameter_name)
            DO UPDATE SET
                unit         = excluded.unit,
                month_actual = excluded.month_actual,
                ytd_actual   = excluded.ytd_actual
        """, (report_month, plant, param, unit, month_actual, ytd_actual))

        if existing is None:
            inserted += 1
        else:
            updated += 1

    conn.commit()
    conn.close()

    print(f"Inserted : {inserted} new rows")
    print(f"Updated  : {updated} existing rows")
    print(f"Total    : {inserted + updated} rows written to techno_table")


if __name__ == "__main__":
    main()
