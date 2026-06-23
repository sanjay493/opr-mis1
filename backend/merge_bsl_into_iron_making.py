"""
Merge BSL group into IRON_MAKING group.

This consolidates the separate "Iron Making — BSL Furnaces" group into
"Iron Making — Blast Furnace" since IRON_MAKING already covers all furnaces
including BSL.

Operations:
  1. Link all BSL-only params to IRON_MAKING group
  2. Remove BSL group from techno_param_group
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "mis_reports.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=" * 70)
print("Merge BSL Group into IRON_MAKING")
print("=" * 70)

# Get all params currently in BSL group
cur.execute("SELECT DISTINCT param_id FROM techno_param_group WHERE group_code='BSL'")
bsl_param_ids = [row[0] for row in cur.fetchall()]

print(f"\nPhase 1: Linking {len(bsl_param_ids)} BSL params to IRON_MAKING...")

linked_count = 0
already_linked = 0

for param_id in bsl_param_ids:
    # Check if already in IRON_MAKING
    cur.execute("""
        SELECT COUNT(*) FROM techno_param_group
        WHERE param_id = ? AND group_code = 'IRON_MAKING'
    """, (param_id,))

    if cur.fetchone()[0] == 0:
        # Not in IRON_MAKING - add it
        cur.execute("""
            INSERT INTO techno_param_group (param_id, group_code, sort_order)
            VALUES (?, 'IRON_MAKING', 0)
        """, (param_id,))
        linked_count += 1
    else:
        already_linked += 1

conn.commit()

print(f"  + Linked {linked_count} params to IRON_MAKING")
print(f"  + {already_linked} params already in IRON_MAKING")

# Phase 2: Remove BSL group
print("\nPhase 2: Removing BSL group from techno_param_group...")

cur.execute("DELETE FROM techno_param_group WHERE group_code='BSL'")
conn.commit()

deleted_count = cur.rowcount
print(f"  - Removed {deleted_count} BSL group memberships")

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

print("\n[OK] BSL group successfully merged into IRON_MAKING!")
print("\nRemaining tasks:")
print("  1. Update backend/main.py - remove 'BSL' from _GROUP_META")
print("  2. Update frontend/src/app/data-entry/techno/page.js - remove from FALLBACK_GROUPS")
print("  3. Update documentation files")
