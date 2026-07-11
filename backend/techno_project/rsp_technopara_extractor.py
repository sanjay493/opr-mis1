import calendar
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from rsp_row_scan import find_p18_sheet, norm_label  # noqa: E402  (path set above)
from rsp_technopara_parser import clean_technopara_sheet  # noqa: E402
from rsp_technopara_sections import (  # noqa: E402
    SECTION_UNITS, PARAM_ALIASES, FURNACE_BLOCKS, PARAM_UNIT_FILTERS, DAILY_AVG_PARAMS,
)

_MONTH_ABBR_TO_NUM = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
}


def _ytd_days(year_i: int, month_i: int) -> int:
    """Total calendar days from April 1 of the financial year to end of report
    month (RSP's FY starts in April)."""
    fy_year = year_i if month_i >= 4 else year_i - 1
    total, y, m = 0, fy_year, 4
    while True:
        total += calendar.monthrange(y, m)[1]
        if y == year_i and m == month_i:
            break
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return total


def _clean_value(val):
    """Convert a raw cell value to a JSON-serializable number/None."""
    if isinstance(val, time):
        return None
    if isinstance(val, datetime):
        return None
    if isinstance(val, str):
        s = val.strip()
        if not s or s in {"#DIV/0!", "#VALUE!", "-", "--"}:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    if isinstance(val, (int, float)):
        return val
    return None


# Pre-normalize the registry once at import time so every lookup at runtime
# is a plain dict hit — no repeated re-normalization of the same keys.
_SECTION_UNITS_NORM = {norm_label(k): v for k, v in SECTION_UNITS.items()}
_PARAM_ALIASES_NORM = {norm_label(k): v for k, v in PARAM_ALIASES.items()}
_FURNACE_BLOCKS_NORM = {norm_label(k): v for k, v in FURNACE_BLOCKS.items()}
_PARAM_UNIT_FILTERS_NORM = {norm_label(k): norm_label(v) for k, v in PARAM_UNIT_FILTERS.items()}
_PROBE_LABELS = list(PARAM_ALIASES.keys()) + list(SECTION_UNITS.keys())


class TechnoExtractor:
    def __init__(self, excel_file: str, report_month: str = None):
        """
        Args:
            excel_file: Path to the RSP technopara Excel file.
            report_month: Report month in YYYY-MM format (e.g. "2026-05").
        """
        self.excel_file = Path(excel_file)
        self.report_month = report_month
        self.workbook = None
        self.ws = None

    def open_workbook(self):
        from openpyxl import load_workbook
        self.workbook = load_workbook(self.excel_file, data_only=True)

    def load_sheet(self):
        if self.workbook is None:
            self.open_workbook()
        sheet = find_p18_sheet(self.workbook.sheetnames)
        if sheet is None:
            raise Exception(
                "No page-1-8-style sheet found in workbook (expected a sheet name "
                "starting with 'page1-8'/'page-1-9', e.g. 'page-1-8', "
                "'PAGE-1-8 & 11,12', 'PAGE-1-9')."
            )
        self.ws = self.workbook[sheet]
        print(f"Loaded sheet: {sheet}")

    def _walk(self, df) -> Dict[str, Dict]:
        """Single top-to-bottom pass over the cleaned sheet. Tracks the
        current unit section and resolves every row via SECTION_UNITS /
        FURNACE_BLOCKS / PARAM_ALIASES — never by stored row number."""
        units: Dict[str, Dict] = {}

        def _set(unit, param_key, month_val, cum_val):
            if unit is None or param_key is None:
                return
            slot = units.setdefault(unit, {"month": {}, "till_month": {}})
            # First occurrence wins — a couple of labels legitimately repeat
            # later in the sheet (e.g. "Make-Up Water Cons." appears twice,
            # once per unit-of-measure variant; only the first is wanted).
            if param_key in slot["month"]:
                return
            slot["month"][param_key] = month_val
            slot["till_month"][param_key] = cum_val

        current_unit = None
        n = len(df)
        for i in range(n):
            label_raw = df.at[i, "label"]
            label_norm = norm_label(label_raw)
            if not label_norm:
                continue

            if label_norm in _SECTION_UNITS_NORM:
                current_unit = _SECTION_UNITS_NORM[label_norm]
                continue

            if label_norm in _FURNACE_BLOCKS_NORM:
                param_key, offsets = _FURNACE_BLOCKS_NORM[label_norm]
                for offset, unit in offsets:
                    j = i + offset
                    if j < n:
                        mv = _clean_value(df.at[j, "month_val"])
                        cv = _clean_value(df.at[j, "cum_val"])
                        _set(unit, param_key, mv, cv)
                continue

            alias = _PARAM_ALIASES_NORM.get(label_norm)
            if alias is None:
                continue

            required_unit_str = _PARAM_UNIT_FILTERS_NORM.get(label_norm)
            if required_unit_str is not None:
                unit_str = norm_label(df.at[i, "unit_str"])
                if required_unit_str not in unit_str:
                    continue

            if isinstance(alias, tuple):
                unit, param_key = alias
            else:
                if current_unit is None:
                    continue
                unit, param_key = current_unit, alias

            mv = _clean_value(df.at[i, "month_val"])
            cv = _clean_value(df.at[i, "cum_val"])
            _set(unit, param_key, mv, cv)

        return units

    def extract(self) -> List[Dict]:
        self.load_sheet()

        month_num = None
        if self.report_month:
            try:
                month_num = f"{int(self.report_month.split('-')[1]):02d}"
            except (ValueError, IndexError):
                pass
        if not month_num:
            raise Exception(
                "report_month is required (YYYY-MM) — the technopara sheet has "
                "no reliable way to auto-detect which month column is current."
            )

        df = clean_technopara_sheet(self.ws, month_num, _PROBE_LABELS)

        year_i, month_i = int(self.report_month[:4]), int(month_num)
        days_in_month = calendar.monthrange(year_i, month_i)[1]
        ytd_days = _ytd_days(year_i, month_i)

        units = self._walk(df)

        records = []
        print("\n--- Starting RSP Techno Extraction ---\n")
        for unit_name, techno in units.items():
            for param_key in DAILY_AVG_PARAMS:
                mv = techno["month"].get(param_key)
                cv = techno["till_month"].get(param_key)
                if isinstance(mv, (int, float)):
                    techno["month"][param_key] = round(mv / days_in_month, 1)
                if isinstance(cv, (int, float)):
                    techno["till_month"][param_key] = round(cv / ytd_days, 1)

            if any(v is not None for v in techno["month"].values()):
                records.append({
                    "report_month": self.report_month,
                    "plant": "RSP",
                    "unit": unit_name,
                    "techno_json": techno,
                })
                print(f"  Extracted: {unit_name}")

        print(f"\nExtraction Completed. Total Records: {len(records)}")
        return records
