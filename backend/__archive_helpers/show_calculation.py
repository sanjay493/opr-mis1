#!/usr/bin/env python3
"""
Show detailed step-by-step calculation for SAIL SMS parameters
"""

import sqlite3
from collections import defaultdict

DB_PATH = 'mis_reports.db'
month = '2026-03'

SMS_SHOPS = [
    'BSP SMS-2', 'BSP SMS-3', 'DSP SMS',
    'RSP SMS-1', 'RSP SMS-2',
    'BSL SMS-1', 'BSL SMS-2',
    'ISP SMS-1',
]

SMS_SHOP_PLANT = {
    'BSP SMS-2': 'BSP', 'BSP SMS-3': 'BSP', 'DSP SMS': 'DSP',
    'RSP SMS-1': 'RSP', 'RSP SMS-2': 'RSP',
    'BSL SMS-1': 'BSL', 'BSL SMS-2': 'BSL', 'ISP SMS-1': 'ISP',
}

print('='*80)
print('SAIL SMS PARAMETER CALCULATION - DETAILED STEPS')
print('='*80)
print(f'Month: {month}\n')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Step 1: Get SMS shop values
print('STEP 1: Get SMS Shop Values')
print('-'*80)

cursor.execute(f'''
    SELECT p.row_label, p.param_name, a.actual, a.till_month_actual
    FROM techno_actuals a
    JOIN techno_param p ON a.param_id = p.param_id
    WHERE p.param_name = 'Hot Metal Consumption'
        AND a.report_month = ?
        AND p.row_label IN ({','.join(['?']*len(SMS_SHOPS))})
    ORDER BY p.row_label
''', [month] + SMS_SHOPS)

shop_values = {}
for shop, param_name, actual, till_month in cursor.fetchall():
    shop_values[shop] = (actual, till_month)
    print(f'  {shop:<15}: Monthly={actual:<10.2f}  YTD={till_month:.2f}')

# Step 2: Get Crude Steel Production
print('\n\nSTEP 2: Get Crude Steel Production')
print('-'*80)

cursor.execute('''
    SELECT plant_name, month_actual
    FROM production_table
    WHERE item_name = 'Total Crude Steel'
        AND report_month = ?
''', (month,))

cs_monthly = {}
total_cs_monthly = 0
for plant, value in cursor.fetchall():
    if value is not None:
        cs_monthly[plant] = value
        total_cs_monthly += value

print('Monthly Crude Steel Production (T):')
for plant, cs in sorted(cs_monthly.items()):
    pct = (cs / total_cs_monthly * 100) if total_cs_monthly > 0 else 0
    print(f'  {plant:<10}: {cs:>10.3f} T ({pct:>5.1f}%)')
print(f'  TOTAL     : {total_cs_monthly:>10.3f} T (100.0%)')

# Get YTD Crude Steel
print('\n\nYTD Crude Steel Production (Apr to Mar):')
print('-'*80)

ytd_months = ['2025-04', '2025-05', '2025-06', '2025-07', '2025-08', '2025-09',
              '2025-10', '2025-11', '2025-12', '2026-01', '2026-02', '2026-03']

cursor.execute(f'''
    SELECT plant_name, SUM(month_actual) as ytd_cs
    FROM production_table
    WHERE item_name = 'Total Crude Steel'
        AND report_month IN ({','.join(['?']*len(ytd_months))})
    GROUP BY plant_name
''', ytd_months)

cs_ytd = {}
total_cs_ytd = 0
for plant, value in cursor.fetchall():
    if value is not None:
        cs_ytd[plant] = value
        total_cs_ytd += value

print('YTD Crude Steel:')
for plant, cs in sorted(cs_ytd.items()):
    pct = (cs / total_cs_ytd * 100) if total_cs_ytd > 0 else 0
    print(f'  {plant:<10}: {cs:>10.3f} T ({pct:>5.1f}%)')
print(f'  TOTAL     : {total_cs_ytd:>10.3f} T (100.0%)')

# Step 3: Calculate Plant Averages
print('\n\nSTEP 3: Calculate Plant Averages (Group SMS shops by plant)')
print('-'*80)

by_plant = defaultdict(list)
for shop, (actual, till_month) in shop_values.items():
    plant = SMS_SHOP_PLANT[shop]
    by_plant[plant].append((shop, actual, till_month))

plant_averages = {}
for plant in sorted(by_plant.keys()):
    shops_data = by_plant[plant]
    monthly_values = [v[1] for v in shops_data]
    ytd_values = [v[2] for v in shops_data]

    avg_monthly = sum(monthly_values) / len(monthly_values)
    avg_ytd = sum(ytd_values) / len(ytd_values)

    plant_averages[plant] = (avg_monthly, avg_ytd)

    shop_list = ' + '.join([s[0] for s in shops_data])
    print(f'\n{plant}:')
    print(f'  Shops: {len(shops_data)} ({shop_list})')
    for shop, actual, till in shops_data:
        print(f'    {shop}: monthly={actual:.2f}, ytd={till:.2f}')
    print(f'  PLANT AVERAGE:')
    print(f'    Monthly: {avg_monthly:.2f}')
    print(f'    YTD:     {avg_ytd:.2f}')

# Step 4: Calculate Weighted Averages
print('\n\nSTEP 4: Calculate Weighted Averages')
print('-'*80)

print('\nMonthly Weighted Average Formula:')
print('SAIL_monthly = Sum(Plant_Avg_Monthly * Plant_CS_Monthly) / Sum(Plant_CS_Monthly)\n')

monthly_sum = 0
total_cs_for_plants = 0
print('Calculation (only plants with SMS data):')
for plant in sorted(plant_averages.keys()):
    avg_monthly, _ = plant_averages[plant]
    cs = cs_monthly.get(plant, 0)
    contribution = avg_monthly * cs
    monthly_sum += contribution
    total_cs_for_plants += cs
    print(f'  {plant}: {avg_monthly:>8.2f} × {cs:>10.3f} = {contribution:>12.2f}')

print(f'\n  Sum: {monthly_sum:>60.2f}')
print(f'  Denominator (Total CS for SMS plants): {total_cs_for_plants:.3f}')

sail_monthly = monthly_sum / total_cs_for_plants if total_cs_for_plants > 0 else None

print(f'\n  SAIL Monthly = {monthly_sum:.2f} / {total_cs_for_plants:.3f}')
print(f'  SAIL Monthly = {sail_monthly:.10f} Kg/TCS')

# YTD Calculation
print('\n\nYTD Weighted Average Formula:')
print('SAIL_YTD = Sum(Plant_Avg_YTD * Plant_CS_YTD) / Sum(Plant_CS_YTD)\n')

ytd_sum = 0
total_cs_ytd_for_plants = 0
print('Calculation (only plants with SMS data):')
for plant in sorted(plant_averages.keys()):
    _, avg_ytd = plant_averages[plant]
    cs = cs_ytd.get(plant, 0)
    contribution = avg_ytd * cs
    ytd_sum += contribution
    total_cs_ytd_for_plants += cs
    print(f'  {plant}: {avg_ytd:>8.2f} × {cs:>10.3f} = {contribution:>12.2f}')

print(f'\n  Sum: {ytd_sum:>60.2f}')
print(f'  Denominator (Total CS YTD for SMS plants): {total_cs_ytd_for_plants:.3f}')

sail_ytd = ytd_sum / total_cs_ytd_for_plants if total_cs_ytd_for_plants > 0 else None

print(f'\n  SAIL YTD = {ytd_sum:.2f} / {total_cs_ytd_for_plants:.3f}')
print(f'  SAIL YTD = {sail_ytd:.10f} Kg/TCS')

# Step 5: Final Result
print('\n\n' + '='*80)
print('FINAL CALCULATED SAIL RESULT')
print('='*80)
print(f'Hot Metal Consumption (Monthly): {sail_monthly:.10f} Kg/TCS')
print(f'Hot Metal Consumption (YTD):     {sail_ytd:.10f} Kg/TCS')
print('='*80)

conn.close()
