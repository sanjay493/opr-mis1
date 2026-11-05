"""SAIL Mill Production Performance for one financial year (/reports/excel
tab 'mills-performance'), after the "Mills Performance" sheet: every major
mill of the five integrated plants, with its capacity, and a Plan (APP),
Actual and %Ful row over the 12 months, Q1-Q4, H1, H2, the FY and the
cumulative Apr-to-latest-month. A mill with no plan or actual in the FY
(e.g. DSP's Section Mill) is left out.

Figures come from production_monthly (repo.production.values): actual, and
the APP monthly plan (abp). A cell with no DB row is blank, not 0; a period
total sums what is there and is blank only when nothing is. %Ful is Actual /
Plan of the same cell, blank when either is blank or the plan is 0. The
cumulative column runs from April to the FY's latest month with a mill
actual, plan and actual over the same months.

Mill capacities are not in the capacity table; a capacity entry for the
mill's DB item (plant, item) takes precedence over the sheet's figure."""

import calendar
import io
from html import escape

import app_actual_trend as trend
from repo import capacity as rcap
from repo import production as rp

# (plant, plant note, [(mill, DB items summed, sheet capacity)])
MILLS = [
    ("BSP", "", [
        ("WRM", ["WIRERODS"], "550"),
        ("MM", ["MM"], "750"),
        ("BRM", ["BARS&RODMILL"], "900"),
        ("RSM", ["RSM_RAIL"], "850 (500)"),
        ("URM", ["URM_RAIL"], "1200"),
        ("PM", ["PLATEMILL"], "1300 (1000)"),
    ]),
    ("DSP", "(excluding SM)", [
        ("Section Mill", ["SM"], "150"),
        ("MSM", ["MSM"], "1000"),
        ("MM", ["MM"], "360"),
        ("W&A", ["WAP"], "32"),
    ]),
    ("RSP", "", [
        ("PM", ["OPM Plate"], "500"),
        ("NPM", ["NPM Plate"], "920"),
        ("HSM-2", ["HSM-2 Total HR Coil"], "2940"),
        ("ERW", ["ERW Pipes"], "75"),
        ("SWPP", ["SW Pipes"], "55"),
        ("SSM", ["CRNO Coils"], "75"),
    ]),
    ("BSL", "", [
        ("HSM", ["HSM Total HR Coil"], "4500"),
        ("CRM-I/II", ["CR(1&2) Total Saleable"], "1200"),
        ("CRM-III", ["CR III Total Saleable"], "1200"),
    ]),
    ("ISP", "", [
        ("WRM", ["WRMILL"], "550"),
        ("BAR Mill", ["BARMILL"], "900"),
        ("USM", ["USMILL"], "850"),
    ]),
]
PLANT_CAP_ITEM = "Finished Steel"   # the plant's capacity shown under its name
KINDS = (("plan", "Plan"), ("act", "Actual"), ("pct", "%Ful"))


def _mon(m):
    return f"{calendar.month_abbr[int(m[5:])]}'{m[2:4]}"


def columns(fy_start, cum_upto=None):
    """trend.columns relabelled as the sheet (Apr'26, Q-1, H-1), plus the
    cumulative Apr-to-cum_upto column when given."""
    cols = []
    for c in trend.columns(fy_start):
        c = dict(c)
        if c["kind"] == "m":
            c["label"] = _mon(c["months"][0])
        elif c["kind"] in ("q", "h"):
            c["label"] = f"{c['label'][0]}-{c['label'][1:]}"
        cols.append(c)
    if cum_upto:
        ms = trend.fy_months(fy_start)
        upto = ms[:ms.index(cum_upto) + 1]
        label = _mon(cum_upto) if len(upto) == 1 else f"Apr-{_mon(cum_upto)}"
        cols.append({"label": label, "kind": "cum", "months": upto})
    return cols


def _capacity(plant, items, month, fallback):
    v = rcap.get_effective_capacity(plant, items[0], month) if len(items) == 1 else None
    return fallback if v is None else f"{v:g}"


def build(fy_start):
    months = trend.fy_months(fy_start)
    plants = [p for p, _, _ in MILLS]
    db_items = sorted({i for _, _, mills in MILLS for _, items, _ in mills for i in items})

    def index(measure):
        return {(m, p.upper(), i.lower()): v for (m, p, i), v in rp.values(months, plants, db_items, measure).items()}

    src = {"act": index("actual"), "plan": index("abp")}
    with_act = [m for m in months if any(k[0] == m and v is not None for k, v in src["act"].items())]
    cols = columns(fy_start, with_act[-1] if with_act else None)

    out = []
    for plant, note, mills in MILLS:
        cap = rcap.get_effective_capacity(plant, PLANT_CAP_ITEM, months[0])
        rows = []
        for mill, items, cap_label in mills:
            by_month = {kind: {m: trend._sum([src[kind].get((m, plant.upper(), i.lower())) for i in items])
                               for m in months} for kind in ("plan", "act")}
            r = {"mill": mill, "capacity": _capacity(plant, items, months[0], cap_label)}
            for kind in ("plan", "act"):
                r[kind] = [trend._sum([by_month[kind][m] for m in c["months"]]) for c in cols]
            r["pct"] = [trend._pct(a, p) for a, p in zip(r["act"], r["plan"])]
            if any(v is not None for v in r["plan"] + r["act"]):   # a mill with no data at all is left out
                rows.append(r)
        if rows:
            out.append({"plant": plant, "capacity": None if cap is None else f"{cap:g}", "note": note, "mills": rows})
    return {
        "fy": fy_start, "fy_label": trend.fy_label(fy_start),
        "title": f"SAIL Mill Production Performance for FY {trend.fy_label(fy_start)}",
        "columns": [{k: c[k] for k in ("label", "kind")} for c in cols],
        "plants": out,
        "has_plan": any(v is not None for p in out for r in p["mills"] for v in r["plan"]),
    }


def filename(rep, ext):
    return f"Mills_Performance_{rep['fy_label']}.{ext}"


def fmt(v, col_kind, kind):
    """Sheet's number style: a month's tonnage under 10 to one decimal,
    everything else whole; blank for no data."""
    if v is None:
        return ""
    s = f"{v:.1f}" if kind != "pct" and col_kind == "m" and abs(v) < 10 else f"{v:.0f}"
    return s.lstrip("-") if float(s) == 0 else s


# --------------------------------------------------------------------------
# PDF (HTML for Playwright)
# --------------------------------------------------------------------------

def cap_lines(cap):
    """A capacity with a bracketed figure on two lines: '1300 (1000)' ->
    ['1300', '(1000)']."""
    return [x.strip() for x in (cap or "").replace("(", "\n(", 1).split("\n") if x.strip()]


def _plant_label(p):
    return "<br>".join(escape(x) for x in (p["plant"], p["capacity"] or "", p["note"]) if x)


def build_html(rep, colors):
    def c(k, dflt):  # defaults mirror colors_loader._DEFAULTS
        return colors.get(k, dflt)
    blk, txt = c("border_black", "#000000"), c("text_black", "#000000")
    cols = rep["columns"]
    head = ('<tr><th>Plant</th><th>Mill</th><th>Capacity</th><th></th>'
            + "".join(f'<th class="{x["kind"]}">{escape(x["label"])}</th>' for x in cols) + "</tr>")
    width = {"m": 31, "q": 33, "h": 36, "fy": 38, "cum": 44}
    colgroup = ('<colgroup><col style="width:36px"><col style="width:36px"><col style="width:28px">'
                '<col style="width:30px">' + "".join(f'<col style="width:{width[x["kind"]]}px">' for x in cols)
                + "</colgroup>")
    body = []
    for p in rep["plants"]:
        n = 3 * len(p["mills"])
        for k, r in enumerate(p["mills"]):
            for j, (kind, label) in enumerate(KINDS):
                cells = []
                if k == 0 and j == 0:
                    cells.append(f'<td rowspan="{n}" class="plant">{_plant_label(p)}</td>')
                if j == 0:
                    cells.append(f'<td rowspan="3" class="mill">{escape(r["mill"])}</td>'
                                 f'<td rowspan="3" class="mill">{"<br>".join(escape(x) for x in cap_lines(r["capacity"]))}</td>')
                cells.append(f'<td class="kind">{label}</td>')
                for col, v in zip(cols, r[kind]):
                    cls = [col["kind"]] + (["low"] if kind == "pct" and v is not None and round(v) < 100 else [])
                    cells.append(f'<td class="{" ".join(cls)}">{fmt(v, col["kind"], kind)}</td>')
                tr = [kind] + (["first"] if j == 0 else []) + (["pfirst"] if j == 0 and k == 0 else [])
                body.append(f'<tr class="{" ".join(tr)}">{"".join(cells)}</tr>')
    note = "" if rep["has_plan"] else f'<p class="note">No APP data in the database for FY {rep["fy_label"]}.</p>'
    css = f"""
  @page {{ size: A4 landscape; margin: 6mm 6mm 6mm 6mm; }}
  body {{ font-family: 'Times New Roman', serif; margin: 0; color: {txt};
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  h2 {{ font-size: 12pt; margin: 0; text-align: center; }}
  .unit {{ font-size: 7pt; text-align: right; }}
  .note {{ font-size: 9pt; font-weight: 700; margin: 2px 0; }}
  table {{ border-collapse: collapse; width: 100%; table-layout: fixed; border: 1px solid {blk}; }}
  th, td {{ white-space: nowrap; overflow: hidden; padding: 0 1px; line-height: 1.0; }}
  th {{ font-size: 7pt; font-weight: 400; text-align: center; border: 1px solid {blk}; }}
  td {{ font-size: 7pt; text-align: center; border: 1px solid {c("border_medium", "#94a3b8")}; }}
  td.plant {{ border: 1px solid {blk}; font-size: 7pt; vertical-align: middle; white-space: normal; }}
  td.mill {{ border-top: 1px solid {blk}; font-size: 7pt; vertical-align: middle; white-space: normal; }}
  td.kind {{ text-align: left; font-size: 6.5pt; }}
  tr.first td {{ border-top: 1px solid {blk}; }}
  tr.pfirst td {{ border-top: 1.5px solid {blk}; }}
  tr.plan td:not(.plant):not(.mill):not(.kind) {{ color: {c("trend_plan_text", "#0000FF")}; }}
  tr.pct td.low {{ color: {c("trend_low_pct_text", "#FF0000")}; }}
  td.q, td.h, th.q, th.h {{ background: {c("trend_period_bg", "#E2EFDA")}; font-weight: 700; }}
  td.fy, th.fy, td.cum, th.cum {{ background: {c("trend_fy_bg", "#F2F2F2")}; font-weight: 700; }}
"""
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>'
            f'<section class="sheet"><h2>{escape(rep["title"])}</h2><div class="unit">Unit:\'000T</div>{note}'
            f'<table>{colgroup}<thead>{head}</thead><tbody>{"".join(body)}</tbody></table></section></body></html>')


_W_PX, _H_PX = 1077, 748   # A4 landscape minus 6 mm margins, at 96 dpi


def render_pdf(html):
    """Synchronous; call from a plain-def FastAPI handler (threadpool). One
    landscape page: trend's fit zooms the sheet down or grows its rows."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": _W_PX, "height": _H_PX})
        page.emulate_media(media="print")
        page.set_content(html, wait_until="load")
        page.evaluate(trend._FIT_JS, _H_PX)
        pdf = page.pdf(format="A4", landscape=True, print_background=True,
                       margin={"top": "6mm", "right": "6mm", "bottom": "6mm", "left": "6mm"})
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
    period = PatternFill("solid", fgColor=hexc("trend_period_bg", "#E2EFDA"))
    total = PatternFill("solid", fgColor=hexc("trend_fy_bg", "#F2F2F2"))
    fills = {"q": period, "h": period, "fy": total, "cum": total}
    thin, hair = Side(style="thin"), Side(style="thin", color="94A3B8")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    box = Border(top=thin, bottom=thin, left=thin, right=thin)

    wb = Workbook()
    ws = wb.active
    ws.title = "Mills Performance"
    cols = rep["columns"]
    last = 4 + len(cols)
    ws.cell(1, 1, rep["title"]).font = Font(bold=True, size=12)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last)
    ws.cell(1, 1).alignment = Alignment(horizontal="center")
    ws.cell(2, last, "Unit:'000T").font = Font(size=8)
    for j, h in enumerate(["Plant", "Mill", "Capacity", ""] + [c["label"] for c in cols]):
        cell = ws.cell(3, 1 + j, h)
        cell.font, cell.alignment, cell.border = Font(bold=True), center, box
        if j >= 4 and cols[j - 4]["kind"] in fills:
            cell.fill = fills[cols[j - 4]["kind"]]
    r = 4
    for p in rep["plants"]:
        pstart = r
        for m in p["mills"]:
            mstart = r
            for kind, label in KINDS:
                ws.cell(r, 4, label).font = Font(size=8)
                ws.cell(r, 4).border = Border(left=hair, right=hair, bottom=hair, top=thin if r == mstart else hair)
                for k, (c, v) in enumerate(zip(cols, m[kind])):
                    s = fmt(v, c["kind"], kind)
                    cell = ws.cell(r, 5 + k, None if v is None else float(s))
                    cell.number_format = "0.0" if "." in s else "0"
                    cell.alignment = center
                    color = blue if kind == "plan" else red if (kind == "pct" and v is not None and round(v) < 100) else None
                    cell.font = Font(color=color, bold=c["kind"] != "m")
                    if c["kind"] in fills:
                        cell.fill = fills[c["kind"]]
                    cell.border = Border(left=hair, right=hair, bottom=hair, top=thin if r == mstart else hair)
                r += 1
            for col, val in ((2, m["mill"]), (3, "\n".join(cap_lines(m["capacity"])))):
                ws.merge_cells(start_row=mstart, start_column=col, end_row=r - 1, end_column=col)
                ws.cell(mstart, col, val).alignment = center
                for rr in range(mstart, r):
                    ws.cell(rr, col).border = Border(left=thin, right=thin, top=thin if rr == mstart else None,
                                                     bottom=thin if rr == r - 1 else None)
        ws.merge_cells(start_row=pstart, start_column=1, end_row=r - 1, end_column=1)
        ws.cell(pstart, 1, "\n".join(x for x in (p["plant"], p["capacity"] or "", p["note"]) if x)).alignment = center
        ws.cell(pstart, 1).font = Font(bold=True)
        for rr in range(pstart, r):
            ws.cell(rr, 1).border = Border(left=thin, right=thin, top=thin if rr == pstart else None,
                                           bottom=thin if rr == r - 1 else None)
    for col, w in (("A", 8), ("B", 8), ("C", 7), ("D", 7)):
        ws.column_dimensions[col].width = w
    for j, c in enumerate(cols):
        ws.column_dimensions[get_column_letter(5 + j)].width = 10 if c["kind"] == "cum" else 8 if c["kind"] == "fy" else 7
    ws.freeze_panes = ws.cell(4, 5)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
