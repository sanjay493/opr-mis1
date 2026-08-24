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
from constants import ALL_PLANTS as _SAIL_8

_PLANT_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL", "SAIL"]


def _fy_months(fy_start: int) -> list:
    """2026 -> ["2026-04", ..., "2026-12", "2027-01", "2027-02", "2027-03"]"""
    return [f"{fy_start}-{m:02d}" for m in range(4, 13)] + \
           [f"{fy_start + 1}-{m:02d}" for m in range(1, 4)]


def _finished_steel_pivot(months: list = None) -> dict:
    """-> {report_month: {plant: value}}, optionally scoped to `months`.
    SAIL's stored row is a separately-saved snapshot that goes stale
    whenever a constituent plant's own figure is corrected or added after
    the fact — mirrors page7_13.py's _live_sum_or_sail_fallback. Prefer a
    live sum of the 8 plants for months where all of them have data;
    otherwise leave the stored SAIL value (or blank) as-is."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        if months is not None:
            phs = ",".join("?" for _ in months)
            cur.execute(f"""
                SELECT report_month, plant_name, month_actual
                FROM production_table
                WHERE item_name = 'Finished Steel' AND report_month IN ({phs})
                ORDER BY report_month
            """, months)
        else:
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

    for month, by_plant in pivot.items():
        plant_vals = [by_plant.get(p) for p in _SAIL_8]
        if all(v is not None for v in plant_vals):
            by_plant["SAIL"] = sum(plant_vals)

    return pivot


def build_finished_steel_report_csv(fy_start: int = None) -> bytes:
    """Full history (fy_start=None) or one financial year's rows only."""
    months = _fy_months(fy_start) if fy_start is not None else None
    pivot = _finished_steel_pivot(months)

    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel reads UTF-8 correctly
    w = csv.writer(buf)
    w.writerow(["Report Month"] + _PLANT_ORDER)
    for month in sorted(months) if months is not None else sorted(pivot):
        row = [month]
        for plant in _PLANT_ORDER:
            v = pivot.get(month, {}).get(plant)
            row.append("" if v is None else round(v, 3))
        w.writerow(row)

    return buf.getvalue().encode("utf-8")


def list_finished_steel_fys() -> list:
    """Financial years that have at least one 'Finished Steel' figure.
    -> [{"fy_start": 2026, "label": "2026-27"}, ...] (newest first)."""
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT report_month FROM production_table
        WHERE item_name = 'Finished Steel'
          AND report_month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
    """)
    fy_starts = set()
    for (m,) in cur.fetchall():
        year, month = int(m[:4]), int(m[5:7])
        fy_starts.add(year if month >= 4 else year - 1)
    conn.close()
    return [
        {"fy_start": y, "label": f"{y}-{str(y + 1)[2:]}"}
        for y in sorted(fy_starts, reverse=True)
    ]


def build_finished_steel_fy_data(fy_start: int) -> dict:
    """One financial year's Finished Steel, month-wise/plant-wise, for the
    on-screen table (see build_finished_steel_report_csv for the CSV
    equivalent — same pivot/SAIL-fallback logic, just JSON-shaped)."""
    months = _fy_months(fy_start)
    pivot = _finished_steel_pivot(months)

    rows = {}
    for m in months:
        by_plant = pivot.get(m, {})
        rows[m] = {p: (round(v, 3) if (v := by_plant.get(p)) is not None else None) for p in _PLANT_ORDER}

    return {
        "fy_start": fy_start,
        "fy_label": f"{fy_start}-{str(fy_start + 1)[2:]}",
        "months": months,
        "plants": _PLANT_ORDER,
        "rows": rows,
    }
