"""
"Indian Steel Sector Performance" extractor — the monthly PIB (Ministry of
Steel) press release (Report_format/"Indian Steel Sector Performance in
<Mon>'<YY>.pdf"), reproduced as pages 2.1-2.4 of the report (see
page_steel_sector_performance.py).

The release is a fixed-template document (same section numbering every
month: 1a/1b/1c under "1. Steel Production & Prices", "2. Demand", "3a"
under "3. Trade Dynamics", "4a" under "4. Raw Materials", "5. Key Indices",
then free-text sections "6. Policy Initiatives...", "7. International
Co-operation", "8. Green Steel Initiatives") but the exact page each section
lands on can drift month to month, so sections are located by their own
heading text rather than by a fixed page/position — same anchor-by-label
approach sail_sales_stock_extractor.py uses for "A. SALES"/"D. STOCK".

pdfplumber's extract_tables() grid-extracts every table on this PDF cleanly
(verified against a real file), so — unlike pdf_extractor_dsp_pcontrep.py's
border-less report — no word-clustering/X-position heuristics are needed:
each table heading is matched to the next table pdfplumber finds on that
page, in document order.

Storage philosophy (matches sail_sales_table's data_json): every table is
kept EXACTLY as printed (headers + row cells, no reshaping) under "tables",
so a future month's slightly different wording/column set still archives
correctly and the report page can always reproduce the source verbatim.
Table 1a additionally gets a normalized "production_overview_1a_items" list
with the user-facing generic column names (report_month, cply_month,
apr_report_month, cply_apr_report_month, yoy_pct, cply_pct) as floats —
this is the one table page_steel_sector_performance.py does real math
against (adding SAIL rows + SAIL share %), so it needs typed values, not
just archived strings.

extract_preview() returns a preview dict — NO database writes; the
frontend's confirm-extraction flow persists whatever the user reviews and
accepts (see /api/steel-sector-performance/confirm in main.py).
"""
import re

_PARA_GAP_THRESHOLD = 9.0  # points; within-paragraph line gap is ~5, between-paragraph ~13+

# (key, heading prefix to match at the start of a line) — order matters: this
# is also the document order the sections normally appear in, used to slice
# each heading's own text block from the next one's start.
_TABLE_HEADINGS = [
    ("1a", "1a."), ("1b", "1b."), ("1c", "1c."),
    ("2", "2. Demand"),
    ("3a", "3a."),
    ("4a", "4a."),
    ("5", "5. Key Indices"),
]
_TEXT_HEADINGS = [
    ("6", "6."), ("7", "7."), ("8", "8."),
]
_ALL_HEADINGS = _TABLE_HEADINGS + _TEXT_HEADINGS

_ITEM_LABELS_1A = ["Crude Steel", "Hot Metal", "Finished Steel"]

# Trailing boilerplate that sometimes shares a text line with real content
# on the last text section (e.g. "Source: Provisional JPC data...") — cut
# off there rather than folding it into section 8's last paragraph.
_FOOTER_RE = re.compile(r'^Source:\s*Provisional JPC data', re.IGNORECASE)

# A free-standing "Note: ..." paragraph under a table (e.g. 1c's "Note:
# Prices are inclusive of GST...") isn't part of pdfplumber's table grid at
# all — it's ordinary body text sitting between the table and the next
# heading — so it needs a separate text-based pass, not the row-shape
# heuristic _is_footnote_row() uses for a trailing row like 1b's "Top 7
# includes...".
_NOTE_RE = re.compile(r'^Note\s*:', re.IGNORECASE)


def _clean_num(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = s.replace("₹", "").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _norm_cell(v):
    """For the verbatim 'tables' archive: collapse embedded newlines
    (multi-line header/label cells) to a single space, keep everything
    else exactly as pdfplumber returned it."""
    if v is None:
        return None
    return re.sub(r'\s+', ' ', str(v)).strip()


def _load_pages(file_path):
    import pdfplumber
    pdf = pdfplumber.open(file_path)
    pages = []
    for page in pdf.pages:
        pages.append({
            "lines": page.extract_text_lines(),
            "tables": page.extract_tables(),
        })
    pdf.close()
    return pages


def _find_heading_positions(pages):
    """Returns {key: (page_idx, line_idx)} for every heading found."""
    found = {}
    for pi, page in enumerate(pages):
        for li, line in enumerate(page["lines"]):
            text = line["text"].strip()
            for key, prefix in _ALL_HEADINGS:
                if key in found:
                    continue
                if text.startswith(prefix):
                    found[key] = (pi, li)
    return found


def _map_tables_to_headings(pages, positions, table_keys):
    """Zips table headings to tables strictly by document order across the
    WHOLE pdf (not per-page): a heading's own table sometimes renders on
    the NEXT physical page (e.g. '1c. Steel Prices' sits at the bottom of
    page 1 but its table starts page 2), so matching must not assume same-
    page placement. Relies on every table heading having exactly one table
    of its own, in the same relative order they're printed — true for this
    fixed-template report (verified: 7 table headings, 7 tables found,
    same order, on a real file)."""
    ordered_keys = sorted(
        (k for k in table_keys if k in positions),
        key=lambda k: positions[k],
    )
    all_tables = [t for page in pages for t in page["tables"]]
    return {k: all_tables[i] for i, k in enumerate(ordered_keys) if i < len(all_tables)}


def _is_footnote_row(row):
    """A row where only the first cell is populated (e.g. 1b's 'Top 7
    includes SAIL, RINL, NSL, ...' line) is a footnote pdfplumber pulled in
    as part of the table grid, not a real data row — split it out so it
    prints as a footnote under the table instead of a table row full of
    dashes. Generic (not 1b-specific) since any table in a future month's
    release could carry the same trailing-note pattern."""
    return bool(row and row[0]) and all(c is None for c in row[1:])


def _group_table_rows(data_rows):
    """Groups consecutive rows that share one leading-column label into a
    single row-group — e.g. 3a reports Imports/Exports as TWO rows each
    ('000 t, then Rs Crore), with the label only present on the first; a
    blank leading cell means "still the previous row's label", so those
    rows get grouped under it (rendered with the label cell rowspan'd
    across the group instead of repeated/blank).

    A group of exactly one row whose 2nd cell holds text while every cell
    after it is empty (e.g. 3a's 'Net Trade Position' -> 'India was net
    importer...' line) is flagged wide_text=True so the renderer can print
    that cell spanning the rest of the row instead of as an ordinary
    column value trailed by dashes.

    Generic across every table (not 3a-specific) — a table with no such
    blank-leading-cell rows just yields one single-row group per row,
    identical to the unmerged rendering used before this existed.

    Returns: [{"label": str|None, "cells": [[tail...], ...], "wide_text": bool}]
    """
    groups = []
    for row in data_rows:
        tail = list(row[1:]) if row else []
        if row and row[0] is not None:
            groups.append({"label": row[0], "cells": [tail]})
        elif groups:
            groups[-1]["cells"].append(tail)
        else:
            groups.append({"label": None, "cells": [tail]})
    for g in groups:
        only_row = g["cells"][0] if len(g["cells"]) == 1 else None
        g["wide_text"] = bool(
            only_row and only_row and only_row[0] not in (None, "")
            and all(c is None for c in only_row[1:])
        )
    return groups


def _table_dict(raw_table, heading_text):
    if not raw_table:
        return None
    rows = [[_norm_cell(c) for c in row] for row in raw_table]
    headers, *body = rows
    data_rows = [r for r in body if not _is_footnote_row(r)]
    footnotes = [r[0] for r in body if _is_footnote_row(r)]
    return {
        "heading": heading_text,
        "headers": headers,
        "rows": data_rows,
        "row_groups": _group_table_rows(data_rows),
        "footnotes": footnotes,
    }


def _heading_text(pages, positions, key):
    if key not in positions:
        return None
    pi, li = positions[key]
    return pages[pi]["lines"][li]["text"].strip()


def _extract_production_overview_items(table_1a):
    """table_1a's rows -> the normalized, math-ready item list. Column
    order is fixed on this report (label, report month, CPLY month, YoY%,
    Apr-report cum, CPLY Apr-report cum, CPLY%) — mapped by POSITION, not by
    parsing the month name out of the header, since the header text (e.g.
    'Jul 2026') changes every month but the column order does not."""
    if not table_1a:
        return []
    items = []
    for row in table_1a["rows"]:
        if not row or not row[0]:
            continue
        label = row[0].strip()
        cells = row[1:8]
        while len(cells) < 6:
            cells.append(None)
        items.append({
            "item": label,
            "report_month": _clean_num(cells[0]),
            "cply_month": _clean_num(cells[1]),
            "yoy_pct": _clean_num(cells[2]),
            "apr_report_month": _clean_num(cells[3]),
            "cply_apr_report_month": _clean_num(cells[4]),
            "cply_pct": _clean_num(cells[5]),
        })
    return items


def _text_block(pages, positions, key, next_key):
    """Lines strictly between heading `key` (exclusive) and the next known
    heading `next_key` (exclusive), or end of document if there is none."""
    if key not in positions:
        return []
    start_pi, start_li = positions[key]
    end = positions.get(next_key) if next_key else None

    out = []
    for pi in range(start_pi, len(pages)):
        lines = pages[pi]["lines"]
        for li, line in enumerate(lines):
            if pi == start_pi and li <= start_li:
                continue
            if end is not None and (pi, li) >= end:
                return out
            out.append(line)
    return out


def _paragraphs_from_lines(lines):
    """Groups wrapped lines into paragraphs using the vertical gap between
    consecutive lines — within a paragraph the gap is ~5pt (single line
    spacing), between paragraphs ~13pt+ (verified against this report's own
    layout). Stops at the footer 'Source: Provisional JPC data...' line
    rather than folding it into the last paragraph."""
    paras, cur, prev_bottom = [], [], None
    for line in lines:
        text = line["text"].strip()
        if not text:
            continue
        if _FOOTER_RE.match(text):
            break
        gap = None if prev_bottom is None else line["top"] - prev_bottom
        if cur and gap is not None and gap > _PARA_GAP_THRESHOLD:
            paras.append(" ".join(cur))
            cur = []
        cur.append(text)
        prev_bottom = line["bottom"]
    if cur:
        paras.append(" ".join(cur))
    return paras


def _next_heading_key(positions, key):
    """The heading that comes right after `key` in overall document order
    (across BOTH table and text headings, not just table ones) — used to
    bound the search for a free-text 'Note:' paragraph sitting between a
    table and whatever section follows it."""
    ordered = sorted(positions.keys(), key=lambda k: positions[k])
    idx = ordered.index(key)
    return ordered[idx + 1] if idx + 1 < len(ordered) else None


def _table_note_footnotes(pages, positions, key):
    """Any 'Note: ...' paragraph (with wrapped continuation lines) sitting
    between table `key`'s heading and the next heading anywhere in the
    document — e.g. 1c's 'Note: Prices are inclusive of GST...'. Generic
    across every table key, not just 1c, since a future month's release
    could carry the same kind of note under a different table."""
    if key not in positions:
        return []
    next_key = _next_heading_key(positions, key)
    lines = _text_block(pages, positions, key, next_key)
    return [p for p in _paragraphs_from_lines(lines) if _NOTE_RE.match(p)]


def _footer_note(pages):
    """The 'Source: Provisional JPC data...' legend line, joined with its
    wrapped continuation line(s) (small line-gap = still the same
    paragraph), stopping before the unrelated signature block ('****',
    'AG', release-id line) that follows it with a larger gap."""
    for page in pages:
        lines = page["lines"]
        for i, line in enumerate(lines):
            if not _FOOTER_RE.match(line["text"].strip()):
                continue
            parts = [line["text"].strip()]
            prev_bottom = line["bottom"]
            for cont in lines[i + 1:]:
                gap = cont["top"] - prev_bottom
                if gap > _PARA_GAP_THRESHOLD:
                    break
                parts.append(cont["text"].strip())
                prev_bottom = cont["bottom"]
            return " ".join(parts)
    return None


def extract_preview(file_path: str, report_month: str, **_kwargs) -> dict:
    """Extract every numbered table (1a/1b/1c/2/3a/4a/5) and every
    narrative text section (6/7/8) from the monthly PIB steel-sector
    release. Returns a preview dict — no DB writes.
    """
    pages = _load_pages(file_path)
    if not pages:
        raise ValueError("Could not read any pages from the PDF.")

    positions = _find_heading_positions(pages)
    table_keys = [k for k, _ in _TABLE_HEADINGS]
    missing = [k for k in table_keys if k not in positions]
    if len(missing) == len(table_keys):
        raise ValueError(
            "No known section headings (1a, 1b, 1c, 2, 3a, 4a, 5) found — "
            "verify this is the 'Indian Steel Sector Performance' PIB release."
        )

    table_for_key = _map_tables_to_headings(pages, positions, table_keys)
    tables = {}
    for key, _prefix in _TABLE_HEADINGS:
        heading_text = _heading_text(pages, positions, key)
        tables[key] = _table_dict(table_for_key.get(key), heading_text)
        if tables[key] is not None:
            tables[key]["footnotes"].extend(_table_note_footnotes(pages, positions, key))

    production_overview_1a_items = _extract_production_overview_items(tables.get("1a"))
    if not production_overview_1a_items:
        raise ValueError(
            "Table 1a (Production Overview) not found or empty — cannot "
            "build the report's SAIL-share table without it."
        )

    text_sections = {}
    ordered_text_keys = [k for k, _ in _TEXT_HEADINGS]
    for i, (key, _prefix) in enumerate(_TEXT_HEADINGS):
        next_key = ordered_text_keys[i + 1] if i + 1 < len(ordered_text_keys) else None
        lines = _text_block(pages, positions, key, next_key)
        text_sections[key] = {
            "heading": _heading_text(pages, positions, key),
            "paragraphs": _paragraphs_from_lines(lines),
        }

    title_line = pages[0]["lines"][1]["text"].strip() if len(pages[0]["lines"]) > 1 else None
    title2_line = pages[0]["lines"][2]["text"].strip() if len(pages[0]["lines"]) > 2 else ""
    title = f"{title_line} {title2_line}".strip() if title_line else None
    posted_on = None
    for line in pages[0]["lines"][:6]:
        if line["text"].strip().startswith("Posted On:"):
            posted_on = line["text"].strip().replace("Posted On:", "").strip()
            break

    return {
        "report_month": report_month,
        "source_type": "Indian Steel Sector Performance (PIB, Ministry of Steel)",
        "title": title,
        "posted_on": posted_on,
        "tables": tables,
        "production_overview_1a_items": production_overview_1a_items,
        "text_sections": text_sections,
        "footer_note": _footer_note(pages),
    }
