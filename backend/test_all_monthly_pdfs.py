#!/usr/bin/env python
"""
Test extraction for ALL monthly DSP PDFs (Apr'25 - Mar'26 FY).
Verifies both current and prior year techno extraction.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "excel_extractors"))

import excel_extractor_dsp

# All monthly PDFs for FY 2025-26 (Apr'25 to Mar'26)
test_cases = [
    ("d:/opr-mis1/Report_format/Monthly/mis0425.pdf", "2025-04", "April 2025"),
    ("d:/opr-mis1/Report_format/Monthly/mis0625.pdf", "2025-06", "June 2025"),
    ("d:/opr-mis1/Report_format/Monthly/mis0725.pdf", "2025-07", "July 2025"),
    ("d:/opr-mis1/Report_format/Monthly/DSP mis0825 (1).pdf", "2025-08", "August 2025"),
    ("d:/opr-mis1/Report_format/Monthly/mis0925 (1).pdf", "2025-09", "September 2025"),
    ("d:/opr-mis1/Report_format/Monthly/mis1025.pdf", "2025-10", "October 2025"),
    ("d:/opr-mis1/Report_format/Monthly/mis1125.pdf", "2025-11", "November 2025"),
    ("d:/opr-mis1/Report_format/Monthly/mis1225.pdf", "2025-12", "December 2025"),
    ("d:/opr-mis1/Report_format/Monthly/mis0126 DSP.pdf", "2026-01", "January 2026"),
    ("d:/opr-mis1/Report_format/Monthly/DSPmis0226.pdf", "2026-02", "February 2026"),
    ("d:/opr-mis1/Report_format/Monthly/DSPmis0326.pdf", "2026-03", "March 2026"),
]

def test_techno_extraction(pdf_path, month, label):
    """Test techno extraction for a single PDF."""
    if not os.path.exists(pdf_path):
        return None, f"File not found: {pdf_path}"

    try:
        result = excel_extractor_dsp.extract_preview(pdf_path, month, block='techno')
        techno_rows = result.get('techno_param_rows', [])

        # Group by parameter and month to show both current and prior year
        by_param = {}
        for row in techno_rows:
            param = row.get('parameter', 'Unknown')
            section = row.get('section', '')
            month_val = row.get('month', 'N/A')
            actual = row.get('actual')
            cum = row.get('cum_actual')

            key = f"{section} - {param}"
            if key not in by_param:
                by_param[key] = []
            by_param[key].append({
                'month': month_val,
                'actual': actual,
                'cum': cum
            })

        # Count current and prior year rows
        current_year_count = sum(1 for r in techno_rows if f"{month[:4]}" in r.get('month', ''))
        prior_year_count = sum(1 for r in techno_rows if f"{int(month[:4])-1}" in r.get('month', ''))

        return {
            'total': len(techno_rows),
            'current_year': current_year_count,
            'prior_year': prior_year_count,
            'by_param': by_param,
            'samples': list(by_param.items())[:3]  # First 3 parameters
        }, None

    except Exception as e:
        return None, str(e)

def main():
    print("\n" + "="*100)
    print("TESTING ALL MONTHLY DSP PDFs (FY 2025-26)")
    print("="*100)

    results = {}
    errors = {}

    for pdf_path, month, label in test_cases:
        print(f"\n{'-'*100}")
        print(f"[TEST] {label}")
        print(f"   File: {os.path.basename(pdf_path)}")
        print(f"   Month: {month}")

        result, error = test_techno_extraction(pdf_path, month, label)

        if error:
            print(f"   [ERROR] {error}")
            errors[label] = error
            continue

        if result is None:
            print(f"   [SKIP] File not found")
            continue

        print(f"   [OK] Extracted {result['total']} techno rows")
        print(f"      Current year: {result['current_year']} rows")
        print(f"      Prior year:   {result['prior_year']} rows")

        # Show sample parameters
        if result['samples']:
            print(f"\n   Sample parameters (showing current + prior year):")
            for param_key, months_data in result['samples']:
                print(f"\n      [{param_key}]")
                for month_data in months_data:
                    actual_str = f"{month_data['actual']:.1f}" if month_data['actual'] else "None"
                    cum_str = f"{month_data['cum']:.1f}" if month_data['cum'] else "None"
                    year_marker = "[25]" if month_data['month'].startswith("2025") else "[24]"
                    print(f"         {year_marker} {month_data['month']}: actual={actual_str:>8s}, cum={cum_str:>8s}")

        results[label] = result

    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY")
    print(f"{'='*100}\n")

    print(f"{'PDF File':<25s} {'Status':<15s} {'Total':<8s} {'Current':<10s} {'Prior':<10s}")
    print(f"{'-'*70}")

    total_success = 0
    total_rows = 0
    total_current = 0
    total_prior = 0

    for label, result in results.items():
        status = "[OK]" if result else "[ERROR]"
        total_rows_val = result['total'] if result else 0
        current_val = result['current_year'] if result else 0
        prior_val = result['prior_year'] if result else 0

        print(f"{label:<25s} {status:<15s} {total_rows_val:<8d} {current_val:<10d} {prior_val:<10d}")

        if result:
            total_success += 1
            total_rows += total_rows_val
            total_current += current_val
            total_prior += prior_val

    print(f"{'-'*70}")
    print(f"{'TOTAL':<25s} {'':<15s} {total_rows:<8d} {total_current:<10d} {total_prior:<10d}")

    if errors:
        print(f"\n[ERRORS] ({len(errors)}):")
        for label, error_msg in errors.items():
            print(f"   - {label}: {error_msg}")

    print(f"\n{'='*100}")
    print(f"[SUCCESS] Extraction successful on {total_success}/{len(results)} PDFs")
    print(f"   Total techno parameters: {total_rows}")
    print(f"   Current year (FY 25-26): {total_current}")
    print(f"   Prior year (FY 24-25):   {total_prior}")
    print(f"\nRatio check: Prior should be ~50% of current (each param appears twice)")
    if total_current > 0:
        ratio = (total_prior / total_current) * 100
        print(f"   Actual ratio: {ratio:.1f}%")
        if ratio >= 45 and ratio <= 55:
            print(f"   [OK] RATIO OK")
        else:
            print(f"   [WARN] RATIO OFF - May indicate missing prior year data")
    print(f"{'='*100}\n")

if __name__ == "__main__":
    main()
