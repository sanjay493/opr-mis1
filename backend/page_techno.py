"""
Techno-Economic Parameter pages — pages 27-35.

Data sources:
  techno_param_master (param_id, group_code, section, row_label, unit, sort_order)
  techno_monthly      (report_month, param_id, actual)
  techno_target       (fy, param_id, target)

Column layout (per the printed report):
  <FY-2> Actual | <FY-1> Actual | Target <FY> |
  Apr'YY ... <report month> | <CPLY month> | Apr-<Mon>'YY | Apr-<Mon>'YY-1

Annual actuals for past FYs = AVG of whatever monthly values exist in that FY
(Apr..Mar).  Cumulative columns = AVG of Apr..report-month values.

SAIL row computation (MAJOR page + Summary page te_table):
  BF params (Coal/HM, Coke, Nut Coke, CDI, Fuel, Sinter%, Pellet%):
      weighted average of plant values, weight = plant Hot Metal production
  BF Productivity:
      SAIL = sum(HM) / sum(HM / plant_BFprod)
  SMS params (HM Consumption, Scrap, TMI):
      weighted average of shop values, weight = plant Crude Steel / shops_per_plant
  Specific Energy Consumption:
      weighted average of plant values, weight = plant Crude Steel production
"""
import sqlite3
import db

_MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Sections in IRON_MAKING that show furnace-level DSP/RSP data only.
_DSP_FURNACE_SECTIONS = frozenset({
    "Si in HM", "S in HM", "HBT",
})

# Whitelist of sections shown on page 28 — everything else is hidden.
_COKE_SINTER_VISIBLE = frozenset({
    "Dry Coal Charge/Oven",
    "Coal Tar Yield",
    "Coke Oven Gas Yield",
    "Crude Benzol Yield",
    "Amm. Sulphate Yld",
    "Sinter Productivity",
    "BOF Slag Utilisation",
})

# Whitelist of sections shown on page 30 (SMS) — everything else is hidden.
_BOF_VISIBLE = frozenset({
    "Average Blows (Per Day)",
    "Average Heat Weight",
    "Oxygen Blowing",
    "Refractory",
    "Hot Metal Consumption",
    "Scrap Consumption",
    "TMI",
    "Converter Yield",
    "Caster Availability",
    "Caster Utilisation",
    "Caster Yield",
    "Avg Cast Sequence",
    "Fe-Mn Consumption",
    "Fe-Si Consumption",
    "Si-Mn Consumption",
    "Lime Consumption",
    "LD Gas Recovery",
    "Tap to Tap Time",
    "Average Heat Weight",
})

# Whitelist of sections shown on page 29 — everything else is hidden.
_IRON_MAKING_VISIBLE = frozenset({
    "CDI",
    "Si in HM",
    "S in HM",
    "HBT",
    "Coke Screen Loss",
})

# IRON_MAKING page 29: CDI Avg rows mirror the plant-level MAJOR CDI Rate.
# Maps IRON_MAKING/CDI param_id → MAJOR/CDI Rate param_id.
_CDI_AVG_FROM_MAJOR = {63: 614, 64: 615, 65: 616, 66: 617, 67: 618}

# Aggregation rules for BSL BF per-furnace and Plant Shop cumulative computation.
# Cumulative is always computed from monthly actuals (never from stored cum_actual)
# so that uploading any middle month automatically corrects all affected cums.
_BSL_BF_AGG = {
    # Weighted average by HM production
    "CDI":               "wtavg",
    "BF Coke Rate":      "wtavg",
    "Nut Coke Rate":     "wtavg",
    "Fuel Rate":         "wtavg",
    "Sinter in Burden":  "wtavg",
    "Pellet in Burden":  "wtavg",
    "Si in HM":          "wtavg",
    "S in HM":           "wtavg",
    "Slag Rate":         "wtavg",
    # Harmonic mean weighted by HM production
    "BF Productivity":   "harmonic",
    # Simple average (not production-dependent)
    "HBT":               "simple",
    "O2 Enrichment":     "simple",
    "Hot Metal Temp":    "simple",
    # Running sum
    "Iron Ore":          "sum",
    "Sinter Consumption": "sum",
    "BF Scrap":          "sum",
    "Pellet Consumption": "sum",
}

# ---------------------------------------------------------------------------
# Constants for SAIL weighted-average computation
# ---------------------------------------------------------------------------

_BF_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]

# BF params weighted by Hot Metal production: section → {plant/SAIL: param_id}
_BF_HM_SECTIONS = {
    "Coal to Hot Metal":    {"BSP": 1,   "DSP": 2,   "RSP": 3,   "BSL": 4,   "ISP": 5,   "SAIL": 6},
    "Coke Rate":            {"BSP": 7,   "DSP": 8,   "RSP": 9,   "BSL": 10,  "ISP": 11,  "SAIL": 12},
    "Nut Coke Consumption": {"BSP": 13,  "DSP": 14,  "RSP": 15,  "BSL": 16,  "ISP": 17,  "SAIL": 18},
    "CDI Rate":             {"BSP": 614, "DSP": 615, "RSP": 616, "BSL": 617, "ISP": 618, "SAIL": 619},
    "Fuel Rate":            {"BSP": 19,  "DSP": 20,  "RSP": 21,  "BSL": 22,  "ISP": 23,  "SAIL": 24},
    "Sinter in Burden":     {"BSP": 626, "DSP": 627, "RSP": 628, "BSL": 629, "ISP": 630, "SAIL": 631},
    "Pellet in Burden":     {"BSP": 632, "DSP": 633, "RSP": 634, "BSL": 635, "ISP": 636, "SAIL": 637},
}

# BF Productivity: SAIL = ΣHM / Σ(HM/plant_BFprod)
_BF_PROD_PARAMS = {"BSP": 25, "DSP": 26, "RSP": 27, "BSL": 28, "ISP": 29, "SAIL": 30}

# SMS-level params: shop → param_id (SAIL is the aggregate)
_SMS_SHOP_PARAMS = {
    "Hot Metal Consumption": {
        "BSP SMS-2": 644, "BSP SMS-3": 645, "DSP SMS": 646,
        "RSP SMS-1": 647, "RSP SMS-2": 648,
        "BSL SMS-1": 649, "BSL SMS-2": 650, "ISP SMS-1": 651, "SAIL": 652,
    },
    "Scrap Consumption": {
        "BSP SMS-2": 653, "BSP SMS-3": 654, "DSP SMS": 655,
        "RSP SMS-1": 656, "RSP SMS-2": 657,
        "BSL SMS-1": 658, "BSL SMS-2": 659, "ISP SMS-1": 660, "SAIL": 661,
    },
    "TMI": {
        "BSP SMS-2": 662, "BSP SMS-3": 663, "DSP SMS": 664,
        "RSP SMS-1": 665, "RSP SMS-2": 666,
        "BSL SMS-1": 667, "BSL SMS-2": 668, "ISP SMS-1": 669, "SAIL": 670,
    },
}
# Shop → plant mapping for production weight lookup
_SMS_SHOP_PLANT = {
    "BSP SMS-2": "BSP", "BSP SMS-3": "BSP", "DSP SMS": "DSP",
    "RSP SMS-1": "RSP", "RSP SMS-2": "RSP",
    "BSL SMS-1": "BSL", "BSL SMS-2": "BSL", "ISP SMS-1": "ISP",
}
# Number of shops per plant (for equal-split CS weight within plant)
_PLANT_SHOP_CNT = {"BSP": 2, "DSP": 1, "RSP": 2, "BSL": 2, "ISP": 1}

# Specific Energy Consumption weighted by Crude Steel
_SEC_PARAMS = {"BSP": 31, "DSP": 32, "RSP": 33, "BSL": 34, "ISP": 35, "SAIL": 36}

# All component (non-SAIL) param_ids needed for SAIL computation
_SAIL_COMPONENT_PIDS = frozenset(
    pid
    for pm in list(_BF_HM_SECTIONS.values()) + [_BF_PROD_PARAMS, _SEC_PARAMS]
    for k, pid in pm.items() if k != "SAIL"
) | frozenset(
    pid
    for sm in _SMS_SHOP_PARAMS.values()
    for k, pid in sm.items() if k != "SAIL"
)

# page number → (group_code, title, subtitle, orientation)
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


def _fy_start(report_month):
    y, m = int(report_month[:4]), int(report_month[5:7])
    return y if m >= 4 else y - 1

def _fy_months(fy):
    """FY starting Apr of year fy → 12 'YYYY-MM' strings."""
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
    """Precision like the printed report: 448 / 67.5 / 2.11 / 0.964."""
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


def _avg_map(cur, months):
    """param_id → AVG(actual) over the given months."""
    if not months:
        return {}
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT param_id, AVG(actual) FROM techno_monthly
        WHERE report_month IN ({ph}) GROUP BY param_id
    """, months)
    return dict(cur.fetchall())


def _cum_of_month(cur, month):
    """param_id → stored cum_actual of one month (plant-reported Apr-to-month)."""
    cur.execute("""
        SELECT param_id, cum_actual FROM techno_monthly
        WHERE report_month=? AND cum_actual IS NOT NULL
    """, (month,))
    return dict(cur.fetchall())


def _annual_map(cur, fy):
    """param_id → annual value for a past FY.
    Latest stored cum_actual within the FY (Mar row = full year);
    falls back to AVG(actual) for params with no cumulative stored.
    Returns (map, cum_pids) where cum_pids = params that had real cum_actual."""
    months = _fy_months(fy)
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT param_id, report_month, cum_actual FROM techno_monthly
        WHERE report_month IN ({ph}) AND cum_actual IS NOT NULL
        ORDER BY report_month
    """, months)
    out = {}
    cum_pids = set()
    for pid, _, c in cur.fetchall():   # later months overwrite earlier ones
        out[pid] = c
        cum_pids.add(pid)
    for pid, avg in _avg_map(cur, months).items():
        out.setdefault(pid, avg)
    return out, cum_pids


# ---------------------------------------------------------------------------
# SAIL weighted-average helpers
# ---------------------------------------------------------------------------

def _fetch_techno_multi(cur, param_ids, months):
    """Return {param_id: {month: actual}} for the given param_ids and months."""
    pids = list(param_ids)
    if not pids or not months:
        return {pid: {} for pid in pids}
    ph_p = ",".join("?" * len(pids))
    ph_m = ",".join("?" * len(months))
    cur.execute(
        f"SELECT param_id, report_month, actual FROM techno_monthly "
        f"WHERE param_id IN ({ph_p}) AND report_month IN ({ph_m})",
        pids + list(months),
    )
    result = {pid: {} for pid in pids}
    for pid, m, v in cur.fetchall():
        if v is not None and pid in result:
            result[pid][m] = v
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


def _compute_sail(techno_data, hm_by_plant, cs_by_plant, months):
    """
    Compute SAIL-level aggregate techno values for the given months.
    Returns {sail_param_id: value}.
    """
    out = {}

    # BF params weighted by Hot Metal
    for pid_map in _BF_HM_SECTIONS.values():
        sail_pid = pid_map["SAIL"]
        num = den = 0.0
        for m in months:
            for p in _BF_PLANTS:
                v = techno_data.get(pid_map[p], {}).get(m)
                w = hm_by_plant.get(p, {}).get(m)
                if v is not None and w is not None and w > 0:
                    num += v * w
                    den += w
        out[sail_pid] = num / den if den > 0 else None

    # BF Productivity: SAIL = ΣHM / Σ(HM / plant_BFprod)
    t_hm = t_denom = 0.0
    for m in months:
        for p in _BF_PLANTS:
            hm  = hm_by_plant.get(p, {}).get(m)
            bfp = techno_data.get(_BF_PROD_PARAMS[p], {}).get(m)
            if hm is not None and bfp is not None and bfp > 0:
                t_hm    += hm
                t_denom += hm / bfp
    out[_BF_PROD_PARAMS["SAIL"]] = t_hm / t_denom if t_denom > 0 else None

    # SMS params weighted by Crude Steel / shops per plant
    for shop_pid_map in _SMS_SHOP_PARAMS.values():
        sail_pid = shop_pid_map["SAIL"]
        num = den = 0.0
        for m in months:
            for shop, pid in shop_pid_map.items():
                if shop == "SAIL":
                    continue
                plant = _SMS_SHOP_PLANT[shop]
                n     = _PLANT_SHOP_CNT[plant]
                v  = techno_data.get(pid, {}).get(m)
                cs = cs_by_plant.get(plant, {}).get(m)
                if v is not None and cs is not None and cs > 0:
                    w = cs / n
                    num += v * w
                    den += w
        out[sail_pid] = num / den if den > 0 else None

    # Specific Energy Consumption weighted by Crude Steel
    num = den = 0.0
    for m in months:
        for p in _BF_PLANTS:
            v  = techno_data.get(_SEC_PARAMS[p], {}).get(m)
            cs = cs_by_plant.get(p, {}).get(m)
            if v is not None and cs is not None and cs > 0:
                num += v * cs
                den += cs
    out[_SEC_PARAMS["SAIL"]] = num / den if den > 0 else None

    return out


def _inject_plant_weighted_annual(cur, fy_map, cum_pids, months):
    """Replace simple-AVG fallbacks with production-weighted annual values for
    plant-level MAJOR params (same logic as _compute_sail but per plant, not SAIL).
    Only overrides params that lacked cum_actual (not in cum_pids).
    """
    if not months:
        return
    all_plant_pids = set()
    for pid_map in _BF_HM_SECTIONS.values():
        for p in _BF_PLANTS:
            all_plant_pids.add(pid_map[p])
    for p in _BF_PLANTS:
        all_plant_pids.add(_BF_PROD_PARAMS[p])
    for shop_map in _SMS_SHOP_PARAMS.values():
        for shop, pid in shop_map.items():
            if shop != "SAIL":
                all_plant_pids.add(pid)
    for p in _BF_PLANTS:
        all_plant_pids.add(_SEC_PARAMS[p])

    techno_data = _fetch_techno_multi(cur, all_plant_pids, months)
    prod_raw    = _fetch_prod_multi(cur, _BF_PLANTS,
                                    ["Hot Metal", "Total Crude Steel"], months)
    hm = prod_raw["Hot Metal"]
    cs = prod_raw["Total Crude Steel"]

    # BF params: weighted by Hot Metal production
    for pid_map in _BF_HM_SECTIONS.values():
        for p in _BF_PLANTS:
            pid = pid_map[p]
            if pid in cum_pids:
                continue
            num = den = 0.0
            for m in months:
                v = techno_data.get(pid, {}).get(m)
                w = hm.get(p, {}).get(m)
                if v is not None and w is not None and w > 0:
                    num += v * w
                    den += w
            if den > 0:
                fy_map[pid] = num / den

    # BF Productivity: harmonic mean weighted by Hot Metal
    for p in _BF_PLANTS:
        pid = _BF_PROD_PARAMS[p]
        if pid in cum_pids:
            continue
        t_hm = t_denom = 0.0
        for m in months:
            hm_v = hm.get(p, {}).get(m)
            bfp  = techno_data.get(pid, {}).get(m)
            if hm_v is not None and bfp is not None and bfp > 0:
                t_hm    += hm_v
                t_denom += hm_v / bfp
        if t_denom > 0:
            fy_map[pid] = t_hm / t_denom

    # SMS params: weighted by Crude Steel / shop count
    for shop_map in _SMS_SHOP_PARAMS.values():
        for shop, pid in shop_map.items():
            if shop == "SAIL":
                continue
            if pid in cum_pids:
                continue
            plant = _SMS_SHOP_PLANT[shop]
            n     = _PLANT_SHOP_CNT[plant]
            num = den = 0.0
            for m in months:
                v    = techno_data.get(pid, {}).get(m)
                cs_v = cs.get(plant, {}).get(m)
                if v is not None and cs_v is not None and cs_v > 0:
                    w = cs_v / n
                    num += v * w
                    den += w
            if den > 0:
                fy_map[pid] = num / den

    # Specific Energy Consumption: weighted by Crude Steel
    for p in _BF_PLANTS:
        pid = _SEC_PARAMS[p]
        if pid in cum_pids:
            continue
        num = den = 0.0
        for m in months:
            v    = techno_data.get(pid, {}).get(m)
            cs_v = cs.get(p, {}).get(m)
            if v is not None and cs_v is not None and cs_v > 0:
                num += v * cs_v
                den += cs_v
        if den > 0:
            fy_map[pid] = num / den


def _inject_sail_techno(cur, mon_map, cum_map, ccum_map, cply_map,
                        fy2_map, fy1_map,
                        ytd, cply_ytd, cply_month, fy2_months, fy1_months):
    """
    Compute SAIL weighted-average techno values and inject them into the
    existing maps in-place, overriding the stored values for SAIL param_ids.
    """
    all_months = sorted(
        set(ytd) | set(cply_ytd) | {cply_month} | set(fy2_months) | set(fy1_months)
    )
    techno_data = _fetch_techno_multi(cur, _SAIL_COMPONENT_PIDS, all_months)
    prod_raw    = _fetch_prod_multi(cur, _BF_PLANTS,
                                    ["Hot Metal", "Total Crude Steel"], all_months)
    hm = prod_raw["Hot Metal"]
    cs = prod_raw["Total Crude Steel"]

    # Per-month actuals (for monthly columns)
    for m in ytd:
        for sail_pid, val in _compute_sail(techno_data, hm, cs, [m]).items():
            mon_map.setdefault(sail_pid, {})[m] = val

    # Monthly CPLY
    for sail_pid, val in _compute_sail(techno_data, hm, cs, [cply_month]).items():
        cply_map[sail_pid] = val

    # Cumulative YTD
    for sail_pid, val in _compute_sail(techno_data, hm, cs, ytd).items():
        cum_map[sail_pid] = val

    # Cumulative YTD CPLY
    for sail_pid, val in _compute_sail(techno_data, hm, cs, cply_ytd).items():
        ccum_map[sail_pid] = val

    # Historical annual FY-2
    for sail_pid, val in _compute_sail(techno_data, hm, cs, fy2_months).items():
        fy2_map[sail_pid] = val

    # Historical annual FY-1
    for sail_pid, val in _compute_sail(techno_data, hm, cs, fy1_months).items():
        fy1_map[sail_pid] = val


def _inject_bsl_bf_wtavg(cur, cum_map, ccum_map, fy2_map, fy1_map,
                          ytd, cply_ytd, fy2_months, fy1_months):
    """
    Compute YTD cumulative values for ALL BSL BF params (per-furnace and Plant Shop)
    from monthly actuals — never from stored cum_actual. This ensures uploading any
    middle month automatically corrects cumulative values for all subsequent months.

    Per-furnace (BSL BF-1/2/4/5):
      Weighted/harmonic/simple/sum using per-furnace HM Production as weight.
    BSL Plant Shop:
      Monthly value comes directly from the PDF's BF Shop row (priority 5).
      For YTD, weighted/harmonic use total BSL Hot Metal from production_table
      so the Plant Shop cumulative is independent of per-furnace HM Production data.
    """
    all_months = sorted(set(ytd) | set(cply_ytd) | set(fy2_months) | set(fy1_months))
    if not all_months:
        return

    # Load per-furnace HM Production param_ids
    cur.execute("""
        SELECT p.param_id, p.row_label
        FROM techno_param_master p
        WHERE p.group_code = 'IRON_MAKING' AND p.section = 'HM Production'
          AND p.row_label LIKE 'BSL BF-%'
    """)
    hm_rows = cur.fetchall()
    hm_pid_to_label = {pid: lbl for pid, lbl in hm_rows}

    # Load all BSL BF section param_ids (per-furnace + Plant Shop)
    sections = list(_BSL_BF_AGG.keys())
    ph_s = ",".join("?" * len(sections))
    cur.execute(f"""
        SELECT p.param_id, p.section, p.row_label
        FROM techno_param_master p
        WHERE p.group_code = 'IRON_MAKING'
          AND p.section IN ({ph_s})
          AND (p.row_label LIKE 'BSL BF-%' OR p.row_label = 'BSL Plant Shop')
    """, sections)
    bf_rows = cur.fetchall()
    if not bf_rows:
        return

    # Fetch all monthly actuals (HM Production + BF params) in one query
    all_pids = list(hm_pid_to_label) + [r[0] for r in bf_rows]
    data = _fetch_techno_multi(cur, all_pids, all_months)

    # Per-furnace HM per month
    fce_hm = {}  # {(row_label, month): hm_val}
    for hm_pid, lbl in hm_pid_to_label.items():
        for m, v in data.get(hm_pid, {}).items():
            if v and v > 0:
                fce_hm[(lbl, m)] = v

    # Total BSL HM from production_table (for BSL Plant Shop YTD weighting)
    ph_m = ",".join("?" * len(all_months))
    cur.execute(
        f"SELECT report_month, month_actual FROM production_table "
        f"WHERE plant_name='BSL' AND item_name='Hot Metal' AND report_month IN ({ph_m})",
        all_months,
    )
    prod_hm = {m: v for m, v in cur.fetchall() if v and v > 0}

    def _agg(pid, section, row_label, months):
        method = _BSL_BF_AGG.get(section)
        if not method:
            return None
        vals = data.get(pid, {})
        is_shop = (row_label == "BSL Plant Shop")

        if method == "sum":
            vs = [v for m in months if (v := vals.get(m)) is not None]
            total = sum(vs)
            return round(total, 4) if vs else None

        if method == "simple":
            vs = [v for m in months if (v := vals.get(m)) is not None]
            return round(sum(vs) / len(vs), 4) if vs else None

        if method == "wtavg":
            num = den = 0.0
            for m in months:
                v = vals.get(m)
                hm = prod_hm.get(m) if is_shop else fce_hm.get((row_label, m))
                if v is not None and hm:
                    num += v * hm
                    den += hm
            return round(num / den, 4) if den else None

        if method == "harmonic":
            num = den = 0.0
            for m in months:
                v = vals.get(m)
                hm = prod_hm.get(m) if is_shop else fce_hm.get((row_label, m))
                if v is not None and v > 0 and hm:
                    num += hm
                    den += hm / v
            return round(num / den, 4) if den else None

        return None

    for pid, section, row_label in bf_rows:
        cum_map[pid]  = _agg(pid, section, row_label, ytd)
        ccum_map[pid] = _agg(pid, section, row_label, cply_ytd)
        fy2_map[pid]  = _agg(pid, section, row_label, fy2_months)
        fy1_map[pid]  = _agg(pid, section, row_label, fy1_months)


def generate_techno(report_month: str, page_no: int) -> dict:
    group, title, subtitle = TECHNO_PAGES[page_no]

    fy   = _fy_start(report_month)
    ytd  = db.get_ytd_months(report_month)               # Apr..report month
    cply_month = db.get_cply_month(report_month)
    cply_ytd   = [db.get_cply_month(m) for m in ytd]

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT param_id, section, row_label, unit
            FROM techno_param_master
            WHERE group_code=? ORDER BY sort_order, param_id
        """, (group,))
        master = cur.fetchall()

        fy2_map, fy2_cum_pids = _annual_map(cur, fy - 2)
        fy1_map, fy1_cum_pids = _annual_map(cur, fy - 1)
        cum_map  = _cum_of_month(cur, report_month)   # stored Apr-to-month cum
        ccum_map = _cum_of_month(cur, cply_month)

        # per-month values
        ph = ",".join("?" * len(ytd))
        cur.execute(f"""
            SELECT param_id, report_month, actual FROM techno_monthly
            WHERE report_month IN ({ph})
        """, ytd)
        mon_map = {}
        for pid, m, v in cur.fetchall():
            mon_map.setdefault(pid, {})[m] = v

        cur.execute("""
            SELECT param_id, actual FROM techno_monthly WHERE report_month=?
        """, (cply_month,))
        cply_map = dict(cur.fetchall())

        cur.execute("SELECT param_id, target FROM techno_target WHERE fy=?",
                    (_fy_label(fy),))
        tgt_map = dict(cur.fetchall())

        # Override SAIL rows with properly weighted averages;
        # also replace simple-AVG fallbacks in plant-level rows with production-weighted values.
        if group == "MAJOR":
            _inject_plant_weighted_annual(cur, fy2_map, fy2_cum_pids, _fy_months(fy - 2))
            _inject_plant_weighted_annual(cur, fy1_map, fy1_cum_pids, _fy_months(fy - 1))
            _inject_sail_techno(
                cur, mon_map, cum_map, ccum_map, cply_map, fy2_map, fy1_map,
                ytd, cply_ytd, cply_month,
                _fy_months(fy - 2), _fy_months(fy - 1),
            )

        # CDI Avg rows on IRON_MAKING page prefer the plant-level MAJOR CDI Rate.
        # Falls back to stored IRON_MAKING value when MAJOR has no data for a month.
        if group == "IRON_MAKING":
            for avg_pid, maj_pid in _CDI_AVG_FROM_MAJOR.items():
                if maj_pid in mon_map:
                    mon_map[avg_pid] = mon_map[maj_pid]
                if maj_pid in cum_map:
                    cum_map[avg_pid] = cum_map[maj_pid]
                if maj_pid in ccum_map:
                    ccum_map[avg_pid] = ccum_map[maj_pid]
                if maj_pid in cply_map:
                    cply_map[avg_pid] = cply_map[maj_pid]
                if maj_pid in fy2_map:
                    fy2_map[avg_pid] = fy2_map[maj_pid]
                if maj_pid in fy1_map:
                    fy1_map[avg_pid] = fy1_map[maj_pid]
                if maj_pid in tgt_map:
                    tgt_map[avg_pid] = tgt_map[maj_pid]
            # BSL BF cumulative = computed from monthly actuals, never stored cum
            _inject_bsl_bf_wtavg(
                cur, cum_map, ccum_map,
                fy2_map, fy1_map,
                ytd, cply_ytd, _fy_months(fy - 2), _fy_months(fy - 1),
            )

        sections, by_sec = [], {}
        for pid, section, row_label, unit in master:
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
            row = {
                "label": row_label,
                "unit":  unit or "",
                "fy2":    _fmt(fy2_map.get(pid)),
                "fy1":    _fmt(fy1_map.get(pid)),
                "target": _fmt(tgt_map.get(pid)),
                "months": [_fmt(mon_map.get(pid, {}).get(m)) for m in ytd],
                "cply":     _fmt(cply_map.get(pid)),
                "cum":      _fmt(cum_map.get(pid)),
                "cum_cply": _fmt(ccum_map.get(pid)),
            }
            if section not in by_sec:
                by_sec[section] = {"label": section, "rows": []}
                sections.append(by_sec[section])
            by_sec[section]["rows"].append(row)

        return {
            "title":    title,
            "subtitle": subtitle,
            "variant":  "techno_params",
            "fy2_label":    f"{_fy_label(fy - 2)}",
            "fy1_label":    f"{_fy_label(fy - 1)}",
            "target_label": f"Target {_fy_label(fy)}",
            "month_labels": [_mlabel(m) for m in ytd],
            "cply_label":      _mlabel(cply_month),
            "cum_label":       _cum_label(ytd),
            "cum_cply_label":  _cum_label(cply_ytd),
            "sections": sections,
        }
    finally:
        conn.close()


def generate_summary_te_table(report_month: str) -> list:
    """
    Generate the te_table for the SAIL Performance Summary page (page 3).
    Returns list of {parameter, unit, values: [target, month, cply, ytd, ytd_cply]}.
    All values use proper weighted averages (not stored SAIL values).
    """
    fy         = _fy_start(report_month)
    ytd        = db.get_ytd_months(report_month)
    cply_month = db.get_cply_month(report_month)
    cply_ytd   = [db.get_cply_month(m) for m in ytd]

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    try:
        all_months  = sorted(set(ytd) | set(cply_ytd) | {cply_month})
        techno_data = _fetch_techno_multi(cur, _SAIL_COMPONENT_PIDS, all_months)
        prod_raw    = _fetch_prod_multi(cur, _BF_PLANTS,
                                        ["Hot Metal", "Total Crude Steel"], all_months)
        hm = prod_raw["Hot Metal"]
        cs = prod_raw["Total Crude Steel"]

        cur.execute("SELECT param_id, target FROM techno_target WHERE fy=?",
                    (_fy_label(fy),))
        tgt_by_pid = dict(cur.fetchall())

        def entry(param_name, unit, sail_pid, month_sets):
            tgt_val = _fmt(tgt_by_pid.get(sail_pid))
            vals    = [_fmt(_compute_sail(techno_data, hm, cs, ms).get(sail_pid))
                       for ms in month_sets]
            return {"parameter": param_name, "unit": unit, "values": [tgt_val] + vals}

        period_sets = [
            [report_month],   # current month
            [cply_month],     # CPLY month
            ytd,              # YTD current
            cply_ytd,         # YTD CPLY
        ]

        return [
            entry("Coke Rate",       "kg/thm",   _BF_HM_SECTIONS["Coke Rate"]["SAIL"],    period_sets),
            entry("CDI",             "kg/thm",   _BF_HM_SECTIONS["CDI Rate"]["SAIL"],     period_sets),
            entry("Fuel Rate",       "kg/thm",   _BF_HM_SECTIONS["Fuel Rate"]["SAIL"],    period_sets),
            entry("BF Productivity", "t/m3/day", _BF_PROD_PARAMS["SAIL"],                 period_sets),
            entry("S.E.C.",          "Gcal/tcs", _SEC_PARAMS["SAIL"],                     period_sets),
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Page 3 bar chart data  (Coke Rate, CDI, BF Productivity, S.E.C.)
# ---------------------------------------------------------------------------

def generate_summary_chart_data(report_month: str) -> dict:
    """Return chart data for page 3 bar charts.

    Structure per param:
      { name, unit,
        fy_bars:      [{ label, value }, ...],   # last 3 FY annual actuals  (gold)
        target_bar:   { label, value },           # current FY target         (green)
        monthly_bars: [{ label, value }, ...] }   # current FY monthly actuals (blue)

    Labels use "FY24" format for past FYs and "FY27\nTarget" for the target bar.
    """
    fy = _fy_start(report_month)
    cur_fy_months = [m for m in _fy_months(fy) if m <= report_month]
    past_fys = [fy - 3, fy - 2, fy - 1]

    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT param_id, target FROM techno_target WHERE fy=?", (_fy_label(fy),))
        tgt_by_pid = dict(cur.fetchall())

        fetch_months = cur_fy_months if cur_fy_months else [report_month]
        techno_data = _fetch_techno_multi(cur, _SAIL_COMPONENT_PIDS, fetch_months)
        prod_raw = _fetch_prod_multi(
            cur, _BF_PLANTS, ["Hot Metal", "Total Crude Steel"], fetch_months
        )
        hm = prod_raw["Hot Metal"]
        cs = prod_raw["Total Crude Steel"]

        past_fy_maps = {pfy: _annual_map(cur, pfy)[0] for pfy in past_fys}

        # chart_name = display name used on the chart title (different from TE table name)
        param_specs = [
            ("Coke Rate", "Kg/THM",    _BF_HM_SECTIONS["Coke Rate"]["SAIL"]),
            ("PCI Rate",  "Kg/THM",    _BF_HM_SECTIONS["CDI Rate"]["SAIL"]),
            ("BF Productivity", "T/m³/Day", _BF_PROD_PARAMS["SAIL"]),
            ("Sp. Energy", "Gcal/TCS", _SEC_PARAMS["SAIL"]),
        ]

        def fy_label_short(yr):
            """FY label as FY24 (ending year, 2-digit)."""
            return f"FY{(yr + 1) % 100:02d}"

        result = []
        for param_name, unit, sail_pid in param_specs:
            fy_bars = []
            for pfy in past_fys:
                raw = past_fy_maps[pfy].get(sail_pid)
                fy_bars.append({
                    "label": fy_label_short(pfy),
                    "value": round(float(raw), 3) if raw is not None else None,
                })

            tgt_v = tgt_by_pid.get(sail_pid)
            # Two-line label: "FY27" on line1, "Target" on line2
            target_bar = {
                "label": f"{fy_label_short(fy)}\nTarget",
                "value": round(float(tgt_v), 3) if tgt_v is not None else None,
            }

            monthly_bars = []
            for m in cur_fy_months:
                v = _compute_sail(techno_data, hm, cs, [m]).get(sail_pid)
                monthly_bars.append({
                    "label": _mlabel(m),
                    "value": round(float(v), 3) if v is not None else None,
                })

            result.append({
                "name": param_name,
                "unit": unit,
                "fy_bars": fy_bars,
                "target_bar": target_bar,
                "monthly_bars": monthly_bars,
            })

        return {"params": result}
    finally:
        conn.close()


def compute_sail_targets(fy: str) -> dict:
    """
    Compute SAIL-level techno targets from plant-level targets using the same
    weighted-average formulas as _compute_sail().  Returns {sail_param_id: value}.

    Weights come from the annual production plan (production_plan_table) for the
    FY year-start month range (Apr-YYYY to Mar-YYYY+1).
    """
    # Derive the April-YYYY year from fy string like "2026-27"
    try:
        fy_start = int(fy.split("-")[0])
    except (ValueError, IndexError):
        return {}

    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()

    # ── Fetch annual production plan weights ────────────────────────────────
    # Sum all monthly plan values for the FY (Apr fy_start … Mar fy_start+1)
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
    hm_wt  = {}   # {plant: annual HM target}
    cs_wt  = {}   # {plant: annual CS target}
    for plant, item, val in cur.fetchall():
        if val and val > 0:
            if item == "Hot Metal":
                hm_wt[plant] = val
            else:
                cs_wt[plant] = val

    # ── Fetch plant-level targets ────────────────────────────────────────────
    all_pids = list(_SAIL_COMPONENT_PIDS)
    ph2 = ",".join("?" * len(all_pids))
    cur.execute(
        f"SELECT param_id, target FROM techno_target WHERE fy=? AND param_id IN ({ph2})",
        [fy] + all_pids,
    )
    tgt = dict(cur.fetchall())   # {param_id: target_value}
    conn.close()

    out = {}

    # ── BF params weighted by Hot Metal ─────────────────────────────────────
    for pid_map in _BF_HM_SECTIONS.values():
        sail_pid = pid_map["SAIL"]
        num = den = 0.0
        for p in _BF_PLANTS:
            v = tgt.get(pid_map[p])
            w = hm_wt.get(p)
            if v is not None and w:
                num += v * w
                den += w
        out[sail_pid] = round(num / den, 3) if den > 0 else None

    # ── BF Productivity: SAIL = ΣHM / Σ(HM/plant_BFprod) ──────────────────
    t_hm = t_denom = 0.0
    for p in _BF_PLANTS:
        hm  = hm_wt.get(p)
        bfp = tgt.get(_BF_PROD_PARAMS[p])
        if hm and bfp and bfp > 0:
            t_hm    += hm
            t_denom += hm / bfp
    out[_BF_PROD_PARAMS["SAIL"]] = round(t_hm / t_denom, 3) if t_denom > 0 else None

    # ── Shop-level TMI = HM + Scrap for each shop (before SAIL computation) ──
    _hm_map    = _SMS_SHOP_PARAMS["Hot Metal Consumption"]
    _scrap_map = _SMS_SHOP_PARAMS["Scrap Consumption"]
    _tmi_map   = _SMS_SHOP_PARAMS["TMI"]
    for shop in _hm_map:
        if shop == "SAIL":
            continue
        hm_v    = tgt.get(_hm_map[shop])
        scrap_v = tgt.get(_scrap_map[shop])
        if hm_v is not None and scrap_v is not None:
            tmi_val = round(hm_v + scrap_v, 3)
            tgt[_tmi_map[shop]] = tmi_val   # update tgt so SAIL uses correct shop TMI
            out[_tmi_map[shop]] = tmi_val   # also emit for saving

    # ── SMS params weighted by CS / shop_count ───────────────────────────────
    for shop_pid_map in _SMS_SHOP_PARAMS.values():
        sail_pid = shop_pid_map["SAIL"]
        num = den = 0.0
        for shop, pid in shop_pid_map.items():
            if shop == "SAIL":
                continue
            plant = _SMS_SHOP_PLANT[shop]
            n     = _PLANT_SHOP_CNT[plant]
            v  = tgt.get(pid)
            cs = cs_wt.get(plant)
            if v is not None and cs:
                w = cs / n
                num += v * w
                den += w
        out[sail_pid] = round(num / den, 3) if den > 0 else None

    # ── Specific Energy Consumption weighted by Crude Steel ─────────────────
    num = den = 0.0
    for p in _BF_PLANTS:
        v  = tgt.get(_SEC_PARAMS[p])
        cs = cs_wt.get(p)
        if v is not None and cs:
            num += v * cs
            den += cs
    out[_SEC_PARAMS["SAIL"]] = round(num / den, 3) if den > 0 else None

    return out


# Bar chart colours  (match screenshot palette)
_C_FY      = "#FFC000"   # gold   – past FY actuals
_C_TARGET  = "#70AD47"   # green  – current FY target
_C_MONTHLY = "#4472C4"   # blue   – current FY month(s)


def _fmt_bar_val(v: float) -> str:
    """Format a bar value for display on top of the bar."""
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
    """Render one bar chart as an inline SVG (matches screenshot style)."""
    mt   = 28   # top margin (title + gap above bars)
    mb   = 32   # bottom margin (x-axis labels; 2-line needs ~28px)
    ml   = 5    # minimal left (no Y-axis labels)
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
    rng = yhi_v - ylo_v
    pad_lo = rng * 0.66 if rng > 0 else max(abs(yhi_v) * 0.1, 0.5)
    pad_hi = rng * 0.23 if rng > 0 else max(abs(yhi_v) * 0.05, 0.2)
    ylo, yhi = ylo_v - pad_lo, yhi_v + pad_hi
    yspan = yhi - ylo

    def ys(v: float) -> float:
        return mt + ch * (1.0 - (v - ylo) / yspan)

    n_seps = sum(1 for e in bars if e.get("sep"))
    n_bars = len(bars) - n_seps
    many = n_bars > 7   # rotate x-labels when crowded
    slot_w = (cw - n_seps * SEP_W) / max(n_bars, 1)
    bar_w = max(5.0, slot_w * 0.78)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}">']

    # Chart title
    lines.append(
        f'<text x="{vw / 2:.0f}" y="13" text-anchor="middle" '
        f'font-size="8.5" font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">'
        f'{p.get("name", "")} ({p.get("unit", "")})</text>'
    )

    # Baseline (x-axis line)
    lines.append(
        f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
        f'stroke="#374151" stroke-width="0.6"/>'
    )

    x = float(ml)
    for e in bars:
        if e.get("sep"):
            x += SEP_W
            continue
        bx = x + (slot_w - bar_w) / 2
        v = e.get("value")
        color = e.get("color", "#aaa")
        if v is not None:
            bh = max(1.0, (v - ylo) / yspan * ch)
            by = ys(v)
            # Bar
            lines.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                f'height="{bh:.1f}" fill="{color}" rx="1.5"/>'
            )
            # Value label above bar (white if inside, colored if outside)
            val_str = _fmt_bar_val(v)
            vly = by - 3
            lines.append(
                f'<text x="{bx + bar_w / 2:.1f}" y="{vly:.1f}" text-anchor="middle" '
                f'font-size="7" font-weight="bold" font-family="Arial,sans-serif" '
                f'fill="{color}">{val_str}</text>'
            )

        # X-axis label (supports two-line via \n in label)
        lbl = e.get("label", "")
        lx = bx + bar_w / 2
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
            # Two-line label (target bar: "FY27" + "Target")
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
    """Return an HTML snippet (2×2 grid of SVG bar charts) for the PDF summary page."""
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

    return (
        '<div style="margin-top:6px;">'
        + rows_html
        + "</div>"
    )
