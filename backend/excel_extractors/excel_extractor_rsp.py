import re
import openpyxl
import logging
import sqlite3
import os
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


def _parse_report_month(report_month: str):
    """Returns (db_report_month_yyyymm, month_num_str) from 'YYYY-MM' or legacy 'Month Year'."""
    if len(report_month) == 7 and report_month[4] == "-":
        return report_month, report_month[5:7]
    parts = report_month.split()
    m_name, y_str = parts[0], parts[1]
    m_num = MONTH_NUMS.get(m_name, "11")
    return f"{y_str}-{m_num}", m_num


def extract_and_save_excel(file_path: str, report_month: str, source_file_name: str = "") -> bool:
    """
    Dispatcher: auto-detects RSP file type by sheet name and calls the correct extractor.

    Supported file types:
      • Final Monthly Report  — sheets 'page-9' and 'page 1-8'
      • Daily Morning Report  — sheet starting with 'RSP Morning Report Data for-'
    """
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet_names = wb.sheetnames

        if "page-9" in sheet_names and "page 1-8" in sheet_names:
            return _extract_monthly_report(wb, report_month, source_file_name)

        morning_sheet = next(
            (s for s in sheet_names if s.startswith("RSP Morning Report Data for-")), None
        )
        if morning_sheet:
            return _extract_morning_report(wb, morning_sheet, source_file_name)

        raise ValueError(
            "Uploaded RSP file does not match any known format. "
            "Expected sheets 'page-9'+'page 1-8' (Monthly Report) or "
            "'RSP Morning Report Data for-...' (Daily Morning Report)."
        )
    except ValueError as ve:
        logger.error(f"RSP validation error: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"RSP extraction error: {e}")
        return False


# ---------------------------------------------------------------------------
# Extractor 1 — Final Monthly Report (page-9 + page 1-8)
# ---------------------------------------------------------------------------

def _extract_monthly_report(wb, report_month: str, source_file_name: str) -> bool:
    """Extracts production + techno-economic data from the RSP final monthly report."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import db

    db_report_month, month_num = _parse_report_month(report_month)

    col_map_p9 = {
        "04": "B", "05": "C", "06": "D", "07": "F", "08": "G", "09": "H",
        "10": "J", "11": "K", "12": "L", "01": "N", "02": "O", "03": "P"
    }
    col_map_p18 = {
        "04": "W", "05": "X", "06": "Y", "07": "AA", "08": "AB", "09": "AC",
        "10": "AE", "11": "AF", "12": "AG", "01": "AI", "02": "AJ", "03": "AK"
    }

    col_p9 = col_map_p9.get(month_num)
    col_p18 = col_map_p18.get(month_num)
    if not col_p9 or not col_p18:
        raise ValueError(f"Month column mapping not found for month code '{month_num}'.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    vals_extracted = 0

    # Production data from page-9
    sheet_p9 = wb["page-9"]
    production_cells = {
        "COB#6":               f"{col_p9}6",
        "COB#1-5":             f"{col_p9}7",
        "Oven Pushing(nos/d)": f"{col_p9}8",
        "SP-1":                f"{col_p9}9",
        "SP-2":                f"{col_p9}10",
        "SP-3":                f"{col_p9}11",
        "Total Sinter":        f"{col_p9}12",
        "BF-1":                f"{col_p9}13",
        "BF-5":                f"{col_p9}14",
        "Hot Metal":           f"{col_p9}15",
        "Pig Iron":            f"{col_p9}16",
        "SMS-1 CCM-1":         f"{col_p9}19",
        "SMS-2 CCM-1&2":       f"{col_p9}20",
        "SMS-2 CCM-3":         f"{col_p9}21",
        "SMS-2 CCM-4":         f"{col_p9}22",
        "Total Crude Steel":   f"{col_p9}24",
        "HSM-2 Total HR Coil": f"{col_p9}26",
        "HSM-2 HR Coil (Sale)":f"{col_p9}27",
        "HSM-2 HR Plate":      f"{col_p9}28",
        "OPM Plate":           f"{col_p9}29",
        "NPM Plate":           f"{col_p9}30",
        "CRNO Coils":          f"{col_p9}31",
        "ERW Pipes":           f"{col_p9}32",
        "SW Pipes":            f"{col_p9}33",
        "Saleable Steel":      f"{col_p9}34",
        "Finished Steel":      f"{col_p9}34",
    }
    NO_CONVERT = {"Oven Pushing(nos/d)", "COB#6", "COB#1-5"}

    for item_name, cell in production_cells.items():
        val = clean_val(sheet_p9[cell].value)
        if val is not None:
            vals_extracted += 1
            if item_name not in NO_CONVERT:
                val = round(val / 1000.0, 3)
        cursor.execute("""
            INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, item_name)
            DO UPDATE SET month_actual = excluded.month_actual
        """, (db_report_month, "RSP", item_name, val))

    # Techno-economic data from page 1-8
    sheet_p18 = wb["page 1-8"]
    te_cells = {
        "Coal to Hot metal ratio":                              (f"{col_p18}113", "AM113"),
        "Coke Rate":                                           (f"{col_p18}104", "AM104"),
        "Nut Coke Rate":                                       (f"{col_p18}112", "AM112"),
        "CDI":                                                 (f"{col_p18}108", "AM108"),
        "CDI BF-1":                                            (f"{col_p18}105", "AM105"),
        "CDI BF-5":                                            (f"{col_p18}107", "AM107"),
        "Fuel Rate":                                           (f"{col_p18}156", "AM156"),
        "BF Productivity":                                     (f"{col_p18}100", "AM100"),
        "Sinter% in Burden":                                   (f"{col_p18}124", "AM124"),
        "Pellet% in Burden":                                   (f"{col_p18}125", "AM125"),
        "Energy consumption":                                  (f"{col_p18}340", "AM340"),
        "SMS-1 HM consumption per ton of crude steel":         (f"{col_p18}163", "AM163"),
        "SMS-1 Scrap consumption per ton of crude steel":      (f"{col_p18}164", "AM164"),
        "SMS-2 HM consumption per ton of crude steel":         (f"{col_p18}190", "AM190"),
        "SMS-2 Scrap consumption per ton of crude steel":      (f"{col_p18}191", "AM191"),
        "COB#6 Coke yield%":                                   (f"{col_p18}21",  "AM21"),
        "Oven heat Consumption per ton of Dry coke Input":     (f"{col_p18}304", "AM304"),
        "COB-6 Dry Coal Charge per Oven":                      (f"{col_p18}17",  "AM17"),
        "Coke oven tar yield":                                 (f"{col_p18}27",  "AM27"),
        "Coke oven Ammonia Sulphate yield":                    (f"{col_p18}28",  "AM28"),
        "SP-1 Sinter Productivity":                            (f"{col_p18}38",  "AM38"),
        "SP-2 Sinter Productivity":                            (f"{col_p18}58",  "AM58"),
        "SP-3 Sinter Productivity":                            (f"{col_p18}81",  "AM81"),
        "Coke Screen Loss":                                    (f"{col_p18}31",  "AM31"),
        "SMS-1 Avg Blows per day":                             (f"{col_p18}183", "AM183"),
        "SMS-2 Avg Blows per day":                             (f"{col_p18}213", "AM213"),
        "SMS-1 Avg heat wt":                                   (f"{col_p18}174", "AM174"),
        "SMS-2 Avg heat wt":                                   (f"{col_p18}203", "AM203"),
        "SMS-1 lining life":                                   (f"{col_p18}213", "AM213"),
        "SMS-2 lining life":                                   (f"{col_p18}205", "AM205"),
    }
    unit_map = {
        "Coal to Hot metal ratio": "--",
        "Coke Rate": "kg/thm", "Nut Coke Rate": "kg/thm", "CDI": "kg/thm",
        "Fuel Rate": "kg/thm", "BF Productivity": "t/m3/day",
        "Sinter% in Burden": "%", "Pellet% in Burden": "%",
        "Energy consumption": "Gcal/tcs",
        "SMS-1 HM consumption per ton of crude steel": "kg/tcs",
        "SMS-1 Scrap consumption per ton of crude steel": "kg/tcs",
        "SMS-2 HM consumption per ton of crude steel": "kg/tcs",
        "SMS-2 Scrap consumption per ton of crude steel": "kg/tcs",
    }

    for param, (month_cell, ytd_cell) in te_cells.items():
        month_val = clean_val(sheet_p18[month_cell].value)
        ytd_val = clean_val(sheet_p18[ytd_cell].value)
        if month_val is not None or ytd_val is not None:
            vals_extracted += 1
        cursor.execute("""
            INSERT INTO techno_table (report_month, plant_name, parameter_name, unit, month_actual, ytd_actual)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, parameter_name)
            DO UPDATE SET unit=excluded.unit, month_actual=excluded.month_actual, ytd_actual=excluded.ytd_actual
        """, (db_report_month, "RSP", param, unit_map.get(param, ""), month_val, ytd_val))

    if vals_extracted == 0:
        raise ValueError(
            "No numeric data found in sheets 'page-9' and 'page 1-8'. "
            "Please verify the RSP monthly report file."
        )

    conn.commit()
    conn.close()

    db.log_extraction(
        plant="RSP",
        report_month=db_report_month,
        file_name=source_file_name,
        sheet_name="page-9, page 1-8",
        source_type="Final Monthly Report",
        items_extracted=vals_extracted,
    )
    logger.info(f"RSP Monthly Report extraction done: {vals_extracted} values for {db_report_month}.")
    return True


# ---------------------------------------------------------------------------
# Extractor 2 — Daily Morning Report (RSP Morning Report Data for-...)
# ---------------------------------------------------------------------------

def _extract_morning_report(wb, sheet_name: str, source_file_name: str) -> bool:
    """
    Extracts cumulative production data from the RSP daily morning report.

    Month is auto-detected from cell A2: 'For the Date -:  DD.MM.YYYY'

    Cell map (all values in the single sheet, column F/E/K/etc.):
      COB#6              F11   — nos/day, no conversion
      COB#1-5            F10   — nos/day, no conversion
      Oven Pushing(nos/d)F12   — nos/day, no conversion
      SP-1               E41   — tonnes → /1000
      SP-2               E42
      SP-3               E43
      Total Sinter       E44
      BF-1               K50
      BF-5               K52
      Hot Metal          K53
      Pig Iron           E296
      SMS-1 CCM-1        E92
      SMS-2 CCM-1&2      X69 + X74  (sum of two cells)
      SMS-2 CCM-3        L99
      SMS-2 CCM-4        X79
      Total Crude Steel  F94
      HSM-2 Total HR Coil AB209
      HSM-2 HR Coil (Sale)Z263
      HSM-2 HR Plate     AB210
      OPM Plate          F204
      NPM Plate          F215
      CRNO Coils         E267
      ERW Pipes          E265
      SW Pipes           E266
      Saleable Steel     E268
      Finished Steel     E268
    """
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import db

    ws = wb[sheet_name]

    # Auto-detect month from A2
    a2_raw = ws["A2"].value or ""
    date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", str(a2_raw))
    if not date_match:
        raise ValueError(
            f"Cannot parse date from cell A2: {repr(a2_raw)!r}. "
            "Expected format DD.MM.YYYY inside the cell text."
        )
    _day, m_num, year = date_match.groups()
    db_report_month = f"{year}-{m_num}"
    logger.info(f"RSP Morning Report: month auto-detected from A2 → {db_report_month}")

    NO_CONVERT = {"Oven Pushing(nos/d)", "COB#6", "COB#1-5"}

    # cell value is either a single cell string or a tuple of cells to sum
    production_cells = {
        "COB#1-5":             "F10",
        "COB#6":               "F11",
        "Oven Pushing(nos/d)": "F12",
        "SP-1":                "E41",
        "SP-2":                "E42",
        "SP-3":                "E43",
        "Total Sinter":        "E44",
        "BF-1":                "K50",
        "BF-5":                "K52",
        "Hot Metal":           "K53",
        "Pig Iron":            "E296",
        "SMS-1 CCM-1":         "E92",
        "SMS-2 CCM-1&2":       ("X69", "X74"),   # sum
        "SMS-2 CCM-3":         "L99",
        "SMS-2 CCM-4":         "X79",
        "Total Crude Steel":   "F94",
        "HSM-2 Total HR Coil": "AB209",
        "HSM-2 HR Coil (Sale)":"Z263",
        "HSM-2 HR Plate":      "AB210",
        "OPM Plate":           "F204",
        "NPM Plate":           "F215",
        "CRNO Coils":          "E267",
        "ERW Pipes":           "E265",
        "SW Pipes":            "E266",
        "Saleable Steel":      "E268",
        "Finished Steel":      "E268",
    }

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    vals_extracted = 0

    for item_name, cell_spec in production_cells.items():
        if isinstance(cell_spec, tuple):
            parts = [clean_val(ws[c].value) for c in cell_spec]
            val = sum(p for p in parts if p is not None) or None
            if all(p is None for p in parts):
                val = None
        else:
            val = clean_val(ws[cell_spec].value)

        if val is not None:
            vals_extracted += 1
            if item_name not in NO_CONVERT:
                val = round(val / 1000.0, 3)

        cursor.execute("""
            INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, item_name)
            DO UPDATE SET month_actual = excluded.month_actual
        """, (db_report_month, "RSP", item_name, val))

    if vals_extracted == 0:
        raise ValueError(
            "No numeric data found at the expected cell locations. "
            "Please verify this is the correct RSP Morning Report file."
        )

    conn.commit()
    conn.close()

    db.log_extraction(
        plant="RSP",
        report_month=db_report_month,
        file_name=source_file_name,
        sheet_name=sheet_name,
        source_type="Daily Morning Report",
        items_extracted=vals_extracted,
    )
    logger.info(f"RSP Morning Report extraction done: {vals_extracted} values for {db_report_month}.")
    return True

