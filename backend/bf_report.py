"""BF Parameters report for one financial year (/reports/excel tab
'bf-parameters'), after the format sheet "BF Report.xlsx" (its print area,
A2:JU35, without the Pellet (Kg/THM) block): each furnace with its plant's shop
row and a SAIL row, across eleven parameter sections. A section runs: past FYs, APP, the 12 months, Cum.

Static furnace data (working volume, tuyeres, CHSGP, ...) is in
bf_report_config.json. Everything else comes from the database:
  months    techno_upload / techno_value 'month'; production from
            production_monthly actual (a shop is its plant's Hot Metal)
  Cum, FYs  the latest 'till_month' value of that FY, else the monthly values
            combined by techno_cumulative's rule for the parameter
  APP       techno_plan_fy; production from production_monthly abp, FY total
  SAIL      as Techno page 27 (page_techno._bf_sail_v): a stored plant='SAIL'
            value wins, else the plant rows combined by techno_cumulative's
            rule, weighted by plant Hot Metal (productivity harmonic, HBT and
            %Si plain average; BF_SAIL_SPECS' zero-fill plants count as 0).
            SAIL APP is the stored SAIL plan, Fuel = coke + nut coke + CDI as
            on page 27; a parameter it lacks is combined from the plant plans.

A cell with no DB value is blank, not 0."""

import io
import json
import os
from datetime import date

import app_actual_trend as trend
import techno_cumulative as tc
import techno_period as tp
from page_techno import BF_SAIL_SPECS
from repo import production as rp
from repo import techno as rt

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bf_report_config.json")
_STATIC_FIELDS = ("working_volume", "tuyeres", "tap_holes", "cast_houses", "chsgp", "blt", "stoves")

# (key, heading, past FYs shown, decimals, techno keys in preference order)
SECTIONS = [
    ("production", "Production('000T)", 9, 0, ()),
    ("productivity", "Productivity-W.V.(T/m3/day)", 9, 2, ("bf_productivity",)),
    ("sinter", "Sinter in burden(%)", 9, 0, ("sinter_in_burden",)),
    ("hbt", "HBT(oC)", 9, 0, ("hot_blast_temp", "blast_temperature")),
    ("slag", "Slag Rate(Kg/THM)", 8, 0, ("slag_rate",)),
    ("coke", "Coke Rate(Kg/THM)", 8, 0, ("coke_rate",)),
    ("cdi", "CDI Rate(Kg/THM)", 8, 0, ("cdi",)),
    ("fuel", "Fuel Rate(Kg/THM)", 8, 0, ("fuel_rate",)),
    ("o2", "O2 enrichment(%)", 8, 1, ("o2_enrichment",)),
    ("si", "%[Si]", 8, 2, ("silicon_in_hm", "si_in_hm", "si%_in_hm")),
    ("pellet_pct", "Pellet(%)", 3, 0, ("pellet_in_burden",)),
]
# A narrow blank column closes these sections, as on the sheet.
_GAP_AFTER = {"production", "productivity", "sinter", "slag", "coke", "cdi", "fuel", "o2"}
_MAX_PAST = max(s[2] for s in SECTIONS)
_SAIL_UNITS = ("BF_Shop", "Shop")     # where a stored SAIL figure may sit
# Section -> its name in the stored SAIL plan (plant='SAIL', unit='Shop').
_SAIL_PLAN_NAMES = {"productivity": "BF Productivity", "sinter": "Sinter in Burden", "coke": "Coke Rate",
                    "cdi": "CDI Rate", "pellet_pct": "Pellet in Burden"}
_ZERO_FILL = {spec[0]: spec[4] for spec in BF_SAIL_SPECS.values() if spec[4]}
_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def load_config():
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _num(v):
    if isinstance(v, dict):
        v = v.get("value")
    if isinstance(v, bool) or v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sum(values):
    vals = [v for v in values if v is not None]
    return sum(vals) if vals else None


def _combine(keys, pairs):
    """(value, weight) pairs by the app's cumulative rule for the parameter."""
    method, _basis = tc.get_rule(keys[0])
    return tp._weighted_combine(method, pairs)[0]


def _pct(num, den):
    return num / den * 100 if num is not None and den else None


def _mon(m):
    return f"{_MON[int(m[5:7]) - 1]}'{m[2:4]}"


def columns(fy_start, past):
    """A section's data columns; aligned with each row's cells for it."""
    cols = [{"kind": "fy", "label": trend.fy_label(y)[2:], "fy": y}
            for y in range(fy_start - past, fy_start)]
    cols.append({"kind": "app", "label": f"APP {trend.fy_label(fy_start)[2:]}"})
    cols += [{"kind": "month", "label": _mon(m), "month": m} for m in trend.fy_months(fy_start)]
    cols.append({"kind": "cum", "label": "Cum"})
    return cols


def _app_index(cols):
    return next(i for i, c in enumerate(cols) if c["kind"] == "app")


class _Data:
    """The FY's DB figures (plus the past FYs the sheet shows)."""

    def __init__(self, cfg, fy_start):
        years = range(fy_start - _MAX_PAST, fy_start + 1)
        self.months = {y: trend.fy_months(y) for y in years}
        every = [m for y in years for m in self.months[y]]
        plants = [p["plant"] for p in cfg["plants"]]
        units = {f["unit"] for p in cfg["plants"] for f in p["furnaces"]}
        units |= {p["shop_unit"] for p in cfg["plants"] if p["shop_unit"]}
        items = {i for p in cfg["plants"] for f in p["furnaces"] for i in f["production_items"]}
        items |= {p["plan_item"] for p in cfg["plants"]}
        self.blobs = rt.blobs(every, plants + ["SAIL"], sorted(units | set(_SAIL_UNITS)))
        self.actual = rp.values(every, plants, sorted(items), "actual")
        self.abp = rp.values(self.months[fy_start], plants, sorted(items), "abp")
        label = trend.fy_label(fy_start)
        self.plans = {p: rt.get_techno_plan(p, label) for p in plants}
        self.sail_plan = rt.get_sail_techno_plan(label).get("data") or {}

    def rate(self, plant, unit, keys, month, period="month"):
        block = self.blobs.get((month, plant, unit), {}).get(period) or {}
        for k in keys:
            v = _num(block.get(k))
            if v is not None:
                return v
        return None

    def plan_rate(self, plant, unit, keys):
        data = (self.plans[plant].get(unit) or {}).get("data") or {}
        for k in keys:
            v = _num(data.get(k))
            if v is not None:
                return v
        if "fuel_rate" in keys:     # no stored Fuel plan: coke + nut coke + CDI, as page 27
            coke, cdi = _num(data.get("coke_rate")), _num(data.get("cdi"))
            if coke is not None and cdi is not None:
                return coke + (_num(data.get("nut_coke_rate")) or 0) + cdi
        return None

    def sail_stored(self, keys, month, period):
        for unit in _SAIL_UNITS:
            v = self.rate("SAIL", unit, keys, month, period)
            if v is not None:
                return v
        return None

    def sail_plan_rate(self, key):
        if key == "fuel":
            coke, cdi = _num(self.sail_plan.get("Coke Rate")), _num(self.sail_plan.get("CDI Rate"))
            if coke is None or cdi is None:
                return None
            return coke + (_num(self.sail_plan.get("Nut Coke Rate")) or 0) + cdi
        return _num(self.sail_plan.get(_SAIL_PLAN_NAMES.get(key)))

    @staticmethod
    def item(source, month, plant, items):
        for i in items:
            v = source.get((month, plant, i))
            if v is not None:
                return float(v)
        return None


class _Line:
    """A furnace or shop: its production and rates by period."""

    def __init__(self, data, plant, unit, items, furnaces=None):
        self.data, self.plant, self.unit, self.items, self.furnaces = data, plant, unit, items, furnaces

    def prod(self, month):
        v = self.data.item(self.data.actual, month, self.plant, self.items)
        if v is None and self.furnaces:     # no Hot Metal row: its furnaces
            return _sum(f.prod(month) for f in self.furnaces)
        return v

    def plan(self, month):
        return self.data.item(self.data.abp, month, self.plant, self.items)

    def prod_fy(self, year):
        return _sum(self.prod(m) for m in self.data.months[year])

    def rate(self, keys, month):
        return self.data.rate(self.plant, self.unit, keys, month)

    def rate_fy(self, keys, year):
        months = self.data.months[year]
        for m in reversed(months):
            v = self.data.rate(self.plant, self.unit, keys, m, "till_month")
            if v is not None:
                return v
        return _combine(keys, [(self.rate(keys, m), self.prod(m)) for m in months])

    def plan_rate(self, keys):
        return self.data.plan_rate(self.plant, self.unit, keys)


def _production(cols, months, prod, prod_fy, plan):
    """The production section of any row, from its three lookups."""
    cells = []
    for c in cols:
        if c["kind"] == "fy":
            cells.append(prod_fy(c["fy"]))
        elif c["kind"] == "app":
            cells.append(_sum(plan(m) for m in months))
        elif c["kind"] == "month":
            cells.append(prod(c["month"]))
        else:
            cells.append(_sum(prod(m) for m in months))
    to_date = _sum(plan(m) for m in months if prod(m) is not None)
    return {"cells": cells, "pct": _pct(cells[-1], to_date)}


def _with_pct(key, cols, cells):
    sec = {"cells": cells}
    if key == "hbt":
        sec["pct"] = _pct(cells[-1], cells[_app_index(cols)])
    return sec


def _line_cells(line, months, fy_start, sec_cols):
    out = {}
    for key, _h, _p, _d, keys in SECTIONS:
        cols = sec_cols[key]
        if key == "production":
            out[key] = _production(cols, months, line.prod, line.prod_fy, line.plan)
            continue
        cells = []
        for c in cols:
            if not keys:
                cells.append(None)
            elif c["kind"] == "fy":
                cells.append(line.rate_fy(keys, c["fy"]))
            elif c["kind"] == "app":
                cells.append(line.plan_rate(keys))
            elif c["kind"] == "month":
                cells.append(line.rate(keys, c["month"]))
            else:
                cells.append(line.rate_fy(keys, fy_start))
        out[key] = _with_pct(key, cols, cells)
    return out


def _sail_rate(lines, keys, pairs):
    """Plant (value, weight) pairs -> SAIL; zero-fill plants' blanks count as 0."""
    if all(v is None for v, _ in pairs):
        return None
    fill = _ZERO_FILL.get(keys[0]) or ()
    # A plant with no Hot Metal drops out (w = 0), as in page_techno._bf_sail.
    return _combine(keys, [(0.0 if v is None and ln.plant in fill else v, w or 0)
                           for ln, (v, w) in zip(lines, pairs)])


def _sail_fy(data, lines, keys, year):
    """A stored SAIL till-month figure of the FY, else the plants' FY values."""
    for m in reversed(data.months[year]):
        v = data.sail_stored(keys, m, "till_month")
        if v is not None:
            return v
    return _sail_rate(lines, keys, [(ln.rate_fy(keys, year), ln.prod_fy(year)) for ln in lines])


def _sail_cells(lines, data, months, fy_start, sec_cols):
    out = {}
    for key, _h, _p, _d, keys in SECTIONS:
        cols = sec_cols[key]
        if key == "production":
            out[key] = _production(cols, months,
                                   lambda m: _sum(ln.prod(m) for ln in lines),
                                   lambda y: _sum(ln.prod_fy(y) for ln in lines),
                                   lambda m: _sum(ln.plan(m) for ln in lines))
            continue
        cells = []
        for c in cols:
            if not keys:
                cells.append(None)
            elif c["kind"] == "fy":
                cells.append(_sail_fy(data, lines, keys, c["fy"]))
            elif c["kind"] == "app":
                v = data.sail_plan_rate(key)
                if v is None:
                    v = _sail_rate(lines, keys,
                                   [(ln.plan_rate(keys), _sum(ln.plan(m) for m in months)) for ln in lines])
                cells.append(v)
            elif c["kind"] == "month":
                v = data.sail_stored(keys, c["month"], "month")
                if v is None:
                    v = _sail_rate(lines, keys, [(ln.rate(keys, c["month"]), ln.prod(c["month"])) for ln in lines])
                cells.append(v)
            else:
                cells.append(_sail_fy(data, lines, keys, fy_start))
        out[key] = _with_pct(key, cols, cells)
    return out


def _has_data(sections, sec_cols):
    """Any non-zero figure in the FY: a closed furnace can still carry 0 rows."""
    return any(v for key, sec in sections.items()
               for v, c in zip(sec["cells"], sec_cols[key]) if c["kind"] in ("month", "cum"))


def build(fy_start):
    cfg = load_config()
    data = _Data(cfg, fy_start)
    months = data.months[fy_start]
    sec_cols = {s[0]: columns(fy_start, s[2]) for s in SECTIONS}
    rows, plant_lines = [], []
    for p in cfg["plants"]:
        lines = [_Line(data, p["plant"], f["unit"], f["production_items"]) for f in p["furnaces"]]
        plant_rows = []
        for f, line in zip(p["furnaces"], lines):
            sections = _line_cells(line, months, fy_start, sec_cols)
            if f["show"] or _has_data(sections, sec_cols):
                plant_rows.append({"id": f"{p['plant']}:{f['unit']}", "kind": "furnace", "plant": p["plant"], "bf": f["bf"],
                                   "static": {k: f.get(k) for k in _STATIC_FIELDS},
                                   "aux_fuel": f.get("aux_fuel"), "sections": sections})
        if p["shop_unit"]:
            shop = _Line(data, p["plant"], p["shop_unit"], [p["plan_item"]], furnaces=lines)
            plant_rows.append({"id": f"{p['plant']}:Shop", "kind": "shop", "plant": p["plant"], "bf": "Shop", "static": {},
                               "aux_fuel": p.get("shop_aux_fuel"),
                               "sections": _line_cells(shop, months, fy_start, sec_cols)})
            plant_lines.append(shop)
        else:   # no shop row: the furnace carrying the plant's Hot Metal is the plant
            plant_lines.append(next(ln for ln in lines if p["plan_item"] in ln.items))
        for i, row in enumerate(plant_rows):
            row["plant_span"] = len(plant_rows) if i == 0 else 0
        rows.extend(plant_rows)
    sail = _sail_cells(plant_lines, data, months, fy_start, sec_cols)
    rows.append({"id": "SAIL", "kind": "sail", "plant": "SAIL", "bf": "", "static": {}, "aux_fuel": None,
                 "plant_span": 1, "sections": sail})
    return {
        "title": cfg["title"], "fy": fy_start, "fy_label": trend.fy_label(fy_start),
        "sections": [{"key": k, "label": h, "decimals": d, "columns": sec_cols[k],
                      "pct_label": {"production": "%ful APP", "hbt": "% efficiency"}.get(k),
                      "aux": k == "cdi", "gap": k in _GAP_AFTER} for k, h, _p, d, _k in SECTIONS],
        "rows": rows,
        "has_plan": any(sec["cells"][_app_index(sec_cols[key])] is not None for key, sec in sail.items()),
    }


def narrow(rep, hide_rows=(), hide_fys=(), hide_months=(), sections=()):
    """The report without the chosen rows (ids), past FYs (start years) and
    calendar months ('04'), limited to `sections` (keys) if any are given, for
    the Excel download of what the page shows. APP and Cum stay; every figure
    keeps its value, so a shop or SAIL row still covers a hidden furnace and
    Cum still covers a hidden month."""
    hide_rows, hide_fys, hide_months = set(hide_rows), set(hide_fys), set(hide_months)
    wanted = set(sections)

    def keep(c):
        return not ((c["kind"] == "fy" and c["fy"] in hide_fys)
                    or (c["kind"] == "month" and c["month"][5:7] in hide_months))

    secs = [s for s in rep["sections"] if not wanted or s["key"] in wanted]
    out_rows, spans = [], {}
    for row in rep["rows"]:
        if row["id"] in hide_rows:
            continue
        out = dict(row, sections={})
        for s in secs:
            sec = row["sections"][s["key"]]
            cells = [v for c, v in zip(s["columns"], sec["cells"]) if keep(c)]
            out["sections"][s["key"]] = dict(sec, cells=cells)
        spans[row["plant"]] = spans.get(row["plant"], 0) + 1
        out_rows.append(out)
    seen = set()
    for row in out_rows:
        row["plant_span"] = 0 if row["plant"] in seen else spans[row["plant"]]
        seen.add(row["plant"])
    return dict(rep, rows=out_rows,
                sections=[dict(s, columns=[c for c in s["columns"] if keep(c)]) for s in secs])


def available_fys():
    """FY start years with any techno data, newest first."""
    return sorted({int(m[:4]) - (int(m[5:7]) < 4) for m in rt.get_techno_months() if m}, reverse=True)


def filename(rep, ext):
    return f"BF_Report_{rep['fy_label']}.{ext}"


# ── Excel, in the format sheet's layout ──────────────────────────────────────
_APP_BG, _CUM_BG, _TOTAL_BG = "E5E5FF", "CCECFF", "DCE6F1"
_FONT = "Arial Narrow"
_STATIC_HEADS = [("W/V", "(M3)"), ("No. of", "tuyeres"), ("No. of tap", "Holes"), ("No. of cast", "houses"),
                 ("CHSGP", "(Y/N)"), ("BLT", "(Y/N)"), ("No. of", "Stoves")]
_STATIC_WIDTHS = [9.9, 12.1, 9.1, 14.4, 18.4, 18.7, 15.6, 10.6, 13.7]
_FIRST_DATA_ROW = 8
_TITLE_EVERY = 2    # one merged title over each pair of sections, as on the sheet


def build_xlsx(rep):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter as col_letter

    thin, medium = Side(style="thin"), Side(style="medium")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    wb = Workbook()
    ws = wb.active
    ws.title = rep["fy_label"][2:]
    ws.sheet_view.zoomScale = 40

    def put(r, c, value, *, size=30, bold=False, bg=None, fmt=None, left=thin, top=None, bottom=None):
        cell = ws.cell(r, c, value)
        cell.font = Font(name=_FONT, size=size, bold=bold)
        cell.alignment = center
        cell.border = Border(left=left, top=top, bottom=bottom)
        if bg:
            cell.fill = PatternFill("solid", fgColor=bg)
        if fmt:
            cell.number_format = fmt
        return cell

    def head(c, value, width, **kw):
        """A heading over rows 6-7."""
        put(6, c, value, top=medium, **kw)
        put(7, c, None, bottom=medium, **{k: v for k, v in kw.items() if k in ("bg", "left")})
        ws.merge_cells(start_row=6, start_column=c, end_row=7, end_column=c)
        ws.column_dimensions[col_letter(c)].width = width

    # Static headings
    for c, label in ((1, "Plant"), (2, "BF#")):
        head(c, label, _STATIC_WIDTHS[c - 1], size=24, bold=True, left=medium)
    for i, (a, b) in enumerate(_STATIC_HEADS):
        put(6, 3 + i, a, size=24, bold=True, left=medium, top=medium)
        put(7, 3 + i, b, size=24, bold=True, left=medium, bottom=medium)
        ws.column_dimensions[col_letter(3 + i)].width = _STATIC_WIDTHS[2 + i]

    # Section headings
    col = len(_STATIC_WIDTHS) + 1
    layout = []     # per section: (first column, first cell column, % column)
    for sec in rep["sections"]:
        first = col
        if sec["aux"]:
            head(col, "Auxiliary\nFuel", 16, size=24, bold=True, left=medium)
            col += 1
        data_col = col
        for c in sec["columns"]:
            kind = c["kind"]
            value, fmt, size, bold, bg = c["label"], None, 24, False, None
            if kind == "app":
                value, bg = f" APP\n{c['label'].split(' ')[1]}", _APP_BG
            elif kind == "month":
                value, fmt, size, bold = date(int(c["month"][:4]), int(c["month"][5:7]), 1), "mmm\\'yy", 20, True
            elif kind == "cum":
                bg, bold = _CUM_BG, True
            head(col, value, 15, size=size, bold=bold, bg=bg, fmt=fmt, left=medium if col == first else thin)
            col += 1
        pct_col = None
        if sec["pct_label"]:
            pct_col = col
            bg = _TOTAL_BG if sec["key"] == "production" else _CUM_BG
            head(col, sec["pct_label"].replace(" ", " \n", 1), 16, size=24, bold=True, bg=bg)
            col += 1
        if sec["gap"]:
            ws.column_dimensions[col_letter(col)].width = 3
            col += 1
        put(5, first, sec["label"], bold=True, left=medium, top=medium)
        ws.merge_cells(start_row=5, start_column=first, end_row=5, end_column=col - 1)
        layout.append((first, data_col, pct_col))
    last_col = col - 1

    for i in range(0, len(layout), _TITLE_EVERY):
        start = layout[i][0] if i else 1
        end = layout[i + _TITLE_EVERY][0] - 1 if i + _TITLE_EVERY < len(layout) else last_col
        put(3, start, rep["title"], size=36, bold=True, left=None)
        ws.merge_cells(start_row=3, start_column=start, end_row=3, end_column=end)

    # Rows
    r = _FIRST_DATA_ROW
    for row in rep["rows"]:
        kind = row["kind"]
        total = kind != "furnace"
        bg = _TOTAL_BG if kind == "sail" else None
        top = medium if row["plant_span"] else (thin if kind == "shop" else None)
        ws.row_dimensions[r].height = {"furnace": 50.1, "shop": 98.25, "sail": 64.5}[kind]
        if row["plant_span"]:
            put(r, 1, row["plant"], size=22 if kind == "sail" else 48, bold=True, bg=bg, left=medium, top=top)
            if kind != "sail" and row["plant_span"] > 1:
                ws.merge_cells(start_row=r, start_column=1, end_row=r + row["plant_span"] - 1, end_column=1)
        if kind == "sail":
            put(r, 2, None, bg=bg, top=top)
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        else:
            put(r, 2, row["bf"], size=24, bold=total, left=medium, top=top)
        for i, field in enumerate(_STATIC_FIELDS):
            put(r, 3 + i, row["static"].get(field), size=20 if i == 0 else 24, bold=total, bg=bg,
                left=medium, top=top)
        for sec, (first, data_col, pct_col) in zip(rep["sections"], layout):
            fmt = "0" if sec["decimals"] == 0 else "0." + "0" * sec["decimals"]
            values = row["sections"][sec["key"]]
            if sec["aux"]:
                put(r, first, row["aux_fuel"], size=28, bold=total, bg=bg, left=medium, top=top)
            for j, (c, v) in enumerate(zip(sec["columns"], values["cells"])):
                cell_bg = bg or {"app": _APP_BG, "cum": _CUM_BG}.get(c["kind"])
                left = medium if data_col + j == first else thin
                put(r, data_col + j, v, bold=total or c["kind"] == "cum", bg=cell_bg, fmt=fmt, left=left, top=top)
            if pct_col:
                cell_bg = bg or (_TOTAL_BG if sec["key"] == "production" else _CUM_BG)
                put(r, pct_col, values.get("pct"), bold=kind == "sail" or sec["key"] == "hbt", bg=cell_bg,
                    fmt="0", top=top)
        r += 1
    last_row = r - 1
    for c in range(1, last_col + 1):    # close the table
        cell = ws.cell(last_row, c)
        cell.border = Border(left=cell.border.left, top=cell.border.top, bottom=medium)

    ws.freeze_panes = ws.cell(_FIRST_DATA_ROW, 4)
    ws.row_dimensions[4].height = 0.75
    ws.row_dimensions[5].height = ws.row_dimensions[6].height = 50.1
    ws.row_dimensions[7].height = 29.25
    ws.print_area = f"A2:{col_letter(last_col)}{last_row}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
