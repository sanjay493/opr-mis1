#!/usr/bin/env python3
"""
Complete workflow: Extract from Excel cells → Insert into database

Usage:
    python extract_and_insert.py <mapping_file> [--preview-only]

Example:
    python extract_and_insert.py bsp_techno_mapping.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from excel_cell_mapper import ExcelCellExtractor, MappingManager, CellMapping
from db import insert_techno_furnace_data, get_techno_furnace_data, get_techno_plant_data
from techno_json_utils import TechnoPlantCalculator


class ExtractionAndInsertionPipeline:
    """Complete pipeline: Extract → Validate → Preview → Insert → Verify"""

    def __init__(self, mapping_file: str):
        self.mapping_file = Path(mapping_file)
        self.config = None
        self.mappings = None
        self.extracted_data = None

    def run(self, preview_only: bool = False):
        """Run complete pipeline"""
        print("\n" + "="*80)
        print("EXTRACTION AND INSERTION PIPELINE")
        print("="*80)

        # Step 1: Load mapping
        self._step_load_mapping()

        # Step 2: Extract data
        self._step_extract_data()

        # Step 3: Preview
        self._step_preview()

        # Step 4: Validate
        if not self._step_validate():
            return False

        # Step 5: Confirm
        if preview_only:
            print("\n[PREVIEW MODE] Stopping before insertion.")
            return True

        if not self._step_confirm():
            print("\nInsertion cancelled.")
            return False

        # Step 6: Insert
        self._step_insert()

        # Step 7: Verify
        self._step_verify()

        return True

    def _step_load_mapping(self):
        """Step 1: Load mapping from JSON file"""
        print("\n[STEP 1] LOADING MAPPING FILE")
        print("-" * 80)

        if not self.mapping_file.exists():
            print(f"✗ File not found: {self.mapping_file}")
            sys.exit(1)

        self.config, self.mappings = MappingManager.load_mapping(str(self.mapping_file))

        print(f"✓ Loaded mapping: {self.mapping_file.name}")
        print(f"  Plant: {self.config['plant']}")
        print(f"  File: {self.config['file']}")
        print(f"  Sheet: {self.config['sheet_name']}")
        print(f"  Mappings: {len(self.mappings)} parameters")

    def _step_extract_data(self):
        """Step 2: Extract data from Excel using cell mappings"""
        print("\n[STEP 2] EXTRACTING DATA FROM EXCEL")
        print("-" * 80)

        excel_file = self.config['file']
        sheet_name = self.config['sheet_name']

        if not Path(excel_file).exists():
            print(f"✗ Excel file not found: {excel_file}")
            sys.exit(1)

        extractor = ExcelCellExtractor(excel_file)
        self.extracted_data = extractor.extract_from_mapping(self.mappings, sheet_name)
        extractor.close()

        print(f"\n✓ Extracted {len(self.extracted_data)} parameters")

    def _step_preview(self):
        """Step 3: Show preview of extracted data"""
        print("\n[STEP 3] PREVIEW OF EXTRACTED DATA")
        print("-" * 80)

        print(f"\nPlant: {self.config['plant']}")
        print(f"Month: {self.config['report_month']}\n")

        if not self.extracted_data:
            print("⊘ No data extracted")
            return

        for param in sorted(self.extracted_data.keys()):
            value = self.extracted_data[param]

            # Find unit from mapping
            unit = None
            for mapping in self.mappings:
                if mapping.parameter == param:
                    unit = mapping.unit
                    break

            if unit:
                print(f"  {param:30} = {value:12.2f} {unit}")
            else:
                print(f"  {param:30} = {value:12.2f}")

    def _step_validate(self) -> bool:
        """Step 4: Validate extracted data"""
        print("\n[STEP 4] VALIDATING DATA")
        print("-" * 80)

        errors = []

        # Check all values are numbers
        for param, value in self.extracted_data.items():
            if not isinstance(value, (int, float)):
                errors.append(f"{param}: Invalid type {type(value)}")
            elif value < 0:
                errors.append(f"{param}: Negative value {value}")

        # Check mappings match
        if len(self.extracted_data) == 0:
            errors.append("No parameters extracted")

        if errors:
            print(f"\n✗ Validation failed ({len(errors)} errors):\n")
            for error in errors:
                print(f"  • {error}")
            return False

        print(f"\n✓ All validation checks passed")
        print(f"  • {len(self.extracted_data)} parameters valid")
        print(f"  • All values are numbers")
        print(f"  • No negative values")

        return True

    def _step_confirm(self) -> bool:
        """Step 5: Ask user confirmation before insert"""
        print("\n[STEP 5] CONFIRMATION")
        print("-" * 80)

        response = input("\nInsert this data into database? (yes/no): ").strip().lower()
        return response == 'yes'

    def _step_insert(self):
        """Step 6: Insert data into database"""
        print("\n[STEP 6] INSERTING INTO DATABASE")
        print("-" * 80)

        plant = self.config['plant']
        month = self.config['report_month']

        # Prepare data for insertion
        furnace_data = {}

        # If no furnace specified in mapping, it's plant-level data
        # Create a single furnace entry (or merge with existing)
        for param, value in self.extracted_data.items():
            # Find unit from mapping
            unit = None
            furnace = None
            for mapping in self.mappings:
                if mapping.parameter == param:
                    unit = mapping.unit
                    furnace = mapping.furnace
                    break

            if furnace:
                if furnace not in furnace_data:
                    furnace_data[furnace] = {}
                furnace_data[furnace][param] = {
                    'value': float(value),
                    'unit': unit,
                    'source': 'Excel-Mapped'
                }
            else:
                # Plant-level - store in all furnaces for averaging
                # Or in a special "PLANT" furnace
                if 'PLANT' not in furnace_data:
                    furnace_data['PLANT'] = {}
                furnace_data['PLANT'][param] = {
                    'value': float(value),
                    'unit': unit,
                    'source': 'Excel-Mapped'
                }

        print(f"\nInserting data for {plant} ({month}):\n")

        inserted_count = 0
        errors = []

        for furnace, params in furnace_data.items():
            try:
                if furnace == 'PLANT':
                    print(f"  ⓘ Plant-level data: {len(params)} parameters")
                    # Plant-level data - might store separately or skip furnace insert
                    # For now, skip furnace insert for PLANT
                    continue
                else:
                    insert_techno_furnace_data(plant, furnace, month, params)
                    print(f"  ✓ {furnace}: {len(params)} parameters inserted")
                    inserted_count += 1

            except Exception as e:
                error_msg = f"{furnace}: {str(e)}"
                errors.append(error_msg)
                print(f"  ✗ {furnace}: ERROR - {str(e)}")

        # Calculate plant consolidated
        print(f"\nCalculating plant consolidated:\n")

        try:
            calc = TechnoPlantCalculator()
            plant_data, calc_details = calc.calculate_plant_consolidated(plant, month)

            if plant_data:
                print(f"  ✓ Calculated: {len(plant_data)} parameters")
            else:
                print(f"  ⓘ No furnace data to calculate from")

        except Exception as e:
            error_msg = f"Plant calculation: {str(e)}"
            errors.append(error_msg)
            print(f"  ✗ ERROR: {str(e)}")

        # Report results
        print(f"\n{'='*80}")
        print("INSERTION RESULTS")
        print("="*80)

        if errors:
            print(f"\n✗ {len(errors)} error(s):")
            for error in errors:
                print(f"  • {error}")
            return

        print(f"\n✓ Successfully inserted data for {plant}")

    def _step_verify(self):
        """Step 7: Verify insertion by retrieving from database"""
        print("\n[STEP 7] VERIFYING INSERTION")
        print("-" * 80)

        plant = self.config['plant']
        month = self.config['report_month']

        try:
            furnace_data = get_techno_furnace_data(plant, month)
            print(f"\n✓ Furnace data in database: {len(furnace_data)} furnaces")

            for furnace in sorted(furnace_data.keys()):
                params = furnace_data[furnace]
                print(f"  {furnace}: {len(params)} parameters")

            plant_info = get_techno_plant_data(plant, month)
            if plant_info.get('data'):
                print(f"\n✓ Plant consolidated in database: {len(plant_info['data'])} parameters")

        except Exception as e:
            print(f"\n⚠️  Could not verify: {e}")

        print("\n" + "="*80)
        print("✅ PIPELINE COMPLETE")
        print("="*80 + "\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_and_insert.py <mapping_file> [--preview-only]")
        print("\nExample:")
        print("  python extract_and_insert.py bsp_techno_mapping.json")
        print("  python extract_and_insert.py bsp_techno_mapping.json --preview-only")
        sys.exit(1)

    mapping_file = sys.argv[1]
    preview_only = '--preview-only' in sys.argv

    pipeline = ExtractionAndInsertionPipeline(mapping_file)
    success = pipeline.run(preview_only=preview_only)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
