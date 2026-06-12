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
    ("pig iron",           "Pig Iron",             True),
    ("crude steel",        "Total Crude Steel",    True),
    ("bottom pouring",     "BOTTOM_POURING_INGOT", True),
    ("concast steel",      "Total Caster",         True),
    ("cc billet",          "BILLET Caster",        True),
    ("cc bloom",           "Bloom Caster ",        True),   # trailing space matches DB
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


def _find_production_page(pdf):
    """First page that has the heading AND a month header row
    (skips the index page, which also mentions 'Production Monthwise')."""
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if "PRODUCTION MONTHWISE" not in text.upper():
            continue
        lines = text.splitlines()
        if _month_header(lines):
            return i + 1, text
    return None, None


def extract_preview(file_path: str, report_month: str) -> dict:
    """Extract DSP production from the OMI PDF. Preview only — no DB writes."""
    import pdfplumber

    y, m = int(report_month[:4]), int(report_month[5:7])
    want_mon = _MONTHS[m - 1]

    with pdfplumber.open(file_path) as pdf:
        page_no, text = _find_production_page(pdf)

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
        label_toks = toks[:len(toks) - len(nums)]
        label = _norm(" ".join(label_toks))
        if not label:
            continue

        # value for the requested month
        if len(nums) >= n_cols:
            val = nums[m_idx]
        elif len(nums) > m_idx:
            val = nums[m_idx]
        else:
            continue

        item, convert = None, True
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

    return {
        "plant": PLANT,
        "month": report_month,
        "source_type": "DSP OMI PDF Report",
        "sheets": f"PDF page {page_no} (PRODUCTION MONTHWISE)",
        "workbook_sheets": [f"PDF page {page_no}"],
        "production_rows": rows,
        "techno_rows": [],
        "techno_param_rows": [],
    }
