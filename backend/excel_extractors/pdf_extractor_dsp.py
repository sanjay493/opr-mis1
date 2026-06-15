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

# (normalized pdf label → (item_name in production_table, convert_to_000T))
# Labels are matched after stripping serial prefixes ('3 ', 'i) ', 'iii) ').
_ITEM_MAP = [
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
# inside the 'SALEABLE STEEL' block only:
_SALEABLE_MAP = [
    ("finished", "Finished Steel",  True),
    ("semis",    "Saleable Semis",  True),
    ("total",    "Saleable Steel",  True),
]


def _norm(s):
    s = re.sub(r'^\s*\d+\s+', '', str(s))          # leading serial number '4 '
    s = re.sub(r'^\s*[ivx]+\)\s*', '', s.lower())  # roman prefix 'iii) '
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


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
    ("coke rate",                "MAJOR",       "Coke Rate",                        "DSP",     "kg/Thm",    21),
    ("cdi rate",                 "MAJOR",       "CDI Rate",                         "DSP",     "kg/Thm",    41),
    ("nut coke rate",            "MAJOR",       "Nut Coke Consumption",             "DSP",     "kg/Thm",    31),
    ("fuel rate",                "MAJOR",       "Fuel Rate",                        "DSP",     "kg/Thm",    51),
    ("sinter in burden",         "MAJOR",       "Sinter in Burden",                 "DSP",     "%",         61),
    ("bf productivity",          "MAJOR",       "BF Productivity (Working Volume)", "DSP",     "T/m3/Day",  81),
    ("total metallic input",     "MAJOR",       "TMI",                              "DSP SMS", "Kg/TCS",   112),
    ("gross energy consumption", "MAJOR",       "Specific Energy Consumption",      "DSP",     "G.Cal/Tcs",121),
    ("bof slag utilisation",     "IRON_MAKING", "BOF Slag Utilisation",             "DSP",     "%",         41),
    ("loss at skip",             "IRON_MAKING", "Screen Loss",                      "DSP",     "%",         31),
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
                      alias_lookup: dict):
    """Open PDF, read only the production page, close, parse and return rows."""
    import pdfplumber

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
        if len(nums) <= m_idx:
            continue
        val = nums[m_idx]

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
                            "unit":       "T/m2/hr",
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
        for furnace_marker, row_label, sort in [
            ("furnace-ii",  "DSP BF#2", 12),
            ("furnace-iii", "DSP BF#3", 13),
            ("furnace-iv",  "DSP BF#4", 14),
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
                            "unit":       "Kg/Thm",
                            "sort_order": sort,
                            "actual":     actual,
                            "cum_actual": cum,
                            "cell":       f"PDF p{bf_pno} · {want_mon}'{yy}",
                            "found_via":  f"DSP BF CDI {row_label}",
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
# Public API
# ---------------------------------------------------------------------------

def extract_preview(file_path: str, report_month: str, aliases: dict = None,
                    block: str = 'all') -> dict:
    """Extract DSP data from the OMI PDF.

    block controls which sections are processed:
      'all'           — production + techno + special_steel (default)
      'production'    — Block 1 only
      'techno'        — Block 2 only
      'special_steel' — Block 3 only

    Processes in three independent memory-bounded blocks (each opens and
    closes the PDF independently).
    aliases: user-saved mapping {pdf_label: (item_name, convert_to_000T)}
    No database writes — preview only.
    """
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
            file_path, page_index['prod'], want_mon, y, yy, alias_lookup)
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
