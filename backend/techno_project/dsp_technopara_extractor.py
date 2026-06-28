"""
DSP Techno Extractor — Extracts from PDF reports
Converts DSP PDF techno data to JSON format for storage in techno_data table
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Import PDF extractor
sys.path.insert(0, str(Path(__file__).parent.parent / "excel_extractors"))
from pdf_extractor_dsp import extract_preview


class DspTechnoExtractor:
    """
    Extract techno parameters from DSP PDF reports.
    Groups data by unit (section) and formats as JSON with month/till_month structure.
    """

    def __init__(self, file_path: str, report_month: str = ""):
        """
        Initialize DSP techno extractor.

        Args:
            file_path: Path to DSP PDF file
            report_month: Report month in YYYY-MM format (auto-detected if not provided)
        """
        self.file_path = file_path
        self.report_month = report_month
        self.pdf_data = None

    def _detect_report_month(self) -> str:
        """Extract month from PDF data if not provided."""
        if not self.pdf_data:
            return ""

        # First priority: use pdf_report_month detected by PDF parser
        if self.pdf_data.get("pdf_report_month"):
            return self.pdf_data["pdf_report_month"]

        # Fallback: extract from first techno row
        techno_rows = self.pdf_data.get("techno_param_rows", [])
        if not techno_rows:
            return ""

        first_row = techno_rows[0]
        month_str = first_row.get("month", "")

        try:
            # Format: "Mar'26" → extract month and year
            if "'" in month_str:
                month_part, year_part = month_str.split("'")
            else:
                return ""

            # Convert month name to number
            months = {
                "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
                "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
                "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
            }
            month_num = months.get(month_part, "")
            if not month_num:
                return ""

            # Convert year: "26" → "2026"
            full_year = f"20{year_part}" if len(year_part) == 2 else year_part

            return f"{full_year}-{month_num}"
        except Exception:
            return ""

    def _map_section_to_unit(self, section: str) -> str:
        """
        Map PDF section names to proper unit names.
        Handles variations in section naming from PDF extractor.
        """
        if not section:
            return "General"

        section_lower = section.lower().strip()

        # Exact mappings
        mappings = {
            "sms": "SMS",
            "coke": "Coke",
            "coke ovens": "Coke",
            "merchant mill": "Merchant Mill",
            "mm": "Merchant Mill",
            "msm": "MSM",
            "wheel plant": "Wheel Plant",
            "wheel & axle": "Wheel Plant",
            "wa": "Wheel Plant",
            "axle plant": "Axle Plant",
            "blast furnace": "Blast Furnace",
            "bf": "Blast Furnace",
            "bf shop": "Blast Furnace Shop",
            "bf coke": "Coke",
            "major": "Major Techno",
            "major techno": "Major Techno",
            "general": "General",
        }

        # Check exact match
        if section_lower in mappings:
            return mappings[section_lower]

        # Check partial match (priority order)
        for key, value in mappings.items():
            if key in section_lower:
                return value

        # Default
        return section

    def extract(self) -> List[Dict]:
        """
        Extract techno data from DSP PDF and return as list of records.

        Returns:
            List of dicts: {
                "report_month": "2026-03",
                "plant": "DSP",
                "unit": "SMS" or "Major" or "Coke" etc.,
                "techno_json": {"month": {...}, "till_month": {...}}
            }
        """
        try:
            # Extract data from PDF using existing extractor
            # If no report_month provided, pass current month as fallback for PDF parser
            if not self.report_month:
                today = datetime.now()
                fallback_month = f"{today.year:04d}-{today.month:02d}"
            else:
                fallback_month = self.report_month

            print(f"[DSP] Calling PDF extractor with fallback_month={fallback_month}")
            self.pdf_data = extract_preview(
                self.file_path,
                fallback_month,
                block="techno"
            )

            if not self.pdf_data:
                print("[DSP] ERROR: PDF extractor returned no data")
                return []

            if "techno_param_rows" not in self.pdf_data:
                print("[DSP] ERROR: No techno_param_rows in PDF data")
                print(f"[DSP] Available keys: {list(self.pdf_data.keys())}")
                return []

            techno_rows = self.pdf_data.get("techno_param_rows", [])
            if not techno_rows:
                print("[DSP] WARNING: techno_param_rows is empty")
                return []

            print(f"[DSP] ✓ Extracted {len(techno_rows)} techno parameter rows from PDF")

            # Detect report month if not provided
            if not self.report_month:
                self.report_month = self._detect_report_month()
                if not self.report_month:
                    print("[DSP] ERROR: Could not detect report month from PDF")
                    return []

            print(f"[DSP] Report month: {self.report_month}")

            # Group rows by unit (section)
            units_data = {}  # unit_name → {"month": {}, "till_month": {}}
            param_count = 0

            print(f"[DSP] Processing {len(techno_rows)} rows:")
            for row in techno_rows:
                # Map section to proper unit name
                section_raw = row.get("section", "General")
                unit_name = self._map_section_to_unit(section_raw)

                parameter_name = row.get("parameter", "")
                actual_val = row.get("actual")
                cum_val = row.get("cum_actual")

                if not parameter_name:
                    continue

                # Create clean parameter key from display name
                param_key = parameter_name.lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").replace("/", "_").replace(".", "")

                # Initialize unit if needed
                if unit_name not in units_data:
                    units_data[unit_name] = {"month": {}, "till_month": {}}

                # Clean values
                month_val = self._clean_value(actual_val)
                till_val = self._clean_value(cum_val)

                # Store in both month and till_month (even if one is None)
                units_data[unit_name]["month"][param_key] = month_val
                units_data[unit_name]["till_month"][param_key] = till_val

                # Debug logging
                param_count += 1
                section_info = f"[{section_raw}→{unit_name}]" if section_raw != unit_name else f"[{unit_name}]"
                if month_val is not None or till_val is not None:
                    print(f"  ✓ {section_info:25s} {parameter_name:35s} | month={month_val} | cum={till_val}")

            print(f"[DSP] Processed {param_count} parameters across {len(units_data)} units")

            # Convert to records
            records = []
            for unit_name, techno_json in units_data.items():
                month_params = techno_json.get("month", {})
                till_params = techno_json.get("till_month", {})

                # Count non-None values
                month_count = sum(1 for v in month_params.values() if v is not None)
                till_count = sum(1 for v in till_params.values() if v is not None)

                print(f"  📊 {unit_name:20s} → {month_count} month, {till_count} cumulative")

                records.append({
                    "report_month": self.report_month,
                    "plant": "DSP",
                    "unit": unit_name,
                    "techno_json": techno_json,
                })

            print(f"\n✓ DSP Extraction complete: {len(records)} units with {param_count} total parameters")
            return records

        except Exception as e:
            print(f"[DSP] ERROR during extraction: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _clean_value(self, val) -> Optional[float]:
        """Clean and convert value to float."""
        if val is None:
            return None
        try:
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                val_str = val.strip().upper()
                if val_str in ("NAN", "###", "-", "#DIV/0!", ""):
                    return None
                return float(val_str)
            return None
        except (ValueError, TypeError):
            return None
