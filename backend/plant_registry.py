"""
Plant and unit registry for the SAIL MIS system.

Defines all physical units (blast furnaces, converters, mills, etc.) at each
integrated steel plant, plus the standard techno-economic parameters for each
unit type with their aggregation rules for computing shop averages.

Designed for scalability: adding a new plant or a new unit is a single row here
and the rest of the system picks it up automatically.
"""

# ---------------------------------------------------------------------------
# Unit type codes (short, stable identifiers used as DB keys)
# ---------------------------------------------------------------------------
UNIT_TYPES = {
    "BF":      "Blast Furnace",
    "SMS":     "Steel Melting Shop (Converter)",
    "MILL":    "Rolling Mill",
    "COKE":    "Coke Oven",
    "SINTER":  "Sinter Plant",
    "GENERAL": "Plant-Level General",
}

# ---------------------------------------------------------------------------
# Plant units registry
# Each entry: (plant_code, unit_type, unit_name, is_shop, sort_order)
#   plant_code  — 'BSP' / 'DSP' / 'RSP' / 'BSL' / 'ISP'
#   unit_type   — key from UNIT_TYPES above
#   unit_name   — short name of the unit ('BF-4', 'SMS-2', 'HSM', 'Shop')
#   is_shop     — 1 if this is the plant-level shop / average row, not a physical unit
#   sort_order  — display order within (plant, unit_type)
#
# display_label (stored in DB) = f"{plant_code} {unit_name}"
# ---------------------------------------------------------------------------
PLANT_UNITS = [
    # ── BSP (Bhilai Steel Plant) ─────────────────────────────────────────────
    # Blast Furnaces
    ("BSP", "BF",   "BF-4",      0,  10),
    ("BSP", "BF",   "BF-6",      0,  20),
    ("BSP", "BF",   "BF-7",      0,  30),
    ("BSP", "BF",   "BF-8",      0,  40),
    ("BSP", "BF",   "Shop",      1,  50),   # plant avg across all BFs
    # Converters / SMS
    ("BSP", "SMS",  "SMS-2",     0,  60),
    ("BSP", "SMS",  "SMS-3",     0,  70),
    ("BSP", "SMS",  "Shop",      1,  80),
    # Rolling Mills
    ("BSP", "MILL", "RSM",       0,  90),
    ("BSP", "MILL", "URM",       0, 100),
    ("BSP", "MILL", "MM",        0, 110),
    ("BSP", "MILL", "BRM",       0, 120),
    ("BSP", "MILL", "WRM",       0, 130),
    ("BSP", "MILL", "Plate Mill",0, 140),

    # ── DSP (Durgapur Steel Plant) ───────────────────────────────────────────
    ("DSP", "BF",   "BF-2",      0,  10),
    ("DSP", "BF",   "BF-3",      0,  20),
    ("DSP", "BF",   "BF-4",      0,  30),
    ("DSP", "BF",   "Shop",      1,  40),
    ("DSP", "SMS",  "SMS",       0,  50),
    ("DSP", "SMS",  "Shop",      1,  60),
    ("DSP", "MILL", "WAP",       0,  70),
    ("DSP", "MILL", "MM",        0,  80),
    ("DSP", "MILL", "MSM",       0,  90),

    # ── RSP (Rourkela Steel Plant) ───────────────────────────────────────────
    ("RSP", "BF",   "BF-1",      0,  10),
    ("RSP", "BF",   "BF-4",      0,  20),
    ("RSP", "BF",   "BF-5",      0,  30),
    ("RSP", "BF",   "Shop",      1,  40),
    ("RSP", "SMS",  "SMS-1",     0,  50),
    ("RSP", "SMS",  "SMS-2",     0,  60),
    ("RSP", "SMS",  "Shop",      1,  70),
    ("RSP", "MILL", "PM",        0,  80),
    ("RSP", "MILL", "NPM",       0,  90),
    ("RSP", "MILL", "HSM-2",     0, 100),

    # ── BSL (Bokaro Steel Plant) ─────────────────────────────────────────────
    ("BSL", "BF",   "BF-1",      0,  10),
    ("BSL", "BF",   "BF-2",      0,  20),
    ("BSL", "BF",   "BF-3",      0,  30),
    ("BSL", "BF",   "BF-4",      0,  40),
    ("BSL", "BF",   "BF-5",      0,  50),
    ("BSL", "BF",   "Shop",      1,  60),
    ("BSL", "SMS",  "SMS-1",     0,  70),
    ("BSL", "SMS",  "SMS-2",     0,  80),
    ("BSL", "SMS",  "Shop",      1,  90),
    ("BSL", "MILL", "HSM",       0, 100),
    ("BSL", "MILL", "CRM-1&2",   0, 110),
    ("BSL", "MILL", "CRM-3",     0, 120),

    # ── ISP (IISCO Steel Plant) ──────────────────────────────────────────────
    ("ISP", "BF",   "BF-5",      0,  10),
    ("ISP", "BF",   "Shop",      1,  20),   # single BF: furnace == shop
    ("ISP", "SMS",  "SMS",       0,  30),
    ("ISP", "SMS",  "Shop",      1,  40),
    ("ISP", "MILL", "USM",       0,  50),
    ("ISP", "MILL", "BRM",       0,  60),
    ("ISP", "MILL", "WRM",       0,  70),
]

# ---------------------------------------------------------------------------
# Standard techno-economic parameters per unit type
# Each entry: (unit_type, param_name, unit_of_measurement, agg_method, sort_order)
#   agg_method — how to compute the shop/plant average from per-unit values:
#     'weighted_avg'  : Σ(val × production) / Σ(production)
#     'harmonic_mean' : Σ(production) / Σ(production/val)
#     'simple_avg'    : Σ(val) / n
#     'sum'           : Σ(val) — e.g. total blows, total heats
# ---------------------------------------------------------------------------
PARAM_TYPES = [
    # ── Blast Furnace ────────────────────────────────────────────────────────
    ("BF", "CDI Rate",             "Kg/THM",    "weighted_avg",   10),
    ("BF", "Coke Rate",            "Kg/THM",    "weighted_avg",   20),
    ("BF", "Nut Coke Rate",        "Kg/THM",    "weighted_avg",   30),
    ("BF", "Fuel Rate",            "Kg/THM",    "weighted_avg",   40),
    ("BF", "BF Productivity",      "T/m³/day",  "harmonic_mean",  50),
    ("BF", "HBT",                  "°C",        "simple_avg",     60),
    ("BF", "Si in HM",             "%",         "weighted_avg",   70),
    ("BF", "S in HM",              "%",         "weighted_avg",   80),
    ("BF", "Sinter in Burden",     "%",         "weighted_avg",   90),
    ("BF", "Pellet in Burden",     "%",         "weighted_avg",  100),
    ("BF", "O2 Enrichment",        "%",         "simple_avg",    110),
    ("BF", "Slag Rate",            "Kg/THM",    "weighted_avg",  120),
    ("BF", "Hot Metal Temp",       "°C",        "simple_avg",    130),
    ("BF", "Iron Ore",             "T",         "sum",           140),
    ("BF", "Sinter",               "T",         "sum",           150),
    ("BF", "Pellet",               "T",         "sum",           160),
    ("BF", "Scrap",                "T",         "sum",           170),

    # ── SMS / Converter ──────────────────────────────────────────────────────
    ("SMS", "HM Consumption",      "Kg/TCS",    "weighted_avg",   10),
    ("SMS", "Scrap Consumption",   "Kg/TCS",    "weighted_avg",   20),
    ("SMS", "TMI",                 "Kg/TCS",    "weighted_avg",   30),
    ("SMS", "Blows per Day",       "Nos./day",  "sum",            40),
    ("SMS", "Heat Weight",         "T",         "weighted_avg",   50),
    ("SMS", "O2 Blow per T CS",    "Nm³/TCS",   "weighted_avg",   60),
    ("SMS", "Fe-Mn Consumption",   "Kg/TCS",    "weighted_avg",   70),
    ("SMS", "Si-Mn Consumption",   "Kg/TCS",    "weighted_avg",   80),
    ("SMS", "Fe-Si Consumption",   "Kg/TCS",    "weighted_avg",   90),
    ("SMS", "Lime Consumption",    "Kg/TCS",    "weighted_avg",  100),
    ("SMS", "Tap to Tap Time",     "Min",       "simple_avg",    110),
    ("SMS", "Cast Sequence",       "Heats",     "simple_avg",    120),
    ("SMS", "Converter Av%",       "%",         "simple_avg",    130),
    ("SMS", "Converter Ut%",       "%",         "simple_avg",    140),
    ("SMS", "Caster Av%",          "%",         "simple_avg",    150),
    ("SMS", "Caster Ut%",          "%",         "simple_avg",    160),
    ("SMS", "Caster Yield",        "%",         "weighted_avg",  170),
    ("SMS", "Converter Yield",     "%",         "weighted_avg",  180),
    ("SMS", "Refractory Cons.",    "Kg/T",      "weighted_avg",  190),

    # ── Rolling Mill ─────────────────────────────────────────────────────────
    ("MILL", "Availability%",      "%",         "simple_avg",    10),
    ("MILL", "Utilisation%",       "%",         "simple_avg",    20),
    ("MILL", "Rolling Rate",       "T/hr",      "simple_avg",    30),
    ("MILL", "Sp. Power Cons.",    "KWh/T",     "weighted_avg",  40),
    ("MILL", "Heat Consumption",   "Mcal/T",    "weighted_avg",  50),
    ("MILL", "Yield",              "%",         "weighted_avg",  60),

    # ── Coke Ovens ───────────────────────────────────────────────────────────
    ("COKE", "BF Coke Yield",      "%",         "weighted_avg",  10),
    ("COKE", "Dry Coal Charge",    "T/oven",    "simple_avg",    20),
    ("COKE", "COG Yield",          "M³/T DC",   "weighted_avg",  30),
    ("COKE", "Crude Benzol Yield", "Kg/T DC",   "weighted_avg",  40),
    ("COKE", "Amm. Sulphate Yield","Kg/T DC",   "weighted_avg",  50),
    ("COKE", "Coke Screen Loss",   "%",         "simple_avg",    60),
    ("COKE", "M-10",               "%",         "simple_avg",    70),
    ("COKE", "M-40",               "%",         "simple_avg",    80),
    ("COKE", "CSR",                "%",         "simple_avg",    90),

    # ── Sinter Plant ─────────────────────────────────────────────────────────
    ("SINTER", "Machine Productivity","T/m²/hr","weighted_avg",  10),
    ("SINTER", "Sinter Return%",   "%",         "simple_avg",    20),
    ("SINTER", "Fe% in Sinter",    "%",         "simple_avg",    30),
    ("SINTER", "Basicity",         "",          "simple_avg",    40),

    # ── General / Plant-level ────────────────────────────────────────────────
    ("GENERAL", "Sp. Water Cons.",   "m³/TCS",  "weighted_avg",  10),
    ("GENERAL", "Sp. Energy Cons.",  "GJ/TCS",  "weighted_avg",  20),
    ("GENERAL", "Sp. CO2 Emission",  "T CO2/TCS","weighted_avg", 30),
    ("GENERAL", "Labour Productivity","T/Man-yr","simple_avg",   40),
]


def seed_plant_registry(conn):
    """
    Seed plant_units and techno_param_types tables from the definitions above.
    Safe to call multiple times — uses INSERT OR IGNORE.
    Returns (units_added, param_types_added).
    """
    cur = conn.cursor()

    units_added = 0
    for plant_code, unit_type, unit_name, is_shop, sort_order in PLANT_UNITS:
        if is_shop:
            display_label = f"{plant_code} Plant Shop"
        else:
            display_label = f"{plant_code} {unit_name}"
        cur.execute("""
            INSERT OR IGNORE INTO plant_units
                (plant_code, unit_type, unit_name, display_label, is_shop, is_active, sort_order)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (plant_code, unit_type, unit_name, display_label, is_shop, sort_order))
        units_added += cur.rowcount

    param_types_added = 0
    for unit_type, param_name, unit_of_meas, agg_method, sort_order in PARAM_TYPES:
        cur.execute("""
            INSERT OR IGNORE INTO techno_param_types
                (unit_type, param_name, unit_of_meas, agg_method, sort_order)
            VALUES (?, ?, ?, ?, ?)
        """, (unit_type, param_name, unit_of_meas, agg_method, sort_order))
        param_types_added += cur.rowcount

    conn.commit()
    return units_added, param_types_added


def get_plant_units(conn, plant_code=None, unit_type=None, include_shop=True):
    """Query plant_units with optional filters. Returns list of dicts."""
    sql = "SELECT unit_id, plant_code, unit_type, unit_name, display_label, is_shop, sort_order FROM plant_units WHERE is_active=1"
    args = []
    if plant_code:
        sql += " AND plant_code=?"
        args.append(plant_code)
    if unit_type:
        sql += " AND unit_type=?"
        args.append(unit_type)
    if not include_shop:
        sql += " AND is_shop=0"
    sql += " ORDER BY plant_code, sort_order"
    cur = conn.execute(sql, args)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_param_types(conn, unit_type=None):
    """Query techno_param_types with optional unit_type filter. Returns list of dicts."""
    sql = "SELECT type_id, unit_type, param_name, unit_of_meas, agg_method, sort_order FROM techno_param_types"
    args = []
    if unit_type:
        sql += " WHERE unit_type=?"
        args.append(unit_type)
    sql += " ORDER BY unit_type, sort_order"
    cur = conn.execute(sql, args)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]
