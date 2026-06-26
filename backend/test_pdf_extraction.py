#!/usr/bin/env python3
"""Test PDF extraction to understand page 14 structure"""

import sys
import json

try:
    import pdfplumber

    pdf_file = r"d:\opr-mis1\Report_format\monthly\flash-apr26.pdf"

    print("[STEP 1] Opening PDF...")
    with pdfplumber.open(pdf_file) as pdf:
        print(f"[OK] Total pages in PDF: {len(pdf.pages)}")

        # Check page 14 (index 13)
        if len(pdf.pages) > 13:
            page = pdf.pages[13]
            print(f"[OK] Page 14 found")

            # Extract tables
            tables = page.extract_tables()
            print(f"[OK] Tables found on page 14: {len(tables) if tables else 0}")

            if tables and len(tables) > 0:
                table = tables[0]
                print(f"[OK] First table dimensions: {len(table)} rows x {len(table[0]) if table else 0} cols")

                # Print first 10 rows to understand structure
                print("\n[PREVIEW] First 10 rows of table:\n")
                for i, row in enumerate(table[:10]):
                    print(f"  Row {i:2d}: {row}")

                # Try to identify furnaces and parameters
                print("\n" + "="*80)
                print("[ANALYSIS]")
                print("="*80)

                # Check for furnace columns
                header_row = None
                for row_idx, row in enumerate(table[:3]):
                    row_text = " ".join(str(c) for c in row).upper()
                    if any(bf in row_text for bf in ["BF-4", "BF-6", "BF-7", "BF-8"]):
                        header_row = row_idx
                        print(f"[OK] Header row found at index {row_idx}")
                        print(f"     Headers: {row}")
                        break

                if not header_row:
                    print("[WARN] Could not find furnace headers (BF-4, BF-6, BF-7, BF-8)")
                    print("[INFO] Check if different page or different table structure")
            else:
                print("[WARN] No tables found on page 14")
                print("[INFO] Trying to extract all text...")
                text = page.extract_text()
                print(f"[INFO] Page text length: {len(text) if text else 0} chars")
                if text:
                    lines = text.split('\n')[:15]
                    print("[INFO] First 15 lines of page:")
                    for i, line in enumerate(lines):
                        print(f"  {i:2d}: {line}")
        else:
            print(f"[ERROR] PDF has only {len(pdf.pages)} pages, page 14 not available")
            print("[INFO] Available pages: 1 to", len(pdf.pages))

except ImportError as e:
    print(f"[ERROR] Missing module: {e}")
    print("[INFO] Install with: pip install pdfplumber")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("[DONE]")
