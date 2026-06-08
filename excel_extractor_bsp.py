import xlrd
import logging
import sqlite3
import os
from typing import Optional

logger = logging.getLogger("excel_extractor")

DB_PATH = os.path.join(os.path.dirname(__file__), "backend", "mis_reports.db")

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}

def clean_val(val) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("nan", "###", "-", "#div/0!", ""):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def extract_and_save_excel(file_path: str, report_month: str = None, source_file_name: str = "") -> bool:
    """
    Extracts BSP production actuals from the daily PPC MIS .xls report (sheet S1).

    Month is auto-detected from cell N1 (date serial). report_month is used only
    as a fallback when N1 cannot be parsed.

    Source: column F = monthly cumulative ("Cum. Till Date") for tonnage items.
    Units: raw values are in Tonnes; divide by 1000 to store as '000 T.
           Coke oven items (nos/day) are stored as-is.

    Cell map (1-based Excel notation → 0-based xlrd indices):
      F4  = COB#1-8           row 3,  col 5  — avg nos/day, no conversion
      F6  = Oven Pushing      row 5,  col 5  — avg nos/day, no conversion
      F8  = SP-2              row 7,  col 5  — tonnes → /1000
      F9  = SP-3              row 8,  col 5
      F10 = Total Sinter      row 9,  col 5
      F11 = BF#1-7            row 10, col 5
      F12 = BF#8              row 11, col 5
      F13 = Hot Metal         row 12, col 5
      F14 = SMS-2             row 13, col 5
      F16 = SMS-3             row 15, col 5
      F17 = Total Crude Steel row 16, col 5
      F18 = RSM_RAIL          row 17, col 5
      F22 = URM_RAIL          row 21, col 5
      F24 = MM                row 23, col 5
      F25 = WIRERODS          row 24, col 5
      F26 = BARS&RODMILL      row 25, col 5
      F27 = PLATEMILL         row 26, col 5
      F28 = Finished Steel    row 27, col 5
      F35 = Saleable Semis    row 34, col 5
      F36 = Saleable Steel    row 35, col 5
      F39 = RSMPRIME          row 38, col 5
      J39 = URMPRIME          row 38, col 9
      N63 = Pig Iron          row 62, col 13 — tonnes → /1000
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
            db_report_month = f"{MONTH_NAMES[m]} {y}"
            logger.info(f"BSP: month auto-detected from N1 → {db_report_month}")
        elif report_month:
            db_report_month = report_month
            logger.info(f"BSP: using provided report_month → {db_report_month}")
        else:
            raise ValueError(
                "Cannot determine report month: N1 is not a valid date and "
                "no report_month was provided."
            )

        COL_F = 5
        COL_J = 9
        COL_N = 13

        # (row_0based, col_0based, divide_by_1000)
        production_cells = {
            "COB#1-8":           (3,  COL_F, False),
            "Oven Pushing(nos/d)":(5,  COL_F, False),
            "SP-2":              (7,  COL_F, True),
            "SP-3":              (8,  COL_F, True),
            "Total Sinter":      (9,  COL_F, True),
            "BF#1-7":            (10, COL_F, True),
            "BF#8":              (11, COL_F, True),
            "Hot Metal":         (12, COL_F, True),
            "SMS-2":             (13, COL_F, True),
            "SMS-3":             (15, COL_F, True),
            "Total Crude Steel": (16, COL_F, True),
            "RSM_RAIL":          (17, COL_F, True),
            "URM_RAIL":          (21, COL_F, True),
            "MM":                (23, COL_F, True),
            "WIRERODS":          (24, COL_F, True),
            "BARS&RODMILL":      (25, COL_F, True),
            "PLATEMILL":         (26, COL_F, True),
            "Finished Steel":    (27, COL_F, True),
            "Saleable Semis":    (34, COL_F, True),
            "Saleable Steel":    (35, COL_F, True),
            "RSMPRIME":          (38, COL_F, True),
            "URMPRIME":          (38, COL_J, True),
            "Pig Iron":          (62, COL_N, True),
        }

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        vals_extracted = 0

        for item_name, (row_idx, col_idx, do_convert) in production_cells.items():
            raw = ws.cell_value(row_idx, col_idx)
            val = clean_val(raw)
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
                "No numeric data found at the expected cell locations in sheet S1. "
                "Please verify this is the correct BSP PPC MIS file."
            )

        conn.commit()
        conn.close()

        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        import db as _db
        _db.log_extraction(
            plant="BSP",
            report_month=db_report_month,
            file_name=source_file_name,
            sheet_name="S1",
            source_type="Daily PPC MIS Report",
            items_extracted=vals_extracted,
        )
        logger.info(f"BSP extraction done: {vals_extracted} values saved for {db_report_month}.")
        return True

    except ValueError as ve:
        logger.error(f"BSP validation error: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"BSP extraction error: {e}")
        return False
