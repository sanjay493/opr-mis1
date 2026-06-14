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
MONTHS_MAP = {v: k for k, v in MONTH_NAMES.items()}


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
    m_num = MONTHS_MAP.get(m_name, "01")
    return f"{y_str}-{m_num}", m_num


def extract_and_save_excel(file_path: str, report_month: str = "", source_file_name: str = "") -> bool:
    """
    Dispatcher: auto-detects ISP file type by sheet name.

    Supported file types:
      • Morning Report (.xlsx)       — sheet 'DAILYREPORT1'. Month auto-detected from K5.
      • Final Monthly Report (.xlsx) — sheet 'Maj Production Summ'. Month set manually.
    """
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet_names = wb.sheetnames
        logger.info(f"ISP: loading file. Sheets: {sheet_names}")

        if "DAILYREPORT1" in sheet_names:
            return _extract_morning_report(wb, source_file_name)

        if "Maj Production Summ" in sheet_names:
            return _extract_monthly_report(wb, report_month, source_file_name)

        raise ValueError(
            "Uploaded ISP file does not match any known format. "
            "Expected sheet 'DAILYREPORT1' (Morning Report) or "
            "'Maj Production Summ' (Final Monthly Report)."
        )
    except ValueError as ve:
        logger.error(f"ISP validation error: {ve}")
        raise
    except Exception as e:
        logger.error(f"ISP extraction error: {e}")
        return False


# ---------------------------------------------------------------------------
# Extractor 1 — ISP Morning Report (month-end daily, sheet: DAILYREPORT1)
# ---------------------------------------------------------------------------

def _extract_morning_report(wb, source_file_name: str) -> bool:
    """
    Extracts cumulative monthly production from ISP Morning Report (sheet 'DAILYREPORT1').

    Date is auto-detected from K5 (Python datetime object). Column E = Monthly Rate.

    Cell map — sheet 'DAILYREPORT1':
      E9:       COB#10              — monthly avg, no unit conversion
      E10:      COB#11              — monthly avg, no unit conversion
      E11:      Oven Pushing(nos/d) — monthly avg nos/day, no unit conversion
      E12:      SP-1                — tonnes → /1000
      E13:      SP-2                — tonnes → /1000
      E14:      Total Sinter        — tonnes → /1000
      E16:      Hot Metal           — tonnes → /1000
      E18+E20:  Pig Iron            — derived sum, tonnes → /1000
      E30:      CCM-1&2             — tonnes → /1000
      E31:      CCM-3               — tonnes → /1000
      E32:      Total Crude Steel   — tonnes → /1000
      E33:      WRMILL              — tonnes → /1000
      E34:      BARMILL             — tonnes → /1000
      E35:      USMILL              — tonnes → /1000
      E36:      Finished Steel      — tonnes → /1000
      E37:      Saleable 150 Billets — tonnes → /1000
      E38:      200 Blooms          — tonnes → /1000
      E37+E38:  Saleable Semis      — derived sum, tonnes → /1000
      E39:      Saleable Steel      — tonnes → /1000
    """
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import db

    ws = wb["DAILYREPORT1"]

    # Date from K5 (Excel stores it as a Python datetime)
    k5_raw = ws["K5"].value
    if isinstance(k5_raw, datetime):
        m_num = str(k5_raw.month).zfill(2)
        year  = str(k5_raw.year)
        db_report_month = f"{year}-{m_num}"
    elif k5_raw:
        date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(k5_raw))
        if date_match:
            _d, m_num, year = date_match.groups()
            db_report_month = f"{year}-{m_num}"
        else:
            raise ValueError(
                f"Cannot parse date from K5: {repr(k5_raw)}. "
                "Expected a datetime value or DD.MM.YYYY string."
            )
    else:
        raise ValueError("Cell K5 is empty — cannot determine report month.")

    logger.info(f"ISP Morning Report: month auto-detected from K5 → {db_report_month}")

    NO_CONVERT = {"COB#10", "COB#11", "Oven Pushing(nos/d)"}

    # Single-cell items: item_name → cell address
    production_cells = {
        "COB#10":                "E9",
        "COB#11":                "E10",
        "Oven Pushing(nos/d)":   "E11",
        "SP-1":                  "E12",
        "SP-2":                  "E13",
        "Total Sinter":          "E14",
        "Hot Metal":             "E16",
        "CCM-1&2":               "E30",
        "CCM-3":                 "E31",
        "Total Crude Steel":     "E32",
        "WRMILL":                "E33",
        "BARMILL":               "E34",
        "USMILL":                "E35",
        "Finished Steel":        "E36",
        "Saleable 150 Billets":  "E37",
        "200 Blooms":            "E38",
        "Saleable Steel":        "E39",
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
        """, (db_report_month, "ISP", item_name, val))

    for item_name, cell in production_cells.items():
        _save(item_name, clean_val(ws[cell].value))

    # Derived: Pig Iron = E18 + E20
    pig_e18 = clean_val(ws["E18"].value)
    pig_e20 = clean_val(ws["E20"].value)
    if pig_e18 is not None or pig_e20 is not None:
        _save("Pig Iron", (pig_e18 or 0.0) + (pig_e20 or 0.0))

    # Derived: Saleable Semis = E37 + E38 (CC Billets + CC Blooms)
    sem_e37 = clean_val(ws["E37"].value)
    sem_e38 = clean_val(ws["E38"].value)
    if sem_e37 is not None or sem_e38 is not None:
        _save("Saleable Semis", (sem_e37 or 0.0) + (sem_e38 or 0.0))

    if vals_extracted == 0:
        raise ValueError(
            "No numeric data found at the expected cell locations in sheet 'DAILYREPORT1'. "
            "Please verify this is the correct ISP Morning Report file."
        )

    conn.commit()
    conn.close()

    db.log_extraction(
        plant="ISP",
        report_month=db_report_month,
        file_name=source_file_name,
        sheet_name="DAILYREPORT1",
        source_type="Daily Morning Report",
        items_extracted=vals_extracted,
    )
    logger.info(f"ISP Morning Report extraction done: {vals_extracted} values saved for {db_report_month}.")
    return True


# ---------------------------------------------------------------------------
# Extractor 2 — ISP Final Monthly Report (sheet: Maj Production Summ)
# ---------------------------------------------------------------------------

def _extract_monthly_report(wb, report_month: str, source_file_name: str) -> bool:
    """
    Extracts production data from ISP Final Monthly Report (sheet 'Maj Production Summ').
    Month must be provided via report_month ('Month Year' or 'YYYY-MM').

    Cell map: items are in fixed rows; month selects the column via col_map.
    """
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import db

    if not report_month:
        raise ValueError(
            "report_month is required for ISP Final Monthly Report. "
            "Set the month selector before uploading."
        )

    db_report_month, month_num = _parse_report_month(report_month)

    col_map = {
        "04": "F",  "05": "H",  "06": "L",  "07": "P",
        "08": "T",  "09": "X",  "10": "AD", "11": "AH",
        "12": "AL", "01": "AR", "02": "AV", "03": "AZ",
    }
    col = col_map.get(month_num)
    if not col:
        raise ValueError(f"Month column mapping not found for month code '{month_num}'.")

    ws = wb["Maj Production Summ"]

    NO_CONVERT = {"COB#10", "COB#11", "Oven Pushing(nos/d)"}

    # item_name → row number (column is dynamic per month via col_map)
    production_cells = {
        "COB#10":                6,
        "COB#11":                7,
        "Oven Pushing(nos/d)":   8,
        "Total Sinter":          16,
        "Hot Metal":             17,
        "Pig Iron":              26,
        "CCM-1&2":               19,
        "CCM-3":                 20,
        "Total Crude Steel":     18,
        "WRMILL":                30,
        "BARMILL":               31,
        "USMILL":                32,
        "Finished Steel":        33,
        "Saleable 150 Billets":  34,
        "200 Blooms":            35,
        "Saleable Semis":        36,
        "Saleable Steel":        37,
    }

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    vals_extracted = 0

    for item_name, row_num in production_cells.items():
        cell_ref = f"{col}{row_num}"
        val = clean_val(ws[cell_ref].value)
        if val is not None:
            vals_extracted += 1
            if item_name not in NO_CONVERT:
                val = round(val / 1000.0, 3)
        cursor.execute("""
            INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, item_name)
            DO UPDATE SET month_actual = excluded.month_actual
        """, (db_report_month, "ISP", item_name, val))

    if vals_extracted == 0:
        raise ValueError(
            "No numeric data could be extracted from 'Maj Production Summ'. "
            "Please verify the contents of the Excel file."
        )

    conn.commit()
    conn.close()

    db.log_extraction(
        plant="ISP",
        report_month=db_report_month,
        file_name=source_file_name,
        sheet_name="Maj Production Summ",
        source_type="Final Monthly Report",
        items_extracted=vals_extracted,
    )
    logger.info(f"ISP Monthly Report extraction done: {vals_extracted} values saved for {db_report_month}.")
    return True


# ---------------------------------------------------------------------------
# Preview functions (no DB writes)
# ---------------------------------------------------------------------------

def _preview_morning_report_rows(wb):
    """Returns (production_rows, db_report_month) for a Morning Report workbook."""
    ws = wb["DAILYREPORT1"]

    k5_raw = ws["K5"].value
    if isinstance(k5_raw, datetime):
        m_num = str(k5_raw.month).zfill(2)
        year  = str(k5_raw.year)
        db_report_month = f"{year}-{m_num}"
    elif k5_raw:
        date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(k5_raw))
        if date_match:
            _, m_num, year = date_match.groups()
            db_report_month = f"{year}-{m_num}"
        else:
            raise ValueError(f"Cannot parse date from K5: {repr(k5_raw)}.")
    else:
        raise ValueError("Cell K5 is empty — cannot determine report month.")

    NO_CONVERT = {"COB#10", "COB#11", "Oven Pushing(nos/d)"}
    production_cells = {
        "COB#10":               "E9",
        "COB#11":               "E10",
        "Oven Pushing(nos/d)":  "E11",
        "SP-1":                 "E12",
        "SP-2":                 "E13",
        "Total Sinter":         "E14",
        "Hot Metal":            "E16",
        "CCM-1&2":              "E30",
        "CCM-3":                "E31",
        "Total Crude Steel":    "E32",
        "WRMILL":               "E33",
        "BARMILL":              "E34",
        "USMILL":               "E35",
        "Finished Steel":       "E36",
        "Saleable 150 Billets": "E37",
        "200 Blooms":           "E38",
        "Saleable Steel":       "E39",
    }

    rows = []
    for item_name, cell in production_cells.items():
        val = clean_val(ws[cell].value)
        if val is not None and item_name not in NO_CONVERT:
            val = round(val / 1000.0, 3)
        rows.append({
            "item_name": item_name,
            "value":     val,
            "cell":      cell,
            "unit":      "nos/d" if item_name in NO_CONVERT else "'000T",
            "status":    "ok" if val is not None else "no value",
        })

    # Derived: Pig Iron = E18 + E20
    pig_e18 = clean_val(ws["E18"].value)
    pig_e20 = clean_val(ws["E20"].value)
    if pig_e18 is not None or pig_e20 is not None:
        pig_val = round(((pig_e18 or 0.0) + (pig_e20 or 0.0)) / 1000.0, 3)
        rows.append({"item_name": "Pig Iron", "value": pig_val, "cell": "E18+E20", "unit": "'000T", "status": "ok"})
    else:
        rows.append({"item_name": "Pig Iron", "value": None, "cell": "E18+E20", "unit": "'000T", "status": "no value"})

    # Derived: Saleable Semis = E37 + E38
    sem_e37 = clean_val(ws["E37"].value)
    sem_e38 = clean_val(ws["E38"].value)
    if sem_e37 is not None or sem_e38 is not None:
        sem_val = round(((sem_e37 or 0.0) + (sem_e38 or 0.0)) / 1000.0, 3)
        rows.append({"item_name": "Saleable Semis", "value": sem_val, "cell": "E37+E38", "unit": "'000T", "status": "ok"})
    else:
        rows.append({"item_name": "Saleable Semis", "value": None, "cell": "E37+E38", "unit": "'000T", "status": "no value"})

    return rows, db_report_month


def _preview_monthly_report_rows(wb, report_month: str):
    """Returns (production_rows, db_report_month) for a Final Monthly Report workbook."""
    if not report_month:
        raise ValueError(
            "report_month is required for ISP Final Monthly Report. "
            "Set the month selector before uploading."
        )

    db_report_month, month_num = _parse_report_month(report_month)

    col_map = {
        "04": "F",  "05": "H",  "06": "L",  "07": "P",
        "08": "T",  "09": "X",  "10": "AD", "11": "AH",
        "12": "AL", "01": "AR", "02": "AV", "03": "AZ",
    }
    col = col_map.get(month_num)
    if not col:
        raise ValueError(f"Month column mapping not found for month code '{month_num}'.")

    ws = wb["Maj Production Summ"]
    NO_CONVERT = {"COB#10", "COB#11", "Oven Pushing(nos/d)"}

    production_cells = {
        "COB#10":               6,
        "COB#11":               7,
        "Oven Pushing(nos/d)":  8,
        "Total Sinter":         16,
        "Hot Metal":            17,
        "Pig Iron":             26,
        "CCM-1&2":              19,
        "CCM-3":                20,
        "Total Crude Steel":    18,
        "WRMILL":               30,
        "BARMILL":              31,
        "USMILL":               32,
        "Finished Steel":       33,
        "Saleable 150 Billets": 34,
        "200 Blooms":           35,
        "Saleable Semis":       36,
        "Saleable Steel":       37,
    }

    rows = []
    for item_name, row_num in production_cells.items():
        cell_ref = f"{col}{row_num}"
        val = clean_val(ws[cell_ref].value)
        if val is not None and item_name not in NO_CONVERT:
            val = round(val / 1000.0, 3)
        rows.append({
            "item_name": item_name,
            "value":     val,
            "cell":      cell_ref,
            "unit":      "nos/d" if item_name in NO_CONVERT else "'000T",
            "status":    "ok" if val is not None else "no value",
        })

    return rows, db_report_month


# ---------------------------------------------------------------------------
# Summarized Monthly Report helpers (no DB writes)
# ---------------------------------------------------------------------------

_MONTH_ABBR3 = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
}


def _find_act_col(ws, month_num: str, year_2d: str, header_row: int, subheader_row: int):
    """Scan header_row for the month label; return 1-based ACT column index or None.

    Matches cells that contain the 3-letter month abbreviation AND the 2-digit year
    suffix (e.g. "'25"), then verifies the next column in subheader_row is "ACT".
    Handles variations like "Jul'25" vs "July'25".
    """
    abbr = _MONTH_ABBR3[month_num].lower()
    year_suffix = f"'{year_2d}"
    for col in range(1, 120):
        raw = ws.cell(row=header_row, column=col).value
        if raw is None:
            continue
        s = str(raw).strip()
        if abbr in s.lower() and year_suffix in s:
            act_check = str(ws.cell(row=subheader_row, column=col + 1).value or "").strip()
            if act_check == "ACT":
                return col + 1
    return None


def _find_cum_act_col(ws, monthly_act_col: int, subheader_row: int):
    """Return the 1-based column index of the next 'ACT' cell after monthly_act_col
    in subheader_row — i.e. the cumulative (YTD) ACT column."""
    for col in range(monthly_act_col + 1, monthly_act_col + 6):
        if str(ws.cell(row=subheader_row, column=col).value or "").strip() == "ACT":
            return col
    return None


def _tr(section: str, name: str, unit: str, val, cell_ref: str, row_label: str = "", ytd_val=None):
    """Build a single techno_row dict."""
    return {
        "parameter":    f"{section} {name}",
        "unit":         unit,
        "month_actual": round(float(val), 4) if val is not None else None,
        "ytd_actual":   round(float(ytd_val), 4) if ytd_val is not None else None,
        "cell":         cell_ref,
        "row_label":    row_label or name,
        "mapping_ok":   True,
        "status":       "ok" if val is not None else "no value",
    }


def _preview_summarized_monthly(wb, report_month: str, sheet_names: list) -> dict:
    """Extract ISP techno parameters from the Summarized Monthly Report.

    Sheet groups and their header rows:
      B-FCE / SINTER / SMS  — month-label row 3 or 4, ABP/ACT row 4 or 5 (varies)
      WRM / BM              — month-label row 3, ABP/ACT row 4
      USM                   — month-label row 3, ABP/ACT row 4  (col shift: Apr ABP=F)

    Column for a given month is detected dynamically so this works regardless of
    how many cumulative columns are interspersed between monthly columns.
    """
    if not report_month:
        raise ValueError(
            "report_month is required for ISP Summarized Monthly Report. "
            "Set the month selector before uploading."
        )

    db_report_month, month_num = _parse_report_month(report_month)
    year_2d = db_report_month[2:4]          # "2025-04" → "25"

    techno_rows = []

    # ------------------------------------------------------------------
    # B-FCE   (header row 4, ABP/ACT sub-header row 5, days in row 2)
    # User-provided rows (verified against file):
    #   39=Coke, 40=Nut Coke, 41=CDI/PCI, 49=Productivity,
    #   52=Sinter%, 53=Pellet%, 72=Coke screen loss,
    #   81=Hot blast temp, 82=Slag rate, 83=Si in HM, 84=S in HM,
    #   93=O2 enrichment%   (user quoted 80-83,92 but file rows are 81-84,93)
    # ------------------------------------------------------------------
    if "B-FCE" in sheet_names:
        ws = wb["B-FCE"]
        ac = _find_act_col(ws, month_num, year_2d, 4, 5)
        if ac:
            cum_ac = _find_cum_act_col(ws, ac, 5)
            col = get_column_letter(ac)
            bf_params = [
                (39,  "Coke Rate",          "Kg/THM"),
                (40,  "Nut Coke Rate",       "Kg/THM"),
                (41,  "PCI Rate",            "Kg/THM"),
                (49,  "Productivity",        "T/M3/Day"),
                (52,  "Sinter% in Burden",   "%"),
                (53,  "Pellet% in Burden",   "%"),
                (72,  "Coke Screen Loss",    "%"),
                (80,  "Hot Blast Temp",      "°C"),
                (81,  "Slag Rate",           "Kg/T"),
                (82,  "Si in HM",            "%"),
                (83,  "S in HM",             "%"),
                (92,  "O2 Enrichment",       "%"),
            ]
            for row, name, unit in bf_params:
                val = clean_val(ws.cell(row=row, column=ac).value)
                ytd_val = clean_val(ws.cell(row=row, column=cum_ac).value) if cum_ac else None
                lbl = str(ws.cell(row=row, column=2).value or "").strip()
                techno_rows.append(_tr("BF", name, unit, val, f"B-FCE!{col}{row}", lbl, ytd_val))

    # ------------------------------------------------------------------
    # SINTER  (header row 3, ABP/ACT row 4)
    # Row 81 — Specific Productivity
    # ------------------------------------------------------------------
    if "SINTER" in sheet_names:
        ws = wb["SINTER"]
        ac = _find_act_col(ws, month_num, year_2d, 3, 4)
        if ac:
            cum_ac = _find_cum_act_col(ws, ac, 4)
            col = get_column_letter(ac)
            val = clean_val(ws.cell(row=81, column=ac).value)
            ytd_val = clean_val(ws.cell(row=81, column=cum_ac).value) if cum_ac else None
            lbl = str(ws.cell(row=81, column=2).value or "").strip()
            techno_rows.append(_tr("Sinter", "Sp Productivity", "T/M2/Utlz Hr", val, f"SINTER!{col}81", lbl, ytd_val))

    # ------------------------------------------------------------------
    # SMS / BOF-CCP  (header row 3, ABP/ACT row 4, days in row 2)
    # Row 10 — Total heats → Blows/day = value ÷ calendar days
    # ------------------------------------------------------------------
    if "SMS" in sheet_names:
        ws = wb["SMS"]
        ac = _find_act_col(ws, month_num, year_2d, 3, 4)
        if ac:
            cum_ac = _find_cum_act_col(ws, ac, 4)
            col = get_column_letter(ac)
            days = clean_val(ws.cell(row=2, column=ac).value) or 30
            heats = clean_val(ws.cell(row=10, column=ac).value)
            blows_day = round(heats / days, 2) if heats is not None else None
            cum_days = clean_val(ws.cell(row=2, column=cum_ac).value) if cum_ac else None
            cum_heats = clean_val(ws.cell(row=10, column=cum_ac).value) if cum_ac else None
            cum_blows = round(cum_heats / cum_days, 2) if (cum_heats is not None and cum_days) else None
            lbl10 = str(ws.cell(row=10, column=2).value or "").strip()
            techno_rows.append(_tr("SMS", "Blows per Day", "Nos/Day", blows_day,
                                   f"SMS!{col}10÷{int(days)}days", lbl10, cum_blows))
            sms_params = [
                (52,  "Avg Cast Wt",           "Mt/Cast"),
                (89,  "HM Consumption",        "Kg/TCS"),
                (90,  "Scrap Consumption",     "Kg/TCS"),
                (91,  "TMI",                   "Kg/TCS"),
                (96,  "Sp O2 Consumption",     "Nm3/T"),
            ]
            for row, name, unit in sms_params:
                val = clean_val(ws.cell(row=row, column=ac).value)
                ytd_val = clean_val(ws.cell(row=row, column=cum_ac).value) if cum_ac else None
                lbl = str(ws.cell(row=row, column=2).value or "").strip()
                techno_rows.append(_tr("SMS", name, unit, val, f"SMS!{col}{row}", lbl, ytd_val))

    # ------------------------------------------------------------------
    # WRM — Wire & Rod Mill  (header row 3, ABP/ACT row 4)
    # ------------------------------------------------------------------
    if "WRM" in sheet_names:
        ws = wb["WRM"]
        ac = _find_act_col(ws, month_num, year_2d, 3, 4)
        if ac:
            cum_ac = _find_cum_act_col(ws, ac, 4)
            col = get_column_letter(ac)
            wrm_params = [
                # (158, "Total Production",     "T"),
                (162, "Mill Yield",           "%"),
                (167, "Mill Availability",    "%"),
                (169, "Mill Utilisation",     "%"),
                (170, "Rolling Rate",      "T/Hr"),
                (174, "Sp Power Cons",        "KWh/T"),
                (172, "Sp Heat Consumption",         "1000 KCal/T"),
            ]
            for row, name, unit in wrm_params:
                val = clean_val(ws.cell(row=row, column=ac).value)
                ytd_val = clean_val(ws.cell(row=row, column=cum_ac).value) if cum_ac else None
                if name == "Sp Heat Consumption":
                    if val is not None: val = val * 1000
                    if ytd_val is not None: ytd_val = ytd_val * 1000
                lbl = str(ws.cell(row=row, column=2).value or "").strip()
                techno_rows.append(_tr("WRM", name, unit, val, f"WRM!{col}{row}", lbl, ytd_val))

    # ------------------------------------------------------------------
    # BM — Bar Mill  (header row 3, ABP/ACT row 4)
    # ------------------------------------------------------------------
    if "BM" in sheet_names:
        ws = wb["BM"]
        ac = _find_act_col(ws, month_num, year_2d, 3, 4)
        if ac:
            cum_ac = _find_cum_act_col(ws, ac, 4)
            col = get_column_letter(ac)
            bm_params = [
                (55,  "Total Production",     "T"),
                (58,  "Mill Yield",           "%"),
                (67,  "Mill Availability",    "%"),
                (69,  "Mill Utilisation",     "%"),
                (72,  "Sp Heat Consumption",      "1000 KCal/T"),
                (73,  "Sp Power Cons",        "KWh/T"),
                (79,  "Rolling Rate",         "T/Hr"),
            ]
            for row, name, unit in bm_params:
                val = clean_val(ws.cell(row=row, column=ac).value)
                ytd_val = clean_val(ws.cell(row=row, column=cum_ac).value) if cum_ac else None
                if name == "Sp Heat Consumption":
                    if val is not None: val = val * 1000
                    if ytd_val is not None: ytd_val = ytd_val * 1000
                lbl = str(ws.cell(row=row, column=2).value or "").strip()
                techno_rows.append(_tr("BM", name, unit, val, f"BM!{col}{row}", lbl, ytd_val))

    # ------------------------------------------------------------------
    # USM — Universal Section Mill
    # Header row 3, ABP/ACT row 4 — but column layout is shifted:
    # Apr'25 label lands in col F (ABP), col G (ACT) instead of E/F.
    # _find_act_col handles this automatically.
    # ------------------------------------------------------------------
    if "USM" in sheet_names:
        ws = wb["USM"]
        ac = _find_act_col(ws, month_num, year_2d, 3, 4)
        if ac:
            cum_ac = _find_cum_act_col(ws, ac, 4)
            col = get_column_letter(ac)
            usm_params = [
                # (120, "Total Production",     "T"),
                (124, "Mill Yield",           "%"),
                (133, "Mill Availability",    "%"),
                (135, "Mill Utilisation",     "%"),
                (138, "Sp Heat Consumption",      "1000 KCal/T"),
                (140, "Sp Power Cons",        "KWh/T"),
                (145, "Rolling Rate",         "T/Hr"),
            ]
            for row, name, unit in usm_params:
                val = clean_val(ws.cell(row=row, column=ac).value)
                ytd_val = clean_val(ws.cell(row=row, column=cum_ac).value) if cum_ac else None
                if name == "Sp Heat Consumption":
                    if val is not None: val = val * 1000
                    if ytd_val is not None: ytd_val = ytd_val * 1000
                lbl = str(ws.cell(row=row, column=2).value or "").strip()
                techno_rows.append(_tr("USM", name, unit, val, f"USM!{col}{row}", lbl, ytd_val))

    ok_count = sum(1 for r in techno_rows if r["status"] == "ok")
    if ok_count == 0:
        raise ValueError(
            f"No data found for month '{report_month}' in the ISP Summarized Monthly Report. "
            "Verify the month selector matches the reporting period of this file."
        )

    # Also extract production from 'Maj Production Summ' when present in the same workbook
    prod_rows = []
    if "Maj Production Summ" in sheet_names:
        try:
            prod_rows, _ = _preview_monthly_report_rows(wb, report_month)
        except Exception as e:
            logger.warning(f"ISP: could not extract production from 'Maj Production Summ': {e}")

    sheets_str = "B-FCE, SINTER, SMS, WRM, BM, USM"
    if prod_rows:
        sheets_str += ", Maj Production Summ"

    logger.info(f"ISP Summarized Monthly Report preview: {ok_count} techno, {len(prod_rows)} production values for {db_report_month}.")
    return {
        "plant":             "ISP",
        "month":             db_report_month,
        "source_type":       "Summarized Monthly Report",
        "sheets":            sheets_str,
        "workbook_sheets":   sheet_names,
        "production_rows":   prod_rows,
        "techno_rows":       techno_rows,
        "techno_param_rows": [],
    }


# ---------------------------------------------------------------------------
# Preview dispatcher
# ---------------------------------------------------------------------------

def extract_preview(file_path: str, report_month: str) -> dict:
    """ISP preview: production or techno rows depending on file type. No DB writes.

    Detects file type by sheet names:
      DAILYREPORT1       → Morning Report (production_rows)
      Maj Production Summ → Final Monthly Report (production_rows)
      B-FCE              → Summarized Monthly Report (techno_rows)
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet_names = wb.sheetnames
    logger.info(f"ISP preview: loading file. Sheets: {sheet_names}")

    if "DAILYREPORT1" in sheet_names:
        rows, db_report_month = _preview_morning_report_rows(wb)
        return {
            "plant":             "ISP",
            "month":             db_report_month,
            "source_type":       "Daily Morning Report",
            "sheets":            "DAILYREPORT1",
            "workbook_sheets":   sheet_names,
            "production_rows":   rows,
            "techno_rows":       [],
            "techno_param_rows": [],
        }

    # Check B-FCE before Maj Production Summ — the Summarized Monthly Report
    # contains BOTH sheets; the standalone Final Monthly Report has only the latter.
    if "B-FCE" in sheet_names:
        return _preview_summarized_monthly(wb, report_month, sheet_names)

    if "Maj Production Summ" in sheet_names:
        rows, db_report_month = _preview_monthly_report_rows(wb, report_month)
        return {
            "plant":             "ISP",
            "month":             db_report_month,
            "source_type":       "Final Monthly Report",
            "sheets":            "Maj Production Summ",
            "workbook_sheets":   sheet_names,
            "production_rows":   rows,
            "techno_rows":       [],
            "techno_param_rows": [],
        }

    raise ValueError(
        "Uploaded ISP file does not match any known format. "
        "Expected sheet 'DAILYREPORT1' (Morning Report), "
        "'Maj Production Summ' (Final Monthly Report), or "
        "'B-FCE' (Summarized Monthly Report)."
    )

