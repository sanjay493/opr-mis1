"""
Excel Extractor to JSON Converter

Adapts output from existing Excel extractors to new JSON-based techno system.

Workflow:
  1. Run existing Excel extractors (excel_extractor_bsp_techno.py, excel_extractor_bsp_oisco.py)
  2. Extract parameter data (plant-level or section-level)
  3. Convert to JSON format (furnace-wise or plant-level)
  4. Insert into techno_furnace_data and techno_plant_data tables
  5. Auto-calculate plant consolidated
  6. Auto-calculate SAIL consolidated
"""

import json
import logging
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from db import insert_techno_furnace_data, insert_techno_plant_data
from techno_json_utils import TechnoPlantCalculator, TechnoSAILCalculator
from parameter_naming import normalize_parameter_name

logger = logging.getLogger("excel_to_json_converter")


@dataclass
class ParameterRow:
    """Represents a single parameter from extractor output"""
    group_code: str          # IRON_MAKING, SMS, COKE_SINTER, etc.
    section: str             # "Blast Furnaces", "SMS-II", etc.
    parameter: str           # "Coke Rate", "BF Productivity", etc.
    unit: str                # "Kg/THM", "T/m³/day", etc.
    value: Optional[float]   # Actual value
    plant: str               # "BSP", "DSP", etc.
    month: str               # "2026-04" (YYYY-MM)
    source: str = "Excel"    # Where data came from


class ExcelToJsonConverter:
    """Convert existing Excel extractor output to JSON format"""

    # Map section names to furnace identifiers
    FURNACE_PATTERNS = {
        'BF-1': ['BF 1', 'BF-1', 'BF#1', 'BF 01'],
        'BF-2': ['BF 2', 'BF-2', 'BF#2', 'BF 02'],
        'BF-3': ['BF 3', 'BF-3', 'BF#3', 'BF 03'],
        'BF-4': ['BF 4', 'BF-4', 'BF#4', 'BF 04'],
        'BF-5': ['BF 5', 'BF-5', 'BF#5', 'BF 05'],
        'BF-6': ['BF 6', 'BF-6', 'BF#6', 'BF 06'],
        'BF-7': ['BF 7', 'BF-7', 'BF#7', 'BF 07'],
        'BF-8': ['BF 8', 'BF-8', 'BF#8', 'BF 08'],
    }

    # Blast furnace-specific parameter groups
    BF_GROUPS = {'IRON_MAKING', 'BLAST_FURNACE', 'BF_OPERATIONS'}

    def __init__(self, plant: str):
        self.plant = plant
        self.logger = logging.getLogger(f"{__name__}.{plant}")

    def convert_parameter_rows(
        self,
        parameter_rows: List[ParameterRow],
        report_month: str
    ) -> Tuple[Dict[str, Dict[str, Any]], str]:
        """
        Convert parameter rows from Excel extractor to JSON furnace data

        Args:
            parameter_rows: List of ParameterRow objects from extractor
            report_month: "YYYY-MM" format

        Returns:
            (furnace_data_dict, preview_text)
        """

        furnace_data = {}

        # Identify furnaces from parameter sections
        furnaces_used = set()

        for row in parameter_rows:
            if row.value is None:
                continue

            # Try to identify furnace from section name or parameter name
            furnace = self._identify_furnace_from_section(row.section, row.parameter)

            if furnace:
                furnaces_used.add(furnace)
                # Normalize parameter name to universal standard
                param_name = normalize_parameter_name(row.parameter)

                if furnace not in furnace_data:
                    furnace_data[furnace] = {}

                furnace_data[furnace][param_name] = {
                    'value': float(row.value),
                    'unit': row.unit,
                    'source': row.source,
                    'section': row.section
                }

        self.logger.info(
            f"Converted {len(parameter_rows)} parameters to {len(furnace_data)} furnaces"
        )

        # Generate preview
        preview = self._generate_preview(furnace_data, report_month, furnaces_used)

        return furnace_data, preview

    def _identify_furnace_from_section(self, section: str, parameter: str = '') -> Optional[str]:
        """
        Try to identify furnace name from section string or parameter name

        Returns:
            "BF-1", "BF-2", etc., or None if not a furnace section
        """

        search_text = (section or '') + ' ' + (parameter or '')

        if not search_text.strip():
            return None

        text_upper = search_text.upper()

        for furnace, patterns in self.FURNACE_PATTERNS.items():
            for pattern in patterns:
                if pattern.upper() in text_upper:
                    return furnace

        return None

    def _generate_preview(
        self,
        furnace_data: Dict[str, Dict[str, Any]],
        report_month: str,
        furnaces_used: set
    ) -> str:
        """Generate human-readable preview of converted data"""

        lines = []
        lines.append(f"\n{'='*80}")
        lines.append(f"EXCEL TO JSON CONVERSION PREVIEW")
        lines.append(f"{'='*80}")
        lines.append(f"Plant: {self.plant}")
        lines.append(f"Report Month: {report_month}")
        lines.append(f"Source: Excel Extractors")
        lines.append(f"\n")

        if not furnace_data:
            lines.append("NO FURNACE DATA CONVERTED")
            return "\n".join(lines)

        for furnace in sorted(furnace_data.keys()):
            data = furnace_data[furnace]
            lines.append(f"\n{furnace}:")
            lines.append("-" * 60)

            for param, info in sorted(data.items()):
                value = info['value']
                unit = info['unit']
                section = info.get('section', 'N/A')
                source = info['source']
                lines.append(
                    f"  {param:30} = {value:12.2f} {unit:15} [{section:25}]"
                )

            lines.append("")

        # Summary
        lines.append(f"\n{'='*80}")
        lines.append("CONVERSION SUMMARY:")
        total_params = sum(len(data) for data in furnace_data.values())
        lines.append(f"  Furnaces: {len(furnace_data)}")
        lines.append(f"  Total parameters: {total_params}")
        lines.append(f"  Avg params/furnace: {total_params/len(furnace_data):.1f}" if furnace_data else "")
        lines.append(f"{'='*80}\n")

        return "\n".join(lines)


class JsonDataManager:
    """Insert and manage JSON data in database"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.JsonDataManager")

    def insert_furnace_data(
        self,
        plant: str,
        furnace_data: Dict[str, Dict[str, Any]],
        report_month: str
    ) -> int:
        """
        Insert furnace data into techno_furnace_data table

        Returns:
            Number of furnaces inserted
        """

        inserted_count = 0

        for furnace, params in furnace_data.items():
            if not params:
                self.logger.debug(f"Skipping {furnace} - no data")
                continue

            try:
                # Remove 'section' key before inserting (it was for preview only)
                clean_data = {}
                for param, info in params.items():
                    clean_data[param] = {
                        'value': info['value'],
                        'unit': info['unit'],
                        'source': info['source']
                    }

                insert_techno_furnace_data(
                    plant=plant,
                    furnace=furnace,
                    report_month=report_month,
                    data=clean_data
                )
                inserted_count += 1
                self.logger.info(f"Inserted {furnace}: {len(clean_data)} parameters")

            except Exception as e:
                self.logger.error(f"Error inserting {furnace}: {e}")

        return inserted_count

    def calculate_and_insert_plant_consolidated(
        self,
        plant: str,
        report_month: str
    ) -> bool:
        """
        Calculate plant consolidated from furnaces and insert

        Returns:
            True if successful
        """

        try:
            calculator = TechnoPlantCalculator()
            plant_data, calc_details = calculator.calculate_plant_consolidated(
                plant, report_month
            )

            if not plant_data:
                self.logger.warning(f"No plant data to insert for {plant}")
                return False

            insert_techno_plant_data(
                plant=plant,
                report_month=report_month,
                data=plant_data,
                calculation_details=calc_details
            )

            self.logger.info(f"Inserted plant consolidated for {plant}: {len(plant_data)} parameters")
            return True

        except Exception as e:
            self.logger.error(f"Error calculating plant consolidated: {e}")
            return False

    def calculate_and_insert_sail_consolidated(self, report_month: str) -> bool:
        """
        Calculate SAIL consolidated and insert

        Returns:
            True if successful
        """

        try:
            calculator = TechnoSAILCalculator()
            sail_data, calc_method = calculator.calculate_sail_consolidated(report_month)

            if not sail_data:
                self.logger.warning("No SAIL data to insert")
                return False

            from db import insert_techno_sail_consolidated

            insert_techno_sail_consolidated(
                report_month=report_month,
                data=sail_data,
                calculation_method=calc_method
            )

            self.logger.info(f"Inserted SAIL consolidated: {len(sail_data)} parameters")
            return True

        except Exception as e:
            self.logger.error(f"Error calculating SAIL consolidated: {e}")
            return False


def process_excel_extraction(
    plant: str,
    parameter_rows: List[Dict[str, Any]],
    report_month: str,
    auto_calculate_plant: bool = True,
    auto_calculate_sail: bool = False
) -> Tuple[int, str]:
    """
    Main function to process Excel extraction and convert to JSON

    Args:
        plant: Plant code (BSP, DSP, etc.)
        parameter_rows: List of parameter dicts from extractor
        report_month: "YYYY-MM" format
        auto_calculate_plant: Whether to auto-calculate plant consolidated
        auto_calculate_sail: Whether to auto-calculate SAIL consolidated

    Returns:
        (furnaces_inserted, preview_text)
    """

    # Convert to ParameterRow objects
    param_rows = [
        ParameterRow(
            group_code=row.get('group_code', ''),
            section=row.get('section', ''),
            parameter=row.get('parameter', ''),
            unit=row.get('unit', ''),
            value=row.get('actual'),
            plant=plant,
            month=report_month
        )
        for row in parameter_rows
    ]

    # Convert to JSON
    converter = ExcelToJsonConverter(plant)
    furnace_data, preview = converter.convert_parameter_rows(param_rows, report_month)

    # Insert to database
    manager = JsonDataManager()
    count = manager.insert_furnace_data(plant, furnace_data, report_month)

    # Auto-calculate plant consolidated
    if auto_calculate_plant and count > 0:
        manager.calculate_and_insert_plant_consolidated(plant, report_month)

    # Auto-calculate SAIL consolidated
    if auto_calculate_sail:
        manager.calculate_and_insert_sail_consolidated(report_month)

    return count, preview


# ============================================================================
# Example usage / CLI
# ============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python excel_to_json_converter.py <plant> <report_month>")
        print("Example: python excel_to_json_converter.py BSP 2026-05")
        print("\nNote: This is a helper tool. See process_excel_extraction() for usage.")
        sys.exit(0)

    plant = sys.argv[1].upper()
    month = sys.argv[2]

    print(f"\n[INFO] Excel to JSON Converter")
    print(f"[INFO] Plant: {plant}, Month: {month}")
    print(f"[INFO] This tool is designed to be called from existing extractors.")
    print(f"[INFO] See source code for integration examples.")
