import json
import re
from datetime import datetime, time
from pathlib import Path
from openpyxl import load_workbook
from typing import Dict, List, Optional

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


class IspTechnoExtractor:
    def __init__(self, excel_file: str, report_month: str = None):
        """
        Args:
            excel_file: Path to the ISP monthly report Excel file.
            report_month: Report month in YYYY-MM format (e.g. "2026-03").
        """
        self.excel_file = Path(excel_file)
        self.report_month = report_month
        self.workbook = None
        self.hardcoded_map = self._load_hardcoded_map()
        self.row_labels = self._load_row_labels()
        self.month_col = None
        self.header_row = None

    def _load_hardcoded_map(self) -> Dict:
        """Load sheet-wise parameter mapping."""
        map_path = Path(__file__).parent / "isp_technopara_map.json"
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: isp_technopara_map.json not found at {map_path}!")
            return {}

    def _load_row_labels(self) -> Dict:
        """Load the companion {sheet: {unit: {param_key: expected column-B
        label}}} file used to verify/self-heal isp_technopara_map.json's
        hardcoded row numbers against future report-template row shifts.
        Covers only the simple (non-expression) row specs — see
        _verified_row(). Missing file/entries just disable verification,
        never break extraction."""
        labels_path = Path(__file__).parent / "isp_technopara_row_labels.json"
        try:
            with open(labels_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    @staticmethod
    def _norm_label(s) -> str:
        return re.sub(r"\s+", " ", str(s or "")).strip().lower()

    def _find_label_row(self, ws, label: str, near_row: int, window: int = 20) -> Optional[int]:
        """Scan column B for `label` (case-insensitive substring), searching
        outward from `near_row` first within +/-`window` rows (bounded to the
        sheet), so a shift is found nearby rather than matching a same-named
        parameter in a distant, unrelated section (e.g. COB-old vs COB-new
        both have a 'BF Coke'/'Sp Heat Cons' row)."""
        lc = self._norm_label(label)
        if not lc:
            return None
        lo = max(1, near_row - window)
        hi = min(ws.max_row, near_row + window)
        for offset in range(0, window + 1):
            for r in ({near_row - offset, near_row + offset} if offset else {near_row}):
                if lo <= r <= hi and lc in self._norm_label(ws.cell(row=r, column=2).value):
                    return r
        return None

    def _verified_row(self, ws, sheet_name: str, unit_name: str, param_key: str, configured_row: int) -> int:
        """Return the row to actually read for (sheet, unit, param_key):
        the configured row if its column-B label still matches, the nearby
        row the label moved to if not, or the configured row unchanged (with
        a warning) if the label can't be found anywhere nearby. Only called
        for simple int/numeric-string row specs — expression-based specs
        (e.g. '17/8', '(134+135+136)/3') are left untouched."""
        expected = (self.row_labels.get(sheet_name, {}).get(unit_name, {}).get(param_key))
        if not expected:
            return configured_row
        actual_label = ws.cell(row=configured_row, column=2).value
        if self._norm_label(expected) in self._norm_label(actual_label):
            return configured_row
        found = self._find_label_row(ws, expected, configured_row)
        if found:
            print(f"Warning: '{sheet_name}/{unit_name}/{param_key}' row shifted "
                  f"{configured_row} -> {found} (label '{expected}')")
            return found
        print(f"Warning: '{sheet_name}/{unit_name}/{param_key}' expected label "
              f"'{expected}' not found near row {configured_row} — using "
              f"configured row unverified (got {actual_label!r})")
        return configured_row

    @staticmethod
    def _clean_value(val):
        """Convert value to JSON-serializable format."""
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
        print(f"Opened workbook with sheets: {self.workbook.sheetnames[:10]}...")

    def _find_month_column(self, ws):
        """Detect month column in given worksheet."""
        # Try rows 3, 2, 4, 5 to find headers
        for row_num in [3, 2, 4, 5]:
            header = [str(c.value).strip() if c.value else "" for c in ws[row_num]]
            has_months = any(
                abbr in h or f"{abbr}'" in h
                for h in header
                for abbr in _MONTH_ABBRS
            )
            if has_months:
                self.header_row = row_num
                return row_num, header
        return None, []

    def _get_cum_column_offset(self, month_num: int) -> int:
        """
        Get cumulative column offset based on month.
        ISP Excel pattern:
          - Most months: cum is 2 columns ahead
          - Sep & Dec: cum is 4 columns ahead
          - Mar: cum is 6 columns ahead
        """
        if month_num == 3:  # March
            return 6
        elif month_num in [9, 12]:  # September, December
            return 4
        else:  # May, June, July, Aug, Oct, Nov, Jan, Feb
            return 2

    def _get_cell_value(self, ws, row_num: int, col_num: int):
        """Get value from cell, handling None/error values."""
        try:
            val = ws.cell(row_num, col_num + 1).value
            if val is None or val in {"#DIV/0!", "#VALUE!", "-", "--", ""}:
                return None
            if isinstance(val, (int, float)):
                return val
            return None
        except Exception:
            return None

    def _evaluate_row_expression(self, ws, expression: str, month_col: int) -> float:
        """Evaluate expressions like '5+6', '5/days', '(5+6)/days'."""
        try:
            # Get days in month from row 2
            days_val = ws.cell(2, month_col + 1).value
            days = float(days_val) if days_val and isinstance(days_val, (int, float)) else 30

            # Replace 'days' with actual value
            expr = expression.replace("days", str(days))

            # Parse row references (numbers)
            import re
            def get_row_value(match):
                row_num = int(match.group(1))
                val = self._get_cell_value(ws, row_num, month_col)
                return str(val) if val is not None else "0"

            expr = re.sub(r'(\d+)(?![\d\.])', get_row_value, expr)

            # Safely evaluate the expression
            result = eval(expr)
            return float(result) if result else None

        except Exception as e:
            print(f"Error evaluating expression '{expression}': {e}")
            return None

    def _get_actual_column(self, ws, month_col: int) -> int:
        """
        ISP format: Columns are merged with Plan/Actual sub-columns.
        Check row 4 to find the Actual (ACT) column.
        Usually month_col = Plan, month_col+1 = Actual
        """
        try:
            row4 = [str(c.value).strip().upper() if c.value else "" for c in ws[4]]

            # Check if month_col is Plan and month_col+1 is Actual
            if month_col < len(row4) and month_col + 1 < len(row4):
                curr = row4[month_col]
                next_col = row4[month_col + 1]

                if "ACT" in next_col or "ACT" in curr:
                    # Use whichever is ACT
                    if "ACT" in next_col:
                        return month_col + 1
                    else:
                        return month_col
        except Exception as e:
            print(f"Warning detecting actual column: {e}")

        # Fallback: assume next column is actual
        return month_col + 1

    def _get_parameter_multiplier(self, sheet_name: str, param_key: str) -> float:
        """
        Get unit multiplier for specific sheet/parameter combinations.
        Used to normalize units across different sheets.

        ISP Mills (BM, USM, WRM): specific_heat_consumption needs *1000
        COKE OVENS: Sp Heat Cons is in 10^6 kcal/t -> *1000 gives kcal/kg DC
        """
        multipliers = {
            "BM": {"specific_heat_consumption": 1000},
            "USM": {"specific_heat_consumption": 1000},
            "WRM": {"specific_heat_consumption": 1000},
            "COKE OVENS": {"specific_heat_coke_ovens": 1000},
        }

        if sheet_name in multipliers and param_key in multipliers[sheet_name]:
            return multipliers[sheet_name][param_key]
        return 1.0

    def _extract_from_sheet(self, sheet_name: str, unit_name: str, unit_params: Dict) -> Dict:
        """Extract techno data from a single sheet for both month and till_month."""
        if sheet_name not in self.workbook.sheetnames:
            print(f"Sheet '{sheet_name}' not found")
            return None

        ws = self.workbook[sheet_name]
        header_row, header = self._find_month_column(ws)

        if header_row is None:
            print(f"Cannot find month headers in sheet '{sheet_name}'")
            return None

        # Find month column for report_month
        month_col = None
        if self.report_month:
            try:
                month_num = int(self.report_month.split('-')[1])
                target_abbr = _MONTH_NUM_TO_ABBR.get(month_num)
                for i, h in enumerate(header):
                    if target_abbr in h:
                        month_col = i
                        break
            except (ValueError, IndexError):
                pass

        if month_col is None:
            # Use last filled month
            for abbr in reversed(_MONTH_ABBRS):
                for i, h in enumerate(header):
                    if abbr in h:
                        month_col = i
                        break
                if month_col is not None:
                    break

        if month_col is None:
            print(f"Cannot find month column in sheet '{sheet_name}'")
            return None

        # Get the actual (ACT) column - ISP has Plan/Actual pairs
        month_col = self._get_actual_column(ws, month_col)
        print(f"Using actual column: {month_col}")

        # Calculate cumulative column based on ISP pattern
        cum_col = None
        try:
            month_num = int(self.report_month.split('-')[1])
            cum_offset = self._get_cum_column_offset(month_num)
            cum_col = month_col + cum_offset
            print(f"Cumulative offset for month {month_num}: +{cum_offset} → column {cum_col}")
        except Exception as e:
            print(f"Warning calculating cum_col: {e}")

        print(f"Extracting from sheet '{sheet_name}', month_col={month_col}, cum_col={cum_col}")

        # Extract parameters from this sheet
        data = {"month": {}, "till_month": {}}

        for param_key, row_spec in unit_params.items():
            try:
                # Determine row number(s) to read
                if isinstance(row_spec, str):
                    if any(op in row_spec for op in ['+', '-', '/', '*', '(', ')']):
                        # Expression - evaluate for both columns
                        month_val = self._evaluate_row_expression(ws, row_spec, month_col)
                        till_val = self._evaluate_row_expression(ws, row_spec, cum_col) if cum_col else None
                    else:
                        # Simple row number as string
                        row_num = self._verified_row(ws, sheet_name, unit_name, param_key, int(row_spec))
                        row = list(ws.iter_rows(
                            min_row=row_num, max_row=row_num, values_only=True
                        ))[0]
                        month_val = row[month_col] if month_col < len(row) else None
                        till_val = row[cum_col] if cum_col and cum_col < len(row) else None
                else:
                    # Integer row number
                    row_num = self._verified_row(ws, sheet_name, unit_name, param_key, row_spec)
                    row = list(ws.iter_rows(
                        min_row=row_num, max_row=row_num, values_only=True
                    ))[0]
                    month_val = row[month_col] if month_col < len(row) else None
                    till_val = row[cum_col] if cum_col and cum_col < len(row) else None

                # Clean values
                month_val = self._clean_value(month_val)
                till_val = self._clean_value(till_val)

                # Apply unit multipliers if needed
                multiplier = self._get_parameter_multiplier(sheet_name, param_key)
                if multiplier != 1.0:
                    if month_val is not None:
                        month_val = float(month_val) * multiplier
                    if till_val is not None:
                        till_val = float(till_val) * multiplier
                    print(f"  Applied multiplier {multiplier}x to {param_key}")

                # Store both month and till_month
                data["month"][param_key] = month_val
                data["till_month"][param_key] = till_val

            except Exception as e:
                print(f"Warning: Could not read '{row_spec}' for {param_key} in sheet '{sheet_name}': {e}")

        return data

    def extract(self) -> List[Dict]:
        """Extract techno data from all mapped sheets."""
        self.open_workbook()

        # Auto-detect report month if not provided
        if not self.report_month:
            # Try to find month from first available sheet
            for sheet_name in list(self.hardcoded_map.keys())[:1]:
                if sheet_name in self.workbook.sheetnames:
                    ws = self.workbook[sheet_name]
                    _, header = self._find_month_column(ws)
                    if header:
                        for h in header:
                            for abbr in _MONTH_ABBRS:
                                if abbr in h:
                                    try:
                                        year_part = h.split("'")[-1]
                                        if year_part.isdigit() and len(year_part) == 2:
                                            year = 2000 + int(year_part)
                                        else:
                                            year = 2026
                                    except:
                                        year = 2026
                                    month_num = _MONTH_ABBR_TO_NUM.get(abbr, 4)
                                    self.report_month = f"{year}-{month_num:02d}"
                                    print(f"Auto-detected report month: {self.report_month}")
                                    break
                            if self.report_month:
                                break

        if not self.report_month:
            self.report_month = "2026-03"
            print(f"Using default report month: {self.report_month}")

        records = []
        print(f"\n--- Starting ISP Techno Extraction ---\n")

        # Process each sheet in the mapping
        for sheet_name, sheet_units in self.hardcoded_map.items():
            print(f"\nProcessing sheet: '{sheet_name}'")

            for unit_name, unit_params in sheet_units.items():
                data = self._extract_from_sheet(sheet_name, unit_name, unit_params)

                if data and any(v is not None for v in data["month"].values()):
                    records.append({
                        "report_month": self.report_month,
                        "plant": "ISP",
                        "unit": unit_name,
                        "techno_json": data,
                    })
                    print(f"  OK Extracted: {unit_name}")
                else:
                    print(f"  -- No data for: {unit_name}")

        print(f"\nExtraction Completed. Total Records: {len(records)}")
        return records
