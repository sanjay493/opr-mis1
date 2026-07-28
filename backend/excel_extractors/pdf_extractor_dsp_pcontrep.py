"""
DSP "pcontrep.pdf" extractor — Plant Control daily performance summary
(Hindi title: "डीएसपी/पीपीसीडी/प्लांट कंट्रोल दैनिक निष्पादन सारांश").

This is a PDF export of the same underlying control-room report the DSP
MCR-I text file ('mcr1_*.xls', see excel_extractor_dsp.py) comes from, just
with more columns (APP, monthly best, daily best, etc. alongside the ones
MCR-I already has) and, unlike MCR-I, no fixed row numbers to key off of —
pdfplumber's text layout isn't guaranteed stable line-to-line the way a
tab-separated file is. So rows are found by item-label text match instead,
and values by X-position within the row rather than by counting columns
left-to-right — several rows have a blank leading cell (e.g. "CC Blooms/BCB"
has no "Asking Rate"), which would silently misalign a plain
split-and-count parse.

Two tables share the page: "Production" (target column: "Monthly Rate",
except "Round Production" which mirrors MCR-I's exception and reads
"Actual To Date" instead — see excel_extractor_dsp.py's row-map docstring)
and "Despatch" (target column: also "Monthly Rate", but a different X
position — it's a separate table with its own two-line header). Column
positions are located at runtime from each table's own header (pairing each
upper-row header word with its nearest lower-row word — the standard
two-line header layout this report uses throughout) rather than hardcoded,
so minor font/rendering drift across report generations doesn't break it;
only the row-to-item label map below is assumed stable.

extract_preview() returns the same dict shape excel_extractor_dsp.py's
_mcr_preview() does — NO database writes; the frontend's confirm-extraction
flow persists whatever the user reviews and accepts.
"""
import re
from typing import Optional

NO_CONVERT = {"Oven Pushing (nos/day)"}

# (item_name, label to match in the row's leading text, which table block,
#  which target column). block: "production" | "despatch".
# column: "monthly_rate" (default) | "actual_to_date" (Round Production's
# MCR-I exception — its Monthly Rate cell is blank/0 in both formats).
_ITEM_ROWS = [
    ("Oven Pushing (nos/day)", "oven pushing", "production", "monthly_rate"),
    ("SP-1",                   "sinter plant-1", "production", "monthly_rate"),
    ("SP-2",                   "sinter plant-2", "production", "monthly_rate"),
    ("Total Sinter",           "total sinter", "production", "monthly_rate"),
    ("Hot Metal",              "hot metal", "production", "monthly_rate"),
    ("Pig Iron",               "pig iron", "production", "monthly_rate"),
    ("BILLET Caster",          "total cc billet", "production", "monthly_rate"),
    ("Bloom Caster ",          "cc bloom m/c-3", "production", "monthly_rate"),
    ("Round Production",       "cc round m/c-4", "production", "actual_to_date"),
    ("SMS Total Caster",       "total caster", "production", "monthly_rate"),
    ("BOTTOM_POURING_INGOT",   "bottom pouring", "production", "monthly_rate"),
    ("Total Crude Steel",      "total crude steel", "production", "monthly_rate"),
    ("MSM",                    "msm", "production", "monthly_rate"),
    ("MM",                     "merchant mill", "production", "monthly_rate"),
    ("WAP",                    "w&a", "production", "monthly_rate"),
    ("Saleable Semis",         "semi finished steel", "production", "monthly_rate"),
    ("Finished Steel",         "finished steel", "production", "monthly_rate"),
    ("Saleable Steel",         "total saleable steel", "production", "monthly_rate"),
    ("BILLET for Sale",        "cc billets", "despatch", "monthly_rate"),
    ("Blooms for Sale ",       "cc blooms/bcb", "despatch", "monthly_rate"),
    ("BRC",                    "cc bloom/brc", "despatch", "monthly_rate"),
]

_NUMERIC_RE = re.compile(r'^-?\d+(\.\d+)?a?$')
_DATE_RE = re.compile(r'(\d{2})\.(\d{2})\.(\d{4})')


def clean_val(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip()
    if s.endswith('a'):
        s = s[:-1]
    if s.lower() in ("nan", "###", "-", "#div/0!", ""):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def looks_like_pcontrep(file_path: str) -> bool:
    """Cheap format sniff so excel_extractor_dsp.py's PDF dispatch can tell
    this apart from the DSP monthly OMI PDF (pdf_extractor_dsp.py) — that
    one has a 'PRODUCTION MONTHWISE' page; this one is a single page with
    these column headers instead."""
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            text = (pdf.pages[0].extract_text() or "") if pdf.pages else ""
        text_low = text.lower()
        return "rate-mp" in text_low and "shop / items" in text_low
    except Exception:
        return False


def _cluster_rows(file_path: str) -> list:
    """Groups extracted words into visual rows by Y-position with a small
    tolerance (a few points) rather than exact-top matching — the 'a'
    suffix glyphs in this report render on a slightly different baseline
    than the surrounding digits, which splits an exact-top grouping into
    two rows for the same table line."""
    import pdfplumber
    with pdfplumber.open(file_path) as pdf:
        words = pdf.pages[0].extract_words(use_text_flow=False, keep_blank_chars=False)
    words.sort(key=lambda w: (w['top'], w['x0']))
    rows, cur, cur_top = [], [], None
    for w in words:
        if cur_top is None or abs(w['top'] - cur_top) <= 4:
            cur.append(w)
        else:
            rows.append(cur)
            cur = [w]
        cur_top = w['top']
    if cur:
        rows.append(cur)
    for r in rows:
        r.sort(key=lambda w: w['x0'])
    return rows


def _pair_header_columns(rows: list, upper_idx: int, lower_idx: int, threshold: float = 20.0) -> list:
    """Pairs each word in the upper header row with its nearest-X word in
    the lower header row (this report's headers are always two stacked
    lines, e.g. 'Monthly' / 'Rate'), producing a (label, x_center) per
    detected column. A word with no lower-row partner within `threshold`
    points is kept as its own single-word column (harmless — we only look
    up columns we actually need by substring match)."""
    upper, lower = rows[upper_idx], rows[lower_idx]
    used = set()
    pairs = []
    for uw in upper:
        best_i, best_dist = None, None
        for li, lw in enumerate(lower):
            if li in used:
                continue
            dist = abs(lw['x0'] - uw['x0'])
            if best_dist is None or dist < best_dist:
                best_i, best_dist = li, dist
        if best_i is not None and best_dist < threshold:
            lw = lower[best_i]
            used.add(best_i)
            label = f"{uw['text']} {lw['text']}".lower()
            xc = ((uw['x0'] + uw['x1']) / 2 + (lw['x0'] + lw['x1']) / 2) / 2
        else:
            label = uw['text'].lower()
            xc = (uw['x0'] + uw['x1']) / 2
        pairs.append((label, xc))
    return pairs


def _col_center(pairs: list, *substrings: str) -> Optional[float]:
    for label, xc in pairs:
        if all(s in label for s in substrings):
            return xc
    return None


def _row_label(row: list) -> str:
    """Leading non-numeric words of a row — the item name, however many
    words it spans (numbers start wherever the first numeric-looking
    token appears, so this works whether or not the row's first data
    cell — usually 'Asking Rate' — is blank)."""
    words = []
    for w in row:
        if _NUMERIC_RE.match(w['text']):
            break
        words.append(w['text'])
    return ' '.join(words).strip().lower()


def _find_row(rows: list, start: int, end: int, label: str) -> Optional[list]:
    """startswith, not exact-equal or plain substring — some item labels run
    straight into a trailing "(Nos)"/"(Tonne)" unit suffix with no space
    (e.g. the row text is literally 'pushing(Nos)' as one token), so 'oven
    pushing' wouldn't equal the full row label even though it's
    unambiguously that row. Plain substring is too loose, though: 'finished
    steel' is a substring of 'semi finished steel', which sits right above
    it — startswith excludes that false match while still tolerating the
    fused suffix case."""
    for r in rows[start:end]:
        if _row_label(r).startswith(label):
            return r
    return None


def _nearest_numeric(row: list, x_center: float) -> Optional[str]:
    candidates = [w for w in row if _NUMERIC_RE.match(w['text'])]
    if not candidates or x_center is None:
        return None
    best = min(candidates, key=lambda w: abs((w['x0'] + w['x1']) / 2 - x_center))
    return best['text']


def _extract(file_path: str) -> dict:
    """Shared parse used by both extract_preview() and (indirectly, via the
    preview→confirm-extraction flow) the save path. Returns
    {"report_month": "YYYY-MM", "values": {item_name: float or None}}."""
    rows = _cluster_rows(file_path)
    if not rows:
        raise ValueError("Empty PDF — could not extract any text.")

    date_match = _DATE_RE.search(rows[0][0]['text']) if rows[0] else None
    if not date_match:
        # Date may be split across words on the first line — fall back to
        # scanning all of its text.
        first_line = ' '.join(w['text'] for w in rows[0])
        date_match = _DATE_RE.search(first_line)
    if not date_match:
        raise ValueError(
            "Cannot find a DD.MM.YYYY date on the first line. "
            "Is this a DSP Plant Control report (pcontrep.pdf)?"
        )
    _d, m_num, year = date_match.groups()
    report_month = f"{year}-{m_num}"

    despatch_idx = next(
        (i for i, r in enumerate(rows) if r and r[0]['text'].strip().lower() == 'despatch'),
        len(rows),
    )
    # Production header is the two lines right after the date line;
    # despatch's is the two lines starting at despatch_idx.
    prod_pairs = _pair_header_columns(rows, 1, 2)
    desp_pairs = (
        _pair_header_columns(rows, despatch_idx, despatch_idx + 1)
        if despatch_idx < len(rows) else []
    )

    prod_monthly_rate_x = _col_center(prod_pairs, "monthly", "rate")
    prod_actual_to_date_x = _col_center(prod_pairs, "actual", "to")
    desp_monthly_rate_x = _col_center(desp_pairs, "monthly", "rate")

    if prod_monthly_rate_x is None:
        raise ValueError(
            "Could not locate the 'Monthly Rate' column in the Production table header. "
            "The report layout may have changed."
        )

    values = {}
    for item_name, label, block, column in _ITEM_ROWS:
        if block == "production":
            row = _find_row(rows, 0, despatch_idx, label)
            x_center = prod_actual_to_date_x if column == "actual_to_date" else prod_monthly_rate_x
        else:
            row = _find_row(rows, despatch_idx, len(rows), label)
            x_center = desp_monthly_rate_x
        raw = _nearest_numeric(row, x_center) if row is not None else None
        values[item_name] = clean_val(raw)

    return {"report_month": report_month, "values": values}


def extract_preview(file_path: str, report_month: str, aliases: dict = None,
                     block: str = 'all', **_ignored) -> dict:
    """Preview-only (no DB writes) — same return shape as
    excel_extractor_dsp.py's _mcr_preview(), so the frontend review UI
    doesn't need to know which of the two DSP formats produced it.
    `aliases`/`block`/any other kwarg are accepted for interface parity
    with the other DSP extractors but unused here (this report has a
    fixed, small item set — nothing to remap or section off)."""
    result = _extract(file_path)
    db_month = result["report_month"]

    rows = []
    for item_name, _label, _blk, _col in _ITEM_ROWS:
        raw_val = result["values"].get(item_name)
        val = raw_val
        if val is not None and item_name not in NO_CONVERT:
            val = round(val / 1000.0, 3)
        unit = "nos/d" if item_name in NO_CONVERT else "'000T"
        rows.append({
            "item_name": item_name,
            "value": val,
            "unit": unit,
            "cell": "",
            "pdf_label": item_name,
            "status": "ok" if val is not None else "no value",
        })

    return {
        "plant": "DSP",
        "month": db_month,
        "source_type": "DSP Plant Control Report (pcontrep.pdf)",
        "sheets": "pcontrep",
        "workbook_sheets": ["pcontrep"],
        "production_rows": rows,
        "special_steel_rows": [],
        "techno_rows": [],
        "techno_param_rows": [],
    }
