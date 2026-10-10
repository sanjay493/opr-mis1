"""MoU month-wise production target workbook — "MoU YY-YY.xlsx"
(Report_format/ABP/), sheet "MoU YY-YY":

    row 3   "Items" | "Plant" | 12 month dates (Apr..Mar) | quarter/annual totals
    col A   item name, merged down its plant rows (Hot Metal, Crude Steel,
            Saleable Steel, Pig Iron, Finished Steel)
    col B   plant (BSP, DSP, RSP, BSL, ISP, ASP, SSP, VISL) or a total row
            ("SAIL - 5PL", "SAIL -5 PL", "SAIL", "SAIL ")

Only plant rows are kept; page 4 computes "5 Plants"/SAIL itself. The
file's own SAIL row is used as a check: a month where it differs from the
plant sum is reported as a warning. Month columns are found by their date
values and the header row by its labels, never by fixed positions.
Unit '000 T.
"""
import datetime
from typing import Dict, List, Optional, Tuple

import openpyxl

# Workbook item label (upper-cased, single-spaced) -> page-4 db_item name
ITEM_MAP = {
    "HOT METAL": "Hot Metal",
    "CRUDE STEEL": "Total Crude Steel",
    "SALEABLE STEEL": "Saleable Steel",
    "PIG IRON": "Pig Iron",
    "FINISHED STEEL": "Finished Steel",
}
PLANTS = ("BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL")
_SUM_TOLERANCE = 0.01


def _num(v) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        try:
            return float(s) if s else None
        except ValueError:
            return None
    return None


def _find_header(ws) -> Tuple[Optional[int], Dict[str, int]]:
    for r in range(1, 21):
        a, b = ws.cell(r, 1).value, ws.cell(r, 2).value
        if (isinstance(a, str) and a.strip().upper() == "ITEMS"
                and isinstance(b, str) and b.strip().upper() == "PLANT"):
            # Only the unbroken run of dates from column C: the sheet keeps a
            # side table further right with the previous FY's months.
            cols = {}
            c = 3
            while isinstance(ws.cell(r, c).value, datetime.datetime):
                v = ws.cell(r, c).value
                cols[f"{v.year}-{v.month:02d}"] = c
                c += 1
            return r, cols
    return None, {}


def extract_mou_plan(file_path: str) -> dict:
    """Parse a MoU workbook — no DB writes. Returns
        {"records": [{"report_month","plant_name","item_name","value"}, ...],
         "months": [...], "items_found": [...], "warnings": [...]}
    Raises ValueError if no sheet has the expected header or no plant rows."""
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws, hdr, month_cols = None, None, {}
    for sheet in wb.worksheets:
        hdr, month_cols = _find_header(sheet)
        if hdr and month_cols:
            ws = sheet
            break
    if ws is None:
        raise ValueError("No sheet with an 'Items' / 'Plant' header row and month columns was found.")

    warnings: List[str] = []
    if len(month_cols) != 12:
        warnings.append(f"Found {len(month_cols)} month columns, expected 12.")

    records: List[dict] = []
    items_found: List[str] = []
    sail_rows: Dict[str, int] = {}
    item = None
    for r in range(hdr + 1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        if isinstance(a, str) and a.strip():
            label = " ".join(a.split()).upper()
            item = ITEM_MAP.get(label)
            if item is None:
                warnings.append(f"Row {r}: item {a.strip()!r} not recognised; its rows were skipped.")
            elif item not in items_found:
                items_found.append(item)
        b = ws.cell(r, 2).value
        if item is None or not isinstance(b, str) or not b.strip():
            continue
        plant = b.strip().upper()
        if plant.startswith("SAIL"):
            if plant.replace(" ", "") == "SAIL":
                sail_rows[item] = r
            continue
        if plant not in PLANTS:
            warnings.append(f"Row {r}: plant {b.strip()!r} not recognised; skipped.")
            continue
        for month, col in month_cols.items():
            raw = ws.cell(r, col).value
            val = _num(raw)
            if val is None:
                if raw not in (None, ""):
                    warnings.append(f"{item} {plant} {month}: {raw!r} is not a number; skipped.")
                continue
            records.append({"report_month": month, "plant_name": plant, "item_name": item, "value": val})

    for it, r in sail_rows.items():
        for month, col in month_cols.items():
            file_total = _num(ws.cell(r, col).value)
            if file_total is None:
                continue
            plant_sum = sum(x["value"] for x in records if x["item_name"] == it and x["report_month"] == month)
            if abs(plant_sum - file_total) > _SUM_TOLERANCE:
                warnings.append(
                    f"{it} {month}: the file's SAIL row is {file_total:.3f} but its plants add up to "
                    f"{plant_sum:.3f}."
                )

    if not records:
        raise ValueError("No plant rows found under the 'Items' / 'Plant' header.")
    return {
        "records": records,
        "months": sorted(month_cols),
        "items_found": items_found,
        "warnings": warnings,
    }
