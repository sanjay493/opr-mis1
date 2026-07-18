"""
VISL PDF extractor — two report formats supported.

Format A  "Month-End" (e.g. VISLreportsMAY26.pdf)
  Detected by: header contains "On Date" and "To Date"
  Column layout:  On Date | To Date | APP | As % of APP
  Target column:  index 1  (2nd number = To Date / cumulative month)

  Example key rows:
    Total Saleable Steel 254.25 3654.85 6360 57.47
    Sales (AS+MS)          0.00 2591.76 4089 63.38

Format B  "Daily Production and Performance" (e.g. VISLreportsAPR25.pdf)
  Detected by: header contains "Day" + "Month" + "APP ACT" — no "To Date"
  Column layout:  Day-APP | Day-ACT | Month-APP | Month-ACT | As% | Monthly Rate
  Target column:  index 3  (4th number = Month ACT)

  Example key rows:
    Total Saleable Steel 150  85.820  4510  2257.180  0  0
    Sales (AS+MS)        154 119.860  4610  2696.400  0  0

Values are in Tonnes in both formats → stored as '000T (÷ 1000).
"""
import os
import re
import sys

PLANT = "VISL"

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _load_pdf_text(file_path: str):
    import pdfplumber
    try:
        with pdfplumber.open(file_path) as pdf:
            n = len(pdf.pages)
            parts = [pg.extract_text() or "" for pg in pdf.pages]
            return "\n".join(parts), n
    except Exception as exc:
        raise ValueError(f"Cannot open PDF '{os.path.basename(file_path)}': {exc}") from exc


def _nums_from_line(line: str):
    """All floats on the line, excluding year-like integers 2000-2099."""
    result = []
    for tok in re.findall(r'\d[\d,]*(?:\.\d+)?', line):
        try:
            v = float(tok.replace(',', ''))
        except ValueError:
            continue
        if 2000 <= v <= 2099 and '.' not in tok:
            continue
        result.append(v)
    return result


def _letters_only(s: str) -> str:
    """Upper-cased letters only — for matching a label against a line whose
    layout got scrambled (see _strip_letters)."""
    return re.sub(r"[^A-Za-z]", "", s).upper()


def _strip_letters(s: str) -> str:
    """Drop only the alphabetic characters, keeping digits/./,/spaces intact.

    Some PDF exports (e.g. reports_Dec'25.pdf) render a label column and the
    number right after it with slightly overlapping x-positions, so
    pdfplumber's extract_text() interleaves a stray label character into the
    middle of the number: "Total Saleable Steel 92.030" comes out as
    "Total Saleable Stee9l2.030" — the '9' and '2.030' end up split by the
    displaced 'l' and _nums_from_line reads them as two numbers (9, 2.03)
    instead of one (92.030). Stripping letters first re-joins '9' directly
    against '2.030' into '92.030', with no effect on an already-clean line.
    """
    return re.sub(r"[A-Za-z]", "", s)


_DATE_RE = re.compile(r"Date:\s*(\d{1,2})-([A-Za-z]{3})-(\d{2})")


def _detect_month_from_pdf_text(full_text: str):
    """Detect 'YYYY-MM' from the report's own header 'Date: DD-Mon-YY' line
    (e.g. 'Date: 30-Jun-24') — always the last day of the report's own
    month across every sample checked. Returns None if not found, since a
    missing signal shouldn't block extraction, only a genuine mismatch."""
    m = _DATE_RE.search(full_text[:300])
    if not m:
        return None
    _, mon_abbr, yy = m.groups()
    try:
        mon_num = _MONTHS.index(mon_abbr.upper()) + 1
    except ValueError:
        return None
    return f"20{yy}-{mon_num:02d}"


def _fmt_month(ym: str) -> str:
    try:
        y, mo = ym[:4], int(ym[5:7])
        return f"{_MONTHS[mo - 1].title()} {y}"
    except Exception:
        return ym


def _assert_month_match(detected, user_month: str) -> None:
    if detected and detected != user_month:
        raise ValueError(
            f"Month mismatch: this VISL report's own header shows "
            f"{_fmt_month(detected)}, but you selected {_fmt_month(user_month)}. "
            f"Please select '{_fmt_month(detected)}' in the month picker, "
            f"or upload the report for {_fmt_month(user_month)}."
        )


def _detect_format(full_text: str) -> str:
    """
    Returns 'B' for Daily-Production format (Day/Month APP ACT layout)
    or     'A' for Month-End format (On Date / To Date layout).

    Check Format B first: the APR25 PDF contains 'to date' in a utilities
    section, so 'daily production' is the reliable discriminator.
    """
    low = full_text.lower()
    if "daily production" in low:
        return "B"
    if "to date" in low:
        return "A"
    return "A"


def _row(item_name, val_t, cell_desc, pdf_label):
    """Build a standard production_row dict. val_t is in Tonnes."""
    if val_t is None:
        return {
            "item_name": f"(not found) {item_name}",
            "value":     None,
            "unit":      "T",
            "cell":      cell_desc,
            "pdf_label": pdf_label,
            "status":    "unmapped",
        }
    return {
        "item_name": item_name,
        "value":     round(val_t / 1000.0, 3),
        "unit":      "'000T",
        "cell":      cell_desc,
        "pdf_label": pdf_label,
        "status":    "ok",
    }


def _extract_value(nums: list, fmt: str, label: str):
    """
    Pick the right column index based on format.
    Format A: index 1 (2nd number = To Date / cumulative).
    Format B: index 3 (4th number = Month ACT).
    Falls back gracefully if the line has fewer numbers.
    """
    if fmt == "A":
        idx = 1
    else:
        idx = 3

    if len(nums) > idx:
        return nums[idx]
    # Graceful fallback: use last available number if expected index missing
    if nums:
        return nums[-1]
    return None


def extract_preview(file_path: str, report_month: str, **_kwargs) -> dict:
    """
    Extract VISL production data from a monthly report PDF.
    Handles both the Month-End (Format A) and Daily-Production (Format B) layouts.
    Returns the standard extract_preview() dict — no DB writes.
    """
    y, m     = int(report_month[:4]), int(report_month[5:7])
    want_mon = _MONTHS[m - 1]
    yy       = str(y)[2:]
    fname    = os.path.basename(file_path)

    print(f"[VISL PDF] extract_preview: file={fname}  month={want_mon}'{yy}",
          flush=True, file=sys.stderr)

    full_text, n_pages = _load_pdf_text(file_path)

    detected_month = _detect_month_from_pdf_text(full_text)
    _assert_month_match(detected_month, report_month)

    fmt = _detect_format(full_text)
    col_desc = "To Date (col 2)" if fmt == "A" else "Month ACT (col 4)"

    print(f"[VISL PDF] Loaded {n_pages} pages, {len(full_text)} chars — Format {fmt} ({col_desc})",
          flush=True, file=sys.stderr)

    lines = full_text.splitlines()
    prod_rows = []
    cell_tag  = f"PDF ({n_pages}p) · {want_mon}'{yy} · Fmt-{fmt}"

    # ── Saleable Steel & Finished Steel: "Total Saleable Steel" row ────────────
    sal_val   = None
    sal_label = "(Total Saleable Steel line not found)"
    for ln in lines:
        if "TOTALSALEABLESTEEL" in _letters_only(ln):
            nums = _nums_from_line(_strip_letters(ln))
            sal_val   = _extract_value(nums, fmt, "Total Saleable Steel")
            sal_label = ln.strip()[:80]
            break

    for item in ("Saleable Steel", "Finished Steel"):
        prod_rows.append(_row(item, sal_val,
                              f"{cell_tag} · Total Saleable Steel · {col_desc}", sal_label))

    # ── Per-mill Saleable Steel breakdown: Primary Mill / Bar Mill /
    # Forging Press / Long Forging Machine ─────────────────────────────────
    # These same mill names also appear earlier in the report's "Production"
    # section (gross tonnage through the mill, not saleable output) and, in
    # Format A, in a "WORK IN PROGRESS(WIP)" section — so the rows are only
    # read from between the "Saleable Steel" section header and the
    # "Total Saleable Steel" line that closes it, never by label alone.
    sec_start = None
    sec_end = len(lines)
    for i, ln in enumerate(lines):
        skeleton = _letters_only(ln)
        if sec_start is None and skeleton == "SALEABLESTEEL":
            sec_start = i
        elif sec_start is not None and "TOTALSALEABLESTEEL" in skeleton:
            sec_end = i
            break
    section_lines = lines[sec_start + 1:sec_end] if sec_start is not None else []

    for item_name in ("Primary Mill", "Bar Mill", "Forging Press", "Long Forging Machine"):
        item_skel = _letters_only(item_name)
        val, label = None, f"({item_name} line not found in Saleable Steel section)"
        for ln in section_lines:
            if _letters_only(ln).startswith(item_skel):
                nums = _nums_from_line(_strip_letters(ln))
                val = _extract_value(nums, fmt, item_name)
                label = ln.strip()[:80]
                break
        prod_rows.append(_row(item_name, val,
                              f"{cell_tag} · Saleable Steel · {item_name} · {col_desc}", label))

    # ── Saleable Steel Despatch: "Sales (AS+MS)" row ───────────────────────────
    desp_val   = None
    desp_label = "(Sales (AS+MS) line not found)"
    for ln in lines:
        skeleton = _letters_only(ln)
        if "SALES" in skeleton and "AS" in skeleton and "MS" in skeleton:
            nums = _nums_from_line(_strip_letters(ln))
            desp_val   = _extract_value(nums, fmt, "Sales (AS+MS)")
            desp_label = ln.strip()[:80]
            break

    prod_rows.append(_row("Saleable Steel Despatch", desp_val,
                          f"{cell_tag} · Sales (AS+MS) · {col_desc}", desp_label))

    ok = sum(1 for r in prod_rows if r["status"] == "ok")
    print(f"[VISL PDF] {ok}/{len(prod_rows)} rows ok", flush=True, file=sys.stderr)

    if ok == 0:
        raise ValueError(
            "No values extracted. Verify this is a VISL report PDF containing "
            "'Total Saleable Steel' and 'Sales (AS+MS)' rows. "
            f"Detected format: {fmt} ({col_desc})."
        )

    fmt_label = "Month-End" if fmt == "A" else "Daily Production & Performance"
    return {
        "plant":              PLANT,
        "month":              report_month,
        "detected_month":     detected_month,
        "source_type":        f"VISL Monthly Report ({fmt_label})",
        "sheets":             f"PDF ({n_pages} page) — VISL {fmt_label}",
        "workbook_sheets":    [f"PDF ({n_pages} pages)"],
        "report_type":        "MONTHLY",
        "production_rows":    prod_rows,
        "special_steel_rows": [],
        "special_steel_note": "",
        "techno_rows":        [],
        "techno_param_rows":  [],
    }
