"""
Special Steel — Saleable Steel Composition & Value-Added Share (page 24).

Replaces the old page-24 "Special Steel Performance of SAIL" table — that
content now lives appended below page 23's own ISP table instead (see
main.py's pg==23 handling, which now also sets page["sail_section"] =
generate_special_steel_sail(month); special_steel.html renders it as a
second table on the same physical page). Page 24 itself now shows a 7
(entity) x 3 (period) grid of donut charts:

  Two concentric rings per cell (see the module-docstring paragraph below
  for the current design; superseded an even earlier one-ring design that
  shaded each Finished/Semis slice by special-steel intensity instead of
  drawing Special Steel as its own ring).

  The Finished/Semis split of Special Steel needs special_steel_orders' own `product`
  grouping (see _SEMIS_PRODUCTS) to know how much of a plant's despatched
  Special Steel was itself Finished vs Semis — special_steel_abp_table (the
  Annual ABP Plan column's source) carries no such breakdown, only one
  aggregate figure per plant/month, so the Plan column's ring shows plain
  Finished/Semis with no special-steel shading (see _cell's is_plan branch
  and the page's own footnote about this).

Periods (columns): the current FY's Annual ABP Plan, the report month, and
Apr-report month (YTD) — mirrors the exact three periods
page_special_steel_trend.py's annual/month/till-month charts already use.
Entities (rows): BSP/DSP/RSP/BSL/ISP, SSPs (the ASP+VISL+SSP bundle — see
page_special_steel._SSPS_PLANTS), and SAIL (all 8 plants). 7 rows total.

Each cell (Actual columns) draws TWO separate concentric rings rather than
one shaded ring: an outer ring for Saleable Steel's own Finished/Semis
split (light "regular" colors) and an inner ring for Special Steel's own
Finished/Semis split (full-saturation "special" colors) — per direct
instruction, replacing the single-ring intensity-shaded design below.
Saleable Steel (production) and Special Steel (despatch) are different
physical flows for the same plant (see the footnote further down) and
aren't guaranteed exact subsets of one another, so giving Special Steel
its own full ring avoids implying an exact subset relationship the data
doesn't back up. Both rings start at angle 0 (12 o'clock) and go
Finished-then-Semis clockwise, so the Finished slice's start edge lines up
between the two rings — "drawn matching" per direct instruction — even
though the Finished/Semis boundary itself generally falls at a different
angle in each ring (the two totals have different proportions). The
Annual ABP Plan column still has no Finished/Semis split for its Special
Steel target (see below), so it keeps the single plain ring it always
had — see _nested_donut_svg's has_split branch.

Data sources:
  Saleable Steel (Finished + Saleable Semis) — production_table (actual)
    and production_plan_table (ABP plan), both '000T, scaled to Tonnes
    here to match Special Steel's own native Tonnes unit. SAIL sums all 8
    plants and "Finished Steel" gets the same alias-fallback (SSP/VISL ->
    Saleable Steel when no dedicated Finished Steel row) and, for actuals
    only, the conversion adjustment — db.get_sail_production_actual/_plan/
    _ytd_actual's own established convention, replicated here on a SHARED
    cursor (see _prod_item_sum's docstring for why: those db.py helpers
    each open their own fresh MySQL connection per call, and the ABP
    period needs 12 monthly figures per entity — looping the db.py
    helpers directly would reopen the exact per-call-connection slowdown
    fixed earlier for the coal-blend %import chart).
  Special Steel actual — page_special_steel_trend._sum_actual (Tonnes) for
    the total, plus special_steel_orders.product grouped into Finished/
    Semis (_special_fin_semis_split) for the two actual columns' ring
    shading.
  Special Steel ABP — page_special_steel._get_abp_sum (special_steel_abp_table,
    Tonnes) — one aggregate figure, no Finished/Semis split available.

Saleable Steel here is production (production_table/production_plan_table),
while Special Steel is despatch (special_steel_orders / Salem's own
despatch figure) for the Month/YTD columns — two different physical flows
for the same plant, not necessarily equal tonnage even before the
Finished/Semis split. Called out in the page's own footnote rather than
buried only in this docstring, since it materially affects how the ring's
proportions should be read.
"""
import math
import datetime as _dt
import db
from constants import ALL_PLANTS
from db import _fs_alias_sum, _sail_conversion_actual
from page_special_steel import _get_abp_sum, _SSPS_PLANTS
from page_special_steel_trend import _sum_actual

_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_ABP_ENTITIES = _PLANTS + ["SSPs"]   # special_steel_abp_table's own plant set
_ROWS = _PLANTS + ["SSPs", "SAIL"]

# special_steel_orders.product values that belong to a plant's Semis group —
# mirrors page_special_steel.py's own per-plant groupings (_gen_bsp/_gen_dsp/
# _gen_rsp/_gen_bsl/_gen_isp), but as raw `product` values rather than the
# Python-side display group labels: BSP/BSL/DSP/RSP's group label IS the
# stored `product` value (confirmed by _build_group's own `product=?`
# lookup), but ISP's 4 displayed mill groups are each built from 1-2 RAW
# mill-name `product` values (see _gen_isp's mill_groups) — "Semis" is never
# itself a stored ISP `product`, only "150 BLT"/"200 BLM" are.
_SEMIS_PRODUCTS = {
    "BSP": {"Semis"},
    "DSP": {"CC BILLET", "CC Bloom", "CC Round", "ASP"},
    "RSP": set(),
    "BSL": {"SLAB"},
    "ISP": {"150 BLT", "200 BLM"},
}

# Full-saturation swatch draws the inner (Special Steel) ring, the lighter
# tint of the same color draws the outer (Saleable Steel) ring — "same
# color, more intense for the special-steel ring" per direct instruction.
_FINISHED_COLOR = "#4472C4"
_FINISHED_LIGHT = "#B4C7E7"
_SEMIS_COLOR = "#ED7D31"
_SEMIS_LIGHT = "#F8CBAD"


# ── data ──────────────────────────────────────────────────────────────────

def _prod_item_sum(cur, months: list, entity: str, item: str, is_plan: bool = False):
    """Sum of `item` ('Finished Steel'/'Saleable Semis') over `months`, in
    Tonnes ('000T stored -> x1000) — on the CALLER's shared cursor (see
    module docstring for why this doesn't just call
    db.get_sail_production_actual/_plan/_ytd_actual directly for every
    entity: those each open their own connection per call, and the ABP
    period needs one call per fy month).

    'Saleable Semis' additionally folds in a residual for any of ASP/VISL/
    SSP present in `plants` (that plant's own Saleable Steel minus Finished
    Steel) — confirmed against production_table/production_plan_table that
    none of the three ever carries a 'Saleable Semis' row of its own, so a
    plain item_name='Saleable Semis' sum silently shows them (and SAIL/SSPs,
    which both include them) as 100% Finished / 0% Semis. See
    _ssps_semis_residual's docstring for why the residual is computed this
    way rather than by summing a 'Saleable Semis' row that doesn't exist."""
    table = "production_plan_table" if is_plan else "production_table"
    if entity == "SAIL":
        plants = ALL_PLANTS
    elif entity == "SSPs":
        plants = list(_SSPS_PLANTS)
    else:
        plants = [entity]

    if item == "Finished Steel":
        total, found = 0.0, False
        for m in months:
            v = _fs_alias_sum(cur, table, m, plants)
            c = None if (is_plan or entity != "SAIL") else _sail_conversion_actual(cur, m)
            if v is not None or c is not None:
                total += (v or 0.0) + (c or 0.0)
                found = True
        return (total * 1000) if found else None

    direct_plants = [p for p in plants if item != "Saleable Semis" or p not in _SSPS_PLANTS]
    total, found = 0.0, False
    if direct_plants:
        ph_m = ",".join("?" * len(months))
        ph_p = ",".join("?" * len(direct_plants))
        cur.execute(f"""
            SELECT COALESCE(SUM(month_actual),0), COUNT(*)
            FROM {table}
            WHERE report_month IN ({ph_m}) AND plant_name IN ({ph_p}) AND item_name=?
        """, (*months, *direct_plants, item))
        t, c = cur.fetchone()
        if c > 0:
            total += t
            found = True

    if item == "Saleable Semis":
        ssps_plants = [p for p in plants if p in _SSPS_PLANTS]
        if ssps_plants:
            total += _ssps_semis_residual(cur, table, months, ssps_plants)
            found = True

    return (total * 1000) if found else None


def _ssps_semis_residual(cur, table: str, months: list, plants: list) -> float:
    """Saleable Steel minus Finished Steel, summed over `plants` (a subset
    of ASP/VISL/SSP) and `months`, in '000T (the caller applies the x1000
    Tonnes conversion). None of the three ever record a 'Saleable Semis'
    row (verified against both production_table and
    production_plan_table), so their Semis has to be derived from the two
    totals they DO record instead — "plant wise saleable-finished steel to
    get their semis" per direct instruction. Finished Steel goes through
    _fs_alias_sum (SSP/VISL fall back to that same month's Saleable Steel
    there when no dedicated Finished Steel row exists — the residual is
    then correctly ~0 for that plant/month, not negative). Clamped at 0
    overall so a data gap in one table/month doesn't flip the sign."""
    ph_m = ",".join("?" * len(months))
    ph_p = ",".join("?" * len(plants))
    cur.execute(f"""
        SELECT COALESCE(SUM(month_actual),0)
        FROM {table}
        WHERE report_month IN ({ph_m}) AND plant_name IN ({ph_p}) AND item_name='Saleable Steel'
    """, (*months, *plants))
    saleable = cur.fetchone()[0] or 0.0

    finished = 0.0
    for m in months:
        v = _fs_alias_sum(cur, table, m, plants)
        finished += v or 0.0

    return max(saleable - finished, 0.0)


def _abp_special_sum(cur, fy_months: list, entity: str):
    """Special Steel FY ABP target, Tonnes — special_steel_abp_table has no
    'SAIL' row of its own (see generate_special_steel_sail's sail_abp_fy),
    so SAIL sums the 6 real ABP entities."""
    if entity == "SAIL":
        total, any_ = 0.0, False
        for p in _ABP_ENTITIES:
            v = _get_abp_sum(cur, fy_months, p)
            if v:
                total += v
                any_ = True
        return total if any_ else None
    return _get_abp_sum(cur, fy_months, entity)


def _special_fin_semis_split(cur, months: list, entity: str):
    """(special_finished_T, special_semis_T) — Special Steel actual_despatch
    split by whether its `product` group is Semis (per _SEMIS_PRODUCTS) or
    Finished (everything else), for the given months. Always returns real
    numbers (0.0 for a side with no matching rows), not None — callers
    already know from _sum_actual whether there was any Special Steel data
    at all this period.

    SSPs (ASP+VISL+SSP bundle) has no special_steel_orders rows of its own
    (see page_special_steel._ssps_special_steel) — its whole Special Steel
    figure is attributed to Finished, since ASP/VISL/SSP's own Saleable
    Steel is ~100% Finished Steel (no Saleable Semis rows at all for any of
    the three, per production_table). SAIL sums the 5 real plants' own
    splits plus SSPs' Finished-only figure."""
    if entity == "SAIL":
        fin_total, semis_total = 0.0, 0.0
        for p in _PLANTS:
            f, s = _special_fin_semis_split(cur, months, p)
            fin_total += f
            semis_total += s
        ssps_qty, has = _sum_actual(cur, months, "SSPs")
        if has:
            fin_total += ssps_qty
        return fin_total, semis_total
    if entity == "SSPs":
        qty, has = _sum_actual(cur, months, "SSPs")
        return (qty if has else 0.0), 0.0

    semis_products = _SEMIS_PRODUCTS.get(entity, set())
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT product, COALESCE(SUM(actual_despatch),0)
        FROM special_steel_orders
        WHERE report_month IN ({ph}) AND plant_name=?
        GROUP BY product
    """, (*months, entity))
    fin, semis = 0.0, 0.0
    for product, qty in cur.fetchall():
        if product in semis_products:
            semis += qty or 0.0
        else:
            fin += qty or 0.0
    return fin, semis


def _fmt_int(v):
    return f"{v:,.0f}" if v is not None else "N/A"


def _pct(v, total):
    return f"{v / total * 100:.0f}%" if (v is not None and total) else "—"


def _cell(cur, months: list, entity: str, is_plan: bool) -> dict:
    fin = _prod_item_sum(cur, months, entity, "Finished Steel", is_plan)
    semis = _prod_item_sum(cur, months, entity, "Saleable Semis", is_plan)
    total = (fin or 0) + (semis or 0)

    special_fin = special_semis = None
    if is_plan:
        special = _abp_special_sum(cur, months, entity)
    else:
        special, has = _sum_actual(cur, months, entity)
        if not has:
            special = None
        else:
            special_fin, special_semis = _special_fin_semis_split(cur, months, entity)

    # Each qty gets its own "(NN% of SS)" line underneath it — per direct
    # instruction, matching the reference mock-up's line layout rather than
    # the old single-line "label: qty (pct)" format ("SS"/"FS" abbreviate
    # Saleable Steel/Finished Steel, again per direct instruction, to keep
    # these lines short enough not to wrap). Spl. FS additionally gets a
    # SECOND pct line, against Finished Steel itself (not Saleable Steel) —
    # "additional % of special Finished steel in total finished steel" per
    # direct instruction — since that's the ratio that shows how
    # value-added-heavy a plant's own Finished Steel mix is. Only computed
    # when the Fin/Semis split is available (see _special_fin_semis_split's
    # docstring for why the Annual ABP Plan column never has one): mixing
    # an aggregate Plan Special figure (Finished+Semis together) into a
    # Finished-Steel-only denominator would misstate the ratio.
    if special_fin is not None:
        spl_fin_txt = f"Spl. FS: {_fmt_int(special_fin)} T"
        spl_fin_pct_txt = f"({_pct(special_fin, total)} of SS)"
        spl_fin_pct_of_fin_txt = f"({_pct(special_fin, fin)} of FS)"
        # None (not "Spl. Semis: 0 T (0% of SS)") whenever Special Semis is
        # structurally always zero for this entity — RSP (semis is None:
        # _SEMIS_PRODUCTS["RSP"] is empty, so every despatched product
        # counts as Finished) and SSPs (_special_fin_semis_split's SSPs
        # branch always returns 0 for special_semis: SSPs has no
        # special_steel_orders rows of its own, so its whole Special Steel
        # figure is attributed to Finished) — showing a permanently-zero
        # Spl. Semis line for an entity that can never have one is just
        # noise, per direct instruction.
        if semis is not None and entity != "SSPs":
            spl_semis_txt = f"Spl. Semis: {_fmt_int(special_semis)} T"
            spl_semis_pct_txt = f"({_pct(special_semis, total)} of SS)"
        else:
            spl_semis_txt = None
            spl_semis_pct_txt = None
    else:
        spl_fin_txt = f"Spl: {_fmt_int(special)} T"
        spl_fin_pct_txt = f"({_pct(special, total)} of SS)"
        spl_fin_pct_of_fin_txt = None
        spl_semis_txt = None
        spl_semis_pct_txt = None

    return {
        "svg": _nested_donut_svg(fin, semis, special_fin, special_semis),
        "total_txt": _fmt_int(total) if total else "N/A",
        "fin_txt": f"FS: {_fmt_int(fin)} T",
        "fin_pct_txt": f"({_pct(fin, total)} of SS)",
        # None (not "Semis: N/A (—)") when this entity structurally has no
        # Semis at all — RSP, in both production_table and
        # production_plan_table, has never once carried a 'Saleable Semis'
        # row (unlike SSPs, now covered by _prod_item_sum's own residual —
        # see that function's docstring) — per direct instruction, the line
        # is omitted by special_steel_donut.html rather than shown as N/A.
        "semis_txt": f"Semis: {_fmt_int(semis)} T" if semis is not None else None,
        "semis_pct_txt": f"({_pct(semis, total)} of SS)" if semis is not None else None,
        "spl_fin_txt": spl_fin_txt,
        "spl_fin_pct_txt": spl_fin_pct_txt,
        "spl_fin_pct_of_fin_txt": spl_fin_pct_of_fin_txt,
        "spl_semis_txt": spl_semis_txt,
        "spl_semis_pct_txt": spl_semis_pct_txt,
    }


# ── SVG: two concentric rings — outer Saleable, inner Special ──────────────

def _nested_donut_svg(fin_qty, semis_qty, special_fin_qty, special_semis_qty,
                       vw: float = 100, vh: float = 100) -> str:
    """Outer ring = Saleable Steel's own Finished/Semis split (light
    "regular" colors); inner ring = Special Steel's own Finished/Semis
    split (full-saturation "special" colors) — two independent 100%
    breakdowns, not one ring shaded by a sub-portion, per direct
    instruction (see module docstring for why). Both rings start at angle
    0 and go Finished-then-Semis clockwise, so the Finished slice's start
    edge lines up between the two rings ("drawn matching") even though
    each ring's own Finished/Semis boundary angle differs (the two totals
    have different proportions).

    special_fin_qty/special_semis_qty are None together when no
    per-product-group split is available (the Annual ABP Plan column —
    see module docstring); only the single outer-sized ring is drawn then,
    in full-saturation colors since there's nothing to contrast it
    against — the page's pre-existing plain-ring fallback."""
    total = (fin_qty or 0) + (semis_qty or 0)
    has_split = special_fin_qty is not None or special_semis_qty is not None
    cx, cy = vw / 2, vh / 2

    def polar(r, deg):
        a = math.radians(deg)
        return cx + r * math.sin(a), cy - r * math.cos(a)

    def ring_slice(r_o, r_i, a0, a1, color):
        large = 1 if (a1 - a0) > 180 else 0
        x1o, y1o = polar(r_o, a0); x2o, y2o = polar(r_o, a1)
        x1i, y1i = polar(r_i, a1); x2i, y2i = polar(r_i, a0)
        path = (f'M {x1o:.2f} {y1o:.2f} A {r_o} {r_o} 0 {large} 1 {x2o:.2f} {y2o:.2f} '
                f'L {x1i:.2f} {y1i:.2f} A {r_i} {r_i} 0 {large} 0 {x2i:.2f} {y2i:.2f} Z')
        return f'<path d="{path}" fill="{color}" stroke="#ffffff" stroke-width="0.6"/>'

    def ring(r_o, r_i, slices):
        # A share of exactly 1.0 (e.g. RSP has no Semis, or a period with no
        # Special Steel at all) can't be drawn as a single A-arc — start and
        # end points coincide, which is degenerate for the sweep-flag math
        # above. Drawn as a plain stroked circle instead whenever only one
        # slice is actually non-zero. Both rings always start at angle 0
        # (the loop's initial a=0.0) so the Finished slice's start edge
        # matches between the outer and inner ring.
        out = []
        active = [(s, c) for s, c in slices if s and s > 0]
        if not active:
            return out
        if len(active) == 1 and active[0][0] >= 0.999:
            _, color = active[0]
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{(r_o + r_i) / 2:.2f}" '
                       f'fill="none" stroke="{color}" stroke-width="{r_o - r_i}"/>')
            return out
        a = 0.0
        for share, color in active:
            sweep = share * 360.0
            out.append(ring_slice(r_o, r_i, a, a + sweep, color))
            a += sweep
        return out

    def na_ring(r_o):
        return (f'<circle cx="{cx}" cy="{cy}" r="{r_o}" fill="none" '
                f'stroke="#cbd5e1" stroke-width="1" stroke-dasharray="3,2"/>')

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']

    if total <= 0:
        lines.append(na_ring(46.0))
        lines.append("</svg>")
        return "\n".join(lines)

    fin_sh = (fin_qty or 0) / total
    semis_sh = (semis_qty or 0) / total

    if not has_split:
        # Plan column: no Special Steel Finished/Semis split available —
        # single plain ring, same as before this page grew a second ring.
        lines.extend(ring(46.0, 26.0, [(fin_sh, _FINISHED_COLOR), (semis_sh, _SEMIS_COLOR)]))
        lines.append("</svg>")
        return "\n".join(lines)

    # Outer ring: Saleable Steel, Finished/Semis, light "regular" colors.
    lines.extend(ring(46.0, 33.0, [(fin_sh, _FINISHED_LIGHT), (semis_sh, _SEMIS_LIGHT)]))

    # Inner ring: Special Steel, Finished/Semis, full-saturation "special"
    # colors — its OWN 100% (special_fin+special_semis), not a share of the
    # Saleable total, since despatch and production don't share a base.
    special_total = (special_fin_qty or 0) + (special_semis_qty or 0)
    if special_total > 0:
        sfin_sh = (special_fin_qty or 0) / special_total
        ssemis_sh = (special_semis_qty or 0) / special_total
        lines.extend(ring(29.0, 16.0, [(sfin_sh, _FINISHED_COLOR), (ssemis_sh, _SEMIS_COLOR)]))
    else:
        lines.append(na_ring(29.0))

    lines.append("</svg>")
    return "\n".join(lines)


# ── public API ──────────────────────────────────────────────────────────────

def generate_special_steel_donut(report_month: str) -> dict:
    fy_months = db.get_fy_months(report_month)
    ytd_months = db.get_ytd_months(report_month)

    conn = db.connect()
    cur = conn.cursor()
    try:
        rows = []
        for ent in _ROWS:
            rows.append({
                "label": ent,
                "plan":  _cell(cur, fy_months, ent, is_plan=True),
                "month": _cell(cur, [report_month], ent, is_plan=False),
                "ytd":   _cell(cur, ytd_months, ent, is_plan=False),
            })
    finally:
        conn.close()

    dt = _dt.datetime.strptime(report_month, "%Y-%m")
    month_label = dt.strftime("%b'%y")
    cum_label = (_dt.datetime.strptime(ytd_months[0], "%Y-%m").strftime("%b'%y") + "-" + month_label
                 if len(ytd_months) > 1 else month_label)

    return {
        "type": "special_steel_donut",
        "title": "Special Steel — Saleable Steel Composition & Value-Added Share",
        "fy_label": db.get_fy_for_month(report_month)[2:],
        "month_label": month_label,
        "cum_label": cum_label,
        "rows": rows,
    }
