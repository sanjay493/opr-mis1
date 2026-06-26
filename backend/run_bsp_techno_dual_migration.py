#!/usr/bin/env python3
"""
Extract BSP TechnoMya and insert into BOTH tables (Gradual Migration)

This extracts ONCE and inserts into:
  1. OLD tables (backward compatible)
  2. NEW JSON tables (techno_furnace_data)

Both tables stay in sync automatically!
"""

import sys
from pathlib import Path

sys.path.insert(0, 'excel_extractors')

from gradual_migration_adapter import dual_extract_and_insert, MigrationTracker

# Configuration
PLANT = 'BSP'
EXTRACTOR_TYPE = 'techno'
REPORT_MONTH = '2026-05'
MIGRATION_PHASE = 1  # 1=dual insert, 2=new primary, 3=read-only, 4=removed

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
print("BSP TECHNO DATA EXTRACTION - DUAL MIGRATION")
print("="*80)
print(f"\nThis will insert data into BOTH:")
print(f"  • OLD tables (backward compatible)")
print(f"  • NEW JSON tables (techno_furnace_data)")
print(f"\nBoth tables stay in sync!")

# Load and call extractor module directly
from excel_extractor_bsp_techno import extract_preview

success = dual_extract_and_insert(
    plant=PLANT,
    extractor_type=EXTRACTOR_TYPE,
    excel_file=str(TECHNO_FILE),
    report_month=REPORT_MONTH,
    extractor_module=sys.modules['excel_extractor_bsp_techno'],
    auto_insert=False,
    migration_phase=MIGRATION_PHASE
)

if success:
    print("\n✓ Dual migration successful!")
    print("\nData inserted into:")
    print("  ✓ Old tables (backward compatible)")
    print("  ✓ New JSON tables (techno_furnace_data)")
    print("  ✓ Plant consolidated calculated")

    print("\nVerify in dashboard:")
    print("  http://localhost:8000/dashboard")
    print("  Select: Plant=BSP, Month=2026-05")
else:
    print("\n✗ Extraction failed")

# Show migration progress
print("\n" + "-"*80)
MigrationTracker.print_migration_status()

sys.exit(0 if success else 1)
