"""Saleable Steel & Mills performance for one financial year (/reports/abp tab
'abp-mills'), after the "Mills Performance" sheet: each plant's mills, then its
Finished Steel, Semis, Saleable Steel and % Finished Steel, and the same four
rows for the five plants together.

Columns: installed capacity (the sheet's figure for a mill; item_capacity for
Finished Steel), the four previous FYs' actuals, the best FY before the selected
one, and for the selected FY its ABP (the monthly APP), Likely and best month.
  Likely = actual to date + running month's OP + remaining months' APP, as in
  abp_projection.py. An item with no OP for the running month uses APP.
  Semis = Saleable - Finished; % Finished = Finished / Saleable.

Figures come only from the DB. A past FY counts only when each of a row's items
has all 12 months: a part year would understate the row, so it is blank and can't
be the best FY. A row with no DB item (GP/GC Sheets, SPU Kandrori) stays blank.
The five plants' past FYs and best FY need all five plants to have the full year."""

import io
from html import escape

from abp_projection import _FIT_JS, _fmt, _pct, _projection_label, _short_fy, _sum
from app_actual_trend import available_fys, fy_label, fy_months  # noqa: F401  (available_fys: the API's FY list)
from constants import FIVE_PLANTS
from repo import production as rp
from repo.capacity import get_effective_capacity

# plant -> (name of its semis row, [(mill, DB items summed, sheet capacity)])
MILLS = {
    "BSP": ("Semis", [
        ("WRM", ["WIRERODS"], 550), ("MM", ["MM"], 750), ("PM", ["PLATEMILL"], 1000),
        ("BRM", ["BARS&RODMILL"], 900), ("RSM", ["RSM_RAIL"], 500), ("URM", ["URM_RAIL"], 1200),
    ]),
    "DSP": ("Semis", [
        ("MM", ["MM"], 360), ("SM(150)", ["SM"], 0), ("MSM", ["MSM"], 1000), ("WAP", ["WAP"], 32),
        ("SPU Kandrori", [], None), ("SPU Jagdishpur", ["SPU Jagdishpur"], None),
    ]),
    "RSP": ("Semis", [
        ("HSM-2 total HR Coils", ["HSM-2 Total HR Coil"], 2940),
        ("HSM-2(Coils/Plts/shts)", ["HSM-2 HR Coil (Sale)", "HSM-2 HR Plate"], 2681),
        ("NPM", ["NPM Plate"], 920), ("PM", ["OPM Plate"], 500), ("ERW", ["ERW Pipes"], 75),
        ("SW", ["SW Pipes"], 55), ("CRNO", ["CRNO Coils"], 75), ("GP/GC Sheets(120)", [], 0),
    ]),
    "BSL": ("Slabs", [
        ("HSM", ["HSM Total HR Coil"], 4500), ("HR Coil for Sale", ["HSM HR Coil (Sale)"], None),
        ("HR Plate/sheet", ["HSM HR Plate", "HR Sheet"], None),
        ("CRM-1&2", ["CR(1&2) Total Saleable"], 1200), ("CRM-3", ["CR III Total Saleable"], 1200),
    ]),
    "ISP": ("Semis", [
        ("WRM", ["WRMILL"], 550), ("Bar Mill", ["BARMILL"], 900), ("USM", ["USMILL"], 850),
    ]),
}
FINISHED, SALEABLE = "Finished Steel", "Saleable Steel"
FIVE = "5 Plants"
N_PAST = 4
FIRST_FY = 1964   # the oldest actual in production_monthly


def _minus(a, b):
    return None if a is None or b is None else a - b


def _best(totals):
    """(value, FY label) of the highest of {fy: total}; a tie goes to the latest
    FY, and an FY with no total is skipped."""
    best, period = None, ""
    for y in sorted(totals):
        if totals[y] is not None and (best is None or totals[y] >= best):
            best, period = totals[y], _short_fy(y)
    return best, period


def _derived(rows_by_kind, semis_label, past_len):
    """The Semis and % Finished rows from Finished and Saleable."""
    fin, sale = rows_by_kind["finished"], rows_by_kind["saleable"]
    def blank(label, kind):
        return {"label": label, "kind": kind, "capacity": None, "best_act": None, "best_period": "", "best_month": None}
    semis = blank(semis_label, "semis")
    pct = blank("% Finished Steel", "pct")
    semis["past"] = [_minus(sale["past"][i], fin["past"][i]) for i in range(past_len)]
    pct["past"] = [_pct(fin["past"][i], sale["past"][i]) for i in range(past_len)]
    for k in ("abp", "likely"):
        semis[k] = _minus(sale[k], fin[k])
        pct[k] = _pct(fin[k], sale[k])
    return semis, pct


def build(fy_start):
    months = fy_months(fy_start)
    past_fys = [fy_start - n for n in range(N_PAST, 0, -1)]
    history_fys = list(range(FIRST_FY, fy_start))
    history = {y: fy_months(y) for y in history_fys}
    all_months = [m for y in history_fys for m in history[y]] + months
    db_items = sorted({i for _, mills in MILLS.values() for _, items, _ in mills for i in items} | {FINISHED, SALEABLE})

    def index(rows):
        return {(m, p.upper(), i.lower()): v for (m, p, i), v in rows.items()}

    act = index(rp.values(all_months, FIVE_PLANTS, db_items, "actual"))
    app = index(rp.values(months, FIVE_PLANTS, db_items, "abp"))

    # One cut-off for every row, so the Likely header holds for the whole sheet.
    with_act = [m for m in months
                if any(act.get((m, p, i.lower())) is not None for p in FIVE_PLANTS for i in db_items)]
    act_months = months[:months.index(with_act[-1]) + 1] if with_act else []
    after = months[len(act_months):]
    running, rest = (after[0], after[1:]) if after else (None, [])
    op = {}
    if running:
        op = {(p.upper(), i.lower()): v for _, p, i, v in rp.op_plan_month_rows([running], FIVE_PLANTS)}
    op_missing = []

    def fy_total(plant, items, y):
        """The FY's total, or None unless every item has all 12 months."""
        if not items:
            return None
        vals = [act.get((m, plant, i.lower())) for i in items for m in history[y]]
        return None if any(v is None for v in vals) else sum(vals)

    def row(plant, label, kind, items, capacity):
        pu = plant.upper()
        by_month = [_sum([act.get((m, pu, i.lower())) for i in items]) for m in act_months]
        running_vals = []
        missing = False
        if running:
            for i in items:
                v = op.get((pu, i.lower()))
                if v is None:
                    v = app.get((running, pu, i.lower()))
                    missing = missing or bool(v)
                running_vals.append(v)
        if op and missing:
            op_missing.append(f"{plant}: {label}")
        totals = {y: fy_total(pu, items, y) for y in history_fys}
        best_act, best_period = _best(totals)
        return {
            "label": label, "kind": kind, "capacity": None if capacity is None else float(capacity),
            "past": [totals.get(y) for y in past_fys],
            "best_act": best_act, "best_period": best_period,
            "abp": _sum([app.get((m, pu, i.lower())) for m in months for i in items]),
            "likely": _sum(by_month + running_vals + [app.get((m, pu, i.lower())) for m in rest for i in items]),
            "best_month": max((v for v in by_month if v is not None), default=None) if kind == "mill" else None,
        }

    plants = []
    per_plant = {}
    for plant, (semis_label, mills) in MILLS.items():
        rows = [row(plant, label, "mill", items, cap) for label, items, cap in mills]
        finished = row(plant, FINISHED, "finished", [FINISHED],
                       get_effective_capacity(plant, FINISHED, months[-1]))
        saleable = row(plant, SALEABLE, "saleable", [SALEABLE], None)
        semis, pct = _derived({"finished": finished, "saleable": saleable}, semis_label, N_PAST)
        per_plant[plant] = {"finished": finished, "saleable": saleable}
        plants.append({"plant": plant, "rows": rows + [finished, semis, saleable, pct]})

    def five_row(label, kind, item):
        rows = [per_plant[p][kind] for p in FIVE_PLANTS]
        totals = {}
        for y in history_fys:
            vals = [fy_total(p, [item], y) for p in FIVE_PLANTS]
            totals[y] = None if any(v is None for v in vals) else sum(vals)
        best_act, best_period = _best(totals)
        return {
            "label": label, "kind": kind, "capacity": _sum([r["capacity"] for r in rows]),
            "past": [totals.get(y) for y in past_fys],
            "best_act": best_act, "best_period": best_period,
            "abp": _sum([r["abp"] for r in rows]), "likely": _sum([r["likely"] for r in rows]),
            "best_month": None,
        }

    fin5, sale5 = five_row(FINISHED, "finished", FINISHED), five_row(SALEABLE, "saleable", SALEABLE)
    semis5, pct5 = _derived({"finished": fin5, "saleable": sale5}, "Semis for sale", N_PAST)
    plants.append({"plant": FIVE, "rows": [fin5, semis5, sale5, pct5]})

    label = fy_label(fy_start)
    return {
        "fy": fy_start, "fy_label": label, "short_fy": _short_fy(fy_start),
        "title": "Saleable Steel & Mills performance",
        "past_labels": [_short_fy(y) for y in past_fys],
        "likely_label": _projection_label(act_months, running, rest, bool(op)),
        "plants": plants,
        "op_missing": op_missing,
        "has_plan": any(r["abp"] is not None for p in plants for r in p["rows"]),
    }


def filename(rep, ext):
    return f"Saleable_Steel_Mills_Performance_{rep['fy_label']}.{ext}"


def notes(rep):
    """Lines printed under the table."""
    out = []
    if not rep["has_plan"]:
        out.append(f"No APP data in the database for FY {rep['fy_label']}.")
    if rep["op_missing"]:
        out.append("No OP for the running month, APP used: " + "; ".join(rep["op_missing"]) + ".")
    return out


def _cells(r):
    """The figure cells left to right, shared by the PDF and the Excel: values,
    except the Best Achieved period, which is text."""
    return [r["capacity"]] + r["past"] + [r["best_act"], r["best_period"], r["abp"], r["likely"], r["best_month"]]


# --------------------------------------------------------------------------
# PDF (HTML for Playwright)
# --------------------------------------------------------------------------

def _head_html(rep):
    past = "".join(f"<th>{escape(x)}</th>" for x in rep["past_labels"])
    return (
        '<tr><th rowspan="2">Plants</th><th rowspan="2">Mills</th><th rowspan="2">Installed<br>Capacity</th>'
        f'{past}<th colspan="2">Best Achieved</th><th colspan="3">{escape(rep["short_fy"])}</th></tr>'
        "<tr>" + "<th>Act</th>" * N_PAST + "<th>Act</th><th>Period</th><th>ABP</th>"
        f'<th class="wrap">Likely<br>{escape(rep["likely_label"])}</th><th>Best<br>Month</th></tr>'
    )


def _body_html(rep, decimals):
    body = []
    for p in rep["plants"]:
        for k, r in enumerate(p["rows"]):
            cells = []
            if k == 0:
                cells.append(f'<td rowspan="{len(p["rows"])}" class="plant">{escape(p["plant"])}</td>')
            cells.append(f'<td class="mill">{escape(r["label"])}</td>')
            for v in _cells(r):
                cells.append(f"<td>{escape(v) if isinstance(v, str) else _fmt(v, decimals)}</td>")
            cls = " ".join(([r["kind"]]) + (["first"] if k == 0 else []) + (["five"] if p["plant"] == FIVE else []))
            body.append(f'<tr class="{cls}">{"".join(cells)}</tr>')
    return "".join(body)


def build_html(rep, colors, decimals=0):
    def c(k, dflt):  # defaults mirror colors_loader._DEFAULTS
        return colors.get(k, dflt)
    blk, txt = c("border_black", "#000000"), c("text_black", "#000000")
    note = "".join(f'<p class="note">{escape(n)}</p>' for n in notes(rep))
    size = {0: 8.5, 1: 8, 2: 7.5, 3: 7}[decimals]   # wider figures, smaller type, same one page
    blue, yellow = c("abp_mill_finished_bg", "#C5D9F1"), c("abp_mill_saleable_bg", "#FFFF00")
    css = f"""
  @page {{ size: A4 portrait; margin: 8mm 8mm 8mm 8mm; }}
  body {{ font-family: Arial, sans-serif; margin: 0; color: {txt};
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  h2 {{ font-family: 'Times New Roman', serif; font-size: 13pt; margin: 0; text-align: center; }}
  .unit {{ font-size: 7pt; text-align: right; }}
  .note {{ font-size: 7pt; margin: 2px 0 0; }}
  table {{ border-collapse: collapse; width: 100%; border: 1px solid {blk}; }}
  th, td {{ white-space: nowrap; padding: 0 2px; line-height: 1.15; border: 1px solid {blk}; text-align: center; }}
  th {{ font-size: 7.5pt; font-weight: 700; }}
  th.wrap {{ white-space: normal; }}
  td {{ font-size: {size}pt; font-weight: 700; }}
  td.plant {{ font-size: 9pt; white-space: normal; }}
  td.mill {{ text-align: left; }}
  tr.first td {{ border-top: 2.4px solid {blk}; }}
  tr.finished td:not(.plant), tr.pct td:not(.plant) {{ background: {blue}; }}
  tr.saleable td:not(.plant) {{ background: {yellow}; }}
  tr.five td {{ font-size: {size + 1}pt; }}
"""
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>'
            f'<section class="sheet"><h2>{escape(rep["title"])}</h2><div class="unit">Unit: \'000 T</div>'
            f'<table><thead>{_head_html(rep)}</thead><tbody>{_body_html(rep, decimals)}</tbody></table>{note}'
            '</section></body></html>')


_W_PX, _H_PX = 733, 1062   # A4 portrait minus 8 mm margins, at 96 dpi


def render_pdf(html):
    """Synchronous; call from a plain-def FastAPI handler (threadpool)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": _W_PX, "height": _H_PX})
        page.emulate_media(media="print")
        page.set_content(html, wait_until="load")
        page.evaluate(_FIT_JS, [_W_PX, _H_PX])
        pdf = page.pdf(format="A4", print_background=True,
                       margin={"top": "8mm", "right": "8mm", "bottom": "8mm", "left": "8mm"})
        browser.close()
    return pdf


# --------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------

def build_xlsx(rep, colors, decimals=0):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    def fill(k, dflt):
        return PatternFill("solid", fgColor=colors.get(k, dflt).lstrip("#").upper())
    fills = {"finished": fill("abp_mill_finished_bg", "#C5D9F1"), "pct": fill("abp_mill_finished_bg", "#C5D9F1"),
             "saleable": fill("abp_mill_saleable_bg", "#FFFF00")}
    thin = Side(style="thin")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    number_format = "0" if decimals == 0 else "0." + "0" * decimals
    n_cols = 12   # Plants, Mills, Capacity, 4 past, Best Act and Period, ABP, Likely, Best Month

    wb = Workbook()
    ws = wb.active
    ws.title = "Mills"
    ws.cell(1, 1, rep["title"]).font = Font(bold=True, size=13)
    ws.cell(2, 1, "Unit: '000 T").font = Font(size=8)
    top = 3

    def head(row, col, text, *, rows=1, cols=1):
        ws.merge_cells(start_row=row, start_column=col, end_row=row + rows - 1, end_column=col + cols - 1)
        ws.cell(row, col, text)
        for rr in range(row, row + rows):
            for cc in range(col, col + cols):
                cell = ws.cell(rr, cc)
                cell.border, cell.alignment, cell.font = box, center, Font(bold=True, size=9)

    head(top, 1, "Plants", rows=2)
    head(top, 2, "Mills", rows=2)
    head(top, 3, "Installed Capacity", rows=2)
    for k, lab in enumerate(rep["past_labels"]):
        head(top, 4 + k, lab)
        head(top + 1, 4 + k, "Act")
    head(top, 8, "Best Achieved", cols=2)
    head(top + 1, 8, "Act")
    head(top + 1, 9, "Period")
    head(top, 10, rep["short_fy"], cols=3)
    head(top + 1, 10, "ABP")
    head(top + 1, 11, f"Likely {rep['likely_label']}")
    head(top + 1, 12, "Best Month")
    ws.row_dimensions[top + 1].height = 62

    r = top + 2
    for p in rep["plants"]:
        start = r
        for row in p["rows"]:
            ws.cell(r, 2, row["label"])
            for k, v in enumerate(_cells(row)):
                cell = ws.cell(r, 3 + k, v)
                if not isinstance(v, str):
                    cell.number_format = number_format
            for cc in range(2, n_cols + 1):
                cell = ws.cell(r, cc)
                cell.border = box
                cell.font = Font(bold=True, size=9)
                cell.alignment = Alignment(horizontal="left" if cc == 2 else "center", vertical="center")
                if row["kind"] in fills:
                    cell.fill = fills[row["kind"]]
            r += 1
        ws.merge_cells(start_row=start, start_column=1, end_row=r - 1, end_column=1)
        it = ws.cell(start, 1, p["plant"])
        it.font = Font(bold=True, size=11)
        it.alignment = center
        for rr in range(start, r):
            ws.cell(rr, 1).border = box
    for n in notes(rep):
        ws.cell(r, 1, n).font = Font(size=8)
        r += 1

    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 23
    for cc in range(3, n_cols + 1):
        ws.column_dimensions[get_column_letter(cc)].width = 10
    ws.column_dimensions["K"].width = 15
    ws.freeze_panes = ws.cell(top + 2, 3)
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
