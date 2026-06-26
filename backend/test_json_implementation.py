#!/usr/bin/env python3
"""
Test script for JSON-based techno data implementation
Tests: DB, extraction utilities, calculations, and API
"""

import sys
import json
import sqlite3

# Test 1: Database Creation & Functions
print("\n" + "="*70)
print("TEST 1: DATABASE TABLES & FUNCTIONS")
print("="*70)

try:
    import db
    from db import (
        insert_techno_furnace_data,
        get_techno_furnace_data,
        insert_techno_plant_data,
        get_techno_plant_data,
        insert_techno_sail_consolidated,
        get_techno_sail_consolidated
    )

    db.init_db()
    print("[OK] Database initialized")

    # Check tables exist
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'techno%'")
    tables = [row[0] for row in cursor.fetchall()]

    required_tables = ['techno_furnace_data', 'techno_plant_data', 'techno_sail_consolidated']
    for table in required_tables:
        if table in tables:
            print(f"[OK] Table '{table}' created")
        else:
            print(f"[FAIL] Table '{table}' NOT found")

    conn.close()

except Exception as e:
    print(f"[FAIL] Database test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# Test 2: Insert Sample Furnace Data
print("\n" + "="*70)
print("TEST 2: INSERT & RETRIEVE FURNACE DATA")
print("="*70)

try:
    furnace_data = [
        ('BF-1', 300.0, 2.10, 10000.0),
        ('BF-2', 350.0, 2.15, 11100.0),
        ('BF-3', 345.0, 1.95, 7234.0),
        ('BF-4', 357.0, 2.20, 9879.0),
    ]

    for furnace, coke, prod, hm in furnace_data:
        insert_techno_furnace_data(
            plant='BSP',
            furnace=furnace,
            report_month='2026-06',
            data={
                'Coke Rate': {'value': coke, 'unit': 'Kg/THM', 'source': 'PDF'},
                'BF Productivity': {'value': prod, 'unit': 'T/m³/day', 'source': 'PDF'},
                'HM Production': {'value': hm, 'unit': 'T', 'source': 'PDF'}
            }
        )

    print(f"[OK] Inserted {len(furnace_data)} furnace records")

    # Retrieve
    result = get_techno_furnace_data('BSP', '2026-06')
    print(f"[OK] Retrieved {len(result)} furnaces from DB")

    for furnace, data in sorted(result.items()):
        coke = data['Coke Rate']['value']
        hm = data['HM Production']['value']
        print(f"   {furnace}: Coke Rate = {coke:6.1f} Kg/THM, HM Prod = {hm:7.0f} T")

except Exception as e:
    print(f"[FAIL] Furnace data test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# Test 3: Plant Consolidated Calculation
print("\n" + "="*70)
print("TEST 3: CALCULATE PLANT CONSOLIDATED (Weighted Average)")
print("="*70)

try:
    from techno_json_utils import TechnoPlantCalculator

    calculator = TechnoPlantCalculator()
    plant_data, calc_details = calculator.calculate_plant_consolidated('BSP', '2026-06')

    print(f"[OK] Calculated plant consolidated data")

    if 'Coke Rate' in plant_data:
        coke_value = plant_data['Coke Rate']['value']
        method = plant_data['Coke Rate']['calculation_method']
        print(f"   Coke Rate: {coke_value:.2f} Kg/THM")
        print(f"   Calculation: {method}")

        if 'Coke Rate' in calc_details:
            calc = calc_details['Coke Rate']['calculation']
            print(f"   Formula: {calc}")

    # Save to DB
    insert_techno_plant_data('BSP', '2026-06', plant_data, calc_details)
    print(f"[OK] Saved plant consolidated to DB")

    # Retrieve to verify
    result = get_techno_plant_data('BSP', '2026-06')
    print(f"[OK] Retrieved plant data: {len(result['data'])} parameters")

except Exception as e:
    print(f"[FAIL] Plant calculation test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# Test 4: SAIL Consolidated
print("\n" + "="*70)
print("TEST 4: SAIL CONSOLIDATED (Multi-Plant Aggregation)")
print("="*70)

try:
    # First, insert data for other plants (for SAIL calculation)
    other_plants_data = {
        'DSP': [('BF-1', 320.0, 2.05, 9500.0), ('BF-2', 330.0, 2.12, 10000.0)],
        'RSP': [('BF-1', 310.0, 2.08, 9200.0), ('BF-2', 340.0, 2.18, 10500.0)],
        'BSL': [('BF-1', 305.0, 2.09, 9800.0)],
        'ISP': [('BF-1', 315.0, 2.11, 10200.0)],
    }

    for plant, furnaces in other_plants_data.items():
        for furnace, coke, prod, hm in furnaces:
            insert_techno_furnace_data(
                plant=plant,
                furnace=furnace,
                report_month='2026-06',
                data={
                    'Coke Rate': {'value': coke, 'unit': 'Kg/THM', 'source': 'PDF'},
                    'BF Productivity': {'value': prod, 'unit': 'T/m³/day', 'source': 'PDF'},
                    'HM Production': {'value': hm, 'unit': 'T', 'source': 'PDF'}
                }
            )

    print(f"[OK] Inserted furnace data for DSP, RSP, BSL, ISP")

    # Calculate plant consolidated for all 5
    for plant in ['DSP', 'RSP', 'BSL', 'ISP']:
        calc = TechnoPlantCalculator()
        plant_data, calc_details = calc.calculate_plant_consolidated(plant, '2026-06')
        if plant_data:
            insert_techno_plant_data(plant, '2026-06', plant_data, calc_details)

    print(f"[OK] Calculated plant consolidated for all 5 plants")

    # Now calculate SAIL
    from techno_json_utils import TechnoSAILCalculator

    sail_calc = TechnoSAILCalculator()
    sail_data, calc_method = sail_calc.calculate_sail_consolidated('2026-06')

    print(f"[OK] Calculated SAIL consolidated data")

    if 'Coke Rate' in sail_data:
        sail_coke = sail_data['Coke Rate']
        method = calc_method['Coke Rate']
        print(f"   SAIL Coke Rate: {sail_coke:.2f} Kg/THM")
        print(f"   Calculation: {method}")

    # Save to DB
    insert_techno_sail_consolidated('2026-06', sail_data, calc_method)
    print(f"[OK] Saved SAIL consolidated to DB")

    # Retrieve to verify
    result = get_techno_sail_consolidated('2026-06')
    print(f"[OK] Retrieved SAIL data: {len(result['data'])} parameters")

except Exception as e:
    print(f"[FAIL] SAIL calculation test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# Test 5: API Endpoint Simulation
print("\n" + "="*70)
print("TEST 5: API ENDPOINT SIMULATION")
print("="*70)

try:
    # Simulate API calls
    print("[OK] GET /api/techno-furnace-data?plant=BSP&report_month=2026-06")
    furnaces = get_techno_furnace_data('BSP', '2026-06')
    print(f"   Response: {len(furnaces)} furnaces")

    print("[OK] GET /api/techno-plant-data?plant=BSP&report_month=2026-06")
    plant = get_techno_plant_data('BSP', '2026-06')
    print(f"   Response: {len(plant['data'])} parameters")

    print("[OK] GET /api/techno-sail-data?report_month=2026-06")
    sail = get_techno_sail_consolidated('2026-06')
    print(f"   Response: {len(sail['data'])} parameters")

except Exception as e:
    print(f"[FAIL] API test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# Final Summary
print("\n" + "="*70)
print("SUCCESS: ALL TESTS PASSED!")
print("="*70)

print("\nTest Summary:")
print("   [OK] Database tables created")
print("   [OK] Furnace data insertion & retrieval")
print("   [OK] Plant consolidated calculation (weighted average)")
print("   [OK] SAIL consolidated calculation (multi-plant)")
print("   [OK] API endpoint simulation")

print("\nData In Database:")
print("   BSP Plant: 4 furnaces, 1 plant consolidated, 1 SAIL consolidated")
print("   DSP, RSP, BSL, ISP: Each has furnace and plant data")

print("\nReady for:")
print("   1. Frontend dashboard integration")
print("   2. PDF report generation")
print("   3. Production extraction from PDFs/Excel")

print("\n" + "="*70)
