#!/usr/bin/env python3
import sqlite3
import json

DB_PATH = "mis_reports.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=" * 80)
print("STEP 1: Find quoted/duplicate SMS entries")
print("=" * 80)

# Find entries with quotes
cur.execute("""
    SELECT plant_name, item_name, report_month, month_actual
    FROM production_plan_table
    WHERE (item_name LIKE '%' || char(39) || '%' OR item_name LIKE '% ')
      AND item_name LIKE '%SMS%'
      AND report_month >= '2026-04'
      AND report_month <= '2027-03'
    ORDER BY plant_name, item_name, report_month
""")

quoted_entries = cur.fetchall()
print(f"Found {len(quoted_entries)} entries with quotes/trailing spaces:")
for row in quoted_entries:
    print(f"  {row[0]} | '{row[1]}' | {row[2]} | {row[3]}")

print("\n" + "=" * 80)
print("STEP 2: Delete quoted/duplicate entries")
print("=" * 80)

cur.execute("""
    DELETE FROM production_plan_table
    WHERE (item_name LIKE '%' || char(39) || '%' OR item_name LIKE '% ')
      AND item_name LIKE '%SMS%'
      AND report_month >= '2026-04'
      AND report_month <= '2027-03'
""")

print(f"Deleted {cur.rowcount} rows")

print("\n" + "=" * 80)
print("STEP 3: Show remaining SMS-wise production data (cleaned)")
print("=" * 80)

cur.execute("""
    SELECT plant_name, item_name, SUM(month_actual) as annual_total
    FROM production_plan_table
    WHERE item_name LIKE '%SMS%'
      AND report_month >= '2026-04'
      AND report_month <= '2027-03'
    GROUP BY plant_name, item_name
    ORDER BY plant_name, item_name
""")

print("\nCleaned SMS Production Data:")
print("-" * 80)
sms_data = {}
for row in cur.fetchall():
    plant, item, total = row
    print(f"{plant:8} | {item:30} | {total:12,.1f}")

    # Extract shop name (e.g., "BSP SMS-2" from "BSP SMS-2 SLAB")
    parts = item.split()
    if len(parts) >= 2:
        shop_key = f"{parts[0]} {parts[1]}"  # e.g., "BSP SMS-2"
        if plant not in sms_data:
            sms_data[plant] = {}
        if shop_key not in sms_data[plant]:
            sms_data[plant][shop_key] = 0
        sms_data[plant][shop_key] += total

print("\n" + "=" * 80)
print("STEP 4: SMS-wise production totals (sum of all product types)")
print("=" * 80)

for plant in sorted(sms_data.keys()):
    print(f"\n{plant}:")
    for shop in sorted(sms_data[plant].keys()):
        print(f"  {shop:15} | {sms_data[plant][shop]:12,.1f}")

conn.commit()
conn.close()

print("\n" + "=" * 80)
print("✓ Cleanup complete!")
print("=" * 80)
