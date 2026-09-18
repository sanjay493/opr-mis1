"""
Special Steel — Saleable Steel Composition & Value-Added Share in Despatch
(page 24).

Replaces the old page-24 "Special Steel Performance of SAIL" table — that
content now lives appended below page 23's own ISP table instead (see
main.py's pg==23 handling, which now also sets page["sail_section"] =
generate_special_steel_sail(month); special_steel.html renders it as a
second table on the same physical page). Page 24 itself is a plain figures
table, no charts (an earlier two-ring donut design was dropped per direct
instruction — see git history): Plant | Metric | Total | Annual ABP Plan |
Month (Actual) | YTD (Actual), with "Plant" a merged cell spanning every
row for that entity and, within each of the two Metric/Total column pairs
below, a "Total" cell ALSO merged (rowspanned) down its own 2-row block —
per direct instruction matching a reference layout, to cut the row count
(and so the table's overall height, making room for the bubble chart on
the same page) by moving SS/Spl. SS beside their own detail rows instead
of under them in a dedicated full-width row.

Two blocks per entity (see _block_rows), each a detail column (1-2 rows)
plus one Total column rowspanned across them. The Annual ABP Plan column
stays on PRODUCTION data throughout (no despatch plan exists, and the
plan's own Finished/Semis distribution is the same either way); the Month
and YTD (Actual) columns are DESPATCH-based throughout, per direct
instruction — see _raw_cell/_desp_item_sum:
  Saleable Steel block — detail rows FS then Semis (Semis omitted entirely
                  for an entity that structurally never carries a Semis
                  despatch/production row, e.g. RSP — see _prod_item_sum's
                  and _desp_item_sum's docstrings — rather than shown as a
                  permanent blank row), each "% of SS"; Total column is SS
                  itself (Plan: FS+Semis production; Actual: the plant's
                  own Saleable Steel DESPATCH figure, with FS derived as
                  SS-minus-Semis), no "% of" line (it IS the 100% base
                  every other row's percentage is against).
  Despatch block  — detail rows Spl. FS then Spl. Semis (Spl. Semis
                  omitted, like the Semis row, for an entity structurally
                  incapable of having one: RSP — no Semis products at all,
                  _SEMIS_PRODUCTS["RSP"] is empty — and SSPs — no
                  special_steel_orders rows of its own, its whole Special
                  Steel figure is attributed to Finished, see
                  _special_fin_semis_split's docstring). Spl. FS carries
                  "% of SS" AND "% of FS" (value-added intensity of the
                  plant's own Finished Steel mix) on the SAME line,
                  separated by "||" (_amt_dual_pct). Blank cell (not
                  "N/A") wherever the Fin/Semis split isn't available for
                  that period — always true for the Annual ABP Plan
                  column, since special_steel_abp_table carries only one
                  aggregate figure per plant/month with no Finished/Semis
                  breakdown. Total column is Spl. SS (Spl. FS + Spl.
                  Semis, or the Plan column's own single aggregate figure,
                  which is what this column alone carries there); no
                  "% of" line, per direct instruction (unlike the SS
                  column, this total draws no percentage of its own since
                  despatch isn't a slice of the production base).

Periods (columns): the current FY's Annual ABP Plan, the report month, and
Apr-report month (YTD) — mirrors the exact three periods
page_special_steel_trend.py's annual/month/till-month charts already use.
Entities (rows): BSP/DSP/RSP/BSL/ISP, SSP (Salem Steel Plant — shown under
the internal entity key "SSPs" throughout this module, matching
page_special_steel._SSPS_PLANTS/special_steel_abp_table's own stored key,
but displayed as "SSP" per _DISPLAY_LABEL and resolved to SSP alone, not
the wider ASP/VISL/SSP bundle, for every figure computed here — only Salem
itself produces Special Steel, so ASP/VISL's ordinary-steel production has
no place in a row now labeled as SSP's own), and SAIL (all 8 plants). 7
entities.

Saleable Steel (production) and Special Steel (despatch) are different
physical flows for the same plant and aren't guaranteed exact subsets of
one another — every Spl.-row "% of SS" line is against the production
total only for a value-added-share reading, not because despatch is a
subset of production.

Below the table, a bubble chart plots each plant's till-month (YTD)
value-addition positioning (_bubble_data/_bubble_chart_svg) — per direct
instruction, replacing the table's old footnote paragraph:
  X = Finished Steel Share = Finished Steel / Saleable Steel x 100.
  Y = Special Finished Steel Share = Special Finished Steel /
      Saleable Steel x 100 (i.e. the Spl. FS row's own "% of SS" figure).
  size = Saleable Steel production (Tonnes), sqrt-scaled between a fixed
      min/max radius so the largest plant doesn't swamp the smallest.
Dashed quadrant dividers sit at the mean X/mean Y of the plotted plants
(not a fixed 50%, since neither share clusters near the middle) with
"High/Low Value Addition" labels in the upper/lower right, matching a
reference mock-up. SAIL is excluded (it's the sum of the other rows, not
a peer plant to compare); SSP is included as its own point (shown under
the "SSPs" entity key — see the module's "Entities" note above), same as
the table above. A plant with no YTD despatch data at all is silently
dropped from the plot (nothing meaningful to place at either axis) rather
than plotted at a misleading 0.

Data sources:
  Saleable Steel — Annual ABP Plan: production_plan_table (Finished Steel +
    Saleable Semis), '000T, scaled to Tonnes here to match Special Steel's
    own native Tonnes unit. SAIL sums all 8 plants and "Finished Steel"
    gets the same alias-fallback (SSP/VISL -> Saleable Steel when no
    dedicated Finished Steel row) db.get_sail_production_plan itself uses,
    replicated here on a SHARED cursor (see _prod_item_sum's docstring for
    why: those db.py helpers each open their own fresh MySQL connection
    per call, and the ABP period needs 12 monthly figures per entity —
    looping the db.py helpers directly would reopen the exact per-call-
    connection slowdown fixed earlier for the coal-blend %import chart).
    Month/YTD (Actual): production_table's own 'Saleable Steel Despatch'/
    'Semis Despatch' items (_desp_item_sum) — no alias/conversion handling
    needed there (see that function's docstring; the inter-plant
    conversion adjustment is production-actual-specific and no longer
    reachable from this page now that Actual periods are despatch-based).
  Special Steel actual — page_special_steel_trend._sum_actual (Tonnes) for
    the total, plus special_steel_orders.product grouped into Finished/
    Semis (_special_fin_semis_split) for the Spl. FS/Spl. Semis rows.
  Special Steel ABP — page_special_steel._get_abp_sum (special_steel_abp_table,
    Tonnes) — one aggregate figure, no Finished/Semis split available.

Saleable Steel and Special Steel are now both DESPATCH for the Month/YTD
(Actual) columns (Saleable Steel Despatch / Semis Despatch vs.
special_steel_orders.actual_despatch) — the same physical flow, so every
"% of SS"/"% of FS" figure and the bubble chart's X/Y/size all sit on one
consistent despatch base. The Annual ABP Plan column alone stays on
PRODUCTION (production_plan_table) throughout, per direct instruction: no
despatch plan data exists, and Saleable Steel's planned Finished/Semis
distribution is taken to be the same whichever side it's read from.
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

# Display-only rename: the internal entity key "SSPs" (matching
# _SSPS_PLANTS/special_steel_abp_table's own stored key — left unrenamed
# throughout this module to avoid touching either) shows on the page as
# "SSP" instead, per direct instruction — only Salem Steel Plant itself
# produces Special Steel among ASP/VISL/SSP (see _prod_item_sum/
# _desp_item_sum's own entity=="SSPs" branch below, changed to resolve to
# SSP alone rather than the 3-plant bundle for exactly that reason), so the
# row is now SSP's own figures throughout and the old plural/bundle label
# would be misleading.
_DISPLAY_LABEL = {"SSPs": "SSP"}

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

# ── data ──────────────────────────────────────────────────────────────────

def _prod_item_sum(cur, months: list, entity: str, item: str, is_plan: bool = False):
    """Sum of `item` ('Finished Steel'/'Saleable Semis') over `months`, in
    Tonnes ('000T stored -> x1000) — on the CALLER's shared cursor (see
    module docstring for why this doesn't just call
    db.get_sail_production_actual/_plan/_ytd_actual directly for every
    entity: those each open their own connection per call, and the ABP
    period needs one call per fy month).

    'Saleable Semis' additionally folds in a residual for ASP/VISL/SSP
    present in `plants` (that plant's own Saleable Steel minus Finished
    Steel) — confirmed against production_table/production_plan_table that
    none of the three ever carries a 'Saleable Semis' row of its own, so a
    plain item_name='Saleable Semis' sum silently shows them (and SAIL,
    which includes them) as 100% Finished / 0% Semis. See
    _ssps_semis_residual's docstring for why the residual is computed this
    way rather than by summing a 'Saleable Semis' row that doesn't exist.

    entity=="SSPs" resolves to SSP alone, not the full ASP/VISL/SSP bundle
    (_SSPS_PLANTS) — per direct instruction, this page's "SSP" row (see
    _DISPLAY_LABEL) is Salem Steel Plant's own figures only: it's the only
    one of the three that actually produces Special Steel, so bundling
    ASP/VISL's ordinary-steel production into a row now labeled "SSP" would
    overstate it and mismatch the despatch-side Spl. FS/Spl. Semis figures
    below (_special_fin_semis_split), which were already SSP-only."""
    table = "production_plan_table" if is_plan else "production_table"
    if entity == "SAIL":
        plants = ALL_PLANTS
    elif entity == "SSPs":
        plants = ["SSP"]
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


def _desp_item_sum(cur, months: list, entity: str, item: str):
    """Sum of `item` ('Saleable Steel Despatch'/'Semis Despatch') over
    `months`, in Tonnes ('000T stored -> x1000) — the despatch-side
    counterpart to _prod_item_sum's PRODUCTION-side sum, used for every
    Actual (Month/YTD) period's FS/Semis/SS figures per direct instruction
    (the Annual ABP Plan column keeps using _prod_item_sum/production
    tables unchanged, since no despatch plan data exists and the plan's
    Saleable Steel distribution is the same whichever side it's read from).

    Same plants-per-entity resolution as _prod_item_sum (SAIL -> all 8
    plants, SSPs -> SSP alone, else -> the one plant) but no Finished-Steel
    alias/conversion handling — those are production-table-specific
    mechanisms (SSP/VISL's Finished Steel alias, SAIL's inter-plant
    conversion adjustment) that don't apply to despatch, and aren't needed
    here anyway: 'Semis Despatch' simply doesn't exist for SSP/VISL/RSP
    (see module's _SEMIS_PRODUCTS), so _raw_cell's total-minus-semis
    derivation of Finished Despatch already comes out as 100% Finished for
    them with no alias needed."""
    if entity == "SAIL":
        plants = ALL_PLANTS
    elif entity == "SSPs":
        plants = ["SSP"]
    else:
        plants = [entity]

    ph_m = ",".join("?" * len(months))
    ph_p = ",".join("?" * len(plants))
    cur.execute(f"""
        SELECT COALESCE(SUM(month_actual),0), COUNT(*)
        FROM production_table
        WHERE report_month IN ({ph_m}) AND plant_name IN ({ph_p}) AND item_name=?
    """, (*months, *plants, item))
    t, c = cur.fetchone()
    return (t * 1000) if c > 0 else None


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


def _amt_pct(v, total, unit="SS"):
    return f"{_fmt_int(v)} ({_pct(v, total)} of {unit})"


def _amt_dual_pct(v, total_a, unit_a, total_b, unit_b):
    return f"{_fmt_int(v)} ({_pct(v, total_a)} of {unit_a} || {_pct(v, total_b)} of {unit_b})"


def _raw_cell(cur, months: list, entity: str, is_plan: bool) -> dict:
    """Numeric-only figures for one entity/period — the per-period building
    block for generate_special_steel_donut's metric rows (see module
    docstring). `spl_fin`/`spl_semis` are None together whenever no
    Fin/Semis split is available for Special Steel this period (always
    true for the Annual ABP Plan column; also true for an Actual period
    with no despatch at all); `spl_total` is spl_fin+spl_semis when the
    split is known, else the Plan column's own single aggregate figure.

    Plan period: `total`/`fin`/`semis` are Saleable Steel PRODUCTION plan
    (fin+semis summed from production_plan_table) — unchanged, per direct
    instruction, since no despatch plan data exists and the plan's own
    Finished/Semis distribution is the same whichever side it's read from.
    Actual period (Month/YTD): `total` is the plant's Saleable Steel
    DESPATCH itself (not a sum of fin+semis — the more reliably-reported
    figure), and `fin` is derived as total-minus-semis so Spl. FS's "% of
    SS"/"% of FS" (and the bubble chart's X/Y/size) all land on the same
    despatch-side base as Special Steel's own despatch figure."""
    if is_plan:
        fin = _prod_item_sum(cur, months, entity, "Finished Steel", is_plan=True)
        semis = _prod_item_sum(cur, months, entity, "Saleable Semis", is_plan=True)
        total = (fin or 0) + (semis or 0)
    else:
        total = _desp_item_sum(cur, months, entity, "Saleable Steel Despatch")
        semis = _desp_item_sum(cur, months, entity, "Semis Despatch")
        fin = (total - (semis or 0)) if total is not None else None

    spl_fin = spl_semis = None
    if is_plan:
        spl_total = _abp_special_sum(cur, months, entity)
    else:
        spl_total, has = _sum_actual(cur, months, entity)
        if not has:
            spl_total = None
        else:
            spl_fin, spl_semis = _special_fin_semis_split(cur, months, entity)
            spl_total = spl_fin + spl_semis

    return {"fin": fin, "semis": semis, "total": total,
            "spl_fin": spl_fin, "spl_semis": spl_semis, "spl_total": spl_total}


def _block_rows(periods: tuple, detail_defs: list, total_label: str, total_fn, special: bool,
                 emphasize: frozenset = frozenset()) -> list:
    """One physical table row per (label, cells_fn) in `detail_defs`, all
    sharing a single "total" column (total_label/total_fn) that's rowspanned
    down the whole block — see generate_special_steel_donut's module
    docstring: this is what lets e.g. FS+Semis+SS collapse from 3 full-width
    rows into 2, with SS moved beside them rather than under them. Only the
    first row of the block carries "total_cells" (non-None) — the template
    renders the Total <td>s (with rowspan=len(detail_defs)) on that row only
    and skips them on the rest, exactly like the Plant column's own
    rowspan.

    `emphasize` names detail rows (by label) whose own value cells should
    render bold — currently just Spl. FS, per direct instruction, since
    it's the page's core value-added figure ("596,744 (78% of SS || 102%
    of FS)"-style lines) and the rest are supporting context."""
    n = len(detail_defs)
    total_cells = [total_fn(d) for d in periods]
    rows = []
    for i, (label, cells_fn) in enumerate(detail_defs):
        rows.append({
            "metric_label": label,
            "cells": [cells_fn(d) for d in periods],
            "special": special,
            "emphasis": label in emphasize,
            "is_block_first": i == 0,
            "block_span": n,
            "total_label": total_label if i == 0 else None,
            "total_cells": total_cells if i == 0 else None,
        })
    return rows


def _entity_metrics(cur, entity: str, fy_months: list, month: str, ytd_months: list) -> dict:
    plan_d = _raw_cell(cur, fy_months, entity, is_plan=True)
    month_d = _raw_cell(cur, [month], entity, is_plan=False)
    ytd_d = _raw_cell(cur, ytd_months, entity, is_plan=False)
    periods = (plan_d, month_d, ytd_d)

    # Row shown at all only when at least one period actually carries the
    # figure — Semis is entity-structural (RSP never has a Saleable Semis
    # production row, in either production_table or
    # production_plan_table — see _prod_item_sum's docstring), so this is
    # equivalent to an entity-level flag despite being computed from the
    # three periods. Spl. Semis piggybacks on the same flag (an entity that
    # never despatches Semis-grouped product also never produces Semis
    # Saleable Steel) and additionally excludes SSPs (see
    # _special_fin_semis_split's docstring: its whole Special Steel figure
    # is attributed to Finished by construction, never Semis).
    show_semis = any(d["semis"] is not None for d in periods)
    show_spl_semis = show_semis and entity != "SSPs"

    prod_defs = [("FS", lambda d: [_amt_pct(d["fin"], d["total"])])]
    if show_semis:
        prod_defs.append(("Semis", lambda d: [_amt_pct(d["semis"], d["total"])] if d["semis"] is not None else []))
    prod_rows = _block_rows(
        periods, prod_defs, "SS",
        lambda d: [f"{_fmt_int(d['total']) if d['total'] else 'N/A'}"],
        special=False,
    )

    despatch_defs = [("Spl. FS", lambda d: [_amt_dual_pct(d["spl_fin"], d["total"], "SS", d["fin"], "FS")]
                      if d["spl_fin"] is not None else [])]
    if show_spl_semis:
        despatch_defs.append(("Spl. Semis", lambda d: [_amt_pct(d["spl_semis"], d["total"])]
                               if d["spl_semis"] is not None else []))
    despatch_rows = _block_rows(
        periods, despatch_defs, "Spl. SS",
        lambda d: [f"{_fmt_int(d['spl_total'])}"],
        special=True,
        emphasize=frozenset({"Spl. FS"}),
    )

    rows = prod_rows + despatch_rows
    for i, row in enumerate(rows):
        row["is_entity_first"] = (i == 0)

    return {"label": _DISPLAY_LABEL.get(entity, entity), "rowspan": len(rows), "rows": rows}


# ── bubble chart: till-month (YTD) value-addition positioning ──────────────

_BUBBLE_COLORS = {
    "BSP": "#4472C4",
    "DSP": "#70AD47",
    "RSP": "#7030A0",
    "BSL": "#ED7D31",
    "ISP": "#FFC000",
    "SSPs": "#00B0B9",
}


def _bubble_data(cur, ytd_months: list) -> list:
    """One point per plant (SAIL excluded — it's the sum of these rows, not
    a peer to compare) for the till-month bubble chart: X = Finished Steel
    Share of Saleable Steel DESPATCH, Y = Special Finished Steel Share of
    Saleable Steel Despatch (the Spl. FS row's own "% of SS" figure), size
    = Saleable Steel Despatch. A plant with no YTD Special Steel despatch
    at all (spl_fin is None) or no Saleable Steel despatch is dropped
    rather than plotted at a misleading 0."""
    points = []
    for ent in _PLANTS + ["SSPs"]:
        d = _raw_cell(cur, ytd_months, ent, is_plan=False)
        if not d["total"] or d["spl_fin"] is None:
            continue
        points.append({
            "label": _DISPLAY_LABEL.get(ent, ent),
            "x": (d["fin"] or 0) / d["total"] * 100,
            "y": d["spl_fin"] / d["total"] * 100,
            "size": d["total"],
            "color": _BUBBLE_COLORS.get(ent, "#6b7280"),
        })
    return points


def _bubble_chart_svg(points: list, vw: float = 1000, vh: float = 600) -> str:
    """Quadrant bubble chart matching a reference mock-up: plain L-shaped
    axes (no box) with 0/20/40/60/80/100% tick marks on X and 6 even ticks
    up to y_max on Y, dashed quadrant dividers at the mean X/mean Y of the
    plotted plants (not a fixed 50% — neither share clusters near the
    middle in practice), "High/Low Value Addition" labels in the upper/
    lower right, and a plant-colored, sqrt-scaled bubble per plant with its
    label centered inside. Returns "" when fewer than 2 plants have data
    (a quadrant split is meaningless with 0-1 points).

    The default vw:vh is tuned, not arbitrary — since the <svg> is only
    ever set to width:100% (height:auto) in CSS, this ratio IS the chart's
    rendered aspect ratio on the page, and Chromium's print layout can't
    split this block (no internal break point): too tall and the WHOLE
    chart gets pushed onto page 25 instead of just clipping. Widening the
    ratio (taller relative to its width) doesn't grow the chart's own
    PRINTED width, which is capped by .ssd-bubble-chart's CSS width — it
    only spends the page's remaining blank vertical room (page 24's table
    is well short of a full page even with main.html's current .ssd-table/
    .ssd-stat font sizes) on spreading the plotted bubbles apart, which was
    otherwise their main legibility problem (the "High Value Addition"
    label sitting right on top of a bubble at the old, shorter vh).

    History: 1000:420 (bumped from an original 1000:500, alongside tighter
    pad_l/pad_t/pad_b) was chosen specifically to claw back headroom that a
    MUCH smaller table font (main.html's old 7.5pt .ssd-stat) had almost
    entirely used up — at 1000:500 the page as a whole had near-zero
    margin, and lost it entirely whenever page 23 (ISP's special-steel
    page, immediately before it) was printed in the same job: verified via
    generate_pdf_bytes(pages_override=[page 23, page 24]) that page 23's
    own font shrank below its configured value in that combination even
    though EITHER page alone, or paired with any OTHER neighbor, rendered
    at full size — i.e. that pairing specifically had too little combined
    slack, not a bug in either page's own layout math. Since then
    main.html's .ssd-table/.ssd-stat sizes have grown substantially (9.5pt/
    7.5pt -> 11pt across the board, per direct instruction, 2026-09-18)
    yet the SAME generate_pdf_bytes(pages_override=[page 23, page 24])
    check confirms page 24 still has ~80mm of blank vertical room below
    the chart at 1000:420 — i.e. plenty of margin even after that font
    growth, so 1000:600 (using roughly half that slack, not all of it) is
    still comfortably within budget. Re-verify the same way (a synthetic
    single-page render or a plain page.evaluate()-based height measurement
    are NOT reliable signals for this page — see git history for the
    DOM-measurement figure that was off by ~25%) any time page 23's or
    page 24's own content grows again."""
    if len(points) < 2:
        return ""

    # pad_r must clear r_max (the largest possible bubble radius, below) —
    # RSP structurally has no Semis (_SEMIS_PRODUCTS["RSP"] is empty), so
    # its Finished Steel Share is always exactly 100%, i.e. x=x_max, every
    # single period: its bubble sits with its CENTER on the plot's right
    # edge every time, not just near it. The old pad_r=50 was smaller than
    # r_max=72, so whenever RSP was a large-enough plant its bubble spilled
    # off the right edge of the viewBox and got clipped — per direct
    # instruction, fixed by widening pad_r past r_max with a small margin
    # rather than by touching x_max/the 100% axis meaning itself.
    pad_l, pad_r, pad_t, pad_b = 115, 90, 45, 95
    plot_w = vw - pad_l - pad_r
    plot_h = vh - pad_t - pad_b

    x_max = 100.0
    y_max = max(100.0, math.ceil(max(p["y"] for p in points) * 1.1 / 10) * 10)

    mean_x = sum(p["x"] for p in points) / len(points)
    mean_y = sum(p["y"] for p in points) / len(points)

    sizes = [p["size"] for p in points]
    s_min, s_max = min(sizes), max(sizes)
    r_min, r_max = 34.0, 72.0

    def radius(size):
        if s_max <= s_min:
            return (r_min + r_max) / 2
        t = (math.sqrt(size) - math.sqrt(s_min)) / (math.sqrt(s_max) - math.sqrt(s_min))
        return r_min + t * (r_max - r_min)

    def xp(x):
        return pad_l + (x / x_max) * plot_w

    def yp(y):
        return pad_t + (1 - y / y_max) * plot_h

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']

    # Fine orange frame around the whole chart (per direct instruction,
    # 2026-09-17) — inset by half the stroke width so the 1px-wide line
    # itself isn't clipped by the viewBox edge. Same orange as the report's
    # other fixed-categorical orange (pdf.py's trends band / _SERIES_COLORS).
    lines.append(f'<rect x="0.75" y="0.75" width="{vw - 1.5}" height="{vh - 1.5}" '
                 f'fill="none" stroke="#eb6834" stroke-width="1.5"/>')

    # L-shaped axes (Y then X), solid black — no surrounding box.
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}" stroke="#000000" stroke-width="2.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" y2="{pad_t + plot_h}" stroke="#000000" stroke-width="2.5"/>')

    # Tick marks + %-value labels on both axes — X at fixed 0/20/40/60/80/100
    # (x_max is always exactly 100, a real percentage), Y at 5 even steps up
    # to y_max (dynamic — rounded up to the nearest 10 above the tallest
    # plotted point, see y_max above), so the ticks always cover the full
    # plotted range regardless of how high Special FS Share climbs that month.
    axis_y = pad_t + plot_h
    for xv in (0, 20, 40, 60, 80, 100):
        tx = xp(xv)
        lines.append(f'<line x1="{tx:.1f}" y1="{axis_y:.1f}" x2="{tx:.1f}" y2="{axis_y + 7:.1f}" stroke="#000000" stroke-width="1.5"/>')
        lines.append(f'<text x="{tx:.1f}" y="{axis_y + 21:.1f}" font-size="14" font-family="Arial, sans-serif" '
                     f'fill="#374151" text-anchor="middle">{xv}%</text>')

    y_step = y_max / 5
    for i in range(6):
        yv = y_step * i
        ty = yp(yv)
        lines.append(f'<line x1="{pad_l - 7:.1f}" y1="{ty:.1f}" x2="{pad_l:.1f}" y2="{ty:.1f}" stroke="#000000" stroke-width="1.5"/>')
        lines.append(f'<text x="{pad_l - 12:.1f}" y="{ty + 4:.1f}" font-size="14" font-family="Arial, sans-serif" '
                     f'fill="#374151" text-anchor="end">{yv:.0f}%</text>')

    # Dashed quadrant dividers at the plotted set's own mean, not a fixed 50%.
    mx, my = xp(mean_x), yp(mean_y)
    lines.append(f'<line x1="{mx:.1f}" y1="{pad_t}" x2="{mx:.1f}" y2="{pad_t + plot_h}" stroke="#9ca3af" stroke-width="1.5" stroke-dasharray="7,5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{my:.1f}" x2="{pad_l + plot_w}" y2="{my:.1f}" stroke="#9ca3af" stroke-width="1.5" stroke-dasharray="7,5"/>')

    # Quadrant labels, upper/lower right — matching the reference mock-up.
    label_x = pad_l + plot_w * 0.56
    lines.append(f'<text x="{label_x:.1f}" y="{pad_t + 22:.1f}" font-size="20" '
                 f'font-family="Arial, sans-serif" fill="#16a34a" font-weight="600">High Value Addition</text>')
    lines.append(f'<text x="{label_x:.1f}" y="{pad_t + plot_h - 14:.1f}" font-size="20" '
                 f'font-family="Arial, sans-serif" fill="#c2410c" font-weight="600">Low Value Addition</text>')

    # Axis titles — pushed down/left of the tick labels added above (axis_y+21
    # for X, pad_l-12 for Y), not just off the plot edge, so they never
    # overlap the new tick text at this shrunk vh/pad.
    xt = pad_l + plot_w / 2
    lines.append(f'<text x="{xt:.1f}" y="{vh - 12:.1f}" font-size="12" font-family="Arial, sans-serif" '
                 f'fill="#111827" text-anchor="middle">Finished Steel Share of Saleable Steel Despatch (%)</text>')
    yt = pad_t + plot_h / 2
    # Shorter, abbreviated wording (matching the table's own "FS"/"SS")
    # rather than the fully spelled-out label the X-axis uses — this text
    # runs vertically along plot_h, which is far shorter than plot_w, and
    # appending "Despatch" to the old, already-long spelled-out label
    # pushed it past the chart's own top/bottom bounds.
    lines.append(f'<text x="20" y="{yt:.1f}" font-size="12" font-family="Arial, sans-serif" fill="#111827" '
                 f'text-anchor="middle" transform="rotate(-90 20 {yt:.1f})">Special FS Share of Saleable Steel Despatch (%)</text>')

    # Bubbles, sqrt-scaled by Saleable Steel production, label centered.
    for p in points:
        cx, cy = xp(p["x"]), yp(p["y"])
        r = radius(p["size"])
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{p["color"]}" '
                     f'fill-opacity="0.88" stroke="#ffffff" stroke-width="2"/>')
        lines.append(f'<text x="{cx:.1f}" y="{cy + 7:.1f}" font-size="22" font-family="Arial, sans-serif" '
                     f'fill="#ffffff" font-weight="700" text-anchor="middle">{p["label"]}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ── public API ──────────────────────────────────────────────────────────────

def generate_special_steel_donut(report_month: str) -> dict:
    fy_months = db.get_fy_months(report_month)
    ytd_months = db.get_ytd_months(report_month)

    conn = db.connect()
    cur = conn.cursor()
    try:
        entities = [_entity_metrics(cur, ent, fy_months, report_month, ytd_months) for ent in _ROWS]
        bubble_svg = _bubble_chart_svg(_bubble_data(cur, ytd_months))
    finally:
        conn.close()

    dt = _dt.datetime.strptime(report_month, "%Y-%m")
    month_label = dt.strftime("%b'%y")
    cum_label = (_dt.datetime.strptime(ytd_months[0], "%Y-%m").strftime("%b'%y") + "-" + month_label
                 if len(ytd_months) > 1 else month_label)

    return {
        "type": "special_steel_donut",
        "title": "Special Steel — Saleable Steel Composition & Value-Added Share in Despatch",
        "fy_label": db.get_fy_for_month(report_month)[2:],
        "month_label": month_label,
        "cum_label": cum_label,
        "entities": entities,
        "bubble_svg": bubble_svg,
    }
