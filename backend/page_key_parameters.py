"""
"Key Parameters" — a dense per-plant summary table (BSP/DSP/RSP/BSL/ISP
columns, no SAIL column), page 1.5's structural sibling on the front of the
report. Format sample: Report_format/key_parameters.jpeg ("Performance of
SAIL Plants in Q-1 2026-27").

Sourced from techno_data (BF-shop-level, Coke-Oven-shop-level and General
units — see page_techno.py's BF_SAIL_SPECS for the same key names) and
production_table, using April→report_month cumulative ("till the month")
values, matching the title's period_label — techno parameters read the
stored "till_month" dict (the same cumulative the Techno Manual Entry form
computes/saves), production items are summed (day-weighted average for
Oven Pushings, a Nos./day rate) across the FY-to-date months.

Rows grouped under three section-header bands (Major Production
Performance / Major Blast Furnace Techno-economic Parameters / Recovery of
Process Gases), matching the sample layout. A few rows still have no data
source wired up anywhere yet (CAPEX, Labour Productivity, Avg Rake
Detention Time, HM Sent to PCM/Sand Pit/Dry Pit, Recovery of Process Gases
COG/BFG/LDG) — these read a `techno_data` "General"-unit key that has been
added to the Techno Manual Entry form's template (see
frontend/src/app/data-entry/techno-manual/page.js PARAM_TEMPLATES.General)
so they'll start showing real numbers the moment someone fills them in
there; until then they render as "—". Coke Ash and Sinter Fe already had a
manual-entry home (Coke Ovens' ash_in_coke, Blast Furnace's tfe_in_sinter)
and are now wired up here too.
"""
import calendar as _calendar
import json as _json

import db

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]

# Shop-level BF unit candidates, tried in order (mirrors page_techno.py's
# BF_UNITS) — "BF_Shop" for BSP/DSP/RSP/BSL, "BF-5" for ISP (single-furnace
# plant with no separate shop-aggregate row).
_BF_UNITS = ["BF_Shop", "BF-5"]

# Coke-Oven unit candidates, tried in order (mirrors the frontend's
# COKE_UNITS in techno-manual/page.js) — plants store this shop's data
# under whichever of these names their extractor/manual entry used.
_COKE_UNITS = ["COB", "Coke Ovens", "COB-old", "COB-new"]

# Per-plant SMS unit lists (mirrors page_techno.py's SMS_UNIT_MAP) — TMI is
# shown per-converter, slash-joined, since there's no stored plant-level SMS
# aggregate the way BF has "BF_Shop".
_SMS_UNIT_MAP = {
    "BSP": ["SMS-2", "SMS-3"],
    "DSP": ["SMS"],
    "RSP": ["SMS-1", "SMS-2"],
    "BSL": ["SMS-I", "SMS-II"],
    "ISP": ["SMS"],
}

_GENERAL_UNIT = "General"

# Row-type markers (kind values that short-circuit per-plant computation)
_SECTION = "section"
_SPACER = "spacer"


def _round(v, dp):
    if v is None:
        return None
    return round(v, dp)


def _fetch_techno(report_month: str) -> dict:
    """{(plant, unit): {param: cumulative_value}} — reads the stored
    "till_month" dict (April→report_month cumulative), the same figure the
    Techno Manual Entry form computes/saves via techno_cumulative.py, not
    the report month's own "month" value."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(PLANTS))
        cur.execute(
            f"SELECT plant, unit, techno_json FROM techno_data "
            f"WHERE report_month=? AND plant IN ({ph})",
            [report_month, *PLANTS],
        )
        out = {}
        for plant, unit, tj in cur.fetchall():
            out[(plant, unit)] = _json.loads(tj).get("till_month", {})
        return out
    finally:
        conn.close()


def _fetch_production(ytd_months: list) -> dict:
    """{(plant, item_name): {month: month_actual}} across April→report_month,
    for _prod_val to aggregate (sum, or day-weighted average for Nos./day
    items)."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        ph_p = ",".join("?" * len(PLANTS))
        ph_m = ",".join("?" * len(ytd_months))
        cur.execute(
            f"SELECT plant_name, item_name, report_month, month_actual FROM production_table "
            f"WHERE report_month IN ({ph_m}) AND plant_name IN ({ph_p})",
            [*ytd_months, *PLANTS],
        )
        out = {}
        for p, item, m, v in cur.fetchall():
            if v is not None:
                out.setdefault((p, item), {})[m] = v
        return out
    finally:
        conn.close()


def _bf_unit_for(plant: str, techno: dict) -> str:
    for u in _BF_UNITS:
        if (plant, u) in techno:
            return u
    return _BF_UNITS[0]


def _bf_val(plant, key, techno, dp):
    unit = _bf_unit_for(plant, techno)
    v = techno.get((plant, unit), {}).get(key)
    # DSP's burden mix is sinter + iron ore only, no pellets — matches the
    # zero_fill_plants={"DSP"} convention for Pellet in Burden in
    # page_techno.py's BF_SAIL_SPECS.
    if v is None and key == "pellet_in_burden" and plant == "DSP":
        v = 0.0
    return _round(v, dp)


def _general_val(plant, key, techno, dp):
    return _round(techno.get((plant, _GENERAL_UNIT), {}).get(key), dp)


def _first_present_val(plant, unit_candidates, key_or_keys, techno, dp):
    """Try each candidate unit name in order, return the first non-None
    value found for `key_or_keys` — used for shops (e.g. Coke Ovens) whose
    stored unit name varies by plant, the same fallback idea as
    _bf_unit_for. `key_or_keys` may be a single key or a list of key-name
    aliases (some concepts have been stored under more than one literal key
    across manual entry vs. different extractor generations — e.g. BSP's
    July'26 Ash in Coal Blend was manually entered as
    "average_ash_in_coal_blend" before the "3 page Tech" extractor started
    writing "ash_in_coal_blend" from April'26 onward); aliases are tried in
    the given order per unit."""
    keys = key_or_keys if isinstance(key_or_keys, (list, tuple)) else [key_or_keys]
    for u in unit_candidates:
        d = techno.get((plant, u), {})
        for k in keys:
            v = d.get(k)
            if v is not None:
                return _round(v, dp)
    return None


def _sms_joined(plant, key, techno, dp):
    vals = []
    for u in _SMS_UNIT_MAP.get(plant, []):
        v = techno.get((plant, u), {}).get(key)
        vals.append(f"{_round(v, dp):.{dp}f}" if v is not None else "—")
    return "/".join(vals) if vals else None


# LDG (BOF/LD Gas Yield) — same per-plant SMS shop list as TMI
# (_SMS_UNIT_MAP, slash-joined when a plant reports more than one shop), but
# the stored key name varies by plant: BSP calls it "ld_gas_recovery", DSP
# "bof_gas_yield". RSP/ISP/BSL don't track this parameter in techno_data
# yet — blank until a dedicated source is extracted.
_LDG_KEY_BY_PLANT = {
    "BSP": "ld_gas_recovery",
    "DSP": "bof_gas_yield",
}


def _ldg_val(plant, techno, dp):
    key = _LDG_KEY_BY_PLANT.get(plant)
    if not key:
        return None
    vals = []
    for u in _SMS_UNIT_MAP.get(plant, []):
        v = techno.get((plant, u), {}).get(key)
        vals.append(f"{_round(v, dp):.{dp}f}" if v is not None else "—")
    return "/".join(vals) if vals else None


def _days_in_month(month_str):
    try:
        y, m = int(month_str[:4]), int(month_str[5:7])
        return _calendar.monthrange(y, m)[1]
    except Exception:
        return 30


def _prod_val(plant, item_names, production, dp, ytd_months, nos_day=False):
    """Aggregates a production_table item across ytd_months: summed
    (extensive totals, e.g. Hot Metal) or day-weighted averaged (nos_day=True,
    for Oven Pushings' Nos./day rate)."""
    for item in item_names:
        monthly = production.get((plant, item))
        if not monthly:
            continue
        if nos_day:
            tw, td = 0.0, 0
            for m in ytd_months:
                v = monthly.get(m)
                if v is not None:
                    days = _days_in_month(m)
                    tw += v * days
                    td += days
            if td:
                return _round(tw / td, dp)
        else:
            vals = [monthly[m] for m in ytd_months if m in monthly]
            if vals:
                return _round(sum(vals), dp)
    return None


def _coal_blend_pct(plant, kind, techno, dp):
    """kind: "total" (Imported Coking Coal in Blend) or "soft" (Imported
    Soft Coking Coal in Blend), both % of total coking coal quantity."""
    m = techno.get((plant, _GENERAL_UNIT), {})
    pcc, mcc = m.get("indigenous_pcc"), m.get("indigenous_mcc")
    hard, soft = m.get("imported_hard_coal"), m.get("imported_soft_coal")
    if None in (pcc, mcc, hard, soft):
        return None
    total = pcc + mcc + hard + soft
    if total <= 0:
        return None
    numer = (hard + soft) if kind == "total" else soft
    return _round(numer / total * 100, dp)


def _special_steel_pct(plant, report_month, dp):
    from page_special_steel import generate_special_steel_plant
    try:
        ss = generate_special_steel_plant(report_month, plant)
        v = ss.get("special_pct", {}).get("cum_current")
        return v if v not in (None, "") else None
    except Exception:
        return None


# (label, unit, kind, spec, decimal_places, flags)
#   flags:
#     highlight       - light background on this data row
#     label_rowspan   - merge the parameter-name cell down N rows
#     continuation    - this row shares its parameter-name cell with the
#                       row above (part of a label_rowspan group), so it
#                       renders no parameter cell of its own
_ROWS = [
    ("Major Production Performance", "", _SECTION, None, 0, {}),
    ("Oven Pushings",       "Nos./day", "prod", ["Oven Pushing (nos/day)", "Oven Pushing(nos/d)"], 0, {}),
    ("Sinter",               "'000 T",  "prod", ["Total Sinter"], 0, {}),
    ("Hot Metal",            "'000 T",  "prod", ["Hot Metal"], 0, {}),
    ("Pig Iron",             "'000 T",  "prod", ["Pig Iron"], 1, {}),
    ("Crude Steel",          "'000 T",  "prod", ["Total Crude Steel"], 0, {}),
    ("Finished Steel",       "'000 T",  "prod", ["Finished Steel"], 0, {}),
    ("Saleable Steel",       "'000 T",  "prod", ["Saleable Steel"], 0, {}),
    ("Finished in Total SS", "%",       "ratio_prod", ("Finished Steel", "Saleable Steel"), 1, {"highlight": True}),
    ("Imported Coking Coal in Blend",      "%", "coal_blend", "total", 1, {}),
    ("Imported Soft Coking Coal in Blend", "%", "coal_blend", "soft", 1, {}),

    ("Major Blast Furnace Techno-economic Parameters", "", _SECTION, None, 0, {}),
    ("BF Productivity",     "t/m³/day", "bf", "bf_productivity", 2, {}),
    ("BF Coke Rate",        "kg/THM",   "bf", "coke_rate", 0, {}),
    ("Nut Coke Rate",       "kg/THM",   "bf", "nut_coke_rate", 0, {}),
    ("PCI/CDI Rate",        "kg/THM",   "bf", "cdi", 0, {}),
    ("BF Fuel Rate",        "kg/THM",   "bf", "fuel_rate", 0, {}),
    ("Sinter in Burden",    "%",        "bf", "sinter_in_burden", 1, {}),
    ("Pellet in Burden",    "%",        "bf", "pellet_in_burden", 1, {}),
    ("Total Prepared Burden","%",       "bf_sum", ("sinter_in_burden", "pellet_in_burden"), 1, {}),
    ("Lump in Burden",      "%",        "burden_complement", ("sinter_in_burden", "pellet_in_burden"), 1, {}),
    ("HBT",                 "°C",       "bf", "hot_blast_temp", 0, {}),
    ("O2 Enrichment",       "%",        "bf", "o2_enrichment", 2, {}),
    ("Not Dry Casts",       "%",        "bf", "not_dry_cast", 2, {}),
    ("Coke Ash",            "%",        "coke_unit", "ash_in_coke", 2, {}),
    # Coke-oven-sourced coal-blend quality metric — distinct from "Imported
    # Coking Coal in Blend" above, which is a SAIL-rollup % derived from
    # separate indigenous/imported coal quantities (unit="General"); this
    # reads the "Overall" ash figure the coke-oven techno source reports
    # directly. (A parallel "Imported Coal in Blend" row read from the same
    # coke-oven source was dropped — it duplicated "Imported Coking Coal in
    # Blend" above in concept and was only ever populated for BSP.)
    ("Ash in Coal Blend",   "%",        "coke_unit",
     ["ash_in_coal_blend", "average_ash_in_coal_blend", "ash_blend_coal"], 2, {}),
    ("Sinter Fe",           "%",        "bf", "tfe_in_sinter", 2, {}),
    ("BF Slag Rate",        "kg/THM",   "bf", "slag_rate", 0, {}),
    ("HM Sent to PCM/Sand Pit/Dry Pit", "'000 T", "general", "hm_to_pcm_sandpit_drypit", 1, {"label_rowspan": 2}),
    (None,                  "%",        "ratio_general_prod", ("hm_to_pcm_sandpit_drypit", ["Hot Metal"]), 1, {"continuation": True}),

    ("TMI",                 "kg/TCS",   "sms_join", "tmi", 1, {}),
    ("CHM Ratio",           "",         "general", "coal_to_hm", 3, {}),
    ("SEC",                 "Gcal/TCS", "general", "specific_energy_consumption", 2, {}),
    ("SWC",                 "m³/TCS",   "general", "sp_water_consumption", 2, {}),
    ("Sp CO2 Emission",     "T-CO2/TCS","general", "sp_co2_emission", 2, {}),

    (None, "", _SPACER, None, 0, {}),

    ("CAPEX",                  "Rs Cr",    "general", "capex", 1, {}),
    ("Labour Productivity",    "T/Man-yr", "general", "labour_productivity", 0, {}),
    ("Avg Rake Detention Time","Hrs",      "general", "avg_rake_detention_time", 1, {}),
    ("Value Added Products %", "%",        "special", None, 0, {}),

    ("Recovery of Process Gases", "", _SECTION, None, 0, {}),
    # cog_recovery/bfg_recovery/ldg_recovery below were placeholder keys no
    # extractor ever writes -- these rows were always blank. Mapped to the
    # actual stored parameters instead:
    ("COG", "Nm³/T",    "coke_unit", "coke_oven_gas_yield", 0, {}),
    ("BFG", "Nm³/THM",  "bf", "bf_gas_yield", 0, {}),
    ("LDG", "Nm³/TCS",  "ldg", None, 0, {}),
]


def generate_key_parameters(report_month: str) -> dict:
    ytd_months = db.get_ytd_months(report_month)
    techno = _fetch_techno(report_month)
    production = _fetch_production(ytd_months)

    import datetime as _dt
    period_label = _dt.datetime.strptime(ytd_months[0], "%Y-%m").strftime("%b")
    if len(ytd_months) > 1:
        period_label += "-" + _dt.datetime.strptime(ytd_months[-1], "%Y-%m").strftime("%b")
    report_year_2d = report_month[2:4]
    fy_year = int(report_month[:4]) if int(report_month[5:7]) >= 4 else int(report_month[:4]) - 1
    fy_label = f"{fy_year}-{(fy_year + 1) % 100:02d}"

    rows = []
    for label, unit, kind, spec, dp, flags in _ROWS:
        if kind == _SECTION:
            rows.append({"type": "section", "label": label})
            continue
        if kind == _SPACER:
            rows.append({"type": "spacer"})
            continue

        values = {}
        for plant in PLANTS:
            if kind == "prod":
                v = _prod_val(plant, spec, production, dp, ytd_months,
                              nos_day=(unit == "Nos./day"))
            elif kind == "bf":
                v = _bf_val(plant, spec, techno, dp)
            elif kind == "general":
                v = _general_val(plant, spec, techno, dp)
            elif kind == "sms_join":
                v = _sms_joined(plant, spec, techno, dp)
            elif kind == "coal_blend":
                v = _coal_blend_pct(plant, spec, techno, dp)
            elif kind == "coke_unit":
                # Any parameter scoped to the coke-oven unit (Coke Ash, COG)
                # — stored under whichever of COB/Coke Ovens/COB-old/COB-new
                # this plant's extractor used.
                v = _first_present_val(plant, _COKE_UNITS, spec, techno, dp)
            elif kind == "ldg":
                v = _ldg_val(plant, techno, dp)
            elif kind == "bf_sum":
                a = _bf_val(plant, spec[0], techno, dp)
                b = _bf_val(plant, spec[1], techno, dp)
                v = _round(a + b, dp) if a is not None and b is not None else None
            elif kind == "burden_complement":
                # Lump in Burden = 100 - Total Prepared Burden, using the
                # SAME rounded component values as the Total Prepared
                # Burden row above so the three burden rows sum to exactly
                # 100 as displayed.
                a = _bf_val(plant, spec[0], techno, dp)
                b = _bf_val(plant, spec[1], techno, dp)
                v = _round(100 - (a + b), dp) if a is not None and b is not None else None
            elif kind == "ratio_prod":
                num = _prod_val(plant, [spec[0]], production, 6, ytd_months)
                den = _prod_val(plant, [spec[1]], production, 6, ytd_months)
                v = _round(num / den * 100, dp) if num is not None and den else None
            elif kind == "ratio_general_prod":
                gkey, prod_items = spec
                num = _general_val(plant, gkey, techno, 6)
                den = _prod_val(plant, prod_items, production, 6, ytd_months)
                v = _round(num / den * 100, dp) if num is not None and den else None
            elif kind == "special":
                v = _special_steel_pct(plant, report_month, dp)
            else:
                v = None
            values[plant] = v
        # NOT "values" - Jinja2's dot-notation resolves that to dict.values
        # (the built-in method) before falling back to item lookup, since
        # getattr succeeds first; row.plant_values avoids the collision.
        row = {"type": "data", "parameter": label, "unit": unit, "plant_values": values}
        if flags.get("highlight"):
            row["highlight"] = True
        if flags.get("label_rowspan"):
            row["label_rowspan"] = flags["label_rowspan"]
        if flags.get("continuation"):
            row["continuation"] = True
        rows.append(row)

    return {
        "title": f"Performance of SAIL Plants — {period_label}'{report_year_2d} (FY {fy_label})",
        "plants": PLANTS,
        "rows": rows,
    }
