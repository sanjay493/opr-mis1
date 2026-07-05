"""
BSL Techno Extractor — Extracts from two file sources:
  1. BSL Techno-Economic Parameters Excel (Sheet1/Sheet2/Sheet3/Sheet4/SMS-I/SMS-II)
  2. BSL BF Performance & Analysis Report PDF (per-furnace BF data)

Both save to the techno_data table with plant='BSL'.
Unit names follow the same convention as RSP/BSP/ISP/DSP:
  BF_Shop, BF-1/BF-2/BF-4/BF-5, Coke Ovens, Sinter, SMS-I, SMS-II, General, CRM 1&2, CRM 3
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "excel_extractors"))
from excel_extractor_bsl import extract_preview, extract_preview_bf_pdf


# ---------------------------------------------------------------------------
# Standard BF PDF section → snake_case key (matches ISP/DSP BF param names)
# ---------------------------------------------------------------------------
_BF_PDF_KEY = {
    # Identity params
    "CDI":               "cdi",
    "HM Production":     "hm_production",
    "BF Productivity":   "bf_productivity",
    "HBT":               "hot_blast_temp",
    # Quality
    "Hot Metal Temp":    "hot_metal_temp",
    "Si in HM":          "si_in_hm",
    "S in HM":           "s_in_hm",
    "Slag Al2O3":        "slag_al2o3",
    "Slag MgO":          "slag_mgo",
    "Slag Basicity":     "slag_basicity",
    # Fuel rates
    "BF Coke Rate":      "coke_rate",
    "Nut Coke Rate":     "nut_coke_rate",
    "Fuel Rate":         "fuel_rate",
    "Carbon Rate":       "carbon_rate",
    "F Dust Rate":       "f_dust_rate",
    "CO CO2 Ratio":      "co_co2_ratio",
    # Burden / operating
    "O2 Enrichment":     "o2_enrichment",
    "Slag Rate":         "slag_rate",
    "Sinter in Burden":  "sinter_in_burden",
    "Sint Rate":         "sint_rate",
    "Ore Rate":          "ore_rate",
    # Raw material consumption (T/month)
    "Iron Ore":          "iron_ore",
    "Sinter Consumption":"sinter_consumption",
    "BF Scrap":          "bf_scrap",
    "Pellet Consumption":"pellet_consumption",
    "Nut Coke":          "nut_coke",
    "Coke Consumption":  "coke_consumption",
    "CDI Total":         "cdi_total",
    "Coke ECY":          "coke_ecy",
}

# Techno Excel shop-level BF section names → standard key
_BF_SHOP_SECTION_KEY = {
    "BF Productivity": "bf_productivity",
    "BF Coke Rate":    "coke_rate",
    "CDI":             "cdi",
    "Fuel Rate":       "fuel_rate",
    "Sinter in Burden":"sinter_in_burden",
    "O2 Enrichment":   "o2_enrichment",
    "Coke Screen Loss":"coke_screen_loss",  # goes to General, not BF_Shop
    "Nut Coke":        "nut_coke_rate",     # FAX GM OPRN sheet
    "Tar Injection":   "tar_injection",     # FAX GM OPRN sheet
}

# MAJOR-group KPI labels → standard key (matches RSP/ISP/BSP convention;
# plain _to_snake() of BSL's own label text would otherwise give a different
# key, e.g. "Coal to Hot Metal" -> "coal_to_hot_metal" instead of "coal_to_hm").
_MAJOR_KEY_NORM = {
    "Coal to Hot Metal": "coal_to_hm",
}

# SMS raw snake_case → normalized key matching RSP/BSP/ISP page-30 convention.
# Keys are the exact _to_snake() output for each BSL SMS parameter label.
_SMS_KEY_NORM = {
    "tap_to_tap_time_avail_hrs":       "tap_to_tap_time",
    "tap_to_tap_time_working_hrs":     "tap_to_tap_time_working",
    "converter_availability_cal_hr":   "converter_availability",
    "converter_availability_avail_hr": "converter_availability_avail",
    "sp_hot_metal_cons":               "specific_hm_consumption",
    "sp_scrap_cons":                   "specific_scrap_consumption",
    "fe_si_cons":                      "fe-si",    # hyphen preserved to match page_techno key
    "fe_mn_cons":                      "fe-mn",
    "si_mn_cons":                      "si-mn",
    "oxygen_blow_per_t_crude":         "oxygen_blowing",
    "refractory_cons":                 "refractory_cons",
}

# Coke oven labels where BSL's own wording diverges from the canonical key
# used by RSP/ISP/BSP and page_techno.py's page-28 schema.
_COKE_KEY_NORM = {
    "crude_tar":         "crude_tar_yield",
    "crude_benzol":      "crude_benzol_yield",
    "ammonium_sulphate": "ammonium_sulphate_yield",
}

# BF furnace IDs in BSL (which are under repair varies by month; repair rows auto-filtered by extractor)
_BSL_BF_UNITS = frozenset(["BF-1", "BF-2", "BF-3", "BF-4", "BF-5"])

# FAX GM OPRN's per-furnace BF Productivity is reported on both a "useful
# volume" and "working volume" basis (see excel_extractor_bsl.py's
# _FAX_BF_FURNACE_PARAMS). Every other plant (ISP, RSP, BSP, DSP) reports only
# the working-volume figure under the shared "bf_productivity" key that
# page_techno.py's page-27 BF Productivity row reads, so fold BSL's
# working-volume figure onto that key too instead of leaving it stranded
# under a separate name. The useful-volume figure keeps its own distinct key.
_BF_KEY_NORM = {
    "bf_productivity_working_volume": "bf_productivity",
    "bf_productivity_useful_volume":  "bf_productivity_useful",
}


def _to_snake(text: str) -> str:
    s = str(text).strip().lower()
    s = re.sub(r'[^a-z0-9%]+', '_', s)
    return s.strip('_')


def _clean_val(val) -> Optional[float]:
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip().upper()
        if s in ("NAN", "###", "-", "#DIV/0!", "#VALUE!", ""):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _derive_unit_and_key(row: dict):
    """
    Map a techno_param_row from the BSL Techno Excel to (unit_name, param_key).

    Row conventions in _TECHNO_PARAM_MAP:
      group_code=MILL_BSL:    section=mill unit,       parameter=display label
      group_code=SMS:         section=display label,   parameter="BSL"
      section in SMS-I/SMS-II:section=SMS unit,        parameter=display label
      section=Coke Ovens:     section=unit,            parameter=display label
      section=Sinter Plant:   section=unit,            parameter=display label
      group_code=IRON_MAKING: section=BF section,      parameter="BSL" (shop avg)
      group_code=IRON_MAKING, section=Blast Furnaces:  parameter=display label
      group_code=IRON_MAKING, section=Coke Screen Loss parameter="BSL"
      group_code=MAJOR:       section=display label,   parameter="BSL"
      group_code=COKE_SINTER, section=Energy:          parameter=display label
      group_code=COKE_SINTER, section=Water:           parameter=display label
    """
    section    = row.get("section",    "")
    parameter  = row.get("parameter",  "")
    group_code = row.get("group_code", "")

    # ── Rolling mills (CRM 1&2, CRM 3) ─────────────────────────────────────
    if group_code == "MILL_BSL":
        return section, _to_snake(parameter)

    # ── SMS shops (individual converters) ───────────────────────────────────
    if section in ("SMS-I", "SMS-II"):
        raw_key = _to_snake(parameter)
        return section, _SMS_KEY_NORM.get(raw_key, raw_key)

    # ── Coke Ovens ──────────────────────────────────────────────────────────
    if section == "Coke Ovens":
        raw_key = _to_snake(parameter)
        return "Coke Ovens", _COKE_KEY_NORM.get(raw_key, raw_key)

    # ── Sinter Plant ────────────────────────────────────────────────────────
    if section == "Sinter Plant":
        return "Sinter", _to_snake(parameter)

    # ── BF Shop averages (IRON_MAKING, parameter="BSL") ─────────────────────
    if group_code == "IRON_MAKING" and parameter == "BSL":
        if section == "Coke Screen Loss":
            return "General", "coke_screen_loss"
        key = _BF_SHOP_SECTION_KEY.get(section) or _to_snake(section)
        return "BF_Shop", key

    # ── Per-furnace BF params from FAX GM OPRN (section=furnace unit) ───────
    if group_code == "IRON_MAKING" and section in _BSL_BF_UNITS:
        raw_key = _to_snake(parameter)
        return section, _BF_KEY_NORM.get(raw_key, raw_key)

    # ── BF Shop derived params (Blast Furnaces section) ─────────────────────
    if group_code == "IRON_MAKING" and section == "Blast Furnaces":
        return "BF_Shop", _to_snake(parameter)

    # ── SMS shop overall refractory (Sheet1 row 55) ─────────────────────────
    if group_code == "SMS" and section == "Refractory":
        return "SMS", "refractory"

    # ── SMS shop overall params from FAX GM OPRN (LD Slag, Gross HM, etc.) ──
    if group_code == "SMS" and section not in ("SMS-I", "SMS-II"):
        return "SMS", _to_snake(section)

    # ── MAJOR KPIs → General ────────────────────────────────────────────────
    if group_code == "MAJOR":
        return "General", _MAJOR_KEY_NORM.get(section) or _to_snake(section)

    # ── COKE_SINTER Energy rows ─────────────────────────────────────────────
    if group_code == "COKE_SINTER" and section == "Energy":
        if "Specific Energy" in parameter:
            return "General", "specific_energy_consumption"
        return "Coke Ovens", _to_snake(parameter)

    # ── Water consumption → General ─────────────────────────────────────────
    if group_code == "COKE_SINTER" and section == "Water":
        return "General", "water_consumption"

    # ── Fallback ─────────────────────────────────────────────────────────────
    unit = section or "General"
    key  = _to_snake(parameter or section)
    key  = _BF_KEY_NORM.get(key, key)
    return unit, key


def _derive_unit_and_key_pdf(row: dict):
    """
    Map a BF PDF techno_param_row to (unit_name, param_key).

    PDF rows use:
      section  = metric name  ("CDI", "BF Productivity", "HBT", …)
      parameter = furnace id  ("BSL BF-1", "BSL BF-2", "BSL BF-4", "BSL BF-5", "BSL")
    """
    section   = row.get("section",   "")
    parameter = row.get("parameter", "")

    # unit: strip "BSL " prefix → "BF-1", "BF-2", etc.; shop avg stays "BF_Shop"
    if parameter == "BSL":
        unit = "BF_Shop"
    elif parameter.startswith("BSL BF-"):
        unit = parameter[4:]   # "BSL BF-1" → "BF-1"
    else:
        unit = parameter or "BF_Shop"

    key = _BF_PDF_KEY.get(section) or _to_snake(section)
    return unit, key


class BslTechnoExtractor:
    """
    Extract BSL techno parameters from either:
      - Techno-Economic Parameters Excel (.xls / .xlsx)
      - BF Performance & Analysis Report (.pdf)

    Both file types are auto-detected and output the same record format:
      [{"plant": "BSL", "report_month": "YYYY-MM",
        "unit": str, "techno_json": {"month": {...}, "till_month": {...}}}]
    """

    def __init__(self, file_path: str, report_month: str = ""):
        self.file_path    = file_path
        self.report_month = report_month
        self._is_pdf      = file_path.lower().endswith(".pdf")

    # ── Public API ────────────────────────────────────────────────────────────
    def extract(self) -> List[Dict]:
        try:
            if self._is_pdf:
                return self._extract_pdf()
            return self._extract_excel()
        except Exception as e:
            print(f"[BSL] ERROR during extraction: {e}")
            import traceback
            traceback.print_exc()
            return []

    # ── Private helpers ───────────────────────────────────────────────────────
    def _build_records(self, rows: list, derive_fn) -> List[Dict]:
        """Apply derive_fn to each row and group results by unit."""
        units_data: Dict[str, Dict] = {}
        for row in rows:
            if not row.get("parameter") and not row.get("section"):
                continue
            unit_name, param_key = derive_fn(row)
            if not unit_name or not param_key:
                continue
            if unit_name not in units_data:
                units_data[unit_name] = {"month": {}, "till_month": {}}
            mv = _clean_val(row.get("actual"))
            tv = _clean_val(row.get("cum_actual"))
            if mv is not None:
                units_data[unit_name]["month"][param_key]      = mv
            if tv is not None:
                units_data[unit_name]["till_month"][param_key] = tv

        records = [
            {"plant": "BSL", "report_month": self.report_month,
             "unit": u, "techno_json": d}
            for u, d in units_data.items()
        ]
        print(f"[BSL] {len(records)} units extracted")
        return records

    def _extract_excel(self) -> List[Dict]:
        print(f"[BSL] Excel extractor: {self.file_path}, month={self.report_month}")
        data = extract_preview(self.file_path, self.report_month)

        # Only process Techno-Economic Parameters files
        if data.get("report_type") == "CORP_SS" or "DPR" in data.get("source_type", ""):
            print("[BSL] Not a Techno Excel file (DPR or Corp SS) — no techno rows")
            return []

        rows = data.get("techno_param_rows", [])
        if not rows:
            print("[BSL] WARNING: techno_param_rows is empty")
            return []

        # Detect report_month from extracted data if not provided
        if not self.report_month:
            self.report_month = data.get("month", "")
        if not self.report_month:
            print("[BSL] ERROR: could not detect report month")
            return []

        print(f"[BSL] {len(rows)} techno rows from Excel, month={self.report_month}")
        return self._build_records(rows, _derive_unit_and_key)

    def _extract_pdf(self) -> List[Dict]:
        print(f"[BSL] PDF extractor: {self.file_path}, month={self.report_month}")
        if not self.report_month:
            raise ValueError("report_month is required for BSL BF PDF extraction")

        data = extract_preview_bf_pdf(self.file_path, self.report_month)
        rows = data.get("techno_param_rows", [])
        if not rows:
            print("[BSL] WARNING: no BF rows from PDF")
            return []

        print(f"[BSL] {len(rows)} techno rows from BF PDF, month={self.report_month}")
        return self._build_records(rows, _derive_unit_and_key_pdf)
