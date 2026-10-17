"""mines_performance_pdf.build_html: block sections, SAIL page break, number
formatting, colours from the config, empty month."""
import mines_performance_pdf as mpp

COLORS = {"border_black": "#000000", "text_black": "#000000", "mines_perf_total_bg": "#ABCDEF",
          "perf_app_bg": "#FFF2CC", "perf_act_bg": "#C6EFCE", "perf_gr_bg": "#e2e8f0"}
LABELS = {"title": "Mines Production Performance :Sep'26 and Apr-Sep'26", "fy": "26-27",
          "month": "Sep'26", "cply": "Sep'25", "ytd": "Apr-Sep'26", "ytd_cply": "Apr-Sep'25"}


def _row(label, kind, vals=None, decimals=None):
    return {"label": label, "kind": kind, "values": vals or [None] * 11, "decimals": decimals}


DATA = {
    "labels": LABELS, "pct_idx": [3, 5, 8, 10],
    "blocks": [
        {"name": "Kiriburu", "kind": "mine", "group": "JGoM", "note": None, "rows": [
            _row("I/ORE FRESH PRODUCTION", "heading"),
            _row("Lump", "item", [1200.4, 100.0, 95.25, 95.25, 90.0, 5.8, 600.0, 570.0, 95.0, 550.0, 3.6]),
            _row("Total Fresh Production", "total", [1200.4, 100.0, 95.25, 95.25, 90.0, 5.8, 600.0, 570.0, 95.0, 550.0, 3.6]),
        ]},
        {"name": "SAIL", "kind": "sail", "group": None, "note": "Coal and flux note.", "rows": [
            _row("WASHERY", "heading"),
            _row("Yield (%)", "item", [40.0, 40.0, 45.0, 112.5, 40.0, 12.5, 41.0, 44.0, 107.3, 39.0, 12.8], decimals=1),
        ]},
    ],
}


def test_one_table_one_header_tbody_per_block():
    html = mpp.build_html(DATA, 0, COLORS)
    assert html.count("<table") == 1 and html.count("<thead>") == 1
    assert html.count('<tbody class="blk') == 2
    assert '<tbody class="blk sail">' in html
    assert "Coal and flux note." in html
    assert LABELS["title"] in html


def test_pdf_header_on_every_page_blocks_never_split():
    """A real render: the column header repeats at the top of every page
    (once, not per block), no block is split across pages, and the SAIL
    block starts a new page."""
    import io

    import pdfplumber
    blocks = [{"name": f"M{i}", "kind": "mine", "group": "G", "note": None,
               "rows": [_row("I/ORE FRESH PRODUCTION", "heading")]
               + [_row(f"r{i}x{j}", "item", [float(j)] * 11) for j in range(9)]}
              for i in range(14)]
    blocks.append({"name": "SAIL", "kind": "sail", "group": None, "note": None,
                   "rows": [_row("sailrow", "item", [1.0] * 11)]})
    pdf = mpp.render(mpp.build_html({"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": blocks}, 0, COLORS))
    with pdfplumber.open(io.BytesIO(pdf)) as d:
        pages = [set(w["text"] for w in p.extract_words()) for p in d.pages]
    assert len(pages) >= 3
    assert all("ITEM" in words for words in pages)
    for i in range(14):
        on = [n for n, words in enumerate(pages) if f"r{i}x0" in words or f"r{i}x8" in words]
        assert len(set(on)) == 1, f"block M{i} split across pages {on}"
    sail_page = next(n for n, words in enumerate(pages) if "sailrow" in words)
    assert not any(f"r{i}x0" in pages[sail_page] for i in range(14))


def test_frame_closes_at_each_page_end():
    """The black frame stops at the last row on each page -- it must not run
    on down the empty bottom of a page the table continues from."""
    import io

    import pdfplumber
    blocks = [{"name": f"M{i}", "kind": "mine", "group": "G", "note": None,
               "rows": [_row(f"r{i}x{j}", "item", [float(j)] * 11) for j in range(12)]}
              for i in range(8)]
    pdf = mpp.render(mpp.build_html({"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": blocks}, 0, COLORS))
    with pdfplumber.open(io.BytesIO(pdf)) as d:
        assert len(d.pages) >= 2
        for p in d.pages:
            black = [r for r in p.rects if tuple(r["non_stroking_color"] or ()) in ((0, 0, 0), (0,))]
            text_bottom = max(w["bottom"] for w in p.extract_words())
            assert max(r["bottom"] for r in black) - text_bottom < 8


def test_number_formatting():
    html = mpp.build_html(DATA, 2, COLORS)
    assert ">95.25<" in html            # quantity at 2 decimals
    assert ">95<" in html               # %Ful whole number
    assert ">45.0<" in html             # Yield quantity column at 1 decimal
    assert ">112<" in html or ">113<" in html


def test_colours_from_config():
    html = mpp.build_html(DATA, 0, COLORS)
    assert "#ABCDEF" in html


def test_header_cells_fit_their_columns():
    """Laid out at the A4 printable width (190 mm = 718 px), no header cell's
    text overflows its column -- 'APR-SEP'25 ACT.' / '%GR. APR-SEP'25' were
    being cropped in the narrow value columns."""
    from playwright.sync_api import sync_playwright
    html = mpp.build_html(DATA, 0, COLORS)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        p = b.new_page(viewport={"width": 718, "height": 1077})
        p.emulate_media(media="print")
        p.set_content(html, wait_until="load")
        clipped = p.evaluate("""() => [...document.querySelectorAll('th')]
            .filter(th => th.scrollWidth > th.clientWidth + 0.5).map(th => th.textContent)""")
        b.close()
    assert clipped == []


def _clipped_cells(html):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        p = b.new_page(viewport={"width": 718, "height": 1077})
        p.emulate_media(media="print")
        p.set_content(html, wait_until="load")
        clipped = p.evaluate("""() => [...document.querySelectorAll('td:not(.lbl):not(.ent)')]
            .filter(td => td.scrollWidth > td.clientWidth + 0.5).map(td => td.textContent)""")
        b.close()
    return clipped


def test_large_values_fit_at_three_decimals():
    """SAIL-sized figures (5 digits) at the maximum 3 decimals still fit."""
    big = [54772.123, 54772.123, 54772.123, 101.0, 54772.123, -12.0,
           54772.123, 54772.123, 101.0, 54772.123, 13.0]
    data = {"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": [
        {"name": "SAIL", "kind": "sail", "group": None, "note": None, "rows": [
            _row("Total", "total", big), _row("Lump", "item", big)]}]}
    assert _clipped_cells(mpp.build_html(data, 3, COLORS)) == []


def test_pdf_html_empty():
    html = mpp.build_html({"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": []}, 0, COLORS)
    assert "No mines data for Sep'26" in html
    assert "<section" not in html
