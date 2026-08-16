"""
IPT (Inter-Plant Transfer) Status — page 26.

Data source: ipt_table
  (report_month, item, from_plant, to_plant, unit, sort_order, plan, actual)

Columns: Item | From | To | Unit | <Month> Plan/Actual | <Apr-Month> Plan/Actual
Cumulative = SUM across FY months Apr → report month.
Routes shown = union of routes having any record in the FY so far,
so a route transferred only in earlier months still appears.

Item order/icons: every row in ipt_table currently has sort_order=0 (it's a
per-route field, editable in the data-entry grid, but never actually used to
differentiate item order yet), so the SQL's "ORDER BY MIN(sort_order), item"
collapses to plain alphabetical. _ITEM_ORDER below re-sorts the built
`sections` list into process order (use → produced order: Sinter/BF Coke/
Coke Breeze feed the Blast Furnace; Screened Coke is BF Coke's coke-oven
sibling; CC Slabs/Blooms/Billets are continuous-casting semis; HR Coil and
Spade/2Pi/Jackal Slabs are downstream rolled/finished products) rather than
writing real sort_order values into the DB, since that field is per-route
(not per-item) and user-editable — overwriting it here could silently clobber
a future manual edit. An item not in the list (a new one someone starts
transferring) sorts after all known ones, alphabetically among itself, so it
still shows up rather than erroring.
"""
import db
from page_prod_by_process import _sankey_svg

_MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

_ITEM_ORDER = [
    "Sinter", "BF Coke", "Coke Breeze", "Screened Coke",
    "CC Slabs", "CC Blooms", "CC Billets (105 sq mm)",
    "HR Coil", "Spade/ 2Pi / Jackal Slabs",
]
_ITEM_RANK = {name: i for i, name in enumerate(_ITEM_ORDER)}

# Small per-item icon (emoji — needs no image asset, renders identically in
# the PDF export (Chromium) and the web view (React), unlike an <img> tag
# which would need a static asset path reachable by both render paths).
_ITEM_ICON = {
    "Sinter":                    "🪨",
    "BF Coke":                   "⚫",
    "Coke Breeze":                "💨",
    "Screened Coke":              "🔲",
    "CC Slabs":                   "🟫",
    "CC Blooms":                   "🧱",
    "CC Billets (105 sq mm)":      "🪵",
    "HR Coil":                    "🌀",
    "Spade/ 2Pi / Jackal Slabs":   "🔩",
}
_DEFAULT_ICON = "📦"

# Sankey (senders -> receivers) built for these 4 items only — the ones
# explicitly asked for. Reuses page_prod_by_process.py's hand-rolled SVG
# Sankey builder (no chart library — that page's own SVG string is embedded
# verbatim in both the PDF template and the React web view, so a JS-only
# charting lib like recharts, already a frontend dependency, wouldn't render
# in the server-generated PDF; see that module for the full rationale).
_SANKEY_ITEMS = {"Sinter", "BF Coke", "CC Slabs", "CC Blooms"}
_SANKEY_NODE_COLORS = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#5b9bd5", "#e87ba4", "#a5a5a5", "#94a3b8",
]


def _item_sankey_svg(item, routes_for_item, cum_map):
    """Bipartite Sankey (senders in column 0, receivers in column 1) for one
    item, sized by cumulative FY actual (the same figure the table's own
    "cum_actual" column shows) — plan isn't plotted, this illustrates what
    actually moved. A route with no actual yet (nothing reported this FY)
    is simply omitted rather than drawn as a zero-width ribbon.

    side_labels=True (per direct instruction, for legibility): sender labels
    sit to the LEFT of their node, receiver labels to the RIGHT, each
    anchored to its own node's vertical center — rather than
    _sankey_svg's default of every label stacked above its node. Only this
    page opts in; page_prod_by_process.py's own (non-bipartite, multi-stage)
    Sankey is unaffected."""
    froms, tos, links = [], [], []
    unit_label = "T"
    for frm, to, unit in routes_for_item:
        _, ca, _, _ = cum_map.get((item, frm, to), (None, None, None, None))
        if not ca:
            continue
        unit_label = unit or unit_label
        if frm not in froms:
            froms.append(frm)
        if to not in tos:
            tos.append(to)
        links.append({"source": f"from:{frm}", "target": f"to:{to}", "value": ca})
    if not links:
        return None

    nodes = []
    for i, f in enumerate(froms):
        nodes.append({"id": f"from:{f}", "label": f, "column": 0,
                      "color": _SANKEY_NODE_COLORS[i % len(_SANKEY_NODE_COLORS)]})
    for i, t in enumerate(tos):
        nodes.append({"id": f"to:{t}", "label": t, "column": 1,
                      "color": _SANKEY_NODE_COLORS[(i + len(froms)) % len(_SANKEY_NODE_COLORS)]})

    unit_disp = "Rake" if (unit_label or "").strip().lower() == "rake" else "T"
    # Taller than the width alone would suggest — a route list with 3+
    # senders/receivers on one side needs real vertical room for the
    # 2-line, 12pt side labels to stay legibly spaced without crowding the
    # canvas edges.
    return _sankey_svg(nodes, links, vw=560, vh=260, side_labels=True,
                        value_fmt=lambda v: f'{v:,.0f} {unit_disp}')


def _month_label(ym):
    return f"{_MON[int(ym[5:7])]}'{ym[2:4]}"

def _cum_label(months):
    if len(months) == 1:
        return _month_label(months[0])
    return f"{_MON[int(months[0][5:7])]}-{_month_label(months[-1])}"

def _fmt(v):
    return "" if v is None else str(int(round(v)))

def _add_col_rowspans(rows, key):
    """In-place: for consecutive rows sharing the same value under `key`,
    the first row gets f"{key}_rowspan" = run length, the rest get 0 (skip
    the cell entirely — merged into the first row's, per direct
    instruction: "From"/"To" plant cells merge when adjacent rows repeat
    the same plant). Rows are already grouped by item then sorted
    from_plant, to_plant (see the SQL's ORDER BY), so "From" runs are
    always contiguous within an item; "To" runs merge wherever two
    adjacent rows happen to share the same receiver, whichever "From"
    they're under."""
    n = len(rows)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and rows[j + 1][key] == rows[i][key]:
            j += 1
        rows[i][f"{key}_rowspan"] = j - i + 1
        for k in range(i + 1, j + 1):
            rows[k][f"{key}_rowspan"] = 0
        i = j + 1


def generate_ipt(report_month: str) -> dict:
    ytd_months = db.get_ytd_months(report_month)

    conn = db.connect()
    cur  = conn.cursor()
    try:
        ph = ",".join("?" * len(ytd_months))

        # union of routes seen this FY, keeping entry order
        cur.execute(f"""
            SELECT item, from_plant, to_plant, MAX(unit), MIN(sort_order)
            FROM ipt_table
            WHERE report_month IN ({ph})
            GROUP BY item, from_plant, to_plant
            ORDER BY MIN(sort_order), item, from_plant, to_plant
        """, ytd_months)
        routes = cur.fetchall()

        # current-month values
        cur.execute("""
            SELECT item, from_plant, to_plant, plan, actual, plan_tonnage, actual_tonnage
            FROM ipt_table WHERE report_month=?
        """, (report_month,))
        cur_map = {(i, f, t): (p, a, pt, at) for i, f, t, p, a, pt, at in cur.fetchall()}

        # cumulative values (SUM skips NULLs; NULL when every value is NULL)
        cur.execute(f"""
            SELECT item, from_plant, to_plant,
                   SUM(plan), SUM(actual), SUM(plan_tonnage), SUM(actual_tonnage)
            FROM ipt_table
            WHERE report_month IN ({ph})
            GROUP BY item, from_plant, to_plant
        """, ytd_months)
        cum_map = {(i, f, t): (p, a, pt, at) for i, f, t, p, a, pt, at in cur.fetchall()}

        # group routes by item, preserving order of first appearance
        sections, by_item, routes_by_item = [], {}, {}
        for item, frm, to, unit, _ in routes:
            mp, ma, mpt, mat = cur_map.get((item, frm, to), (None, None, None, None))
            cp, ca, cpt, cat = cum_map.get((item, frm, to), (None, None, None, None))
            is_rake = (unit or "").strip().lower() == "rake"
            row = {
                "from": frm, "to": to, "unit": unit,
                "plan": _fmt(mp), "actual": _fmt(ma),
                "cum_plan": _fmt(cp), "cum_actual": _fmt(ca),
                # tonnes equivalent — only meaningful for Rake routes
                "plan_t":       _fmt(mpt) if is_rake else "",
                "actual_t":     _fmt(mat) if is_rake else "",
                "cum_plan_t":   _fmt(cpt) if is_rake else "",
                "cum_actual_t": _fmt(cat) if is_rake else "",
            }
            if item not in by_item:
                by_item[item] = {"item": item, "icon": _ITEM_ICON.get(item, _DEFAULT_ICON), "rows": []}
                sections.append(by_item[item])
                routes_by_item[item] = []
            by_item[item]["rows"].append(row)
            routes_by_item[item].append((frm, to, unit))

        for item in _SANKEY_ITEMS:
            if item in by_item:
                by_item[item]["sankey_svg"] = _item_sankey_svg(item, routes_by_item[item], cum_map)

        for sec in sections:
            _add_col_rowspans(sec["rows"], "from")
            _add_col_rowspans(sec["rows"], "to")

        # Process order (_ITEM_ORDER), unlisted items sorted alphabetically
        # after all known ones — see module docstring.
        sections.sort(key=lambda sec: (_ITEM_RANK.get(sec["item"], len(_ITEM_ORDER)), sec["item"]))

        month_label = _month_label(report_month)
        cum_label = _cum_label(ytd_months)

        return {
            # Dynamic per the selected report month (same month_label/
            # cum_label the header columns below already use), not a fixed
            # FY string — per direct instruction.
            "title": f"IPT Status for {month_label} & {cum_label}",
            "variant": "ipt_status",
            "month_label": month_label,
            "cum_label": cum_label,
            "sections": sections,
        }
    finally:
        conn.close()
