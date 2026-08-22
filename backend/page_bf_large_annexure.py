"""
"Large BFs" — Comparison of Performance of SAIL's Largest BFs (Annexure-4)
— page 3.6, inserted right after "Performance of SAIL Plants" (Key
Parameters, page 3.5). SAIL-only — the non-SAIL comparison columns the
source Excel and the original design had were dropped per direction; that
data is still maintained (and still comparable) in the separate, standalone
/reports/bf-benchmark tool, which this page's row additions to
bf_benchmark_registry.py also benefit.

Row list mirrors Report_format/Large BFs for OMI.xlsx (sheet "Large BFs
(2)") — Working Volume, Total HM Prod, ... Fce Utilisation — for the same 3
SAIL BFs (BSP BF-8, RSP BF-5, ISP BF-5). Column shape mirrors
Report_format/"Comparative Performance of large BFs of SAIL.pdf" — Prev FY
(closed) Actual | ABP Targets (current FY) | one column per YTD month
(Apr, May, ... up to report_month) | Apr-<report month> (YTD) Actual —
each period's own dynamic label (e.g. "25-26" / "ABP Targets for 2026-27" /
"Apr-26" / ... / "Apr-Jul'26" for report_month "2026-07") on the table's own
parent header row, per direct instruction — each period-group's 3
sub-columns are the 3 SAIL BFs (plant name over furnace name, wrapped).
Landscape orientation (set in main.py alongside every other page's
orientation flag), also per direct instruction — this many period groups
(up to 7 for a March report month) needs the extra width.

Data sources, per row:
  - Most rows read techno_data directly under the BF's own unit (BSP BF-8,
    RSP BF-5, ISP BF-5) — same params page_techno.py's Iron Making page (29)
    already shows per furnace, so these are already populated by the normal
    monthly techno uploads, nothing new to enter.
  - "Production" is the one exception: it reads production_table (each SAIL
    BF's own furnace-specific item — see _PRODUCTION_ITEM), not techno_data,
    per direct instruction — techno_data's "production" key is sparse and
    unreliable (manual-entry-only, entered late and inconsistently), while
    production_table is this app's deep, reliably-populated production
    history. Summed per period from each month's own figure rather than any
    stored cumulative, same reasoning as every other additive row here.
  - "ABP Targets" reads techno_plan_fy (plant_name/unit=the BF's own unit,
    fy=report_month's FY) — the same store the Techno Manual Entry form's
    annual-target tab already writes into (BF-8/BF-5 tabs), so whatever's
    already been entered there shows up here for free; a key with no entry
    shows "—" rather than being computed or guessed. "Production"'s own ABP
    is the one exception — techno_plan_fy has no per-furnace HM target
    field, so it's computed instead as the Apr-Mar sum of
    production_plan_table's monthly plan for that furnace's own item (see
    _production_plan_annual_tonnes), the same plan data every other
    production page's own ABP/APP column already reads.
  - "Coke Ash" and "Sinter Fe" reuse the same plant-level (not per-furnace)
    figures page_key_parameters.py's Key Parameters page already shows
    (Coke-Ovens shop's ash_in_coke, and tfe_in_sinter — RSP split across
    SP-1/2/3, other plants from the BF-shop unit) — same _COKE_UNITS/
    _SP_UNIT_MAP/_first_present_val/_sinter_fe_val helpers, imported rather
    than reimplemented.
  - "Avg. Daily Rate" and "Total Prepared Burden" are pure arithmetic on
    other rows in this same table (production÷days-in-period, sinter+pellet
    in burden respectively) — computed here, never stored. "Lump in Burden"
    used to be computed the same way (100 - Total Prepared Burden), but
    that assumes sinter+pellet+lump always sum to 100% of the burden, which
    doesn't hold for a furnace charging scrap too — it's now its own
    directly-entered techno_data key (bf_benchmark_registry.py's
    lump_in_burden), same as sinter_in_burden/pellet_in_burden, reading
    whatever the plant's own report actually states rather than inferring
    it.
  - The remaining ~12 rows (Lump Ore Fe, Pellet Fe, Steam Rate, Top
    Pressure, Slag MgO/Al2O3/B2, Eta CO, Heat Load/Flux, Tapping Duration,
    Fce Availability/Utilisation) have no extractor writing them for any
    SAIL plant today — added to bf_benchmark_registry.py's
    BF_BENCHMARK_PARAMS (purely additive; also gives the existing
    /reports/bf-benchmark comparison tool and its non-SAIL entry grid these
    same rows for free) and filled in via the Techno Manual Entry form's
    BF-8/BF-5 tabs (technoParamRegistry.js's Blast Furnace template),
    which write into the SAME per-BF techno_data unit these rows read from
    here. There used to be a second, dedicated /data-entry/bf-large-manual
    page for exactly these rows, saving into the same cells via a
    different form — removed per direct instruction once its field list
    was folded into Techno Manual Entry, since having two forms edit the
    same values under slightly different key names is exactly what caused
    the Pellet Fe/Lump Ore Fe/Fce Availability divergence bugs fixed
    earlier (a value entered on one form not showing up on the other).
  - Working Volume is a static engineering spec, unchanged from month to
    month — reused as-is from bf_benchmark_sail_meta.working_volume_m3 (the
    table the existing BF Benchmarking feature already maintains this in;
    no reason to duplicate it) — shown under every period column, same
    figure repeated, matching the source PDF.

Note: the source PDF has no "Heat Load/Flux" row (it's skipped entirely in
that report), but this page keeps it — it's already wired up for RSP (whose
techno_data does carry heat_load_flux most months) and dropping a row is a
bigger call than this rewrite's brief covers; flagged to the user rather
than silently removed.
"""
import json as _json
import db
from bf_benchmark_registry import SAIL_BFS, PARAM_BY_KEY, KEY_ALIASES, compute_fuel_rate
from page_key_parameters import (
    _COKE_UNITS, _SP_UNIT_MAP, _first_present_val, _round, _days_in_month,
)
from page_special_steel_trend import _days_in_fy

# Row order matches the source Excel exactly (rows 8-41 of "Large BFs (2)").
# A plain string is a bf_benchmark_registry key (read from the BF's own
# techno_data unit); an entry starting with "_" is special-cased below
# (computed, or read from a different unit than the BF's own).
_ROW_KEYS = [
    "working_volume_m3", "production", "_avg_daily_rate", "bf_productivity",
    "coke_rate", "nut_coke_rate", "cdi", "fuel_rate",
    "sinter_in_burden", "pellet_in_burden", "_total_prepared_burden", "lump_in_burden",
    "_coke_ash", "_sinter_fe", "lump_ore_fe", "pellet_fe", "_avg_burden_fe",
    "slag_rate", "hot_blast_temp", "o2_enrichment", "steam_rate_hr", "top_pressure",
    "silicon_in_hm", "sulphur_in_hm", "avg_hot_metal_temperature",
    "slag_mgo", "slag_al2o3", "slag_b2", "eta_co", "heat_load_flux",
    "tapping_duration", "availability", "utilisation",
]

_SPECIAL_ROWS = {
    "_avg_daily_rate":         ("Avg. Daily Rate", "TPD"),
    "_total_prepared_burden":  ("Total Prepared Burden", "%"),
    "_coke_ash":               ("Coke Ash", "%"),
    "_sinter_fe":              ("Sinter Fe", "%"),
    "_avg_burden_fe":          ("Avg. Burden Fe", "%"),
}

# Params whose techno_data figure is an additive per-month tonnage rather
# than a rate/average — see module docstring's "Production" note. Only
# "production" today, but kept as a set in case a future row needs the same
# treatment.
_ADDITIVE_KEYS = {"production"}

# Production reads production_table exclusively, never techno_data's own
# "production" key — per direct instruction, that key isn't a trustworthy
# source (sparsely manual-entered only from ~2026-06 onward for BSP/RSP,
# never at all for ISP), whereas production_table is
# this app's established, deeply-historical production source (same table
# page_key_parameters.py's Hot Metal row reads) and — confirmed against
# every month where techno_data's key WAS populated — carries the exact
# same figures anyway. BSP/RSP have their own furnace-specific item there
# ("BF#8"/"BF#5"); ISP has no per-furnace item (the OMI production report
# only ever tracked it at plant level there), but ISP is single-furnace
# (same fact _BF_UNITS/_bf_unit_for in page_key_parameters.py relies on),
# so its plant-level "Hot Metal" total IS BF-5's own output.
_PRODUCTION_ITEM = {"BSP": "BF#8", "RSP": "BF#5", "ISP": "Hot Metal"}

# No ABP target makes sense for these — pure per-shift/derived readings a
# plant's annual plan never states a single-figure target for. Skipped when
# building the ABP column so the row shows "—" rather than a stray 0/None
# read as if it were a real (and missing) target.
_NO_ABP_KEYS = {"working_volume_m3", "_avg_daily_rate", "_total_prepared_burden",
                "_coke_ash", "_sinter_fe", "lump_ore_fe", "pellet_fe", "_avg_burden_fe"}


def _production_table_tonnes(plant: str, months: list) -> dict:
    """{report_month: production_in_tonnes} from production_table (stored
    in '000 T, like every other production_table item — see
    _PRODUCTION_ITEM for which item_name each SAIL BF reads)."""
    item = _PRODUCTION_ITEM.get(plant)
    if not months or not item:
        return {}
    conn = db.connect()
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(months))
        cur.execute(
            f"SELECT report_month, month_actual FROM production_table "
            f"WHERE plant_name=? AND item_name=? AND report_month IN ({ph})",
            (plant, item, *months),
        )
        return {rm: v * 1000 for rm, v in cur.fetchall() if v is not None}
    finally:
        conn.close()


def _production_plan_annual_tonnes(plant: str, fy_months: list) -> float:
    """Sum of production_plan_table's monthly plan figures (same per-BF
    item_name as _production_table_tonnes' actual figures, same '000T ->
    tonnes scaling) across the full FY — the "ABP Target <FY>" figure for
    Total HM Prod, computed here rather than read from techno_plan_fy: that
    store is the Techno Manual Entry form's own annual-target tab, and
    nobody enters a per-furnace HM production target there, so abp.get(
    "production") was always None. production_plan_table already carries
    a real monthly plan per furnace (the same ABP feeding every other
    production page's own "APP"/plan columns), so this just sums Apr-Mar
    of it instead of requiring a second, redundant manual entry."""
    item = _PRODUCTION_ITEM.get(plant)
    if not fy_months or not item:
        return None
    conn = db.connect()
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(fy_months))
        cur.execute(
            f"SELECT SUM(month_actual) FROM production_plan_table "
            f"WHERE plant_name=? AND item_name=? AND report_month IN ({ph})",
            (plant, item, *fy_months),
        )
        r = cur.fetchone()
        return r[0] * 1000 if r and r[0] is not None else None
    finally:
        conn.close()


def _row_spec(key):
    if key in _SPECIAL_ROWS:
        label, unit = _SPECIAL_ROWS[key]
        return label, unit
    p = PARAM_BY_KEY[key]
    if key == "production":
        # bf_benchmark_registry.py's own unit (UNIT.T = "T") and label
        # ("Production") are shared with /reports/bf-benchmark, which shows
        # this key at its raw techno_data scale — this page's own
        # _fmt_production divides by 1e6 first (matching the source
        # PDF/Excel's "Total HM Prod" column), so only THIS page's label
        # and unit need overriding to match that sample.
        return "Total HM Prod", "MT"
    if key == "bf_productivity":
        # Sample PDF's own row label ("BF Prodty-WV") — bf_benchmark_
        # registry.py's shared label ("BF Productivity") stays as-is for
        # every other page/tool that reads PARAM_BY_KEY.
        return "BF Prodty-WV", p["unit"]
    return p["label"], p["unit"]


def _prev_fy_end_month(report_month: str) -> str:
    """March of the FY immediately before report_month's own FY — e.g. for
    report_month in FY2026-27 (starts April 2026), the previous FY (2025-26)
    ends March 2026, i.e. the SAME calendar year the current FY starts in."""
    fy_start = db.get_fy_months(report_month)[0]  # "<fy_start_year>-04"
    fy_start_year = int(fy_start[:4])
    return f"{fy_start_year}-03"


def _fetch_bf_rows(plant, unit, months):
    """{report_month: {"month": {...}, "till_month": {...}}} for one
    plant/unit across the given months (only rows that exist)."""
    if not months:
        return {}
    conn = db.connect()
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(months))
        cur.execute(
            f"SELECT report_month, techno_json FROM techno_data "
            f"WHERE plant=? AND unit=? AND report_month IN ({ph})",
            (plant, unit, *months),
        )
        return {rm: _json.loads(tj) for rm, tj in cur.fetchall()}
    finally:
        conn.close()


def _period_value(key, period_dict):
    """Single-month or single-cumulative-row lookup, trying the key's
    registered aliases (KEY_ALIASES) too."""
    for k in [key] + KEY_ALIASES.get(key, []):
        v = period_dict.get(k)
        if v is not None:
            return v
    return None


def _sail_bf_values(plant, unit, report_month):
    """{key: {"prev_fy": v, <ytd_month>: v, ..., "ytd": v}} for every
    non-special row, for one SAIL BF. "abp" is NOT included here — see
    _sail_bf_abp, a separate data source (techno_plan_fy, not techno_data)."""
    fy_months = db.get_fy_months(report_month)          # this FY, Apr..Mar
    ytd_months = [m for m in fy_months if m <= report_month]
    # Shift report_month back exactly one calendar year and ask for THAT
    # month's FY — correct even for report_months in Jan/Feb/Mar, where a
    # flat "subtract 1 from fy_months[0]'s year" would mislabel every month
    # after the calendar-year rollover within the FY (e.g. Jan/Feb/Mar).
    prev_fy_months = db.get_fy_months(f"{int(report_month[:4]) - 1}-{report_month[5:]}")
    prev_fy_end = _prev_fy_end_month(report_month)

    all_months = list(dict.fromkeys(prev_fy_months + fy_months))
    rows = _fetch_bf_rows(plant, unit, all_months)
    cur_row = rows.get(report_month, {})
    prev_fy_row = rows.get(prev_fy_end, {})

    # HM Sulphur: RSP's own monthly report has no per-furnace breakdown for
    # this parameter (confirmed against a real source workbook — unlike HM
    # Silicon, which does), so whoever enters it can only ever have a
    # shop-level figure to type in. Fall back to the plant's BF_Shop unit
    # when the furnace's own unit has no value — same "shop-level fallback"
    # pattern _coke_ash_and_sinter_fe below already uses for Sinter Fe/Coke
    # Ash, applied generically here rather than gated to RSP specifically,
    # since any plant could be in the same position.
    shop_rows = {} if unit == "BF_Shop" else _fetch_bf_rows(plant, "BF_Shop", all_months)
    shop_cur_row = shop_rows.get(report_month, {})
    shop_prev_fy_row = shop_rows.get(prev_fy_end, {})

    production_tonnes = _production_table_tonnes(plant, all_months)

    out = {}
    for key in list(PARAM_BY_KEY.keys()):
        vals = {}
        if key in _ADDITIVE_KEYS:
            for m in ytd_months:
                vals[m] = production_tonnes.get(m)
            vals["ytd"] = sum(
                v for m in ytd_months for v in [production_tonnes.get(m)] if v is not None
            ) or None
            vals["prev_fy"] = sum(
                v for m in prev_fy_months for v in [production_tonnes.get(m)] if v is not None
            ) or None
        else:
            for m in ytd_months:
                vals[m] = _period_value(key, rows.get(m, {}).get("month", {}))
            vals["ytd"] = _period_value(key, cur_row.get("till_month", {}))
            vals["prev_fy"] = _period_value(key, prev_fy_row.get("till_month", {}))
            if key == "fuel_rate":
                for m in ytd_months:
                    if vals[m] is None:
                        vals[m] = compute_fuel_rate(rows.get(m, {}).get("month", {}))
                if vals["ytd"] is None:
                    vals["ytd"] = compute_fuel_rate(cur_row.get("till_month", {}))
                if vals["prev_fy"] is None:
                    vals["prev_fy"] = compute_fuel_rate(prev_fy_row.get("till_month", {}))
            elif key == "sulphur_in_hm":
                for m in ytd_months:
                    if vals[m] is None:
                        vals[m] = _period_value(key, shop_rows.get(m, {}).get("month", {}))
                if vals["ytd"] is None:
                    vals["ytd"] = _period_value(key, shop_cur_row.get("till_month", {}))
                if vals["prev_fy"] is None:
                    vals["prev_fy"] = _period_value(key, shop_prev_fy_row.get("till_month", {}))
        out[key] = vals
    return out, ytd_months, prev_fy_months


def _sail_bf_abp(plant, unit, fy_label):
    """{key: value} — this BF's ABP/annual-target figures for fy_label
    (e.g. "2026-27"), from techno_plan_fy (the same store the Techno Manual
    Entry form's annual-target tab writes into). A key with nothing entered
    is simply absent — shown as "—", never computed or guessed."""
    data = db.get_techno_plan(plant, fy_label, unit=unit).get("data", {})
    out = {}
    for key in PARAM_BY_KEY:
        v = data.get(key)
        out[key] = v.get("value") if isinstance(v, dict) else v
    return out


def _sail_static_working_volume(plant, unit):
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT working_volume_m3 FROM bf_benchmark_sail_meta WHERE plant=? AND unit=?",
            (plant, unit),
        )
        r = cur.fetchone()
        return r[0] if r else None
    finally:
        conn.close()


def _plant_techno_view(plant, period_dict_by_unit):
    """Build the {(plant, unit): {...period values...}} shape
    _first_present_val/_sinter_fe_val expect, for one plant, one period."""
    return {(plant, u): d for u, d in period_dict_by_unit.items()}


def _coke_ash_and_sinter_fe(plant, unit, report_month, ytd_months):
    """({"prev_fy":v, <ytd_month>:v, ..., "ytd":v} for Coke Ash,
    same shape for Sinter Fe) — reusing page_key_parameters.py's
    plant-level (not per-furnace) resolution as a fallback for Sinter Fe —
    see _resolve's furnace_fe check below for the furnace-level figure
    this page prefers first."""
    prev_fy_end = _prev_fy_end_month(report_month)
    periods = ["prev_fy"] + ytd_months + ["ytd"]
    period_months = {"prev_fy": prev_fy_end, "ytd": report_month}
    for m in ytd_months:
        period_months[m] = m

    # Units potentially needed: coke-oven candidates + whichever Sinter/BF
    # units _sinter_fe_val itself may read (BF_Shop/BF-5, or SP-1/2/3 for RSP)
    # + this BF's own unit (for the furnace-level figure _resolve prefers).
    sinter_units = _SP_UNIT_MAP.get(plant, ["BF_Shop", "BF-5"])
    all_units = list(dict.fromkeys(_COKE_UNITS + sinter_units + [unit]))
    all_months = list(dict.fromkeys(period_months.values()))

    rows = {}
    conn = db.connect()
    cur = conn.cursor()
    try:
        ph_u = ",".join("?" * len(all_units))
        ph_m = ",".join("?" * len(all_months))
        cur.execute(
            f"SELECT unit, report_month, techno_json FROM techno_data "
            f"WHERE plant=? AND unit IN ({ph_u}) AND report_month IN ({ph_m})",
            (plant, *all_units, *all_months),
        )
        for row_unit, rm, tj in cur.fetchall():
            rows[(row_unit, rm)] = _json.loads(tj)
    finally:
        conn.close()

    def _resolve(rm, period):
        by_unit = {u: rows.get((u, rm), {}).get(period, {}) for u in all_units}
        techno = _plant_techno_view(plant, by_unit)
        ash = _first_present_val(plant, _COKE_UNITS, ["ash_in_coke", "average_ash_in_coke"], techno, 2)
        # Prefer Sinter Fe entered directly under this BF's OWN unit (e.g.
        # RSP's BF-5 tab in Techno Manual Entry, tfe_in_sinter) — the exact
        # furnace-level figure this per-furnace comparison row wants,
        # confirmed live for RSP March'26 (entered under BF-5, not any of
        # SP-1/2/3). Only falls back to the plant-wide SP-1/2/3 (or
        # BF_Shop/BF-5) average — page_key_parameters.py's same
        # resolution, a fair stand-in when nobody's entered the
        # furnace-specific figure yet, but not as accurate as the real one.
        furnace_fe = by_unit.get(unit, {}).get("tfe_in_sinter")
        if furnace_fe is not None:
            fe = _round(furnace_fe, 2)
        else:
            sinter_vals = [
                v for u in sinter_units
                for v in [by_unit.get(u, {}).get("tfe_in_sinter")]
                if v is not None
            ]
            fe = _round(sum(sinter_vals) / len(sinter_vals), 2) if sinter_vals else None
        return ash, fe

    ash_out, fe_out = {}, {}
    for p in periods:
        rm = period_months[p]
        period_kind = "month" if p not in ("prev_fy", "ytd") else "till_month"
        ash_out[p], fe_out[p] = _resolve(rm, period_kind)
    return ash_out, fe_out


def _avg_daily_rate(production_vals, report_month, ytd_months, prev_fy_months):
    out = {}
    month_days = _days_in_month(report_month)
    prev_fy_days = _days_in_fy(db.get_fy_for_month(prev_fy_months[0])) if prev_fy_months else 1
    for m in ytd_months:
        v = production_vals.get(m)
        out[m] = _round(v / _days_in_month(m), 0) if v else None
    ytd_days = sum(_days_in_month(m) for m in ytd_months) or 1
    out["ytd"] = _round(production_vals.get("ytd") / ytd_days, 0) if production_vals.get("ytd") else None
    out["prev_fy"] = _round(production_vals.get("prev_fy") / prev_fy_days, 0) if production_vals.get("prev_fy") else None
    return out


def _avg_burden_fe(sinter_pct, pellet_pct, lump_pct, sinter_fe, pellet_fe, lump_fe, periods):
    """{period: value} — per direct instruction:
    (Sinter%×SinterFe + Pellet%×PelletFe + Lump%×LumpOreFe) / 100,
    the same 3-way burden split Total Prepared Burden/Lump in Burden already
    use, weighted by each component's own Fe assay instead of summed as a
    single fixed-Fe blend. A component with a burden % of None/0 is simply
    skipped (it isn't part of the mix); a component with a real, nonzero %
    but no Fe assay entered makes the whole period's average un-computable
    (silently treating its Fe as 0 would understate the true average), so
    that period shows blank rather than a misleadingly low figure until the
    missing Fe assay (Sinter Fe / Pellet Fe / Lump Ore Fe row) is entered."""
    out = {}
    for p in periods:
        s, pl_, l = sinter_pct.get(p), pellet_pct.get(p), lump_pct.get(p)
        sf, pf, lf = sinter_fe.get(p), pellet_fe.get(p), lump_fe.get(p)
        total = 0.0
        has_component = False
        computable = True
        for pct, fe in ((s, sf), (pl_, pf), (l, lf)):
            if not pct:
                continue
            has_component = True
            if fe is None:
                computable = False
                break
            total += pct * fe
        out[p] = _round(total / 100, 2) if has_component and computable else None
    return out


def _dp_for(key):
    if key in ("production", "sulphur_in_hm"):
        return 3
    if key in ("working_volume_m3", "_avg_daily_rate", "hot_blast_temp",
               "avg_hot_metal_temperature",
               "coke_rate", "nut_coke_rate", "cdi", "fuel_rate", "slag_rate"):
        return 0
    return 2


def _clean(v, dp):
    """_round(v, dp), but a 0dp row displays as a plain integer ("397") —
    Python's round(float, 0) still returns a float, and DB-stored values
    are a mix of int/float depending on how each was originally saved, so
    without this, some cells in the same 0dp row would show "397" and
    others "397.0" purely by storage-type accident."""
    r = _round(v, dp)
    if r is not None and dp == 0:
        return int(r)
    return r


def _fmt_production(v):
    """techno_data's raw tonnes -> Million T (MT), matching the source
    Excel's own Total HM Prod unit."""
    return None if v is None else round(v / 1_000_000, 3)


_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_col_label(report_month: str) -> str:
    """'2026-07' -> 'Jul-26' — a single month column's own header label."""
    y, m = int(report_month[:4]), int(report_month[5:7])
    return f"{_MON_ABBR[m]}-{y % 100:02d}"


def _ytd_col_label(ytd_months: list) -> str:
    """['2026-04',...,'2026-07'] -> 'Apr-Jul'26' (or just "Apr'26" for a
    single-month YTD) — mirrors page_key_parameters.py's period_label."""
    y0, m0 = int(ytd_months[0][:4]), int(ytd_months[0][5:7])
    y1, m1 = int(ytd_months[-1][:4]), int(ytd_months[-1][5:7])
    if len(ytd_months) == 1:
        return f"{_MON_ABBR[m0]}'{y0 % 100:02d}"
    return f"{_MON_ABBR[m0]}-{_MON_ABBR[m1]}'{y1 % 100:02d}"


def generate_bf_large_annexure(report_month: str) -> dict:
    fy_months = db.get_fy_months(report_month)
    prev_fy_start_year = int(fy_months[0][:4]) - 1
    # Short "YY-YY" form, matching page_ipt.py's/page_special_steel_trend.py's
    # own fy_label convention elsewhere in this app.
    prev_fy_col_label = f"{prev_fy_start_year % 100:02d}-{(prev_fy_start_year + 1) % 100:02d}"
    fy_label = db.get_fy_for_month(report_month)  # e.g. "2026-27"

    sail_cols = []
    sail_values = {}   # {bf_label: {key: {period: value}}}
    ytd_months = [m for m in fy_months if m <= report_month]
    periods = ["prev_fy", "abp"] + ytd_months + ["ytd"]

    for bf in SAIL_BFS:
        plant, unit, label = bf["plant"], bf["unit"], bf["label"]
        sail_cols.append({"label": label, "plant": plant, "unit": unit})
        vals, ytd_months, prev_fy_months = _sail_bf_values(plant, unit, report_month)
        abp = _sail_bf_abp(plant, unit, fy_label)
        # Fuel Rate is never entered directly as its own ABP target (same
        # rule as everywhere else in this app — bf_benchmark_registry.py's
        # compute_fuel_rate, db._maybe_recompute_derived_params,
        # page_techno.py's Iron Making Norm/Target column): Coke Rate + Nut
        # Coke Rate + CDI Rate, computed on the fly from those three's own
        # ABP entries when nothing was stored under "fuel_rate" itself
        # directly (which only happened to be true for ISP here, leaving
        # BSP/RSP blank despite having real Coke/CDI targets to derive it
        # from).
        if abp.get("fuel_rate") is None:
            computed_fuel_rate = compute_fuel_rate(abp)
            if computed_fuel_rate is not None:
                abp["fuel_rate"] = computed_fuel_rate
        for key in vals:
            vals[key]["abp"] = None if key in _NO_ABP_KEYS else abp.get(key)
        # Total HM Prod's ABP target is computed (Apr-Mar sum of
        # production_plan_table), not read from techno_plan_fy — see
        # _production_plan_annual_tonnes' docstring.
        vals["production"]["abp"] = _production_plan_annual_tonnes(plant, fy_months)

        ash, fe = _coke_ash_and_sinter_fe(plant, unit, report_month, ytd_months)
        vals["_coke_ash"] = {**ash, "abp": None}
        vals["_sinter_fe"] = {**fe, "abp": None}
        # Avg. Daily Rate's ABP = the same annual ABP Total HM Prod figure
        # (now computed, see _production_plan_annual_tonnes above) divided
        # by the FY's own day count — same "production / days-in-period"
        # rule every other period on this row already uses.
        abp_production = vals["production"].get("abp")
        abp_avg_daily_rate = _round(abp_production / _days_in_fy(fy_label), 0) if abp_production else None
        vals["_avg_daily_rate"] = {**_avg_daily_rate(vals["production"], report_month, ytd_months, prev_fy_months), "abp": abp_avg_daily_rate}

        sp, pl_ = vals["sinter_in_burden"], vals["pellet_in_burden"]
        tpb = {}
        for p in periods:
            s, pl2 = sp.get(p), pl_.get(p)
            tpb[p] = _round(s + pl2, 2) if s is not None and pl2 is not None else None
        vals["_total_prepared_burden"] = tpb

        vals["_avg_burden_fe"] = _avg_burden_fe(
            sp, pl_, vals["lump_in_burden"], vals["_sinter_fe"], vals["pellet_fe"], vals["lump_ore_fe"], periods,
        )

        wv = _sail_static_working_volume(plant, unit)
        vals["working_volume_m3"] = {p: wv for p in periods}
        sail_values[label] = vals

    rows = []
    for key in _ROW_KEYS:
        label, unit = _row_spec(key)
        dp = _dp_for(key)
        sail_out = {}
        for bf in sail_cols:
            bf_label = bf["label"]
            pvals = sail_values[bf_label][key]
            if key == "production":
                out = {}
                for p in periods:
                    v = _fmt_production(pvals.get(p))
                    # Fixed 3dp string, not a plain round — Python drops
                    # trailing zeros on a bare float (2.900 -> 2.9, 0.870 ->
                    # 0.87), which reads as mixed precision across cells in
                    # the same row. Same fix CHM Ratio already applies for
                    # its own always-3dp display.
                    out[p] = f"{v:.3f}" if v is not None else None
                sail_out[bf_label] = out
                continue
            sail_out[bf_label] = {p: _clean(pvals.get(p), dp) for p in periods}
        rows.append({"parameter": label, "unit": unit, "sail": sail_out})

    period_defs = [{"key": "prev_fy", "label": prev_fy_col_label, "kind": "prev_fy"},
                   {"key": "abp", "label": f"ABP Targets for<br/>{fy_label}", "kind": "abp"}]
    for m in ytd_months:
        period_defs.append({"key": m, "label": _month_col_label(m), "kind": "month"})
    period_defs.append({"key": "ytd", "label": _ytd_col_label(ytd_months), "kind": "ytd"})

    return {
        "title": "SAIL Large BFs - Performance Snapshot",
        "variant": "bf_large_annexure",
        "orientation": "landscape",
        "sail_cols": sail_cols,
        "periods": period_defs,
        "rows": rows,
    }
