"""
BSL Month-End Report PDF Parser - Robust text-based extraction

Parses raw PDF text and extracts techno parameters for each furnace.
"""

import re
from typing import Dict, List, Optional, Tuple

_FURNACE_RE = re.compile(r'^(\d+|SHOP|SH)\b', re.IGNORECASE)
_FURNACE_MAP = {"1": "BF-1", "2": "BF-2", "4": "BF-4", "5": "BF-5", "SHOP": "BF_Shop", "SH": "BF_Shop"}


def _match_unit(furnace_str: str) -> Optional[str]:
    """Identify the furnace/shop unit from a row's first cell, tolerant of
    the different shop abbreviations used across tables ("Shop"/"SHOP"/"SH")."""
    m = _FURNACE_RE.match(furnace_str or "")
    if not m:
        return None
    return _FURNACE_MAP.get(m.group(1).upper())


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

        Returns: {"BF-1": {"production_month": 3678, ...}, ...}
        """
        units = {unit: {} for unit in ["BF-1", "BF-2", "BF-4", "BF-5", "BF_Shop"]}

        self._extract_production_data(units)
        self._extract_quality_data(units)
        self._extract_consumption_data(units)
        self._calculate_burden_percentages(units)

        return units

    def _extract_production_data(self, units: Dict):
        """Extract from PRODUCTION PERFORMANCE section - match by furnace ID."""
        prod_idx = self.text.find("PRODUCTION PERFORMANCE")
        if prod_idx < 0:
            return

        # Section ends where the Quality Parameters table's header begins
        section_end = self.text.find("COKE RATE", prod_idx)
        if section_end < 0:
            section_end = len(self.text)

        prod_section = self.text[prod_idx:section_end]
        lines = prod_section.split("\n")

        for line in lines:
            if "|" not in line or len(line) < 50:
                continue
            if any(keyword in line for keyword in ["PRODUCTION", "FCS", "No", "Tonnes", "Rate", "Temp"]):
                continue
            if line.count("*") > 10:
                continue

            cells = [c.strip() for c in line.split("|")]
            if len(cells) < 15:
                continue

            has_production = "/" in str(cells[2] if len(cells) > 2 else "")
            if not has_production:
                continue

            unit_id = _match_unit(cells[1] if len(cells) > 1 else "")
            if not unit_id:
                continue

            # [2] = Production (3203/104510)
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
        """Extract from QUALITY PARAMETERS section (Coke/Nut Coke/CDI/Fuel Rate).

        Bounded strictly between the "COKE RATE" header and "CAST DETAILS" —
        the Cast Details table that follows has furnace-ID rows with the same
        shape ("| 1. | .../... | ...") and was previously being scanned too
        (section end was found via the next "Consumption" match, which is
        *after* Cast Details), silently overwriting Coke/Nut Coke/CDI/Fuel
        Rate with Cast Details columns.
        """
        coke_idx = self.text.find("COKE RATE")
        if coke_idx < 0:
            return

        section_end = self.text.find("CAST DETAILS", coke_idx)
        if section_end < 0:
            section_end = self.text.find("Consumption", coke_idx)
        if section_end < 0:
            section_end = coke_idx + 3000

        qual_section = self.text[coke_idx:section_end]
        lines = qual_section.split("\n")

        for line in lines:
            if "|" not in line or len(line) < 40:
                continue
            if any(keyword in line for keyword in ["COKE", "CDI", "FUEL", "FCS", "No", "kg/THM", "N/C"]):
                continue
            if line.count("*") > 10:
                continue

            cells = [c.strip() for c in line.split("|")]
            if len(cells) < 12:
                continue

            has_coke = "/" in str(cells[8] if len(cells) > 8 else "")
            has_cdi  = "/" in str(cells[10] if len(cells) > 10 else "")
            has_fuel = "/" in str(cells[11] if len(cells) > 11 else "")
            if not (has_coke and has_cdi and has_fuel):
                continue

            unit_id = _match_unit(cells[1] if len(cells) > 1 else "")
            if not unit_id:
                continue

            # [8] = Coke Rate (440/439)
            m, c = _extract_both_values(cells[8])
            if m is not None:
                units[unit_id]["coke_rate_month"] = m
            if c is not None:
                units[unit_id]["coke_rate_cumul"] = c

            # [9] = N/C Rate / Nut Coke Rate (19/16)
            m, c = _extract_both_values(cells[9])
            if m is not None:
                units[unit_id]["nut_coke_rate_month"] = m
            if c is not None:
                units[unit_id]["nut_coke_rate_cumul"] = c

            # [10] = CDI Rate (108/94)
            m, c = _extract_both_values(cells[10])
            if m is not None:
                units[unit_id]["cdi_month"] = m
            if c is not None:
                units[unit_id]["cdi_cumul"] = c

            # [11] = Fuel Rate (568/548)
            m, c = _extract_both_values(cells[11])
            if m is not None:
                units[unit_id]["fuel_rate_month"] = m
            if c is not None:
                units[unit_id]["fuel_rate_cumul"] = c

    def _extract_consumption_data(self, units: Dict):
        """Extract from "Consumption of Raw Material / Consumption Rates" section.

        Column layout (verified against sample reports):
          [2]=Coke(t) [3]=IronOre(t) [4]=Sinter(t) [5]=Scrap(t) [6]=NutCoke
          [7]=CDI [8]=Pellet [9]=CokeEco [10]=O2 En(%) [11]=SLG RATE
        """
        cons_idx = self.text.find("Consumption")
        if cons_idx < 0:
            return

        section_end = self.text.find("PCM DETAILS", cons_idx)
        if section_end < 0:
            section_end = cons_idx + 5000

        cons_section = self.text[cons_idx:section_end]
        lines = cons_section.split("\n")

        for line in lines:
            if "|" not in line or len(line) < 50:
                continue
            if any(keyword in line for keyword in ["O2", "SLAG", "CARBON", "DUST", "Ratio", "kg/", "CONSUMPTION"]):
                continue
            if line.count("*") > 10:
                continue

            cells = [c.strip() for c in line.split("|")]
            if len(cells) < 12:
                continue

            unit_id = _match_unit(cells[1] if len(cells) > 1 else "")
            if not unit_id:
                continue

            # Raw material consumption — all "monthly/till_month" pairs
            m, c = _extract_both_values(cells[3] if len(cells) > 3 else "")
            if m is not None:
                units[unit_id]["iron_ore_consumption_month"] = m
            if c is not None:
                units[unit_id]["iron_ore_consumption_cumul"] = c

            m, c = _extract_both_values(cells[4] if len(cells) > 4 else "")
            if m is not None:
                units[unit_id]["sinter_consumption_month"] = m
            if c is not None:
                units[unit_id]["sinter_consumption_cumul"] = c

            m, c = _extract_both_values(cells[5] if len(cells) > 5 else "")
            if m is not None:
                units[unit_id]["scrap_consumption_month"] = m
            if c is not None:
                units[unit_id]["scrap_consumption_cumul"] = c

            m, c = _extract_both_values(cells[8] if len(cells) > 8 else "")
            if m is not None:
                units[unit_id]["pellet_consumption_month"] = m
            if c is not None:
                units[unit_id]["pellet_consumption_cumul"] = c

            # [10] = O2 Enrichment (%)
            m, c = _extract_both_values(cells[10] if len(cells) > 10 else "")
            if m is not None:
                units[unit_id]["o2_enrichment_month"] = m
            if c is not None:
                units[unit_id]["o2_enrichment_cumul"] = c

            # [11] = Slag Rate
            m, c = _extract_both_values(cells[11] if len(cells) > 11 else "")
            if m is not None:
                units[unit_id]["slag_rate_month"] = m
            if c is not None:
                units[unit_id]["slag_rate_cumul"] = c

    def _calculate_burden_percentages(self, units: Dict):
        """Calculate Sinter % and Pellet % in Burden from raw material consumption,
        separately for the month and till_month (cumulative) periods."""
        for unit, params in units.items():
            for suffix in ("month", "cumul"):
                iron_ore = params.get(f"iron_ore_consumption_{suffix}") or 0
                sinter   = params.get(f"sinter_consumption_{suffix}") or 0
                pellet   = params.get(f"pellet_consumption_{suffix}") or 0
                scrap    = params.get(f"scrap_consumption_{suffix}") or 0

                total = iron_ore + sinter + pellet + scrap
                if total > 0:
                    params[f"sinter_in_burden_{suffix}"] = round((sinter / total) * 100, 2)
                    params[f"pellet_in_burden_{suffix}"] = round((pellet / total) * 100, 2)


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

        month_params = {}
        till_month_params = {}

        for key, val in params.items():
            if key.endswith("_month"):
                param_name = key[:-len("_month")]
                month_params[param_name] = val
            elif key.endswith("_cumul"):
                param_name = key[:-len("_cumul")]
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
