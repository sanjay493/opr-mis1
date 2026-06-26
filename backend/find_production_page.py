#!/usr/bin/env python
"""
Find which page has PRODUCTION MONTHWISE data by scanning all pages.
"""

import pdfplumber

pdf_file = r"D:\opr-mis1\Report_format\Monthly\mis0925 (1).pdf"

print("=" * 100)
print(f"Scanning all pages in: {pdf_file}")
print("=" * 100)

with pdfplumber.open(pdf_file) as pdf:
    print(f"Total pages: {len(pdf.pages)}\n")

    for page_idx in range(len(pdf.pages)):
        page = pdf.pages[page_idx]
        text = page.extract_text() or ""
        lines = text.splitlines()

        # Check for key indicators
        has_production = "PRODUCTION" in text.upper()
        has_monthwise = "MONTHWISE" in text.upper()
        has_months = any(m in text.upper() for m in ['APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT'])
        has_toc = "INDEX" in text.upper() or "CONTENTS" in text.upper()

        # Show summary
        print(f"Page {page_idx + 1} (index {page_idx}):")
        print(f"  Lines: {len(lines)}")
        print(f"  Has 'PRODUCTION': {has_production}")
        print(f"  Has 'MONTHWISE': {has_monthwise}")
        print(f"  Has month names: {has_months}")
        print(f"  Has 'INDEX'/'CONTENTS': {has_toc}")

        if has_production or has_monthwise or has_months:
            print(f"  First 10 lines:")
            for i, line in enumerate(lines[:10]):
                print(f"    {i}: {line[:80]}")
        print()

print("=" * 100)
print("ANALYSIS:")
print("=" * 100)
print("""
Look for a page that has:
  ✓ Has 'PRODUCTION': True
  ✓ Has 'MONTHWISE': True
  ✓ Has month names: True
  ✓ Has 'INDEX'/'CONTENTS': False

That page contains the actual production data you need!

Once you identify the page, update the PDF extractor to use that page index.
""")
