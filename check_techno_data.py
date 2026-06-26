#!/usr/bin/env python3
"""Check techno data records in database."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import db
import sqlite3
import json

db.init_db()
conn = sqlite3.connect(db.DB_PATH)
cursor = conn.cursor()

print("=" * 80)
print("TECHNO DATA RECORDS CHECK")
print("=" * 80)

# Check techno furnace data
cursor.execute('SELECT COUNT(*) FROM techno_furnace_data')
furnace_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(DISTINCT plant) FROM techno_furnace_data')
plants_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(DISTINCT report_month) FROM techno_furnace_data')
months_count = cursor.fetchone()[0]

cursor.execute('SELECT DISTINCT plant FROM techno_furnace_data ORDER BY plant')
plants = [r[0] for r in cursor.fetchall()]

cursor.execute('SELECT DISTINCT report_month FROM techno_furnace_data ORDER BY report_month DESC LIMIT 5')
recent_months = [r[0] for r in cursor.fetchall()]

print("\nTECHNO FURNACE DATA")
print("-" * 80)
print(f"Total Records: {furnace_count}")
print(f"Plants: {plants_count} - {plants}")
print(f"Total Months: {months_count}")
print(f"Recent 5 months: {recent_months}")

# Check techno plant data
cursor.execute('SELECT COUNT(*) FROM techno_plant_data')
plant_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(DISTINCT plant) FROM techno_plant_data')
plant_count_plants = cursor.fetchone()[0]

cursor.execute('SELECT DISTINCT plant FROM techno_plant_data ORDER BY plant')
plant_plants = [r[0] for r in cursor.fetchall()]

print("\nTECHNO PLANT DATA (Consolidated)")
print("-" * 80)
print(f"Total Records: {plant_count}")
print(f"Plants: {plant_count_plants} - {plant_plants}")

# Sample a furnace record
cursor.execute('SELECT plant, report_month, furnace FROM techno_furnace_data LIMIT 1')
sample = cursor.fetchone()
if sample:
    plant, month, furnace = sample
    print(f"\nSample Furnace Record: {plant} {furnace} - {month}")
    cursor.execute(
        'SELECT data FROM techno_furnace_data WHERE plant = ? AND report_month = ? AND furnace = ?',
        (plant, month, furnace)
    )
    data_row = cursor.fetchone()
    if data_row:
        data = json.loads(data_row[0])
        print(f"  Parameters: {len(data)} parameters")
        for param_name, param_data in list(data.items())[:5]:
            if isinstance(param_data, dict):
                print(f"    {param_name}: {param_data}")
            else:
                print(f"    {param_name}: {param_data}")

# Sample a plant record
cursor.execute('SELECT plant, report_month FROM techno_plant_data LIMIT 1')
sample_plant = cursor.fetchone()
if sample_plant:
    plant, month = sample_plant
    print(f"\nSample Plant Record: {plant} - {month}")
    cursor.execute(
        'SELECT data FROM techno_plant_data WHERE plant = ? AND report_month = ?',
        (plant, month)
    )
    data_row = cursor.fetchone()
    if data_row:
        data = json.loads(data_row[0])
        print(f"  Parameters: {len(data)} parameters")
        for param_name, param_data in list(data.items())[:5]:
            print(f"    {param_name}: {param_data}")

conn.close()

print("\n" + "=" * 80)
print("API ENDPOINTS FOR TECHNO DATA")
print("=" * 80)
print("""
GET /api/techno-available-data
  Returns: {plants, months_by_plant}
  Example: http://127.0.0.1:8082/api/techno-available-data

GET /api/techno-furnace-data?plant=BSP&report_month=2025-05&furnace=BF-1
  Returns: Furnace-level parameters
  Query params: plant, report_month, furnace (optional)

GET /api/techno-plant-data?plant=BSP&report_month=2025-05
  Returns: Plant-level consolidated parameters
  Query params: plant, report_month

GET /api/techno-sail-consolidated?report_month=2025-05
  Returns: SAIL-wide consolidated parameters
  Query params: report_month

GET /api/techno-furnace-list?plant=BSP&report_month=2025-05
  Returns: List of furnaces with data
  Query params: plant, report_month
""")
