#!/usr/bin/env python3
"""
Smart Extractor Adapter

Intelligently handles plant data:
- If plant data in Excel: use directly
- If plant data not in Excel: auto-calculate from furnaces

Only inserts into NEW JSON tables.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

sys.path.insert(0, 'excel_extractors')

from db import insert_techno_furnace_data, insert_techno_plant_data, init_db
from techno_json_utils import TechnoPlantCalculator
from parameter_naming import normalize_parameter_name

logger = logging.getLogger(__name__)


class SmartExtractorAdapter:
    """Smart extraction and insertion with intelligent plant data handling"""

    def __init__(self, plant: str):
        self.plant = plant.upper()

    def extract_and_insert(
        self,
        extractor_module: Any,
        excel_file: str,
        report_month: str,
        auto_insert: bool = False
    ) -> bool:
        """
        Smart extraction workflow

        Logic:
        1. Extract all parameters from Excel
        2. Separate furnace vs plant data
        3. If plant data in source: use directly
        4. If plant data not in source: auto-calculate from furnaces
        5. Insert both into NEW JSON tables

        Args:
            extractor_module: Loaded extractor module
            excel_file: Path to Excel file
            report_month: Report month
            auto_insert: Skip confirmation

        Returns:
            Success status
        """

        init_db()

        # Step 1: Extract
        print(f"\n{'='*80}")
        print(f"SMART EXTRACTION - {self.plant}")
        print(f"{'='*80}")

        try:
            result = extractor_module.extract_preview(excel_file, report_month)
            param_rows = result.get('techno_param_rows', [])

            if not param_rows:
                print(f"✗ No parameters extracted")
                return False

            print(f"\n✓ Extracted {len(param_rows)} parameters")

        except Exception as e:
            print(f"✗ Extraction failed: {e}")
            return False

        # Step 2: Separate furnace vs plant data
        print(f"\nSeparating data:")

        furnace_data = {}
        plant_data_from_source = {}

        for row in param_rows:
            value = row.get('actual')

            if value is None:
                continue

            # Identify furnace
            furnace = self._identify_furnace(row)
            param_name = normalize_parameter_name(row.get('parameter', ''))

            if not param_name:
                continue

            if furnace:
                # Furnace-specific data
                if furnace not in furnace_data:
                    furnace_data[furnace] = {}

                furnace_data[furnace][param_name] = {
                    'value': float(value),
                    'unit': row.get('unit', ''),
                    'source': 'Excel-Extracted',
                }
            else:
                # Plant-level data (no furnace identified)
                plant_data_from_source[param_name] = {
                    'value': float(value),
                    'unit': row.get('unit', ''),
                    'source': 'Excel-Extracted',
                }

        print(f"  ✓ Furnace data: {sum(len(v) for v in furnace_data.values())} parameters")
        print(f"  ✓ Plant data in source: {len(plant_data_from_source)} parameters")

        if not furnace_data and not plant_data_from_source:
            print(f"\n✗ No data found")
            return False

        # Step 3: Show preview
        print(f"\nPreview:")
        for furnace in sorted(furnace_data.keys()):
            print(f"  {furnace}: {len(furnace_data[furnace])} parameters")

        if plant_data_from_source:
            print(f"  [Plant-level data from source]: {len(plant_data_from_source)} parameters")
        else:
            print(f"  [Plant-level data]: Will be auto-calculated from furnaces")

        # Step 4: Confirm
        if not auto_insert:
            response = input(f"\nInsert into NEW JSON tables? (yes/no): ").strip().lower()
            if response != 'yes':
                print("Cancelled")
                return False

        # Step 5: Insert furnace data
        print(f"\n{'='*80}")
        print(f"INSERTING DATA")
        print(f"{'='*80}\n")

        inserted_count = 0
        errors = []

        for furnace, params in furnace_data.items():
            try:
                insert_techno_furnace_data(self.plant, furnace, report_month, params)
                print(f"  ✓ {furnace}: {len(params)} parameters")
                inserted_count += 1

            except Exception as e:
                print(f"  ✗ {furnace}: {str(e)}")
                errors.append(str(e))

        # Step 6: Handle plant data
        print(f"\nPlant consolidated:")

        if plant_data_from_source:
            # Plant data from source - use directly
            print(f"  ✓ Using data from source: {len(plant_data_from_source)} parameters")
            try:
                insert_techno_plant_data(
                    plant=self.plant,
                    report_month=report_month,
                    data=plant_data_from_source,
                    calculation_details={'method': 'from_source', 'source': 'Excel-Extracted'}
                )
                print(f"  ✓ Inserted")
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
                errors.append(str(e))

        elif inserted_count > 0:
            # No plant data in source - auto-calculate
            print(f"  ⓘ Not in source, calculating from furnace data...")
            try:
                calc = TechnoPlantCalculator()
                plant_data, calc_details = calc.calculate_plant_consolidated(self.plant, report_month)

                if plant_data:
                    print(f"  ✓ Calculated: {len(plant_data)} parameters")
                else:
                    print(f"  ⊘ No data to calculate")

            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
                errors.append(str(e))
        else:
            print(f"  ⊘ No furnace data to calculate from")

        # Step 7: Report
        print(f"\n{'='*80}")
        print(f"INSERTION RESULTS")
        print(f"{'='*80}")

        if errors:
            print(f"\n✗ {len(errors)} error(s):")
            for error in errors:
                print(f"  • {error}")
            return False

        print(f"\n✓ SUCCESS")
        print(f"  Furnaces inserted: {inserted_count}")
        print(f"  Plant consolidated: {'from source' if plant_data_from_source else 'auto-calculated'}")

        print(f"\n{'='*80}\n")

        return True

    def _identify_furnace(self, row: Dict) -> Optional[str]:
        """Identify furnace from parameter or section"""
        param = str(row.get('parameter', '')).upper()
        section = str(row.get('section', '')).upper()
        search_text = param + ' ' + section

        furnace_patterns = {
            'BF-1': ['BF-1', 'BF 1', 'BF#1'],
            'BF-2': ['BF-2', 'BF 2', 'BF#2'],
            'BF-3': ['BF-3', 'BF 3', 'BF#3'],
            'BF-4': ['BF-4', 'BF 4', 'BF#4'],
            'BF-5': ['BF-5', 'BF 5', 'BF#5'],
            'BF-6': ['BF-6', 'BF 6', 'BF#6'],
            'BF-7': ['BF-7', 'BF 7', 'BF#7'],
            'BF-8': ['BF-8', 'BF 8', 'BF#8'],
        }

        for furnace, patterns in furnace_patterns.items():
            for pattern in patterns:
                if pattern in search_text:
                    return furnace

        return None


def smart_extract_and_insert(
    plant: str,
    extractor_type: str,
    excel_file: str,
    report_month: str,
    extractor_module: Any = None,
    auto_insert: bool = False
) -> bool:
    """
    Main entry point for smart extraction

    Intelligently handles:
    - Plant data from source (if available)
    - Auto-calculated plant data (if not in source)
    """

    init_db()

    if extractor_module is None:
        try:
            module_name = f'excel_extractor_{plant.lower()}_{extractor_type}'
            extractor_module = __import__(module_name)
        except ImportError as e:
            print(f"✗ Could not load extractor: {e}")
            return False

    adapter = SmartExtractorAdapter(plant)
    return adapter.extract_and_insert(
        extractor_module=extractor_module,
        excel_file=excel_file,
        report_month=report_month,
        auto_insert=auto_insert
    )


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Smart Extractor Adapter')
    parser.add_argument('plant', help='Plant code (BSP, DSP, RSP, BSL, ISP)')
    parser.add_argument('extractor_type', help='Extractor type (oisco, techno, rsp)')
    parser.add_argument('excel_file', help='Path to Excel file')
    parser.add_argument('--month', default='2026-05', help='Report month (YYYY-MM)')
    parser.add_argument('--auto-insert', action='store_true', help='Auto-insert without confirmation')

    args = parser.parse_args()

    success = smart_extract_and_insert(
        plant=args.plant,
        extractor_type=args.extractor_type,
        excel_file=args.excel_file,
        report_month=args.month,
        auto_insert=args.auto_insert
    )

    sys.exit(0 if success else 1)
