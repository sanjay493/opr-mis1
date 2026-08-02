"""
Finished Steel — month-wise, unit(plant)-wise CSV export.

One row per report_month, one column per plant (+ SAIL total), values from
production_table where item_name='Finished Steel'. Plain CSV (not a page in
the 1-40 report) — a standalone downloadable listing, same shape as the
month-wise/plant-wise data already reviewed in Report_format/
finished_steel_month_plant_wise.csv.
"""
import csv
import io

import db

_PLANT_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL", "SAIL"]


def build_finished_steel_report_csv() -> bytes:
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT report_month, plant_name, month_actual
            FROM production_table
            WHERE item_name = 'Finished Steel'
            ORDER BY report_month
        """)
        rows = cur.fetchall()
    finally:
        conn.close()

    pivot = {}
    for month, plant, value in rows:
        pivot.setdefault(month, {})[plant] = value

    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel reads UTF-8 correctly
    w = csv.writer(buf)
    w.writerow(["Report Month"] + _PLANT_ORDER)
    for month in sorted(pivot):
        row = [month]
        for plant in _PLANT_ORDER:
            v = pivot[month].get(plant)
            row.append("" if v is None else round(v, 3))
        w.writerow(row)

    return buf.getvalue().encode("utf-8")
