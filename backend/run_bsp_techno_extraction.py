#!/usr/bin/env python3
"""
Extract BSP TechnoMya data and insert into NEW JSON tables

Features:
- If plant data in Excel: uses it directly
- If plant data NOT in Excel: auto-calculates from furnaces

Smart handling of plant consolidated!
"""

import sys
from pathlib import Path

sys.path.insert(0, 'excel_extractors')

from smart_extractor_adapter import smart_extract_and_insert

# Configuration
PLANT = 'BSP'
EXTRACTOR_TYPE = 'techno'
REPORT_MONTH = '2026-05'

# Find Excel file
TECHNO_FILE = Path('Report_format/Monthly/BSP-3-page-TechMay\'26.xlsx')

if not TECHNO_FILE.exists():
    print(f"[ERROR] File not found: {TECHNO_FILE}")
    print("\nSearching for TechnoMya files...")
    import glob
    files = glob.glob('Report_format/Monthly/*TechMya*') + glob.glob('Report_format/Monthly/*TechMay*')
    if files:
        print(f"Found: {files}")
        TECHNO_FILE = files[0]
    else:
        print("No TechnoMya files found")
        sys.exit(1)

print("\n" + "="*80)
print("BSP TECHNO DATA EXTRACTION - SMART MODE")
print("="*80)
print(f"\nPlant consolidated handling:")
print(f"  ✓ If in source file: use directly")
print(f"  ✓ If NOT in source: auto-calculate from furnaces")

success = smart_extract_and_insert(
    plant=PLANT,
    extractor_type=EXTRACTOR_TYPE,
    excel_file=str(TECHNO_FILE),
    report_month=REPORT_MONTH,
    auto_insert=False
)

if success:
    print("\n✓ Extraction complete!")
    print("\nData inserted into NEW JSON tables:")
    print("  ✓ techno_furnace_data (furnace-wise data)")
    print("  ✓ techno_plant_data (intelligent consolidation)")
else:
    print("\n✗ Extraction failed")

sys.exit(0 if success else 1)
