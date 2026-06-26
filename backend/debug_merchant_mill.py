#!/usr/bin/env python
"""
Debug script to show extracted Merchant Mill techno data from DSP PDF.
Displays: month header, month_diff, and all extracted values.
"""

import sys
import pdfplumber
from excel_extractors.pdf_extractor_dsp import (
    _find_page_by_heading, _slice_text, _month_header, _parse_te_nums, _te_values,
    _MM_MSM_PARAMS
)

def debug_merchant_mill(pdf_path, report_month="2025-09"):
    """Extract and display Merchant Mill techno data."""

    print("=" * 100)
    print(f"PDF: {pdf_path}")
    print(f"Report Month: {report_month}")
    print("=" * 100)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Find page
            page_index = _find_page_by_heading(
                [p.extract_text() or "" for p in pdf.pages],
                "TE PARAMETERS - MERCHANT MILL"
            )

            if page_index is None:
                print("✗ Merchant Mill page NOT found!")
                return

            print(f"\n✓ Found Merchant Mill page: {page_index + 1} (index {page_index})\n")

            # Extract text
            page_text = pdf.pages[page_index].extract_text() or ""
            lines = page_text.splitlines()

            # Detect month header
            month_cols = _month_header(lines)
            print(f"Detected month columns: {month_cols}")

            if not month_cols:
                print("✗ No month header found!")
                return

            # Parse report month
            y, m = int(report_month[:4]), int(report_month[5:7])
            months_3 = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                       "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
            want_mon = months_3[m - 1]

            # Calculate month_diff
            if want_mon not in month_cols:
                print(f"✗ Requested month {want_mon} not in columns!")
                return

            month_diff = len(month_cols) - 1 - month_cols.index(want_mon)
            print(f"Requested month: {want_mon}")
            print(f"Month position in list: {month_cols.index(want_mon)}")
            print(f"Calculated month_diff: {month_diff}\n")

            # Extract Merchant Mill section
            mm_lines = _slice_text(page_text, "TE PARAMETERS - MERCHANT MILL",
                                   ["PRODUCTION - MSM", "TE PARAMETERS - MSM"])

            print("=" * 100)
            print("MERCHANT MILL PARAMETERS")
            print("=" * 100)

            # Get parameter definitions
            mm_params = _MM_MSM_PARAMS.get("Merchant Mill", [])

            print(f"\nParameter list ({len(mm_params)} items):\n")

            extracted_count = 0
            for keyword, label, unit, sort in mm_params:
                found = False
                for ln in mm_lines:
                    if keyword in ln.lower():
                        found = True
                        # Parse numbers
                        nums = _parse_te_nums(ln)
                        actual, cum = _te_values(nums, month_diff)

                        print(f"✓ {label:40s} | Unit: {unit:8s}")
                        print(f"  Keyword match: '{keyword}'")
                        print(f"  Found in line: {ln[:80]}")
                        print(f"  Parsed numbers: {nums}")
                        print(f"  Actual value:   {actual} (index: -{4 + month_diff} = nums[{-4-month_diff}])")
                        print(f"  Cumulative:     {cum} (index: -3)")
                        print()

                        if actual is not None:
                            extracted_count += 1
                        break

                if not found:
                    print(f"✗ {label:40s} | NOT FOUND")
                    print(f"  Searching for keyword: '{keyword}'")
                    # Show lines that start with similar patterns
                    for ln in mm_lines[:20]:
                        if len(ln.strip()) > 0:
                            print(f"    {ln[:80]}")
                    print()

            print("=" * 100)
            print(f"SUMMARY: Extracted {extracted_count}/{len(mm_params)} parameters")
            print("=" * 100)

            # Show all lines in Merchant Mill section for reference
            print(f"\nAll lines in Merchant Mill section ({len(mm_lines)} lines):\n")
            for i, ln in enumerate(mm_lines):
                print(f"{i:3d}: {ln}")

    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    pdf_file = r"D:\opr-mis1\Report_format\Monthly\mis0925 (1).pdf"
    report_month = "2025-09"

    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    if len(sys.argv) > 2:
        report_month = sys.argv[2]

    debug_merchant_mill(pdf_file, report_month)
