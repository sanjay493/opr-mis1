"""A4 PDF of the Mines Production Performance report
(mines_performance.generate) for /reports/mines. Pages 5-6 columns, with the
fonts and border rules of plant_performance_pdf.py: separate borders, so the
table's own border is the black frame and each cell draws only its right
edge -- no light line between rows; black rules above section headings and
totals. One table per block, so each block carries the column header and is
never split across pages; the SAIL block starts a new page. Not part of the
layout-guarded monthly report. Colours come from colors_config.json."""
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
        f'<th rowspan="2">{L["cply"]}<br>Act.</th><th rowspan="2" class="gr">%Gr.<br>{L["cply"]}</th>'
        f'<th colspan="3">{L["ytd"]}</th><th rowspan="2">{L["ytd_cply"]}<br>Act.</th>'
        f'<th rowspan="2" class="gr">%Gr.<br>{L["ytd_cply"]}</th></tr>'
        '<tr><th class="plan">Plan</th><th class="act">Actual</th><th>%Ful</th>'
        '<th class="plan">Plan</th><th class="act">Actual</th><th>%Ful</th></tr></thead>'
    )


_COLS = '<colgroup><col class="c-ent"><col class="c-lbl">' + '<col class="c-num">' * 11 + "</colgroup>"


def _block(b: dict, L: dict, pct: set, d: int) -> str:
    trs = []
    for i, r in enumerate(b["rows"]):
        cells = []
        if i == 0:
            cells.append(f'<td rowspan="{len(b["rows"])}" class="ent"><div>{escape(b["name"], quote=False)}</div></td>')
        cells.append(f'<td class="lbl">{escape(r["label"], quote=False)}</td>')
        qd = r["decimals"] if r["decimals"] is not None else d
        for vi, v in enumerate(r["values"]):
            text = _p(v) if vi in pct else _q(v, qd)
            cells.append(f'<td class="{_cls(vi)}">{text}</td>')
        trs.append(f'<tr class="{r["kind"]}">{"".join(cells)}</tr>')
    note = f'<p class="note">{escape(b["note"], quote=False)}</p>' if b.get("note") else ""
    cls = "blk sail" if b["kind"] == "sail" else "blk"
    return (f'<section class="{cls}"><table>{_COLS}{_head(L)}<tbody>{"".join(trs)}</tbody></table>'
            f"{note}</section>")


def build_html(data: dict, decimals: int, colors: dict) -> str:
    """data: mines_performance.generate(); colors: colors_loader.load_colors_config()."""
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
  .blk {{ break-inside: avoid; margin-top: 6px; }}
  .blk.sail {{ break-before: page; }}
  .note {{ font-size: 8pt; font-style: italic; margin: 2px 0 0; }}
  table {{ table-layout: fixed; width: 100%; border-collapse: separate; border-spacing: 0;
           border: 1px solid {blk}; }}
  col.c-ent {{ width: 3.5%; }} col.c-lbl {{ width: 21%; }} col.c-num {{ width: 6.86%; }}
  th, td {{ color: {txt}; line-height: 1.1; white-space: nowrap; overflow: hidden; }}
  th {{ font-family: 'Arial Narrow', Arial, sans-serif; font-size: 8.2pt; font-weight: 700;
        text-transform: uppercase; text-align: center; padding: 1.8px 1px; border: none;
        border-right: 1px solid {c("border_medium", "#94a3b8")};
        background: {c("table_header_bg", "transparent")}; }}
  th.l {{ text-align: left; padding-left: 3px; }}
  th[colspan] {{ border-bottom: 1px solid {c("border_medium", "#94a3b8")}; }}
  thead tr:last-child th, thead tr:first-child th[rowspan] {{ border-bottom: 1px solid {blk}; }}
  td {{ font-size: 8.5pt; padding: 1.8px 2px; text-align: right; border: none; border-right: 1px solid {line}; }}
  thead tr:first-child > :last-child, tbody tr > :last-child {{ border-right: none; }}
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
  tbody tr:first-child td {{ border-top: none; }}
"""
    head = f'<div class="hd"><h2>{escape(L["title"], quote=False)}</h2><span class="unit">Unit: \'000 T</span></div>'
    if data["blocks"]:
        body = "".join(_block(b, L, pct, decimals) for b in data["blocks"])
    else:
        body = f'<p class="empty">No mines data for {escape(L["month"], quote=False)}.</p>'
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{head}{body}</body></html>'


def render(html: str) -> bytes:
    """Synchronous -- call from a plain `def` route (FastAPI threadpool)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.emulate_media(media="print")
        page.set_content(html, wait_until="load")
        page.evaluate("document.fonts.ready.then(() => true)")
        pdf = page.pdf(format="A4", landscape=False, print_background=True, margin=_MARGIN)
        browser.close()
    return pdf
