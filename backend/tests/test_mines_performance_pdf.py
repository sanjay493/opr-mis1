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


def _segs(segments):
    return [(s["b"], s["start"], s["end"], s["new_page"]) for s in segments]


def test_paginate_all_fit():
    assert _segs(mpp.paginate([[10] * 3, [10] * 4], [["item"] * 3, ["item"] * 4], 100, 120, set())) == [
        (0, 0, 3, False), (1, 0, 4, False)]


def test_paginate_splits_to_fill_page():
    # 6 rows fit in the 65 left on page 1; the other 4 continue on page 2
    assert _segs(mpp.paginate([[10] * 10], [["item"] * 10], 65, 200, set())) == [
        (0, 0, 6, False), (0, 6, 10, True)]


def test_paginate_keeps_three_rows_on_each_side():
    # 9 rows would fit, but that leaves 1 for the next page: split after 7
    assert _segs(mpp.paginate([[10] * 10], [["item"] * 10], 95, 200, set())) == [
        (0, 0, 7, False), (0, 7, 10, True)]


def test_paginate_moves_block_when_fewer_than_three_rows_fit():
    assert _segs(mpp.paginate([[10] * 2, [10] * 8], [["item"] * 2, ["item"] * 8], 45, 200, set())) == [
        (0, 0, 2, False), (1, 0, 8, True)]


def test_paginate_does_not_end_a_part_on_a_heading():
    kinds = [["item", "item", "item", "item", "item", "heading", "item", "item", "item", "item"]]
    assert _segs(mpp.paginate([[10] * 10], kinds, 65, 200, set())) == [
        (0, 0, 5, False), (0, 5, 10, True)]


def test_paginate_forced_new_page_for_sail():
    assert _segs(mpp.paginate([[10] * 3, [10] * 3], [["item"] * 3, ["item"] * 3], 500, 500, {1})) == [
        (0, 0, 3, False), (1, 0, 3, True)]


def test_paginate_block_longer_than_a_page():
    assert _segs(mpp.paginate([[10] * 25], [["item"] * 25], 100, 100, set())) == [
        (0, 0, 10, False), (0, 10, 20, True), (0, 20, 25, True)]


def test_split_block_uses_short_name_on_each_part():
    data = {"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": [
        {"name": "Kiriburu", "short": "KBR", "kind": "mine", "group": "JGoM", "note": None,
         "rows": [_row(f"r{j}", "item", [1.0] * 11) for j in range(8)]},
        {"name": "Gua", "short": "GUA", "kind": "mine", "group": "JGoM", "note": None,
         "rows": [_row("g", "item", [1.0] * 11)]}]}
    segments = [{"b": 0, "start": 0, "end": 4, "new_page": False},
                {"b": 0, "start": 4, "end": 8, "new_page": True},
                {"b": 1, "start": 0, "end": 1, "new_page": False}]
    html = mpp.build_html(data, 0, COLORS, segments)
    assert html.count("<div>KBR</div>") == 2 and "Kiriburu" not in html
    assert "<div>Gua</div>" in html                       # not split: full name
    assert html.count('rowspan="4"') == 2
    assert html.count('<tbody class="blk" style="break-before: page">') == 1


def test_one_table_one_header_tbody_per_block():
    html = mpp.build_html(DATA, 0, COLORS)
    assert html.count("<table") == 1 and html.count("<thead>") == 1
    assert html.count('<tbody class="blk') == 2
    assert '<tbody class="blk sail">' in html                # SAIL continues on the same page
    assert "Coal and flux note." in html
    assert LABELS["title"] in html


def test_pdf_fills_pages_and_splits_mines_with_three_rows_each_side():
    """A real render: pages are filled to the printable height (a mine
    continues onto the next page), a split mine keeps at least 3 rows on
    each page, the column header repeats on every page, and SAIL continues
    on the page the last mine ends on."""
    import io

    import pdfplumber
    blocks = [{"name": f"M{i}", "short": f"S{i}", "kind": "mine", "group": "G", "note": None,
               "rows": [_row("I/ORE FRESH PRODUCTION", "heading")]
               + [_row(f"r{i}x{j}", "item", [float(j)] * 11) for j in range(9)]}
              for i in range(14)]
    blocks.append({"name": "SAIL", "short": "SAIL", "kind": "sail", "group": None, "note": None,
                   "rows": [_row("sailrow", "item", [1.0] * 11)]})
    pdf = mpp.render_pdf({"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": blocks}, 0, COLORS)
    with pdfplumber.open(io.BytesIO(pdf)) as d:
        words = [p.extract_words() for p in d.pages]
        height = d.pages[0].height
    pages = [set(w["text"] for w in ws) for ws in words]
    assert all("ITEM" in p for p in pages)
    sail_page = next(n for n, p in enumerate(pages) if "sailrow" in p)
    assert sail_page == len(pages) - 1 and "r13x8" in pages[sail_page]   # right after the last mine
    bottom_room = height - 7 / 25.4 * 72                    # page bottom less the 7 mm margin
    for n in range(len(pages) - 1):                         # every page but the last is full
        assert max(w["bottom"] for w in words[n]) > bottom_room - 50, f"page {n + 1} not filled"
    assert any(len({n for n, p in enumerate(pages) if any(f"r{i}x{j}" in p for j in range(9))}) > 1
               for i in range(14)), "no mine was split -- pages are not being filled"
    for i in range(14):
        per_page = [sum(f"r{i}x{j}" in p for j in range(9)) + ("I/ORE" in p and f"r{i}x0" in p)
                    for p in pages]
        parts = [c for c in per_page if c]
        if len(parts) > 1:
            assert min(parts) >= 3, f"mine M{i} split {parts}"


def test_frame_closes_at_each_page_end():
    """The black frame stops at the last row on each page -- it must not run
    on down the empty bottom of a page the table continues from."""
    import io

    import pdfplumber
    blocks = [{"name": f"M{i}", "kind": "mine", "group": "G", "note": None,
               "rows": [_row(f"r{i}x{j}", "item", [float(j)] * 11) for j in range(12)]}
              for i in range(8)]
    pdf = mpp.render_pdf({"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": blocks}, 0, COLORS)
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


def test_only_fy_plan_column_is_tinted():
    """Month and Apr-to-month Plan columns have no background; FY Plan keeps it."""
    import re
    html = mpp.build_html(DATA, 0, COLORS)
    row = re.search(r'<tr class="item">(.*?)</tr>', html).group(1)
    classes = re.findall(r'<td class="([^"]*)">', row)[1:]     # the 11 value cells
    assert classes[0] == "plan" and classes[1] == "" and classes[6] == ""
    head = html[html.index("<thead>"):html.index("</thead>")]
    assert head.count('class="plan"') == 1                    # only the FY Plan header


def test_choose_names_short_only_on_parts_too_short_for_the_full_name():
    segments = [{"b": 0, "start": 0, "end": 7, "new_page": False},
                {"b": 0, "start": 7, "end": 10, "new_page": True},
                {"b": 1, "start": 0, "end": 2, "new_page": False}]
    heights = [[15] * 10, [15] * 2]
    out = mpp.choose_names(segments, heights, [80, 80])
    # part 1: 105 px of rows holds the 80 px name; part 2: 45 px does not;
    # block 1 is not split, so it keeps its full name even though it is short
    assert [s["short"] for s in out] == [False, True, False]


def test_build_html_follows_each_segments_name_choice():
    data = {"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": [
        {"name": "Kiriburu", "short": "KBR", "kind": "mine", "group": "JGoM", "note": None,
         "rows": [_row(f"r{j}", "item", [1.0] * 11) for j in range(8)]}]}
    segments = [{"b": 0, "start": 0, "end": 5, "new_page": False, "short": False},
                {"b": 0, "start": 5, "end": 8, "new_page": True, "short": True}]
    html = mpp.build_html(data, 0, COLORS, segments)
    assert html.count("<div>Kiriburu</div>") == 1 and html.count("<div>KBR</div>") == 1
