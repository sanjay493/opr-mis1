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

        sections, by_sec = [], {}
        for pid, section, row_label, unit in master:
            if group == "MILL_DSP" and section == "Section Mill":
                continue
            if group == "IRON_MAKING" and section in ("Productivity (Working vol.)", "Sinter %"):
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
