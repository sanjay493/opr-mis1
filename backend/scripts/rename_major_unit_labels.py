"""One-off migration for the 2026-09-24 label-uniformity pass on
page_major_unit_records.py's _UNIT_REGISTRY: major_unit_daily_record's
primary key is (plant_code, unit_label), so renaming a registry label that
already has backfilled Daily data would silently orphan that row (a fresh,
empty row would appear under the new label instead). This renames each
affected row in place, preserving value/record_date/remarks/sort_order.
Safe to re-run — skips a plant/label already renamed, and skips (reporting)
a case where rows now exist under BOTH the old and new label (e.g. an
editor saved the /data-entry/major-unit-daily form under the new label
before this script got a chance to migrate the old one) rather than
guessing which one to keep.

Run from backend/: python scripts/rename_major_unit_labels.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

# (plant_code, old_label, new_label)
RENAMES = [
    ("BSL", "Oven Pushing", "Equiv. Oven Pushing"),
    ("BSP", "Eq. Oven Pushing", "Equiv. Oven Pushing"),
    ("BSP", "Total Finished Steel", "Finished Steel"),
    ("BSP", "Total Saleable Steel", "Saleable Steel"),
    ("ISP", "Oven Pushing", "Equiv. Oven Pushing"),
    ("ISP", "Sinter", "Total Sinter"),
    ("ISP", "Hot Metal", "Total Hot Metal"),
    ("ISP", "Crude Steel", "Total Crude Steel"),
    ("ISP", "FIN. STEEL", "Finished Steel"),
    ("ISP", "Saleable Steel loading", "Saleable Steel Despatch"),
    ("RSP", "Eqvt. Oven Pushing", "Equiv. Oven Pushing"),
    ("RSP", "Sinter - Total", "Total Sinter"),
    ("RSP", "Hot Metal", "Total Hot Metal"),
    ("RSP", "Crude Steel - Total", "Total Crude Steel"),
    ("RSP", "HR Coils prod. HSM-2", "HSM-2"),
    ("RSP", "PM Plates prod.", "PM"),
]


def main():
    conn = db.connect()
    cur = conn.cursor()
    try:
        for plant_code, old_label, new_label in RENAMES:
            cur.execute(
                "SELECT value, record_date, updated_by, updated_at "
                "FROM major_unit_daily_record WHERE plant_code = ? AND unit_label = ?",
                (plant_code, new_label),
            )
            existing_new = cur.fetchone()
            if existing_new is not None:
                cur.execute(
                    "SELECT value, record_date, updated_by, updated_at "
                    "FROM major_unit_daily_record WHERE plant_code = ? AND unit_label = ?",
                    (plant_code, old_label),
                )
                existing_old = cur.fetchone()
                if existing_old is None:
                    print(f"{plant_code}: '{new_label}' already renamed, nothing under "
                          f"'{old_label}' left — OK")
                else:
                    print(f"{plant_code}: CONFLICT — both '{old_label}' {existing_old} "
                          f"and '{new_label}' {existing_new} exist. Skipped; resolve by hand.")
                continue
            cur.execute(
                "UPDATE major_unit_daily_record SET unit_label = ? "
                "WHERE plant_code = ? AND unit_label = ?",
                (new_label, plant_code, old_label),
            )
            conn.commit()
            print(f"{plant_code}: '{old_label}' -> '{new_label}' "
                  f"({cur.rowcount} row(s))")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
