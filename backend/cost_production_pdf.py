"""A4 landscape PDF of the Cost of Production report
(cost_production.generate) for /reports/cost-production: one page per
product, its Total/Variable/Fixed blocks one row per plant. Not part of the
layout-guarded monthly report. Colours come from colors_config.json."""
from html import escape

from plant_performance_pdf import _fonts

_MARGIN = {"top": "10mm", "right": "10mm", "bottom": "10mm", "left": "10mm"}
_W_PX = round((297 - 10 - 10) / 25.4 * 96)


def fmt(v):
    return "" if v is None else f"{v:,.0f}"


def _product(data: dict, prod: dict) -> str:
    periods = data["periods"]
    head = ('<thead><tr><th class="l">Plant</th>'
            + "".join(f'<th class="{p["kind"]}">{escape(p["label"], quote=False)}</th>' for p in periods)
            + "</tr></thead>")
    body = []
    for b in prod["blocks"]:
        body.append(f'<tr class="blk"><td class="l" colspan="{len(periods) + 1}">{escape(b["label"], quote=False)}</td></tr>')
        for r in b["rows"]:
            cls = ' class="sail"' if r["plant"].startswith("SAIL") else ""
            body.append(f'<tr{cls}><td class="l">{escape(r["plant"], quote=False)}</td>'
                        + "".join(f'<td class="{p["kind"]}">{fmt(v)}</td>' for p, v in zip(periods, r["values"]))
                        + "</tr>")
    note = f'<p class="note">{escape(prod["note"], quote=False)}</p>' if prod.get("note") else ""
    return (f'<div class="sheet"><div class="hd"><h2>{escape(data["title"], quote=False)}: '
            f'{escape(prod["name"], quote=False)}</h2><span class="unit">Unit: {escape(data["unit"], quote=False)}</span></div>'
            f'<table>{head}<tbody>{"".join(body)}</tbody></table>{note}</div>')


def build_html(data: dict, colors: dict) -> str:
    """data: cost_production.generate(); colors: colors_loader.load_colors_config()."""
    def c(k, dflt):  # defaults mirror colors_loader._DEFAULTS
        return colors.get(k, dflt)
    blk = c("border_black", "#000000")
    css = f"""
  {_fonts()}
  @page {{ size: A4 landscape; margin: 10mm; }}
  body {{ font-family: 'IBM Plex Sans', Arial, sans-serif; margin: 0; color: {c("text_black", "#000000")};
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .sheet {{ break-after: page; width: {_W_PX}px; }}
  .sheet:last-child {{ break-after: auto; }}
  .hd {{ display: flex; justify-content: space-between; align-items: flex-end;
         border-bottom: 1.5px solid {c("text_primary", "#0f172a")}; padding-bottom: 3px; margin-bottom: 6px; }}
  h2 {{ font-size: 13pt; font-weight: 700; color: rgb(0,0,255); margin: 0; }}
  .unit {{ font-size: 10pt; font-weight: 500; }}
  .empty {{ font-size: 11pt; font-weight: 700; margin-top: 12px; }}
  .note {{ font-size: 9pt; font-style: italic; margin: 4px 0 0; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid {blk}; padding: 4px 6px; font-size: 10.5pt; white-space: nowrap; }}
  th {{ background: {c("table_header_bg", "#dbeafe")}; font-weight: 700; text-align: center; }}
  td {{ text-align: right; }}
  .l {{ text-align: left; }}
  tr.blk td {{ font-weight: 700; color: rgb(0,0,255); background: {c("highlight_group_label_bg", "#e0e7ff")}; }}
  tr.sail td {{ font-weight: 700; background: {c("mines_perf_total_bg", "#FEF3C7")}; }}
  th.till, td.till {{ background: {c("perf_gr_bg", "#e2e8f0")}; }}
  tr.sail td.till {{ background: {c("perf_gr_bg", "#e2e8f0")}; }}
"""
    if data["products"] and data["periods"]:
        body = "".join(_product(data, p) for p in data["products"])
    else:
        body = (f'<div class="hd"><h2>{escape(data["title"], quote=False)}</h2></div>'
                '<p class="empty">No cost of production data entered for this period.</p>')
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'


def render_pdf(data: dict, colors: dict) -> bytes:
    """Synchronous -- call from a plain `def` route (FastAPI threadpool)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": _W_PX, "height": 700})
        page.emulate_media(media="print")
        page.set_content(build_html(data, colors), wait_until="load")
        page.evaluate("document.fonts.ready.then(() => true)")
        pdf = page.pdf(format="A4", landscape=True, print_background=True, margin=_MARGIN)
        browser.close()
    return pdf
