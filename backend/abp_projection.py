"""SAIL production projection for one financial year (/reports/abp tab
'production-projection'), after the "pre ABP HM-CS-SS performance likely"
sheet: Hot Metal, Crude Steel, Saleable Steel and Finished Steel, plant-wise
with SAIL-5 PL and SAIL totals (Finished Steel stops at SAIL-5 PL).

Columns: installed capacity (abp_projection_config.json; no DB source),
operating capacity (item_capacity at the FY's last month), the three previous
FYs' actuals with the highest flagged, the FY's APP and MoU, its best month
and average of 3 best months so far, actual to date, and two estimates of the
full year, each against APP and MoU:
  Projection = actual to date + running month's OP + remaining months' APP.
  Pro-rated  = actual to date x days in the FY / days elapsed.

The running month is the one after the FY's latest actual at the five plants.
A plant with no OP for it uses APP for that month and is listed in op_missing.
A completed FY projects its actual; an FY with no actuals projects its plan.

A cell with no DB row is blank, not 0. A total adds what is there, so its best
month is the sum of the plants' bests (as on the sheet), not a joint month."""

import calendar
import io
import json
import os
from html import escape

from app_actual_trend import available_fys, fy_label, fy_months  # noqa: F401  (available_fys: the API's FY list)
from constants import FIVE_PLANTS
from repo import production as rp
from repo.capacity import get_effective_capacity

# (section title, DB item, plants after SAIL-5 PL that join SAIL; None = no SAIL row)
ITEMS = [
    ("Hot Metal", "Hot Metal", ["VISL"]),
    ("Crude Steel", "Total Crude Steel", ["ASP", "SSP", "VISL"]),
    ("Saleable Steel", "Saleable Steel", ["ASP", "SSP", "VISL"]),
    ("Finished Steel", "Finished Steel", None),
]
FIVE_PL = "SAIL-5 PL"
N_PAST = 3
_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "abp_projection_config.json")


def _sum(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def _pct(val, plan):
    return None if val is None or not plan else val * 100.0 / plan


def _past_max(vals):
    """Per value, whether it is the row's highest (ties all flagged). A row
    with nothing above 0 flags none."""
    top = max((v for v in vals if v is not None), default=None)
    return [bool(top) and v == top for v in vals]


def _days(months):
    return sum(calendar.monthrange(int(m[:4]), int(m[5:]))[1] for m in months)


def _mon(m):
    return f"{calendar.month_abbr[int(m[5:])]}'{m[2:4]}"


def _span(months):
    return _mon(months[0]) if len(months) == 1 else f"{_mon(months[0])}-{_mon(months[-1])}"


def _short_fy(fy_start):
    return f"{fy_start % 100:02d}-{(fy_start + 1) % 100:02d}"


def _ytd_label(months):
    """Apr-Oct'26: the first month's year is left out, as on the sheet."""
    if not months:
        return ""
    if len(months) == 1:
        return _mon(months[0])
    return f"{calendar.month_abbr[int(months[0][5:])]}-{_mon(months[-1])}"


def _projection_label(act_months, running, rest, has_op):
    parts = [f"{_ytd_label(act_months)} act"] if act_months else []
    if running and has_op:
        parts.append(f"{_mon(running)} OP")
        if rest:
            parts.append(f"{_span(rest)} APP")
    elif running:
        parts.append(f"{_span([running] + rest)} APP")
    return " + ".join(parts)


def _load_config():
    with open(_CONFIG, encoding="utf-8") as f:
        return json.load(f)["installed_capacity"]


def _finish(row):
    """Fill in what is derived the same way for a plant and for a total."""
    row["past_max"] = _past_max(row["past"])
    row["proj_app"] = _pct(row["projection"], row["app"])
    row["proj_mou"] = _pct(row["projection"], row["mou"])
    row["pro_app"] = _pct(row["prorated"], row["app"])
    row["pro_mou"] = _pct(row["prorated"], row["mou"])
    return row


def _total(label, rows):
    out = {"plant": label, "total": True,
           "past": [_sum([r["past"][i] for r in rows]) for i in range(N_PAST)]}
    for k in ("installed", "operating", "app", "mou", "best", "avg3", "ytd", "projection", "prorated"):
        out[k] = _sum([r[k] for r in rows])
    return _finish(out)


def build(fy_start):
    months = fy_months(fy_start)
    past_fys = [fy_start - n for n in range(N_PAST, 0, -1)]
    past_months = {y: fy_months(y) for y in past_fys}
    all_months = [m for y in past_fys for m in past_months[y]] + months
    plants = FIVE_PLANTS + ["ASP", "SSP", "VISL"]
    db_items = [db for _, db, _ in ITEMS]

    def index(rows):
        return {(m, p.upper(), i.lower()): v for (m, p, i), v in rows.items()}

    act = index(rp.values(all_months, plants, db_items, "actual"))
    app = index(rp.values(months, plants, db_items, "abp"))
    mou = index(rp.values(months, plants, db_items, "mou"))

    # One cut-off for every row, so the column headers hold for the whole sheet.
    with_act = [m for m in months
                if any(act.get((m, p, i.lower())) is not None for p in FIVE_PLANTS for i in db_items)]
    act_months = months[:months.index(with_act[-1]) + 1] if with_act else []
    after = months[len(act_months):]
    running, rest = (after[0], after[1:]) if after else (None, [])

    op = {}
    if running:
        op = {(p.upper(), i.lower()): v for _, p, i, v in rp.op_plan_month_rows([running], plants)}
    op_missing = []

    fy_days, act_days = _days(months), _days(act_months)
    config = _load_config()

    def plant_row(title, db, plant):
        key = (plant.upper(), db.lower())
        got = [act.get((m, *key)) for m in act_months]
        got = [v for v in got if v is not None]
        ytd = _sum(got)
        top3 = sorted(got, reverse=True)[:3]
        running_val = None
        if running:
            running_val = op.get(key)
            if running_val is None:
                running_val = app.get((running, *key))
                if op and running_val:
                    op_missing.append(f"{title}: {plant}")
        installed = config.get(title, {}).get(plant)
        return _finish({
            "plant": plant, "total": False,
            "installed": None if installed is None else float(installed),
            "operating": get_effective_capacity(plant, db, months[-1]),
            "past": [_sum([act.get((m, *key)) for m in past_months[y]]) for y in past_fys],
            "app": _sum([app.get((m, *key)) for m in months]),
            "mou": _sum([mou.get((m, *key)) for m in months]),
            "best": top3[0] if top3 else None,
            "avg3": sum(top3) / len(top3) if top3 else None,
            "ytd": ytd,
            "projection": _sum([ytd, running_val] + [app.get((m, *key)) for m in rest]),
            "prorated": None if ytd is None else ytd * fy_days / act_days,
        })

    sections = []
    for title, db, extra in ITEMS:
        five = [plant_row(title, db, p) for p in FIVE_PLANTS]
        rows = five + [_total(FIVE_PL, five)]
        if extra is not None:
            others = [plant_row(title, db, p) for p in extra]
            rows += others + [_total("SAIL", five + others)]
        sections.append({"item": title, "rows": rows})

    label = fy_label(fy_start)
    return {
        "fy": fy_start, "fy_label": label, "short_fy": _short_fy(fy_start),
        "title": f"SAIL Production Projection for FY {label}",
        "past_labels": [_short_fy(y) for y in past_fys],
        "ytd_label": _ytd_label(act_months),
        "projection_label": _projection_label(act_months, running, rest, bool(op)),
        "sections": sections,
        "op_missing": op_missing,
        "has_plan": any(r["app"] is not None for s in sections for r in s["rows"]),
    }


def filename(rep, ext):
    return f"ABP_Production_Projection_{rep['fy_label']}.{ext}"


def notes(rep):
    """Lines printed under the table."""
    out = []
    if not rep["has_plan"]:
        out.append(f"No APP / MoU data in the database for FY {rep['fy_label']}.")
    if rep["op_missing"]:
        out.append("No OP for the running month, APP used: " + "; ".join(rep["op_missing"]) + ".")
    return out


# The figure columns after the past years, left to right; the last six are the
# pink Projection and Pro-rated block.
_AFTER_PAST = ["app", "mou", "best", "avg3", "ytd", "projection", "proj_app", "proj_mou",
               "prorated", "pro_app", "pro_mou"]


def _fmt(v, decimals):
    if v is None:
        return ""
    s = f"{v:.{decimals}f}"
    return s[1:] if s.startswith("-") and not s.strip("-0.") else s


# --------------------------------------------------------------------------
# PDF (HTML for Playwright)
# --------------------------------------------------------------------------

def _head_html(rep):
    fy = escape(rep["short_fy"])
    past = "".join(f"<th>{escape(x)}</th>" for x in rep["past_labels"])
    return (
        '<tr><th rowspan="3" class="vert"><div>Items</div></th><th rowspan="3">Plant</th>'
        '<th rowspan="3">Installed<br>Capacity</th>'
        f'<th rowspan="3">Operating<br>Capacity<br>{fy}</th>{past}'
        f'<th colspan="4" class="plan">{fy}</th><th rowspan="3">{escape(rep["ytd_label"])}</th>'
        f'<th colspan="6" class="proj">{fy}</th></tr>'
        + "<tr>" + '<th rowspan="2">Act</th>' * N_PAST
        + '<th rowspan="2" class="plan">APP</th><th rowspan="2">MoU</th><th rowspan="2">Best<br>Month</th>'
          '<th rowspan="2">Avg of<br>3 best<br>months</th>'
        + f'<th colspan="3" class="proj wrap">{escape(rep["projection_label"])}</th>'
          '<th colspan="3" class="proj">Pro-rated</th></tr>'
        + "<tr>" + '<th class="proj">Projection</th><th class="proj">%APP</th><th class="proj">%MoU</th>' * 2 + "</tr>"
    )


def _body_html(rep, decimals):
    body = []
    for sec in rep["sections"]:
        for k, r in enumerate(sec["rows"]):
            cells = []
            if k == 0:
                cells.append(f'<td rowspan="{len(sec["rows"])}" class="item"><div>{escape(sec["item"])}</div></td>')
            cells.append(f'<td class="plant">{escape(r["plant"])}</td>')
            cells += [f"<td>{_fmt(r[c], decimals)}</td>" for c in ("installed", "operating")]
            cells += [f'<td class="{"best" if b else ""}">{_fmt(v, decimals)}</td>'
                      for v, b in zip(r["past"], r["past_max"])]
            for c in _AFTER_PAST:
                cls = "plan" if c == "app" else "proj" if c in _AFTER_PAST[5:] else ""
                cells.append(f'<td class="{cls}">{_fmt(r[c], decimals)}</td>')
            cls = " ".join((["tot"] if r["total"] else []) + (["first"] if k == 0 else []))
            body.append(f'<tr class="{cls}">{"".join(cells)}</tr>')
    return "".join(body)


def build_html(rep, colors, decimals=0):
    def c(k, dflt):  # defaults mirror colors_loader._DEFAULTS
        return colors.get(k, dflt)
    blk, txt = c("border_black", "#000000"), c("text_black", "#000000")
    note = "".join(f'<p class="note">{escape(n)}</p>' for n in notes(rep))
    size = {0: 8.5, 1: 8, 2: 7.5, 3: 7}[decimals]   # wider figures, smaller type, same one page
    css = f"""
  @page {{ size: A4 landscape; margin: 8mm 8mm 8mm 8mm; }}
  body {{ font-family: Arial, sans-serif; margin: 0; color: {txt};
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  h2 {{ font-family: 'Times New Roman', serif; font-size: 13pt; margin: 0; text-align: center; }}
  .unit {{ font-size: 7pt; text-align: right; }}
  .note {{ font-size: 7pt; margin: 2px 0 0; }}
  table {{ border-collapse: collapse; width: 100%; border: 1px solid {blk}; }}
  th, td {{ white-space: nowrap; padding: 0 3px; line-height: 1.15; border: 1px solid {blk}; text-align: center; }}
  th {{ font-size: 7.5pt; font-weight: 700; }}
  th.wrap {{ white-space: normal; }}
  td {{ font-size: {size}pt; }}
  th.vert div {{ writing-mode: vertical-rl; transform: rotate(180deg); margin: 0 auto; }}
  td.item {{ vertical-align: middle; padding: 0; }}
  td.item div {{ writing-mode: vertical-rl; transform: rotate(180deg); font-size: 10pt; font-weight: 700; margin: 0 auto; }}
  td.plant {{ text-align: left; }}
  tr.tot td {{ font-weight: 700; }}
  tr.first td {{ border-top: 2.4px solid {blk}; }}
  .plan {{ background: {c("abp_plan_bg", "#DCE6F1")}; }}
  .proj {{ background: {c("abp_projection_bg", "#F2DCDB")}; }}
  td.best {{ background: {c("abp_best_fy_bg", "#92D050")}; }}
"""
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>'
            f'<section class="sheet"><h2>{escape(rep["title"])}</h2><div class="unit">Unit: \'000 T</div>'
            f'<table><thead>{_head_html(rep)}</thead><tbody>{_body_html(rep, decimals)}</tbody></table>{note}'
            '</section></body></html>')


# Zoom the sheet down if it overflows the page, else grow its rows to fill it.
_FIT_JS = """([W, H]) => {
    const sheet = document.querySelector('.sheet');
    const table = sheet.querySelector('table');
    const box = sheet.getBoundingClientRect();
    const scale = Math.min(W / Math.max(table.scrollWidth, box.width), H / box.height);
    if (scale < 1) { sheet.style.zoom = scale; return; }
    const rows = Array.from(sheet.querySelectorAll('tbody tr'));
    const extra = (H - box.height) * 0.97 / rows.length;
    const hs = rows.map(r => r.getBoundingClientRect().height);
    rows.forEach((r, i) => r.style.height = (hs[i] + extra) + 'px');
}"""
_W_PX, _H_PX = 1062, 733   # A4 landscape minus 8 mm margins, at 96 dpi


def render_pdf(html):
    """Synchronous; call from a plain-def FastAPI handler (threadpool)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": _W_PX, "height": _H_PX})
        page.emulate_media(media="print")
        page.set_content(html, wait_until="load")
        page.evaluate(_FIT_JS, [_W_PX, _H_PX])
        pdf = page.pdf(format="A4", landscape=True, print_background=True,
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
    plan_fill = fill("abp_plan_bg", "#DCE6F1")
    proj_fill = fill("abp_projection_bg", "#F2DCDB")
    best_fill = fill("abp_best_fy_bg", "#92D050")
    thin = Side(style="thin")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    number_format = "0" if decimals == 0 else "0." + "0" * decimals
    n_cols = 4 + N_PAST + len(_AFTER_PAST)
    plan_col, ytd_col, proj_col = 5 + N_PAST, 9 + N_PAST, 10 + N_PAST

    wb = Workbook()
    ws = wb.active
    ws.title = "Projection"
    ws.cell(1, 1, rep["title"]).font = Font(bold=True, size=13)
    ws.cell(2, 1, "Unit: '000 T").font = Font(size=8)
    top = 3

    def head(row, col, text, *, rows=1, cols=1, bg=None):
        ws.merge_cells(start_row=row, start_column=col, end_row=row + rows - 1, end_column=col + cols - 1)
        ws.cell(row, col, text)
        for rr in range(row, row + rows):
            for cc in range(col, col + cols):
                cell = ws.cell(rr, cc)
                cell.border, cell.alignment, cell.font = box, center, Font(bold=True, size=9)
                if bg:
                    cell.fill = bg

    head(top, 1, "Items", rows=3)
    ws.cell(top, 1).alignment = Alignment(text_rotation=90, horizontal="center", vertical="center")
    head(top, 2, "Plant", rows=3)
    head(top, 3, "Installed Capacity", rows=3)
    head(top, 4, f"Operating Capacity {rep['short_fy']}", rows=3)
    for k, lab in enumerate(rep["past_labels"]):
        head(top, 5 + k, lab)
        head(top + 1, 5 + k, "Act", rows=2)
    head(top, plan_col, rep["short_fy"], cols=4, bg=plan_fill)
    for k, (lab, bg) in enumerate((("APP", plan_fill), ("MoU", None), ("Best Month", None), ("Avg of 3 best months", None))):
        head(top + 1, plan_col + k, lab, rows=2, bg=bg)
    head(top, ytd_col, rep["ytd_label"], rows=3)
    head(top, proj_col, rep["short_fy"], cols=6, bg=proj_fill)
    head(top + 1, proj_col, rep["projection_label"], cols=3, bg=proj_fill)
    head(top + 1, proj_col + 3, "Pro-rated", cols=3, bg=proj_fill)
    for k, lab in enumerate(("Projection", "%APP", "%MoU") * 2):
        head(top + 2, proj_col + k, lab, bg=proj_fill)
    ws.row_dimensions[top + 1].height = 40

    r = top + 3
    for sec in rep["sections"]:
        start = r
        for row in sec["rows"]:
            ws.cell(r, 2, row["plant"])
            values = [row["installed"], row["operating"]] + row["past"] + [row[c] for c in _AFTER_PAST]
            for k, v in enumerate(values):
                ws.cell(r, 3 + k, v).number_format = number_format
            for cc in range(2, n_cols + 1):
                cell = ws.cell(r, cc)
                cell.border = box
                cell.font = Font(bold=row["total"], size=9)
                cell.alignment = Alignment(horizontal="left" if cc == 2 else "center", vertical="center")
            for k, is_max in enumerate(row["past_max"]):
                if is_max:
                    ws.cell(r, 5 + k).fill = best_fill
            ws.cell(r, plan_col).fill = plan_fill
            for cc in range(proj_col, n_cols + 1):
                ws.cell(r, cc).fill = proj_fill
            r += 1
        ws.merge_cells(start_row=start, start_column=1, end_row=r - 1, end_column=1)
        it = ws.cell(start, 1, sec["item"])
        it.font = Font(bold=True, size=11)
        it.alignment = Alignment(text_rotation=90, horizontal="center", vertical="center")
        for rr in range(start, r):
            ws.cell(rr, 1).border = box
    for n in notes(rep):
        ws.cell(r, 1, n).font = Font(size=8)
        r += 1

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 11
    for cc in range(3, n_cols + 1):
        ws.column_dimensions[get_column_letter(cc)].width = 10
    ws.freeze_panes = ws.cell(top + 3, 3)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
