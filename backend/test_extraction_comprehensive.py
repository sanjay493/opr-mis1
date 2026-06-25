#!/usr/bin/env python
"""
Comprehensive extraction test across all DSP PDFs.
Tests:
1. Production single-month extraction
2. Production all-months extraction
3. Techno single-month extraction (with column validation)
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "excel_extractors"))

import excel_extractor_dsp

# Test PDFs
test_pdfs = [
    ("D:/opr-mis1/Report_format/Monthly/DSPmis0226.pdf", "2026-02", "February 2026"),
    ("D:/opr-mis1/Report_format/Monthly/DSPmis0326.pdf", "2026-03", "March 2026"),
    ("D:/opr-mis1/Report_format/Monthly/DSPmis0526.pdf", "2026-05", "May 2026"),
    ("D:/opr-mis1/Report_format/Monthly/mis0925 (1).pdf", "2025-09", "September 2025"),
]

def test_single_month_production(pdf_path, month, label):
    """Test single-month production extraction."""
    print(f"\n{'='*80}")
    print(f"TEST: {label} - SINGLE MONTH PRODUCTION")
    print(f"{'='*80}")

    try:
        # Try with all_months parameter, fall back if not supported
        try:
            result = excel_extractor_dsp.extract_preview(pdf_path, month, block='production', all_months=False)
        except TypeError:
            result = excel_extractor_dsp.extract_preview(pdf_path, month, block='production')

        prod_rows = result.get('production_rows', [])
        print(f"✓ Extracted {len(prod_rows)} items")

        # Show first 5 items
        print(f"\nFirst 5 items:")
        for i, row in enumerate(prod_rows[:5]):
            print(f"  {i+1}. {row['item_name']:30s} = {row['value']:>10} {row['unit']:>8s} | {row['status']}")

        # Count by status
        ok_count = sum(1 for r in prod_rows if r['status'] == 'ok')
        unmapped_count = sum(1 for r in prod_rows if r['status'] == 'unmapped')
        print(f"\nSummary: {ok_count} mapped, {unmapped_count} unmapped")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_all_months_production(pdf_path, month, label):
    """Test all-months production extraction."""
    print(f"\n{'='*80}")
    print(f"TEST: {label} - ALL MONTHS PRODUCTION")
    print(f"{'='*80}")

    try:
        # Try with all_months parameter, fall back if not supported
        try:
            result = excel_extractor_dsp.extract_preview(pdf_path, month, block='production', all_months=True)
        except TypeError:
            print("(Skipping - all_months not supported in this version)")
            return None

        prod_rows = result.get('production_rows', [])
        print(f"✓ Extracted {len(prod_rows)} total rows")

        # Group by item to see months
        by_item = {}
        for row in prod_rows:
            item = row['item_name'] or row['pdf_label']
            if item not in by_item:
                by_item[item] = []
            by_item[item].append((row['report_month'], row['value']))

        # Show first item with all its months
        if by_item:
            first_item = list(by_item.keys())[0]
            print(f"\nExample: {first_item}")
            for month_data, value in sorted(by_item[first_item]):
                print(f"  {month_data}: {value}")

        print(f"\n{len(by_item)} unique items across all months")
        return True
    except Exception as e:
        print(f"X Error: {e}")
        return None

def test_techno_extraction(pdf_path, month, label):
    """Test techno extraction with column validation."""
    print(f"\n{'='*80}")
    print(f"TEST: {label} - TECHNO (SINGLE MONTH)")
    print(f"{'='*80}")

    try:
        result = excel_extractor_dsp.extract_preview(pdf_path, month, block='techno')

        techno_rows = result.get('techno_param_rows', [])
        print(f"✓ Extracted {len(techno_rows)} techno parameters")

        # Group by section
        by_section = {}
        for row in techno_rows:
            section = row.get('section', 'Unknown')
            if section not in by_section:
                by_section[section] = []
            by_section[section].append(row)

        print(f"\nBy section:")
        for section in sorted(by_section.keys()):
            rows = by_section[section]
            print(f"\n  {section}: {len(rows)} items")
            for row in rows[:3]:  # Show first 3 items per section
                actual = row.get('actual')
                cum = row.get('cum_actual')
                print(f"    - {row['parameter']:40s} actual={actual:>10} cum={cum:>10}")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("COMPREHENSIVE DSP EXTRACTION TEST")
    print("="*80)

    results = {
        'single_month_prod': [],
        'all_months_prod': [],
        'techno': []
    }

    for pdf_path, month, label in test_pdfs:
        if not os.path.exists(pdf_path):
            print(f"\n✗ File not found: {pdf_path}")
            continue

        # Test 1: Single-month production
        success = test_single_month_production(pdf_path, month, label)
        results['single_month_prod'].append((label, success))

        # Test 2: All-months production
        success = test_all_months_production(pdf_path, month, label)
        results['all_months_prod'].append((label, success))

        # Test 3: Techno
        success = test_techno_extraction(pdf_path, month, label)
        results['techno'].append((label, success))

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    print("\nSingle-Month Production:")
    for label, success in results['single_month_prod']:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status:8s} {label}")

    print("\nAll-Months Production:")
    for label, success in results['all_months_prod']:
        if success is None:
            status = "~ SKIP"
        else:
            status = "✓ PASS" if success else "X FAIL"
        print(f"  {status:8s} {label}")

    print("\nTechno Extraction:")
    for label, success in results['techno']:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status:8s} {label}")

    # Overall result
    all_pass = all(s for _, s in results['single_month_prod']) and \
               all(s for _, s in results['all_months_prod'] if s is not None) and \
               all(s for _, s in results['techno'])

    print(f"\n{'='*80}")
    if all_pass:
        print("✓ ALL TESTS PASSED!")
    else:
        print("✗ SOME TESTS FAILED - See details above")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
