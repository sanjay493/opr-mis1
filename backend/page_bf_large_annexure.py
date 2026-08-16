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
SAIL BFs (BSP BF-8, RSP BF-5, ISP BF-5). Columns differ from the source
file on purpose: that Excel is a hand-built snapshot with one column per
individual month of whichever FY it was made in (Apr, May, Jun, Apr-Jun,
Jul, Apr-Jul, ...), which doesn't fit this app's per-report_month generation
model (every other page here regenerates cleanly for any selected month from
a fixed column set). This page instead uses the same 3-column shape as the
rest of the report — Previous FY (closed) Actual | <report month> Actual |
Apr-<report month> (YTD) Actual — with each period's own dynamic label
(e.g. "25-26" / "Jul-26" / "Apr-Jul'26" for report_month "2026-07") on the
table's own parent header row, per user direction — each period-group's 3
sub-columns are the 3 SAIL BFs (plant name over furnace name, wrapped).

Data sources, per row:
  - Most rows read techno_data directly under the BF's own unit (BSP BF-8,
    RSP BF-5, ISP BF-5) — same params page_techno.py's Iron Making page (29)
    already shows per furnace, so these are already populated by the normal
    monthly techno uploads, nothing new to enter.
  - "Production" is summed from each month's "month" value rather than read
    from "till_month" — confirmed live that unlike rate params (coke_rate,
    cdi, etc., which DO get a proper cumulative written to till_month),
    production's till_month is only ever populated for April (the trivial
    case where month==till_month); every other month leaves it null, so a
    real YTD figure has to be summed here instead of trusted from storage.
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
  - The remaining ~12 rows (Lump Ore Fe, Pellet Fe, Avg. Burden Fe, Steam
    Rate, Top Pressure, Slag MgO/Al2O3/B2, Eta CO, Heat Load/Flux, Tapping
    Duration, Fce Availability/Utilisation) have no extractor writing them
    for any SAIL plant today — added to bf_benchmark_registry.py's
    BF_BENCHMARK_PARAMS (purely additive; also gives the existing
    /reports/bf-benchmark comparison tool and its non-SAIL entry grid these
    same rows for free) and filled in via the dedicated
    /data-entry/bf-large-manual page, which saves into techno_data under
    the SAME per-BF unit these rows read from here — so a value entered
    there (or via the general Techno Manual Entry form's BF-8/BF-5 tabs,
    which shows the same techno_data cells) shows up on both forms and on
    this report page immediately, all being the same underlying value.
  - Working Volume is a static engineering spec, unchanged from month to
    month — reused as-is from bf_benchmark_sail_meta.working_volume_m3 (the
    table the existing BF Benchmarking feature already maintains this in;
    no reason to duplicate it).
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
    "_coke_ash", "_sinter_fe", "lump_ore_fe", "pellet_fe", "avg_burden_fe",
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
}

# Params whose techno_data figure is an additive per-month tonnage rather
# than a rate/average — see module docstring's "Production" note. Only
# "production" today, but kept as a set in case a future row needs the same
# treatment.
_ADDITIVE_KEYS = {"production"}


def _row_spec(key):
    if key in _SPECIAL_ROWS:
        label, unit = _SPECIAL_ROWS[key]
        return label, unit
    p = PARAM_BY_KEY[key]
    if key == "production":
        # bf_benchmark_registry.py's own unit (UNIT.T = "T") is shared with
        # /reports/bf-benchmark, which shows this key at its raw
        # techno_data scale (tonnes) — this page's own _fmt_production
        # divides by 1e6 first (matching the source Excel's "Total HM Prod"
        # column), so only THIS page's label needs overriding to "MT".
        return p["label"], "MT"
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
    """{key: (prev_fy, month, ytd)} for every non-special row, for one SAIL BF."""
    fy_months = db.get_fy_months(report_month)          # this FY, Apr..Mar
    # Shift report_month back exactly one calendar year and ask for THAT
    # month's FY — correct even for report_months in Jan/Feb/Mar, where a
    # flat "subtract 1 from fy_months[0]'s year" would mislabel every month
    # after the calendar-year rollover within the FY (e.g. Jan/Feb/Mar).
    prev_fy_months = db.get_fy_months(f"{int(report_month[:4]) - 1}-{report_month[5:]}")
    prev_fy_end = _prev_fy_end_month(report_month)

    rows = _fetch_bf_rows(plant, unit, list(dict.fromkeys(prev_fy_months + fy_months)))
    cur_row = rows.get(report_month, {})
    prev_fy_row = rows.get(prev_fy_end, {})
    ytd_months = [m for m in fy_months if m <= report_month]

    # HM Sulphur: RSP's own monthly report has no per-furnace breakdown for
    # this parameter (confirmed against a real source workbook — unlike HM
    # Silicon, which does), so whoever enters it can only ever have a
    # shop-level figure to type in. Fall back to the plant's BF_Shop unit
    # when the furnace's own unit has no value — same "shop-level fallback"
    # pattern _coke_ash_and_sinter_fe below already uses for Sinter Fe/Coke
    # Ash, applied generically here rather than gated to RSP specifically,
    # since any plant could be in the same position.
    shop_rows = {} if unit == "BF_Shop" else _fetch_bf_rows(plant, "BF_Shop", list(dict.fromkeys(prev_fy_months + fy_months)))
    shop_cur_row = shop_rows.get(report_month, {})
    shop_prev_fy_row = shop_rows.get(prev_fy_end, {})

    out = {}
    for key in list(PARAM_BY_KEY.keys()):
        if key in _ADDITIVE_KEYS:
            month_v = _period_value(key, cur_row.get("month", {}))
            ytd_v = sum(
                v for m in ytd_months
                for v in [_period_value(key, rows.get(m, {}).get("month", {}))]
                if v is not None
            ) or None
            prev_fy_v = sum(
                v for m in prev_fy_months
                for v in [_period_value(key, rows.get(m, {}).get("month", {}))]
                if v is not None
            ) or None
        else:
            month_v = _period_value(key, cur_row.get("month", {}))
            ytd_v = _period_value(key, cur_row.get("till_month", {}))
            prev_fy_v = _period_value(key, prev_fy_row.get("till_month", {}))
            if key == "fuel_rate":
                month_v = month_v if month_v is not None else compute_fuel_rate(cur_row.get("month", {}))
                ytd_v = ytd_v if ytd_v is not None else compute_fuel_rate(cur_row.get("till_month", {}))
                prev_fy_v = prev_fy_v if prev_fy_v is not None else compute_fuel_rate(prev_fy_row.get("till_month", {}))
            elif key == "sulphur_in_hm":
                if month_v is None:
                    month_v = _period_value(key, shop_cur_row.get("month", {}))
                if ytd_v is None:
                    ytd_v = _period_value(key, shop_cur_row.get("till_month", {}))
                if prev_fy_v is None:
                    prev_fy_v = _period_value(key, shop_prev_fy_row.get("till_month", {}))
        out[key] = (prev_fy_v, month_v, ytd_v)
    return out, ytd_months, prev_fy_months


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


def _coke_ash_and_sinter_fe(plant, report_month):
    """(prev_fy, month, ytd) tuples for Coke Ash and Sinter Fe, reusing
    page_key_parameters.py's plant-level (not per-furnace) resolution."""
    prev_fy_end = _prev_fy_end_month(report_month)

    # Units potentially needed: coke-oven candidates + whichever Sinter/BF
    # units _sinter_fe_val itself may read (BF_Shop/BF-5, or SP-1/2/3 for RSP).
    sinter_units = _SP_UNIT_MAP.get(plant, ["BF_Shop", "BF-5"])
    all_units = list(dict.fromkeys(_COKE_UNITS + sinter_units))

    rows = {}
    conn = db.connect()
    cur = conn.cursor()
    try:
        ph_u = ",".join("?" * len(all_units))
        cur.execute(
            f"SELECT unit, report_month, techno_json FROM techno_data "
            f"WHERE plant=? AND unit IN ({ph_u}) AND report_month IN (?, ?)",
            (plant, *all_units, report_month, prev_fy_end),
        )
        for unit, rm, tj in cur.fetchall():
            rows[(unit, rm)] = _json.loads(tj)
    finally:
        conn.close()

    def _resolve(rm, period):
        by_unit = {u: rows.get((u, rm), {}).get(period, {}) for u in all_units}
        techno = _plant_techno_view(plant, by_unit)
        ash = _first_present_val(plant, _COKE_UNITS, ["ash_in_coke", "average_ash_in_coke"], techno, 2)
        # _sinter_fe_val (page_key_parameters.py) returns a "/"-joined
        # display STRING for RSP (its 3 sinter plants shown side by side) —
        # not usable here where every value needs to stay numeric for
        # rounding/formatting. RSP's furnaces all draw from the same sinter
        # supply, so the average across SP-1/2/3 is a fair single figure for
        # a single-furnace comparison row.
        sinter_vals = [
            v for u in sinter_units
            for v in [by_unit.get(u, {}).get("tfe_in_sinter")]
            if v is not None
        ]
        fe = _round(sum(sinter_vals) / len(sinter_vals), 2) if sinter_vals else None
        return ash, fe

    ash_month, fe_month = _resolve(report_month, "month")
    ash_ytd, fe_ytd = _resolve(report_month, "till_month")
    ash_prev, fe_prev = _resolve(prev_fy_end, "till_month")
    return (ash_prev, ash_month, ash_ytd), (fe_prev, fe_month, fe_ytd)


def _avg_daily_rate(production_tuple, report_month, ytd_months, prev_fy_months):
    prev_fy_prod, month_prod, ytd_prod = production_tuple
    month_days = _days_in_month(report_month)
    ytd_days = sum(_days_in_month(m) for m in ytd_months) or 1
    prev_fy_days = _days_in_fy(db.get_fy_for_month(prev_fy_months[0])) if prev_fy_months else 1
    return (
        _round(prev_fy_prod / prev_fy_days, 0) if prev_fy_prod else None,
        _round(month_prod / month_days, 0) if month_prod else None,
        _round(ytd_prod / ytd_days, 0) if ytd_prod else None,
    )


def _dp_for(key):
    if key in ("production",):
        return 3
    if key in ("working_volume_m3", "_avg_daily_rate", "hot_blast_temp",
               "avg_hot_metal_temperature", "tapping_duration",
               "coke_rate", "nut_coke_rate", "cdi", "fuel_rate",
               "sinter_in_burden", "pellet_in_burden",
               "_total_prepared_burden", "lump_in_burden", "slag_rate"):
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
    """'2026-07' -> 'Jul-26' — the Month column's own header label."""
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
    ytd_months_for_label = [m for m in fy_months if m <= report_month]

    sail_cols = []
    sail_values = {}   # {bf_label: {key: (prev_fy, month, ytd)}}
    for bf in SAIL_BFS:
        plant, unit, label = bf["plant"], bf["unit"], bf["label"]
        sail_cols.append({"label": label, "plant": plant, "unit": unit})
        vals, ytd_months, prev_fy_months = _sail_bf_values(plant, unit, report_month)
        vals["_coke_ash"], vals["_sinter_fe"] = _coke_ash_and_sinter_fe(plant, report_month)
        vals["_avg_daily_rate"] = _avg_daily_rate(vals["production"], report_month, ytd_months, prev_fy_months)
        sp = vals["sinter_in_burden"]
        pl = vals["pellet_in_burden"]
        vals["_total_prepared_burden"] = tuple(
            _round(s + p, 2) if s is not None and p is not None else None for s, p in zip(sp, pl)
        )
        wv = _sail_static_working_volume(plant, unit)
        vals["working_volume_m3"] = (wv, wv, wv)
        sail_values[label] = vals

    rows = []
    for key in _ROW_KEYS:
        label, unit = _row_spec(key)
        dp = _dp_for(key)
        sail_out = {}
        for bf in sail_cols:
            bf_label = bf["label"]
            prev_fy, month, ytd = sail_values[bf_label][key]
            if key == "production":
                prev_fy, month, ytd = _fmt_production(prev_fy), _fmt_production(month), _fmt_production(ytd)
                dp = 3
            sail_out[bf_label] = {
                "prev_fy": _clean(prev_fy, dp), "month": _clean(month, dp), "ytd": _clean(ytd, dp),
            }
        rows.append({"parameter": label, "unit": unit, "sail": sail_out})

    return {
        "title": "Comparison of Performance of Large BFs of SAIL",
        "variant": "bf_large_annexure",
        "sail_cols": sail_cols,
        "prev_fy_col_label": prev_fy_col_label,
        "month_col_label": _month_col_label(report_month),
        "ytd_col_label": _ytd_col_label(ytd_months_for_label),
        "rows": rows,
    }
