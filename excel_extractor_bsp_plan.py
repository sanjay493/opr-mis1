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
    except ValueError:
        return None

def extract_and_save_excel_plan(file_path: str, financial_year: str) -> bool:
    """
    Extracts data from Excel ABP Plan file for all 12 months.
    Writes directly to SQLite table production_plan_table.
    """
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet_names = wb.sheetnames
        logger.info(f"Loading Plan Excel file. Sheets found: {sheet_names}")
        
        # Validation: Verify required sheet exists (checking case-insensitively)
        sheet_key = None
        for s in sheet_names:
            if s.lower() == "table 1":
                sheet_key = s
                break
                
        if not sheet_key:
            raise ValueError(
                "Uploaded Plan Excel file is missing the required sheet 'Table 1'."
            )
            
        logger.info(f"Running custom BSP coordinate-based ABP plan parser on sheet '{sheet_key}'...")
        
        # Parse starting year from financial_year (supports e.g., "2026-27", "2026")
        if "-" in financial_year:
            year_val = int(financial_year.split("-")[0])
        else:
            year_val = int(financial_year)
            
        # Map months to column letters in Table 1
        col_map_p9 = {
            "04": "C", "05": "D", "06": "E", "07": "F", "08": "G", "09": "H",
            "10": "I", "11": "J", "12": "K", "01": "L", "02": "M", "03": "N"
        }
        
        # Mapping from month code to month name and year offset from starting fiscal year
        months_map = {
            "04": ("April", 0),
            "05": ("May", 0),
            "06": ("June", 0),
            "07": ("July", 0),
            "08": ("August", 0),
            "09": ("September", 0),
            "10": ("October", 0),
            "11": ("November", 0),
            "12": ("December", 0),
            "01": ("January", 1),
            "02": ("February", 1),
            "03": ("March", 1)
        }
        
        # Cell row offsets
        production_cells = {
            "COB#1-8": 6,
            "COB#9-10": 7,
            "COB#11": 8,
            "Oven Pushing(nos/d)": 9,
             "SP-2": 11,
             "SP-3": 12,
             "Total Sinter": 13,
            
            "BF#1-7": 14,
            "BF#8": 15,
            "Hot Metal": 16,
            "Pig Iron": 17,
            "SMS-2": 18,
            "SMS-3": 19,
            "SMS-2 BLOOM ": 22,
            "SMS-2 SLAB ": 23,
            "SMS-3 BLOOM(CV1&2)": 26,
            "SMS-3 BILLET105 ": 27,
            "SMS-3 BILLET150 ": 28,
            "Total Crude Steel": 20,
            "RSM_RAIL": 31,
            "URM_RAIL": 32,
            "MM": 33,
            "WIRERODS": 34,
            "BARS&RODMILL": 35,
            "PLATEMILL": 36,
            "Finished Steel": 37,
            "SEMIS SLABS": 39,
            "SEMIS BLOOM": 40,
            "SEMIS BILLETS": 41,
            "Saleable Semis": 42,
            
            "Saleable Steel": 43,
            "RSMPRIME": 45,
            "URMPRIME": 46,
        
        }
        
        vals_extracted = 0
        
        # Connect to SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        sheet = wb[sheet_key]
        
        # Loop over each of the 12 months
        for m_code, (m_name, year_offset) in months_map.items():
            db_report_month = f"{year_val + year_offset}-{m_code}"
            col_p9 = col_map_p9.get(m_code)
            if not col_p9:
                continue
                
            for db_item, row_num in production_cells.items():
                cell_coord = f"{col_p9}{row_num}"
                raw_val = sheet[cell_coord].value
                val = clean_val(raw_val)
                
                if val is not None:
                    vals_extracted += 1
                    # In plan sheet, if numbers are already in thousands, preserve them
                    # (only round to 3 decimal places to keep precision)
                    if db_item not in ("Oven Pushing(nos/d)", "COB#1-8", "COB#9-10", "COB#11"):
                        val = round(val, 3)
                
                # Insert or replace in production_plan_table (using column 'month_actual' as per DB schema)
                cursor.execute("""
                    INSERT INTO production_plan_table (report_month, plant_name, item_name, month_actual)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(report_month, plant_name, item_name) 
                    DO UPDATE SET month_actual = excluded.month_actual
                """, (db_report_month, "BSP", db_item, val))
                
        # Validation: Verify that we extracted some numeric values
        if vals_extracted == 0:
            raise ValueError(
                "No numeric data could be extracted from Table 1. Please verify the contents of the Excel file."
            )

            
        conn.commit()
        conn.close()
        logger.info(f"Custom coordinate BSP ABP Excel plan parsing completed successfully for 12 months starting {year_val}!")
        return True
            
    except ValueError as ve:
        logger.error(f"Validation error parsing Excel file: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        return False
