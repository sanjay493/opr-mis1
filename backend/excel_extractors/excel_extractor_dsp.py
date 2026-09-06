import re
import logging
import os
from typing import Optional

logger = logging.getLogger("excel_extractor")

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
      Row 5:  Oven Pushing (nos/day)  — nos/day avg, no unit conversion
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

    NO_CONVERT = {"Oven Pushing (nos/day)"}

    # (row_1based, col_0based, item_name_in_production_table)
    # Note: "Bloom Caster " and "Blooms for Sale " have trailing spaces matching plan table
    production_rows = [
        (5,  COL_E, "Oven Pushing (nos/day)"),   # avg nos/day — no /1000
        (13, COL_E, "SP-1"),
        (14, COL_E, "SP-2"),
        (15, COL_E, "Total Sinter"),
        (16, COL_E, "Hot Metal"),
        (17, COL_E, "Pig Iron"),
        (20, COL_E, "BILLET Caster"),          # Total CC Billet
        (21, COL_E, "Bloom Caster "),          # CC Bloom M/c-3
        (23, COL_D, "Round Production"),       # CC Round M/c-4 — col E blank for M/c-4
        (25, COL_E, "SMS Total Caster"),
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

    conn = db.connect()
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
    NO_CONVERT = {"Oven Pushing (nos/day)"}

    row_specs = [
        (5,  COL_E, "Oven Pushing (nos/day)"),
        (13, COL_E, "SP-1"),
        (14, COL_E, "SP-2"),
        (15, COL_E, "Total Sinter"),
        (16, COL_E, "Hot Metal"),
        (17, COL_E, "Pig Iron"),
        (20, COL_E, "BILLET Caster"),
        (21, COL_E, "Bloom Caster "),
        (23, COL_D, "Round Production"),
        (25, COL_E, "SMS Total Caster"),
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
# Extractor — DSP "mcr_<date>.xls" (tab-separated text, RICHER report than
# the "mcr1_<date>.xls" one above — same general shape and DAILY MANAGEMENT
# CONTROL REPORT lineage, but its column-A title is truncated to "DAILY
# MANAGEMENT CON" rather than the full "...CONTROL REPORT -I", so
# _mcr_preview's own file-type check already rejects it outright with a
# clear error rather than misreading it — safe to distinguish by content
# and add a dedicated path alongside, per direct instruction.
#
# Carries a genuine Blast-Furnace block this file family's "mcr1" sibling
# doesn't have at all: furnace-wise Hot Metal (BF#2/BF#3/BF#4) plus where
# that Hot Metal went (SMS / PCM / ASP) — confirmed present and at the same
# label text across every file sampled (2025-01 through 2026-06/08); rows
# found by label search rather than a fixed offset regardless, same
# precaution as everywhere else in this codebase.
#
# This report typically arrives BEFORE the monthly OMI PDF (the eventual
# authoritative source for BF#2/3/4 and Hot Metal to ASP — see
# pdf_extractor_dsp.py's _ITEM_MAP_DEFAULT) — per direct instruction, these
# figures are meant as an early/preliminary read, useful for comparing
# against the OMI PDF's own final figure once that arrives (both write the
# same item_names, so confirming the PDF's preview later simply supersedes
# whichever value is already in the DB — the preview screen's existing
# "current DB value" column is what actually shows that comparison, same
# pattern as BSP's MIS-2 vs PPC MIS tentative/final relationship).
# ---------------------------------------------------------------------------

_MCR_FURNACE_TITLE = "DAILY MANAGEMENT CON"
_MCR_FURNACE_HM_LABEL = "HOT METAL PRODUCTION"
_MCR_FURNACE_PCM_LABEL = "HOT METAL SENT TO PCM"
_MCR_FURNACE_ASP_LABEL = "HOT METAL TO ASP"
_MCR_FURNACE_LABEL_COL = 4   # column E


def _looks_like_mcr_furnace_report(lines) -> bool:
    """True for the richer 'mcr_<date>.xls' format (has a Blast-Furnace-
    wise Hot Metal block) rather than the simpler 'mcr1_<date>.xls' one
    _mcr_preview already handles — distinguished by content (the "HOT
    METAL PRODUCTION" label appears in column E on this format only, not
    filename, since both share the .xls extension and general tab-text
    shape)."""
    if not lines or _MCR_FURNACE_TITLE not in lines[0][0].upper():
        return False
    for row in lines[:15]:
        if len(row) > _MCR_FURNACE_LABEL_COL and \
                _MCR_FURNACE_HM_LABEL in row[_MCR_FURNACE_LABEL_COL].strip().upper():
            return True
    return False


def _find_mcr_furnace_label_row(lines, label, max_row=55):
    """First row (0-based) whose column E reads exactly `label`."""
    for i, row in enumerate(lines[:max_row]):
        if len(row) > _MCR_FURNACE_LABEL_COL and \
                row[_MCR_FURNACE_LABEL_COL].strip().upper() == label:
            return i
    return None


def _mcr_furnace_project(cum, report_day, days_in_month):
    """Scale a To-Date cumulative up to a full-month estimate — this
    report has no separate Monthly-Rate column of its own for the Blast
    Furnace block (unlike the main Production block's column E/F), so the
    projection is computed directly from the report's own date instead."""
    if cum is None or not report_day or not days_in_month or report_day >= days_in_month:
        return cum
    return cum * days_in_month / report_day


def _extract_mcr_furnace_report(lines) -> dict:
    """{"report_month": "YYYY-MM", "values": {item_name: value_000T}} for
    BF#2/BF#3/BF#4 (from the "HOT METAL PRODUCTION" row's Todate BF2/BF3/
    BF4 columns — J/K/L), "Hot Metal to PCM" (from the "HOT METAL SENT TO
    PCM" row's Todate Shop-total column — M, i.e. summed across all 3
    furnaces already), and "Hot Metal to ASP" (a single-item row further
    down the sheet, Todate column — G). All 3 figures are Month-to-Date
    cumulatives, projected to a full month via _mcr_furnace_project.
    """
    date_str = lines[0][2].strip() if len(lines) > 0 and len(lines[0]) > 2 else ""
    date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
    if not date_match:
        raise ValueError(
            f"Cannot parse date from row 1, column C: {date_str!r}. "
            "Expected format DD.MM.YYYY (e.g. 31.08.2026)."
        )
    d, m_num, year = date_match.groups()
    import calendar
    report_day = int(d)
    days_in_month = calendar.monthrange(int(year), int(m_num))[1]
    report_month = f"{year}-{m_num}"

    def _cell(row_idx, col_idx):
        if row_idx is None or col_idx >= len(lines[row_idx]):
            return None
        return clean_val(lines[row_idx][col_idx])

    def _mrate(v):
        v = _mcr_furnace_project(v, report_day, days_in_month)
        return round(v / 1000.0, 3) if v is not None else None

    hm_row = _find_mcr_furnace_label_row(lines, _MCR_FURNACE_HM_LABEL)
    pcm_row = _find_mcr_furnace_label_row(lines, _MCR_FURNACE_PCM_LABEL)
    asp_row = _find_mcr_furnace_label_row(lines, _MCR_FURNACE_ASP_LABEL)

    values = {}
    for col, item in ((9, "BF#2"), (10, "BF#3"), (11, "BF#4")):
        v = _mrate(_cell(hm_row, col))
        if v is not None:
            values[item] = v

    v = _mrate(_cell(pcm_row, 12))
    if v is not None:
        values["Hot Metal to PCM"] = v

    v = _mrate(_cell(asp_row, 6))
    if v is not None:
        values["Hot Metal to ASP"] = v

    return {"report_month": report_month, "values": values}


def _mcr_furnace_preview(file_path: str) -> dict:
    with open(file_path, encoding='utf-8', errors='replace') as f:
        lines = [line.rstrip('\r\n').split('\t') for line in f.readlines()]

    result = _extract_mcr_furnace_report(lines)
    rows = []
    cells = {"BF#2": "J", "BF#3": "K", "BF#4": "L", "Hot Metal to PCM": "M", "Hot Metal to ASP": "G"}
    for item_name, value in result["values"].items():
        col_letter = cells.get(item_name, "")
        rows.append({
            "item_name": item_name,
            "value": value,
            "unit": "'000T",
            "cell": f"{col_letter} (Todate, projected)" if col_letter else "",
            "pdf_label": item_name,
            "status": "ok",
        })

    return {
        "plant": "DSP",
        "month": result["report_month"],
        "source_type": "DSP MCR Report (Blast Furnace, preliminary)",
        "sheets": "MCR",
        "workbook_sheets": ["MCR"],
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

    Two different PDFs can show up for DSP: the monthly OMI report
    (pdf_extractor_dsp.py — has a 'PRODUCTION MONTHWISE' page) and the daily
    Plant Control summary 'pcontrep.pdf' (pdf_extractor_dsp_pcontrep.py — a
    PDF export of the same underlying report the MCR-I text file comes
    from). Sniff which one it is before picking an extractor.

    Args:
        column_shift: Column offset for data extraction (-1 for Sep'25 left-shifted layout)
    """
    import os as _os
    suffix = _os.path.splitext(file_path)[1].lower()

    if suffix == '.pdf':
        import pdf_extractor_dsp_pcontrep
        if pdf_extractor_dsp_pcontrep.looks_like_pcontrep(file_path):
            return pdf_extractor_dsp_pcontrep.extract_preview(
                file_path, report_month, aliases=aliases, block=block)
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

    with open(file_path, encoding='utf-8', errors='replace') as f:
        lines = [line.rstrip('\r\n').split('\t') for line in f.readlines()]
    if _looks_like_mcr_furnace_report(lines):
        return _mcr_furnace_preview(file_path)

    return _mcr_preview(file_path, report_month, column_shift=column_shift)

