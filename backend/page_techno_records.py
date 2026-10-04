"""
Best-ever techno-economic parameters per calendar month — the techno
counterpart of the Monthly Records Matrix (page_records.py), served by
/api/techno-records (frontend: /reports/highlights-records?tab=techno-records).

Two sections per plant (SAIL gets the first only):
  * Major 12 Parameters — the page-27 set (Coal to HM ... Specific Energy
    Consumption). Values come from page_techno.generate_major_techno_from_db,
    run once per financial year, so plant / SMS-shop / SAIL figures are
    exactly what page 27 prints (SAIL weighted averages included).
  * Iron Making, BF-wise — the pages 29/29.5 parameters per blast furnace,
    straight from techno_data's monthly values.

"Best" depends on the parameter: consumption rates (coke, nut coke, fuel,
coal to HM, hot metal / TMI per t of steel, slag, energy) are best when
LOWEST; CDI, burden sinter/pellet, productivity, hot blast temperature,
O2 enrichment and scrap are best when HIGHEST. Zero/blank months are
ignored (a missing reading must never win a "lowest" record).
"""
import json
import threading
from datetime import date

import db
import page_techno as pt

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]

# (page-27 section label, unit, better)
MAJOR_PARAMS = [
    ("Coal to Hot Metal Ratio", "t/thm", "low"),
    ("Coke Rate", "kg/thm", "low"),
    ("Nut Coke Rate", "kg/thm", "high"),
    ("CDI Rate", "kg/thm", "high"),
    ("Fuel Rate", "kg/thm", "low"),
    ("Sinter in Burden", "%", "high"),
    ("Pellet in Burden", "%", "high"),
    ("BF Productivity", "t/m³/day", "high"),
    ("Hot Metal Consumption", "kg/tcs", "low"),
    ("Scrap Consumption", "kg/tcs", "high"),
    ("TMI", "kg/tcs", "low"),
    ("Specific Energy Consumption", "Gcal/tcs", "low"),
]

# (label, techno_data key, unit, better) - pages 29 / 29.5, in page order.
BF_PARAMS = [
    ("Coke Rate", "coke_rate", "kg/thm", "low"),
    ("CDI Rate", "cdi", "kg/thm", "high"),
    ("Fuel Rate", "fuel_rate", "kg/thm", "low"),
    ("Hot Blast Temp", "hot_blast_temp", "°C", "high"),
    ("BF Productivity", "bf_productivity", "t/m³/day", "high"),
    ("Oxygen Enrichment", "o2_enrichment", "%", "high"),
    ("Pellet in Burden", "pellet_in_burden", "%", "high"),
    ("Slag Rate", "slag_rate", "kg/thm", "low"),
]
BF_UNITS = ["BF-1", "BF-2", "BF-3", "BF-4", "BF-5", "BF-6", "BF-7", "BF-8"]

_cache_lock = threading.Lock()
_fy_cache: dict = {}   # fy start year -> (signature, {(row_label, param): {month: value}})


def _num(v):
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _fy_months(fy: int) -> list:
    return [f"{fy}-{m:02d}" for m in range(4, 13)] + [f"{fy + 1}-{m:02d}" for m in range(1, 4)]


def _signature(fy: int):
    """Changes whenever techno or production data for that FY is added,
    re-uploaded or edited - so a cached FY is recomputed only then."""
    months = _fy_months(fy)
    ph = ",".join("?" * len(months))
    conn = db.connect()
    try:
        t = conn.execute(f"SELECT COUNT(*), MAX(id), MAX(created_at) FROM techno_data WHERE report_month IN ({ph})",
                         months).fetchone()
        p = conn.execute(f"SELECT COUNT(*), SUM(month_actual) FROM production_table "
                         f"WHERE report_month IN ({ph}) AND item_name IN ('Hot Metal','Total Crude Steel')",
                         months).fetchone()
    finally:
        conn.close()
    return tuple(t) + (p[0], round(float(p[1] or 0), 3))


def _major_for_fy(fy: int, last_month: str) -> dict:
    """{(row_label, param): {'YYYY-MM': value}} for one FY, via page 27."""
    months = [m for m in _fy_months(fy) if m <= last_month]
    if not months:
        return {}
    sig = _signature(fy)
    with _cache_lock:
        hit = _fy_cache.get(fy)
        if hit and hit[0] == sig and hit[2] == months[-1]:
            return hit[1]
    data = pt.generate_major_techno_from_db(months[-1])
    wanted = {p for p, _u, _b in MAJOR_PARAMS}
    out: dict = {}
    for sec in data.get("sections", []):
        if sec.get("label") not in wanted:
            continue
        for row in sec.get("rows", []):
            vals = row.get("months") or []
            for m, v in zip(months, vals):
                f = _num(v)
                if f is not None:
                    out.setdefault((row["label"], sec["label"]), {})[m] = f
    with _cache_lock:
        _fy_cache[fy] = (sig, out, months[-1])
    return out


def _bf_values() -> dict:
    """{(plant, BF, param): {'YYYY-MM': value}} from techno_data month values."""
    keys = {k for _l, k, _u, _b in BF_PARAMS}
    aliases = {k: [k] + pt.KEY_ALIASES.get(k, []) for k in keys}
    ph = ",".join("?" * len(BF_UNITS))
    conn = db.connect()
    try:
        rows = conn.execute(f"SELECT plant, report_month, unit, techno_json FROM techno_data "
                            f"WHERE plant IN ('BSP','DSP','RSP','BSL','ISP') AND unit IN ({ph})",
                            BF_UNITS).fetchall()
    finally:
        conn.close()
    out: dict = {}
    for plant, rm, unit, tj in rows:
        md = (json.loads(tj) if isinstance(tj, str) else tj or {}).get("month") or {}
        for label, key, _u, _b in BF_PARAMS:
            v = next((md.get(a) for a in aliases[key] if md.get(a) is not None), None)
            if v is None and key == "fuel_rate" and md.get("coke_rate") is not None and md.get("cdi") is not None:
                v = md["coke_rate"] + (md.get("nut_coke_rate") or 0) + md["cdi"]
            f = _num(v)
            if f is not None:
                out.setdefault((plant, unit, label), {})[rm] = f
    return out


def _row(label: str, unit: str, better: str, series: dict) -> dict:
    """Top two per calendar month (by `better`) + the all-time best."""
    by_cal: dict = {}
    for m, v in series.items():
        by_cal.setdefault(int(m[5:7]), []).append({"month": m, "value": round(v, 4)})
    rev = better == "high"
    cal = {c: sorted(lst, key=lambda r: r["value"], reverse=rev)[:2] for c, lst in by_cal.items()}
    tops = [lst[0] for lst in cal.values()]
    best = (max if rev else min)(tops, key=lambda r: r["value"]) if tops else None
    return {"label": label, "unit": unit, "better": better, "cal_months": cal,
            "best": best, "years": len({m[:4] for m in series})}


def generate_techno_records() -> dict:
    today = date.today()
    last_month = f"{today.year:04d}-{today.month:02d}"
    conn = db.connect()
    try:
        first = conn.execute("SELECT MIN(report_month) FROM techno_data WHERE plant IN "
                             "('BSP','DSP','RSP','BSL','ISP')").fetchone()[0]
    finally:
        conn.close()
    if not first:
        return {g: {"sections": []} for g in PLANTS + ["SAIL"]}
    y, m = int(first[:4]), int(first[5:7])
    first_fy = y if m >= 4 else y - 1
    last_fy = today.year if today.month >= 4 else today.year - 1

    major: dict = {}
    for fy in range(first_fy, last_fy + 1):
        for key, series in _major_for_fy(fy, last_month).items():
            major.setdefault(key, {}).update(series)

    # SAIL only counts from the month all five plants have techno data - before
    # that (BSL from Nov'20, RSP from Apr'21) page 27's "SAIL" is really just
    # BSP+DSP(+ISP) and would set false records.
    conn = db.connect()
    try:
        firsts = conn.execute("SELECT plant, MIN(report_month) FROM techno_data WHERE plant IN "
                              "('BSP','DSP','RSP','BSL','ISP') GROUP BY plant").fetchall()
    finally:
        conn.close()
    sail_from = max(f for _p, f in firsts) if len(firsts) == len(PLANTS) else "9999-99"
    for param, _u, _b in MAJOR_PARAMS:
        if ("SAIL", param) in major:
            major[("SAIL", param)] = {m: v for m, v in major[("SAIL", param)].items() if m >= sail_from}

    bf = _bf_values()
    result = {}
    for group in PLANTS + ["SAIL"]:
        major_rows = []
        for param, unit, better in MAJOR_PARAMS:
            # Plant rows are labelled "BSP" (BF/energy params) or "BSP SMS-2"
            # (per-shop SMS params); SAIL's is "SAIL".
            labels = sorted({lbl for (lbl, p) in major if p == param
                             and (lbl == group or lbl.startswith(group + " "))})
            for lbl in labels:
                shop = lbl[len(group):].strip()
                major_rows.append(_row(f"{param} ({shop})" if shop else param, unit, better, major[(lbl, param)]))
        sections = [{"title": "Major 12 Parameters", "rows": major_rows}]
        if group != "SAIL":
            bf_rows = []
            for label, _key, unit, better in BF_PARAMS:
                for u in BF_UNITS:
                    series = bf.get((group, u, label))
                    if series:
                        bf_rows.append(_row(f"{label} — {u}", unit, better, series))
            sections.append({"title": "Iron Making — BF-wise", "rows": bf_rows})
        result[group] = {"sections": sections}
    return result
