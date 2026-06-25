#!/usr/bin/env python
"""
Debug script to show exactly which columns are being detected and extracted.
Run with: python debug_dsp_columns.py path/to/pdf month
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pdfplumber

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

def _month_header(lines):
    """Returns the month-column list from a header line."""
    for ln in lines[:15]:
        toks = [t.upper().rstrip('.') for t in ln.split()]
        cols = [t for t in toks if t in _MONTHS]
        if cols and "TOTAL" in toks:
            return cols
    return None

def debug_columns(pdf_path, report_month="2025-09"):
    """Show column detection for production page."""

    print("=" * 100)
    print(f"PDF: {pdf_path}")
    print(f"Report Month: {report_month}")
    print("=" * 100)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Find production page
            page_idx = None
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if "PRODUCTION MONTHWISE" in text.upper() and any(m in text for m in _MONTHS):
                    page_idx = i
                    break

            if page_idx is None:
                print("✗ Production page not found!")
                return

            print(f"\n✓ Production page: {page_idx + 1}\n")

            text = pdf.pages[page_idx].extract_text() or ""
            lines = text.splitlines()

            # Detect month header
            month_cols = _month_header(lines)
            print(f"Detected month columns: {month_cols}")
            print(f"Number of month columns: {len(month_cols)}")

            # Parse report month
            y, m = int(report_month[:4]), int(report_month[5:7])
            want_mon = _MONTHS[m - 1]

            if want_mon not in month_cols:
                print(f"✗ {want_mon} not in columns!")
                return

            m_idx = month_cols.index(want_mon)
            print(f"\nRequested month: {want_mon}")
            print(f"Position in month list: index {m_idx}")
            print(f"Full month list: {month_cols}")
            print(f"Month list with indices:")
            for i, m in enumerate(month_cols):
                marker = " ← WANT" if m == want_mon else ""
                print(f"  [{i}] {m}{marker}")

            # Find header row
            print(f"\n--- Header Row Analysis ---")
            header_row = None
            for ln in lines[:20]:
                if month_cols[0] in ln.upper():
                    header_row = ln
                    break

            if header_row:
                print(f"Header row: {header_row[:100]}")
                toks = header_row.split()
                print(f"Header tokens ({len(toks)} total):")
                for i, t in enumerate(toks):
                    marker = ""
                    if t.upper() in month_cols:
                        marker = " ← MONTH"
                    elif t.upper() in ("Q1", "Q2", "H1", "TOTAL"):
                        marker = " ← AGGREGATE"
                    print(f"  [{i}] {t}{marker}")

            # Show first data row
            print(f"\n--- First Data Row ---")
            for ln in lines:
                tokens = ln.split()
                nums = []
                for t in reversed(tokens):
                    try:
                        v = float(t.replace(',', ''))
                        nums.insert(0, v)
                    except:
                        break

                if nums and len(nums) >= len(month_cols):
                    label = " ".join(tokens[:len(tokens)-len(nums)])
                    if label.strip():
                        print(f"Item: {label}")
                        print(f"Numbers extracted: {nums}")
                        print(f"Number count: {len(nums)}")
                        print(f"\nData by month:")
                        for i, num in enumerate(nums):
                            month_name = month_cols[i] if i < len(month_cols) else f"[{i}]"
                            marker = " ← EXTRACTING THIS" if i == m_idx else ""
                            print(f"  nums[{i}] = {num:>10} ({month_name}){marker}")
                        break

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    pdf_file = r"D:\opr-mis1\Report_format\Monthly\mis0925 (1).pdf"
    report_month = "2025-09"

    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    if len(sys.argv) > 2:
        report_month = sys.argv[2]

    debug_columns(pdf_file, report_month)
