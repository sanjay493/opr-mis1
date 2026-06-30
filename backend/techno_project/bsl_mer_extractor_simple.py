"""
BSL Blast Furnace Month-End Report (MER) Extractor - Text Parser Version

Extracts furnace-wise techno parameters from raw PDF text.
No external PDF library required - works with extracted text.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional


def _extract_date_from_filename(filename: str) -> Optional[str]:
    """
    Extract report_month (YYYY-MM) from filename like BSL_BlastFurnace_30042026.pdf
    Date format: DDMMYYYY → month is chars 2-4
    30042026 → April (04) → 2026-04
    """
    m = re.search(r'(\d{8})', filename)
    if not m:
        return None

    date_str = m.group(1)
    try:
        day = int(date_str[0:2])
        month = int(date_str[2:4])
        year = int(date_str[4:8])

        if not (1 <= month <= 12):
            return None

        return f"{year}-{month:02d}"
    except (ValueError, IndexError):
        return None


def _extract_monthly_value(cell_value) -> Optional[float]:
    """
    Extract monthly value from "monthly / till_month" format.

    Examples:
      "3678/100056" → 3678.0
      "440 / 439" → 440.0
      "100/89.2" → 100.0
    """
    if cell_value is None:
        return None

    try:
        s = str(cell_value).strip()
        if not s or s in ("NA", "N/A", "-", "--", "#DIV/0!", "#VALUE!", "", "***"):
            return None

        # Extract value before "/" if present
        if "/" in s:
            parts = s.split("/")
            s = parts[0].strip()

        # Remove commas and convert
        s = s.replace(",", "")
        return float(s) if s else None

    except (ValueError, TypeError):
        return None


class BslMerTextParser:
    """Parse BSL Month-End Report from raw PDF text."""

    def __init__(self, pdf_text: str, report_month: str = "", filename: str = ""):
        self.pdf_text = pdf_text
        self.report_month = report_month or _extract_date_from_filename(filename)
        self.lines = pdf_text.split("\n")

    def extract(self) -> List[Dict]:
        """
        Parse text and extract month-end report data.

        Returns:
            List of records: [{"plant": "BSL", "report_month": "YYYY-MM", ...}]
        """
        if not self.report_month:
            print("[BSL MER] ERROR: Could not detect report month")
            return []

        print(f"[BSL MER] Parsing BSL month-end report, month={self.report_month}")

        try:
            # Extract data for each unit
            units_data = self._parse_all_sections()

            # Calculate burden percentages
            units_data = self._calculate_burden_percentages(units_data)

            # Build records
            records = [
                {
                    "plant": "BSL",
                    "report_month": self.report_month,
                    "unit": unit,
                    "techno_json": {"month": params, "till_month": {}}
                }
                for unit, params in sorted(units_data.items())
                if params
            ]

            print(f"[BSL MER] Extracted {len(records)} units")
            return records

        except Exception as e:
            print(f"[BSL MER] ERROR: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_all_sections(self) -> Dict[str, Dict]:
        """Parse all data sections and extract parameters."""
        units_data = {unit: {} for unit in ["BF-1", "BF-2", "BF-4", "BF-5", "BF_Shop"]}

        # Find key section markers
        prod_idx = self._find_section("PRODUCTION PERFORMANCE")
        qual_idx = self._find_section("QUALITY PARAMETERS")
        cons_idx = self._find_section("Consumption")

        if prod_idx >= 0:
            self._parse_production(units_data, prod_idx)

        if qual_idx >= 0:
            self._parse_quality(units_data, qual_idx)

        if cons_idx >= 0:
            self._parse_consumption(units_data, cons_idx)

        return units_data

    def _find_section(self, marker: str) -> int:
        """Find line index containing section marker."""
        for i, line in enumerate(self.lines):
            if marker.upper() in line.upper():
                return i
        return -1

    def _parse_production(self, units_data: Dict, start_idx: int):
        """Parse PRODUCTION PERFORMANCE section."""
        print(f"[BSL MER] Parsing production section starting at line {start_idx}")

        furnace_map = {
            "| 1.": "BF-1",
            "| 2.": "BF-2",
            "| 4.": "BF-4",
            "| 5.": "BF-5",
            "|Shop": "BF_Shop"
        }

        for i in range(start_idx, min(start_idx + 20, len(self.lines))):
            line = self.lines[i]

            for marker, unit in furnace_map.items():
                if marker in line:
                    # Parse pipe-delimited values
                    cells = [c.strip() for c in line.split("|")]

                    try:
                        if len(cells) > 2:
                            units_data[unit]["production"] = _extract_monthly_value(cells[2])
                        if len(cells) > 4:
                            units_data[unit]["daily_rate"] = _extract_monthly_value(cells[4])
                        if len(cells) > 5:
                            units_data[unit]["monthly_rate"] = _extract_monthly_value(cells[5])
                        if len(cells) > 16:
                            units_data[unit]["bf_productivity"] = _extract_monthly_value(cells[16])

                        print(f"  {unit}: production={units_data[unit].get('production')}, productivity={units_data[unit].get('bf_productivity')}")

                    except Exception as e:
                        print(f"  Warning parsing {unit}: {e}")

    def _parse_quality(self, units_data: Dict, start_idx: int):
        """Parse QUALITY PARAMETERS section."""
        print(f"[BSL MER] Parsing quality section starting at line {start_idx}")

        furnace_map = {
            "| 1.": "BF-1",
            "| 2.": "BF-2",
            "| 4.": "BF-4",
            "| 5.": "BF-5",
            "|SHOP": "BF_Shop"
        }

        for i in range(start_idx, min(start_idx + 20, len(self.lines))):
            line = self.lines[i]

            for marker, unit in furnace_map.items():
                if marker in line:
                    cells = [c.strip() for c in line.split("|")]

                    try:
                        if len(cells) > 2:
                            units_data[unit]["si_in_hm"] = _extract_monthly_value(cells[2])
                        if len(cells) > 3:
                            units_data[unit]["s_in_hm"] = _extract_monthly_value(cells[3])
                        if len(cells) > 6:
                            units_data[unit]["slag_rate"] = _extract_monthly_value(cells[6])
                        if len(cells) > 7:
                            units_data[unit]["coke_rate"] = _extract_monthly_value(cells[7])
                        if len(cells) > 8:
                            units_data[unit]["nut_coke_rate"] = _extract_monthly_value(cells[8])
                        if len(cells) > 9:
                            units_data[unit]["cdi"] = _extract_monthly_value(cells[9])
                        if len(cells) > 10:
                            units_data[unit]["fuel_rate"] = _extract_monthly_value(cells[10])
                        if len(cells) > 11:
                            units_data[unit]["o2_enrichment"] = _extract_monthly_value(cells[11])
                        if len(cells) > 13:
                            units_data[unit]["hot_blast_temp"] = _extract_monthly_value(cells[13])

                        print(f"  {unit}: coke_rate={units_data[unit].get('coke_rate')}, o2={units_data[unit].get('o2_enrichment')}")

                    except Exception as e:
                        print(f"  Warning parsing {unit}: {e}")

    def _parse_consumption(self, units_data: Dict, start_idx: int):
        """Parse CONSUMPTION OF RAW MATERIAL section."""
        print(f"[BSL MER] Parsing consumption section starting at line {start_idx}")

        furnace_map = {
            "| 1.": "BF-1",
            "| 2.": "BF-2",
            "| 4.": "BF-4",
            "| 5.": "BF-5",
            "|SH": "BF_Shop"
        }

        for i in range(start_idx, min(start_idx + 20, len(self.lines))):
            line = self.lines[i]

            for marker, unit in furnace_map.items():
                if marker in line:
                    cells = [c.strip() for c in line.split("|")]

                    try:
                        if len(cells) > 2:
                            units_data[unit]["coke_consumption"] = _extract_monthly_value(cells[2])
                        if len(cells) > 3:
                            units_data[unit]["iron_ore_consumption"] = _extract_monthly_value(cells[3])
                        if len(cells) > 4:
                            units_data[unit]["sinter_consumption"] = _extract_monthly_value(cells[4])
                        if len(cells) > 5:
                            units_data[unit]["scrap_consumption"] = _extract_monthly_value(cells[5])
                        if len(cells) > 9:
                            units_data[unit]["pellet_consumption"] = _extract_monthly_value(cells[9])

                        print(f"  {unit}: sinter={units_data[unit].get('sinter_consumption')}, pellet={units_data[unit].get('pellet_consumption')}")

                    except Exception as e:
                        print(f"  Warning parsing {unit}: {e}")

    def _calculate_burden_percentages(self, units_data: Dict[str, Dict]) -> Dict[str, Dict]:
        """Calculate Sinter % and Pellet % in Burden."""
        print(f"[BSL MER] Calculating burden percentages...")

        for unit, params in units_data.items():
            iron_ore = params.get("iron_ore_consumption") or 0
            sinter = params.get("sinter_consumption") or 0
            pellet = params.get("pellet_consumption") or 0
            scrap = params.get("scrap_consumption") or 0

            total_burden = iron_ore + sinter + pellet + scrap

            if total_burden > 0:
                sinter_pct = round((sinter / total_burden) * 100, 2)
                pellet_pct = round((pellet / total_burden) * 100, 2)

                params["sinter_in_burden"] = sinter_pct
                params["pellet_in_burden"] = pellet_pct

                print(f"  {unit}: Total Burden={total_burden:.0f}t, Sinter={sinter_pct}%, Pellet={pellet_pct}%")

        return units_data


def extract_bsl_mer_from_text(pdf_text: str, report_month: str = "", filename: str = "") -> List[Dict]:
    """
    Extract BSL Month-End Report from PDF text.

    Args:
        pdf_text: Raw PDF text content
        report_month: Optional report month (YYYY-MM)
        filename: Optional filename to auto-detect month

    Returns:
        List of techno_data records
    """
    parser = BslMerTextParser(pdf_text, report_month, filename)
    return parser.extract()
