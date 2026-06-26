#!/usr/bin/env python3
"""
Extract from Uploaded File and Insert into JSON Tables

Workflow:
1. Upload file via port 3000 (old system)
2. Run this script with file path
3. Auto-extracts and inserts into new JSON tables

Usage:
    python extract_from_upload.py <file_path> <plant> <extractor_type> <month>

Examples:
    python extract_from_upload.py "Report_format/Monthly/BSPOISCO_MAY'25.xlsx" BSP oisco 2025-05
    python extract_from_upload.py "uploads/BSP-3-page-TechMay'26.xlsx" BSP techno 2026-05
"""

import sys
from pathlib import Path

sys.path.insert(0, 'excel_extractors')

from smart_extractor_adapter import SmartExtractorAdapter
from db import init_db


def extract_from_upload(excel_file: str, plant: str, extractor_type: str, report_month: str) -> bool:
    """
    Extract from uploaded file and insert into JSON tables

    Args:
        excel_file: Path to uploaded Excel file
        plant: Plant code (BSP, DSP, RSP, BSL, ISP)
        extractor_type: Extractor type (oisco, techno, rsp)
        report_month: Report month (YYYY-MM)

    Returns:
        Success status
    """

    excel_path = Path(excel_file)

    # Validate file exists
    if not excel_path.exists():
        print(f"✗ File not found: {excel_file}")
        return False

    print("\n" + "="*80)
    print("EXTRACT FROM UPLOADED FILE")
    print("="*80)
    print(f"\nFile: {excel_path.name}")
    print(f"Plant: {plant}")
    print(f"Extractor: {extractor_type}")
    print(f"Month: {report_month}")

    # Initialize database
    init_db()

    # Load extractor module
    try:
        module_name = f'excel_extractor_{plant.lower()}_{extractor_type}'
        extractor_module = __import__(module_name)
        print(f"✓ Loaded extractor: {module_name}")
    except ImportError as e:
        print(f"✗ Could not load extractor: {e}")
        return False

    # Extract and insert
    adapter = SmartExtractorAdapter(plant.upper())
    success = adapter.extract_and_insert(
        extractor_module=extractor_module,
        excel_file=str(excel_path),
        report_month=report_month,
        auto_insert=True  # Auto-insert (no confirmation needed)
    )

    return success


def main():
    if len(sys.argv) < 5:
        print("Usage: python extract_from_upload.py <file_path> <plant> <extractor_type> <month>")
        print("\nExamples:")
        print("  python extract_from_upload.py 'uploads/BSPOISCO_MAY25.xlsx' BSP oisco 2025-05")
        print("  python extract_from_upload.py 'uploads/BSP-3-page-TechMay26.xlsx' BSP techno 2026-05")
        print("\nSupported plants: BSP, DSP, RSP, BSL, ISP")
        print("Supported extractors: oisco, techno, rsp")
        sys.exit(1)

    excel_file = sys.argv[1]
    plant = sys.argv[2].upper()
    extractor_type = sys.argv[3].lower()
    report_month = sys.argv[4]

    success = extract_from_upload(excel_file, plant, extractor_type, report_month)

    if success:
        print("\n✓ Extraction complete!")
        print("\nData inserted into JSON tables:")
        print("  ✓ techno_furnace_data")
        print("  ✓ techno_plant_data")
        print("\nVerify in dashboard: http://localhost:8000/dashboard")
    else:
        print("\n✗ Extraction failed")

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
