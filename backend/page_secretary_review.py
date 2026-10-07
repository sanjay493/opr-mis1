"""Secretary Review deck ("SECRETARY REVIEW Operations Inputs <Mon><YY>.pptx").

build_context(month) gathers the month's numbers; render_pptx(month, texts)
fills secretary_review_templates/secretary_review.pptx (see
scripts/prep_secretary_review_template.py for how the template was made).
Production figures come from page4._p4_row_values so they match the MIS
report; techno figures from techno_period.build_period_report."""

import calendar

import board_note_common as bnc
import db
import page4
import page_techno as pt
import techno_period as tp
from constants import FIVE_PLANTS
from secretary_review_layout import KPIS, PLANTS, SCOPES, period_labels

ITEMS = [("HM", "Hot Metal"), ("CS", "Total Crude Steel"), ("FS", "Finished Steel"), ("SS", "Saleable Steel")]
_P4 = {i["db_item"]: i for i in page4.PAGE4_ITEMS}


def latest_month():
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT MAX(report_month) FROM production_table "
                    "WHERE item_name='Hot Metal' AND month_actual IS NOT NULL")
        row = cur.fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Production
# --------------------------------------------------------------------------

def _prod_row(cur, month, plant, db_item, members=None):
    """members: an explicit plant list summed as one row (the SSPs row)."""
    cfg = _P4[db_item]
    sail_set = members if members is not None else cfg["sail_set"]
    p = "SAIL" if members is not None else plant
    raw, cap = page4._p4_row_values(cur, month, p, db_item, False, cfg.get("five_plants", []),
                                    sail_set, has_capacity=True, raw=True)
    return {"cap": cap, "app_m": raw[1], "act_m": raw[2], "cply_m": raw[5], "gr_m": raw[6],
            "cu_m": raw[7], "app_ytd": raw[8], "act_ytd": raw[9], "cply_ytd": raw[12],
            "gr_ytd": raw[13], "cu_ytd": raw[14]}


def _plus(a, b):
    return None if a is None or b is None else a + b


def _with_conversion(cur, month, row):
    """SAIL Finished Steel plus Conversion (slide 5's Total row). CU% scales
    with the actual, since capacity is unchanged."""
    cm, cc, cy, cyc = page4._p4_conv_actuals(cur, month)
    r = dict(row)
    r["act_m"], r["cply_m"] = _plus(row["act_m"], cm), _plus(row["cply_m"], cc)
    r["act_ytd"], r["cply_ytd"] = _plus(row["act_ytd"], cy), _plus(row["cply_ytd"], cyc)
    r["gr_m"] = page4._raw_gr(r["act_m"], r["cply_m"])
    r["gr_ytd"] = page4._raw_gr(r["act_ytd"], r["cply_ytd"])
    for cu, act in (("cu_m", "act_m"), ("cu_ytd", "act_ytd")):
        r[cu] = (row[cu] * r[act] / row[act]) if (row[cu] is not None and r[act] is not None and row[act]) else None
    return r


def build_production(cur, month):
    out = {}
    for key, db_item in ITEMS:
        rows = {s: _prod_row(cur, month, s, db_item) for s in SCOPES}
        ssps = [p for p in _P4[db_item]["sail_set"] if p not in FIVE_PLANTS]
        rows["SSPs"] = _prod_row(cur, month, "SSPs", db_item, members=ssps) if ssps else None
        if key == "FS":
            rows["TOTAL_CONV"] = _with_conversion(cur, month, rows["SAIL"])
        out[key] = rows
    return out


# --------------------------------------------------------------------------
# Techno
# --------------------------------------------------------------------------

def _num(d):
    s = (d or {}).get("display") or ""
    s = s.replace(",", "").strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _targets(labels):
    """{scope: {param: target}}; a scope whose targets can't be read (e.g. an
    FY with no techno_plan_fy rows yet) gets {} and shows as 'no FY target'."""
    out = {}
    fetch = {"SAIL": lambda: pt.compute_sail_targets(labels["fy_label"])}
    fetch.update({p: (lambda p=p: pt._get_plant_techno_plan_targets(p, labels["month"])) for p in PLANTS})
    for scope, fn in fetch.items():
        try:
            raw = fn() or {}
        except Exception:
            raw = {}
        out[scope] = bnc.fuel_rate_fallback({k[1]: v for k, v in raw.items()})
    return out


def _round_fmt(v, fmt):
    if v is None:
        return None
    return round(v) if fmt == "0" else round(v, 2)


def build_techno(labels, warnings):
    fy_start, n, month = labels["fy_start"], labels["n"], labels["month"]
    months = bnc.fy_months(fy_start)[:n]
    periods = [{"label": "FYm2", "months": bnc.fy_months(fy_start - 2)},
               {"label": "FYm1", "months": bnc.fy_months(fy_start - 1)}]
    periods += [{"label": m, "months": [m]} for m in months]
    periods += [{"label": "ytd:" + m, "months": months[: i + 1]} for i, m in enumerate(months)]
    res = tp.build_period_report(SCOPES, [name for _, name, _ in KPIS], periods)
    display = {p["name"]: p["display_name"] for p in tp._build_major_params()}
    sections = {s["parameter"]: {r["plant"]: r["values"] for r in s["rows"]} for s in res["sections"]}
    targets = _targets(labels)

    def vals(name, scope):
        return sections.get(display.get(name, name), {}).get(scope, {})

    co2_name = dict((k, nm) for k, nm, _ in KPIS)["co2"]
    sail_co2 = vals(co2_name, "SAIL")
    co2_month = next((m for m in reversed(months) if _num(sail_co2.get(m)) is not None), month)
    if co2_month != month:
        warnings.append(f"Sp. CO₂ for {labels['mon']} not loaded yet – using "
                        f"{calendar.month_abbr[int(co2_month[5:])]}")

    out = {}
    for scope in SCOPES:
        out[scope] = {}
        for key, name, fmt in KPIS:
            v = vals(name, scope)
            used = co2_month if key == "co2" else month
            upto = months[: months.index(used) + 1]
            entry = {
                "fy_m2": _num(v.get("FYm2")), "fy_m1": _num(v.get("FYm1")),
                "target": _round_fmt((targets.get(scope) or {}).get(name), fmt),
                "month": _num(v.get(used)), "ytd": _num(v.get("ytd:" + used)),
                "trend": [(calendar.month_abbr[int(m[5:])], _num(v.get(m))) for m in upto],
                "month_used": used,
            }
            if entry["month"] is None:
                warnings.append(f"{scope} {name}: no value for {calendar.month_abbr[int(used[5:])]}")
            if entry["target"] is None:
                warnings.append(f"{scope} {name}: no FY target")
            out[scope][key] = entry
    return out


def build_context(month):
    labels = period_labels(month)
    warnings = []
    conn = db.connect()
    try:
        production = build_production(conn.cursor(), month)
    finally:
        conn.close()
    if production["HM"]["SAIL"]["act_m"] is None:
        warnings.append(f"No production actuals for {labels['mon']}")
    techno = build_techno(labels, warnings)
    return {"labels": labels, "production": production, "techno": techno, "warnings": warnings}
