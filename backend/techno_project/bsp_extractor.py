"""
BSP 3-page-Tech.xlsx extractor.

Sheet layout (Sheet1):
  Row 3, Col A : month name, e.g. "MAY"
  Row 4, Cols D-O (1-based cols 4-15): APR … MAR
  Row 4, Col P (col 16): cumulative header ("ACTUAL" or "CUM")
  Col layout is FIXED — April always = col 4, May = col 5, … Mar = col 15, Cum = col 16

Row numbers come from bsp_techno_map.json (editable without touching Python).
Records are stored in techno_data with plant='BSP'.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "excel_extractors"))
from excel_extractor_bsp import _open_workbook  # noqa: E402 — handles legacy .xls via xlrd

_MONTH_NUM_TO_ABBR = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
}
_MONTH_ABBR_TO_NUM = {v: k for k, v in _MONTH_NUM_TO_ABBR.items()}

# Fixed column index (1-based) for each month in the BSP 3-page-tech format
_MONTH_NUM_TO_COL: Dict[int, int] = {
    4: 4,  5: 5,  6: 6,  7: 7,  8: 8,  9: 9,
    10: 10, 11: 11, 12: 12, 1: 13, 2: 14, 3: 15,
}
_CUM_COL = 16   # Column P = always cumulative (Apr → report month)

_BAD = {"#DIV/0!", "#VALUE!", "-", "--", None, ""}

_MAP_PATH = Path(__file__).parent / "bsp_techno_map.json"

# Heat Cons./Power Cons./Gross Energy Consumption block — resolved by label
# search instead of trusting bsp_techno_map.json's fixed row numbers. Two
# real file-layout variants circulate for the same "3 page Tech for CO_..."
# filename convention: one with "BAR AND ROD MILL" inserted inline within
# this block (shifting every row below it), one with it appended at the very
# end of the sheet — confirmed via bsp_techno_map.json's rows silently
# extracting the WRONG mill's data when fed the inline-variant file (RSM's
# row returning Merchant Mill's figure, etc.), since the map is calibrated
# to the append-variant. The labels themselves are stable across both
# variants, so a bounded-window keyword search (same technique already used
# for BSL's Sheet4 and RSP's furnace blocks) makes extraction correct
# regardless of which variant is uploaded.
# (unit, param_key) -> (block anchor header, label keyword)
_HEAT_POWER_ENERGY_SEARCH = {
    ("RSM", "heat_consumption"):  ("heat cons", "rail"),
    ("URM", "heat_consumption"):  ("heat cons", "urm"),
    ("MM",  "heat_consumption"):  ("heat cons", "merchant"),
    ("WRM", "heat_consumption"):  ("heat cons", "wire rod"),
    ("PM",  "heat_consumption"):  ("heat cons", "plate"),
    ("RSM", "power_consumption"): ("power cons", "rail"),
    ("URM", "power_consumption"): ("power cons", "urm"),
    ("MM",  "power_consumption"): ("power cons", "merchant"),
    ("WRM", "power_consumption"): ("power cons", "wire rod"),
    ("PM",  "power_consumption"): ("power cons", "plate"),
    ("General", "specific_energy_consumption"): (None, "gross energy"),
}


def _find_row(ws, start_row: int, end_row: int, keyword: str) -> Optional[int]:
    """First row (1-based, inclusive range) whose column-A label contains
    `keyword` (case-insensitive)."""
    for r in range(start_row, min(end_row, ws.max_row) + 1):
        label = str(ws.cell(r, 1).value or "").strip().lower()
        if keyword in label:
            return r
    return None


def _resolve_search_rows(ws) -> Dict:
    """Resolve every (unit, param_key) in _HEAT_POWER_ENERGY_SEARCH to an
    actual row number for this specific file, searching a generous window
    rather than trusting a fixed row. Falls back to None (caller keeps the
    map's row and logs a warning) if a label can't be found."""
    heat_header  = _find_row(ws, 1, ws.max_row, "heat cons")
    power_header = _find_row(ws, (heat_header or 1) + 1, ws.max_row, "power cons")
    block_end    = _find_row(ws, (power_header or 1) + 1, ws.max_row, "gross energy")

    resolved = {}
    for (unit, param_key), (anchor, keyword) in _HEAT_POWER_ENERGY_SEARCH.items():
        if anchor == "heat cons" and heat_header and power_header:
            row = _find_row(ws, heat_header + 1, power_header - 1, keyword)
        elif anchor == "power cons" and power_header:
            row = _find_row(ws, power_header + 1, (block_end or power_header + 30) - 1, keyword)
        elif anchor is None:  # Gross Energy Consumption itself
            row = block_end
        else:
            row = None
        if row is not None:
            resolved[(unit, param_key)] = row
    return resolved


def _load_map() -> Dict:
    try:
        with open(_MAP_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    except FileNotFoundError:
        raise FileNotFoundError(f"bsp_techno_map.json not found at {_MAP_PATH}")


def _clean(v) -> Optional[float]:
    if v in _BAD:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in _BAD:
        return None
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _detect_report_month(ws, report_month: Optional[str]) -> str:
    """Return 'YYYY-MM' — prefer explicit parameter, fall back to cell A3 + FY guess."""
    if report_month:
        return report_month

    raw = str(ws.cell(3, 1).value or "").strip().upper()
    mon_num = None
    for abbr, num in _MONTH_ABBR_TO_NUM.items():
        if abbr.upper() in raw:
            mon_num = num
            break
    if mon_num is None:
        raise ValueError("Cannot detect month from cell A3. Pass report_month explicitly.")

    # Guess year from today — caller should always pass report_month anyway
    import datetime
    today = datetime.date.today()
    # If detected month ≥ April, assume current FY start year; else next calendar year
    year = today.year
    return f"{year}-{mon_num:02d}"


class BspTechnoExtractor:
    def __init__(self, excel_file: str, report_month: Optional[str] = None):
        self.excel_file = Path(excel_file)
        self.report_month = report_month
        self._map = _load_map()

    def extract(self) -> List[Dict]:
        wb = _open_workbook(str(self.excel_file))

        # Find Sheet1
        ws = None
        for name in wb.sheetnames:
            if name.strip().lower() in ("sheet1", "sheet 1"):
                ws = wb[name]
                break
        if ws is None:
            ws = wb.active

        report_month = _detect_report_month(ws, self.report_month)
        month_num = int(report_month.split("-")[1])

        if month_num not in _MONTH_NUM_TO_COL:
            raise ValueError(f"Month {month_num} not in fixed column map")
        month_col = _MONTH_NUM_TO_COL[month_num]
        cum_col = _CUM_COL

        # Verify col header in row 4 matches expected month abbreviation
        expected_abbr = _MONTH_NUM_TO_ABBR.get(month_num, "").upper()
        actual_hdr = str(ws.cell(4, month_col).value or "").strip().upper()
        if actual_hdr != expected_abbr:
            print(
                f"[BSP-TechnoExtractor] Warning: expected '{expected_abbr}' in row 4 col {month_col}, "
                f"found '{actual_hdr}'. Verify bsp_techno_map.json row numbers."
            )

        search_rows = _resolve_search_rows(ws)

        records = []
        for unit_name, params in self._map.items():
            techno = {"month": {}, "till_month": {}}
            for param_key, row_num in params.items():
                search_key = (unit_name, param_key)
                if search_key in _HEAT_POWER_ENERGY_SEARCH:
                    found_row = search_rows.get(search_key)
                    if found_row is not None:
                        row_num = found_row
                    else:
                        print(
                            f"[BSP-TechnoExtractor] Warning: label search failed for "
                            f"{unit_name}/{param_key} — falling back to bsp_techno_map.json "
                            f"row {row_num}, which may not match this file's layout."
                        )
                try:
                    month_val = _clean(ws.cell(row_num, month_col).value)
                    till_val  = _clean(ws.cell(row_num, cum_col).value)
                    if till_val is None and month_val is not None and month_num == 4:
                        # April is FY month 1, so cumulative April->April is
                        # always identical to the month value — some report
                        # preparers leave the Cum column blank for it (same
                        # convention already handled in
                        # pdf_extractor_bsp_flash.py's _text_param).
                        till_val = month_val
                    techno["month"][param_key]     = month_val
                    techno["till_month"][param_key] = till_val
                except Exception as e:
                    print(f"[BSP-TechnoExtractor] Warning: row {row_num} / {param_key}: {e}")

            if any(v is not None for v in techno["month"].values()):
                records.append({
                    "report_month": report_month,
                    "plant":        "BSP",
                    "unit":         unit_name,
                    "techno_json":  techno,
                })
                print(f"  Extracted: {unit_name}")

        print(f"[BSP-TechnoExtractor] {len(records)} units extracted for {report_month}")
        return records
