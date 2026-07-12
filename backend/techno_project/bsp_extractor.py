"""
BSP 3-page-Tech.xlsx extractor.

Sheet layout (Sheet1):
  Row 3, Col A : month name, e.g. "MAY"
  Row 4           : APR … MAR month headers, followed by a cumulative header
                    ("ACTUAL"/"CUM"). Column positions are NOT fixed across
                    real files — some editions insert an extra "ABP/Norm"
                    column right before APR, shifting every month (and the
                    cumulative column) one to the right. Month columns are
                    therefore resolved per-file by searching row 4's header
                    text (see `_resolve_month_columns`); the old fixed
                    _MONTH_NUM_TO_COL mapping is kept only as a last-resort
                    fallback if that search somehow finds nothing.

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

def _resolve_month_columns(ws) -> Dict[int, int]:
    """Map calendar month number -> column index (1-based) by searching row
    4's header text for each month abbreviation, instead of trusting a fixed
    position. Confirmed necessary: some real files insert an extra
    "ABP/Norm" column before APR, shifting every month column one to the
    right relative to files where APR sits directly at column 4."""
    mapping: Dict[int, int] = {}
    max_c = min(ws.max_column or 40, 40)
    for c in range(1, max_c + 1):
        label = str(ws.cell(4, c).value or "").strip().upper()
        for abbr, num in _MONTH_ABBR_TO_NUM.items():
            if label == abbr.upper() and num not in mapping:
                mapping[num] = c
                break
    return mapping


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


_BF_COKE_LABEL = "bf coke"
_FY_ORDER = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]


def _find_bf_coke_row(ws, month_cols: Dict[int, int]) -> Optional[int]:
    """Row for the genuine "BF Coke" yield data row (a Yield-from-coal-charge
    sub-item) — distinguished from header-like rows sharing the same
    substring (e.g. "Av. Ash in BF Coke") by requiring real numeric data in
    at least one resolved month column."""
    check_cols = list(month_cols.values()) or list(range(4, 17))
    for r in range(1, ws.max_row + 1):
        label = str(ws.cell(r, 1).value or "").strip().lower()
        if _BF_COKE_LABEL not in label:
            continue
        if any(_clean(ws.cell(r, c).value) is not None for c in check_cols):
            return r
    return None


def _detect_actual_report_month(ws, month_cols: Dict[int, int]) -> Optional[int]:
    """The true last non-blank month column — scanned across the FULL FY
    (never capped at the selected month), via the "BF Coke" row, using the
    same last-non-blank-column technique as RSP's production/technopara
    sheets. Scanning the whole FY rather than stopping at the selected month
    is what lets this catch mismatches in BOTH directions: a selected month
    later than the file's real content (later columns are genuinely blank)
    and — the case a capped scan would miss — a selected month earlier than
    the file's real content (real data exists past the selected column,
    since a capped scan would only ever "confirm" whatever was selected)."""
    target_row = _find_bf_coke_row(ws, month_cols)
    if target_row is None:
        return None

    last_found = None
    for m in _FY_ORDER:
        # Only consider months whose header was actually found in row 4 — a
        # month missing from month_cols means this file's own header simply
        # doesn't extend that far (a real, shorter-header file variant, e.g.
        # a file whose row 4 stops at JAN with no Feb/Mar columns at all),
        # which is itself corroborating evidence for an earlier report month
        # rather than something to paper over with a guessed fallback column.
        col = month_cols.get(m)
        if col is None:
            continue
        v = _clean(ws.cell(target_row, col).value)
        if v is not None and v != 0:
            last_found = m
    return last_found


def _assert_bsp_month_match(ws, report_month: str, month_num: int, month_cols: Dict[int, int]) -> None:
    """Raise ValueError only when the file's own BF-Coke data column actively
    disagrees with the user-selected month — never blocks upload just because
    detection failed. No reliable FY/year signal exists in this file format:
    the only year-like header cell (row 4, near the "ACTUAL"/"Cum. APR-MAR"
    columns) drifts position between files and represents a prior-year
    comparison column, not the current report period — so only month is
    checked here, not year."""
    detected = _detect_actual_report_month(ws, month_cols)
    if detected and detected != month_num:
        raise ValueError(
            f"Month mismatch: the uploaded file's techno data appears to be for "
            f"month {_MONTH_NUM_TO_ABBR.get(detected, detected)}, but you selected "
            f"month {_MONTH_NUM_TO_ABBR.get(month_num, month_num)} ({report_month}). "
            f"Please select the matching month, or upload the correct file."
        )


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

        month_cols = _resolve_month_columns(ws)

        if month_num in month_cols:
            month_col = month_cols[month_num]
        elif month_num in _MONTH_NUM_TO_COL:
            month_col = _MONTH_NUM_TO_COL[month_num]
            print(
                f"[BSP-TechnoExtractor] Warning: could not find an '{_MONTH_NUM_TO_ABBR.get(month_num, month_num)}' "
                f"header in row 4 — falling back to fixed column {month_col}, which may not match this file's layout."
            )
        else:
            raise ValueError(f"Month {month_num} not in fixed column map")

        mar_col = month_cols.get(3)
        cum_col = (mar_col + 1) if mar_col else _CUM_COL

        _assert_bsp_month_match(ws, report_month, month_num, month_cols)

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
