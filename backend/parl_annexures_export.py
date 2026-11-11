"""Excel and PDF of the Parliament annexures (parl_annexures.py), laid out
like the sheets of Report_format/work/HisParlia_Annexures.xlsx:

  production_performance  "hisparlia"         A4 portrait, one page
  production_history      "ProdHIS"           A4 portrait, one page
  techno_history          "techhistoryfinal"  A4 portrait, one page

All in Calibri. Each workbook also gets a "Data check" sheet listing the deviations (the
JSON / workbook figure against the DB). The PDF is its own small template,
not part of the layout-guarded monthly report. Colours: colors_config.json
(parl_* keys).
"""
from html import escape

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from colors_loader import load_colors_config
from page_techno import _round_half_up

SHEET_NAMES = {
    "production_performance": "hisparlia",
    "production_history": "ProdHIS",
    "techno_history": "techhistoryfinal",
}
REPORT_TITLES = {
    "production_performance": "Annexure-II Production Performance",
    "production_history": "Production History",
    "techno_history": "Annexure-III Techno-Economic History",
}
PP_FIELDS = ["cap", "app", "mou", "actual", "ful_app", "ful_mou", "gr", "cu"]


# ── display rules (shared by Excel and PDF) ──────────────────────────────────

def fmt(v, dp=0):
    """Rounded half up like the techno pages (page_techno._round_half_up):
    6.095 -> 6.10, as Excel shows it."""
    if v is None:
        return ""
    s = f"{_round_half_up(float(v), dp):f}"
    return s[1:] if s.startswith("-") and not s.strip("-0.") else s


def pp_cells(kind, vals):
    """The 8 values of one item block in a row of the production
    performance sheet: numbers, None (blank) or '-'. A block with no data
    at all stays blank (ASP's Hot Metal); otherwise a missing MoU, and the
    %Ful. against it, show '-'. The annual plan row has Cap., APP, MoU only."""
    out = [vals.get(f) for f in PP_FIELDS]
    if all(v is None for v in out):
        return out
    if vals.get("mou") is None:
        out[2] = "-"
        if kind != "plan":
            out[5] = "-"
    return out


def _hex(c):
    return c.lstrip("#").upper()


# ── Excel ────────────────────────────────────────────────────────────────────

FONT = "Calibri"   # every downloaded sheet / PDF page

_THIN = Side(style="thin", color="000000")
_MED = Side(style="medium", color="000000")
_BOX = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_C = Alignment(horizontal="center", vertical="center", wrap_text=True)
_L = Alignment(horizontal="left", vertical="center")
_R = Alignment(horizontal="right", vertical="center")


def _fill(c):
    return PatternFill("solid", fgColor=_hex(c))


def _put(ws, r, c, v, font=None, fill=None, align=_C, border=_BOX, fmt_=None):
    cell = ws.cell(r, c, v)
    if font:
        cell.font = font
    if fill:
        cell.fill = fill
    if align:
        cell.alignment = align
    if border:
        cell.border = border
    if fmt_ and isinstance(v, (int, float)):
        cell.number_format = fmt_
    return cell


def _merge(ws, r1, c1, r2, c2):
    if (r1, c1) != (r2, c2):
        ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)


def _page(ws, landscape, title_rows=None):
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0 if title_rows else 1
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.page_margins.top = ws.page_margins.bottom = 0.5
    if title_rows:
        ws.print_title_rows = title_rows


def _xl_pp(ws, d, colors):
    L = d["labels"]
    f = FONT
    item_fill, cap_fill, act_fill = (_fill(colors["parl_item_bg"]), _fill(colors["parl_cap_bg"]),
                                     _fill(colors["parl_actual_bg"]))
    last = 3 + 8 * len(d["items"])
    _put(ws, 2, 2, L["title"], Font(name=f, size=18, bold=True), border=None)
    _merge(ws, 2, 2, 2, last - 3)
    _put(ws, 2, last, L["annexure"], Font(name=f, size=14, bold=True), align=_R, border=None)
    _put(ws, 3, 2, L["subtitle"], Font(name=f, size=18, bold=True), border=None)
    _merge(ws, 3, 2, 3, last - 3)
    _put(ws, 4, last, L["unit"], Font(name=f, size=12), align=_R, border=None)

    hf, hn = Font(name=f, size=16, bold=True), Font(name=FONT, size=14, bold=True)
    _put(ws, 5, 2, "PLANT", hf)
    _merge(ws, 5, 2, 7, 2)
    _put(ws, 5, 3, "YEAR", hf)
    _merge(ws, 5, 3, 7, 3)
    for n, it in enumerate(d["items"]):
        c0 = 4 + 8 * n
        _put(ws, 5, c0, it["label"], hf, item_fill)
        _merge(ws, 5, c0, 5, c0 + 7)
        for c, t, span in ((c0, "CAP.*", 1), (c0 + 1, "TARGET", 2), (c0 + 3, "ACTUAL", 1),
                           (c0 + 4, "% FUL.", 2), (c0 + 6, "% GR.", 1), (c0 + 7, "% C.U", 1)):
            _put(ws, 6, c, t, hn, cap_fill if c == c0 else (act_fill if c == c0 + 3 else None))
            if span == 2:
                _merge(ws, 6, c, 6, c + 1)
                _put(ws, 7, c, "APP", Font(name=FONT, size=14))
                _put(ws, 7, c + 1, "MoU", Font(name=FONT, size=14))
            else:
                _put(ws, 7, c, None, fill=cap_fill if c == c0 else (act_fill if c == c0 + 3 else None))
                _merge(ws, 6, c, 7, c)
        for c in range(c0, c0 + 8):
            ws.cell(5, c).border = _BOX

    r = 8
    for blk in d["plants"]:
        sail = blk["plant"] == "SAIL"
        font = Font(name=f, size=16 if sail else 14, bold=True)
        nf = Font(name=f, size=16 if sail else 14, bold=sail)
        first = r
        for row in blk["rows"]:
            _put(ws, r, 3, row["label"], font)
            for n, it in enumerate(d["items"]):
                c0 = 4 + 8 * n
                for i, v in enumerate(pp_cells(row["kind"], row["values"][it["key"]])):
                    fill = cap_fill if i == 0 else (act_fill if i == 3 else None)
                    _put(ws, r, c0 + i, v, nf, fill, fmt_="0")
                ws.cell(r, c0).border = Border(left=_MED, right=_THIN, top=_THIN, bottom=_THIN)
            ws.row_dimensions[r].height = 24
            r += 1
        _put(ws, first, 2, blk["plant"], Font(name=f, size=16 if sail else 14, bold=True))
        # no rule between the years of a plant: a medium rule over each
        # plant block, a thin one under the last
        closing = blk is d["plants"][-1]
        for rr in range(first, r):
            for c in range(2, last + 1):
                cell = ws.cell(rr, c)
                cell.border = Border(left=cell.border.left, right=cell.border.right,
                                     top=_MED if rr == first else None,
                                     bottom=_THIN if closing and rr == r - 1 else None)
        _merge(ws, first, 2, r - 1, 2)
    widths = {1: 3, 2: 10, 3: 34}
    for n in range(len(d["items"])):
        for i, w in enumerate([12, 10, 10, 13, 8, 8, 8, 8]):
            widths[4 + 8 * n + i] = w
    for c, w in widths.items():
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "D8"
    _page(ws, False, "5:7")
    ws.print_area = f"B2:{get_column_letter(last)}{r - 1}"


def _xl_ph(ws, d, colors):
    L = d["labels"]
    fys = d["fys"]
    bk, nar = FONT, FONT
    ncy = 3 + len(fys)          # period CY column
    last = ncy + 2              # % growth
    _put(ws, 4, 2, L["company"], Font(name=FONT, size=16, bold=True), align=_L, border=None)
    _put(ws, 6, 2, L["title"], Font(name=bk, size=16, bold=True), align=_L, border=None)
    _put(ws, 6, last, L["unit"], Font(name=bk, size=11), align=_R, border=None)
    hb = Font(name=bk, size=12, bold=True)
    _put(ws, 7, 2, "PLANT/ITEMS", hb, align=_L)
    _merge(ws, 7, 2, 9, 2)
    for i, fy in enumerate(fys):
        c = 3 + i
        _put(ws, 7, c, fy, hb)
        _merge(ws, 7, c, 8, c)
        _put(ws, 9, c, "ACTUAL", Font(name=FONT, size=11))
    _put(ws, 7, ncy, L["span"], hb)
    _merge(ws, 7, ncy, 8, ncy + 1)
    _put(ws, 9, ncy, L["fy"], Font(name=FONT, size=11))
    _put(ws, 9, ncy + 1, L["cply_fy"], Font(name=FONT, size=11))
    _put(ws, 7, last, "% growth", hb)
    _put(ws, 8, last, "over", hb)
    _put(ws, 9, last, "CPLY", Font(name=FONT, size=11))
    for rr in (7, 8, 9):
        for c in range(2, last + 1):
            ws.cell(rr, c).border = _BOX
    r = 10
    for it in d["items"]:
        _put(ws, r, 2, it["label"], hb, align=_L)
        for c in range(3, last + 1):
            _put(ws, r, c, None)
        r += 1
        for row in it["rows"]:
            bold = row["total"]
            lf = Font(name=bk, size=12, bold=bold)
            nf = Font(name=nar, size=12, bold=bold)
            label = "SAIL-5 PL" if row["plant"] == "SAIL-5PL" else row["plant"]
            _put(ws, r, 2, label, lf, align=_L)
            for i, v in enumerate(row["fys"] + [row["cy"], row["cply"], row["gr"]]):
                _put(ws, r, 3 + i, v, nf, fmt_="0")
            r += 1
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 22
    for c in range(3, last + 1):
        ws.column_dimensions[get_column_letter(c)].width = 11
    ws.column_dimensions[get_column_letter(last)].width = 13
    _page(ws, False)
    ws.print_area = f"B6:{get_column_letter(last)}{r - 1}"


def _xl_th(ws, d, colors):
    L = d["labels"]
    fys = d["fys"]
    nar = FONT
    ncy = 3 + len(fys)
    last = ncy + 2
    _put(ws, 4, last, L["annexure"], Font(name=nar, size=16, bold=True), align=_R, border=None)
    _put(ws, 7, 2, L["title"], Font(name=FONT, size=18, bold=True), align=_L, border=None)
    b14 = Font(name=nar, size=14, bold=True)
    r = 9
    for sec in d["sections"]:
        dp = sec["decimals"]
        nf = "0" if dp == 0 else "0." + "0" * dp
        _put(ws, r, 2, sec["label"], b14, align=_L, border=None)
        _put(ws, r + 1, 2, sec["unit"], b14, align=_L, border=None)
        h1, h2 = r + 2, r + 3
        _put(ws, h1, 2, None, b14)
        _put(ws, h2, 2, None, b14)
        _merge(ws, h1, 2, h2, 2)
        for i, fy in enumerate(fys):
            _put(ws, h1, 3 + i, fy, b14)
            _merge(ws, h1, 3 + i, h2, 3 + i)
        _put(ws, h1, ncy, L["span"], b14)
        _merge(ws, h1, ncy, h1, ncy + 1)
        _put(ws, h2, ncy, L["fy"], b14)
        _put(ws, h2, ncy + 1, L["cply_fy"], b14)
        _put(ws, h1, last, "% imp. Over", b14)
        _put(ws, h2, last, "CPLY", b14)
        for rr in (h1, h2):
            for c in range(2, last + 1):
                ws.cell(rr, c).border = _BOX
        r = h2 + 1
        for row in sec["rows"]:
            bold = row["total"]
            _put(ws, r, 2, row["plant"], b14, align=_L)
            for i, v in enumerate(row["fys"] + [row["cy"], row["cply"]]):
                _put(ws, r, 3 + i, "-" if v is None and i < len(fys) else v,
                     Font(name=nar, size=14, bold=bold), fmt_=nf)
            _put(ws, r, last, row["imp"], Font(name=nar, size=14, bold=bold), fmt_="0")
            r += 1
        r += 2
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 16
    for c in range(3, last + 1):
        ws.column_dimensions[get_column_letter(c)].width = 11
    ws.column_dimensions[get_column_letter(last)].width = 14
    _page(ws, False)
    ws.print_area = f"B4:{get_column_letter(last)}{r - 2}"


def _xl_devs(ws, items):
    """items: [(report, data), ...] -> one table of every deviation."""
    hdr = ["Report", "Plant", "Item", "Period", "Measure", "Workbook / JSON", "DB", "DB - Workbook"]
    bold = Font(bold=True)
    ws.cell(1, 1, "Data check: figures in parl_annexures_history.json (the workbook) that differ "
                  "from the DB for the same unit and period").font = Font(bold=True, size=12)
    for c, h in enumerate(hdr, start=1):
        _put(ws, 3, c, h, bold, PatternFill("solid", fgColor="DBEAFE"))
    r = 4
    for report, d in items:
        for x in d.get("deviations", []):
            vals = [REPORT_TITLES[report], x["plant"], x["item"], x["period"], x["measure"],
                    x["workbook"], x["db"], x["diff"]]
            for c, v in enumerate(vals, start=1):
                _put(ws, r, c, v, align=_L if c <= 5 else _R, fmt_="0.000")
            r += 1
    if r == 4:
        ws.cell(4, 1, "No deviations: the DB agrees with the workbook for every period shown.")
    for c, w in enumerate([34, 10, 20, 22, 10, 16, 14, 14], start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A4"


_XL = {"production_performance": _xl_pp, "production_history": _xl_ph, "techno_history": _xl_th}


def build_xlsx(items) -> bytes:
    """items: [(report, data), ...] -> workbook bytes, one sheet each plus
    the data-check sheet."""
    import io
    colors = load_colors_config()
    wb = Workbook()
    wb.remove(wb.active)
    for report, d in items:
        _XL[report](wb.create_sheet(SHEET_NAMES[report]), d, colors)
    _xl_devs(wb.create_sheet("Data check"), items)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── PDF ──────────────────────────────────────────────────────────────────────

def _td(v, dp=0, cls=""):
    s = v if isinstance(v, str) else fmt(v, dp)
    return f'<td class="{cls}">{escape(s)}</td>' if cls else f"<td>{escape(s)}</td>"


def _html_pp(d):
    L = d["labels"]
    items = d["items"]
    head1 = '<tr><th rowspan="3" class="plant">PLANT</th><th rowspan="3" class="year">YEAR</th>' + "".join(
        f'<th colspan="8" class="item wall">{escape(it["label"])}</th>' for it in items) + "</tr>"
    head2 = "<tr>" + "".join(
        '<th rowspan="2" class="cap wall">CAP.*</th><th colspan="2">TARGET</th>'
        '<th rowspan="2" class="act">ACTUAL</th><th colspan="2">% FUL.</th>'
        '<th rowspan="2">% GR.</th><th rowspan="2">% C.U</th>' for _ in items) + "</tr>"
    head3 = "<tr>" + "<th>APP</th><th>MoU</th><th>APP</th><th>MoU</th>" * len(items) + "</tr>"
    bodies = []
    for blk in d["plants"]:
        rows = []
        for k, row in enumerate(blk["rows"]):
            cells = []
            if k == 0:
                cells.append(f'<td rowspan="{len(blk["rows"])}" class="plant">{escape(blk["plant"])}</td>')
            cells.append(f'<td class="year">{escape(row["label"])}</td>')
            for it in items:
                for i, v in enumerate(pp_cells(row["kind"], row["values"][it["key"]])):
                    cells.append(_td(v, 0, "cap wall" if i == 0 else ("act" if i == 3 else "")))
            rows.append(f'<tr class="{row["kind"]}">{"".join(cells)}</tr>')
        cls = "blk sail" if blk["plant"] == "SAIL" else "blk"
        bodies.append(f'<tbody class="{cls}">{"".join(rows)}</tbody>')
    return (
        '<section class="sheet pp">'
        f'<div class="hd"><div class="ttl"><h1>{escape(L["title"])}</h1><h2>{escape(L["subtitle"])}</h2></div>'
        f'<div class="ann">{escape(L["annexure"])}<br><span>{escape(L["unit"])}</span></div></div>'
        f'<table><colgroup><col class="c-plant"><col class="c-year">{"<col>" * (8 * len(items))}</colgroup>'
        f'<thead>{head1}{head2}{head3}</thead>{"".join(bodies)}</table></section>'
    )


def _html_ph(d):
    L = d["labels"]
    fys = d["fys"]
    head = ('<tr><th rowspan="3" class="lbl">PLANT/ITEMS</th>'
            + "".join(f'<th rowspan="2">{f}</th>' for f in fys)
            + f'<th colspan="2" rowspan="2">{escape(L["span"])}</th><th>% growth</th></tr>'
            + '<tr><th class="nb">over</th></tr><tr>'
            + "<th class=\"sub\">ACTUAL</th>" * len(fys)
            + f'<th class="sub">{L["fy"]}</th><th class="sub">{L["cply_fy"]}</th><th class="sub">CPLY</th></tr>')
    body = []
    for it in d["items"]:
        body.append(f'<tr class="sec"><td class="lbl">{escape(it["label"])}</td>'
                    + "<td></td>" * (len(fys) + 3) + "</tr>")
        for row in it["rows"]:
            label = "SAIL-5 PL" if row["plant"] == "SAIL-5PL" else row["plant"]
            cells = "".join(_td(v) for v in row["fys"] + [row["cy"], row["cply"], row["gr"]])
            body.append(f'<tr class="{"tot" if row["total"] else ""}"><td class="lbl">{escape(label)}</td>{cells}</tr>')
    return (
        '<section class="sheet ph">'
        f'<div class="co">{escape(L["company"])}</div>'
        f'<div class="hd"><h1>{escape(L["title"])}</h1><span>{escape(L["unit"])}</span></div>'
        f'<table><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></section>'
    )


def _html_th(d):
    L = d["labels"]
    fys = d["fys"]
    parts = []
    for sec in d["sections"]:
        dp = sec["decimals"]
        head = ('<tr><th rowspan="2" class="lbl"></th>' + "".join(f'<th rowspan="2">{f}</th>' for f in fys)
                + f'<th colspan="2">{escape(L["span"])}</th><th>% imp. Over</th></tr>'
                + f'<tr><th>{L["fy"]}</th><th>{L["cply_fy"]}</th><th>CPLY</th></tr>')
        body = []
        for row in sec["rows"]:
            vals = ["-" if v is None else v for v in row["fys"]] + [row["cy"], row["cply"]]
            cells = "".join(_td(v, dp) for v in vals) + _td(row["imp"], 0)
            body.append(f'<tr class="{"tot" if row["total"] else ""}"><td class="lbl">{escape(row["plant"])}</td>{cells}</tr>')
        parts.append(f'<h3>{escape(sec["label"])}</h3><div class="unit">{escape(sec["unit"])}</div>'
                     f'<table><thead>{head}</thead><tbody>{"".join(body)}</tbody></table>')
    return (
        '<section class="sheet th">'
        f'<div class="ann">{escape(L["annexure"])}</div><h1>{escape(L["title"])}</h1>{"".join(parts)}</section>'
    )


_HTML = {"production_performance": _html_pp, "production_history": _html_ph, "techno_history": _html_th}


def _fonts():
    try:
        from pdf import _local_font_face_css
        return _local_font_face_css("IBM Plex Sans")
    except Exception:
        return ""


def build_html(report, d) -> str:
    c = load_colors_config()
    blk = c.get("border_black", "#000000")
    txt = c.get("text_black", "#000000")
    css = f"""
  {_fonts()}
  @page {{ size: A4 portrait; margin: 8mm 8mm 8mm 8mm; }}
  body {{ font-family: Calibri, Carlito, sans-serif; margin: 0; color: {txt};
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid {blk}; text-align: center; padding: 1px 3px; line-height: 1.15; white-space: nowrap; }}
  h1 {{ margin: 0; text-align: center; }}
  /* hisparlia */
  .pp .hd {{ display: flex; align-items: flex-start; }}
  .pp .ttl {{ flex: 1; text-align: center; }}
  .pp h1 {{ font-size: 13pt; }} .pp h2 {{ font-size: 12pt; margin: 2px 0 4px; }}
  .pp .ann {{ font-size: 11pt; font-weight: 700; text-align: right; }}
  .pp .ann span {{ font-size: 8.5pt; font-weight: 400; }}
  .pp th {{ font-family: Calibri, Carlito, sans-serif; font-size: 8.5pt; font-weight: 700; }}
  .pp th.item {{ font-family: Calibri, Carlito, sans-serif; font-size: 9.5pt; background: {c["parl_item_bg"]}; }}
  .pp td {{ font-size: 8.5pt; font-weight: 400; }}
  .pp td.plant {{ font-weight: 700; font-size: 10pt; vertical-align: middle; }}
  .pp td.year {{ font-weight: 700; text-align: center; white-space: normal; line-height: 1.05; }}
  /* portrait: the 26 columns fit the page width as laid out (no zoom);
     _FIT_JS shrinks the font until no figure is clipped */
  .pp table {{ table-layout: fixed; }}
  .pp col.c-plant {{ width: 26px; }} .pp col.c-year {{ width: 54px; }}
  .pp th, .pp td {{ padding: 1px 0; overflow: hidden; }}
  .pp th {{ white-space: normal; line-height: 1.0; }}
  .pp .cap {{ background: {c["parl_cap_bg"]}; }}
  .pp .act {{ background: {c["parl_actual_bg"]}; }}
  .pp .wall {{ border-left: 1.6px solid {blk}; }}
  .pp tbody.blk {{ border-top: 1.6px solid {blk}; break-inside: avoid; }}
  /* no rule between the years of a plant, only between plant blocks
     (and under the last one) */
  .pp tbody td {{ border-top: none; border-bottom: none; }}
  .pp tbody tr:first-child td {{ border-top: 1.6px solid {blk}; }}
  .pp tbody:last-child tr:last-child td, .pp tbody td.plant {{ border-bottom: 1px solid {blk}; }}
  .pp tbody.sail td {{ font-weight: 700; }}
  .pp thead {{ display: table-header-group; }}
  /* ProdHIS */
  .ph .co {{ font-size: 13pt; font-weight: 700; margin: 4px 0 8px; }}
  .ph .hd {{ display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 3px; }}
  .ph h1 {{ font-family: Calibri, Carlito, sans-serif; font-size: 13pt; text-align: left; }}
  .ph .hd span {{ font-size: 9pt; }}
  .ph th {{ font-family: Calibri, Carlito, sans-serif; font-size: 10.5pt; font-weight: 700; }}
  .ph th.sub {{ font-family: Calibri, Carlito, sans-serif; font-weight: 400; font-size: 9.5pt; }}
  .ph th.nb {{ border-top: none; }}
  .ph td {{ font-family: Calibri, Carlito, sans-serif; font-size: 11.5pt; border-top: none; border-bottom: none; }}
  .ph td.lbl, .ph th.lbl {{ text-align: left; font-family: Calibri, Carlito, sans-serif; }}
  .ph tr.sec td {{ font-weight: 700; border-top: 1px solid {blk}; }}
  .ph tr.tot td {{ font-weight: 700; border-top: 1px solid {blk}; border-bottom: 1px solid {blk}; }}
  .ph tbody tr:last-child td {{ border-bottom: 1px solid {blk}; }}
  /* techhistoryfinal */
  .th .ann {{ text-align: right; font-family: Calibri, Carlito, sans-serif; font-size: 12pt; font-weight: 700; }}
  .th h1 {{ font-size: 14pt; text-align: left; margin: 6px 0 10px; }}
  .th h3 {{ font-family: Calibri, Carlito, sans-serif; font-size: 11pt; margin: 14px 0 0; }}
  .th .unit {{ font-family: Calibri, Carlito, sans-serif; font-size: 10.5pt; font-weight: 700; margin-bottom: 3px; }}
  .th th, .th td {{ font-family: Calibri, Carlito, sans-serif; font-size: 12pt; padding: 2px 4px; }}
  .th th {{ font-weight: 700; }}
  .th td.lbl {{ text-align: left; font-weight: 700; }}
  .th tr.tot td {{ font-weight: 700; }}
"""
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head>'
            f'<body>{_HTML[report](d)}</body></html>')


# Every sheet is A4 portrait on one page: zoom down to the page width (the
# 26-column Annexure-II) and height, then let the rows grow to fill it.
_FIT_JS = """([W, H, onePage]) => {
    const s = document.querySelector('.sheet');
    const fits = c => c.scrollWidth <= c.clientWidth + 0.5;
    const cells = Array.from(s.querySelectorAll('.pp td, .pp th'));
    if (cells.length) {
        const fs = parseFloat(getComputedStyle(s.querySelector('.pp td')).fontSize);
        for (let k = 1; k <= 30 && !cells.every(fits); k++)
            cells.forEach(c => c.style.fontSize = (fs * (1 - 0.025 * k)) + 'px');
    }
    const w = Math.max(...Array.from(s.querySelectorAll('table')).map(x => x.getBoundingClientRect().width));
    const h0 = s.getBoundingClientRect().height;
    let z = w > W ? W / w : 1;
    if (onePage && h0 * z > H * 0.97) z = H * 0.97 / h0;   // same 3% margin as below
    if (z < 1) s.style.zoom = z;
    // Chromium may report sizes inside a zoomed element zoomed or not
    const hz = s.getBoundingClientRect().height;
    const scale = Math.abs(hz - h0 * z) < Math.abs(hz - h0) ? 1 : z;
    const height = () => s.getBoundingClientRect().height * scale;
    if (onePage) {
        // grow the rows into the free height, backing off until the sheet
        // keeps a 3% margin (print layout runs a little taller than this
        // measure; a plant block that no longer fits would move to page 2)
        const rows = Array.from(s.querySelectorAll('tbody tr'));
        const base = rows.map(r => r.offsetHeight);
        const free = H - height();
        for (let f = 0.9; f > 0 && free > 0; f -= 0.1) {
            const extra = free * f / rows.length / z;
            rows.forEach((r, i) => r.style.height = (base[i] + extra) + 'px');
            if (height() <= H * 0.97) break;
            rows.forEach(r => r.style.height = '');
        }
    }
}"""

# A4 at 96 dpi minus 8 mm margins
_SIZE = (733, 1062)


def render_pdf(pages) -> bytes:
    """pages: [(report, data), ...] -> one PDF (each report on its own page(s)).
    Synchronous: call from a threadpool."""
    import io
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter

    out = PdfWriter()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for report, d in pages:
                W, H = _SIZE
                page = browser.new_page(viewport={"width": W, "height": H})
                page.emulate_media(media="print")
                page.set_content(build_html(report, d), wait_until="load")
                page.evaluate("document.fonts.ready.then(() => true)")
                page.evaluate(_FIT_JS, [W, H, True])
                pdf = page.pdf(format="A4", landscape=False, print_background=True,
                               margin={"top": "8mm", "right": "8mm", "bottom": "8mm", "left": "8mm"})
                page.close()
                for p in PdfReader(io.BytesIO(pdf)).pages:
                    out.add_page(p)
        finally:
            browser.close()
    buf = io.BytesIO()
    out.write(buf)
    return buf.getvalue()
