"""
Sync techno_table from techno_monthly (authoritative source).

The MAJOR techno page reads from techno_monthly.  When techno_table was
populated from the legacy techno.xlsx, INSERT OR IGNORE kept the Excel values
instead of the extractor values, causing the two tables to disagree.

This script overwrites techno_table.month_actual / ytd_actual with
techno_monthly.actual / cum_actual wherever they differ.

Usage (run from h:/opr-mis1/backend):
    python sync_techno_tables.py [--dry-run]
"""

import os
import sys
import sqlite3

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB  = os.path.join(_SCRIPT_DIR, "mis_reports.db")

_FLAT = ("MAJOR", "COKE_SINTER", "IRON_MAKING", "SMS")

_PLANT_SQL = f"""
    CASE
        WHEN pm.group_code IN {_FLAT!r}
            THEN pm.row_label
        WHEN pm.group_code = 'BSL'
            THEN 'BSL ' || pm.section
        WHEN pm.group_code LIKE 'MILL_%'
            THEN replace(pm.group_code,'MILL_','') || ' ' || pm.section
        ELSE NULL
    END
""".replace("('MAJOR', 'COKE_SINTER', 'IRON_MAKING', 'SMS')",
            "('MAJOR','COKE_SINTER','IRON_MAKING','SMS')")

_PARAM_SQL = f"""
    CASE
        WHEN pm.group_code IN ('MAJOR','COKE_SINTER','IRON_MAKING','SMS')
            THEN pm.section
        ELSE pm.row_label
    END
"""


def build_rows(cur):
    """
    Return list of (report_month, plant_name, parameter_name,
                    new_month_actual, new_ytd_actual,
                    old_month_actual, old_ytd_actual)
    for rows where techno_monthly and techno_table disagree.
    """
    cur.execute(f"""
        SELECT
            tm.report_month,
            {_PLANT_SQL}                  AS plant_name,
            {_PARAM_SQL}                  AS parameter_name,
            tm.actual                     AS new_month,
            tm.cum_actual                 AS new_ytd,
            tt.month_actual               AS old_month,
            tt.ytd_actual                 AS old_ytd
        FROM techno_monthly tm
        JOIN techno_param_master pm ON tm.param_id = pm.param_id
        JOIN techno_table tt ON
            tt.report_month   = tm.report_month
            AND tt.plant_name = {_PLANT_SQL}
            AND tt.parameter_name = {_PARAM_SQL}
        WHERE
            (tm.actual IS NOT NULL AND round(tm.actual,6) != round(tt.month_actual,6))
            OR
            (tm.cum_actual IS NOT NULL AND tt.ytd_actual IS NOT NULL
             AND round(tm.cum_actual,6) != round(tt.ytd_actual,6))
        ORDER BY plant_name, parameter_name, tm.report_month
    """)
    return cur.fetchall()


def main():
    dry_run = "--dry-run" in sys.argv

    print(f"DB   : {_DEFAULT_DB}")
    print(f"Mode : {'DRY RUN (no writes)' if dry_run else 'LIVE UPDATE'}")
    print()

    conn = sqlite3.connect(_DEFAULT_DB)
    cur  = conn.cursor()

    rows = build_rows(cur)
    print(f"Conflicting rows found : {len(rows)}")
    print()

    if not rows:
        print("Nothing to sync.")
        conn.close()
        return

    # Summary by plant
    from collections import Counter
    plant_counts = Counter(r[1] for r in rows)
    print("Conflicts by plant:")
    for plant, cnt in sorted(plant_counts.items(), key=lambda x: -x[1]):
        print(f"  {plant:<30} {cnt}")
    print()

    if dry_run:
        print(f"{'Month':<10} {'Plant':<28} {'Parameter':<35} {'old_act':>10} {'new_act':>10} {'old_ytd':>10} {'new_ytd':>10}")
        print("-" * 108)
        for report_month, plant, param, new_m, new_y, old_m, old_y in rows[:60]:
            print(f"{report_month:<10} {plant:<28} {param:<35} "
                  f"{str(round(old_m,3) if old_m else '')!s:>10} "
                  f"{str(round(new_m,3) if new_m else '')!s:>10} "
                  f"{str(round(old_y,3) if old_y else '')!s:>10} "
                  f"{str(round(new_y,3) if new_y else '')!s:>10}")
        if len(rows) > 60:
            print(f"  ... and {len(rows) - 60} more rows")
        conn.close()
        return

    # Apply updates
    updated = 0
    for report_month, plant, param, new_month, new_ytd, _old_m, _old_y in rows:
        cur.execute("""
            UPDATE techno_table
            SET month_actual = COALESCE(?, month_actual),
                ytd_actual   = COALESCE(?, ytd_actual)
            WHERE report_month=? AND plant_name=? AND parameter_name=?
        """, (new_month, new_ytd, report_month, plant, param))
        updated += cur.rowcount

    conn.commit()
    conn.close()

    print(f"Updated : {updated} rows in techno_table")
    print("techno_table is now consistent with techno_monthly.")


if __name__ == "__main__":
    main()
