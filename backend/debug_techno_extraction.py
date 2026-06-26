#!/usr/bin/env python
"""
Debug script to understand why techno extraction returns 0 rows for April 2025.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "excel_extractors"))

import pdfplumber
from excel_extractors.pdf_extractor_dsp import (
    _scan_page_index, _month_header, _parse_te_nums, _slice_text,
    _MM_MSM_PARAMS, _MAJOR_PAGE_DEFS, _COKE_PAGE_DEFS
)

pdf_path = r"d:\opr-mis1\Report_format\Monthly\mis0425.pdf"
report_month = "2025-04"

print("\n" + "="*100)
print("DEBUG: TECHNO EXTRACTION FOR APRIL 2025")
print("="*100)

print(f"\nFile: {pdf_path}")
print(f"Month: {report_month}")

# Step 1: Open PDF and scan for pages
print(f"\n{'-'*100}")
print("STEP 1: SCAN PAGE INDEX")
print(f"{'-'*100}")

with pdfplumber.open(pdf_path) as pdf:
    n_pages = len(pdf.pages)
    print(f"\nTotal pages in PDF: {n_pages}")

    # Get text from all pages
    page_texts = [pdf.pages[i].extract_text() or "" for i in range(n_pages)]

    # Scan page index
    page_index = _scan_page_index(pdf_path, max_pages=n_pages)

    print(f"\nPage index found: {page_index}")
    print(f"Keys in page_index: {list(page_index.keys())}")

    # Check if expected keys are present
    expected_keys = ['prod', 'major', 'sms', 'coke', 'sint', 'bf_cdi', 'mm', 'wa', 'ss']
    print(f"\nExpected keys: {expected_keys}")
    found_keys = [k for k in expected_keys if k in page_index]
    missing_keys = [k for k in expected_keys if k not in page_index]
    print(f"Found keys: {found_keys}")
    print(f"Missing keys: {missing_keys}")

    # Step 2: Check if techno pages exist and their content
    print(f"\n{'-'*100}")
    print("STEP 2: CHECK TECHNO PAGES")
    print(f"{'-'*100}")

    techno_keys = ['mm', 'major', 'sms', 'coke', 'sint', 'bf_cdi', 'wa']
    for key in techno_keys:
        if key in page_index:
            page_no = page_index[key]
            print(f"\n[{key.upper()}] Page {page_no}:")
            text = page_texts[page_no]
            lines = text.splitlines()
            print(f"  Lines: {len(lines)}")
            print(f"  First 5 lines:")
            for i, line in enumerate(lines[:5]):
                try:
                    print(f"    {i}: {line[:80]}")
                except:
                    print(f"    {i}: [encoding error]")

            # Try to detect month header
            month_cols = _month_header(lines)
            print(f"  Month columns detected: {month_cols}")
        else:
            print(f"\n[{key.upper()}] NOT FOUND in page_index")

    # Step 3: Try to extract Merchant Mill parameters
    print(f"\n{'-'*100}")
    print("STEP 3: TEST MERCHANT MILL EXTRACTION")
    print(f"{'-'*100}")

    mm_idx = page_index.get('mm')
    if mm_idx is not None:
        text = page_texts[mm_idx]
        lines = text.splitlines()

        print(f"\nMerchant Mill page {mm_idx}:")
        print(f"  Total lines: {len(lines)}")

        # Try to slice Merchant Mill section
        mm_lines = _slice_text(text, "TE PARAMETERS - MERCHANT MILL",
                               ["PRODUCTION - MSM", "TE PARAMETERS - MSM"])
        print(f"  Lines in MM section: {len(mm_lines)}")
        print(f"  First 10 MM section lines:")
        for i, line in enumerate(mm_lines[:10]):
            try:
                print(f"    {i}: {line[:80]}")
            except:
                print(f"    {i}: [encoding error]")

        # Show parameter list
        params = _MM_MSM_PARAMS.get("Merchant Mill", [])
        print(f"\n  Parameter list for Merchant Mill: {len(params)} items")
        for i, (keyword, label, unit, sort) in enumerate(params[:5]):
            print(f"    {i}: keyword='{keyword}' -> label='{label}'")

            # Try to find this keyword in the section
            found = False
            for line_no, line in enumerate(mm_lines):
                if keyword in line.lower():
                    try:
                        print(f"       FOUND on line {line_no}: {line[:80]}")
                    except:
                        print(f"       FOUND on line {line_no}: [encoding error]")
                    found = True
                    # Try to parse numbers
                    nums = _parse_te_nums(line)
                    print(f"       Parsed numbers: {nums}")
                    break
            if not found:
                print(f"       NOT FOUND in section")
    else:
        print("\nMerchant Mill page NOT FOUND in page_index")

    # Step 4: Check Major Techno
    print(f"\n{'-'*100}")
    print("STEP 4: TEST MAJOR TECHNO EXTRACTION")
    print(f"{'-'*100}")

    major_idx = page_index.get('major')
    if major_idx is not None:
        text = page_texts[major_idx]
        lines = text.splitlines()

        print(f"\nMajor Techno page {major_idx}:")
        print(f"  Total lines: {len(lines)}")
        print(f"  First 10 lines:")
        for i, line in enumerate(lines[:10]):
            try:
                print(f"    {i}: {line[:80]}")
            except:
                print(f"    {i}: [encoding error]")

        # Try to detect month header
        month_cols = _month_header(lines)
        print(f"\n  Month columns: {month_cols}")

        # Show parameter list
        params = _MAJOR_PAGE_DEFS
        print(f"\n  Parameter list for Major Techno: {len(params)} items")
        for i, (keyword, group_code, section, label, unit, sort) in enumerate(params[:5]):
            print(f"    {i}: keyword='{keyword}' -> section='{section}' label='{label}'")

            # Try to find this keyword
            found = False
            for line_no, line in enumerate(lines):
                if keyword in line.lower():
                    try:
                        print(f"       FOUND on line {line_no}: {line[:80]}")
                    except:
                        print(f"       FOUND on line {line_no}: [encoding error]")
                    found = True
                    break
            if not found:
                print(f"       NOT FOUND in section")
    else:
        print("\nMajor Techno page NOT FOUND in page_index")

print(f"\n{'='*100}")
print("DEBUG COMPLETE")
print(f"{'='*100}\n")
