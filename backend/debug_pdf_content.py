#!/usr/bin/env python
"""
Debug script to extract and display full PRODUCTION MONTHWISE page content
from DSP OMI PDF reports.
"""

import sys
import pdfplumber

def extract_production_page(pdf_path):
    """Extract and print full content of PRODUCTION MONTHWISE page."""

    print("=" * 80)
    print(f"PDF File: {pdf_path}")
    print("=" * 80)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Total pages in PDF: {len(pdf.pages)}\n")

            # Search for PRODUCTION MONTHWISE page (with actual data, not index)
            prod_page_idx = None
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                lines = text.splitlines()

                # Look for PRODUCTION MONTHWISE with month headers (APR, MAY, etc.)
                has_months = any(month in text.upper() for month in ['APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'])
                has_heading = "PRODUCTION MONTHWISE" in text.upper()

                if has_heading and has_months:
                    prod_page_idx = i
                    print(f"✓ Found PRODUCTION MONTHWISE DATA on page {i + 1} (index {i})\n")
                    break

            # If not found with months, just look for the heading (it's the index)
            if prod_page_idx is None:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if "PRODUCTION MONTHWISE" in text.upper():
                        print(f"⚠ Found 'PRODUCTION MONTHWISE' on page {i + 1} but it's likely the INDEX")
                        print(f"  Looking for actual data page (should be a few pages after)...\n")
                        break

            if prod_page_idx is None:
                print("✗ PRODUCTION MONTHWISE page NOT FOUND!")
                print("\nSearching for any page with 'PRODUCTION':")
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if "PRODUCTION" in text.upper():
                        print(f"  Page {i + 1}: {text[:100]}...")
                return

            # Extract and display full page
            page = pdf.pages[prod_page_idx]
            text = page.extract_text() or ""
            lines = text.splitlines()

            print("=" * 80)
            print("FULL PAGE CONTENT (line-by-line):")
            print("=" * 80)

            for line_no, line in enumerate(lines):
                print(f"Line {line_no:3d}: {line}")

            print("=" * 80)
            print(f"Total lines: {len(lines)}")
            print("=" * 80)

            # Analysis
            print("\nANALYSIS:")
            print("-" * 80)

            # Find header row
            header_found = False
            for i, line in enumerate(lines):
                if any(month in line.upper() for month in ['APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']):
                    print(f"✓ Month header at line {i}: {line}")
                    header_found = True
                    break

            if not header_found:
                print("✗ Month header NOT found!")

            # Find data rows
            print(f"\nData rows (containing numbers):")
            for i, line in enumerate(lines):
                tokens = line.split()
                numbers = [t for t in tokens if t.replace(',', '').replace('.', '').isdigit()]
                if numbers and i > 5:  # Skip header area
                    print(f"  Line {i}: {line[:70]}... → {len(numbers)} numbers")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    pdf_file = r"D:\opr-mis1\Report_format\Monthly\mis0925 (1).pdf"
    extract_production_page(pdf_file)
