"""
"Indian Steel Sector Performance" extractor — HTML variant. Fetches the
monthly PIB (Ministry of Steel) press release directly from its
PressReleasePage.aspx URL and parses the same 1a/1b/1c/2/3a/4a/5 tables and
6/7/8 narrative sections that pdf_extractor_steel_sector_performance.py
reads out of the PDF, so both entry paths (file upload, paste-a-URL) land
on the exact same preview shape and page_steel_sector_performance.py never
needs to know which source produced it.

Why parse HTML instead of reusing the PDF extractor on a fetched file: PIB
does not serve a PDF at this URL — the release is a normal HTML page (a
"Print"/"Download PDF" button on the page renders one client-side). The
page's real content is duplicated three times in the raw HTML (the visible
render, a hidden #PdfDiv used by that print button, and an HTML-escaped
copy inside a hidden field for social-share previews) — scoping every
lookup to the single div#innner-page-main-about-us-content-right-part
container (found by class, since BeautifulSoup handles the nesting) is
what keeps this to exactly one copy of each table/paragraph.

Table/section detection mirrors the PDF extractor: every heading (in its
own bordered <div> wrapping one <p>) is matched by its numbering prefix
("1a.", "1b.", ... "8.") rather than by color or position, because the
prefix is the one thing guaranteed stable month to month. Table dict shape,
row-grouping, footnote-splitting and the numeric 1a item list are NOT
reimplemented here — they're imported from pdf_extractor_steel_sector_
performance.py so a fix to that logic (e.g. a new footnote pattern) applies
to both extraction paths at once.

extract_preview_from_url() returns the same preview dict shape as
pdf_extractor_steel_sector_performance.extract_preview() — no DB writes;
the frontend's confirm-extraction flow persists whatever the user reviews
and accepts (see /api/steel-sector-performance/confirm in main.py).
"""
import re
import sys
import os

sys.path.append(os.path.dirname(__file__))
import pdf_extractor_steel_sector_performance as _pdf_mod

# Only PIB's own domain may be fetched server-side — this endpoint takes an
# arbitrary URL from the data-entry form, so without an allowlist it would
# be an open SSRF proxy (fetch-any-internal-or-external-URL-on-request).
_ALLOWED_HOSTS = {"pib.gov.in", "www.pib.gov.in"}

_TABLE_HEADINGS = _pdf_mod._TABLE_HEADINGS  # [(key, prefix), ...] — "1a." etc.
_TEXT_HEADINGS = _pdf_mod._TEXT_HEADINGS    # [("6","6."), ("7","7."), ("8","8.")]
_TABLE_KEYS = {k for k, _ in _TABLE_HEADINGS}
_TEXT_KEYS = {k for k, _ in _TEXT_HEADINGS}
_ALL_KEYS = _TABLE_KEYS | _TEXT_KEYS

_HEADING_RE = re.compile(r'^(\d[a-z]?)\.\s*(.*)$')
_NOTE_RE = _pdf_mod._NOTE_RE
_FOOTER_RE = _pdf_mod._FOOTER_RE

_CONTAINER_CLASS = "innner-page-main-about-us-content-right-part"


def _fetch_html(url: str) -> str:
    import requests
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError(
            "Only pib.gov.in press release URLs are supported "
            "(e.g. https://www.pib.gov.in/PressReleasePage.aspx?PRID=...)."
        )
    # PIB's edge filtering 403s anything with a recognizable bot/library
    # signature in the User-Agent (verified: a bare "python-requests" UA and
    # one naming this app both got 403; an ordinary browser UA gets 200) —
    # so this impersonates a normal browser rather than identifying itself.
    resp = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.text


def _clean_text(s) -> str:
    if s is None:
        return ""
    return re.sub(r'\s+', ' ', s).strip()


def _cell_text(tag):
    text = _clean_text(tag.get_text(" ", strip=True))
    return text if text else None


def _table_rows(table_tag):
    """Grid-extract every row as a flat list of cell values, ONE list entry
    per header column — the frontend's EditableTable and _group_table_rows
    (pdf_extractor_steel_sector_performance.py) both index row[i] against
    header[i] positionally, so a row must have exactly as many entries as
    the table has columns.

    A plain `tr.find_all('td', recursive=False)` breaks that for any row
    following a rowspan'd cell: e.g. table 3a's 'Imports'/'Exports' label
    cell carries rowspan="2" over its ('000 t / Rs Crore) sub-rows, so the
    second <tr> only has 7 real <td>s for an 8-column table — read naively,
    every later cell in that row silently shifts one column left (verified
    against a real release: Aug-26's value landed under Unit, CPLY% went
    blank). Tracking active rowspans (and colspan, for the header row's
    merged cells) and inserting a None placeholder for whichever column a
    still-active span occupies keeps every row's length == the column
    count, with a leading None meaning "still the previous row's label" —
    exactly what _group_table_rows already expects.
    """
    rows = []
    span_map = {}  # col_index -> remaining row-count still covered by a rowspan
    for tr in table_tag.find_all("tr"):
        if tr.find_parent("table") is not table_tag:
            continue  # a nested table's own row, not this table's
        cells = tr.find_all(["td", "th"], recursive=False)
        row = []
        real_values = []  # the actual <td> texts in order, ignoring None spacers
        col = 0
        ci = 0
        while ci < len(cells) or col in span_map:
            if col in span_map:
                row.append(None)
                span_map[col] -= 1
                if span_map[col] <= 0:
                    del span_map[col]
                col += 1
                continue
            cell = cells[ci]
            ci += 1
            try:
                colspan = max(1, int(cell.get("colspan", 1)))
            except (TypeError, ValueError):
                colspan = 1
            try:
                rowspan = max(1, int(cell.get("rowspan", 1)))
            except (TypeError, ValueError):
                rowspan = 1
            text = _cell_text(cell)
            real_values.append(text)
            for i in range(colspan):
                row.append(text if i == 0 else None)
                if rowspan > 1:
                    span_map[col + i] = rowspan - 1
            col += colspan

        # A row built from exactly TWO real <td>s (e.g. 3a's "Net Trade
        # Position" row: <td colspan="2">Net Trade Position</td><td
        # colspan="6">India was net importer...</td>) is a label + a wide
        # note, not ordinary data columns — but the label's own colspan
        # here is 2, not 1, so straight span-expansion above lands the note
        # text one column further right (under "Aug-26") than
        # _group_table_rows' wide_text heuristic and the report template's
        # renderer both hardcode ("label occupies column 0 only, note fills
        # column 1 through the end" — verified against SteelSectorPerformance
        # Template.js's `colSpan={headers.length - 1}` on `cells[0]`).
        # Re-pack to that canonical [label, note, None, None, ...] shape
        # regardless of how many columns the source colspan'd the label
        # over, so this renders identically to how the PDF path already
        # produces (and how a prior month's release rendered correctly).
        if len(real_values) == 2 and len(row) > 2:
            row = [real_values[0], real_values[1]] + [None] * (len(row) - 2)

        rows.append(row)
    return rows


def extract_preview_from_url(url: str, report_month: str, **_kwargs) -> dict:
    from bs4 import BeautifulSoup

    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_=_CONTAINER_CLASS)
    if container is None:
        raise ValueError(
            "Could not find the press release content on this page — verify "
            "the URL is a PIB 'PressReleasePage.aspx' link for the Ministry "
            "of Steel monthly release."
        )

    title_el = container.find(id="Titleh2")
    title = _clean_text(title_el.get_text(" ", strip=True)) if title_el else None

    posted_on = None
    date_el = container.find(id="PrDateTime")
    if date_el:
        posted_on = _clean_text(date_el.get_text(" ", strip=True)).replace("Posted On:", "").strip()

    # Every <p> (heading text, notes, running narrative) and every <table>,
    # in true document order, with <p>'s that live inside a <table> cell
    # filtered back out — find_all(['p','table']) is a single depth-first
    # walk so document order is preserved even after the filter.
    elements = container.find_all(["p", "table"])
    elements = [el for el in elements if el.name == "table" or el.find_parent("table") is None]

    tables_raw = {}          # key -> BeautifulSoup <table> tag
    heading_text = {}        # key -> the heading line as printed
    table_notes = {}         # key -> ["Note: ...", ...]
    text_paragraphs = {}     # key -> [paragraph, ...] for 6/7/8
    footer_note = None

    current_key = None
    done = False
    for el in elements:
        if done:
            break
        if el.name == "table":
            if current_key in _TABLE_KEYS and current_key not in tables_raw:
                tables_raw[current_key] = el
            continue

        text = _clean_text(el.get_text(" ", strip=True))
        if not text:
            continue

        m = _HEADING_RE.match(text)
        if m and m.group(1) in _ALL_KEYS and m.group(1) not in heading_text:
            current_key = m.group(1)
            heading_text[current_key] = text
            if current_key in _TEXT_KEYS:
                text_paragraphs[current_key] = []
            continue

        if _FOOTER_RE.match(text):
            footer_note = text
            done = True
            continue

        if current_key in _TABLE_KEYS and _NOTE_RE.match(text):
            table_notes.setdefault(current_key, []).append(text)
        elif current_key in _TEXT_KEYS:
            text_paragraphs[current_key].append(text)
        # else: a spacer ("&nbsp;") or stray line between sections — ignored

    missing_table_keys = [k for k in _TABLE_KEYS if k not in heading_text]
    if len(missing_table_keys) == len(_TABLE_KEYS):
        raise ValueError(
            "No known section headings (1a, 1b, 1c, 2, 3a, 4a, 5) found on "
            "this page — verify it is the 'Indian Steel Sector Performance' "
            "PIB release."
        )

    tables = {}
    for key, _prefix in _TABLE_HEADINGS:
        raw_tag = tables_raw.get(key)
        raw_rows = _table_rows(raw_tag) if raw_tag is not None else None
        table_dict = _pdf_mod._table_dict(raw_rows, heading_text.get(key))
        if table_dict is not None:
            table_dict["footnotes"].extend(table_notes.get(key, []))
        tables[key] = table_dict

    production_overview_1a_items = _pdf_mod._extract_production_overview_items(tables.get("1a"))
    if not production_overview_1a_items:
        raise ValueError(
            "Table 1a (Production Overview) not found or empty — cannot "
            "build the report's SAIL-share table without it."
        )

    text_sections = {}
    for key, _prefix in _TEXT_HEADINGS:
        text_sections[key] = {
            "heading": heading_text.get(key),
            "paragraphs": text_paragraphs.get(key, []),
        }

    return {
        "report_month": report_month,
        "source_type": "Indian Steel Sector Performance (PIB, Ministry of Steel)",
        "title": title,
        "posted_on": posted_on,
        "tables": tables,
        "production_overview_1a_items": production_overview_1a_items,
        "text_sections": text_sections,
        "footer_note": footer_note,
        "source_url": url,
    }
