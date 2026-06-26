"""
Techno parameter group restructuring migration.

Migrates from data-duplication model (MAJOR stores plant-level, IRON_MAKING stores
separate Plant Shop entries) to single-source-of-truth model where params are linked
to multiple groups via techno_param_group many-to-many table.

Phases:
  A. Link MAJOR BF params to IRON_MAKING (non-destructive)
  B. Remove duplicate Plant Shop entries from IRON_MAKING
  C. Create GENERAL group (Specific Energy Consumption)
  D. Create MILLS group (all mill params)
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "mis_reports.db")

# The 8 BF parameters that should be shared between MAJOR and IRON_MAKING
BF_PARAMS = [
    "Coal to Hot Metal",
    "Coke Rate",
    "Nut Coke Rate",
    "CDI Rate",
    "Fuel Rate",
    "Sinter in Burden",
    "Pellet in Burden",
    "BF Productivity",
]

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=" * 70)
print("Techno Parameter Group Restructuring Migration")
print("=" * 70)

# Phase A: Link MAJOR BF params to IRON_MAKING
print("\nPhase A: Linking MAJOR BF params to IRON_MAKING group...")
linked_count = 0
for param_name in BF_PARAMS:
    for plant in PLANTS:
        cur.execute("""
            SELECT p.param_id FROM techno_param p
            WHERE p.param_name = ? AND p.row_label = ?
        """, (param_name, plant))
        row = cur.fetchone()
        if row:
            param_id = row[0]
            # Check if already linked to IRON_MAKING
            cur.execute("""
                SELECT COUNT(*) FROM techno_param_group
                WHERE param_id = ? AND group_code = 'IRON_MAKING'
            """, (param_id,))
            if cur.fetchone()[0] == 0:
                # Not linked yet - add it
                cur.execute("""
                    INSERT INTO techno_param_group (param_id, group_code, sort_order)
                    VALUES (?, 'IRON_MAKING', 0)
                """, (param_id,))
                linked_count += 1
                print(f"  + Linked {param_name:30} | {plant:10} to IRON_MAKING")

conn.commit()
print(f"\nLinked {linked_count} params to IRON_MAKING group.")

# Phase B: Find and remove duplicate Plant Shop entries
print("\nPhase B: Removing duplicate Plant Shop entries...")

# Find all Plant Shop params in IRON_MAKING that have canonical plant-level params in MAJOR
plant_shops = ["BSP Plant Shop", "DSP Plant Shop", "RSP Plant Shop",
               "BSL Plant Shop", "ISP Plant Shop"]

removed_count = 0
for param_name in BF_PARAMS:
    for plant_shop in plant_shops:
        plant = plant_shop.split()[0]  # e.g. "BSP" from "BSP Plant Shop"

        # Find the Plant Shop param
        cur.execute("""
            SELECT p.param_id FROM techno_param p
            WHERE p.param_name = ? AND p.row_label = ?
        """, (param_name, plant_shop))
        ps_row = cur.fetchone()
        if not ps_row:
            continue
        ps_param_id = ps_row[0]

        # Find the canonical plant-level param
        cur.execute("""
            SELECT p.param_id FROM techno_param p
            WHERE p.param_name = ? AND p.row_label = ?
        """, (param_name, plant))
        pl_row = cur.fetchone()
        if not pl_row:
            continue
        pl_param_id = pl_row[0]

        # Migrate any actuals from Plant Shop → plant-level
        cur.execute("""
            INSERT OR IGNORE INTO techno_actuals (report_month, param_id, actual, till_month_actual, source)
            SELECT report_month, ?, actual, till_month_actual, source
            FROM techno_actuals WHERE param_id = ?
        """, (pl_param_id, ps_param_id))
        conn.commit()

        # Delete Plant Shop from IRON_MAKING group
        cur.execute("""
            DELETE FROM techno_param_group
            WHERE param_id = ? AND group_code = 'IRON_MAKING'
        """, (ps_param_id,))

        # Check if Plant Shop param has any other group memberships
        cur.execute("""
            SELECT COUNT(*) FROM techno_param_group WHERE param_id = ?
        """, (ps_param_id,))
        if cur.fetchone()[0] == 0:
            # No other groups - delete the param itself
            cur.execute("DELETE FROM techno_param WHERE param_id = ?", (ps_param_id,))
            print(f"  - Removed {param_name:30} | {plant_shop:20}")
            removed_count += 1

conn.commit()
print(f"\nRemoved {removed_count} duplicate Plant Shop entries.")

# Phase C: Create GENERAL group
print("\nPhase C: Creating GENERAL group...")
cur.execute("""
    INSERT OR IGNORE INTO techno_param_group (param_id, group_code, sort_order)
    SELECT param_id, 'GENERAL', 0 FROM techno_param
    WHERE param_name = 'Specific Energy Consumption'
""")
conn.commit()

cur.execute("SELECT COUNT(*) FROM techno_param_group WHERE group_code = 'GENERAL'")
general_count = cur.fetchone()[0]
print(f"  + Created GENERAL group with {general_count} params")

# Phase D: Create MILLS group
print("\nPhase D: Creating MILLS group (combines all MILL_* params)...")
cur.execute("""
    INSERT OR IGNORE INTO techno_param_group (param_id, group_code, sort_order)
    SELECT param_id, 'MILLS', sort_order FROM techno_param_group
    WHERE group_code LIKE 'MILL_%'
""")
conn.commit()

cur.execute("SELECT COUNT(*) FROM techno_param_group WHERE group_code = 'MILLS'")
mills_count = cur.fetchone()[0]
print(f"  + Created MILLS group with {mills_count} params")

# Summary
print("\n" + "=" * 70)
print("Summary:")
print("=" * 70)
cur.execute("""
    SELECT group_code, COUNT(*) as cnt FROM techno_param_group
    GROUP BY group_code ORDER BY group_code
""")
for group_code, cnt in cur.fetchall():
    print(f"  {group_code:20} : {cnt:4} params")

conn.close()
print("\n[OK] Migration complete!")
