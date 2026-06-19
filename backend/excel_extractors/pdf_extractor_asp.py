"""
ASP PDF extractor — handles two monthly report types:

1. REP*.pdf  (OMI Daily/Monthly Production Report, e.g. REP010526.pdf)
   Detected by: "CRUDE STEEL" + ("CONCAST" or "INGOT") in text, or filename starts with REP.
   Extracts: Total Crude Steel, Ingot Steel, Total Caster (Concast),
             Saleable Steel, Closing Stock.

2. FL*.pdf   (Finished Steel Production Report, e.g. FL26-27 MAY'26.pdf)
   Detected by: "BARS" + "FS PRD" in text, or filename starts with FL.
   Extracts: BARS Mill, FS PRD, Plate Mill individually, plus a computed
             "Finished Steel" total (sum of the three).

All raw tonnage values (T) are converted to '000T before returning.
extract_preview() returns rows in the standard format — no DB writes.
"""
import os
import re

PLANT = "ASP"

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# ── REP report: keyword → (item_name in production_table, search_alternatives)
_REP_ITEMS = [
    # keyword (lowercase)    item_name                 alternatives
    ("crude steel",          "Total Crude Steel",      ["total crude","CRUDE"]),
    ("concast",              "Total Caster",           ["cc steel", "continuous cast"]),
    ("ingot",                "Ingot Steel",            ["ingot steel"]),
    ("saleable steel",       "Saleable Steel",         ["saleable"]),
    ("closing stock",        "Closing Stock",          ["total stock", "stock"]),
]

# ── FL report: keyword → item_name
_FL_ITEMS = [
    ("bars",    "BARS Mill"),
    ("fs prd",  "FS PRD"),
    ("pl mill", "Plate Mill"),
]


def _nums_from_line(line: str):
    """Return all positive floats found in *line*, excluding year-like values (2000-2099)."""
    result = []
    for tok in re.findall(r'\d[\d,]*(?:\.\d+)?', line):
        try:
            v = float(tok.replace(',', ''))
        except ValueError:
            continue
        if 2000 <= v <= 2099:
            continue          # year token — skip
        if v <= 0:
            continue
        result.append(v)
    return result


def _nums_all(line: str):
    """Return ALL numbers from *line* including zeros/negatives, preserving column order.

    Used for FL column-indexed extraction where zeros mean 'no production that month'
    and must be kept to maintain column alignment.
    Excludes year-like values (2000-2099).
    """
    result = []
    for tok in re.findall(r'-?\d[\d,]*(?:\.\d+)?', line):
        try:
            v = float(tok.replace(',', ''))
        except ValueError:
            continue
        if 2000 <= abs(v) <= 2099:
            continue      # year token — skip
        result.append(v)
    return result


def _best_value(line: str, min_val: float = 50.0):
    """Largest number on the line that is >= min_val.

    Used for REP PDFs where the largest number is the MTD/FY total we want.
    """
    candidates = [v for v in _nums_from_line(line) if v >= min_val]
    return max(candidates) if candidates else None


def _find_keyword_line(lines, *keywords):
    """Return the first line whose lowercase text contains ALL keywords."""
    for ln in lines:
        low = ln.lower()
        if all(kw in low for kw in keywords):
            return ln
    return None


def _find_any_keyword_line(lines, primary, alternatives):
    """Return (matched_line, keyword_used) for primary or first matching alternative."""
    result = _find_keyword_line(lines, primary)
    if result:
        return result, primary
    for alt in alternatives:
        result = _find_keyword_line(lines, *alt.split())
        if result:
            return result, alt
    return None, primary


def _detect_report_type(full_text: str, filename: str = "") -> str:
    """Return 'REP', 'FL', or 'UNKNOWN'."""
    fname_upper = os.path.basename(filename).upper()

    # Filename prefix takes priority
    if fname_upper.startswith("REP"):
        return "REP"
    if fname_upper.startswith("FL"):
        return "FL"

    up = full_text.upper()
    # Content heuristics
    if "CRUDE STEEL" in up and ("CONCAST" in up or "INGOT" in up):
        return "REP"
    if ("BARS" in up or "PLATE MILL" in up or "PL MILL" in up) and "FS PRD" in up:
        return "FL"
    # Secondary FL hint
    if "FINISHED STEEL" in up and ("BARS" in up or "PLATE" in up):
        return "FL"

    return "UNKNOWN"


def _load_pdf_text(file_path: str):
    """Open PDF with pdfplumber, concatenate all page texts. Returns (text, n_pages)."""
    import pdfplumber

    try:
        with pdfplumber.open(file_path) as pdf:
            n = len(pdf.pages)
            parts = []
            for pg in pdf.pages:
                try:
                    parts.append(pg.extract_text() or "")
                except Exception:
                    parts.append("")
            return "\n".join(parts), n
    except Exception as exc:
        raise ValueError(f"Cannot open PDF '{os.path.basename(file_path)}': {exc}") from exc


def _parse_rep(lines, want_mon, yy, n_pages):
    """Extract production items from a REP-type PDF."""
    rows = []
    for primary, item_name, alts in _REP_ITEMS:
        ln, kw_used = _find_any_keyword_line(lines, primary, alts)
        if ln is not None:
            val = _best_value(ln, min_val=50.0)
            if val is not None:
                stored = round(val / 1000.0, 3)
                rows.append({
                    "item_name": item_name,
                    "value":     stored,
                    "unit":      "'000T",
                    "cell":      f"PDF ({n_pages}p) · {want_mon}'{yy}",
                    "pdf_label": ln.strip()[:70],
                    "status":    "ok",
                })
            else:
                rows.append({
                    "item_name": f"(no value) {item_name}",
                    "value":     None,
                    "unit":      "T",
                    "cell":      f"PDF ({n_pages}p) · {want_mon}'{yy}",
                    "pdf_label": ln.strip()[:70],
                    "status":    "unmapped",
                })
        else:
            rows.append({
                "item_name": f"(not found) {item_name}",
                "value":     None,
                "unit":      "T",
                "cell":      f"PDF ({n_pages}p) · {want_mon}'{yy}",
                "pdf_label": primary,
                "status":    "unmapped",
            })
    return rows


def _parse_fl(lines, want_mon, yy, n_pages):
    """Extract finished-steel mill items from a FL-type PDF.

    FL report column structure (fixed layout, same month header for all rows):
        [Shop name]  [Plan]  [Actual]  [other columns ...]
        BARS           40      199       0   125   0  ...
        FS PRD        400      323      81   183  ...
        PL MILL       200      175      88   211  ...

    Column 1 = label, Column 2 = Plan, Column 3 = Actual (what we want).
    → Pick the 2nd number (index 1, 0-based) from each keyword line.
    """
    rows = []
    found_vals = {}

    for keyword, item_name in _FL_ITEMS:
        ln = _find_keyword_line(lines, keyword)
        if ln is not None:
            # _nums_all preserves zeros to keep column positions intact
            nums = _nums_all(ln)
            # Need at least [plan, actual] = 2 numbers; actual is at index 1
            if len(nums) >= 2:
                val = nums[1]   # 2nd number = Actual (3rd column counting label)
                if val > 0:
                    stored = round(val / 1000.0, 3)
                    found_vals[item_name] = stored
                    rows.append({
                        "item_name": item_name,
                        "value":     stored,
                        "unit":      "'000T",
                        "cell":      f"PDF ({n_pages}p) · {want_mon}'{yy} col3(actual)",
                        "pdf_label": ln.strip()[:70],
                        "status":    "ok",
                    })
                else:
                    rows.append({
                        "item_name": f"(zero/neg) {item_name}",
                        "value":     val,
                        "unit":      "T",
                        "cell":      f"PDF ({n_pages}p) · {want_mon}'{yy} col3(actual)",
                        "pdf_label": ln.strip()[:70],
                        "status":    "unmapped",
                    })
            elif len(nums) == 1:
                # Only one number found — take it as-is (might be just actual, no plan)
                val = nums[0]
                stored = round(val / 1000.0, 3)
                found_vals[item_name] = stored
                rows.append({
                    "item_name": item_name,
                    "value":     stored,
                    "unit":      "'000T",
                    "cell":      f"PDF ({n_pages}p) · {want_mon}'{yy} col2(only)",
                    "pdf_label": ln.strip()[:70],
                    "status":    "ok",
                })
            else:
                rows.append({
                    "item_name": f"(no value) {item_name}",
                    "value":     None,
                    "unit":      "T",
                    "cell":      f"PDF ({n_pages}p) · {want_mon}'{yy}",
                    "pdf_label": ln.strip()[:70],
                    "status":    "unmapped",
                })
        else:
            rows.append({
                "item_name": f"(not found) {item_name}",
                "value":     None,
                "unit":      "T",
                "cell":      f"PDF ({n_pages}p) · {want_mon}'{yy}",
                "pdf_label": keyword,
                "status":    "unmapped",
            })

    # Compute Finished Steel = sum of all found mill items
    ok_vals = list(found_vals.values())
    if ok_vals:
        total_fs = round(sum(ok_vals), 3)
        component_labels = " + ".join(
            f"{k}={v}" for k, v in found_vals.items()
        )
        rows.append({
            "item_name": "Finished Steel",
            "value":     total_fs,
            "unit":      "'000T",
            "cell":      f"PDF ({n_pages}p) · {want_mon}'{yy} (computed)",
            "pdf_label": component_labels,
            "status":    "ok",
        })

    return rows


def extract_preview(file_path: str, report_month: str, **_kwargs) -> dict:
    """Extract ASP production data from a PDF report.

    Auto-detects file type (REP = crude steel report, FL = finished steel report)
    from the filename or PDF text content.

    Returns a dict in the standard extract_preview() format — no DB writes.
    """
    import sys

    y, m    = int(report_month[:4]), int(report_month[5:7])
    want_mon = _MONTHS[m - 1]
    yy       = str(y)[2:]

    fname = os.path.basename(file_path)
    print(f"[ASP PDF] extract_preview: file={fname}  month={want_mon}'{yy}",
          flush=True, file=sys.stderr)

    full_text, n_pages = _load_pdf_text(file_path)
    print(f"[ASP PDF] Loaded {n_pages} pages, {len(full_text)} chars",
          flush=True, file=sys.stderr)

    report_type = _detect_report_type(full_text, fname)
    print(f"[ASP PDF] Detected type: {report_type}", flush=True, file=sys.stderr)

    if report_type == "UNKNOWN":
        raise ValueError(
            f"Cannot identify ASP report type from '{fname}'. "
            "Expected a REP*.pdf (crude steel) or FL*.pdf (finished steel) report."
        )

    lines = full_text.splitlines()

    if report_type == "REP":
        prod_rows   = _parse_rep(lines, want_mon, yy, n_pages)
        source_type = "ASP OMI Production Report (REP)"
        sheets      = f"PDF ({n_pages} pages) — Crude Steel & Stock"
    else:
        prod_rows   = _parse_fl(lines, want_mon, yy, n_pages)
        source_type = "ASP Finished Steel Report (FL)"
        sheets      = f"PDF ({n_pages} pages) — Finished Steel by Mill"

    ok = sum(1 for r in prod_rows if r["status"] == "ok")
    print(f"[ASP PDF] {report_type}: {ok}/{len(prod_rows)} rows ok", flush=True, file=sys.stderr)

    return {
        "plant":              PLANT,
        "month":              report_month,
        "source_type":        source_type,
        "sheets":             sheets,
        "workbook_sheets":    [f"PDF ({n_pages} pages)"],
        "report_type":        report_type,
        "production_rows":    prod_rows,
        "special_steel_rows": [],
        "special_steel_note": "",
        "techno_rows":        [],
        "techno_param_rows":  [],
    }
