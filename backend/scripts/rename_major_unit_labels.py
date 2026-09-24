"""One-off migration for the 2026-09-24 label-uniformity pass on
page_major_unit_records.py's _UNIT_REGISTRY: major_unit_daily_record's
primary key is (plant_code, unit_label), so renaming a registry label that
already has backfilled Daily data would silently orphan that row (a fresh,
empty row would appear under the new label instead). This renames each
affected row in place, preserving value/record_date/remarks/sort_order.

Run once from backend/: python scripts/rename_major_unit_labels.py
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
]


def main():
    conn = db.connect()
    cur = conn.cursor()
    try:
        for plant_code, old_label, new_label in RENAMES:
            cur.execute(
                "UPDATE major_unit_daily_record SET unit_label = ? "
                "WHERE plant_code = ? AND unit_label = ?",
                (new_label, plant_code, old_label),
            )
            print(f"{plant_code}: '{old_label}' -> '{new_label}' "
                  f"({cur.rowcount} row(s))")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
