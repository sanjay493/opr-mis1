#!/usr/bin/env python3
"""
Unified Extractor Adapter

Adapts existing Excel extractors (OISCO, TechnoMya, DSP, RSP, BSL, ISP)
to work with new JSON-based DB architecture

Bridges:
  - Existing extractors (excel_extractor_*.py) → extract_preview() output
  - New converter layer → JSON structure
  - New DB layer → techno_furnace_data table
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

sys.path.insert(0, 'excel_extractors')

from db import insert_techno_furnace_data, init_db
from techno_json_utils import TechnoPlantCalculator
from parameter_naming import normalize_parameter_name

logger = logging.getLogger(__name__)


class ExtractorAdapter:
    """Adapt existing extractors to new JSON DB architecture"""

    # Map plant codes to extractor modules
    EXTRACTORS = {
        'BSP': {
            'oisco': 'excel_extractor_bsp_oisco',
            'techno': 'excel_extractor_bsp_techno',
        },
        'DSP': {
            'rsp': 'excel_extractor_dsp_rsp',  # If exists
        },
        'RSP': {
            'rsp': 'excel_extractor_rsp_rsp',  # If exists
        },
    }

    def __init__(self, plant: str, extractor_type: str):
        """
        Initialize adapter

        Args:
            plant: Plant code (BSP, DSP, RSP, BSL, ISP)
            extractor_type: Type of extractor (oisco, techno, rsp, etc.)
        """
        self.plant = plant.upper()
        self.extractor_type = extractor_type.lower()
        self.extractor_module = None
        self._load_extractor()

    def _load_extractor(self):
        """Dynamically load extractor module"""
        try:
            # Try to load from EXTRACTORS mapping
            if self.plant in self.EXTRACTORS and self.extractor_type in self.EXTRACTORS[self.plant]:
                module_name = self.EXTRACTORS[self.plant][self.extractor_type]
                self.extractor_module = __import__(module_name)
                logger.info(f"Loaded extractor: {module_name}")
            else:
                # Try generic naming: excel_extractor_{plant}_{type}
                module_name = f'excel_extractor_{self.plant.lower()}_{self.extractor_type}'
                self.extractor_module = __import__(module_name)
                logger.info(f"Loaded extractor: {module_name}")

        except ImportError as e:
            logger.error(f"Could not load extractor for {self.plant} ({self.extractor_type}): {e}")
            raise

    def extract_and_convert(
        self,
        excel_file: str,
        report_month: str
    ) -> Tuple[Dict[str, Dict[str, Any]], str]:
        """
        Extract from Excel using existing extractor and convert to JSON format

        Args:
            excel_file: Path to Excel file
            report_month: Report month (YYYY-MM)

        Returns:
            (furnace_data_dict, preview_text)
        """

        print(f"\n{'='*80}")
        print(f"EXTRACTION: {self.plant} - {self.extractor_type.upper()}")
        print(f"{'='*80}")

        # Step 1: Call existing extractor
        print(f"\n[STEP 1] Calling existing extractor...")
        print(f"  File: {Path(excel_file).name}")
        print(f"  Month: {report_month}\n")

        try:
            result = self.extractor_module.extract_preview(excel_file, report_month)
            param_rows = result.get('techno_param_rows', [])

            if not param_rows:
                logger.error("No parameters extracted")
                return {}, "No parameters extracted"

            print(f"  ✓ Extracted {len(param_rows)} parameters")

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise

        # Step 2: Convert to JSON format
        print(f"\n[STEP 2] Converting to JSON format...")

        furnace_data = self._convert_to_json(param_rows)

        print(f"  ✓ Converted {sum(len(v) for v in furnace_data.values())} parameters")
        print(f"  ✓ {len(furnace_data)} furnaces with data")

        # Step 3: Generate preview
        preview = self._generate_preview(furnace_data, report_month)

        return furnace_data, preview

    def _convert_to_json(self, param_rows: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """
        Convert extractor output to JSON furnace data format

        Handles:
        - Parameter name normalization
        - Furnace identification
        - Null value filtering
        """

        furnace_data = {}

        for row in param_rows:
            value = row.get('actual')

            # Skip null values
            if value is None:
                continue

            # Try to identify furnace from parameter or section
            furnace = self._identify_furnace(row)

            # Normalize parameter name
            param_name = normalize_parameter_name(row.get('parameter', ''))

            # Skip if parameter name couldn't be normalized
            if not param_name:
                continue

            # Initialize furnace if needed
            if furnace and furnace not in furnace_data:
                furnace_data[furnace] = {}

            # Add parameter to furnace
            if furnace:
                furnace_data[furnace][param_name] = {
                    'value': float(value),
                    'unit': row.get('unit', ''),
                    'source': 'Excel-Extracted',
                    'section': row.get('section', ''),
                }

        return furnace_data

    def _identify_furnace(self, row: Dict) -> Optional[str]:
        """
        Identify furnace from parameter name or section

        Returns:
            "BF-1", "BF-2", etc., or None if not furnace-specific
        """

        param = str(row.get('parameter', '')).upper()
        section = str(row.get('section', '')).upper()

        search_text = param + ' ' + section

        # Look for furnace patterns
        furnace_patterns = {
            'BF-1': ['BF-1', 'BF 1', 'BF#1', 'BF 01'],
            'BF-2': ['BF-2', 'BF 2', 'BF#2', 'BF 02'],
            'BF-3': ['BF-3', 'BF 3', 'BF#3', 'BF 03'],
            'BF-4': ['BF-4', 'BF 4', 'BF#4', 'BF 04'],
            'BF-5': ['BF-5', 'BF 5', 'BF#5', 'BF 05'],
            'BF-6': ['BF-6', 'BF 6', 'BF#6', 'BF 06'],
            'BF-7': ['BF-7', 'BF 7', 'BF#7', 'BF 07'],
            'BF-8': ['BF-8', 'BF 8', 'BF#8', 'BF 08'],
        }

        for furnace, patterns in furnace_patterns.items():
            for pattern in patterns:
                if pattern in search_text:
                    return furnace

        return None

    def _generate_preview(self, furnace_data: Dict, report_month: str) -> str:
        """Generate human-readable preview"""

        lines = [
            f"\n{'='*80}",
            f"EXTRACTION PREVIEW",
            f"{'='*80}",
            f"Plant: {self.plant}",
            f"Month: {report_month}",
            f"Type: {self.extractor_type.upper()}",
            f"\n"
        ]

        if not furnace_data:
            lines.append("NO FURNACE DATA")
            return "\n".join(lines)

        for furnace in sorted(furnace_data.keys()):
            params = furnace_data[furnace]
            lines.append(f"\n{furnace}: {len(params)} parameters")
            lines.append("-" * 60)

            for param, info in sorted(params.items()):
                value = info['value']
                unit = info['unit']
                lines.append(f"  {param:30} = {value:12.2f} {unit}")

        lines.append(f"\n{'='*80}")
        lines.append(f"Summary:")
        lines.append(f"  Furnaces: {len(furnace_data)}")
        lines.append(f"  Total parameters: {sum(len(v) for v in furnace_data.values())}")
        lines.append(f"{'='*80}\n")

        return "\n".join(lines)


class UnifiedInsertionPipeline:
    """Insert extracted data into new JSON DB architecture"""

    def __init__(self, plant: str):
        self.plant = plant.upper()

    def insert_extracted_data(
        self,
        furnace_data: Dict[str, Dict[str, Any]],
        report_month: str,
        plant_data_from_source: Dict[str, Any] = None,
        auto_calculate_plant: bool = True
    ) -> bool:
        """
        Insert extracted furnace data into database

        Args:
            furnace_data: Furnace-wise data dict
            report_month: Report month (YYYY-MM)
            plant_data_from_source: Plant-level data from Excel (if available)
            auto_calculate_plant: Auto-calculate only if plant data not in source

        Returns:
            Success status
        """

        print(f"\n{'='*80}")
        print(f"INSERTING DATA INTO DATABASE")
        print(f"{'='*80}\n")

        inserted_count = 0
        errors = []

        # Insert furnace-wise data
        for furnace, params in furnace_data.items():
            if not params:
                print(f"  ⊘ {furnace}: No data")
                continue

            try:
                insert_techno_furnace_data(self.plant, furnace, report_month, params)
                print(f"  ✓ {furnace}: {len(params)} parameters")
                inserted_count += 1

            except Exception as e:
                error_msg = f"{furnace}: {str(e)}"
                errors.append(error_msg)
                print(f"  ✗ {furnace}: ERROR - {str(e)}")

        # Handle plant consolidated
        print(f"\nPlant consolidated:")

        if plant_data_from_source and len(plant_data_from_source) > 0:
            # Plant data exists in source - use it directly
            print(f"  ✓ Found in source file: {len(plant_data_from_source)} parameters")
            try:
                from db import insert_techno_plant_data
                insert_techno_plant_data(
                    plant=self.plant,
                    report_month=report_month,
                    data=plant_data_from_source,
                    calculation_details={'method': 'from_source', 'source': 'Excel-Extracted'}
                )
                print(f"  ✓ Inserted from source")
            except Exception as e:
                error_msg = f"Plant data insertion: {str(e)}"
                errors.append(error_msg)
                print(f"  ✗ ERROR: {str(e)}")

        elif auto_calculate_plant and inserted_count > 0:
            # No source data - auto-calculate from furnace data
            print(f"  ⓘ Not in source file, calculating from furnace data...")

            try:
                calc = TechnoPlantCalculator()
                plant_data, calc_details = calc.calculate_plant_consolidated(self.plant, report_month)

                if plant_data:
                    print(f"  ✓ Calculated: {len(plant_data)} parameters")
                else:
                    print(f"  ⊘ No data to calculate")

            except Exception as e:
                error_msg = f"Plant calculation: {str(e)}"
                errors.append(error_msg)
                print(f"  ✗ ERROR: {str(e)}")
        else:
            print(f"  ⊘ No plant data available")

        # Report results
        print(f"\n{'='*80}")
        print(f"INSERTION RESULTS")
        print(f"{'='*80}")

        if errors:
            print(f"\n✗ {len(errors)} error(s):")
            for error in errors:
                print(f"  • {error}")
            return False

        print(f"\n✓ Successfully inserted {inserted_count} furnaces")
        return True


def extract_and_insert(
    plant: str,
    extractor_type: str,
    excel_file: str,
    report_month: str,
    auto_insert: bool = False
) -> bool:
    """
    Main unified extraction and insertion workflow

    Args:
        plant: Plant code (BSP, DSP, RSP, etc.)
        extractor_type: Extractor type (oisco, techno, rsp, etc.)
        excel_file: Path to Excel file
        report_month: Report month (YYYY-MM)
        auto_insert: Auto-insert without confirmation

    Returns:
        Success status
    """

    init_db()

    # Step 1: Extract and convert
    adapter = ExtractorAdapter(plant, extractor_type)
    furnace_data, preview = adapter.extract_and_convert(excel_file, report_month)

    if not furnace_data:
        print("✗ No data to insert")
        return False

    # Step 2: Show preview
    print(preview)

    # Step 3: Confirm
    if not auto_insert:
        response = input("Insert this data into database? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Insertion cancelled")
            return False

    # Step 4: Insert
    pipeline = UnifiedInsertionPipeline(plant)
    return pipeline.insert_extracted_data(furnace_data, report_month)


if __name__ == '__main__':
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(description='Unified Extractor Adapter')
    parser.add_argument('plant', help='Plant code (BSP, DSP, RSP, BSL, ISP)')
    parser.add_argument('extractor_type', help='Extractor type (oisco, techno, rsp)')
    parser.add_argument('excel_file', help='Path to Excel file')
    parser.add_argument('--month', default='2026-05', help='Report month (YYYY-MM)')
    parser.add_argument('--auto-insert', action='store_true', help='Auto-insert without confirmation')

    args = parser.parse_args()

    success = extract_and_insert(
        plant=args.plant,
        extractor_type=args.extractor_type,
        excel_file=args.excel_file,
        report_month=args.month,
        auto_insert=args.auto_insert
    )

    sys.exit(0 if success else 1)
