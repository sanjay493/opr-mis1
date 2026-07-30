"""
"Key Parameters" — a dense per-plant summary table (BSP/DSP/RSP/BSL/ISP
columns, no SAIL column), page 1.5's structural sibling on the front of the
report. Format sample: Report_format/key_parameters.jpeg ("Performance of
SAIL Plants in Q-1 2026-27").

Sourced from techno_data (BF-shop-level and General units — see
page_techno.py's BF_SAIL_SPECS for the same key names) and production_table,
using the report month's own values (not a quarterly average like the
sample — this report is monthly). Rows the sample has that aren't backed by
any current data source (Coke Ash, Sinter Fe, Lump in Burden, HM Sent to
PCM/Sand-Pit/Dry Pit, Specific Power Consumption, CAPEX, Labour
Productivity, Avg Rake Detention Time, Recovery of Process Gases) are left
out rather than shown permanently blank — add them here once a source
exists.
"""
import json as _json

import db

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]

# Shop-level BF unit candidates, tried in order (mirrors page_techno.py's
# BF_UNITS) — "BF_Shop" for BSP/DSP/RSP/BSL, "BF-5" for ISP (single-furnace
# plant with no separate shop-aggregate row).
_BF_UNITS = ["BF_Shop", "BF-5"]

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


def _round(v, dp):
    if v is None:
        return None
    return round(v, dp)


def _fetch_techno(report_month: str) -> dict:
    """{(plant, unit): {month: {...}}}"""
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
            out[(plant, unit)] = _json.loads(tj).get("month", {})
        return out
    finally:
        conn.close()


def _fetch_production(report_month: str) -> dict:
    """{(plant, item_name): month_actual}"""
    conn = db.connect()
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(PLANTS))
        cur.execute(
            f"SELECT plant_name, item_name, month_actual FROM production_table "
            f"WHERE report_month=? AND plant_name IN ({ph})",
            [report_month, *PLANTS],
        )
        return {(p, item): v for p, item, v in cur.fetchall() if v is not None}
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


def _sms_joined(plant, key, techno, dp):
    vals = []
    for u in _SMS_UNIT_MAP.get(plant, []):
        v = techno.get((plant, u), {}).get(key)
        vals.append(f"{_round(v, dp):.{dp}f}" if v is not None else "—")
    return "/".join(vals) if vals else None


def _prod_val(plant, item_names, production, dp):
    for item in item_names:
        v = production.get((plant, item))
        if v is not None:
            return _round(v, dp)
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
        v = ss.get("special_pct", {}).get("current")
        return v if v not in (None, "") else None
    except Exception:
        return None


# (label, unit, kind, spec, decimal_places)
_ROWS = [
    ("Oven Pushings",       "Nos./day", "prod", ["Oven Pushing (nos/day)", "Oven Pushing(nos/d)"], 0),
    ("Sinter Prod",         "'000 T",   "prod", ["Total Sinter"], 0),
    ("HM Prod",             "'000 T",   "prod", ["Hot Metal"], 0),
    ("Pig Iron",            "'000 T",   "prod", ["Pig Iron"], 1),
    ("CS Prod",             "'000 T",   "prod", ["Total Crude Steel"], 0),
    ("FS Prod",             "'000 T",   "prod", ["Finished Steel"], 0),
    ("SS Prod",             "'000 T",   "prod", ["Saleable Steel"], 0),
    ("Finished in Total SS","%",        "ratio_prod", ("Finished Steel", "Saleable Steel"), 1),
    ("Imported Coking Coal in Blend",      "%", "coal_blend", "total", 1),
    ("Imported Soft Coking Coal in Blend", "%", "coal_blend", "soft", 1),
    ("BF Productivity",     "t/m³/day", "bf", "bf_productivity", 2),
    ("BF Coke Rate",        "kg/THM",   "bf", "coke_rate", 0),
    ("Nut Coke Rate",       "kg/THM",   "bf", "nut_coke_rate", 0),
    ("PCI/CDI Rate",        "kg/THM",   "bf", "cdi", 0),
    ("BF Fuel Rate",        "kg/THM",   "bf", "fuel_rate", 0),
    ("Sinter in Burden",    "%",        "bf", "sinter_in_burden", 1),
    ("Pellet in Burden",    "%",        "bf", "pellet_in_burden", 1),
    ("Total Prepared Burden","%",       "bf_sum", ("sinter_in_burden", "pellet_in_burden"), 1),
    ("HBT",                 "°C",       "bf", "hot_blast_temp", 0),
    ("O2 Enrichment",       "%",        "bf", "o2_enrichment", 2),
    ("Not Dry Casts",       "%",        "bf", "not_dry_cast", 2),
    ("BF Slag Rate",        "kg/THM",   "bf", "slag_rate", 0),
    ("TMI",                 "kg/TCS",   "sms_join", "tmi", 1),
    ("CHM Ratio",           "",         "general", "coal_to_hm", 3),
    ("SEC",                 "Gcal/TCS", "general", "specific_energy_consumption", 2),
    ("SWC",                 "m³/TCS",   "general", "sp_water_consumption", 2),
    ("Sp CO2 Emission",     "T-CO2/TCS","general", "sp_co2_emission", 2),
    ("Special Steel % of Saleable Steel", "%", "special", None, 0),
]


def generate_key_parameters(report_month: str) -> dict:
    techno = _fetch_techno(report_month)
    production = _fetch_production(report_month)

    ytd_months = db.get_ytd_months(report_month)
    import datetime as _dt
    period_label = _dt.datetime.strptime(ytd_months[0], "%Y-%m").strftime("%b")
    if len(ytd_months) > 1:
        period_label += "-" + _dt.datetime.strptime(ytd_months[-1], "%Y-%m").strftime("%b")
    report_year_2d = report_month[2:4]
    fy_year = int(report_month[:4]) if int(report_month[5:7]) >= 4 else int(report_month[:4]) - 1
    fy_label = f"{fy_year}-{(fy_year + 1) % 100:02d}"

    rows = []
    for label, unit, kind, spec, dp in _ROWS:
        values = {}
        for plant in PLANTS:
            if kind == "prod":
                v = _prod_val(plant, spec, production, dp)
            elif kind == "bf":
                v = _bf_val(plant, spec, techno, dp)
            elif kind == "general":
                v = _general_val(plant, spec, techno, dp)
            elif kind == "sms_join":
                v = _sms_joined(plant, spec, techno, dp)
            elif kind == "coal_blend":
                v = _coal_blend_pct(plant, spec, techno, dp)
            elif kind == "bf_sum":
                a = _bf_val(plant, spec[0], techno, dp)
                b = _bf_val(plant, spec[1], techno, dp)
                v = _round(a + b, dp) if a is not None and b is not None else None
            elif kind == "ratio_prod":
                num = _prod_val(plant, [spec[0]], production, 6)
                den = _prod_val(plant, [spec[1]], production, 6)
                v = _round(num / den * 100, dp) if num is not None and den else None
            elif kind == "special":
                v = _special_steel_pct(plant, report_month, dp)
            else:
                v = None
            values[plant] = v if v is not None else None
        # NOT "values" - Jinja2's dot-notation resolves that to dict.values
        # (the built-in method) before falling back to item lookup, since
        # getattr succeeds first; row.plant_values avoids the collision.
        rows.append({"parameter": label, "unit": unit, "plant_values": values})

    return {
        "title": f"Performance of SAIL Plants — {period_label}'{report_year_2d} (FY {fy_label})",
        "plants": PLANTS,
        "rows": rows,
    }
