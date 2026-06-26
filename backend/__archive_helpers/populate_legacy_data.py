import sqlite3
import openpyxl
from pathlib import Path
import csv
from collections import defaultdict

# ================== CONFIG ==================
excel_path = "Report_format/Monthwise.xlsx"
db_path = "backend/mis_reports.db"

excel_file = Path(excel_path)
if not excel_file.exists():
    print(f"❌ Excel not found: {excel_file.absolute()}")
    exit(1)

# Target items mapping
target_items = {
    'Oven Pushing': 'Oven Pushing(nos/d)',
    'Sinter': 'Total Sinter',
    'Hot Metal': 'Hot Metal',
    'Crude Steel': 'Total Crude Steel',
    'Saleable Steel': 'Saleable Steel',
    'Pig Iron': 'Pig Iron',
    'Finished Steel': 'Finished Steel',
    'Total Crude': 'Total Crude Steel',
}

# Months in fiscal year order (Apr=start, Mar=end)
# April-December fall in the starting calendar year; Jan-March in the ending year
fy_start_months = {'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'}

_MONTH_NUM = {
    'April': '04', 'May': '05', 'June': '06', 'July': '07',
    'August': '08', 'September': '09', 'October': '10', 'November': '11',
    'December': '12', 'January': '01', 'February': '02', 'March': '03',
}

# ================== EXTRACTION ==================
print(f"Loading Excel: {excel_file.absolute()}")
wb = openpyxl.load_workbook(excel_file, data_only=True)
ws = wb['monthwise ']

extracted_data = []
current_item = None
current_plant = None

for row in ws.iter_rows(min_row=7, values_only=True):
    col0 = row[0]
    col1 = row[1]
    col2 = row[2]
    col3 = row[3]

    # Detect Item
    if col0 and isinstance(col0, str):
        col0_str = str(col0).strip()
        matched = next((v for k, v in target_items.items() if k.lower() in col0_str.lower()), None)
        current_item = matched or col0_str

    # Detect Plant
    if col1 and isinstance(col1, str):
        plant_str = col1.strip().upper()
        if plant_str in ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL', 'ASP', 'SSP', 'VISL']:
            current_plant = plant_str

    # Extract ALL Actual years
    if col2 == 'Actual' and current_item and current_plant and col3:
        year_str = str(col3).strip()
        if year_str and '-' in year_str:
            for col_idx, full_month in enumerate(['April', 'May', 'June', 'July', 'August', 'September',
                                                  'October', 'November', 'December', 'January', 'February', 'March'], start=4):
                if col_idx < len(row):
                    val = row[col_idx]
                    if val is not None and str(val).strip() != '':
                        try:
                            f_val = float(val)
                            start_year = int(year_str[:4])
                            cal_year = start_year if full_month in fy_start_months else start_year + 1
                            report_month = f"{cal_year}-{_MONTH_NUM[full_month]}"
                            extracted_data.append((report_month, current_plant, current_item, f_val))
                        except (ValueError, TypeError):
                            pass

print(f"\n✅ Extracted {len(extracted_data)} records.\n")

# ================== PREVIEW ==================
if extracted_data:
    print("=== SAMPLE DATA (first 10) ===")
    for rec in extracted_data[:10]:
        print(rec)

    summary = defaultdict(lambda: defaultdict(int))
    for rm, plant, item, _ in extracted_data:
        summary[plant][item] += 1

    print("\n=== SUMMARY BY PLANT ===")
    for plant in sorted(summary):
        print(f"\n{plant}:")
        for item, cnt in sorted(summary[plant].items()):
            print(f"   • {item}: {cnt} months")

# Save preview
with open("extracted_preview.csv", "w", newline="") as f:
    csv.writer(f).writerows([['report_month', 'plant_name', 'item_name', 'month_actual']] + extracted_data)

# ================== DATABASE ==================
proceed = input("\nDo you want to INSERT this data? (yes/no): ").strip().lower()

if proceed in ['yes', 'y']:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS production_table (
            report_month TEXT,
            plant_name TEXT,
            item_name TEXT,
            month_actual REAL,
            PRIMARY KEY (report_month, plant_name, item_name)
        )
    ''')

    insert_query = """
        INSERT OR IGNORE INTO production_table (report_month, plant_name, item_name, month_actual)
        VALUES (?, ?, ?, ?)
    """
    cursor.executemany(insert_query, extracted_data)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM production_table")
    total = cursor.fetchone()[0]
    print(f"\n🎉 Insertion completed! Total records: {total}")

    # Show sample with new format
    cursor.execute("SELECT * FROM production_table LIMIT 10")
    print("\n=== SAMPLE FROM DATABASE ===")
    for row in cursor.fetchall():
        print(row)

    conn.close()
else:
    print("Cancelled.")