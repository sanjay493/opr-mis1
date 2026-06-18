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
            "Expected sheet 'DPR' (DPR Mail month-end report)."
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
      Oven Pushing(nos/d)  P6    — nos/day average, no unit conversion
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

    NO_CONVERT = {"Oven Pushing(nos/d)"}

    # Simple cells: item_name → cell address
    production_cells = {
        "Oven Pushing(nos/d)": "P6",
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

    # Extract all mapped cells
    for item_name, cell in production_cells.items():
        _save(item_name, clean_val(ws[cell].value))

    # Derived: Finished Steel = Saleable Steel (P31) − Saleable Semis (E32)
    sal_steel = clean_val(ws["P31"].value)
    sal_semis  = clean_val(ws["E32"].value)
    if sal_steel is not None and sal_semis is not None:
        finished = round((sal_steel - sal_semis) / 1000.0, 3)
        cursor.execute("""
            INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, item_name)
            DO UPDATE SET month_actual = excluded.month_actual
        """, (db_report_month, "BSL", "Finished Steel", finished))
        vals_extracted += 1
    elif sal_steel is not None:
        _save("Finished Steel", sal_steel)   # best-effort if semis missing

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
    ("Sheet1", 33,  6,    1.0, "IRON_MAKING", "BF Productivity (BSL)", "BF Productivity",                   "T/m³/day"),
    ("Sheet1", 35,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Coke Rate",                         "Kg/THM"),
    ("Sheet1", 37,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "CDI Rate",                          "Kg/THM"),
    ("Sheet1", 39,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Fuel Rate",                         "Kg/THM"),
    ("Sheet1", 41,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Coal to Hot Metal",                 "Kg/THM"),
    ("Sheet1", 49,  6,    1.0, "MILL_BSL",    "CRM 1&2",               "Yield of HR Coil",                  "%"),
    ("Sheet1", 51,  6,    1.0, "MILL_BSL",    "CRM 3",                 "Yield of HR Coil",                  "%"),
    ("Sheet1", 55,  6,    1.0, "BOF",         "Refractory",            "Refractory Consumption",            "Kg/TCS"),
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
    ("Sheet4", 31,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Sinter in Burden",                  "%"),
    ("Sheet4", 33,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Oxygen Enrichment",                  "%"),
    ("Sheet4", 35,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "BF Coke Screen Loss (-25mm)",        "%"),
    ("Sheet4", 37,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Slag Rate",                          "Kg/THM"),
    ("Sheet4", 38,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "BF Gas Yield",                       "Nm³/THM"),
    ("Sheet4", 39,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "CV of BF Gas",                       "Kcal/Nm³"),
    ("Sheet4", 40,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Furnace Availability",               "%"),
    ("Sheet4", 41,  6,    1.0, "IRON_MAKING", "Blast Furnaces",        "Furnace Utilization",                "%"),
    # ── SMS-I ──────────────────────────────────────────────────────────────
    ("SMS-I",   12,  6,    1.0, "BOF",         "SMS-I",                 "Tap to Tap Time (Avail. Hrs)",      "Min"),
    ("SMS-I",   14,  6,    1.0, "BOF",         "SMS-I",                 "Tap to Tap Time (Working Hrs)",     "Min"),
    ("SMS-I",  16,  6,    1.0, "BOF",         "SMS-I",                 "Average Lining Life",               "Heats"),
    ("SMS-I",  18,  6,    1.0, "BOF",         "SMS-I",                 "Converter Availability (Cal. Hr)",  "%"),
    ("SMS-I",  20,  6,    1.0, "BOF",         "SMS-I",                 "Converter Availability (Avail. Hr)","%"),
    ("SMS-I",  23,  6,    1.0, "BOF",         "SMS-I",                 "Sp. Hot Metal Cons.",               "Kg/T CS"),
    ("SMS-I",  25,  6,    1.0, "BOF",         "SMS-I",                 "Sp. Scrap Cons.",                   "Kg/T CS"),
    ("SMS-I",  27,  6,    1.0, "BOF",         "SMS-I",                 "Sp. Iron Ore Cons.",                "Kg/T CS"),
    ("SMS-I",  26,  6,    1.0, "BOF",         "SMS-I",                 "Sp. Pellet Cons.",                  "Kg/T CS"),
    ("SMS-I",  28,  6,    1.0, "BOF",         "SMS-I",                 "Fe-Si Cons.",                       "Kg/T CS"),
    ("SMS-I",  29,  6,    1.0, "BOF",         "SMS-I",                 "Fe-Mn Cons.",                       "Kg/T CS"),
    ("SMS-I",  30,  6,    1.0, "BOF",         "SMS-I",                 "Si-Mn Cons.",                       "Kg/T CS"),
    ("SMS-I",  34,  6,    1.0, "BOF",         "SMS-I",                 "Oxygen Blow per T Crude",           "Nm³/T CS"),
    ("SMS-I",  33,  6,    1.0, "BOF",         "SMS-I",                 "Refractory Cons.",                  "Kg/T CS"),
    ("SMS-I",  40,  6,    1.0, "BOF",         "SMS-I",                 "Heat Consumed",                     "Kcal/T CS"),
    ("SMS-I",  42,  6,    1.0, "BOF",         "SMS-I",                 "Power Consumed",                    "KWH/T CS"),
    ("SMS-I",  48,  6,    1.0, "BOF",         "SMS-I",                 "Reblown Heat",                      "%"),
    ("SMS-I",  50,  6,    1.0, "BOF",         "SMS-I",                 "FeO in Slag",                       "%"),
    # ── SMS-II ─────────────────────────────────────────────────────────────
    ("SMS-II",  12,  6,    1.0, "BOF",         "SMS-II",                "Tap to Tap Time (Avail. Hrs)",      "Min"),
    ("SMS-II",  14,  6,    1.0, "BOF",         "SMS-II",                "Tap to Tap Time (Working Hrs)",     "Min"),
    ("SMS-II", 16,  6,    1.0, "BOF",         "SMS-II",                "Average Lining Life",               "Heats"),
    ("SMS-II", 18,  6,    1.0, "BOF",         "SMS-II",                "Converter Availability (Cal. Hr)",  "%"),
    ("SMS-II", 20,  6,    1.0, "BOF",         "SMS-II",                "Converter Availability (Avail. Hr)","%"),
    ("SMS-II", 23,  6,    1.0, "BOF",         "SMS-II",                "Sp. Hot Metal Cons.",               "Kg/T CS"),
    ("SMS-II", 25,  6,    1.0, "BOF",         "SMS-II",                "Sp. Scrap Cons.",                   "Kg/T CS"),
    ("SMS-II", 27,  6,    1.0, "BOF",         "SMS-II",                "Sp. Iron Ore Cons.",                "Kg/T CS"),
    ("SMS-II", 26,  6,    1.0, "BOF",         "SMS-II",                "Sp. Pellet Cons.",                  "Kg/T CS"),
    ("SMS-II", 28,  6,    1.0, "BOF",         "SMS-II",                "Fe-Si Cons.",                       "Kg/T CS"),
    ("SMS-II", 29,  6,    1.0, "BOF",         "SMS-II",                "Fe-Mn Cons.",                       "Kg/T CS"),
    ("SMS-II", 30,  6,    1.0, "BOF",         "SMS-II",                "Si-Mn Cons.",                       "Kg/T CS"),
    ("SMS-II", 36,  6,    1.0, "BOF",         "SMS-II",                "Oxygen Blow per T Crude",           "Nm³/T CS"),
    ("SMS-II", 35,  6,    1.0, "BOF",         "SMS-II",                "Refractory Cons.",                  "Kg/T CS"),
    ("SMS-II", 42,  6,    1.0, "BOF",         "SMS-II",                "Heat Consumed",                     "Kcal/T CS"),
    ("SMS-II", 44,  6,    1.0, "BOF",         "SMS-II",                "Power Consumed",                    "KWH/T CS"),
    ("SMS-II", 50,  6,    1.0, "BOF",         "SMS-II",                "Reblown Heat",                      "%"),
    ("SMS-II", 52,  6,    1.0, "BOF",         "SMS-II",                "FeO in Slag",                       "%"),
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


def extract_preview(file_path: str, report_month: str) -> dict:
    """
    Extract BSL Techno-Economic Parameters from TECHNO <MON><YYYY>.XLS.

    Supported sheets:
      Sheet1 — COKE AND COAL CHEMICALS, SINTER PLANT + Iron Making + Mills
      Sheet2 — Coke Oven parameters

    Returns a preview dict compatible with /api/confirm-extraction.
    Month is taken from `report_month` ('YYYY-MM'); if empty, falls back to
    the filename.
    """
    wb = _open_wb(file_path)

    # ── Determine report month ────────────────────────────────────────────
    db_month = report_month
    if not db_month or len(db_month) < 7:
        db_month = _detect_month_from_filename(file_path) or ""
    if not db_month:
        raise ValueError(
            "Cannot determine report month. Set the month in the selector or "
            "name the file as TECHNO <MONTH><YYYY>.XLS (e.g. TECHNO APRIL2026.XLS)."
        )

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
        "plant":             "BSL",
        "workbook_sheets":   sheets_present,
        "production_rows":   [],
        "techno_rows":       [],
        "techno_param_rows": rows_out,
        "special_steel_rows": [],
    }

