"""
Page 17 – Concast Production Performance.
Two tables on one page: Monthly and YTD (Apr-to-month).
Unit displayed: Tonnes  (DB stores '000 T → multiply × 1000, round to integer)
"""
import math
import sqlite3
import db

# ── per-plant DB item specs ──────────────────────────────────────────────────
# actuals table
_ACT = {
    "BSP":  ["SMS-2", "SMS-3"],
    "DSP":  "Total Caster",
    "RSP":  ["SMS-1 CCM-1", "SMS-2 CCM-1&2", "SMS-2 CCM-3", "SMS-2 CCM-4"],
    "BSL":  ["SMS-1 CCM-1", "SMS-2 CCM-1&2"],
    "ISP":  ["SMS CCM-1&2", "SMS CCM-3"],
    "ASP":  "Total Crude Steel",   # ASP is fully CC; no separate Concast in actuals
    "SSP":  "Total Crude Steel",   # SSP is fully CC
    "VISL": "Total Crude Steel",
}

# plan table  (BSP plan stored as sub-items; sum them to get SMS-2/SMS-3 totals)
_PLAN = {
    "BSP":  ["SMS-2 BLOOM", "SMS-2 SLAB", "SMS-3 BILLET105", "SMS-3 BILLET150", "SMS-3 BLOOM(CV1&2)"],
    "DSP":  "SMS Total Caster",
    "RSP":  ["SMS-1 CCM-1", "SMS-2 CCM-1&2", "SMS-2 CCM-3", "SMS-2 CCM-4"],
    "BSL":  ["SMS-1 CCM-1", "SMS-2 CCM-1&2"],
    "ISP":  ["SMS CCM-1&2", "SMS CCM-3"],
    "ASP":  "Concast",
    "SSP":  "Total Crude Steel",
    "VISL": "Concast",
}

_FIVE  = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_ALL8  = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL"]
_ROWS  = ["BSP", "DSP", "RSP", "BSL", "ISP", "5 Plants", "ASP", "SSP", "VISL", "SAIL"]


# ── DB helpers ───────────────────────────────────────────────────────────────

def _fetch(cur, tbl, plant, item, month):
    table = "production_table" if tbl == "act" else "production_plan_table"
    if isinstance(item, list):
        total, found = 0.0, False
        for it in item:
            cur.execute(
                f"SELECT month_actual FROM {table} WHERE plant_name=? AND item_name=? AND report_month=?",
                (plant, it, month),
            )
            r = cur.fetchone()
            if r and r[0] is not None:
                total += r[0]; found = True
        return total if found else None
    cur.execute(
        f"SELECT month_actual FROM {table} WHERE plant_name=? AND item_name=? AND report_month=?",
        (plant, item, month),
    )
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None


def _sum_plants(cur, tbl, plants, spec_dict, month):
    total, found = 0.0, False
    for p in plants:
        spec = spec_dict.get(p)
        if spec is None:
            continue
        v = _fetch(cur, tbl, p, spec, month)
        if v is not None:
            total += v; found = True
    return total if found else None


def _ytd_sum(cur, tbl, plant, spec, months):
    total, found = 0.0, False
    for m in months:
        v = _fetch(cur, tbl, plant, spec, m)
        if v is not None:
            total += v; found = True
    return total if found else None


def _ytd_agg(cur, tbl, plants, spec_dict, months):
    total, found = 0.0, False
    for p in plants:
        spec = spec_dict.get(p)
        if spec is None:
            continue
        for m in months:
            v = _fetch(cur, tbl, p, spec, m)
            if v is not None:
                total += v; found = True
    return total if found else None


# ── formatting ───────────────────────────────────────────────────────────────

def _T(v):
    """'000T → Tonnes integer string."""
    if v is None:
        return ""
    return str(int(math.floor(v * 1000 + 0.5)))


def _pct(a, p):
    if a is None or p is None or p == 0:
        return ""
    return str(int(math.floor(float(a) / float(p) * 100 + 0.5)))


def _gr(curr, prev):
    if curr is None or prev is None or prev == 0:
        return ""
    return str(int(math.floor((float(curr) - float(prev)) / abs(float(prev)) * 100 + 0.5)))


# ── main public function ─────────────────────────────────────────────────────

def generate_concast_data(report_month: str) -> dict:
    ytd_months      = db.get_ytd_months(report_month)
    all_fy          = db.get_fy_months(report_month)
    prev_month      = db.get_cply_month(report_month)
    prev_ytd_months = db.get_ytd_months(prev_month)

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()

    monthly_rows, ytd_rows = [], []

    try:
        for plant in _ROWS:
            is_agg = plant in ("5 Plants", "SAIL")
            plants = _FIVE if plant == "5 Plants" else (_ALL8 if plant == "SAIL" else [plant])
            bold   = plant in ("5 Plants", "SAIL")

            if is_agg:
                # Annual plan
                ann = sum(
                    v for m in all_fy
                    if (v := _sum_plants(cur, "plan", plants, _PLAN, m)) is not None
                )
                ann = ann if ann else None

                m_plan = _sum_plants(cur, "plan", plants, _PLAN, report_month)
                m_act  = _sum_plants(cur, "act",  plants, _ACT,  report_month)
                cply   = _sum_plants(cur, "act",  plants, _ACT,  prev_month)

                ytd_plan = _ytd_agg(cur, "plan", plants, _PLAN, ytd_months)
                ytd_act  = _ytd_agg(cur, "act",  plants, _ACT,  ytd_months)
                ytd_cply = _ytd_agg(cur, "act",  plants, _ACT,  prev_ytd_months)
            else:
                act_spec  = _ACT.get(plant)
                plan_spec = _PLAN.get(plant)

                # Annual plan: sum all FY months
                ann_t, ann_f = 0.0, False
                for m in all_fy:
                    v = _fetch(cur, "plan", plant, plan_spec, m)
                    if v is not None:
                        ann_t += v; ann_f = True
                ann = ann_t if ann_f else None

                m_plan = _fetch(cur, "plan", plant, plan_spec, report_month)
                m_act  = _fetch(cur, "act",  plant, act_spec,  report_month)
                cply   = _fetch(cur, "act",  plant, act_spec,  prev_month)

                ytd_plan = _ytd_sum(cur, "plan", plant, plan_spec, ytd_months)
                ytd_act  = _ytd_sum(cur, "act",  plant, act_spec,  ytd_months)
                ytd_cply = _ytd_sum(cur, "act",  plant, act_spec,  prev_ytd_months)

            monthly_rows.append({
                "plant":    plant,
                "bold":     bold,
                "ann_plan": _T(ann),
                "m_plan":   _T(m_plan),
                "m_act":    _T(m_act),
                "m_pct":    _pct(m_act, m_plan),
                "cply_act": _T(cply),
                "m_growth": _gr(m_act, cply),
            })
            ytd_rows.append({
                "plant":      plant,
                "bold":       bold,
                "ann_plan":   _T(ann),
                "ytd_plan":   _T(ytd_plan),
                "ytd_act":    _T(ytd_act),
                "ytd_pct":    _pct(ytd_act, ytd_plan),
                "ytd_cply":   _T(ytd_cply),
                "ytd_growth": _gr(ytd_act, ytd_cply),
            })
    finally:
        conn.close()

    return {"monthly": monthly_rows, "ytd": ytd_rows}
