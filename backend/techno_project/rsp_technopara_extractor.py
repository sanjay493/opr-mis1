import calendar
import json
import sys
from datetime import datetime, time
from pathlib import Path
from openpyxl import load_workbook
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from rsp_row_scan import (  # noqa: E402  (path set above)
    find_month_cum_columns, find_p18_sheet, verified_row, detect_label_column,
)

# Params that the source sheet reports as a TOTAL for the period (total blows
# in the month / FY-to-date), not a daily average - must be divided by the
# number of days before being displayed/stored, to match "Average Blows/Day"
# as actually labelled.
_DAILY_AVG_PARAMS = {"average_blows_per_day"}

# BF-4's row is unlabeled in column A/B for these three params (confirmed
# across every sample file checked) — the O2-Enrichment/Hot-Blast-Temp/
# Si-in-HM block lists BF-1/BF-5/Shop by label but leaves BF-4's row blank,
# always the row immediately after BF-1's verified row for the same param
# (BF-1/BF-4/BF-5/Shop are laid out as four consecutive rows in that block in
# every sample file checked). Resolved by anchoring off BF-1's own
# (label-verified) row rather than by label match.
_BF4_BLANK_ANCHOR_OFFSET = {
    "o2_enrichment": 1, "hot_blast_temp": 1, "silicon_in_hm": 1,
}


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
        self.month_col = None   # 0-based, for values_only row tuples
        self.cum_col = None     # 0-based
        self.label_col = 1      # 1-based (openpyxl convention); detected per sheet
        self.hardcoded_map = self._load_hardcoded_map()
        self.row_labels = self._load_row_labels()

    def _load_hardcoded_map(self) -> Dict:
        map_path = Path(__file__).parent / "rsp_technopara_map.json"
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: rsp_technopara_map.json not found at {map_path}!")
            return {}

    def _load_row_labels(self) -> Dict:
        """Load the companion {unit: {param_key: expected column label}} file
        used to self-heal rsp_technopara_map.json's hardcoded row numbers
        against report-template row shifts (mirrors isp_technopara_extractor.py's
        isp_technopara_row_labels.json). Missing file/entries just disable
        verification for that row, never break extraction."""
        labels_path = Path(__file__).parent / "rsp_technopara_row_labels.json"
        try:
            with open(labels_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
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
        sheet = find_p18_sheet(self.workbook.sheetnames)
        if sheet is None:
            raise Exception(
                "No page-1-8-style sheet found in workbook (expected a sheet name "
                "starting with 'page1-8'/'page-1-9', e.g. 'page-1-8', "
                "'PAGE-1-8 & 11,12', 'PAGE-1-9')."
            )
        self.ws = self.workbook[sheet]
        print(f"Loaded sheet: {sheet}")

    def detect_month_column(self):
        """Find the month column and cumulative column by scanning the sheet's
        own header rows (see rsp_row_scan.find_month_cum_columns) instead of
        assuming a fixed row/column — the sheet prepends one more legacy
        fiscal-year column every year, shifting every month's column annually,
        and the header row itself has been seen at row 1 as well as row 3."""
        month_num = None
        if self.report_month:
            try:
                month_num = f"{int(self.report_month.split('-')[1]):02d}"
            except (ValueError, IndexError):
                pass

        month_col_1based = cum_col_1based = None
        if month_num:
            month_col_1based, cum_col_1based = find_month_cum_columns(self.ws, month_num)

        if month_col_1based is None:
            # No report_month given (or its column wasn't found) — fall back to
            # the last month with valid numeric data, scanning back from March.
            for mnum in ["03", "02", "01", "12", "11", "10", "09", "08", "07", "06", "05", "04"]:
                mc, cc = find_month_cum_columns(self.ws, mnum)
                if mc is None:
                    continue
                valid = sum(
                    1 for r in range(5, 40)
                    if isinstance(self.ws.cell(r, mc).value, (int, float))
                )
                if valid > 5:
                    month_col_1based, cum_col_1based, month_num = mc, cc, mnum
                    break

        if month_col_1based is None:
            raise Exception("Cannot detect report month column on the techno sheet")
        if cum_col_1based is None:
            raise Exception("Cannot find 'Cum.' column on the techno sheet")

        self.month_col = month_col_1based - 1
        self.cum_col = cum_col_1based - 1
        self._detected_month_num = int(month_num)

    def detect_report_month(self):
        """Auto-detect report month from the FY cell + detected column.
        Only used when report_month was not provided externally."""
        if self.report_month:
            return

        start_year = 2026
        try:
            # The FY label ("2025-26") sits directly above the 'Cum.' column
            # in every sample file checked, regardless of how many legacy-year
            # columns precede it.
            fy = str(self.ws.cell(2, self.cum_col + 1).value)
            start_year = int(fy.split("-")[0])
        except Exception:
            pass

        month_num = getattr(self, "_detected_month_num", 4)
        year = start_year + (1 if month_num in (1, 2, 3) else 0)
        self.report_month = f"{year}-{month_num:02d}"

    def extract(self) -> List[Dict]:
        self.load_sheet()

        probe_labels = [
            lbl for unit in self.row_labels.values() for lbl in unit.values() if lbl
        ]
        # Probe near a representative early row (BF-1's bf_productivity, row 97
        # in the reference file) to detect whether this file's labels live in
        # column A or column B — some sheet variants insert an extra leading
        # serial-number column before the label.
        probe_row = next(
            (r for r in self.hardcoded_map.get("BF-1", {}).values()), 5)
        self.label_col = detect_label_column(self.ws, probe_row, probe_labels)

        self.detect_month_column()
        if not self.report_month:
            self.detect_report_month()

        year_i, month_i = map(int, self.report_month.split('-'))
        days_in_month = calendar.monthrange(year_i, month_i)[1]
        ytd_days = _ytd_days(year_i, month_i)

        records = []
        print("\n--- Starting RSP Techno Extraction ---\n")

        for unit_name, params in self.hardcoded_map.items():
            techno = {"month": {}, "till_month": {}}

            for param_key, configured_row in params.items():
                try:
                    expected_label = self.row_labels.get(unit_name, {}).get(param_key)
                    if expected_label:
                        row_num = verified_row(
                            self.ws, self.label_col, configured_row, expected_label,
                            window=20, context=f"{unit_name}/{param_key}")
                    elif unit_name == "BF-4" and param_key in _BF4_BLANK_ANCHOR_OFFSET:
                        # BF-4's row is unlabeled here — anchor off BF-1's
                        # verified row for the same param (see
                        # _BF4_BLANK_ANCHOR_OFFSET docstring above).
                        bf1_configured = self.hardcoded_map.get("BF-1", {}).get(param_key)
                        bf1_label = self.row_labels.get("BF-1", {}).get(param_key)
                        if bf1_configured and bf1_label:
                            bf1_row = verified_row(
                                self.ws, self.label_col, bf1_configured, bf1_label,
                                window=20, context=f"BF-1/{param_key}")
                            row_num = bf1_row + _BF4_BLANK_ANCHOR_OFFSET[param_key]
                        else:
                            row_num = configured_row
                    else:
                        row_num = configured_row

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
                    print(f"Warning: Could not read row {configured_row} for "
                          f"{unit_name}/{param_key}: {e}")

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
