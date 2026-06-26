#!/usr/bin/env python3
"""
Excel Cell Mapper - Map Excel cells to parameters and extract data for multiple months

Usage:
    1. Create a mapping file (JSON) with Excel cell locations
    2. Run extraction with date range (from_month to till_month)
    3. Automatically pulls all months' data
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import openpyxl


@dataclass
class CellMapping:
    """Maps a parameter to an Excel cell location"""
    parameter: str          # "Coke Rate", "BF Productivity", etc.
    cell: str              # "B5", "C10", etc.
    unit: str              # "Kg/THM", "T/m³/day", etc.
    furnace: Optional[str] = None  # "BF-1", "BF-2", etc. (if furnace-specific)


class ExcelCellExtractor:
    """Extract data using cell mappings"""

    def __init__(self, excel_file: str):
        self.excel_file = Path(excel_file)
        self.workbook = openpyxl.load_workbook(self.excel_file, data_only=True)

    def extract_from_mapping(
        self,
        mappings: List[CellMapping],
        sheet_name: str = "Sheet1"
    ) -> Dict[str, float]:
        """
        Extract parameter values from Excel using cell mappings

        Args:
            mappings: List of CellMapping objects
            sheet_name: Which sheet to read from

        Returns:
            {parameter: value, ...}
        """
        sheet = self.workbook[sheet_name]
        data = {}

        for mapping in mappings:
            try:
                cell_value = sheet[mapping.cell].value

                if cell_value is None:
                    print(f"  ⊘ {mapping.parameter} ({mapping.cell}): No value")
                    continue

                # Convert to float
                value = float(cell_value)
                data[mapping.parameter] = value
                print(f"  ✓ {mapping.parameter} ({mapping.cell}): {value}")

            except (ValueError, TypeError):
                print(f"  ✗ {mapping.parameter} ({mapping.cell}): Invalid value: {cell_value}")
            except KeyError:
                print(f"  ✗ {mapping.parameter} ({mapping.cell}): Cell not found")

        return data

    def close(self):
        self.workbook.close()


class MappingManager:
    """Manage Excel cell mappings"""

    @staticmethod
    def create_mapping_template(output_file: str):
        """Create a template mapping file for user to fill in"""
        template = {
            "file": "BSP-3-page-TechMay'26.xlsx",
            "sheet_name": "Sheet1",
            "plant": "BSP",
            "report_month": "2026-05",
            "notes": "Map Excel cell locations to parameters. E.g., B5 = Coke Rate value",
            "mappings": [
                {
                    "parameter": "Coke Rate",
                    "cell": "B5",
                    "unit": "Kg/THM",
                    "furnace": None,
                    "notes": "Find in Excel and update cell reference"
                },
                {
                    "parameter": "BF Productivity",
                    "cell": "C5",
                    "unit": "T/m³/day",
                    "furnace": None,
                    "notes": "Find in Excel and update cell reference"
                },
                {
                    "parameter": "CDI",
                    "cell": "D5",
                    "unit": "Kg/THM",
                    "furnace": None,
                    "notes": "Find in Excel and update cell reference"
                }
            ]
        }

        with open(output_file, 'w') as f:
            json.dump(template, f, indent=2)

        print(f"✓ Template created: {output_file}")
        return template

    @staticmethod
    def load_mapping(file: str) -> Tuple[Dict, List[CellMapping]]:
        """Load mapping from JSON file"""
        with open(file, 'r') as f:
            data = json.load(f)

        config = {
            'file': data.get('file'),
            'sheet_name': data.get('sheet_name', 'Sheet1'),
            'plant': data.get('plant'),
            'report_month': data.get('report_month'),
        }

        mappings = [
            CellMapping(
                parameter=m['parameter'],
                cell=m['cell'],
                unit=m['unit'],
                furnace=m.get('furnace')
            )
            for m in data.get('mappings', [])
        ]

        return config, mappings

    @staticmethod
    def save_mapping(output_file: str, config: Dict, mappings: List[CellMapping]):
        """Save mapping to JSON file"""
        data = {
            'file': config['file'],
            'sheet_name': config.get('sheet_name', 'Sheet1'),
            'plant': config['plant'],
            'report_month': config['report_month'],
            'mappings': [
                {
                    'parameter': m.parameter,
                    'cell': m.cell,
                    'unit': m.unit,
                    'furnace': m.furnace
                }
                for m in mappings
            ]
        }

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"✓ Mapping saved: {output_file}")


class MultiMonthExtractor:
    """Extract data for multiple months using cell mappings"""

    def __init__(self, plant: str):
        self.plant = plant

    def extract_month_range(
        self,
        excel_file: str,
        mappings: List[CellMapping],
        from_month: str,  # "2026-01"
        till_month: str,  # "2026-05"
        sheet_name: str = "Sheet1"
    ) -> Dict[str, Dict[str, float]]:
        """
        Extract data for all months from_month to till_month

        Returns:
            {month: {parameter: value}, ...}
        """

        # Parse month range
        from_year, from_m = map(int, from_month.split('-'))
        till_year, till_m = map(int, till_month.split('-'))

        months = []
        year, month = from_year, from_m

        while (year, month) <= (till_year, till_m):
            months.append(f"{year:04d}-{month:02d}")
            month += 1
            if month > 12:
                month = 1
                year += 1

        print(f"\n[EXTRACTING {len(months)} MONTHS]")
        print(f"  From: {from_month}")
        print(f"  Till: {till_month}")
        print(f"  Months: {', '.join(months)}\n")

        # Extract each month (in this case, same file - but structure ready for multi-file)
        all_data = {}

        extractor = ExcelCellExtractor(excel_file)

        for month in months:
            print(f"Month: {month}")
            data = extractor.extract_from_mapping(mappings, sheet_name)
            all_data[month] = data

        extractor.close()

        return all_data


def main():
    """Example usage"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python excel_cell_mapper.py <command>")
        print("Commands:")
        print("  create-template <output_file>  - Create mapping template")
        print("  extract <mapping_file>         - Extract data using mapping")
        print("\nExample:")
        print("  python excel_cell_mapper.py create-template bsp_mapping.json")
        print("  python excel_cell_mapper.py extract bsp_mapping.json")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'create-template':
        output = sys.argv[2] if len(sys.argv) > 2 else 'mapping_template.json'
        MappingManager.create_mapping_template(output)

    elif command == 'extract':
        mapping_file = sys.argv[2]
        config, mappings = MappingManager.load_mapping(mapping_file)

        print("\n" + "="*80)
        print("EXCEL CELL MAPPING EXTRACTOR")
        print("="*80)
        print(f"\nConfiguration:")
        print(f"  Plant: {config['plant']}")
        print(f"  File: {config['file']}")
        print(f"  Sheet: {config['sheet_name']}")
        print(f"  Mappings: {len(mappings)} parameters\n")

        extractor = ExcelCellExtractor(config['file'])
        data = extractor.extract_from_mapping(mappings, config['sheet_name'])

        print(f"\n{'='*80}")
        print("EXTRACTED DATA")
        print("="*80)
        for param, value in sorted(data.items()):
            print(f"  {param}: {value}")

        extractor.close()


if __name__ == '__main__':
    main()
