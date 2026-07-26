"""
SAIL "1 page report" (Report_format/1 page report for Jun26.xlsx format) —
combines 4 tables into one workbook for a selected report_month:

  A. Sales             — sail_sales_table (data_json, verbatim archive —
                          extracted from the external Sales report, see
                          excel_extractors/sail_sales_stock_extractor.py;
                          every figure here — including %Ful/CPLY/Growth/
                          cumulative — is read back exactly as reported,
                          never recomputed, since the source department's
                          own cumulative figures are provisional and don't
                          reliably equal summing each month's own Actual)
  B. Production         — production_table / production_plan_table
                          (Hot Metal / Crude Steel / Saleable Steel, same
                          source as page4.py's Crude Steel Production page)
  C. Techno-Economic     — reuses page_techno.generate_summary_te_table()'s
     Parameters            SAIL rows (Coke Rate / SEC / BF Productivity)
  D. Stock - 8 Plants    — sail_stock_snapshot_table (extracted alongside
                          Sales from the same external report)

Tables A and D depend entirely on having been extracted+saved via
sail_sales_stock_extractor.py for the relevant months/dates; anything not
yet uploaded renders blank rather than guessed.
"""
import calendar
from datetime import date

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

import db
from constants import FIVE_PLANTS as _5P
from page_techno import generate_summary_te_table

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _mlabel(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{_MONTHS[m - 1]}'{str(y)[2:]}"


def _fy_start(ym: str) -> int:
    y, m = int(ym[:4]), int(ym[5:7])
    return y if m >= 4 else y - 1


def _cum_label(month: str) -> str:
    fy = _fy_start(month)
    return f"Apr-{_mlabel(month)}"


def _gr(cur_v, prev_v):
    if cur_v is None or prev_v is None or prev_v == 0:
        return None
    return round((cur_v - prev_v) / abs(prev_v) * 100, 1)


def _pct_ful(actual, abp):
    if actual is None or abp is None or abp == 0:
        return None
    return round(actual / abp * 100, 1)


# ── Table A: Sales ───────────────────────────────────────────────────────

_SALES_ITEMS = [
    "Lp Sales", "Fp Sales", "Pet Sales", "Total : Home Sales",
    "Sales By Special Steel Plants", "Exports", "Total Cmo Sales",
    "Plant Sales", "Total Sales",
]


def _sales_data(cur, item, month):
    """Raw data_json for one (report_month, item) — every field exactly as
    the source department reported it, no computation. None if not extracted."""
    import json
    cur.execute("SELECT data_json FROM sail_sales_table WHERE report_month=? AND item_name=?", (month, item))
    r = cur.fetchone()
    if not r or not r[0]:
        return {}
    data = r[0] if isinstance(r[0], dict) else json.loads(r[0])
    return data or {}


def _sum_months(getter, months):
    total, found = 0.0, False
    for m in months:
        v = getter(m)
        if v is not None:
            total += v
            found = True
    return round(total, 3) if found else None


def _build_sales_rows(cur, month):
    """Table A rows, read back verbatim — no CPLY/cumulative lookups or
    summation across months; this month's own report already carries
    everything (see sail_sales_stock_extractor.py's module docstring)."""
    rows = []
    for item in _SALES_ITEMS:
        d = _sales_data(cur, item, month)
        rows.append({
            "label": item, "bold": item.upper().startswith("TOTAL"),
            "m_abp": d.get("month_abp"), "m_act": d.get("month_actual"),
            "m_ful": d.get("month_ful"), "m_cply": d.get("month_cply"),
            "m_growth": d.get("month_growth"),
            "c_abp": d.get("till_month_abp"), "c_act": d.get("till_month_actual"),
            "c_ful": d.get("till_month_ful"), "c_cply": d.get("till_month_cply"),
            "c_growth": d.get("till_month_growth"),
        })
    return rows


# ── Table B: Production ─────────────────────────────────────────────────

def _p_one(cur, table, plant, item, month):
    tbl = "production_table" if table == "act" else "production_plan_table"
    cur.execute(f"SELECT month_actual FROM {tbl} WHERE report_month=? AND plant_name=? AND item_name=?",
                (month, plant, item))
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None


def _p_sum(cur, table, plants, item, month):
    if not plants:
        return None
    tbl = "production_table" if table == "act" else "production_plan_table"
    phs = ",".join("?" for _ in plants)
    cur.execute(f"SELECT SUM(month_actual) FROM {tbl} WHERE report_month=? AND plant_name IN ({phs}) AND item_name=?",
                [month] + list(plants) + [item])
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None


def _p_cum_one(cur, table, plant, item, months):
    return _sum_months(lambda mo: _p_one(cur, table, plant, item, mo), months)


def _p_cum_sum(cur, table, plants, item, months):
    return _sum_months(lambda mo: _p_sum(cur, table, plants, item, mo), months)


def _prod_row(label, m_abp, m_act, m_cply, c_abp, c_act, c_cply, indent=1, bold=False):
    return {"label": label, "indent": indent, "bold": bold,
            "m_abp": m_abp, "m_act": m_act, "m_cply": m_cply,
            "c_abp": c_abp, "c_act": c_act, "c_cply": c_cply}


def _build_production_rows(cur, month, cply_month, ytd_months, cply_ytd_months):
    rows = []

    def plant_block(item, plants, extra_plants=None, extra_label=None):
        block = []
        for p in plants:
            block.append(_prod_row(
                f"-{p}",
                _p_one(cur, "plan", p, item, month), _p_one(cur, "act", p, item, month),
                _p_one(cur, "act", p, item, cply_month),
                _p_cum_one(cur, "plan", p, item, ytd_months), _p_cum_one(cur, "act", p, item, ytd_months),
                _p_cum_one(cur, "act", p, item, cply_ytd_months)))
        block.append(_prod_row(
            "Total: 5 PLANTS",
            _p_sum(cur, "plan", plants, item, month), _p_sum(cur, "act", plants, item, month),
            _p_sum(cur, "act", plants, item, cply_month),
            _p_cum_sum(cur, "plan", plants, item, ytd_months), _p_cum_sum(cur, "act", plants, item, ytd_months),
            _p_cum_sum(cur, "act", plants, item, cply_ytd_months), bold=True))
        sail_set = list(plants) + list(extra_plants or [])
        if extra_plants and extra_label:
            block.append(_prod_row(
                extra_label,
                _p_sum(cur, "plan", extra_plants, item, month), _p_sum(cur, "act", extra_plants, item, month),
                _p_sum(cur, "act", extra_plants, item, cply_month),
                _p_cum_sum(cur, "plan", extra_plants, item, ytd_months), _p_cum_sum(cur, "act", extra_plants, item, ytd_months),
                _p_cum_sum(cur, "act", extra_plants, item, cply_ytd_months)))
        block.append(_prod_row(
            "SAIL (Total)",
            _p_sum(cur, "plan", sail_set, item, month), _p_sum(cur, "act", sail_set, item, month),
            _p_sum(cur, "act", sail_set, item, cply_month),
            _p_cum_sum(cur, "plan", sail_set, item, ytd_months), _p_cum_sum(cur, "act", sail_set, item, ytd_months),
            _p_cum_sum(cur, "act", sail_set, item, cply_ytd_months), bold=True))
        return block

    rows.append({"label": "HOT METAL", "header": True})
    rows += plant_block("Hot Metal", _5P, extra_plants=["VISL"])

    rows.append(_prod_row(
        "CRUDE STEEL",
        _p_sum(cur, "plan", _5P + ["ASP", "SSP", "VISL"], "Total Crude Steel", month),
        _p_sum(cur, "act", _5P + ["ASP", "SSP", "VISL"], "Total Crude Steel", month),
        _p_sum(cur, "act", _5P + ["ASP", "SSP", "VISL"], "Total Crude Steel", cply_month),
        _p_cum_sum(cur, "plan", _5P + ["ASP", "SSP", "VISL"], "Total Crude Steel", ytd_months),
        _p_cum_sum(cur, "act", _5P + ["ASP", "SSP", "VISL"], "Total Crude Steel", ytd_months),
        _p_cum_sum(cur, "act", _5P + ["ASP", "SSP", "VISL"], "Total Crude Steel", cply_ytd_months),
        indent=0, bold=True))

    rows.append({"label": "SALEABLE STEEL", "header": True})
    for p in _5P:
        rows.append(_prod_row(
            f"-{p}",
            _p_one(cur, "plan", p, "Saleable Steel", month), _p_one(cur, "act", p, "Saleable Steel", month),
            _p_one(cur, "act", p, "Saleable Steel", cply_month),
            _p_cum_one(cur, "plan", p, "Saleable Steel", ytd_months), _p_cum_one(cur, "act", p, "Saleable Steel", ytd_months),
            _p_cum_one(cur, "act", p, "Saleable Steel", cply_ytd_months)))
    rows.append(_prod_row(
        "Total: 5 PLANTS",
        _p_sum(cur, "plan", _5P, "Saleable Steel", month), _p_sum(cur, "act", _5P, "Saleable Steel", month),
        _p_sum(cur, "act", _5P, "Saleable Steel", cply_month),
        _p_cum_sum(cur, "plan", _5P, "Saleable Steel", ytd_months), _p_cum_sum(cur, "act", _5P, "Saleable Steel", ytd_months),
        _p_cum_sum(cur, "act", _5P, "Saleable Steel", cply_ytd_months), bold=True))
    ssp_plants = ["ASP", "SSP", "VISL"]
    rows.append(_prod_row(
        "SPECIAL STEEL PLANTS",
        _p_sum(cur, "plan", ssp_plants, "Saleable Steel", month), _p_sum(cur, "act", ssp_plants, "Saleable Steel", month),
        _p_sum(cur, "act", ssp_plants, "Saleable Steel", cply_month),
        _p_cum_sum(cur, "plan", ssp_plants, "Saleable Steel", ytd_months), _p_cum_sum(cur, "act", ssp_plants, "Saleable Steel", ytd_months),
        _p_cum_sum(cur, "act", ssp_plants, "Saleable Steel", cply_ytd_months)))
    sail_set = _5P + ssp_plants
    rows.append(_prod_row(
        "SAIL (Total)",
        _p_sum(cur, "plan", sail_set, "Saleable Steel", month), _p_sum(cur, "act", sail_set, "Saleable Steel", month),
        _p_sum(cur, "act", sail_set, "Saleable Steel", cply_month),
        _p_cum_sum(cur, "plan", sail_set, "Saleable Steel", ytd_months), _p_cum_sum(cur, "act", sail_set, "Saleable Steel", ytd_months),
        _p_cum_sum(cur, "act", sail_set, "Saleable Steel", cply_ytd_months), bold=True))

    return rows


# ── Table C: Techno-Economic Parameters ─────────────────────────────────

_TECHNO_WANTED = ["Coke Rate", "Specific Energy Consumption", "BF Productivity"]
_TECHNO_DISPLAY = {
    "Coke Rate": "COKE RATE (Kg/THM)",
    "Specific Energy Consumption": "ENERGY CONSUMPTION (G Cal/TCS)",
    "BF Productivity": "BF PRODUCTIVITY (T/CuM/Day)",
}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build_techno_rows(month):
    te = generate_summary_te_table(month)
    by_param = {r["parameter"]: r for r in te}
    rows = []
    for param in _TECHNO_WANTED:
        r = by_param.get(param, {})
        vals = r.get("values", [])
        abp = _num(vals[0]) if len(vals) > 0 else None
        m_act = _num(vals[1]) if len(vals) > 1 else None
        m_cply = _num(vals[2]) if len(vals) > 2 else None
        c_act = _num(vals[3]) if len(vals) > 3 else None
        c_cply = _num(vals[4]) if len(vals) > 4 else None
        # Lower is better for these rate/consumption params, so "% imp." is
        # (CPLY - Actual)/CPLY — a decrease shows as a positive improvement.
        m_imp = round((m_cply - m_act) / m_cply * 100, 1) if m_act is not None and m_cply else None
        c_imp = round((c_cply - c_act) / c_cply * 100, 1) if c_act is not None and c_cply else None
        rows.append({
            "label": _TECHNO_DISPLAY[param], "abp": abp,
            "m_act": m_act, "m_cply": m_cply, "m_imp": m_imp,
            "c_act": c_act, "c_cply": c_cply, "c_imp": c_imp,
        })
    return rows


# ── Table D: Stock - 8 Plants ────────────────────────────────────────────

_STOCK_ITEMS = ["Plants", "Stockyards", "Stock In Transit", "Total"]


def _stock_reference_dates(as_on: date):
    """Column dates to show: April 1st of the last 5 FYs, the H1 midpoint
    (Sep 1) of the FY immediately before the current one, this FY's start,
    previous month, and the current 'as on' date — matches the sample
    file's own column selection (1.4.21..1.4.25, 1.9.25, 1.4.26, 1.6.26,
    1.7.26 for a Jun'26 report). Adjust here if a different history window
    is wanted in future."""
    fy = as_on.year if as_on.month >= 4 else as_on.year - 1
    dates = [date(fy - i, 4, 1) for i in range(5, 0, -1)]
    dates.append(date(fy - 1, 9, 1))
    dates.append(date(fy, 4, 1))
    prev_month_end = as_on.replace(day=1)
    py, pm = (prev_month_end.year, prev_month_end.month - 1) if prev_month_end.month > 1 else (prev_month_end.year - 1, 12)
    dates.append(date(py, pm, 1))
    dates.append(as_on)
    # de-dup while preserving order (as_on may coincide with an FY-start etc.)
    seen, out = set(), []
    for d in dates:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return sorted(out)


def _stock_value(cur, item, snap_date):
    cur.execute("SELECT value FROM sail_stock_snapshot_table WHERE snapshot_date=? AND item_name=?",
                (snap_date.isoformat(), item))
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None


def _build_stock_table(cur, month):
    y, m = int(month[:4]), int(month[5:7])
    as_on = date(y + (1 if m == 12 else 0), (m % 12) + 1, 1)
    dates = _stock_reference_dates(as_on)
    fy_start_date = date(as_on.year if as_on.month >= 4 else as_on.year - 1, 4, 1)

    rows = []
    for item in _STOCK_ITEMS:
        vals = [_stock_value(cur, item, d) for d in dates]
        fy_start_val = _stock_value(cur, item, fy_start_date)
        var = round(vals[-1] - fy_start_val, 3) if vals and vals[-1] is not None and fy_start_val is not None else None
        rows.append({"label": item, "values": vals, "var": var, "bold": item == "Total"})
    return {"dates": dates, "fy_start_date": fy_start_date, "rows": rows}


# ── Excel writer ─────────────────────────────────────────────────────────

_TITLE_FONT = Font(bold=True, size=13)
_SEC_FONT = Font(bold=True, size=10.5)
_SEC_FILL = PatternFill("solid", fgColor="1A73E8")
_SEC_FONT_WHITE = Font(bold=True, size=10.5, color="FFFFFF")
_HDR_FONT = Font(bold=True, size=9)
_HDR_FILL = PatternFill("solid", fgColor="D9E6F5")
_BOLD = Font(bold=True, size=9)
_THIN = Side(style="thin", color="B0B0B0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _num_cell(ws, row, col, value, bold=False, pct=False, frac_pct=False):
    c = ws.cell(row=row, column=col)
    if value is not None:
        c.value = value
        c.number_format = "0.0%" if frac_pct else ("0.0" if pct else "0.000")
    c.border = _BORDER
    c.alignment = Alignment(horizontal="right")
    if bold:
        c.font = _BOLD


def _label_cell(ws, row, col, text, indent=0, bold=False):
    c = ws.cell(row=row, column=col, value=text)
    c.alignment = Alignment(horizontal="left", indent=indent)
    c.border = _BORDER
    if bold:
        c.font = _BOLD


def _section_header(ws, row, text, span):
    for col in range(1, span + 1):
        c = ws.cell(row=row, column=col)
        c.fill = _SEC_FILL
        c.border = _BORDER
    ws.cell(row=row, column=1, value=text).font = _SEC_FONT_WHITE


def build_one_page_workbook(report_month: str):
    cply_month = db.get_cply_month(report_month)
    ytd_months = db.get_ytd_months(report_month)
    cply_ytd_months = [db.get_cply_month(m) for m in ytd_months]

    conn = db.connect()
    cur = conn.cursor()
    try:
        sales_rows = _build_sales_rows(cur, report_month)
        prod_rows = _build_production_rows(cur, report_month, cply_month, ytd_months, cply_ytd_months)
        techno_rows = _build_techno_rows(report_month)
        stock = _build_stock_table(cur, report_month)
    finally:
        conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{_mlabel(report_month)} PS CMO"

    ws.cell(row=1, column=1,
            value=f"PERFORMANCE: {_mlabel(report_month)} and {_cum_label(report_month)}"
            ).font = _TITLE_FONT
    ws.cell(row=2, column=1, value="Unit: '000 T").font = Font(italic=True, size=9)

    cply_label = _mlabel(cply_month)
    cply_cum_label = _cum_label(cply_month)
    cum_label = _cum_label(report_month)

    row = 4
    _section_header(ws, row, "A. SALES ['000 T]", 11)
    row += 1
    # month block: cols 2-6 (ABP, Actual, %Ful, CPLY, %Gr); cum block: cols 7-11
    for col, text in enumerate(["Item", f"{_mlabel(report_month)} ABP", f"{_mlabel(report_month)} Actual",
                                 "% Ful", f"{cply_label} Actual", "% Gr.",
                                 f"{cum_label} ABP", f"{cum_label} Actual", "% Ful",
                                 f"{cply_cum_label} Actual", "% Gr."], start=1):
        c = ws.cell(row=row, column=col, value=text)
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    row += 1

    def write_metric_row(label, m_abp, m_act, m_cply, c_abp, c_act, c_cply, indent=1, bold=False):
        nonlocal row
        _label_cell(ws, row, 1, label, indent=indent, bold=bold)
        _num_cell(ws, row, 2, m_abp, bold=bold)
        _num_cell(ws, row, 3, m_act, bold=bold)
        _num_cell(ws, row, 4, _pct_ful(m_act, m_abp), bold=bold, pct=True)
        _num_cell(ws, row, 5, m_cply, bold=bold)
        _num_cell(ws, row, 6, _gr(m_act, m_cply), bold=bold, pct=True)
        _num_cell(ws, row, 7, c_abp, bold=bold)
        _num_cell(ws, row, 8, c_act, bold=bold)
        _num_cell(ws, row, 9, _pct_ful(c_act, c_abp), bold=bold, pct=True)
        _num_cell(ws, row, 10, c_cply, bold=bold)
        _num_cell(ws, row, 11, _gr(c_act, c_cply), bold=bold, pct=True)
        row += 1

    def write_sales_row(r):
        # Every value here — including %Ful/Growth — is written back exactly
        # as the source department reported it; nothing is computed (see
        # sail_sales_stock_extractor.py). %Ful/Growth are stored as raw
        # fractions (0.81, not 81), so they're formatted as Excel percentages
        # rather than rescaled.
        nonlocal row
        _label_cell(ws, row, 1, r["label"], indent=1, bold=r["bold"])
        _num_cell(ws, row, 2, r["m_abp"], bold=r["bold"])
        _num_cell(ws, row, 3, r["m_act"], bold=r["bold"])
        _num_cell(ws, row, 4, r["m_ful"], bold=r["bold"], frac_pct=True)
        _num_cell(ws, row, 5, r["m_cply"], bold=r["bold"])
        _num_cell(ws, row, 6, r["m_growth"], bold=r["bold"], frac_pct=True)
        _num_cell(ws, row, 7, r["c_abp"], bold=r["bold"])
        _num_cell(ws, row, 8, r["c_act"], bold=r["bold"])
        _num_cell(ws, row, 9, r["c_ful"], bold=r["bold"], frac_pct=True)
        _num_cell(ws, row, 10, r["c_cply"], bold=r["bold"])
        _num_cell(ws, row, 11, r["c_growth"], bold=r["bold"], frac_pct=True)
        row += 1

    for r in sales_rows:
        write_sales_row(r)

    row += 1
    _section_header(ws, row, "B. PRODUCTION ['000 T]", 11)
    row += 1
    for col, text in enumerate(["Item", f"{_mlabel(report_month)} ABP", f"{_mlabel(report_month)} Actual",
                                 "% Ful", f"{cply_label} Actual", "% Gr.",
                                 f"{cum_label} ABP", f"{cum_label} Actual", "% Ful",
                                 f"{cply_cum_label} Actual", "% Gr."], start=1):
        c = ws.cell(row=row, column=col, value=text)
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    row += 1
    for r in prod_rows:
        if r.get("header"):
            _section_header(ws, row, r["label"], 11)
            row += 1
            continue
        write_metric_row(r["label"], r["m_abp"], r["m_act"], r["m_cply"],
                         r["c_abp"], r["c_act"], r["c_cply"],
                         indent=r.get("indent", 1), bold=r.get("bold", False))

    row += 1
    _section_header(ws, row, "C. TECHNO-ECONOMIC PARAMETERS", 8)
    row += 1
    for col, text in enumerate(["Item", "ABP", f"{_mlabel(report_month)}", f"{cply_label}", "% imp.",
                                 f"{cum_label}", f"{cply_cum_label}", "% imp."], start=1):
        c = ws.cell(row=row, column=col, value=text)
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    row += 1
    for r in techno_rows:
        _label_cell(ws, row, 1, r["label"], indent=1)
        _num_cell(ws, row, 2, r["abp"])
        _num_cell(ws, row, 3, r["m_act"])
        _num_cell(ws, row, 4, r["m_cply"])
        _num_cell(ws, row, 5, r["m_imp"], pct=True)
        _num_cell(ws, row, 6, r["c_act"])
        _num_cell(ws, row, 7, r["c_cply"])
        _num_cell(ws, row, 8, r["c_imp"], pct=True)
        row += 1

    row += 1
    n_date_cols = len(stock["dates"])
    _section_header(ws, row, "D. STOCK - 8 PLANTS ['000 T]", n_date_cols + 2)
    row += 1
    ws.cell(row=row, column=1, value="Item").font = _HDR_FONT
    ws.cell(row=row, column=1).fill = _HDR_FILL
    for i, d in enumerate(stock["dates"], start=2):
        c = ws.cell(row=row, column=i, value=d.strftime("%d.%m.%y"))
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal="center")
    var_col = n_date_cols + 2
    fy_d = stock["fy_start_date"]
    var_header = f"Var. w.r.t. {fy_d.day}.{fy_d.month}.{fy_d.strftime('%y')}"
    c = ws.cell(row=row, column=var_col, value=var_header)
    c.font = _HDR_FONT
    c.fill = _HDR_FILL
    c.alignment = Alignment(horizontal="center", wrap_text=True)
    row += 1
    for r in stock["rows"]:
        _label_cell(ws, row, 1, r["label"], indent=1, bold=r["bold"])
        for i, v in enumerate(r["values"], start=2):
            _num_cell(ws, row, i, v, bold=r["bold"])
        _num_cell(ws, row, var_col, r["var"], bold=r["bold"])
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Note: All figures are provisional").font = Font(italic=True, size=8)

    ws.column_dimensions["A"].width = 30
    for i in range(2, 12):
        ws.column_dimensions[get_column_letter(i)].width = 11
    ws.freeze_panes = "B5"

    return wb


def build_one_page_report_bytes(report_month: str) -> bytes:
    import io
    wb = build_one_page_workbook(report_month)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
