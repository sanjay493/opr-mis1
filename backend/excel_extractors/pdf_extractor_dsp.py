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

extract_preview() returns rows for review — NO database writes.
"""
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


def _find_production_page(page_texts):
    """First page that has the heading AND a month header row."""
    for i, text in enumerate(page_texts):
        if "PRODUCTION MONTHWISE" not in text.upper():
            continue
        if _month_header(text.splitlines()):
            return i + 1, text
    return None, None


# ── Special Steel Performance page ───────────────────────────────────────────

def _period_month(label):
    """'April 26' / \"May'26\" → 'APR'/'MAY'; None for 'Cum. 2026-27' etc."""
    m = re.match(r"\s*([A-Za-z]+)", label or "")
    if not m:
        return None
    tok = m.group(1).upper()[:3]
    return tok if tok in _MONTHS else None


def _find_special_steel_page(pdf, page_texts):
    """Page with the 'Special Steel Performance' grid (heading + Section column).
    Uses pre-extracted page_texts to avoid re-scanning; extract_table() only
    called once on the matching page."""
    for i, text in enumerate(page_texts):
        up = text.upper()
        if "SPECIAL STEEL PERFORMANCE" not in up or "SECTION" not in up:
            continue
        tbl = pdf.pages[i].extract_table()
        if tbl and len(tbl) > 5 and len(tbl[0]) >= 6:
            return i + 1, tbl
    return None, None


def _extract_special_steel(pdf, page_texts, want_mon, yy):
    """Parse the Special Steel Performance grid into special_steel_orders rows.

    Grid layout (pdfplumber table):
        Product | Quality/Grade | Section | (Order Prodn Desp.) per period
    Product / Quality-Grade are merged cells (None on continuation rows) and are
    carried forward.  'Total …' rows are returned with status 'total' so the
    preview can show them for cross-checking — the report regenerates totals
    itself, so inserting them would double-count.
    Returns (rows, page_no); ([], None) if the page is absent.
    """
    page_no, tbl = _find_special_steel_page(pdf, page_texts)
    if not tbl:
        return [], None

    # period header row: first row containing a month-like label
    period_row = None
    for ri, row in enumerate(tbl[:6]):
        if any(_period_month(c) for c in row):
            period_row = ri
            break
    if period_row is None:
        return [], page_no

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

    # Order / Prodn / Desp positions inside the chosen period span
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
    return rows, page_no


# ── Mill Techno-Economic Parameters extraction ────────────────────────────────
#
# Two pages: "MERCHANT MILL & MEDIUM STRUCTURAL MILL (MSM)" (page ~27 in PDF)
#            "WHEEL & AXLE PLANT"                            (page ~28 in PDF)
#
# Column layout (for report month M, 0-indexed from Apr=0):
#   Best (YY-YY) | [Norm] | Apr | ... | M (report month) | Cum | CPLY_m | CPLY_FY
# Right-aligned: nums[-4]=report_month actual, nums[-3]=YTD cum.

# (keyword_in_line, param_label_in_db, unit, sort_order)
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


def _parse_te_nums(line):
    """Strip 'Best Achieved (YY-YY)' token, return list of floats.

    '--' (furnace-not-operating marker) is returned as None so that column
    alignment is preserved.  All callers already guard 'if actual is not None'.
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

    Cumulative (nums[-(offset-1)]) is only valid when month_diff == 0 — for
    earlier months the Cum column reflects the PDF's current month.
    """
    needed = offset + month_diff
    if len(nums) < needed:
        return None, None
    actual = nums[-offset - month_diff]
    cum = nums[-(offset - 1)] if month_diff == 0 else None
    return actual, cum


def _find_page_by_heading(page_texts, keyword, also_require=None):
    """Return (page_no, text) for first page whose text contains keyword."""
    for i, text in enumerate(page_texts):
        up = text.upper()
        if keyword.upper() not in up:
            continue
        if also_require and also_require.upper() not in up:
            continue
        return i + 1, text
    return None, None


def _find_line_start(text_upper, marker):
    """Return char offset of marker only when it appears as a full line
    (i.e., preceded by newline or start-of-text and immediately followed by
    newline, space, or end). Avoids partial matches like 'AXLE PLANT' inside
    'WHEEL & AXLE PLANT'."""
    import re as _re
    for m in _re.finditer(re.escape(marker), text_upper):
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


# ── General param extractor (multi-group) ────────────────────────────────────

# (keyword_in_line, group_code, section, row_label, unit, sort_order)
# section = parameter name, row_label = plant/shop  (matches techno_param_master)

# MAJOR TECHNO page — offset=3 because of extra FY-prev-actual column
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

# SMS page — standard offset=4
_SMS_PAGE_DEFS = [
    ("gross h.metal",  "MAJOR", "Hot Metal Consumption", "DSP SMS", "Kg/TCS",  92),
    ("total scrap",    "MAJOR", "Scrap Consumption",     "DSP SMS", "Kg/TCS", 102),
]

# COKE OVENS page — standard offset=4
_COKE_PAGE_DEFS = [
    ("b.f. coke yield", "COKE_SINTER", "BF Coke Yield",  "DSP", "%",              2),
    ("specific heat",   "COKE_SINTER", "Sp. Heat Cons.", "DSP", "000 K.Cal/TDC", 11),
    ("crude tar",       "COKE_SINTER", "Coal Tar Yield", "DSP", "kg/TDC",        21),
]


def _parse_general_params(lines, param_defs, page_no, want_mon, yy, month_diff=0, offset=4):
    """Generic extractor: each param_def = (keyword, group, section, row_label, unit, sort)."""
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


def _extract_bf_furnace_cdi(page_texts, want_mon, yy, month_diff=0):
    """Extract furnace-wise CDI Rate for DSP BF#2, BF#3, BF#4.

    Source: the BF page that contains 'CDI Rate :' furnace rows (page 23 in the
    May'26 PDF).  The column layout is standard offset=4:
      [Norm, Apr, May, Cum, CPLY_Apr, CPLY_FY]
    BF#2 may show '--' for the current month (capital repair) — _parse_te_nums
    returns None for that position so the row is simply skipped.
    """
    rows = []
    # also_require="CDI RATE" pins to page 23 (has CDI data), not page 22 or INDEX
    bf_no, bf_text = _find_page_by_heading(page_texts, "BLAST FURNACE",
                                            also_require="CDI RATE")
    if not bf_text:
        return rows

    # Slice just the CDI Rate block to avoid matching "furnace-ii" etc. from
    # other sections (Si in HM, Productivity, …) that use the same sub-labels.
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
                        "cell":       f"PDF p{bf_no} · {want_mon}'{yy}",
                        "found_via":  f"DSP BF CDI {row_label}",
                        "status":     "ok",
                    })
                break

    return rows


def _extract_major_techno_params(page_texts, want_mon, yy, month_diff=0):
    """Extract MAJOR + IRON_MAKING params from the MAJOR TECHNO page and SMS page."""
    rows = []

    # MAJOR TECHNO page — also_require="Kg/THM" skips the INDEX/TOC page
    page_no, text = _find_page_by_heading(page_texts, "MAJOR TECHNO", also_require="Kg/THM")
    if text:
        lines = text.splitlines()
        rows.extend(_parse_general_params(lines, _MAJOR_PAGE_DEFS, page_no,
                                          want_mon, yy, month_diff, offset=3))

    # SMS page (offset=4: standard layout)
    sms_no, sms_text = _find_page_by_heading(page_texts, "STEEL MELTING SHOP",
                                              also_require="BOF SHOP")
    if sms_text:
        lines = sms_text.splitlines()
        rows.extend(_parse_general_params(lines, _SMS_PAGE_DEFS, sms_no,
                                          want_mon, yy, month_diff, offset=4))

    return rows


def _extract_coke_sinter_params(page_texts, want_mon, yy, month_diff=0):
    """Extract COKE_SINTER params from Coke Ovens and RMHP/Sinter pages."""
    rows = []

    # COKE OVENS page (offset=4)
    coke_no, coke_text = _find_page_by_heading(page_texts, "COKE OVENS & COAL CHEMICALS")
    if coke_text:
        lines = coke_text.splitlines()
        rows.extend(_parse_general_params(lines, _COKE_PAGE_DEFS, coke_no,
                                          want_mon, yy, month_diff, offset=4))

    # RMHP & SINTER page — also_require="OLD MACHINE" skips the INDEX/TOC page
    sint_no, sint_text = _find_page_by_heading(page_texts, "RMHP & SINTER PLANT",
                                                also_require="OLD MACHINE")
    if sint_text:
        for label, marker, stop in [("DSP SP-1", "OLD MACHINE", ["NEW MACHINE"]),
                                    ("DSP SP-2", "NEW MACHINE", [])]:
            lines = _slice_text(sint_text, marker, stop)
            for ln in lines:
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
                            "cell":       f"PDF p{sint_no} · {want_mon}'{yy}",
                            "found_via":  f"DSP Sinter {label}",
                            "status":     "ok",
                        })
                    break

    return rows


def _extract_mill_techno(page_texts, want_mon, yy, month_diff=0):
    """Extract MILL_DSP techno params from the two mill pages.

    month_diff: how many columns back want_mon is from the PDF's last month
    (0 = current month = also extract cum; >0 = historical month = no cum).
    """
    rows = []

    page_no, text = _find_page_by_heading(page_texts, "MERCHANT MILL & MEDIUM STRUCTURAL MILL")
    if text:
        mm_lines = _slice_text(text, "TE PARAMETERS - MERCHANT MILL",
                               ["PRODUCTION - MSM", "TE PARAMETERS - MSM"])
        rows.extend(_parse_params_from_lines(
            mm_lines, "Merchant Mill", _MM_MSM_PARAMS["Merchant Mill"], page_no, want_mon, yy, month_diff))
        msm_lines = _slice_text(text, "TE PARAMETERS - MSM", [])
        rows.extend(_parse_params_from_lines(
            msm_lines, "MSM", _MM_MSM_PARAMS["MSM"], page_no, want_mon, yy, month_diff))

    page_no2, text2 = _find_page_by_heading(page_texts, "WHEEL & AXLE PLANT", also_require="FORGING AVAIL")
    if text2:
        wp_lines = _slice_text(text2, "WHEEL PLANT", ["AXLE PLANT"])
        rows.extend(_parse_params_from_lines(
            wp_lines, "Wheel Plant", _WA_PARAMS["Wheel Plant"], page_no2, want_mon, yy, month_diff))
        ap_lines = _slice_text(text2, "AXLE PLANT", [])
        rows.extend(_parse_params_from_lines(
            ap_lines, "Axle Plant", _WA_PARAMS["Axle Plant"], page_no2, want_mon, yy, month_diff))

    return rows


def extract_preview(file_path: str, report_month: str, aliases: dict = None) -> dict:
    """Extract DSP production from the OMI PDF. Preview only — no DB writes.

    aliases: optional user-saved mapping {pdf_label: (item_name, convert_to_000T)}
    persisted from earlier preview corrections (pdf_item_alias table). Matched on
    the normalized label and takes priority over the built-in maps.
    """
    import pdfplumber

    alias_lookup = {}
    for raw_label, (a_item, a_conv) in (aliases or {}).items():
        alias_lookup[_norm(raw_label)] = (a_item, bool(a_conv))

    y, m = int(report_month[:4]), int(report_month[5:7])
    want_mon = _MONTHS[m - 1]

    yy = str(y)[2:]
    ss_rows, ss_page, ss_note = [], None, ""
    mill_techno_rows = []
    with pdfplumber.open(file_path) as pdf:
        # Single-pass, early-stopping text extraction: scan pages until all
        # required sections are found (production, special steel, MM/MSM, W&A,
        # MAJOR TECHNO, COKE OVENS, RMHP/SINTER, SMS).
        page_texts = []
        _need_prod = _need_ss = _need_mm = _need_wa = True
        _need_major = _need_coke = _need_sint = _need_sms = _need_bf_cdi = True
        for pg in pdf.pages:
            txt = pg.extract_text() or ""
            page_texts.append(txt)
            up = txt.upper()
            if _need_prod and "PRODUCTION MONTHWISE" in up and _month_header(txt.splitlines()):
                _need_prod = False
            if _need_ss and "SPECIAL STEEL PERFORMANCE" in up and "SECTION" in up:
                _need_ss = False
            if _need_mm and "MERCHANT MILL & MEDIUM STRUCTURAL MILL" in up:
                _need_mm = False
            if _need_wa and "WHEEL & AXLE PLANT" in up and "FORGING AVAIL" in up:
                _need_wa = False
            if _need_major and "MAJOR TECHNO" in up:
                _need_major = False
            if _need_coke and "COKE OVENS & COAL CHEMICALS" in up:
                _need_coke = False
            if _need_sint and "RMHP & SINTER PLANT" in up:
                _need_sint = False
            if _need_sms and "STEEL MELTING SHOP" in up and "BOF SHOP" in up:
                _need_sms = False
            if _need_bf_cdi and "BLAST FURNACE" in up and "CDI RATE" in up:
                _need_bf_cdi = False
            if not any([_need_prod, _need_ss, _need_mm, _need_wa,
                        _need_major, _need_coke, _need_sint, _need_sms,
                        _need_bf_cdi]):
                # Pad remaining pages with empty strings so index alignment is preserved
                page_texts += [""] * (len(pdf.pages) - len(page_texts))
                break

        page_no, text = _find_production_page(page_texts)

        # month_diff: how many months behind want_mon is vs the PDF's last month.
        # e.g. uploading May report to extract April → month_diff = 1.
        # Used to pick the right TE params column and suppress invalid cum values.
        month_diff = 0
        if text:
            mc = _month_header(text.splitlines())
            if mc and want_mon in mc:
                month_diff = len(mc) - 1 - mc.index(want_mon)

        try:
            ss_rows, ss_page = _extract_special_steel(pdf, page_texts, want_mon, yy)
        except Exception as e:                      # special steel is optional
            ss_note = f"Special Steel extraction skipped: {e}"
        try:
            mill_techno_rows = _extract_mill_techno(page_texts, want_mon, yy, month_diff)
        except Exception:
            mill_techno_rows = []
        try:
            mill_techno_rows.extend(
                _extract_major_techno_params(page_texts, want_mon, yy, month_diff))
        except Exception:
            pass
        try:
            mill_techno_rows.extend(
                _extract_coke_sinter_params(page_texts, want_mon, yy, month_diff))
        except Exception:
            pass
        try:
            mill_techno_rows.extend(
                _extract_bf_furnace_cdi(page_texts, want_mon, yy, month_diff))
        except Exception:
            pass

    if not text:
        raise ValueError("No 'PRODUCTION MONTHWISE' page found in the PDF. "
                         "Is this the DSP monthly MIS report?")

    lines = text.splitlines()

    month_cols = _month_header(lines)
    if not month_cols:
        raise ValueError("Month header row not found on the production page.")
    if want_mon not in month_cols:
        raise ValueError(
            f"Report month {want_mon}'{str(y)[2:]} not present in this PDF "
            f"(columns found: {', '.join(month_cols)}).")
    m_idx = month_cols.index(want_mon)
    n_cols = len(month_cols) + 1            # months + TOTAL

    rows = []
    in_saleable = False
    for ln in lines:
        if "SALEABLE STEEL" in ln.upper():
            in_saleable = True

        toks = ln.split()
        # trailing numeric run
        nums = []
        for t in reversed(toks):
            v = _num(t)
            if v is None:
                break
            nums.insert(0, v)
        if not nums:
            continue
        # Data columns are the LAST n_cols numbers (months + TOTAL). Any extra
        # leading numbers belong to the label — e.g. 'i) BF 2 16857 0 16857'
        # where the '2' of 'BF 2' would otherwise shift the month column.
        if len(nums) > n_cols:
            nums = nums[len(nums) - n_cols:]
        label_toks = toks[:len(toks) - len(nums)]
        label = _norm(" ".join(label_toks))
        if not label:
            continue

        # value for the requested month
        if len(nums) > m_idx:
            val = nums[m_idx]
        else:
            continue

        item, convert = None, True
        if label in alias_lookup:               # user-saved corrections first
            item, convert = alias_lookup[label]
        if item is None:
            table = _SALEABLE_MAP if in_saleable else _ITEM_MAP
            for alias, name, conv in table:
                if label == alias:
                    item, convert = name, conv
                    break
        if item is None and in_saleable:        # fall back to the general map
            for alias, name, conv in _ITEM_MAP:
                if label == alias:
                    item, convert = name, conv
                    break

        stored = round(val / 1000.0, 3) if (convert and item) else val
        rows.append({
            "item_name": item if item else f"(unmapped) {label}",
            "value": stored if item else val,
            "unit": "nos/d" if (item and not convert) else "'000T" if item else "T",
            "cell": f"PDF p{page_no} · {want_mon}'{str(y)[2:]} col",
            "pdf_label": " ".join(label_toks),
            "status": "ok" if item else "unmapped",
        })

    if not any(r["status"] == "ok" for r in rows):
        raise ValueError("Production page found but no known items matched.")

    sheets = f"PDF page {page_no} (PRODUCTION MONTHWISE)"
    workbook_sheets = [f"PDF page {page_no}"]
    if ss_page:
        sheets += f" + page {ss_page} (SPECIAL STEEL)"
        workbook_sheets.append(f"PDF page {ss_page}")

    return {
        "plant": PLANT,
        "month": report_month,
        "source_type": "DSP OMI PDF Report",
        "sheets": sheets,
        "workbook_sheets": workbook_sheets,
        "production_rows": rows,
        "special_steel_rows": ss_rows,
        "special_steel_note": ss_note,
        "techno_rows": [],
        "techno_param_rows": mill_techno_rows,
    }
