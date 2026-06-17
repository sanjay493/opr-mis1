"""
ASP (Alloy Steels Plant, Durgapur) Excel extractor.

Source file: Daily Performance Summary Report (asp.xlsx, sheet "md cell").

Fixed cell mappings (column F = monthly actual, column E = monthly plan/target):
    F10  → Total Crude Steel
    F11  → Total Caster  (Concast / CC Steel)
    F12  → Ingot Steel
    F20  → Saleable Steel
    L25  → Closing Stock  (Total Plant Stock)

Report month is auto-detected from cell E3 which contains the report date
(e.g. '30/04/2026' → 2026-04).  The user-supplied month is used as fallback
if E3 is blank or unparseable.

All values are in Tonnes in the source file; stored as '000T in the DB.
"""
import os
import re

PLANT = "ASP"
SHEET_NAME = "md cell"

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# (cell address, item_name in production_table)
_CELL_MAP = [
    ("F10", "Total Crude Steel"),
    ("F11", "Total Caster"),    # Concast
    ("F12", "Ingot Steel"),
    ("F20", "Saleable Steel"),
    ("L25", "Closing Stock"),
]


def _parse_date_cell(raw):
    """Convert E3 value to 'YYYY-MM' string.

    Handles:
      - datetime / date objects  (openpyxl returns these for real date cells)
      - string like '30/04/2026' or '2026-04-30'
    Returns None if the value cannot be parsed.
    """
    if raw is None:
        return None
    # openpyxl datetime / date
    if hasattr(raw, "month") and hasattr(raw, "year"):
        return f"{raw.year}-{str(raw.month).zfill(2)}"
    s = str(raw).strip()
    # dd/mm/yyyy
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}"
    # yyyy-mm-dd
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


def extract_preview(file_path: str, report_month: str, **_kwargs) -> dict:
    """Extract ASP production actuals from the Daily Performance Summary Excel.

    Returns a dict in the standard extract_preview() format — no DB writes.
    Month is auto-detected from cell E3; report_month is used as fallback.
    """
    import sys
    import openpyxl

    fname = os.path.basename(file_path)
    print(f"[ASP Excel] extract_preview: file={fname}  month={report_month}",
          flush=True, file=sys.stderr)

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
    except Exception as exc:
        raise ValueError(f"Cannot open Excel file '{fname}': {exc}") from exc

    # Try named sheet first, fall back to active
    if SHEET_NAME in wb.sheetnames:
        ws = wb[SHEET_NAME]
    else:
        ws = wb.active
        print(f"[ASP Excel] Sheet '{SHEET_NAME}' not found, using active: '{ws.title}'",
              flush=True, file=sys.stderr)

    # ── Auto-detect month from E3 ─────────────────────────────────────────
    date_val    = ws["E3"].value
    detected    = _parse_date_cell(date_val)
    actual_month = detected or report_month

    y, m   = int(actual_month[:4]), int(actual_month[5:7])
    want_mon = _MONTHS[m - 1]
    yy       = str(y)[2:]

    print(f"[ASP Excel] E3={repr(date_val)}  detected={detected}  using={actual_month}",
          flush=True, file=sys.stderr)

    # ── Read fixed cells ──────────────────────────────────────────────────
    rows = []
    for cell_addr, item_name in _CELL_MAP:
        raw = ws[cell_addr].value
        if raw is not None and isinstance(raw, (int, float)):
            stored = round(float(raw) / 1000.0, 3)
            rows.append({
                "item_name": item_name,
                "value":     stored,
                "unit":      "'000T",
                "cell":      f"Excel [{ws.title}!{cell_addr}] · {want_mon}'{yy}",
                "pdf_label": cell_addr,
                "status":    "ok",
            })
            print(f"[ASP Excel] {item_name:20s} [{cell_addr}] = {raw} T → {stored} '000T",
                  flush=True, file=sys.stderr)
        else:
            rows.append({
                "item_name": f"(empty) {item_name}",
                "value":     None,
                "unit":      "T",
                "cell":      f"Excel [{ws.title}!{cell_addr}]",
                "pdf_label": cell_addr,
                "status":    "unmapped",
            })
            print(f"[ASP Excel] {item_name:20s} [{cell_addr}] = EMPTY (raw={repr(raw)})",
                  flush=True, file=sys.stderr)

    ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"[ASP Excel] {ok}/{len(rows)} rows ok", flush=True, file=sys.stderr)

    date_display = str(date_val) if date_val else "unknown date"

    return {
        "plant":              PLANT,
        "month":              actual_month,
        "source_type":        "ASP Daily Performance Summary (Excel)",
        "sheets":             f"Sheet '{ws.title}' · Report date: {date_display}",
        "workbook_sheets":    [ws.title],
        "report_type":        "EXCEL",
        "detected_month":     detected,
        "production_rows":    rows,
        "special_steel_rows": [],
        "special_steel_note": "",
        "techno_rows":        [],
        "techno_param_rows":  [],
    }
