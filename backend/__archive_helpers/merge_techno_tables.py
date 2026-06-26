"""
Merge techno_monthly + techno_param_master → techno_table (single unified table).

Handles all group_code types with correct plant_name / parameter_name mapping:
  MAJOR        : plant = row_label,  parameter = section
  COKE_SINTER  : plant = row_label,  parameter = section
  IRON_MAKING  : plant = row_label,  parameter = section
  SMS          : plant = row_label,  parameter = section
  BSL          : plant = "BSL " + section, parameter = row_label
  MILL_*       : plant = "PLANT MILL: " + section, parameter = row_label

Conflict rule: existing techno_table rows are kept unchanged (DO NOTHING).
Re-run safely — already-merged rows are skipped.

Usage (run from h:/opr-mis1/backend):
    python merge_techno_tables.py [--dry-run]
"""

import os
import sys
import sqlite3

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB  = os.path.join(_SCRIPT_DIR, "mis_reports.db")

# group_codes where section=parameter, row_label=plant
FLAT_GROUPS = {"MAJOR", "COKE_SINTER", "IRON_MAKING", "SMS"}


def extract_plant_from_group(group_code: str) -> str:
    """'MILL_BSP' -> 'BSP',  'MILL_RSP' -> 'RSP'"""
    return group_code.replace("MILL_", "")


def build_merged_rows(cur) -> list:
    """
    Join techno_monthly with techno_param_master and return
    list of (report_month, plant_name, parameter_name, unit, actual, cum_actual).
    """
    cur.execute("""
        SELECT
            tm.report_month,
            pm.group_code,
            pm.section,
            pm.row_label,
            pm.unit,
            tm.actual,
            tm.cum_actual
        FROM techno_monthly tm
        JOIN techno_param_master pm ON tm.param_id = pm.param_id
        ORDER BY pm.group_code, pm.section, pm.row_label, tm.report_month
    """)
    rows = cur.fetchall()

    result = []
    for report_month, group_code, section, row_label, unit, actual, cum_actual in rows:
        if actual is None:
            continue

        if group_code in FLAT_GROUPS:
            plant_name     = row_label.strip()
            parameter_name = section.strip()
        elif group_code == "BSL":
            plant_name     = f"BSL {section.strip()}"
            parameter_name = row_label.strip()
        elif group_code.startswith("MILL_"):
            plant          = extract_plant_from_group(group_code)
            plant_name     = f"{plant} {section.strip()}"
            parameter_name = row_label.strip()
        else:
            # Unknown group — skip
            continue

        if not plant_name or not parameter_name:
            continue

        result.append((report_month, plant_name, parameter_name,
                        unit or "", actual, cum_actual))
    return result


def main():
    dry_run = "--dry-run" in sys.argv

    print(f"DB   : {_DEFAULT_DB}")
    print(f"Mode : {'DRY RUN (no writes)' if dry_run else 'LIVE MERGE'}")
    print()

    conn = sqlite3.connect(_DEFAULT_DB)
    cur  = conn.cursor()

    # ── Before state ─────────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM techno_table")
    before_count = cur.fetchone()[0]
    print(f"techno_table rows BEFORE merge : {before_count}")

    cur.execute("SELECT COUNT(*) FROM techno_monthly")
    monthly_count = cur.fetchone()[0]
    print(f"techno_monthly rows to process : {monthly_count}")
    print()

    # ── Build rows ────────────────────────────────────────────────────────────
    rows = build_merged_rows(cur)
    print(f"Rows extracted from techno_monthly : {len(rows)}")

    # ── Check for duplicates within the source itself ─────────────────────────
    seen   = {}
    unique = []
    dupes  = 0
    for r in rows:
        key = (r[0], r[1], r[2])   # report_month, plant, parameter
        if key in seen:
            dupes += 1
        else:
            seen[key] = True
            unique.append(r)
    print(f"Duplicate keys within source    : {dupes}  (kept first occurrence)")
    print(f"Unique rows to insert           : {len(unique)}")

    if dry_run:
        print()
        print("Sample (first 40 rows):")
        print(f"{'report_month':<13} {'plant':<25} {'parameter':<35} {'unit':<12} {'actual':<12} {'ytd'}")
        print("-" * 110)
        for r in unique[:40]:
            print(f"{r[0]:<13} {r[1]:<25} {r[2]:<35} {str(r[3]):<12} {str(r[4]):<12} {r[5]}")
        if len(unique) > 40:
            print(f"  ... and {len(unique) - 40} more rows")

        # Show how many would conflict vs new
        cur.execute("SELECT report_month, plant_name, parameter_name FROM techno_table")
        existing = set(cur.fetchall())
        new_rows      = sum(1 for r in unique if (r[0], r[1], r[2]) not in existing)
        conflict_rows = len(unique) - new_rows
        print()
        print(f"Would insert (new)     : {new_rows}")
        print(f"Would skip (duplicate) : {conflict_rows}")
        conn.close()
        return

    # ── Insert ────────────────────────────────────────────────────────────────
    inserted = skipped = 0
    cur.execute("SELECT report_month, plant_name, parameter_name FROM techno_table")
    existing = set(cur.fetchall())

    for report_month, plant_name, parameter_name, unit, actual, cum_actual in unique:
        if (report_month, plant_name, parameter_name) in existing:
            skipped += 1
            continue
        cur.execute("""
            INSERT OR IGNORE INTO techno_table
                (report_month, plant_name, parameter_name, unit, month_actual, ytd_actual)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (report_month, plant_name, parameter_name, unit, actual, cum_actual))
        inserted += 1

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM techno_table")
    after_count = cur.fetchone()[0]
    conn.close()

    print()
    print(f"Inserted (new rows)     : {inserted}")
    print(f"Skipped (already exist) : {skipped}")
    print()
    print(f"techno_table rows BEFORE : {before_count}")
    print(f"techno_table rows AFTER  : {after_count}")
    print(f"Net new rows added       : {after_count - before_count}")


if __name__ == "__main__":
    main()
