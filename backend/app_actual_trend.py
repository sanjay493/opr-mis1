"""APP (or MoU) vs Actual performance trend for one financial year
(/reports/excel tab 'app-actual-trend'), after the "APP Vs Actual performance
trend" sheet: Hot Metal, Crude Steel, Saleable Steel, Saleable production
(Saleable Steel + Pig Iron) and Finished Steel, plant-wise with SAIL-5 PL
and SAIL totals; for each a Plan, Act and % ful row over the 12 months,
Q1-Q4, H1, H2 and the FY. Finished Steel ends, like the MIS report's page 4,
with Conversion (SAIL actual only, no plan) and SAIL incl. Conv. (SAIL's
plan against SAIL's actual plus Conversion).

Figures come from production_monthly (repo.production.values): actual, and
the plan as APP (abp) or MoU. A cell with no DB row is blank, not 0; a total
(SAIL rows, quarters, halves, FY) sums what is there and is blank only when
nothing is. % ful is Act / Plan of the same cell, blank when either is
blank or the plan is 0. Like the sheet, a period's % ful compares the
actuals entered so far with the whole period's plan."""

import calendar
import io
from html import escape

from constants import FIVE_PLANTS
from repo import production as rp

BASIS = {"app": ("abp", "APP"), "mou": ("mou", "MoU")}

# (section title, DB items summed, plants after SAIL-5 PL that join SAIL)
ITEMS = [
    ("Hot Metal", ["Hot Metal"], ["VISL"]),
    ("Crude Steel", ["Total Crude Steel"], ["ASP", "SSP", "VISL"]),
    ("Saleable Steel", ["Saleable Steel"], ["ASP", "SSP", "VISL"]),
    ("Saleable production", ["Saleable Steel", "Pig Iron"], ["ASP", "SSP", "VISL"]),
    ("Finished Steel", ["Finished Steel"], ["ASP", "SSP", "VISL"]),
]
CONV_ITEM = "Conversion"       # production_monthly row of plant SAIL
FIVE_PL = "SAIL-5 PL"
PAGES = [(0, 1), (2, 3), (4,)]   # sections per PDF page; the first two as the reference sheet


def fy_months(fy_start):
    return [f"{fy_start + (m < 4)}-{m:02d}" for m in (4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3)]


def fy_label(fy_start):
    return f"{fy_start}-{(fy_start + 1) % 100:02d}"


def columns(fy_start):
    """[{label, kind: m|q|h|fy, months}] in sheet order, H1 after Q2, H2 after Q4."""
    ms = fy_months(fy_start)
    mon = [{"label": f"{calendar.month_abbr[int(m[5:])]}-{m[2:4]}", "kind": "m", "months": [m]} for m in ms]
    q = [{"label": f"Q{i + 1}", "kind": "q", "months": ms[3 * i:3 * i + 3]} for i in range(4)]
    h = [{"label": f"H{i + 1}", "kind": "h", "months": ms[6 * i:6 * i + 6]} for i in range(2)]
    return (mon[0:3] + [q[0]] + mon[3:6] + [q[1], h[0]] + mon[6:9] + [q[2]] + mon[9:12] + [q[3], h[1]]
            + [{"label": fy_label(fy_start), "kind": "fy", "months": ms}])


def _sum(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def _pct(act, plan):
    return None if act is None or not plan else act * 100.0 / plan


def available_fys():
    """FY start years that have production actual or plan rows, newest first."""
    from repo import conn as rc
    with rc.cursor() as cur:
        months = [r[0] for r in rp.production_report_months(cur)]
    return sorted({int(m[:4]) - (int(m[5:7]) < 4) for m in months if m}, reverse=True)


def build(fy_start, basis="app"):
    measure, plan_label = BASIS[basis]
    months = fy_months(fy_start)
    plants = FIVE_PLANTS + ["ASP", "SSP", "VISL", "SAIL"]
    db_items = sorted({i for _, items, _ in ITEMS for i in items} | {CONV_ITEM})

    def index(measure):
        return {(m, p.upper(), i.lower()): v for (m, p, i), v in rp.values(months, plants, db_items, measure).items()}

    src = {"act": index("actual"), "plan": index(measure)}
    cols = columns(fy_start)

    def monthly(kind, plant_list, items):
        return {m: _sum([src[kind].get((m, p.upper(), i.lower())) for p in plant_list for i in items])
                for m in months}

    def finish(out, by_month):
        for kind in ("plan", "act"):
            out[kind] = [_sum([by_month[kind][m] for m in c["months"]]) for c in cols]
        out["pct"] = [_pct(a, p) for a, p in zip(out["act"], out["plan"])]
        return out

    def row(label, plant_list, items, total=False):
        return finish({"plant": label, "total": total},
                      {kind: monthly(kind, plant_list, items) for kind in ("plan", "act")})

    def conversion_rows(items, extra):
        conv = monthly("act", ["SAIL"], [CONV_ITEM])
        sail = {kind: monthly(kind, FIVE_PLANTS + extra, items) for kind in ("plan", "act")}
        return [
            finish({"plant": "Conversion", "total": False}, {"plan": {m: None for m in months}, "act": conv}),
            finish({"plant": "SAIL incl. Conv.", "total": True},
                   {"plan": sail["plan"], "act": {m: _sum([sail["act"][m], conv[m]]) for m in months}}),
        ]

    sections = []
    for title, items, extra in ITEMS:
        rows = [row(p, [p], items) for p in FIVE_PLANTS]
        rows.append(row(FIVE_PL, FIVE_PLANTS, items, total=True))
        rows += [row(p, [p], items) for p in extra]
        rows.append(row("SAIL", FIVE_PLANTS + extra, items, total=True))
        if title == "Finished Steel":
            rows += conversion_rows(items, extra)
        sections.append({"item": title, "rows": rows})
    return {
        "fy": fy_start, "fy_label": fy_label(fy_start), "basis": basis, "plan_label": plan_label,
        "title": f"{plan_label}/Actual performance trend : {fy_label(fy_start)}",
        "columns": [{"label": c["label"], "kind": c["kind"]} for c in cols],
        "sections": sections,
        "has_plan": any(v is not None for s in sections for r in s["rows"] for v in r["plan"]),
    }


def filename(rep, ext):
    return f"{rep['plan_label']}_Vs_Actual_Performance_Trend_{rep['fy_label']}.{ext}"


# --------------------------------------------------------------------------
# PDF (HTML for Playwright)
# --------------------------------------------------------------------------

def _n(v):
    if v is None:
        return ""
    s = f"{v:.0f}"
    return "0" if s == "-0" else s


def _section_html(sec, rep):
    cols = rep["columns"]
    body = []
    n_rows = 3 * len(sec["rows"])
    for k, r in enumerate(sec["rows"]):
        for j, (kind, label) in enumerate((("plan", rep["plan_label"]), ("act", "Act"), ("pct", "% ful"))):
            cells = []
            if k == 0 and j == 0:
                cells.append(f'<td rowspan="{n_rows}" class="item"><div>{escape(sec["item"])}</div></td>')
            if j == 0:
                cells.append(f'<td rowspan="3" class="plant">{escape(r["plant"])}</td>')
            cells.append(f'<td class="kind">{label}</td>')
            for c, v in zip(cols, r[kind]):
                cls = [c["kind"]]
                if kind == "pct" and v is not None and round(v) < 100:
                    cls.append("low")
                cells.append(f'<td class="{" ".join(cls)}">{_n(v)}</td>')
            tr = [kind] + (["first"] if j == 0 else []) + (["tot"] if r["total"] else [])
            body.append(f'<tr class="{" ".join(tr)}">{"".join(cells)}</tr>')
    return "".join(body)


def build_html(rep, colors):
    def c(k, dflt):  # defaults mirror colors_loader._DEFAULTS
        return colors.get(k, dflt)
    blk, txt = c("border_black", "#000000"), c("text_black", "#000000")
    head = ('<tr><th class="l" colspan="3">Items</th>'
            + "".join(f'<th class="{x["kind"]}">{escape(x["label"])}</th>' for x in rep["columns"]) + "</tr>")
    note = "" if rep["has_plan"] else f'<p class="note">No {rep["plan_label"]} data in the database for FY {rep["fy_label"]}.</p>'
    # Months narrow, the 5-digit half-year and FY totals wider.
    width = {"m": 30, "q": 34, "h": 39, "fy": 40}
    cols = ('<colgroup><col style="width:22px"><col style="width:50px"><col style="width:30px">'
            + "".join(f'<col style="width:{width[x["kind"]]}px">' for x in rep["columns"]) + "</colgroup>")
    pages = []
    for n, idx in enumerate(PAGES):
        top = (f'<div class="hd"><h2>{escape(rep["title"])}</h2></div><div class="unit">Unit: \'000 T</div>{note}'
               if n == 0 else "")
        body = "".join(_section_html(rep["sections"][i], rep) for i in idx)
        pages.append(f'<section class="sheet">{top}<table>{cols}<thead>{head}</thead><tbody>{body}</tbody></table></section>')
    css = f"""
  @page {{ size: A4 portrait; margin: 8mm 8mm 8mm 8mm; }}
  body {{ font-family: Arial, sans-serif; margin: 0; color: {txt};
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .sheet {{ page-break-after: always; }}
  .sheet:last-child {{ page-break-after: auto; }}
  h2 {{ font-family: 'Times New Roman', serif; font-size: 12pt; margin: 0; }}
  .unit {{ font-size: 7pt; }}
  .note {{ font-size: 9pt; font-weight: 700; margin: 2px 0; }}
  table {{ border-collapse: collapse; width: 100%; table-layout: fixed; border: 1px solid {blk}; }}
  th, td {{ white-space: nowrap; overflow: hidden; padding: 0 1px; line-height: 1.15; }}
  th {{ font-size: 6.5pt; font-weight: 700; text-align: center; border: 1px solid {blk}; }}
  th.l {{ text-align: left; }}
  td {{ font-size: 8pt; text-align: center; border-left: 1px solid {c("border_medium", "#94a3b8")};
        border-bottom: 1px dotted {c("border_medium", "#94a3b8")}; }}
  td.item {{ border: 1px solid {blk}; vertical-align: middle; padding: 0; }}
  td.item div {{ writing-mode: vertical-rl; transform: rotate(180deg); font-size: 17pt; font-weight: 700;
                 margin: 0 auto; }}
  td.plant {{ text-align: left; font-size: 6.5pt; white-space: normal; font-weight: 700;
              color: {c("trend_plan_text", "#0000FF")}; vertical-align: top; }}
  td.kind {{ text-align: left; font-size: 6.5pt; }}
  tr.plan td.kind, tr.pct td.kind {{ font-weight: 700; }}
  tr.plan td.kind {{ color: {c("trend_plan_text", "#0000FF")}; }}
  tr.first td {{ border-top: 1px solid {blk}; }}
  tr.plan td:not(.item):not(.plant):not(.kind) {{ color: {c("trend_plan_text", "#0000FF")}; font-weight: 700; }}
  tr.act td:not(.item):not(.plant):not(.kind) {{ font-style: italic; }}
  tr.act td.q, tr.act td.h, tr.act td.fy {{ font-weight: 700; }}
  tr.pct td:not(.item):not(.plant):not(.kind) {{ font-weight: 700; }}
  tr.pct td.low {{ color: {c("trend_low_pct_text", "#FF0000")}; }}
  td.q, td.h, th.q, th.h {{ background: {c("trend_period_bg", "#E2EFDA")}; }}
  td.fy, th.fy {{ background: {c("trend_fy_bg", "#F2F2F2")}; }}
"""
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{"".join(pages)}</body></html>'


# Zoom a sheet down if too tall, else grow its rows to fill the page; every
# sheet gets the smallest sheet's row growth, so the shorter Finished Steel
# page keeps the row height of the first two.
_FIT_JS = """(H) => {
    const sheets = Array.from(document.querySelectorAll('.sheet'));
    const extras = sheets.map(s => {
        const h = s.getBoundingClientRect().height;
        if (h > H) { s.style.zoom = H / h; return 0; }
        return (H - h) * 0.97 / s.querySelectorAll('tbody tr').length;
    });
    const extra = Math.min(...extras);
    if (extra > 0) sheets.forEach(s => {
        const rows = Array.from(s.querySelectorAll('tbody tr'));
        const hs = rows.map(r => r.getBoundingClientRect().height);
        rows.forEach((r, i) => r.style.height = (hs[i] + extra) + 'px');
    });
}"""
_W_PX, _H_PX = 733, 1062   # A4 portrait minus 8 mm margins, at 96 dpi


def render_pdf(html):
    """Synchronous; call from a plain-def FastAPI handler (threadpool)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": _W_PX, "height": _H_PX})
        page.emulate_media(media="print")
        page.set_content(html, wait_until="load")
        page.evaluate(_FIT_JS, _H_PX)
        pdf = page.pdf(format="A4", print_background=True,
                       margin={"top": "8mm", "right": "8mm", "bottom": "8mm", "left": "8mm"})
        browser.close()
    return pdf


# --------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------

def build_xlsx(rep, colors):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    def hexc(k, dflt):
        return colors.get(k, dflt).lstrip("#").upper()
    blue, red = hexc("trend_plan_text", "#0000FF"), hexc("trend_low_pct_text", "#FF0000")
    fills = {"q": PatternFill("solid", fgColor=hexc("trend_period_bg", "#E2EFDA")),
             "h": PatternFill("solid", fgColor=hexc("trend_period_bg", "#E2EFDA")),
             "fy": PatternFill("solid", fgColor=hexc("trend_fy_bg", "#F2F2F2"))}
    thin, dot = Side(style="thin"), Side(style="dotted", color="94A3B8")
    center = Alignment(horizontal="center", vertical="center")

    wb = Workbook()
    ws = wb.active
    ws.title = f"{rep['plan_label']} vs Actual"
    cols = rep["columns"]
    ws.cell(1, 1, rep["title"]).font = Font(bold=True, size=12)
    ws.cell(2, 1, "Unit:'000 T").font = Font(size=8)
    ws.cell(3, 1, "Items").font = Font(bold=True)
    for j, c in enumerate(cols):
        cell = ws.cell(3, 4 + j, c["label"])
        cell.font, cell.alignment = Font(bold=True), center
        cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
        if c["kind"] in fills:
            cell.fill = fills[c["kind"]]
    r = 4
    for sec in rep["sections"]:
        start = r
        for row in sec["rows"]:
            for j, (kind, label) in enumerate((("plan", rep["plan_label"]), ("act", "Act"), ("pct", "% ful"))):
                if j == 0:
                    ws.cell(r, 2, row["plant"]).font = Font(bold=True, color=blue, size=9)
                lab = ws.cell(r, 3, label)
                lab.font = Font(size=8, bold=kind != "act", color=blue if kind == "plan" else None)
                for k, (c, v) in enumerate(zip(cols, row[kind])):
                    cell = ws.cell(r, 4 + k, None if v is None else round(v) if kind == "pct" else v)
                    cell.number_format = "0"
                    cell.alignment = center
                    bold = kind != "act" or c["kind"] != "m"
                    color = blue if kind == "plan" else red if (kind == "pct" and v is not None and round(v) < 100) else None
                    cell.font = Font(bold=bold, italic=kind == "act", color=color)
                    if c["kind"] in fills:
                        cell.fill = fills[c["kind"]]
                    cell.border = Border(left=dot, right=dot, bottom=dot, top=thin if j == 0 else None)
                for cc in (2, 3):
                    ws.cell(r, cc).border = Border(top=thin if j == 0 else None, left=thin if cc == 2 else None)
                r += 1
        ws.merge_cells(start_row=start, start_column=1, end_row=r - 1, end_column=1)
        it = ws.cell(start, 1, sec["item"])
        it.font = Font(bold=True, size=16)
        it.alignment = Alignment(text_rotation=90, horizontal="center", vertical="center")
        for rr in range(start, r):
            ws.cell(rr, 1).border = Border(left=thin, right=thin, top=thin if rr == start else None,
                                           bottom=thin if rr == r - 1 else None)
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 6
    for j, c in enumerate(cols):
        ws.column_dimensions[get_column_letter(4 + j)].width = 9 if c["kind"] == "fy" else 7
    ws.freeze_panes = ws.cell(4, 4)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToHeight = 0
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
