import re
import logging
import sqlite3
import os
from typing import Optional

logger = logging.getLogger("excel_extractor")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "mis_reports.db")

MONTH_NAMES = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May",     "06": "June",     "07": "July",  "08": "August",
    "09": "September","10": "October", "11": "November","12": "December"
}


def clean_val(val) -> Optional[float]:
    if val is None or str(val).strip().lower() in ("nan", "###", "-", "#div/0!", ""):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def extract_and_save_excel(file_path: str, report_month: str = "", source_file_name: str = "", column_shift: int = 0) -> bool:
    """
    Dispatcher for DSP Excel uploads.

    DSP MCR-I report ('mcr1_*.xls') is a tab-separated ASCII text file
    despite the .xls extension. Detect binary vs text by reading first bytes.

    Args:
        file_path: Path to the Excel file
        report_month: Report month (optional, auto-detected from file)
        source_file_name: Original filename for logging
        column_shift: Column shift adjustment (-1 for left shift, +1 for right shift)
                     Use -1 when data is in columns C-D instead of D-E
    """
    try:
        with open(file_path, 'rb') as f:
            magic = f.read(4)

        if magic == b'\xd0\xcf\x11\xe0':
            raise ValueError(
                "Binary XLS format is not yet supported for DSP. "
                "Please upload the MCR-I report (tab-separated .xls file)."
            )

        return _extract_mcr_report(file_path, source_file_name, column_shift=column_shift)

    except ValueError as ve:
        logger.error(f"DSP validation error: {ve}")
        raise
    except Exception as e:
        logger.error(f"DSP extraction error: {e}")
        return False


# ---------------------------------------------------------------------------
# Extractor — DSP MCR-I (tab-separated text file, month-end daily report)
# ---------------------------------------------------------------------------

def _extract_mcr_report(file_path: str, source_file_name: str, column_shift: int = 0) -> bool:
    """
    Extracts cumulative production data from DSP MCR-I report (tab-separated text).

    File structure: ~57 rows, tab-delimited columns (0-based):
      Col A (0): Item name
      Col B (1): Asking Rate (daily target)
      Col C (2): Actual On Date
      Col D (3): Actual To Date (cumulative)
      Col E (4): Monthly Rate

    Args:
        column_shift: Adjust columns left (-1) or right (+1) for layout variations
                     Sep'25 uses column_shift=-1 (data in C-D instead of D-E)

    Date: row 1, col C (index 2) = "31.05.2026" (DD.MM.YYYY)

    Row map (1-based). Col E (index 4) = Monthly Rate except Round Production:
      Row 5:  Oven Pushing(nos/d)  — nos/day avg, no unit conversion
      Row 13: SP-1                 — tonnes → /1000
      Row 14: SP-2                 — tonnes → /1000
      Row 15: Total Sinter         — tonnes → /1000
      Row 16: Hot Metal            — tonnes → /1000
      Row 17: Pig Iron             — tonnes → /1000
      Row 20: BILLET Caster        — tonnes → /1000 (Total CC Billet)
      Row 21: Bloom Caster         — tonnes → /1000 (CC Bloom M/c-3)
      Row 23: Round Production     — col D used (col E blank for M/c-4 split)
      Row 25: Total Caster         — tonnes → /1000
      Row 26: BOTTOM_POURING_INGOT — tonnes → /1000 (Bottom Pouring ingots)
      Row 27: Total Crude Steel    — tonnes → /1000
      Row 30: MSM                  — tonnes → /1000
      Row 32: MM                   — tonnes → /1000 (Merchant Mill)
      Row 37: WAP                  — tonnes → /1000 (Wheel & Axle Plant)
      Row 38: Saleable Semis       — tonnes → /1000
      Row 39: Finished Steel       — tonnes → /1000
      Row 40: Saleable Steel       — tonnes → /1000
      Row 43: BILLET for Sale      — tonnes → /1000 (CC Billets despatch)
      Row 44: Blooms for Sale      — tonnes → /1000 (CC Blooms/BCB despatch)
      Row 46: BRC                  — tonnes → /1000 (CC Bloom/BRC despatch)
    """
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import db

    with open(file_path, encoding='utf-8', errors='replace') as f:
        lines = [line.rstrip('\r\n').split('\t') for line in f.readlines()]

    if not lines or 'DAILY MANAGEMENT CONTROL REPORT' not in lines[0][0].upper():
        raise ValueError(
            "File does not appear to be a DSP MCR-I report. "
            "First line must start with 'DAILY MANAGEMENT CONTROL REPORT'."
        )

    def get_cell(row_1based: int, col_0based: int) -> Optional[str]:
        idx = row_1based - 1
        if idx >= len(lines):
            return None
        cols = lines[idx]
        if col_0based >= len(cols):
            return None
        return cols[col_0based].strip() or None

    # Date from row 1, col C (index 2): e.g. "31.05.2026"
    date_str = get_cell(1, 2) or ""
    date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
    if not date_match:
        raise ValueError(
            f"Cannot parse date from row 1, column C: {repr(date_str)}. "
            "Expected format DD.MM.YYYY (e.g. 31.05.2026)."
        )
    _d, m_num, year = date_match.groups()
    db_report_month = f"{year}-{m_num}"
    logger.info(f"DSP MCR: month auto-detected → {db_report_month}")

    COL_D = 3 + column_shift  # Actual To Date (cumulative)
    COL_E = 4 + column_shift  # Monthly Rate
    if column_shift != 0:
        logger.info(f"DSP MCR: column shift applied → {column_shift} (COL_D={COL_D}, COL_E={COL_E})")

    NO_CONVERT = {"Oven Pushing(nos/d)"}

    # (row_1based, col_0based, item_name_in_production_table)
    # Note: "Bloom Caster " and "Blooms for Sale " have trailing spaces matching plan table
    production_rows = [
        (5,  COL_E, "Oven Pushing(nos/d)"),   # avg nos/day — no /1000
        (13, COL_E, "SP-1"),
        (14, COL_E, "SP-2"),
        (15, COL_E, "Total Sinter"),
        (16, COL_E, "Hot Metal"),
        (17, COL_E, "Pig Iron"),
        (20, COL_E, "BILLET Caster"),          # Total CC Billet
        (21, COL_E, "Bloom Caster "),          # CC Bloom M/c-3
        (23, COL_D, "Round Production"),       # CC Round M/c-4 — col E blank for M/c-4
        (25, COL_E, "Total Caster"),
        (26, COL_E, "BOTTOM_POURING_INGOT"),
        (27, COL_E, "Total Crude Steel"),
        (30, COL_E, "MSM"),
        (32, COL_E, "MM"),
        (37, COL_E, "WAP"),
        (38, COL_E, "Saleable Semis"),
        (39, COL_E, "Finished Steel"),
        (40, COL_E, "Saleable Steel"),
        (43, COL_E, "BILLET for Sale"),        # CC Billets despatch
        (44, COL_E, "Blooms for Sale "),       # CC Blooms/BCB despatch
        (46, COL_E, "BRC"),                    # CC Bloom/BRC despatch
    ]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    vals_extracted = 0

    def _save(item_name: str, raw_str: Optional[str]):
        nonlocal vals_extracted
        val = clean_val(raw_str)
        if val is not None:
            vals_extracted += 1
            if item_name not in NO_CONVERT:
                val = round(val / 1000.0, 3)
        cursor.execute("""
            INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(report_month, plant_name, item_name)
            DO UPDATE SET month_actual = excluded.month_actual
        """, (db_report_month, "DSP", item_name, val))

    for row, col, item_name in production_rows:
        _save(item_name, get_cell(row, col))

    if vals_extracted == 0:
        raise ValueError(
            "No numeric data found at the expected row positions in the MCR-I report. "
            "Please verify this is the correct DSP MCR-I file."
        )

    conn.commit()
    conn.close()

    db.log_extraction(
        plant="DSP",
        report_month=db_report_month,
        file_name=source_file_name,
        sheet_name="MCR-I",
        source_type="MCR1 Report (Month-End)",
        items_extracted=vals_extracted,
    )
    logger.info(f"DSP MCR extraction done: {vals_extracted} values saved for {db_report_month}.")
    return True


# ---------------------------------------------------------------------------
# Preview — MCR-I (no DB writes, returns standard preview dict)
# ---------------------------------------------------------------------------

def _mcr_preview(file_path: str, report_month: str, column_shift: int = 0) -> dict:
    with open(file_path, encoding='utf-8', errors='replace') as f:
        lines = [line.rstrip('\r\n').split('\t') for line in f.readlines()]

    if not lines or 'DAILY MANAGEMENT CONTROL REPORT' not in lines[0][0].upper():
        raise ValueError(
            "File does not appear to be a DSP MCR-I report. "
            "First line must start with 'DAILY MANAGEMENT CONTROL REPORT'."
        )

    def get_cell(row_1based: int, col_0based: int) -> Optional[str]:
        idx = row_1based - 1
        if idx >= len(lines):
            return None
        cols = lines[idx]
        if col_0based >= len(cols):
            return None
        return cols[col_0based].strip() or None

    date_str = get_cell(1, 2) or ""
    date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
    if date_match:
        _, m_num, year = date_match.groups()
        db_month = f"{year}-{m_num}"
    else:
        db_month = report_month

    COL_D = 3 + column_shift
    COL_E = 4 + column_shift
    NO_CONVERT = {"Oven Pushing(nos/d)"}

    row_specs = [
        (5,  COL_E, "Oven Pushing(nos/d)"),
        (13, COL_E, "SP-1"),
        (14, COL_E, "SP-2"),
        (15, COL_E, "Total Sinter"),
        (16, COL_E, "Hot Metal"),
        (17, COL_E, "Pig Iron"),
        (20, COL_E, "BILLET Caster"),
        (21, COL_E, "Bloom Caster "),
        (23, COL_D, "Round Production"),
        (25, COL_E, "Total Caster"),
        (26, COL_E, "BOTTOM_POURING_INGOT"),
        (27, COL_E, "Total Crude Steel"),
        (30, COL_E, "MSM"),
        (32, COL_E, "MM"),
        (37, COL_E, "WAP"),
        (38, COL_E, "Saleable Semis"),
        (39, COL_E, "Finished Steel"),
        (40, COL_E, "Saleable Steel"),
        (43, COL_E, "BILLET for Sale"),
        (44, COL_E, "Blooms for Sale "),
        (46, COL_E, "BRC"),
    ]

    rows = []
    for row, col, item_name in row_specs:
        raw = get_cell(row, col)
        val = clean_val(raw)
        if val is not None and item_name not in NO_CONVERT:
            val = round(val / 1000.0, 3)
        unit = "nos/d" if item_name in NO_CONVERT else "'000T"
        rows.append({
            "item_name": item_name,
            "value": val,
            "unit": unit,
            "cell": f"R{row}C{col + 1}",
            "pdf_label": item_name,
            "status": "ok" if val is not None else "no value",
        })

    return {
        "plant": "DSP",
        "month": db_month,
        "source_type": "DSP MCR-I Report",
        "sheets": "MCR-I",
        "workbook_sheets": ["MCR-I"],
        "production_rows": rows,
        "special_steel_rows": [],
        "techno_rows": [],
        "techno_param_rows": [],
    }


# ---------------------------------------------------------------------------
# Unified preview entry point — auto-detects PDF vs MCR-I text
# ---------------------------------------------------------------------------

def extract_preview(file_path: str, report_month: str, aliases: dict = None,
                    block: str = 'all', column_shift: int = 0) -> dict:
    """DSP preview: delegates to pdf_extractor_dsp for .pdf, else MCR-I text.

    Args:
        column_shift: Column offset for data extraction (-1 for Sep'25 left-shifted layout)
    """
    import os as _os
    suffix = _os.path.splitext(file_path)[1].lower()

    if suffix == '.pdf':
        import pdf_extractor_dsp
        return pdf_extractor_dsp.extract_preview(
            file_path, report_month, aliases=aliases, block=block)

    with open(file_path, 'rb') as f:
        magic = f.read(4)
    if magic == b'\xd0\xcf\x11\xe0':
        raise ValueError(
            "Binary XLS format is not supported for DSP. "
            "Upload the MCR-I tab-separated .xls file or the OMI PDF report."
        )
    return _mcr_preview(file_path, report_month, column_shift=column_shift)

