"""
BSL Month-End Report PDF Parser - Robust text-based extraction

Parses raw PDF text and extracts techno parameters for each furnace.
"""

import re
from typing import Dict, List, Optional, Tuple


def _extract_both_values(value_str) -> Tuple[Optional[float], Optional[float]]:
    """Extract both monthly and cumulative values from 'monthly/cumulative' format.

    Returns: (monthly_value, cumulative_value)
    """
    if not value_str:
        return None, None

    s = str(value_str).strip()

    if not s or s in ("NA", "N/A", "-", "--", "", "***", "#DIV/0!"):
        return None, None

    # Split by "/" to get monthly and cumulative
    parts = s.split("/")

    monthly = None
    cumulative = None

    try:
        if len(parts) >= 1:
            monthly_str = parts[0].strip()
            if monthly_str and monthly_str not in ("NA", "N/A", "-", "--", "", "***"):
                monthly = float(monthly_str)

        if len(parts) >= 2:
            cumul_str = parts[1].strip()
            if cumul_str and cumul_str not in ("NA", "N/A", "-", "--", "", "***"):
                cumulative = float(cumul_str)
    except (ValueError, IndexError):
        pass

    return monthly, cumulative


def _extract_monthly_value(value_str) -> Optional[float]:
    """Extract monthly value from 'monthly/till_month' or single value format."""
    if not value_str:
        return None

    s = str(value_str).strip()

    if not s or s in ("NA", "N/A", "-", "--", "", "***", "#DIV/0!"):
        return None

    try:
        # Extract before "/" if present
        if "/" in s:
            s = s.split("/")[0].strip()

        # Remove non-numeric characters except decimal point and minus
        s = re.sub(r'[^0-9.\-]', '', s)

        if s and s != "-":
            return float(s)
    except (ValueError, TypeError):
        pass

    return None


class BslMerParser:
    """Parse BSL Month-End Report from PDF text."""

    def __init__(self, pdf_text: str, report_month: str = "", filename: str = ""):
        self.text = pdf_text
        self.report_month = report_month or self._extract_month_from_filename(filename)

    @staticmethod
    def _extract_month_from_filename(filename: str) -> Optional[str]:
        """Extract YYYY-MM from filename like BSL_BlastFurnace_30042026.pdf"""
        m = re.search(r'(\d{8})', filename)
        if m:
            try:
                d = m.group(1)
                return f"{d[4:8]}-{d[2:4]}"
            except:
                pass
        return None

    def parse(self) -> Dict[str, Dict]:
        """
        Parse PDF text and extract parameters.

        Returns: {"BF-1": {"production": 3678, ...}, ...}
        """
        units = {unit: {} for unit in ["BF-1", "BF-2", "BF-4", "BF-5", "BF_Shop"]}

        # Extract production data
        self._extract_production_data(units)

        # Extract quality data
        self._extract_quality_data(units)

        # Extract consumption data
        self._extract_consumption_data(units)

        # Calculate burden percentages
        self._calculate_burden_percentages(units)

        return units

    def _extract_production_data(self, units: Dict):
        """Extract from PRODUCTION PERFORMANCE section - match by furnace ID."""
        prod_idx = self.text.find("PRODUCTION PERFORMANCE")
        if prod_idx < 0:
            return

        # Section boundaries
        coke_idx = self.text.find("COKE RATE", prod_idx)
        if coke_idx < 0:
            coke_idx = len(self.text)

        prod_section = self.text[prod_idx:coke_idx]
        lines = prod_section.split("\n")

        for line in lines:
            # Skip short or non-data lines
            if not "|" in line or len(line) < 50:
                continue

            # Skip header and separator lines
            if any(keyword in line for keyword in ["PRODUCTION", "FCS", "No", "Tonnes", "Rate", "Temp"]):
                continue

            # Skip lines with many asterisks (under repair - BF-3)
            if line.count("*") > 10:
                continue

            cells = [c.strip() for c in line.split("|")]

            if len(cells) < 15:
                continue

            # Check if this looks like a data row
            has_production = "/" in str(cells[2] if len(cells) > 2 else "")
            if not has_production:
                continue

            # Extract furnace ID from cells[1] - format is "1.", "2.", "4.", "5.", "SHOP"
            furnace_str = cells[1] if len(cells) > 1 else ""
            if not furnace_str:
                continue

            # Match furnace patterns: "1.", "1 ", "2.", "4.", "5.", "SHOP"
            fnum_match = re.match(r'^(\d+|SHOP)', furnace_str)
            if not fnum_match:
                continue

            fnum = fnum_match.group(1)

            # Map to furnace names - skip BF-3
            furnace_map = {"1": "BF-1", "2": "BF-2", "4": "BF-4", "5": "BF-5", "SHOP": "BF_Shop"}

            if fnum not in furnace_map:
                continue

            unit_id = furnace_map[fnum]

            # [2] = Production (3203/104510)
            if len(cells) > 2:
                m, c = _extract_both_values(cells[2])
                if m is not None:
                    units[unit_id]["production_month"] = m
                if c is not None:
                    units[unit_id]["production_cumul"] = c

            # [13] = Hot Blast Temp (1100/1093)
            if len(cells) > 13:
                m, c = _extract_both_values(cells[13])
                if m is not None:
                    units[unit_id]["hot_blast_temp_month"] = m
                if c is not None:
                    units[unit_id]["hot_blast_temp_cumul"] = c

            # [16] = BF Productivity (1.82/2.00)
            if len(cells) > 16:
                m, c = _extract_both_values(cells[16])
                if m is not None:
                    units[unit_id]["bf_productivity_month"] = m
                if c is not None:
                    units[unit_id]["bf_productivity_cumul"] = c

    def _extract_quality_data(self, units: Dict):
        """Extract from QUALITY PARAMETERS section - look for COKE RATE header."""
        # Find "COKE RATE" text which marks the quality table section
        coke_idx = self.text.find("COKE RATE")
        if coke_idx < 0:
            return

        # Extract section from COKE RATE onwards
        section_end = self.text.find("Consumption", coke_idx)
        if section_end < 0:
            section_end = coke_idx + 3000

        qual_section = self.text[coke_idx:section_end]
        lines = qual_section.split("\n")

        for line in lines:
            # Skip short lines and header lines
            if not "|" in line or len(line) < 40:
                continue

            # Skip header/separator lines (they contain text keywords)
            if any(keyword in line for keyword in ["COKE", "CDI", "FUEL", "FCS", "No", "kg/THM", "N/C"]):
                continue

            # Skip lines with many asterisks (under repair marker - BF-3)
            if line.count("*") > 10:
                continue

            cells = [c.strip() for c in line.split("|")]

            # Need at least columns up to fuel rate [11]
            if len(cells) < 12:
                continue

            # Check if this looks like a data row (has "/" delimiters in the right columns)
            has_coke = "/" in str(cells[8] if len(cells) > 8 else "")
            has_cdi = "/" in str(cells[10] if len(cells) > 10 else "")
            has_fuel = "/" in str(cells[11] if len(cells) > 11 else "")

            if not (has_coke and has_cdi and has_fuel):
                continue

            # Extract furnace ID from cells[1] - format is "1.", "2.", "4.", "5.", "SHOP"
            furnace_str = cells[1] if len(cells) > 1 else ""
            if not furnace_str:
                continue

            # Match furnace patterns
            fnum_match = re.match(r'^(\d+|SHOP)', furnace_str)
            if not fnum_match:
                continue

            fnum = fnum_match.group(1)
            furnace_map = {"1": "BF-1", "2": "BF-2", "4": "BF-4", "5": "BF-5", "SHOP": "BF_Shop"}

            if fnum not in furnace_map:
                continue

            unit_id = furnace_map[fnum]

            # [8] = Coke Rate (440/439)
            if len(cells) > 8:
                m, c = _extract_both_values(cells[8])
                if m is not None:
                    units[unit_id]["coke_rate_month"] = m
                if c is not None:
                    units[unit_id]["coke_rate_cumul"] = c

            # [9] = N/C Rate / Nut Coke Rate (19/16) - NEW!
            if len(cells) > 9:
                m, c = _extract_both_values(cells[9])
                if m is not None:
                    units[unit_id]["nut_coke_rate_month"] = m
                if c is not None:
                    units[unit_id]["nut_coke_rate_cumul"] = c

            # [10] = CDI Rate (108/94)
            if len(cells) > 10:
                m, c = _extract_both_values(cells[10])
                if m is not None:
                    units[unit_id]["cdi_month"] = m
                if c is not None:
                    units[unit_id]["cdi_cumul"] = c

            # [11] = Fuel Rate (568/548)
            if len(cells) > 11:
                m, c = _extract_both_values(cells[11])
                if m is not None:
                    units[unit_id]["fuel_rate_month"] = m
                if c is not None:
                    units[unit_id]["fuel_rate_cumul"] = c

    def _extract_consumption_data(self, units: Dict):
        """Extract from CONSUMPTION OF RAW MATERIAL section - match by furnace ID."""
        cons_idx = self.text.find("Consumption")
        if cons_idx < 0:
            cons_idx = self.text.find("CONSUMPTION")
        if cons_idx < 0:
            return

        cons_section = self.text[cons_idx:cons_idx + 5000]
        lines = cons_section.split("\n")

        for line in lines:
            if not "|" in line or len(line) < 50:
                continue

            # Skip header lines
            if any(keyword in line for keyword in ["O2", "SLAG", "CARBON", "DUST", "Ratio", "kg/", "CONSUMPTION"]):
                continue

            # Skip lines with many asterisks (BF-3 under repair)
            if line.count("*") > 10:
                continue

            cells = [c.strip() for c in line.split("|")]

            if len(cells) < 10:
                continue

            # Extract furnace ID from cells[1] - format is "1.", "2.", "4.", "5.", "SHOP"
            furnace_str = cells[1] if len(cells) > 1 else ""
            if not furnace_str:
                continue

            # Match furnace patterns
            fnum_match = re.match(r'^(\d+|SHOP)', furnace_str)
            if not fnum_match:
                continue

            fnum = fnum_match.group(1)
            furnace_map = {"1": "BF-1", "2": "BF-2", "4": "BF-4", "5": "BF-5", "SHOP": "BF_Shop"}

            if fnum not in furnace_map:
                continue

            unit_id = furnace_map[fnum]

            # Consumption table columns (approx):
            # [2]=Coke [3]=IronOre [4]=Sinter [5]=Scrap [6]=NutCoke [7]=CDI [8]=Pellet [9]=CokeEco [10]=O2 [11]=Slag [12]=SinterPct

            # Iron Ore (t) - usually column 3
            if len(cells) > 3:
                try:
                    val = float(cells[3])
                    units[unit_id]["iron_ore_cumul"] = val
                except:
                    pass

            # Sinter (t) - usually column 4
            if len(cells) > 4:
                try:
                    val = float(cells[4])
                    units[unit_id]["sinter_cumul"] = val
                except:
                    pass

            # Pellet (t) - usually column 8
            if len(cells) > 8:
                try:
                    val = float(cells[8])
                    units[unit_id]["pellet_cumul"] = val
                except:
                    pass

            # Sinter % in Burden - usually column 12 (may have "/" format)
            if len(cells) > 12:
                m, c = _extract_both_values(cells[12])
                if c is not None:
                    units[unit_id]["sinter_pct_burden"] = c
                elif m is not None:
                    units[unit_id]["sinter_pct_burden"] = m

            # O2 Enrichment (try multiple columns as layout varies)
            for col_idx in [10, 11, 9, 12]:
                if len(cells) > col_idx:
                    m, c = _extract_both_values(cells[col_idx])
                    if m is not None or c is not None:
                        if m is not None:
                            units[unit_id]["o2_enrichment_month"] = m
                        if c is not None:
                            units[unit_id]["o2_enrichment_cumul"] = c
                        break

            # Slag Rate (try multiple columns)
            for col_idx in [11, 12, 10, 13]:
                if len(cells) > col_idx:
                    m, c = _extract_both_values(cells[col_idx])
                    if m is not None or c is not None:
                        if m is not None:
                            units[unit_id]["slag_rate_month"] = m
                        if c is not None:
                            units[unit_id]["slag_rate_cumul"] = c
                        break

    def _calculate_burden_percentages(self, units: Dict):
        """Calculate Sinter % and Pellet % in Burden."""
        for unit, params in units.items():
            iron_ore = params.get("iron_ore_consumption") or 0
            sinter = params.get("sinter_consumption") or 0
            pellet = params.get("pellet_consumption") or 0
            scrap = params.get("scrap_consumption") or 0

            total = iron_ore + sinter + pellet + scrap

            if total > 0:
                params["sinter_in_burden"] = round((sinter / total) * 100, 2)
                params["pellet_in_burden"] = round((pellet / total) * 100, 2)


def extract_bsl_mer(pdf_text: str, report_month: str = "", filename: str = "") -> List[Dict]:
    """
    Extract BSL Month-End Report from PDF text.

    Args:
        pdf_text: Raw PDF text
        report_month: Optional YYYY-MM format
        filename: Optional filename to auto-detect month

    Returns:
        List of techno_data records ready for database
    """
    parser = BslMerParser(pdf_text, report_month, filename)
    report_month = parser.report_month

    if not report_month:
        print("[BSL MER] ERROR: Could not detect report month")
        return []

    units_data = parser.parse()

    records = []
    for unit, params in sorted(units_data.items()):
        if not params:
            continue

        # Map extracted parameters to month and till_month fields
        month_params = {}
        till_month_params = {}

        # Map _month and _cumul suffixes to proper fields
        param_mapping = {
            "production_month": "production",
            "production_cumul": "production",
            "bf_productivity_month": "bf_productivity",
            "bf_productivity_cumul": "bf_productivity",
            "coke_rate_month": "coke_rate",
            "coke_rate_cumul": "coke_rate",
            "cdi_month": "cdi",
            "cdi_cumul": "cdi",
            "fuel_rate_month": "fuel_rate",
            "fuel_rate_cumul": "fuel_rate",
            "hot_blast_temp_month": "hot_blast_temp",
            "hot_blast_temp_cumul": "hot_blast_temp",
            "o2_enrichment_month": "o2_enrichment",
            "o2_enrichment_cumul": "o2_enrichment",
            "slag_rate_month": "slag_rate",
            "slag_rate_cumul": "slag_rate",
        }

        for key, val in params.items():
            if key.endswith("_month"):
                param_name = key.replace("_month", "")
                month_params[param_name] = val
            elif key.endswith("_cumul"):
                param_name = key.replace("_cumul", "")
                till_month_params[param_name] = val

        records.append({
            "plant": "BSL",
            "report_month": report_month,
            "unit": unit,
            "techno_json": {
                "month": month_params,
                "till_month": till_month_params
            }
        })

    return records
