import openpyxl
import logging
import sqlite3
import os
from typing import Optional

logger = logging.getLogger("excel_extractor_plan")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "mis_reports.db")

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
            if s.lower() == "monthwise":
                sheet_key = s
                break
                
        if not sheet_key:
            raise ValueError(
                "Uploaded Plan Excel file is missing the required sheet 'Monthwise'."
            )
            
        logger.info(f"Running custom DSP coordinate-based ABP plan parser on sheet '{sheet_key}'...")
        
        # Parse starting year from financial_year (supports e.g., "2026-27", "2026")
        if "-" in financial_year:
            year_val = int(financial_year.split("-")[0])
        else:
            year_val = int(financial_year)
            
        # Map months to column letters in Monthwise
        col_map_p9 = {
            "04": "D", "05": "E", "06": "F", "07": "H", "08": "I", "09": "J",
            "10": "M", "11": "N", "12": "O", "01": "Q", "02": "R", "03": "S"
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
            "Oven Pushing (nos/day)": 7,
            "SP-1": 11,
            "SP-2": 12,
            "Total Sinter": 10,
            
            "BF#2": 14,
            "BF#3": 15,
            "BF#4": 16,
            "Hot Metal": 13,
            "Hot Metal to ASP": 17,
            "Hot Metal to PCM": 18,
            "Pig Iron": 19,
            "Total Crude Steel": 21,
            "BOTTOM_POURING_INGOT": 22,
            "BILLET Caster": 24,
            "BILLET for Sale": 25,
            "Bloom Caster ": 26,
            "BRC": 27,

            "Round Production": 28,
            "Blooms for Sale ": 29,
            "Total Caster": 30,
            "MM": 32,
            "MSM": 35,
            "WAP": 36,
            "Finished Steel": 41,
            
            "Saleable Semis": 40,
            
            "Saleable Steel": 39,
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
                    val = round(val, 3)
                
                # Insert or replace in production_plan_table (using column 'month_actual' as per DB schema)
                cursor.execute("""
                    INSERT INTO production_plan_table (report_month, plant_name, item_name, month_actual)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(report_month, plant_name, item_name) 
                    DO UPDATE SET month_actual = excluded.month_actual
                """, (db_report_month, "DSP", db_item, val))
                
        # Validation: Verify that we extracted some numeric values
        if vals_extracted == 0:
            raise ValueError(
                "No numeric data could be extracted from Monthwise. Please verify the contents of the Excel file."
            )

            
        conn.commit()
        conn.close()
        logger.info(f"Custom coordinate DSP ABP Excel plan parsing completed successfully for 12 months starting {year_val}!")
        return True
            
    except ValueError as ve:
        logger.error(f"Validation error parsing Excel file: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        return False

