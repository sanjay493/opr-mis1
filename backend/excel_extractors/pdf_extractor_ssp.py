"""
SSP PDF extractor — SSP-DPR Monthly Report (e.g. SSP-DPR-01.06.206-REVISED.pdf)

Single-page DPR with 5 numbered sections, each row laid out as:
    On Date Actual | Cum Actual | Monthly Target | Rate | Stock As on Date | Stock As on 1st
(trailing columns are absent on some rows — e.g. SMS (SLAB) has no On Date
Actual, so its first number IS the Cum Actual).

Extraction mapping (all "Cum Actual" / "Stock As on Date" columns):
  1.0 UNITWISE PRODUCTION
    Total Crude Steel   — "SMS (SLAB)" row, Cum Actual (On Date blank → 1st number)
    HRM                 — "HRM" row, Cum Actual
    Input SS Slab       — "- STAINLESS" row, Stock As on Date
    Input Carbon Slab   — "- CARBON" row, Stock As on Date
  2.0 SALEABLE PRODUCTION
    Total Saleable Steel     — "TOTAL" row, Cum Actual
    Carbon Steel Production  — "HRCS" row, Cum Actual
    NO1 Production           — "NO1" row, Cum Actual
    CRSS Production          — "CRSS" row, Cum Actual
    HRSS Production          — "HRSS" row, Cum Actual (no Target/Stock cols on this row)
    (Saleable Steel / Finished Steel — same "TOTAL" Cum Actual, existing aliases)
  3.0 DESPATCHES
    Finished Carbon Steel Despatch — "HRCS" row, Cum Actual
    Total Saleable Steel Despatch  — "TOTAL" row, Cum Actual
    Finished Carbon Steel          — "HRCS" row, Stock As on Date
    Finished Total Steel           — "TOTAL" row, Stock As on Date
    Finished Stainless Steel       — computed: Finished Total Steel - Finished Carbon Steel

Values are in Tonnes in the PDF → stored as '000T (÷ 1000).
"""
import os
import re
import sys

PLANT = "SSP"

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

_SECTION_ANCHORS = [
    ("unitwise",   re.compile(r'^1\.0\s+UNITWISE', re.I)),
    ("saleable",   re.compile(r'^2\.0\s+SALEABLE', re.I)),
    ("despatches", re.compile(r'^3\.0\s+DESPATCHES', re.I)),
    ("sales",      re.compile(r'^4\.0\s+SALES', re.I)),
    ("raw_material", re.compile(r'^5\.0\s+RAW', re.I)),
]


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
    """All positive floats on the line.

    Unlike the other plants' PDF extractors, this does NOT exclude
    year-like values (2000-2099) — SSP's DPR rows are matched and read
    per-section (never against the report's own date header line), and
    tonnage/stock figures for this plant routinely fall in that range
    (e.g. a 'Stock As on 1st' of 2017 t), so filtering them out would
    silently drop a real column value instead of a stray year token.
    """
    result = []
    for tok in re.findall(r'\d[\d,]*(?:\.\d+)?', line):
        try:
            v = float(tok.replace(',', ''))
        except ValueError:
            continue
        result.append(v)
    return result


def _split_sections(lines):
    """Split report lines into named sections by their '#.0 LABEL' anchors."""
    sections = {}
    cur_key, cur_lines = None, []
    for ln in lines:
        matched = None
        for key, pat in _SECTION_ANCHORS:
            if pat.match(ln.strip()):
                matched = key
                break
        if matched:
            if cur_key:
                sections[cur_key] = cur_lines
            cur_key, cur_lines = matched, []
            continue
        if cur_key:
            cur_lines.append(ln)
    if cur_key:
        sections[cur_key] = cur_lines
    return sections


def _find_row(lines, predicate):
    """First line in `lines` matching predicate(upper-stripped text) →
    (nums, label) or (None, None) if not found."""
    for ln in lines:
        if predicate(ln.strip().upper()):
            return _nums_from_line(ln), ln.strip()[:80]
    return None, None


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
    sections = _split_sections(lines)

    prod_rows = []
    cell_tag  = f"PDF ({n_pages}p) · {want_mon}'{yy}"

    def add(item_name, section_key, predicate, col_from_end, tag_suffix):
        """col_from_end: negative index counted from the row's last column
        (Stock As on 1st / Rate / whatever trails). 'On Date Actual' is the
        only column that goes missing on a zero-production day, so counting
        from the end stays correct whether or not it's present — counting
        from the front would silently misread every later column on those
        rows (see 'HRM'/'STAINLESS'/'CARBON' in the 31/05/2026 report)."""
        nums, label = _find_row(sections.get(section_key, []), predicate)
        val = None
        if nums is not None and len(nums) >= abs(col_from_end):
            val = nums[col_from_end]
        if nums is None:
            label = f"({item_name} line not found)"
        prod_rows.append(_row(item_name, val, f"{cell_tag} · {tag_suffix}", label))
        return val

    # ── 1.0 UNITWISE PRODUCTION ─────────────────────────────────────────────
    # Total Crude Steel — SMS (SLAB) row: [OnDate?, Cum, Target, Rate].
    # On Date is normally blank for slab, but count from the end (like the
    # other rows below) so a report where it's present wouldn't misread.
    crude_nums, crude_label = _find_row(
        sections.get("unitwise", []),
        lambda t: t.startswith("SMS") and "SLAB" in t)
    crude_val = crude_nums[-3] if crude_nums and len(crude_nums) >= 3 else None
    if crude_nums is None:
        crude_label = "(SMS SLAB line not found)"
    prod_rows.append(_row("Total Crude Steel", crude_val,
                          f"{cell_tag} · SMS(SLAB) Cum Actual", crude_label))

    # unitwise 6-col layout: [OnDate?, Cum, Target, Rate, StockDate, Stock1st]
    add("HRM", "unitwise", lambda t: t.startswith("HRM"), -5, "HRM Cum Actual")
    add("Input SS Slab", "unitwise", lambda t: t.startswith("- STAINLESS") or t.startswith("STAINLESS"),
        -2, "- STAINLESS Stock As on Date")
    add("Input Carbon Slab", "unitwise", lambda t: t.startswith("- CARBON") or t.startswith("CARBON"),
        -2, "- CARBON Stock As on Date")

    # ── 2.0 SALEABLE PRODUCTION ─────────────────────────────────────────────
    # 4-col layout: [OnDate?, Cum, Target, StockDate]
    sal_nums, sal_label = _find_row(sections.get("saleable", []), lambda t: t.startswith("TOTAL"))
    sal_val = sal_nums[-3] if sal_nums and len(sal_nums) >= 3 else None
    if sal_nums is None:
        sal_label = "(Saleable TOTAL line not found)"
    sal_tag = f"{cell_tag} · SALEABLE PRODUCTION TOTAL Cum Actual"

    for item in ("Total Saleable Steel", "Saleable Steel", "Finished Steel"):
        prod_rows.append(_row(item, sal_val, sal_tag, sal_label))

    add("Carbon Steel Production", "saleable", lambda t: t.startswith("HRCS"),
        -3, "SALEABLE PRODUCTION HRCS Cum Actual")
    add("NO1 Production", "saleable", lambda t: t.startswith("NO1"),
        -3, "SALEABLE PRODUCTION NO1 Cum Actual")
    add("CRSS Production", "saleable", lambda t: t.startswith("CRSS"),
        -3, "SALEABLE PRODUCTION CRSS Cum Actual")
    # HRSS carries no Monthly Target / Stock in either sample month — only
    # [OnDate, Cum] (or just [Cum] if On Date itself goes blank) — so Cum is
    # whatever number trails, not the 3rd-from-end like the other rows above.
    add("HRSS Production", "saleable", lambda t: t.startswith("HRSS"),
        -1, "SALEABLE PRODUCTION HRSS Cum Actual")

    # ── 3.0 DESPATCHES ───────────────────────────────────────────────────────
    # 6-col layout: [OnDate?, Cum, Target, Rate, StockDate, Stock1st]
    add("Finished Carbon Steel Despatch", "despatches", lambda t: t.startswith("HRCS"),
        -5, "DESPATCHES HRCS Cum Actual")
    add("Total Saleable Steel Despatch", "despatches", lambda t: t.startswith("TOTAL"),
        -5, "DESPATCHES TOTAL Cum Actual")
    finished_carbon_val = add("Finished Carbon Steel", "despatches", lambda t: t.startswith("HRCS"),
                              -2, "DESPATCHES HRCS Stock As on Date")
    finished_total_val = add("Finished Total Steel", "despatches", lambda t: t.startswith("TOTAL"),
                             -2, "DESPATCHES TOTAL Stock As on Date")

    # Finished Stainless Steel = Finished Total Steel - Finished Carbon Steel
    if finished_total_val is not None and finished_carbon_val is not None:
        finished_ss_val = finished_total_val - finished_carbon_val
        prod_rows.append(_row("Finished Stainless Steel", finished_ss_val,
                              f"{cell_tag} · Finished Total Steel - Finished Carbon Steel",
                              "(computed)"))
    else:
        prod_rows.append(_row("Finished Stainless Steel", None,
                              f"{cell_tag} · Finished Total Steel - Finished Carbon Steel",
                              "(Finished Total Steel or Finished Carbon Steel missing)"))

    ok = sum(1 for r in prod_rows if r["status"] == "ok")
    print(f"[SSP PDF] {ok}/{len(prod_rows)} rows ok", flush=True, file=sys.stderr)

    if ok == 0:
        raise ValueError(
            "No values extracted. Verify this is an SSP DPR PDF with "
            "'SMS (SLAB)', 'HRM' and 'SALEABLE PRODUCTION ... TOTAL' rows."
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
