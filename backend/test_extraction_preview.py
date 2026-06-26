#!/usr/bin/env python3
"""
Test what data the existing extractors return
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, 'excel_extractors')

print("\n" + "="*80)
print("TESTING EXISTING EXTRACTORS")
print("="*80)

# Test BSP Techno extractor
try:
    from excel_extractor_bsp_techno import extract_preview as extract_bsp_techno

    file1 = r'Report_format\monthly\BSP-3-page-TechMya\'26.xlsx'

    if Path(file1).exists():
        print(f"\n[1] Testing {file1}")

        try:
            result = extract_bsp_techno(file1, '2026-05')

            print(f"    Keys in result: {list(result.keys())}")

            if 'techno_param_rows' in result:
                param_rows = result['techno_param_rows']
                print(f"    Total parameters: {len(param_rows)}")

                if param_rows:
                    first_row = param_rows[0]
                    print(f"    First row keys: {list(first_row.keys())}")
                    print(f"    First row: {first_row}")

                    # Count how many have actual values
                    with_values = sum(1 for r in param_rows if r.get('actual') is not None)
                    print(f"    Parameters with values: {with_values}/{len(param_rows)}")
        except Exception as e:
            print(f"    ERROR: {e}")
    else:
        print(f"    File not found: {file1}")

except Exception as e:
    print(f"ERROR importing extractor: {e}")

# Test BSP OISCO extractor
try:
    from excel_extractor_bsp_oisco import extract_preview as extract_bsp_oisco

    file2 = r'Report_format\monthly\BSPOISCO_MAY\'25.xlsx'

    if Path(file2).exists():
        print(f"\n[2] Testing {file2}")

        try:
            result = extract_bsp_oisco(file2, '2025-05')

            print(f"    Keys in result: {list(result.keys())}")

            if 'techno_param_rows' in result:
                param_rows = result['techno_param_rows']
                print(f"    Total parameters: {len(param_rows)}")

                if param_rows:
                    first_row = param_rows[0]
                    print(f"    First row keys: {list(first_row.keys())}")
                    print(f"    First row: {first_row}")

                    # Count how many have actual values
                    with_values = sum(1 for r in param_rows if r.get('actual') is not None)
                    print(f"    Parameters with values: {with_values}/{len(param_rows)}")
        except Exception as e:
            print(f"    ERROR: {e}")
    else:
        print(f"    File not found: {file2}")

except Exception as e:
    print(f"ERROR importing extractor: {e}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("\nThis shows what the existing extractors return.")
print("Next step: adapt the converter to handle these data structures.")
