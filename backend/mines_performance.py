"""
Mines Production Performance -- a standalone report laid out like the
monthly report's pages 5-6 (Plant Wise Item Wise Production), with mines in
place of plants. Not part of the monthly PDF yet (some coal/flux figures are
only kept at SAIL level today). See
docs/superpowers/specs/2026-10-17-mines-production-performance-design.md.

generate(month) -> {"labels", "pct_idx", "blocks"}: one block per mine, per
group (JGoM/OGoM/CGoM) and for SAIL. Every row carries 11 unrounded values:
    0 FY Plan | 1 Plan  2 Actual  3 %Ful  4 CPLY Act.  5 %Gr    (month)
              | 6 Plan  7 Actual  8 %Ful  9 CPLY Act. 10 %Gr    (Apr-to-month)
Every total is a live sum of its parts -- nothing stored is a total.

A "series" is {report_month: (actual, plan)}; rows are built by combining
series and then deriving the 11 values, so totals' percentages come from
the summed quantities, never from averaging percentages.
"""
import db

PCT_IDX = (3, 5, 8, 10)

_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def periods(month: str) -> dict:
    y, m = int(month[:4]), int(month[5:7])
    fy = y if m >= 4 else y - 1
    fy_months = [f"{fy}-{k:02d}" for k in range(4, 13)] + [f"{fy + 1}-{k:02d}" for k in range(1, 4)]
    ytd = [mo for mo in fy_months if mo <= month]

    def prev(mo):
        return f"{int(mo[:4]) - 1}{mo[4:]}"

    return {"fy": fy_months, "month": month, "cply": prev(month),
            "ytd": ytd, "cply_ytd": [prev(mo) for mo in ytd]}


def labels(month: str) -> dict:
    y, m = int(month[:4]), int(month[5:7])
    fy = y if m >= 4 else y - 1
    sy, py = f"{y % 100:02d}", f"{(y - 1) % 100:02d}"
    return {
        "title": f"Mines Production Performance :{_MON[m]}'{sy} and Apr-{_MON[m]}'{sy}",
        "fy": f"{fy % 100:02d}-{(fy + 1) % 100:02d}",
        "month": f"{_MON[m]}'{sy}",
        "cply": f"{_MON[m]}'{py}",
        "ytd": f"Apr-{_MON[m]}'{sy}",
        "ytd_cply": f"Apr-{_MON[m]}'{py}",
    }


def _sum(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def combine(series_list) -> dict:
    out = {}
    for s in series_list:
        for mo, (a, p) in s.items():
            oa, op = out.get(mo, (None, None))
            out[mo] = (_sum([oa, a]), _sum([op, p]))
    return out


def _ratio(n, d):
    # n * 100 / d (not n / d * 100): 90 / 200 * 100 is 45.00000000000001
    return None if n is None or not d else n * 100 / d


def _growth(a, c):
    return None if a is None or not c else (a - c) * 100 / c


def values(series: dict, P: dict) -> list:
    def act(mo):
        return series.get(mo, (None, None))[0]

    def plan(mo):
        return series.get(mo, (None, None))[1]

    m_plan, m_act, m_cply = plan(P["month"]), act(P["month"]), act(P["cply"])
    y_plan = _sum(plan(mo) for mo in P["ytd"])
    y_act = _sum(act(mo) for mo in P["ytd"])
    y_cply = _sum(act(mo) for mo in P["cply_ytd"])
    return [_sum(plan(mo) for mo in P["fy"]),
            m_plan, m_act, _ratio(m_act, m_plan), m_cply, _growth(m_act, m_cply),
            y_plan, y_act, _ratio(y_act, y_plan), y_cply, _growth(y_act, y_cply)]


# Despatch sub-groups, in report order (not mine_end_uses_master's order).
END_USES = (("CAPTIVE", "Captive"), ("PELLET_CONV", "Conversion Agent"), ("SALES", "Sales"))

# Reported Production = fresh Lump + Fines + these despatches (None = any
# end use) -- the rule in db.get_iron_ore_group_rollup_monthly, applied per
# mine here so a group/SAIL block's figure equals the SAIL Mines page's.
REPORTED_PARTS = (
    ("Pellets Despatch", "PELLETS", None),
    ("Dump Fines Despatch", "DUMP_FINES", ("CAPTIVE", "SALES")),
    ("Tailings Despatch", "TAILINGS", ("SALES",)),
)

SAIL_NOTE = "Coal and flux are shown at SAIL level; mine-level figures will be added."


def _f(v):
    """MySQL can hand back Decimal; arithmetic here is all float."""
    return None if v is None else float(v)


def _row(label, kind, vals=None, decimals=None):
    return {"label": label, "kind": kind, "values": vals or [None] * 11, "decimals": decimals}


def _empty(vals) -> bool:
    """No figure worth a row: every value blank or 0 (e.g. a plan entered as 0
    with no actual)."""
    return all(v is None or v == 0 for v in vals)


def _visible(items):
    """[(label, series, values)] -> only the rows with data."""
    return [it for it in items if not _empty(it[2])]


def _with_total(items, total_label, V):
    """Item rows plus a total -- the total only when it adds up two or more
    rows (a total of one row just repeats it)."""
    rows = [_row(label, "item", v) for label, _, v in items]
    if len(items) >= 2:
        rows.append(_row(total_label, "total", V(combine([s for _, s, _ in items]))))
    return rows


def _load(months: list) -> dict:
    """Masters plus every series needed, read once for the given months:
    prod[(mine, material)], desp[(mine, material, end_use)] (Rail + Road
    summed), booked[(mine, material)] (Rail + Road summed),
    sail[(section, item)]."""
    conn = db.connect()
    cur = conn.cursor()
    ph = ",".join("?" * len(months))
    stores = {"prod": {}, "desp": {}, "booked": {}, "sail": {}}

    def put(store, key, mo, a=None, p=None):
        s = stores[store].setdefault(key, {})
        oa, op = s.get(mo, (None, None))
        s[mo] = (_sum([oa, _f(a)]), _sum([op, _f(p)]))

    cur.execute("SELECT group_code, group_name FROM mine_groups_master ORDER BY sort_order")
    groups = cur.fetchall()
    cur.execute("SELECT mine_code, mine_name, group_code FROM mines_master "
                "WHERE is_active = 1 ORDER BY sort_order")
    mines = cur.fetchall()
    cur.execute("SELECT material_code, material_name FROM mine_materials_master ORDER BY sort_order")
    materials = cur.fetchall()

    cur.execute(f"SELECT mine_code, material_code, report_month, qty_actual, qty_plan "
                f"FROM mines_production_monthly WHERE report_month IN ({ph})", months)
    for mine, mat, mo, a, p in cur.fetchall():
        put("prod", (mine, mat), mo, a, p)
    cur.execute(f"SELECT mine_code, material_code, end_use_code, report_month, qty_actual "
                f"FROM mines_despatch_actual_monthly WHERE report_month IN ({ph})", months)
    for mine, mat, eu, mo, a in cur.fetchall():
        put("desp", (mine, mat, eu), mo, a=a)
    cur.execute(f"SELECT mine_code, material_code, end_use_code, report_month, qty_plan "
                f"FROM mines_despatch_plan_monthly WHERE report_month IN ({ph})", months)
    for mine, mat, eu, mo, p in cur.fetchall():
        put("desp", (mine, mat, eu), mo, p=p)
    cur.execute(f"SELECT mine_code, material_code, report_month, qty_actual "
                f"FROM mines_booked_qty_actual_monthly WHERE report_month IN ({ph})", months)
    for mine, mat, mo, a in cur.fetchall():
        put("booked", (mine, mat), mo, a=a)
    cur.execute(f"SELECT mine_code, material_code, report_month, qty_plan "
                f"FROM mines_booked_qty_plan_monthly WHERE report_month IN ({ph})", months)
    for mine, mat, mo, p in cur.fetchall():
        put("booked", (mine, mat), mo, p=p)
    cur.execute(f"SELECT section, item, report_month, month_actual, month_plan "
                f"FROM sail_mines_monthly WHERE report_month IN ({ph})", months)
    for section, item, mo, a, p in cur.fetchall():
        put("sail", (section, item), mo, a, p)
    conn.close()
    return {"groups": groups, "mines": mines, "materials": materials, **stores}


def _pick(store: dict, mines, *key) -> dict:
    return combine([store.get((m, *key), {}) for m in mines])


def _pick_any_end_use(store: dict, mines, material) -> dict:
    return combine([s for k, s in store.items() if k[0] in mines and k[1] == material])


def iron_ore_rows(data: dict, mines: list, P: dict) -> list:
    def V(s):
        return values(s, P)

    # Rows with no data (blank or 0) are hidden, a section with none left is
    # hidden with its heading, and a total is shown only when it adds up two
    # or more rows.
    rows = []
    lump, fines = _pick(data["prod"], mines, "LUMP"), _pick(data["prod"], mines, "FINES")
    fresh = combine([lump, fines])
    fresh_items = _visible([("Lump", lump, V(lump)), ("Fines", fines, V(fines))])
    if fresh_items:
        rows.append(_row("I/ORE FRESH PRODUCTION", "heading"))
        rows += _with_total(fresh_items, "Total Fresh Production", V)

    desp_rows, subtotals = [], []
    for eu, eu_label in END_USES:
        items = _visible([(name, s, V(s)) for code, name in data["materials"]
                          for s in [_pick(data["desp"], mines, code, eu)]])
        if not items:
            continue
        subtotals.append(combine([s for _, s, _ in items]))
        desp_rows.append(_row(eu_label, "subheading"))
        desp_rows += _with_total(items, f"Total {eu_label}", V)
    if desp_rows:
        rows.append(_row("I/ORE DESPATCH", "heading"))
        rows += desp_rows
        if len(subtotals) >= 2:
            rows.append(_row("Grand Total Despatch", "total", V(combine(subtotals))))

    parts = [("Fresh Production (Lump+Fines)", fresh, V(fresh))]
    for label, material, eus in REPORTED_PARTS:
        if eus is None:
            s = _pick_any_end_use(data["desp"], mines, material)
        else:
            s = combine([_pick(data["desp"], mines, material, eu) for eu in eus])
        parts.append((label, s, V(s)))
    parts = _visible(parts)
    if parts:
        rows.append(_row("REPORTED PRODUCTION", "heading"))
        if len(parts) == 1:
            # One component: show it once, under the section's own name.
            rows.append(_row("Reported Production", "total", parts[0][2]))
        else:
            rows += _with_total(parts, "Reported Production", V)

    booked = _visible([(name, s, V(s)) for code, name in data["materials"]
                       for s in [_pick(data["booked"], mines, code)]])
    if booked:
        rows.append(_row("BOOKED QUANTITY (SALES)", "heading"))
        rows += _with_total(booked, "Total Booked", V)
    return rows


# (heading, sail_mines_monthly section, items) -- summed into a "Total" row.
_SAIL_SIMPLE = {
    "coal_prod": ("COAL MINES PRODUCTION", ("Raw Coking Coal", "Thermal Coal")),
    "coal_despatch": ("COAL DESPATCH", ("Clean Coal", "Thermal")),
    "flux_prod": ("FLUX PRODUCTION", ("Limestone", "Dolomite")),
    "flux_despatch": ("FLUX DESPATCH", ("Limestone", "Dolomite")),
}

# Quantity indices of the 11 values (the rest are %Ful / %Gr).
_QTY_IDX = (0, 1, 2, 4, 6, 7, 9)


def _yield_values(clean: list, raw: list) -> list:
    """Washery Yield (%) = Clean Coal / Input Raw Coal x 100 for each
    quantity column, then %Ful / %Gr from those yields."""
    y = [None] * 11
    for i in _QTY_IDX:
        y[i] = _ratio(clean[i], raw[i])
    y[3], y[5] = _ratio(y[2], y[1]), _growth(y[2], y[4])
    y[8], y[10] = _ratio(y[7], y[6]), _growth(y[7], y[9])
    return y


def coal_flux_rows(data: dict, P: dict) -> list:
    """SAIL-only sections from sail_mines_monthly (coal and flux are not
    kept per mine yet): Coal Mines Production, Washery, Coal Despatch, Flux
    Production, Flux Despatch. Same hiding rules as the iron-ore rows."""
    def S(section, item):
        return data["sail"].get((section, item), {})

    def V(s):
        return values(s, P)

    def simple(section):
        heading, items = _SAIL_SIMPLE[section]
        visible = _visible([(item, s, V(s)) for item in items for s in [S(section, item)]])
        return [_row(heading, "heading")] + _with_total(visible, "Total", V) if visible else []

    raw = V(S("washery", "Input Raw Coal"))
    clean = V(S("washery", "Clean Coal"))
    washery = [_row(label, "item", v, decimals=d) for label, v, d in
               (("Input Raw Coal", raw, None), ("Clean Coal", clean, None),
                ("Yield (%)", _yield_values(clean, raw), 1)) if not _empty(v)]
    if washery:
        washery.insert(0, _row("WASHERY", "heading"))
    return (simple("coal_prod") + washery + simple("coal_despatch")
            + simple("flux_prod") + simple("flux_despatch"))


def generate(month: str) -> dict:
    P = periods(month)
    data = _load(sorted(set(P["fy"] + P["cply_ytd"] + [P["cply"]])))
    blocks = []
    for gcode, gname in data["groups"]:
        gmines = [(code, name) for code, name, g in data["mines"] if g == gcode]
        for code, name in gmines:
            blocks.append({"name": name, "kind": "mine", "group": gcode, "note": None,
                           "rows": iron_ore_rows(data, [code], P)})
        if gmines:
            blocks.append({"name": gname, "kind": "group", "group": gcode, "note": None,
                           "rows": iron_ore_rows(data, [c for c, _ in gmines], P)})
    all_mines = [code for code, _, _ in data["mines"]]
    blocks.append({"name": "SAIL", "kind": "sail", "group": None, "note": SAIL_NOTE,
                   "rows": iron_ore_rows(data, all_mines, P) + coal_flux_rows(data, P)})
    has_data = any(r["kind"] in ("item", "total") and not _empty(r["values"])
                   for b in blocks for r in b["rows"])
    return {"labels": labels(month), "pct_idx": list(PCT_IDX), "blocks": blocks if has_data else []}
