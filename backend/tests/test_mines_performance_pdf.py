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


def test_blocks_and_sail_break():
    html = mpp.build_html(DATA, 0, COLORS)
    assert html.count('<section class="blk') == 2
    assert '<section class="blk sail">' in html
    assert "break-before: page" in html
    assert "Coal and flux note." in html
    assert LABELS["title"] in html


def test_number_formatting():
    html = mpp.build_html(DATA, 2, COLORS)
    assert ">95.25<" in html            # quantity at 2 decimals
    assert ">95<" in html               # %Ful whole number
    assert ">45.0<" in html             # Yield quantity column at 1 decimal
    assert ">112<" in html or ">113<" in html


def test_colours_from_config():
    html = mpp.build_html(DATA, 0, COLORS)
    assert "#ABCDEF" in html


def test_pdf_html_empty():
    html = mpp.build_html({"labels": LABELS, "pct_idx": [3, 5, 8, 10], "blocks": []}, 0, COLORS)
    assert "No mines data for Sep'26" in html
    assert "<section" not in html
