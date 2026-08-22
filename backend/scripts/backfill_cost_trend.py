"""
One-time backfill: extracts Apr-Jul 2026 Variable/Fixed cost (HM/CS/SS, all
6 plants) from the Report_format/Cost/ workbooks and writes them into
cost_trend_monthly, both the Month column (from the single-month files) and
the Till Month column (from the "APRIL-<month>" cumulative files). April has
no separate cumulative file since it's the FY's first month — its Till
Month is just its own Month value, written from the same extraction.

Run once from backend/: ../venv/Scripts/python.exe scripts/backfill_cost_trend.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from excel_extractors.excel_extractor_cost_trend import PLANT_ORDER, extract_cost_trend_workbook

_COST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Report_format", "Cost")

_MONTH_FILES = ["ELHM CS SS APRIL26.xlsx", "ELHM CS SS MAY26.xlsx", "ELHM CS SS JUNE26.xlsx", "ELHM CS SS JULY26.xlsx"]
_TILL_FILES = ["ELHM CS SS APRIL-MAY26.xlsx", "ELHM CS SS APRIL-JUNE26.xlsx", "ELHM CS SS APRIL-JULY26.xlsx"]


def _entries_for_product(plants: dict) -> list:
    entries = []
    for plant in PLANT_ORDER:
        cell = plants.get(plant, {})
        if cell.get("variable") is not None:
            entries.append({"cost_type": "VARIABLE", "plant": plant, "value": cell["variable"]})
        if cell.get("fixed") is not None:
            entries.append({"cost_type": "FIXED", "plant": plant, "value": cell["fixed"]})
    return entries


def _save(extracted: dict, field: str, report_month_override: str = None):
    report_month = report_month_override or extracted["report_month"]
    for product, plants in extracted["products"].items():
        entries = _entries_for_product(plants)
        n = db.save_cost_trend_monthly_field(report_month, product, entries, field)
        print(f"  {report_month} {product} {field}: {n} cells")


def main():
    print("=== Month-value files ===")
    for fname in _MONTH_FILES:
        path = os.path.join(_COST_DIR, fname)
        print(fname)
        extracted = extract_cost_trend_workbook(path)
        assert not extracted["is_till_month"], f"{fname} unexpectedly parsed as a till-month file"
        _save(extracted, "month_value")
        if fname == "ELHM CS SS APRIL26.xlsx":
            print("  (April has no separate cumulative file — its till-month = its own month value)")
            _save(extracted, "till_month_value")

    print("=== Till-month (cumulative) files ===")
    for fname in _TILL_FILES:
        path = os.path.join(_COST_DIR, fname)
        print(fname)
        extracted = extract_cost_trend_workbook(path)
        assert extracted["is_till_month"], f"{fname} unexpectedly parsed as a month-value file"
        _save(extracted, "till_month_value")

    print("Done.")


if __name__ == "__main__":
    main()
