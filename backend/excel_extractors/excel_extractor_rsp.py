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


def _canon_sheet(s: str) -> str:
    """Canonical sheet name: lowercase, alphanumerics only ('Page 1-8' → 'page18')."""
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

# accepted canonical spellings seen in plant files ('page-9', 'pag-9', 'Page 9', ...)
_P9_NAMES  = {"page9", "pag9", "pg9"}
_P18_NAMES = {"page18", "pag18", "pg18", "pages18"}

def _find_report_sheets(sheet_names):
    """Returns (production_sheet, techno_sheet) or (None, None)."""
    p9 = next((s for s in sheet_names if _canon_sheet(s) in _P9_NAMES), None)
    p18 = next((s for s in sheet_names if _canon_sheet(s) in _P18_NAMES), None)
    return p9, p18


def _parse_report_month(report_month: str):
    """Returns (db_report_month_yyyymm, month_num_str) from 'YYYY-MM' or legacy 'Month Year'."""
    if len(report_month) == 7 and report_month[4] == "-":
        return report_month, report_month[5:7]
    parts = report_month.split()
    m_name, y_str = parts[0], parts[1]
    m_num = MONTH_NUMS.get(m_name, "11")
    return f"{y_str}-{m_num}", m_num


# ---------------------------------------------------------------------------
# Shared cell maps (used by both the direct-save path and the preview path)
# ---------------------------------------------------------------------------

COL_MAP_P9 = {
    "04": "B", "05": "C", "06": "D", "07": "F", "08": "G", "09": "H",
    "10": "J", "11": "K", "12": "L", "01": "N", "02": "O", "03": "P"
}
COL_MAP_P18 = {
    "04": "W", "05": "X", "06": "Y", "07": "AA", "08": "AB", "09": "AC",
    "10": "AE", "11": "AF", "12": "AG", "01": "AI", "02": "AJ", "03": "AK"
}
NO_CONVERT = {"Oven Pushing(nos/d)", "COB#6", "COB#1-5"}

def production_cells_p9(col):
    return {
        "COB#6":               f"{col}6",
        "COB#1-5":             f"{col}7",
        "Oven Pushing(nos/d)": f"{col}8",
        "SP-1":                f"{col}9",
        "SP-2":                f"{col}10",
        "SP-3":                f"{col}11",
        "Total Sinter":        f"{col}12",
        "BF-1":                f"{col}13",
        "BF-5":                f"{col}14",
        "Hot Metal":           f"{col}15",
        "Pig Iron":            f"{col}16",
        "SMS-1 CCM-1":         f"{col}19",
        "SMS-2 CCM-1&2":       f"{col}20",
        "SMS-2 CCM-3":         f"{col}21",
        "SMS-2 CCM-4":         f"{col}22",
        "Total Crude Steel":   f"{col}24",
        "HSM-2 Total HR Coil": f"{col}26",
        "HSM-2 HR Coil (Sale)":f"{col}27",
        "HSM-2 HR Plate":      f"{col}28",
        "OPM Plate":           f"{col}29",
        "NPM Plate":           f"{col}30",
        "CRNO Coils":          f"{col}31",
        "ERW Pipes":           f"{col}32",
        "SW Pipes":            f"{col}33",
        "Saleable Steel":      f"{col}34",
        "Finished Steel":      f"{col}34",
    }

def techno_cells_p18(col):
    return {
        "Coal to Hot metal ratio":                          (f"{col}113", "AM113"),
        "Coke Rate":                                        (f"{col}104", "AM104"),
        "Nut Coke Rate":                                    (f"{col}112", "AM112"),
        "CDI":                                              (f"{col}108", "AM108"),
        "CDI BF-1":                                         (f"{col}105", "AM105"),
        "CDI BF-5":                                         (f"{col}107", "AM107"),
        "Fuel Rate":                                        (f"{col}156", "AM156"),
        "BF Productivity":                                  (f"{col}100", "AM100"),
        "Sinter% in Burden":                                (f"{col}124", "AM124"),
        "Pellet% in Burden":                                (f"{col}125", "AM125"),
        "Energy consumption":                               (f"{col}340", "AM340"),
        "SMS-1 HM consumption per ton of crude steel":      (f"{col}163", "AM163"),
        "SMS-1 Scrap consumption per ton of crude steel":   (f"{col}164", "AM164"),
        "SMS-2 HM consumption per ton of crude steel":      (f"{col}190", "AM190"),
        "SMS-2 Scrap consumption per ton of crude steel":   (f"{col}191", "AM191"),
        "COB#6 Coke yield%":                                (f"{col}21",  "AM21"),
        "Oven heat Consumption per ton of Dry coke Input":  (f"{col}304", "AM304"),
        "COB-6 Dry Coal Charge per Oven":                   (f"{col}17",  "AM17"),
        "Coke oven tar yield":                              (f"{col}27",  "AM27"),
        "Coke oven Ammonia Sulphate yield":                 (f"{col}28",  "AM28"),
        "SP-1 Sinter Productivity":                         (f"{col}38",  "AM38"),
        "SP-2 Sinter Productivity":                         (f"{col}58",  "AM58"),
        "SP-3 Sinter Productivity":                         (f"{col}81",  "AM81"),
        "Coke Screen Loss":                                 (f"{col}31",  "AM31"),
        "SMS-1 Avg Blows per day":                          (f"{col}183", "AM183"),
        "SMS-2 Avg Blows per day":                          (f"{col}213", "AM213"),
        "SMS-1 Avg heat wt":                                (f"{col}174", "AM174"),
        "SMS-2 Avg heat wt":                                (f"{col}203", "AM203"),
        "SMS-1 lining life":                                (f"{col}213", "AM213"),
        "SMS-2 lining life":                                (f"{col}205", "AM205"),
    }

TECHNO_UNIT_MAP = {
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

MORNING_CELLS = {
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
    "SMS-2 CCM-1&2":       ("X69", "X74"),
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


# ---------------------------------------------------------------------------
# Preview extraction — reads everything, writes NOTHING.
# Returned rows are confirmed by the user and inserted via /api/confirm-extraction.
# ---------------------------------------------------------------------------

def _preview_production_from_cells(ws, cells):
    rows = []
    for item, spec in cells.items():
        if isinstance(spec, tuple):
            parts = [clean_val(ws[c].value) for c in spec]
            val = None if all(p is None for p in parts) else sum(p for p in parts if p is not None)
            cell_ref = "+".join(spec)
        else:
            val = clean_val(ws[spec].value)
            cell_ref = spec
        if val is not None and item not in NO_CONVERT:
            val = round(val / 1000.0, 3)
        rows.append({
            "item_name": item, "value": val, "cell": cell_ref,
            "unit": "nos/d" if item in NO_CONVERT else "'000T",
            "status": "ok" if val is not None else "no value",
        })
    return rows


def _preview_techno_from_cells(ws, cells):
    rows = []
    for param, (m_cell, y_cell) in cells.items():
        mv = clean_val(ws[m_cell].value)
        yv = clean_val(ws[y_cell].value)
        rows.append({
            "parameter": param, "unit": TECHNO_UNIT_MAP.get(param, ""),
            "month_actual": mv, "ytd_actual": yv,
            "cell": f"{m_cell}/{y_cell}",
            "status": "ok" if (mv is not None or yv is not None) else "no value",
        })
    return rows


def extract_preview(file_path: str, report_month: str) -> dict:
    """Unified RSP preview: production + techno_table params + mill techno params.
    Auto-detects the file type. No database writes."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))

    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet_names = wb.sheetnames

    production_rows, techno_rows = [], []
    source_type, sheets_used = "Techno Parameters File", ""
    db_report_month, month_num = _parse_report_month(report_month)

    p9_sheet, p18_sheet = _find_report_sheets(sheet_names)
    if p9_sheet and p18_sheet:
        source_type, sheets_used = "Final Monthly Report", f"{p9_sheet}, {p18_sheet}"
        col_p9, col_p18 = COL_MAP_P9.get(month_num), COL_MAP_P18.get(month_num)
        if not col_p9 or not col_p18:
            raise ValueError(f"Month column mapping not found for month code '{month_num}'.")
        production_rows = _preview_production_from_cells(wb[p9_sheet], production_cells_p9(col_p9))
        techno_rows     = _preview_techno_from_cells(wb[p18_sheet], techno_cells_p18(col_p18))
    else:
        morning_sheet = next(
            (s for s in sheet_names
             if s.strip().lower().startswith("rsp morning report data for-")), None)
        if morning_sheet:
            source_type, sheets_used = "Daily Morning Report", morning_sheet
            ws = wb[morning_sheet]
            a2_raw = ws["A2"].value or ""
            dm = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", str(a2_raw))
            if dm:
                _d, m_num, year = dm.groups()
                db_report_month = f"{year}-{m_num}"
            production_rows = _preview_production_from_cells(ws, MORNING_CELLS)

    # Mill techno parameters — anchor-based, works on any RSP file containing
    # the mill sheets (incl. standalone 'technopara' files)
    import excel_extractor_rsp_techno as mill_techno
    techno_param_rows, mill_meta = [], {}
    try:
        t = mill_techno.extract_techno(file_path, db_report_month)
        if t.get("shops_found"):
            techno_param_rows = t["rows"]
            mill_meta = {
                "mill_sheet": t["sheet"], "month_col": t["month_col"],
                "cum_col": t["cum_col"], "columns_detected": t["columns_detected"],
                "shops_found": t["shops_found"],
            }
    except Exception as e:
        logger.warning(f"RSP mill techno scan skipped: {e}")

    if not production_rows and not techno_rows and not techno_param_rows:
        raise ValueError(
            "No extractable data found. Expected an RSP Final Monthly Report, "
            "Daily Morning Report, or a techno-parameters workbook with mill sections.")

    return {
        "plant": "RSP",
        "month": db_report_month,
        "source_type": source_type,
        "sheets": sheets_used,
        "workbook_sheets": sheet_names,
        "production_rows": production_rows,
        "techno_rows": techno_rows,
        "techno_param_rows": techno_param_rows,
        **mill_meta,
    }


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

        p9_sheet, p18_sheet = _find_report_sheets(sheet_names)
        if p9_sheet and p18_sheet:
            return _extract_monthly_report(wb, report_month, source_file_name,
                                           p9_sheet, p18_sheet)

        morning_sheet = next(
            (s for s in sheet_names
             if s.strip().lower().startswith("rsp morning report data for-")), None
        )
        if morning_sheet:
            return _extract_morning_report(wb, morning_sheet, source_file_name)

        # Techno-parameters file (mill sections located by anchors)
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        import excel_extractor_rsp_techno as mill_techno
        import db
        db_report_month, _ = _parse_report_month(report_month)
        t = mill_techno.extract_techno(file_path, db_report_month)
        ok_rows = [r for r in t["rows"] if r["status"] == "ok"]
        if t.get("shops_found") and ok_rows:
            for r in ok_rows:
                pid = db.get_or_create_techno_param(
                    r["group_code"], r["section"], r["parameter"],
                    r["unit"], r["sort_order"])
                db.save_techno_value(db_report_month, pid, r["actual"], r["cum_actual"])
            db.log_extraction(
                plant="RSP", report_month=db_report_month,
                file_name=source_file_name, sheet_name=t["sheet"],
                source_type="Techno Parameters File",
                items_extracted=len(ok_rows))
            logger.info(f"RSP techno-parameters extraction done: {len(ok_rows)} values.")
            return True

        raise ValueError(
            "Uploaded RSP file does not match any known format. "
            "Expected sheets 'page-9'+'page 1-8' (Monthly Report), "
            "'RSP Morning Report Data for-...' (Daily Morning Report), or a "
            "techno-parameters workbook with mill sections (Plate Mill, HSM-II, ...). "
            "Tip: use the 'RSP Extraction (Preview → Insert)' panel to review "
            "extracted data before it is written."
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

def _extract_monthly_report(wb, report_month: str, source_file_name: str,
                            p9_name: str = "page-9", p18_name: str = "page 1-8") -> bool:
    """Extracts production + techno-economic data from the RSP final monthly report."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import db

    db_report_month, month_num = _parse_report_month(report_month)

    col_p9 = COL_MAP_P9.get(month_num)
    col_p18 = COL_MAP_P18.get(month_num)
    if not col_p9 or not col_p18:
        raise ValueError(f"Month column mapping not found for month code '{month_num}'.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    vals_extracted = 0

    # Production data from page-9
    sheet_p9 = wb[p9_name]
    production_cells = production_cells_p9(col_p9)

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
    sheet_p18 = wb[p18_name]
    te_cells = techno_cells_p18(col_p18)
    unit_map = TECHNO_UNIT_MAP

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

    # cell value is either a single cell string or a tuple of cells to sum
    production_cells = MORNING_CELLS

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

