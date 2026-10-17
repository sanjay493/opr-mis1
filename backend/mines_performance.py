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
    return all(v is None for v in vals)


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

    rows = [_row("I/ORE FRESH PRODUCTION", "heading")]
    lump, fines = _pick(data["prod"], mines, "LUMP"), _pick(data["prod"], mines, "FINES")
    fresh = combine([lump, fines])
    rows += [_row("Lump", "item", V(lump)), _row("Fines", "item", V(fines)),
             _row("Total Fresh Production", "total", V(fresh))]

    desp_rows, subtotals = [], []
    for eu, eu_label in END_USES:
        items = []
        for code, name in data["materials"]:
            s = _pick(data["desp"], mines, code, eu)
            v = V(s)
            if not _empty(v):
                items.append((name, s, v))
        if not items:
            continue
        sub = combine([s for _, s, _ in items])
        subtotals.append(sub)
        desp_rows.append(_row(eu_label, "subheading"))
        desp_rows += [_row(n, "item", v) for n, _, v in items]
        desp_rows.append(_row(f"Total {eu_label}", "total", V(sub)))
    if desp_rows:
        rows.append(_row("I/ORE DESPATCH", "heading"))
        rows += desp_rows
        rows.append(_row("Grand Total Despatch", "total", V(combine(subtotals))))

    parts = []
    for label, material, eus in REPORTED_PARTS:
        if eus is None:
            s = _pick_any_end_use(data["desp"], mines, material)
        else:
            s = combine([_pick(data["desp"], mines, material, eu) for eu in eus])
        parts.append((label, s, V(s)))
    rows.append(_row("REPORTED PRODUCTION", "heading"))
    rows.append(_row("Fresh Production (Lump+Fines)", "item", V(fresh)))
    rows += [_row(label, "item", v) for label, _, v in parts if not _empty(v)]
    rows.append(_row("Reported Production", "total", V(combine([fresh] + [s for _, s, _ in parts]))))

    booked = []
    for code, name in data["materials"]:
        s = _pick(data["booked"], mines, code)
        v = V(s)
        if not _empty(v):
            booked.append((name, s, v))
    if booked:
        rows.append(_row("BOOKED QUANTITY (SALES)", "heading"))
        rows += [_row(n, "item", v) for n, _, v in booked]
        rows.append(_row("Total Booked", "total", V(combine([s for _, s, _ in booked]))))
    return rows


def coal_flux_rows(data: dict, P: dict) -> list:
    """SAIL-only coal/washery/flux sections -- implemented in Task 3."""
    return []


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
