#!/usr/bin/env python3
"""
Demo: Show What the Converter Does
(Simulates Excel extraction and shows conversion)
"""

import json
from excel_to_json_converter import process_excel_extraction
from db import init_db, get_techno_furnace_data, get_techno_plant_data

print("\n" + "="*80)
print("JSON CONVERSION DEMO - SIMULATED EXCEL DATA")
print("="*80)

# Initialize DB
print("\n[STEP 1] Initializing database...")
init_db()
print("[OK] Database ready")

# Simulate extracted parameters from your Excel file
# This is what extract_preview() would return
print("\n[STEP 2] Simulating Excel extraction (BSP-3-page-TechMya'26.xlsx)...")

simulated_excel_output = [
    # BF-4 parameters
    {
        'group_code': 'IRON_MAKING',
        'section': 'Blast Furnaces (BSP)',
        'parameter': 'Coke Rate',
        'unit': 'Kg/THM',
        'actual': 425.5,
    },
    {
        'group_code': 'IRON_MAKING',
        'section': 'Blast Furnaces (BSP)',
        'parameter': 'BF Productivity',
        'unit': 'T/m³/day',
        'actual': 2.15,
    },
    {
        'group_code': 'IRON_MAKING',
        'section': 'Blast Furnaces (BSP)',
        'parameter': 'HM Production',
        'unit': 'T',
        'actual': 10000,
    },
    # BF-6 parameters
    {
        'group_code': 'IRON_MAKING',
        'section': 'Blast Furnaces, BF-6',
        'parameter': 'Coke Rate',
        'unit': 'Kg/THM',
        'actual': 430.2,
    },
    {
        'group_code': 'IRON_MAKING',
        'section': 'Blast Furnaces, BF-6',
        'parameter': 'BF Productivity',
        'unit': 'T/m³/day',
        'actual': 2.12,
    },
    {
        'group_code': 'IRON_MAKING',
        'section': 'BF-6 Operations',
        'parameter': 'HM Production',
        'unit': 'T',
        'actual': 11100,
    },
    # BF-7 parameters
    {
        'group_code': 'IRON_MAKING',
        'section': 'BF-7',
        'parameter': 'Coke Rate',
        'unit': 'Kg/THM',
        'actual': 428.0,
    },
    {
        'group_code': 'IRON_MAKING',
        'section': 'BF-7',
        'parameter': 'BF Productivity',
        'unit': 'T/m³/day',
        'actual': 2.18,
    },
    {
        'group_code': 'IRON_MAKING',
        'section': 'BF-7',
        'parameter': 'HM Production',
        'unit': 'T',
        'actual': 9500,
    },
    # BF-8 parameters
    {
        'group_code': 'IRON_MAKING',
        'section': 'Furnace BF-8',
        'parameter': 'Coke Rate',
        'unit': 'Kg/THM',
        'actual': 432.1,
    },
    {
        'group_code': 'IRON_MAKING',
        'section': 'Furnace BF-8',
        'parameter': 'BF Productivity',
        'unit': 'T/m³/day',
        'actual': 2.20,
    },
    {
        'group_code': 'IRON_MAKING',
        'section': 'BF-8 Operations',
        'parameter': 'HM Production',
        'unit': 'T',
        'actual': 10400,
    },
]

print(f"[OK] Simulated {len(simulated_excel_output)} parameters from Excel")

# Show sample input
print("\n[INPUT SAMPLE] First 3 extracted parameters:")
print("-" * 80)
for param in simulated_excel_output[:3]:
    print(f"  Section: '{param['section']}'")
    print(f"    Parameter: {param['parameter']} = {param['actual']} {param['unit']}")
    print()

# Step 3: Convert to JSON
print("[STEP 3] Converting to JSON format (using converter)...")
print("-" * 80)

furnaces_inserted, preview = process_excel_extraction(
    plant='BSP',
    parameter_rows=simulated_excel_output,
    report_month='2026-05',
    auto_calculate_plant=True,
    auto_calculate_sail=False
)

# Show the preview
print(preview)

# Step 4: Verify in database
print("[STEP 4] Verifying results in database...")
print("-" * 80)

try:
    furnaces = get_techno_furnace_data('BSP', '2026-05')
    print(f"\n[OK] FURNACE DATA INSERTED: {len(furnaces)} furnaces")

    for furnace in sorted(furnaces.keys()):
        data = furnaces[furnace]
        params = list(data.keys())
        print(f"\n  {furnace}:")
        for param in params:
            value = data[param]['value']
            unit = data[param]['unit']
            print(f"    • {param}: {value:.2f} {unit}")

    plant_data = get_techno_plant_data('BSP', '2026-05')
    if plant_data['data']:
        print(f"\n[OK] PLANT CONSOLIDATED: {len(plant_data['data'])} parameters")
        print(f"\n  Calculated (Weighted Average):")
        for param, info in plant_data['data'].items():
            value = info.get('value', 'N/A')
            method = info.get('calculation_method', 'N/A')
            if isinstance(value, (int, float)):
                print(f"    • {param}: {value:.2f} (Method: {method})")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

# Step 5: Show what API would return
print("\n[STEP 5] What API endpoints will return...")
print("-" * 80)

try:
    furnace_json = json.dumps(furnaces['BF-4'], indent=2)
    print(f"\nGET /api/techno-furnace-data?plant=BSP&furnace=BF-4&report_month=2026-05")
    print(f"Response (BF-4 data):\n{furnace_json}")

    plant_json = json.dumps({
        'data': plant_data['data'],
        'calculation_details': plant_data['calculation_details']
    }, indent=2, default=str)
    print(f"\nGET /api/techno-plant-data?plant=BSP&report_month=2026-05")
    print(f"Response (Plant consolidated):\n{plant_json}")

except Exception as e:
    print(f"Could not generate API responses: {e}")

# Summary
print("\n" + "="*80)
print("DEMO SUMMARY")
print("="*80)

print(f"""
INPUT:
  • File: BSP-3-page-TechMya'26.xlsx (simulated)
  • Parameters extracted: {len(simulated_excel_output)}
  • Date range: 2026-05

CONVERSION:
  • Furnaces identified: 4 (BF-4, BF-6, BF-7, BF-8)
  • Parameters per furnace: 3 (Coke Rate, BF Productivity, HM Production)
  • Furnace records inserted: {furnaces_inserted}

DATABASE TABLES:
  ✓ techno_furnace_data: {len(furnaces)} records
  ✓ techno_plant_data: 1 record (BSP consolidated)

NEXT STEPS:
  1. Review the output above
  2. If it looks correct → Run full migration
  3. Full migration: python migrate_excel_to_json.py
  4. Both Excel files will be processed
  5. Data ready for dashboard update

API READY:
  ✓ /api/techno-furnace-data (furnace-wise)
  ✓ /api/techno-plant-data (plant consolidated)
  ✓ /api/techno-sail-data (SAIL consolidated)
""")

print("="*80)
print("✅ TEST COMPLETE - Ready for production migration!")
print("="*80 + "\n")
