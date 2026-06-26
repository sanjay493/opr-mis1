#!/usr/bin/env python3
"""Simple test to show extraction workflow"""

import sys
sys.path.insert(0, 'excel_extractors')

from pathlib import Path
from db import init_db

print("\n" + "="*80)
print("SIMPLE EXTRACTION AND JSON CONVERSION TEST")
print("="*80)

# Initialize DB
print("\n[1] Initializing database...")
init_db()
print("[OK] Database ready")

# Test with one simple extractor
print("\n[2] Testing BSP Techno Extractor...")

from excel_extractor_bsp_techno import extract_preview

file1 = r'Report_format\monthly\BSP-3-page-TechMya\'26.xlsx'

if not Path(file1).exists():
    print(f"[ERROR] File not found: {file1}")
    print("\nNote: You need to have the Excel files in:")
    print(f"  {Path(file1).absolute().parent}")
    sys.exit(1)

try:
    result = extract_preview(file1, '2026-05')

    if 'techno_param_rows' in result:
        param_rows = result['techno_param_rows']
        print(f"[OK] Extracted {len(param_rows)} parameters")

        # Show first 5
        print("\n[3] First 5 parameters:")
        print("-" * 80)
        for i, row in enumerate(param_rows[:5]):
            print(f"  {row}")

        # Count params with values
        with_values = sum(1 for r in param_rows if r.get('actual') is not None)
        print(f"\n[OK] {with_values} parameters have actual values")

        # Now convert to JSON
        print("\n[4] Converting to JSON format...")

        from excel_to_json_converter import process_excel_extraction

        # Prepare rows
        rows_for_conversion = []
        for row in param_rows:
            if isinstance(row, dict) and row.get('actual') is not None:
                rows_for_conversion.append({
                    'group_code': row.get('group_code', ''),
                    'section': row.get('section', ''),
                    'parameter': row.get('parameter', ''),
                    'unit': row.get('unit', ''),
                    'actual': row.get('actual'),
                })

        # Convert and insert
        furnaces_inserted, preview = process_excel_extraction(
            plant='BSP',
            parameter_rows=rows_for_conversion,
            report_month='2026-05',
            auto_calculate_plant=True,
            auto_calculate_sail=False
        )

        print(preview)

        print(f"\n[SUCCESS] Conversion complete!")
        print(f"  Furnaces inserted: {furnaces_inserted}")
        print(f"  Check database for techno_furnace_data table")

        # Try to retrieve
        print("\n[5] Verifying database...")

        from db import get_techno_furnace_data, get_techno_plant_data

        furnaces = get_techno_furnace_data('BSP', '2026-05')
        print(f"[OK] Retrieved {len(furnaces)} furnaces from database")

        for furnace, data in sorted(furnaces.items()):
            print(f"     {furnace}: {len(data)} parameters")

        plant_data = get_techno_plant_data('BSP', '2026-05')
        if plant_data['data']:
            print(f"[OK] Plant consolidated: {len(plant_data['data'])} parameters")

    else:
        print(f"[ERROR] Expected 'techno_param_rows' in result")
        print(f"  Got keys: {list(result.keys())}")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
