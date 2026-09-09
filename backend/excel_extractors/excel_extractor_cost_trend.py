"""
Cost Trend Excel extractor — reads one "ELHM CS SS <...>.xlsx" elementwise
cost-of-production workbook (kept in Report_format/Cost/, one per month plus
one cumulative "APRIL-<month>" file per month after April) and pulls out the
per-plant VARIABLE and FIXED cost (Rs/T) from each sheet's "TOTAL COST" row,
for HM/CS/SS and all 6 plant blocks (BSP/DSP/RSP/BSL/ISP/SAIL).

Feeds db.cost_trend_monthly — see page_cost_trend.py and frontend/src/app/
data-entry/cost-trend for how this data is used/entered manually; this
extractor is the automated alternative for months a source workbook exists
for. TOTAL COST itself is never extracted/stored — it stays computed
(VARIABLE + FIXED) in page_cost_trend.py, same as the manual-entry path.

Workbook layout (consistent across HM/CS/SS sheets and both file kinds,
confirmed against Report_format/Cost/*.xlsx):
  - Row 3 holds a cell reading "<Month>'<YYYY>" for a single month's figures,
    or "UPTO <Month>'<YYYY>" for a cumulative (till-month) file — this is
    the authoritative source of report_month/kind, not the filename.
  - Row 6 holds plant labels (BSP, DSP, RSP, BSL, ISP, "SAIL (5 ISP'S)"),
    one per 5-column block (PRICE, USAGE, VARIABLE, FIXED, COST) starting
    at column C.
  - The row whose column B reads "TOTAL COST (...)" holds the final blended
    VARIABLE/FIXED Rs/T figures extracted here. SAIL's block is its own
    reported blended rate — confirmed NOT a sum of the other 5 blocks — so
    it's extracted the same way as any other plant, not derived.
"""
import re

import openpyxl

PLANT_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]
_BLOCK_START_COLS = [3, 8, 13, 18, 23, 28]  # C, H, M, R, W, AB (1-indexed)
_VARIABLE_OFFSET = 2  # PRICE(+0), USAGE(+1), VARIABLE(+2), FIXED(+3), COST(+4)
_FIXED_OFFSET = 3

_MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_HEADER_RE = re.compile(r"([A-Z]{3,})'?\s*(\d{4})")


def _parse_header(text: str):
    """"<MONTH>'<YYYY>" or "UPTO <MONTH>'<YYYY>" -> (report_month 'YYYY-MM',
    is_till_month). Returns (None, None) if text doesn't match."""
    if not text:
        return None, None
    t = str(text).strip().upper().replace("’", "'")
    is_till = t.startswith("UPTO")
    m = _HEADER_RE.search(t)
    if not m:
        return None, None
    mon = _MONTH_ABBR.get(m.group(1)[:3])
    if not mon:
        return None, None
    return f"{int(m.group(2))}-{mon:02d}", is_till


def _find_month_cell_text(ws):
    """Row 3 holds the header; scan its first columns for the month text
    rather than trusting one fixed column (observed to vary by sheet)."""
    for c in range(1, 20):
        v = ws.cell(row=3, column=c).value
        if v and re.search(r"[A-Za-z]{3,}'?\s*\d{4}", str(v)):
            return str(v)
    return None


def _find_total_cost_row(ws):
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=2).value
        if v and "TOTAL COST" in str(v).upper():
            return r
    return None


def _validate_plant_label(ws, block_start_col: int, expected: str) -> bool:
    """expected's label isn't always at the same offset within its 5-column
    block (SAIL's sits on the block's first column, everyone else's on the
    second) — scan the whole block rather than assuming one offset."""
    for c in range(block_start_col, block_start_col + 5):
        v = ws.cell(row=6, column=c).value
        if v and str(v).strip().upper().startswith(expected):
            return True
    return False


def _num(v):
    return round(v, 3) if isinstance(v, (int, float)) else None


def extract_cost_trend_workbook(file_path) -> dict:
    """-> {"report_month": "YYYY-MM", "is_till_month": bool,
           "products": {"HM": {"BSP": {"variable":.., "fixed":..}, ...,
                                "SAIL": {...}},
                        "CS": {...}, "SS": {...}}}
    Raises ValueError on anything that doesn't match the expected layout —
    this feeds financial figures, so a column/row mismatch must fail loudly
    rather than silently extracting the wrong cell."""
    wb = openpyxl.load_workbook(file_path, data_only=True)

    report_month = None
    is_till_month = None
    products = {}

    for sheet_name in wb.sheetnames:
        key = sheet_name.strip().upper()
        if key not in ("HM", "CS", "SS"):
            continue
        ws = wb[sheet_name]

        header_text = _find_month_cell_text(ws)
        rm, till = _parse_header(header_text)
        if rm is None:
            raise ValueError(
                f"Sheet '{sheet_name}': could not parse a report month from row 3 (found: {header_text!r})"
            )
        if report_month is None:
            report_month, is_till_month = rm, till
        elif (rm, till) != (report_month, is_till_month):
            raise ValueError(
                f"Sheet '{sheet_name}' header ({rm}, till={till}) disagrees with an earlier "
                f"sheet in this workbook ({report_month}, till={is_till_month})"
            )

        total_row = _find_total_cost_row(ws)
        if total_row is None:
            raise ValueError(f"Sheet '{sheet_name}': no 'TOTAL COST' row found in column B")

        plants = {}
        for plant, block_start in zip(PLANT_ORDER, _BLOCK_START_COLS):
            if not _validate_plant_label(ws, block_start, plant):
                raise ValueError(
                    f"Sheet '{sheet_name}': expected plant '{plant}' in the column block "
                    f"starting at column {block_start}, but its row-6 label doesn't match"
                )
            plants[plant] = {
                "variable": _num(ws.cell(row=total_row, column=block_start + _VARIABLE_OFFSET).value),
                "fixed": _num(ws.cell(row=total_row, column=block_start + _FIXED_OFFSET).value),
            }
        products[key] = plants

    if not products:
        raise ValueError("No HM/CS/SS sheet found in this workbook")

    return {"report_month": report_month, "is_till_month": is_till_month, "products": products}


# ---------------------------------------------------------------------------
# BF Coke extractor — reads one "BF Coke-5ISPs-For and Upto <Mon><YY>.xlsx"
# workbook (a completely different source than the elementwise HM/CS/SS one
# above — one sheet per plant, named BSP/DSP/RSP/BSL/ISP rather than one
# sheet per product) and pulls VARIABLE + FIXED cost (Rs/T) for BOTH the
# month and the till-month (cumulative) columns in a single pass, since —
# unlike the HM/CS/SS workbook, which is either a month file or a separate
# "APRIL-<month>" till-month file — this workbook prints both blocks
# side by side on every sheet (columns ~1-6 for the month, ~7-13 for
# "Upto <Mon>"). Feeds cost_trend_monthly with product="COKE" (same table
# HM/CS/SS use; see data-entry/cost-trend's PRODUCTS list for "BF Coke").
#
# Each plant's sheet is that plant's OWN report template (not a shared one
# like HM/CS/SS's 3 identical sheets) — confirmed against a real Aug'26
# file: label column, header wording (Fixed/Variable vs VAR/FIXED vs "V
# Cost"/"F Cost"), and column order all differ plant to plant, so column
# positions are hardcoded per plant below rather than located generically.
# What's NOT hardcoded is the ROW: a plant's "TOTAL COST" line drifts as
# line items are added/removed month to month, so it's always located by
# searching for that label, never by a fixed row number.
#
# RSP and ISP additionally print SEVERAL cost blocks per sheet (RSP: WET
# 1-5/DRY 1-5/Battery 6/"DRY AVERAGE (1-5 & 6)"; ISP: OLD/NEW/Skip Coke/
# "COMBINED") — verified against the real file that the plant-level figure
# is the one block titled AVERAGE (RSP) or COMBINED (ISP): ISP's COMBINED
# production (102042.1935 t) is exactly OLD (36304.298) + NEW (65737.8955),
# confirming it's the whole-plant total, not another sub-unit. block_re
# below locates that one block by its title; if a future month's workbook
# doesn't have exactly one block matching it, extraction fails loudly
# rather than silently reading the wrong sub-unit's figures.
_BF_COKE_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]  # no SAIL row in this workbook

# plant -> (variable col, fixed col) x (month block, till-month block),
# the label column its own "TOTAL COST" row is found in, and — for a sheet
# with multiple cost blocks — the regex that names its plant-level block.
_BF_COKE_COLUMNS = {
    "BSP": dict(var_m=5, fixed_m=4, var_u=10, fixed_u=9,  label_col=1, block_re=None),
    "DSP": dict(var_m=6, fixed_m=7, var_u=11, fixed_u=12, label_col=3, block_re=None),
    "RSP": dict(var_m=7, fixed_m=8, var_u=12, fixed_u=13, label_col=2, block_re=re.compile(r"AVERAGE", re.I)),
    "BSL": dict(var_m=4, fixed_m=5, var_u=11, fixed_u=12, label_col=1, block_re=None),
    "ISP": dict(var_m=4, fixed_m=5, var_u=11, fixed_u=12, label_col=1, block_re=re.compile(r"COMBINED", re.I)),
}

_MONTHLIKE_RE = re.compile(r"([A-Za-z]{3,9})\s*'?\s*(\d{2,4})")
_HEADER_TOKEN_RE = re.compile(r"\bFIX(ED)?\b|\bVAR(IABLE)?\b", re.I)


def _find_bf_coke_month(ws):
    """Scans the sheet's top rows for the first recognizable "<Mon> <YY>"
    (or "<Mon>'<YYYY>", "UPTO <Mon>'<YY>", ...) label — row/column position
    and punctuation both vary by plant, unlike the HM/CS/SS workbook's
    fixed row 3."""
    for row in ws.iter_rows(min_row=1, max_row=10):
        for cell in row:
            v = cell.value
            if not isinstance(v, str):
                continue
            m = _MONTHLIKE_RE.search(v)
            if not m:
                continue
            mon = _MONTH_ABBR.get(m.group(1)[:3].upper())
            if not mon:
                continue
            yr = int(m.group(2))
            if yr < 100:
                yr += 2000
            return f"{yr}-{mon:02d}"
    return None


def _row_has_header_tokens(ws, row, max_col=20):
    """True if `row` itself looks like a column-header row (has a
    Fixed/Variable-ish label in it) rather than a data row — used to reject
    a false-positive "TOTAL COST" hit that's actually a column header
    reading "Total Cost" (seen on BSP's own header row) rather than a
    TOTAL COST data row."""
    for c in range(1, max_col + 1):
        v = ws.cell(row=row, column=c).value
        if isinstance(v, str) and _HEADER_TOKEN_RE.search(v):
            return True
    return False


def _dedupe_adjacent_rows(rows, gap=3):
    """Collapses total-row hits that are within `gap` rows of each other
    into one (keeping the first) — e.g. BSL prints both 'TOTAL COST' and
    'TOTAL COST AS PER COST SHEET' one row apart for the same block
    (numerically identical to rounding noise); real distinct blocks (RSP/
    ISP's sub-units) sit dozens of rows apart and are never merged by this."""
    groups = []
    for r in rows:
        if groups and r - groups[-1][-1] <= gap:
            groups[-1].append(r)
        else:
            groups.append([r])
    return [g[0] for g in groups]


def _nearest_block_title_above(ws, row, max_back=150):
    for r in range(row, max(1, row - max_back) - 1, -1):
        for c in range(1, 5):
            v = ws.cell(row=r, column=c).value
            if isinstance(v, str) and "ELEMENTWISE" in v.upper():
                return v
    return None


def _find_bf_coke_total_row(ws, cfg, sheet_name):
    """Locates the ONE 'TOTAL COST' row this plant's Fixed/Variable figures
    should be read from. Raises ValueError (rather than guessing) if the
    sheet doesn't resolve to exactly one candidate — either because it has
    no multi-block marker (cfg['block_re'] is None) but printed more than
    one TOTAL COST block, or because a multi-block sheet doesn't have
    exactly one block matching its expected AVERAGE/COMBINED title."""
    hits = []
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=cfg["label_col"]).value
        if isinstance(v, str) and "TOTAL COST" in v.upper() and not _row_has_header_tokens(ws, r):
            hits.append(r)
    groups = _dedupe_adjacent_rows(hits)

    if not groups:
        raise ValueError(f"Sheet '{sheet_name}': no 'TOTAL COST' row found in column {cfg['label_col']}")

    if cfg["block_re"] is None:
        if len(groups) != 1:
            raise ValueError(
                f"Sheet '{sheet_name}': expected exactly one TOTAL COST block, found {len(groups)} "
                f"at rows {groups} — this plant's sheet may have gained a second cost block"
            )
        return groups[0]

    matches = [r for r in groups if (t := _nearest_block_title_above(ws, r)) and cfg["block_re"].search(t)]
    if len(matches) != 1:
        titles = [_nearest_block_title_above(ws, r) for r in groups]
        raise ValueError(
            f"Sheet '{sheet_name}': expected exactly one cost block titled like "
            f"{cfg['block_re'].pattern!r} (the plant-level total), found {len(matches)} "
            f"among blocks {list(zip(groups, titles))}"
        )
    return matches[0]


def extract_bf_coke_workbook(file_path) -> dict:
    """-> {"report_month": "YYYY-MM", "product": "COKE",
           "plants": {"BSP": {"month": {"variable":.., "fixed":..},
                               "till_month": {"variable":.., "fixed":..}},
                      ..., "ISP": {...}}}  (no SAIL — not in this workbook)
    Raises ValueError on anything that doesn't match the expected layout —
    same "fail loudly" philosophy as extract_cost_trend_workbook above."""
    wb = openpyxl.load_workbook(file_path, data_only=True)

    report_month = None
    plants = {}

    for plant in _BF_COKE_PLANTS:
        if plant not in wb.sheetnames:
            continue
        cfg = _BF_COKE_COLUMNS[plant]
        ws = wb[plant]

        rm = _find_bf_coke_month(ws)
        if rm is None:
            raise ValueError(f"Sheet '{plant}': could not find a month label (e.g. \"Aug 26\", \"AUG'2026\")")
        if report_month is None:
            report_month = rm
        elif rm != report_month:
            raise ValueError(
                f"Sheet '{plant}' month ({rm}) disagrees with an earlier sheet in this workbook ({report_month})"
            )

        total_row = _find_bf_coke_total_row(ws, cfg, plant)

        cell_map = {
            ("month", "variable"): cfg["var_m"], ("month", "fixed"): cfg["fixed_m"],
            ("till_month", "variable"): cfg["var_u"], ("till_month", "fixed"): cfg["fixed_u"],
        }
        values = {"month": {}, "till_month": {}}
        for (block_key, cost_key), col in cell_map.items():
            raw = ws.cell(row=total_row, column=col).value
            num = _num(raw)
            if num is None:
                raise ValueError(
                    f"Sheet '{plant}', row {total_row}, column {col} ({block_key}/{cost_key}): "
                    f"expected a number, found {raw!r}"
                )
            values[block_key][cost_key] = num
        plants[plant] = values

    if not plants:
        raise ValueError("No BF Coke plant sheet (BSP/DSP/RSP/BSL/ISP) found in this workbook")

    return {"report_month": report_month, "product": "COKE", "plants": plants}
