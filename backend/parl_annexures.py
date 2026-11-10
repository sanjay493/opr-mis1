"""
Parliament annexures (/reports/parliament) — the three sheets of
Report_format/work/HisParlia_Annexures.xlsx, for any period Apr..<month>
of a FY:

  production_performance  "hisparlia"  Annexure-II: Production performance of
                          SAIL plants — per plant, one row per past FY, then the
                          FY's annual APP/MoU row and the period row. Hot Metal,
                          Crude Steel, Saleable Steel: Cap., APP, MoU, Actual,
                          %Ful. (APP, MoU), %Gr., %C.U.
  production_history      "ProdHIS"    Production: HM / CS / SS / Pig Iron actual
                          by plant for past FYs, the period, its CPLY and % growth.
  techno_history          "techhistoryfinal"  Annexure-III: BF productivity, coke
                          rate and energy consumption by plant for past FYs, the
                          period, its CPLY and % improvement.

Past FYs come from parl_annexures_history.json (hard-coded from the workbook)
when they are in it, else from the DB (a full FY). The period, its CPLY and
the annual APP / MoU are always from the DB: production_monthly (actual,
abp, mou; SAIL = sum of the plants) and item_capacity; the period's
Cap., APP and MoU are the annual figures x days in the period / days in
the FY) and techno_value till_month (SAIL: the
stored SAIL figure, else the HM / CS weighted average page 27 uses).

deviations() compares the DB with the figures the JSON holds for the same
period (its history FYs, and the workbook's own current-period columns
under "reference_periods") and lists each unit whose figure differs.
"""
import calendar
import json
from functools import lru_cache
from pathlib import Path

import dbengine
from constants import ALL_PLANTS, FIVE_PLANTS
from repo import capacity as rcap
from repo import production as rp
from repo import techno as rt

HISTORY_PATH = Path(__file__).resolve().parent / "parl_annexures_history.json"

_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# report item key -> production_monthly item name
ITEM_DB = {"hm": "Hot Metal", "cs": "Total Crude Steel", "ss": "Saleable Steel", "pig_iron": "Pig Iron"}
PP_ITEMS = [("hm", "HOT METAL"), ("cs", "CRUDE STEEL"), ("ss", "SALEABLE STEEL")]
PP_PLANTS = ["SAIL"] + FIVE_PLANTS + ["ASP", "SSP", "VISL"]

PH_ITEMS = [("hm", "HOT METAL"), ("cs", "CRUDE STEEL"), ("ss", "SAL.STEEL"), ("pig_iron", "PIG IRON")]
# rows of each ProdHIS item; SAIL-5PL = the five integrated plants
PH_ROWS = {
    "hm": FIVE_PLANTS + ["SAIL-5PL", "VISL", "SAIL"],
    "cs": FIVE_PLANTS + ["SAIL-5PL", "ASP", "SSP", "VISL", "SAIL"],
    "ss": FIVE_PLANTS + ["SAIL-5PL", "ASP", "SSP", "VISL", "SAIL"],
    "pig_iron": FIVE_PLANTS + ["SAIL-5PL", "VISL", "SAIL"],
}

# key -> (title, unit, techno key, unit candidates, weight item, harmonic,
#         higher is better, decimals)
TECHNO = [
    ("bf_productivity", "Blast furnace productivity", "T/CuM/day", "bf_productivity",
     ["BF_Shop", "BF-5"], "hm", True, True, 2),
    ("coke_rate", "Coke rate", "Kg/thm", "coke_rate", ["BF_Shop", "BF-5"], "hm", False, False, 0),
    ("energy", "Energy Consumption", "Gcal/tcs", "specific_energy_consumption",
     ["General"], "cs", False, False, 2),
]
_KEY_ALIASES = {"specific_energy_consumption": ["sp_energy", "specific_energy"]}
TH_PLANTS = FIVE_PLANTS + ["SAIL"]

DEFAULT_YEARS = {"production_performance": 5, "production_history": 7, "techno_history": 6}


# ── periods ──────────────────────────────────────────────────────────────────

def fy_of(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    s = y if m >= 4 else y - 1
    return f"{s}-{(s + 1) % 100:02d}"


def fy_start(fy: str) -> int:
    return int(fy[:4])


def shift_fy(fy: str, n: int) -> str:
    s = fy_start(fy) + n
    return f"{s}-{(s + 1) % 100:02d}"


def period_months(month: str) -> list:
    """April of month's FY .. month."""
    s = fy_start(fy_of(month))
    out, y, m = [], s, 4
    while True:
        ym = f"{y}-{m:02d}"
        out.append(ym)
        if ym == month:
            return out
        m += 1
        if m == 13:
            y, m = y + 1, 1


def fy_months(fy: str) -> list:
    return period_months(f"{fy_start(fy) + 1}-03")


def cply(month: str) -> str:
    return f"{int(month[:4]) - 1}{month[4:]}"


def _days(ym: str) -> int:
    return calendar.monthrange(int(ym[:4]), int(ym[5:7]))[1]


def labels(month: str) -> dict:
    fy = fy_of(month)
    m = int(month[5:7])
    span = f"Apr-{_MON[m]}"
    return {
        "month": month,
        "fy": fy,
        "cply_fy": shift_fy(fy, -1),
        "span": span,                                         # "Apr-Jun"
        "period": f"{fy}({span}'{month[2:4]})",               # "2026-27(Apr-Jun'26)"
        "cply_period": f"{shift_fy(fy, -1)}({span}'{cply(month)[2:4]})",
        "plan": f"{fy} Plan/ MoU perf",
        "full_year": m == 3,
    }


# ── history (JSON) ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _history_cached(mtime):
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def history() -> dict:
    """parl_annexures_history.json, re-read when the file changes."""
    return _history_cached(HISTORY_PATH.stat().st_mtime)


# ── DB access ────────────────────────────────────────────────────────────────

class _Prod:
    """production_monthly values for a set of months, all plants (+ SAIL row)."""

    def __init__(self, months):
        months = sorted(set(months))
        items = list(ITEM_DB.values())
        self.v = {meas: {} for meas in ("actual", "abp", "mou")}
        for meas in self.v:
            for (m, p, i), x in rp.values(months, ALL_PLANTS + ["SAIL"], items, meas).items():
                if x is not None:
                    self.v[meas][(m, p.upper(), i.lower())] = x

    def plant(self, meas, plant, item, months):
        """Sum over months; None when no month has a value."""
        name = ITEM_DB[item].lower()
        vals = [self.v[meas].get((m, plant, name)) for m in months]
        vals = [x for x in vals if x is not None]
        return sum(vals) if vals else None

    def months_with(self, meas, plant, item, months):
        name = ITEM_DB[item].lower()
        return sum(1 for m in months if (m, plant, name) in self.v[meas])

    def group(self, meas, plants, item, months):
        vals = [self.plant(meas, p, item, months) for p in plants]
        vals = [x for x in vals if x is not None]
        return sum(vals) if vals else None

    def get(self, meas, plant, item, months):
        """A plant, 'SAIL-5PL' (five plants) or 'SAIL' (every plant, else the
        stored SAIL row)."""
        if plant == "SAIL-5PL":
            return self.group(meas, FIVE_PLANTS, item, months)
        if plant == "SAIL":
            v = self.group(meas, ALL_PLANTS, item, months)
            return v if v is not None else self.plant(meas, "SAIL", item, months)
        return self.plant(meas, plant, item, months)


class _Cap:
    """item_capacity: annual capacity in effect each month, pro rata by days."""

    def __init__(self):
        self.e = {}
        for r in rcap.list_capacity_entries():
            key = (r["plant_name"].upper(), r["item_name"].lower())
            self.e.setdefault(key, []).append((r["effective_month"], r["annual_capacity"]))
        for v in self.e.values():
            v.sort()

    def _at(self, plant, item, month):
        best = None
        for eff, cap in self.e.get((plant, ITEM_DB[item].lower()), ()):
            if eff <= month:
                best = cap
        return best

    def plant(self, plant, item, months, fy_days):
        tot, found = 0.0, False
        for m in months:
            c = self._at(plant, item, m)
            if c is not None:
                tot += c * _days(m) / fy_days
                found = True
        return tot if found else None

    def get(self, plant, item, months, fy_days):
        if plant == "SAIL":
            own = self.plant("SAIL", item, months, fy_days)
            if own is not None:
                return own
            vals = [self.plant(p, item, months, fy_days) for p in ALL_PLANTS]
            vals = [x for x in vals if x is not None]
            return sum(vals) if vals else None
        return self.plant(plant, item, months, fy_days)


def _techno_till(months):
    """{month: {(plant, unit): till_month dict}} for each month."""
    out = {}
    conn = dbengine.connect()
    try:
        cur = conn.cursor()
        for m in sorted(set(months)):
            d = {}
            for plant, unit, tj in rt.plants_month_rows(cur, m, ALL_PLANTS + ["SAIL"]):
                try:
                    d[(plant, unit)] = (json.loads(tj) or {}).get("till_month", {}) or {}
                except (TypeError, ValueError):
                    pass
            out[m] = d
    finally:
        conn.close()
    return out


def _tv(store, plant, units, key):
    for u in units:
        d = store.get((plant, u), {})
        for k in [key] + _KEY_ALIASES.get(key, []):
            v = d.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
    return None


def _techno_value(store, prod, spec, plant, month):
    """A plant's till_month value at `month`; SAIL: the stored SAIL figure,
    else the five plants' average weighted by their Apr..month HM (BF
    params; harmonic for productivity) or Crude Steel (energy)."""
    _, _, _, key, units, weight, harmonic, _, _ = spec
    if plant != "SAIL":
        return _tv(store, plant, units, key)
    v = _tv(store, "SAIL", units, key)
    if v is not None:
        return v
    months = period_months(month)
    num = den = 0.0
    for p in FIVE_PLANTS:
        w = prod.plant("actual", p, weight, months)
        x = _tv(store, p, units, key)
        if not w or w <= 0 or x is None:
            continue
        if harmonic:
            if x <= 0:
                continue
            num += w
            den += w / x
        else:
            num += x * w
            den += w
    return num / den if den > 0 else None


# ── helpers ──────────────────────────────────────────────────────────────────

def _pct(a, b):
    return a / b * 100 if a is not None and b else None


def _gr(a, b):
    return (a / b - 1) * 100 if a is not None and b else None


def _past_fys(fy, years):
    return [shift_fy(fy, -k) for k in range(years, 0, -1)]


def _pp_block(prod, cap, plant, item, months, fy_days, prev_actual):
    v = {
        "cap": cap.get(plant, item, months, fy_days),
        "app": prod.get("abp", plant, item, months),
        "mou": prod.get("mou", plant, item, months),
        "actual": prod.get("actual", plant, item, months),
    }
    v["ful_app"] = _pct(v["actual"], v["app"])
    v["ful_mou"] = _pct(v["actual"], v["mou"])
    v["gr"] = _gr(v["actual"], prev_actual)
    v["cu"] = _pct(v["actual"], v["cap"])
    return v


def _period_block(prod, plant, item, months, annual, share, prev_actual):
    """The period row: Cap., APP and MoU are the annual figures pro rata by
    days (annual x days in the period / days in the FY); Actual is the
    period's own."""
    v = {f: None if annual[f] is None else annual[f] * share for f in ("cap", "app", "mou")}
    v["actual"] = prod.get("actual", plant, item, months)
    v["ful_app"] = _pct(v["actual"], v["app"])
    v["ful_mou"] = _pct(v["actual"], v["mou"])
    v["gr"] = _gr(v["actual"], prev_actual)
    v["cu"] = _pct(v["actual"], v["cap"])
    return v


def _fy_days(fy):
    return sum(_days(m) for m in fy_months(fy))


# ── report 1: production performance (hisparlia, Annexure-II) ────────────────

def production_performance(month: str, years: int = 5) -> dict:
    L = labels(month)
    fy = L["fy"]
    hist = history()["production_performance"]
    jplants = hist["plants"]
    past = _past_fys(fy, years)
    db_fys = [f for f in past if not all(f in jplants.get(p, {}) for p in PP_PLANTS)]
    months = period_months(month)
    cply_months = [cply(m) for m in months]
    need = set(fy_months(fy)) | set(cply_months)
    for f in db_fys:
        need |= set(fy_months(f)) | set(fy_months(shift_fy(f, -1)))
    prod = _Prod(need)
    cap = _Cap()
    fdays = _fy_days(fy)
    pdays = sum(_days(m) for m in months)

    def fy_actual(plant, item, f):
        rec = jplants.get(plant, {}).get(f)
        if rec is not None:
            return rec[item]["actual"]
        return prod.get("actual", plant, item, fy_months(f))

    plants = []
    for plant in PP_PLANTS:
        rows = []
        for f in past:
            rec = jplants.get(plant, {}).get(f)
            if rec is not None:
                rows.append({"kind": "fy", "label": f, "source": "history",
                             "values": {k: dict(rec[k]) for k, _ in PP_ITEMS}})
            else:
                fm = fy_months(f)
                rows.append({"kind": "fy", "label": f, "source": "db", "values": {
                    k: _pp_block(prod, cap, plant, k, fm, _fy_days(f), fy_actual(plant, k, shift_fy(f, -1)))
                    for k, _ in PP_ITEMS}})
        fm = fy_months(fy)
        annual = {k: {"cap": cap.get(plant, k, fm, fdays), "app": prod.get("abp", plant, k, fm),
                      "mou": prod.get("mou", plant, k, fm)} for k, _ in PP_ITEMS}
        rows.append({"kind": "plan", "label": L["plan"], "source": "db", "values": annual})
        rows.append({"kind": "period", "label": L["period"], "source": "db", "values": {
            k: _period_block(prod, plant, k, months, annual[k], pdays / fdays,
                             prod.get("actual", plant, k, cply_months))
            for k, _ in PP_ITEMS}})
        plants.append({"plant": plant, "rows": rows})
    first = past[0] if past else fy
    return {
        "report": "production_performance",
        "labels": {**L, "title": "PRODUCTION PERFORMANCE OF SAIL PLANTS",
                   "subtitle": f"{first}  to  {fy}", "annexure": "ANNEXURE-II",
                   "unit": "UNIT : '000 T", "org": "Operations Directorate"},
        "items": [{"key": k, "label": t} for k, t in PP_ITEMS],
        "plants": plants,
        "note": hist.get("note", ""),
    }


# ── report 2: production history (ProdHIS) ───────────────────────────────────

def production_history(month: str, years: int = 7) -> dict:
    L = labels(month)
    fy = L["fy"]
    jh = history()["production_history"]
    past = _past_fys(fy, years)
    months = period_months(month)
    cply_months = [cply(m) for m in months]
    need = set(months) | set(cply_months)
    for f in past:
        if not all(f in jh.get(i, {}).get(p, {}) for i in PH_ROWS for p in PH_ROWS[i]):
            need |= set(fy_months(f))
    prod = _Prod(need)
    items = []
    for key, title in PH_ITEMS:
        rows = []
        for plant in PH_ROWS[key]:
            jp = jh.get(key, {}).get(plant, {})
            fys = []
            for f in past:
                if f in jp:
                    fys.append(jp[f])
                else:
                    fys.append(prod.get("actual", plant, key, fy_months(f)))
            cy = prod.get("actual", plant, key, months)
            cp = prod.get("actual", plant, key, cply_months)
            rows.append({"plant": plant, "fys": fys, "cy": cy, "cply": cp, "gr": _gr(cy, cp),
                         "total": plant in ("SAIL", "SAIL-5PL")})
        items.append({"key": key, "label": title, "rows": rows})
    return {
        "report": "production_history",
        "labels": {**L, "title": "PRODUCTION", "unit": "Unit:'000T",
                   "org": "OPERATIONS DIRECTORATE", "company": "STEEL AUTHORITY OF INDIA LIMITED"},
        "fys": past,
        "items": items,
    }


# ── report 3: techno history (techhistoryfinal, Annexure-III) ────────────────

def techno_history(month: str, years: int = 6) -> dict:
    L = labels(month)
    fy = L["fy"]
    jh = history()["techno_history"]
    past = _past_fys(fy, years)
    cm = cply(month)
    db_marches = [f"{fy_start(f) + 1}-03" for f in past
                  if not all(f in jh.get(s[0], {}).get(p, {}) for s in TECHNO for p in TH_PLANTS)]
    till = _techno_till([month, cm] + db_marches)
    pm = set(period_months(month)) | set(period_months(cm))
    for m in db_marches:
        pm |= set(period_months(m))
    prod = _Prod(pm)
    sections = []
    for spec in TECHNO:
        key, title, unit, _, _, _, _, higher, dp = spec
        rows = []
        for plant in TH_PLANTS:
            jp = jh.get(key, {}).get(plant, {})
            fys = []
            for f in past:
                if f in jp:
                    fys.append(jp[f])
                else:
                    mar = f"{fy_start(f) + 1}-03"
                    fys.append(_techno_value(till.get(mar, {}), prod, spec, plant, mar))
            cy = _techno_value(till.get(month, {}), prod, spec, plant, month)
            cp = _techno_value(till.get(cm, {}), prod, spec, plant, cm)
            if cy is None or not cp:
                imp = None
            else:
                imp = (cy / cp - 1) * 100 if higher else (cp - cy) / cp * 100
            rows.append({"plant": plant, "fys": fys, "cy": cy, "cply": cp, "imp": imp,
                         "total": plant == "SAIL"})
        sections.append({"key": key, "label": title, "unit": f"Unit: {unit}", "decimals": dp, "rows": rows})
    return {
        "report": "techno_history",
        "labels": {**L, "title": "MAJOR TECHNO ECONOMIC PARAMETERS", "annexure": "ANNEXURE-III"},
        "fys": past,
        "sections": sections,
    }


BUILDERS = {
    "production_performance": production_performance,
    "production_history": production_history,
    "techno_history": techno_history,
}


# ── deviations: JSON (workbook) figures vs the DB ────────────────────────────

def _dp(x):
    """Decimals the workbook figure carries (0..3)."""
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return min(len(s.split(".")[1]) if "." in s else 0, 3)


def _differs(ref, db, tol):
    """Differs by at least `tol`, and by more than the workbook figure's own
    rounding (an integer 1579 against the DB's 1578.904 is no deviation)."""
    if ref is None or db is None:
        return False
    return abs(db - ref) >= max(tol, 0.5 * 10 ** -_dp(ref))


# production: 0.01 '000 T (10 t), below which the DB's 3-decimal monthly
# figures and the workbook's unrounded sums only differ in rounding;
# techno: half a unit of the figure's shown decimals.
_PROD_TOL = 0.01


def _dev(out, plant, item, col, period, measure, ref, db, tol=_PROD_TOL):
    """col: the report column ('<FY>' | 'period' | 'cy' | 'cply'), so the
    preview can mark the cell."""
    if _differs(ref, db, tol):
        out.append({"plant": plant, "item_key": item, "item": _ITEM_LABEL[item], "col": col,
                    "period": period, "measure": measure, "workbook": round(ref, 6),
                    "db": round(db, 6), "diff": round(db - ref, 6)})


_ITEM_LABEL = {"hm": "Hot Metal", "cs": "Crude Steel", "ss": "Saleable Steel", "pig_iron": "Pig Iron",
               "bf_productivity": "BF Productivity", "coke_rate": "Coke Rate", "energy": "Energy Consumption"}


def _union_months(fys, fn=None):
    out = set()
    for f in fys:
        out |= set(fn(f) if fn else fy_months(f))
    return out


def deviations(report: str, data: dict) -> list:
    """Every unit whose figure in the JSON (a history FY shown in the report,
    or the workbook's current-period column for this period / its CPLY)
    differs from the DB's. A production history FY is checked only when
    the DB holds all 12 months of it."""
    L = data["labels"]
    month, fy = L["month"], L["fy"]
    refs = history().get("reference_periods", {})
    out = []
    if report == "production_performance":
        past = [r["label"] for r in data["plants"][0]["rows"] if r["kind"] == "fy"]
        prod = _Prod(_union_months(past))
        for blk in data["plants"]:
            plant = blk["plant"]
            ref = refs.get(month, {}).get(report, {}).get(plant)
            for r in blk["rows"]:
                if r["kind"] == "fy" and r["source"] == "history":
                    fm = fy_months(r["label"])
                    for k, _ in PP_ITEMS:
                        if _complete(prod, plant, k, fm):
                            _dev(out, plant, k, r["label"], r["label"], "Actual",
                                 r["values"][k]["actual"], prod.get("actual", plant, k, fm))
                elif r["kind"] == "period" and ref:
                    for k, _ in PP_ITEMS:
                        # Actual only: the workbook's period APP / MoU are
                        # monthly sums, this report's are pro rata by days
                        _dev(out, plant, k, "period", L["period"], "Actual",
                             ref[k].get("actual"), r["values"][k].get("actual"))
    elif report == "production_history":
        fys = data["fys"]
        prod = _Prod(_union_months(fys))
        jh = history()["production_history"]
        for it in data["items"]:
            k = it["key"]
            for r in it["rows"]:
                plant = r["plant"]
                for f, v in zip(fys, r["fys"]):
                    if f in jh.get(k, {}).get(plant, {}) and _complete(prod, plant, k, fy_months(f)):
                        _dev(out, plant, k, f, f, "Actual", v, prod.get("actual", plant, k, fy_months(f)))
                for which, m, lbl in (("cy", month, f"{L['span']} {fy}"),
                                      ("cply", cply(month), f"{L['span']} {L['cply_fy']}")):
                    ref = refs.get(m, {}).get(report, {}).get(k, {}).get(plant)
                    _dev(out, plant, k, which, lbl, "Actual", ref, r[which])
    elif report == "techno_history":
        fys = data["fys"]
        jh = history()["techno_history"]
        marches = [f"{fy_start(f) + 1}-03" for f in fys]
        till = _techno_till(marches)
        prod = _Prod(_union_months(marches, period_months))
        specs = {s[0]: s for s in TECHNO}
        for sec in data["sections"]:
            k = sec["key"]
            tol = 0.5 * 10 ** -sec["decimals"]
            for r in sec["rows"]:
                plant = r["plant"]
                for f, mar, v in zip(fys, marches, r["fys"]):
                    if f in jh.get(k, {}).get(plant, {}):
                        _dev(out, plant, k, f, f, "Value", v,
                             _techno_value(till.get(mar, {}), prod, specs[k], plant, mar), tol)
                for which, m, lbl in (("cy", month, f"{L['span']} {fy}"),
                                      ("cply", cply(month), f"{L['span']} {L['cply_fy']}")):
                    ref = refs.get(m, {}).get(report, {}).get(k, {}).get(plant)
                    _dev(out, plant, k, which, lbl, "Value", ref, r[which], tol)
    return out


def _complete(prod, plant, item, months):
    """The DB holds an actual for every month (SAIL / SAIL-5PL: for some
    plant in every month)."""
    if plant in ("SAIL", "SAIL-5PL"):
        plants = FIVE_PLANTS if plant == "SAIL-5PL" else ALL_PLANTS
        return all(any(prod.months_with("actual", p, item, [m]) for p in plants) for m in months)
    return prod.months_with("actual", plant, item, months) == len(months)


def build(report: str, month: str, years=None) -> dict:
    """The report's JSON payload, with its deviations."""
    years = DEFAULT_YEARS[report] if years is None else years
    data = BUILDERS[report](month, years)
    data["years"] = years
    data["deviations"] = deviations(report, data)
    return data
