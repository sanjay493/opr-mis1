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

# Sections in IRON_MAKING that show furnace-level DSP data only.
# Other plants (RSP BF-1, RSP BF-5 etc.) must never appear here.
_DSP_FURNACE_SECTIONS = frozenset({
    "BF Coke Rate", "Nut Coke Rate", "BF Productivity",
    "Si in HM", "S in HM", "Blast Temperature",
})

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
    30: ("BOF",         "MONTH-WISE TECHNO-ECONOMIC PARAMETERS", "BOF SHOP"),
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
    falls back to AVG(actual) for params with no cumulative stored."""
    months = _fy_months(fy)
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT param_id, report_month, cum_actual FROM techno_monthly
        WHERE report_month IN ({ph}) AND cum_actual IS NOT NULL
        ORDER BY report_month
    """, months)
    out = {}
    for pid, _, c in cur.fetchall():   # later months overwrite earlier ones
        out[pid] = c
    for pid, avg in _avg_map(cur, months).items():
        out.setdefault(pid, avg)
    return out


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

        fy2_map = _annual_map(cur, fy - 2)
        fy1_map = _annual_map(cur, fy - 1)
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

        # Override SAIL rows with properly weighted averages
        if group == "MAJOR":
            _inject_sail_techno(
                cur, mon_map, cum_map, ccum_map, cply_map, fy2_map, fy1_map,
                ytd, cply_ytd, cply_month,
                _fy_months(fy - 2), _fy_months(fy - 1),
            )

        sections, by_sec = [], {}
        for pid, section, row_label, unit in master:
            if group == "MILL_DSP" and section == "Section Mill":
                continue
            if group == "IRON_MAKING" and section == "Sinter %":
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
