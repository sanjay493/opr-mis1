"""
DSP OMI PDF extractor (e.g. 'mis0526.pdf' — DSP monthly MIS report).

Production data comes from the 'PRODUCTION MONTHWISE' page (page 7 in the
May'26 file, but the page is FOUND BY ITS HEADING, not by number, so a page
shift in future reports does not break extraction).

Layout of that page:
    SL.            APR    MAY    TOTAL
    ITEM           2026   2026   2026-27
    4 HOT METAL    159581 153453 313034
One numeric column per FY month elapsed + a TOTAL column.  The requested
report month selects the column.  Values are tonnes → stored as '000T,
matching the Excel DSP extractor conventions (same item_name strings).

extract_preview() processes the PDF in three independent blocks to keep peak
memory bounded.  Each block opens, reads, and closes the PDF before the next
block starts:
  Block 1 — Production data      (PRODUCTION MONTHWISE page)
  Block 2 — Techno parameters    (MAJOR TECHNO, COKE OVENS, RMHP/SINTER,
                                   BLAST FURNACE, SMS, MILL pages)
  Block 3 — Special Steel grid   (SPECIAL STEEL PERFORMANCE page — table only)

extract_preview() returns rows for review — NO database writes.
"""
import gc
import re

PLANT = "DSP"

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# Default label maps — overridden at runtime from excel_cells_config.json ["dsp_pdf"]
_ITEM_MAP_DEFAULT = [
    ("nos per day",        "Oven Pushing(nos/d)",  False),
    ("sinter",             "Total Sinter",         True),
    ("sp 1",               "SP-1",                 True),
    ("sp 2",               "SP-2",                 True),
    ("hot metal",          "Hot Metal",            True),
    ("bf 2",               "BF#2",                 True),
    ("bf 3",               "BF#3",                 True),
    ("bf 4",               "BF#4",                 True),
    ("hm to asp",          "Hot Metal to ASP",     True),
    ("pig iron",           "Pig Iron",             True),
    ("crude steel",        "Total Crude Steel",    True),
    ("bottom pouring",     "BOTTOM_POURING_INGOT", True),
    ("concast steel",      "Total Caster",         True),
    ("cc billet",          "BILLET Caster",        True),
    ("cc bloom",           "Bloom Caster ",        True),   # trailing space matches DB
    ("brc bloom",          "BRC",                  True),
    ("brc round",          "Round Production",     True),
    ("merchant mill",      "MM",                   True),
    ("msm",                "MSM",                  True),
    ("wheel axle plant",   "WAP",                  True),
]
_SALEABLE_MAP_DEFAULT = [
    ("finished", "Finished Steel",  True),
    ("semis",    "Saleable Semis",  True),
    ("total",    "Saleable Steel",  True),
]


def _load_maps():
    """Load item maps from config; fall back to defaults if config absent."""
    try:
        from cells_loader import get_extractor_config
        cfg = get_extractor_config("dsp_pdf")
        raw_item = cfg.get("item_map")
        raw_sale = cfg.get("saleable_map")
        item_map = [tuple(r) for r in raw_item] if raw_item else _ITEM_MAP_DEFAULT
        sale_map = [tuple(r) for r in raw_sale] if raw_sale else _SALEABLE_MAP_DEFAULT
        return item_map, sale_map
    except Exception:
        return _ITEM_MAP_DEFAULT, _SALEABLE_MAP_DEFAULT




def _norm(s):
    s = re.sub(r'^\s*\d+\s+', '', str(s))          # leading serial number '4 '

    # Convert roman numerals to numbers before removing them
    # e.g., "i) BF" → "1 BF" → "1 bf"
    roman_map = {
        r'\bi\b': '1', r'\bii\b': '2', r'\biii\b': '3',
        r'\biv\b': '4', r'\bv\b': '5', r'\bvi\b': '6',
        r'\bvii\b': '7', r'\bviii\b': '8', r'\bix\b': '9', r'\bx\b': '10'
    }
    s = s.lower()
    for roman, num in roman_map.items():
        s = re.sub(roman, num, s)

    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    return s


def _num(tok):
    t = tok.replace(",", "")
    if re.fullmatch(r'-?\d+(\.\d+)?', t):
        return float(t)
    return None


def _month_header(lines):
    """Returns the month-column list from a header line like 'SL. APR MAY TOTAL'."""
    for ln in lines[:15]:
        toks = [t.upper().rstrip('.') for t in ln.split()]
        cols = [t for t in toks if t in _MONTHS]
        if cols and "TOTAL" in toks:
            return cols
    return None


def _find_month_column_index(lines, want_mon):
    """Find the exact column index (in split tokens) of the requested month.

    Returns: (month_index_in_header, total_columns_in_header)
    This helps identify if columns are shifted in the PDF.
    """
    for ln in lines[:15]:
        toks = [t.upper().rstrip('.') for t in ln.split()]
        cols = [t for t in toks if t in _MONTHS]
        if cols and "TOTAL" in toks and want_mon in cols:
            return cols.index(want_mon), len(cols)
    return None, None


# ---------------------------------------------------------------------------
# Pass 0: lightweight page index scan
# ---------------------------------------------------------------------------

# Each entry: section_key → (heading_keyword, optional_second_keyword)
_SECTION_HEADINGS = {
    'prod':   ("PRODUCTION MONTHWISE", None),
    'ss':     ("SPECIAL STEEL PERFORMANCE", "SECTION"),
    'mm':     ("MERCHANT MILL & MEDIUM STRUCTURAL MILL", None),
    'wa':     ("WHEEL & AXLE PLANT", "FORGING AVAIL"),
    'major':  ("MAJOR TECHNO", "KG/THM"),
    'coke':   ("COKE OVENS & COAL CHEMICALS", None),
    'sint':   ("RMHP & SINTER PLANT", None),
    'sms':    ("STEEL MELTING SHOP", "BOF SHOP"),
    'bf_cdi': ("BLAST FURNACE", "CDI RATE"),
}


def _scan_page_index(file_path: str, max_pages: int = 120) -> dict:
    """Single lightweight pass: return {section_key: 0-based_page_index}.

    Reads one page at a time; page text is not retained between iterations so
    memory stays flat throughout the scan.
    """
    import pdfplumber
    import sys
    found = {}
    remaining = set(_SECTION_HEADINGS.keys())

    try:
        pdf_obj = pdfplumber.open(file_path)
    except Exception as exc:
        raise ValueError(f"Cannot open PDF: {exc}") from exc

    try:
        total = len(pdf_obj.pages)
        print(f"[DSP PDF] scan: {total} pages total, looking for {len(remaining)} sections",
              flush=True, file=sys.stderr)
        for i, pg in enumerate(pdf_obj.pages[:max_pages]):
            if not remaining:
                break
            try:
                txt = pg.extract_text() or ""
            except Exception as exc:
                print(f"[DSP PDF] scan: page {i+1} extract_text failed ({exc}), skipping",
                      flush=True, file=sys.stderr)
                continue

            up    = txt.upper()
            lines = txt.splitlines() if 'prod' in remaining else []

            done = set()
            for key in remaining:
                h1, h2 = _SECTION_HEADINGS[key]
                if h1 not in up:
                    continue
                if h2 and h2 not in up:
                    continue
                if key == 'prod' and not _month_header(lines):
                    continue
                found[key] = i
                done.add(key)
                print(f"[DSP PDF] scan: found '{key}' on page {i+1}", flush=True, file=sys.stderr)
            remaining -= done
    finally:
        pdf_obj.close()

    if remaining:
        print(f"[DSP PDF] scan: sections NOT found: {remaining}", flush=True, file=sys.stderr)
    return found


# ---------------------------------------------------------------------------
# Shared low-level helpers
# ---------------------------------------------------------------------------

def _period_month(label):
    """'April 26' / "May'26" → 'APR'/'MAY'; None for 'Cum. 2026-27' etc."""
    m = re.match(r"\s*([A-Za-z]+)", label or "")
    if not m:
        return None
    tok = m.group(1).upper()[:3]
    return tok if tok in _MONTHS else None


def _parse_te_nums(line):
    """Strip 'Best Achieved (YY-YY)' token, return list of floats.

    '--' (furnace-not-operating marker) is returned as None so that column
    alignment is preserved.
    """
    line2 = re.sub(r'\d[\d,.]*\s*\(\d{2}-\d{2}\)', '', line)
    result = []
    for tok in re.findall(r'(?<!\d)--(?!\d)|-?\d+(?:,\d+)*(?:\.\d+)?', line2):
        if tok == '--':
            result.append(None)
        else:
            result.append(float(tok.replace(',', '')))
    return result


def _te_values(nums, month_diff=0, offset=4):
    """Return (actual, cum) from right-aligned numeric list.

    month_diff = how many months behind the PDF's last month the requested month
    is (0 = current/last month, 1 = one month back, etc.).

    offset = right-alignment offset for the report-month column:
      4 for standard pages (COKE, SINTER, BF, SMS, MILL):
        [...months...] | want_mon | Cum | CPLY_mon | CPLY_FY
      3 for the MAJOR TECHNO page (has an extra FY-prev actual column):
        [Norm_curr, FY_prev, ...months...] | want_mon | Cum | CPLY_cum

    Cumulative (nums[-(offset-1)]) is only valid when month_diff == 0.
    """
    needed = offset + month_diff
    if len(nums) < needed:
        return None, None
    actual = nums[-offset - month_diff]
    cum = nums[-(offset - 1)] if month_diff == 0 else None
    return actual, cum


def _find_line_start(text_upper, marker):
    """Return char offset of marker only when it appears as a full line."""
    for m in re.finditer(re.escape(marker), text_upper):
        pos = m.start()
        before = text_upper[pos - 1] if pos > 0 else '\n'
        if before == '\n':
            return pos
    return -1


def _slice_text(text, start_marker, end_markers):
    """Lines between start_marker (whole-line) and first end_marker (exclusive)."""
    up = text.upper()
    s = _find_line_start(up, start_marker.upper())
    if s == -1:
        return []
    end = len(text)
    for em in end_markers:
        pos = _find_line_start(up, em.upper())
        if pos != -1 and pos > s and pos < end:
            end = pos
    return text[s:end].splitlines()


# ---------------------------------------------------------------------------
# Techno param definitions
# ---------------------------------------------------------------------------

_MM_MSM_PARAMS = {
    "Merchant Mill": [
        ("yield",            "Yield",           "%",       10),
        ("rolling rate",     "Rolling Rate",    "T/Hr.",   11),
        ("mill availability","Mill Availability","%",      12),
        ("on available",     "Mill Utilisation","%Avl.",   13),
        ("on ich",           "On ICH",          "%",       14),
        ("specific heat",    "Specific Heat",   "M.Cal/T", 15),
        ("specific power",   "Specific Power",  "KWH/T",   16),
    ],
    "MSM": [
        ("yield",            "Yield",           "%",       20),
        ("rolling rate",     "Rolling Rate",    "T/Utl.Hr.",21),
        ("mill availability","Mill Availability","%",      22),
        ("on available",     "Mill Utilisation","%Avl.",   23),
        ("on ich",           "On ICH",          "%",       24),
        ("specific heat",    "Specific Heat",   "M.Cal/T", 25),
        ("specific power",   "Specific Power",  "KWH/T",   26),
    ],
}

_WA_PARAMS = {
    "Wheel Plant": [
        ("finished wheel",   "Finished Wheel over Ingot/Round", "%",       30),
        ("rolling rate",     "Rolling Rate",                    "Nos./Hr.", 31),
        ("forging avail",    "Forging Availability",            "%",        32),
        ("on available",     "Forging Utilisation",             "%Avl.",    33),
        ("on ich",           "On ICH",                         "%",        34),
        ("specific heat",    "Specific Heat",                   "M.Cal/T",  35),
        ("specific power",   "Specific Power",                  "KWH/T",    36),
    ],
    "Axle Plant": [
        ("yield over",       "Yield over good Bloom",  "%",       40),
        ("forging rate",     "Forging Rate",           "Nos./Hr.", 41),
        ("forging avail",    "Forging Availability",   "%",        42),
        ("on available",     "Forging Utilisation",    "%Avl.",    43),
        ("on ich",           "On ICH",                 "%",        44),
        ("specific heat",    "Specific Heat",          "M.Cal/T",  45),
        ("specific power",   "Specific Power",         "KWH/T",    46),
    ],
}

_MAJOR_PAGE_DEFS = [
    ("coke rate",                "MAJOR",       "Coke Rate",                        "DSP",     "Kg/THM",    21),
    ("cdi rate",                 "MAJOR",       "CDI Rate",                         "DSP",     "Kg/THM",    41),
    ("nut coke rate",            "MAJOR",       "Nut Coke Consumption",             "DSP",     "Kg/THM",    31),
    ("fuel rate",                "MAJOR",       "Fuel Rate",                        "DSP",     "Kg/THM",    51),
    ("sinter in burden",         "MAJOR",       "Sinter in Burden",                 "DSP",     "%",         61),
    ("bf productivity",          "MAJOR",       "BF Productivity (Working Volume)", "DSP",     "T/m³/day",  81),
    ("total metallic input",     "MAJOR",       "TMI",                              "DSP SMS", "Kg/TCS",   112),
    ("gross energy consumption", "MAJOR",       "Specific Energy Consumption",      "DSP",     "G.Cal/TCS",121),
    ("bof slag utilisation",     "COKE_SINTER", "BOF Slag Utilisation",             "DSP",     "%",         41),
    ("loss at skip",             "IRON_MAKING", "Coke Screen Loss",                 "DSP Plant Shop", "%",  31),
]

_SMS_PAGE_DEFS = [
    ("gross h.metal",  "MAJOR", "Hot Metal Consumption", "DSP SMS", "Kg/TCS",  92),
    ("total scrap",    "MAJOR", "Scrap Consumption",     "DSP SMS", "Kg/TCS", 102),
]

_COKE_PAGE_DEFS = [
    ("b.f. coke yield", "COKE_SINTER", "BF Coke Yield",  "DSP", "%",              2),
    ("specific heat",   "COKE_SINTER", "Sp. Heat Cons.", "DSP", "000 K.Cal/TDC", 11),
    ("crude tar",       "COKE_SINTER", "Coal Tar Yield", "DSP", "kg/TDC",        21),
]


# ---------------------------------------------------------------------------
# Techno parsing helpers (work on plain text, no pdf object needed)
# ---------------------------------------------------------------------------

def _parse_params_from_lines(lines, section, param_list, page_no, want_mon, yy, month_diff=0):
    rows = []
    for keyword, label, unit, sort in param_list:
        for ln in lines:
            if keyword in ln.lower():
                nums = _parse_te_nums(ln)
                actual, cum = _te_values(nums, month_diff)
                if actual is not None:
                    rows.append({
                        "group_code": "MILL_DSP",
                        "section":    section,
                        "parameter":  label,
                        "unit":       unit,
                        "sort_order": sort,
                        "actual":     actual,
                        "cum_actual": cum,
                        "cell":       f"PDF p{page_no} · {want_mon}'{yy}",
                        "found_via":  f"DSP {section}",
                        "status":     "ok",
                    })
                break
    return rows


def _parse_general_params(lines, param_defs, page_no, want_mon, yy, month_diff=0, offset=4):
    rows = []
    for keyword, group_code, section, row_label, unit, sort in param_defs:
        for ln in lines:
            if keyword in ln.lower():
                nums = _parse_te_nums(ln)
                actual, cum = _te_values(nums, month_diff, offset)
                if actual is not None:
                    rows.append({
                        "group_code": group_code,
                        "section":    section,
                        "parameter":  row_label,
                        "unit":       unit,
                        "sort_order": sort,
                        "actual":     actual,
                        "cum_actual": cum,
                        "cell":       f"PDF p{page_no} · {want_mon}'{yy}",
                        "found_via":  f"DSP {section}",
                        "status":     "ok",
                    })
                break
    return rows


def _parse_special_steel_table(tbl, page_no, want_mon, yy):
    """Parse an already-extracted pdfplumber table into special_steel_orders rows."""
    period_row = None
    for ri, row in enumerate(tbl[:6]):
        if any(_period_month(c) for c in row):
            period_row = ri
            break
    if period_row is None:
        return []

    periods = [(_period_month(c), ci)
               for ci, c in enumerate(tbl[period_row]) if (c or "").strip()]
    start = next((ci for mon, ci in periods if mon == want_mon), None)
    if start is None:
        found = ", ".join((tbl[period_row][ci] or "").strip() for _, ci in periods)
        raise ValueError(
            f"Special Steel page: month {want_mon}'{yy} not present "
            f"(period columns: {found}).")
    next_start = min((ci for _, ci in periods if ci > start),
                     default=len(tbl[period_row]))

    sub = [(c or "").strip().upper() for c in tbl[period_row + 1]] \
        if period_row + 1 < len(tbl) else []

    def _col(name, default):
        for ci in range(start, next_start):
            if ci < len(sub) and sub[ci].startswith(name):
                return ci
        return default

    c_ord, c_pro, c_des = _col("ORDER", start), _col("PRODN", start + 1), _col("DESP", start + 2)

    rows = []
    cur_product = cur_grade = ""
    for row in tbl[period_row + 2:]:
        cells = ["" if c is None else str(c).strip() for c in row]
        if len(cells) <= max(c_ord, c_pro, c_des):
            continue
        col0, col1, col2 = cells[0], cells[1], cells[2]
        label0 = col0 or col1
        is_total = bool(label0) and label0.upper().startswith("TOTAL")
        if not is_total:
            if col0:
                cur_product = col0
            if col1:
                cur_grade = col1

        order, prodn, desp = (_num(cells[ci]) for ci in (c_ord, c_pro, c_des))
        if order is None and prodn is None and desp is None:
            continue

        rows.append({
            "product":         "" if is_total else cur_product,
            "quality_grade":   label0 if is_total else cur_grade,
            "section":         "" if is_total else col2,
            "sort_order":      len(rows) + 1,
            "order_qty":       order,
            "prodn":           prodn,
            "actual_despatch": desp,
            "unit":            "T",
            "cell":            f"PDF p{page_no} · {want_mon}'{yy} cols",
            "status":          "total" if is_total else "ok",
        })
    return rows


# ---------------------------------------------------------------------------
# Block 1: Production
# ---------------------------------------------------------------------------

def _block_production(file_path: str, prod_page_idx: int,
                      want_mon: str, y: int, yy: str,
                      alias_lookup: dict, column_shift: int = 0):
    """Open PDF, read only the production page, close, parse and return rows.

    Args:
        column_shift: Adjust data column by this amount (-1 for Sep'25 left-shifted)
    """
    import pdfplumber
    _ITEM_MAP, _SALEABLE_MAP = _load_maps()

    with pdfplumber.open(file_path) as pdf:
        text = pdf.pages[prod_page_idx].extract_text() or ""

    page_no = prod_page_idx + 1
    lines   = text.splitlines()

    month_cols = _month_header(lines)
    if not month_cols:
        raise ValueError("Month header row not found on the production page.")
    if want_mon not in month_cols:
        raise ValueError(
            f"Report month {want_mon}'{yy} not present in this PDF "
            f"(columns found: {', '.join(month_cols)}).")

    m_idx      = month_cols.index(want_mon)
    month_diff = len(month_cols) - 1 - m_idx
    n_cols     = len(month_cols) + 1   # data months + TOTAL column

    # AUTO-DETECT column position in header row to find any shifts
    # This handles PDFs where the month columns appear at different token positions
    header_col_index = None
    header_row_text = None
    for ln in lines[:15]:
        toks = [t.upper().rstrip('.') for t in ln.split()]
        if month_cols[0] in toks:
            header_col_index = toks.index(month_cols[0])
            header_row_text = toks
            break

    # If header_col_index != 0, we have prefix columns (SL., i), ii), etc.)
    # This offset should be applied to m_idx when extracting data
    header_col_offset = (header_col_index or 0)
    if header_col_offset > 0 and column_shift == 0:
        # Auto-adjust if not manually set
        column_shift = -header_col_offset
        import sys
        print(f"[INFO] Auto-detected column shift: {column_shift} (header starts at col {header_col_index})",
              file=sys.stderr)

    # DEBUG: Print header and month info
    import sys
    print(f"\n[DEBUG] ====== PDF COLUMN STRUCTURE ======", file=sys.stderr)
    print(f"[DEBUG] Month columns found: {month_cols}", file=sys.stderr)
    print(f"[DEBUG] Want month: {want_mon} (index in month_cols: {m_idx})", file=sys.stderr)
    print(f"[DEBUG] Header row tokens: {header_row_text}", file=sys.stderr)
    print(f"[DEBUG] First month at token position: {header_col_index}", file=sys.stderr)
    print(f"[DEBUG] Applied column_shift: {column_shift}", file=sys.stderr)
    print(f"[DEBUG] Data will be extracted from index: {m_idx + column_shift}", file=sys.stderr)
    print(f"[DEBUG] ====================================\n", file=sys.stderr)

    rows = []
    in_saleable = False
    for ln in lines:
        if "SALEABLE STEEL" in ln.upper():
            in_saleable = True
            continue

        toks = ln.split()
        nums = []
        for t in reversed(toks):
            v = _num(t)
            if v is None:
                break
            nums.insert(0, v)
        if not nums:
            continue
        n_raw = len(nums)           # count BEFORE trimming for label recovery
        if n_raw > n_cols:
            nums = nums[n_raw - n_cols:]
        label_toks = toks[:len(toks) - n_raw]   # use original count, not trimmed
        label = _norm(" ".join(label_toks))
        if not label:
            continue

        # Apply column shift for layout variations (e.g., Sep'25)
        # column_shift may be auto-detected or manually set
        data_col_idx = m_idx + column_shift
        if len(nums) <= data_col_idx or data_col_idx < 0:
            continue
        val = nums[data_col_idx]

        # DEBUG: Print row data for first few items
        import sys
        if not hasattr(_block_production, '_row_debug_count'):
            _block_production._row_debug_count = 0
        if _block_production._row_debug_count < 5:  # First 5 items
            print(f"[DEBUG] Row: '{label}' → Raw tokens: {toks}", file=sys.stderr)
            print(f"[DEBUG]   → All extracted numbers: {nums}", file=sys.stderr)
            print(f"[DEBUG]   → Extracting from index {data_col_idx} (m_idx={m_idx} + column_shift={column_shift})", file=sys.stderr)
            print(f"[DEBUG]   → Value: {val} (mapped to: {label})\n", file=sys.stderr)
            _block_production._row_debug_count += 1

        item, convert = None, True
        if label in alias_lookup:
            item, convert = alias_lookup[label]
        if item is None:
            table = _SALEABLE_MAP if in_saleable else _ITEM_MAP
            for alias, name, conv in table:
                if label == alias:
                    item, convert = name, conv
                    break
        if item is None and in_saleable:
            for alias, name, conv in _ITEM_MAP:
                if label == alias:
                    item, convert = name, conv
                    break

        stored = round(val / 1000.0, 3) if (convert and item) else val
        rows.append({
            "item_name": item if item else f"(unmapped) {label}",
            "value":     stored if item else val,
            "unit":      "nos/d" if (item and not convert) else "'000T" if item else "T",
            "cell":      f"PDF p{page_no} · {want_mon}'{yy} col",
            "pdf_label": " ".join(label_toks),
            "status":    "ok" if item else "unmapped",
        })

    return rows, page_no, month_diff


# ---------------------------------------------------------------------------
# Block 2: Techno parameters
# ---------------------------------------------------------------------------

def _block_techno(file_path: str, page_index: dict,
                  want_mon: str, yy: str, month_diff: int) -> list:
    """Open PDF, read only the techno pages (by index), close, parse rows."""
    import pdfplumber

    techno_keys = ('major', 'sms', 'coke', 'sint', 'bf_cdi', 'mm', 'wa')
    needed_idxs = {page_index[k] for k in techno_keys if k in page_index}

    if not needed_idxs:
        return []

    # Read only the specific pages we need; build a sparse page_texts list
    # (all other positions are empty strings so _find_page_by_heading still works
    # by index without touching unloaded pages).
    with pdfplumber.open(file_path) as pdf:
        n_pages    = len(pdf.pages)
        page_texts = [""] * n_pages
        for idx in needed_idxs:
            if 0 <= idx < n_pages:
                page_texts[idx] = pdf.pages[idx].extract_text() or ""

    rows = []

    # ── Mill techno (MM/MSM and Wheel & Axle) ────────────────────────────
    mm_idx = page_index.get('mm')
    if mm_idx is not None:
        text = page_texts[mm_idx]
        pno  = mm_idx + 1
        mm_lines  = _slice_text(text, "TE PARAMETERS - MERCHANT MILL",
                                 ["PRODUCTION - MSM", "TE PARAMETERS - MSM"])
        rows.extend(_parse_params_from_lines(
            mm_lines, "Merchant Mill", _MM_MSM_PARAMS["Merchant Mill"],
            pno, want_mon, yy, month_diff))
        msm_lines = _slice_text(text, "TE PARAMETERS - MSM", [])
        rows.extend(_parse_params_from_lines(
            msm_lines, "MSM", _MM_MSM_PARAMS["MSM"],
            pno, want_mon, yy, month_diff))

    wa_idx = page_index.get('wa')
    if wa_idx is not None:
        text = page_texts[wa_idx]
        pno  = wa_idx + 1
        wp_lines = _slice_text(text, "WHEEL PLANT", ["AXLE PLANT"])
        rows.extend(_parse_params_from_lines(
            wp_lines, "Wheel Plant", _WA_PARAMS["Wheel Plant"],
            pno, want_mon, yy, month_diff))
        ap_lines = _slice_text(text, "AXLE PLANT", [])
        rows.extend(_parse_params_from_lines(
            ap_lines, "Axle Plant", _WA_PARAMS["Axle Plant"],
            pno, want_mon, yy, month_diff))

    # ── Major techno + SMS ────────────────────────────────────────────────
    major_idx = page_index.get('major')
    if major_idx is not None:
        lines = page_texts[major_idx].splitlines()
        rows.extend(_parse_general_params(
            lines, _MAJOR_PAGE_DEFS, major_idx + 1,
            want_mon, yy, month_diff, offset=3))

    sms_idx = page_index.get('sms')
    if sms_idx is not None:
        lines = page_texts[sms_idx].splitlines()
        rows.extend(_parse_general_params(
            lines, _SMS_PAGE_DEFS, sms_idx + 1,
            want_mon, yy, month_diff, offset=4))

    # ── Coke & Sinter ────────────────────────────────────────────────────
    coke_idx = page_index.get('coke')
    if coke_idx is not None:
        lines = page_texts[coke_idx].splitlines()
        rows.extend(_parse_general_params(
            lines, _COKE_PAGE_DEFS, coke_idx + 1,
            want_mon, yy, month_diff, offset=4))

    sint_idx = page_index.get('sint')
    if sint_idx is not None:
        sint_text = page_texts[sint_idx]
        sint_pno  = sint_idx + 1
        for label, marker, stop in [("DSP SP-1", "OLD MACHINE", ["NEW MACHINE"]),
                                     ("DSP SP-2", "NEW MACHINE", [])]:
            for ln in _slice_text(sint_text, marker, stop):
                if "productivity" in ln.lower():
                    nums = _parse_te_nums(ln)
                    actual, cum = _te_values(nums, month_diff, offset=4)
                    if actual is not None:
                        rows.append({
                            "group_code": "COKE_SINTER",
                            "section":    "Sinter Productivity",
                            "parameter":  label,
                            "unit":       "T/m²/hr",
                            "sort_order": 31 if label == "DSP SP-1" else 32,
                            "actual":     actual,
                            "cum_actual": cum,
                            "cell":       f"PDF p{sint_pno} · {want_mon}'{yy}",
                            "found_via":  f"DSP Sinter {label}",
                            "status":     "ok",
                        })
                    break

    # ── BF furnace-wise CDI ───────────────────────────────────────────────
    bf_idx = page_index.get('bf_cdi')
    if bf_idx is not None:
        bf_text = page_texts[bf_idx]
        bf_pno  = bf_idx + 1
        cdi_lines = _slice_text(bf_text, "CDI RATE", ["FUEL RATE", "SINTER IN BURDEN"])
        _fce_markers = ("furnace-ii", "furnace-iii", "furnace-iv")
        for furnace_marker, row_label, sort in [
            ("furnace-ii",  "DSP BF-2", 12),
            ("furnace-iii", "DSP BF-3", 13),
            ("furnace-iv",  "DSP BF-4", 14),
        ]:
            for ln in cdi_lines:
                if furnace_marker in ln.lower():
                    nums = _parse_te_nums(ln)
                    actual, cum = _te_values(nums, month_diff, offset=4)
                    if actual is not None:
                        rows.append({
                            "group_code": "IRON_MAKING",
                            "section":    "CDI",
                            "parameter":  row_label,
                            "unit":       "Kg/THM",
                            "sort_order": sort,
                            "actual":     actual,
                            "cum_actual": cum,
                            "cell":       f"PDF p{bf_pno} · {want_mon}'{yy}",
                            "found_via":  f"DSP BF CDI {row_label}",
                            "status":     "ok",
                        })
                    break
        # Shop-level CDI average: first numeric line not belonging to a specific furnace
        for ln in cdi_lines:
            if not any(m in ln.lower() for m in _fce_markers):
                nums = _parse_te_nums(ln)
                actual, cum = _te_values(nums, month_diff, offset=4)
                if actual is not None:
                    rows.append({
                        "group_code": "IRON_MAKING",
                        "section":    "CDI",
                        "parameter":  "DSP Plant Shop",
                        "unit":       "Kg/THM",
                        "sort_order": 11,
                        "actual":     actual,
                        "cum_actual": cum,
                        "cell":       f"PDF p{bf_pno} · {want_mon}'{yy}",
                        "found_via":  "DSP BF CDI shop avg",
                        "status":     "ok",
                    })
                    break

    return rows


# ---------------------------------------------------------------------------
# Block 3: Special Steel
# ---------------------------------------------------------------------------

def _block_special_steel(file_path: str, ss_page_idx,
                          want_mon: str, yy: str,
                          timeout_s: float = 60.0):
    """Open PDF, extract the table from the Special Steel page only, close, parse.

    extract_table() can hang on complex tables so it runs in a worker thread
    with a hard timeout.  Returns (rows, page_no, note).
    """
    import pdfplumber
    import concurrent.futures as _cf
    import sys

    if ss_page_idx is None:
        return [], None, "Special Steel page not found in PDF."

    page_no = ss_page_idx + 1

    def _do_extract():
        with pdfplumber.open(file_path) as _pdf:
            return _pdf.pages[ss_page_idx].extract_table()

    try:
        with _cf.ThreadPoolExecutor(max_workers=1) as _pool:
            fut = _pool.submit(_do_extract)
            try:
                tbl = fut.result(timeout=timeout_s)
            except _cf.TimeoutError:
                msg = (f"Special Steel table extraction timed out "
                       f"({timeout_s:.0f}s limit) — production data still saved.")
                print(f"[DSP PDF] Block 3 TIMEOUT: {msg}", flush=True, file=sys.stderr)
                return [], page_no, msg

        if not tbl or len(tbl) < 5 or len(tbl[0]) < 6:
            return [], page_no, "Special Steel table too small to parse."

        rows = _parse_special_steel_table(tbl, page_no, want_mon, yy)
        return rows, page_no, ""
    except ValueError:
        raise
    except Exception as exc:
        return [], page_no, f"Special Steel extraction skipped: {exc}"


# ---------------------------------------------------------------------------
# DSP Flash.pdf — closing stock extraction
# ---------------------------------------------------------------------------

def _is_flash_pdf(file_path: str) -> bool:
    """Return True if the file is a DSP Flash daily/monthly report."""
    try:
        import pdfplumber as _plumb
        with _plumb.open(file_path) as _pdf:
            text = _pdf.pages[0].extract_text() or ""
            return "In-process Stock" in text and "Sal.Steel Stock" in text
    except Exception:
        return False


def _extract_flash_stock(file_path: str, report_month: str) -> dict:
    """Parse Flash.pdf and return raw stock values (Tonnes).

    Layout (single 27-row × 14-col table):
      row with "CC Billet" in col[7]  → In-process col[9], Sal.Steel col[12]
      row with "Saleable Semis" in col[7] → Total col[13]
    """
    import pdfplumber as _plumb

    with _plumb.open(file_path) as pdf:
        page   = pdf.pages[0]
        text   = page.extract_text() or ""
        tables = page.extract_tables()

    # Date from top of page e.g. "20.06.2026"
    date_m = re.search(r'\b(\d{1,2})\.(\d{2})\.(\d{4})\b', text)
    detected_date  = None
    detected_month = None
    if date_m:
        dd, mo, yr = date_m.group(1), date_m.group(2), date_m.group(3)
        detected_date  = f"{dd}.{mo}.{yr}"
        detected_month = f"{yr}-{mo}"

    inprocess_total = None
    sal_semis_total = None
    finished_total  = None
    pig_iron        = None

    def _num(s):
        s = str(s or "").strip().replace(',', '')
        try:
            return float(s) if re.fullmatch(r'\d+(\.\d+)?', s) else None
        except (ValueError, TypeError):
            return None

    for table in tables:
        for row in table:
            if not row or len(row) < 8:
                continue

            col7 = str(row[7] or "")

            # ── In-process / Sal.Steel Stock block ──────────────────────────
            # Items in col[7], In-process values in col[9], Sal.Steel in col[12]
            if "CC Billet" in col7:
                inp_str = str(row[9] if len(row) > 9 else "") or ""
                vals_inp = [_num(v) for v in inp_str.split('\n')]
                vals_inp = [v for v in vals_inp if v is not None]
                if vals_inp:
                    inprocess_total = sum(vals_inp)

                # Pig Iron* aligned by position in col[7] items vs col[12] values
                sal_str  = str(row[12] if len(row) > 12 else "") or ""
                sal_vals = [v.strip() for v in sal_str.split('\n') if v.strip()]
                items    = [v.strip() for v in col7.split('\n') if v.strip()]
                for j, item in enumerate(items):
                    if 'Pig Iron' in item and j < len(sal_vals):
                        n = _num(sal_vals[j])
                        if n is not None:
                            pig_iron = n
                        break

            # ── Movable / Non-Movable / Total block ─────────────────────────
            # Items in col[7], Total values in col[13]
            if "Saleable Semis" in col7:
                total_str  = str(row[13] if len(row) > 13 else "") or ""
                total_vals = [v.strip() for v in total_str.split('\n') if v.strip()]
                items      = [v.strip() for v in col7.split('\n') if v.strip()]
                for j, item in enumerate(items):
                    if j >= len(total_vals):
                        break
                    if 'Saleable Semis' in item:
                        n = _num(total_vals[j])
                        if n is not None:
                            sal_semis_total = n
                    elif item == 'Finished':
                        n = _num(total_vals[j])
                        if n is not None:
                            finished_total = n

    month_mismatch = bool(
        detected_month and report_month and detected_month != report_month
    )
    return {
        "inprocess":      inprocess_total,
        "for_sale":       sal_semis_total,
        "finished":       finished_total,
        "pig_iron":       pig_iron,
        "detected_date":  detected_date,
        "detected_month": detected_month,
        "month_mismatch": month_mismatch,
    }


def extract_preview_flash(file_path: str, report_month: str) -> dict:
    """Preview DSP Flash.pdf closing stock for stock_table.

    Values stored in '000T (raw Tonnes ÷ 1000, 3 d.p.).
    stock_month = next month of report_month (closing = opening of next month).
    """
    raw = _extract_flash_stock(file_path, report_month)

    def _t(v):
        return round(v / 1000, 3) if v is not None else None

    y, m = int(report_month[:4]), int(report_month[5:7])
    stock_month = f"{y+1 if m == 12 else y}-{1 if m == 12 else m+1:02d}"

    stock_rows = [
        {
            "plant": "DSP", "item_type": "BLOOM/BILLETS", "stock_type": "INPROCESS",
            "stock_month": stock_month, "value": _t(raw["inprocess"]),
            "formula": "Sum of In-process Stock column (CC Billet + CC Bloom + BRC Bloom + ...)",
            "status": "ok" if raw["inprocess"] is not None else "skip",
        },
        {
            "plant": "DSP", "item_type": "BLOOM/BILLETS", "stock_type": "FOR SALE",
            "stock_month": stock_month, "value": _t(raw["for_sale"]),
            "formula": "Saleable Semis → Total column",
            "status": "ok" if raw["for_sale"] is not None else "skip",
        },
        {
            "plant": "DSP", "item_type": "FINISHED STEEL", "stock_type": "",
            "stock_month": stock_month, "value": _t(raw["finished"]),
            "formula": "Finished → Total column",
            "status": "ok" if raw["finished"] is not None else "skip",
        },
        {
            "plant": "DSP", "item_type": "PIG IRON", "stock_type": "",
            "stock_month": stock_month, "value": _t(raw["pig_iron"]),
            "formula": "Pig Iron* → Sal.Steel Stock column",
            "status": "ok" if raw["pig_iron"] is not None else "skip",
        },
    ]

    ok_n = sum(1 for r in stock_rows if r["status"] == "ok")
    import sys
    print(f"[DSP Flash] stock extraction: {ok_n}/4 ok  stock_month={stock_month}  "
          f"detected_date={raw['detected_date']}", flush=True, file=sys.stderr)

    return {
        "source_type":        "DSP Flash Report (Closing Stock)",
        "month":              report_month,
        "plant":              "DSP",
        "workbook_sheets":    ["Flash.pdf page 1"],
        "month_mismatch":     raw["month_mismatch"],
        "selected_month":     report_month,
        "detected_date":      raw.get("detected_date", ""),
        "detected_month":     raw.get("detected_month", ""),
        "production_rows":    [],
        "techno_rows":        [],
        "techno_param_rows":  [],
        "special_steel_rows": [],
        "stock_rows":         stock_rows,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_preview(file_path: str, report_month: str, aliases: dict = None,
                    block: str = 'all', column_shift: int = 0) -> dict:
    """Extract DSP data from the OMI PDF or Flash.pdf.

    Args:
        block: which sections to process ('all', 'production', 'techno', 'special_steel', 'stock')
        aliases: user-saved mapping {pdf_label: (item_name, convert_to_000T)}
        column_shift: adjust data column position (-1 for Sep'25 left-shifted layout)

    No database writes — preview only.
    """
    if block == 'stock':
        return extract_preview_flash(file_path, report_month)

    import sys
    alias_lookup = {}
    for raw_label, (a_item, a_conv) in (aliases or {}).items():
        alias_lookup[_norm(raw_label)] = (a_item, bool(a_conv))

    y, m    = int(report_month[:4]), int(report_month[5:7])
    want_mon = _MONTHS[m - 1]
    yy       = str(y)[2:]

    file_kb = 0
    try:
        import os as _os
        file_kb = _os.path.getsize(file_path) // 1024
    except Exception:
        pass
    print(f"[DSP PDF] extract_preview: file={file_kb} KB  month={want_mon}'{yy}",
          flush=True, file=sys.stderr)

    # ── Pass 0: page index scan ───────────────────────────────────────────
    print("[DSP PDF] Pass 0: scanning page index ...", flush=True, file=sys.stderr)
    page_index = _scan_page_index(file_path)
    gc.collect()
    print(f"[DSP PDF] Pass 0 done. Found pages: {page_index}", flush=True, file=sys.stderr)

    run_prod = block in ('all', 'production')
    run_tech = block in ('all', 'techno')
    run_ss   = block in ('all', 'special_steel')

    if run_prod and 'prod' not in page_index:
        raise ValueError(
            "No 'PRODUCTION MONTHWISE' page found in the PDF. "
            "Is this the DSP monthly MIS report?")

    # ── Block 1: Production ───────────────────────────────────────────────
    prod_rows, prod_page_no, month_diff = [], 0, 0
    if run_prod:
        print(f"[DSP PDF] Block 1: production (page {page_index['prod']+1}) ...",
              flush=True, file=sys.stderr)
        prod_rows, prod_page_no, month_diff = _block_production(
            file_path, page_index['prod'], want_mon, y, yy, alias_lookup, column_shift=column_shift)
        gc.collect()
        ok_count = sum(1 for r in prod_rows if r["status"] == "ok")
        print(f"[DSP PDF] Block 1 done: {ok_count}/{len(prod_rows)} rows ok",
              flush=True, file=sys.stderr)
        if not any(r["status"] == "ok" for r in prod_rows):
            raise ValueError("Production page found but no known items matched.")

    # ── Block 2: Techno parameters ────────────────────────────────────────
    techno_rows = []
    if run_tech:
        # need month_diff — derive from production page if we didn't run block 1
        if not run_prod and 'prod' in page_index:
            try:
                import pdfplumber as _plumb
                with _plumb.open(file_path) as _pdf:
                    _txt = _pdf.pages[page_index['prod']].extract_text() or ""
                _mc = _month_header(_txt.splitlines())
                if _mc and want_mon in _mc:
                    month_diff = len(_mc) - 1 - _mc.index(want_mon)
            except Exception:
                month_diff = 0

        print("[DSP PDF] Block 2: techno parameters ...", flush=True, file=sys.stderr)
        try:
            techno_rows = _block_techno(file_path, page_index, want_mon, yy, month_diff)
            print(f"[DSP PDF] Block 2 done: {len(techno_rows)} techno rows",
                  flush=True, file=sys.stderr)
        except Exception as exc:
            techno_rows = []
            print(f"[DSP PDF] Block 2 FAILED: {type(exc).__name__}: {exc}",
                  flush=True, file=sys.stderr)
            import traceback as _tb
            _tb.print_exc(file=sys.stderr)
        gc.collect()

    # ── Block 3: Special Steel ────────────────────────────────────────────
    ss_rows, ss_page, ss_note = [], None, ""
    if run_ss:
        print("[DSP PDF] Block 3: special steel ...", flush=True, file=sys.stderr)
        ss_rows, ss_page, ss_note = _block_special_steel(
            file_path, page_index.get('ss'), want_mon, yy)
        print(f"[DSP PDF] Block 3 done: {len(ss_rows)} rows, note={ss_note!r}",
              flush=True, file=sys.stderr)
        gc.collect()

    # ── Build result ──────────────────────────────────────────────────────
    sheets = f"PDF page {prod_page_no} (PRODUCTION MONTHWISE)"
    workbook_sheets = [f"PDF page {prod_page_no}"]
    if ss_page:
        sheets += f" + page {ss_page} (SPECIAL STEEL)"
        workbook_sheets.append(f"PDF page {ss_page}")

    return {
        "plant":               PLANT,
        "month":               report_month,
        "source_type":         "DSP OMI PDF Report",
        "sheets":              sheets,
        "workbook_sheets":     workbook_sheets,
        "production_rows":     prod_rows,
        "special_steel_rows":  ss_rows,
        "special_steel_note":  ss_note,
        "techno_rows":         [],
        "techno_param_rows":   techno_rows,
    }
