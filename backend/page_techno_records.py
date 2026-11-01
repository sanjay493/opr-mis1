"""
Best-ever techno-economic parameters per calendar month — the techno
counterpart of the Monthly Records Matrix (page_records.py), served by
/api/techno-records (frontend: /reports/highlights-records?tab=techno-records).

Two sections per plant (SAIL gets the first only):
  * Major 12 Parameters — the page-27 set (Coal to HM ... Specific Energy
    Consumption). Values come from page_techno.generate_major_techno_from_db,
    run once per financial year, so plant / SMS-shop / SAIL figures are
    exactly what page 27 prints (SAIL weighted averages included).
  * Iron Making, BF-wise — the pages 29/29.5 parameters (plus nut coke and
    sinter in burden) per blast furnace and for the BF shop total, straight
    from techno_data's monthly values.

"Best" depends on the parameter: consumption rates (coke, nut coke, fuel,
coal to HM, hot metal / TMI per t of steel, slag, energy) are best when
LOWEST; CDI, burden sinter/pellet, productivity, hot blast temperature,
O2 enrichment and scrap are best when HIGHEST. Zero/blank months are
ignored (a missing reading must never win a "lowest" record).
"""
import json
import threading
from datetime import date

import dbengine
import page_techno as pt
from repo import production as rp
from repo import techno as rt

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
    ("Nut Coke Rate", "nut_coke_rate", "kg/thm", "high"),
    ("CDI Rate", "cdi", "kg/thm", "high"),
    ("Fuel Rate", "fuel_rate", "kg/thm", "low"),
    ("Hot Blast Temp", "hot_blast_temp", "°C", "high"),
    ("BF Productivity", "bf_productivity", "t/m³/day", "high"),
    ("Oxygen Enrichment", "o2_enrichment", "%", "high"),
    ("Sinter in Burden", "sinter_in_burden", "%", "high"),
    ("Pellet in Burden", "pellet_in_burden", "%", "high"),
    ("Slag Rate", "slag_rate", "kg/thm", "low"),
]
# BF_Shop = the plant's shop-total row on pages 29/29.5 (ISP has none: one BF).
BF_UNITS = ["BF-1", "BF-2", "BF-3", "BF-4", "BF-5", "BF-6", "BF-7", "BF-8", "BF_Shop"]
BF_UNIT_LABEL = {"BF_Shop": "BF Shop"}

_cache_lock = threading.Lock()
_fy_cache: dict = {}   # fy start year -> (signature, monthly, last month, yearly) - see _major_for_fy


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
    conn = dbengine.connect()
    try:
        t = rt.months_signature_row(conn.cursor(), months)
        p = rp.hm_cs_signature_row(conn.cursor(), months)
    finally:
        conn.close()
    return tuple(t) + (p[0], round(float(p[1] or 0), 3))


def _fy_label(fy: int) -> str:
    return f"{fy}-{(fy + 1) % 100:02d}"


def _major_for_fy(fy: int, last_month: str) -> tuple:
    """({(row_label, param): {'YYYY-MM': value}}, {(row_label, param): year_value})
    for one FY, via page 27. The year value is the March cumulative, so only a
    completed FY has one."""
    months = [m for m in _fy_months(fy) if m <= last_month]
    if not months:
        return {}, {}
    sig = _signature(fy)
    with _cache_lock:
        hit = _fy_cache.get(fy)
        if hit and hit[0] == sig and hit[2] == months[-1]:
            return hit[1], hit[3]
    data = pt.generate_major_techno_from_db(months[-1])
    wanted = {p for p, _u, _b in MAJOR_PARAMS}
    out: dict = {}
    year: dict = {}
    for sec in data.get("sections", []):
        if sec.get("label") not in wanted:
            continue
        for row in sec.get("rows", []):
            vals = row.get("months") or []
            for m, v in zip(months, vals):
                f = _num(v)
                if f is not None:
                    out.setdefault((row["label"], sec["label"]), {})[m] = f
            f = _num(row.get("cum")) if months[-1].endswith("-03") else None
            if f is not None:
                year[(row["label"], sec["label"])] = f
    with _cache_lock:
        _fy_cache[fy] = (sig, out, months[-1], year)
    return out, year


def _bf_values() -> tuple:
    """({(plant, BF, param): {'YYYY-MM': value}}, {(plant, BF, param): {'YYYY-YY': value}})
    from techno_data: month values, and March till_month values as the FY figure."""
    keys = {k for _l, k, _u, _b in BF_PARAMS}
    aliases = {k: [k] + pt.KEY_ALIASES.get(k, []) for k in keys}
    conn = dbengine.connect()
    try:
        rows = rt.five_plant_unit_rows(conn.cursor(), BF_UNITS)
    finally:
        conn.close()

    def pick(d, key):
        v = next((d.get(a) for a in aliases[key] if d.get(a) is not None), None)
        if v is None and key == "fuel_rate" and d.get("coke_rate") is not None and d.get("cdi") is not None:
            v = d["coke_rate"] + (d.get("nut_coke_rate") or 0) + d["cdi"]
        return _num(v)

    out: dict = {}
    year: dict = {}
    for plant, rm, unit, tj in rows:
        js = (json.loads(tj) if isinstance(tj, str) else tj) or {}
        md = js.get("month") or {}
        td = (js.get("till_month") or {}) if rm.endswith("-03") else {}
        for label, key, _u, _b in BF_PARAMS:
            f = pick(md, key)
            if f is not None:
                out.setdefault((plant, unit, label), {})[rm] = f
            f = pick(td, key)
            if f is not None:
                year.setdefault((plant, unit, label), {})[_fy_label(int(rm[:4]) - 1)] = f
    return out, year


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


def _top(series: dict, better: str, n: int = 3) -> list:
    """Best `n` periods of a {period: value} series (lowest first when better='low')."""
    ranked = sorted(series.items(), key=lambda kv: kv[1], reverse=better == "high")
    return [{"period": p, "value": round(v, 4)} for p, v in ranked[:n]]


def _period_row(label: str, unit: str, better: str, monthly: dict, yearly: dict) -> dict:
    return {"label": label, "unit": unit, "better": better,
            "months": _top(monthly, better), "years": _top(yearly or {}, better)}


def generate_techno_records() -> dict:
    """Best / 2nd-best per calendar month (Best Techno Matrix)."""
    return _build(lambda label, unit, better, monthly, _yearly: _row(label, unit, better, monthly))


def generate_techno_best_periods() -> dict:
    """Top 3 months ever and top 3 financial years (March cumulative) per row."""
    return _build(_period_row)


def _collect():
    """(major, major_y, bf, bf_y) series - see _major_for_fy / _bf_values - or
    None when there is no techno data at all."""
    today = date.today()
    last_month = f"{today.year:04d}-{today.month:02d}"
    conn = dbengine.connect()
    try:
        first = rt.five_plant_first_month_row(conn.cursor())[0]
    finally:
        conn.close()
    if not first:
        return None
    y, m = int(first[:4]), int(first[5:7])
    first_fy = y if m >= 4 else y - 1
    last_fy = today.year if today.month >= 4 else today.year - 1

    major: dict = {}
    major_y: dict = {}
    for fy in range(first_fy, last_fy + 1):
        monthly, yearly = _major_for_fy(fy, last_month)
        for key, series in monthly.items():
            major.setdefault(key, {}).update(series)
        for key, v in yearly.items():
            major_y.setdefault(key, {})[_fy_label(fy)] = v

    # SAIL only counts from the month all five plants have techno data - before
    # that (BSL from Nov'20, RSP from Apr'21) page 27's "SAIL" is really just
    # BSP+DSP(+ISP) and would set false records.
    conn = dbengine.connect()
    try:
        firsts = rt.five_plant_first_months(conn.cursor())
    finally:
        conn.close()
    sail_from = max(f for _p, f in firsts) if len(firsts) == len(PLANTS) else "9999-99"
    for param, _u, _b in MAJOR_PARAMS:
        if ("SAIL", param) in major:
            major[("SAIL", param)] = {m: v for m, v in major[("SAIL", param)].items() if m >= sail_from}
        if ("SAIL", param) in major_y:  # FY "2021-22" counts only if its April >= sail_from
            major_y[("SAIL", param)] = {f: v for f, v in major_y[("SAIL", param)].items()
                                        if f"{f[:4]}-04" >= sail_from}

    bf, bf_y = _bf_values()
    return major, major_y, bf, bf_y


def _rank_plants(cands: dict, better: str, n: int = 3) -> list:
    """Each candidate's (plant / shop / furnace) own best figure, then the best
    `n` candidates: [{'name', 'period', 'value'}]."""
    per = [{"name": name, **_top(s, better, 1)[0]} for name, s in cands.items() if s]
    return sorted(per, key=lambda r: r["value"], reverse=better == "high")[:n]


def _plant_row(label, level, unit, better, cands_m, cands_y) -> dict:
    return {"label": label, "level": level, "unit": unit, "better": better,
            "months": _rank_plants(cands_m, better), "years": _rank_plants(cands_y, better)}


def generate_techno_best_plants() -> dict:
    """Per techno parameter, the 3 best plants (or SMS shops) by their own best
    month and best year (March cumulative). Blast-furnace parameters get two
    rows: best furnaces (plant + BF) and best plant BF shops."""
    data = _collect()
    if data is None:
        return {"rows": []}
    major, major_y, bf, bf_y = data
    bf_params = {label: key for label, key, _u, _b in BF_PARAMS}
    furnaces = [u for u in BF_UNITS if u != "BF_Shop"]

    def furnace_cands(src, label):
        return {f"{p} {u}": src.get((p, u, label)) for p in PLANTS for u in furnaces}

    def shop_cands(src, label):
        out = {}
        for p in PLANTS:
            s = src.get((p, "BF_Shop", label))
            if not s:  # a one-furnace plant (ISP) reports no shop total: its BF is the shop
                own = [src[(p, u, label)] for u in furnaces if src.get((p, u, label))]
                s = own[0] if len(own) == 1 else None
            out[p] = s
        return out

    rows = []
    for param, unit, better in MAJOR_PARAMS:
        lbls = [lbl for (lbl, p) in major if p == param and lbl != "SAIL"]
        if param in bf_params:
            rows.append(_plant_row(param, "Furnace", unit, better,
                                   furnace_cands(bf, param), furnace_cands(bf_y, param)))
        level = "BF Shop" if param in bf_params else ("Shop" if any(" " in lbl for lbl in lbls) else "Plant")
        rows.append(_plant_row(param, level, unit, better,
                               {lbl: major[(lbl, param)] for lbl in lbls},
                               {lbl: major_y.get((lbl, param)) for lbl in lbls}))
    # BF parameters page 27 doesn't carry (hot blast, O2, slag): shop from techno_data.
    major_names = {p for p, _u, _b in MAJOR_PARAMS}
    for label, _key, unit, better in BF_PARAMS:
        if label in major_names:
            continue
        rows.append(_plant_row(label, "Furnace", unit, better, furnace_cands(bf, label), furnace_cands(bf_y, label)))
        rows.append(_plant_row(label, "BF Shop", unit, better, shop_cands(bf, label), shop_cands(bf_y, label)))
    return {"rows": rows}


def _build(make_row) -> dict:
    data = _collect()
    if data is None:
        return {g: {"sections": []} for g in PLANTS + ["SAIL"]}
    major, major_y, bf, bf_y = data
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
                major_rows.append(make_row(f"{param} ({shop})" if shop else param, unit, better,
                                           major[(lbl, param)], major_y.get((lbl, param))))
        sections = [{"title": "Major 12 Parameters", "rows": major_rows}]
        if group != "SAIL":
            bf_rows = []
            for label, _key, unit, better in BF_PARAMS:
                for u in BF_UNITS:
                    series = bf.get((group, u, label))
                    if series:
                        bf_rows.append(make_row(f"{label} — {BF_UNIT_LABEL.get(u, u)}", unit, better, series,
                                                bf_y.get((group, u, label))))
            sections.append({"title": "Iron Making — BF-wise", "rows": bf_rows})
        result[group] = {"sections": sections}
    return result
