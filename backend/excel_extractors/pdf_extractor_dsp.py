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

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

# Default label maps — overridden at runtime from excel_cells_config.json ["dsp_pdf"]
_ITEM_MAP_DEFAULT = [
    # ("i) Nos.(Total)",      "Oven Pushing (nos/day)",  False),
    ("ii) nos. per day",        "Oven Pushing (nos/day)",  False),
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
    ("concast steel",      "SMS Total Caster",     True),
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
        import os
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
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


def _strip_lead_digit(label):
    """Drop a leading roman-numeral-derived serial ('1 cc bloom' -> 'cc bloom').

    Items like CC Bloom/CC Billet/BRC Bloom/BRC Round are printed as a
    lettered sub-list (i, ii, iii, iv) whose ORDER varies between report
    vintages — which physical item gets "i)" isn't fixed, so a hardcoded
    "1 cc bloom" alias only covers one ordering. BF#2/3/4 don't have this
    problem (the number is the furnace's own identity, always fixed), so
    this is only used as a fallback after an exact match already failed.
    """
    return re.sub(r'^\d+\s+', '', label)


def _extract_pdf_report_month(file_path: str) -> str:
    """Extract report month from first page of PDF.

    Looks for text like "September 2025" or "Sep'25" on first page.
    Returns "YYYY-MM" format (e.g. "2025-09") or raises ValueError if not found.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ValueError("pdfplumber not installed - cannot extract PDF report month")

    import re

    try:
        with pdfplumber.open(file_path) as pdf:
            first_page_text = (pdf.pages[0].extract_text() or "").upper()
    except Exception as e:
        raise ValueError(f"Cannot read PDF first page: {e}")

    # Try to find month name (full or abbreviated) + year
    # Patterns: "SEPTEMBER 2025", "SEP 2025", "SEP'25", "September'25"
    # Older reports (~2016-2019) use a curly/typographic apostrophe (U+2019/U+2018)
    # between month and year instead of a plain ASCII "'" — include both, plus a
    # dash, so "January’ 2018" style headers still match.
    patterns = [
        r'(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[\'‘’\-|\s]+(20\d{2})',
        r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[\'‘’\-|\s]+(20\d{2})',
    ]

    for pattern in patterns:
        match = re.search(pattern, first_page_text)
        if match:
            month_str = match.group(1)
            year_str = match.group(2)

            # Map month name to number
            month_num = None
            for name, num in _MONTH_NAMES.items():
                if month_str.upper().startswith(name[:3].upper()):
                    month_num = num
                    break

            if month_num:
                year = int(year_str)
                return f"{year}-{month_num:02d}"

    raise ValueError(
        f"Could not find report month on first page of PDF. "
        f"Expected format like 'September 2025' or 'SEP 2025'."
    )


# Recognized non-month aggregate-column labels: newer reports end the row
# with "TOTAL"; older (~2015-2018) reports interleave quarterly/half-yearly
# cumulative columns ("Q1", "Q2", "Q3", "Q4", "H1", "H2") with no "TOTAL".
_AGGREGATE_TOKENS = {"TOTAL", "Q1", "Q2", "Q3", "Q4", "H1", "H2", "YTD"}


def _month_header(lines):
    """Returns the month-column list from a header line like 'SL. APR MAY TOTAL' or 'APR'25 MAY'25 TOTAL'.

    Extracts months in order they appear, skipping duplicates and non-month columns.
    Handles month names with years like "SEP'25", "Sep'25", etc.
    """
    for ln in lines[:15]:
        toks = [t.upper().rstrip('.').rstrip('\'').split('\'')[0] for t in ln.split()]
        # Extract only month abbreviations (first 3 letters of year-prefixed tokens)
        cols = []
        seen = set()
        for t in toks:
            # Get first 3 chars (month abbr)
            mon_abbr = t[:3] if len(t) >= 3 else t
            if mon_abbr in _MONTHS and mon_abbr not in seen:
                cols.append(mon_abbr)
                seen.add(mon_abbr)

        # Older (~2015-2018) mid-year reports sometimes omit the redundant
        # "TOTAL" column entirely (the last Q/H-period column already IS
        # the cumulative-to-date figure), so don't require it — just require
        # at least one recognized month abbreviation on the line.
        if cols:
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
    'prod':     ("PRODUCTION MONTHWISE", None),
    'ss':       ("SPECIAL STEEL PERFORMANCE", "SECTION"),
    'mm':       ("MERCHANT MILL & MEDIUM STRUCTURAL MILL", None),
    'wa':       ("WHEEL & AXLE PLANT", "FORGING AVAIL"),
    'major':    ("MAJOR TECHNO", "KG/THM"),
    'coke':     ("COKE OVENS & COAL CHEMICALS", None),
    'sint':     ("RMHP & SINTER PLANT", "OLD MACHINE"),   # OLD MACHINE avoids TOC match
    'sms':      ("STEEL MELTING SHOP", "BOF SHOP"),
    'sms2':     ("STEEL MELTING SHOP", "BOF SHOP CONTD"), # SMS page 2 (raw-material rates)
    'ccp':      ("CONTINUOUS CASTING PLANT", "TE PARAMETERS"), # Billet/Bloom/BRC Caster Yield
    'bf_main':  ("BLAST FURNACE", "SILICON IN HM"),        # BF page 1: Si, S, Slag, Productivity
    'bf_cdi':   ("BLAST FURNACE", "NUT COKE RATE"),        # BF page 2: CDI, Coke Rate, Sinter
    # NOTE: h2 was "CDI RATE" but that also matches the narrative "Highlights"
    # page's prose ("...achieved best monthly CDI rate..."), which appears
    # earlier in the document and would win the scan first. "NUT COKE RATE"
    # only appears on the real BF-CDI data table.
}


def _scan_page_index(file_path: str, max_pages: int = 120) -> tuple:
    """Single lightweight pass: return ({section_key: 0-based_page_index}, page_texts).

    page_texts caches every page's extract_text() result keyed by 0-based
    index, for the pages this scan actually had to read (i.e. up to and
    including the last page examined before every section was found). This
    text is the expensive part of a scan pass — some scanned/vector-heavy
    pages take many seconds each (see extract_preview's Block 2 comment) —
    so callers that need one of these pages again (e.g. _block_techno for
    the section pages just located, or the month_diff fallback below) should
    reuse it instead of re-opening the PDF and re-extracting.
    """
    import pdfplumber
    import sys
    found = {}
    page_texts = {}
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

            page_texts[i] = txt
            up    = txt.upper()
            lines = txt.splitlines() if 'prod' in remaining else []

            done = set()
            for key in remaining:
                h1, h2 = _SECTION_HEADINGS[key]
                if h1 not in up:
                    continue
                if h2 and h2 not in up:
                    continue

                # For PRODUCTION MONTHWISE: skip TABLE OF CONTENTS pages
                # TOC pages have "INDEX" or "CONTENTS" in them
                if key == 'prod':
                    if 'INDEX' in up or 'CONTENTS' in up or 'TABLE OF' in up:
                        continue  # Skip TOC pages
                    if not _month_header(lines):
                        continue

                found[key] = i
                done.add(key)
                print(f"[DSP PDF] scan: found '{key}' on page {i+1}", flush=True, file=sys.stderr)
            remaining -= done
    finally:
        pdf_obj.close()

    if remaining:
        print(f"[DSP PDF] scan: sections NOT found: {remaining}", flush=True, file=sys.stderr)
    return found, page_texts


# ---------------------------------------------------------------------------
# Shared low-level helpers
# ---------------------------------------------------------------------------

def _period_month(label):
    """'April 26' / "May'26" → 'APR'/'MAY'; None for 'Cum. 2026-27' etc.

    Scans every word in the label rather than just the first one — some
    exports (e.g. Feb'24) run adjacent header cells together so the month
    token isn't always at the start (seen as "Section Jan" / "24 Feb 24").
    """
    for tok in re.findall(r"[A-Za-z]+", label or ""):
        u = tok.upper()[:3]
        if u in _MONTHS:
            return u
    return None


def _parse_te_nums(line):
    """Strip 'Best Achieved (YY-YY)' token, return list of floats.

    '--' (furnace-not-operating marker) is returned as None so that column
    alignment is preserved.
    """
    # Strip best-achieved: number followed by (YY-YY) — allow trailing space
    # before ')' and a stray leading quote before the year (seen as "('04-05)"
    # in some rows, e.g. Sinter in Burden: Shop, instead of "(04-05)").
    line2 = re.sub(r"\d[\d,.]*\s*\(['‘’]?\d{2}-\d{2}\s*\)", '', line)
    # Strip unit labels with embedded digits: NM3/T, NM3/TDC, Nm3, etc.
    line2 = re.sub(r'\b[A-Za-z]+\d+(?:[/][A-Za-z]+)*\b', '', line2)
    result = []
    for tok in re.findall(r'(?<!\d)--(?!\d)|-?\d+(?:,\d+)*(?:\.\d+)?', line2):
        if tok == '--':
            result.append(None)
        else:
            result.append(float(tok.replace(',', '')))
    return result



def _prior_quarter_subtotal_present(lines, want_mon):
    """Whether this growing-FY-table's header repeats a quarter-subtotal
    column on the prior-year side too, or omits it.

    Real DSP reports are inconsistent about this: Jun'25 and Sep'25 both
    show "... Q1 2025-26 Jun.'24 Q1 2024-25" / "... Q2 2025-26 Sep.'24 Q2
    2024-25" (prior side = [prior_month, prior_Q, prior_FY_ref], 3 tokens),
    while Dec'25 shows "... Q3 2025-26 Nov.'24 2024-25" (prior side =
    [prior_month, prior_FY_ref], only 2 tokens — no prior-Q). Dec's prior-
    month column is also mislabeled "Nov" instead of "Dec" in that same
    header, which is why this locates the prior side via the FY-year token
    (e.g. "2025-26") rather than via a second occurrence of want_mon's own
    label — that label can't be trusted to repeat correctly.

    Returns True/False when a growing-table header for want_mon is found,
    None if no such header line was found in `lines` (caller should fall
    back to the historically-assumed True in that case).
    """
    mon3 = want_mon[:3].upper()
    for ln in lines[:25]:
        toks = ln.split()
        if not toks or toks[0].upper() != "ITEM":
            continue
        cleaned = []
        for t in toks:
            m = re.match(r'^([A-Za-z]+)', t)
            cleaned.append(m.group(1).upper() if m else t.upper())
        positions = [i for i, t in enumerate(cleaned) if t[:3] == mon3]
        if not positions:
            continue
        current_idx = positions[0]
        fy_idx = None
        for i in range(current_idx + 1, len(cleaned)):
            if re.match(r'^\d{4}-\d{2}$', cleaned[i]):
                fy_idx = i
                break
        if fy_idx is None:
            continue
        prior_side = cleaned[fy_idx + 1:]
        if not prior_side:
            continue
        return len(prior_side) >= 3
    return None


def _te_values_techno(nums, report_month_num=None, has_prior_q=True):
    """Extract techno values from a techno row (handles variable column count).

    Every DSP techno-page row — whether it's a small fixed page (MAJOR/SMS/
    Coke/Mill, always ~4-7 columns year-round) or a "growing FY table" row
    (BF Silicon/Sulphur/HM Temp/CDI/Coke Rate/.../Sinter Productivity, which
    gains one column per elapsed month plus a quarter-subtotal column at
    Jun/Sep/Dec/Mar) ends in the same trailing shape once you count from the
    right:
        [..., current_month, (current_Q, only at quarter-end), YTD_so_far,
         prior_year_same_month, (prior_Q — only some quarter-end reports),
         prior_year_ref]
    So a single pair of negative-offset formulas — one for quarter-end
    months (Jun/Sep/Dec/Mar) and one for every other month — correctly
    locates actual/cum/prior regardless of how many leading columns (Norm,
    elapsed months, elapsed quarters) have accumulated. This replaces what
    used to be five separate length-keyed branches (4/5/6/7/>=14 columns)
    that were all — once worked out — the exact same formula in disguise;
    the old dispatch had a gap for lengths 8-13 (roughly Jun-Oct) that
    silently dropped every growing-table parameter for those months.

    Verified against real DSP monthly reports: YTD matches the arithmetic
    average of that FY's elapsed monthly values for Jan/Feb/Mar/Aug/May/Jun/
    Sep/Oct/Nov/Dec reports; quarter subtotals match avg() of their 3
    months. Quarter-end handling is now verified against real Jun/Sep/Dec
    reports (previously only March had a real sample) — cross-checked
    column-by-column against each report's own header AND against the same
    parameter's value as it reappears in a *later* month's growing table
    (e.g. December's own Apr-Dec columns must agree with what Jun/Sep/Oct/
    Nov's own independent reports say for those same months — confirmed for
    Silicon in HM on all three furnaces).

    This is where `has_prior_q` (see _prior_quarter_subtotal_present)
    matters: Jun'25 and Sep'25 both carry a prior-year quarter-subtotal
    column that Dec'25 omits, which shifts actual_current/cum_current/
    actual_prior together by one column at quarter-end. Guessing this
    instead of detecting it from the header was the original bug — it
    silently pulled the PRIOR month's value (e.g. November for a December
    report) into the CURRENT month's slot for whichever shape didn't match
    the guess.

    report_month_num: Month number (1-12).
    - Quarter-end months (Mar/Jun/Sep/Dec) get an extra current-quarter
      column right after the current month.
    - Prior-year cumulative (cum_prior) is only a complete FY at March —
      every other month's trailing "prior_year_ref" column is a partial-year
      figure, so cum_prior is None everywhere except March.

    Returns: (actual_current, cum_current, actual_prior, cum_prior)
    """
    if report_month_num == 3 and len(nums) in (19, 20):
        # March annual-layout row, Major-page shape:
        # [Norm?, PriorFY_annual, Apr..Feb, Mar, Q4, CurrentFY_annual, PriorFY_annual]
        # actual_prior isn't broken out separately in this shape — only the
        # prior FY's annual total is available. Verified: Q4 == avg(Jan,Feb,Mar).
        actual_current = nums[-4]
        cum_current    = nums[-2]
        actual_prior   = None
        cum_prior      = nums[-1]
        return actual_current, cum_current, actual_prior, cum_prior

    is_quarter_end = report_month_num in (3, 6, 9, 12)
    quarter_end_with_prior_q = is_quarter_end and has_prior_q
    if is_quarter_end:
        min_len = 6 if has_prior_q else 5
    else:
        min_len = 4
    if len(nums) < min_len:
        return None, None, None, None

    if quarter_end_with_prior_q:
        actual_current = nums[-6]
        cum_current    = nums[-4]
        actual_prior   = nums[-3]
    elif is_quarter_end:
        actual_current = nums[-5]
        cum_current    = nums[-3]
        actual_prior   = nums[-2]
    else:
        actual_current = nums[-4]
        cum_current    = nums[-3]
        actual_prior   = nums[-2]
    cum_prior = nums[-1] if report_month_num == 3 else None
    return actual_current, cum_current, actual_prior, cum_prior


def _te_values_major_page(nums, report_month_num=None):
    """Extract (actual, cum) from a MAJOR TECHNO ECONOMIC PARAMETERS page row.

    This page's "growing FY table" rows have one fewer trailing column than
    the BF/SMS/Coke/Sinter pages: there's no prior-year-same-month
    comparison, just [..., current_month, (current_Q, quarter-end only),
    YTD_so_far, prior_FY_total_reference]. Verified against real reports via
    quarterly cross-check (Q1-Q4 all equal avg() of their 3 months) and the
    FY-end YTD equalling avg() of all 12 monthly values, for both
    "Gross Energy Consumption" and "BOF Slag Utilisation".

    This replaces a previous hardcoded nums[2]/nums[3] extraction that only
    ever happened to be correct for the first month or two of the FY, and
    was wrong (picking up an early elapsed month instead of the current one)
    for every other month.
    """
    is_quarter_end = report_month_num in (3, 6, 9, 12)
    min_len = 4 if is_quarter_end else 3
    if len(nums) < min_len:
        return None, None
    if is_quarter_end:
        return nums[-4], nums[-2]
    return nums[-3], nums[-2]


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
    ("gross energy consumption",   "MAJOR",       "Specific Energy Consumption",      "DSP",     "G.Cal/TCS",121),
    # Section text is "Sp Power Consumption" (not "Specific...") so
    # _to_snake() in dsp_technopara_extractor.py yields "sp_power_consumption"
    # — the same canonical key page_key_parameters.py and every other
    # plant's extractor use (ISP's own source row is literally labeled "Sp
    # Power Consumption" too). Same growing-FY-table row structure as
    # "Gross Energy Consumption" immediately above it in the source PDF —
    # see special_params/skip_prior_year below.
    ("specific power consumption", "MAJOR",       "Sp Power Consumption",             "DSP",     "KWH/TSS",  122),
    ("bof slag utilisation",       "COKE_SINTER", "BOF Slag Utilisation",             "DSP",     "%",         41),
    ("loss at skip",               "IRON_MAKING", "Coke Screen Loss",                 "DSP", "%",  31),
]
# NOTE: Removed from Major Techno (will be extracted from Blast Furnace page instead):
# - Coke Rate, CDI Rate, Nut Coke Rate, Fuel Rate, Sinter in Burden
# - TMI will be computed from Hot Metal + Scrap Consumption instead

_SMS_PAGE_DEFS = [
    ("gross h\\.metal",              "MAJOR", "Hot Metal Consumption",       "DSP SMS", "Kg/TCS",  92),
    ("total scrap",                  "MAJOR", "Scrap Consumption",           "DSP SMS", "Kg/TCS", 102),
    ("heat size",                    "MAJOR", "Heat Size",                   "DSP SMS", "T",       103),
    ("refractory consumption.*sms",  "MAJOR", "Refractory Consumption(SMS)", "DSP SMS", "Kg/TCS", 104),
    ("refractory consumption.*red",  "MAJOR", "Refractory Consumption(RED)", "DSP SMS", "Kg/TCS", 105),
    ("tap to tap",                   "MAJOR", "Tap to Tap Time",             "DSP SMS", "mins",    106),
    ("conv\\.availability",          "MAJOR", "Converter Availability",      "DSP SMS", "%",       107),
    ("conv.*utilisation",            "MAJOR", "Converter Utilisation",       "DSP SMS", "%",       108),
    ("b\\.o\\.f.*gas yield",         "MAJOR", "BOF Gas Yield",               "DSP SMS", "Nm³/TCS", 114),
]

# SMS page 2 — raw-material consumption rates (BOF SHOP CONTD.)
_SMS2_PAGE_DEFS = [
    ("calcined lime",    "MAJOR", "Calcined Lime Consumption",      "DSP SMS", "Kg/TCS", 109),
    ("limestone",        "MAJOR", "Limestone Consumption",          "DSP SMS", "Kg/TCS", 110),
    ("si\\.mn",          "MAJOR", "Silicon Manganese Consumption",  "DSP SMS", "Kg/TCS", 111),
    ("fe-si",            "MAJOR", "Ferro Silicon Consumption",      "DSP SMS", "Kg/TCS", 112),
    ("fe-mn",            "MAJOR", "Ferro Manganese Consumption",    "DSP SMS", "Kg/TCS", 113),
    ("oxygen.*conv",     "MAJOR", "Oxygen (Converter)",             "DSP SMS", "NM3/TCS", 115),
    ("calcined dolo",    "MAJOR", "Calcined Dolomite Consumption",  "DSP SMS", "Kg/TCS", 116),
]

_COKE_PAGE_DEFS = [
    ("b\\.f\\. coke yield",  "COKE_SINTER", "BF Coke Yield",                       "DSP", "%",             2),
    ("gross coke yield",     "COKE_SINTER", "Gross Coke Yield",                     "DSP", "%",             3),
    ("sp\\. heat cons",      "COKE_SINTER", "Sp. Heat Cons.",                       "DSP", "000 K.Cal/TDC", 11),
    ("crude tar",            "COKE_SINTER", "Coal Tar Yield",                       "DSP", "kg/TDC",        21),
    ("coal charge.*dry",     "COKE_SINTER", "Dry Coal Charge/Oven",                 "DSP", "T",             22),
    ("specific heat",        "COKE_SINTER", "Specific Heat (Coke Ovens)",           "DSP", "M.Cal/T",       23),
    ("specific power",       "COKE_SINTER", "Specific Power (Coke Ovens)",          "DSP", "KWH/T",         23),
    ("crude benzol",         "COKE_SINTER", "Crude Benzol",                         "DSP", "kg/TDC",        24),
    ("c\\.o\\.gas yield|c\\.o gas yield|c\\.o\\. gas yield",
                             "COKE_SINTER", "Coke Oven Gas Yield",                  "DSP", "Nm³/TDC",       25),
    ("ammonium sulphate",    "COKE_SINTER", "Ammonium Sulphate",                    "DSP", "Kg/TDC",        26),
    (r"m\s*10",              "COKE_SINTER", "M10",                                  "DSP", "%",             28),
    (r"m\s*40",              "COKE_SINTER", "M40",                                  "DSP", "%",             29),
    ("average ash in.*coke", "COKE_SINTER", "Average Ash in Coke",                  "DSP", "%",             30),
    ("average ash in coal",  "COKE_SINTER", "Average Ash in Coal Blend",            "DSP", "%",             31),
    ("average.*v\\.m\\..*coal|volatile matter",
                             "COKE_SINTER", "Average Volatile Matter in Coal Blend", "DSP", "%",            32),
]

_BF_FURNACE_PARAMS = [
    ("silicon in hm",           "IRON_MAKING", "Silicon in HM",          "%",      51),
    ("sulphur in hm",           "IRON_MAKING", "Sulphur in HM",          "%",      61),
    ("avg hot metal temperature",       "IRON_MAKING", "Avg Hot Metal Temperature",      "°C",     65),
    ("blast temp",       "IRON_MAKING", "Blast Temperature",      "°C",     71),
    ("sinter in burden",        "IRON_MAKING", "Sinter in Burden",       "%",     81),
    ("coke rate",          "IRON_MAKING", "Coke Rate",              "kg/T",   91),
    ("nut coke rate",           "IRON_MAKING", "Nut Coke Rate",          "kg/T",  101),
    ("productivity.*useful",           "IRON_MAKING", "BF Productivity (useful)",          "T/m³/day",  1000),
    ("productivity.*working",           "IRON_MAKING", "BF Productivity (working)",          "T/m³/day",  1001),
]

_BF_SHOP_PARAMS = [
    ("slag rate",               "IRON_MAKING", "Slag Rate",              "kg/THM", 111),
    ("slag offtake",            "IRON_MAKING", "Slag Offtake",           "%",      112),
    ("fuel rate",               "IRON_MAKING", "Fuel Rate",              "kg/T",   121),
]


# ---------------------------------------------------------------------------
# Techno parsing helpers (work on plain text, no pdf object needed)
# ---------------------------------------------------------------------------

def _parse_params_from_lines(lines, section, param_list, page_no, want_mon, yy, month_diff=0, offset=4, report_month_num=None):
    rows = []
    _hpq = _prior_quarter_subtotal_present(lines, want_mon)
    has_prior_q = True if _hpq is None else _hpq
    for keyword, label, unit, sort in param_list:
        for ln in lines:
            if keyword in ln.lower():
                nums = _parse_te_nums(ln)
                actual_curr, cum_curr, actual_prior, cum_prior = _te_values_techno(nums, report_month_num, has_prior_q)
                if actual_curr is not None:
                    # Current year row
                    rows.append({
                        "group_code": "MILL_DSP",
                        "section":    section,
                        "parameter":  label,
                        "unit":       unit,
                        "sort_order": sort,
                        "actual":     actual_curr,
                        "cum_actual": cum_curr,
                        "month":      f"{want_mon}'{yy}",
                        "cell":       f"PDF p{page_no} · {want_mon}'{yy}",
                        "found_via":  f"DSP {section}",
                        "status":     "ok",
                    })
                    # Prior year row (if available)
                    if actual_prior is not None:
                        prior_yy = str(int(yy) - 1)
                        rows.append({
                            "group_code": "MILL_DSP",
                            "section":    section,
                            "parameter":  label,
                            "unit":       unit,
                            "sort_order": sort + 0.5,  # Group after current year
                            "actual":     actual_prior,
                            "cum_actual": cum_prior,
                            "month":      f"{want_mon}'{prior_yy}",
                            "cell":       f"PDF p{page_no} · {want_mon}'{prior_yy}",
                            "found_via":  f"DSP {section} (prior year)",
                            "status":     "ok",
                        })
                break
    return rows


def _parse_general_params(lines, param_defs, page_no, want_mon, yy, month_diff=0, offset=4, report_month_num=None):
    rows = []
    # Parameters that should NOT have prior year extraction
    skip_prior_year = {"gross energy consumption", "specific power consumption", "bof slag utilisation", "loss at skip"}
    # Parameters with special column handling (different structure in PDF)
    special_params = {"gross energy consumption", "specific power consumption", "bof slag utilisation", "loss at skip"}
    # crude benzol appears on two lines: Lit./TDC (skip) then Kg/TDC (use next line)
    _crude_benzol_kw = "crude benzol"
    lines_list = list(lines)
    _hpq = _prior_quarter_subtotal_present(lines_list, want_mon)
    has_prior_q = True if _hpq is None else _hpq

    for keyword, group_code, section, row_label, unit, sort in param_defs:
        found = False
        for li, ln in enumerate(lines_list):
            # Use re.search so regex-style keywords (.*  |  \(  etc.) work correctly
            if not re.search(keyword, ln.lower()):
                continue

            # crude benzol: first line is Lit./TDC → use the next line (Kg/TDC)
            if _crude_benzol_kw in keyword.lower() and "lit." in ln.lower():
                if li + 1 < len(lines_list):
                    ln = lines_list[li + 1]
                else:
                    break

            # M10 / M40 rows often start with "M 40" or "M 10" — skip header/label-only lines
            nums = _parse_te_nums(ln)
            if len(nums) < 4:
                continue

            # Special handling for MAJOR-page params (growing FY table, but no
            # prior-year comparison column — see _te_values_major_page).
            if keyword in special_params:
                actual_curr, cum_curr = _te_values_major_page(nums, report_month_num)
                actual_prior = None
                cum_prior    = None
            else:
                actual_curr, cum_curr, actual_prior, cum_prior = _te_values_techno(nums, report_month_num, has_prior_q)

            if actual_curr is not None:
                rows.append({
                    "group_code": group_code,
                    "section":    section,
                    "parameter":  row_label,
                    "unit":       unit,
                    "sort_order": sort,
                    "actual":     actual_curr,
                    "cum_actual": cum_curr,
                    "month":      f"{want_mon}'{yy}",
                    "cell":       f"PDF p{page_no} · {want_mon}'{yy}",
                    "found_via":  f"DSP {section}",
                    "status":     "ok",
                })
                if actual_prior is not None and keyword not in skip_prior_year:
                    prior_yy = str(int(yy) - 1)
                    rows.append({
                        "group_code": group_code,
                        "section":    section,
                        "parameter":  row_label,
                        "unit":       unit,
                        "sort_order": sort + 0.5,
                        "actual":     actual_prior,
                        "cum_actual": cum_prior,
                        "month":      f"{want_mon}'{prior_yy}",
                        "cell":       f"PDF p{page_no} · {want_mon}'{prior_yy}",
                        "found_via":  f"DSP {section} (prior year)",
                        "status":     "ok",
                    })
            found = True
            break
        _ = found  # suppress unused warning
    return rows


# Product-name cell text drifted across report eras/table layouts — early
# (~2015-2017) reports used colon-suffixed/abbreviated labels ("STRLS :",
# "TMT BAR :", "W & A :"), and pdfplumber occasionally wraps a long product
# name across two lines in one cell (embedded "\n"), plus a handful of
# one-month column-shift glitches (all confined to 2022-03) that truncated
# the label entirely ("CC BILL", "CC Bloo", "CC Rou", "Structu"). None of
# these coexist in the same month as their canonical spelling below — a
# clean sequential handoff or an isolated one-off, not a genuinely distinct
# product. (Confirmed distinct and deliberately NOT in this map: "ASP" vs
# "ASP Structurals" vs "ASP : INGOT"→"Special Ingot" is folded in since
# those two share an identical 2015-09..2017-07 date range; "CC Round" vs
# "CC Round ASP" — both pairs coexist in the same months, so they're real,
# separate product lines, not label drift.)
_PRODUCT_NAME_MAP = {
    "CC BILL": "CC BILLET",
    "CC Bloo": "CC Bloom",
    "CC Rou": "CC Round",
    "Structu": "Structurals",
    "Structrals": "Structurals",
    "STRLS": "Structurals",
    "STRLS :": "Structurals",
    "STRLS :\n(MSM)": "Structurals",
    "(MSM)": "Structurals",
    "MSM": "Structurals",
    "TMT BAR :": "TMT",
    "TMT Bar": "TMT",
    "TMT Bars": "TMT",
    "W & A :": "W & A",
    "ASP : INGOT": "Special Ingot",
    "Rolled": "Rolled Bloom",
    "Rolled\nBloom": "Rolled Bloom",
    "Spl Steel\nto ASP": "Spl Steel to ASP",
    # Wrapped-cell newline artifacts on otherwise-distinct products.
    "ASP\nStructurals": "ASP Structurals",
    "CC Round\nASP": "CC Round ASP",
}


def _normalize_product_name(raw: str) -> str:
    return _PRODUCT_NAME_MAP.get(raw, raw)


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

    # Section is always the column immediately before the first period column —
    # but older reports (~2016-2017) insert extra "APP"/"Pro-rata" columns
    # between Quality/Grade and Section, shifting it right of a hardcoded
    # index 2. Deriving it from `start` keeps both layouts working.
    sec_ci = max(2, start - 1)

    rows = []
    cur_product = cur_grade = ""
    for row in tbl[period_row + 2:]:
        cells = ["" if c is None else str(c).strip() for c in row]
        if len(cells) <= max(c_ord, c_pro, c_des):
            continue
        col0, col1, col2 = cells[0], cells[1], cells[sec_ci]
        # A subtotal's "Total ..." label can land in either column — usually
        # col0, but sometimes col1 while col0 already holds the *next*
        # product group's name on the same row (e.g. mis1021.pdf row
        # ['TMT', 'Total Structurals', ...]). Check both independently
        # rather than picking whichever is non-blank first, or a real
        # product name sharing a row with a subtotal gets treated as the
        # subtotal's own label and the subtotal's figures get double-counted
        # as if they were a fresh line item.
        col0_is_total = bool(col0) and col0.upper().startswith("TOTAL")
        col1_is_total = bool(col1) and col1.upper().startswith("TOTAL")
        label0 = col0 if col0_is_total else (col1 if col1_is_total else (col0 or col1))
        # A per-grade subtotal row sometimes prints with no "Total ..." label
        # at all (just the summed figures) — e.g. DSP mis0523/mis0524.pdf,
        # grades like "SEQR 550D"/"E250 BR" where the row after all section
        # lines has product/grade/section all blank. A genuine data row
        # always carries at least a section value (even when product/grade
        # are blank continuation cells), so treat an all-blank identifier
        # row as a subtotal to avoid double-counting it as a real entry.
        is_total = col0_is_total or col1_is_total or (not col0 and not col1 and not col2)
        # col0 may introduce a new product group even on a total row (the
        # "TMT" in the example above) — only col1-as-grade is suppressed.
        if col0 and not col0_is_total:
            cur_product = _normalize_product_name(col0)
        if not is_total and col1:
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

    # DEBUG: Show page and content info
    import sys
    print(f"\n[DEBUG] ====== PDF PAGE EXTRACTION ======", file=sys.stderr)
    print(f"[DEBUG] PDF file: {file_path}", file=sys.stderr)
    print(f"[DEBUG] Extracting page: {page_no} (index {prod_page_idx})", file=sys.stderr)
    print(f"[DEBUG] Total lines on page: {len(lines)}", file=sys.stderr)
    print(f"[DEBUG] ====================================", file=sys.stderr)
    print(f"[DEBUG] ====== FULL PAGE CONTENT ======", file=sys.stderr)
    for i, ln in enumerate(lines):
        print(f"[DEBUG] Line {i:3d}: {ln}", file=sys.stderr)
    print(f"[DEBUG] ====== END FULL PAGE ======", file=sys.stderr)
    print(f"[DEBUG] ====================================\n", file=sys.stderr)

    month_cols = _month_header(lines)
    if not month_cols:
        print(f"[ERROR] Month header NOT found on page {page_no}!", file=sys.stderr)
        print(f"[ERROR] Page content sample:", file=sys.stderr)
        for i, ln in enumerate(lines[:20]):
            print(f"[ERROR]   {i}: {ln}", file=sys.stderr)
        raise ValueError(f"Month header row not found on page {page_no}. This may be the wrong page!")
    if want_mon not in month_cols:
        raise ValueError(
            f"Report month {want_mon}'{yy} not present in this PDF "
            f"(columns found: {', '.join(month_cols)}).")

    m_idx      = month_cols.index(want_mon)
    month_diff = len(month_cols) - 1 - m_idx

    # Find exact position of requested month in HEADER row (including aggregates)
    want_mon_header_pos = None
    header_row_text = None
    all_header_cols = None

    for ln in lines[:15]:
        toks = [t.upper().rstrip('.') for t in ln.split()]
        # Find header row: has months AND an aggregate column. Newer reports
        # end the row with "TOTAL"; older (~2015-2018) reports instead
        # interleave "Q1"/"Q2"/"H1" cumulative columns right after each
        # quarter (e.g. "APR MAY JUN Q1 JUL AUG SEP Q2 H1") with no "TOTAL"
        # at all - either way, the column position of the requested month
        # among ALL these columns (not just the month-only list) is what
        # matters, so any recognized aggregate label counts.
        has_months = any(m in toks for m in month_cols)
        has_aggregate = any(t in _AGGREGATE_TOKENS for t in toks)

        if has_months and has_aggregate:
            header_row_text = toks
            # Find position of first month
            first_month_pos = min((toks.index(m) for m in month_cols if m in toks), default=-1)
            if first_month_pos >= 0:
                all_header_cols = toks[first_month_pos:]  # All cols from first month onward
                # Find position of requested month in this list
                if want_mon in all_header_cols:
                    want_mon_header_pos = all_header_cols.index(want_mon)
                break

    # n_cols = total number of data columns (months + aggregates + cumulative)
    n_cols = len(all_header_cols) if all_header_cols else (len(month_cols) + 1)
    m_idx = want_mon_header_pos if want_mon_header_pos is not None else month_cols.index(want_mon)

    # DEBUG: Print header and month info
    import sys
    print(f"\n[DEBUG] ====== PDF COLUMN STRUCTURE ======", file=sys.stderr)
    print(f"[DEBUG] Month columns found: {month_cols}", file=sys.stderr)
    print(f"[DEBUG] All header columns (from first month): {all_header_cols}", file=sys.stderr)
    print(f"[DEBUG] Want month: {want_mon}", file=sys.stderr)
    print(f"[DEBUG] Position of {want_mon} in header: {m_idx}", file=sys.stderr)
    print(f"[DEBUG] Total data columns: {n_cols}", file=sys.stderr)
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
        if item is None:
            stripped = _strip_lead_digit(label)
            if stripped != label:
                for alias, name, conv in _ITEM_MAP:
                    if stripped == alias:
                        item, convert = name, conv
                        break

        # Count-type items (nos/day) are never tonnes — override any stale
        # alias/config convert flag so they are never divided by 1000.
        if item and "(nos" in item.lower():
            convert = False

        stored = round(val / 1000.0, 3) if (convert and item) else val
        rows.append({
            "item_name": item if item else f"(unmapped) {label}",
            "value":     stored if item else val,
            "unit":      "nos/day" if (item and not convert) else "'000T" if item else "T",
            "cell":      f"PDF p{page_no} · {want_mon}'{yy} col",
            "pdf_label": " ".join(label_toks),
            "status":    "ok" if item else "unmapped",
        })

    return rows, page_no, month_diff


def _block_production_all_months(file_path: str, prod_page_idx: int,
                                  report_month: str, y: int, yy: str,
                                  alias_lookup: dict, column_shift: int = 0):
    """Extract production data for ALL months in the report, not just the requested month.

    Args:
        report_month: Report month in YYYY-MM format (e.g., '2025-09')
        y, yy: Year as full and 2-digit integers
        Returns: (all_month_rows, page_no, month_diff)
               where all_month_rows has data for each month in the PDF header
    """
    import pdfplumber
    import sys

    with pdfplumber.open(file_path) as pdf:
        text = pdf.pages[prod_page_idx].extract_text() or ""

    lines = text.splitlines()
    page_no = prod_page_idx + 1

    # Find all months in header
    month_cols = _month_header(lines)
    if not month_cols:
        raise ValueError(f"Month header not found on page {page_no}")

    print(f"[DSP PDF] Extracting ALL months from header: {month_cols}", flush=True, file=sys.stderr)

    # Load item maps
    _ITEM_MAP, _SALEABLE_MAP = _load_maps()

    # Find full header row (with all columns including Q1, Q2, etc.)
    header_row_idx = None
    header_toks = None
    for i, ln in enumerate(lines[:15]):
        toks = [t.upper().rstrip('.') for t in ln.split()]
        if month_cols[0] in toks:
            header_row_idx = i
            header_toks = toks
            break

    if not header_toks:
        raise ValueError("Could not find full header row")

    # Map each month to its position in the header
    month_positions = {}
    for mon in month_cols:
        if mon in header_toks:
            month_positions[mon] = header_toks.index(mon)

    print(f"[DSP PDF] Month positions in header: {month_positions}", flush=True, file=sys.stderr)

    # Calculate FY based on report month
    # FY 2025-26 = April 2025 to March 2026
    # If report is March 2026 (2026-03): FY starts April 2025, so FY start year = 2025
    # If report is Sept 2025 (2025-09): FY starts April 2025, so FY start year = 2025
    report_month_num = int(report_month[5:7])
    fy_start_month = 4
    if report_month_num < fy_start_month:
        # Report in Jan-Mar: FY started previous calendar year
        fy_start_year = y - 1
    else:
        # Report in Apr-Dec: FY started this calendar year
        fy_start_year = y

    print(f"[DSP PDF] Report month: {report_month}, FY start year: {fy_start_year}", flush=True, file=sys.stderr)

    # Get first month position to use as anchor
    first_month_idx = min(month_positions.values()) if month_positions else 0

    # Process each data row once, extract ALL month columns
    all_rows = []
    for ln in lines:
        toks = ln.split()
        if not toks or len(toks) < 5:
            continue

        # Skip header rows
        if any(m in toks for m in month_cols) and toks[0].upper() in ['SL', 'NO']:
            continue

        # Extract all numbers from this row
        nums = []
        for t in reversed(toks):
            v = _num(t)
            if v is None:
                break
            nums.insert(0, v)

        if not nums or len(nums) < len(month_cols):
            continue

        # Trim to header size
        if len(nums) > len(header_toks):
            nums = nums[len(nums) - len(header_toks):]

        # Get item label
        label_toks = toks[:len(toks) - len(nums)]
        label = _norm(" ".join(label_toks))
        if not label:
            continue

        # For each month, extract from correct column position
        for mon_name in month_cols:
            # Calculate year for this month based on FY
            mon_num = _MONTHS.index(mon_name) + 1
            if mon_num >= fy_start_month:
                # April-Dec: same year as FY start
                mon_year = fy_start_year
            else:
                # Jan-Mar: next calendar year
                mon_year = fy_start_year + 1
            mon_str = f"{mon_year}-{mon_num:02d}"

            # Get column index for this month in header
            col_idx_in_header = month_positions.get(mon_name)
            if col_idx_in_header is None:
                continue

            # Offset from first month
            col_offset = col_idx_in_header - first_month_idx

            # Check bounds
            if col_offset < 0 or col_offset >= len(nums):
                continue

            val = nums[col_offset]

            # Map label to item
            item = None
            convert = True
            in_saleable = "SALEABLE" in label.upper() or "SEMIS" in label.upper()
            table = _SALEABLE_MAP if in_saleable else _ITEM_MAP
            for alias, name, conv in table:
                if label == alias:
                    item = name
                    convert = conv
                    break

            if item is None and in_saleable:
                for alias, name, conv in _ITEM_MAP:
                    if label == alias:
                        item, convert = name, conv
                        break

            if item is None:
                stripped = _strip_lead_digit(label)
                if stripped != label:
                    for alias, name, conv in _ITEM_MAP:
                        if stripped == alias:
                            item, convert = name, conv
                            break

            if item is None:
                item = label

            # Count-type items (nos/day) are never tonnes — never ÷1000
            if "(nos" in item.lower():
                convert = False

            # Convert units if needed
            if convert and isinstance(val, (int, float)):
                val = round(val / 1000.0, 3)

            all_rows.append({
                "report_month": mon_str,
                "plant_name": "DSP",
                "item_name": item,
                "month_actual": val,
                "value": val,
                "unit": "'000T" if convert else "T",
                "status": "ok" if item != label else "unmapped",
                "pdf_label": " ".join(label_toks),
                "cell": f"PDF p{page_no}",
            })

    print(f"[DSP PDF] ✓ Extracted ALL {len(month_cols)} months: {', '.join(month_cols)}",
          flush=True, file=sys.stderr)
    print(f"[DSP PDF] ✓ Total rows extracted: {len(all_rows)}", flush=True, file=sys.stderr)

    return all_rows, page_no, 0


# ---------------------------------------------------------------------------
# BF page 1 parser (Silicon, Sulphur, Slag Rate, BF Productivity)
# ---------------------------------------------------------------------------

def _parse_bf_page1(lines, pno, want_mon, yy, report_month_num):
    """Parse BF page 1: Silicon/Sulphur in HM, HM Temp, Slag Rate/Offtake, BF Productivity."""
    rows = []

    # BF page 1 uses two furnace-marker styles:
    #   "Furnace-II/III/IV" for Silicon, Sulphur, HM Temp (and their shop line)
    #   "B.F.-II/III/IV"    for Productivity
    _FF_MARKERS = [("furnace-ii", "BF-2"), ("furnace-iii", "BF-3"), ("furnace-iv", "BF-4")]
    _BF_MARKERS = [("b.f.-ii",   "BF-2"), ("b.f.-iii",   "BF-3"), ("b.f.-iv",   "BF-4")]

    _hpq = _prior_quarter_subtotal_present(lines, want_mon)
    has_prior_q = True if _hpq is None else _hpq

    def _append_row(group_code, section, param_label, param_unit, param_sort, ln):
        nums = _parse_te_nums(ln)
        if len(nums) < 3:
            return
        actual_curr, cum_curr, actual_prior, cum_prior = _te_values_techno(nums, report_month_num, has_prior_q)
        if actual_curr is not None:
            rows.append({
                "group_code": group_code, "section": section,
                "parameter":  param_label, "unit": param_unit,
                "sort_order": param_sort,
                "actual":     actual_curr, "cum_actual": cum_curr,
                "month":      f"{want_mon}'{yy}",
                "cell":       f"PDF p{pno} · {want_mon}'{yy}",
                "found_via":  f"DSP BF1 {param_label}", "status": "ok",
            })
            if actual_prior is not None:
                prior_yy = str(int(yy) - 1)
                rows.append({
                    "group_code": group_code, "section": section,
                    "parameter":  param_label, "unit": param_unit,
                    "sort_order": param_sort + 0.5,
                    "actual":     actual_prior, "cum_actual": cum_prior,
                    "month":      f"{want_mon}'{prior_yy}",
                    "cell":       f"PDF p{pno} · {want_mon}'{prior_yy}",
                    "found_via":  f"DSP BF1 {param_label} (prior)", "status": "ok",
                })

    # Markers ordered longest-first: "furnace-ii" is a substring of "furnace-iii",
    # so checking "furnace-iii" first prevents BF-3 rows from being mislabelled BF-2.
    _FF_ORDERED = [("furnace-iv", "BF-4"), ("furnace-iii", "BF-3"), ("furnace-ii", "BF-2")]

    def _ff_name(ln_low, after_heading):
        for marker, fname in _FF_ORDERED:
            if marker in ln_low:
                return fname
        if after_heading and "shop" in ln_low:
            if not re.search(r"(steel melting|blast furnace|coke oven|sinter)", ln_low):
                return "BF_Shop"
        return None

    # ── Furnace-wise params with first furnace inline on the heading line ──
    bf1_furnace_params = [
        (r"silicon in hm",          "IRON_MAKING", "Silicon in HM",           "%",    51),
        (r"sulphur in hm",          "IRON_MAKING", "Sulphur in HM",           "%",    61),
        (r"avg\.?.*hot metal temp", "IRON_MAKING", "Avg Hot Metal Temperature","°C",  65),
    ]

    for keyword, group_code, param_label, param_unit, param_sort in bf1_furnace_params:
        heading_idx = -1
        for i, ln in enumerate(lines):
            if re.search(keyword, ln.lower()):
                heading_idx = i
                break
        if heading_idx == -1:
            continue

        found_fnames = set()
        for i in range(heading_idx, min(heading_idx + 6, len(lines))):
            ln     = lines[i]
            ln_low = ln.lower()
            # Stop if we've entered the next parameter section (but not on the heading line)
            if i > heading_idx and re.search(r"in hm|productivity|slag rate|slag offtake", ln_low):
                break
            fname = _ff_name(ln_low, after_heading=(i > heading_idx))
            if fname and fname not in found_fnames:
                found_fnames.add(fname)
                _append_row(group_code, fname, param_label, param_unit, param_sort, ln)

    # ── Shop-only: Slag Rate, Slag Offtake ────────────────────────────────
    for keyword, param_label, param_unit, param_sort in [
        (r"slag rate",    "Slag Rate",    "kg/THM", 111),
        (r"slag offtake", "Slag Offtake", "%",       112),
    ]:
        for ln in lines:
            if re.search(keyword, ln.lower()):
                _append_row("IRON_MAKING", "BF_Shop", param_label, param_unit, param_sort, ln)
                break

    # ── BF Productivity (B.F.-II/III/IV/Shop format) ──────────────────────
    for prod_keyword, prod_label, prod_sort in [
        (r"productivity.*useful",  "BF Productivity (useful)",  1000),
        (r"productivity.*working", "BF Productivity (working)", 1001),
    ]:
        heading_idx = -1
        for i, ln in enumerate(lines):
            if re.search(prod_keyword, ln.lower()):
                heading_idx = i
                break
        if heading_idx == -1:
            continue

        # Also ordered longest-first to avoid "b.f.-ii" matching "b.f.-iii" lines
        _BF_ORDERED = [("b.f.-iv", "BF-4"), ("b.f.-iii", "BF-3"), ("b.f.-ii", "BF-2")]
        for i in range(heading_idx + 1, min(heading_idx + 8, len(lines))):
            ln     = lines[i]
            ln_low = ln.lower()
            # Stop at next Productivity section heading
            if re.search(r"productivity.*on.*(useful|working)", ln_low):
                break
            furnace_name = None
            for marker, fname in _BF_ORDERED:
                if marker in ln_low:
                    furnace_name = fname
                    break
            if furnace_name is None and "shop" in ln_low:
                furnace_name = "BF_Shop"
            if furnace_name:
                nums = _parse_te_nums(ln)
                if len(nums) >= 4:
                    actual_curr, cum_curr, actual_prior, cum_prior = _te_values_techno(nums, report_month_num, has_prior_q)
                    # Skip zero/None (furnace not operating)
                    if actual_curr is not None and actual_curr > 0:
                        rows.append({
                            "group_code": "IRON_MAKING", "section": furnace_name,
                            "parameter":  prod_label, "unit": "T/m³/day",
                            "sort_order": prod_sort,
                            "actual":     actual_curr, "cum_actual": cum_curr,
                            "month":      f"{want_mon}'{yy}",
                            "cell":       f"PDF p{pno} · {want_mon}'{yy}",
                            "found_via":  f"DSP BF1 {prod_label}", "status": "ok",
                        })

    return rows


# ---------------------------------------------------------------------------
# Block 2: Techno parameters
# ---------------------------------------------------------------------------

def _block_techno(file_path: str, page_index: dict,
                  want_mon: str, y: int, yy: str, month_diff: int,
                  page_texts_cache: dict = None) -> list:
    """Open PDF, read only the techno pages (by index), close, parse rows.

    Args:
        y: Full year (e.g., 2025) for FY calculation
        yy: 2-digit year string (e.g., '25') for display
        want_mon: Month name (e.g., 'SEP')
        month_diff: Column offset for month extraction
        page_texts_cache: {0-based page index: extract_text() result} already
            read by _scan_page_index's Pass 0 for these same section pages —
            reused instead of re-extracting (some pages take 10-20s+ each, so
            re-reading them is the difference between the request finishing
            and timing out). Pages not already in the cache still get read
            from the PDF as before.
    """
    import pdfplumber
    import sys

    # Calculate correct FY year (April=start, Jan-Mar=end of next year)
    report_month_num = _MONTHS.index(want_mon) + 1
    fy_start_month = 4
    if report_month_num < fy_start_month:
        fy_year = y - 1
    else:
        fy_year = y
    fy_year2 = fy_year + 1
    fy_label = f"{fy_year}-{fy_year2}"

    print(f"[DSP PDF] Techno: Month {want_mon}'{yy} → FY {fy_label}", flush=True, file=sys.stderr)

    techno_keys = ('major', 'sms', 'sms2', 'ccp', 'coke', 'sint', 'bf_main', 'bf_cdi', 'mm', 'wa')
    needed_idxs = {page_index[k] for k in techno_keys if k in page_index}

    if not needed_idxs:
        print(f"[DSP PDF] WARNING: No techno pages found! Returning 0 rows.",
              flush=True, file=sys.stderr)
        return []

    print(f"[DSP PDF] Techno: Found {len(needed_idxs)} pages, structure: [Norm | {want_mon}'25 | 2025-26 | {want_mon}'24 | 2024-25]",
          flush=True, file=sys.stderr)

    # Read only the specific pages we need; build a sparse page_texts list
    # (all other positions are empty strings so _find_page_by_heading still works
    # by index without touching unloaded pages). Pages Pass 0 already read are
    # reused from page_texts_cache rather than re-extracted from the PDF.
    page_texts_cache = page_texts_cache or {}
    missing_idxs = [idx for idx in needed_idxs if idx not in page_texts_cache]

    fresh_texts = {}
    if missing_idxs:
        with pdfplumber.open(file_path) as pdf:
            n_pages = len(pdf.pages)
            for idx in missing_idxs:
                if 0 <= idx < n_pages:
                    fresh_texts[idx] = pdf.pages[idx].extract_text() or ""
        n_pages_total = n_pages
    else:
        n_pages_total = max(needed_idxs) + 1

    page_texts = [""] * n_pages_total
    for idx in needed_idxs:
        if idx in page_texts_cache:
            page_texts[idx] = page_texts_cache[idx]
        elif idx in fresh_texts:
            page_texts[idx] = fresh_texts[idx]

    rows = []

    # ── Mill techno (MM/MSM and Wheel & Axle) ────────────────────────────
    # NOTE: Techno pages have FIXED structure (no month columns to detect):
    # [Norm | Current_Month_Actual | Current_FY_Cum | Prior_Month_Actual | Prior_FY_Cum]
    # Use offset=5 and month_diff=0 (always current month in these fixed columns)

    mm_idx = page_index.get('mm')
    if mm_idx is not None:
        text = page_texts[mm_idx]
        pno  = mm_idx + 1
        lines = text.splitlines()

        mm_lines  = _slice_text(text, "TE PARAMETERS - MERCHANT MILL",
                                 ["PRODUCTION - MSM", "TE PARAMETERS - MSM"])
        # For techno: use offset=5 (5 columns at right), month_diff=0 (current month)
        rows.extend(_parse_params_from_lines(
            mm_lines, "Merchant Mill", _MM_MSM_PARAMS["Merchant Mill"],
            pno, want_mon, yy, month_diff=0, offset=5, report_month_num=report_month_num))
        msm_lines = _slice_text(text, "TE PARAMETERS - MSM", [])
        rows.extend(_parse_params_from_lines(
            msm_lines, "MSM", _MM_MSM_PARAMS["MSM"],
            pno, want_mon, yy, month_diff=0, offset=5, report_month_num=report_month_num))

    wa_idx = page_index.get('wa')
    if wa_idx is not None:
        text = page_texts[wa_idx]
        pno  = wa_idx + 1

        wp_lines = _slice_text(text, "WHEEL PLANT", ["AXLE PLANT"])
        rows.extend(_parse_params_from_lines(
            wp_lines, "Wheel Plant", _WA_PARAMS["Wheel Plant"],
            pno, want_mon, yy, month_diff=0, offset=5, report_month_num=report_month_num))
        ap_lines = _slice_text(text, "AXLE PLANT", [])
        rows.extend(_parse_params_from_lines(
            ap_lines, "Axle Plant", _WA_PARAMS["Axle Plant"],
            pno, want_mon, yy, month_diff=0, offset=5, report_month_num=report_month_num))

    # ── Major techno + SMS ────────────────────────────────────────────────
    major_idx = page_index.get('major')
    if major_idx is not None:
        lines = page_texts[major_idx].splitlines()
        # For techno: use offset=5, month_diff=0
        rows.extend(_parse_general_params(
            lines, _MAJOR_PAGE_DEFS, major_idx + 1,
            want_mon, yy, month_diff=0, offset=5, report_month_num=report_month_num))

    sms_idx = page_index.get('sms')
    if sms_idx is not None:
        lines = page_texts[sms_idx].splitlines()
        rows.extend(_parse_general_params(
            lines, _SMS_PAGE_DEFS, sms_idx + 1,
            want_mon, yy, month_diff=0, offset=5, report_month_num=report_month_num))

    # ── SMS page 2 (Calcined Lime, Limestone, Si.Mn, Fe-Si, Fe-Mn …) ──────
    sms2_idx = page_index.get('sms2')
    if sms2_idx is not None:
        lines = page_texts[sms2_idx].splitlines()
        rows.extend(_parse_general_params(
            lines, _SMS2_PAGE_DEFS, sms2_idx + 1,
            want_mon, yy, month_diff=0, offset=5, report_month_num=report_month_num))

    # ── Continuous Casting Plant (Billet/Bloom/BRC Caster Yield) ──────────
    # TE PARAMETERS section repeats "Yield" under three sub-headers (Billet
    # Caster / Bloom Caster / Bloom cum Round Caster); the PRODUCTION section
    # higher on the same page also starts lines with these same names, so we
    # slice from "TE PARAMETERS" first to avoid matching the production rows.
    ccp_idx = page_index.get('ccp')
    if ccp_idx is not None:
        text = page_texts[ccp_idx]
        pno  = ccp_idx + 1
        te_text = "\n".join(_slice_text(text, "TE PARAMETERS", []))
        _ccp_hpq = _prior_quarter_subtotal_present(text.splitlines(), want_mon)
        ccp_has_prior_q = True if _ccp_hpq is None else _ccp_hpq
        for block_marker, next_marker, sort in (
            ("Billet Caster",         "Bloom Caster",           117),
            ("Bloom Caster",          "Bloom cum Round Caster", 118),
            ("Bloom cum Round Caster", None,                    119),
        ):
            block_lines = _slice_text(
                te_text, block_marker, [next_marker] if next_marker else [])
            for ln in block_lines[1:]:
                if "yield" in ln.lower():
                    nums = _parse_te_nums(ln)
                    actual_curr, cum_curr, _, _ = _te_values_techno(
                        nums, report_month_num, ccp_has_prior_q)
                    if actual_curr is not None:
                        rows.append({
                            "group_code": "MAJOR",
                            "section":    f"{block_marker} Yield",
                            "parameter":  "DSP SMS",
                            "unit":       "%",
                            "sort_order": sort,
                            "actual":     actual_curr,
                            "cum_actual": cum_curr,
                            "month":      f"{want_mon}'{yy}",
                            "cell":       f"PDF p{pno} · {want_mon}'{yy}",
                            "found_via":  f"DSP CCP {block_marker} Yield",
                            "status":     "ok",
                        })
                    break

        # "Total Caster-Heats per day" — the shop-level total of the CCP's
        # 4 casting machines' individual "M/c-N Heats per day" rows (those
        # per-machine rows are deliberately NOT extracted here — only the
        # total is a meaningful single figure). Mapped to the same
        # "average_blows_per_day" key other plants (RSP/BSP/ISP) already use
        # for their SMS shop's average blows/heats per day — DSP's PDF never
        # reported this parameter before. Verified present with identical
        # wording/spacing in every DSP report from 2018 onward; absent
        # (format didn't exist yet) in reports from 2017 and earlier, which
        # this simply skips (no row appended, same as any other line that
        # doesn't match).
        #
        # Unlike the Yield rows above, this one lives in the PRODUCTION
        # section (right after "Total Caster APP/Actual"), NOT under "TE
        # PARAMETERS" — so it's searched in the raw page `text`, not
        # `te_text`. It grows the same way as every other DSP "FY table" row
        # (one column per elapsed month, +1 at each quarter-end: [Apr, May,
        # Jun, Q1, Jul, Aug, Sep, Q2, Oct, Nov, Dec, Q3, Jan, Feb, Mar, Q4,
        # YTD, prior-year-same-month, prior-year-Q4, prior-FY-total] once the
        # whole FY has elapsed) — confirmed against the real column headers
        # in mis0525/mis0825/mis0326.pdf.
        #
        # Deliberately NOT using _te_values_techno here: its report_month==3
        # special case (len(nums) in (19,20)) is for a DIFFERENT DSP page
        # layout ("MAJOR page" rows) that happens to also reach 19-20 columns
        # by March — this row's true March columns (verified against
        # mis0326.pdf's actual header row) are [..., Mar, Q4, YTD, Mar-prior,
        # Q4-prior, FY-total-prior], i.e. actual=nums[-6]/cum=nums[-4], the
        # same generic quarter-end formula as every other month — so that
        # special case would misidentify nums[-4]/nums[-2] (YTD/Q4-prior)
        # as (actual/cum) instead. Verified: Apr(0)/May(1)/Jun(2)/Q1(3)/
        # Jul(4)/Aug(5)/Sep(6)/Q2(7)/Oct(8)/Nov(9)/Dec(10)/Q3(11)/Jan(12)/
        # Feb(13)/Mar(14)/Q4(15)/2025-26(16)/Mar'25(17)/Q4(18)/2024-25(19) —
        # nums[-6]=index14=Mar actual, nums[-4]=index16=YTD. Matches.
        is_quarter_end = report_month_num in (3, 6, 9, 12)
        quarter_end_with_prior_q = is_quarter_end and ccp_has_prior_q
        if is_quarter_end:
            min_len = 6 if ccp_has_prior_q else 5
        else:
            min_len = 4
        for ln in text.splitlines():
            if re.search(r'total\s*caster\s*-?\s*heats\s*per\s*day', ln, re.I):
                nums = _parse_te_nums(ln)
                if len(nums) >= min_len:
                    if quarter_end_with_prior_q:
                        actual_curr, cum_curr = nums[-6], nums[-4]
                    elif is_quarter_end:
                        actual_curr, cum_curr = nums[-5], nums[-3]
                    else:
                        actual_curr, cum_curr = nums[-4], nums[-3]
                elif report_month_num == 4 and len(nums) == 3:
                    # April is the FY's first month, so actual == YTD — most
                    # reports still carry a trailing prior-FY-total column
                    # even so (4 columns total, the general formula above
                    # handles it), but a few early years' reports (confirmed:
                    # mis0419.pdf) omit that column entirely: [Apr, YTD(=Apr),
                    # Apr-prior] only. Verified against mis0419.pdf's real
                    # row ("42.9 42.9 44.8"): actual=cum=42.9, prior=44.8.
                    actual_curr, cum_curr = nums[-3], nums[-2]
                else:
                    actual_curr = cum_curr = None
                if actual_curr is not None:
                    rows.append({
                        "group_code": "MAJOR",
                        "section":    "Average Blows Per Day",
                        "parameter":  "DSP SMS",
                        "unit":       "Ht./day",
                        "sort_order": 116,
                        "actual":     actual_curr,
                        "cum_actual": cum_curr,
                        "month":      f"{want_mon}'{yy}",
                        "cell":       f"PDF p{pno} · {want_mon}'{yy}",
                        "found_via":  "DSP CCP Total Caster-Heats per day",
                        "status":     "ok",
                    })
                break

    # ── Coke & Sinter ────────────────────────────────────────────────────
    coke_idx = page_index.get('coke')
    if coke_idx is not None:
        lines = page_texts[coke_idx].splitlines()
        rows.extend(_parse_general_params(
            lines, _COKE_PAGE_DEFS, coke_idx + 1,
            want_mon, yy, month_diff=0, offset=5, report_month_num=report_month_num))

    sint_idx = page_index.get('sint')
    if sint_idx is not None:
        sint_text = page_texts[sint_idx]
        sint_pno  = sint_idx + 1
        _sint_hpq = _prior_quarter_subtotal_present(sint_text.splitlines(), want_mon)
        sint_has_prior_q = True if _sint_hpq is None else _sint_hpq

        for label, marker, stop in [("DSP SP-1", "OLD MACHINE", ["NEW MACHINE"]),
                                     ("DSP SP-2", "NEW MACHINE", [])]:
            for ln in _slice_text(sint_text, marker, stop):
                if "productivity" in ln.lower():
                    nums = _parse_te_nums(ln)
                    # Use _te_values_techno (fixed-column structure, same as all techno pages)
                    actual_curr, cum_curr, actual_prior, cum_prior = _te_values_techno(nums, report_month_num, sint_has_prior_q)
                    if actual_curr is not None:
                        sort_base = 31 if label == "DSP SP-1" else 32
                        rows.append({
                            "group_code": "COKE_SINTER",
                            "section":    "Sinter Productivity",
                            "parameter":  label,
                            "unit":       "T/m²/hr",
                            "sort_order": sort_base,
                            "actual":     actual_curr,
                            "cum_actual": cum_curr,
                            "month":      f"{want_mon}'{yy}",
                            "cell":       f"PDF p{sint_pno} · {want_mon}'{yy}",
                            "found_via":  f"DSP Sinter {label}",
                            "status":     "ok",
                        })
                        if actual_prior is not None:
                            prior_yy = str(int(yy) - 1)
                            rows.append({
                                "group_code": "COKE_SINTER",
                                "section":    "Sinter Productivity",
                                "parameter":  label,
                                "unit":       "T/m²/hr",
                                "sort_order": sort_base + 0.5,
                                "actual":     actual_prior,
                                "cum_actual": cum_prior,
                                "month":      f"{want_mon}'{prior_yy}",
                                "cell":       f"PDF p{sint_pno} · {want_mon}'{prior_yy}",
                                "found_via":  f"DSP Sinter {label} (prior year)",
                                "status":     "ok",
                            })
                    break

    # ── BF page 1 (Silicon/Sulphur/HM Temp/Slag Rate/BF Productivity) ────
    bf_main_idx = page_index.get('bf_main')
    if bf_main_idx is not None:
        bf_main_lines = page_texts[bf_main_idx].splitlines()
        rows.extend(_parse_bf_page1(
            bf_main_lines, bf_main_idx + 1, want_mon, yy, report_month_num))

    # ── BF furnace-wise CDI ───────────────────────────────────────────────
    bf_idx = page_index.get('bf_cdi')
    if bf_idx is not None:
        bf_text = page_texts[bf_idx]
        bf_pno  = bf_idx + 1
        _bf_hpq = _prior_quarter_subtotal_present(bf_text.splitlines(), want_mon)
        bf_has_prior_q = True if _bf_hpq is None else _bf_hpq

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
                    actual_curr, cum_curr, actual_prior, cum_prior = _te_values_techno(nums, report_month_num, bf_has_prior_q)
                    if actual_curr is not None:
                        # Current year row
                        rows.append({
                            "group_code": "IRON_MAKING",
                            "section":    row_label,
                            "parameter":  "CDI",
                            "unit":       "Kg/THM",
                            "sort_order": sort,
                            "actual":     actual_curr,
                            "cum_actual": cum_curr,
                            "month":      f"{want_mon}'{yy}",
                            "cell":       f"PDF p{bf_pno} · {want_mon}'{yy}",
                            "found_via":  f"DSP BF CDI {row_label}",
                            "status":     "ok",
                        })
                        # Prior year row
                        if actual_prior is not None:
                            prior_yy = str(int(yy) - 1)
                            rows.append({
                                "group_code": "IRON_MAKING",
                                "section":    row_label,
                                "parameter":  "CDI",
                                "unit":       "Kg/THM",
                                "sort_order": sort + 0.5,
                                "actual":     actual_prior,
                                "cum_actual": cum_prior,
                                "month":      f"{want_mon}'{prior_yy}",
                                "cell":       f"PDF p{bf_pno} · {want_mon}'{prior_yy}",
                                "found_via":  f"DSP BF CDI {row_label} (prior year)",
                                "status":     "ok",
                            })
                    break
        # Shop-level CDI average: first numeric line not belonging to a specific furnace
        for ln in cdi_lines:
            if not any(m in ln.lower() for m in _fce_markers):
                nums = _parse_te_nums(ln)
                actual_curr, cum_curr, actual_prior, cum_prior = _te_values_techno(nums, report_month_num, bf_has_prior_q)
                if actual_curr is not None:
                    # Current year row
                    rows.append({
                        "group_code": "IRON_MAKING",
                        "section":    "DSP",
                        "parameter":  "CDI",
                        "unit":       "Kg/THM",
                        "sort_order": 11,
                        "actual":     actual_curr,
                        "cum_actual": cum_curr,
                        "month":      f"{want_mon}'{yy}",
                        "cell":       f"PDF p{bf_pno} · {want_mon}'{yy}",
                        "found_via":  "DSP BF CDI shop avg",
                        "status":     "ok",
                    })
                    # Prior year row
                    if actual_prior is not None:
                        prior_yy = str(int(yy) - 1)
                        rows.append({
                            "group_code": "IRON_MAKING",
                            "section":    "DSP",
                            "parameter":  "CDI",
                            "unit":       "Kg/THM",
                            "sort_order": 11.5,
                            "actual":     actual_prior,
                            "cum_actual": cum_prior,
                            "month":      f"{want_mon}'{prior_yy}",
                            "cell":       f"PDF p{bf_pno} · {want_mon}'{prior_yy}",
                            "found_via":  "DSP BF CDI shop avg (prior year)",
                            "status":     "ok",
                        })
                    break

    # ── Additional BF furnace-wise parameters ──────────────────────────────
    # Extract Silicon, Sulphur, Blast Temp, Sinter, Coke Rate, Nut Coke Rate
    if bf_idx is not None:
        bf_text = page_texts[bf_idx]
        bf_pno  = bf_idx + 1
        bf_lines = bf_text.splitlines()

        # Extract furnace-wise parameters
        for param_keyword, group_code, param_label, param_unit, param_sort in _BF_FURNACE_PARAMS:
            # Find the line with this parameter keyword
            param_start = -1
            for i, ln in enumerate(bf_lines):
                if param_keyword in ln.lower():
                    param_start = i
                    break

            if param_start == -1:
                continue

            # Extract furnace-wise and shop data from lines following this parameter
            for furnace_marker, furnace_label, _ in [
                ("furnace-ii",  "DSP BF-2", 0),
                ("furnace-iii", "DSP BF-3", 0),
                ("furnace-iv",  "DSP BF-4", 0),
            ]:
                # Look in next 20 lines for furnace marker
                for i in range(param_start + 1, min(param_start + 20, len(bf_lines))):
                    ln = bf_lines[i]
                    if furnace_marker in ln.lower():
                        nums = _parse_te_nums(ln)
                        if len(nums) >= 4:
                            actual_curr, cum_curr, actual_prior, cum_prior = _te_values_techno(nums, report_month_num, bf_has_prior_q)
                            if actual_curr is not None:
                                # Current year
                                rows.append({
                                    "group_code": group_code,
                                    "section":    furnace_label,
                                    "parameter":  param_label,
                                    "unit":       param_unit,
                                    "sort_order": param_sort,
                                    "actual":     actual_curr,
                                    "cum_actual": cum_curr,
                                    "month":      f"{want_mon}'{yy}",
                                    "cell":       f"PDF p{bf_pno} · {want_mon}'{yy}",
                                    "found_via":  f"DSP BF {param_label}",
                                    "status":     "ok",
                                })
                                # Prior year
                                if actual_prior is not None:
                                    prior_yy = str(int(yy) - 1)
                                    rows.append({
                                        "group_code": group_code,
                                        "section":    furnace_label,
                                        "parameter":  param_label,
                                        "unit":       param_unit,
                                        "sort_order": param_sort + 0.5,
                                        "actual":     actual_prior,
                                        "cum_actual": cum_prior,
                                        "month":      f"{want_mon}'{prior_yy}",
                                        "cell":       f"PDF p{bf_pno} · {want_mon}'{prior_yy}",
                                        "found_via":  f"DSP BF {param_label} (prior year)",
                                        "status":     "ok",
                                    })
                        break

            # Shop level for this parameter
            for i in range(param_start + 1, min(param_start + 20, len(bf_lines))):
                ln = bf_lines[i]
                if "shop" in ln.lower():
                    nums = _parse_te_nums(ln)
                    if len(nums) >= 4:
                        actual_curr, cum_curr, actual_prior, cum_prior = _te_values_techno(nums, report_month_num, bf_has_prior_q)
                        if actual_curr is not None:
                            # Current year
                            rows.append({
                                "group_code": group_code,
                                "section":    "DSP",
                                "parameter":  param_label,
                                "unit":       param_unit,
                                "sort_order": param_sort + 0.2,
                                "actual":     actual_curr,
                                "cum_actual": cum_curr,
                                "month":      f"{want_mon}'{yy}",
                                "cell":       f"PDF p{bf_pno} · {want_mon}'{yy}",
                                "found_via":  f"DSP BF {param_label} shop",
                                "status":     "ok",
                            })
                            # Prior year
                            if actual_prior is not None:
                                prior_yy = str(int(yy) - 1)
                                rows.append({
                                    "group_code": group_code,
                                    "section":    "DSP",
                                    "parameter":  param_label,
                                    "unit":       param_unit,
                                    "sort_order": param_sort + 0.7,
                                    "actual":     actual_prior,
                                    "cum_actual": cum_prior,
                                    "month":      f"{want_mon}'{prior_yy}",
                                    "cell":       f"PDF p{bf_pno} · {want_mon}'{prior_yy}",
                                    "found_via":  f"DSP BF {param_label} shop (prior year)",
                                    "status":     "ok",
                                })
                    break

        # Extract shop-only parameters (Slag Rate, Fuel Rate)
        for param_keyword, group_code, param_label, param_unit, param_sort in _BF_SHOP_PARAMS:
            for i, ln in enumerate(bf_lines):
                if param_keyword in ln.lower():
                    nums = _parse_te_nums(ln)
                    if len(nums) >= 4:
                        actual_curr, cum_curr, actual_prior, cum_prior = _te_values_techno(nums, report_month_num, bf_has_prior_q)
                        if actual_curr is not None:
                            # Current year
                            rows.append({
                                "group_code": group_code,
                                "section":    "DSP",
                                "parameter":  param_label,
                                "unit":       param_unit,
                                "sort_order": param_sort,
                                "actual":     actual_curr,
                                "cum_actual": cum_curr,
                                "month":      f"{want_mon}'{yy}",
                                "cell":       f"PDF p{bf_pno} · {want_mon}'{yy}",
                                "found_via":  f"DSP BF {param_label}",
                                "status":     "ok",
                            })
                            # Prior year
                            if actual_prior is not None:
                                prior_yy = str(int(yy) - 1)
                                rows.append({
                                    "group_code": group_code,
                                    "section":    "DSP",
                                    "parameter":  param_label,
                                    "unit":       param_unit,
                                    "sort_order": param_sort + 0.5,
                                    "actual":     actual_prior,
                                    "cum_actual": cum_prior,
                                    "month":      f"{want_mon}'{prior_yy}",
                                    "cell":       f"PDF p{bf_pno} · {want_mon}'{prior_yy}",
                                    "found_via":  f"DSP BF {param_label} (prior year)",
                                    "status":     "ok",
                                })
                    break

    print(f"[DSP PDF] Techno extraction complete: {len(rows)} rows extracted",
          flush=True, file=sys.stderr)
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
                    block: str = 'all', column_shift: int = 0, all_months: bool = False) -> dict:
    """Extract DSP data from the OMI PDF or Flash.pdf.

    Args:
        block: which sections to process ('all', 'production', 'techno', 'special_steel', 'stock')
        aliases: user-saved mapping {pdf_label: (item_name, convert_to_000T)}
        column_shift: adjust data column position (-1 for Sep'25 left-shifted layout)
        all_months: if True, extract ALL months from PDF; if False, extract only report_month

    No database writes — preview only.
    """
    if block == 'stock':
        return extract_preview_flash(file_path, report_month)

    import sys
    alias_lookup = {}
    for raw_label, (a_item, a_conv) in (aliases or {}).items():
        alias_lookup[_norm(raw_label)] = (a_item, bool(a_conv))

    # Extract actual PDF report month from first page
    try:
        actual_report_month = _extract_pdf_report_month(file_path)
        pdf_year, pdf_month = int(actual_report_month[:4]), int(actual_report_month[5:7])
        pdf_mon_name = _MONTHS[pdf_month - 1]
        print(f"[DSP PDF] PDF report month detected: {pdf_mon_name}'{str(pdf_year)[2:]} ({actual_report_month})",
              flush=True, file=sys.stderr)
    except Exception as e:
        print(f"[DSP PDF] ⚠ Could not detect PDF month from first page: {e}",
              flush=True, file=sys.stderr)
        actual_report_month = report_month
        pdf_year, pdf_month = int(report_month[:4]), int(report_month[5:7])
        pdf_mon_name = _MONTHS[pdf_month - 1]

    y, m    = int(report_month[:4]), int(report_month[5:7])
    want_mon = _MONTHS[m - 1]
    yy       = str(y)[2:]

    # Check if selected month matches PDF month
    month_mismatch = None
    if actual_report_month != report_month:
        month_mismatch = {
            "selected_month": report_month,
            "actual_month": actual_report_month,
            "message": f"Selected month {want_mon}'{yy} but PDF is for {pdf_mon_name}'{str(pdf_year)[2:]}. "
                       f"Extract from PDF's actual month instead?"
        }
        print(f"[DSP PDF] ⚠ Month mismatch: selected {report_month}, PDF is {actual_report_month}",
              flush=True, file=sys.stderr)

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
    page_index, page_texts_cache = _scan_page_index(file_path)
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

        if all_months:
            # Extract ALL months from the PDF
            print(f"[DSP PDF] MODE: All-months extraction", flush=True, file=sys.stderr)
            prod_rows, prod_page_no, month_diff = _block_production_all_months(
                file_path, page_index['prod'], report_month, y, yy, alias_lookup, column_shift=column_shift)
            mode_label = "all months"
        else:
            # Extract only the requested month (single-month mode)
            print(f"[DSP PDF] MODE: Single-month extraction for {want_mon}'{yy}", flush=True, file=sys.stderr)
            prod_rows, prod_page_no, month_diff = _block_production(
                file_path, page_index['prod'], want_mon, y, yy, alias_lookup, column_shift=column_shift)
            mode_label = "single month"

        gc.collect()
        ok_count = sum(1 for r in prod_rows if r["status"] == "ok")
        print(f"[DSP PDF] Block 1 done: {ok_count}/{len(prod_rows)} rows ok ({mode_label})",
              flush=True, file=sys.stderr)
        if not any(r["status"] == "ok" for r in prod_rows):
            raise ValueError("Production page found but no known items matched.")

    # ── Block 2: Techno parameters ────────────────────────────────────────
    techno_rows = []
    if run_tech:
        # need month_diff — derive from production page if we didn't run block 1
        if not run_prod and 'prod' in page_index:
            try:
                _prod_idx = page_index['prod']
                _txt = page_texts_cache.get(_prod_idx)
                if _txt is None:
                    import pdfplumber as _plumb
                    with _plumb.open(file_path) as _pdf:
                        _txt = _pdf.pages[_prod_idx].extract_text() or ""
                _mc = _month_header(_txt.splitlines())
                if _mc and want_mon in _mc:
                    month_diff = len(_mc) - 1 - _mc.index(want_mon)
            except Exception:
                month_diff = 0

        print("[DSP PDF] Block 2: techno parameters ...", flush=True, file=sys.stderr)
        try:
            techno_rows = _block_techno(file_path, page_index, want_mon, y, yy, month_diff,
                                         page_texts_cache=page_texts_cache)
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

    # TMI is a derived value (Hot Metal + Scrap Consumption), recomputed
    # centrally in db._maybe_recompute_derived_params on every save rather
    # than here — no "TMI" placeholder row exists in this PDF's own param
    # tables for calculate_tmi_consumption to fill in, so calling it here was
    # always a silent no-op.

    # ── Build result ──────────────────────────────────────────────────────
    sheets = f"PDF page {prod_page_no} (PRODUCTION MONTHWISE)"
    workbook_sheets = [f"PDF page {prod_page_no}"]
    if ss_page:
        sheets += f" + page {ss_page} (SPECIAL STEEL)"
        workbook_sheets.append(f"PDF page {ss_page}")

    return {
        "plant":               PLANT,
        "month":               report_month,
        "pdf_report_month":    actual_report_month,  # Actual month from PDF
        "month_mismatch":      month_mismatch,       # Warning if mismatch
        "source_type":         "DSP OMI PDF Report",
        "sheets":              sheets,
        "workbook_sheets":     workbook_sheets,
        "production_rows":     prod_rows,
        "special_steel_rows":  ss_rows,
        "special_steel_note":  ss_note,
        "techno_rows":         [],
        "techno_param_rows":   techno_rows,
    }
