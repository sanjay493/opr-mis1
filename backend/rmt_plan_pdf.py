"""A4 landscape PDF of the RMT "Production Plan for <month>" report
(rmt_plan.generate): one sheet per sample page. Not part of the
layout-guarded monthly report. Colours come from colors_config.json.

A sheet that comes out taller than the page (long remarks) is zoomed out
to fit in render_pdf, so each sheet stays one page."""
import re
from html import escape

from plant_performance_pdf import _fonts

_MARGIN = {"top": "8mm", "right": "8mm", "bottom": "8mm", "left": "8mm"}
# printable area in CSS px (96 dpi)
_PRINT_W = round((297 - 16) / 25.4 * 96)
_PRINT_H = (210 - 16) / 25.4 * 96 - 4


def num(v) -> str:
    """'000 T figures as the sample prints them: whole numbers, one decimal
    below 100 when the value has a fraction."""
    if v is None:
        return ""
    if abs(v) < 100 and round(v, 1) != round(v):
        return f"{v:.1f}"
    s = f"{v:.0f}"
    return "0" if s == "-0" else s


def rich(text) -> str:
    """Remarks: escaped, **bold** and line breaks kept."""
    if not text:
        return ""
    s = escape(text, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s, flags=re.S)
    return s.replace("\r\n", "\n").replace("\n", "<br>")


def _page1(data) -> str:
    L = data["labels"]
    head = (
        '<thead><tr><th rowspan="3" class="it">Item</th><th rowspan="3" class="pl">Plant</th>'
        f'<th>{L["ly_col"]}</th><th colspan="5">{L["prev_col"]}</th><th colspan="4">{L["month_col"]}</th>'
        '<th rowspan="3" class="rm">Remarks regarding S/d plan</th></tr>'
        '<tr><th rowspan="2" class="act">Actual</th><th rowspan="2" class="app">APP</th><th rowspan="2" class="op">OP</th>'
        '<th rowspan="2" class="act">M/rate</th><th rowspan="2">%ful.<br>APP</th><th rowspan="2">%ful.<br>OP</th>'
        '<th colspan="2" class="app">APP</th><th colspan="2" class="op">OP</th></tr>'
        '<tr><th class="app">Total</th><th class="app">TPD</th><th class="op">Total</th><th class="op">TPD</th></tr></thead>'
    )
    body = []
    for sec in data["page1"]:
        rows = sec["rows"]
        trs = []
        for i, r in enumerate(rows):
            cells = []
            if i == 0:
                cells.append(f'<td rowspan="{len(rows)}" class="ent"><div>{escape(sec["label"])}</div></td>')
            cells.append(f'<td class="pl">{escape(r["row"])}</td>')
            for k, cls in (("ly_actual", "act"), ("prev_app", "app"), ("prev_op", "op"), ("prev_mrate", "act"),
                           ("ful_app", ""), ("ful_op", ""), ("app", "app"), ("app_tpd", "app"),
                           ("op", "op"), ("op_tpd", "op")):
                cells.append(f'<td class="n {cls}">{num(r[k])}</td>')
            cells.append(f'<td class="rm">{rich(r["remarks"])}</td>')
            trs.append(f'<tr class="{"tot" if r["total"] else ""}">{"".join(cells)}</tr>')
        body.append(f'<tbody>{"".join(trs)}</tbody>')
    cols = ('<colgroup><col style="width:3%"><col style="width:4.6%">' + '<col style="width:4.5%">' * 4
            + '<col style="width:3.6%">' * 2 + '<col style="width:4.6%">' * 4 + '<col></colgroup>')
    return (f'<section class="sheet"><div class="hd"><h1>Production Plan for {L["month"]}</h1>'
            f'<span class="unit">Unit: \'000T</span></div>'
            f'<table class="t1">{cols}{head}{"".join(body)}</table>'
            + (f'<p class="note">{escape(data["note"])}</p>' if data.get("note") else "")
            + "</section>")


def _page2(data) -> str:
    L = data["labels"]
    out = []
    for n, sec in enumerate(data["page2"]):
        if sec["rate"]:
            sub = ("<th>Plan</th><th>Coal Requirement<br>per day(T)</th>", "<th>Plan</th><th>Coal Requirement<br>per day(T)</th>")
        else:
            sub = ("<th>APP</th><th>APP (tpd)</th>", "<th>OP</th><th>OP (tpd)</th>")
        head = (f'<thead><tr><th rowspan="2" class="it">Item</th><th rowspan="2" class="pl">Plant</th>'
                f'<th colspan="2" class="app">APP</th><th colspan="2" class="op">OP</th>'
                f'<th rowspan="2" class="rm">Remarks</th></tr><tr>{sub[0]}{sub[1]}</tr></thead>')
        trs = []
        for i, r in enumerate(sec["rows"]):
            cells = []
            if i == 0:
                cells.append(f'<td rowspan="{len(sec["rows"])}" class="ent"><div>{escape(sec["label"])}</div></td>')
            cells.append(f'<td class="pl">{escape(r["row"])}</td>')
            for k, cls in (("app", "app"), ("app_day", "app"), ("op", "op"), ("op_day", "op")):
                cells.append(f'<td class="n {cls}">{num(r[k])}</td>')
            cells.append(f'<td class="rm">{rich(r["remarks"])}</td>')
            trs.append(f'<tr class="{"tot" if r["total"] else ""}">{"".join(cells)}</tr>')
        cols = ('<colgroup><col style="width:4.5%"><col style="width:6%">' + '<col style="width:10%">' * 4
                + '<col></colgroup>')
        out.append(f'<table class="t2">{cols}{head}<tbody>{"".join(trs)}</tbody></table>')
        if sec["rate"]:
            out.append(_coal_basis(data))
    return (f'<section class="sheet"><div class="hd"><h1>Production Plan for {L["month"]}</h1>'
            f'<span class="unit">{L["month_col"]} · Unit: \'000T</span></div>{"".join(out)}</section>')


def coal_formula(cb) -> str:
    """The coal requirement's basis in one line (also the Excel note)."""
    return (f"Coal requirement = dry coal charge per oven (FY {cb['fy']} target; the smaller norm where a plant "
            f"has two) ÷ (1 − {cb['handling_loss'] * 100:g}% handling loss) ÷ (1 − {cb['moisture_loss'] * 100:g}% "
            "moisture loss) × pushings per day")


def _coal_basis(data) -> str:
    cb = data["coal_basis"]
    if not cb["plants"]:
        return f'<p class="cb-note">No dry coal charge target for FY {escape(cb["fy"])}: no coal requirement.</p>'
    return f'<p class="cb-note">{escape(coal_formula(cb))}.</p>'


def _ipt_groups(rows):
    """Consecutive rows with the same item as one group (one merged item cell)."""
    groups = []
    for r in rows:
        if groups and groups[-1][0] == r["item"]:
            groups[-1][1].append(r)
        else:
            groups.append((r["item"], [r]))
    return groups


def _page3(data) -> str:
    L = data["labels"]
    e = lambda v: escape(v or "")
    trs = []
    for item, rows in _ipt_groups(data["ipt"]):
        for i, r in enumerate(rows):
            first = f'<td rowspan="{len(rows)}" class="ipt-item">{e(item)}</td>' if i == 0 else ""
            trs.append(f'<tr class="{"grp" if i == 0 else ""}">{first}<td class="c">{e(r["from_plant"])}</td>'
                       f'<td class="c">{e(r["to_plant"])}</td><td class="c">{e(r["availability"])}</td>'
                       f'<td class="c">{e(r["requirement"])}</td><td class="rm">{rich(r["remarks"])}</td></tr>')
    if not trs:
        trs = ['<tr><td colspan="6" class="empty">No IPT requirement / availability entered.</td></tr>']
    ipt = ('<table class="t3"><colgroup><col style="width:9%"><col style="width:5%"><col style="width:5%">'
           '<col style="width:9%"><col style="width:9%"><col></colgroup>'
           '<thead><tr><th>Item</th><th>From</th><th>To</th><th>Availability</th><th>Requirement</th>'
           f'<th>Remarks</th></tr></thead><tbody>{"".join(trs)}</tbody></table>')
    stock = ""
    if data["stock"]:
        as_on = data.get("stock_as_on")
        if as_on:
            as_on = f"{as_on[8:10]}.{as_on[5:7]}.{as_on[2:4]}"
        srows = "".join(f'<tr><td class="b">{e(r["plant"])}</td><td class="c">{rich(r["bf_coke"])}</td>'
                        f'<td class="c">{rich(r["slab"])}</td><td class="c">{rich(r["bloom"])}</td></tr>'
                        for r in data["stock"])
        stock = (f'<p class="stk-h">Stock{" as on " + as_on if as_on else ""}</p>'
                 '<table class="t4"><colgroup><col style="width:12%"><col style="width:22%"><col style="width:22%">'
                 '<col></colgroup><thead><tr><th></th><th>BF Coke</th><th>Slab</th><th>Bloom</th></tr></thead>'
                 f'<tbody>{srows}</tbody></table>')
    return (f'<section class="sheet"><div class="hd"><h1 class="sm">IPT Requirement / Availability Plant wise for '
            f'{L["month"]}</h1><span class="unit">Unit: T</span></div>{ipt}{stock}</section>')


def build_html(data: dict, colors: dict) -> str:
    def c(k, dflt):  # defaults mirror colors_loader._DEFAULTS
        return colors.get(k, dflt)
    blk = c("border_black", "#000000")
    txt = c("text_black", "#000000")
    css = f"""
  {_fonts()}
  @page {{ size: A4 landscape; margin: 8mm; }}
  body {{ font-family: 'IBM Plex Sans', Arial, sans-serif; margin: 0; color: {txt};
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .sheet {{ break-after: page; width: {_PRINT_W}px; }}
  .sheet:last-child {{ break-after: auto; }}
  .hd {{ display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 4px; }}
  h1 {{ font-size: 15pt; font-weight: 700; margin: 0; }}
  h1.sm {{ font-size: 12pt; }}
  .unit {{ font-size: 8pt; }}
  .note {{ font-size: 8.5pt; font-weight: 700; margin: 6px 0 0; }}
  table {{ width: 100%; table-layout: fixed; border-collapse: collapse; margin-bottom: 10px; }}
  th, td {{ border: 1px solid {blk}; padding: 1.5px 3px; line-height: 1.15; }}
  th {{ font-size: 8.5pt; font-weight: 700; text-align: center; background: {c("rmt_header_bg", "#E2E8F0")}; }}
  td {{ font-size: 8.5pt; }}
  td.n {{ text-align: center; white-space: nowrap; }}
  td.c {{ text-align: center; }}
  td.pl, td.b {{ font-weight: 600; }}
  th.app, td.app {{ background: {c("perf_app_bg", "#FFF2CC")}; }}
  th.op, td.op {{ background: {c("rmt_op_bg", "#DDEBF7")}; }}
  th.act, td.act {{ background: {c("perf_act_bg", "#C6EFCE")}; }}
  td.rm {{ font-size: 7.6pt; text-align: left; }}
  tr.tot td {{ font-weight: 700; }}
  td.ent {{ text-align: center; vertical-align: middle; padding: 2px 0; }}
  td.ent div {{ writing-mode: vertical-rl; transform: rotate(180deg); margin: 0 auto; font-weight: 700; font-size: 8.5pt; }}
  table.t2 td {{ font-size: 10pt; padding: 3px 4px; }}
  table.t2 td.rm {{ font-size: 8.5pt; }}
  .cb-note {{ font-size: 7.6pt; font-style: italic; margin: -6px 0 10px; }}
  table.t3 td, table.t4 td {{ font-size: 8.5pt; padding: 2px 4px; }}
  td.ipt-item {{ font-weight: 700; text-align: center; vertical-align: middle; }}
  table.t3 tr.grp td {{ border-top: 2px solid {blk}; }}
  td.empty {{ text-align: center; font-style: italic; padding: 8px; }}
  .stk-h {{ font-size: 9.5pt; margin: 10px 0 4px; text-align: center; }}
  table.t4 {{ width: 75%; margin: 0 auto; }}
"""
    body = _page1(data) + _page2(data) + _page3(data)
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'


# Shrink each sheet that is taller than the printable height with CSS zoom
# (which, unlike a transform, also shrinks the layout box Chromium paginates).
_FIT_JS = """(h) => [...document.querySelectorAll('.sheet')].map((s) => {
    const sh = s.getBoundingClientRect().height;
    if (sh <= h) return 100;
    const k = Math.floor(h / sh * 1000) / 1000;
    s.style.zoom = k;
    return Math.round(k * 100);
})"""


def render_pdf(data: dict, colors: dict) -> bytes:
    """Synchronous -- call from a plain `def` route (FastAPI threadpool)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": _PRINT_W, "height": 800})
        page.emulate_media(media="print")
        page.set_content(build_html(data, colors), wait_until="load")
        page.evaluate("document.fonts.ready.then(() => true)")
        page.evaluate(_FIT_JS, _PRINT_H)
        pdf = page.pdf(format="A4", landscape=True, print_background=True, margin=_MARGIN)
        browser.close()
    return pdf
