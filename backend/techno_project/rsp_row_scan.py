"""Shared row/column-scanning primitives for RSP technopara-style sheets.

Used by both excel_extractors/excel_extractor_rsp.py (page-1-8 techno_table +
page-9 production_table extraction) and techno_project/rsp_technopara_extractor.py
(techno_data / the /data-entry/techno page) — both read from the same family of
RSP monthly report workbooks, which share the same layout quirks:
  - the current month's column shifts every year (one more legacy fiscal-year
    column gets prepended annually), so a fixed month->column-letter map goes
    stale annually;
  - some file variants insert an extra leading serial-number column before the
    row label, shifting the label from column A to column B;
  - one real file (June-2026) stores the current month's header cells as native
    datetime objects instead of the usual "Apr"/"May" strings;
  - row numbers for a given parameter drift between file editions.

The detection logic lives here once instead of being duplicated across both
extractors.
"""
import re
import datetime as _dt
from typing import Optional, Tuple

_MONTH_ABBR_BY_NUM = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
    "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
}

# page-1-8's sheet name varies constantly across real RSP files: "page-1-8",
# "PAGE-1-8 & 11,12", "PAGE1-8 &11-12", and even "PAGE-1-9" (June-2026, after
# RSP folded page-9's numbering into this sheet's title). None of these are
# exact-matchable, so canon-then-prefix-match instead of using an exact set —
# "page18.*"/"page19.*" is unambiguous since PAGE-10/11/12/13... never share
# this prefix (canon "page10" etc. doesn't start with "page18"/"page19").
P18_NAME_RE = re.compile(r'^page1[89]')


def canon_sheet(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def find_p18_sheet(sheet_names):
    """Return the first sheet name matching the page-1-8/page-1-9 pattern, or None."""
    return next((s for s in sheet_names if P18_NAME_RE.match(canon_sheet(s))), None)


def _header_month_abbr(val) -> str:
    """Normalize a header cell to a 3-letter month abbreviation ('' if not a month
    cell). Handles both string headers ('Apr', "Apr'25") and datetime/date-typed
    headers."""
    if isinstance(val, (_dt.datetime, _dt.date)):
        return val.strftime("%b")
    s = str(val).strip() if val is not None else ""
    return s[:3] if s[:3] in _MONTH_ABBR_BY_NUM.values() else ""


def find_month_cum_columns(ws, month_num: str, max_header_row: int = 6,
                            max_col: int = 400) -> Tuple[Optional[int], Optional[int]]:
    """Locate the (month_col, cum_col) 1-based column indices for the report month
    by scanning the sheet's header rows directly, instead of assuming a fixed
    month -> column-letter map. Each month abbreviation appears exactly once per
    header row — legacy years are labelled by full year strings like '2007-08',
    never bare month names, so a plain substring match is unambiguous.

    Returns (None, None) if no single row yields both a month match and a
    'Cum'/'Cum.' match.
    """
    target_abbr = _MONTH_ABBR_BY_NUM.get(month_num)
    if not target_abbr:
        return None, None

    for row in range(1, max_header_row + 1):
        month_col = cum_col = None
        for col in range(1, max_col + 1):
            val = ws.cell(row=row, column=col).value
            if val is None:
                continue
            if month_col is None and _header_month_abbr(val) == target_abbr:
                month_col = col
            elif (cum_col is None and isinstance(val, str)
                  and val.strip().lower().startswith("cum")):
                cum_col = col
        if month_col is not None and cum_col is not None:
            return month_col, cum_col
    return None, None


def _norm_label(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def find_label_row(ws, label_col: int, label: str, near_row: int,
                    window: int = 20) -> Optional[int]:
    """Scan `label_col` for `label` (case-insensitive substring), searching
    outward from `near_row` first within +/-`window` rows, so a shift is found
    nearby rather than matching a same-named parameter in a distant, unrelated
    section (mirrors isp_technopara_extractor.py's _find_label_row)."""
    lc = _norm_label(label)
    if not lc:
        return None
    lo, hi = max(1, near_row - window), near_row + window
    for offset in range(0, window + 1):
        for r in ({near_row - offset, near_row + offset} if offset else {near_row}):
            if lo <= r <= hi and lc in _norm_label(ws.cell(row=r, column=label_col).value):
                return r
    return None


def verified_row(ws, label_col: int, configured_row: int, expected_label: str,
                  window: int = 20, context: str = "") -> int:
    """Return the row to actually read: the configured row if its label still
    matches, the nearby row the label moved to if not, or the configured row
    unchanged (with a printed warning) if the label can't be found nearby at
    all. Mirrors isp_technopara_extractor.py's _verified_row. `context` is only
    used to identify which (unit/param) drifted in the warning message."""
    if not expected_label:
        return configured_row
    actual_label = ws.cell(row=configured_row, column=label_col).value
    if _norm_label(expected_label) in _norm_label(actual_label):
        return configured_row
    found = find_label_row(ws, label_col, expected_label, configured_row, window)
    if found:
        print(f"Warning: {context or 'row'} shifted {configured_row} -> {found} "
              f"(label '{expected_label}')")
        return found
    print(f"Warning: {context or 'row'} expected label '{expected_label}' not found "
          f"near row {configured_row} — using configured row unverified "
          f"(got {actual_label!r})")
    return configured_row


def detect_label_column(ws, near_row: int, probe_labels, max_col: int = 2) -> int:
    """Detect whether row labels live in column A (1) or column B (2) for this
    sheet. Some RSP file variants insert an extra leading serial-number column
    before the label. Checks a small window around `near_row` against
    `probe_labels` (known label text expected somewhere nearby) and returns
    whichever column is the better match; defaults to column 1 if neither
    matches anything."""
    probes = [_norm_label(p) for p in probe_labels if p]
    best_col, best_hits = 1, -1
    for col in range(1, max_col + 1):
        hits = 0
        for r in range(max(1, near_row - 5), near_row + 6):
            cell_val = _norm_label(ws.cell(row=r, column=col).value)
            if cell_val and any(p in cell_val for p in probes):
                hits += 1
        if hits > best_hits:
            best_col, best_hits = col, hits
    return best_col
