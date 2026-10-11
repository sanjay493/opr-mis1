"""Two-page (APP, MoU) PDF of the Plant Wise Performance of Main Items
report for /reports/excel. Laid out like the monthly report's page 4
(page_templates/page4_table.html + its .page4-* rules in main.html): A4
portrait with page 4's margins, the same 18 column widths, fonts, rules and
column tints. It is its own small template, not part of the layout-guarded
monthly report, so restyling page 4 does not change it (and vice versa).
Colours come from colors_config.json."""
from html import escape

_W_PX, _H_PX = 718, 1077   # A4 portrait minus page 4's 10/10mm, 7/5mm margins, at 96 dpi
_MARGIN = {"top": "7mm", "right": "10mm", "bottom": "5mm", "left": "10mm"}

# page 4's <colgroup>: Items, Plant, Ann.Cap., APP yy-yy, then the month
# and cumulative blocks (Plan, Act., Var, %Ful., CPLY Act., %Gr., CU%)
_COLS = (["c-items", "c-plant", "c-cap", "c-ann"]
         + ["c-num", "c-num", "c-num-sm", "c-num-sm", "c-num", "c-num-sm", "c-num-sm"] * 2)

# value index -> cell class, as page4_table.html's col_cls
_VAL_CLASS = {0: "col-ann", 2: "col-act", 8: "col-ytd", 9: "col-act"}


def _q(v, d):
    if v is None:
        return ""
    s = f"{v:.{d}f}"
    return s[1:] if s.startswith("-") and not s.strip("-0.") else s


def _p(v):
    if v is None:
        return ""
    s = f"{v:.0f}"
    return "0" if s == "-0" else s


def _sheet(sec, d):
    L, pct, rows = sec["labels"], set(sec["pct_idx"]), sec["rows"]
    B = L["basis"]
    sub = [("", B), ("col-act", "Act."), ("", "Var"), ("", "%Ful.")]
    ytd_sub = [("col-ytd", B)] + sub[1:]
    head = (
        '<tr><th rowspan="2" class="l">Items</th><th rowspan="2">Plant</th>'
        f'<th rowspan="2" class="col-cap">Ann.<br>Cap.</th><th rowspan="2" class="col-ann">{B}<br>{L["fy"]}</th>'
        f'<th colspan="4">{L["month"]}</th><th rowspan="2" class="sm">{L["cply"]}<br>Act.</th>'
        f'<th rowspan="2" class="sm">%Gr.<br>{L["cply"]}</th><th rowspan="2" class="sm">CU%</th>'
        f'<th colspan="4" class="col-ytd">{L["ytd"]}</th><th rowspan="2" class="sm">{L["ytd_cply"]}<br>Act.</th>'
        f'<th rowspan="2" class="sm">%Gr.<br>{L["ytd_cply"]}</th><th rowspan="2" class="sm">CU%</th></tr><tr>'
        + "".join(f'<th class="{k}">{t}</th>' for k, t in sub + ytd_sub)
        + "</tr>"
    )
    body, i = [], 0
    while i < len(rows):
        r = rows[i]
        j = i
        if not (r["is_conversion"] or r["is_sail_incl_conv"]):
            while (j + 1 < len(rows) and rows[j + 1]["item"] == r["item"]
                   and not rows[j + 1]["is_conversion"] and not rows[j + 1]["is_sail_incl_conv"]):
                j += 1
        for k in range(i, j + 1):
            row = rows[k]
            cls = ["group-first"] if k == i else []
            if row["plant"] in ("SAIL", "5 Plants") or row["is_conversion"] or row["is_sail_incl_conv"]:
                cls.append("tot")
            cells = []
            if row["is_conversion"]:
                cells.append('<td colspan="3" class="lbl">Conversion</td>')
            elif row["is_sail_incl_conv"]:
                cells.append('<td colspan="2" class="lbl">SAIL incl. conversion</td>')
            else:
                if k == i:
                    cells.append(f'<td rowspan="{j - i + 1}" class="lbl item">{escape(row["item"])}</td>')
                cells.append(f'<td class="plant">{escape(row["plant"])}</td>')
            if not row["is_conversion"]:
                cells.append(f'<td class="col-cap">{_q(row["capacity"], d)}</td>')
            for vi, v in enumerate(row["values"]):
                c = _VAL_CLASS.get(vi)
                attr = f' class="{c}"' if c else ""
                cells.append(f'<td{attr}>{_p(v) if vi in pct else _q(v, d)}</td>')
            body.append(f'<tr class="{" ".join(cls)}">{"".join(cells)}</tr>')
        i = j + 1
    note = "" if sec["has_plan"] else f'<p class="note">No {B} data uploaded for FY {L["fy"]}.</p>'
    cols = "".join(f'<col class="{c}" />' for c in _COLS)
    tcls = ' class="auto"' if d else ""
    return (
        f'<section class="sheet"><div class="hd"><h2>{escape(L["title"])}</h2><h2 class="basis">w.r.t {B}</h2></div>'
        f'<div class="meta"><span>Tentative</span><span>Unit: \'000 T</span></div>{note}'
        f'<table{tcls}><colgroup>{cols}</colgroup><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></section>'
    )


def _fonts():
    """The report's body font (IBM Plex Sans), embedded as pdf.py does."""
    try:
        from pdf import _local_font_face_css
        return _local_font_face_css("IBM Plex Sans")
    except Exception:
        return ""


def build_html(sections, decimals, colors):
    """sections: [{labels, pct_idx, rows, has_plan}, ...], one page each.
    colors: colors_loader.load_colors_config() (flat key -> CSS colour)."""
    def c(k, dflt):  # defaults mirror colors_loader._DEFAULTS
        return colors.get(k, dflt)
    blk = c("border_black", "#000000")
    txt = c("text_black", "#000000")
    css = f"""
  {_fonts()}
  @page {{ size: A4 portrait; margin: 7mm 10mm 5mm 10mm; }}
  body {{ font-family: 'IBM Plex Sans', Arial, sans-serif; margin: 0; color: {txt};
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .sheet {{ page-break-after: always; width: {_W_PX}px; }}
  .sheet:last-child {{ page-break-after: auto; }}
  .hd {{ display: flex; justify-content: space-between; align-items: flex-end;
         border-bottom: 1.5px solid {c("text_primary", "#0f172a")}; padding-bottom: 3px; margin-bottom: 4px; }}
  h2 {{ font-size: 10pt; font-weight: 700; color: rgb(0,0,255); margin: 0; }}
  h2.basis {{ color: {txt}; }}
  .meta {{ display: flex; justify-content: space-between; font-size: 8.5pt; font-weight: 500; margin-bottom: 2px; }}
  .note {{ font-size: 9pt; font-weight: 700; margin: 2px 0 4px; }}
  table {{ table-layout: fixed; width: 100%; border-collapse: collapse; margin-top: 10px;
           box-shadow: 0 0 0 1px {blk}; }}
  table.auto {{ table-layout: auto; }}
  col.c-items {{ width: 50px; }} col.c-plant {{ width: 28px; }} col.c-cap {{ width: 32px; }}
  col.c-ann {{ width: 32px; }} col.c-num {{ width: 35px; }} col.c-num-sm {{ width: 22px; }}
  th, td {{ color: {txt}; line-height: 1.05; white-space: nowrap; overflow: hidden; }}
  th {{ font-family: 'Arial Narrow', Arial, sans-serif; font-size: 8.2pt; font-weight: 700; text-transform: uppercase;
        text-align: center; padding: 1.8px 1px; border: 1px solid {c("border_medium", "#94a3b8")};
        background: {c("table_header_bg", "transparent")}; }}
  th.l {{ text-align: left; padding-left: 1px; }}
  th.sm {{ font-size: 6.8pt; line-height: 0.95; padding: 1px 0; white-space: normal; }}
  td {{ font-size: 8.5pt; padding: 1.8px 1px; text-align: right; border: 1px solid {c("border_light", "#cbd5e1")}; }}
  td.lbl {{ font-family: 'Arial Narrow', Arial, sans-serif; font-size: 8pt; font-weight: 700; text-align: left;
            vertical-align: middle; padding: 1.8px 2px 1.8px 4px; }}
  td.item {{ white-space: normal; border-right: 1px solid {blk}; border-bottom: 1px solid {blk}; }}
  td.plant {{ font-weight: 600; text-align: center; padding: 1.8px 2px; }}
  thead tr:first-child th {{ border-top: none; }}
  tr > :first-child {{ border-left: none; }}
  tr > :last-child {{ border-right: none; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  thead tr:last-child th, thead tr:first-child th[rowspan] {{ border-bottom: 1px solid {blk}; }}
  tr.group-first td {{ border-top: 1px solid {blk}; }}
  .col-cap {{ background: {c("perf_cap_bg", "#F8CBAD")}; color: {c("perf_cap_text", "#843C0C")}; }}
  .col-ann {{ background: {c("perf_app_bg", "#FFF2CC")}; color: {c("perf_app_text", "#7F6000")};
              border-left: 1px solid {blk}; border-right: 1px solid {c("perf_app_border", "#BF9000")}; }}
  .col-act {{ background: {c("perf_act_bg", "#C6EFCE")}; color: {c("perf_act_text", "#006100")}; }}
  .col-ytd {{ border-left: 1px solid {blk}; }}
  :has(+ .col-ann), :has(+ .col-ytd) {{ border-right: 1px solid {blk}; }}
  tr.tot td {{ font-weight: 700; border-top: 1px solid {blk}; border-bottom: 1px solid {blk}; }}
  tr:has(+ tr.tot) td {{ border-bottom: 1px solid {blk}; }}
"""
    pages = "".join(_sheet(s, decimals) for s in sections)
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{pages}</body></html>'


# Fit each sheet to one page the way the report's page 4 fills its sheet:
# shrink the number font until no number is clipped by page 4's fixed
# column widths -- with decimals the table is laid out "auto" (page 4's
# widths become minimums, the decimal columns widen), so the numbers shrink
# until the table fits the page width instead -- shrink a plant label that doesn't
# fit ("5 Plants"), zoom down if still too tall, then grow the rows to fill
# the page. Both sheets get the same row growth -- the smaller of the two --
# so the MoU sheet (fewer items) keeps the APP sheet's row height instead of
# stretching its rows over the whole page.
_FIT_JS = """(H) => {
    const fits = c => c.scrollWidth <= c.clientWidth + 0.5;
    const shrink = (cells, ok) => {
        if (!cells.length) return;
        const fs = parseFloat(getComputedStyle(cells[0]).fontSize);
        const done = () => cells.every(fits) && (!ok || ok());
        for (let k = 1; k <= 24 && !done(); k++)
            cells.forEach(c => c.style.fontSize = (fs * (1 - 0.025 * k)) + 'px');
    };
    const sheets = Array.from(document.querySelectorAll('.sheet'));
    const extras = sheets.map(s => {
        const t = s.querySelector('table');
        shrink(Array.from(t.querySelectorAll('tbody td:not(.lbl):not(.plant)')),
               () => t.getBoundingClientRect().width <= s.clientWidth + 0.5);
        t.querySelectorAll('td.plant').forEach(c => shrink([c]));
        const h = s.getBoundingClientRect().height;
        if (h > H) { s.style.zoom = H / h; return 0; }
        return (H - h) * 0.97 / t.querySelectorAll('tbody tr').length;
    });
    const extra = Math.min(...extras);
    if (extra > 0) sheets.forEach(s => {
        const rows = Array.from(s.querySelectorAll('tbody tr'));
        const hs = rows.map(r => r.getBoundingClientRect().height);
        rows.forEach((r, i) => r.style.height = (hs[i] + extra) + 'px');
    });
}"""


def render(html: str) -> bytes:
    """Synchronous — call via a threadpool executor from async code."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # Measure in print layout at the printable width, so the fit is
        # computed against what the PDF will lay out.
        page = browser.new_page(viewport={"width": _W_PX, "height": _H_PX})
        page.emulate_media(media="print")
        page.set_content(html, wait_until="load")
        page.evaluate("document.fonts.ready.then(() => true)")
        page.evaluate(_FIT_JS, _H_PX)
        pdf = page.pdf(format="A4", landscape=False, print_background=True, margin=_MARGIN)
        browser.close()
    return pdf
