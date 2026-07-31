"""
Production by Process page.
Shows BOF / EAF / CC / CS per plant for:
  - monthly: current month vs CPLY month
  - ytd:     Apr-to-month vs CPLY Apr-to-month
Unit: Tonnes  (DB stores '000 T — multiply × 1000)
"""
import math
import db
from page4 import _p4_ytd_sum, _p4_conv_actuals

_FIVE = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_ALL8 = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL"]
_ROWS = ["BSP", "DSP", "RSP", "BSL", "ISP", "5 Plants", "ASP", "SSP", "VISL", "SAIL"]

_CS = "Total Crude Steel"

# CC item names per plant (same approach as page17_concast._ACT)
_CC: dict = {
    "BSP":  ["SMS-2", "SMS-3"],
    "DSP":  "SMS Total Caster",
    "RSP":  ["SMS-1 CCM-1", "SMS-2 CCM-1&2", "SMS-2 CCM-3", "SMS-2 CCM-4"],
    "BSL":  ["SMS-1 CCM-1", "SMS-2 CCM-1&2"],
    "ISP":  ["SMS CCM-1&2", "SMS CCM-3"],
    "ASP":  "Total Caster",   # returns 0 if absent from DB
    "SSP":  _CS,              # SSP is 100 % CC
    "VISL": _CS,
}

_EAF_PLANTS = {"ASP", "SSP"}   # all other plants use BOF


# ── helpers ──────────────────────────────────────────────────────────────────

def _T(v) -> str:
    return "" if v is None else str(int(math.floor(v * 1000 + 0.5)))


def _pct(a, b) -> str:
    if a is None or b is None or b == 0:
        return ""
    return f"{int(math.floor(a / b * 100 + 0.5))}%"


def _fetch(cur, plant: str, item, month: str):
    if isinstance(item, list):
        tot, ok = 0.0, False
        for it in item:
            cur.execute(
                "SELECT month_actual FROM production_table "
                "WHERE plant_name=? AND item_name=? AND report_month=?",
                (plant, it, month),
            )
            r = cur.fetchone()
            if r and r[0] is not None:
                tot += r[0]; ok = True
        return tot if ok else None
    cur.execute(
        "SELECT month_actual FROM production_table "
        "WHERE plant_name=? AND item_name=? AND report_month=?",
        (plant, item, month),
    )
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None


def _ytd(cur, plant: str, item, months: list):
    tot, ok = 0.0, False
    for m in months:
        v = _fetch(cur, plant, item, m)
        if v is not None:
            tot += v; ok = True
    return tot if ok else None


def _agg(cur, plants: list, item_fn, month: str):
    """Sum item_fn(plant) across plants for one month."""
    tot, ok = 0.0, False
    for p in plants:
        spec = item_fn(p)
        if spec is None:
            continue
        v = _fetch(cur, p, spec, month)
        if v is not None:
            tot += v; ok = True
    return tot if ok else None


def _ytd_agg(cur, plants: list, item_fn, months: list):
    tot, ok = 0.0, False
    for p in plants:
        spec = item_fn(p)
        if spec is None:
            continue
        for m in months:
            v = _fetch(cur, p, spec, m)
            if v is not None:
                tot += v; ok = True
    return tot if ok else None


# ── row builder ───────────────────────────────────────────────────────────────

def _row(plant: str, bof, eaf, cc, cs) -> dict:
    is_eaf = plant in _EAF_PLANTS
    is_sail = plant == "SAIL"
    # BOF % of CS: EAF plants show "0%" (not blank) when they have CS
    if is_eaf:
        bof_pct = "0%" if (cs is not None and cs > 0) else ""
    else:
        bof_pct = _pct(bof, cs)

    return {
        "plant":   plant,
        "bold":    plant in ("5 Plants", "SAIL"),
        "bof":     "" if is_eaf else _T(bof),
        "eaf":     _T(eaf) if (is_eaf or is_sail) else "",
        "cc":      _T(cc),
        "cs":      _T(cs),
        "bof_pct": bof_pct,
        "cc_pct":  _pct(cc, cs),
    }


# ── per-plant data fetchers ───────────────────────────────────────────────────

def _plant_month(cur, plant: str, month: str):
    cs = _fetch(cur, plant, _CS, month)
    cc = _fetch(cur, plant, _CC.get(plant), month) if _CC.get(plant) else None
    if plant in _EAF_PLANTS:
        return None, cs, cc, cs   # bof, eaf, cc, cs
    return cs, None, cc, cs


def _plant_ytd(cur, plant: str, months: list):
    cs = _ytd(cur, plant, _CS, months)
    cc = _ytd(cur, plant, _CC.get(plant), months) if _CC.get(plant) else None
    if plant in _EAF_PLANTS:
        return None, cs, cc, cs
    return cs, None, cc, cs


def _agg_month(cur, plants: list, month: str):
    bof_p = [p for p in plants if p not in _EAF_PLANTS]
    eaf_p = [p for p in plants if p in _EAF_PLANTS]
    cs  = _agg(cur, plants,  lambda p: _CS,        month)
    bof = _agg(cur, bof_p,   lambda p: _CS,        month)
    eaf = _agg(cur, eaf_p,   lambda p: _CS,        month) if eaf_p else None
    cc  = _agg(cur, plants,  lambda p: _CC.get(p), month)
    return bof, eaf, cc, cs


def _agg_ytd(cur, plants: list, months: list):
    bof_p = [p for p in plants if p not in _EAF_PLANTS]
    eaf_p = [p for p in plants if p in _EAF_PLANTS]
    cs  = _ytd_agg(cur, plants,  lambda p: _CS,        months)
    bof = _ytd_agg(cur, bof_p,   lambda p: _CS,        months)
    eaf = _ytd_agg(cur, eaf_p,   lambda p: _CS,        months) if eaf_p else None
    cc  = _ytd_agg(cur, plants,  lambda p: _CC.get(p), months)
    return bof, eaf, cc, cs


# ── Hot-Metal-to-Saleable-Steel flow (Sankey) ────────────────────────────────
#
# SAIL-total, till-the-month (YTD) only. Node/link quantities come straight
# from the same DB items already relied on elsewhere in the report — no new
# tracking is introduced:
#   Hot Metal, Pig Iron, Finished Steel (SAIL rollup)  -> page4.py's own
#     PAGE4_ITEMS plant sets (_5P+VISL for HM/Pig Iron, _5P+ASP+SSP+VISL with
#     the SSP/VISL -> Saleable Steel fallback for Finished Steel), via
#     page4._p4_ytd_sum so this stays in lockstep with the page-4 table if
#     that logic ever changes.
#   Crude Steel BOF vs EAF split                       -> this module's own
#     _agg_ytd (same plant-inferred BOF/EAF split already shown in this
#     page's own table).
#   Conversion (SAIL)                                  -> page4._p4_conv_actuals
#     (the literal 'Conversion' actual, plant_name='SAIL').
#   Saleable Semis (semis sold, pre-rolling)            -> summed across the
#     5 main plants' 'Saleable Semis' item (page5_6.py's Category-Wise
#     Saleable Steel page uses the same item for the same purpose).
#
# One split has no independent DB actual and is taken as the remainder of a
# measured total minus its measured sibling (clamped >= 0): "direct sale
# semis" = Semis for Sale − Conversion. Everything else below is a real
# reported actual, not a derived estimate.
#
# There is no "feed to rolling mills" item in this project's data, so it is
# NOT shown as a node — an earlier version inferred it as Crude Steel total
# minus Semis for Sale, which silently folds every other unmeasured loss/
# routing into that one number and reads as a real figure when it isn't.
# Crude Steel instead links straight to Finished Steel (Mills) using the
# real Finished Steel actual, without claiming to know the intermediate
# tonnage.
_FIVE_VISL = _FIVE + ["VISL"]
_FS_SAIL_SET = _FIVE + ["ASP", "SSP", "VISL"]


def _semis_ytd(cur, months: list) -> float:
    """SAIL 'Saleable Semis' (5 main plants only — RSP/ASP/SSP/VISL don't
    report it), summed over YTD months."""
    ph_m = ",".join("?" * len(months))
    ph_p = ",".join("?" * len(_FIVE))
    cur.execute(
        f"SELECT COALESCE(SUM(month_actual),0) FROM production_table "
        f"WHERE report_month IN ({ph_m}) AND plant_name IN ({ph_p}) "
        f"AND item_name='Saleable Semis'",
        (*months, *_FIVE),
    )
    r = cur.fetchone()
    return float(r[0]) if r and r[0] is not None else 0.0


def _node_totals(nodes: list, links: list) -> tuple:
    incoming = {n["id"]: 0.0 for n in nodes}
    outgoing = {n["id"]: 0.0 for n in nodes}
    for l in links:
        outgoing[l["source"]] += l["value"]
        incoming[l["target"]] += l["value"]
    return incoming, outgoing


def _sankey_svg(nodes: list, links: list, vw: int = 980, vh: int = 300) -> str:
    """Hand-rolled layered Sankey: nodes carry a fixed 'column' (left-to-right
    stage), links only ever join adjacent columns. A node's height defaults to
    max(incoming, outgoing) so a node whose in/out differ (a process-yield
    step, e.g. rolling mills) draws with visibly tapering ribbons either side
    rather than being forced to a false balance. A node MAY instead carry an
    explicit "value" (its own independently measured actual, e.g. Hot Metal)
    which overrides that — its outgoing ribbons then only fill part of its
    height when they don't fully account for it (real process loss/yield,
    surfaced as unfilled bar rather than silently shrinking the node to match
    only what the split figures can explain)."""
    ml, mr, mt, mb = 92, 92, 46, 10
    cw, ch = vw - ml - mr, vh - mt - mb

    incoming, outgoing = _node_totals(nodes, links)
    sizes = {n["id"]: n["value"] if n.get("value") is not None
             else max(incoming[n["id"]], outgoing[n["id"]]) for n in nodes}

    columns = sorted({n["column"] for n in nodes})
    by_col = {c: [n for n in nodes if n["column"] == c] for c in columns}

    node_gap = 40.0
    scale = None
    for ns in by_col.values():
        total = sum(sizes[n["id"]] for n in ns)
        if total <= 0:
            continue
        avail = ch - (len(ns) - 1) * node_gap
        col_scale = avail / total
        scale = col_scale if scale is None else min(scale, col_scale)
    scale = scale or 1.0

    node_w = 14.0
    n_cols = len(columns)
    col_gap = (cw - node_w * n_cols) / max(n_cols - 1, 1)

    geo = {}
    for c in columns:
        ns = by_col[c]
        heights = [max(sizes[n["id"]] * scale, 4.0) for n in ns]
        total_h = sum(heights) + node_gap * (len(ns) - 1)
        y = mt + (ch - total_h) / 2.0
        x = ml + c * (node_w + col_gap)
        for n, h in zip(ns, heights):
            geo[n["id"]] = {"x": x, "y": y, "w": node_w, "h": h, "node": n}
            y += h + node_gap

    out_used = {nid: 0.0 for nid in geo}
    in_used = {nid: 0.0 for nid in geo}

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
           f'style="width:100%;height:auto;display:block;">']

    for l in links:
        s, t, v = l["source"], l["target"], l["value"]
        if v <= 0 or s not in geo or t not in geo:
            continue
        sg, tg = geo[s], geo[t]
        h = max(v * scale, 2.0)
        sy0 = sg["y"] + out_used[s]
        ty0 = tg["y"] + in_used[t]
        out_used[s] += h
        in_used[t] += h
        x0, x1 = sg["x"] + sg["w"], tg["x"]
        xm = (x0 + x1) / 2
        d = (f'M{x0:.1f},{sy0:.1f} C{xm:.1f},{sy0:.1f} {xm:.1f},{ty0:.1f} {x1:.1f},{ty0:.1f} '
             f'L{x1:.1f},{ty0 + h:.1f} C{xm:.1f},{ty0 + h:.1f} {xm:.1f},{sy0 + h:.1f} {x0:.1f},{sy0 + h:.1f} Z')
        svg.append(f'<path d="{d}" fill="{sg["node"]["color"]}" fill-opacity="0.32" stroke="none"/>')

    for nid, g in geo.items():
        n = g["node"]
        color = n["color"]
        svg.append(f'<rect x="{g["x"]:.1f}" y="{g["y"]:.1f}" width="{g["w"]:.1f}" height="{g["h"]:.1f}" '
                    f'rx="2.5" fill="{color}"/>')
        cx = g["x"] + g["w"] / 2
        val_str = f'{sizes[nid] * 1000:,.0f} T'  # '000T -> T
        svg.append(f'<text x="{cx:.1f}" y="{g["y"] - 32:.1f}" text-anchor="middle" font-size="12" '
                    f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{n["label"]}</text>')
        svg.append(f'<text x="{cx:.1f}" y="{g["y"] - 14:.1f}" text-anchor="middle" font-size="12" '
                    f'font-family="Arial,sans-serif" fill="#475569">{val_str}</text>')

    svg.append("</svg>")
    return "\n".join(svg)


def _flow_sankey_svg(cur, report_month: str) -> str:
    ytd_months = db.get_ytd_months(report_month)

    hm_ytd  = _p4_ytd_sum(cur, "act", ytd_months, "SAIL", "Hot Metal",      _FIVE, _FIVE_VISL) or 0.0
    pig_ytd = _p4_ytd_sum(cur, "act", ytd_months, "SAIL", "Pig Iron",       _FIVE, _FIVE_VISL) or 0.0
    fs_ytd  = _p4_ytd_sum(cur, "act", ytd_months, "SAIL", "Finished Steel", _FIVE, _FS_SAIL_SET) or 0.0
    _, _, conv_ytd, _ = _p4_conv_actuals(cur, report_month)
    conv_ytd = conv_ytd or 0.0

    bof_ytd, eaf_ytd, _cc_ytd, cs_ytd = _agg_ytd(cur, _ALL8, ytd_months)
    bof_ytd, eaf_ytd, cs_ytd = bof_ytd or 0.0, eaf_ytd or 0.0, cs_ytd or 0.0

    semis_ytd = _semis_ytd(cur, ytd_months)
    direct_sale_ytd = max(0.0, semis_ytd - conv_ytd)

    nodes = [
        {"id": "hm",     "label": "Hot Metal",              "column": 0, "color": "#2a78d6", "value": hm_ytd},
        {"id": "eaf",    "label": "EAF Route (ASP+SSP)",     "column": 0, "color": "#eda100"},
        {"id": "pig",    "label": "Pig Iron",                "column": 1, "color": "#94a3b8"},
        {"id": "cs",     "label": "Crude Steel",             "column": 1, "color": "#1baf7a"},
        {"id": "semis",  "label": "Semis for Sale",          "column": 2, "color": "#eb6834"},
        {"id": "dsale",  "label": "Direct Sale (Semis)",     "column": 3, "color": "#94a3b8"},
        {"id": "conv",   "label": "Conversion Agent",        "column": 3, "color": "#e87ba4"},
        {"id": "fsmill", "label": "Finished Steel (Mills)",  "column": 3, "color": "#1baf7a"},
        {"id": "fstot",  "label": "SAIL Finished Steel",     "column": 4, "color": "#2a78d6"},
    ]
    links = [
        {"source": "hm",     "target": "pig",    "value": pig_ytd},
        {"source": "hm",     "target": "cs",     "value": bof_ytd},
        {"source": "eaf",    "target": "cs",     "value": eaf_ytd},
        {"source": "cs",     "target": "semis",  "value": semis_ytd},
        {"source": "cs",     "target": "fsmill", "value": fs_ytd},
        {"source": "semis",  "target": "dsale",  "value": direct_sale_ytd},
        {"source": "semis",  "target": "conv",   "value": conv_ytd},
        {"source": "fsmill", "target": "fstot",  "value": fs_ytd},
        {"source": "conv",   "target": "fstot",  "value": conv_ytd},
    ]
    return _sankey_svg(nodes, links)


# ── public API ────────────────────────────────────────────────────────────────

def generate_prod_by_process(report_month: str) -> dict:
    prev_month      = db.get_cply_month(report_month)
    ytd_months      = db.get_ytd_months(report_month)
    prev_ytd_months = db.get_ytd_months(prev_month)

    conn = db.connect()
    cur  = conn.cursor()
    m_cur, m_prev, y_cur, y_prev = [], [], [], []

    try:
        for plant in _ROWS:
            is_agg = plant in ("5 Plants", "SAIL")
            plants = _FIVE if plant == "5 Plants" else (_ALL8 if plant == "SAIL" else None)

            if is_agg:
                bof,  eaf,  cc,  cs  = _agg_month(cur, plants, report_month)
                bofp, eafp, ccp, csp = _agg_month(cur, plants, prev_month)
                yb,   ye,   yc,  ycs = _agg_ytd(cur, plants, ytd_months)
                ybp,  yep,  ycp, ycsp = _agg_ytd(cur, plants, prev_ytd_months)
            else:
                bof,  eaf,  cc,  cs  = _plant_month(cur, plant, report_month)
                bofp, eafp, ccp, csp = _plant_month(cur, plant, prev_month)
                yb,   ye,   yc,  ycs = _plant_ytd(cur, plant, ytd_months)
                ybp,  yep,  ycp, ycsp = _plant_ytd(cur, plant, prev_ytd_months)

            m_cur.append(_row(plant, bof,  eaf,  cc,  cs))
            m_prev.append(_row(plant, bofp, eafp, ccp, csp))
            y_cur.append(_row(plant, yb,   ye,   yc,  ycs))
            y_prev.append(_row(plant, ybp,  yep,  ycp, ycsp))

        sankey_svg = _flow_sankey_svg(cur, report_month)
    finally:
        conn.close()

    return {
        "monthly":      m_cur,
        "monthly_prev": m_prev,
        "ytd":          y_cur,
        "ytd_prev":     y_prev,
        "sankey_svg":   sankey_svg,
    }
