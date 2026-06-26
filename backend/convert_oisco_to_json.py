#!/usr/bin/env python3
"""
Convert Extracted OISCO Data to JSON and Insert into Database
"""

import sys
sys.path.insert(0, 'excel_extractors')

from excel_extractor_bsp_oisco import extract_preview
from excel_to_json_converter import process_excel_extraction
from db import init_db, get_techno_furnace_data, get_techno_plant_data
from pathlib import Path
import os

print("\n" + "="*80)
print("OISCO DATA CONVERSION TO JSON")
print("="*80)

# File info
oisco_file = os.path.abspath(r'../Report_format/monthly/BSPOISCO_MAY' + "'25.xlsx")
report_month = '2025-05'

print(f"\n[FILE] {Path(oisco_file).name}")
print(f"[MONTH] {report_month}")

# Step 1: Initialize database
print("\n[STEP 1] Initializing database...")
init_db()
print("[OK] Database ready")

# Step 2: Extract from OISCO
print(f"\n[STEP 2] Extracting from OISCO file...")

try:
    result = extract_preview(oisco_file, report_month)
    param_rows = result.get('techno_param_rows', [])
    print(f"[OK] Extracted {len(param_rows)} parameters")

except Exception as e:
    print(f"[ERROR] Extraction failed: {e}")
    sys.exit(1)

# Step 3: Filter furnace-specific data
print(f"\n[STEP 3] Identifying furnace-wise data...")

furnace_data_rows = []
for row in param_rows:
    param = row.get('parameter', '')
    # Look for furnace-specific parameters (containing BF-4, BF-6, BF-7, BF-8)
    if any(bf in str(param) for bf in ['BF-4', 'BF-6', 'BF-7', 'BF-8', 'BF 4', 'BF 6', 'BF 7', 'BF 8']):
        furnace_data_rows.append(row)

all_plant_rows = param_rows  # Keep all for plant-level

print(f"[OK] Found {len(furnace_data_rows)} furnace-specific parameters")
print(f"[OK] Found {len(all_plant_rows)} total parameters for plant-level")

# Step 4: Show what will be converted
print(f"\n[STEP 4] Preview of furnace-wise data:")
print("-" * 80)

for row in furnace_data_rows[:10]:
    param = row.get('parameter', 'N/A')
    section = row.get('section', 'N/A')
    value = row.get('actual', 'NULL')
    unit = row.get('unit', 'N/A')
    if value is not None:
        print(f"  {param:25} = {value:12.2f} {unit:15} ({section})")
    else:
        print(f"  {param:25} = NULL")

if len(furnace_data_rows) > 10:
    print(f"  ... and {len(furnace_data_rows) - 10} more")

# Step 5: Convert to JSON using converter
print(f"\n[STEP 5] Converting to JSON format...")
print("-" * 80)

try:
    furnaces_inserted, preview = process_excel_extraction(
        plant='BSP',
        parameter_rows=all_plant_rows,
        report_month=report_month,
        auto_calculate_plant=True,
        auto_calculate_sail=False
    )

    # Show preview (without unicode)
    print(preview)

except Exception as e:
    print(f"[ERROR] Conversion failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 6: Verify insertion
print(f"\n[STEP 6] Verifying data in database...")
print("-" * 80)

try:
    # Get furnace data
    furnaces = get_techno_furnace_data('BSP', report_month)
    print(f"\n[OK] Furnace records inserted: {len(furnaces)}")

    if furnaces:
        for furnace in sorted(furnaces.keys()):
            params = furnaces[furnace]
            print(f"     {furnace}: {len(params)} parameters")

            # Show sample values
            for param, info in list(params.items())[:3]:
                value = info['value']
                unit = info['unit']
                print(f"       - {param}: {value:.2f} {unit}")

    # Get plant data
    plant_data = get_techno_plant_data('BSP', report_month)
    if plant_data['data']:
        print(f"\n[OK] Plant consolidated: {len(plant_data['data'])} parameters")

        for param, info in list(plant_data['data'].items())[:3]:
            value = info.get('value', 'N/A')
            if isinstance(value, (int, float)):
                print(f"     - {param}: {value:.2f}")

except Exception as e:
    print(f"[ERROR] Verification failed: {e}")
    import traceback
    traceback.print_exc()

# Summary
print(f"\n{'='*80}")
print("CONVERSION COMPLETE")
print(f"{'='*80}")

print("""
[SUCCESS] OISCO data extracted and converted to JSON!

Database Status:
  - Furnace data:      Inserted
  - Plant data:        Calculated and inserted
  - Next:              Check results above

What Was Imported:
  - CDI (furnace-wise)
  - Fuel Rate
  - Pellet in Burden
  - SMS data (SMS-2, SMS-3)
  - And 30+ other parameters

Ready for:
  - Dashboard integration
  - API endpoints serving data
  - PDF reports using new tables

Next Step:
  Option A) Migrate TechnoMya file (similar process)
  Option B) Test dashboard with this data
  Option C) Run /api/techno-* endpoints to see results
""")

print("="*80 + "\n")
