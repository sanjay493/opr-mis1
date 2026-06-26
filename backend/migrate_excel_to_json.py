#!/usr/bin/env python3
"""
Complete Migration Example: Excel Extractors → JSON Database

This script demonstrates the complete workflow:
1. Extract data from existing Excel files using current extractors
2. Convert to JSON format
3. Insert into new techno_furnace_data table
4. Calculate plant consolidated
5. Calculate SAIL consolidated
6. Display results

Usage:
    python migrate_excel_to_json.py

Files processed:
    - Report_format/monthly/BSP-3-page-TechMya'26.xlsx
    - Report_format/monthly/BSPOISCO_MAY'25.xlsx
"""

import json
import logging
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, 'excel_extractors')

from excel_extractor_bsp_techno import extract_preview as extract_bsp_techno
from excel_extractor_bsp_oisco import extract_preview as extract_bsp_oisco
from excel_to_json_converter import process_excel_extraction
from db import init_db, get_techno_furnace_data, get_techno_plant_data, get_techno_sail_consolidated

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run complete migration example"""

    logger.info("="*80)
    logger.info("EXCEL TO JSON MIGRATION - COMPLETE EXAMPLE")
    logger.info("="*80)

    # Initialize database
    logger.info("\n[STEP 1] Initializing database...")
    init_db()
    logger.info("[OK] Database initialized")

    # Define files to process
    files_to_process = [
        {
            'file': r'Report_format\monthly\BSP-3-page-TechMya\'26.xlsx',
            'plant': 'BSP',
            'month': '2026-05',
            'extractor': 'excel_extractor_bsp_techno',
            'description': 'BSP Techno Parameters (Excel)'
        },
        {
            'file': r'Report_format\monthly\BSPOISCO_MAY\'25.xlsx',
            'plant': 'BSP',
            'month': '2025-05',
            'extractor': 'excel_extractor_bsp_oisco',
            'description': 'BSP OISCO Parameters (Excel)'
        }
    ]

    # Process each file
    all_inserted = 0

    for file_info in files_to_process:
        logger.info(f"\n[PROCESSING] {file_info['description']}")
        logger.info("-" * 80)

        file_path = file_info['file']
        plant = file_info['plant']
        month = file_info['month']

        # Check file exists
        if not Path(file_path).exists():
            logger.warning(f"[SKIP] File not found: {file_path}")
            continue

        try:
            # Step 1: Extract using existing extractor
            logger.info(f"[STEP 1] Extracting from {file_path}...")

            # Call the appropriate extractor
            if 'techno' in file_info['extractor']:
                preview_data = extract_bsp_techno(file_path, month)
            else:
                preview_data = extract_bsp_oisco(file_path, month)

            # Get parameter rows from preview
            param_rows = preview_data.get('techno_param_rows', [])

            if not param_rows:
                logger.warning(f"[WARN] No parameters extracted from {file_path}")
                continue

            logger.info(f"[OK] Extracted {len(param_rows)} parameters")

            # Step 2: Convert to JSON format
            logger.info(f"\n[STEP 2] Converting to JSON format...")

            # Create parameter row dicts compatible with converter
            rows_for_conversion = []
            for row in param_rows:
                if isinstance(row, dict):
                    rows_for_conversion.append({
                        'group_code': row.get('group_code', ''),
                        'section': row.get('section', ''),
                        'parameter': row.get('parameter', ''),
                        'unit': row.get('unit', ''),
                        'actual': row.get('actual'),
                    })

            # Process with converter
            furnaces_inserted, preview = process_excel_extraction(
                plant=plant,
                parameter_rows=rows_for_conversion,
                report_month=month,
                auto_calculate_plant=True,
                auto_calculate_sail=False  # Will do SAIL at the end
            )

            logger.info(preview)

            all_inserted += furnaces_inserted

            logger.info(f"\n[SUCCESS] {furnaces_inserted} furnaces inserted for {plant} - {month}")

        except Exception as e:
            logger.error(f"[ERROR] Processing {file_path}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Step 3: Calculate SAIL consolidated (after all plants processed)
    if all_inserted > 0:
        logger.info("\n[STEP 3] Calculating SAIL consolidated...")

        try:
            from excel_to_json_converter import JsonDataManager

            manager = JsonDataManager()
            success = manager.calculate_and_insert_sail_consolidated('2026-05')

            if success:
                logger.info("[OK] SAIL consolidated calculated")
            else:
                logger.warning("[WARN] Could not calculate SAIL consolidated")

        except Exception as e:
            logger.error(f"[ERROR] SAIL calculation: {e}")

    # Step 4: Display results
    logger.info("\n" + "="*80)
    logger.info("MIGRATION RESULTS")
    logger.info("="*80)

    try:
        # Check what's in the database
        furnaces_bsp = get_techno_furnace_data('BSP', '2026-05')
        logger.info(f"\n✓ Furnace data (BSP, 2026-05): {len(furnaces_bsp)} furnaces")

        for furnace, data in sorted(furnaces_bsp.items()):
            param_count = len(data)
            logger.info(f"    {furnace}: {param_count} parameters")

        # Check plant consolidated
        plant_data = get_techno_plant_data('BSP', '2026-05')
        if plant_data['data']:
            logger.info(f"\n✓ Plant consolidated (BSP, 2026-05): {len(plant_data['data'])} parameters")

            for param, info in list(plant_data['data'].items())[:5]:
                value = info.get('value', 'N/A')
                logger.info(f"    {param}: {value}")

        # Check SAIL consolidated
        sail_data = get_techno_sail_consolidated('2026-05')
        if sail_data['data']:
            logger.info(f"\n✓ SAIL consolidated (2026-05): {len(sail_data['data'])} parameters")

    except Exception as e:
        logger.error(f"[ERROR] Retrieving results: {e}")

    logger.info("\n" + "="*80)
    logger.info("MIGRATION COMPLETE")
    logger.info("="*80)
    logger.info("\nNext steps:")
    logger.info("  1. Verify data in database matches expectations")
    logger.info("  2. Update dashboard to use new /api/techno-* endpoints")
    logger.info("  3. Update PDF report generation")
    logger.info("  4. Add more plant extractors (DSP, RSP, BSL, ISP)")
    logger.info("\nTo query the data:")
    logger.info("  - GET http://localhost:8000/api/techno-furnace-data?plant=BSP&report_month=2026-05")
    logger.info("  - GET http://localhost:8000/api/techno-plant-data?plant=BSP&report_month=2026-05")
    logger.info("  - GET http://localhost:8000/api/techno-sail-data?report_month=2026-05")


if __name__ == '__main__':
    main()
