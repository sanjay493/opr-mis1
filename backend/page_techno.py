"""
Techno-Economic Parameter pages — pages 27-35.

Data source: techno_actuals JOIN techno_param (replaces techno_table + techno_param_master)
Display ordering: techno_param_group (group_code, sort_order)
Annual targets:   techno_target JOIN techno_param JOIN techno_param_group

Column layout:
  <FY-2> Actual | <FY-1> Actual | Target <FY> |
  Apr'YY … <report month> | <CPLY month> | Apr-<Mon>'YY | Apr-<Mon>'YY-1

Annual FY value: stored March till_month_actual only (represents full FY Apr-Mar).
                 Empty if March data not in DB (no fallback averaging).
YTD value:       stored till_month_actual if present; else computed from monthly actuals Apr→month.

SAIL row computation (MAJOR page + Summary page te_table):
  BF params (Coal/HM, Coke, Nut Coke, CDI Rate, Fuel, Sinter%, Pellet%):
      weighted average of plant values, weight = plant Hot Metal production
  BF Productivity:
      SAIL = Σ(HM) / Σ(HM / plant_BFprod)
  SMS params (HM Consumption, Scrap, TMI):
      weighted average of shop values, weight = plant Crude Steel / shops_per_plant
  Specific Energy Consumption:
      weighted average of plant values, weight = plant Crude Steel production
"""
import sqlite3
import db

_MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# ---------------------------------------------------------------------------
# Page registry
# ---------------------------------------------------------------------------

_DSP_FURNACE_SECTIONS = frozenset({"Si in HM", "S in HM", "HBT"})

_COKE_SINTER_VISIBLE = frozenset({
    "Dry Coal Charge/Oven", "Coal Tar Yield", "Coke Oven Gas Yield",
    "Crude Benzol Yield", "Amm. Sulphate Yld", "Sinter Productivity",

})

_BOF_VISIBLE = frozenset({
    "Average Blows (Per Day)", "Average Heat Weight", "Oxygen Blowing",
    "Refractory", "Hot Metal Consumption", "Scrap Consumption", "TMI",
    "Converter Yield", "Caster Availability", "Caster Utilisation",
    "Caster Yield", "Avg Cast Sequence", "Fe-Mn Consumption",
    "Fe-Si Consumption", "Si-Mn Consumption", "Lime Consumption",
    "LD Gas Recovery", "Tap to Tap Time",
})

_IRON_MAKING_VISIBLE = frozenset({
    "CDI Rate", 
    # "Si in HM", "S in HM", "HBT", 
    "Coke Screen Loss",
})

TECHNO_PAGES = {
    27: ("MAJOR",       "MAJOR TECHNO-ECONOMIC PARAMETERS", ""),
    28: ("COKE_SINTER", "MONTH-WISE TECHNO-ECONOMIC PARAMETERS", "COKE AND COAL CHEMICALS, SINTER PLANT"),
    29: ("IRON_MAKING", "MONTH-WISE TECHNO-ECONOMIC PARAMETERS", "IRON MAKING"),
    30: ("SMS",         "MONTH-WISE TECHNO-ECONOMIC PARAMETERS", "SMS SHOP"),
    31: ("MILL_BSP",    "MILL WISE TECHNO-ECONOMIC PARAMETERS", "Bhilai Steel Plant"),
    32: ("MILL_DSP",    "MILL WISE TECHNO-ECONOMIC PARAMETERS", "Durgapur Steel Plant"),
    33: ("MILL_RSP",    "MILL WISE TECHNO-ECONOMIC PARAMETERS", "Rourkela Steel Plant"),
    34: ("MILL_BSL",    "MILL WISE TECHNO-ECONOMIC PARAMETERS", "Bokaro Steel Plant"),
    35: ("MILL_ISP",    "MILL WISE TECHNO-ECONOMIC PARAMETERS", "IISCO Steel Plant"),
}

# ---------------------------------------------------------------------------
# SAIL weighted-average constants  (string-based, no param_ids)
# ---------------------------------------------------------------------------

_BF_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]

# BF parameters weighted by Hot Metal production
_BF_HM_PARAMS = [
    "Coal to Hot Metal", "Coke Rate", "Nut Coke Rate",
    "CDI Rate", "Fuel Rate", "Sinter in Burden", "Pellet in Burden",
]

# SMS shops and their plant mapping
_SMS_SHOPS = [
    "BSP SMS-2", "BSP SMS-3", "DSP SMS",
    "RSP SMS-1", "RSP SMS-2",
    "BSL SMS-1", "BSL SMS-2",
    "ISP SMS-1",
]
_SMS_SHOP_PLANT = {
    "BSP SMS-2": "BSP", "BSP SMS-3": "BSP", "DSP SMS": "DSP",
    "RSP SMS-1": "RSP", "RSP SMS-2": "RSP",
    "BSL SMS-1": "BSL", "BSL SMS-2": "BSL", "ISP SMS-1": "ISP",
}
_PLANT_SHOP_CNT = {"BSP": 2, "DSP": 1, "RSP": 2, "BSL": 2, "ISP": 1}

_SMS_PARAMS = ["Hot Metal Consumption", "Scrap Consumption", "TMI"]

# Plant BF per-furnace aggregation methods (canonical param names)
# Aggregation happens only if Plant Shop data is missing; otherwise uses stored Plant Shop data

_BF_AGG_METHODS = {
    # Weighted by HM production
    "CDI Rate":         "wtavg",
    "BF Coke Rate":     "wtavg",
    "Coke Rate":        "wtavg",
    "Nut Coke Rate":    "wtavg",
    "Fuel Rate":        "wtavg",
    "Sinter in Burden": "wtavg",
    "Pellet in Burden": "wtavg",
    "Si in HM":         "wtavg",
    "S in HM":          "wtavg",
    "Slag Rate":        "wtavg",
    "O2 Enrichment":    "wtavg",
    # Harmonic mean
    "BF Productivity":  "harmonic",
    # Simple average
    "HBT":              "simple",
    "Hot Metal Temp":   "simple",
    # Sum
    "Iron Ore":         "sum",
    "Sinter Consumption": "sum",
    "BF Scrap":         "sum",
    "Pellet Consumption": "sum",
}

# Plant furnace configurations
_PLANT_FURNACES = {
    "BSP": ["BSP BF-4", "BSP BF-5", "BSP BF-6", "BSP BF-7", "BSP BF-8"],
    "RSP": ["RSP BF-1", "RSP BF-4", "RSP BF-5"],
    "DSP": ["DSP BF-1", "DSP BF-2", "DSP BF-3"],
    "BSL": ["BSL BF-1", "BSL BF-2", "BSL BF-3", "BSL BF-4", "BSL BF-5"],
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fy_start(report_month):
    y, m = int(report_month[:4]), int(report_month[5:7])
    return y if m >= 4 else y - 1

def _fy_months(fy):
    out = []
    for i in range(12):
        y, m = fy + (4 + i - 1) // 12, (4 + i - 1) % 12 + 1
        out.append(f"{y}-{m:02d}")
    return out

def _fy_label(fy):
    return f"{fy}-{(fy + 1) % 100:02d}"

def _mlabel(ym):
    return f"{_MON[int(ym[5:7])]}'{ym[2:4]}"

def _cum_label(months):
    if len(months) == 1:
        return _mlabel(months[0])
    return f"{_MON[int(months[0][5:7])]}-{_mlabel(months[-1])}"

def _fmt(v):
    if v is None:
        return ""
    a = abs(v)
    if a >= 100:
        return str(int(round(v)))
    if a >= 10:
        s = f"{v:.1f}"
    elif a >= 1:
        s = f"{v:.2f}"
    else:
        s = f"{v:.3f}"
    return s.rstrip("0").rstrip(".") if "." in s else s

# ---------------------------------------------------------------------------
# Data access — techno_actuals JOIN techno_param
# ---------------------------------------------------------------------------

def _avg_map(cur, months):
    """(row_label, param_name) → AVG(actual) over given months."""
    if not months:
        return {}
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT p.row_label, p.param_name, AVG(a.actual)
        FROM techno_actuals a
        JOIN techno_param p ON a.param_id = p.param_id
        WHERE a.report_month IN ({ph}) AND a.actual IS NOT NULL
        GROUP BY p.row_label, p.param_name
    """, months)
    return {(r[0], r[1]): r[2] for r in cur.fetchall()}


def _ytd_of_month(cur, month):
    """(row_label, param_name) → YTD value.
    Uses stored till_month_actual if present; otherwise AVG(actual) Apr→month."""
    # 1. Stored till_month_actual for this month
    cur.execute("""
        SELECT p.row_label, p.param_name, a.till_month_actual
        FROM techno_actuals a
        JOIN techno_param p ON a.param_id = p.param_id
        WHERE a.report_month = ? AND a.till_month_actual IS NOT NULL
    """, (month,))
    out = {(r[0], r[1]): r[2] for r in cur.fetchall()}
    # 2. Compute from monthly actuals for those without stored value
    fy = _fy_start(month)
    ytd_months = [m for m in _fy_months(fy) if m <= month]
    for key, val in _avg_map(cur, ytd_months).items():
        out.setdefault(key, val)
    return out


def _annual_map(cur, fy):
    """(row_label, param_name) → annual value for a past FY.
    Uses stored March till_month_actual only (represents full FY Apr-Mar).
    Empty if March data not in DB. No fallback averaging.
    Returns (map, stored_keys) where stored_keys came from plant-reported till_month_actual."""
    march = f"{fy + 1}-03"
    # Fetch March till_month_actual (plant-reported annual cumulative Apr-Mar)
    cur.execute("""
        SELECT p.row_label, p.param_name, a.till_month_actual
        FROM techno_actuals a
        JOIN techno_param p ON a.param_id = p.param_id
        WHERE a.report_month = ? AND a.till_month_actual IS NOT NULL
    """, (march,))
    out = {(r[0], r[1]): r[2] for r in cur.fetchall()}
    stored_keys = set(out.keys())
    return out, stored_keys


def _fetch_techno_data(cur, plant_params, months):
    """Return {(row_label, param_name): {month: actual}} for the given pairs and months.
    Also computes TMI as HM Consumption + Scrap Consumption if not in DB."""
    if not plant_params or not months:
        return {}
    pp_set  = set(plant_params)
    entities = list({p  for p, _ in pp_set})
    params   = list({pm for _, pm in pp_set})
    ph_m  = ",".join("?" * len(months))
    ph_p  = ",".join("?" * len(entities))
    ph_pm = ",".join("?" * len(params))
    cur.execute(
        f"SELECT p.row_label, p.param_name, a.report_month, a.actual "
        f"FROM techno_actuals a "
        f"JOIN techno_param p ON a.param_id = p.param_id "
        f"WHERE a.report_month IN ({ph_m}) AND p.row_label IN ({ph_p}) AND p.param_name IN ({ph_pm})",
        list(months) + entities + params,
    )
    result = {}
    for rl, pn, month, val in cur.fetchall():
        if val is not None and (rl, pn) in pp_set:
            result.setdefault((rl, pn), {})[month] = val

    # Compute TMI as HM Consumption + Scrap Consumption for SMS shops if not in DB
    for rl in entities:
        if rl in _SMS_SHOPS:  # Only for SMS shops
            tmi_data = {}
            for month in months:
                hm_v = result.get((rl, "Hot Metal Consumption"), {}).get(month)
                scrap_v = result.get((rl, "Scrap Consumption"), {}).get(month)
                if hm_v is not None and scrap_v is not None:
                    tmi_val = result.get((rl, "TMI"), {}).get(month)
                    # Only compute if TMI not already in DB
                    if tmi_val is None:
                        tmi_data[month] = hm_v + scrap_v
            if tmi_data:
                result.setdefault((rl, "TMI"), {}).update(tmi_data)

    return result


def _fetch_prod_multi(cur, plants, item_names, months):
    """Return {item_name: {plant: {month: value}}} from production_table."""
    if not plants or not item_names or not months:
        return {i: {p: {} for p in plants} for i in item_names}
    ph_p = ",".join("?" * len(plants))
    ph_m = ",".join("?" * len(months))
    ph_i = ",".join("?" * len(item_names))
    cur.execute(
        f"SELECT item_name, plant_name, report_month, month_actual FROM production_table "
        f"WHERE plant_name IN ({ph_p}) AND item_name IN ({ph_i}) AND report_month IN ({ph_m})",
        list(plants) + list(item_names) + list(months),
    )
    result = {i: {p: {} for p in plants} for i in item_names}
    for item, plant, month, val in cur.fetchall():
        if val is not None and item in result and plant in result[item]:
            result[item][plant][month] = val
    return result

# ---------------------------------------------------------------------------
# SAIL weighted-average computation
# ---------------------------------------------------------------------------

def _compute_sail(techno_data, hm_by_plant, cs_by_plant, months):
    """Compute SAIL-level aggregate for the given months.
    Returns {("SAIL", parameter_name): value}.

    Primary: production-weighted average (HM for BF params, CS for SMS/SEC).
    Fallback: simple average of available plant values when no production
              weights exist in production_table for those months.
    """
    out = {}

    # BF params weighted by Hot Metal
    for param in _BF_HM_PARAMS:
        num = den = 0.0
        plain = []
        for m in months:
            for p in _BF_PLANTS:
                v = techno_data.get((p, param), {}).get(m)
                w = hm_by_plant.get(p, {}).get(m)
                if v is not None and w is not None and w > 0:
                    num += v * w
                    den += w
                elif v is not None:
                    plain.append(v)
        if den > 0:
            out[("SAIL", param)] = num / den
        elif plain:
            out[("SAIL", param)] = sum(plain) / len(plain)
        else:
            out[("SAIL", param)] = None

    # BF Productivity: SAIL = ΣHM / Σ(HM / plant_BFprod)
    # Fallback: equal-weight harmonic mean
    t_hm = t_denom = 0.0
    plain_bfp = []
    for m in months:
        for p in _BF_PLANTS:
            hm  = hm_by_plant.get(p, {}).get(m)
            bfp = techno_data.get((p, "BF Productivity"), {}).get(m)
            if hm is not None and bfp is not None and bfp > 0:
                t_hm    += hm
                t_denom += hm / bfp
            elif bfp is not None and bfp > 0:
                plain_bfp.append(bfp)
    if t_denom > 0:
        out[("SAIL", "BF Productivity")] = t_hm / t_denom
    elif plain_bfp:
        denom = sum(1.0 / v for v in plain_bfp)
        out[("SAIL", "BF Productivity")] = len(plain_bfp) / denom if denom else None
    else:
        out[("SAIL", "BF Productivity")] = None

    # SMS params weighted by Crude Steel / shops per plant
    for param in _SMS_PARAMS:
        num = den = 0.0
        plain = []
        for m in months:
            for shop in _SMS_SHOPS:
                # For TMI: compute as HM Consumption + Scrap Consumption if not in DB
                if param == "TMI":
                    hm_v = techno_data.get((shop, "Hot Metal Consumption"), {}).get(m)
                    scrap_v = techno_data.get((shop, "Scrap Consumption"), {}).get(m)
                    v = None
                    if hm_v is not None and scrap_v is not None:
                        v = hm_v + scrap_v
                    else:
                        # Fallback: try to get TMI directly from DB
                        v = techno_data.get((shop, param), {}).get(m)
                else:
                    v = techno_data.get((shop, param), {}).get(m)

                # Weight by individual shop's Crude Steel production (not plant total / n)
                cs_shop = techno_data.get((shop, "Total Crude Steel"), {}).get(m)
                if v is not None and cs_shop is not None and cs_shop > 0:
                    num += v * cs_shop
                    den += cs_shop
                elif v is not None:
                    plain.append(v)
        if den > 0:
            out[("SAIL", param)] = num / den
        elif plain:
            out[("SAIL", param)] = sum(plain) / len(plain)
        else:
            out[("SAIL", param)] = None

    # Specific Energy Consumption weighted by Crude Steel
    num = den = 0.0
    plain = []
    for m in months:
        for p in _BF_PLANTS:
            v  = techno_data.get((p, "Specific Energy Consumption"), {}).get(m)
            cs = cs_by_plant.get(p, {}).get(m)
            if v is not None and cs is not None and cs > 0:
                num += v * cs
                den += cs
            elif v is not None:
                plain.append(v)
    if den > 0:
        out[("SAIL", "Specific Energy Consumption")] = num / den
    elif plain:
        out[("SAIL", "Specific Energy Consumption")] = sum(plain) / len(plain)
    else:
        out[("SAIL", "Specific Energy Consumption")] = None

    return out


def _all_sail_plant_params():
    """Set of (plant, param) pairs needed to compute SAIL values."""
    pp = set()
    for param in _BF_HM_PARAMS + ["BF Productivity"]:
        for p in _BF_PLANTS:
            pp.add((p, param))
    for shop in _SMS_SHOPS:
        for param in _SMS_PARAMS:
            pp.add((shop, param))
    for p in _BF_PLANTS:
        pp.add((p, "Specific Energy Consumption"))
    return pp


def _inject_plant_weighted_annual(cur, fy_map, ytd_keys, months):
    """DEPRECATED: No longer used. Historical FY data uses stored March till_month_actual only.
    Left in place for backwards compatibility but not called by generate_techno()."""
    if not months:
        return
    plant_params = _all_sail_plant_params()
    techno_data  = _fetch_techno_data(cur, plant_params, months)
    prod_raw     = _fetch_prod_multi(cur, _BF_PLANTS, ["Hot Metal", "Total Crude Steel"], months)
    hm = prod_raw["Hot Metal"]
    cs = prod_raw["Total Crude Steel"]

    for param in _BF_HM_PARAMS:
        for p in _BF_PLANTS:
            key = (p, param)
            if key in ytd_keys:
                continue
            num = den = 0.0
            for m in months:
                v = techno_data.get(key, {}).get(m)
                w = hm.get(p, {}).get(m)
                if v is not None and w is not None and w > 0:
                    num += v * w
                    den += w
            if den > 0:
                fy_map[key] = num / den

    for p in _BF_PLANTS:
        key = (p, "BF Productivity")
        if key in ytd_keys:
            continue
        t_hm = t_denom = 0.0
        for m in months:
            hm_v = hm.get(p, {}).get(m)
            bfp  = techno_data.get(key, {}).get(m)
            if hm_v is not None and bfp is not None and bfp > 0:
                t_hm    += hm_v
                t_denom += hm_v / bfp
        if t_denom > 0:
            fy_map[key] = t_hm / t_denom

    for param in _SMS_PARAMS:
        for shop in _SMS_SHOPS:
            key   = (shop, param)
            if key in ytd_keys:
                continue
            plant = _SMS_SHOP_PLANT[shop]
            n     = _PLANT_SHOP_CNT[plant]
            num = den = 0.0
            for m in months:
                v    = techno_data.get(key, {}).get(m)
                cs_v = cs.get(plant, {}).get(m)
                if v is not None and cs_v is not None and cs_v > 0:
                    w = cs_v / n
                    num += v * w
                    den += w
            if den > 0:
                fy_map[key] = num / den

    for p in _BF_PLANTS:
        key = (p, "Specific Energy Consumption")
        if key in ytd_keys:
            continue
        num = den = 0.0
        for m in months:
            v    = techno_data.get(key, {}).get(m)
            cs_v = cs.get(p, {}).get(m)
            if v is not None and cs_v is not None and cs_v > 0:
                num += v * cs_v
                den += cs_v
        if den > 0:
            fy_map[key] = num / den


def _inject_sail_techno(cur, mon_map, cum_map, ccum_map, cply_map,
                        fy2_map, fy1_map, fy3_map,
                        ytd, cply_ytd, cply_month, fy2_months, fy1_months, fy3_months,
                        fy2_stored=None, fy1_stored=None):
    """Compute SAIL weighted-average techno values for all periods.
    Fills: mon_map (current month), cum_map (YTD), ccum_map (CPLY YTD), cply_map (CPLY month).
    Also fills FY maps (fy1/fy2/fy3) if SAIL values missing but shop data available (use setdefault).
    Stored March till_month_actual values are never overwritten (setdefault ensures this)."""
    all_months   = sorted(set(ytd) | set(cply_ytd) | {cply_month} | set(fy2_months) | set(fy1_months) | set(fy3_months))
    plant_params = _all_sail_plant_params()
    techno_data  = _fetch_techno_data(cur, plant_params, all_months)
    prod_raw     = _fetch_prod_multi(cur, _BF_PLANTS, ["Hot Metal", "Total Crude Steel"], all_months)
    hm = prod_raw["Hot Metal"]
    cs = prod_raw["Total Crude Steel"]

    for m in ytd:
        for key, val in _compute_sail(techno_data, hm, cs, [m]).items():
            mon_map.setdefault(key, {}).setdefault(m, val)

    for key, val in _compute_sail(techno_data, hm, cs, [cply_month]).items():
        cply_map.setdefault(key, val)

    for key, val in _compute_sail(techno_data, hm, cs, ytd).items():
        cum_map.setdefault(key, val)

    for key, val in _compute_sail(techno_data, hm, cs, cply_ytd).items():
        ccum_map.setdefault(key, val)

    # Compute SAIL for historical FY maps if missing
    # Use stored March till_month_actual if available; compute from shop data if not
    for key, val in _compute_sail(techno_data, hm, cs, fy3_months).items():
        fy3_map.setdefault(key, val)

    for key, val in _compute_sail(techno_data, hm, cs, fy2_months).items():
        fy2_map.setdefault(key, val)

    for key, val in _compute_sail(techno_data, hm, cs, fy1_months).items():
        fy1_map.setdefault(key, val)


def _compute_plant_bf_aggregation(data, hm_data, plant, param, months, method):
    """Compute aggregated BF value for a plant+param across months.

    Args:
        data: {(entity, param): {month: value}}
        hm_data: {(entity, month): hm_value} for furnaces, {month: hm_value} for plant shop
        plant: plant code (BSP, RSP, DSP, BSL)
        param: parameter name
        months: list of months to aggregate over
        method: aggregation method (wtavg, harmonic, simple, sum)

    Returns:
        Aggregated value or None
    """
    furnaces = _PLANT_FURNACES.get(plant, [])
    plant_shop = f"{plant} Plant Shop"
    vals = data.get((plant_shop, param), {})

    # If Plant Shop data exists in DB, use it (don't recompute)
    if vals:
        if method == "sum":
            vs = [v for m in months if (v := vals.get(m)) is not None]
            return round(sum(vs), 4) if vs else None
        elif method == "simple":
            vs = [v for m in months if (v := vals.get(m)) is not None]
            return round(sum(vs) / len(vs), 4) if vs else None
        else:  # wtavg, harmonic
            return _aggregate_from_furnaces(data, hm_data, plant, param, months, method, furnaces)

    # Plant Shop data missing: compute from furnaces
    return _aggregate_from_furnaces(data, hm_data, plant, param, months, method, furnaces)


def _aggregate_from_furnaces(data, hm_data, plant, param, months, method, furnaces):
    """Compute aggregation from individual furnace data."""
    if method == "sum":
        vs = [v for f in furnaces for m in months if (v := data.get((f, param), {}).get(m)) is not None]
        return round(sum(vs), 4) if vs else None

    if method == "simple":
        vs = [v for f in furnaces for m in months if (v := data.get((f, param), {}).get(m)) is not None]
        return round(sum(vs) / len(vs), 4) if vs else None

    if method == "wtavg":
        num = den = 0.0
        for m in months:
            for f in furnaces:
                v  = data.get((f, param), {}).get(m)
                hm = hm_data.get((f, m))
                if v is not None and hm is not None and hm > 0:
                    num += v * hm
                    den += hm
        return round(num / den, 4) if den > 0 else None

    if method == "harmonic":
        num = den = 0.0
        for m in months:
            for f in furnaces:
                v  = data.get((f, param), {}).get(m)
                hm = hm_data.get((f, m))
                if v is not None and v > 0 and hm is not None and hm > 0:
                    num += hm
                    den += hm / v
        return round(num / den, 4) if den > 0 else None

    return None


def _inject_bf_aggregation(cur, plant, cum_map, ccum_map, fy2_map, fy1_map, fy3_map,
                            ytd, cply_ytd, fy2_months, fy1_months, fy3_months):
    """Compute BF Plant Shop aggregations from per-furnace data for BSP, RSP, DSP, BSL.
    Only fills Plant Shop if data is missing from DB."""
    all_months = sorted(set(ytd) | set(cply_ytd) | set(fy2_months) | set(fy1_months) | set(fy3_months))
    if not all_months:
        return

    furnaces = _PLANT_FURNACES.get(plant, [])
    if not furnaces:
        return

    plant_shop = f"{plant} Plant Shop"

    # Fetch all BF params for this plant (furnaces + plant shop)
    all_entities = furnaces + [plant_shop]
    all_pp = {(e, p) for e in all_entities for p in _BF_AGG_METHODS}
    data = _fetch_techno_data(cur, all_pp, all_months)

    # Get HM production for each furnace and plant
    if plant == "BSL":
        # BSL: fetch per-furnace HM from techno_actuals
        fce_hm = {}
        for f in furnaces:
            for m, v in data.get((f, "HM Production"), {}).items():
                if v and v > 0:
                    fce_hm[(f, m)] = v

    # Get total plant HM from production_table
    ph_m = ",".join("?" * len(all_months))
    cur.execute(
        f"SELECT report_month, month_actual FROM production_table "
        f"WHERE plant_name=? AND item_name='Hot Metal' AND report_month IN ({ph_m})",
        [plant] + list(all_months),
    )
    prod_hm = {m: v for m, v in cur.fetchall() if v and v > 0}

    # Prepare HM data for aggregation
    hm_data = {}
    for f in furnaces:
        for m in all_months:
            if plant == "BSL":
                # BSL: use per-furnace HM from techno data
                hm_data[(f, m)] = data.get((f, "HM Production"), {}).get(m)
            else:
                # Other plants: use total plant HM (assume equal distribution)
                hm = prod_hm.get(m)
                if hm:
                    hm_data[(f, m)] = hm / len(furnaces)

    # Compute Plant Shop aggregations for all periods
    for param in _BF_AGG_METHODS:
        method = _BF_AGG_METHODS[param]

        # Check if Plant Shop data already exists
        shop_data = data.get((plant_shop, param), {})

        # Only compute if Plant Shop data is missing
        if not shop_data:
            cum_map[(plant_shop, param)] = _compute_plant_bf_aggregation(
                data, hm_data, plant, param, ytd, method)
            ccum_map[(plant_shop, param)] = _compute_plant_bf_aggregation(
                data, hm_data, plant, param, cply_ytd, method)
            fy3_map[(plant_shop, param)] = _compute_plant_bf_aggregation(
                data, hm_data, plant, param, fy3_months, method)
            fy2_map[(plant_shop, param)] = _compute_plant_bf_aggregation(
                data, hm_data, plant, param, fy2_months, method)
            fy1_map[(plant_shop, param)] = _compute_plant_bf_aggregation(
                data, hm_data, plant, param, fy1_months, method)


# ---------------------------------------------------------------------------
# Main page generator
# ---------------------------------------------------------------------------

def generate_techno(report_month: str, page_no: int) -> dict:
    group, title, subtitle = TECHNO_PAGES[page_no]

    fy         = _fy_start(report_month)
    ytd        = db.get_ytd_months(report_month)
    cply_month = db.get_cply_month(report_month)
    cply_ytd   = [db.get_cply_month(m) for m in ytd]

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT p.param_name, p.row_label, p.unit
            FROM techno_param p
            JOIN techno_param_group g ON p.param_id = g.param_id
            WHERE g.group_code = ?
            ORDER BY g.sort_order, p.param_id
        """, (group,))
        master = cur.fetchall()   # [(param_name, row_label, unit), ...]

        fy3_map, fy3_stored = _annual_map(cur, fy - 3)
        fy2_map, fy2_stored = _annual_map(cur, fy - 2)
        fy1_map, fy1_stored = _annual_map(cur, fy - 1)
        cum_map  = _ytd_of_month(cur, report_month)
        ccum_map = _ytd_of_month(cur, cply_month)

        # Per-month actuals for YTD columns
        ph = ",".join("?" * len(ytd))
        cur.execute(f"""
            SELECT p.row_label, p.param_name, a.report_month, a.actual
            FROM techno_actuals a
            JOIN techno_param p ON a.param_id = p.param_id
            WHERE a.report_month IN ({ph})
        """, ytd)
        mon_map = {}
        for rl, pn, m, v in cur.fetchall():
            mon_map.setdefault((rl, pn), {})[m] = v

        # CPLY monthly actuals
        cur.execute("""
            SELECT p.row_label, p.param_name, a.actual
            FROM techno_actuals a
            JOIN techno_param p ON a.param_id = p.param_id
            WHERE a.report_month = ?
        """, (cply_month,))
        cply_map = {(r[0], r[1]): r[2] for r in cur.fetchall()}

        # Annual targets
        cur.execute("""
            SELECT p.row_label, p.param_name, tt.target
            FROM techno_target tt
            JOIN techno_param p ON tt.param_id = p.param_id
            JOIN techno_param_group g ON p.param_id = g.param_id
            WHERE tt.fy = ? AND g.group_code = ?
        """, (_fy_label(fy), group))
        tgt_map = {(r[0], r[1]): r[2] for r in cur.fetchall()}

        if group == "MAJOR":
            # Historical FY data (fy1/fy2/fy3) now uses stored March till_month_actual only.
            # No computed fallbacks — empty if March data not in DB.
            _inject_sail_techno(
                cur, mon_map, cum_map, ccum_map, cply_map, fy2_map, fy1_map, fy3_map,
                ytd, cply_ytd, cply_month,
                _fy_months(fy - 2), _fy_months(fy - 1), _fy_months(fy - 3),
            )

        if group == "IRON_MAKING":
            # Plant Shop CDI Rate rows mirror the MAJOR CDI Rate for each plant
            for p in _BF_PLANTS:
                src = (p, "CDI Rate")
                dst = (f"{p} Plant Shop", "CDI Rate")
                for mp in (fy3_map, fy2_map, fy1_map, cum_map, ccum_map, cply_map, tgt_map):
                    if src in mp:
                        mp.setdefault(dst, mp[src])
                if src in mon_map:
                    mon_map.setdefault(dst, dict(mon_map[src]))

            # Aggregate per-furnace BF data to Plant Shop level for all plants
            # Only fills Plant Shop if data is missing from DB
            for plant in _BF_PLANTS:
                _inject_bf_aggregation(
                    cur, plant, cum_map, ccum_map,
                    fy2_map, fy1_map, fy3_map,
                    ytd, cply_ytd, _fy_months(fy - 2), _fy_months(fy - 1), _fy_months(fy - 3),
                )

        # Build output sections
        sections, by_sec = [], {}
        for param_name, row_label, unit in master:


            if group == "IRON_MAKING" and param_name not in _IRON_MAKING_VISIBLE:
                continue
            if group == "COKE_SINTER" and param_name not in _COKE_SINTER_VISIBLE:
                continue
            if group == "SMS" and param_name not in _BOF_VISIBLE:
                continue



            pk = (row_label, param_name)
            row = {
                "label":  row_label,
                "unit":   unit or "",
                "fy3":    _fmt(fy3_map.get(pk)),
                "fy2":    _fmt(fy2_map.get(pk)),
                "fy1":    _fmt(fy1_map.get(pk)),
                "target": _fmt(tgt_map.get(pk)),
                "months": [_fmt(mon_map.get(pk, {}).get(m)) for m in ytd],
                "cply":     _fmt(cply_map.get(pk)),
                "cum":      _fmt(cum_map.get(pk)),
                "cum_cply": _fmt(ccum_map.get(pk)),
            }
            if param_name not in by_sec:
                by_sec[param_name] = {"label": param_name, "rows": []}
                sections.append(by_sec[param_name])
            by_sec[param_name]["rows"].append(row)

        # Sort rows within each section: plants first (in order), then SAIL
        plant_order = ["BSP", "DSP", "RSP", "BSL", "ISP"]
        for section in sections:
            def sort_key(row_dict):
                label = row_dict["label"]
                if label == "SAIL":
                    return (999,)  # SAIL at end
                try:
                    return (plant_order.index(label), label)
                except ValueError:
                    return (len(plant_order), label)  # Unknown plants after SAIL
            section["rows"].sort(key=sort_key)

        return {
            "title":          title,
            "subtitle":       subtitle,
            "variant":        "techno_params",
            "group":          group,
            "fy3_label":      _fy_label(fy - 3),
            "fy2_label":      _fy_label(fy - 2),
            "fy1_label":      _fy_label(fy - 1),
            "target_label":   f"Target {_fy_label(fy)}",
            "month_labels":   [_mlabel(m) for m in ytd],
            "cply_label":     _mlabel(cply_month),
            "cum_label":      _cum_label(ytd),
            "cum_cply_label": _cum_label(cply_ytd),
            "sections":       sections,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Page 3 summary TE table
# ---------------------------------------------------------------------------

def generate_summary_te_table(report_month: str) -> list:
    """Generate the te_table for the SAIL Performance Summary page (page 3)."""
    fy         = _fy_start(report_month)
    ytd        = db.get_ytd_months(report_month)
    cply_month = db.get_cply_month(report_month)
    cply_ytd   = [db.get_cply_month(m) for m in ytd]

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    try:
        all_months   = sorted(set(ytd) | set(cply_ytd) | {cply_month})
        plant_params = _all_sail_plant_params()
        techno_data  = _fetch_techno_data(cur, plant_params, all_months)
        prod_raw     = _fetch_prod_multi(cur, _BF_PLANTS, ["Hot Metal", "Total Crude Steel"], all_months)
        hm = prod_raw["Hot Metal"]
        cs = prod_raw["Total Crude Steel"]

        # Targets for SAIL row in MAJOR group
        cur.execute("""
            SELECT p.param_name, tt.target
            FROM techno_target tt
            JOIN techno_param p ON tt.param_id = p.param_id
            JOIN techno_param_group g ON p.param_id = g.param_id
            WHERE tt.fy = ? AND g.group_code = 'MAJOR' AND p.row_label = 'SAIL'
        """, (_fy_label(fy),))
        tgt_by_param = dict(cur.fetchall())

        def entry(param_name, unit, period_sets):
            tgt_val = _fmt(tgt_by_param.get(param_name))
            vals    = [_fmt(_compute_sail(techno_data, hm, cs, ms).get(("SAIL", param_name)))
                       for ms in period_sets]
            return {"parameter": param_name, "unit": unit, "values": [tgt_val] + vals}

        period_sets = [[report_month], [cply_month], ytd, cply_ytd]

        return [
            entry("Coke Rate",                  "kg/thm",   period_sets),
            entry("CDI Rate",                   "kg/thm",   period_sets),
            entry("Fuel Rate",                  "kg/thm",   period_sets),
            entry("BF Productivity",            "t/m3/day", period_sets),
            entry("Specific Energy Consumption","Gcal/tcs", period_sets),
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Page 3 bar chart data
# ---------------------------------------------------------------------------

def generate_summary_chart_data(report_month: str) -> dict:
    """Return chart data for page 3 bar charts (Coke Rate, CDI, BF Productivity, S.E.C.)."""
    fy             = _fy_start(report_month)
    cur_fy_months  = [m for m in _fy_months(fy) if m <= report_month]
    past_fys       = [fy - 3, fy - 2, fy - 1]

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    try:
        # Targets for current FY SAIL row
        cur.execute("""
            SELECT p.param_name, tt.target
            FROM techno_target tt
            JOIN techno_param p ON tt.param_id = p.param_id
            JOIN techno_param_group g ON p.param_id = g.param_id
            WHERE tt.fy = ? AND g.group_code = 'MAJOR' AND p.row_label = 'SAIL'
        """, (_fy_label(fy),))
        tgt_by_param = dict(cur.fetchall())

        # Fetch component data for current FY months
        fetch_months = cur_fy_months if cur_fy_months else [report_month]
        plant_params = _all_sail_plant_params()
        techno_data  = _fetch_techno_data(cur, plant_params, fetch_months)
        prod_raw     = _fetch_prod_multi(cur, _BF_PLANTS, ["Hot Metal", "Total Crude Steel"], fetch_months)
        hm = prod_raw["Hot Metal"]
        cs = prod_raw["Total Crude Steel"]

        # Past FY annual maps (use stored ytd_actual for SAIL)
        past_fy_maps = {pfy: _annual_map(cur, pfy)[0] for pfy in past_fys}

        param_specs = [
            ("Coke Rate",       "Kg/THM",    "Coke Rate"),
            ("PCI Rate",        "Kg/THM",    "CDI Rate"),
            ("BF Productivity", "T/m³/Day",  "BF Productivity"),
            ("Sp. Energy",      "Gcal/TCS",  "Specific Energy Consumption"),
        ]

        def fy_label_short(yr):
            return f"FY{(yr + 1) % 100:02d}"

        result = []
        for chart_name, unit, param_name in param_specs:
            fy_bars = []
            for pfy in past_fys:
                raw = past_fy_maps[pfy].get(("SAIL", param_name))
                fy_bars.append({
                    "label": fy_label_short(pfy),
                    "value": round(float(raw), 3) if raw is not None else None,
                })

            tgt_v = tgt_by_param.get(param_name)
            target_bar = {
                "label": f"{fy_label_short(fy)}\nTarget",
                "value": round(float(tgt_v), 3) if tgt_v is not None else None,
            }

            monthly_bars = []
            for m in cur_fy_months:
                v = _compute_sail(techno_data, hm, cs, [m]).get(("SAIL", param_name))
                monthly_bars.append({
                    "label": _mlabel(m),
                    "value": round(float(v), 3) if v is not None else None,
                })

            result.append({
                "name": chart_name, "unit": unit,
                "fy_bars": fy_bars, "target_bar": target_bar,
                "monthly_bars": monthly_bars,
            })

        return {"params": result}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SAIL target computation
# ---------------------------------------------------------------------------

def compute_sail_targets(fy: str) -> dict:
    """Compute SAIL-level techno targets from plant-level targets.
    Returns {(plant_name, parameter_name): value} for SAIL rows."""
    try:
        fy_start = int(fy.split("-")[0])
    except (ValueError, IndexError):
        return {}

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()

    # Annual production plan weights
    months = (
        [f"{fy_start}-{m:02d}" for m in range(4, 13)] +
        [f"{fy_start + 1}-{m:02d}" for m in range(1, 4)]
    )
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT plant_name, item_name, SUM(month_actual)
        FROM production_plan_table
        WHERE report_month IN ({ph})
          AND item_name IN ('Hot Metal', 'Total Crude Steel')
          AND plant_name IN ('BSP','DSP','RSP','BSL','ISP')
        GROUP BY plant_name, item_name
    """, months)
    hm_wt = {}
    cs_wt = {}
    for plant, item, val in cur.fetchall():
        if val and val > 0:
            (hm_wt if item == "Hot Metal" else cs_wt)[plant] = val

    # Plant-level targets from techno_target joined with techno_param
    cur.execute("""
        SELECT p.row_label, p.param_name, tt.target
        FROM techno_target tt
        JOIN techno_param p ON tt.param_id = p.param_id
        JOIN techno_param_group g ON p.param_id = g.param_id
        WHERE tt.fy = ? AND g.group_code IN ('MAJOR','SMS')
          AND p.row_label != 'SAIL'
    """, (fy,))
    tgt = {}   # {(row_label, param_name): target}
    for rl, pn, t in cur.fetchall():
        tgt[(rl, pn)] = t
    conn.close()

    out = {}

    # BF params weighted by Hot Metal
    for param in _BF_HM_PARAMS:
        num = den = 0.0
        for p in _BF_PLANTS:
            v = tgt.get((p, param))
            w = hm_wt.get(p)
            if v is not None and w:
                num += v * w
                den += w
        out[("SAIL", param)] = round(num / den, 3) if den > 0 else None

    # BF Productivity: harmonic mean
    t_hm = t_denom = 0.0
    for p in _BF_PLANTS:
        hm  = hm_wt.get(p)
        bfp = tgt.get((p, "BF Productivity"))
        if hm and bfp and bfp > 0:
            t_hm    += hm
            t_denom += hm / bfp
    out[("SAIL", "BF Productivity")] = round(t_hm / t_denom, 3) if t_denom > 0 else None

    # SMS: compute shop TMI = HM + Scrap first, then weight by CS
    for shop in _SMS_SHOPS:
        hm_v    = tgt.get((shop, "Hot Metal Consumption"))
        scrap_v = tgt.get((shop, "Scrap Consumption"))
        if hm_v is not None and scrap_v is not None:
            tgt[(shop, "TMI")] = round(hm_v + scrap_v, 3)

    for param in _SMS_PARAMS:
        num = den = 0.0
        for shop in _SMS_SHOPS:
            plant = _SMS_SHOP_PLANT[shop]
            n     = _PLANT_SHOP_CNT[plant]
            v  = tgt.get((shop, param))
            cs = cs_wt.get(plant)
            if v is not None and cs:
                w = cs / n
                num += v * w
                den += w
        out[("SAIL", param)] = round(num / den, 3) if den > 0 else None

    # Specific Energy Consumption weighted by CS
    num = den = 0.0
    for p in _BF_PLANTS:
        v  = tgt.get((p, "Specific Energy Consumption"))
        cs = cs_wt.get(p)
        if v is not None and cs:
            num += v * cs
            den += cs
    out[("SAIL", "Specific Energy Consumption")] = round(num / den, 3) if den > 0 else None

    # Convert (row_label, param_name) keys → param_id for save_techno_target
    conn2 = sqlite3.connect(db.DB_PATH)
    cur2  = conn2.cursor()
    result = {}
    for (rl, pn), val in out.items():
        if val is None:
            continue
        cur2.execute(
            "SELECT param_id FROM techno_param WHERE row_label=? AND param_name=?",
            (rl, pn),
        )
        row = cur2.fetchone()
        if row:
            result[row[0]] = val
    conn2.close()
    return result


# ---------------------------------------------------------------------------
# Bar chart SVG rendering  (unchanged — operates on computed dicts only)
# ---------------------------------------------------------------------------

_C_FY      = "#FFC000"
_C_TARGET  = "#70AD47"
_C_MONTHLY = "#4472C4"


def _fmt_bar_val(v: float) -> str:
    a = abs(v)
    if a >= 100:
        return str(int(round(v)))
    if a >= 10:
        s = f"{v:.1f}"
    elif a >= 1:
        s = f"{v:.2f}"
    else:
        s = f"{v:.3f}"
    return s.rstrip("0").rstrip(".")


def _param_svg(p: dict, vw: int = 290, vh: int = 165) -> str:
    mt   = 28
    mb   = 32
    ml   = 5
    mr   = 5
    cw, ch = vw - ml - mr, vh - mt - mb
    SEP_W = 4

    bars: list = []
    for b in p.get("fy_bars", []):
        bars.append({"label": b["label"], "value": b["value"], "color": _C_FY})
    bars.append({"sep": True})
    tb = p.get("target_bar", {})
    bars.append({"label": tb.get("label", ""), "value": tb.get("value"), "color": _C_TARGET})
    bars.append({"sep": True})
    for b in p.get("monthly_bars", []):
        bars.append({"label": b["label"], "value": b["value"], "color": _C_MONTHLY})

    valid = [e["value"] for e in bars if not e.get("sep") and e.get("value") is not None]
    if not valid:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}">'
            f'<rect width="{vw}" height="{vh}" fill="#f8fafc" rx="3"/>'
            f'<text x="{vw // 2}" y="{vh // 2}" text-anchor="middle" '
            f'font-size="9" font-family="Arial,sans-serif" fill="#94a3b8">'
            f'{p.get("name", "")} – no data</text></svg>'
        )

    ylo_v, yhi_v = min(valid), max(valid)
    rng    = yhi_v - ylo_v
    pad_lo = rng * 0.66 if rng > 0 else max(abs(yhi_v) * 0.1, 0.5)
    pad_hi = rng * 0.23 if rng > 0 else max(abs(yhi_v) * 0.05, 0.2)
    ylo, yhi = ylo_v - pad_lo, yhi_v + pad_hi
    yspan = yhi - ylo

    def ys(v: float) -> float:
        return mt + ch * (1.0 - (v - ylo) / yspan)

    n_seps  = sum(1 for e in bars if e.get("sep"))
    n_bars  = len(bars) - n_seps
    many    = n_bars > 7
    slot_w  = (cw - n_seps * SEP_W) / max(n_bars, 1)
    bar_w   = max(5.0, slot_w * 0.78)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}">']
    lines.append(
        f'<text x="{vw / 2:.0f}" y="13" text-anchor="middle" '
        f'font-size="8.5" font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">'
        f'{p.get("name", "")} ({p.get("unit", "")})</text>'
    )
    lines.append(
        f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
        f'stroke="#374151" stroke-width="0.6"/>'
    )

    x = float(ml)
    for e in bars:
        if e.get("sep"):
            x += SEP_W
            continue
        bx    = x + (slot_w - bar_w) / 2
        v     = e.get("value")
        color = e.get("color", "#aaa")
        if v is not None:
            bh  = max(1.0, (v - ylo) / yspan * ch)
            by  = ys(v)
            lines.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                f'height="{bh:.1f}" fill="{color}" rx="1.5"/>'
            )
            val_str = _fmt_bar_val(v)
            vly     = by - 3
            lines.append(
                f'<text x="{bx + bar_w / 2:.1f}" y="{vly:.1f}" text-anchor="middle" '
                f'font-size="7" font-weight="bold" font-family="Arial,sans-serif" '
                f'fill="{color}">{val_str}</text>'
            )

        lbl         = e.get("label", "")
        lx          = bx + bar_w / 2
        label_parts = lbl.split("\n")
        if len(label_parts) == 1:
            if many:
                ly = mt + ch + 7
                lines.append(
                    f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="end" '
                    f'font-size="6" font-family="Arial,sans-serif" fill="#374151" '
                    f'transform="rotate(-40,{lx:.1f},{ly:.1f})">{lbl}</text>'
                )
            else:
                ly = mt + ch + 10
                lines.append(
                    f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                    f'font-size="6.5" font-family="Arial,sans-serif" fill="#374151">'
                    f'{lbl}</text>'
                )
        else:
            ly1 = mt + ch + 10
            ly2 = mt + ch + 19
            lines.append(
                f'<text x="{lx:.1f}" y="{ly1:.1f}" text-anchor="middle" '
                f'font-size="6.5" font-family="Arial,sans-serif" fill="#374151">'
                f'{label_parts[0]}</text>'
            )
            lines.append(
                f'<text x="{lx:.1f}" y="{ly2:.1f}" text-anchor="middle" '
                f'font-size="6.5" font-family="Arial,sans-serif" fill="#374151">'
                f'{label_parts[1]}</text>'
            )
        x += slot_w

    lines.append("</svg>")
    return "\n".join(lines)


def generate_summary_chart_html(chart_data: dict) -> str:
    params = (chart_data or {}).get("params", [])
    if len(params) < 4:
        return ""
    rows_html = ""
    for row_start in (0, 2):
        p0, p1 = params[row_start], params[row_start + 1]
        rows_html += (
            '<div style="display:flex;gap:4px;margin-bottom:2px;">'
            f'<div style="flex:1;border:0.5px solid #e2e8f0;border-radius:3px;padding:2px;">'
            f'{_param_svg(p0)}</div>'
            f'<div style="flex:1;border:0.5px solid #e2e8f0;border-radius:3px;padding:2px;">'
            f'{_param_svg(p1)}</div>'
            "</div>"
        )
    return '<div style="margin-top:6px;">' + rows_html + "</div>"


# ---------------------------------------------------------------------------
# MAJOR page from techno_data table (replaces legacy techno_actuals path)
# ---------------------------------------------------------------------------

def generate_major_techno_from_db(report_month: str) -> dict:
    """
    Generate page 27 (MAJOR TECHNO-ECONOMIC PARAMETERS) from techno_data.
    FY columns use the till_month value from the March row of each past FY,
    which represents the full-year cumulative.
    """
    import json as _json

    fy         = _fy_start(report_month)
    ytd        = db.get_ytd_months(report_month)
    cply_month = db.get_cply_month(report_month)

    # March month for past FYs: till_month of March = full-year cumulative
    # FY (fy-1) ends March of year fy; FY (fy-2) ends March of year fy-1; etc.
    fy1_march = f"{fy}-03"
    fy2_march = f"{fy - 1}-03"
    fy3_march = f"{fy - 2}-03"

    all_months = sorted(set(ytd) | {cply_month, fy1_march, fy2_march, fy3_march})

    # store[(plant, month)][unit] = {"month": {...}, "till_month": {...}}
    store = {}
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(all_months))
        cur.execute(
            f"SELECT plant, report_month, unit, techno_json FROM techno_data WHERE report_month IN ({ph})",
            all_months,
        )
        for plant, rm, unit, tj in cur.fetchall():
            store.setdefault((plant, rm), {})[unit] = _json.loads(tj)
    finally:
        conn.close()

    _PLANT_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP"]
    plants_with_data = sorted(
        {p for (p, rm) in store if rm == report_month},
        key=lambda p: _PLANT_ORDER.index(p) if p in _PLANT_ORDER else 99,
    )

    def _gv(plant, rm, unit, key, period="month"):
        return store.get((plant, rm), {}).get(unit, {}).get(period, {}).get(key)

    def _fy_val(plant, march_rm, src_unit, src_key):
        """Full-year value = till_month of March row for that FY."""
        return _gv(plant, march_rm, src_unit, src_key, "till_month")

    def _build_row(label, unit_str, month_fn, cum_fn, cply_fn, fy1_fn, fy2_fn, fy3_fn, cum_cply_fn=None):
        return {
            "label":  label,
            "unit":   unit_str,
            "fy3":    _fmt(fy3_fn()),
            "fy2":    _fmt(fy2_fn()),
            "fy1":    _fmt(fy1_fn()),
            "target": "",
            "months":    [_fmt(month_fn(m)) for m in ytd],
            "cply":      _fmt(cply_fn()),
            "cum":       _fmt(cum_fn()),
            "cum_cply":  _fmt(cum_cply_fn()) if cum_cply_fn else "",
        }

    def unit_section(param_name, unit_str, src_units, src_key):
        """One row per plant.  src_units: single unit name OR list tried in order
        (first unit with data for that plant wins).  Enables ISP BF-5 fallback
        when no BF_Shop unit exists."""
        if isinstance(src_units, str):
            src_units = [src_units]
        rows = []
        for p in plants_with_data:
            p_data = store.get((p, report_month), {})
            src_unit = next((u for u in src_units if p_data.get(u)), None)
            if not src_unit:
                continue
            rows.append(_build_row(
                p, unit_str,
                month_fn     = lambda m, _p=p, _u=src_unit: _gv(_p, m,             _u, src_key),
                cum_fn       = lambda     _p=p, _u=src_unit: _gv(_p, report_month,  _u, src_key, "till_month"),
                cply_fn      = lambda     _p=p, _u=src_unit: _gv(_p, cply_month,    _u, src_key),
                fy1_fn       = lambda     _p=p, _u=src_unit: _fy_val(_p, fy1_march, _u, src_key),
                fy2_fn       = lambda     _p=p, _u=src_unit: _fy_val(_p, fy2_march, _u, src_key),
                fy3_fn       = lambda     _p=p, _u=src_unit: _fy_val(_p, fy3_march, _u, src_key),
                cum_cply_fn  = lambda     _p=p, _u=src_unit: _gv(_p, cply_month,    _u, src_key, "till_month"),
            ))
        return {"label": param_name, "rows": rows}

    # BF_Shop is preferred (shop average); fall back to individual furnace units
    # for plants that publish per-furnace only (e.g. ISP has BF-5, no BF_Shop)
    _BF_UNITS = ["BF_Shop", "BF-5", "BF-4", "BF-2", "BF-1", "BF-3"]

    # SMS unit scan order — covers RSP/BSP (SMS-1/2/3), ISP/DSP (SMS), BSL (SMS-I/II)
    _SMS_UNIT_ORDER = ["SMS-1", "SMS-2", "SMS-3", "SMS", "SMS-I", "SMS-II"]

    def sms_section(param_name, unit_str, src_key, tmi=False):
        """One row per (plant, SMS-unit) pair that has data for the report month."""
        rows = []
        for p in plants_with_data:
            p_units = store.get((p, report_month), {})
            for su in _SMS_UNIT_ORDER:
                if not p_units.get(su):
                    continue
                if tmi:
                    def _tmi(plant, rm, period, _su=su):
                        hm = _gv(plant, rm, _su, "specific_hm_consumption",   period)
                        sc = _gv(plant, rm, _su, "specific_scrap_consumption", period)
                        if hm is not None and sc is not None:
                            return hm + sc
                        return hm if hm is not None else sc
                    rows.append(_build_row(
                        f"{p} {su}", unit_str,
                        month_fn    = lambda m, _p=p: _tmi(_p, m, "month"),
                        cum_fn      = lambda     _p=p: _tmi(_p, report_month, "till_month"),
                        cply_fn     = lambda     _p=p: _tmi(_p, cply_month,   "month"),
                        fy1_fn      = lambda     _p=p: _tmi(_p, fy1_march, "till_month"),
                        fy2_fn      = lambda     _p=p: _tmi(_p, fy2_march, "till_month"),
                        fy3_fn      = lambda     _p=p: _tmi(_p, fy3_march, "till_month"),
                        cum_cply_fn = lambda     _p=p: _tmi(_p, cply_month,   "till_month"),
                    ))
                else:
                    rows.append(_build_row(
                        f"{p} {su}", unit_str,
                        month_fn    = lambda m, _p=p, _su=su: _gv(_p, m,            _su, src_key),
                        cum_fn      = lambda     _p=p, _su=su: _gv(_p, report_month, _su, src_key, "till_month"),
                        cply_fn     = lambda     _p=p, _su=su: _gv(_p, cply_month,   _su, src_key),
                        fy1_fn      = lambda     _p=p, _su=su: _fy_val(_p, fy1_march, _su, src_key),
                        fy2_fn      = lambda     _p=p, _su=su: _fy_val(_p, fy2_march, _su, src_key),
                        fy3_fn      = lambda     _p=p, _su=su: _fy_val(_p, fy3_march, _su, src_key),
                        cum_cply_fn = lambda     _p=p, _su=su: _gv(_p, cply_month,   _su, src_key, "till_month"),
                    ))
        return {"label": param_name, "rows": rows}

    raw_sections = [
        unit_section("Coal to Hot Metal",           "kg/kg",      "General",   "coal_to_hm"),
        unit_section("Coke Rate",                   "kg/thm",     _BF_UNITS,   "coke_rate"),
        unit_section("Nut Coke Rate",               "kg/thm",     _BF_UNITS,   "nut_coke_rate"),
        unit_section("CDI Rate",                    "kg/thm",     _BF_UNITS,   "cdi"),
        unit_section("Fuel Rate",                   "kg/thm",     _BF_UNITS,   "fuel_rate"),
        unit_section("Sinter in Burden",            "%",          _BF_UNITS,   "sinter% in burden"),
        unit_section("Pellet in Burden",            "%",          _BF_UNITS,   "pellet% in burden"),
        unit_section("BF Productivity",             "t/m³/day",   _BF_UNITS,   "bf_productivity"),
        sms_section ("Hot Metal Consumption",       "kg/tcs",     "specific_hm_consumption"),
        sms_section ("Scrap Consumption",           "kg/tcs",     "specific_scrap_consumption"),
        sms_section ("TMI",                         "kg/tcs",     None,  tmi=True),
        unit_section("Specific Energy Consumption", "Gcal/tcs",   "General",   "specific_energy_consumption"),
    ]
    sections = [s for s in raw_sections if s["rows"]]

    return {
        "title":          "MAJOR TECHNO-ECONOMIC PARAMETERS",
        "subtitle":       "",
        "variant":        "techno_params",
        "group":          "MAJOR",
        "fy3_label":      _fy_label(fy - 3),
        "fy2_label":      _fy_label(fy - 2),
        "fy1_label":      _fy_label(fy - 1),
        "target_label":   f"Target {_fy_label(fy)}",
        "month_labels":   [_mlabel(m) for m in ytd],
        "cply_label":     _mlabel(cply_month),
        "cum_label":      _cum_label(ytd),
        "cum_cply_label": _cum_label([db.get_cply_month(m) for m in ytd]),
        "sections":       sections,
    }


# ---------------------------------------------------------------------------
# Pages 28-35 from techno_data table
# ---------------------------------------------------------------------------

# Schema for "param" pages (28-30): sections=parameters, rows=plant×unit combos
# Each entry: (section_label, unit_str, [(src_unit, src_key), ...])
# Schema for "mill" pages (31-35): sections=mill-units, rows=params for one plant
# Each entry: (mill_unit_name, [(param_label, src_key, unit_str), ...])

_TECHNO_DB_SCHEMA = {
    28: {
        "type": "param",
        "sections": [
            # Coke oven parameters (COB-old = battery 1-5, COB-new = battery 6)
            ("BF Coke Yield",          "%",          [("COB-old", "bf_coke_yield"),       ("COB-new", "bf_coke_yield")]),
            ("Dry Coal Charge/Oven",   "t/oven",     [("COB-old", "dry_coal_charge"),     ("COB-new", "dry_coal_charge")]),
            ("Sp. Heat Consmn./t DC",  "kcal/kg DC", [("General", "Specific_heat_consumption_per_ton_dry_coal_charged")]),
            ("Coke Oven Gas Yield",    "NM3/t",      [("COB-old", "cog_yield")]),
            ("Coal Tar Yield",         "kg/t",       [("COB-new", "crude_tar_yield")]),
            ("Crude Benzol Yield",     "kg/t",       [("COB-new", "crude_benzol_yield")]),   # add row to hardcoded_map when available
            ("Amm. Sulphate Yield",    "kg/t",       [("COB-new", "ammonium_sulphate_yield")]),
        ],
    },
    29: {
        "type": "param",
        "sections": [
            # Sinter plants — RSP: SP-1/SP-2/SP-3, ISP: SP
            ("Sinter Productivity", "t/m²/day", [("SP-1", "specific_productivity"), ("SP-2", "specific_productivity"), ("SP-3", "specific_productivity"), ("SP", "specific_productivity")]),
            ("LD Slag Usage",       "kg/t",      [("SP-1", "ld_slag_cons"),          ("SP-2", "ld_slag_cons"),          ("SP-3", "ld_slag_cons"),          ("SP", "ld_slag_cons")]),
            # Blast furnaces — RSP: BF-1/BF-4/BF-5/BF_Shop, ISP: BF-5 (shared unit name)
            ("CDI Rate",            "kg/thm",    [("BF-1", "cdi"), ("BF-4", "cdi"), ("BF-5", "cdi"), ("BF_Shop", "cdi")]),
            ("Coke Screen Loss",    "%",         [("General", "coke_screen_loss")]),
        ],
    },
    30: {
        "type": "param",
        "sections": [
            # SMS shops — RSP: SMS-1/SMS-2, BSP: SMS-2/SMS-3, ISP/DSP: SMS, BSL: SMS-I/SMS-II
            ("Average Blows/Day",   "Nos",   [("SMS-1", "average_blows_per_day"), ("SMS-2", "average_blows_per_day"), ("SMS-3", "average_blows_per_day"), ("SMS", "average_blows_per_day")]),
            ("Average Heat Weight", "t",     [("SMS-1", "average_heat_weight"),   ("SMS-2", "average_heat_weight"),   ("SMS-3", "average_heat_weight"),   ("SMS", "average_heat_weight")]),
            ("Average Lining Life", "heats", [("SMS-1", "average_lining_life"),   ("SMS-2", "average_lining_life"),   ("SMS-3", "average_lining_life"),   ("SMS-I", "average_lining_life"), ("SMS-II", "average_lining_life")]),
            ("Fe-Mn Consumption",   "kg/t",  [("SMS-1", "fe-mn"),  ("SMS-2", "fe-mn"),  ("SMS-3", "fe-mn"),  ("SMS", "fe-mn"),  ("SMS-I", "fe-mn"),  ("SMS-II", "fe-mn")]),
            ("Fe-Si Consumption",   "kg/t",  [("SMS-1", "fe-si"),  ("SMS-2", "fe-si"),  ("SMS-3", "fe-si"),  ("SMS", "fe-si"),  ("SMS-I", "fe-si"),  ("SMS-II", "fe-si")]),
            ("Si-Mn Consumption",   "kg/t",  [("SMS-1", "si-mn"),  ("SMS-2", "si-mn"),  ("SMS-3", "si-mn"),  ("SMS", "si-mn"),  ("SMS-I", "si-mn"),  ("SMS-II", "si-mn")]),
            ("Oxygen Blowing",      "NM3/t", [("SMS-1", "oxygen_blowing"), ("SMS-2", "oxygen_blowing"), ("SMS-3", "oxygen_blowing"), ("SMS", "oxygen_blowing"), ("SMS-I", "oxygen_blowing"), ("SMS-II", "oxygen_blowing")]),
            ("Caster Yield",        "%",     [("SMS-1", "caster_yield"),   ("SMS-2", "caster_yield"),   ("SMS-3", "caster_yield"),   ("SMS", "caster_yield")]),
        ],
    },
    # Mill pages: sections = mill-unit, rows = params for that plant
    31: {
        "type": "mill",
        "plant": "BSP",
        "sections": [
            ("PM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("RSM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("MM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("URM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("WRM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("BRM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
            ]),
        ],
    },
    32: {
        "type": "mill",
        "plant": "DSP",
        "sections": [
            ("Merchant Mill", [
                ("Yield",             "yield",              "%"),
                ("Availability",      "mill_availability",  "%"),
                ("Utilisation",       "mill_utilisation",   "%"),
                ("Rolling Rate",      "rolling_rate",       "t/hr"),
                ("On ICH",            "on_ich",             "%"),
                ("Sp. Heat Consmn.",  "specific_heat",      "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power",     "kWh/T"),
            ]),
            ("MSM", [
                ("Yield",             "yield",              "%"),
                ("Availability",      "mill_availability",  "%"),
                ("Utilisation",       "mill_utilisation",   "%"),
                ("Rolling Rate",      "rolling_rate",       "t/hr"),
                ("On ICH",            "on_ich",             "%"),
                ("Sp. Heat Consmn.",  "specific_heat",      "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power",     "kWh/T"),
            ]),
            ("Wheel Plant", [
                ("Yield",             "finished_wheel_over_ingot_round", "%"),
                ("Availability",      "forging_availability",            "%"),
                ("Utilisation",       "forging_utilisation",             "%"),
                ("Rolling Rate",      "rolling_rate",                    "Nos./Hr."),
                ("On ICH",            "on_ich",                          "%"),
                ("Sp. Heat Consmn.",  "specific_heat",                   "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power",                  "kWh/T"),
            ]),
            ("Axle Plant", [
                ("Yield",             "yield_over_good_bloom", "%"),
                ("Availability",      "forging_availability",  "%"),
                ("Utilisation",       "forging_utilisation",   "%"),
                ("Forging Rate",      "forging_rate",          "Nos./Hr."),
                ("On ICH",            "on_ich",                "%"),
                ("Sp. Heat Consmn.",  "specific_heat",         "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power",        "kWh/T"),
            ]),
        ],
    },
    33: {
        "type": "mill",
        "plant": "RSP",
        "sections": [
            ("PM", [
                ("Yield Prime",       "yield_prime",               "%"),
                ("Yield Total",       "yield_total",               "%"),
                ("Avg Slab Weight",   "average_slab_weight",       "t"),
                ("Availability",      "availability",              "%"),
                ("Utilisation",       "utilisation",               "%"),
                ("Rolling Rate",      "rolling_rate",              "t/hr"),
                ("Sp. Power Consmn.", "specific_power_consumption","kWh/t"),
            ]),
            ("NPM", [
                ("Yield Prime",       "yield_prime",               "%"),
                ("Yield Total",       "yield_total",               "%"),
                ("Avg Slab Weight",   "average_slab_weight",       "t"),
                ("Availability",      "availability",              "%"),
                ("Utilisation",       "utilisation",               "%"),
                ("Rolling Rate",      "rolling_rate",              "t/hr"),
                ("Sp. Power Consmn.", "specific_power_consumption","kWh/t"),
            ]),
            ("HSM-2", [
                ("HR Coil Yield",     "yield_total",                  "%"),
                ("Avg Slab Weight",   "average_slab_weight",          "t"),
                ("Availability",      "availability",                 "%"),
                ("Utilisation",       "utilisation",                  "%"),
                ("Rolling Rate",      "rolling_rate",                 "t/hr"),
                ("RH Fce Avail.",     "average_furnace_availability", "Nos/day"),
                ("Sp. Power Consmn.", "specific_power_consumption",   "kWh/t"),
            ]),
            ("SSM", [
                ("Yield",             "yield",            "%"),
                ("Acid Consumption",  "acid_consumption", "kg/t"),
                ("Availability",      "availability",     "%"),
                ("Utilisation",       "utilisation",      "%"),
                ("Rolling Rate",      "rolling_rate",     "t/hr"),
            ]),
            ("SWP", [
                ("Yield",             "yield",        "%"),
                ("Availability",      "availability", "%"),
                ("Utilisation",       "utilisation",  "%"),
                ("Rolling Rate",      "rolling_rate", "t/hr"),
            ]),
            ("ERW", [
                ("Yield",             "yield",        "%"),
                ("Availability",      "availability", "%"),
                ("Utilisation",       "utilisation",  "%"),
                ("Rolling Rate",      "rolling_rate", "t/hr"),
            ]),
        ],
    },
    34: {
        "type": "mill",
        "plant": "BSL",
        "sections": [
            # BF_Shop — shop averages from Techno Excel and BF PDF
            ("BF_Shop", [
                ("BF Productivity",   "bf_productivity",     "T/m³/day"),
                ("Coke Rate",         "coke_rate",           "Kg/THM"),
                ("CDI Rate",          "cdi",                 "Kg/THM"),
                ("Fuel Rate",         "fuel_rate",           "Kg/THM"),
                ("Sinter in Burden",  "sinter_in_burden",    "%"),
                ("O2 Enrichment",     "o2_enrichment",       "%"),
                ("Slag Rate",         "slag_rate",           "Kg/THM"),
                ("Furnace Avail.",    "furnace_availability",  "%"),
                ("Furnace Util.",     "furnace_utilization",  "%"),
            ]),
            # SMS-I and SMS-II from BSL Techno Excel SMS-I/SMS-II sheets
            ("SMS-I", [
                ("Avg Lining Life",   "average_lining_life",       "Heats"),
                ("HM Consumption",    "specific_hm_consumption",   "Kg/TCS"),
                ("Scrap Cons.",       "specific_scrap_consumption", "Kg/TCS"),
                ("Fe-Mn Cons.",       "fe-mn",                     "Kg/TCS"),
                ("Fe-Si Cons.",       "fe-si",                     "Kg/TCS"),
                ("Si-Mn Cons.",       "si-mn",                     "Kg/TCS"),
                ("Oxygen Blowing",    "oxygen_blowing",            "Nm³/TCS"),
            ]),
            ("SMS-II", [
                ("Avg Lining Life",   "average_lining_life",       "Heats"),
                ("HM Consumption",    "specific_hm_consumption",   "Kg/TCS"),
                ("Scrap Cons.",       "specific_scrap_consumption", "Kg/TCS"),
                ("Fe-Mn Cons.",       "fe-mn",                     "Kg/TCS"),
                ("Fe-Si Cons.",       "fe-si",                     "Kg/TCS"),
                ("Si-Mn Cons.",       "si-mn",                     "Kg/TCS"),
                ("Oxygen Blowing",    "oxygen_blowing",            "Nm³/TCS"),
            ]),
        ],
    },
    35: {
        "type": "mill",
        "plant": "ISP",
        "sections": [
            ("BM", [
                ("Yield",             "yield_total",               "%"),
                ("Availability",      "availability",              "%"),
                ("Utilisation",       "utilisation",               "%"),
                ("Rolling Rate",      "rolling_rate",              "t/hr"),
                ("Sp. Power Consmn.", "specific_power_consumption","kWh/t"),
                ("Sp. Heat Consmn.",  "specific_heat_consumption", "kcal/t"),
            ]),
            ("USM", [
                ("Yield",             "yield_total",               "%"),
                ("Availability",      "availability",              "%"),
                ("Utilisation",       "utilisation",               "%"),
                ("Rolling Rate",      "rolling_rate",              "t/hr"),
                ("Sp. Power Consmn.", "specific_power_consumption","kWh/t"),
                ("Sp. Heat Consmn.",  "specific_heat_consumption", "kcal/t"),
            ]),
            ("WRM", [
                ("Yield",             "yield_total",               "%"),
                ("Availability",      "availability",              "%"),
                ("Utilisation",       "utilisation",               "%"),
                ("Rolling Rate",      "rolling_rate",              "t/hr"),
                ("Sp. Power Consmn.", "specific_power_consumption","kWh/t"),
                ("Sp. Heat Consmn.",  "specific_heat_consumption", "kcal/t"),
            ]),
        ],
    },
}


def generate_techno_from_db(report_month: str, page_no: int) -> dict:
    """
    Generate techno pages 28-35 from techno_data.
    FY columns use till_month from March of each past FY.
    """
    import json as _json

    if page_no not in TECHNO_PAGES or page_no not in _TECHNO_DB_SCHEMA:
        return {}

    group, title, subtitle = TECHNO_PAGES[page_no]
    cfg = _TECHNO_DB_SCHEMA[page_no]

    fy         = _fy_start(report_month)
    ytd        = db.get_ytd_months(report_month)
    cply_month = db.get_cply_month(report_month)
    fy1_march  = f"{fy}-03"
    fy2_march  = f"{fy - 1}-03"
    fy3_march  = f"{fy - 2}-03"

    all_months = sorted(set(ytd) | {cply_month, fy1_march, fy2_march, fy3_march})

    store = {}
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(all_months))
        cur.execute(
            f"SELECT plant, report_month, unit, techno_json FROM techno_data WHERE report_month IN ({ph})",
            all_months,
        )
        for plant, rm, unit, tj in cur.fetchall():
            store.setdefault((plant, rm), {})[unit] = _json.loads(tj)
    finally:
        conn.close()

    _PLANT_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP"]
    available_plants = sorted(
        {p for (p, rm) in store if rm == report_month},
        key=lambda p: _PLANT_ORDER.index(p) if p in _PLANT_ORDER else 99,
    )

    def _gv(plant, rm, unit, key, period="month"):
        return store.get((plant, rm), {}).get(unit, {}).get(period, {}).get(key)

    def _make_row(label, unit_str, plant, src_unit, src_key):
        return {
            "label":    label,
            "unit":     unit_str,
            "fy3":      _fmt(_gv(plant, fy3_march,    src_unit, src_key, "till_month")),
            "fy2":      _fmt(_gv(plant, fy2_march,    src_unit, src_key, "till_month")),
            "fy1":      _fmt(_gv(plant, fy1_march,    src_unit, src_key, "till_month")),
            "target":   "",
            "months":   [_fmt(_gv(plant, m, src_unit, src_key)) for m in ytd],
            "cply":     _fmt(_gv(plant, cply_month,   src_unit, src_key)),
            "cum":      _fmt(_gv(plant, report_month, src_unit, src_key, "till_month")),
            "cum_cply": _fmt(_gv(plant, cply_month,   src_unit, src_key, "till_month")),
        }

    sections = []

    if cfg["type"] == "param":
        # sections = parameters, rows = available plant×unit combos
        multi_plant = len(available_plants) > 1
        for (sec_label, unit_str, unit_specs) in cfg["sections"]:
            rows = []
            for (src_unit, src_key) in unit_specs:
                for plant in available_plants:
                    if store.get((plant, report_month), {}).get(src_unit) is None:
                        continue
                    label = f"{plant} {src_unit}" if multi_plant else src_unit
                    rows.append(_make_row(label, unit_str, plant, src_unit, src_key))
            if rows:
                sections.append({"label": sec_label, "rows": rows})

    elif cfg["type"] == "mill":
        # sections = mill units, rows = params for that fixed plant
        plant = cfg.get("plant", "RSP")
        for (src_unit, param_specs) in cfg.get("sections", []):
            if store.get((plant, report_month), {}).get(src_unit) is None:
                continue
            rows = []
            for (param_label, src_key, unit_str) in param_specs:
                # include row if current month or any FY has a value
                has_val = any(
                    _gv(plant, rm, src_unit, src_key, p) is not None
                    for rm in [report_month, fy1_march, fy2_march, fy3_march]
                    for p in ["month", "till_month"]
                )
                if has_val:
                    rows.append(_make_row(param_label, unit_str, plant, src_unit, src_key))
            if rows:
                sections.append({"label": src_unit, "rows": rows})

    return {
        "title":          title,
        "subtitle":       subtitle,
        "variant":        "techno_params",
        "group":          group,
        "fy3_label":      _fy_label(fy - 3),
        "fy2_label":      _fy_label(fy - 2),
        "fy1_label":      _fy_label(fy - 1),
        "target_label":   f"Target {_fy_label(fy)}",
        "month_labels":   [_mlabel(m) for m in ytd],
        "cply_label":     _mlabel(cply_month),
        "cum_label":      _cum_label(ytd),
        "cum_cply_label": _cum_label([db.get_cply_month(m) for m in ytd]),
        "sections":       sections,
    }
