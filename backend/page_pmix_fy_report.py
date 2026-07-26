"""
SAIL Pmix FY report — Report_format/pmix.xlsx format ("Pmix'26-27 ACT" sheet):
year-wise, month-wise Product Mix Performance for a selected financial year
(Apr-Mar), with 4 quarterly sum columns and a full-year cumulative column.

Reuses page_jpc_report.compute_pmix_rows() row-by-row (called once per FY
month) so this stays in sync with the JPC report's Pmix sheet — same plant
blocks, SAIL rollup, Finished Steel / ASP / SSP / VISL / Totals section,
same blanks where nothing is tracked in the DB.

Four extra rows beyond compute_pmix_rows(), specific to this template:
  Finished Steel (conversion)          — SAIL/"Conversion" (page4.py's
                                          existing SAIL-incl.-conversion item)
  Finished Steel including Conversion  — Finished Steel (Total) + Conversion
  RSP HSM-2                            — RSP/"HSM-2 Total HR Coil"
  BSL HSM                              — BSL/"HSM Total HR Coil"
(The sample file's own quarter/cum formulas for the last two rows are
broken — copy-paste leftovers referencing the wrong rows — so quarters/cum
here are computed properly as sums of that row's own months instead of
copying the same mistake.)
"""
import io

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

import db
from page_jpc_report import compute_pmix_rows, _one

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_QTR_LABELS = ["1st Qtr", "IInd Qtr", "IIIrd Qtr", "IVth Qtr"]


def _mlabel(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{_MONTHS[m - 1]}'{str(y)[2:]}"


def _fy_months(fy_start: int):
    return [f"{fy_start}-{m:02d}" for m in range(4, 13)] + \
           [f"{fy_start + 1}-{m:02d}" for m in range(1, 4)]


def _sum_opt(vals):
    nums = [v for v in vals if v is not None]
    return round(sum(nums), 3) if nums else None


_TITLE_FONT = Font(bold=True, size=13)
_UNIT_FONT = Font(italic=True, size=9)
_HDR_FONT = Font(bold=True, size=9)
_HDR_FILL = PatternFill("solid", fgColor="D9E6F5")
_PLANT_FONT = Font(bold=True, size=10)
_PLANT_FILL = PatternFill("solid", fgColor="F0F0F0")
_BOLD = Font(bold=True, size=9)
_THIN = Side(style="thin", color="B0B0B0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _num_cell(ws, row, col, value, bold=False):
    c = ws.cell(row=row, column=col)
    if value is not None:
        c.value = value
        c.number_format = "0.000"
    c.border = _BORDER
    c.alignment = Alignment(horizontal="right")
    if bold:
        c.font = _BOLD


def _label_cell(ws, row, col, text, bold=False):
    c = ws.cell(row=row, column=col, value=text)
    c.alignment = Alignment(horizontal="left")
    c.border = _BORDER
    if bold:
        c.font = _BOLD


def _plant_hdr(ws, row, label, n_cols):
    for col in range(1, n_cols + 1):
        ws.cell(row=row, column=col).fill = _PLANT_FILL
        ws.cell(row=row, column=col).border = _BORDER
    ws.cell(row=row, column=1, value=label).font = _PLANT_FONT


def build_pmix_fy_workbook(fy_start: int):
    fy_label = f"{fy_start}-{str(fy_start + 1)[2:]}"
    months = _fy_months(fy_start)
    n_cols = 1 + 12 + 4 + 1   # label + 12 months + 4 quarters + cum

    conn = db.connect()
    cur = conn.cursor()
    try:
        rows_by_month = {m: compute_pmix_rows(cur, m) for m in months}
        conversion = {m: _one(cur, "SAIL", "Conversion", m) for m in months}
        rsp_hsm2 = {m: _one(cur, "RSP", "HSM-2 Total HR Coil", m) for m in months}
        bsl_hsm = {m: _one(cur, "BSL", "HSM Total HR Coil", m) for m in months}
    finally:
        conn.close()

    n_rows = len(rows_by_month[months[0]])
    fst_by_month = {}
    for m in months:
        fst_row = next((r for r in rows_by_month[m] if r["label"] == "Finished Steel (Total)"), None)
        fst_by_month[m] = fst_row["value"] if fst_row else None

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Pmix'{fy_label[2:]} ACT"

    ws.cell(row=1, column=1, value="Operations Directorate").font = Font(size=10)
    ws.cell(row=2, column=1, value=f"Product mix Performance: {fy_label}").font = _TITLE_FONT
    ws.cell(row=2, column=n_cols, value="Unit: '000 T").font = _UNIT_FONT

    header_row = 3
    ws.cell(row=header_row, column=1, value="Item").font = _HDR_FONT
    ws.cell(row=header_row, column=1).fill = _HDR_FILL
    for i, m in enumerate(months, start=2):
        c = ws.cell(row=header_row, column=i, value=_mlabel(m))
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal="center")
    for i, label in enumerate(_QTR_LABELS, start=14):
        c = ws.cell(row=header_row, column=i, value=label)
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal="center")
    c = ws.cell(row=header_row, column=18, value="Cum")
    c.font = _HDR_FONT
    c.fill = _HDR_FILL
    c.alignment = Alignment(horizontal="center")

    def write_data_row(label, values_by_month, bold=False):
        nonlocal row
        _label_cell(ws, row, 1, label, bold=bold)
        vals = [values_by_month.get(m) for m in months]
        for i, v in enumerate(vals, start=2):
            _num_cell(ws, row, i, v, bold=bold)
        quarters = [vals[0:3], vals[3:6], vals[6:9], vals[9:12]]
        q_sums = [_sum_opt(q) for q in quarters]
        for i, qs in enumerate(q_sums, start=14):
            _num_cell(ws, row, i, qs, bold=bold)
        _num_cell(ws, row, 18, _sum_opt(q_sums), bold=bold)
        row += 1

    row = header_row + 1
    for row_idx in range(n_rows):
        spec = rows_by_month[months[0]][row_idx]
        if spec["kind"] == "header":
            _plant_hdr(ws, row, spec["label"], n_cols)
            row += 1
        else:
            values_by_month = {m: rows_by_month[m][row_idx]["value"] for m in months}
            write_data_row(spec["label"], values_by_month, bold=spec["bold"])

    write_data_row("Finished Steel (conversion)", conversion)
    fsic = {m: (fst_by_month[m] or 0) + (conversion[m] or 0)
            if fst_by_month[m] is not None or conversion[m] is not None else None
            for m in months}
    write_data_row("Finished Steel including Conversion", fsic, bold=True)
    write_data_row("RSP HSM-2", rsp_hsm2)
    write_data_row("BSL HSM", bsl_hsm)

    ws.column_dimensions["A"].width = 30
    for i in range(2, n_cols + 1):
        ws.column_dimensions[get_column_letter(i)].width = 10
    ws.freeze_panes = "B4"

    return wb


def build_pmix_fy_report_bytes(fy_start: int) -> bytes:
    wb = build_pmix_fy_workbook(fy_start)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
