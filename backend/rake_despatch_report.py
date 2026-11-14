"""
Rake Despatch report (Reports > Rail Logistics > Rake Despatch): the stored
Despatch Summary Report figures for a month plus the management insights
built on them. Web page only (api_rake_despatch.py /report); no MIS PDF page.

build_report(month) reads through repo.rake and hands plain dicts to the
pure functions below (headline, ranking, wagon_mix, trend, records,
run_rate, export_watch, key_points), which tests/test_rake_despatch_report.py
exercises without a database.

Monthly totals: for a month that has wagon-type rows (page 2, current FY)
the total is their sum; otherwise page 5's history. The two can disagree in
the source PDF (the upload preview lists where); page 2 is the detailed,
current one, so it wins.
"""
import calendar

from repo import rake as rrake

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
ALL = PLANTS + ["SAIL"]
HISTORY_FYS = 7
PLAN_STATUS = ((100.0, "ok"), (95.0, "watch"))  # attainment % >= -> status; below the last -> "behind"


# ── month helpers ────────────────────────────────────────────────────────────

def fy_start_year(month: str) -> int:
    y, m = int(month[:4]), int(month[5:7])
    return y if m >= 4 else y - 1


def fy_label(start: int) -> str:
    return f"{start}-{(start + 1) % 100:02d}"


def fy_months(start: int) -> list:
    return [f"{start + (i >= 9):04d}-{(i + 3) % 12 + 1:02d}" for i in range(12)]


def days_in(month: str) -> int:
    return calendar.monthrange(int(month[:4]), int(month[5:7]))[1]


def shift_year(month: str, years: int) -> str:
    return f"{int(month[:4]) + years:04d}{month[4:]}"


def mlabel(month: str) -> str:
    return f"{calendar.month_abbr[int(month[5:7])]}'{month[2:4]}"


def _pct(a, b):
    return round(100.0 * a / b, 1) if a is not None and b else None


def _change(a, b):
    return round(100.0 * (a - b) / b, 1) if a is not None and b else None


def _r(v, n=2):
    return None if v is None else round(v, n)


def status_of(attainment):
    if attainment is None:
        return "na"
    for floor, name in PLAN_STATUS:
        if attainment >= floor:
            return name
    return "behind"


# ── totals ───────────────────────────────────────────────────────────────────

def monthly_totals(type_rows: list, history_rows: list) -> dict:
    """{month: {plant: rakes, ..., "SAIL": sum}} — page-2 type sums where a
    month has them, page-5 history otherwise."""
    from_types, out = {}, {}
    for r in type_rows:
        from_types.setdefault(r["report_month"], {}).setdefault(r["plant_code"], 0)
        from_types[r["report_month"]][r["plant_code"]] += r["rakes"]
    for r in history_rows:
        out.setdefault(r["report_month"], {})[r["plant_code"]] = r["rakes"]
    for m, by_plant in from_types.items():
        out.setdefault(m, {}).update(by_plant)
    for m, by_plant in out.items():
        by_plant["SAIL"] = sum(by_plant.get(p, 0) for p in PLANTS)
    return out


def _sum(totals, months, plant):
    vals = [totals[m][plant] for m in months if m in totals and plant in totals[m]]
    return sum(vals) if vals else None


def _days(months):
    return sum(days_in(m) for m in months)


def month_plan(position: dict, plant: str, month: str):
    """Plan rakes for the month = page-1 plan avg/day x days."""
    if plant == "SAIL":
        vals = [position.get(p, {}).get("plan_avg_day") for p in PLANTS]
        per_day = sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None
    else:
        per_day = position.get(plant, {}).get("plan_avg_day")
    return (per_day, None if per_day is None else per_day * days_in(month))


# ── insights (pure) ──────────────────────────────────────────────────────────

def headline(month, totals, position, plans_by_month):
    """SAIL cards. plans_by_month: {month: {plant: plan rakes}} for every
    uploaded month of the FY (FYTD plan only when every month has one)."""
    start = fy_start_year(month)
    fytd = [m for m in fy_months(start) if m <= month]
    ly_fytd = [shift_year(m, -1) for m in fytd]
    actual = totals.get(month, {}).get("SAIL")
    per_day_plan, plan = month_plan(position, "SAIL", month)
    ly_actual = totals.get(shift_year(month, -1), {}).get("SAIL")
    fytd_actual = _sum(totals, fytd, "SAIL")
    ly_fytd_actual = _sum(totals, ly_fytd, "SAIL")
    fytd_plan = None
    if all(m in plans_by_month and plans_by_month[m].get("SAIL") is not None for m in fytd):
        fytd_plan = sum(plans_by_month[m]["SAIL"] for m in fytd)
    ly_total = _sum(totals, fy_months(start - 1), "SAIL")
    fy_days = _days(fy_months(start))
    projection = None if fytd_actual is None else fytd_actual / _days(fytd) * fy_days
    return {
        "month_actual": actual,
        "month_plan": _r(plan, 1),
        "month_attainment": _pct(actual, plan),
        "month_avg_day": _r(actual / days_in(month)) if actual is not None else None,
        "month_plan_avg_day": _r(per_day_plan),
        "month_status": status_of(_pct(actual, plan)),
        "ly_month_actual": ly_actual,
        "vs_ly_month_pct": _change(actual, ly_actual),
        "fytd_actual": fytd_actual,
        "fytd_plan": _r(fytd_plan, 1),
        "fytd_attainment": _pct(fytd_actual, fytd_plan),
        "ly_fytd_actual": ly_fytd_actual,
        "vs_ly_fytd_pct": _change(fytd_actual, ly_fytd_actual),
        "fy_projection": _r(projection, 0),
        "ly_fy_total": ly_total,
        "projection_vs_ly_pct": _change(projection, ly_total),
    }


def ranking(month, totals, position):
    """Per plant: month vs plan and FYTD vs last year, worst attainment first."""
    start = fy_start_year(month)
    fytd = [m for m in fy_months(start) if m <= month]
    ly_fytd = [shift_year(m, -1) for m in fytd]
    rows = []
    for p in ALL:
        actual = totals.get(month, {}).get(p)
        per_day_plan, plan = month_plan(position, p, month)
        att = _pct(actual, plan)
        fytd_actual, ly = _sum(totals, fytd, p), _sum(totals, ly_fytd, p)
        rows.append({
            "plant": p,
            "actual": actual,
            "plan": _r(plan, 1),
            "attainment": att,
            "status": status_of(att),
            "avg_day": _r(actual / days_in(month)) if actual is not None else None,
            "plan_avg_day": _r(per_day_plan),
            "gap_per_day": _r(actual / days_in(month) - per_day_plan)
            if actual is not None and per_day_plan is not None else None,
            "fytd_actual": fytd_actual,
            "ly_fytd_actual": ly,
            "fytd_vs_ly_pct": _change(fytd_actual, ly),
        })
    plants = sorted((r for r in rows if r["plant"] != "SAIL"),
                    key=lambda r: (r["attainment"] is None, r["attainment"] if r["attainment"] is not None else 0))
    return plants + [r for r in rows if r["plant"] == "SAIL"]


def wagon_mix(month, type_rows):
    """Share of each wagon type in FYTD rakes per plant (and SAIL), with the
    shift against a comparison period: the same months of last FY when their
    wagon-type rows exist, else H1 vs the months since (from October), else
    the earlier months of the FY vs the latest month."""
    start = fy_start_year(month)
    fytd = [m for m in fy_months(start) if m <= month]
    by = {}  # month -> plant -> type -> rakes
    for r in type_rows:
        by.setdefault(r["report_month"], {}).setdefault(r["plant_code"], {})[r["wagon_type"]] = r["rakes"]

    ly = [shift_year(m, -1) for m in fytd]
    if all(m in by for m in ly):
        basis, current, base = "last_fy", fytd, ly
        label = f"{fy_label(start)} vs same months of {fy_label(start - 1)}"
    elif len(fytd) > 6:
        basis, current, base = "h1_vs_since", fytd[6:], fytd[:6]
        label = f"{mlabel(fytd[6])}-{mlabel(fytd[-1])} vs H1 ({mlabel(fytd[0])}-{mlabel(fytd[5])})"
    elif len(fytd) > 1:
        basis, current, base = "earlier_vs_latest", fytd[-1:], fytd[:-1]
        label = f"{mlabel(fytd[-1])} vs {mlabel(fytd[0])}-{mlabel(fytd[-2])}"
    else:
        basis, current, base, label = "none", fytd, [], "no comparison period yet"

    def mix(months, plant):
        counts = {}
        for m in months:
            src = by.get(m, {})
            plants = PLANTS if plant == "SAIL" else [plant]
            for p in plants:
                for t, v in src.get(p, {}).items():
                    counts[t] = counts.get(t, 0) + v
        return counts

    out = []
    for p in ALL:
        fy_counts, cur, prev = mix(fytd, p), mix(current, p), mix(base, p)
        total, cur_total, prev_total = sum(fy_counts.values()), sum(cur.values()), sum(prev.values())
        if not total:
            continue
        types = []
        for t in sorted(fy_counts, key=lambda t: -fy_counts[t]):
            share_cur = _pct(cur.get(t, 0), cur_total)
            share_prev = _pct(prev.get(t, 0), prev_total)
            types.append({
                "type": t,
                "fytd_rakes": fy_counts[t],
                "fytd_share": _pct(fy_counts[t], total),
                "share_now": share_cur,
                "share_before": share_prev,
                "shift_pp": _r(share_cur - share_prev, 1) if share_cur is not None and share_prev is not None else None,
            })
        biggest = max((t for t in types if t["shift_pp"] is not None), key=lambda t: abs(t["shift_pp"]), default=None)
        out.append({"plant": p, "fytd_total": total, "types": types, "biggest_shift": biggest})
    return {"basis": basis, "label": label, "plants": out}


def trend(month, totals):
    """{plant: [{fy, months: [12 values or None]}]}, newest FY first, HISTORY_FYS FYs."""
    start = fy_start_year(month)
    out = {}
    for p in ALL:
        series = []
        for s in range(start, start - HISTORY_FYS, -1):
            vals = [totals.get(m, {}).get(p) if m <= month else None for m in fy_months(s)]
            series.append({"fy": fy_label(s), "months": vals,
                           "total": sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None})
        out[p] = series
    return out


def records(month, totals):
    """Per plant: this month's rank among the same calendar month of every
    stored FY, best-ever single month, best complete FY, and flags."""
    start = fy_start_year(month)
    out = []
    for p in ALL:
        same = [(shift_year(month, -k), totals.get(shift_year(month, -k), {}).get(p)) for k in range(HISTORY_FYS)]
        same = [(m, v) for m, v in same if v is not None]
        actual = totals.get(month, {}).get(p)
        rank = 1 + sum(1 for _m, v in same if actual is not None and v > actual) if actual is not None else None
        all_months = [(m, by[p]) for m, by in totals.items() if p in by and m <= month]
        best_month = max(all_months, key=lambda mv: mv[1], default=(None, None))
        fys = []
        for s in range(start - 1, start - HISTORY_FYS, -1):
            months = fy_months(s)
            if all(m in totals and p in totals[m] for m in months):
                fys.append((fy_label(s), sum(totals[m][p] for m in months)))
        best_fy = max(fys, key=lambda fv: fv[1], default=(None, None))
        out.append({
            "plant": p,
            "actual": actual,
            "same_month_rank": rank,
            "same_month_count": len(same),
            "same_month_best": max(same, key=lambda mv: mv[1], default=(None, None)),
            "same_month_worst": min(same, key=lambda mv: mv[1], default=(None, None)),
            "best_month": {"month": best_month[0], "rakes": best_month[1]},
            "is_best_month_ever": actual is not None and best_month[0] == month,
            "best_fy": {"fy": best_fy[0], "rakes": best_fy[1]},
        })
    return out


def run_rate(month, totals, position):
    """Rakes/day each plant needs for the rest of the FY to match last FY's
    total (and, alternatively, to keep to this month's plan rate), against
    its FYTD and current-month pace."""
    start = fy_start_year(month)
    months = fy_months(start)
    fytd = [m for m in months if m <= month]
    rest = [m for m in months if m > month]
    rest_days = _days(rest)
    out = []
    for p in ALL:
        fytd_actual = _sum(totals, fytd, p)
        ly_total = _sum(totals, fy_months(start - 1), p)
        per_day_plan, _plan = month_plan(position, p, month)
        pace = fytd_actual / _days(fytd) if fytd_actual is not None else None
        month_pace = totals.get(month, {}).get(p)
        month_pace = month_pace / days_in(month) if month_pace is not None else None
        need = (ly_total - fytd_actual) / rest_days if rest_days and ly_total is not None and fytd_actual is not None else None
        plan_total = fytd_actual + per_day_plan * rest_days if fytd_actual is not None and per_day_plan is not None else None
        out.append({
            "plant": p,
            "fytd_actual": fytd_actual,
            "fytd_avg_day": _r(pace),
            "month_avg_day": _r(month_pace),
            "ly_total": ly_total,
            "remaining_days": rest_days,
            "required_avg_day_ly": _r(need),
            "lift_needed_pct": _change(need, pace),
            "plan_avg_day": _r(per_day_plan),
            "fy_at_plan_rate": _r(plan_total, 0),
            "fy_at_current_pace": _r(pace * _days(months), 0) if pace is not None else None,
        })
    return out


def export_watch(export_rows):
    """Destinations with SAIL programme vs actual (and per plant), group
    totals and a grand total, flagging shortfall / excess."""
    dests, order = {}, []
    for r in export_rows:
        key = r["destination"]
        if key not in dests:
            dests[key] = {"destination": key, "group": r["dest_group"], "plants": {}}
            order.append(key)
        dests[key]["plants"][r["plant_code"]] = {"prog": r["prog"], "actual": r["actual"]}

    def row(name, group, plants):
        prog = sum(v["prog"] or 0 for v in plants.values())
        actual = sum(v["actual"] or 0 for v in plants.values())
        return {"destination": name, "group": group, "plants": plants, "prog": prog, "actual": actual,
                "fulfilment": _pct(actual, prog), "gap": actual - prog,
                "flag": "excess" if actual > prog else "shortfall" if actual < prog else "on"}

    rows = [row(k, dests[k]["group"], dests[k]["plants"]) for k in order]
    out = []
    for group, title in (("NEPAL", "TOTAL NEPAL"), ("PORT", "TOTAL PORT")):
        members = [r for r in rows if r["group"] == group]
        out += members
        out.append({**row(title, group, _sum_plants(members)), "is_total": True})
    out.append({**row("GRAND TOTAL", None, _sum_plants(rows)), "is_total": True})
    return out


def _sum_plants(rows):
    plants = {}
    for r in rows:
        for p, v in r["plants"].items():
            agg = plants.setdefault(p, {"prog": 0, "actual": 0})
            agg["prog"] += v["prog"] or 0
            agg["actual"] += v["actual"] or 0
    return plants


def key_points(month, head, rank, mix, rec, rate, exports):
    """3-6 plain sentences for a management note."""
    pts, mon = [], mlabel(month)
    if head["month_actual"] is not None:
        s = f"SAIL loaded {head['month_actual']} rakes in {mon}"
        if head["month_avg_day"] is not None and head["month_plan_avg_day"]:
            s += (f" ({head['month_avg_day']:.2f}/day against a plan of {head['month_plan_avg_day']:.2f}/day,"
                  f" {head['month_attainment']:.1f}% of plan)")
        if head["vs_ly_month_pct"] is not None:
            s += f", {abs(head['vs_ly_month_pct']):.1f}% {'above' if head['vs_ly_month_pct'] >= 0 else 'below'} {mlabel(shift_year(month, -1))}"
        pts.append(s + ".")
    if head["fytd_actual"] is not None and head["vs_ly_fytd_pct"] is not None:
        pts.append(f"FY to date SAIL has {head['fytd_actual']} rakes, "
                   f"{abs(head['vs_ly_fytd_pct']):.1f}% {'ahead of' if head['vs_ly_fytd_pct'] >= 0 else 'behind'} "
                   f"the same period last year ({head['ly_fytd_actual']}).")
    behind = [r for r in rank if r["plant"] != "SAIL" and r["status"] == "behind"]
    if behind:
        pts.append("Below 95% of plan this month: " + ", ".join(
            f"{r['plant']} ({r['attainment']:.1f}%, {r['gap_per_day']:+.2f} rakes/day)" for r in behind) + ".")
    elif any(r["attainment"] is not None for r in rank):
        pts.append("Every plant loaded at least 95% of its plan this month.")
    sail_rate = next((r for r in rate if r["plant"] == "SAIL"), None)
    if sail_rate and sail_rate["required_avg_day_ly"] is not None and sail_rate["fytd_avg_day"]:
        need, pace = sail_rate["required_avg_day_ly"], sail_rate["fytd_avg_day"]
        if need > pace:
            pts.append(f"To match last FY's {sail_rate['ly_total']} rakes SAIL needs {need:.2f} rakes/day for the rest of "
                       f"the year, {need - pace:.2f}/day above its FY-to-date pace of {pace:.2f}.")
        else:
            pts.append(f"At its FY-to-date pace of {pace:.2f} rakes/day SAIL is on course to beat last FY's "
                       f"{sail_rate['ly_total']} rakes (needs {need:.2f}/day).")
    highs = [r["plant"] for r in rec if r["plant"] != "SAIL" and r["is_best_month_ever"]]
    tops = [r["plant"] for r in rec if r["plant"] != "SAIL" and r["same_month_rank"] == 1 and r["same_month_count"] > 1
            and not r["is_best_month_ever"]]
    if highs:
        pts.append(f"Best month ever: {', '.join(highs)}.")
    if tops:
        pts.append(f"Best {calendar.month_name[int(month[5:7])]} on record: {', '.join(tops)}.")
    sail_mix = next((m for m in mix["plants"] if m["plant"] == "SAIL"), None)
    if sail_mix and sail_mix["biggest_shift"] and abs(sail_mix["biggest_shift"]["shift_pp"]) >= 2:
        b = sail_mix["biggest_shift"]
        pts.append(f"Wagon mix ({mix['label']}): {b['type']} share {'up' if b['shift_pp'] > 0 else 'down'} "
                   f"{abs(b['shift_pp']):.1f} points to {b['share_now']:.1f}%.")
    grand = next((r for r in exports if r["destination"] == "GRAND TOTAL"), None)
    if grand and (grand["prog"] or grand["actual"]):
        pts.append(f"Export: {grand['actual']:g} rakes against a programme of {grand['prog']:g}"
                   + (f" ({grand['fulfilment']:.0f}%)." if grand["fulfilment"] is not None else "."))
    return pts


# ── assembly ─────────────────────────────────────────────────────────────────

def _position_map(rows):
    out = {}
    for r in rows:
        out.setdefault(r["plant_code"], {})[r["metric"]] = r["value"]
    return out


def build_report(month: str) -> dict:
    upload = rrake.rake_despatch_upload(month)
    if upload is None:
        return {"report_month": month, "available": False,
                "months": [u["report_month"] for u in rrake.rake_despatch_months()]}
    start = fy_start_year(month)
    first = fy_months(start - HISTORY_FYS + 1)[0]
    type_rows = rrake.rake_despatch_type_rows(fy_months(start - 1)[0], month)
    totals = monthly_totals(type_rows, rrake.rake_despatch_history_rows(first, month))
    position = _position_map(rrake.rake_despatch_position_rows(month))

    plans_by_month = {}
    for m in fy_months(start):
        if m > month:
            break
        pos = position if m == month else (
            _position_map(rrake.rake_despatch_position_rows(m)) if rrake.rake_despatch_upload(m) else None)
        if pos:
            plans_by_month[m] = {p: month_plan(pos, p, m)[1] for p in ALL}

    head = headline(month, totals, position, plans_by_month)
    rank = ranking(month, totals, position)
    mix = wagon_mix(month, type_rows)
    rec = records(month, totals)
    rate = run_rate(month, totals, position)
    exports = export_watch(rrake.rake_export_despatch_rows(month))

    sail_position = {}
    for metrics in position.values():
        for k, v in metrics.items():
            if v is not None and not k.endswith("_dmt"):
                sail_position[k] = round(sail_position.get(k, 0) + v, 2)
    fy_types = {}
    for r in type_rows:
        if r["report_month"] >= fy_months(start)[0]:
            fy_types.setdefault(r["plant_code"], {}).setdefault(r["wagon_type"], {})[r["report_month"]] = r["rakes"]

    return {
        "report_month": month,
        "available": True,
        "months": [u["report_month"] for u in rrake.rake_despatch_months()],
        "as_on": upload["as_on"].isoformat() if hasattr(upload["as_on"], "isoformat") else upload["as_on"],
        "source_file": upload["source_file"],
        "uploaded_at": str(upload["created_at"]) if upload["created_at"] else None,
        "uploaded_by": upload["created_by"],
        "fy": fy_label(start),
        "fy_months": fy_months(start),
        "days_in_month": days_in(month),
        "headline": head,
        "ranking": rank,
        "wagon_mix": mix,
        "trend": trend(month, totals),
        "records": rec,
        "run_rate": rate,
        "export": exports,
        "key_points": key_points(month, head, rank, mix, rec, rate, exports),
        "source": {
            "position": {**position, "SAIL": sail_position},
            "slab": rrake.rake_slab_despatch_rows(month),
            "slab_note": upload["slab_note"],
            "types": fy_types,
            "totals": {m: totals[m] for m in sorted(totals) if m >= first},
        },
    }
