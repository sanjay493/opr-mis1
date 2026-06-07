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
    Extracts data from Excel file. Supports custom coordinate-based sheets for RSP
    (page-9 for production, page 1-8 for techno-economic).
    Writes directly to SQLite tables production_table and techno_table.
    """
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet_names = wb.sheetnames
        logger.info(f"Loading Excel file. Sheets found: {sheet_names}")
        
        # Validation: Verify both required sheets exist
        if "page-9" not in sheet_names or "page 1-8" not in sheet_names:
            raise ValueError(
                "Uploaded Excel file is missing the required sheets 'page-9' and/or 'page 1-8'. "
                "Please upload the correct RSP Excel report."
            )
            
        logger.info("Detected RSP special Excel report layout. Running custom RSP coordinate-based parser...")
        
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
            "04": "B", "05": "C", "06": "D", "07": "F", "08": "G", "09": "H",
            "10": "J", "11": "K", "12": "L", "01": "N", "02": "O", "03": "P"
        }
        
        # Map months to column letters for page 1-8
        col_map_p18 = {
            "04": "W", "05": "X", "06": "Y", "07": "AA", "08": "AB", "09": "AC",
            "10": "AE", "11": "AF", "12": "AG", "01": "AI", "02": "AJ", "03": "AK"
        }
        
        col_p9 = col_map_p9.get(month_num)
        col_p18 = col_map_p18.get(month_num)
        
        if not col_p9 or not col_p18:
            raise ValueError(f"Month column mapping not found for month code '{month_num}'.")
            
        vals_extracted = 0
        
        # Connect to SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
            
        # --- Part 1: Parse Production Data from 'page-9' ---
        sheet_p9 = wb["page-9"]
        
        # Exact cell mappings
        production_cells = {
            "COB#6": f"{col_p9}6",
            "COB#1-5": f"{col_p9}7",
            "Oven Pushing(nos/d)": f"{col_p9}8",
            "SP-1": f"{col_p9}9",
            "SP-2": f"{col_p9}10",
            "SP-3": f"{col_p9}11",
            "Total Sinter": f"{col_p9}12",
            "BF-1": f"{col_p9}13",
            "BF-5": f"{col_p9}14",
            "Hot Metal": f"{col_p9}15",
            "Pig Iron": f"{col_p9}16",
            "SMS-1 CCM-1": f"{col_p9}19",
            "SMS-2 CCM-1&2": f"{col_p9}20",
            "SMS-2 CCM-3": f"{col_p9}21",
            "SMS-2 CCM-4": f"{col_p9}22",
            "Total Crude Steel": f"{col_p9}24",
            "HSM-2 Total HR Coil": f"{col_p9}26",
            "HSM-2 HR Coil (Sale)": f"{col_p9}27",
            "HSM-2 HR Plate": f"{col_p9}28",
            "OPM Plate": f"{col_p9}29",
            "NPM Plate": f"{col_p9}30",
            "CRNO Coils": f"{col_p9}31",
            "ERW Pipes": f"{col_p9}32",
            "SW Pipes": f"{col_p9}33",
            "Saleable Steel": f"{col_p9}34",
            "Finished Steel": f"{col_p9}34",
        }
        
        for db_item, cell_coord in production_cells.items():
            raw_val = sheet_p9[cell_coord].value
            val = clean_val(raw_val)
            
            if val is not None:
                vals_extracted += 1
                # Convert tonnes to '000 T where appropriate (all except Oven Pushing and COB items)
                if db_item not in ("Oven Pushing(nos/d)", "COB#6", "COB#1-5"):
                    val = round(val / 1000.0, 3)
            
            cursor.execute("""
                INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, plant_name, item_name) 
                DO UPDATE SET month_actual = excluded.month_actual
            """, (db_report_month, "RSP", db_item, val))
            
        # --- Part 2: Parse Techno-Economic Parameters from 'page 1-8' ---
        sheet_p18 = wb["page 1-8"]
        
        # Exact cell mappings based on coordinates in 'page 1-8' (month cell, YTD cell)
        te_cells = {
            "Coal to Hot metal ratio": (f"{col_p18}113", "AM113"),
            "Coke Rate": (f"{col_p18}104", "AM104"),
            "Nut Coke Rate": (f"{col_p18}112", "AM112"),
            "CDI": (f"{col_p18}108", "AM108"),
            "CDI BF-1": (f"{col_p18}105", "AM105"),
            "CDI BF-5": (f"{col_p18}107", "AM107"),
            "Fuel Rate": (f"{col_p18}156", "AM156"),
            "BF Productivity": (f"{col_p18}100", "AM100"),
            "Sinter% in Burden": (f"{col_p18}124", "AM124"),
            "Pellet% in Burden": (f"{col_p18}125", "AM125"),
            "Energy consumption": (f"{col_p18}340", "AM340"),
            "SMS-1 HM consumption per ton of crude steel": (f"{col_p18}163", "AM163"),
            "SMS-1 Scrap consumption per ton of crude steel": (f"{col_p18}164", "AM164"),
            "SMS-2 HM consumption per ton of crude steel": (f"{col_p18}190", "AM190"),
            "SMS-2 Scrap consumption per ton of crude steel": (f"{col_p18}191", "AM191"),
            "COB#6 Coke yield%": (f"{col_p18}21", "AM21"),
            "Oven heat Consumption per ton of Dry coke Input": (f"{col_p18}304", "AM304"),
            "COB-6 Dry Coal Charge per Oven": (f"{col_p18}17", "AM17"),
            "Coke oven tar yield": (f"{col_p18}27", "AM27"),
            "Coke oven Ammonia Sulphate yield": (f"{col_p18}28", "AM28"),
            "SP-1 Sinter Productivity": (f"{col_p18}38", "AM38"),
            "SP-2 Sinter Productivity": (f"{col_p18}58", "AM58"),
            "SP-3 Sinter Productivity": (f"{col_p18}81", "AM81"),
            "Coke Screen Loss": (f"{col_p18}31", "AM31"),
            "SMS-1 Avg Blows per day": (f"{col_p18}183", "AM183"),
            "SMS-2 Avg Blows per day": (f"{col_p18}213", "AM213"),
            "SMS-1 Avg heat wt": (f"{col_p18}174", "AM174"),
            "SMS-2 Avg heat wt": (f"{col_p18}203", "AM203"),
            "SMS-1 lining life": (f"{col_p18}213", "AM213"),
            "SMS-2 lining life": (f"{col_p18}205", "AM205"),
        }
        
        unit_map = {
            "Coal to Hot metal ratio": "--",
            "Coke Rate": "kg/thm",
            "Nut Coke Rate": "kg/thm",
            "CDI": "kg/thm",
            "Fuel Rate": "kg/thm",
            "BF Productivity": "t/m3/day",
            "Sinter% in Burden": "%",
            "Pellet% in Burden": "%",
            "Energy consumption": "Gcal/tcs",
            "SMS-1 HM consumption per ton of crude steel": "kg/tcs",
            "SMS-1 Scrap consumption per ton of crude steel": "kg/tcs",
            "SMS-2 HM consumption per ton of crude steel": "kg/tcs",
            "SMS-2 Scrap consumption per ton of crude steel": "kg/tcs",
        }
        
        for param, (month_cell, ytd_cell) in te_cells.items():
            raw_month_val = sheet_p18[month_cell].value
            month_val = clean_val(raw_month_val)
            
            raw_ytd_val = sheet_p18[ytd_cell].value
            ytd_val = clean_val(raw_ytd_val)
            
            if month_val is not None or ytd_val is not None:
                vals_extracted += 1
                
            unit = unit_map.get(param, "")
            
            cursor.execute("""
                INSERT INTO techno_table (report_month, plant_name, parameter_name, unit, month_actual, ytd_actual)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_month, plant_name, parameter_name) 
                DO UPDATE SET 
                    unit = excluded.unit,
                    month_actual = excluded.month_actual,
                    ytd_actual = excluded.ytd_actual
            """, (db_report_month, "RSP", param, unit, month_val, ytd_val))
            
        # Validation: Verify that we extracted some numeric values
        if vals_extracted == 0:
            raise ValueError(
                "No numeric data could be extracted from the expected cell locations in "
                "sheets 'page-9' and 'page 1-8'. Please verify the contents of the Excel file."
            )
            
        conn.commit()
        conn.close()
        logger.info(f"Custom coordinate RSP Excel parsing completed successfully for month {db_report_month}!")
        return True
            
    except ValueError as ve:
        logger.error(f"Validation error parsing Excel file: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        return False
