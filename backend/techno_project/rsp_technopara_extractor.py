import calendar
import json
from datetime import datetime, time
from pathlib import Path
from openpyxl import load_workbook
from typing import Dict, List

# Params that the source sheet reports as a TOTAL for the period (total blows
# in the month / FY-to-date), not a daily average - must be divided by the
# number of days before being displayed/stored, to match "Average Blows/Day"
# as actually labelled.
_DAILY_AVG_PARAMS = {"average_blows_per_day"}


def _ytd_days(year_i: int, month_i: int) -> int:
    """Total calendar days from April 1 of the financial year to end of report
    month (RSP's FY starts in April). Mirrors excel_extractor_rsp.py's helper
    of the same name, kept local here to avoid cross-package import."""
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

_MONTH_ABBRS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
_MONTH_NUM_TO_ABBR = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
}
_MONTH_ABBR_TO_NUM = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}
_NEXT_YEAR_MONTHS = {'Jan', 'Feb', 'Mar'}


class TechnoExtractor:
    def __init__(self, excel_file: str, report_month: str = None):
        """
        Args:
            excel_file: Path to the RSP technopara Excel file.
            report_month: Report month in YYYY-MM format (e.g. "2026-05").
                         When provided, the matching month column is read directly.
                         When None, auto-detects the last filled month column.
        """
        self.excel_file = Path(excel_file)
        self.report_month = report_month  # YYYY-MM or None
        self.workbook = None
        self.ws = None
        self.month_col = None
        self.cum_col = None
        self.hardcoded_map = self._load_hardcoded_map()

    def _load_hardcoded_map(self) -> Dict:
        map_path = Path(__file__).parent / "rsp_technopara_map.json"
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: rsp_technopara_map.json not found at {map_path}!")
            return {}

    @staticmethod
    def _clean_value(val):
        if isinstance(val, time):
            return val.strftime("%H:%M:%S")
        if isinstance(val, datetime):
            return val.time().strftime("%H:%M:%S")
        if isinstance(val, str) and not val.strip():
            return None
        _bad = {"#DIV/0!", "#VALUE!", "-", "--", None, ""}
        if val in _bad:
            return None
        return val

    def open_workbook(self):
        self.workbook = load_workbook(self.excel_file, data_only=True)

    def load_sheet(self):
        if self.workbook is None:
            self.open_workbook()
        for sheet in self.workbook.sheetnames:
            norm = sheet.lower().replace(" ", "").replace("-", "")
            if norm in ["page18", "page1-8", "page-1-8"]:
                self.ws = self.workbook[sheet]
                print(f"Loaded sheet: {sheet}")
                return
        raise Exception("Sheet 'page1-8' (or 'page18') not found in workbook.")

    def detect_month_column(self):
        """Find the month column and cumulative column in row 3.

        If report_month was provided, seeks that specific month's column.
        Otherwise falls back to the last month column that has valid numeric data.
        """
        header = [str(c.value).strip() if c.value else "" for c in self.ws[3]]

        if self.report_month:
            try:
                month_num = int(self.report_month.split('-')[1])
                target_abbr = _MONTH_NUM_TO_ABBR.get(month_num)
                if target_abbr and target_abbr in header:
                    self.month_col = header.index(target_abbr)
            except (ValueError, IndexError, AttributeError):
                pass

        if self.month_col is None:
            # Scan in reverse order (Mar -> Apr) to find the last filled month
            for abbr in reversed(_MONTH_ABBRS):
                if abbr not in header:
                    continue
                col = header.index(abbr)
                valid = sum(
                    1 for r in range(5, 40)
                    if isinstance(self.ws.cell(r + 1, col + 1).value, (int, float))
                )
                if valid > 5:
                    self.month_col = col
                    break

        if self.month_col is None:
            raise Exception("Cannot detect report month column in row 3")

        if "Cum." not in header:
            raise Exception("Cannot find 'Cum.' column in row 3")
        self.cum_col = header.index("Cum.")

    def detect_report_month(self):
        """Auto-detect report month from FY cell + detected column.
        Only used when report_month was not provided externally.
        """
        if self.report_month:
            return

        try:
            fy = str(self.ws["AM2"].value)
            start_year = int(fy.split("-")[0])
        except Exception:
            start_year = 2026

        header = [str(c.value).strip() if c.value else "" for c in self.ws[3]]
        detected_abbr = _MONTH_ABBRS[0]  # Apr default
        if self.month_col is not None and self.month_col < len(header):
            detected_abbr = header[self.month_col]

        month_num = _MONTH_ABBR_TO_NUM.get(detected_abbr, 4)
        year = start_year + (1 if detected_abbr in _NEXT_YEAR_MONTHS else 0)
        self.report_month = f"{year}-{month_num:02d}"

    def extract(self) -> List[Dict]:
        self.load_sheet()
        self.detect_month_column()
        if not self.report_month:
            self.detect_report_month()

        year_i, month_i = map(int, self.report_month.split('-'))
        days_in_month = calendar.monthrange(year_i, month_i)[1]
        ytd_days = _ytd_days(year_i, month_i)

        records = []
        print("\n--- Starting Hardcoded Extraction ---\n")

        for unit_name, params in self.hardcoded_map.items():
            techno = {"month": {}, "till_month": {}}

            for param_key, row_num in params.items():
                try:
                    row = list(self.ws.iter_rows(
                        min_row=row_num, max_row=row_num, values_only=True
                    ))[0]

                    month_val = row[self.month_col] if self.month_col < len(row) else None
                    till_val = (
                        row[self.cum_col]
                        if self.cum_col is not None and self.cum_col < len(row)
                        else None
                    )

                    month_val = self._clean_value(month_val)
                    till_val = self._clean_value(till_val)

                    if param_key in _DAILY_AVG_PARAMS:
                        # Sheet reports the TOTAL number of blows for the
                        # period, not a per-day average - convert here so the
                        # stored value actually matches "Average Blows/Day".
                        if isinstance(month_val, (int, float)):
                            month_val = round(month_val / days_in_month, 1)
                        if isinstance(till_val, (int, float)):
                            till_val = round(till_val / ytd_days, 1)

                    techno["month"][param_key] = month_val
                    techno["till_month"][param_key] = till_val
                except Exception as e:
                    print(f"Warning: Could not read row {row_num} for {param_key}: {e}")

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