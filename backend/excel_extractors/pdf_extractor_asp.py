"""
ASP PDF extractor — handles two monthly report types:

1. REP*.pdf  (OMI Daily Performance Summary Report, e.g. REP010526.pdf)
   Detected by: "CRUDE STEEL" + ("CONCAST" or "INGOT") in text, or filename starts with REP.
   Report month auto-detected from its "...REPORT FOR DD/MM/YYYY" line (that
   date is always the last day of the month being reported). Each item lives
   in a fixed-column row — [Label][Unit] [OnDateABP] [OnDateACT] [MonthlyABP]
   [CumAct] [CumAct-dup] [Rate%] [CPLY] ... — sharing the page with an
   unrelated equipment-delay table that spills onto the same lines further
   right, and with a "<ITEM> ACTUAL (T) <12 months of history>" row that
   shares the item's own name. Extracts, matched by exact row-label (not
   substring, to avoid both of those traps) and picking the run's 4th
   number (see _rep_resolve_actual() for how a rare disagreement between the
   normally-duplicate 4th/5th columns is resolved):
     Total Crude Steel, Ingot Steel (raw ingot-mould production — NOT the
     same metric as FL's "ING" below, see (2)), Total Caster (Concast label
     varies: "TOTAL CC" / "TOTAL CC SLAB" / "CONCAST PRODN" depending on
     report vintage), Saleable Steel.
   Closing Stock lives in a separate single-value row ("TOTAL PLANT ST.
   <value>"), extracted by regex — carefully distinguished from the
   unrelated "TOTAL PLANT STOCK <12 months of history>" row that precedes
   or follows it.

2. FL*.pdf   (Finished Steel "FLASH" Production Report, e.g. FL26-27 MAY'26.pdf)
   Detected by: "BARS" + "FS PRD" in text, or filename starts with FL.
   Fixed-width monthly table — report month auto-detected from the table's
   own "DETAILS <MON>'<YY> ..." header row (more reliable than the "FLASH :"
   banner line above it, which is occasionally garbled by an overlapping
   text layer in some source PDFs). For BOTH that report month and the
   immediately preceding month — its own dedicated "Actual" column further
   right in the same table, no second file needed — extracts:
     ING      (Production for Finishing section) → Ingot Semis (the
              semi-finished output rolled from ingots — a different, later
              stage than REP/Excel's raw "Ingot Steel" crude production;
              was previously mislabeled "Ingot Steel" here too, which let a
              later FL upload silently overwrite the correct REP-sourced
              value since both wrote the same item_name)
     BILLETS  (Saleable Production section)      → Billets
     BARS     (Saleable Production section)      → BARS
     FS PRD.  (Saleable Production section)      → FS PRD
     PL MILL  (Saleable Production section)      → PLATES
     TOTAL    (Saleable Production section)      → Saleable Steel
     TOTAL    (DESPATCH section, separate from the above) → Saleable Steel
              Despatch — actual dispatched/sold quantity, confirmed against
              REP*.pdf's "PLANT DESPATCH T" row (near-exact match)
   Column values are matched by x-position against a reference row
   ("LIQ.PRD", always fully populated) rather than by list index, so a
   row with its own blank %Ach/CPLY cells doesn't shift later columns
   out from under the Actual/Prev-Actual picks.

   Finished Steel = BARS + FS PRD + PL MILL (computed here, per month, only
   when all three are found — this report has no "FORGINGS" line in its
   Saleable Production section, unlike the DAILY FLASH Excel source handled
   by excel_extractor_asp.py, whose own Finished Steel = BARS+FORGINGS+PLATES
   is a different formula for a different source file).

All raw tonnage values (T) are converted to '000T before returning.
extract_preview() returns rows in the standard format — no DB writes.
"""
import os
import re

PLANT = "ASP"

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# ── REP report: item_name → acceptable (row-start token sequences), tried in
# order. Matching the row-start exactly (not "keyword anywhere in line") is
# what keeps this off the "<ITEM> ACTUAL (T) <history>" row and the small
# performance-summary box in the page header, both of which contain the same
# keywords as substrings elsewhere on the page.
_REP_LABEL_PATTERNS = {
    "Total Crude Steel": [["CRUDE", "T"], ["CRUDE", "STEEL", "T"]],
    "Total Caster": [
        ["TOTAL", "CC", "T"], ["TOTAL", "CC", "SLAB", "T"], ["CONCAST", "PRODN"],
        ["CC", "SLAB", "T"],   # fallback for when the primary label's text is missing from the PDF's text layer
    ],
    "Ingot Steel":       [["INGOT", "PRODUCTION", "T"]],
    "Saleable Steel":    [["SALEABLE", "STEEL", "T"]],
    # NOT the "SALEABLE STEEL T" row above (that's production) — this is the
    # separate "PLANT DESPATCH T" row, confirmed against FL*.pdf's DESPATCH
    # section TOTAL (near-exact match, e.g. Jul'26: REP 12339 vs FL 12338;
    # SALEABLE STEEL's own CUMM for the same month is a different number,
    # 11543, matching FL's SALEABLE PRDUCTION section instead).
    "Saleable Steel Despatch": [["PLANT", "DESPATCH", "T"]],
}
# "ST" not immediately followed by "OCK" — separates the single current-value
# "TOTAL PLANT ST. <value>" row from the unrelated same-prefix
# "TOTAL PLANT STOCK <12 months of history>" row.
_REP_CLOSING_STOCK_RE = re.compile(r'\bTOTAL\s+PLANT\s+ST(?!OCK)\.?\s*(-?\d[\d,]*(?:\.\d+)?)', re.I)
_REP_DATE_RE = re.compile(r'\bFOR\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\b')

# ── FL report: (label words, item_name, is_exact_total)
_FL_ITEMS = [
    (("ING",),          "Ingot Semis",   False),
    (("BILLETS",),      "Billets",       False),
    (("BARS",),         "BARS",          False),
    (("FS", "PRD."),    "FS PRD",        False),
    (("PL", "MILL"),    "PLATES",        False),
    (("TOTAL",),        "Saleable Steel", True),   # exact "TOTAL" row only — not "TOTAL CC SL"
    # Separate "DESPATCH" section's own TOTAL row — actual dispatched/sold
    # quantity, not production. Confirmed against REP*.pdf's "PLANT
    # DESPATCH T" row (near-exact match; see _REP_LABEL_PATTERNS' comment).
    (("TOTAL",),        "Saleable Steel Despatch", True),
]
# Finished Steel = sum of these three (see module docstring)
_FL_FINISHED_STEEL_PARTS = ["BARS", "FS PRD", "PLATES"]

_FL_MONTH_TO_NUM = {
    "JAN": 1, "FEB": 2, "MAR": 3, "MARCH": 3, "APR": 4, "APRIL": 4,
    "MAY": 5, "JUN": 6, "JUNE": 6, "JUL": 7, "JULY": 7, "AUG": 8,
    "SEP": 9, "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_FL_DETAILS_MONTH_RE = re.compile(r"^([A-Za-z]+)'(\d{2,4})$")
_NUM_RE = re.compile(r'^-?\d[\d,]*(?:\.\d+)?$')


def _fmt_month(ym: str) -> str:
    try:
        y, mo = ym[:4], int(ym[5:7])
        return f"{_MONTHS[mo - 1].title()} {y}"
    except Exception:
        return ym


def _assert_month_match(detected, user_month: str, report_kind: str) -> None:
    if detected and user_month and detected != user_month:
        raise ValueError(
            f"Month mismatch: this {report_kind}'s own header shows "
            f"{_fmt_month(detected)}, but you selected {_fmt_month(user_month)}. "
            f"Please select '{_fmt_month(detected)}' in the month picker, "
            f"or upload the report for {_fmt_month(user_month)}."
        )


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


def _detect_rep_report_month(full_text: str):
    """The '...REPORT FOR DD/MM/YYYY' date is always the last day of the
    month being reported (e.g. 'FOR 30/04/2026' is the April 2026 report,
    filed the next day) — not the following month. Returns 'YYYY-MM' or None."""
    m = _REP_DATE_RE.search(full_text)
    if not m:
        return None
    _, mo, yr = m.groups()
    month = int(mo)
    if not (1 <= month <= 12):
        return None
    year = int(yr) if len(yr) == 4 else 2000 + int(yr)
    return f"{year}-{month:02d}"


def _rep_match_row(line: str, patterns):
    """If *line* starts with one of *patterns* (a list of token sequences),
    return (all_tokens, label_token_count) for the first pattern that fits."""
    toks = line.split()
    for pat in patterns:
        if len(toks) > len(pat) and [t.upper() for t in toks[:len(pat)]] == pat:
            return toks, len(pat)
    return None, None


def _rep_find_row(lines, patterns):
    for ln in lines:
        toks, label_len = _rep_match_row(ln, patterns)
        if toks is not None:
            return ln, toks, label_len
    return None, None, None


def _rep_resolve_actual(nums):
    """nums are a REP production row's numbers in column order: [OnDateABP,
    OnDateACT, MonthlyABP, CumAct, CumAct(dup), Rate%, CPLY, ...trailing
    junk from an unrelated table sharing the line]. Returns the month's
    Cumulative Actual (the 4th number), which is what we store.

    The 4th and 5th numbers are normally identical (a duplicated column in
    the source report's export) but occasionally diverge; when they do,
    prefer whichever is closer to MonthlyABP × Rate% ÷ 100, since that's
    self-consistent with the row's own recorded % achievement."""
    if len(nums) < 4:
        return None
    a = nums[3]
    b = nums[4] if len(nums) > 4 else None
    if b is None or a == b or len(nums) <= 5:
        return a
    monthly_abp, rate_pct = nums[2], nums[5]
    if not monthly_abp:
        return a
    implied = monthly_abp * rate_pct / 100.0
    return b if abs(b - implied) < abs(a - implied) else a


def _parse_rep(lines, full_text, want_mon, yy, n_pages):
    """Extract production items from a REP-type PDF. See module docstring
    for the row-matching and column-resolution approach."""
    rows = []
    for item_name, patterns in _REP_LABEL_PATTERNS.items():
        ln, toks, label_len = _rep_find_row(lines, patterns)
        if ln is None:
            rows.append({
                "item_name": f"(not found) {item_name}", "value": None, "unit": "T",
                "cell": f"PDF ({n_pages}p) · {want_mon}'{yy}",
                "pdf_label": "/".join(patterns[0]), "status": "unmapped",
            })
            continue
        nums = [float(t.replace(",", "")) for t in toks[label_len:] if _NUM_RE.match(t)]
        val = _rep_resolve_actual(nums)
        if val is not None:
            rows.append({
                "item_name": item_name, "value": round(val / 1000.0, 3), "unit": "'000T",
                "cell": f"PDF ({n_pages}p) · {want_mon}'{yy} (cumulative actual)",
                "pdf_label": ln.strip()[:70], "status": "ok",
            })
        else:
            rows.append({
                "item_name": f"(no value) {item_name}", "value": None, "unit": "T",
                "cell": f"PDF ({n_pages}p) · {want_mon}'{yy}",
                "pdf_label": ln.strip()[:70], "status": "unmapped",
            })

    m = _REP_CLOSING_STOCK_RE.search(full_text)
    if m:
        stock_val = float(m.group(1).replace(",", ""))
        rows.append({
            "item_name": "Closing Stock", "value": round(stock_val / 1000.0, 3), "unit": "'000T",
            "cell": f"PDF ({n_pages}p) · {want_mon}'{yy}",
            "pdf_label": "TOTAL PLANT ST.", "status": "ok",
        })
    else:
        rows.append({
            "item_name": "(not found) Closing Stock", "value": None, "unit": "T",
            "cell": f"PDF ({n_pages}p) · {want_mon}'{yy}",
            "pdf_label": "TOTAL PLANT ST.", "status": "unmapped",
        })
    return rows


def _load_pdf_word_rows(file_path: str):
    """Open PDF with pdfplumber, return (rows, n_pages).

    rows is every printed line of every page, in reading order, as a list of
    word-dicts ({'text', 'x0', ...}) sorted left-to-right — needed (instead
    of plain extract_text() lines) so FL items can be matched to the report
    month / previous month columns by x-position rather than list index.
    Words are grouped by pdfplumber's rounded 'top' coordinate, which is
    robust against the ~1px jitter between words printed on the same line.
    """
    import pdfplumber

    try:
        with pdfplumber.open(file_path) as pdf:
            n = len(pdf.pages)
            rows = []
            for pg in pdf.pages:
                by_top = {}
                for w in pg.extract_words():
                    by_top.setdefault(round(w["top"]), []).append(w)
                for key in sorted(by_top.keys()):
                    rows.append(sorted(by_top[key], key=lambda w: w["x0"]))
            return rows, n
    except Exception as exc:
        raise ValueError(f"Cannot open PDF '{os.path.basename(file_path)}': {exc}") from exc


def _fl_row_text(row) -> str:
    return " ".join(w["text"] for w in row)


def _fl_is_separator_row(row) -> bool:
    txt = "".join(w["text"] for w in row)
    return bool(txt) and set(txt) <= set("=")


def _fl_section_blocks(rows):
    """Split the table into blocks between '====' separator rows."""
    sep_idx = [i for i, r in enumerate(rows) if _fl_is_separator_row(r)]
    blocks = []
    for a, b in zip(sep_idx, sep_idx[1:]):
        if b - a > 1:
            blocks.append(rows[a + 1:b])
    return blocks


def _fl_find_block(blocks, keyword: str):
    """First block whose own header (its first row) contains *keyword*."""
    for blk in blocks:
        if blk and keyword in _fl_row_text(blk[0]).upper():
            return blk
    return None


def _fl_row_numbers(row, label_word_count: int):
    """(value, x0) for every numeric token after the row's label words."""
    out = []
    for w in row[label_word_count:]:
        if _NUM_RE.match(w["text"]):
            out.append((float(w["text"].replace(",", "")), w["x0"]))
    return out


def _fl_calibrate_columns(rows):
    """Locate the 'LIQ.PRD' reference row (first data row, always present
    and fully populated) and return the x0 of its 2nd and 4th numeric
    columns — i.e. Actual (report month) and Actual (previous month).
    Every FL row shares the same left-to-right column sequence (Plan, Act,
    %Ach, PrevAct, LYAct, ...), so matching by x-position against these two
    reference columns is safe even when a target row's OWN %Ach/CPLY cell
    is blank and would otherwise shift a naive list-index lookup."""
    for row in rows:
        if row and row[0]["text"].upper().startswith("LIQ"):
            nums = _fl_row_numbers(row, 1)
            if len(nums) >= 4:
                return nums[1][1], nums[3][1]
    return None, None


def _fl_find_item_row(block, label_words, exact_total: bool):
    if block is None:
        return None
    upper_label = [w.upper() for w in label_words]
    for row in block:
        if len(row) <= len(label_words):
            continue
        if [w["text"].upper() for w in row[:len(label_words)]] != upper_label:
            continue
        if exact_total and not _NUM_RE.match(row[len(label_words)]["text"]):
            continue   # e.g. "TOTAL CC SL" — not the bare "TOTAL" row
        return row
    return None


def _fl_nearest(nums, target_x: float, tol: float = 40.0):
    best, best_d = None, None
    for val, x in nums:
        d = abs(x - target_x)
        if d <= tol and (best_d is None or d < best_d):
            best, best_d = val, d
    return best


def _detect_fl_report_month(rows):
    """Read the FL table's own 'DETAILS <MON>'<YY|YYYY> ...' header row —
    its 2nd word is always the report month. Returns 'YYYY-MM' or None."""
    for row in rows:
        if row and row[0]["text"].upper() == "DETAILS" and len(row) >= 2:
            m = _FL_DETAILS_MONTH_RE.match(row[1]["text"])
            if not m:
                continue
            mon = _FL_MONTH_TO_NUM.get(m.group(1).upper())
            if mon is None:
                continue
            yy = m.group(2)
            year = int(yy) if len(yy) == 4 else 2000 + int(yy)
            return f"{year}-{mon:02d}"
    return None


def _fl_prev_month(report_month: str) -> str:
    y, m = int(report_month[:4]), int(report_month[5:7])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def _parse_fl_two_month(rows, report_month: str, prev_month: str, n_pages: int):
    """Extract ING / BILLETS / BARS / FS PRD. / PL MILL / TOTAL for both the
    report month and the previous month from an FL-type PDF, then derive
    Finished Steel = BARS + FS PRD + PL MILL for each. See module docstring
    for the item → item_name mapping and the column-calibration approach."""
    act_x, prev_x = _fl_calibrate_columns(rows)
    if act_x is None:
        raise ValueError(
            "Could not locate the FL report's 'LIQ.PRD' reference row — "
            "unexpected table layout, cannot calibrate columns."
        )

    blocks = _fl_section_blocks(rows)
    finishing_block = _fl_find_block(blocks, "FINISHING")
    saleable_block  = _fl_find_block(blocks, "SALEABLE")
    despatch_block  = _fl_find_block(blocks, "DESPATCH")
    section_for = {
        "Ingot Semis":              finishing_block,
        "Billets":                  saleable_block,
        "BARS":                     saleable_block,
        "FS PRD":                   saleable_block,
        "PLATES":                   saleable_block,
        "Saleable Steel":           saleable_block,
        "Saleable Steel Despatch":  despatch_block,
    }

    out_rows = []
    parts_by_month = {report_month: {}, prev_month: {}}  # item_name -> value, for Finished Steel
    for label_words, item_name, exact_total in _FL_ITEMS:
        block = section_for[item_name]
        row = _fl_find_item_row(block, label_words, exact_total)
        pdf_label = " ".join(label_words)
        if row is None:
            for ym in (report_month, prev_month):
                out_rows.append({
                    "item_name": f"(not found) {item_name}", "value": None, "unit": "T",
                    "cell": f"PDF ({n_pages}p) · FL row not found",
                    "pdf_label": pdf_label, "status": "unmapped", "report_month": ym,
                })
            continue

        nums = _fl_row_numbers(row, len(label_words))
        act_val  = _fl_nearest(nums, act_x)
        prev_val = _fl_nearest(nums, prev_x)
        row_text = _fl_row_text(row)[:70]
        for ym, val, tag in (
            (report_month, act_val, f"{_fmt_month(report_month)} Actual"),
            (prev_month,   prev_val, f"{_fmt_month(prev_month)} Actual"),
        ):
            if val is not None:
                out_val = round(val / 1000.0, 3)
                out_rows.append({
                    "item_name": item_name, "value": out_val, "unit": "'000T",
                    "cell": f"PDF ({n_pages}p) · {tag}",
                    "pdf_label": row_text, "status": "ok", "report_month": ym,
                })
                if item_name in _FL_FINISHED_STEEL_PARTS:
                    parts_by_month[ym][item_name] = out_val
            else:
                out_rows.append({
                    "item_name": f"(no value) {item_name}", "value": None, "unit": "T",
                    "cell": f"PDF ({n_pages}p) · {tag}",
                    "pdf_label": row_text, "status": "unmapped", "report_month": ym,
                })

    for ym in (report_month, prev_month):
        parts = parts_by_month[ym]
        if all(p in parts for p in _FL_FINISHED_STEEL_PARTS):
            fs_val = round(sum(parts[p] for p in _FL_FINISHED_STEEL_PARTS), 3)
            out_rows.append({
                "item_name": "Finished Steel", "value": fs_val, "unit": "'000T",
                "cell": f"PDF ({n_pages}p) · {_fmt_month(ym)} [computed: BARS+FS PRD+PL MILL]",
                "pdf_label": "BARS + FS PRD. + PL MILL", "status": "ok", "report_month": ym,
            })
    return out_rows


def extract_preview(file_path: str, report_month: str, **_kwargs) -> dict:
    """Extract ASP production data from a PDF report.

    Auto-detects file type (REP = crude steel report, FL = finished steel report)
    from the filename or PDF text content.

    Returns a dict in the standard extract_preview() format — no DB writes.
    """
    import sys

    fname = os.path.basename(file_path)
    print(f"[ASP PDF] extract_preview: file={fname}  month={report_month}",
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

    out_month = report_month

    if report_type == "REP":
        detected = _detect_rep_report_month(full_text)
        print(f"[ASP PDF] REP detected month: {detected}", flush=True, file=sys.stderr)
        _assert_month_match(detected, report_month, "REP report")
        out_month = detected or report_month
        y, m      = int(out_month[:4]), int(out_month[5:7])
        want_mon  = _MONTHS[m - 1]
        yy        = str(y)[2:]
        lines       = full_text.splitlines()
        prod_rows   = _parse_rep(lines, full_text, want_mon, yy, n_pages)
        source_type = "ASP OMI Daily Performance Summary Report (REP)"
        sheets      = f"PDF ({n_pages} pages) — Crude Steel, Ingot, Concast, Saleable Steel & Stock"
    else:
        word_rows, n_pages = _load_pdf_word_rows(file_path)
        detected = _detect_fl_report_month(word_rows)
        print(f"[ASP PDF] FL detected month: {detected}", flush=True, file=sys.stderr)
        _assert_month_match(detected, report_month, "FL report")
        out_month  = detected or report_month
        prev_month = _fl_prev_month(out_month)
        prod_rows   = _parse_fl_two_month(word_rows, out_month, prev_month, n_pages)
        source_type = "ASP Finished Steel FLASH Report (FL)"
        sheets      = (f"PDF ({n_pages} pages) — Ingot/Billets/Bars/Plates/Saleable Steel "
                       f"({_fmt_month(out_month)} + {_fmt_month(prev_month)})")

    ok = sum(1 for r in prod_rows if r["status"] == "ok")
    print(f"[ASP PDF] {report_type}: {ok}/{len(prod_rows)} rows ok", flush=True, file=sys.stderr)

    return {
        "plant":              PLANT,
        "month":              out_month,
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
