"""Two-page (APP, MoU) PDF of the Plant Wise Performance of Main Items
report for /reports/excel — its own small template, not part of the
layout-guarded monthly report. Each page is scaled with CSS zoom to fit one
A4 landscape sheet. Colours come from colors_config.json (perf_* keys)."""
from html import escape

_W_PX, _H_PX = 1047, 703   # A4 landscape minus 10mm/12mm margins, at 96 dpi

# value index -> cell class: plan (APP/MoU) columns, actual columns, %Gr columns
_VAL_CLASS = {0: "pl", 1: "pl", 8: "pl", 2: "ac", 9: "ac", 6: "gr", 13: "gr"}


def _q(v, d):
    return "" if v is None else f"{v:,.{d}f}"


def _p(v):
    if v is None:
        return ""
    s = f"{v:.0f}"
    return "0" if s == "-0" else s


def _sheet(sec, d):
    L, pct, rows = sec["labels"], set(sec["pct_idx"]), sec["rows"]
    B = L["basis"]
    sub = [("pl", B), ("ac", "Act."), ("", "Var"), ("", "%Ful.")] * 2
    head = (
        f'<tr><th rowspan="2" class="l">Items</th><th rowspan="2">Plant</th>'
        f'<th rowspan="2" class="cap">Ann.<br>Cap.</th><th rowspan="2" class="pl">{B}<br>{L["fy"]}</th>'
        f'<th colspan="4">{L["month"]}</th><th rowspan="2">{L["cply"]}<br>Act.</th>'
        f'<th rowspan="2" class="gr">%Gr.<br>{L["cply"]}</th><th rowspan="2">CU%</th>'
        f'<th colspan="4">{L["ytd"]}</th><th rowspan="2">{L["ytd_cply"]}<br>Act.</th>'
        f'<th rowspan="2" class="gr">%Gr.<br>{L["ytd_cply"]}</th><th rowspan="2">CU%</th></tr><tr>'
        + "".join(f'<th class="{k}">{t}</th>' for k, t in sub)
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
            sail = row["plant"] in ("SAIL", "5 Plants") or row["is_conversion"] or row["is_sail_incl_conv"]
            cells = []
            if row["is_conversion"]:
                cells.append('<td colspan="3" class="l b">Conversion</td>')
            elif row["is_sail_incl_conv"]:
                cells.append('<td colspan="2" class="l b">SAIL incl. conversion</td>')
            else:
                if k == i:
                    cells.append(f'<td rowspan="{j - i + 1}" class="l b item">{escape(row["item"])}</td>')
                cells.append(f'<td class="c b">{escape(row["plant"])}</td>')
            if not row["is_conversion"]:
                cells.append(f'<td class="cap">{_q(row["capacity"], d)}</td>')
            for vi, v in enumerate(row["values"]):
                cells.append(f'<td class="{_VAL_CLASS.get(vi, "")}">{_p(v) if vi in pct else _q(v, d)}</td>')
            body.append(f'<tr class="{"sail" if sail else ""}">{"".join(cells)}</tr>')
        i = j + 1
    note = "" if sec["has_plan"] else f'<p class="note">No {B} data uploaded for FY {L["fy"]}.</p>'
    return (
        f'<section class="sheet"><div class="hd"><h1>{escape(L["title"])}</h1><h1>w.r.t {B}</h1></div>'
        f'<div class="sub"><span>Tentative</span><span>Unit: \'000 T</span></div>{note}'
        f'<table><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></section>'
    )


def build_html(sections, decimals, colors):
    """sections: [{labels, pct_idx, rows, has_plan}, ...], one page each.
    colors: colors_loader.load_colors_config() (flat key -> CSS colour)."""
    def c(k, dflt):  # defaults mirror colors_loader._DEFAULTS
        return colors.get(k, dflt)
    css = f"""
  @page {{ size: A4 landscape; margin: 12mm 10mm; }}
  body {{ font-family: Arial, sans-serif; margin: 0; color: {c("text_primary", "#0f172a")}; }}
  .sheet {{ page-break-after: always; width: {_W_PX}px; }}
  .sheet:last-child {{ page-break-after: auto; }}
  .hd {{ display: flex; justify-content: space-between; border-bottom: 1.5px solid {c("text_primary", "#0f172a")}; }}
  h1 {{ font-size: 12pt; margin: 0 0 2px; }}
  .sub {{ display: flex; justify-content: space-between; font-size: 8pt; font-style: italic; margin: 2px 0 4px; }}
  .note {{ font-size: 9pt; font-weight: 700; margin: 2px 0 4px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 7.5pt; }}
  th, td {{ border: 1px solid {c("border_medium", "#94a3b8")}; padding: 1px 4px; text-align: right; white-space: nowrap; }}
  th {{ text-align: center; font-weight: 700; }}
  .l {{ text-align: left; }} .c {{ text-align: center; }} .b {{ font-weight: 700; }}
  .item {{ white-space: normal; vertical-align: middle; }}
  .pl {{ background: {c("perf_app_bg", "#FFF2CC")}; color: {c("perf_app_text", "#7F6000")}; }}
  .ac {{ background: {c("perf_act_bg", "#C6EFCE")}; color: {c("perf_act_text", "#006100")}; font-weight: 700; }}
  .gr {{ background: {c("perf_gr_bg", "#e2e8f0")}; }}
  .cap {{ background: {c("perf_cap_bg", "#F8CBAD")}; color: {c("perf_cap_text", "#843C0C")}; }}
  tr.sail td {{ font-weight: 700; }}
"""
    pages = "".join(_sheet(s, decimals) for s in sections)
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{pages}</body></html>'


def render(html: str) -> bytes:
    """Synchronous — call via a threadpool executor from async code."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # Measure in print layout at the printable width, so the zoom that
        # makes a sheet fit is computed against what the PDF will lay out.
        page = browser.new_page(viewport={"width": _W_PX, "height": _H_PX})
        page.emulate_media(media="print")
        page.set_content(html, wait_until="domcontentloaded")
        page.evaluate(f"""() => document.querySelectorAll('.sheet').forEach(s => {{
            const r = s.getBoundingClientRect();
            const z = Math.min(1, {_H_PX} * 0.98 / r.height, {_W_PX} / r.width);
            if (z < 1) s.style.zoom = z; }})""")
        pdf = page.pdf(format="A4", landscape=True, print_background=True,
                       margin={"top": "12mm", "right": "10mm", "bottom": "12mm", "left": "10mm"})
        browser.close()
    return pdf
