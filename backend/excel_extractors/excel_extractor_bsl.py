import re
import openpyxl
from openpyxl.utils import get_column_letter
import logging
import sqlite3
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger("excel_extractor")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "mis_reports.db")

MONTH_NAMES = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May",     "06": "June",     "07": "July",  "08": "August",
    "09": "September","10": "October", "11": "November","12": "December"
}
MONTH_NUMS = {v: k for k, v in MONTH_NAMES.items()}


def clean_val(val) -> Optional[float]:
    if val is None or str(val).strip().lower() in ("nan", "###", "-", "#div/0!", ""):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def extract_and_save_excel(file_path: str, report_month: str = "", source_file_name: str = "") -> bool:
    """
    Dispatcher: auto-detects BSL file type by sheet name and calls the correct extractor.

    Supported file types:
      • DPR Mail (.xlsx)         — sheet 'DPR'  (month-end daily production report)
      • Final Monthly Report     — (commented out, to be implemented)
    """
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet_names = wb.sheetnames
        logger.info(f"BSL: loading file. Sheets: {sheet_names}")

        if "DPR" in sheet_names:
            return _extract_dpr_report(wb, source_file_name)

        raise ValueError(
            "Uploaded BSL file does not match any known format. "
            "Expected sheet 'DPR' (DPR Mail month-end report) or "
            "Sheet1 with 'SPECIAL STEEL' title (Corporate Office Special Steel report — "
            "use Extract & Preview workflow for that file)."
        )
    except ValueError as ve:
        logger.error(f"BSL validation error: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"BSL extraction error: {e}")
        return False


# ---------------------------------------------------------------------------
# Extractor 1 — BSL DPR Mail (month-end daily production report, sheet: DPR)
# ---------------------------------------------------------------------------

def _extract_dpr_report(wb, source_file_name: str) -> bool:
    """
    Extracts cumulative production data from the BSL DPR Mail report (sheet 'DPR').

    Date is auto-detected from cell O1 (stored as a Python datetime by Excel).

    Cell map — sheet 'DPR':
      Oven Pushing (nos/day)  P6    — nos/day average, no unit conversion
      Total Sinter         P7    — tonnes → /1000
      Hot Metal            P8
      Pig Iron             E30
      SMS-1 CCM-1          P10
      SMS-2 CCM-1&2        P11
      Total Crude Steel    P12
      HSM Total HR Coil    P14
      HSM HR Coil (Sale)   E7
      HSM HR Plate         E8
      HR Sheet             E9
      CRC&S(1&2)           E10
      CRC(3)               E11
      GP/GC                E12
      GPC3                 E13
      CRSALE               E29
      Saleable Steel       P31
      Saleable Semis       E32
      Finished Steel       P31 − E32  (derived: saleable steel minus semis)
    """
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import db

    ws = wb["DPR"]

    # Auto-detect month from O1 (Excel stores it as a Python datetime object)
    o1_raw = ws["O1"].value
    if isinstance(o1_raw, datetime):
        m_num = str(o1_raw.month).zfill(2)
        year  = str(o1_raw.year)
        db_report_month = f"{year}-{m_num}"
    elif o1_raw:
        # Fallback: try to parse date string formats DD.MM.YYYY or YYYY-MM-DD
        date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", str(o1_raw))
        if date_match:
            _d, m_num, year = date_match.groups()
            db_report_month = f"{year}-{m_num}"
        else:
            raise ValueError(
                f"Cannot parse date from cell O1: {repr(o1_raw)}. "
                "Expected a date value (DD.MM.YYYY or Excel date)."
            )
    else:
        raise ValueError("Cell O1 is empty — cannot determine report month.")

    logger.info(f"BSL DPR: month auto-detected from O1 → {db_report_month}")

    from cells_loader import get_extractor_config
    _cfg = get_extractor_config("bsl_dpr")

    NO_CONVERT = set(_cfg.get("no_convert", ["Oven Pushing (nos/day)"]))

    # Cell map: item_name → A1-style address. Falls back to hardcoded defaults.
    production_cells = _cfg.get("cells", {
        "Oven Pushing (nos/day)": "P6",
        "Total Sinter":        "P7",
        "Hot Metal":           "P8",
        "Pig Iron":            "E30",
        "SMS-1 CCM-1":         "P10",
        "SMS-2 CCM-1&2":       "P11",
        "Total Crude Steel":   "P12",
        "HSM Total HR Coil":   "P14",
        "HSM HR Coil (Sale)":  "E7",
        "HSM HR Plate":        "E8",
        "HR Sheet":            "E9",
        "CRC&S(1&2)":          "E10",
        "CRC(3)":              "E11",
        "GP/GC":               "E12",
        "GPC3":                "E13",
        "CRSALE":              "E29",
        "Saleable Steel":      "P31",
        "Saleable Semis":      "E32",
    })

    _default_derived = [{"item": "Finished Steel", "op": "subtract", "a": "P31", "b": "E32"}]
    derived_rules = _cfg.get("derived", _default_derived)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    vals_extracted = 0

    def _save(item_name, val):
        nonlocal vals_extracted
        if val is not None:
            vals_extracted += 1
            if item_name not in NO_CONVERT:
                val = round(val / 1000.0, 3)
        cursor.execute("""
            INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, item_name)
            DO UPDATE SET month_actual = excluded.month_actual
        """, (db_report_month, "BSL", item_name, val))

    for item_name, cell in production_cells.items():
        _save(item_name, clean_val(ws[cell].value))

    # Derived values driven by config
    for d in derived_rules:
        item = d["item"]
        if d["op"] == "subtract":
            a_val = clean_val(ws[d["a"]].value)
            b_val = clean_val(ws[d["b"]].value)
            if a_val is not None and b_val is not None:
                _save(item, a_val - b_val)
            elif a_val is not None:
                _save(item, a_val)
        elif d["op"] == "add":
            parts = [clean_val(ws[c].value) for c in d.get("cells", [])]
            parts = [v for v in parts if v is not None]
            if parts:
                _save(item, sum(parts))

    if vals_extracted == 0:
        raise ValueError(
            "No numeric data found at the expected cell locations in sheet 'DPR'. "
            "Please verify this is the correct BSL DPR Mail file."
        )

    conn.commit()
    conn.close()

    db.log_extraction(
        plant="BSL",
        report_month=db_report_month,
        file_name=source_file_name,
        sheet_name="DPR",
        source_type="DPR Mail (Month-End)",
        items_extracted=vals_extracted,
    )
    logger.info(f"BSL DPR extraction done: {vals_extracted} values saved for {db_report_month}.")
    return True


# ---------------------------------------------------------------------------
# Extractor 2 — BSL Techno-Economic Parameters (TECHNO <MON><YYYY>.XLS)
# ---------------------------------------------------------------------------
#
# Sheet layout:
#   Sheet1 — COKE AND COAL CHEMICALS, SINTER PLANT + shared plant KPIs
#   Sheet2 — Coke Oven parameters
#   SMS-I  — Steel Melting Shop (BOF / Converter) parameters
#
# Column convention: mon_col = month actual; mon_col+1 = till the month (cumulative)
#
# Parameters: (sheet, row_1based, mon_col, multiplier,
#              group_code, section, parameter, unit)
# ---------------------------------------------------------------------------

try:
    import xlrd as _xlrd
    _XLRD_OK = True
except ImportError:
    _XLRD_OK = False


class _XlsCell:
    __slots__ = ("value",)
    def __init__(self, value):
        self.value = None if value == "" else value


class _XlsSheet:
    def __init__(self, sheet):
        self._s = sheet
        self.max_row    = sheet.nrows
        self.max_column = sheet.ncols

    def cell(self, row: int, col: int) -> "_XlsCell":
        r, c = row - 1, col - 1
        if r < 0 or r >= self._s.nrows or c < 0 or c >= self._s.ncols:
            return _XlsCell(None)
        v = self._s.cell_value(r, c)
        return _XlsCell(v)


class _XlsWb:
    def __init__(self, wb):
        self._wb = wb

    @property
    def sheetnames(self):
        return self._wb.sheet_names()

    def __getitem__(self, name: str) -> "_XlsSheet":
        return _XlsSheet(self._wb.sheet_by_name(name))

    def __contains__(self, name: str) -> bool:
        return name in self._wb.sheet_names()


def _open_wb(file_path: str):
    """Open .xls (xlrd) or .xlsx (openpyxl) and return a unified workbook."""
    if file_path.lower().endswith(".xls"):
        if not _XLRD_OK:
            raise ImportError(
                "xlrd is required for Excel 97-2003 (.xls) files. "
                "Install with: pip install xlrd"
            )
        return _XlsWb(_xlrd.open_workbook(file_path))
    return openpyxl.load_workbook(file_path, data_only=True)


def _cell_float(ws, row: int, col: int) -> Optional[float]:
    """Read a cell and convert to float; return None on blank/error."""
    v = ws.cell(row, col).value
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "—", "nan", "###", "#DIV/0!", "#VALUE!", "#N/A"):
        return None
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


# (sheet_name, row, mon_col, multiplier, group_code, section, parameter, unit)
# cum_col is always mon_col + 1 (next column, same row = "till the month")
_TECHNO_PARAM_MAP = [
    # ── Sheet1 ─────────────────────────────────────────────────────────────
    ("Sheet1", 10,  6, 1000.0, "COKE_SINTER", "Energy",                "Sp. Heat Cons.",                    "Kcal/TCO"),
    ("Sheet1", 26,  6,    1.0, "COKE_SINTER", "Energy",                "Specific Energy Consumption",       "KWH/TCHS"),
    ("Sheet1", 31,  6,    1.0, "COKE_SINTER", "Sinter Plant",          "Machine Productivity",              "T/m²/hr"),
    ("Sheet1", 33,  6,    1.0, "IRON_MAKING", "BF Productivity",       "BSL",                               "T/m³/day"),
    ("Sheet1", 35,  6,    1.0, "IRON_MAKING", "BF Coke Rate",          "BSL",                               "Kg/THM"),
    ("Sheet1", 37,  6,    1.0, "IRON_MAKING", "CDI",                   "BSL",                               "Kg/THM"),
    ("Sheet1", 37,  6,    1.0, "MAJOR",       "CDI Rate",              "BSL",                               "kg/Thm"),
    ("Sheet1", 39,  6,    1.0, "IRON_MAKING", "Fuel Rate",             "BSL",                               "Kg/THM"),
    ("Sheet1", 41,  6,    1.0, "MAJOR",       "Coal to Hot Metal",     "BSL",                               "Ratio"),
    ("Sheet1", 49,  6,    1.0, "MILL_BSL",    "CRM 1&2",               "Yield of HR Coil",                  "%"),
    ("Sheet1", 51,  6,    1.0, "MILL_BSL",    "CRM 3",                 "Yield of HR Coil",                  "%"),
    ("Sheet1", 55,  6,    1.0, "SMS",         "Refractory",            "BSL",                               "Kg/TCS"),
    ("Sheet1", 57,  6,    1.0, "COKE_SINTER", "Water",                 "Water Consumption",                 "m³/T"),
    # ── Sheet2 ─────────────────────────────────────────────────────────────
    ("Sheet2", 11,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Dry Coal Charge per Oven",          "T/oven"),
    ("Sheet2", 12,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Average Coking Time",               "Hrs"),
    ("Sheet2", 14,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Gross Coke Yield",                  "%"),
    ("Sheet2", 15,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "BF Coke Yield",                     "%"),
    ("Sheet2", 16,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Ammonium Sulphate",                 "Kg/TCO"),
    ("Sheet2", 17,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Crude Tar",                         "Kg/TCO"),
    ("Sheet2", 18,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Crude Benzol",                      "Kg/TCO"),
    ("Sheet2", 19,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Coke Oven Gas",                     "Nm³/TCO"),
    ("Sheet2", 21,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "CV of Coke Oven Gas",               "Kcal/Nm³"),
    ("Sheet2", 26,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Ash in Coal Blend",                 "%"),
    ("Sheet2", 27,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "VM in Coal Blend",                  "%"),
    ("Sheet2", 28,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Coal Crushing Index",               "%"),
    ("Sheet2", 29,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Ash in BF Coke",                    "%"),
    ("Sheet2", 30,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Fixed Carbon in BF Coke",           "%"),
    ("Sheet2", 31,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Coke CSR",                          "%"),
    ("Sheet2", 32,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Coke CRI",                          "%"),
    ("Sheet2", 33,  6,    1.0, "COKE_SINTER", "Coke Ovens",            "Coke M-10",                         "%"),
    # ── Sheet3 ─────────────────────────────────────────────────────────────
    ("Sheet3", 25,  6,    1.0, "COKE_SINTER", "Sinter Plant",          "Coke Crushing Index for Sinter",    "%"),
    ("Sheet3", 27,  6,    1.0, "COKE_SINTER", "Sinter Plant",          "Flux Crushing Index for Sinter",    "%"),
    ("Sheet3", 29,  6,    1.0, "COKE_SINTER", "Sinter Plant",          "Sinter Return",                     "%"),
    ("Sheet3", 31,  6,    1.0, "COKE_SINTER", "Sinter Plant",          "FeO in Sinter",                     "%"),
    ("Sheet3", 39,  6,    1.0, "COKE_SINTER", "Sinter Plant",          "Basicity of Sinter",                "ratio"),
    ("Sheet3", 41,  6,    1.0, "COKE_SINTER", "Sinter Plant",          "Fe% in Sinter",                     "%"),
    ("Sheet3", 43,  6,    1.0, "COKE_SINTER", "Sinter Plant",          "Sinter M/c Availability",           "%"),
    ("Sheet3", 46,  6,    1.0, "COKE_SINTER", "Sinter Plant",          "Sinter M/c Utilization",            "%"),
    # ── Sheet4 ─────────────────────────────────────────────────────────────
    ("Sheet4", 31,  6,    1.0, "IRON_MAKING", "Sinter in Burden",      "BSL",                               "%"),
    ("Sheet4", 33,  6,    1.0, "IRON_MAKING", "O2 Enrichment",         "BSL",                               "%"),
    ("Sheet4", 35,  6,    1.0, "IRON_MAKING", "Coke Screen Loss",      "BSL",                               "%"),
    ("Sheet4", 37,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Slag Rate",                          "Kg/THM"),
    ("Sheet4", 38,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "BF Gas Yield",                       "Nm³/THM"),
    ("Sheet4", 39,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "CV of BF Gas",                       "Kcal/Nm³"),
    ("Sheet4", 40,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Furnace Availability",               "%"),
    ("Sheet4", 41,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Furnace Utilization",                "%"),
    # ── SMS-I ──────────────────────────────────────────────────────────────
    ("SMS-I",   12,  6,    1.0, "SMS",         "SMS-I",                 "Tap to Tap Time (Avail. Hrs)",      "Min"),
    ("SMS-I",   14,  6,    1.0, "SMS",         "SMS-I",                 "Tap to Tap Time (Working Hrs)",     "Min"),
    ("SMS-I",  16,  6,    1.0, "SMS",         "SMS-I",                 "Average Lining Life",               "Heats"),
    ("SMS-I",  18,  6,    1.0, "SMS",         "SMS-I",                 "Converter Availability (Cal. Hr)",  "%"),
    ("SMS-I",  20,  6,    1.0, "SMS",         "SMS-I",                 "Converter Availability (Avail. Hr)","%"),
    ("SMS-I",  23,  6,    1.0, "SMS",         "SMS-I",                 "Sp. Hot Metal Cons.",               "Kg/TCS"),
    ("SMS-I",  25,  6,    1.0, "SMS",         "SMS-I",                 "Sp. Scrap Cons.",                   "Kg/TCS"),
    ("SMS-I",  27,  6,    1.0, "SMS",         "SMS-I",                 "Sp. Iron Ore Cons.",                "Kg/TCS"),
    ("SMS-I",  26,  6,    1.0, "SMS",         "SMS-I",                 "Sp. Pellet Cons.",                  "Kg/TCS"),
    ("SMS-I",  28,  6,    1.0, "SMS",         "SMS-I",                 "Fe-Si Cons.",                       "Kg/TCS"),
    ("SMS-I",  29,  6,    1.0, "SMS",         "SMS-I",                 "Fe-Mn Cons.",                       "Kg/TCS"),
    ("SMS-I",  30,  6,    1.0, "SMS",         "SMS-I",                 "Si-Mn Cons.",                       "Kg/TCS"),
    ("SMS-I",  34,  6,    1.0, "SMS",         "SMS-I",                 "Oxygen Blow per T Crude",           "Nm³/T CS"),
    ("SMS-I",  33,  6,    1.0, "SMS",         "SMS-I",                 "Refractory Cons.",                  "Kg/TCS"),
    ("SMS-I",  40,  6,    1.0, "SMS",         "SMS-I",                 "Heat Consumed",                     "Kcal/T CS"),
    ("SMS-I",  42,  6,    1.0, "SMS",         "SMS-I",                 "Power Consumed",                    "KWH/T CS"),
    ("SMS-I",  48,  6,    1.0, "SMS",         "SMS-I",                 "Reblown Heat",                      "%"),
    ("SMS-I",  50,  6,    1.0, "SMS",         "SMS-I",                 "FeO in Slag",                       "%"),
    # ── SMS-II ─────────────────────────────────────────────────────────────
    ("SMS-II",  12,  6,    1.0, "SMS",         "SMS-II",                "Tap to Tap Time (Avail. Hrs)",      "Min"),
    ("SMS-II",  14,  6,    1.0, "SMS",         "SMS-II",                "Tap to Tap Time (Working Hrs)",     "Min"),
    ("SMS-II", 16,  6,    1.0, "SMS",         "SMS-II",                "Average Lining Life",               "Heats"),
    ("SMS-II", 18,  6,    1.0, "SMS",         "SMS-II",                "Converter Availability (Cal. Hr)",  "%"),
    ("SMS-II", 20,  6,    1.0, "SMS",         "SMS-II",                "Converter Availability (Avail. Hr)","%"),
    ("SMS-II", 23,  6,    1.0, "SMS",         "SMS-II",                "Sp. Hot Metal Cons.",               "Kg/TCS"),
    ("SMS-II", 25,  6,    1.0, "SMS",         "SMS-II",                "Sp. Scrap Cons.",                   "Kg/TCS"),
    ("SMS-II", 27,  6,    1.0, "SMS",         "SMS-II",                "Sp. Iron Ore Cons.",                "Kg/TCS"),
    ("SMS-II", 26,  6,    1.0, "SMS",         "SMS-II",                "Sp. Pellet Cons.",                  "Kg/TCS"),
    ("SMS-II", 28,  6,    1.0, "SMS",         "SMS-II",                "Fe-Si Cons.",                       "Kg/TCS"),
    ("SMS-II", 29,  6,    1.0, "SMS",         "SMS-II",                "Fe-Mn Cons.",                       "Kg/TCS"),
    ("SMS-II", 30,  6,    1.0, "SMS",         "SMS-II",                "Si-Mn Cons.",                       "Kg/TCS"),
    ("SMS-II", 36,  6,    1.0, "SMS",         "SMS-II",                "Oxygen Blow per T Crude",           "Nm³/T CS"),
    ("SMS-II", 35,  6,    1.0, "SMS",         "SMS-II",                "Refractory Cons.",                  "Kg/TCS"),
    ("SMS-II", 42,  6,    1.0, "SMS",         "SMS-II",                "Heat Consumed",                     "Kcal/T CS"),
    ("SMS-II", 44,  6,    1.0, "SMS",         "SMS-II",                "Power Consumed",                    "KWH/T CS"),
    ("SMS-II", 50,  6,    1.0, "SMS",         "SMS-II",                "Reblown Heat",                      "%"),
    ("SMS-II", 52,  6,    1.0, "SMS",         "SMS-II",                "FeO in Slag",                       "%"),
]

_MONTH_FROM_NAME = {
    "JANUARY": "01", "FEBRUARY": "02", "MARCH": "03", "APRIL": "04",
    "MAY": "05", "JUNE": "06", "JULY": "07", "AUGUST": "08",
    "SEPTEMBER": "09", "OCTOBER": "10", "NOVEMBER": "11", "DECEMBER": "12",
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "JUN": "06", "JUL": "07", "AUG": "08", "SEP": "09",
    "OCT": "10", "NOV": "11", "DEC": "12",
}


def _detect_month_from_filename(file_path: str) -> Optional[str]:
    """Try to extract YYYY-MM from a filename like TECHNO APRIL2026.XLS."""
    import re
    name = os.path.basename(file_path).upper()
    m = re.search(
        r'(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER'
        r'|JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{4})',
        name
    )
    if m:
        mon_str, yr = m.group(1), m.group(2)
        mon_num = _MONTH_FROM_NAME.get(mon_str)
        if mon_num:
            return f"{yr}-{mon_num}"
    return None


_MONTH_NAME_RE = re.compile(
    r'\b(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)'
    r'[\s\-–]*(\d{4})\b'
)
# BSL BF PDF header: "BF PERFORMANCE & ANALYSIS REPORT For DD/MM/YYYY"
_DATE_DDMMYYYY_RE = re.compile(r'\b\d{2}/(\d{2})/(\d{4})\b')


def _detect_month_from_pdf_text(text: str) -> Optional[str]:
    """Detect YYYY-MM from BSL BF PDF text.

    Primary: DD/MM/YYYY date in the report header line (e.g. 'For 30/04/2026').
    Fallback: month-name + year pattern for any future format variation.
    Searches the first 500 chars first (header), then the full text.
    """
    for chunk in (text[:500], text):
        m = _DATE_DDMMYYYY_RE.search(chunk)
        if m:
            mon, yr = m.group(1), m.group(2)
            if "01" <= mon <= "12":
                return f"{yr}-{mon}"
    for chunk in (text[:500], text):
        m = _MONTH_NAME_RE.search(chunk.upper())
        if m:
            mon_num = _MONTH_FROM_NAME.get(m.group(1))
            if mon_num:
                return f"{m.group(2)}-{mon_num}"
    return None


def _detect_month_from_sheet1(wb) -> Optional[str]:
    """Scan the first 5 rows of Sheet1 for a month-name + year pattern (Techno Excel header)."""
    try:
        ws = wb["Sheet1"]
    except (KeyError, Exception):
        return None
    for row in range(1, 6):
        for col in range(1, 10):
            try:
                val = str(ws.cell(row, col).value or "").upper()
            except Exception:
                continue
            m = _MONTH_NAME_RE.search(val)
            if m:
                mon_num = _MONTH_FROM_NAME.get(m.group(1))
                if mon_num:
                    return f"{m.group(2)}-{mon_num}"
    return None


def _fmt_month(ym: str) -> str:
    """Format 'YYYY-MM' as 'Month YYYY' for human-readable error messages."""
    try:
        y, mo = ym[:4], ym[5:7]
        return f"{MONTH_NAMES[mo]} {y}"
    except Exception:
        return ym


def _assert_month_match(detected: Optional[str], user_month: str, source: str) -> None:
    """Raise ValueError if detected month does not match user-selected month."""
    if detected and detected != user_month:
        raise ValueError(
            f"Month mismatch: the {source} contains data for "
            f"{_fmt_month(detected)}, but you selected {_fmt_month(user_month)}. "
            f"Please select '{_fmt_month(detected)}' in the month picker, "
            f"or upload the file for {_fmt_month(user_month)}."
        )


# ---------------------------------------------------------------------------
# Extractor 3 — BSL Corporate Office Special Steel Report
# ---------------------------------------------------------------------------
# Sheet: Sheet1
#   Row 1:    Title "SPECIAL STEEL REPORT FOR <MONTH> <YEAR>"
#   Row 2:    Date in cell I2 (col 9) — last day of report month
#   Rows 4-6: Two-row column headers
#   Rows 7+:  Data (product group in col A, grade in col B)
#
# Col  A (1)  Product group  (HR COIL / HR PLATE / HR SHEET / CR COIL/ / SLAB)
# Col  B (2)  Quality / Grade
# Col  D (4)  Actual Up To Last Month  (= last month's monthly actual; for growth ref)
# Col  F (6)  APP FOR THE MONTH  (monthly plan, not stored)
# Col  G (7)  ORDER AVAILABLE TOTAL  (current outstanding orders → order_qty)
# Col  I (9)  Despatch Till Date  (= this month's monthly despatch → actual_despatch)
#
# Note: Col I is the MONTHLY figure for the report month, NOT a running cumulative.
# "Actual Up To Last Month" (D) = last month's monthly actual (for growth comparison).
# ---------------------------------------------------------------------------

_CORP_SS_PRODUCT_MAP = {
    "HR COIL":  "HR COIL",
    "HR PLATE": "HR PLATE",
    "HR SHEET": "HR SHEET",
    "CR COIL/": "CR COIL/SHEET/GP GC",  # spans two col-A cells; "SHEET" continues
    "SLAB":     "SLAB",
}
_CORP_SS_STOP_A  = {"GRND/TOT"}      # grand-total sentinel — stop scan
_CORP_SS_SKIP_A  = {"TOTAL"}          # section-total row — skip, keep product
_CORP_SS_SKIP_B  = {"TOTAL", "GRAND TOTAL"}
_CORP_SS_CONT    = "SHEET"            # continuation of "CR COIL/SHEET/GP GC"


def _is_corp_ss_file(wb) -> bool:
    """True if the workbook is a BSL Corporate Office Special Steel report."""
    if "Sheet1" not in wb.sheetnames:
        return False
    try:
        r1 = str(wb["Sheet1"].cell(1, 1).value or "").upper()
        return "SPECIAL STEEL" in r1
    except Exception:
        return False


def _corp_ss_month(ws) -> Optional[str]:
    """Extract 'YYYY-MM' from cell I2 (row 2, col 9)."""
    raw = ws.cell(2, 9).value
    if raw is None:
        return None
    if hasattr(raw, "year") and hasattr(raw, "month"):
        return f"{raw.year}-{str(raw.month).zfill(2)}"
    s = str(raw).strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


def _extract_corp_ss_preview(wb, report_month: str) -> dict:
    """Parse BSL Corporate Office Special Steel Report (Sheet1).

    Col G (ORDER AVAILABLE TOTAL)  = outstanding order quantity → order_qty.
    Col I (Despatch Till Date)     = monthly actual for the report month → actual_despatch.
    Col D (Actual Up To Last Month) = previous month's actual (stored as cply_actual for reference).
    """
    ws = wb["Sheet1"]
    detected = _corp_ss_month(ws)
    db_month = detected or report_month

    rows = []
    current_product = ""
    sort_order = 0

    for row_num in range(7, ws.max_row + 1):
        a_raw = ws.cell(row_num, 1).value
        b_raw = ws.cell(row_num, 2).value
        d_raw = ws.cell(row_num, 4).value   # last month's actual (growth reference)
        g_raw = ws.cell(row_num, 7).value   # order available total → order_qty
        i_raw = ws.cell(row_num, 9).value   # this month's despatch → actual_despatch

        a_str = str(a_raw).strip() if a_raw is not None else ""
        b_str = str(b_raw).strip() if b_raw is not None else ""

        if a_str in _CORP_SS_STOP_A:
            break

        if a_str:
            if a_str in _CORP_SS_SKIP_A:
                continue  # section TOTAL row — skip, keep current product
            elif a_str in _CORP_SS_PRODUCT_MAP:
                current_product = _CORP_SS_PRODUCT_MAP[a_str]
            elif a_str == _CORP_SS_CONT:
                pass  # "SHEET" continues "CR COIL/SHEET/GP GC"; process col B
            else:
                logger.debug("BSL CorpSS row %d: unknown col-A %r — skipped", row_num, a_str)
                continue

        if not b_str or b_str in _CORP_SS_SKIP_B:
            continue
        if not current_product:
            continue

        d_val = clean_val(d_raw)   # last month's actual (display reference)
        g_val = clean_val(g_raw)   # order available total
        i_val = clean_val(i_raw)   # this month's actual despatch

        sort_order += 1
        has_data = bool(
            (g_val is not None and g_val != 0) or
            (i_val is not None and i_val != 0)
        )

        rows.append({
            "product":         current_product,
            "quality_grade":   b_str,
            "section":         "",
            "sort_order":      sort_order,
            "order_qty":       g_val,    # order available total (col G)
            "actual_despatch": i_val,    # monthly actual despatch (col I)
            "cply_actual":     d_val,    # last month's actual (col D, display only)
            "unit":            "T",
            "cell":            f"R{row_num}:G(order) / I(actual)",
            "status":          "ok" if has_data else "zero",
        })

    ok = sum(1 for r in rows if r["status"] == "ok")
    logger.info("BSL CorpSS: %d ok / %d total rows for %s", ok, len(rows), db_month)

    if ok == 0 and not rows:
        raise ValueError(
            "No data rows found in Sheet1. "
            "Verify this is a BSL 'Corporate office Report <MON><YEAR>.xlsx' file."
        )

    note = (f"{ok} grade rows extracted for {db_month}. "
            "Order Qty = ORDER AVAILABLE TOTAL (col G); "
            "Actual = Despatch Till Date (col I, monthly).")

    return {
        "plant":              "BSL",
        "month":              db_month,
        "source_type":        "BSL Corporate Office Special Steel Report",
        "sheets":             "Sheet1",
        "workbook_sheets":    list(wb.sheetnames),
        "report_type":        "CORP_SS",
        "detected_month":     detected,
        "production_rows":    [],
        "special_steel_rows": rows,
        "special_steel_note": note,
        "techno_rows":        [],
        "techno_param_rows":  [],
    }


def extract_preview_bf_pdf(file_path: str, report_month: str) -> dict:
    """
    Extract BF-wise performance data from BSL BF Performance & Analysis Report PDF.

    Parses three tables:
      Table 1 — Production Performance: Productivity (W.V./24h), Hot Blast Temp
      Table 2 — Fuel/Quality Parameters: Coke Rate, Nut Coke Rate, CDI Rate, Fuel Rate
      Table 3 — Raw Material Consumption: O2 Enrichment%, Slag Rate

    All values use OnDate/Monthly format (X/Y); monthly (second) value is stored.
    Cumulative (till-month) is set to None — not available in this PDF.
    BF-3 (UNDER CAPITAL REPAIR) is skipped automatically.
    """
    import pdfplumber, re as _re

    fname = os.path.basename(file_path)
    logger.info("BSL BF PDF: opening %s for month %s", fname, report_month)

    try:
        with pdfplumber.open(file_path) as pdf:
            full_text = "\n".join(pg.extract_text() or "" for pg in pdf.pages)
    except Exception as exc:
        raise ValueError(f"Cannot open PDF '{fname}': {exc}") from exc

    detected = _detect_month_from_pdf_text(full_text)
    _assert_month_match(detected, report_month, "BSL BF Performance PDF")

    lines = full_text.splitlines()

    def _monthly(cell: str):
        """Parse 'X / Y' → float Y (monthly value). Returns None if no slash."""
        m = _re.search(r'[\d.*]+\s*/\s*([\d.]+)', cell.strip())
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
        return None

    def _is_repair(line: str) -> bool:
        lu = line.upper()
        return 'UNDER' in lu or 'CAPITAL REPAIR' in lu

    def _parse_row(line: str):
        """Split pipe-delimited line, strip cells, return list."""
        return [c.strip() for c in line.split('|')]

    def _is_fce_row(line: str) -> bool:
        if _is_repair(line):
            return False
        return bool(_re.match(r'\|?\s*(\d+\.?|Shop|SH|SHOP)\s*\|', line, _re.IGNORECASE))

    def _fce_id(cols):
        if len(cols) < 2:
            return None
        s = cols[1].strip()
        if s.upper() in ('SHOP', 'SH'):
            return 'BF Shop'
        m = _re.match(r'^(\d+)\.?$', s)
        if m:
            return f'BF-{int(m.group(1))}'
        return None

    # ── Identify table sections ───────────────────────────────────────────────
    TABLE_NONE = 0
    TABLE_PROD = 1   # Production Performance
    TABLE_FUEL = 2   # Fuel/Quality Parameters
    TABLE_RAW  = 3   # Raw Material Consumption

    prod_rows = {}   # fce_id → cols list
    fuel_rows = {}
    raw_rows  = {}
    current_table = TABLE_NONE

    for line in lines:
        lu = line.upper()
        # Section transitions detected from header keywords
        if 'PRODUCTIVT' in lu or ('W.V.' in lu and '24H' in lu):
            current_table = TABLE_PROD
            continue
        if 'COKE RATE' in lu and ('CDI RATE' in lu or 'N/C RT' in lu):
            current_table = TABLE_FUEL
            continue
        if ('O2 EN' in lu and 'SLG RATE' in lu) or ('NUTCOKE' in lu and 'CDI' in lu and 'PELLET' in lu):
            current_table = TABLE_RAW
            continue

        if not _is_fce_row(line):
            continue

        cols = _parse_row(line)
        fce = _fce_id(cols)
        if fce is None:
            continue

        if current_table == TABLE_PROD and fce not in prod_rows:
            prod_rows[fce] = cols
        elif current_table == TABLE_FUEL and fce not in fuel_rows:
            fuel_rows[fce] = cols
        elif current_table == TABLE_RAW and fce not in raw_rows:
            raw_rows[fce] = cols

    # ── Column indices (0-based after split by |) ────────────────────────────
    # Production table: [0]='' [1]=Fce [2]=Prod [3]=Theo [4]=DailyRate [5]=MonthlyRate
    #   [6]=Chrg [7]=Tuyr [8]=FlueDust [9]=TotOff [10]=OffBlast [11]=LowBlast [12]=LowBlast2
    #   [13]=HOT BLAST [14]=RecDaily [15]=RecMonthly [16]=Productivity W.V./24h
    # Fuel table: [0]='' [1]=FCE [2]=Si [3]=S [4]=SlagAl2O3 [5]=MgO [6]=Basicity
    #   [7]=HOT MET T [8]=COKE RATE [9]=N/C RT [10]=CDI RATE [11]=FUEL RATE ...
    # Raw material table: [0]='' [1]=Fce [2]=Coke [3]=IronOre [4]=Sinter [5]=Scrap
    #   [6]=NutCoke [7]=CDI [8]=Pellet [9]=CokeEcy [10]=O2 En(%) [11]=SLG RATE ...
    TABLE_DATA = {'prod': prod_rows, 'fuel': fuel_rows, 'raw': raw_rows}

    # ── Build techno_param_rows ───────────────────────────────────────────────
    rows_out = []
    sort_idx = 0

    # Add per-furnace CDI + monthly HM weight (for YTD weighted avg on page 29)
    for fce, label in [('BF-1', 'BSL BF-1'), ('BF-2', 'BSL BF-2'),
                        ('BF-4', 'BSL BF-4'), ('BF-5', 'BSL BF-5')]:
        fuel_cols = TABLE_DATA['fuel'].get(fce, [])
        cdi_val = _monthly(fuel_cols[10]) if len(fuel_cols) > 10 else None
        rows_out.append({
            'group_code': 'IRON_MAKING', 'section': 'CDI',
            'parameter': label, 'unit': 'Kg/THM',
            'actual': cdi_val, 'cum_actual': None,
            'sort_order': sort_idx * 10, 'cell': f'PDF fuel-table col-10 {fce}',
            'file_label': f'CDI Rate ({fce})', 'plant': 'BSL', 'month': report_month,
            'found_via': f'BSL {fce} CDI Rate', 'status': 'ok' if cdi_val is not None else 'skip',
        })
        prod_cols = TABLE_DATA['prod'].get(fce, [])
        hm_val = _monthly(prod_cols[2]) if len(prod_cols) > 2 else None
        rows_out.append({
            'group_code': 'IRON_MAKING', 'section': 'HM Production',
            'parameter': label, 'unit': 'T',
            'actual': hm_val, 'cum_actual': None,
            'sort_order': sort_idx * 10, 'cell': f'PDF prod-table col-2 {fce}',
            'file_label': f'HM Production ({fce})', 'plant': 'BSL', 'month': report_month,
            'found_via': f'BSL {fce} Monthly HM', 'status': 'ok' if hm_val is not None else 'skip',
        })
        sort_idx += 1
    shop_cdi_cols = TABLE_DATA['fuel'].get('BF Shop', [])
    shop_cdi_val = _monthly(shop_cdi_cols[10]) if len(shop_cdi_cols) > 10 else None
    rows_out.append({
        'group_code': 'IRON_MAKING', 'section': 'CDI',
        'parameter': 'BSL', 'unit': 'Kg/THM',
        'actual': shop_cdi_val, 'cum_actual': None,
        'source_priority': 4,   # Monthly Tech Excel (priority 5) can override this shop avg
        'sort_order': sort_idx * 10, 'cell': 'PDF fuel-table col-10 BF Shop',
        'file_label': 'CDI Rate (BF Shop)', 'plant': 'BSL', 'month': report_month,
        'found_via': 'BSL BF Shop CDI Rate', 'status': 'ok' if shop_cdi_val is not None else 'skip',
    })
    sort_idx += 1

    # ── Cross-plant section writes (section-as-section, furnace-as-row_label)
    # prod: [13]=Hot Blast Temp  [16]=BF Productivity
    # fuel: [2]=Si%  [3]=S%  [7]=Hot Metal Temp  [8]=Coke Rate  [9]=Nut Coke Rate  [11]=Fuel Rate
    # raw:  [3]=Iron Ore(T)  [4]=Sinter(T)  [5]=Scrap(T)  [8]=Pellet(T)
    #       [10]=O2 En(%)  [11]=Slag Rate  [12]=Sinter% in Burden  [13]=Pellet% in Burden
    _CROSS = [
        # (table, col, section, unit, sort_base)
        ('prod', 16, 'BF Productivity',    'T/m³/day', 76),
        ('prod', 13, 'HBT',                '°C',      106),
        ('fuel',  7, 'Hot Metal Temp',     '°C',       95),
        ('fuel',  8, 'BF Coke Rate',       'Kg/THM',   56),
        ('fuel',  9, 'Nut Coke Rate',      'Kg/THM',   66),
        ('fuel', 11, 'Fuel Rate',          'Kg/THM',  110),
        ('fuel',  2, 'Si in HM',           '%',        86),
        ('fuel',  3, 'S in HM',            '%',        93),
        ('raw',   3, 'Iron Ore',           'T',        25),
        ('raw',   4, 'Sinter Consumption', 'T',        35),
        ('raw',   5, 'BF Scrap',           'T',        45),
        ('raw',   8, 'Pellet Consumption', 'T',        55),
        ('raw',  10, 'O2 Enrichment',      '%',       140),
        ('raw',  11, 'Slag Rate',          'Kg/THM',  138),
        ('raw',  12, 'Sinter in Burden',   '%',       120),
        ('raw',  13, 'Pellet in Burden',   '%',       130),
    ]
    # All rows (per-furnace and BF Shop) stored at priority 5 — PDF is the authoritative source.
    # compute_bf_shop_averages() at priority 4 will not overwrite these.
    for fce, label in [('BF-1', 'BSL BF-1'), ('BF-2', 'BSL BF-2'),
                        ('BF-4', 'BSL BF-4'), ('BF-5', 'BSL BF-5'),
                        ('BF Shop', 'BSL')]:
        cols_f = TABLE_DATA['fuel'].get(fce, [])
        cols_p = TABLE_DATA['prod'].get(fce, [])
        cols_r = TABLE_DATA['raw'].get(fce, [])
        for tbl, ci, section, unit, so_base in _CROSS:
            cols = cols_f if tbl == 'fuel' else (cols_p if tbl == 'prod' else cols_r)
            val = _monthly(cols[ci]) if ci < len(cols) else None
            rows_out.append({
                'group_code': 'IRON_MAKING', 'section': section,
                'parameter': label, 'unit': unit,
                'actual': val, 'cum_actual': None,
                'sort_order': so_base + sort_idx,
                'source_priority': 5,
                'cell': f'PDF {tbl}-table col-{ci} {fce}',
                'file_label': f'{section} ({fce})', 'plant': 'BSL', 'month': report_month,
                'found_via': f'BSL {fce} {section}',
                'status': 'ok' if val is not None else 'skip',
            })
        sort_idx += 1

    ok = sum(1 for r in rows_out if r['status'] == 'ok')
    logger.info("BSL BF PDF: %d/%d rows ok for %s", ok, len(rows_out), report_month)

    if ok == 0:
        raise ValueError(
            "No BF performance values extracted. "
            "Verify this is a BSL BF Performance & Analysis Report PDF with "
            "'Productivty'/'W.V./24h', 'COKE RATE'/'CDI RATE', and 'O2 En(%)'/'SLG RATE' tables."
        )

    return {
        'source_type':        'BSL BF Performance & Analysis Report (PDF)',
        'month':              report_month,
        'detected_month':     detected,
        'plant':              'BSL',
        'workbook_sheets':    ['PDF'],
        'production_rows':    [],
        'techno_rows':        [],
        'techno_param_rows':  rows_out,
        'special_steel_rows': [],
    }


def _extract_delhi_report_stock(wb, db_month: str) -> list:
    """Extract next-month opening stock from 'Delhi Report' sheet.

    Column M = closing stock as on last day of db_month = opening of next month.
    Cell mapping (Tonnes → stored as '000T, 3 d.p.):
      M67 → SLABS INPROCESS
      M66 → FINISHED STEEL
      M69 → PIG IRON
    """
    dr_name = next((s for s in wb.sheetnames if s.strip().lower() == "delhi report"), None)
    if dr_name is None:
        return []

    ws = wb[dr_name]
    y, m = int(db_month[:4]), int(db_month[5:7])
    next_month = f"{y+1 if m == 12 else y}-{1 if m == 12 else m+1:02d}"

    def _t(addr):
        v = clean_val(ws[addr].value)
        return round(v / 1000, 3) if v is not None else None

    def _row(item_type, stock_type, value, formula):
        return {
            "plant": "BSL", "item_type": item_type, "stock_type": stock_type,
            "stock_month": next_month, "value": value, "formula": formula,
            "status": "ok" if value is not None else "skip",
        }

    return [
        _row("SLABS",         "INPROCESS", _t("M67"), "Delhi Report!M67"),
        _row("FINISHED STEEL", "",          _t("M66"), "Delhi Report!M66"),
        _row("PIG IRON",      "",          _t("M69"), "Delhi Report!M69"),
    ]


def _extract_dpr_preview(wb, report_month: str) -> dict:
    """Preview BSL DPR Mail report (sheet 'DPR') — no DB writes."""
    ws = wb["DPR"]

    # Auto-detect month from O1 (Excel datetime or DD.MM.YYYY string)
    o1_raw = ws["O1"].value
    db_month = None
    if isinstance(o1_raw, datetime):
        db_month = f"{o1_raw.year}-{str(o1_raw.month).zfill(2)}"
    elif o1_raw:
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", str(o1_raw))
        if m:
            db_month = f"{m.group(3)}-{m.group(2)}"
    db_month = db_month or report_month
    if not db_month:
        raise ValueError("Cannot determine report month: cell O1 is empty and no month supplied.")

    if db_month != report_month and report_month and len(report_month) >= 7:
        raise ValueError(
            f"Month mismatch: the DPR file's date cell (O1) shows "
            f"{_fmt_month(db_month)}, but you selected {_fmt_month(report_month)}. "
            f"Please select '{_fmt_month(db_month)}' in the month picker, "
            f"or upload the DPR file for {_fmt_month(report_month)}."
        )

    logger.info("BSL DPR preview: month from O1 → %s", db_month)

    NO_CONVERT = {"Oven Pushing (nos/day)"}
    CELL_MAP = {
        "Oven Pushing (nos/day)": "P6",
        "Total Sinter":        "P7",
        "Hot Metal":           "P8",
        "Pig Iron":            "E30",
        "SMS-1 CCM-1":         "P10",
        "SMS-2 CCM-1&2":       "P11",
        "Total Crude Steel":   "P12",
        "HSM Total HR Coil":   "P14",
        "HSM HR Coil (Sale)":  "E7",
        "HSM HR Plate":        "E8",
        "HR Sheet":            "E9",
        "CRC&S(1&2)":          "E10",
        "CRC(3)":              "E11",
        "GP/GC":               "E12",
        "GPC3":                "E13",
        "CRSALE":              "E29",
        "Saleable Steel":      "P31",
        "Saleable Semis":      "E32",
    }

    rows = []
    for item_name, addr in CELL_MAP.items():
        raw = clean_val(ws[addr].value)
        if raw is not None:
            if item_name in NO_CONVERT:
                stored, unit = raw, "nos/d"
            else:
                stored, unit = round(raw / 1000.0, 3), "'000T"
            rows.append({"item_name": item_name, "value": stored, "unit": unit,
                         "cell": f"DPR!{addr}", "pdf_label": addr, "status": "ok"})
        else:
            unit = "nos/d" if item_name in NO_CONVERT else "'000T"
            rows.append({"item_name": item_name, "value": None, "unit": unit,
                         "cell": f"DPR!{addr}", "pdf_label": addr, "status": "skip"})

    # Derived: Finished Steel = Saleable Steel (P31) − Saleable Semis (E32)
    sal = clean_val(ws["P31"].value)
    sem = clean_val(ws["E32"].value)
    if sal is not None and sem is not None:
        rows.append({"item_name": "Finished Steel",
                     "value": round((sal - sem) / 1000.0, 3), "unit": "'000T",
                     "cell": "DPR!P31-E32 (computed)", "pdf_label": "P31-E32", "status": "ok"})
    elif sal is not None:
        rows.append({"item_name": "Finished Steel",
                     "value": round(sal / 1000.0, 3), "unit": "'000T",
                     "cell": "DPR!P31 (semis missing)", "pdf_label": "P31", "status": "ok"})

    ok = sum(1 for r in rows if r["status"] == "ok")
    logger.info("BSL DPR preview: %d/%d ok for %s", ok, len(rows), db_month)

    if ok == 0:
        raise ValueError(
            "No values found at expected cell locations in DPR sheet. "
            "Verify this is a BSL DPR Mail file (sheet 'DPR', date in O1)."
        )

    stock_rows = _extract_delhi_report_stock(wb, db_month)
    stock_ok = sum(1 for r in stock_rows if r["status"] == "ok")
    logger.info("BSL DPR stock (Delhi Report): %d/%d ok for next_month of %s",
                stock_ok, len(stock_rows), db_month)

    return {
        "source_type":        "BSL DPR Mail (Month-End)",
        "month":              db_month,
        "plant":              "BSL",
        "workbook_sheets":    list(wb.sheetnames),
        "production_rows":    rows,
        "techno_rows":        [],
        "techno_param_rows":  [],
        "special_steel_rows": [],
        "stock_rows":         stock_rows,
    }


def extract_preview(file_path: str, report_month: str) -> dict:
    """
    Extract BSL data — auto-detects file type:

    • BF Performance & Analysis Report (.pdf)
      → techno_param_rows populated with BF-wise Productivity, Coke Rate, etc.

    • DPR Mail Month-End Report (.xlsx, sheet 'DPR')
      → production_rows populated with ~19 production items.

    • Corporate Office Special Steel Report (.xlsx, Sheet1 with "SPECIAL STEEL" title)
      → special_steel_rows populated; monthly actual = Despatch Till Date − Actual Up To Last Month.

    • Techno-Economic Parameters (TECHNO <MON><YYYY>.XLS / .XLSX)
      → techno_param_rows populated from Sheet1/Sheet2/SMS-I/SMS-II.

    Returns a preview dict compatible with /api/confirm-extraction.
    """
    if file_path.lower().endswith('.pdf'):
        return extract_preview_bf_pdf(file_path, report_month)

    wb = _open_wb(file_path)

    # ── Route 1: DPR Mail Month-End Report ───────────────────────────────
    if "DPR" in wb.sheetnames:
        return _extract_dpr_preview(wb, report_month)

    # ── Route 2: Corporate Office Special Steel Report ────────────────────
    if _is_corp_ss_file(wb):
        return _extract_corp_ss_preview(wb, report_month)

    # ── Determine report month ────────────────────────────────────────────
    detected_month = _detect_month_from_sheet1(wb) or _detect_month_from_filename(file_path)
    db_month = report_month
    if not db_month or len(db_month) < 7:
        db_month = detected_month or ""
    if not db_month:
        raise ValueError(
            "Cannot determine report month. Set the month in the selector or "
            "name the file as TECHNO <MONTH><YYYY>.XLS (e.g. TECHNO APRIL2026.XLS)."
        )
    _assert_month_match(detected_month, db_month, "BSL Techno Excel")

    # ── Check which sheets are present ───────────────────────────────────
    sheets_present = list(wb.sheetnames)

    rows_out = []
    for sort_idx, (sheet_name, row, mon_col, mult,
                   group, section, param, unit) in enumerate(_TECHNO_PARAM_MAP):

        cum_col = mon_col + 1  # till the month is always the next column

        try:
            ws = wb[sheet_name]
        except (KeyError, Exception):
            logger.warning("BSL techno: sheet %r not found — skipping %s", sheet_name, param)
            continue

        actual_raw  = _cell_float(ws, row, mon_col)
        cum_raw     = _cell_float(ws, row, cum_col)

        actual  = round(actual_raw * mult, 4) if actual_raw is not None else None
        cum     = round(cum_raw   * mult, 4) if cum_raw    is not None else None

        mon_ltr = get_column_letter(mon_col)
        cum_ltr = get_column_letter(cum_col)
        cell_ref = f"{mon_ltr}{row}/{cum_ltr}{row}"
        if mult != 1.0:
            cell_ref += f" ×{int(mult)}"

        # Row label from column A of the same sheet for display
        try:
            file_label = str(ws.cell(row, 1).value or "").strip()
        except Exception:
            file_label = ""

        status = "ok" if (actual is not None or cum is not None) else "skip"
        rows_out.append({
            "group_code": group,
            "section":    section,
            "parameter":  param,
            "unit":       unit,
            "actual":     actual,
            "cum_actual": cum,
            "sort_order": sort_idx * 10,
            "cell":       cell_ref,
            "file_label": file_label,
            "plant":      "BSL",
            "month":      db_month,
            "found_via":  f"hardcoded {sheet_name} R{row}C{mon_col}",
            "status":     status,
        })

    ok = sum(1 for r in rows_out if r["status"] == "ok")
    logger.info("BSL techno preview: %d/%d rows ok for %s", ok, len(rows_out), db_month)

    if ok == 0:
        raise ValueError(
            "No numeric values found at any of the expected cell locations. "
            "Verify this is a BSL TECHNO <MON><YYYY>.XLS file with Sheet1, Sheet2, and SMS-I present."
        )

    return {
        "source_type":       "BSL Techno-Economic Parameters",
        "month":             db_month,
        "detected_month":    detected_month,
        "plant":             "BSL",
        "workbook_sheets":   sheets_present,
        "production_rows":   [],
        "techno_rows":       [],
        "techno_param_rows": rows_out,
        "special_steel_rows": [],
    }


