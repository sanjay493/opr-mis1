import openpyxl
import logging
import sqlite3
import os
from typing import Optional

logger = logging.getLogger("excel_extractor")

DB_PATH = os.path.join(os.path.dirname(__file__), "backend", "mis_reports.db")

def clean_val(val) -> Optional[float]:
    if val is None or str(val).strip().lower() in ("nan", "###", "-", "#div/0!"):
        return None
    try:
        return float(val)
    except ValueError:
        return None

def extract_and_save_excel(file_path: str, report_month: str) -> bool:
    """
    Extracts data from Excel file. Supports custom coordinate-based sheets for ISP
    Writes directly to SQLite tables production_table
    """
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet_names = wb.sheetnames
        logger.info(f"Loading Excel file. Sheets found: {sheet_names}")
        
        # Validation: Verify both required sheets exist
        if "Maj Production Summ" not in sheet_names:
            raise ValueError(
                "Uploaded Excel file is missing the required sheets 'Maj Production Summ' "
                "Please upload the correct ISP Excel report."
            )
            
        logger.info("Detected ISP special Excel report layout. Running custom ISP coordinate-based parser...")
        
        # Robust parsing of report_month (supports "2025-11" or "November 2025")
        if "-" in report_month:
            # Format: "YYYY-MM" (e.g. "2025-11")
            parts = report_month.split("-")
            y_str = parts[0]
            m_num = parts[1]
            month_num = m_num
            months_names = {
                "01": "January", "02": "February", "03": "March", "04": "April",
                "05": "May", "06": "June", "07": "July", "08": "August",
                "09": "September", "10": "October", "11": "November", "12": "December"
            }
            db_report_month = f"{months_names.get(m_num)} {y_str}"
        else:
            # Format: "Month Year" (e.g. "November 2025")
            db_report_month = report_month
            parts = report_month.split()
            m_name = parts[0]
            y_str = parts[1]
            months_map = {
                "January": "01", "February": "02", "March": "03", "April": "04",
                "May": "05", "June": "06", "July": "07", "August": "08",
                "September": "09", "October": "10", "November": "11", "December": "12"
            }
            month_num = months_map.get(m_name, "11")
            
        # Map months to column letters for page-9
        col_map_p9 = {
            "04": "F", "05": "H", "06": "L", "07": "P", "08": "T", "09": "X",
            "10": "AD", "11": "AH", "12": "AL", "01": "AR", "02": "AV", "03": "AZ"
        }
        
      
        
        col_p9 = col_map_p9.get(month_num)
        
        if not col_p9:
            raise ValueError(f"Month column mapping not found for month code '{month_num}'.")
            
        vals_extracted = 0
        
        # Connect to SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
            
        # --- Part 1: Parse Production Data from 'Maj Production Summ' ---
        sheet_p9 = wb["Maj Production Summ"]
        
        # Exact cell mappings
        production_cells = {
            # "COB#6": f"{col_p9}6",
             "COB#10": 6,
            "COB#11": 7,
            "Oven Pushing(nos/d)": 8,
             "Total Sinter": 16,
            
            "Hot Metal": 17,
            "Pig Iron": 26,
            "CCM-1&2": 19,
            "CCM-3": 20,
            "Total Crude Steel": 18,
            "WRMILL": 30,
            "BARMILL": 31,
            "USMILL": 32,
            "Finished Steel": 33,
            "Saleable 150 Billets": 34,
            "200 Blooms": 35,
            "Saleable Semis": 36,
            
            "Saleable Steel": 37,
            
        }
        
        for db_item, cell_coord in production_cells.items():
            cell_ref = f"{col_p9}{cell_coord}"
            raw_val = sheet_p9[cell_ref].value
            val = clean_val(raw_val)
            
            if val is not None:
                vals_extracted += 1
                # Convert tonnes to '000 T where appropriate (all except Oven Pushing and COB items)
                if db_item not in ("Oven Pushing(nos/d)", "COB#10", "COB#11"):
                    val = round(val / 1000.0, 3)
            
            cursor.execute("""
                INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, plant_name, item_name) 
                DO UPDATE SET month_actual = excluded.month_actual
            """, (db_report_month, "ISP", db_item, val))
            
        # Validation: Verify that we extracted some numeric values
        if vals_extracted == 0:
            raise ValueError(
                "No numeric data could be extracted from the expected cell locations in "
                "sheet 'Maj Production Summ'. Please verify the contents of the Excel file."
            )
            
        conn.commit()
        conn.close()
        logger.info(f"Custom coordinate ISP Excel parsing completed successfully for month {db_report_month}!")
        return True
            
    except ValueError as ve:
        logger.error(f"Validation error parsing Excel file: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        return False

