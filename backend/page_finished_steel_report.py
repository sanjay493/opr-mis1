"""
Production item — month-wise, unit(plant)-wise view + CSV export.

One row per report_month, one column per plant (+ SAIL total), values from
production_table for a selected item. Originally Finished Steel only (hence
the module / endpoint names); now the item is selectable on the
/reports/finished-steel page: Oven Pushing, Sinter, Hot Metal, Crude Steel,
Pig Iron, Finished Steel, Saleable Steel.

Plain CSV (not a page in the 1-40 report) — a standalone downloadable
listing, same shape as Report_format/finished_steel_month_plant_wise.csv.
"""
import csv
import io

import db
from constants import ALL_PLANTS as _SAIL_8

_PLANT_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL", "SAIL"]

# Dropdown order. Each: display key -> production_table item_name(s), tried in
# order (Oven Pushing is stored under two spellings across plants/months).
ITEMS = [
    ("Oven Pushing",   ["Oven Pushing (nos/day)", "Oven Pushing(nos/d)"]),
    ("Sinter",         ["Total Sinter"]),
    ("Hot Metal",      ["Hot Metal"]),
    ("Crude Steel",    ["Total Crude Steel"]),
    ("Pig Iron",       ["Pig Iron"]),
    ("Finished Steel", ["Finished Steel"]),
    ("Saleable Steel", ["Saleable Steel"]),
]
_ITEM_ALIASES = {key: aliases for key, aliases in ITEMS}
_ITEM_KEYS = [key for key, _ in ITEMS]
DEFAULT_ITEM = "Finished Steel"


def resolve_item(item: str | None) -> str:
    """Validate a requested item key, falling back to the default."""
    return item if item in _ITEM_ALIASES else DEFAULT_ITEM


def _fy_months(fy_start: int) -> list:
    """2026 -> ["2026-04", ..., "2026-12", "2027-01", "2027-02", "2027-03"]"""
    return [f"{fy_start}-{m:02d}" for m in range(4, 13)] + \
           [f"{fy_start + 1}-{m:02d}" for m in range(1, 4)]


def _item_pivot(item: str, months: list = None) -> dict:
    """-> {report_month: {plant: value}}, optionally scoped to `months`.

    The SAIL column is always the live sum of whichever unit figures are
    present that month (never production_table's own stored 'SAIL' row —
    that snapshot goes stale whenever a unit's figure is later corrected or
    added). Items differ in how many units report: Oven Pushing / Sinter /
    Hot Metal / Pig Iron ~5, Crude Steel ~7, Finished / Saleable Steel ~8."""
    aliases = _ITEM_ALIASES[resolve_item(item)]
    alias_phs = ",".join("?" for _ in aliases)
    conn = db.connect()
    cur = conn.cursor()
    try:
        if months is not None:
            month_phs = ",".join("?" for _ in months)
            cur.execute(f"""
                SELECT report_month, plant_name, item_name, month_actual
                FROM production_table
                WHERE item_name IN ({alias_phs}) AND report_month IN ({month_phs})
                ORDER BY report_month
            """, list(aliases) + list(months))
        else:
            cur.execute(f"""
                SELECT report_month, plant_name, item_name, month_actual
                FROM production_table
                WHERE item_name IN ({alias_phs})
                ORDER BY report_month
            """, list(aliases))
        rows = cur.fetchall()
    finally:
        conn.close()

    # alias priority: first spelling in the list wins when a plant/month has both
    alias_rank = {name: i for i, name in enumerate(aliases)}
    best_rank = {}
    pivot = {}
    for month, plant, item_name, value in rows:
        if value is None:
            continue
        rank = alias_rank.get(item_name, len(aliases))
        if (month, plant) in best_rank and best_rank[(month, plant)] <= rank:
            continue
        best_rank[(month, plant)] = rank
        pivot.setdefault(month, {})[plant] = value

    for month, by_plant in pivot.items():
        present = [by_plant[p] for p in _SAIL_8 if by_plant.get(p) is not None]
        by_plant["SAIL"] = round(sum(present), 3) if present else None

    return pivot


def build_finished_steel_report_csv(fy_start: int = None, item: str = DEFAULT_ITEM) -> bytes:
    """Full history (fy_start=None) or one financial year's rows only."""
    item = resolve_item(item)
    months = _fy_months(fy_start) if fy_start is not None else None
    pivot = _item_pivot(item, months)

    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel reads UTF-8 correctly
    w = csv.writer(buf)
    w.writerow([f"Report Month ({item})"] + _PLANT_ORDER)
    for month in sorted(months) if months is not None else sorted(pivot):
        row = [month]
        for plant in _PLANT_ORDER:
            v = pivot.get(month, {}).get(plant)
            row.append("" if v is None else round(v, 3))
        w.writerow(row)

    return buf.getvalue().encode("utf-8")


def list_finished_steel_fys(item: str = DEFAULT_ITEM) -> list:
    """Financial years that have at least one figure for `item`.
    -> [{"fy_start": 2026, "label": "2026-27"}, ...] (newest first)."""
    aliases = _ITEM_ALIASES[resolve_item(item)]
    alias_phs = ",".join("?" for _ in aliases)
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT report_month FROM production_table
        WHERE item_name IN ({alias_phs})
          AND report_month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
    """, list(aliases))
    fy_starts = set()
    for (m,) in cur.fetchall():
        year, month = int(m[:4]), int(m[5:7])
        fy_starts.add(year if month >= 4 else year - 1)
    conn.close()
    return [
        {"fy_start": y, "label": f"{y}-{str(y + 1)[2:]}"}
        for y in sorted(fy_starts, reverse=True)
    ]


def build_finished_steel_fy_data(fy_start: int, item: str = DEFAULT_ITEM) -> dict:
    """One financial year's figures for `item`, month-wise/plant-wise, for the
    on-screen table (see build_finished_steel_report_csv for the CSV
    equivalent — same pivot/SAIL-fallback logic, just JSON-shaped)."""
    item = resolve_item(item)
    months = _fy_months(fy_start)
    pivot = _item_pivot(item, months)

    rows = {}
    for m in months:
        by_plant = pivot.get(m, {})
        rows[m] = {p: (round(v, 3) if (v := by_plant.get(p)) is not None else None) for p in _PLANT_ORDER}

    return {
        "fy_start": fy_start,
        "fy_label": f"{fy_start}-{str(fy_start + 1)[2:]}",
        "item": item,
        "items": _ITEM_KEYS,
        "months": months,
        "plants": _PLANT_ORDER,
        "rows": rows,
    }
