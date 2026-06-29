"""
Production by Process page.
Shows BOF / EAF / CC / CS per plant for:
  - monthly: current month vs CPLY month
  - ytd:     Apr-to-month vs CPLY Apr-to-month
Unit: Tonnes  (DB stores '000 T — multiply × 1000)
"""
import math
import sqlite3
import db

_FIVE = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_ALL8 = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL"]
_ROWS = ["BSP", "DSP", "RSP", "BSL", "ISP", "5 Plants", "ASP", "SSP", "VISL", "SAIL"]

_CS = "Total Crude Steel"

# CC item names per plant (same approach as page17_concast._ACT)
_CC: dict = {
    "BSP":  ["SMS-2", "SMS-3"],
    "DSP":  "SMS Total Caster",
    "RSP":  ["SMS-1 CCM-1", "SMS-2 CCM-1&2", "SMS-2 CCM-3", "SMS-2 CCM-4"],
    "BSL":  ["SMS-1 CCM-1", "SMS-2 CCM-1&2"],
    "ISP":  ["SMS CCM-1&2", "SMS CCM-3"],
    "ASP":  "Total Caster",   # returns 0 if absent from DB
    "SSP":  _CS,              # SSP is 100 % CC
    "VISL": _CS,
}

_EAF_PLANTS = {"ASP", "SSP"}   # all other plants use BOF


# ── helpers ──────────────────────────────────────────────────────────────────

def _T(v) -> str:
    return "" if v is None else str(int(math.floor(v * 1000 + 0.5)))


def _pct(a, b) -> str:
    if a is None or b is None or b == 0:
        return ""
    return f"{int(math.floor(a / b * 100 + 0.5))}%"


def _fetch(cur, plant: str, item, month: str):
    if isinstance(item, list):
        tot, ok = 0.0, False
        for it in item:
            cur.execute(
                "SELECT month_actual FROM production_table "
                "WHERE plant_name=? AND item_name=? AND report_month=?",
                (plant, it, month),
            )
            r = cur.fetchone()
            if r and r[0] is not None:
                tot += r[0]; ok = True
        return tot if ok else None
    cur.execute(
        "SELECT month_actual FROM production_table "
        "WHERE plant_name=? AND item_name=? AND report_month=?",
        (plant, item, month),
    )
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None


def _ytd(cur, plant: str, item, months: list):
    tot, ok = 0.0, False
    for m in months:
        v = _fetch(cur, plant, item, m)
        if v is not None:
            tot += v; ok = True
    return tot if ok else None


def _agg(cur, plants: list, item_fn, month: str):
    """Sum item_fn(plant) across plants for one month."""
    tot, ok = 0.0, False
    for p in plants:
        spec = item_fn(p)
        if spec is None:
            continue
        v = _fetch(cur, p, spec, month)
        if v is not None:
            tot += v; ok = True
    return tot if ok else None


def _ytd_agg(cur, plants: list, item_fn, months: list):
    tot, ok = 0.0, False
    for p in plants:
        spec = item_fn(p)
        if spec is None:
            continue
        for m in months:
            v = _fetch(cur, p, spec, m)
            if v is not None:
                tot += v; ok = True
    return tot if ok else None


# ── row builder ───────────────────────────────────────────────────────────────

def _row(plant: str, bof, eaf, cc, cs) -> dict:
    is_eaf = plant in _EAF_PLANTS
    is_sail = plant == "SAIL"
    # BOF % of CS: EAF plants show "0%" (not blank) when they have CS
    if is_eaf:
        bof_pct = "0%" if (cs is not None and cs > 0) else ""
    else:
        bof_pct = _pct(bof, cs)

    return {
        "plant":   plant,
        "bold":    plant in ("5 Plants", "SAIL"),
        "bof":     "" if is_eaf else _T(bof),
        "eaf":     _T(eaf) if (is_eaf or is_sail) else "",
        "cc":      _T(cc),
        "cs":      _T(cs),
        "bof_pct": bof_pct,
        "cc_pct":  _pct(cc, cs),
    }


# ── per-plant data fetchers ───────────────────────────────────────────────────

def _plant_month(cur, plant: str, month: str):
    cs = _fetch(cur, plant, _CS, month)
    cc = _fetch(cur, plant, _CC.get(plant), month) if _CC.get(plant) else None
    if plant in _EAF_PLANTS:
        return None, cs, cc, cs   # bof, eaf, cc, cs
    return cs, None, cc, cs


def _plant_ytd(cur, plant: str, months: list):
    cs = _ytd(cur, plant, _CS, months)
    cc = _ytd(cur, plant, _CC.get(plant), months) if _CC.get(plant) else None
    if plant in _EAF_PLANTS:
        return None, cs, cc, cs
    return cs, None, cc, cs


def _agg_month(cur, plants: list, month: str):
    bof_p = [p for p in plants if p not in _EAF_PLANTS]
    eaf_p = [p for p in plants if p in _EAF_PLANTS]
    cs  = _agg(cur, plants,  lambda p: _CS,        month)
    bof = _agg(cur, bof_p,   lambda p: _CS,        month)
    eaf = _agg(cur, eaf_p,   lambda p: _CS,        month) if eaf_p else None
    cc  = _agg(cur, plants,  lambda p: _CC.get(p), month)
    return bof, eaf, cc, cs


def _agg_ytd(cur, plants: list, months: list):
    bof_p = [p for p in plants if p not in _EAF_PLANTS]
    eaf_p = [p for p in plants if p in _EAF_PLANTS]
    cs  = _ytd_agg(cur, plants,  lambda p: _CS,        months)
    bof = _ytd_agg(cur, bof_p,   lambda p: _CS,        months)
    eaf = _ytd_agg(cur, eaf_p,   lambda p: _CS,        months) if eaf_p else None
    cc  = _ytd_agg(cur, plants,  lambda p: _CC.get(p), months)
    return bof, eaf, cc, cs


# ── public API ────────────────────────────────────────────────────────────────

def generate_prod_by_process(report_month: str) -> dict:
    prev_month      = db.get_cply_month(report_month)
    ytd_months      = db.get_ytd_months(report_month)
    prev_ytd_months = db.get_ytd_months(prev_month)

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    m_cur, m_prev, y_cur, y_prev = [], [], [], []

    try:
        for plant in _ROWS:
            is_agg = plant in ("5 Plants", "SAIL")
            plants = _FIVE if plant == "5 Plants" else (_ALL8 if plant == "SAIL" else None)

            if is_agg:
                bof,  eaf,  cc,  cs  = _agg_month(cur, plants, report_month)
                bofp, eafp, ccp, csp = _agg_month(cur, plants, prev_month)
                yb,   ye,   yc,  ycs = _agg_ytd(cur, plants, ytd_months)
                ybp,  yep,  ycp, ycsp = _agg_ytd(cur, plants, prev_ytd_months)
            else:
                bof,  eaf,  cc,  cs  = _plant_month(cur, plant, report_month)
                bofp, eafp, ccp, csp = _plant_month(cur, plant, prev_month)
                yb,   ye,   yc,  ycs = _plant_ytd(cur, plant, ytd_months)
                ybp,  yep,  ycp, ycsp = _plant_ytd(cur, plant, prev_ytd_months)

            m_cur.append(_row(plant, bof,  eaf,  cc,  cs))
            m_prev.append(_row(plant, bofp, eafp, ccp, csp))
            y_cur.append(_row(plant, yb,   ye,   yc,  ycs))
            y_prev.append(_row(plant, ybp,  yep,  ycp, ycsp))
    finally:
        conn.close()

    return {
        "monthly":      m_cur,
        "monthly_prev": m_prev,
        "ytd":          y_cur,
        "ytd_prev":     y_prev,
    }
