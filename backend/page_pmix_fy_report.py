"""
SAIL Pmix FY report — Report_format/pmix.xlsx format ("Pmix'26-27 ACT" sheet):
year-wise, month-wise Product Mix Performance for a selected financial year
(Apr-Mar), with 4 quarterly sum columns and a full-year cumulative column.

Product-mix rows come from this module's own compute_pmix_fy_rows() (called
once per FY month): plant blocks, SAIL rollup, Finished Steel / ASP / SSP /
VISL / Totals section. The mapping is this report's own, not the JPC
report's; only page_jpc_report's small lookup helpers are shared.

Four extra rows beyond compute_pmix_fy_rows(), specific to this template:
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
from datetime import date

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

import db
from constants import FIVE_PLANTS as _5P
from page_jpc_report import _one, _one_of, _sum, _fs, _sub, _mou_value

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


def _avg_opt(vals):
    nums = [v for v in vals if v is not None]
    return round(sum(nums) / len(nums), 3) if nums else None


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


def _plant_hdr(ws, row, label, start_col, end_col):
    for col in range(start_col, end_col + 1):
        ws.cell(row=row, column=col).fill = _PLANT_FILL
        ws.cell(row=row, column=col).border = _BORDER
    ws.cell(row=row, column=start_col, value=label).font = _PLANT_FONT


# ── Product-mix rows ("Pmix'yy-yy ACT" sheet) ──────────────────────────────
# This report's own item mapping — kept separate from page_jpc_report.py's
# Pmix sheet so either can change without moving the other; only the small
# lookup helpers (_one, _one_of, _sum, _fs, _sub) are shared.

# Per-plant mill breakdown. Each entry: (label, plant, item_name_or_None).
# item_name=None → left blank: either confirmed not tracked anywhere in this
# app's DB (checked against page_catwise_saleable.py's item catalog + a live
# query, not just a label grep), or a row Report_format/work/Pmix.xlsx's own
# template keeps as a permanent blank placeholder (e.g. BSP's "BBM blooms"/
# "BBM/billets", DSP's CC Blooms/SPU rows) — will be filled in once a source
# is extracted, for the ones that aren't placeholders.
_BSP_ITEMS = [
    ("WRM",                   "BSP", "WIRERODS"),
    ("TMT coils(WRM)",        "BSP", "TMT COILS(WRM)"),
    ("Others (WRM)",          "BSP", "OTHERS(WRM)"),
    ("TMT Bars (MM)",         "BSP", "TMT BARS(MM)"),
    ("Lt Strls (MM)",         "BSP", "LT STRS(MM)"),
    ("Rounds & Bars (BRM)",   "BSP", "BARS&RODMILL"),
    ("Rail (RSM)",            "BSP", "RSM_RAIL"),
    ("Rail (URM)",            "BSP", "URM_RAIL"),
    ("Hy.Struls.",            "BSP", None),
    ("Plates",                "BSP", "PLATEMILL"),
    ("BBM Blooms",            "BSP", None),   # permanent blank placeholder — see note above
    ("BBM Billets",           "BSP", None),   # permanent blank placeholder — see note above
    # CC BILLET/BLOOM/SLAB (direct-extractor naming) vs SEMIS BilletS/BLOOM/
    # SLABS (the name main.py's normalize_item_name folds BSP's semis-
    # breakdown onto for anything saved via the confirm-extraction path) —
    # see the chat response this came from. Check both so a month isn't
    # blank just because its upload went through confirm-extraction.
    ("CC Billets",            "BSP", ("CC BILLET", "SEMIS BilletS")),
    ("CC bloom",              "BSP", ("CC BLOOM", "SEMIS BLOOM")),
    ("CC slab",               "BSP", ("CC SLAB", "SEMIS SLABS")),
    ("Semis Total",           "BSP", "Saleable Semis"),
    ("Saleable Steel",        "BSP", "Saleable Steel"),
]
_DSP_ITEMS = [
    ("Med Structurals (SM)",  "DSP", "SM"),   # Section Mill — see page_segment_wise.py's Med.Structurals = MSM+SM
    ("Med Structurals (MSM)", "DSP", "MSM"),
    ("Round & bars (MM)",     "DSP", "MM"),
    ("Wheel & Axle",          "DSP", "WAP"),
    ("CC Blooms",             "DSP", None),   # permanent blank placeholder — see note above
    ("CC Blooms from New BRC","DSP", None),   # permanent blank placeholder — see note above
    ("CC Billets",            "DSP", None),   # permanent blank placeholder — see note above
    ("SPU Kandrori",          "DSP", None),   # permanent blank placeholder — see note above
    ("SPU Jagdishpur",        "DSP", None),   # permanent blank placeholder — see note above
    ("Semis Total",           "DSP", "Saleable Semis"),
    ("Saleable steel",        "DSP", "Saleable Steel"),
]
_RSP_ITEMS = [
    ("Plate (PM)",            "RSP", "OPM Plate"),
    ("New Plate Mill",        "RSP", "NPM Plate"),
    ("HR Plates",             "RSP", None),
    ("HR Coils",              "RSP", None),
    ("New HR Plate",          "RSP", "HSM-2 HR Plate"),
    ("New HR Coils",          "RSP", "HSM-2 HR Coil (Sale)"),
    ("GP/GC Sheets",          "RSP", None),
    ("CRNO",                  "RSP", "CRNO Coils"),
    ("ERW Pipes",             "RSP", "ERW Pipes"),
    ("SW Pipes",              "RSP", "SW Pipes"),
    ("Semis",                 "RSP", None),
    ("Saleable Steel",        "RSP", "Saleable Steel"),
]
_BSL_ITEMS = [
    # The extractor stores chequered plate / chequered coil apart from HSM
    # HR Plate / HSM HR Coil (Sale); this sheet reports each pair together
    # (a list = summed).
    ("HR Plates",             "BSL", ["HSM HR Plate", "Checkered plate"]),
    ("HR Coils",              "BSL", ["HSM HR Coil (Sale)", "Checkered Coil"]),
    ("HR Sheets",             "BSL", "HR Sheet"),
    ("CR Coils (old)",        "BSL", "CR I/II CR(Coil) Sale"),
    ("CR Coils (new)",        "BSL", "CR III CR(Coil) Sale"),
    ("CR Sheet (old)",        "BSL", "CR Sheets"),
    ("CR Sheet (new)",        "BSL", "New CR Sheet"),
    ("GP/GC (old)",           "BSL", "GP/GC"),
    ("GP/GC (new)",           "BSL", "GPC3"),
    ("Thick plate",           "BSL", "Thick Plate"),
    ("Semis",                 "BSL", "Saleable Semis"),
    ("Saleable Steel",        "BSL", "Saleable Steel"),
]
_ISP_ITEMS = [
    ("Round & Bars(Bar Mill)","ISP", "BARMILL"),
    ("Hy Structurals(USM)",   "ISP", "USMILL"),
    ("Wire Rod TMT Coiles",   "ISP", None),   # DB has only one combined WRM figure
    ("Wire Rod Coils",        "ISP", "WRMILL"),
    ("WRM",                   "ISP", "WRMILL"),
    # Both have real, non-zero figures in Pmix.xlsx's own sample but aren't
    # sourced from anywhere in this app's DB yet — a genuine data gap, not
    # touched here (flagged, not fixed — see the chat response this came from).
    ("CC Blooms (150X150)",   "ISP", None),
    ("CC Blooms (200x280)",   "ISP", None),
    ("Semis",                 "ISP", "Saleable Semis"),
    ("Saleable Steel",        "ISP", "Saleable Steel"),
]
_PLANT_BLOCKS = [
    ("BSP", _BSP_ITEMS), ("DSP", _DSP_ITEMS), ("RSP", _RSP_ITEMS),
    ("BSL", _BSL_ITEMS), ("ISP", _ISP_ITEMS),
]

# SAIL-wide rollup — sum of the specific plant/item combos that make up each
# product category (cross-checked against the sample file's actual numbers;
# combos not present anywhere in the DB are simply left out of the sum, so
# these totals may run lower than a manually-compiled report until every
# plant's mill split is fully extracted).
_SAIL_ROLLUP = [
    ("Semis",             [("BSP", "Saleable Semis"), ("DSP", "Saleable Semis"),
                            ("BSL", "Saleable Semis"), ("ISP", "Saleable Semis")]),
    ("Wire Rods",         [("BSP", "WIRERODS"), ("ISP", "WRMILL")]),
    ("Round & Bars",      [("BSP", "TMT BARS(MM)"), ("BSP", "BARS&RODMILL"),
                            ("DSP", "MM"), ("ISP", "BARMILL")]),
    ("Lt. Structurals",   [("BSP", "LT STRS(MM)")]),
    ("Med. Structurals",  [("DSP", "MSM"), ("DSP", "SM")]),
    ("Hy. Structurals",   [("ISP", "USMILL")]),
    ("Rail",              [("BSP", "RSM_RAIL"), ("BSP", "URM_RAIL")]),
    ("Wheel & Axle",      [("DSP", "WAP")]),
    ("Plate",             [("BSP", "PLATEMILL"), ("RSP", "OPM Plate"), ("RSP", "NPM Plate")]),
    ("Thick plate",       [("BSL", "Thick Plate")]),
    ("HR Plates",         [("RSP", "HSM-2 HR Plate"), ("BSL", "HSM HR Plate"),
                            ("BSL", "Checkered plate")]),
    ("HR Sheets",         [("BSL", "HR Sheet")]),
    ("HR Coils/Skelp",    [("RSP", "HSM-2 HR Coil (Sale)"), ("BSL", "HSM HR Coil (Sale)"),
                            ("BSL", "Checkered Coil")]),
    ("CR Coils/Sheets",   [("BSL", "CR I/II CR(Coil) Sale"), ("BSL", "CR III CR(Coil) Sale"),
                            ("BSL", "CR Sheets"), ("BSL", "New CR Sheet")]),
    ("GP/GC",             [("BSL", "GP/GC"), ("BSL", "GPC3")]),
    ("CRNO",              [("RSP", "CRNO Coils")]),
    ("ERW pipes",         [("RSP", "ERW Pipes")]),
    ("SW Pipes",          [("RSP", "SW Pipes")]),
]

_FS_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]


def compute_pmix_fy_rows(cur, month, table="production_table"):
    """One month's worth of rows for this report's "Pmix'yy-yy ACT" sheet,
    in display order (called once per FY month, then grouped into
    quarters/cumulative). Mapped here, independently of the JPC report's
    Pmix sheet, though the rows currently match it. table=
    "production_plan_table" gives the same rows from the ABP (the Board
    Note's Annexure-V uses both). Each row:
        {"kind": "header"|"data", "label": str, "value": float|None, "bold": bool}
    """
    rows = []

    def header(label):
        rows.append({"kind": "header", "label": label, "value": None, "bold": False})

    def data(label, value, bold=False):
        rows.append({"kind": "data", "label": label, "value": value, "bold": bold})

    for plant, items in _PLANT_BLOCKS:
        header(plant)
        for label, plant_code, item in items:
            if isinstance(item, list):
                value = _sum(cur, [(plant_code, i) for i in item], month, table)
            elif isinstance(item, tuple):
                value = _one_of(cur, plant_code, item, month, table)
            else:
                value = _one(cur, plant_code, item, month, table)
            data(label, value, bold=label.lower().startswith("saleable"))

    header("SAIL")
    for label, combos in _SAIL_ROLLUP:
        data(label, _sum(cur, combos, month, table))
    sail_5pl_combo = [(p, "Saleable Steel") for p in _FS_PLANTS]
    data("Saleable steel 5 PL", _sum(cur, sail_5pl_combo, month, table), bold=True)

    header("Finished Steel")
    fs_vals = {}
    for plant in _FS_PLANTS:
        fs_vals[plant] = _one(cur, plant, "Finished Steel", month, table)
        data(plant, fs_vals[plant])
    fs5 = _sum(cur, [(p, "Finished Steel") for p in _FS_PLANTS], month, table)
    data("Finished Steel 5PL", fs5, bold=True)

    # ASP
    asp_sal = _one(cur, "ASP", "Saleable Steel", month, table)
    asp_fin = _fs(cur, "ASP", month, table)
    data("ASP (Total)", asp_sal, bold=True)
    data("ASP (Finished)", asp_fin)
    data("ASP (Semis)", _sub(asp_sal, asp_fin))

    # SSP — HRCS = Carbon Steel Production; Stainless = Saleable - Carbon
    ssp_sal = _one(cur, "SSP", "Saleable Steel", month, table)
    ssp_carb = _one(cur, "SSP", "Carbon Steel Production", month, table)
    data("SSP (Finished Carbon Steel)", ssp_carb)
    data("SSP (Finished Stainless Steel)", _sub(ssp_sal, ssp_carb))

    # VISL
    visl = _fs(cur, "VISL", month, table)
    data("VISL(Finished)", visl)

    sail_set = _FS_PLANTS + ["ASP", "SSP", "VISL"]
    fst = _sum(cur, [(p, "Finished Steel") for p in _FS_PLANTS], month, table)
    fst = (fst or 0) + (asp_fin or 0) + (ssp_sal or 0) + (visl or 0)
    data("Finished Steel (Total)", fst, bold=True)

    sal = _sum(cur, [(p, "Saleable Steel") for p in sail_set], month, table)
    data("Semis Total", _sub(sal, fst))
    data("Saleable Steel (Total)", sal, bold=True)

    return rows


# ── Sheet 1: "ACT <FY>" — plant-wise monthwise production summary,
# matching Report_format/PMix26-27.xlsx's "ACT 26-27" sheet ────────────────

# (label, db_item, plant_rows) — plant_rows uses "5 Plants" as the
# aggregate-row key (resolved to "SAIL - 5PL" for display) so _mou_value()
# from page_jpc_report.py (already built for the MoU report sheet) can be
# reused as-is: same rollup rules (Hot Metal/Pig Iron pull in VISL only;
# Crude Steel/Saleable Steel/Finished Steel also pull in ASP/SSP/VISL).
_ACT_ROWS_5PL_ONLY = _5P + ["5 Plants"]
_ACT_ROWS_FULL = _5P + ["5 Plants", "ASP", "SSP", "VISL", "SAIL"]
_ACT_ROWS_HM_PI = _5P + ["5 Plants", "VISL", "SAIL"]

_ACT_ITEMS = [
    ("Oven Pushing\n(nos./day)", "Oven Pushing (nos/day)", _ACT_ROWS_5PL_ONLY, True),
    ("Sinter",                   "Total Sinter",            _ACT_ROWS_5PL_ONLY, False),
    ("Hot Metal",                "Hot Metal",               _ACT_ROWS_HM_PI,    False),
    ("Crude Steel",              "Total Crude Steel",       _ACT_ROWS_FULL,     False),
    ("Pig Iron",                 "Pig Iron",                _ACT_ROWS_HM_PI,    False),
    ("Saleable Steel",           "Saleable Steel",          _ACT_ROWS_FULL,     False),
    ("Saleable Production",      None,                      _ACT_ROWS_FULL,     False),   # = Saleable Steel + Pig Iron
    ("Finished Steel Production","Finished Steel",          _ACT_ROWS_FULL,     False),
]

_ACT_PLANT_LABEL = {"5 Plants": "SAIL - 5PL"}


def _act_plant_value(cur, label, db_item, plant, month):
    if label.startswith("Oven Pushing"):
        # Two raw spellings exist across plants/months ("Oven Pushing (nos/day)"
        # vs "Oven Pushing(nos/d)") — production_table isn't normalized at the
        # row level, only main.py's /api/production-fy query normalizes it.
        if plant == "5 Plants":
            # Summed across plants (a combined ovens/day figure for the same
            # month is meaningful), unlike the quarter/cum columns below
            # which average a single row's own rate across months.
            total, found = 0.0, False
            for p in _5P:
                v = _one_of(cur, p, ["Oven Pushing (nos/day)", "Oven Pushing(nos/d)"], month)
                if v is not None:
                    total += v
                    found = True
            return round(total, 3) if found else None
        return _one_of(cur, plant, ["Oven Pushing (nos/day)", "Oven Pushing(nos/d)"], month)
    if db_item is None:   # Saleable Production = Saleable Steel + Pig Iron
        ss = _mou_value(cur, "Saleable Steel", plant, month)
        pi = _mou_value(cur, "Pig Iron", plant, month)
        if ss is None and pi is None:
            return None
        return round((ss or 0) + (pi or 0), 3)
    return _mou_value(cur, db_item, plant, month)


def build_act_fy_sheet(ws, cur, fy_start: int, months: list):
    fy_label = f"{fy_start}-{str(fy_start + 1)[2:]}"
    n_cols = 2 + 12 + 4 + 1   # item + plant + 12 months + 4 quarters + cum

    ws.cell(row=1, column=1, value="Operations Directorate").font = Font(size=10)
    ws.cell(row=2, column=1, value=f"Actual Monthwise Production: {fy_label}").font = _TITLE_FONT
    ws.cell(row=2, column=n_cols, value="Unit: '000 T (rates: nos/day)").font = _UNIT_FONT

    header_row = 3
    for col, text in ((1, "Items"), (2, "Plant")):
        c = ws.cell(row=header_row, column=col, value=text)
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
    for i, m in enumerate(months, start=3):
        c = ws.cell(row=header_row, column=i, value=_mlabel(m))
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal="center")
    for i, label in enumerate(_QTR_LABELS, start=15):
        c = ws.cell(row=header_row, column=i, value=label)
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal="center")
    c = ws.cell(row=header_row, column=19, value=f"{fy_label}\nCum")
    c.font = _HDR_FONT
    c.fill = _HDR_FILL
    c.alignment = Alignment(horizontal="center", wrap_text=True)

    row = header_row + 1
    for item_label, db_item, plant_rows, is_rate in _ACT_ITEMS:
        first = True
        for plant in plant_rows:
            display_plant = _ACT_PLANT_LABEL.get(plant, plant)
            vals = [_act_plant_value(cur, item_label, db_item, plant, m) for m in months]
            _label_cell(ws, row, 1, item_label if first else "")
            _label_cell(ws, row, 2, display_plant, bold=(plant in ("5 Plants", "SAIL")))
            for i, v in enumerate(vals, start=3):
                _num_cell(ws, row, i, v, bold=(plant in ("5 Plants", "SAIL")))
            quarters = [vals[0:3], vals[3:6], vals[6:9], vals[9:12]]
            agg = _avg_opt if is_rate else _sum_opt
            q_aggs = [agg(q) for q in quarters]
            for i, qa in enumerate(q_aggs, start=15):
                _num_cell(ws, row, i, qa, bold=(plant in ("5 Plants", "SAIL")))
            cum = _avg_opt(vals) if is_rate else _sum_opt(q_aggs)
            _num_cell(ws, row, 19, cum, bold=(plant in ("5 Plants", "SAIL")))
            row += 1
            first = False

    # Conversion / SAIL incl. conversion — SAIL-level only, appended after
    # the Finished Steel Production block (matches the sample's layout).
    conversion_vals = [_one(cur, "SAIL", "Conversion", m) for m in months]
    fs_sail_vals = [_mou_value(cur, "Finished Steel", "SAIL", m) for m in months]
    inc_conv_vals = [
        None if (fs is None and cv is None) else round((fs or 0) + (cv or 0), 3)
        for fs, cv in zip(fs_sail_vals, conversion_vals)
    ]
    for label, vals, bold in (("Conversion", conversion_vals, False),
                              ("SAIL inc. conversion", inc_conv_vals, True)):
        _label_cell(ws, row, 1, "")
        _label_cell(ws, row, 2, label, bold=bold)
        for i, v in enumerate(vals, start=3):
            _num_cell(ws, row, i, v, bold=bold)
        quarters = [vals[0:3], vals[3:6], vals[6:9], vals[9:12]]
        q_sums = [_sum_opt(q) for q in quarters]
        for i, qs in enumerate(q_sums, start=15):
            _num_cell(ws, row, i, qs, bold=bold)
        _num_cell(ws, row, 19, _sum_opt(q_sums), bold=bold)
        row += 1

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 12
    for i in range(3, n_cols + 1):
        ws.column_dimensions[get_column_letter(i)].width = 10
    ws.freeze_panes = "C4"


def build_pmix_fy_workbook(fy_start: int):
    fy_label = f"{fy_start}-{str(fy_start + 1)[2:]}"
    months = _fy_months(fy_start)

    conn = db.connect()
    cur = conn.cursor()
    try:
        rows_by_month = {m: compute_pmix_fy_rows(cur, m) for m in months}
        conversion = {m: _one(cur, "SAIL", "Conversion", m) for m in months}
        rsp_hsm2 = {m: _one(cur, "RSP", "HSM-2 Total HR Coil", m) for m in months}
        bsl_hsm = {m: _one(cur, "BSL", "HSM Total HR Coil", m) for m in months}

        wb = openpyxl.Workbook()
        ws_act = wb.active
        ws_act.title = f"ACT {fy_label}"
        build_act_fy_sheet(ws_act, cur, fy_start, months)
    finally:
        conn.close()

    n_rows = len(rows_by_month[months[0]])
    fst_by_month = {}
    for m in months:
        fst_row = next((r for r in rows_by_month[m] if r["label"] == "Finished Steel (Total)"), None)
        fst_by_month[m] = fst_row["value"] if fst_row else None

    ws = wb.create_sheet(f"Pmix'{fy_label[2:]} ACT")

    # Column layout matches Report_format/work/Pmix.xlsx exactly: that
    # template leaves columns A/B unused, starts labels at C, months at D,
    # quarters at P, Cum at T — so this does too, rather than starting at A.
    LABEL_COL, MONTH_START, QTR_START, CUM_COL = 3, 4, 16, 20

    ws.cell(row=1, column=LABEL_COL, value="Operations Directorate").font = Font(size=10)
    ws.cell(row=2, column=LABEL_COL, value=f"Product mix Performance: {fy_label}").font = _TITLE_FONT
    ws.cell(row=2, column=CUM_COL, value="Unit: '000 T").font = _UNIT_FONT

    header_row = 3
    ws.cell(row=header_row, column=LABEL_COL).fill = _HDR_FILL
    for i, m in enumerate(months, start=MONTH_START):
        y, mo = int(m[:4]), int(m[5:7])
        c = ws.cell(row=header_row, column=i, value=date(y, mo, 1))
        c.number_format = "mmm\\'yy"   # matches the sample's own month header format exactly
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal="center")
    for i, label in enumerate(_QTR_LABELS, start=QTR_START):
        c = ws.cell(row=header_row, column=i, value=label)
        c.font = _HDR_FONT
        c.fill = _HDR_FILL
        c.alignment = Alignment(horizontal="center")
    c = ws.cell(row=header_row, column=CUM_COL, value="Cum")
    c.font = _HDR_FONT
    c.fill = _HDR_FILL
    c.alignment = Alignment(horizontal="center")

    def write_data_row(label, values_by_month, bold=False):
        nonlocal row
        _label_cell(ws, row, LABEL_COL, label, bold=bold)
        vals = [values_by_month.get(m) for m in months]
        for i, v in enumerate(vals, start=MONTH_START):
            _num_cell(ws, row, i, v, bold=bold)
        quarters = [vals[0:3], vals[3:6], vals[6:9], vals[9:12]]
        q_sums = [_sum_opt(q) for q in quarters]
        for i, qs in enumerate(q_sums, start=QTR_START):
            _num_cell(ws, row, i, qs, bold=bold)
        _num_cell(ws, row, CUM_COL, _sum_opt(q_sums), bold=bold)
        row += 1

    row = header_row + 1
    for row_idx in range(n_rows):
        spec = rows_by_month[months[0]][row_idx]
        if spec["kind"] == "header":
            _plant_hdr(ws, row, spec["label"], LABEL_COL, CUM_COL)
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

    ws.column_dimensions[get_column_letter(LABEL_COL)].width = 30
    for i in range(MONTH_START, CUM_COL + 1):
        ws.column_dimensions[get_column_letter(i)].width = 10
    ws.freeze_panes = f"{get_column_letter(MONTH_START)}{header_row + 1}"

    return wb


def build_pmix_fy_report_bytes(fy_start: int) -> bytes:
    wb = build_pmix_fy_workbook(fy_start)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
