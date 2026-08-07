"""
Excel / PDF export for the Large BF Benchmarking comparison page
(frontend: /reports/bf-benchmark). Takes the same dict api_bf_benchmark.
build_compare() returns — {params, sail_bfs, year_blocks, external_blocks}
— so the export always matches what's on screen.

Layout: one row per parameter (2 leading columns: Parameter, Unit), then
one merged column-group per selected SAIL year (month columns × SAIL BFs,
plus an FY Avg group), followed by one merged column-group per non-SAIL BF
showing its own last-available FY.

render_pdf_bytes is imported from page_production_query_export.py directly
rather than duplicated, since it has zero business logic (pure
HTML-string-in, PDF-bytes-out).
"""
import io

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

import page_production_query_export as _ppqe

render_pdf_bytes = _ppqe.render_pdf_bytes

_HDR_FILL = PatternFill("solid", fgColor="1A73E8")
_HDR_FONT = Font(bold=True, color="FFFFFF", size=9)
_SUBHDR_FILL = PatternFill("solid", fgColor="E8F0FE")
_SUBHDR_FONT = Font(bold=True, color="174EA6", size=8)
_AVG_FILL = PatternFill("solid", fgColor="D2E3FC")
_ZEBRA_FILL = PatternFill("solid", fgColor="F8F9FA")
_THIN = Side(style="thin", color="DADCE0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return round(v, 3)
    return v


def _sail_bf_labels(sail_bfs):
    return [b.get("plant", b.get("label", "")) for b in sail_bfs]


def _year_group_width(year_block, n_sail_bfs):
    return (len(year_block["months"]) + 1) * n_sail_bfs  # +1 for FY Avg


def _external_group_width(ext_block):
    return len(ext_block["months"]) + 1 if ext_block.get("has_data") else 1


def build_excel_bytes(data: dict) -> bytes:
    params = [p for p in data.get("params", []) if not p.get("static")]
    sail_bfs = data.get("sail_bfs", [])
    n_sail = len(sail_bfs)
    sail_labels = _sail_bf_labels(sail_bfs)
    years = sorted(data.get("year_blocks", {}).keys(), key=int)
    ext_ids = list(data.get("external_blocks", {}).keys())

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BF Benchmarking"[:31]

    ws.cell(row=1, column=1, value="Large BF Benchmarking — Comparative Performance Analysis").font = Font(bold=True, size=13)

    r1, r2, r3 = 3, 4, 5  # header rows: year/BF-name | month/FY-Avg | SAIL-BF sub-cols
    ws.cell(row=r1, column=1, value="Techno Parameter").font = _HDR_FONT
    ws.cell(row=r1, column=1).fill = _HDR_FILL
    ws.merge_cells(start_row=r1, start_column=1, end_row=r3, end_column=1)
    ws.cell(row=r1, column=2, value="Unit").font = _HDR_FONT
    ws.cell(row=r1, column=2).fill = _HDR_FILL
    ws.merge_cells(start_row=r1, start_column=2, end_row=r3, end_column=2)

    col = 3
    year_col_start = {}
    for y in years:
        yb = data["year_blocks"][y]
        width = _year_group_width(yb, n_sail) if n_sail else 0
        if width == 0:
            continue
        year_col_start[y] = col
        hc = ws.cell(row=r1, column=col, value=f"FY {yb['fy_label']}")
        hc.font = _HDR_FONT; hc.fill = _HDR_FILL
        ws.merge_cells(start_row=r1, start_column=col, end_row=r1, end_column=col + width - 1)
        for c in range(col, col + width):
            ws.cell(row=r1, column=c).fill = _HDR_FILL
        c2 = col
        for m in yb["months"] + ["FY Avg"]:
            hc2 = ws.cell(row=r2, column=c2, value=m)
            hc2.font = _SUBHDR_FONT; hc2.fill = _SUBHDR_FILL
            hc2.alignment = Alignment(horizontal="center")
            ws.merge_cells(start_row=r2, start_column=c2, end_row=r2, end_column=c2 + n_sail - 1)
            for c3, lbl in enumerate(sail_labels, start=c2):
                hc3 = ws.cell(row=r3, column=c3, value=lbl)
                hc3.font = _SUBHDR_FONT; hc3.fill = _SUBHDR_FILL
                hc3.alignment = Alignment(horizontal="center")
                hc3.border = _BORDER
            c2 += n_sail
        col += width

    ext_col_start = {}
    for bf_id in ext_ids:
        eb = data["external_blocks"][bf_id]
        width = _external_group_width(eb)
        ext_col_start[bf_id] = col
        title = f"{eb['label']} (FY {eb['fy_label']})" if eb.get("has_data") else f"{eb['label']} (no data)"
        hc = ws.cell(row=r1, column=col, value=title)
        hc.font = _HDR_FONT; hc.fill = _HDR_FILL
        ws.merge_cells(start_row=r1, start_column=col, end_row=r1, end_column=col + width - 1)
        for c in range(col, col + width):
            ws.cell(row=r1, column=c).fill = _HDR_FILL
        if eb.get("has_data"):
            for c2, m in enumerate(eb["months"] + ["FY Avg"], start=col):
                hc2 = ws.cell(row=r2, column=c2, value=m)
                hc2.font = _SUBHDR_FONT; hc2.fill = _SUBHDR_FILL
                hc2.alignment = Alignment(horizontal="center")
                ws.merge_cells(start_row=r2, start_column=c2, end_row=r3, end_column=c2)
        else:
            ws.merge_cells(start_row=r2, start_column=col, end_row=r3, end_column=col)
        col += width

    total_cols = col - 1
    row = r3 + 1
    for p in params:
        key, label, unit = p["key"], p["label"], p.get("unit", "")
        lc = ws.cell(row=row, column=1, value=label); lc.border = _BORDER
        uc = ws.cell(row=row, column=2, value=unit); uc.border = _BORDER
        fill = _ZEBRA_FILL if row % 2 == 0 else None
        if fill:
            lc.fill = fill; uc.fill = fill

        for y in years:
            yb = data["year_blocks"][y]
            base = year_col_start.get(y)
            if base is None:
                continue
            c = base
            for m in yb["months"]:
                for bidx in range(n_sail):
                    pd = yb["rows"][bidx]["params"].get(key, {})
                    v = _fmt((pd.get("month_values") or {}).get(m))
                    vc = ws.cell(row=row, column=c, value=v)
                    vc.border = _BORDER; vc.alignment = Alignment(horizontal="right")
                    if fill:
                        vc.fill = fill
                    c += 1
            for bidx in range(n_sail):
                pd = yb["rows"][bidx]["params"].get(key, {})
                vc = ws.cell(row=row, column=c, value=_fmt(pd.get("avg")))
                vc.font = Font(bold=True); vc.border = _BORDER; vc.alignment = Alignment(horizontal="right")
                vc.fill = _AVG_FILL
                c += 1

        for bf_id in ext_ids:
            eb = data["external_blocks"][bf_id]
            base = ext_col_start[bf_id]
            if not eb.get("has_data"):
                vc = ws.cell(row=row, column=base, value="—")
                vc.border = _BORDER; vc.alignment = Alignment(horizontal="center")
                if fill:
                    vc.fill = fill
                continue
            c = base
            pd = eb["params"].get(key, {})
            mv = pd.get("month_values") or {}
            for m in eb["months"]:
                vc = ws.cell(row=row, column=c, value=_fmt(mv.get(m)))
                vc.border = _BORDER; vc.alignment = Alignment(horizontal="right")
                if fill:
                    vc.fill = fill
                c += 1
            vc = ws.cell(row=row, column=c, value=_fmt(pd.get("avg")))
            vc.font = Font(bold=True); vc.border = _BORDER; vc.alignment = Alignment(horizontal="right")
            vc.fill = _AVG_FILL
        row += 1

    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 10
    for i in range(3, total_cols + 1):
        ws.column_dimensions[get_column_letter(i)].width = 10
    ws.freeze_panes = "C6"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_pdf_html(data: dict) -> str:
    params = [p for p in data.get("params", []) if not p.get("static")]
    sail_bfs = data.get("sail_bfs", [])
    n_sail = len(sail_bfs)
    sail_labels = _sail_bf_labels(sail_bfs)
    years = sorted(data.get("year_blocks", {}).keys(), key=int)
    ext_ids = list(data.get("external_blocks", {}).keys())

    row1, row2, row3 = ['<th rowspan="3">Parameter</th><th rowspan="3">Unit</th>'], [""], [""]
    for y in years:
        yb = data["year_blocks"][y]
        width = _year_group_width(yb, n_sail) if n_sail else 0
        if width == 0:
            continue
        row1.append(f'<th colspan="{width}">FY {yb["fy_label"]}</th>')
        for m in yb["months"] + ["FY Avg"]:
            row2.append(f'<th colspan="{n_sail}">{m}</th>')
        for _ in yb["months"] + ["FY Avg"]:
            for lbl in sail_labels:
                row3.append(f"<th>{lbl}</th>")

    for bf_id in ext_ids:
        eb = data["external_blocks"][bf_id]
        width = _external_group_width(eb)
        title = f'{eb["label"]} (FY {eb["fy_label"]})' if eb.get("has_data") else f'{eb["label"]} (no data)'
        row1.append(f'<th colspan="{width}">{title}</th>')
        if eb.get("has_data"):
            for m in eb["months"] + ["FY Avg"]:
                row2.append(f'<th rowspan="2">{m}</th>')
        else:
            row2.append('<th rowspan="2">—</th>')

    body_rows = []
    for p in params:
        key, label, unit = p["key"], p["label"], p.get("unit", "")
        cells = [f'<td class="param">{label}</td><td class="unit">{unit}</td>']
        for y in years:
            yb = data["year_blocks"][y]
            for m in yb["months"]:
                for bidx in range(n_sail):
                    pd = yb["rows"][bidx]["params"].get(key, {})
                    v = _fmt((pd.get("month_values") or {}).get(m))
                    cells.append(f"<td>{v if v != '' else '—'}</td>")
            for bidx in range(n_sail):
                pd = yb["rows"][bidx]["params"].get(key, {})
                v = _fmt(pd.get("avg"))
                cells.append(f'<td class="avg">{v if v != "" else "—"}</td>')
        for bf_id in ext_ids:
            eb = data["external_blocks"][bf_id]
            if not eb.get("has_data"):
                cells.append("<td>—</td>")
                continue
            pd = eb["params"].get(key, {})
            mv = pd.get("month_values") or {}
            for m in eb["months"]:
                v = _fmt(mv.get(m))
                cells.append(f"<td>{v if v != '' else '—'}</td>")
            v = _fmt(pd.get("avg"))
            cells.append(f'<td class="avg">{v if v != "" else "—"}</td>')
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: A4 landscape; margin: 10mm 8mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, sans-serif; color: #202124; margin: 0; }}
  h1 {{ font-size: 13pt; margin: 0 0 8px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 7pt; }}
  thead {{ display: table-header-group; }}
  tr {{ page-break-inside: avoid; }}
  th, td {{ border: 1px solid #dadce0; padding: 2px 4px; text-align: right; white-space: nowrap; }}
  th {{ background: #e8f0fe; color: #174ea6; font-weight: 700; text-align: center; }}
  td.param {{ text-align: left; font-weight: 700; }}
  td.unit {{ text-align: left; color: #5f6368; }}
  td.avg {{ font-weight: 700; background: #d2e3fc; }}
  tr:nth-child(even) td {{ background: #f8f9fa; }}
  tr:nth-child(even) td.avg {{ background: #d2e3fc; }}
</style>
</head>
<body>
  <h1>Large BF Benchmarking — Comparative Performance Analysis</h1>
  <table>
    <thead>
      <tr>{''.join(row1)}</tr>
      <tr>{''.join(row2)}</tr>
      <tr>{''.join(row3)}</tr>
    </thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
</body></html>"""
