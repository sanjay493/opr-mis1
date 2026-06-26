#!/usr/bin/env python3
"""
Extract Real Data from BSP-3-page-TechMya'26.xlsx
Step-by-step extraction with preview before conversion
"""

import sys
import json
sys.path.insert(0, 'excel_extractors')

from pathlib import Path
from db import init_db
import os

print("\n" + "="*80)
print("TECHNOMYA REAL DATA EXTRACTION")
print("="*80)

# File info - use absolute path
techno_file = os.path.abspath(r'../Report_format/monthly/BSP-3-page-TechMay' + "'26.xlsx")
report_month = '2026-05'

# Check file exists
if not Path(techno_file).exists():
    print(f"\n[ERROR] File not found: {techno_file}")
    print(f"\nSearching for TechnoMya files...")
    from glob import glob
    files = glob(os.path.abspath('../Report_format/monthly/*TechMya*'))
    if files:
        print(f"Found: {files}")
    else:
        print("No TechnoMya files found in Report_format/monthly/")
    sys.exit(1)

print(f"\n[FILE] {Path(techno_file).name}")
print(f"[MONTH] {report_month}")

# Step 1: Initialize database
print("\n[STEP 1] Initializing database...")
init_db()
print("[OK] Database ready")

# Step 2: Extract from TechnoMya file
print(f"\n[STEP 2] Extracting from {Path(techno_file).name}...")
print("-" * 80)

try:
    from excel_extractor_bsp_techno import extract_preview

    result = extract_preview(techno_file, report_month)

    print(f"[OK] Extraction complete")

    # Get the parameter rows
    param_rows = result.get('techno_param_rows', [])
    print(f"[INFO] Total parameters extracted: {len(param_rows)}")

    if not param_rows:
        print("[ERROR] No parameters found in extraction result")
        print(f"[INFO] Result keys: {list(result.keys())}")
        sys.exit(1)

    # Step 3: Show extracted data preview
    print(f"\n[STEP 3] Preview of extracted data...")
    print("-" * 80)

    # Count and categorize
    params_with_values = [p for p in param_rows if p.get('actual') is not None]
    print(f"[INFO] Parameters with values: {len(params_with_values)}/{len(param_rows)}")

    # Show unique sections
    sections = set()
    for row in param_rows:
        section = row.get('section', 'N/A')
        if section:
            sections.add(section)

    print(f"[INFO] Unique sections: {len(sections)}")
    print("\nSections found (first 15):")
    for section in sorted(sections)[:15]:
        print(f"  • {section}")

    if len(sections) > 15:
        print(f"  ... and {len(sections) - 15} more")

    # Show sample data
    print(f"\n[SAMPLE] First 20 extracted parameters:\n")
    print(f"{'Group':<20} {'Section':<40} {'Parameter':<35} {'Value':<12} {'Unit':<10}")
    print("-" * 120)

    for i, row in enumerate(param_rows[:20]):
        group = row.get('group_code', 'N/A')[:19]
        section = row.get('section', 'N/A')[:39]
        param = row.get('parameter', 'N/A')[:34]
        value = row.get('actual', '')
        unit = row.get('unit', 'N/A')[:9]

        if value is not None:
            if isinstance(value, (int, float)):
                value_str = f"{value:.2f}"
            else:
                value_str = str(value)[:11]
        else:
            value_str = "NULL"

        print(f"{group:<20} {section:<40} {param:<35} {value_str:<12} {unit:<10}")

    if len(param_rows) > 20:
        print(f"\n... and {len(param_rows) - 20} more parameters")

    # Step 4: Show data distribution
    print(f"\n[STEP 4] Data distribution by group:")
    print("-" * 80)

    groups = {}
    for row in param_rows:
        group = row.get('group_code', 'UNKNOWN')
        if group not in groups:
            groups[group] = {'count': 0, 'with_value': 0}
        groups[group]['count'] += 1
        if row.get('actual') is not None:
            groups[group]['with_value'] += 1

    for group in sorted(groups.keys()):
        count = groups[group]['count']
        with_val = groups[group]['with_value']
        print(f"  {group:<20} {count:3} parameters ({with_val:3} with values)")

    # Step 5: Show furnace identification opportunities
    print(f"\n[STEP 5] Furnace-related sections found:")
    print("-" * 80)

    furnace_sections = [s for s in sections if any(bf in s for bf in ['BF', 'bf', 'Furnace', 'furnace'])]

    if furnace_sections:
        print(f"Found {len(furnace_sections)} furnace-related sections:\n")
        for section in sorted(furnace_sections):
            # Count parameters in this section
            count = sum(1 for p in param_rows if p.get('section') == section)
            print(f"  • {section} ({count} parameters)")
    else:
        print("No furnace-specific sections found")

    # Step 6: Save extraction to file for review
    print(f"\n[STEP 6] Saving extraction details...")

    extraction_summary = {
        'file': techno_file,
        'report_month': report_month,
        'total_parameters': len(param_rows),
        'parameters_with_values': len(params_with_values),
        'unique_sections': len(sections),
        'groups': groups,
        'sample_data': [
            {
                'group_code': p.get('group_code'),
                'section': p.get('section'),
                'parameter': p.get('parameter'),
                'unit': p.get('unit'),
                'actual': p.get('actual')
            }
            for p in param_rows[:30]
        ]
    }

    with open('techno_extraction_summary.json', 'w') as f:
        json.dump(extraction_summary, f, indent=2, default=str)

    print("[OK] Summary saved to techno_extraction_summary.json")

    # Summary
    print(f"\n{'='*80}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*80}")
    print(f"""
File:                 {Path(techno_file).name}
Report Month:         {report_month}
Total Parameters:     {len(param_rows)}
With Values:          {len(params_with_values)}
Sections:             {len(sections)}
Groups:               {len(groups)}
Furnace Sections:     {len(furnace_sections)}

Status:               [OK] Ready for conversion

Next Step:
  Run: C:\\Users\\sanja\\anaconda3\\python.exe convert_techno_to_json.py
""")

    print(f"{'='*80}\n")

except Exception as e:
    print(f"\n[ERROR] Extraction failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
