"""
SAIL "1 page report" extractor — Table A (Sales) and Table D (Stock -
8 Plants) from the monthly "<Mon>'YY PS CMO" workbook
(Report_format/1 page report for <Mon><YY>.xlsx style, single sheet).

Tables B (Production) and C (Techno-Economic Parameters) are NOT
extracted here — they're already derivable from production_table /
techno tables already in this app (see page_one_page_report.py).

Table A (Sales) — anchor row starts with 'A.' and contains 'SALES';
row layout: label (col B) | .. | month ABP (D) | month Actual (E) |
month %Ful (F) | month CPLY Actual (G) | month growth (H) | cum ABP
(I) | cum Actual (J) | cum %Ful (K) | cum CPLY Actual (L) | cum growth
(M). ALL ten columns are stored verbatim, as a single JSON blob per
(report_month, item) — this table is a pure archive of what the
source department reported that month, not a computed view. Two
reasons this matters:
  1. We don't have — and can't assume we'll ever backfill — the prior
     year's own report, so deriving CPLY/growth ourselves from our own
     stored history would silently go blank instead of showing the
     figure the department already computed and included.
  2. The department's own cumulative (Apr-month) figures are
     provisional and get revised between reports — they are NOT
     reliably equal to summing each month's own individually-reported
     Actual. Re-deriving "Apr-Jun" by summing Apr+May+Jun as separately
     stored would produce a different number than what was actually
     reported for Jun, silently diverging from the source.
So: extract exactly what's on the row, store it exactly, and the
generator (page_one_page_report.py) reads it back with zero
recalculation.

Table D (Stock - 8 Plants) — anchor row starts with 'D.' and contains
'STOCK'; row layout: label (col B) | .. | one column per historical
snapshot date (e.g. '1.4.21', '01.06.26') | a trailing 'Var. w.r.t.
...' column (not a real date, skipped). Every date column present is
extracted (not just the latest) so a single file backfills history —
the same file that reports June's figures also carries 1.4.21 through
1.4.25 as reference columns.
"""
import re
from datetime import date

_SALES_LABELS = [
    "LP SALES", "FP SALES", "PET SALES", "TOTAL : HOME SALES",
    "SALES BY SPECIAL STEEL PLANTS", "EXPORTS", "TOTAL CMO SALES",
    "PLANT SALES", "TOTAL SALES",
]
_STOCK_LABELS = ["PLANTS", "STOCKYARDS", "STOCK IN TRANSIT", "TOTAL"]

# (json key, 1-based column) — verbatim columns for a Table A row
_SALES_COLS = [
    ("month_abp",         4),   # D
    ("month_actual",      5),   # E
    ("month_ful",         6),   # F
    ("month_cply",        7),   # G
    ("month_growth",      8),   # H
    ("till_month_abp",    9),   # I
    ("till_month_actual", 10),  # J
    ("till_month_ful",    11),  # K
    ("till_month_cply",   12),  # L
    ("till_month_growth", 13),  # M
]
_STOCK_FIRST_DATA_COL = 4  # D onward

_DATE_RE = re.compile(r'^(\d{1,2})\.(\d{1,2})\.(\d{2})$')


def _clean(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm(s):
    return re.sub(r'\s+', ' ', str(s or "")).strip().upper()


def _load_grid(file_path: str):
    with open(file_path, "rb") as f:
        magic = f.read(4)
    if magic[:2] == b"PK":
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        grid = [list(row) for row in wb[wb.sheetnames[0]].iter_rows(values_only=True)]
        wb.close()
        return grid
    if magic == b"\xd0\xcf\x11\xe0":
        import xlrd
        sh = xlrd.open_workbook(file_path).sheet_by_index(0)
        return [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
    raise ValueError(
        "Unrecognised file format — expected the '<Mon>'YY PS CMO' Excel "
        "workbook (.xlsx/.xls)."
    )


def _cell(grid, row_1b, col_1b):
    if row_1b < 1 or row_1b > len(grid):
        return None
    row = grid[row_1b - 1]
    if col_1b < 1 or col_1b > len(row):
        return None
    v = row[col_1b - 1]
    return None if v == "" else v


def _find_anchor(grid, prefix, contains):
    for r in range(1, len(grid) + 1):
        text = _norm(_cell(grid, r, 1))
        if text.startswith(prefix) and contains in text:
            return r
    return None


def _parse_snapshot_date(header_text):
    m = _DATE_RE.match(str(header_text or "").strip())
    if not m:
        return None
    d, mo, yy = (int(g) for g in m.groups())
    try:
        return date(2000 + yy, mo, d)
    except ValueError:
        return None


def extract_preview(file_path: str, report_month: str, **_kwargs) -> dict:
    """
    Extract Table A (Sales) + Table D (Stock) from the SAIL 1-page report.
    Returns {"sales_rows": [...], "stock_rows": [...]} — no DB writes.

    sales_rows: [{"item_name", "data": {month_abp, month_actual, month_ful,
                  month_cply, month_growth, till_month_abp, till_month_actual,
                  till_month_ful, till_month_cply, till_month_growth},
                  "cell", "status"}]
        Every field in "data" is exactly what's in the source cell — no
        %Ful/growth/cumulative is computed here (see the module docstring).
    stock_rows: [{"item_name", "snapshot_date" (YYYY-MM-DD), "value", "cell", "status"}]
    """
    grid = _load_grid(file_path)

    sales_rows = []
    sales_anchor = _find_anchor(grid, "A.", "SALES")
    if sales_anchor is None:
        raise ValueError(
            "Sales table not found — expected a row starting with 'A.' and "
            "containing 'SALES' (e.g. \"A.    SALES ['000 T]\")."
        )
    remaining = list(_SALES_LABELS)
    for r in range(sales_anchor + 1, min(sales_anchor + 15, len(grid)) + 1):
        label = _norm(_cell(grid, r, 2))
        if label in remaining:
            remaining.remove(label)
            data = {key: _clean(_cell(grid, r, col)) for key, col in _SALES_COLS}
            sales_rows.append({
                "item_name": label.title(),
                "data": data,
                "cell": f"row {r}",
                "status": "ok" if any(v is not None for v in data.values()) else "skip",
            })
        if not remaining:
            break
    for label in remaining:
        sales_rows.append({
            "item_name": label.title(),
            "data": {key: None for key, _ in _SALES_COLS},
            "cell": "", "status": "not found",
        })

    stock_rows = []
    stock_anchor = _find_anchor(grid, "D.", "STOCK")
    if stock_anchor is None:
        raise ValueError(
            "Stock table not found — expected a row starting with 'D.' and "
            "containing 'STOCK' (e.g. \"D.    STOCK  - 8 PLANTS ['000 T]\")."
        )
    header_row = stock_anchor
    date_cols = []
    c = _STOCK_FIRST_DATA_COL
    while True:
        header_text = _cell(grid, header_row, c)
        if header_text is None:
            break
        snap = _parse_snapshot_date(header_text)
        if snap is None:
            break
        date_cols.append((c, snap))
        c += 1

    remaining = list(_STOCK_LABELS)
    for r in range(stock_anchor + 1, min(stock_anchor + 10, len(grid)) + 1):
        label = _norm(_cell(grid, r, 2))
        if label in remaining:
            remaining.remove(label)
            for col, snap in date_cols:
                val = _clean(_cell(grid, r, col))
                stock_rows.append({
                    "item_name": label.title(),
                    "snapshot_date": snap.isoformat(),
                    "value": val,
                    "cell": f"row {r} / {snap.isoformat()}",
                    "status": "ok" if val is not None else "skip",
                })
        if not remaining:
            break
    for label in remaining:
        stock_rows.append({
            "item_name": label.title(), "snapshot_date": None, "value": None,
            "cell": "", "status": "not found",
        })

    ok_sales = sum(1 for r in sales_rows if r["status"] == "ok")
    ok_stock = sum(1 for r in stock_rows if r["status"] == "ok")
    if ok_sales == 0 and ok_stock == 0:
        raise ValueError(
            "No values extracted from either table — verify this is the "
            "SAIL '1 page report' workbook."
        )

    return {
        "report_month": report_month,
        "source_type": "SAIL 1-Page Report (Sales & Stock)",
        "sales_rows": sales_rows,
        "stock_rows": stock_rows,
    }
