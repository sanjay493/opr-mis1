"""BSP (Bhilai Steel Plant) Excel extractor — unified module.

Handles four distinct BSP file types, auto-detected:

  1. BSP PPC MIS daily report (.xls, sheet "S1")
       → extract_and_save_excel() — direct DB write, no preview
  2. BSP 3-page Techno parameters (.xlsx, sheet "Sheet1", month in R3C1)
       → _extract_techno_3page_preview()
  3. BSP OISCO Techno parameters (.xlsx, R3C3 contains "TECHNO ECONOMIC PARAMETERS")
       → _extract_oisco_preview()
  4. BSP Special Steel report (.xlsx, sheet "CORP", R3C1 = "BHILAI STEEL PLANT")
       → _extract_bsp_ss_preview()

Public API:
  extract_and_save_excel(file_path, report_month, source_file_name)
  extract_preview(file_path, report_month)  ← unified, auto-detects type (2/3/4)
"""

import logging
import os
import re
import sqlite3
from typing import Optional, List, Dict, Any

import openpyxl
from openpyxl.utils import get_column_letter

try:
    import xlrd
    _XLRD_AVAILABLE = True
except ImportError:
    _XLRD_AVAILABLE = False

logger = logging.getLogger("excel_extractor")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "mis_reports.db")


# ---------------------------------------------------------------------------
# Excel 97-2003 (.xls) compatibility shim
# Makes an xlrd workbook/sheet look like openpyxl (1-based cell access).
# ---------------------------------------------------------------------------

class _XlsCell:
    __slots__ = ("value",)
    def __init__(self, value):
        self.value = None if value == "" else value


class _XlsSheet:
    def __init__(self, sheet):
        self._s = sheet
        self.max_column = sheet.ncols
        self.max_row = sheet.nrows

    def cell(self, row: int, col: int) -> _XlsCell:
        r, c = row - 1, col - 1
        if r < 0 or r >= self._s.nrows or c < 0 or c >= self._s.ncols:
            return _XlsCell(None)
        return _XlsCell(self._s.cell_value(r, c))

    @property
    def title(self):
        return self._s.name


class _XlsWorkbook:
    def __init__(self, wb):
        self._wb = wb
        self.worksheets = [_XlsSheet(wb.sheets()[i]) for i in range(wb.nsheets)]

    @property
    def sheetnames(self):
        return self._wb.sheet_names()

    def __getitem__(self, name: str) -> _XlsSheet:
        return _XlsSheet(self._wb.sheet_by_name(name))

    @property
    def active(self) -> _XlsSheet:
        return _XlsSheet(self._wb.sheets()[0])


def _open_workbook(file_path: str):
    """Open .xlsx (openpyxl) or .xls (xlrd) and return a unified interface."""
    if file_path.lower().endswith(".xls"):
        if not _XLRD_AVAILABLE:
            raise ImportError("xlrd is required for .xls files: pip install xlrd")
        return _XlsWorkbook(xlrd.open_workbook(file_path))
    return openpyxl.load_workbook(file_path, data_only=True)


# ---------------------------------------------------------------------------
# Shared month constants
# ---------------------------------------------------------------------------

_MONTH_NAME_TO_NUM: Dict[str, str] = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
    "JANUARY": "01", "FEBRUARY": "02", "MARCH": "03", "APRIL": "04",
    "JUNE": "06", "JULY": "07", "AUGUST": "08",
    "SEPTEMBER": "09", "OCTOBER": "10", "NOVEMBER": "11", "DECEMBER": "12",
}

_MONTH_NUM_TO_HDR: Dict[str, str] = {
    "04": "APR", "05": "MAY", "06": "JUN", "07": "JUL",
    "08": "AUG", "09": "SEP", "10": "OCT", "11": "NOV",
    "12": "DEC", "01": "JAN", "02": "FEB", "03": "MAR",
}

# report month-number (MM) → 1-based Excel column index (for 3-page-Tech)
_MONTH_NUM_TO_COL: Dict[str, int] = {
    "04": 4, "05": 5, "06": 6, "07": 7, "08": 8, "09": 9,
    "10": 10, "11": 11, "12": 12, "01": 13, "02": 14, "03": 15,
}

_MONTH_FULL: Dict[str, str] = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


# ---------------------------------------------------------------------------
# Shared clean helpers
# ---------------------------------------------------------------------------

def _clean(v) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "—", "nan", "###", "#DIV/0!", "#VALUE!", "#N/A", "#REF!"):
        return None
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Section 1 — BSP PPC MIS daily report (.xls, sheet "S1")
# ---------------------------------------------------------------------------

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


def extract_and_save_excel(file_path: str, report_month: str = None,
                           source_file_name: str = "") -> bool:
    """Extract BSP production actuals from the daily PPC MIS .xls report (sheet S1).

    Month auto-detected from N1 (date serial). report_month used only as fallback.
    Units: raw Tonnes → stored as '000 T (divide by 1000). Coke items as-is (nos/day).
    """
    try:
        wb = xlrd.open_workbook(file_path)
        if "S1" not in wb.sheet_names():
            raise ValueError(
                "Uploaded BSP file is missing required sheet 'S1'. "
                "Please upload the correct BSP PPC MIS daily report."
            )

        ws = wb.sheet_by_name("S1")

        # Auto-detect report month from N1 (col 13, row 0)
        n1_raw = ws.cell_value(0, 13)
        if n1_raw and isinstance(n1_raw, float) and n1_raw > 0:
            y, m, *_ = xlrd.xldate_as_tuple(n1_raw, wb.datemode)
            db_report_month = f"{y}-{m:02d}"
            logger.info(f"BSP PPC MIS: month auto-detected from N1 → {db_report_month}")
        elif report_month:
            db_report_month = report_month
        else:
            raise ValueError(
                "Cannot determine report month: N1 is not a valid date and "
                "no report_month was provided."
            )

        COL_F, COL_J, COL_N = 5, 9, 13

        # (row_0based, col_0based, divide_by_1000)
        production_cells = {
            "COB#1-8":              (3,  COL_F, False),
            "Oven Pushing(nos/d)":  (5,  COL_F, False),
            "SP-2":                 (7,  COL_F, True),
            "SP-3":                 (8,  COL_F, True),
            "Total Sinter":         (9,  COL_F, True),
            "BF#1-7":               (10, COL_F, True),
            "BF#8":                 (11, COL_F, True),
            "Hot Metal":            (12, COL_F, True),
            "SMS-2":                (13, COL_F, True),
            "SMS-3":                (15, COL_F, True),
            "Total Crude Steel":    (16, COL_F, True),
            "RSM_RAIL":             (17, COL_F, True),
            "URM_RAIL":             (21, COL_F, True),
            "MM":                   (23, COL_F, True),
            "WIRERODS":             (24, COL_F, True),
            "BARS&RODMILL":         (25, COL_F, True),
            "PLATEMILL":            (26, COL_F, True),
            "Finished Steel":       (27, COL_F, True),
            "Saleable Semis":       (34, COL_F, True),
            "Saleable Steel":       (35, COL_F, True),
            "RSMPRIME":             (38, COL_F, True),
            "URMPRIME":             (38, COL_J, True),
            "Pig Iron":             (62, COL_N, True),
        }

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        vals_extracted = 0

        for item_name, (row_idx, col_idx, do_convert) in production_cells.items():
            raw = ws.cell_value(row_idx, col_idx)
            val = _clean(raw)
            if val is not None:
                if do_convert:
                    val = round(val / 1000.0, 3)
                vals_extracted += 1

            cursor.execute("""
                INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, plant_name, item_name)
                DO UPDATE SET month_actual = excluded.month_actual
            """, (db_report_month, "BSP", item_name, val))

        if vals_extracted == 0:
            raise ValueError(
                "No numeric data found at expected cell locations in sheet S1. "
                "Please verify this is the correct BSP PPC MIS file."
            )

        conn.commit()
        conn.close()

        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        import db as _db
        _db.log_extraction(
            plant="BSP", report_month=db_report_month,
            file_name=source_file_name, sheet_name="S1",
            source_type="Daily PPC MIS Report",
            items_extracted=vals_extracted,
        )
        logger.info(f"BSP PPC MIS extraction done: {vals_extracted} values for {db_report_month}.")
        return True

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"BSP PPC MIS extraction error: {e}")
        return False


# ---------------------------------------------------------------------------
# Section 2 — BSP 3-page Techno parameters (.xlsx, sheet "Sheet1")
#
# Sheet layout:
#   Row  3, Col A : Report month name, e.g. "MAY"
#   Row  4, Cols D-O : Column month headers APR … MAR
#   Row  4, Col P : "ACTUAL" / cumulative header
#   Col  B (2)    : Unit
#   Col  D–O      : Monthly data (APR–MAR)
#   Col  P (16)   : Cumulative "till month" value — ALWAYS
# ---------------------------------------------------------------------------

_TECHNO_3PAGE_CUM_FALLBACK = 16
_TECHNO_3PAGE_CUM_HEADERS = {
    "ACTUAL", "CUM", "CUMULATIVE", "CUM.", "TILL DATE", "TILL MONTH", "APR-ACTUAL",
}

PARAM_MAP_3PAGE: List[tuple] = [
    # (row_1based, group_code, section, parameter_label, unit)
    # ── Coke & By-products (rows 37-40) ─────────────────────────────────────
    (37, "COKE_SINTER", "Coke Yield",           "BF Coke",                   "%"),
    (38, "COKE_SINTER", "Coke Yield",           "Crude Tar",                 "%"),
    (39, "COKE_SINTER", "Coke Yield",           "Ammonium Sulphate",         "%"),
    (40, "COKE_SINTER", "Coke Yield",           "Crude Benzol",              "%"),
    # ── Sinter Plant 2 (rows 45-49) ─────────────────────────────────────────
    (45, "COKE_SINTER", "Sinter Plant SP-2",    "Machine Availability",      "%"),
    (46, "COKE_SINTER", "Sinter Plant SP-2",    "Machine Utilisation",       "%"),
    (48, "COKE_SINTER", "Sinter Plant SP-2",    "Productivity",              "T/m2/hr"),
    (49, "COKE_SINTER", "Sinter Plant SP-2",    "Basicity",                  ""),
    # ── Sinter Plant 3 (rows 51-55) ─────────────────────────────────────────
    (51, "COKE_SINTER", "Sinter Plant SP-3",    "Machine Availability",      "%"),
    (52, "COKE_SINTER", "Sinter Plant SP-3",    "Machine Utilisation",       "%"),
    (54, "COKE_SINTER", "Sinter Plant SP-3",    "Productivity",              "T/m2/hr"),
    (55, "COKE_SINTER", "Sinter Plant SP-3",    "Basicity",                  ""),
    # ── Blast Furnaces (rows 58-70) ─────────────────────────────────────────
    (58, "IRON_MAKING", "Blast Furnaces",        "Sinter in Burden (BF 1-8)","%" ),
    (59, "IRON_MAKING", "Blast Furnaces",        "Coke Rate (BF 1-8)",       "Kg./THM"),
    (60, "IRON_MAKING", "Blast Furnaces",        "Coke Screening (BF 1-8)",  "25mm%"),
    (68, "IRON_MAKING", "Blast Furnaces",        "CDI Rate",                 "Kg./THM"),
    (69, "IRON_MAKING", "Blast Furnaces",        "Slag Rate (1-8)",          "Kg./THM"),
    (70, "IRON_MAKING", "Blast Furnaces",        "Sp. Nut Coke Consumption", "Kg./THM"),
    # ── BF Productivity (rows 65-67) ────────────────────────────────────────
    (65, "IRON_MAKING", "BF Productivity (BSP)", "BF-7 (2104 Cu.M)",         "T/m3/day"),
    (66, "IRON_MAKING", "BF Productivity (BSP)", "BF-8 (3445 Cu.M)",         "T/m3/day"),
    (67, "IRON_MAKING", "BF Productivity (BSP)", "Overall (BF 1-8)",         "T/m3/day"),
    # ── SMS-II Consumption (rows 76-78) ─────────────────────────────────────
    (76, "BOF", "SMS-II Consumption",            "Hot Metal",                "Kg/T CS"),
    (77, "BOF", "SMS-II Consumption",            "Scrap",                    "Kg/T CS"),
    (78, "BOF", "SMS-II Consumption",            "Total Metallic Charge",    "Kg/T CS"),
    # ── SMS-III Consumption (rows 90-92) ────────────────────────────────────
    (90, "BOF", "SMS-III Consumption",           "Hot Metal",                "Kg/T CS"),
    (91, "BOF", "SMS-III Consumption",           "Scrap",                    "Kg/T CS"),
    (92, "BOF", "SMS-III Consumption",           "Total Metallic Charge",    "Kg/T CS"),
    # ── Rail & Structural Mill — RSM ─────────────────────────────────────────
    ( 97, "MILL_BSP", "Rail & Structural Mill",  "Yield",                    "%"),
    ( 98, "MILL_BSP", "Rail & Structural Mill",  "Rolling Rate",             "T/Hr."),
    ( 99, "MILL_BSP", "Rail & Structural Mill",  "Mill Availability",        "%"),
    (100, "MILL_BSP", "Rail & Structural Mill",  "Mill Utilisation",         "%"),
    (137, "MILL_BSP", "Rail & Structural Mill",  "Heat Consumption",         "103Kcal/T"),
    (153, "MILL_BSP", "Rail & Structural Mill",  "Power Consumption",        "Kwh/T"),
    # ── Universal Rail Mill — URM ─────────────────────────────────────────────
    (103, "MILL_BSP", "Universal Rail Mill",     "Yield",                    "%"),
    (104, "MILL_BSP", "Universal Rail Mill",     "Rolling Rate",             "T/Hr."),
    (105, "MILL_BSP", "Universal Rail Mill",     "Mill Availability",        "%"),
    (106, "MILL_BSP", "Universal Rail Mill",     "Mill Utilisation",         "%"),
    (138, "MILL_BSP", "Universal Rail Mill",     "Heat Consumption",         "103Kcal/T"),
    (154, "MILL_BSP", "Universal Rail Mill",     "Power Consumption",        "Kwh/T"),
    # ── Merchant Mill — MM ───────────────────────────────────────────────────
    (109, "MILL_BSP", "Merchant Mill",           "Yield",                    "%"),
    (110, "MILL_BSP", "Merchant Mill",           "Rolling Rate",             "T/Hr."),
    (111, "MILL_BSP", "Merchant Mill",           "Mill Availability",        "%"),
    (112, "MILL_BSP", "Merchant Mill",           "Mill Utilisation",         "%"),
    (139, "MILL_BSP", "Merchant Mill",           "Heat Consumption",         "103Kcal/T"),
    (155, "MILL_BSP", "Merchant Mill",           "Power Consumption",        "Kwh/T"),
    # ── Wire Rod Mill — WRM ──────────────────────────────────────────────────
    (115, "MILL_BSP", "Wire Rod Mill",           "Yield",                    "%"),
    (116, "MILL_BSP", "Wire Rod Mill",           "Rolling Rate",             "T/Hr."),
    (117, "MILL_BSP", "Wire Rod Mill",           "Mill Availability",        "%"),
    (118, "MILL_BSP", "Wire Rod Mill",           "Mill Utilisation",         "%"),
    (140, "MILL_BSP", "Wire Rod Mill",           "Heat Consumption",         "103Kcal/T"),
    (156, "MILL_BSP", "Wire Rod Mill",           "Power Consumption",        "Kwh/T"),
    # ── Bar & Rod Mill — BRM ─────────────────────────────────────────────────
    (121, "MILL_BSP", "Bar & Rod Mill",          "Yield",                    "%"),
    (122, "MILL_BSP", "Bar & Rod Mill",          "Rolling Rate",             "T/Hr."),
    (123, "MILL_BSP", "Bar & Rod Mill",          "Mill Availability",        "%"),
    (124, "MILL_BSP", "Bar & Rod Mill",          "Mill Utilisation",         "%"),
    # ── Plate Mill ───────────────────────────────────────────────────────────
    (127, "MILL_BSP", "Plate Mill",              "Yield",                    "%"),
    (128, "MILL_BSP", "Plate Mill",              "Rolling Rate",             "T/Hr."),
    (130, "MILL_BSP", "Plate Mill",              "Mill Availability",        "%"),
    (131, "MILL_BSP", "Plate Mill",              "Mill Utilisation",         "%"),
    (141, "MILL_BSP", "Plate Mill",              "Heat Consumption",         "103Kcal/T"),
    (157, "MILL_BSP", "Plate Mill",              "Power Consumption",        "Kwh/T"),
    # ── Energy ───────────────────────────────────────────────────────────────
    (161, "MILL_BSP", "Energy",                  "Sp. Energy Consumption",   "G.Cal/T"),
]


# ---------------------------------------------------------------------------
# Section 3 — BSP OISCO Techno parameters
#
# Sheet layout (single sheet "Sheet1"):
#   Row  3, Col C : Title "TECHNO ECONOMIC PARAMETERS_<MON>'YY"
#   Row  6, Cols E+ : Rolling month headers (APR | MAY | CUM)
#   Col  C (3)    : Parameter label
#   Col  D (4)    : Unit
#   Data col      : Column in row 6 matching user-selected month abbreviation
#   CUM  col      : Always one column to the right of the data column
# ---------------------------------------------------------------------------

_OISCO_HEADER_ROW = 6
_OISCO_LABEL_COL  = 3
_OISCO_UNIT_COL   = 4

PARAM_MAP_OISCO: List[tuple] = [
    # (row_1based, group_code, section, label, unit)
    # ── Blast Furnace Operations (rows 9-20) ─────────────────────────────────
    ( 9, "IRON_MAKING", "BF Operations (BSP)", "CDI Rate (Shop 1-8)",     "Kg/THM"),
    (11, "IRON_MAKING", "BF Operations (BSP)", "CDI BF-4",                "Kg/THM"),
    (12, "IRON_MAKING", "BF Operations (BSP)", "CDI BF-5",                "Kg/THM"),
    (13, "IRON_MAKING", "BF Operations (BSP)", "CDI BF-6",                "Kg/THM"),
    (14, "IRON_MAKING", "BF Operations (BSP)", "CDI BF-7",                "Kg/THM"),
    (15, "IRON_MAKING", "BF Operations (BSP)", "CDI BF-8",                "Kg/THM"),
    (16, "IRON_MAKING", "BF Operations (BSP)", "Fuel Rate (Shop 1-8)",    "Kg/THM"),
    (17, "IRON_MAKING", "BF Operations (BSP)", "Pellet % in Burden",      "%"),
    (18, "IRON_MAKING", "BF Operations (BSP)", "LD Slag Usage (Shop 1-8)","Kg/THM"),
    (19, "IRON_MAKING", "BF Operations (BSP)", "Not Dry Cast (Shop 1-8)", "%"),
    (20, "IRON_MAKING", "BF Operations (BSP)", "Coal to HM Ratio",        "Ratio"),
    # ── SMS-II Operations (rows 22-36) ───────────────────────────────────────
    (22, "BOF", "SMS-II Operations (BSP)", "Converter Availability",      "% ICH"),
    (23, "BOF", "SMS-II Operations (BSP)", "Converter Utilisation",       "% Avail hr"),
    (24, "BOF", "SMS-II Operations (BSP)", "Tap to Tap Time",             "Minutes"),
    (25, "BOF", "SMS-II Operations (BSP)", "Average Blows/Day",           "Heats/Day"),
    (26, "BOF", "SMS-II Operations (BSP)", "Average Heat Weight",         "Tonnes"),
    (27, "BOF", "SMS-II Operations (BSP)", "Avg. Lining Life",            "Heats"),
    (28, "BOF", "SMS-II Operations (BSP)", "Fe-Mn Consumption",           "Kg/TCS"),
    (29, "BOF", "SMS-II Operations (BSP)", "Fe-Si Consumption",           "Kg/TCS"),
    (30, "BOF", "SMS-II Operations (BSP)", "Si-Mn Consumption",           "Kg/TCS"),
    (31, "BOF", "SMS-II Operations (BSP)", "Oxygen Consumption",          "NM3/TCS"),
    (32, "BOF", "SMS-II Operations (BSP)", "Alumina Consumption",         "Kg/TCS"),
    (35, "BOF", "SMS-II Operations (BSP)", "LD Gas Recovery",             "CuM/T"),
    (36, "BOF", "SMS-II Operations (BSP)", "DS Heats",                    "Nos"),
    # ── SMS-III Operations (rows 38-51) ──────────────────────────────────────
    (38, "BOF", "SMS-III Operations (BSP)", "Converter Availability",     "% ICH"),
    (39, "BOF", "SMS-III Operations (BSP)", "Converter Utilisation",      "% Avail hr"),
    (40, "BOF", "SMS-III Operations (BSP)", "Tap to Tap Time",            "Minutes"),
    (41, "BOF", "SMS-III Operations (BSP)", "Average Blows/Day",          "Heats/Day"),
    (42, "BOF", "SMS-III Operations (BSP)", "Average Heat Weight",        "Tonnes"),
    (43, "BOF", "SMS-III Operations (BSP)", "Fe-Mn Consumption",          "Kg/TCS"),
    (44, "BOF", "SMS-III Operations (BSP)", "Fe-Si Consumption",          "Kg/TCS"),
    (45, "BOF", "SMS-III Operations (BSP)", "Si-Mn Consumption",          "Kg/TCS"),
    (46, "BOF", "SMS-III Operations (BSP)", "Oxygen Consumption",         "NM3/TCS"),
    (47, "BOF", "SMS-III Operations (BSP)", "Alumina Consumption",        "Kg/TCS"),
    (50, "BOF", "SMS-III Operations (BSP)", "LD Gas Recovery",            "CuM/T"),
    (51, "BOF", "SMS-III Operations (BSP)", "DS Heats",                   "Nos"),
    # ── Utilities (row 54) ───────────────────────────────────────────────────
    (54, "IRON_MAKING", "Utilities (BSP)", "Sp. Water Consumption",       "CuM/TCS"),
]


# ---------------------------------------------------------------------------
# Section 4 — BSP Special Steel report (.xlsx, sheet "CORP")
#
# Sheet layout:
#   R2C9  : Report date "DD.MM.YY" (e.g. "31.03.26") — month extracted from here
#   R3C1  : "BHILAI STEEL PLANT"
#   R4-R5 : Column headers
#   Col A (1): Products (product group for first row of each group)
#   Col B (2): Quality/Grade
#   Col C (3): ABP Annual
#   Col D (4): ABP Monthly (current month)
#   Col E (5): Orders Available Total
#   Col F (6): Orders Available Effective  → saved as order_qty
#   Col G (7): Loading (Till Date)         → saved as actual_despatch
#   Col H (8): Loadable in stock
#   Col I (9): Semis/Fin in process
#   Data rows from R6 onwards
# ---------------------------------------------------------------------------

# Map from Col A label (uppercase) → canonical product group name stored in DB
_BSP_SS_GROUP_MAP: Dict[str, Optional[str]] = {
    "SEMIS":       "Semis",
    "WIRE RODS":   "Wire Rods",
    "MERCHANT":    "Merchant Products",  # first row of a 2-row merged label
    "PRODUCTS":    None,                 # continuation of "Merchant Products" — skip group change
    "BRM PRODUCT": "BRM Product",
    "RAILS":       "Rails",
    "PLATES":      "Plates",
}

# Labels in Col A that signal a total/subtotal row (prefix match)
_BSP_SS_TOTAL_PREFIXES = ("TOTAL ", "TOTAL\n")


def _is_bsp_ss_file(wb) -> bool:
    """True if workbook is BSP Special Steel: sheet 'CORP' with BHILAI STEEL PLANT in R3C1."""
    if "CORP" not in wb.sheetnames:
        return False
    ws = wb["CORP"]
    return "BHILAI STEEL PLANT" in str(ws.cell(3, 1).value or "").upper()


def _is_oisco_file(wb) -> bool:
    """True if R3C3 contains 'TECHNO ECONOMIC PARAMETERS' (OISCO format)."""
    ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb.active
    return "TECHNO ECONOMIC PARAMETERS" in str(ws.cell(3, 3).value or "").upper()


def _parse_bsp_ss_month(ws) -> Optional[str]:
    """Parse report month from R2C9 date string like '31.03.26' → '2026-03'."""
    raw = str(ws.cell(2, 9).value or "").strip()
    # Format: DD.MM.YY
    m = re.match(r"(\d{1,2})\.(\d{2})\.(\d{2})$", raw)
    if m:
        month_num = m.group(2)
        yr2 = int(m.group(3))
        yr_full = 2000 + yr2 if yr2 < 50 else 1900 + yr2
        return f"{yr_full}-{month_num}"
    return None


def _extract_bsp_ss_preview(wb, report_month: str) -> dict:
    """Parse BSP Special Steel Excel (CORP sheet).

    Returns the standard preview dict with special_steel_rows.
    order_qty = Col F (Orders Available Effective)
    actual_despatch = Col G (Loading Till Date)
    """
    ws = wb["CORP"]
    db_month = _parse_bsp_ss_month(ws) or report_month

    rows: List[Dict[str, Any]] = []
    cur_product = ""
    sort = 0

    for r in range(6, ws.max_row + 1):
        col_a_val = ws.cell(r, 1).value
        col_b_val = ws.cell(r, 2).value

        if col_a_val is None and col_b_val is None:
            continue

        label_a = str(col_a_val).strip() if col_a_val is not None else ""
        label_b = str(col_b_val).strip() if col_b_val is not None else ""
        label_a_up = label_a.upper()

        # Grand total sentinel — include then stop
        if "TOTAL SPECIAL STEEL" in label_a_up:
            cf = _clean(ws.cell(r, 6).value)
            cg = _clean(ws.cell(r, 7).value)
            sort += 1
            rows.append({
                "product": "", "quality_grade": label_a, "section": "",
                "sort_order": sort,
                "order_qty": cf, "prodn": None, "actual_despatch": cg,
                "abp_month": _clean(ws.cell(r, 4).value),
                "unit": "T", "cell": f"R{r}C6/C7",
                "status": "total",
            })
            break

        # Intermediate total / subtotal row
        is_total = any(label_a_up.startswith(p) for p in _BSP_SS_TOTAL_PREFIXES)

        # Update current product group
        canonical = _BSP_SS_GROUP_MAP.get(label_a_up)
        if canonical is not None:
            cur_product = canonical
        # If canonical is explicitly None it's a continuation row — keep cur_product

        # Determine grade label
        if is_total:
            grade = label_a
        elif label_b:
            grade = label_b
        elif label_a and label_a_up not in _BSP_SS_GROUP_MAP:
            grade = label_a
        else:
            continue  # pure group-header row with no grade

        # Extract values
        cf   = _clean(ws.cell(r, 6).value)   # effective orders → order_qty
        cg   = _clean(ws.cell(r, 7).value)   # loading till date → actual_despatch
        c_d  = _clean(ws.cell(r, 4).value)   # ABP monthly (cross-check)
        c_e  = _clean(ws.cell(r, 5).value)   # total orders (cross-check)

        # Skip structurally-empty rows (but keep total rows even if zero)
        if not is_total and not any(v for v in (cf, cg, c_d, c_e)):
            continue

        sort += 1
        rows.append({
            "product":         "" if is_total else cur_product,
            "quality_grade":   grade,
            "section":         "",
            "sort_order":      sort,
            "order_qty":       cf,
            "prodn":           None,
            "actual_despatch": cg,
            "abp_month":       c_d,    # preview cross-check only
            "unit":            "T",
            "cell":            f"R{r}C6/C7",
            "status":          "total" if is_total else "ok",
        })

    ok_count = sum(1 for r in rows if r["status"] == "ok")
    logger.info(
        "BSP Special Steel preview: %d ok rows + %d total rows for %s",
        ok_count, len(rows) - ok_count, db_month,
    )

    return {
        "plant":              "BSP",
        "month":              db_month,
        "source_type":        "BSP Special Steel Report",
        "sheets":             "CORP",
        "workbook_sheets":    wb.sheetnames,
        "production_rows":    [],
        "techno_rows":        [],
        "techno_param_rows":  [],
        "special_steel_rows": rows,
    }


# ---------------------------------------------------------------------------
# Section 2 helpers — 3-page-Tech
# ---------------------------------------------------------------------------

def _detect_3page_cum_col(ws) -> int:
    """Scan row 4 for a known cumulative header; return its 1-based column."""
    for c in range(1, 30):
        v = str(ws.cell(4, c).value or "").strip().upper()
        if v in _TECHNO_3PAGE_CUM_HEADERS:
            return c
    return _TECHNO_3PAGE_CUM_FALLBACK


def _detect_3page_month_from_file(ws) -> Optional[str]:
    """Read month name from row 3, col A. Returns 'MM' string or None."""
    raw = ws.cell(3, 1).value
    if not raw:
        return None
    key = str(raw).strip().upper()
    return _MONTH_NAME_TO_NUM.get(key) or _MONTH_NAME_TO_NUM.get(key[:3])


def _extract_techno_3page_preview(wb, file_path: str, report_month: str) -> dict:
    """Extract BSP techno params from 3-page-Tech.xlsx or S2 sheet of PPC MIS."""
    if "Sheet1" in wb.sheetnames:
        ws = wb["Sheet1"]
    elif "S2" in wb.sheetnames:
        ws = wb["S2"]
    else:
        ws = wb.active

    m_num: Optional[str] = None
    y_str: Optional[str] = None

    if report_month and len(report_month) >= 7 and report_month[4] == "-":
        y_str = report_month[:4]
        m_num = report_month[5:7]
    else:
        m_num = _detect_3page_month_from_file(ws)
        import datetime
        y_str = str(datetime.date.today().year)

    if not m_num or m_num not in _MONTH_NUM_TO_COL:
        raise ValueError(
            f"Cannot determine a valid report month (got m_num={m_num!r}). "
            "Please provide a valid month in YYYY-MM format."
        )

    db_month    = f"{y_str}-{m_num}"
    month_col   = _MONTH_NUM_TO_COL[m_num]
    month_label = _MONTH_FULL.get(m_num, m_num)

    expected_hdr = _MONTH_NUM_TO_HDR.get(m_num, "")
    actual_hdr   = str(ws.cell(4, month_col).value or "").strip().upper()
    header_ok    = actual_hdr == expected_hdr
    if not header_ok:
        logger.warning(
            "BSP 3-page-Tech: expected row-4 header %r in col %s but found %r. Proceeding.",
            expected_hdr, get_column_letter(month_col), actual_hdr,
        )

    cum_col     = _detect_3page_cum_col(ws)
    cum_col_ltr = get_column_letter(cum_col)
    mon_col_ltr = get_column_letter(month_col)

    rows_out: List[Dict[str, Any]] = []
    for sort_idx, (row_1b, group, section, param, unit) in enumerate(PARAM_MAP_3PAGE):
        actual_val = _clean(ws.cell(row_1b, month_col).value)
        cum_val    = _clean(ws.cell(row_1b, cum_col).value)
        file_label = str(ws.cell(row_1b, 1).value or "").strip()
        cell_ref   = f"{mon_col_ltr}{row_1b}/{cum_col_ltr}{row_1b}"
        status     = "ok" if (actual_val is not None or cum_val is not None) else "skip"

        rows_out.append({
            "group_code": group, "section": section, "parameter": param,
            "unit": unit, "actual": actual_val, "cum_actual": cum_val,
            "sort_order": sort_idx * 10, "cell": cell_ref,
            "file_label": file_label, "plant": "BSP", "month": db_month,
            "found_via": f"hardcoded R{row_1b}", "status": status,
        })

    ok_count = sum(1 for r in rows_out if r["status"] == "ok")
    logger.info(
        "BSP 3-page-Tech preview: %d/%d rows ok for %s (col %s, cum col %s)",
        ok_count, len(rows_out), db_month, mon_col_ltr, cum_col_ltr,
    )

    return {
        "source_type":        "BSP-3-page-Tech.xlsx",
        "month":              db_month,
        "plant":              "BSP",
        "workbook_sheets":    wb.sheetnames,
        "month_col_letter":   mon_col_ltr,
        "cum_col_letter":     cum_col_ltr,
        "header_verified":    header_ok,
        "file_month":         month_label,
        "production_rows":    [],
        "techno_rows":        [],
        "techno_param_rows":  rows_out,
        "special_steel_rows": [],
    }


# ---------------------------------------------------------------------------
# Section 3 helpers — OISCO
# ---------------------------------------------------------------------------

def _detect_oisco_month_from_title(ws) -> Optional[str]:
    """Parse month abbreviation from title cell R3C3, e.g. '...PARAMETERS_MAY'25'."""
    raw = str(ws.cell(3, 3).value or "").upper()
    m = re.search(r"_([A-Z]{3})'?\d{2}", raw)
    if m:
        return _MONTH_NAME_TO_NUM.get(m.group(1))
    for abbr, num in _MONTH_NAME_TO_NUM.items():
        if len(abbr) == 3 and abbr in raw:
            return num
    return None


def _detect_oisco_columns(ws, m_num: str):
    """Scan row 6 for month abbreviation; return (data_col, cum_col) 1-based."""
    expected = _MONTH_NUM_TO_HDR.get(m_num, "")
    for c in range(1, ws.max_column + 2):
        v = str(ws.cell(_OISCO_HEADER_ROW, c).value or "").strip().upper()
        if v == expected:
            return c, c + 1
    found = [
        str(ws.cell(_OISCO_HEADER_ROW, c).value or "").strip()
        for c in range(1, ws.max_column + 1)
        if ws.cell(_OISCO_HEADER_ROW, c).value
    ]
    raise ValueError(
        f"Month header '{expected}' not found in row {_OISCO_HEADER_ROW}. "
        f"Found: {found}. Ensure the file is for the selected month."
    )


def _extract_oisco_preview(wb, report_month: str) -> dict:
    """Extract BSP OISCO techno params from OISCO_<Mon>'YY.xlsx."""
    ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb.active

    m_num: Optional[str] = None
    y_str: Optional[str] = None

    if report_month and len(report_month) >= 7 and report_month[4] == "-":
        y_str = report_month[:4]
        m_num = report_month[5:7]
    else:
        m_num = _detect_oisco_month_from_title(ws)
        import datetime
        y_str = str(datetime.date.today().year)

    if not m_num or m_num not in _MONTH_NUM_TO_HDR:
        raise ValueError(
            f"Cannot determine report month (got {m_num!r}). "
            "Provide a valid YYYY-MM month."
        )

    db_month   = f"{y_str}-{m_num}"
    month_full = _MONTH_FULL.get(m_num, m_num)

    data_col, cum_col = _detect_oisco_columns(ws, m_num)
    data_ltr = get_column_letter(data_col)
    cum_ltr  = get_column_letter(cum_col)

    file_m_num = _detect_oisco_month_from_title(ws)
    header_ok  = (file_m_num == m_num)
    if not header_ok:
        logger.warning(
            "OISCO: file title month %r does not match user-selected %r. Proceeding.",
            file_m_num, m_num,
        )

    rows_out: List[Dict[str, Any]] = []
    for sort_idx, (row_1b, group, section, param, unit) in enumerate(PARAM_MAP_OISCO):
        actual_val = _clean(ws.cell(row_1b, data_col).value)
        cum_val    = _clean(ws.cell(row_1b, cum_col).value)
        file_label = str(ws.cell(row_1b, _OISCO_LABEL_COL).value or "").strip().replace("\n", " ")
        cell_ref   = f"{data_ltr}{row_1b}/{cum_ltr}{row_1b}"
        status     = "ok" if (actual_val is not None or cum_val is not None) else "skip"

        rows_out.append({
            "group_code": group, "section": section, "parameter": param,
            "unit": unit, "actual": actual_val, "cum_actual": cum_val,
            "sort_order": sort_idx * 10, "cell": cell_ref,
            "file_label": file_label, "plant": "BSP", "month": db_month,
            "found_via": f"hardcoded R{row_1b}", "status": status,
        })

    ok_count = sum(1 for r in rows_out if r["status"] == "ok")
    logger.info(
        "BSP OISCO preview: %d/%d rows ok for %s (col %s, cum col %s)",
        ok_count, len(rows_out), db_month, data_ltr, cum_ltr,
    )

    return {
        "source_type":        "BSP-OISCO-Techno.xlsx",
        "month":              db_month,
        "plant":              "BSP",
        "workbook_sheets":    wb.sheetnames,
        "month_col_letter":   data_ltr,
        "cum_col_letter":     cum_ltr,
        "header_verified":    header_ok,
        "file_month":         month_full,
        "production_rows":    [],
        "techno_rows":        [],
        "techno_param_rows":  rows_out,
        "special_steel_rows": [],
    }


# ---------------------------------------------------------------------------
# Section 1b — BSP PPC MIS preview (S1 production + S2 techno)
# ---------------------------------------------------------------------------

def _extract_ppc_mis_preview(file_path: str, report_month: str) -> dict:
    """Preview BSP PPC MIS .xls: production from sheet S1 only."""

    wb_raw = xlrd.open_workbook(file_path)
    ws_s1 = wb_raw.sheet_by_name("S1")

    n1_raw = ws_s1.cell_value(0, 13)
    if n1_raw and isinstance(n1_raw, float) and n1_raw > 0:
        y, m, *_ = xlrd.xldate_as_tuple(n1_raw, wb_raw.datemode)
        db_month = f"{y}-{m:02d}"
        logger.info("BSP PPC MIS preview: month from S1!N1 → %s", db_month)
    elif report_month:
        db_month = report_month
    else:
        db_month = "unknown"

    COL_F, COL_J, COL_N = 5, 9, 13
    _PROD_CELLS = [
        ("COB#1-8",             3,  COL_F, False, "F4"),
        ("Oven Pushing(nos/d)", 5,  COL_F, False, "F6"),
        ("SP-2",                7,  COL_F, True,  "F8"),
        ("SP-3",                8,  COL_F, True,  "F9"),
        ("Total Sinter",        9,  COL_F, True,  "F10"),
        ("BF#1-7",              10, COL_F, True,  "F11"),
        ("BF#8",                11, COL_F, True,  "F12"),
        ("Hot Metal",           12, COL_F, True,  "F13"),
        ("SMS-2",               13, COL_F, True,  "F14"),
        ("SMS-3",               15, COL_F, True,  "F16"),
        ("Total Crude Steel",   16, COL_F, True,  "F17"),
        ("RSM_RAIL",            17, COL_F, True,  "F18"),
        ("URM_RAIL",            21, COL_F, True,  "F22"),
        ("MM",                  23, COL_F, True,  "F24"),
        ("WIRERODS",            24, COL_F, True,  "F25"),
        ("BARS&RODMILL",        25, COL_F, True,  "F26"),
        ("PLATEMILL",           26, COL_F, True,  "F27"),
        ("Finished Steel",      27, COL_F, True,  "F28"),
        ("Saleable Semis",      34, COL_F, True,  "F35"),
        ("Saleable Steel",      35, COL_F, True,  "F36"),
        ("RSMPRIME",            38, COL_F, True,  "F39"),
        ("URMPRIME",            38, COL_J, True,  "J39"),
        ("Pig Iron",            62, COL_N, True,  "N63"),
    ]

    production_rows = []
    for item_name, row_0, col_0, do_convert, cell_ref in _PROD_CELLS:
        raw = ws_s1.cell_value(row_0, col_0)
        val = _clean(raw)
        if val is not None and do_convert:
            val = round(val / 1000.0, 3)
        unit = "nos/d" if not do_convert else "'000T"
        production_rows.append({
            "item_name": item_name,
            "value": val,
            "unit": unit,
            "cell": f"S1!{cell_ref}",
            "pdf_label": cell_ref,
            "status": "ok" if val is not None else "skip",
        })

    ok_prod = sum(1 for r in production_rows if r["status"] == "ok")
    logger.info("BSP PPC MIS preview: %d/%d production rows ok for %s", ok_prod, len(production_rows), db_month)

    return {
        "source_type":        "BSP PPC MIS Monthly Report",
        "month":              db_month,
        "plant":              "BSP",
        "workbook_sheets":    wb_raw.sheet_names(),
        "production_rows":    production_rows,
        "techno_rows":        [],
        "techno_param_rows":  [],
        "special_steel_rows": [],
    }


# ---------------------------------------------------------------------------
# Unified preview entry point (auto-detects file type)
# ---------------------------------------------------------------------------

def extract_preview(file_path: str, report_month: str) -> dict:
    """Unified BSP preview — auto-detects file type. No DB writes.

    Detection priority:
      1. BSP PPC MIS       → sheet 'S1' present (.xls monthly report)
      2. BSP Special Steel → sheet 'CORP' with 'BHILAI STEEL PLANT' in R3C1
      3. OISCO Techno      → R3C3 contains 'TECHNO ECONOMIC PARAMETERS'
      4. BSP 3-page-Tech   → default (Sheet1 with month name in R3C1)
    """
    wb = _open_workbook(file_path)

    if "S1" in wb.sheetnames:
        logger.info("BSP: detected PPC MIS file (sheet S1) — production only")
        return _extract_ppc_mis_preview(file_path, report_month)

    if _is_bsp_ss_file(wb):
        logger.info("BSP: detected Special Steel file (sheet CORP)")
        return _extract_bsp_ss_preview(wb, report_month)

    if _is_oisco_file(wb):
        logger.info("BSP: detected OISCO Techno file")
        return _extract_oisco_preview(wb, report_month)

    logger.info("BSP: detected 3-page-Tech file (default)")
    return _extract_techno_3page_preview(wb, file_path, report_month)
