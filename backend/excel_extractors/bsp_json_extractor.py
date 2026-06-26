"""
BSP JSON-based Techno Furnace Data Extractor

Extracts furnace-wise techno parameters from BSP Excel files
and stores them in JSON format in techno_furnace_data table.

This is a simplified example that can be adapted to your actual Excel structure.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional
import openpyxl

from techno_json_utils import TechnoFurnaceExtractor
from production_utils import get_hm_production_for_furnace

logger = logging.getLogger(__name__)


class BSPFurnaceExtractor(TechnoFurnaceExtractor):
    """Extract BSP furnace-wise techno data from Excel files"""

    def __init__(self):
        super().__init__(plant='BSP')
        self.logger = logging.getLogger(f"{__name__}.BSP")

    def _identify_furnaces(self, pdf_rows) -> List[str]:
        """
        Identify furnaces from Excel rows

        For BSP, expected furnaces are: BF-4, BF-6, BF-7, BF-8

        Returns: List of furnace names
        """
        furnaces = set()

        for row in pdf_rows:
            # Look for patterns like "BF-4", "BF-6", "BF-7", "BF-8"
            if isinstance(row, dict):
                row_text = str(row.values())
            else:
                row_text = str(row)

            # Match BF with number: "BF-1", "BF#1", "BF 1", etc.
            matches = re.findall(r'BF[-#\s]?([1-8])', row_text)
            for num in matches:
                furnaces.add(f'BF-{num}')

        # Return sorted list
        return sorted(list(furnaces))

    def _extract_param_for_furnace(self, pdf_rows, furnace: str, param: str) -> Optional[float]:
        """
        Extract specific parameter value for a furnace

        This is a simplified example. Your actual implementation should:
        1. Parse the Excel structure specific to BSP
        2. Find the row for the parameter
        3. Find the column for the furnace
        4. Extract and parse the value

        Args:
            pdf_rows: List of Excel rows or dicts
            furnace: e.g., "BF-8"
            param: e.g., "Coke Rate"

        Returns:
            float value or None
        """

        for row in pdf_rows:
            row_text = str(row).upper()

            # Check if this row contains the furnace
            if furnace.upper() not in row_text:
                continue

            # Check if this row contains the parameter
            if param.upper() not in row_text:
                continue

            # Try to extract a numeric value from this row
            # Look for numbers with optional decimals
            numbers = re.findall(r'(\d+\.?\d*)', str(row))

            if numbers:
                try:
                    # Return the first number found
                    return float(numbers[-1])  # Last number is usually the value
                except ValueError:
                    continue

        return None

    def extract_furnace_data(self, pdf_rows, report_month: str) -> List[Dict[str, Any]]:
        """
        Extract furnace-level data from Excel rows

        Overrides parent to add BSP-specific logic if needed.

        Returns:
            List of furnace records ready to insert into DB
        """

        furnaces = self._identify_furnaces(pdf_rows)

        if not furnaces:
            self.logger.warning(f"No furnaces identified in {report_month}")
            return []

        furnace_records = []

        for furnace in furnaces:
            data = {}

            # Extract all standard parameters
            for param, unit in self.PARAM_UNITS.items():
                value = self._extract_param_for_furnace(pdf_rows, furnace, param)

                if value is not None:
                    data[param] = {
                        'value': float(value),
                        'unit': unit,
                        'source': 'Excel'
                    }

            # If HM Production not extracted from Excel,
            # try to fetch from production_table
            if 'HM Production' not in data:
                hm_value = get_hm_production_for_furnace(
                    self.plant, furnace, report_month
                )
                if hm_value:
                    data['HM Production'] = {
                        'value': hm_value,
                        'unit': 'T',
                        'source': 'production_table'
                    }

            furnace_record = {
                'plant': self.plant,
                'furnace': furnace,
                'report_month': report_month,
                'data': data
            }

            furnace_records.append(furnace_record)

            self.logger.info(
                f"Extracted {furnace}: {len(data)} parameters"
            )

        return furnace_records


def extract_from_excel(file_path: str, report_month: str) -> List[Dict[str, Any]]:
    """
    Public API to extract BSP furnace data from Excel file

    Args:
        file_path: Path to Excel file
        report_month: "YYYY-MM" format

    Returns:
        List of furnace records
    """

    try:
        # Load Excel file
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active

        # Read all rows
        pdf_rows = []
        for row in ws.iter_rows(values_only=True):
            if any(row):  # Skip empty rows
                pdf_rows.append(row)

        # Extract using BSP extractor
        extractor = BSPFurnaceExtractor()
        furnace_records = extractor.extract_furnace_data(pdf_rows, report_month)

        # Save to database
        extractor.save_furnace_data(furnace_records)

        logging.info(
            f"Extracted {len(furnace_records)} furnace records from {file_path}"
        )

        return furnace_records

    except Exception as e:
        logging.error(f"Error extracting from {file_path}: {e}")
        raise


# Example usage
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python bsp_json_extractor.py <excel_file> <month>")
        print("Example: python bsp_json_extractor.py bsp_data.xlsx 2026-06")
        sys.exit(1)

    excel_file = sys.argv[1]
    month = sys.argv[2]

    try:
        records = extract_from_excel(excel_file, month)
        print(f"SUCCESS: Extracted {len(records)} furnace records")

        # Print summary
        for record in records:
            furnace = record['furnace']
            params = len(record['data'])
            print(f"  {furnace}: {params} parameters")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
