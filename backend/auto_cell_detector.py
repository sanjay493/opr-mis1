#!/usr/bin/env python3
"""
Auto Cell Detector - Automatically detect cell locations from Excel

Features:
1. Scan Excel sheet for parameter names
2. Find corresponding values automatically
3. Generate mapping file
4. No manual cell location needed!

Usage:
    python auto_cell_detector.py <excel_file> [--plant BSP] [--sheet Sheet1]
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import openpyxl


class SmartCellDetector:
    """Automatically detect parameter locations in Excel"""

    # Known parameter names to search for
    KNOWN_PARAMETERS = {
        'Coke Rate': ['Coke Rate', 'Coke', 'CR', 'Coke (Kg/THM)'],
        'BF Productivity': ['BF Productivity', 'Productivity', 'BF Prod', 'Prod (T/m³/day)'],
        'CDI': ['CDI', 'Coke Dry Index'],
        'Slag Rate': ['Slag Rate', 'Slag', 'SR'],
        'Nut Coke Rate': ['Nut Coke Rate', 'Nut Coke', 'NCR'],
        'Fuel Rate': ['Fuel Rate', 'Fuel', 'FR'],
        'Energy': ['Energy', 'ENR', 'Energy (GJ/THM)'],
        'Pellet in Burden': ['Pellet in Burden', 'Pellet %', 'Pellet'],
        'Sinter in Burden': ['Sinter in Burden', 'Sinter %', 'Sinter'],
    }

    # Expected units
    PARAMETER_UNITS = {
        'Coke Rate': 'Kg/THM',
        'BF Productivity': 'T/m³/day',
        'CDI': 'Kg/THM',
        'Slag Rate': 'Kg/THM',
        'Nut Coke Rate': 'Kg/THM',
        'Fuel Rate': 'Kg/THM',
        'Energy': 'GJ/THM',
        'Pellet in Burden': '%',
        'Sinter in Burden': '%',
    }

    def __init__(self, excel_file: str):
        self.excel_file = Path(excel_file)
        self.workbook = openpyxl.load_workbook(self.excel_file, data_only=True)

    def detect_mappings(self, sheet_name: str = "Sheet1", scan_rows: int = 50) -> List[Dict]:
        """
        Auto-detect parameter locations in Excel

        Args:
            sheet_name: Which sheet to scan
            scan_rows: How many rows to scan (default: 50)

        Returns:
            List of detected mappings
        """
        sheet = self.workbook[sheet_name]
        detected = []

        print(f"\n[SCANNING EXCEL SHEET]")
        print(f"  Sheet: {sheet_name}")
        print(f"  Scanning: {scan_rows} rows")
        print(f"  Looking for: {len(self.KNOWN_PARAMETERS)} known parameters\n")

        # Scan for parameter names in column A (typical layout)
        for row_idx in range(1, scan_rows + 1):
            cell_value = sheet[f'A{row_idx}'].value

            if not cell_value:
                continue

            cell_text = str(cell_value).strip()

            # Check if this cell contains a known parameter name
            for param, keywords in self.KNOWN_PARAMETERS.items():
                for keyword in keywords:
                    if keyword.lower() in cell_text.lower():
                        # Found parameter! Now find the value
                        # Typically in column B (or next non-empty column)
                        value_cell = self._find_value_cell(sheet, row_idx)

                        if value_cell:
                            mapping = {
                                'parameter': param,
                                'cell': value_cell,
                                'unit': self.PARAMETER_UNITS.get(param, ''),
                                'furnace': None,
                                'source_cell': f'A{row_idx}',  # Where parameter name was found
                                'source_text': cell_text,
                                'confidence': 'high'
                            }
                            detected.append(mapping)
                            print(f"  ✓ {param}")
                            print(f"      Found at: A{row_idx} ('{cell_text}')")
                            print(f"      Value at: {value_cell}")
                            print()
                            break

        return detected

    def _find_value_cell(self, sheet, row_idx: int, max_columns: int = 10) -> Optional[str]:
        """
        Find the cell with actual numeric value for a parameter at given row

        Searches columns B, C, D, etc. for first numeric value
        """
        for col_idx in range(2, max_columns + 2):  # Columns B through K
            cell = sheet.cell(row=row_idx, column=col_idx)
            value = cell.value

            if value is None:
                continue

            try:
                # Try to convert to float
                float_val = float(value)
                # Valid number found
                col_letter = self._col_number_to_letter(col_idx)
                return f"{col_letter}{row_idx}"
            except (ValueError, TypeError):
                # Not a number, try next column
                continue

        return None

    @staticmethod
    def _col_number_to_letter(col_num: int) -> str:
        """Convert column number (1, 2, 3...) to letter (A, B, C...)"""
        result = ""
        while col_num > 0:
            col_num -= 1
            result = chr(65 + (col_num % 26)) + result
            col_num //= 26
        return result

    def close(self):
        self.workbook.close()


class AutoMappingGenerator:
    """Generate mapping file from auto-detected cells"""

    @staticmethod
    def generate_mapping(
        detected: List[Dict],
        excel_file: str,
        plant: str,
        report_month: str,
        sheet_name: str = "Sheet1"
    ) -> Dict:
        """
        Generate complete mapping file from detected cells

        Args:
            detected: List of detected mappings
            excel_file: Path to Excel file
            plant: Plant code (BSP, DSP, etc.)
            report_month: Report month (YYYY-MM)
            sheet_name: Sheet name

        Returns:
            Complete mapping configuration
        """
        mapping = {
            "file": str(excel_file),
            "sheet_name": sheet_name,
            "plant": plant,
            "report_month": report_month,
            "from_month": report_month,
            "till_month": report_month,
            "detected": True,
            "detection_notes": f"Auto-detected {len(detected)} parameters from Excel",
            "mappings": detected
        }

        return mapping

    @staticmethod
    def save_mapping(mapping: Dict, output_file: str):
        """Save mapping to JSON file"""
        with open(output_file, 'w') as f:
            json.dump(mapping, f, indent=2)

        print(f"\n✓ Mapping saved: {output_file}")
        return output_file


class BatchAutoExtractor:
    """Auto-extract from multiple Excel files"""

    PLANT_FILE_PATTERNS = {
        'BSP': ['BSP', 'bsp'],
        'DSP': ['DSP', 'dsp'],
        'RSP': ['RSP', 'rsp'],
        'BSL': ['BSL', 'bsl'],
        'ISP': ['ISP', 'isp'],
    }

    def __init__(self, excel_folder: str):
        self.excel_folder = Path(excel_folder)

    def find_excel_files(self) -> List[Tuple[str, Path]]:
        """
        Find all Excel files and identify plant

        Returns:
            List of (plant_code, file_path) tuples
        """
        files = []

        for excel_file in self.excel_folder.glob('*.xlsx'):
            plant = self._identify_plant(excel_file.name)

            if plant:
                files.append((plant, excel_file))
                print(f"  ✓ {plant}: {excel_file.name}")

        return files

    def _identify_plant(self, filename: str) -> Optional[str]:
        """Identify plant from filename"""
        filename_upper = filename.upper()

        for plant, patterns in self.PLANT_FILE_PATTERNS.items():
            for pattern in patterns:
                if pattern in filename_upper:
                    return plant

        return None

    def auto_extract_all(self) -> Dict[str, Dict]:
        """
        Auto-detect and extract from all Excel files in folder

        Returns:
            {plant: mapping_config, ...}
        """
        print(f"\n[SCANNING FOLDER FOR EXCEL FILES]")
        print(f"  Folder: {self.excel_folder}\n")

        excel_files = self.find_excel_files()

        if not excel_files:
            print(f"  ⊘ No Excel files found")
            return {}

        print(f"\n[AUTO-DETECTING PARAMETERS]\n")

        all_mappings = {}

        for plant, excel_file in excel_files:
            print(f"\n{plant}: {excel_file.name}")
            print("-" * 60)

            detector = SmartCellDetector(str(excel_file))
            detected = detector.detect_mappings()
            detector.close()

            if detected:
                mapping = AutoMappingGenerator.generate_mapping(
                    detected=detected,
                    excel_file=str(excel_file),
                    plant=plant,
                    report_month="2026-05"  # Default, user can change
                )
                all_mappings[plant] = mapping
                print(f"\n  ✓ Auto-detected {len(detected)} parameters for {plant}")
            else:
                print(f"\n  ⊘ No parameters detected for {plant}")

        return all_mappings

    def save_all_mappings(self, all_mappings: Dict[str, Dict], output_folder: str):
        """Save all mapping files"""
        output_path = Path(output_folder)
        output_path.mkdir(exist_ok=True)

        print(f"\n[SAVING MAPPINGS]")
        print(f"  Folder: {output_folder}\n")

        for plant, mapping in all_mappings.items():
            output_file = output_path / f"{plant.lower()}_auto_mapping.json"
            AutoMappingGenerator.save_mapping(mapping, str(output_file))


def main():
    if len(sys.argv) < 2:
        print("Usage: python auto_cell_detector.py <excel_file> [options]")
        print("       python auto_cell_detector.py --batch <folder> [options]")
        print("\nOptions:")
        print("  --plant <CODE>       Plant code (BSP, DSP, etc.). Auto-detected if not specified")
        print("  --month <YYYY-MM>    Report month (default: 2026-05)")
        print("  --sheet <NAME>       Sheet name (default: Sheet1)")
        print("  --output <FILE>      Output mapping file")
        print("\nExamples:")
        print("  python auto_cell_detector.py Report_format/Monthly/BSP-3-page-TechMay'26.xlsx")
        print("  python auto_cell_detector.py --batch Report_format/Monthly/")
        sys.exit(1)

    if sys.argv[1] == '--batch':
        # Batch mode
        folder = sys.argv[2] if len(sys.argv) > 2 else 'Report_format/Monthly'

        print("\n" + "="*80)
        print("AUTO CELL DETECTOR - BATCH MODE")
        print("="*80)

        batch = BatchAutoExtractor(folder)
        all_mappings = batch.auto_extract_all()

        if all_mappings:
            batch.save_all_mappings(all_mappings, 'backend')
            print(f"\n{'='*80}")
            print("✓ AUTO-DETECTION COMPLETE")
            print(f"{'='*80}")
            print(f"\nGenerated {len(all_mappings)} mapping files:")
            for plant in sorted(all_mappings.keys()):
                print(f"  • {plant.lower()}_auto_mapping.json")
        else:
            print("\n✗ No mappings could be generated")

    else:
        # Single file mode
        excel_file = sys.argv[1]
        plant = None
        month = "2026-05"
        sheet_name = "Sheet1"
        output_file = None

        # Parse options
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == '--plant' and i + 1 < len(sys.argv):
                plant = sys.argv[i + 1].upper()
                i += 2
            elif sys.argv[i] == '--month' and i + 1 < len(sys.argv):
                month = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == '--sheet' and i + 1 < len(sys.argv):
                sheet_name = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == '--output' and i + 1 < len(sys.argv):
                output_file = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        # Auto-detect plant if not specified
        if not plant:
            excel_path = Path(excel_file)
            batch = BatchAutoExtractor(excel_path.parent)
            plant = batch._identify_plant(excel_path.name)

            if not plant:
                print(f"✗ Could not identify plant from filename: {excel_path.name}")
                print("Use --plant option to specify: python auto_cell_detector.py <file> --plant BSP")
                sys.exit(1)

        print("\n" + "="*80)
        print("AUTO CELL DETECTOR - SINGLE FILE")
        print("="*80)
        print(f"\nFile: {excel_file}")
        print(f"Plant: {plant}")
        print(f"Month: {month}")
        print(f"Sheet: {sheet_name}")

        detector = SmartCellDetector(excel_file)
        detected = detector.detect_mappings(sheet_name=sheet_name)
        detector.close()

        if not detected:
            print("\n✗ No parameters detected")
            sys.exit(1)

        # Generate mapping
        mapping = AutoMappingGenerator.generate_mapping(
            detected=detected,
            excel_file=excel_file,
            plant=plant,
            report_month=month,
            sheet_name=sheet_name
        )

        # Save mapping
        if not output_file:
            output_file = f"{plant.lower()}_auto_mapping.json"

        AutoMappingGenerator.save_mapping(mapping, output_file)

        print(f"\n{'='*80}")
        print("✓ AUTO-DETECTION COMPLETE")
        print("="*80)
        print(f"\nDetected: {len(detected)} parameters")
        print(f"Mapping saved: {output_file}")
        print(f"\nNext step:")
        print(f"  python extract_and_insert.py {output_file}")


if __name__ == '__main__':
    main()
