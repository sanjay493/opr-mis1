#!/usr/bin/env python3
"""
Insert manually verified JSON data into database

Steps:
1. Validate JSON
2. Show preview of data
3. Ask for confirmation
4. Insert into database
5. Show results

Usage:
    python insert_manual_data.py manual_data.json
"""

import json
import sys
from pathlib import Path

from db import insert_techno_furnace_data, get_techno_furnace_data, get_techno_plant_data
from validate_manual_entry import ManualDataValidator
from techno_json_utils import TechnoPlantCalculator


def preview_data(data):
    """Show data preview"""
    print("\n" + "="*80)
    print("DATA PREVIEW")
    print("="*80)

    report_month = data.get('report_month')
    plant = data.get('plant')

    print(f"\nReport Month: {report_month}")
    print(f"Plant: {plant}")

    furnaces = data.get('furnaces', {})

    print(f"\nFurnace Data ({len(furnaces)} furnaces):\n")

    for furnace in sorted(furnaces.keys()):
        params = furnaces[furnace]
        filled = sum(1 for p in params.values() if p.get('value') is not None)
        print(f"  {furnace}: {filled}/{len(params)} parameters")

        for param, info in sorted(params.items()):
            value = info.get('value')
            unit = info.get('unit')

            if value is not None:
                print(f"    • {param}: {value} {unit}")


def insert_data(data):
    """Insert validated data into database"""
    print("\n" + "="*80)
    print("INSERTING DATA INTO DATABASE")
    print("="*80)

    report_month = data.get('report_month')
    plant = data.get('plant')
    furnaces = data.get('furnaces', {})

    inserted_count = 0
    insertion_errors = []

    print(f"\nInserting furnace data for {plant} ({report_month})...\n")

    for furnace in sorted(furnaces.keys()):
        params = furnaces[furnace]

        # Filter out null values
        clean_data = {}
        for param, info in params.items():
            if info.get('value') is not None:
                clean_data[param] = {
                    'value': float(info['value']),
                    'unit': info.get('unit'),
                    'source': info.get('source', 'Manual'),
                }

        if not clean_data:
            print(f"  ⊘  {furnace}: No data to insert (all values null)")
            continue

        try:
            insert_techno_furnace_data(plant, furnace, report_month, clean_data)
            print(f"  ✓ {furnace}: {len(clean_data)} parameters inserted")
            inserted_count += 1
        except Exception as e:
            error_msg = f"{furnace}: {str(e)}"
            insertion_errors.append(error_msg)
            print(f"  ✗ {furnace}: ERROR - {str(e)}")

    # Calculate plant consolidated
    print(f"\nCalculating plant consolidated for {plant}...\n")

    try:
        calc = TechnoPlantCalculator()
        plant_data, calc_details = calc.calculate_plant_consolidated(plant, report_month)

        if plant_data:
            print(f"  ✓ Plant consolidated calculated: {len(plant_data)} parameters")
        else:
            print(f"  ⊘ No plant data to calculate")

    except Exception as e:
        insertion_errors.append(f"Plant calculation: {str(e)}")
        print(f"  ✗ Plant calculation failed: {str(e)}")

    # Report results
    print("\n" + "="*80)
    print("INSERTION RESULTS")
    print("="*80)

    print(f"\nFurnace records inserted: {inserted_count}")

    if insertion_errors:
        print(f"\nErrors: {len(insertion_errors)}")
        for error in insertion_errors:
            print(f"  • {error}")
        return False

    # Show what was inserted
    print("\nVerifying inserted data:\n")

    try:
        furnace_data = get_techno_furnace_data(plant, report_month)
        print(f"✓ Furnace data retrieved: {len(furnace_data)} furnaces")

        for furnace in sorted(furnace_data.keys()):
            params = furnace_data[furnace]
            print(f"  {furnace}: {len(params)} parameters")

        plant_info = get_techno_plant_data(plant, report_month)
        if plant_info.get('data'):
            print(f"\n✓ Plant consolidated retrieved: {len(plant_info['data'])} parameters")

    except Exception as e:
        print(f"⚠️ Could not verify: {e}")

    print("\n" + "="*80)
    print("✅ DATA INSERTION COMPLETE")
    print("="*80 + "\n")

    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python insert_manual_data.py <json_file>")
        print("Example: python insert_manual_data.py manual_data.json")
        sys.exit(1)

    json_file = sys.argv[1]
    json_path = Path(json_file)

    # Step 1: Validate
    print("\n[STEP 1] VALIDATING JSON FILE")
    validator = ManualDataValidator(json_path)

    if not validator.validate():
        print("\n[ERROR] Validation failed. Fix the JSON file and try again.")
        sys.exit(1)

    # Step 2: Load data
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Step 3: Show preview
    preview_data(data)

    # Step 4: Confirm before insert
    print("\n" + "-"*80)
    response = input("Insert this data into database? (yes/no): ").strip().lower()

    if response != 'yes':
        print("Insertion cancelled.")
        sys.exit(0)

    # Step 5: Insert
    success = insert_data(data)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
