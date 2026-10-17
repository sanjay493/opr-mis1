"""A4 PDF of the Mines Production Performance report
(mines_performance.generate) for /reports/mines. Pages 5-6 columns, with the
fonts and border rules of plant_performance_pdf.py: separate borders, each
cell drawing only its right edge -- no light line between rows; black rules
above section headings and totals. One table, its header repeated at the top
of every page. Not part of the layout-guarded monthly report. Colours come
from colors_config.json.

Pages are filled to the printable height (per direct instruction): a mine
continues onto the next page rather than starting a new one. Chromium will
not split the tall vertical-name cell (a rowspan) across pages, so the
pagination is done here instead -- render_pdf measures every row in
Chromium, paginate() decides where each page ends (at least 3 of a mine's
rows on each side of a break, never a part ending on a heading), and each
part becomes its own <tbody> with its own name cell, the short name
(KBR, MBR, ...) on every part of a split mine. The SAIL block starts a new
page."""
from html import escape

from plant_performance_pdf import _fonts, _p, _q

_MARGIN = {"top": "7mm", "right": "10mm", "bottom": "7mm", "left": "10mm"}

# value index -> column tint (pages 5-6: Plan gold, Actual green, %Gr grey)
_PLAN, _ACT, _GR = {0, 1, 6}, {2, 7}, {5, 10}


def _cls(vi: int) -> str:
    return "plan" if vi in _PLAN else "act" if vi in _ACT else "gr" if vi in _GR else ""


def _head(L: dict) -> str:
    return (
        '<thead><tr><th rowspan="2" class="ent"></th><th rowspan="2" class="l">Item</th>'
        f'<th rowspan="2" class="plan">{L["fy"]}<br>Plan</th><th colspan="3">{L["month"]}</th>'
        f'<th rowspan="2" class="sm">{L["cply"]}<br>Act.</th><th rowspan="2" class="gr sm">%Gr.<br>{L["cply"]}</th>'
        f'<th colspan="3">{L["ytd"]}</th><th rowspan="2" class="sm">{L["ytd_cply"]}<br>Act.</th>'
        f'<th rowspan="2" class="gr sm">%Gr.<br>{L["ytd_cply"]}</th></tr>'
        '<tr><th class="plan">Plan</th><th class="act">Actual</th><th>%Ful</th>'
        '<th class="plan">Plan</th><th class="act">Actual</th><th>%Ful</th></tr></thead>'
    )


_COLS = '<colgroup><col class="c-ent"><col class="c-lbl">' + '<col class="c-num">' * 11 + "</colgroup>"


_MIN_ROWS = 3   # rows of a mine kept on each side of a page break


def paginate(heights: list, kinds: list, first_avail: float, avail: float, new_page_blocks: set) -> list:
    """Split blocks into page parts. heights/kinds: per block, each row's
    height and kind; first_avail / avail: room for body rows on the first /
    any later page; new_page_blocks: block indices that start a new page.
    Returns [{"b", "start", "end", "new_page"}] -- rows start..end-1 of
    block b, new_page when the part starts a new page."""
    segs = []
    remaining, fresh = first_avail, True       # fresh: nothing on this page yet

    def put(b, start, end, new_page):
        segs.append({"b": b, "start": start, "end": end, "new_page": new_page})

    for b, (hs, ks) in enumerate(zip(heights, kinds)):
        new_page = False
        if b in new_page_blocks and not fresh:
            remaining, new_page, fresh = avail, True, True
        start, n = 0, len(hs)
        while start < n:
            rest = sum(hs[start:])
            if rest <= remaining:
                put(b, start, n, new_page)
                remaining -= rest
                fresh = False
                break
            k, acc = 0, 0.0
            while start + k < n and acc + hs[start + k] <= remaining:
                acc += hs[start + k]
                k += 1
            fit = k
            k = min(k, n - start - _MIN_ROWS)
            while k >= _MIN_ROWS and ks[start + k - 1] in ("heading", "subheading"):
                k -= 1
            if k < _MIN_ROWS:
                if not fresh:                       # not enough room here: next page
                    remaining, new_page, fresh = avail, True, True
                    continue
                k = max(fit, 1)                     # a page can't hold 3 rows: place what fits
            put(b, start, start + k, new_page)
            start += k
            remaining, new_page, fresh = avail, True, True
    return segs


def _default_segments(data: dict) -> list:
    """One part per block; only SAIL starts a new page."""
    return [{"b": i, "start": 0, "end": len(b["rows"]), "new_page": b["kind"] == "sail" and i > 0}
            for i, b in enumerate(data["blocks"])]


def _segment(b: dict, seg: dict, split: bool, pct: set, d: int) -> str:
    """One page part of a block as its own <tbody>, with its own name cell
    (the short name when the block is split across pages)."""
    rows = b["rows"][seg["start"]:seg["end"]]
    name = b.get("short", b["name"]) if split else b["name"]
    trs = []
    for i, r in enumerate(rows):
        cells = []
        if i == 0:
            cells.append(f'<td rowspan="{len(rows)}" class="ent"><div>{escape(name, quote=False)}</div></td>')
        cells.append(f'<td class="lbl">{escape(r["label"], quote=False)}</td>')
        qd = r["decimals"] if r["decimals"] is not None else d
        for vi, v in enumerate(r["values"]):
            text = _p(v) if vi in pct else _q(v, qd)
            cells.append(f'<td class="{_cls(vi)}">{text}</td>')
        trs.append(f'<tr class="{r["kind"]}">{"".join(cells)}</tr>')
    cls = "blk sail" if b["kind"] == "sail" else "blk"
    style = ' style="break-before: page"' if seg["new_page"] else ""
    return f'<tbody class="{cls}"{style}>{"".join(trs)}</tbody>'


def build_html(data: dict, decimals: int, colors: dict, segments: list = None) -> str:
    """data: mines_performance.generate(); colors: colors_loader.load_colors_config();
    segments: paginate()'s page parts (default: one part per block)."""
    def c(k, dflt):  # defaults mirror colors_loader._DEFAULTS
        return colors.get(k, dflt)
    blk = c("border_black", "#000000")
    txt = c("text_black", "#000000")
    line = c("border_light", "#cbd5e1")
    L = data["labels"]
    pct = set(data["pct_idx"])
    css = f"""
  {_fonts()}
  @page {{ size: A4 portrait; margin: 7mm 10mm 7mm 10mm; }}
  body {{ font-family: 'IBM Plex Sans', Arial, sans-serif; margin: 0; color: {txt};
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .hd {{ display: flex; justify-content: space-between; align-items: flex-end;
         border-bottom: 1.5px solid {c("text_primary", "#0f172a")}; padding-bottom: 3px; margin-bottom: 4px; }}
  h2 {{ font-size: 10pt; font-weight: 700; color: rgb(0,0,255); margin: 0; }}
  .unit {{ font-size: 8.5pt; font-weight: 500; }}
  .empty {{ font-size: 10pt; font-weight: 700; margin-top: 12px; }}
  tbody.blk {{ break-inside: avoid; }}
  .note {{ font-size: 8pt; font-style: italic; margin: 2px 0 0; }}
  /* The black frame is drawn by the cells, not the table: a table border
     runs on down the empty bottom of a page the table continues from.
     Header row 1: top; outer cells: left/right; each block: bottom (which is
     also the line between blocks). */
  table {{ table-layout: fixed; width: 100%; border-collapse: separate; border-spacing: 0; }}
  thead tr:first-child th {{ border-top: 1px solid {blk}; }}
  thead tr:first-child > :first-child, td.ent {{ border-left: 1px solid {blk}; }}
  tbody.blk tr:last-child td, td.ent {{ border-bottom: 1px solid {blk}; }}
  col.c-ent {{ width: 3.5%; }} col.c-lbl {{ width: 21%; }} col.c-num {{ width: 6.86%; }}
  th, td {{ color: {txt}; line-height: 1.1; white-space: nowrap; overflow: hidden; }}
  th {{ font-family: 'Arial Narrow', Arial, sans-serif; font-size: 8.2pt; font-weight: 700;
        text-transform: uppercase; text-align: center; padding: 1.8px 1px; border: none;
        border-right: 1px solid {c("border_medium", "#94a3b8")};
        background: {c("table_header_bg", "transparent")}; }}
  th.l {{ text-align: left; padding-left: 3px; }}
  /* last-year headers ("Apr-Sep'25 Act.", "%Gr. Apr-Sep'25") are too wide for
     a value column at 8.2pt -- smaller and allowed to wrap, as page 4's
     hdr-small / plant_performance_pdf.py's th.sm */
  th.sm {{ font-size: 6.8pt; line-height: 0.95; padding: 1px 0; white-space: normal; }}
  th[colspan] {{ border-bottom: 1px solid {c("border_medium", "#94a3b8")}; }}
  /* header/body rule -- Chromium repeats the thead, rule included, at the
     top of every page */
  thead tr:last-child th, thead tr:first-child th[rowspan] {{ border-bottom: 1px solid {blk}; }}
  td {{ font-size: 8.5pt; padding: 1.8px 2px; text-align: right; border: none; border-right: 1px solid {line}; }}
  /* value columns are 13 mm wide: a 5-digit SAIL figure needs a smaller font
     the more decimals are shown (d0..d3 = decimals chosen) */
  table.d1 td:not(.lbl):not(.ent) {{ font-size: 8pt; }}
  table.d2 td:not(.lbl):not(.ent) {{ font-size: 7.4pt; padding: 1.8px 1px; }}
  table.d3 td:not(.lbl):not(.ent) {{ font-size: 6.8pt; padding: 1.8px 1px; }}
  thead tr:first-child > :last-child, tbody tr > :last-child {{ border-right: 1px solid {blk}; }}
  td.ent {{ border-right: 1px solid {blk}; text-align: center; vertical-align: middle; padding: 2px 0; }}
  td.ent div {{ writing-mode: vertical-rl; transform: rotate(180deg); margin: 0 auto;
                font-family: 'Arial Narrow', Arial, sans-serif; font-size: 8.5pt; font-weight: 700; }}
  td.lbl {{ text-align: left; white-space: normal; }}
  tr.heading td.lbl {{ font-family: 'Arial Narrow', Arial, sans-serif; font-weight: 700;
                       text-transform: uppercase; padding-left: 3px; }}
  tr.subheading td.lbl {{ font-weight: 700; font-style: italic; padding-left: 8px; }}
  tr.item td.lbl {{ padding-left: 14px; }}
  tr.total td {{ font-weight: 700; }}
  tr.total td.lbl {{ padding-left: 8px; }}
  tr.total td:not(.ent) {{ background: {c("mines_perf_total_bg", "#FEF3C7")}; }}
  td.plan, th.plan {{ background: {c("perf_app_bg", "#FFF2CC")}; }}
  td.act, th.act {{ background: {c("perf_act_bg", "#C6EFCE")}; }}
  td.gr, th.gr {{ background: {c("perf_gr_bg", "#e2e8f0")}; }}
  tr.heading td:not(.ent), tr.total td:not(.ent) {{ border-top: 1px solid {blk}; }}
  tbody.blk tr:first-child td {{ border-top: none; }}
"""
    head = f'<div class="hd"><h2>{escape(L["title"], quote=False)}</h2><span class="unit">Unit: \'000 T</span></div>'
    if data["blocks"]:
        notes = "".join(f'<p class="note">{escape(b["note"], quote=False)}</p>'
                        for b in data["blocks"] if b.get("note"))
        segments = segments if segments is not None else _default_segments(data)
        split = {s["b"] for s in segments} - {s["b"] for s in segments if s["start"] == 0 and
                                                s["end"] == len(data["blocks"][s["b"]]["rows"])}
        body = (f'<table class="d{decimals}">{_COLS}{_head(L)}'
                + "".join(_segment(data["blocks"][s["b"]], s, s["b"] in split, pct, decimals)
                          for s in segments)
                + f"</table>{notes}")
    else:
        body = f'<p class="empty">No mines data for {escape(L["month"], quote=False)}.</p>'
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{head}{body}</body></html>'


# A4 height less the 7 mm top and bottom margins, in CSS px (96 dpi); a few
# px kept spare so a rounding difference never pushes a part to the next page.
_PAGE_H = (297 - 7 - 7) / 25.4 * 96
_SPARE = 6
_PRINT_W = round((210 - 10 - 10) / 25.4 * 96)

_MEASURE_JS = """() => {
    const t = document.querySelector('table');
    return {top: t.getBoundingClientRect().top, thead: t.tHead.getBoundingClientRect().height,
            rows: [...t.tBodies].map(tb => [...tb.rows].map(r => r.getBoundingClientRect().height))};
}"""


def _load(page, html: str):
    page.set_content(html, wait_until="load")
    page.evaluate("document.fonts.ready.then(() => true)")


def render_pdf(data: dict, decimals: int, colors: dict) -> bytes:
    """Measure every row at the printable width, paginate, and print.
    Synchronous -- call from a plain `def` route (FastAPI threadpool)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": _PRINT_W, "height": 1000})
        page.emulate_media(media="print")
        segments = None
        if data["blocks"]:
            _load(page, build_html(data, decimals, colors))
            m = page.evaluate(_MEASURE_JS)
            kinds = [[r["kind"] for r in b["rows"]] for b in data["blocks"]]
            sail = {i for i, b in enumerate(data["blocks"]) if b["kind"] == "sail"}
            segments = paginate(m["rows"], kinds, _PAGE_H - m["top"] - m["thead"] - _SPARE,
                                _PAGE_H - m["thead"] - _SPARE, sail)
        _load(page, build_html(data, decimals, colors, segments))
        pdf = page.pdf(format="A4", landscape=False, print_background=True, margin=_MARGIN)
        browser.close()
    return pdf
