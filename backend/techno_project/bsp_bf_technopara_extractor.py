"""
BSP Blast Furnace "V.PARAMETERS" workbook extractor.

Source file (legacy Excel 97-2003 .xls, read via xlrd — see _open_workbook
in excel_extractor_bsp.py): "BF_V.PARAMETERS ( <FY> )...xls", sheet "FOR GM".

Layout of "FOR GM" (confirmed on "BF_V.PARAMETERS ( 2026-27)NEW WITH CDI-1
(1).xls" — 34 parameter blocks, e.g. row 5 onward):

    [blank col A] [blank] PARAMETER NAME [blank] [blank] (unit)   <- title row
    [1-2 blank rows]
    MONTH  BF # 4  BF # 5  BF # 6  BF # 7  BF # 8  SHOP            <- header row
    2025 - 26   <full prior-FY total, one row>
    APR.'26 ...
    MAY ...
    ... (12 month rows, in fixed Apr-Mar fiscal-year order)
    Yearly  <full current-FY total, NOT a stop-at-month cumulative>

This is a ROW-major month layout (each row is one month; each column is one
furnace) — the opposite of the "Maj Production Summ"/"Technopara" sheets
used elsewhere in this codebase, which are COLUMN-major (fixed month
columns). Nothing here is addressed by a hardcoded row or column number:

  - Each parameter's title row is found by a label search (_BF_PARAMS),
    scanned in sheet order with a whole-sheet fallback — confirmed the
    block spacing is NOT constant (16 to 24 rows apart across the real
    file), so a fixed-offset table would drift.
  - Each block's own header row is found by searching a small window below
    the title row for the literal "MONTH" label, not assumed to sit at a
    fixed offset from the title.
  - Furnace/shop columns are read from that header row's own text (looking
    for "BF # N" / "BF-N" / "BFN" patterns and "SHOP"), so a furnace being
    added, removed, or reordered is picked up automatically instead of
    silently reading the wrong column. BF-5 is included on the same footing
    as every other furnace — it currently always reads 0 (shut, per BSP's
    other techno extractors' own comments) but nothing here hardcodes it
    out, so a real value the day it restarts is picked up without a code
    change.
  - The target month's row is found by matching the month column's own
    text against that month's 3-letter abbreviation (APR/MAY/.../MAR),
    not a fixed offset from the header — confirmed necessary: the very
    last block in the sheet ("(i/o+sinter+m/s)") uses "Month"/"APR.'24"
    instead of "MONTH"/"APR.'26" like every other block, i.e. even the
    year suffix and capitalization drift within the SAME file.

No "till_month" (YTD) figure is produced: the sheet's only full-FY
aggregate is the "Yearly" row, which sums Apr-Mar regardless of how much
of the year has actually been reported (unreported months contribute 0),
so before FY-end it is NOT the same thing as "cumulative Apr-through-
report-month" and would be actively misleading if stored as one.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "excel_extractors"))
from excel_extractor_bsp import _open_workbook  # noqa: E402 — handles legacy .xls via xlrd

_MONTH_NUM_TO_ABBR3 = {
    4: "APR", 5: "MAY", 6: "JUN", 7: "JUL", 8: "AUG", 9: "SEP",
    10: "OCT", 11: "NOV", 12: "DEC", 1: "JAN", 2: "FEB", 3: "MAR",
}

# (canonical param name, [label substrings — normalized, upper-case,
# whitespace-collapsed — any one matching the title row is enough], unit)
# Order matches the sheet's own block order; _resolve_param_rows scans
# sequentially in this order (with a whole-sheet fallback per param), which
# both disambiguates near-duplicate labels (e.g. "SINTER ( % )" vs "SINTER
# RATE") and is resilient to a block being inserted, removed, or reordered
# in some future vintage.
_BF_PARAMS: List[Tuple[str, List[str], str]] = [
    ("Hot Metal Production",             ["HOT METAL PRODUCTION"],                    "T"),
    ("Avg Daily Rate of Production",     ["AVG.DAILY", "RATE OF PRODUCTION"],         "T/day"),
    ("Hot Blast Temperature",            ["HOT BLAST TEMP"],                          "Deg C"),
    ("Scrap Rate",                       ["SCRAP RATE"],                              "Kg/THM"),
    ("Productivity (W/V)",               ["PRODUCTIVITY"],                            "T/m3/day"),
    ("Coke Rate",                        ["COKE RATE"],                               "Kg/THM"),
    ("CDI Rate",                         ["COAL DUST INJECTION"],                     "Kg/THM"),
    ("Fuel Rate",                        ["FUEL RATE"],                               "Kg/THM"),
    ("Nut Coke Rate",                    ["NUT COKE RATE"],                           "Kg/THM"),
    ("Sinter in Burden",                 ["SINTER ( %", "SINTER (%"],                 "%"),
    ("Slag Rate",                        ["SLAG RATE"],                               "Kg/THM"),
    ("O2 Enrichment",                    ["O2 ENRICHMENT"],                           "%"),
    ("Sinter Rate",                      ["SINTER RATE"],                             "Kg/THM"),
    ("Iron Ore Rate",                    ["IRON ORE RATE"],                           "Kg/THM"),
    ("CCS",                              ["CCS(", "CCS ("],                           "Kg/Pellet"),
    ("Pellet in Burden",                 ["PELLET %"],                                "%"),
    ("Slag Basicity",                    ["SLAG BASICITY"],                           "%"),
    ("MgO in BF Slag",                   ["MGO IN BF SLAG"],                          "%"),
    ("Al2O3 in BF Slag",                 ["AL2O3 IN BF SLAG"],                        "%"),
    ("Silicon in Hot Metal",             ["SILICON IN HOT METAL"],                    "%"),
    ("Sulphur in Hot Metal",             ["SULPHUR IN HOT METAL"],                    "%"),
    ("Flue Dust",                        ["FLUE DUST"],                               "Kg/THM"),
    ("Mn Rate",                          ["MN RATE"],                                 "Kg/THM"),
    ("Lime Stone Rate",                  ["LIME STONE RATE"],                         "Kg/THM"),
    ("L/D Slag",                         ["L/D SLAG"],                                "Kg/THM"),
    ("Flux (L/S Rt + L/D Rt)",           ["L/S.RT", "L/S RT"],                        "Kg/THM"),
    ("Furnace Utilization",              ["FCE.UTILIZATION", "FCE UTILIZATION"],      "%"),
    ("Furnace Availability",             ["FCE.AVAILIABILITY", "FCE.AVAILABILITY", "FCE AVAILABILITY", "FCE AVAILIABILITY"], "%"),
    ("Tap Duration",                     ["TAP. DURATION", "TAP DURATION"],           "%"),
    ("Tuyeres Changing",                 ["TUYERES CHANGING"],                        "Nos"),
    ("Quartzite",                        ["QUARTZITE"],                               "Kg/THM"),
    ("Fe Input",                         ["FE INPUT"],                                "Kg/THM"),
    ("Theoretical Hot Metal Production", ["THEO.HOT METAL PRODUCTION", "THEO HOT METAL PRODUCTION"], "T"),
]

_FURNACE_COL_RE = re.compile(r"BF\s*#?\s*-?\s*0*(\d+)")
_BAD = {"#DIV/0!", "#VALUE!", "-", "--", "N/A", None, ""}


def _cell_text(ws, row: int, col: int) -> str:
    return " ".join(str(ws.cell(row, col).value or "").strip().upper().split())


def _row_text(ws, row: int, max_col: int = 16) -> str:
    parts = []
    for c in range(1, min(max_col, ws.max_column or max_col) + 1):
        v = ws.cell(row, c).value
        if isinstance(v, str) and v.strip():
            parts.append(v.strip().upper())
    return " ".join(" ".join(parts).split())


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


def _find_title_row(ws, patterns: List[str], start_row: int) -> Optional[int]:
    """First row at/after start_row whose column-A (MONTH) cell is blank —
    i.e. a title/section row, not a data row — and whose combined text
    contains any of `patterns`. Falls back to searching the whole sheet
    from row 1 if nothing is found from start_row onward (handles a block
    being reordered relative to its neighbours)."""
    def _scan(from_row):
        for r in range(from_row, ws.max_row + 1):
            if _cell_text(ws, r, 1):
                continue  # a data/header row (MONTH column occupied), not a title
            text = _row_text(ws, r)
            if any(p in text for p in patterns):
                return r
        return None

    return _scan(start_row) or _scan(1)


def _find_header_row(ws, title_row: int, window: int = 6) -> Optional[int]:
    """First row within `window` rows after title_row whose MONTH column
    reads exactly "MONTH" (case-insensitive) — the block's own column
    header, wherever it actually sits (1-2 blank rows away in every block
    sampled, but not asserted to be a fixed offset)."""
    for r in range(title_row + 1, title_row + window + 1):
        if r > ws.max_row:
            break
        if _cell_text(ws, r, 1) == "MONTH":
            return r
    return None


def _resolve_furnace_columns(ws, header_row: int, max_col: int = 20) -> Dict[int, str]:
    """{column_index: unit_name} from the header row's own text — "BF # 4"/
    "BF-4"/"BF4" -> "BF-4" (any furnace number, not a fixed BF-4/6/7/8 list,
    so a furnace being added/removed/renumbered is picked up automatically),
    "SHOP" -> "BF_Shop" (matching the unit-naming convention every other BSP
    BF techno source in this codebase already uses — see
    excel_extractor_bsp.py's _MIS2_UNIT_LABELS and bsp_techno_map.json).

    Stops at the first repeated unit name rather than scanning the full
    `max_col` width: several blocks (confirmed on "Coke Rate") repeat the
    exact same title AND "MONTH/BF#4.../SHOP" header a second time further
    right on the SAME row, for a second table showing absolute consumption
    instead of the rate — reading past the first table's own SHOP column
    would silently overwrite each furnace's real (rate) value with that
    second table's (absolute) one."""
    cols: Dict[int, str] = {}
    seen = set()
    for c in range(2, min(max_col, ws.max_column or max_col) + 1):
        text = _cell_text(ws, header_row, c)
        if not text:
            continue
        unit_name = None
        m = _FURNACE_COL_RE.search(text)
        if m:
            unit_name = f"BF-{int(m.group(1))}"
        elif text == "SHOP":
            unit_name = "BF_Shop"
        if unit_name is None:
            continue
        if unit_name in seen:
            break
        cols[c] = unit_name
        seen.add(unit_name)
    return cols


def _find_month_row(ws, header_row: int, month_num: int, window: int = 20) -> Optional[int]:
    """First row within `window` rows after header_row whose MONTH column
    text starts with the target month's 3-letter abbreviation — not a fixed
    offset from header_row, since whether a prior-FY-total row precedes the
    month rows (it does in every block but the sheet's last one) isn't
    assumed. Matches on the abbreviation prefix only (not the trailing
    year), since that drifts too (e.g. "APR.'26" vs a stray "APR.'24" seen
    on the sheet's last block)."""
    abbr = _MONTH_NUM_TO_ABBR3[month_num]
    for r in range(header_row + 1, header_row + window + 1):
        if r > ws.max_row:
            break
        if _cell_text(ws, r, 1).startswith(abbr):
            return r
    return None


def _find_sheet(wb):
    for name in wb.sheetnames:
        if " ".join(name.strip().upper().split()) == "FOR GM":
            return wb[name]
    # Fallback: any sheet whose own title cell announces the report, in case
    # "FOR GM" itself gets renamed in a future vintage.
    for name in wb.sheetnames:
        ws = wb[name]
        for r in range(1, min(6, ws.max_row) + 1):
            if "VARIOUS PARAMETERS FOR THE YEAR" in _row_text(ws, r):
                return ws
    return None


def _resolve_param_rows(ws) -> Dict[str, Optional[int]]:
    cursor = 1
    rows: Dict[str, Optional[int]] = {}
    for name, patterns, _unit in _BF_PARAMS:
        row = _find_title_row(ws, patterns, cursor)
        rows[name] = row
        if row is not None:
            cursor = row + 1
    return rows


def _detect_fy_start_year(ws) -> Optional[int]:
    """FY start year (e.g. 2026 for "2026-27") from the sheet's own title
    cell ("VARIOUS PARAMETERS FOR THE YEAR 2026 - 27"), used only to warn on
    an obviously mismatched upload — never blocks it, since a title cell
    format change shouldn't take the whole extractor down with it."""
    for r in range(1, min(6, ws.max_row) + 1):
        text = _row_text(ws, r, max_col=20)
        m = re.search(r"YEAR\s+(\d{4})\s*-\s*\d{2}", text)
        if m:
            return int(m.group(1))
    return None


class BspBfTechnoExtractor:
    def __init__(self, excel_file: str, report_month: str):
        self.excel_file = Path(excel_file)
        if not report_month:
            raise ValueError("report_month ('YYYY-MM') is required for the BSP BF techno extractor.")
        self.report_month = report_month

    @staticmethod
    def _assert_month_reported(ws, param_rows: Dict[str, Optional[int]], month_num: int) -> None:
        """Refuse to extract a month the sheet hasn't actually reported yet.
        A not-yet-reported month's row isn't reliably blank across every
        block — some blocks (confirmed: Coke Rate, CDI Rate) carry a stray
        literal 7 in every furnace column for every unreported month, a
        template/formula artifact, not real data — so this checks the one
        figure that's reliable everywhere production genuinely happened:
        "Hot Metal Production"'s own SHOP total. A real reported month is
        never 0 across all 5 furnaces combined."""
        title_row = param_rows.get("Hot Metal Production")
        if title_row is None:
            return  # can't check — let extract() proceed and surface its own "not found" gaps
        header_row = _find_header_row(ws, title_row)
        if header_row is None:
            return
        month_row = _find_month_row(ws, header_row, month_num)
        if month_row is None:
            return
        furnace_cols = _resolve_furnace_columns(ws, header_row)
        shop_col = next((c for c, u in furnace_cols.items() if u == "BF_Shop"), None)
        if shop_col is None:
            return
        shop_val = _clean(ws.cell(month_row, shop_col).value)
        if not shop_val:
            raise ValueError(
                f"This workbook shows no Hot Metal Production for "
                f"{_MONTH_NUM_TO_ABBR3[month_num]} — that month hasn't been "
                f"reported in this file yet. Select an earlier month, or "
                f"upload a later file that actually covers it."
            )

    def extract(self) -> List[Dict]:
        year_str, month_str = self.report_month.split("-")
        month_num = int(month_str)
        if month_num not in _MONTH_NUM_TO_ABBR3:
            raise ValueError(f"Invalid month in report_month '{self.report_month}'.")
        fy_start = int(year_str) if month_num >= 4 else int(year_str) - 1

        wb = _open_workbook(str(self.excel_file))
        ws = _find_sheet(wb)
        if ws is None:
            raise ValueError(
                "Could not find the 'FOR GM' sheet (or any sheet titled "
                "'VARIOUS PARAMETERS FOR THE YEAR ...') in this workbook. "
                f"Sheets found: {', '.join(wb.sheetnames)}"
            )

        file_fy_start = _detect_fy_start_year(ws)
        if file_fy_start is not None and file_fy_start != fy_start:
            raise ValueError(
                f"Year mismatch: the uploaded file's own title says FY {file_fy_start}-"
                f"{str(file_fy_start + 1)[2:]}, but the selected report month "
                f"{self.report_month} falls in FY {fy_start}-{str(fy_start + 1)[2:]}. "
                f"Please select the matching month, or upload the correct file."
            )

        param_rows = _resolve_param_rows(ws)
        self._assert_month_reported(ws, param_rows, month_num)

        units: Dict[str, Dict[str, Optional[float]]] = {}

        for param_name, _patterns, _unit in _BF_PARAMS:
            title_row = param_rows.get(param_name)
            if title_row is None:
                continue
            header_row = _find_header_row(ws, title_row)
            if header_row is None:
                continue
            month_row = _find_month_row(ws, header_row, month_num)
            if month_row is None:
                continue
            furnace_cols = _resolve_furnace_columns(ws, header_row)
            if not furnace_cols:
                continue

            raw_by_unit = {}
            for col, unit_name in furnace_cols.items():
                raw_by_unit[unit_name] = _clean(ws.cell(month_row, col).value)

            # A "SHOP" total sometimes carries a formula-artifact 0 for a
            # not-yet-reported month even when every individual furnace
            # column is genuinely blank (confirmed: rows for unreported
            # months show 0.0 in the SHOP column with every furnace column
            # blank) — treated as "not reported" (None) rather than a
            # misleadingly precise 0, same spirit as this codebase's other
            # "don't report a formula artifact as real data" guards (see
            # page_special_steel_donut.py's clamped-at-0 comments).
            furnace_vals = [v for k, v in raw_by_unit.items() if k != "BF_Shop"]
            if "BF_Shop" in raw_by_unit and all(v is None for v in furnace_vals) and furnace_vals:
                raw_by_unit["BF_Shop"] = None

            for unit_name, val in raw_by_unit.items():
                bucket = units.setdefault(unit_name, {})
                bucket[param_name] = val

        records = []
        for unit_name, params in units.items():
            if not any(v is not None for v in params.values()):
                continue
            records.append({
                "report_month": self.report_month,
                "plant": "BSP_BF",
                "unit": unit_name,
                "techno_json": {"month": params, "till_month": {}},
            })

        return records


_PARAM_UNITS = {name: unit for name, _patterns, unit in _BF_PARAMS}
