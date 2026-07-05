"""
DSP Techno Extractor — Extracts from PDF reports
Converts DSP PDF techno data to JSON format for storage in techno_data table
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "excel_extractors"))
from pdf_extractor_dsp import extract_preview

# ---------------------------------------------------------------------------
# Mapping constants (mirror the param_def tables in pdf_extractor_dsp.py)
# ---------------------------------------------------------------------------

# Sections that come from _MAJOR_PAGE_DEFS — plant-level KPIs saved under "DSP" unit
_MAJOR_PARAM_SECTIONS = frozenset([
    "Specific Energy Consumption",
    "BOF Slag Utilisation",
    "Coke Screen Loss",
])

# All valid DSP blast-furnace names used as section values
_BF_FURNACE_NAMES = frozenset(["DSP BF-2", "DSP BF-3", "DSP BF-4"])

# Map PDF section name → standard unit name (strips "DSP " prefix to match RSP/BSP/ISP)
_BF_UNIT_NAME = {f: f.replace("DSP ", "") for f in _BF_FURNACE_NAMES}
# {"DSP BF-2": "BF-2", "DSP BF-3": "BF-3", "DSP BF-4": "BF-4"}


def _to_snake(text: str) -> str:
    """Convert display label to snake_case param key (matches RSP/BSP/ISP convention)."""
    s = str(text).strip().lower()
    s = re.sub(r'[^a-z0-9%]+', '_', s)
    return s.strip('_')


# SMS keys where the plain _to_snake() output diverges from the short/hyphenated
# convention already used by BSL/RSP/ISP and page_techno.py's own schemas.
_SMS_KEY_NORM = {
    "ferro_silicon_consumption":   "fe-si",
    "ferro_manganese_consumption": "fe-mn",
    "silicon_manganese_consumption": "si-mn",
    "heat_size":                   "average_heat_weight",
    "oxygen_converter":            "oxygen_blowing",
}

# Coke oven labels where DSP's own wording diverges from the canonical key
# used by RSP/ISP/BSP and page_techno.py's page-28 schema.
_COKE_KEY_NORM = {
    "coal_tar_yield":    "crude_tar_yield",
    "crude_benzol":      "crude_benzol_yield",
    "ammonium_sulphate": "ammonium_sulphate_yield",
}

# DSP's PDF reports BF Productivity on both a "useful volume" and a "working
# volume" basis; every other plant (see ISP's "BF Productivity (Working
# Volume)" and BSL's "Productivity W.V./24h") reports only the working-volume
# figure under the shared "bf_productivity" key, which is what page_techno.py's
# page-27 BF Productivity row looks up. Map DSP's working-volume key onto that
# shared key so it isn't stranded under a DSP-only name; the useful-volume
# figure keeps its own distinct key.
_BF_KEY_NORM = {
    "bf_productivity_working": "bf_productivity",
}


def _derive_unit_and_key(row: dict, report_yy: str):
    """
    Map a flat techno_param_row to (unit_name, param_key) for JSON grouping.

    Row field conventions (see pdf_extractor_dsp.py):
      - MILL_DSP group: section = unit name, parameter = display label
      - Sinter rows:    section = "Sinter Productivity", parameter = machine tag
      - BF CDI rows:    section = furnace/"DSP",  parameter = "CDI"
      - SMS params:     section = display label,  parameter = "DSP SMS"
      - MAJOR params:   section = display label,  parameter = "DSP"   (group varies)
      - Coke params:    section = display label,  parameter = "DSP",  group = COKE_SINTER
      - BF furnace:     section = furnace name,   parameter = display label
      - BF shop:        section = "DSP",          parameter = display label, group = IRON_MAKING
    """
    section    = row.get("section", "")
    parameter  = row.get("parameter", "")
    group_code = row.get("group_code", "")
    row_month  = row.get("month", "")

    row_yy   = row_month.split("'")[-1] if "'" in row_month else ""
    is_prior = bool(report_yy and row_yy and row_yy != report_yy)
    if is_prior:
        return None, None  # Caller must skip None returns

    if group_code == "MILL_DSP":
        # Merchant Mill, MSM, Wheel Plant, Axle Plant
        unit, key = section, _to_snake(parameter)

    elif section == "Sinter Productivity":
        # parameter = "DSP SP-1" or "DSP SP-2"
        unit, key = "Sinter", _to_snake(parameter)

    elif parameter == "CDI":
        if section in _BF_FURNACE_NAMES:
            unit = _BF_UNIT_NAME[section]   # "BF-2", "BF-3", "BF-4"
            key  = "cdi"
        else:
            unit = "BF_Shop"                # shop average CDI
            key  = "cdi"

    elif parameter == "DSP SMS":
        # SMS shop parameters — section holds the display label
        raw_key = _to_snake(section)
        unit, key = "SMS", _SMS_KEY_NORM.get(raw_key, raw_key)

    elif section in _MAJOR_PARAM_SECTIONS:
        # Plant-level KPIs → "General" unit, same as RSP/ISP
        unit, key = "General", _to_snake(section)

    elif section in _BF_FURNACE_NAMES:
        # Per-furnace params: each furnace is its own unit (like RSP BF-1, BF-4, BF-5)
        unit = _BF_UNIT_NAME[section]       # "BF-2", "BF-3", "BF-4"
        key  = _to_snake(parameter)         # "coke_rate", "silicon_in_hm", etc.

    elif group_code == "IRON_MAKING" and section == "DSP":
        # BF shop-level params (Slag Rate, Fuel Rate, Coke Rate shop avg)
        unit, key = "BF_Shop", _to_snake(parameter)

    elif group_code == "COKE_SINTER":
        # Coke oven parameters — section holds the display label
        raw_key = _to_snake(section)
        unit, key = "Coke Ovens", _COKE_KEY_NORM.get(raw_key, raw_key)

    else:
        unit = section or "DSP"
        key  = _to_snake(parameter or section)

    key = _BF_KEY_NORM.get(key, key)
    return unit, key


class DspTechnoExtractor:
    """
    Extract techno parameters from DSP PDF reports.
    Groups data by unit and formats as JSON with month/till_month structure.
    """

    def __init__(self, file_path: str, report_month: str = ""):
        self.file_path = file_path
        self.report_month = report_month
        self.pdf_data = None

    def _detect_report_month(self) -> str:
        if not self.pdf_data:
            return ""

        if self.pdf_data.get("pdf_report_month"):
            return self.pdf_data["pdf_report_month"]

        techno_rows = self.pdf_data.get("techno_param_rows", [])
        if not techno_rows:
            return ""

        month_str = techno_rows[0].get("month", "")
        try:
            if "'" not in month_str:
                return ""
            month_part, year_part = month_str.split("'")
            month_map = {
                "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
                "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
                "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
            }
            month_num = month_map.get(month_part, "")
            if not month_num:
                return ""
            full_year = f"20{year_part}" if len(year_part) == 2 else year_part
            return f"{full_year}-{month_num}"
        except Exception:
            return ""

    def extract(self) -> List[Dict]:
        """
        Extract techno data from DSP PDF and return as list of records:
            [{"plant": "DSP", "report_month": "YYYY-MM",
              "unit": str, "techno_json": {"month": {...}, "till_month": {...}}}]
        """
        try:
            fallback_month = self.report_month or (
                datetime.now().strftime("%Y-%m")
            )

            print(f"[DSP] Calling PDF extractor with month={fallback_month}")
            self.pdf_data = extract_preview(
                self.file_path, fallback_month, block="techno"
            )

            if not self.pdf_data:
                print("[DSP] ERROR: PDF extractor returned no data")
                return []

            techno_rows = self.pdf_data.get("techno_param_rows", [])
            if not techno_rows:
                print("[DSP] WARNING: techno_param_rows is empty")
                return []

            print(f"[DSP] Extracted {len(techno_rows)} techno rows from PDF")

            if not self.report_month:
                self.report_month = self._detect_report_month()
                if not self.report_month:
                    print("[DSP] ERROR: Could not detect report month from PDF")
                    return []

            print(f"[DSP] Report month: {self.report_month}")

            report_yy = self.report_month.split("-")[0][-2:]
            units_data: Dict[str, Dict] = {}

            for row in techno_rows:
                if not row.get("parameter") and not row.get("section"):
                    continue

                unit_name, param_key = _derive_unit_and_key(row, report_yy)
                if unit_name is None:  # prior-year row — skip
                    continue

                if unit_name not in units_data:
                    units_data[unit_name] = {"month": {}, "till_month": {}}

                units_data[unit_name]["month"][param_key]      = _clean_val(row.get("actual"))
                units_data[unit_name]["till_month"][param_key] = _clean_val(row.get("cum_actual"))

            records = []
            for unit_name, techno_json in units_data.items():
                records.append({
                    "plant":        "DSP",
                    "report_month": self.report_month,
                    "unit":         unit_name,
                    "techno_json":  techno_json,
                })

            print(f"[DSP] {len(records)} units extracted")
            return records

        except Exception as e:
            print(f"[DSP] ERROR during extraction: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return []


def _clean_val(val) -> Optional[float]:
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip().upper()
        if s in ("NAN", "###", "-", "#DIV/0!", ""):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None
