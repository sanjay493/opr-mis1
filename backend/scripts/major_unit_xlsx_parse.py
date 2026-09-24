"""
Shared source-workbook parsing for Annexure-III (5 ISPs Major Units
Records) — used by both verify_major_unit_best_records.py (Annual/Monthly
cross-check, no DB writes) and backfill_major_unit_daily_records.py (Daily
best, writes major_unit_daily_record). Kept in one place so a source
workbook's column layout is only ever hand-verified once — see BSP's own
note below about its layout having shifted mid-session on 2026-09-23.

Every parser returns {raw_label: [{'annual': (value, fy_label) | None,
'monthly': (value, mon_label) | None, 'daily': (value, date_str) | None,
'remarks': str | None}, ...]} — a LIST per raw label because a few sheets
print a group's 2nd+ sub-item with a bare label (e.g. BSP's "URM" appears
under both "Finished Rails" and "Prime Rails" with no group prefix on the
2nd occurrence) with no textual way to disambiguate; callers consume
matches in document (top-to-bottom) order.
"""
import os
import re

import openpyxl

SOURCE_DIR = r"I:\My Drive\Report_format\Plants Best"


def _f(v):
    """float(v), tolerating BSL's Daily Prod column occasionally embedding
    a unit suffix in the cell text itself (e.g. '22516 T', '4703 T') where
    every other plant's/column's cells are a plain number."""
    if isinstance(v, str):
        v = re.sub(r"\s*T\s*$", "", v.strip(), flags=re.IGNORECASE)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_bsl(path: str) -> dict:
    """'best Sheet': Unit | Annual Prod | Annual Year | Monthly Prod |
    Monthly Month | Daily Prod | Daily Date. Header rows 2-4, data from
    row 5."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    out = {}
    for row in ws.iter_rows(min_row=5, values_only=True):
        label = row[1] if len(row) > 1 else None
        if not label or not isinstance(label, str):
            continue
        annual = _f(row[2]); annual_fy = row[3]
        monthly = _f(row[4]); monthly_mon = row[5]
        daily = _f(row[6]) if len(row) > 6 else None
        daily_date = row[7] if len(row) > 7 else None
        if annual is None and monthly is None and daily is None:
            continue
        out.setdefault(label.strip(), []).append({
            "annual": (annual, str(annual_fy)) if annual is not None else None,
            "monthly": (monthly, str(monthly_mon)) if monthly is not None else None,
            "daily": (daily, str(daily_date)) if daily is not None else None,
            "remarks": None,
        })
    return out


def parse_rsp(path: str) -> dict:
    """Sheet1: Unit | Annual Prod | Annual Year | Monthly Prod | Monthly
    Month | Daily Prod | Daily Date. Header rows 1-3, data from row 4."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet1"]
    out = {}
    for row in ws.iter_rows(min_row=4, values_only=True):
        label = row[0]
        if not label or not isinstance(label, str):
            continue
        annual = _f(row[1]); annual_fy = row[2]
        monthly = _f(row[3]); monthly_mon = row[4]
        daily = _f(row[5]) if len(row) > 5 else None
        daily_date = row[6] if len(row) > 6 else None
        if annual is None and monthly is None and daily is None:
            continue
        out.setdefault(label.strip(), []).append({
            "annual": (annual, str(annual_fy)) if annual is not None else None,
            "monthly": (monthly, str(monthly_mon)) if monthly is not None else None,
            "daily": (daily, str(daily_date)) if daily is not None else None,
            "remarks": None,
        })
    return out


def parse_isp(path: str) -> dict:
    """'Since 2014 Data': Best Achieved block is the sheet's last 6
    columns — Annual(Production,Year), Monthly(Production,Month),
    Daily(Production,Day). Header rows 1-5, data from row 6. ISP's Daily
    cells are sometimes compound (two records combined in one cell, e.g.
    Oven Pushing's 'COB#10 - 103\\nCOB#11- 101' / '24.1.23\\n30.1.23') —
    kept as raw text in 'daily' rather than split, since it isn't a single
    clean value+date pair; callers should fall back to storing it as
    remarks when the value can't be parsed as a plain number."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Since 2014 Data"]
    out = {}
    for row in ws.iter_rows(min_row=6, values_only=True):
        label = row[1]
        if not label or not isinstance(label, str):
            continue
        label = label.replace("\n", " ").strip()
        vals = list(row[-6:])
        annual = _f(vals[0]); annual_fy = vals[1]
        monthly = _f(vals[2]); monthly_mon = vals[3]
        daily_raw, daily_date_raw = vals[4], vals[5]
        if annual is None and monthly is None and daily_raw is None:
            continue
        out.setdefault(label, []).append({
            "annual": (annual, str(annual_fy)) if annual is not None else None,
            "monthly": (monthly, str(monthly_mon)) if monthly is not None else None,
            "daily": (daily_raw, daily_date_raw),  # may be compound text — see docstring
            "remarks": None,
        })
    return out


def parse_bsp(path: str) -> dict:
    """'BSP Records': Unit | Day Prod | Day Date | Month Prod | Month
    Month | Annual Prod | Annual Year | Remarks | ... Header spans rows
    3-5, data from row 6.

    NOTE: this workbook is live Google-Drive-synced and had 2 extra
    leading columns (CU%/"2025-26 Likely") on this feature's first read
    this session (2026-09-23) that were gone by a later read the same
    session, shifting every column left by 2 — column positions below
    match the CURRENT (post-edit) layout. If this ever looks wrong again,
    re-dump ws.iter_rows(min_row=1, max_row=6, values_only=True) fresh
    before trusting these indices."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["BSP Records"]
    out = {}
    for row in ws.iter_rows(min_row=6, values_only=True):
        label = row[1]
        if not label or not isinstance(label, str):
            continue
        label = label.replace("\n", " ").strip()
        daily = _f(row[2]); daily_date = row[3]
        monthly = _f(row[4]); monthly_mon = row[5]
        annual = _f(row[6]); annual_fy = row[7]
        remarks = row[8] if len(row) > 8 else None
        if annual is None and monthly is None and daily is None:
            continue
        out.setdefault(label, []).append({
            "annual": (annual, str(annual_fy)) if annual is not None else None,
            "monthly": (monthly, str(monthly_mon)) if monthly is not None else None,
            "daily": (daily, str(daily_date)) if daily is not None else None,
            "remarks": remarks if isinstance(remarks, str) else None,
        })
    return out


PARSERS = {"BSL": parse_bsl, "RSP": parse_rsp, "ISP": parse_isp, "BSP": parse_bsp}

# Registry label -> raw workbook label, only where they genuinely differ in
# wording (not just whitespace/casing) or where a group's bare 2nd+
# sub-item needs disambiguating (see parse_bsp's docstring / callers'
# document-order list consumption) — (plant, registry_label) -> raw_label.
ALIASES = {
    ("BSL", "Equiv. Oven Pushing"): "Oven Pushing (Nos./day)",
    ("BSL", "Saleable Steel"): "Sal. Steel",
    ("ISP", "Equiv. Oven Pushing"): "Oven Pushing (Nos/Day)",
    # Registry labels below were made uniform across plants on 2026-09-24
    # (see page_major_unit_records.py's module docstring); each plant's
    # source workbook still has its own original wording, so those now
    # need an alias where they didn't before.
    ("ISP", "Total Sinter"): "Sinter",
    ("ISP", "Total Hot Metal"): "Hot Metal",
    ("ISP", "Total Crude Steel"): "Crude Steel",
    ("ISP", "Finished Steel"): "FIN. STEEL",
    ("ISP", "Saleable Steel Despatch"): "Saleable Steel loading",
    ("RSP", "Equiv. Oven Pushing"): "Eqvt. Oven Pushing",
    ("RSP", "Total Sinter"): "Sinter - Total",
    ("RSP", "Total Hot Metal"): "Hot Metal",
    ("RSP", "Total Crude Steel"): "Crude Steel - Total",
    ("BSP", "COB-11 (Pushings/day)"): "COB-11 (No. of Pushings/day)",
    ("BSP", "Equiv. Oven Pushing"): "Eq. Oven Pushing (Nos./day)",
    ("BSP", "Finished Steel"): "Total Finished Steel",
    ("BSP", "Saleable Steel"): "Total Saleable Steel",
    ("BSP", "Finished Rails: URM"): "URM",
    ("BSP", "Prime Rails: URM"): "URM",
}


def take_row(wb_data: dict, plant: str, registry_label: str):
    """Consume (pop) the next workbook row matching registry_label for
    `plant` — aliasing + loose (case/whitespace) matching, list-consumed in
    document order for a bare duplicate label. Returns None if no row is
    left to match."""
    raw_label = ALIASES.get((plant, registry_label), registry_label)
    bucket = wb_data.get(raw_label)
    if bucket is None:
        cand = [k for k in wb_data
                if k.lower().replace(" ", "") == raw_label.lower().replace(" ", "")]
        bucket = wb_data.get(cand[0]) if cand else None
    if not bucket:
        return None
    return bucket.pop(0)
