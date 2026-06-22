"""
Techno-Economic Parameter pages — pages 27-35.

Single data source: techno_table (report_month, plant_name, parameter_name, month_actual, ytd_actual)
Display ordering:   techno_param_master (group_code, section, row_label, unit, sort_order)
Annual targets:     techno_target (fy, param_id) → joined with techno_param_master

Column layout:
  <FY-2> Actual | <FY-1> Actual | Target <FY> |
  Apr'YY … <report month> | <CPLY month> | Apr-<Mon>'YY | Apr-<Mon>'YY-1

Annual FY value = March ytd_actual (Apr-to-Mar); falls back to AVG(month_actual).

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
    "BOF Slag Utilisation",
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
    "CDI", "Si in HM", "S in HM", "HBT", "Coke Screen Loss",
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

# BSL BF per-furnace aggregation methods
_BSL_BF_AGG = {
    "CDI":             "wtavg",
    "BF Coke Rate":    "wtavg",
    "Nut Coke Rate":   "wtavg",
    "Fuel Rate":       "wtavg",
    "Sinter in Burden":"wtavg",
    "Pellet in Burden":"wtavg",
    "Si in HM":        "wtavg",
    "S in HM":         "wtavg",
    "Slag Rate":       "wtavg",
    "BF Productivity": "harmonic",
    "HBT":             "simple",
    "O2 Enrichment":   "simple",
    "Hot Metal Temp":  "simple",
    "Iron Ore":        "sum",
    "Sinter Consumption": "sum",
    "BF Scrap":        "sum",
    "Pellet Consumption": "sum",
}
_BSL_FURNACES    = ["BSL BF-1", "BSL BF-2", "BSL BF-4", "BSL BF-5"]
_BSL_BF_ALL      = _BSL_FURNACES + ["BSL Plant Shop"]

# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def _pk(group_code, section, row_label):
    """Return (plant_name, parameter_name) key for techno_table lookup."""
    if group_code in ('MAJOR', 'COKE_SINTER', 'IRON_MAKING', 'SMS'):
        return (row_label, section)
    if group_code == 'BSL':
        return (f'BSL {section}', row_label)
    if group_code.startswith('MILL_'):
        plant = group_code[5:]           # 'MILL_BSP' → 'BSP'
        return (f'{plant} {section}', row_label)
    return (row_label, section)

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
# Data access — all from techno_table
# ---------------------------------------------------------------------------

def _avg_map(cur, months):
    """(plant, param) → AVG(month_actual) over given months."""
    if not months:
        return {}
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT plant_name, parameter_name, AVG(month_actual)
        FROM techno_table
        WHERE report_month IN ({ph}) AND month_actual IS NOT NULL
        GROUP BY plant_name, parameter_name
    """, months)
    return {(r[0], r[1]): r[2] for r in cur.fetchall()}


def _ytd_of_month(cur, month):
    """(plant, param) → ytd_actual for a single month."""
    cur.execute("""
        SELECT plant_name, parameter_name, ytd_actual
        FROM techno_table
        WHERE report_month=? AND ytd_actual IS NOT NULL
    """, (month,))
    return {(r[0], r[1]): r[2] for r in cur.fetchall()}


def _annual_map(cur, fy):
    """(plant, param) → annual value for a past FY.
    Uses latest stored ytd_actual within the FY (March = full year);
    falls back to AVG(month_actual) when no ytd stored.
    Returns (map, ytd_keys) where ytd_keys = params that had real ytd_actual."""
    months = _fy_months(fy)
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT plant_name, parameter_name, report_month, ytd_actual
        FROM techno_table
        WHERE report_month IN ({ph}) AND ytd_actual IS NOT NULL
        ORDER BY report_month
    """, months)
    out = {}
    ytd_keys = set()
    for plant, param, _, ytd in cur.fetchall():
        key = (plant, param)
        out[key] = ytd           # later month overwrites — March wins
        ytd_keys.add(key)
    for key, avg in _avg_map(cur, months).items():
        out.setdefault(key, avg)
    return out, ytd_keys


def _fetch_techno_data(cur, plant_params, months):
    """Return {(plant, param): {month: month_actual}} for the given pairs and months."""
    if not plant_params or not months:
        return {}
    pp_set  = set(plant_params)
    plants  = list({p  for p, _ in pp_set})
    params  = list({pm for _, pm in pp_set})
    ph_m  = ",".join("?" * len(months))
    ph_p  = ",".join("?" * len(plants))
    ph_pm = ",".join("?" * len(params))
    cur.execute(
        f"SELECT plant_name, parameter_name, report_month, month_actual "
        f"FROM techno_table "
        f"WHERE report_month IN ({ph_m}) AND plant_name IN ({ph_p}) AND parameter_name IN ({ph_pm})",
        list(months) + plants + params,
    )
    result = {}
    for plant, param, month, val in cur.fetchall():
        if val is not None and (plant, param) in pp_set:
            result.setdefault((plant, param), {})[month] = val
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
    Returns {("SAIL", parameter_name): value}."""
    out = {}

    # BF params weighted by Hot Metal
    for param in _BF_HM_PARAMS:
        num = den = 0.0
        for m in months:
            for p in _BF_PLANTS:
                v = techno_data.get((p, param), {}).get(m)
                w = hm_by_plant.get(p, {}).get(m)
                if v is not None and w is not None and w > 0:
                    num += v * w
                    den += w
        out[("SAIL", param)] = num / den if den > 0 else None

    # BF Productivity: SAIL = ΣHM / Σ(HM / plant_BFprod)
    t_hm = t_denom = 0.0
    for m in months:
        for p in _BF_PLANTS:
            hm  = hm_by_plant.get(p, {}).get(m)
            bfp = techno_data.get((p, "BF Productivity"), {}).get(m)
            if hm is not None and bfp is not None and bfp > 0:
                t_hm    += hm
                t_denom += hm / bfp
    out[("SAIL", "BF Productivity")] = t_hm / t_denom if t_denom > 0 else None

    # SMS params weighted by Crude Steel / shops per plant
    for param in _SMS_PARAMS:
        num = den = 0.0
        for m in months:
            for shop in _SMS_SHOPS:
                plant = _SMS_SHOP_PLANT[shop]
                n     = _PLANT_SHOP_CNT[plant]
                v  = techno_data.get((shop, param), {}).get(m)
                cs = cs_by_plant.get(plant, {}).get(m)
                if v is not None and cs is not None and cs > 0:
                    w = cs / n
                    num += v * w
                    den += w
        out[("SAIL", param)] = num / den if den > 0 else None

    # Specific Energy Consumption weighted by Crude Steel
    num = den = 0.0
    for m in months:
        for p in _BF_PLANTS:
            v  = techno_data.get((p, "Specific Energy Consumption"), {}).get(m)
            cs = cs_by_plant.get(p, {}).get(m)
            if v is not None and cs is not None and cs > 0:
                num += v * cs
                den += cs
    out[("SAIL", "Specific Energy Consumption")] = num / den if den > 0 else None

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
    """Replace AVG fallbacks with production-weighted annual values for
    plant-level MAJOR params. Only overrides keys not already in ytd_keys."""
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
                        fy2_map, fy1_map,
                        ytd, cply_ytd, cply_month, fy2_months, fy1_months):
    """Compute SAIL weighted-average techno values and inject them into the
    existing maps in-place, overriding stored SAIL values."""
    all_months  = sorted(set(ytd) | set(cply_ytd) | {cply_month} | set(fy2_months) | set(fy1_months))
    plant_params = _all_sail_plant_params()
    techno_data  = _fetch_techno_data(cur, plant_params, all_months)
    prod_raw     = _fetch_prod_multi(cur, _BF_PLANTS, ["Hot Metal", "Total Crude Steel"], all_months)
    hm = prod_raw["Hot Metal"]
    cs = prod_raw["Total Crude Steel"]

    for m in ytd:
        for key, val in _compute_sail(techno_data, hm, cs, [m]).items():
            mon_map.setdefault(key, {})[m] = val

    for key, val in _compute_sail(techno_data, hm, cs, [cply_month]).items():
        cply_map[key] = val

    for key, val in _compute_sail(techno_data, hm, cs, ytd).items():
        cum_map[key] = val

    for key, val in _compute_sail(techno_data, hm, cs, cply_ytd).items():
        ccum_map[key] = val

    for key, val in _compute_sail(techno_data, hm, cs, fy2_months).items():
        fy2_map[key] = val

    for key, val in _compute_sail(techno_data, hm, cs, fy1_months).items():
        fy1_map[key] = val


def _inject_bsl_bf_wtavg(cur, cum_map, ccum_map, fy2_map, fy1_map,
                          ytd, cply_ytd, fy2_months, fy1_months):
    """Compute YTD cumulative values for BSL BF per-furnace and Plant Shop params
    from monthly actuals so that uploading any middle month auto-corrects all cums."""
    all_months = sorted(set(ytd) | set(cply_ytd) | set(fy2_months) | set(fy1_months))
    if not all_months:
        return

    bsl_params = list(_BSL_BF_AGG.keys()) + ["HM Production"]
    all_pp = {(plant, param) for plant in _BSL_BF_ALL for param in bsl_params}
    data   = _fetch_techno_data(cur, all_pp, all_months)

    # Per-furnace HM Production values
    fce_hm = {}   # {(furnace, month): hm_val}
    for furnace in _BSL_FURNACES:
        for m, v in data.get((furnace, "HM Production"), {}).items():
            if v and v > 0:
                fce_hm[(furnace, m)] = v

    # Total BSL HM from production_table for BSL Plant Shop weighting
    ph_m = ",".join("?" * len(all_months))
    cur.execute(
        f"SELECT report_month, month_actual FROM production_table "
        f"WHERE plant_name='BSL' AND item_name='Hot Metal' AND report_month IN ({ph_m})",
        all_months,
    )
    prod_hm = {m: v for m, v in cur.fetchall() if v and v > 0}

    def _agg(plant_name, section, months):
        method  = _BSL_BF_AGG.get(section)
        if not method:
            return None
        vals    = data.get((plant_name, section), {})
        is_shop = (plant_name == "BSL Plant Shop")

        if method == "sum":
            vs = [v for m in months if (v := vals.get(m)) is not None]
            return round(sum(vs), 4) if vs else None
        if method == "simple":
            vs = [v for m in months if (v := vals.get(m)) is not None]
            return round(sum(vs) / len(vs), 4) if vs else None
        if method == "wtavg":
            num = den = 0.0
            for m in months:
                v  = vals.get(m)
                hm = prod_hm.get(m) if is_shop else fce_hm.get((plant_name, m))
                if v is not None and hm:
                    num += v * hm
                    den += hm
            return round(num / den, 4) if den else None
        if method == "harmonic":
            num = den = 0.0
            for m in months:
                v  = vals.get(m)
                hm = prod_hm.get(m) if is_shop else fce_hm.get((plant_name, m))
                if v is not None and v > 0 and hm:
                    num += hm
                    den += hm / v
            return round(num / den, 4) if den else None
        return None

    for plant_name in _BSL_BF_ALL:
        for section in _BSL_BF_AGG:
            key = (plant_name, section)
            cum_map[key]  = _agg(plant_name, section, ytd)
            ccum_map[key] = _agg(plant_name, section, cply_ytd)
            fy2_map[key]  = _agg(plant_name, section, fy2_months)
            fy1_map[key]  = _agg(plant_name, section, fy1_months)


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
            SELECT group_code, section, row_label, unit
            FROM techno_param_master
            WHERE group_code=? ORDER BY sort_order, param_id
        """, (group,))
        master = cur.fetchall()

        fy2_map, fy2_ytd_keys = _annual_map(cur, fy - 2)
        fy1_map, fy1_ytd_keys = _annual_map(cur, fy - 1)
        cum_map  = _ytd_of_month(cur, report_month)
        ccum_map = _ytd_of_month(cur, cply_month)

        # Per-month actuals for YTD columns
        ph = ",".join("?" * len(ytd))
        cur.execute(f"""
            SELECT plant_name, parameter_name, report_month, month_actual
            FROM techno_table WHERE report_month IN ({ph})
        """, ytd)
        mon_map = {}
        for plant, param, m, v in cur.fetchall():
            mon_map.setdefault((plant, param), {})[m] = v

        # CPLY monthly actuals
        cur.execute("""
            SELECT plant_name, parameter_name, month_actual
            FROM techno_table WHERE report_month=?
        """, (cply_month,))
        cply_map = {(r[0], r[1]): r[2] for r in cur.fetchall()}

        # Annual targets (joined via param_master to get plant/param keys)
        cur.execute("""
            SELECT pm.group_code, pm.section, pm.row_label, tt.target
            FROM techno_target tt
            JOIN techno_param_master pm ON tt.param_id = pm.param_id
            WHERE tt.fy=? AND pm.group_code=?
        """, (_fy_label(fy), group))
        tgt_map = {}
        for gc, sec, rl, tgt in cur.fetchall():
            tgt_map[_pk(gc, sec, rl)] = tgt

        if group == "MAJOR":
            _inject_plant_weighted_annual(cur, fy2_map, fy2_ytd_keys, _fy_months(fy - 2))
            _inject_plant_weighted_annual(cur, fy1_map, fy1_ytd_keys, _fy_months(fy - 1))
            _inject_sail_techno(
                cur, mon_map, cum_map, ccum_map, cply_map, fy2_map, fy1_map,
                ytd, cply_ytd, cply_month,
                _fy_months(fy - 2), _fy_months(fy - 1),
            )

        if group == "IRON_MAKING":
            # Plant Shop CDI rows mirror the MAJOR CDI Rate for each plant
            for p in _BF_PLANTS:
                src = (p, "CDI Rate")
                dst = (f"{p} Plant Shop", "CDI")
                for mp in (fy2_map, fy1_map, cum_map, ccum_map, cply_map, tgt_map):
                    if src in mp:
                        mp.setdefault(dst, mp[src])
                if src in mon_map:
                    mon_map.setdefault(dst, dict(mon_map[src]))

            _inject_bsl_bf_wtavg(
                cur, cum_map, ccum_map,
                fy2_map, fy1_map,
                ytd, cply_ytd, _fy_months(fy - 2), _fy_months(fy - 1),
            )

        # Build output sections
        sections, by_sec = [], {}
        for group_code, section, row_label, unit in master:
            if group == "MILL_DSP" and section == "Section Mill":
                continue
            if group == "COKE_SINTER" and section not in _COKE_SINTER_VISIBLE:
                continue
            if group == "IRON_MAKING" and section not in _IRON_MAKING_VISIBLE:
                continue
            if group == "SMS" and section not in _BOF_VISIBLE:
                continue
            if group == "IRON_MAKING" and section in _DSP_FURNACE_SECTIONS \
                    and not (row_label.startswith("DSP") or row_label.startswith("RSP")):
                continue

            pk = _pk(group_code, section, row_label)
            row = {
                "label":  row_label,
                "unit":   unit or "",
                "fy2":    _fmt(fy2_map.get(pk)),
                "fy1":    _fmt(fy1_map.get(pk)),
                "target": _fmt(tgt_map.get(pk)),
                "months": [_fmt(mon_map.get(pk, {}).get(m)) for m in ytd],
                "cply":     _fmt(cply_map.get(pk)),
                "cum":      _fmt(cum_map.get(pk)),
                "cum_cply": _fmt(ccum_map.get(pk)),
            }
            if section not in by_sec:
                by_sec[section] = {"label": section, "rows": []}
                sections.append(by_sec[section])
            by_sec[section]["rows"].append(row)

        return {
            "title":         title,
            "subtitle":      subtitle,
            "variant":       "techno_params",
            "fy2_label":     _fy_label(fy - 2),
            "fy1_label":     _fy_label(fy - 1),
            "target_label":  f"Target {_fy_label(fy)}",
            "month_labels":  [_mlabel(m) for m in ytd],
            "cply_label":    _mlabel(cply_month),
            "cum_label":     _cum_label(ytd),
            "cum_cply_label": _cum_label(cply_ytd),
            "sections":      sections,
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

        # Targets for SAIL via param_master join
        cur.execute("""
            SELECT pm.section, tt.target
            FROM techno_target tt
            JOIN techno_param_master pm ON tt.param_id = pm.param_id
            WHERE tt.fy=? AND pm.group_code='MAJOR' AND pm.row_label='SAIL'
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
            SELECT pm.section, tt.target
            FROM techno_target tt
            JOIN techno_param_master pm ON tt.param_id = pm.param_id
            WHERE tt.fy=? AND pm.group_code='MAJOR' AND pm.row_label='SAIL'
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

    # Plant-level targets from techno_target joined with param_master
    cur.execute("""
        SELECT pm.group_code, pm.section, pm.row_label, tt.target
        FROM techno_target tt
        JOIN techno_param_master pm ON tt.param_id = pm.param_id
        WHERE tt.fy=? AND pm.group_code IN ('MAJOR','SMS')
          AND pm.row_label != 'SAIL'
    """, (fy,))
    tgt = {}   # {(plant, param): target}
    for gc, sec, rl, t in cur.fetchall():
        tgt[_pk(gc, sec, rl)] = t
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

    return out


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
