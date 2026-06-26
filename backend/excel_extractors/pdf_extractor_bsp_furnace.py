"""
BSP Furnace-wise Techno Data Extractor from PDF

Extracts individual blast furnace parameters from:
  File: flash-apr26.pdf
  Page: 14 (Blast Furnace Techno Data)

Layout on page 14:
  Row headers: Parameter names (Coke Rate, BF Productivity, etc.)
  Column headers: Furnace names (BF-4, BF-6, BF-7, BF-8)
  Values: Individual furnace metric values

Output format:
  Furnace-wise data in JSON format:
  {
    'BF-4': {
      'Coke Rate': {'value': 425.5, 'unit': 'Kg/THM'},
      'BF Productivity': {'value': 2.15, 'unit': 'T/m³/day'},
      ...
    },
    'BF-6': {...},
    ...
  }
"""

import logging
import re
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path

try:
    import pdfplumber
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False

logger = logging.getLogger("pdf_extractor_furnace")

PLANT = "BSP"

# Blast furnace names in BSP
FURNACES = ["BF-4", "BF-6", "BF-7", "BF-8"]

# Parameter definitions with units
PARAM_UNITS = {
    'Coke Rate': 'Kg/THM',
    'BF Productivity': 'T/m³/day',
    'CDI Rate': 'Kg/THM',
    'Fuel Rate': 'Kg/THM',
    'O2 Enrichment': '%',
    'Sinter in Burden': '%',
    'Pellet in Burden': '%',
    'BF Coke Rate': 'Kg/THM',
    'Slag Rate': 'Kg/THM',
    'Hot Blast Temp': '°C',
    'Coke Breeze Rate': 'Kg/THM',
    'Silicon Carbide Rate': 'Kg/THM',
}


def _clean_value(val) -> Optional[float]:
    """
    Clean and parse numeric values from PDF text

    Handles:
      - Leading/trailing spaces
      - Commas as thousand separators
      - Dashes/missing values
      - Scientific notation
    """
    if val is None:
        return None

    s = str(val).strip()

    # Handle missing/invalid values
    if s in ('', '-', '—', 'N/A', 'NA', 'nan', 'NaN'):
        return None

    try:
        # Remove comma separators
        s = s.replace(',', '')
        return float(s)
    except (ValueError, TypeError):
        return None


def extract_from_pdf(file_path: str, report_month: str) -> Dict[str, Dict[str, Any]]:
    """
    Extract furnace-wise blast furnace data from PDF page 14

    Args:
        file_path: Path to flash-apr26.pdf
        report_month: "YYYY-MM" format (e.g., "2026-04")

    Returns:
        Dictionary of furnace data:
        {
          'BF-4': {'Coke Rate': {value, unit, source}, ...},
          'BF-6': {...},
          ...
        }
    """

    if not _PDF_AVAILABLE:
        raise ImportError(
            "pdfplumber is required. Install with: pip install pdfplumber"
        )

    try:
        with pdfplumber.open(file_path) as pdf:
            # Page 14 is index 13 (0-indexed)
            page = pdf.pages[13]

            # Extract table from page
            tables = page.extract_tables()

            if not tables:
                logger.warning(f"No tables found on page 14 of {file_path}")
                return {}

            # Usually page 14 has one main table
            table = tables[0]

            furnace_data = _parse_furnace_table(table)

            logger.info(f"Extracted {len(furnace_data)} furnaces from PDF")

            return furnace_data

    except Exception as e:
        logger.error(f"Error extracting from {file_path}: {e}")
        raise


def _parse_furnace_table(table: List[List[str]]) -> Dict[str, Dict[str, Any]]:
    """
    Parse furnace data from extracted PDF table

    Table structure:
      Row 0: Headers (Parameter, BF-4, BF-6, BF-7, BF-8, ...)
      Row 1+: Parameter data

    Returns:
      {
        'BF-4': {param: {value, unit, source}, ...},
        'BF-6': {...},
        ...
      }
    """

    if not table or len(table) < 2:
        logger.warning("Table has insufficient rows")
        return {}

    # Find header row with furnace names
    header_row = None
    furnace_cols = {}  # {furnace_name: column_index}

    for row_idx, row in enumerate(table):
        for col_idx, cell in enumerate(row):
            if cell and any(f in str(cell).upper() for f in ["BF-4", "BF-6", "BF-7", "BF-8"]):
                header_row = row_idx
                # Map furnace names to column indices
                for furnace in FURNACES:
                    for col_i, cell_val in enumerate(row):
                        if cell_val and furnace.upper() in str(cell_val).upper():
                            furnace_cols[furnace] = col_i
                break
        if header_row is not None:
            break

    if not furnace_cols:
        logger.warning("Could not find furnace columns in table")
        return {}

    # Initialize furnace data structure
    result = {furnace: {} for furnace in FURNACES}

    # Parse parameter rows
    for row_idx in range(header_row + 1, len(table)):
        row = table[row_idx]

        if not row or not row[0]:
            continue

        # First column is parameter name
        param_raw = str(row[0]).strip()

        # Try to match with known parameters
        matched_param = None
        for known_param in PARAM_UNITS.keys():
            if known_param.lower() in param_raw.lower():
                matched_param = known_param
                break

        if not matched_param:
            # Try partial match
            for known_param in PARAM_UNITS.keys():
                words = param_raw.lower().split()
                if any(w in known_param.lower() for w in words if len(w) > 3):
                    matched_param = known_param
                    break

        if not matched_param:
            logger.debug(f"Could not match parameter: {param_raw}")
            continue

        # Extract values for each furnace
        for furnace, col_idx in furnace_cols.items():
            if col_idx < len(row):
                value = _clean_value(row[col_idx])

                if value is not None:
                    result[furnace][matched_param] = {
                        'value': value,
                        'unit': PARAM_UNITS[matched_param],
                        'source': 'PDF'
                    }

    return result


def extract_and_preview(file_path: str, report_month: str) -> Tuple[Dict, str]:
    """
    Extract data and return preview before inserting to DB

    Returns:
      (furnace_data, preview_text)
    """

    furnace_data = extract_from_pdf(file_path, report_month)

    # Generate preview
    preview = _generate_preview(furnace_data, report_month)

    return furnace_data, preview


def _generate_preview(furnace_data: Dict[str, Dict[str, Any]], report_month: str) -> str:
    """Generate human-readable preview of extracted data"""

    lines = []
    lines.append(f"\n{'='*80}")
    lines.append(f"BSP FURNACE-WISE TECHNO DATA EXTRACTION PREVIEW")
    lines.append(f"{'='*80}")
    lines.append(f"Report Month: {report_month}")
    lines.append(f"Source: PDF (flash-apr26.pdf, Page 14)")
    lines.append(f"\n")

    if not furnace_data:
        lines.append("NO DATA EXTRACTED")
        return "\n".join(lines)

    for furnace in FURNACES:
        if furnace not in furnace_data or not furnace_data[furnace]:
            lines.append(f"{furnace}: No data")
            continue

        data = furnace_data[furnace]
        lines.append(f"\n{furnace}:")
        lines.append("-" * 60)

        for param, info in sorted(data.items()):
            value = info['value']
            unit = info['unit']
            source = info['source']
            lines.append(f"  {param:30} = {value:12.2f} {unit:15} [{source}]")

        lines.append("")

    # Summary statistics
    lines.append(f"\n{'='*80}")
    lines.append("SUMMARY:")
    total_params = sum(len(data) for data in furnace_data.values() if data)
    furnaces_with_data = sum(1 for data in furnace_data.values() if data)

    lines.append(f"  Furnaces with data: {furnaces_with_data}/{len(FURNACES)}")
    lines.append(f"  Total parameters extracted: {total_params}")

    if furnaces_with_data > 0:
        avg_params = total_params / furnaces_with_data
        lines.append(f"  Avg parameters per furnace: {avg_params:.1f}")

    lines.append(f"{'='*80}\n")

    return "\n".join(lines)


def insert_to_db(furnace_data: Dict[str, Dict[str, Any]], report_month: str):
    """
    Insert extracted furnace data into techno_furnace_data table

    Args:
        furnace_data: Extracted furnace data
        report_month: Report month in YYYY-MM format
    """

    from db import insert_techno_furnace_data

    inserted_count = 0

    for furnace, params in furnace_data.items():
        if not params:
            logger.info(f"Skipping {furnace} - no data")
            continue

        try:
            insert_techno_furnace_data(
                plant=PLANT,
                furnace=furnace,
                report_month=report_month,
                data=params
            )
            inserted_count += 1
            logger.info(f"Inserted {furnace}: {len(params)} parameters")

        except Exception as e:
            logger.error(f"Error inserting {furnace}: {e}")

    logger.info(f"Total records inserted: {inserted_count}")

    return inserted_count


# ============================================================================
# Example usage / CLI
# ============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python pdf_extractor_bsp_furnace.py <pdf_file> <month>")
        print("Example: python pdf_extractor_bsp_furnace.py flash-apr26.pdf 2026-04")
        sys.exit(1)

    pdf_file = sys.argv[1]
    month = sys.argv[2]

    try:
        print(f"\n[STEP 1] EXTRACTING DATA FROM PDF...")
        furnace_data, preview = extract_and_preview(pdf_file, month)

        print(f"\n[STEP 2] PREVIEW OF EXTRACTED DATA:")
        print(preview)

        if not furnace_data or not any(furnace_data.values()):
            print("No data to insert")
            sys.exit(0)

        print(f"\n[STEP 3] INSERTING INTO DATABASE...")
        count = insert_to_db(furnace_data, month)
        print(f"SUCCESS: Inserted {count} furnace records\n")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
