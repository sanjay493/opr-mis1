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
from page_at_a_glance import _declutter_1d

_FIVE = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_ALL8 = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL"]
_ROWS = ["BSP", "DSP", "RSP", "BSL", "ISP", "5 Plants", "ASP", "SSP", "VISL", "SAIL"]

_CS = "Total Crude Steel"

# CC item names per plant (same approach as page17_concast._ACT).
# RSP/BSL: Concast actual = Total Crude Steel - SMS-1 Ingot, rather than
# summing individual CCM items — mirrors page17_concast.py's own fix
# (understated BSL, which has no SMS-2 CCM-3/CCM-4 items, and didn't
# reconcile to the authoritative Total Crude Steel DPR figure).
_CC: dict = {
    "BSP":  ["SMS-2", "SMS-3"],
    "DSP":  "SMS Total Caster",
    "RSP":  ("Total Crude Steel", "-", "SMS-1 Ingot"),
    "BSL":  ("Total Crude Steel", "-", "SMS-1 Ingot"),
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
    if isinstance(item, tuple) and len(item) == 3 and item[1] == "-":
        minuend_item, _, subtrahend_item = item
        minuend = _fetch(cur, plant, minuend_item, month)
        if minuend is None:
            return None
        subtrahend = _fetch(cur, plant, subtrahend_item, month)
        return minuend - (subtrahend or 0.0)
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
    """SAIL 'Semi-finished steel' — the 5 main plants' own 'Saleable Semis'
    item, PLUS ASP's own semi-finished output. ASP has no separate
    "Saleable Semis" item to read directly — it's derived the same way
    page5_6.py's Plant-Wise Production Performance page (the SAIL "Semi-
    finished steel" row on pages 8-9) already does, as Saleable Steel -
    Finished Steel — matching that convention here too so this page's
    Semis for Sale always agrees with that one instead of quietly running
    ~43,000 T under it every month (ASP's own missing share)."""
    ph_m = ",".join("?" * len(months))
    ph_p = ",".join("?" * len(_FIVE))
    cur.execute(
        f"SELECT COALESCE(SUM(month_actual),0) FROM production_table "
        f"WHERE report_month IN ({ph_m}) AND plant_name IN ({ph_p}) "
        f"AND item_name='Saleable Semis'",
        (*months, *_FIVE),
    )
    r = cur.fetchone()
    five_plant = float(r[0]) if r and r[0] is not None else 0.0

    cur.execute(
        f"SELECT report_month, item_name, month_actual FROM production_table "
        f"WHERE report_month IN ({ph_m}) AND plant_name='ASP' "
        f"AND item_name IN ('Saleable Steel','Finished Steel')",
        months,
    )
    asp_by_month = {}
    for rm, item, val in cur.fetchall():
        asp_by_month.setdefault(rm, {})[item] = val
    asp_semis = sum(
        d["Saleable Steel"] - d["Finished Steel"]
        for d in asp_by_month.values()
        if d.get("Saleable Steel") is not None and d.get("Finished Steel") is not None
    )

    return five_plant + asp_semis


_IPT_SEMIS_ITEMS = (
    "CC Slabs", "CC Blooms", "CC Billets (105 sq mm)",
    # ASP -> RSP, a slab-type product under its own item name in
    # ipt_table (not "CC Slabs") — confirmed against a live check
    # (670+560+647+503 = 2,380 T, Apr-Jul'26).
    "Spade/ 2Pi / Jackal Slabs",
)


def _ipt_transfer_ytd(cur, months: list) -> float:
    """Semis moved to another plant to be rolled into finished steel there,
    rather than sold as-is — per direct instruction, "Total IPT" (_IPT_
    SEMIS_ITEMS, ipt_table, any route) plus DSP's entire Bottom Pouring
    Ingot output (all of it goes to ASP, though ipt_table has no explicit
    route for it). ipt_table stores its actual in plain Tonnes (unlike
    production_table's '000 T everywhere else on this page) — /1000 to
    match."""
    ph_m = ",".join("?" * len(months))
    ph_i = ",".join("?" * len(_IPT_SEMIS_ITEMS))
    cur.execute(
        f"SELECT COALESCE(SUM(actual),0) FROM ipt_table "
        f"WHERE report_month IN ({ph_m}) AND item IN ({ph_i})",
        (*months, *_IPT_SEMIS_ITEMS),
    )
    ipt_t = float(cur.fetchone()[0] or 0.0)

    cur.execute(
        f"SELECT COALESCE(SUM(month_actual),0) FROM production_table "
        f"WHERE report_month IN ({ph_m}) AND plant_name='DSP' AND item_name='Bottom Pouring Ingot'",
        months,
    )
    ingot = float(cur.fetchone()[0] or 0.0)

    return ipt_t / 1000.0 + ingot


# Main-flow nodes for the Hot-Metal-to-Saleable-Steel Sankey (_flow_sankey_svg
# below) — these get their label centered on the bar itself instead of the
# above-bar placement every other (branch/split) node uses.
_MID_LABEL_IDS = {"hm", "cs", "fsmill", "fstot"}


def _node_totals(nodes: list, links: list) -> tuple:
    incoming = {n["id"]: 0.0 for n in nodes}
    outgoing = {n["id"]: 0.0 for n in nodes}
    for l in links:
        outgoing[l["source"]] += l["value"]
        incoming[l["target"]] += l["value"]
    return incoming, outgoing


def _sankey_svg(nodes: list, links: list, vw: int = 980, vh: int = 300,
                 value_fmt=None, side_labels: bool = False, label_font_size: float = 12.0) -> str:
    """Hand-rolled layered Sankey: nodes carry a fixed 'column' (left-to-right
    stage), links only ever join adjacent columns. A node's height defaults to
    max(incoming, outgoing) so a node whose in/out differ (a process-yield
    step, e.g. rolling mills) draws with visibly tapering ribbons either side
    rather than being forced to a false balance. A node MAY instead carry an
    explicit "value" (its own independently measured actual, e.g. Hot Metal)
    which overrides that — its outgoing ribbons then only fill part of its
    height when they don't fully account for it (real process loss/yield,
    surfaced as unfilled bar rather than silently shrinking the node to match
    only what the split figures can explain).

    value_fmt(node_value) -> display string, e.g. "1,234 T" — defaults to
    this page's own convention (input values are '000T, displayed as T);
    a caller whose node values are already in their final display unit
    (e.g. page_ipt.py's tonnes/rake counts) passes its own formatter.

    side_labels=True: every non-mid-flow label is anchored to its own
    node's vertical center instead of stacked above it — on the LEFT for
    a first-column node (sender), on the RIGHT for a last-column node
    (receiver). Meant for a simple 2-column bipartite diagram (see
    page_ipt.py, the only current caller) where each node already has
    clear vertical room of its own; skips the above-node decluttering pass
    entirely since there's nothing to declutter — each label just sits
    beside the one node it belongs to.

    label_font_size: every text element's font-size — defaults to 12 (the
    original, only ever value before this parameter existed, so every
    existing caller/appearance is unchanged). Every other text-related
    geometry constant below (margins, chip sizing, label offsets, the
    declutter block height) scales proportionally with it via `fs_scale`,
    so a caller asking for bigger text gets consistently bigger clearance
    around it too, not overlapping labels sized for the old default."""
    fs_scale = label_font_size / 12.0
    ml, mr, mt, mb = 92 * fs_scale, 92 * fs_scale, 46 * fs_scale, 10 * fs_scale
    cw, ch = vw - ml - mr, vh - mt - mb

    incoming, outgoing = _node_totals(nodes, links)
    sizes = {n["id"]: n["value"] if n.get("value") is not None
             else max(incoming[n["id"]], outgoing[n["id"]]) for n in nodes}

    columns = sorted({n["column"] for n in nodes})
    by_col = {c: [n for n in nodes if n["column"] == c] for c in columns}

    node_gap = 40.0 * fs_scale
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
        # A column defaults to vertically centered — fine when its total
        # height is a sizeable chunk of the canvas, but a single small node
        # alone in its column (e.g. this page's "Semis for Sale", a minor
        # branch off the much larger Crude Steel -> Finished Steel flow)
        # centers right on top of whatever big ribbon happens to pass
        # through that same vertical band. Any node in the column carrying
        # "align": "top" pins the whole column to the top margin instead,
        # to sit clear of that main stream.
        if any(n.get("align") == "top" for n in ns):
            y = mt
        elif any(n.get("align") == "bottom" for n in ns):
            y = mt + (ch - total_h)
        else:
            y = mt + (ch - total_h) / 2.0
        x = ml + c * (node_w + col_gap)
        for n, h in zip(ns, heights):
            geo[n["id"]] = {"x": x, "y": y, "w": node_w, "h": h, "node": n}
            y += h + node_gap

    fmt = value_fmt or (lambda v: f'{v * 1000:,.0f} T')
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

    # Above-node labels (name + value, 2 lines, ~34pt tall) are anchored to
    # each node's own top edge (g["y"] - 32 / - 14) — fine when nodes in a
    # column are spaced well apart, but a column with several small/close
    # nodes (e.g. a Sankey with many thin routes) packs their tops closer
    # than 34pt apart, so adjacent labels overlap into an unreadable jumble.
    # Decluttered per column (top-to-bottom, i.e. ascending y) the same way
    # page_at_a_glance.py's own-% badges are — small counts per column, so
    # this converges in a couple of passes — keeping every label at its own
    # font-size (12pt, per direct instruction) rather than shrinking text to
    # make it fit.
    # A 2-line, 12pt label block's own visual footprint is ~30 SVG units
    # tall (cap-height above the first baseline to descender below the
    # second) — this needs real clearance beyond that on top of it, or
    # consecutive blocks read as cramped/touching even when not truly
    # overlapping (confirmed by measuring real rendered bounding boxes at
    # a few tried values before landing here).
    _LABEL_BLOCK_H = 55.0 * fs_scale
    label_y = {}
    if not side_labels:
        for c in columns:
            non_mid = [n for n in by_col[c] if n["id"] not in _MID_LABEL_IDS]
            ids_sorted = sorted((n["id"] for n in non_mid), key=lambda nid: geo[nid]["y"])
            ideal = [geo[nid]["y"] for nid in ids_sorted]
            adjusted = _declutter_1d(ideal, _LABEL_BLOCK_H)
            label_y.update(zip(ids_sorted, adjusted))

    for nid, g in geo.items():
        n = g["node"]
        color = n["color"]
        svg.append(f'<rect x="{g["x"]:.1f}" y="{g["y"]:.1f}" width="{g["w"]:.1f}" height="{g["h"]:.1f}" '
                    f'rx="2.5" fill="{color}"/>')
        cx = g["x"] + g["w"] / 2
        # A node with no independent DB actual of its own (e.g. this page's
        # "Direct Sale (Semis)", a derived remainder) carries its own
        # "value_prefix" (e.g. "≈ ") to mark that in the rendered value —
        # blank for every ordinary, directly-measured node.
        #
        # "display_value" overrides only the printed number, leaving the
        # node's actual geometry (bar height, ribbon widths) keyed to its
        # real sizes[nid] — this page's "Conversion Agent" node sizes to
        # its larger SLAB input (so the ~4% mill-yield loss still shows as
        # an unfilled bar), but the number printed on it is the smaller
        # finished-PRODUCT quantity, so it reads the same as the figure
        # that actually flows on into SAIL Finished Steel.
        val_str = n.get("value_prefix", "") + fmt(n.get("display_value", sizes[nid]))
        if nid in _MID_LABEL_IDS:
            # Main-flow nodes (Hot Metal -> Crude Steel -> Finished Steel
            # (Mills) -> SAIL Finished Steel) label at the bar's own vertical
            # center rather than in the top margin, so the label sits beside
            # the value it actually describes instead of floating above the
            # whole column regardless of where that bar happens to sit. A
            # translucent white chip backs the two lines since, centered,
            # they cross the node's own fill and the ribbons flowing into/
            # out of it, not just clear page background.
            cy = g["y"] + g["h"] / 2
            chip_w = max(len(n["label"]), len(val_str)) * 6.8 * fs_scale + 20 * fs_scale
            chip_h = 30.0 * fs_scale
            svg.append(f'<rect x="{cx - chip_w / 2:.1f}" y="{cy - chip_h / 2:.1f}" '
                        f'width="{chip_w:.1f}" height="{chip_h:.1f}" rx="4" '
                        f'fill="#ffffff" fill-opacity="0.88"/>')
            svg.append(f'<text x="{cx:.1f}" y="{cy - 3 * fs_scale:.1f}" text-anchor="middle" font-size="{label_font_size:g}" '
                        f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{n["label"]}</text>')
            svg.append(f'<text x="{cx:.1f}" y="{cy + 13 * fs_scale:.1f}" text-anchor="middle" font-size="{label_font_size:g}" '
                        f'font-family="Arial,sans-serif" fill="#475569">{val_str}</text>')
        elif side_labels or n.get("label_side"):
            # Sender (first column) labels sit to the left of their node,
            # text growing leftward (text-anchor="end"); receiver (last
            # column) labels sit to the right, growing rightward — each
            # anchored to its own node's vertical center, no decluttering
            # needed since every label already sits right next to (and so
            # is unambiguously tied to) the one node it describes. A single
            # node can opt into this style on its own via "label_side":
            # "left"/"right" (e.g. this page's "EAF Route", inline beside
            # its own line rather than stacked above it like everything
            # else here) without switching every OTHER node over too —
            # only page_ipt.py sets side_labels globally, for its own
            # simple 2-column diagrams.
            cy = g["y"] + g["h"] / 2
            want_right = n.get("label_side", "right" if n["column"] != columns[0] else "left") == "right"
            if want_right:
                tx, anchor = g["x"] + g["w"] + 6 * fs_scale, "start"
            else:
                tx, anchor = g["x"] - 6 * fs_scale, "end"
            svg.append(f'<text x="{tx:.1f}" y="{cy - 3 * fs_scale:.1f}" text-anchor="{anchor}" font-size="{label_font_size:g}" '
                        f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{n["label"]}</text>')
            svg.append(f'<text x="{tx:.1f}" y="{cy + 11 * fs_scale:.1f}" text-anchor="{anchor}" font-size="{label_font_size:g}" '
                        f'font-family="Arial,sans-serif" fill="#475569">{val_str}</text>')
        else:
            ly = label_y.get(nid, g["y"])
            # Collision-avoidance can shift a label away from its node's true
            # top — a thin leader line back to the node keeps it legible
            # which color/ribbon the label actually describes.
            if abs(ly - g["y"]) > 0.5:
                svg.append(f'<line x1="{cx:.1f}" y1="{ly - 6 * fs_scale:.1f}" x2="{cx:.1f}" y2="{g["y"]:.1f}" '
                            f'stroke="#94a3b8" stroke-width="0.6" stroke-dasharray="1.5,1.5"/>')
            svg.append(f'<text x="{cx:.1f}" y="{ly - 32 * fs_scale:.1f}" text-anchor="middle" font-size="{label_font_size:g}" '
                        f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{n["label"]}</text>')
            # "value_anchor": a node's value normally prints right below its
            # own name (above), but one whose ribbon's real destination is
            # what the number is actually about (e.g. this page's
            # "Conversion Agent" — its value IS the finished-steel quantity
            # that ends up at SAIL Finished Steel) can point its value at
            # that OTHER node's own top edge instead, per direct
            # instruction — still colored like the node it came from so
            # it's clear which ribbon it's labeling.
            anchor_id = n.get("value_anchor")
            anchor_g = geo.get(anchor_id) if anchor_id else None
            if anchor_g:
                svg.append(f'<text x="{anchor_g["x"] - 4 * fs_scale:.1f}" y="{anchor_g["y"] - 6 * fs_scale:.1f}" '
                            f'text-anchor="end" font-size="{label_font_size:g}" '
                            f'font-family="Arial,sans-serif" fill="{color}">{val_str}</text>')
            else:
                svg.append(f'<text x="{cx:.1f}" y="{ly - 14 * fs_scale:.1f}" text-anchor="middle" font-size="{label_font_size:g}" '
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
    ipt_ytd = _ipt_transfer_ytd(cur, ytd_months)
    # Conversion Agent's SLAB input, back-estimated from its finished-steel
    # OUTPUT at a 96% mill yield (per direct instruction, revised from an
    # earlier 94% figure) — larger than conv_ytd itself (the actual
    # finished-steel figure, still used unchanged for the conv->fstot link
    # below). The gap between the two surfaces visually as the conv node's
    # own tapering ribbon: a node with no explicit "value" override sizes
    # to max(incoming, outgoing) (see _sankey_svg's doc), so its ~4% yield
    # loss shows as unfilled bar rather than being silently absorbed
    # anywhere. conv_ytd is re-queried fresh per report_month above, so
    # this — and every figure derived from it below — recomputes correctly
    # for any month without further changes.
    _CONV_MILL_YIELD = 0.96
    conv_slab_ytd = conv_ytd / _CONV_MILL_YIELD
    # Semis for Sale now splits 3 ways instead of 2 (Direct Sale, IPT
    # Transfer, Conversion) — Direct Sale is still whatever's left over
    # with no independent DB actual of its own, just against a bigger set
    # of measured deductions than before, hence "≈" on its own value below.
    direct_sale_ytd = max(0.0, semis_ytd - ipt_ytd - conv_slab_ytd)

    # Finished Steel (Mills) now sits one column further right than the
    # other 3 semis-splits (dsale/ipt/conv), with SAIL Finished Steel
    # pushed out to column 5 in turn — makes room for IPT Transfer to flow
    # forward into it as a real link (below), rather than the two being
    # unconnected siblings in the same column whose ribbons used to cross
    # straight through the Finished Steel (Mills) bar to reach their own
    # (more distant) targets. cs -> fsmill and conv -> fstot both already
    # spanned non-adjacent columns before this and rendered fine — see
    # _sankey_svg's own bezier-curve construction, which only needs each
    # link's two endpoints, not that they sit in adjacent columns.
    nodes = [
        {"id": "hm",     "label": "Hot Metal",              "column": 0, "color": "#2a78d6", "value": hm_ytd},
        # "label_side": "right" — inline beside its own line rather than
        # stacked above it (this page's default), per direct instruction.
        {"id": "eaf",    "label": "EAF Route (ASP+SSP)",     "column": 0, "color": "#eda100", "label_side": "right"},
        {"id": "pig",    "label": "Pig Iron",                "column": 1, "color": "#94a3b8"},
        {"id": "cs",     "label": "Crude Steel",             "column": 1, "color": "#1baf7a"},
        {"id": "semis",  "label": "Semis for Sale",          "column": 2, "color": "#eb6834", "align": "top"},
        # Semis for Sale's 3-way split, top-to-bottom per direct
        # instruction: Direct Sale on top, Conversion Agent in the middle,
        # IPT Transfer on the bottom. Pushing Direct Sale out to its own
        # far column (tried previously, to elongate its ribbon) made its
        # long top-hugging ribbon cut straight across Conversion Agent's
        # own ribbon on its way into SAIL Finished Steel — reverted; all
        # three stay together, right next to Semis for Sale, where none of
        # their ribbons has to cross another's path: Direct Sale is a dead
        # end (no ribbon leaving this column at all), Conversion Agent's
        # ribbon (claims SAIL Finished Steel's TOP incoming slot, see the
        # conv->fstot link below) only has a short hop up from the middle,
        # and IPT Transfer's ribbon drops from the bottom straight into
        # Finished Steel (Mills) — itself bottom-aligned — right below it.
        # column 3.5, not 3 — a fractional column is a valid, quieter way
        # to stretch just this one ribbon a bit longer than its siblings'
        # (columns are plain x-axis positions, not slot indices) without
        # reaching all the way out to Finished Steel (Mills)/SAIL Finished
        # Steel's own columns, which is what caused it to cross
        # Conversion Agent's ribbon last time.
        {"id": "dsale",  "label": "Direct Sale (Semis)",     "column": 3.5, "color": "#94a3b8", "value_prefix": "≈ ", "align": "top"},
        # Blue, matching Finished Steel's own color — per direct
        # instruction, since what it's carrying IS finished steel by the
        # time it lands. "value_anchor": "fstot" moves its printed value
        # (still the finished-PRODUCT quantity, see display_value above)
        # to sit right above where its now-blue ribbon actually arrives,
        # at SAIL Finished Steel's own bar, instead of up by its own small
        # node — the number reads next to what it's actually describing.
        {"id": "conv",   "label": "Conversion Agent",        "column": 3, "color": "#2a78d6", "display_value": conv_ytd, "value_anchor": "fstot"},
        {"id": "ipt",    "label": "IPT Transfer",            "column": 3, "color": "#5b9bd5"},
        # "align": "bottom" — its own bar is nearly as tall as the whole
        # canvas (fs_ytd is close in scale to Hot Metal itself), so with no
        # alignment it fills almost the entire column and leaves nothing
        # for Conversion Agent's ribbon (top-aligned, above) to route
        # through on its way to SAIL Finished Steel. Pinning it to the
        # bottom instead opens a clear strip across the top for that
        # ribbon to pass through unobstructed.
        {"id": "fsmill", "label": "Finished Steel (Mills)",  "column": 4, "color": "#1baf7a", "align": "bottom"},
        {"id": "fstot",  "label": "SAIL Finished Steel",     "column": 5, "color": "#2a78d6"},
    ]
    links = [
        {"source": "hm",     "target": "pig",    "value": pig_ytd},
        {"source": "hm",     "target": "cs",     "value": bof_ytd},
        {"source": "eaf",    "target": "cs",     "value": eaf_ytd},
        {"source": "cs",     "target": "semis",  "value": semis_ytd},
        # Split into "direct" (still straight from Crude Steel) and "via
        # IPT Transfer" (below) so the two sum back to the same fs_ytd
        # total Finished Steel (Mills) always had — IPT-transferred semis
        # becoming finished steel at the RECEIVING plant is already
        # counted inside fs_ytd (SAIL's own total), so this only re-splits
        # its source, never adds to it.
        {"source": "cs",     "target": "fsmill", "value": max(0.0, fs_ytd - ipt_ytd)},
        {"source": "semis",  "target": "dsale",  "value": direct_sale_ytd},
        {"source": "semis",  "target": "ipt",    "value": ipt_ytd},
        {"source": "ipt",    "target": "fsmill", "value": ipt_ytd},
        {"source": "semis",  "target": "conv",   "value": conv_slab_ytd},
        # conv->fstot listed BEFORE fsmill->fstot so it claims the TOP of
        # SAIL Finished Steel's incoming edge (ribbons stack in link-list
        # order) — Conversion Agent now sits near the top of its own
        # column (align: "top" above), so its ribbon can arc straight
        # across at that same height into fstot's own top edge without
        # dipping down through the much bigger Finished Steel (Mills)
        # ribbon to reach a lower slot.
        {"source": "conv",   "target": "fstot",  "value": conv_ytd},
        {"source": "fsmill", "target": "fstot",  "value": fs_ytd},
    ]
    # Taller canvas (300 -> 420) to fill more of the page's own leftover
    # space below the two tables above, and bigger text (12 -> 20, the
    # default only ever rendered as ~8px once the SVG's viewBox got
    # stretched to this page's ~667px-wide content column — per direct
    # instruction, sized here for genuine ~12pt legibility instead) — see
    # _sankey_svg's label_font_size doc for how every other text-related
    # constant scales along with it automatically.
    return _sankey_svg(nodes, links, vh=420, label_font_size=16)


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
