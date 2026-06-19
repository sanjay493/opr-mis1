"""
SSP PDF extractor — SSP-DPR Monthly Report (e.g. SSP-DPR-01.06.206-REVISED.pdf)

Single-page DPR with this column layout:
    UNITWISE PRODUCTION  On Date Actual | Cum Actual | Monthly Target | Stock As on Date | Stock As on 1st
    SALEABLE PRODUCTION  On Date Actual | Cum Actual | Monthly Target | Stock As on Date

Extraction mapping:
  Crude Steel  — "SMS (SLAB)" row → 1st number (On Date col is blank for slab → 1st = Cum Actual)
  Saleable &
  Finished Steel — "SALEABLE PRODUCTION" section → "TOTAL" row → 2nd number (= Cum Actual)

Values are in Tonnes in the PDF → stored as '000T (÷ 1000).
"""
import os
import re
import sys

PLANT = "SSP"

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
    """All positive floats on the line, excluding year-like values (2000-2099)."""
    result = []
    for tok in re.findall(r'\d[\d,]*(?:\.\d+)?', line):
        try:
            v = float(tok.replace(',', ''))
        except ValueError:
            continue
        if 2000 <= v <= 2099:
            continue
        result.append(v)
    return result


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


def extract_preview(file_path: str, report_month: str, **_kwargs) -> dict:
    """
    Extract SSP production data from a monthly DPR PDF.

    Returns a dict in the standard extract_preview() format — no DB writes.
    """
    y, m     = int(report_month[:4]), int(report_month[5:7])
    want_mon = _MONTHS[m - 1]
    yy       = str(y)[2:]
    fname    = os.path.basename(file_path)

    print(f"[SSP PDF] extract_preview: file={fname}  month={want_mon}'{yy}",
          flush=True, file=sys.stderr)

    full_text, n_pages = _load_pdf_text(file_path)
    print(f"[SSP PDF] Loaded {n_pages} pages, {len(full_text)} chars", flush=True, file=sys.stderr)
    lines = full_text.splitlines()

    prod_rows = []
    cell_tag  = f"PDF ({n_pages}p) · {want_mon}'{yy}"

    # ── Crude Steel: SMS (SLAB) row ─────────────────────────────────────────
    # On Date column is blank for slab → first number on the line = Cum Actual
    crude_val = None
    crude_label = "(SMS SLAB line not found)"
    for ln in lines:
        low = ln.lower()
        if "sms" in low and "slab" in low:
            nums = _nums_from_line(ln)
            if nums:
                crude_val   = nums[0]       # 1st number = Cum Actual (On Date blank)
                crude_label = ln.strip()[:80]
            break

    prod_rows.append(_row("Total Crude Steel", crude_val,
                          f"{cell_tag} · SMS(SLAB) Cum Actual", crude_label))

    # ── Saleable & Finished Steel: SALEABLE section → TOTAL row ─────────────
    # Columns: [On Date] [Cum Actual] [Target] [Stock] → index 1 = Cum Actual
    sal_val   = None
    sal_label = "(Saleable TOTAL line not found)"
    in_saleable = False
    for ln in lines:
        low = ln.lower()
        if "saleable" in low and ("production" in low or "prod" in low):
            in_saleable = True
            continue
        if in_saleable:
            if "total" in low:
                nums = _nums_from_line(ln)
                if len(nums) >= 2:
                    sal_val   = nums[1]     # 2nd number = Cum Actual
                    sal_label = ln.strip()[:80]
                elif len(nums) == 1:
                    sal_val   = nums[0]
                    sal_label = ln.strip()[:80]
                break
            # Stop scanning if we've passed into another major section
            if re.match(r'^\d+\.\d+\s', ln) and "saleable" not in low:
                break

    for item in ("Saleable Steel", "Finished Steel"):
        prod_rows.append(_row(item, sal_val,
                              f"{cell_tag} · Saleable TOTAL Cum Actual", sal_label))

    ok = sum(1 for r in prod_rows if r["status"] == "ok")
    print(f"[SSP PDF] {ok}/{len(prod_rows)} rows ok", flush=True, file=sys.stderr)

    if ok == 0:
        raise ValueError(
            "No values extracted. Verify this is an SSP DPR PDF with "
            "'SMS (SLAB)' and 'SALEABLE PRODUCTION ... TOTAL' rows."
        )

    return {
        "plant":              PLANT,
        "month":              report_month,
        "source_type":        "SSP Daily Production Report (DPR)",
        "sheets":             f"PDF ({n_pages} page) — SSP DPR",
        "workbook_sheets":    [f"PDF ({n_pages} pages)"],
        "report_type":        "DPR",
        "production_rows":    prod_rows,
        "special_steel_rows": [],
        "special_steel_note": "",
        "techno_rows":        [],
        "techno_param_rows":  [],
    }
