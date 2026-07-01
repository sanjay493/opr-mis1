"""
BSL Blast Furnace Month-End Report (MER) Extractor

Extracts furnace-wise techno parameters from BSL_BlastFurnace_DDMMYYYY.pdf
These are month-only values (no till-month data available).

Parameters extracted include:
  - Production, Productivity, Coke Rate, CDI, Fuel Rate
  - Hot Blast Temp, Hot Metal Temp, Si/S in HM, O2 Enrichment, Slag Rate
  - Iron Ore, Sinter, Pellet, Scrap Consumption
  - Calculated: Sinter % in Burden, Pellet % in Burden

Output format: Same as RSP/BSP/ISP (saved to techno_data table as JSON)
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

sys.path.insert(0, str(Path(__file__).parent.parent / "excel_extractors"))


def _extract_date_from_filename(filename: str) -> Optional[str]:
    """
    Extract report_month (YYYY-MM) from filename like BSL_BlastFurnace_30042026.pdf
    Date format: DDMMYYYY → month is chars 2-4
    30042026 → April (04) → 2026-04
    """
    m = re.search(r'(\d{8})', filename)
    if not m:
        return None

    date_str = m.group(1)  # e.g., "30042026"
    try:
        day = int(date_str[0:2])      # 30
        month = int(date_str[2:4])    # 04
        year = int(date_str[4:8])     # 2026

        if not (1 <= month <= 12):
            return None

        return f"{year}-{month:02d}"
    except (ValueError, IndexError):
        return None


def _extract_monthly_value(cell_value) -> Optional[float]:
    """
    Extract monthly value from cell format: "monthly / till_month"

    Examples:
      "3678/100056" → 3678.0
      "440 / 439" → 440.0
      "100/89.2" → 100.0
      "3.02/2.95" → 3.02
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


class BslMerExtractor:
    """Extract BSL BF Month-End Report PDF data."""

    # Furnace mappings: parameter names map to which rows to extract from
    _PRODUCTION_PARAMS = {
        "production":     0,   # Daily Production Tonnes
        "daily_rate":     2,   # Daily Rate
        "monthly_rate":   4,   # Monthly Rate
        "bf_productivity": 15, # W.V./24h (Productivity)
    }

    _QUALITY_PARAMS = {
        "silicon_in_hm": 0,   # Si<=0.90 (%)
        "sulphur_in_hm": 1,   # S<=0.045 (%)
        "slag_rate":     4,   # SLAG RATE
        "avg_hot_metal_temperature": 3,  # HOT MET T
        "coke_rate":     5,   # COKE RATE
        "nut_coke_rate": 6,   # N/C RT
        "cdi":           7,   # CDI RATE
        "fuel_rate":     8,   # FUEL RATE
        "o2_enrichment": 9,   # O2 En(%)
        "hot_blast_temp": 10, # HOT BLAST
    }

    _CONSUMPTION_PARAMS = {
        "coke_consumption":        0,   # Coke(t)
        "iron_ore_consumption":    1,   # Iron Ore(t)
        "sinter_consumption":      2,   # Sinter (t)
        "scrap_consumption":       3,   # SCRAP(t)
        "nut_coke_consumption":    4,   # NutCoke
        "cdi_consumption":         5,   # CDI
        "pellet_consumption":      6,   # PELLET
    }

    def __init__(self, pdf_path: str, report_month: str = ""):
        self.pdf_path = Path(pdf_path)
        self.report_month = report_month

    def extract(self) -> List[Dict]:
        """
        Extract month-end report data.

        Returns:
            List of records: [{"plant": "BSL", "report_month": "YYYY-MM",
                               "unit": "BF-1", "techno_json": {"month": {...}, "till_month": {}}}]
        """
        if pdfplumber is None:
            print("ERROR: pdfplumber not installed")
            return []

        # Detect month from filename if not provided
        if not self.report_month:
            self.report_month = _extract_date_from_filename(self.pdf_path.name)

        if not self.report_month:
            print(f"ERROR: Could not detect report month from {self.pdf_path.name}")
            return []

        print(f"[BSL MER] Extracting from {self.pdf_path.name}, month={self.report_month}")

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                if len(pdf.pages) == 0:
                    print("[BSL MER] ERROR: PDF has no pages")
                    return []

                # Extract text from page 1
                page = pdf.pages[0]
                text = page.extract_text()

                if not text:
                    print("[BSL MER] ERROR: Could not extract text from PDF")
                    return []

                # Parse text and extract tables
                units_data = self._parse_text(text)

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
                    if params  # Only include units with data
                ]

                print(f"[BSL MER] Extracted {len(records)} units with data")
                for r in records:
                    print(f"  {r['unit']}: {len(r['techno_json']['month'])} parameters")

                return records

        except Exception as e:
            print(f"[BSL MER] ERROR: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_text(self, text: str) -> Dict[str, Dict]:
        """
        Parse PDF text and extract parameter values for each furnace.

        Returns: {"BF-1": {"coke_rate": 440, ...}, ...}
        """
        units_data = {unit: {} for unit in ["BF-1", "BF-2", "BF-4", "BF-5", "BF_Shop"]}

        # Split text into sections
        sections = self._split_into_sections(text)

        # Extract from each section
        if "production" in sections:
            self._extract_production_section(sections["production"], units_data)

        if "quality" in sections:
            self._extract_quality_section(sections["quality"], units_data)

        if "consumption" in sections:
            self._extract_consumption_section(sections["consumption"], units_data)

        return units_data

    def _split_into_sections(self, text: str) -> Dict[str, str]:
        """Split PDF text into major sections."""
        sections = {}

        # Find PRODUCTION PERFORMANCE section
        prod_match = re.search(r'PRODUCTION PERFORMANCE.*?(?=SMS I|QUALITY|$)', text, re.DOTALL | re.IGNORECASE)
        if prod_match:
            sections["production"] = prod_match.group(0)

        # Find QUALITY PARAMETERS section
        qual_match = re.search(r'QUALITY PARAMETERS.*?(?=RAW|CONSUMPTION|$)', text, re.DOTALL | re.IGNORECASE)
        if qual_match:
            sections["quality"] = qual_match.group(0)

        # Find CONSUMPTION OF RAW MATERIAL section
        cons_match = re.search(r'Consumption.*?Raw.*?Material.*?(?=SLAG|CAST|$)', text, re.DOTALL | re.IGNORECASE)
        if cons_match:
            sections["consumption"] = cons_match.group(0)

        return sections

    def _extract_production_section(self, section_text: str, units_data: Dict):
        """Extract production performance data."""
        lines = section_text.split("\n")

        # Find rows for each furnace
        furnace_rows = {
            "BF-1": None, "BF-2": None, "BF-4": None, "BF-5": None, "BF_Shop": None
        }

        for i, line in enumerate(lines):
            line_clean = line.strip()
            if "|" in line and ("BF-1" in line or "BF-2" in line or "BF-4" in line or "BF-5" in line or ("Shop" in line and "BF" in line)):
                for unit in furnace_rows:
                    if unit.replace("-", " ") in line or (unit == "BF_Shop" and "Shop" in line and "BF" in line):
                        furnace_rows[unit] = line

        # Parse furnace rows
        for unit, row in furnace_rows.items():
            if row is None:
                continue

            # Split by | to get cells
            cells = [c.strip() for c in row.split("|")]

            # Extract values from cells based on known column positions
            try:
                if len(cells) > 2:
                    # Daily production (first numeric column)
                    units_data[unit]["production"] = _extract_monthly_value(cells[1])

                if len(cells) > 4:
                    # Daily rate
                    units_data[unit]["daily_rate"] = _extract_monthly_value(cells[3])

                if len(cells) > 5:
                    # Monthly rate
                    units_data[unit]["monthly_rate"] = _extract_monthly_value(cells[4])

                if len(cells) > 16:
                    # Productivity (W.V./24h)
                    units_data[unit]["bf_productivity"] = _extract_monthly_value(cells[16])

            except (IndexError, ValueError) as e:
                print(f"[BSL MER] Warning: Could not parse production row for {unit}: {e}")

    def _extract_quality_section(self, section_text: str, units_data: Dict):
        """Extract quality parameters data."""
        lines = section_text.split("\n")

        furnace_rows = {
            "BF-1": None, "BF-2": None, "BF-4": None, "BF-5": None, "BF_Shop": None
        }

        for i, line in enumerate(lines):
            line_clean = line.strip()
            if "|" in line and len(line) > 50:  # Quality rows are longer
                for unit in furnace_rows:
                    if unit.replace("-", " ") in line or (unit == "BF_Shop" and "Shop" in line):
                        if furnace_rows[unit] is None:  # Get first occurrence
                            furnace_rows[unit] = line

        for unit, row in furnace_rows.items():
            if row is None:
                continue

            cells = [c.strip() for c in row.split("|")]

            try:
                if len(cells) > 1:
                    units_data[unit]["silicon_in_hm"] = _extract_monthly_value(cells[1])
                if len(cells) > 2:
                    units_data[unit]["sulphur_in_hm"] = _extract_monthly_value(cells[2])
                if len(cells) > 4:
                    units_data[unit]["slag_rate"] = _extract_monthly_value(cells[4])
                if len(cells) > 5:
                    units_data[unit]["coke_rate"] = _extract_monthly_value(cells[5])
                if len(cells) > 6:
                    units_data[unit]["nut_coke_rate"] = _extract_monthly_value(cells[6])
                if len(cells) > 7:
                    units_data[unit]["cdi"] = _extract_monthly_value(cells[7])
                if len(cells) > 8:
                    units_data[unit]["fuel_rate"] = _extract_monthly_value(cells[8])
                if len(cells) > 9:
                    units_data[unit]["o2_enrichment"] = _extract_monthly_value(cells[9])
                if len(cells) > 10:
                    units_data[unit]["hot_blast_temp"] = _extract_monthly_value(cells[10])
                if len(cells) > 11:
                    units_data[unit]["avg_hot_metal_temperature"] = _extract_monthly_value(cells[11])

            except (IndexError, ValueError) as e:
                print(f"[BSL MER] Warning: Could not parse quality row for {unit}: {e}")

    def _extract_consumption_section(self, section_text: str, units_data: Dict):
        """Extract raw material consumption data."""
        lines = section_text.split("\n")

        furnace_rows = {
            "BF-1": None, "BF-2": None, "BF-4": None, "BF-5": None, "BF_Shop": None
        }

        for i, line in enumerate(lines):
            if "|" in line:
                for unit in furnace_rows:
                    if unit.replace("-", " ") in line or (unit == "BF_Shop" and "Shop" in line):
                        if furnace_rows[unit] is None:
                            furnace_rows[unit] = line

        for unit, row in furnace_rows.items():
            if row is None:
                continue

            cells = [c.strip() for c in row.split("|")]

            try:
                if len(cells) > 1:
                    units_data[unit]["coke_consumption"] = _extract_monthly_value(cells[1])
                if len(cells) > 2:
                    units_data[unit]["iron_ore_consumption"] = _extract_monthly_value(cells[2])
                if len(cells) > 3:
                    units_data[unit]["sinter_consumption"] = _extract_monthly_value(cells[3])
                if len(cells) > 4:
                    units_data[unit]["scrap_consumption"] = _extract_monthly_value(cells[4])
                if len(cells) > 5:
                    units_data[unit]["nut_coke_consumption"] = _extract_monthly_value(cells[5])
                if len(cells) > 6:
                    units_data[unit]["cdi_consumption"] = _extract_monthly_value(cells[6])
                if len(cells) > 7:
                    units_data[unit]["pellet_consumption"] = _extract_monthly_value(cells[7])

            except (IndexError, ValueError) as e:
                print(f"[BSL MER] Warning: Could not parse consumption row for {unit}: {e}")

    def _calculate_burden_percentages(self, units_data: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        Calculate Sinter % in Burden and Pellet % in Burden from consumption data.

        Formula:
          Total Burden = Iron Ore + Sinter + Pellet + Scrap (in tonnes)
          Sinter % = (Sinter / Total Burden) × 100
          Pellet % = (Pellet / Total Burden) × 100
        """
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

                print(f"[BSL MER] {unit}: Total Burden={total_burden:.0f}t, Sinter {sinter_pct}%, Pellet {pellet_pct}%")

        return units_data


def extract_bsl_mer(pdf_path: str, report_month: str = "") -> List[Dict]:
    """
    Public API to extract BSL Month-End Report.

    Args:
        pdf_path: Path to BSL_BlastFurnace_DDMMYYYY.pdf
        report_month: Optional report month (YYYY-MM). Auto-detected if not provided.

    Returns:
        List of techno_data records ready for database storage.
    """
    extractor = BslMerExtractor(pdf_path, report_month)
    return extractor.extract()


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <pdf_path> [report_month]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    report_month = sys.argv[2] if len(sys.argv) > 2 else ""

    records = extract_bsl_mer(pdf_path, report_month)
    print(f"\nExtracted {len(records)} records:")
    for r in records:
        print(f"  {r['unit']}: {r['techno_json']['month']}")
