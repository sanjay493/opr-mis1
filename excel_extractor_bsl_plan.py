import openpyxl
import logging
import sqlite3
import os
from typing import Optional

logger = logging.getLogger("excel_extractor_plan")

DB_PATH = os.path.join(os.path.dirname(__file__), "backend", "mis_reports.db")


def clean_val(val) -> Optional[float]:
    if val is None or str(val).strip().lower() in ("nan", "###", "-", "#div/0!"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def extract_and_save_excel_plan(file_path: str, financial_year: str) -> bool:
    """
    Extracts BSL ABP plan data for all 12 months.
    Writes to production_plan_table with plant_name='BSL'.

    Expected sheet: 'Monthwise' or 'Sheet1'

    Column layout (0-based after skipping index/label cols):
      APR | MAY | JUN | [Q1] | JUL | AUG | SEP | [Q2] | OCT | NOV | DEC | [Q3] | JAN | FEB | MAR | [Q4/Annual]

    Month columns (1-based):
      Col B=APR, C=MAY, D=JUN, F=JUL, G=AUG, H=SEP, J=OCT, K=NOV, L=DEC, N=JAN, O=FEB, P=MAR

    Row map (1-based) — adjust to match actual BSL ABP layout:
      Row 7:  Oven Pushing(nos/d)   — nos/day average, no /1000
      Row 11: Total Sinter          — '000 T
      Row 14: Hot Metal             — '000 T
      Row 20: Pig Iron              — '000 T
      Row 21: Total Crude Steel     — '000 T
      Row 30: Saleable Semis        — '000 T
      Row 31: Finished Steel        — '000 T
      Row 32: Saleable Steel        — '000 T

    NOTE: Verify row numbers against the actual BSL ABP Excel before uploading.
    """
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet_names = wb.sheetnames
        logger.info(f"BSL Plan: loading file. Sheets: {sheet_names}")

        # Detect sheet
        sheet_key = None
        for candidate in ("Monthwise", "Sheet1", "MONTHWISE", "sheet1"):
            if candidate in sheet_names:
                sheet_key = candidate
                break

        if not sheet_key:
            raise ValueError(
                f"BSL Plan Excel missing expected sheet. "
                f"Found: {sheet_names}. Expected 'Monthwise' or 'Sheet1'."
            )

        logger.info(f"BSL Plan: using sheet '{sheet_key}'")

        if "-" in financial_year:
            year_val = int(financial_year.split("-")[0])
        else:
            year_val = int(financial_year)

        # Month code → (column letter, month name, year offset)
        col_map = {
            "04": ("B", "April",     0),
            "05": ("C", "May",       0),
            "06": ("D", "June",      0),
            "07": ("F", "July",      0),
            "08": ("G", "August",    0),
            "09": ("H", "September", 0),
            "10": ("J", "October",   0),
            "11": ("K", "November",  0),
            "12": ("L", "December",  0),
            "01": ("N", "January",   1),
            "02": ("O", "February",  1),
            "03": ("P", "March",     1),
        }

        NO_CONVERT = {"Oven Pushing(nos/d)"}

        # Row offsets (1-based) — VERIFY against actual BSL ABP Excel layout
        production_cells = {
            "Oven Pushing(nos/d)":  7,
            "Total Sinter":        11,
            "Hot Metal":           14,
            "Pig Iron":            20,
            "Total Crude Steel":   21,
            "Saleable Semis":      30,
            "Finished Steel":      31,
            "Saleable Steel":      32,
        }

        ws = wb[sheet_key]
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        vals_extracted = 0

        for m_code, (col, m_name, yr_off) in col_map.items():
            db_report_month = f"{m_name} {year_val + yr_off}"

            for db_item, row_num in production_cells.items():
                cell_coord = f"{col}{row_num}"
                raw_val = ws[cell_coord].value
                val = clean_val(raw_val)

                if val is not None:
                    vals_extracted += 1
                    if db_item not in NO_CONVERT:
                        val = round(val, 3)

                cursor.execute("""
                    INSERT INTO production_plan_table (report_month, plant_name, item_name, month_actual)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(report_month, plant_name, item_name)
                    DO UPDATE SET month_actual = excluded.month_actual
                """, (db_report_month, "BSL", db_item, val))

        if vals_extracted == 0:
            raise ValueError(
                "No numeric data extracted from BSL Plan Excel. "
                "Verify that the sheet name, row numbers, and column mapping match the actual file."
            )

        conn.commit()
        conn.close()
        logger.info(f"BSL Plan extraction done: {vals_extracted} values for FY {financial_year}.")
        return True

    except ValueError as ve:
        logger.error(f"BSL Plan validation error: {ve}")
        raise
    except Exception as e:
        logger.error(f"BSL Plan extraction error: {e}")
        return False
