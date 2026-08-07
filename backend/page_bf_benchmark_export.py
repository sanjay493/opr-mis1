"""
Excel / PDF export for the Large BF Benchmarking comparison page
(frontend: /reports/bf-benchmark). Takes the same dict api_bf_benchmark.
build_compare() returns — {months, params, rows} — so the export always
matches what's on screen exactly.

Visual style mirrors page_techno_custom_export.py's Custom Period mode
(section-per-parameter, one row per BF, one column per month + an FY Avg
column) for consistency with the rest of the app; render_pdf_bytes is
imported from page_production_query_export.py directly rather than
duplicated, since it has zero business logic (pure HTML-string-in,
PDF-bytes-out).
"""
import io

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

import page_production_query_export as _ppqe

render_pdf_bytes = _ppqe.render_pdf_bytes

_HDR_FILL = PatternFill("solid", fgColor="1A73E8")
_SUBHDR_FILL = PatternFill("solid", fgColor="E8F0FE")
_SUBHDR_FONT = Font(bold=True, color="174EA6", size=9)
_SECTION_FILL = PatternFill("solid", fgColor="1A73E8")
_SECTION_FONT = Font(bold=True, color="FFFFFF", size=10)
_SAIL_FILL = PatternFill("solid", fgColor="F9AB00")
_SAIL_FONT = Font(bold=True, color="3C2F00", size=9)
_ZEBRA_FILL = PatternFill("solid", fgColor="F8F9FA")
_THIN = Side(style="thin", color="DADCE0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return round(v, 3)
    return v


def build_excel_bytes(data: dict) -> bytes:
    months = data.get("months", [])
    params = data.get("params", [])
    rows = data.get("rows", [])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BF Benchmarking"[:31]

    ws.cell(row=1, column=1, value="Large BF Benchmarking — Comparative Performance Analysis").font = Font(bold=True, size=13)
    ws.cell(row=2, column=1, value=f"Months: {', '.join(months)}").font = Font(italic=True, size=9)

    total_cols = 1 + len(months) + 1  # BF + months + FY Avg
    row = 4

    # Working Volume section (static, single column)
    wc = ws.cell(row=row, column=1, value="Working Volume (m³)")
    wc.font = _SECTION_FONT; wc.fill = _SECTION_FILL
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ws.cell(row=row, column=2).fill = _SECTION_FILL
    row += 1
    for idx, r in enumerate(rows):
        fill = _SAIL_FILL if r.get("is_sail") else (_ZEBRA_FILL if idx % 2 == 1 else None)
        font = _SAIL_FONT if r.get("is_sail") else Font(size=9)
        lc = ws.cell(row=row, column=1, value=r.get("label", ""))
        lc.font = font; lc.border = _BORDER
        vc = ws.cell(row=row, column=2, value=_fmt(r.get("working_volume_m3")))
        vc.font = font; vc.border = _BORDER; vc.alignment = Alignment(horizontal="right")
        if fill:
            lc.fill = fill; vc.fill = fill
        row += 1
    row += 1

    headers = ["BF"] + months + ["FY Avg"]
    for p in params:
        if p.get("static"):
            continue
        key, label, unit = p["key"], p["label"], p.get("unit", "")
        sc = ws.cell(row=row, column=1, value=f"{label} ({unit})" if unit else label)
        sc.font = _SECTION_FONT; sc.fill = _SECTION_FILL
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=total_cols)
        for c in range(2, total_cols + 1):
            ws.cell(row=row, column=c).fill = _SECTION_FILL
        row += 1

        for c, h in enumerate(headers, start=1):
            hc = ws.cell(row=row, column=c, value=h)
            hc.font = _SUBHDR_FONT; hc.fill = _SUBHDR_FILL
            hc.alignment = Alignment(horizontal="center"); hc.border = _BORDER
        row += 1

        for idx, r in enumerate(rows):
            fill = _SAIL_FILL if r.get("is_sail") else (_ZEBRA_FILL if idx % 2 == 1 else None)
            font = _SAIL_FONT if r.get("is_sail") else Font(size=9)
            pdata = (r.get("params") or {}).get(key, {})
            mv = pdata.get("month_values", {}) or {}
            values = [r.get("label", "")] + [_fmt(mv.get(m)) for m in months] + [_fmt(pdata.get("avg"))]
            for c, v in enumerate(values, start=1):
                vc = ws.cell(row=row, column=c, value=v)
                vc.font = font; vc.border = _BORDER
                vc.alignment = Alignment(horizontal="left" if c == 1 else "right")
                if fill:
                    vc.fill = fill
            row += 1
        row += 1

    ws.column_dimensions["A"].width = 20
    for i in range(2, total_cols + 1):
        ws.column_dimensions[get_column_letter(i)].width = 12
    ws.freeze_panes = "A5"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_pdf_html(data: dict) -> str:
    months = data.get("months", [])
    params = data.get("params", [])
    rows = data.get("rows", [])

    wv_rows = []
    for r in rows:
        wv_rows.append(
            f'<tr class="{"sail-row" if r.get("is_sail") else ""}">'
            f'<td class="bf">{r.get("label","")}</td><td>{_fmt(r.get("working_volume_m3")) or "—"}</td></tr>'
        )
    sections_html = [
        '<div class="section-title">Working Volume (m³)</div>'
        '<table><thead><tr><th>BF</th><th>Working Volume</th></tr></thead>'
        f'<tbody>{"".join(wv_rows)}</tbody></table>'
    ]

    header_html = "<th>BF</th>" + "".join(f"<th>{m}</th>" for m in months) + "<th>FY Avg</th>"
    for p in params:
        if p.get("static"):
            continue
        key, label, unit = p["key"], p["label"], p.get("unit", "")
        body_rows = []
        for r in rows:
            pdata = (r.get("params") or {}).get(key, {})
            mv = pdata.get("month_values", {}) or {}
            cells = [f'<td class="bf">{r.get("label","")}</td>']
            for m in months:
                v = _fmt(mv.get(m))
                cells.append(f"<td>{v if v != '' else '—'}</td>")
            avg = _fmt(pdata.get("avg"))
            cells.append(f'<td class="avg">{avg if avg != "" else "—"}</td>')
            body_rows.append(f'<tr class="{"sail-row" if r.get("is_sail") else ""}">{"".join(cells)}</tr>')
        title = f"{label} ({unit})" if unit else label
        sections_html.append(
            f'<div class="section-title">{title}</div>'
            f'<table><thead><tr>{header_html}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table>'
        )

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: A4 landscape; margin: 12mm 10mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, sans-serif; color: #202124; margin: 0; }}
  h1 {{ font-size: 14pt; margin: 0 0 2px 0; }}
  .subtitle {{ font-size: 9pt; color: #5f6368; margin: 0 0 8px 0; }}
  .section-title {{ background: #1a73e8; color: #fff; font-weight: 700; font-size: 9.5pt;
    padding: 4px 6px; margin-top: 10px; page-break-after: avoid; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 8pt; margin-bottom: 4px; }}
  thead {{ display: table-header-group; }}
  tr {{ page-break-inside: avoid; }}
  th, td {{ border: 1px solid #dadce0; padding: 3px 6px; text-align: right; white-space: nowrap; }}
  th {{ background: #e8f0fe; color: #174ea6; font-weight: 700; }}
  td.bf {{ text-align: left; font-weight: 700; }}
  td.avg {{ font-weight: 700; }}
  tr:nth-child(even) td {{ background: #f8f9fa; }}
  tr.sail-row td {{ background: #f9ab00; color: #3c2f00; font-weight: 700; }}
</style>
</head>
<body>
  <h1>Large BF Benchmarking — Comparative Performance Analysis</h1>
  <p class="subtitle">Months: {', '.join(months)}</p>
  {''.join(sections_html)}
</body></html>"""
