"""
"Rail Logistics" — five portrait MIS PDF pages, right after Capital Repair
(pages 36-40), right before Details of Rakes Detention.

  40.05 Monthly rail loading — SAIL's rail loading by commodity, month by
                              month (rail_loading.py; its own table, not the
                              Despatch Summary Report)
  40.07 Iron ore from mines — iron ore rakes loaded at the mines, EGOM /
                              CGOM / Total: key points, seven-year monthly
                              trend, wagon-type mix, FY rakes by wagon type
                              (iron_ore_rakes.py; the mines' rake record)

then a selection of the web report (Reports > Rail Logistics > Rake Despatch),
the steel rakes despatched from the plants:

  40.1 Summary              — headline cards, key points, plan attainment (no
                              Status column; the attainment cell is tinted
                              instead), run-rate
  40.2 Performance history  — seven-year monthly trend
  40.3 Wagon types          — wagon-type mix per plant, FY rakes by wagon type

Slag, coke and sinter are on 40.05 only; nothing is printed twice.

Every 40.1-40.3 figure comes from rake_despatch_report.build_report(month); this module
only regroups it for the page layout, so the PDF and the web report always
agree. No upload for the month -> each page prints its title and a
"not uploaded" line.
"""
import iron_ore_rakes
import rail_loading
import rake_despatch_report as rdr
from rake_despatch_report import ALL, PLANTS, days_in, fy_months, mlabel, status_of

PAGE_IDS = {40.05: "loading", 40.07: "mines", 40.1: "summary", 40.2: "history", 40.3: "wagon"}   # print order

_TITLES = {
    "loading": "Rail Logistics – Monthly Rail Loading",
    "mines": "Rail Logistics – Iron Ore Rake Loading from Mines",
    "summary": "Rail Logistics – Steel Rake Despatch from Plant: Summary",
    "history": "Rail Logistics – Steel Rake Despatch from Plant: Performance History",
    "wagon": "Rail Logistics – Steel Rake Despatch from Plant: Wagon Types",
}


def fmt(v, nd=0) -> str:
    """Table cell text: "–" for a missing value."""
    return "–" if v is None else f"{v:.{nd}f}"


def month_labels(fy_months: list) -> list:
    return [mlabel(m)[:3] for m in fy_months]


def mix_rows(wagon_mix: dict) -> dict:
    """Per plant + SAIL: FYTD rakes and the mix as (type, share %, shift pp),
    types with rakes only; a shift under 0.1 point prints nothing, and the
    plant's biggest shift is flagged — as the web report's mix table."""
    rows = []
    for e in wagon_mix["plants"]:
        big = (e.get("biggest_shift") or {}).get("type")
        rows.append({"plant": e["plant"], "fytd_total": e["fytd_total"], "types": [
            {"type": t["type"], "share": t["fytd_share"],
             "shift": t["shift_pp"] if t["shift_pp"] is not None and abs(t["shift_pp"]) >= 0.1 else None,
             "biggest": t["type"] == big}
            for t in e["types"] if t["fytd_rakes"] > 0]})
    return {"label": wagon_mix["label"], "rows": rows}


def per_day(months: list, values: list):
    """(values / days of their month, the total / days of the months present),
    for the 12 months of one FY; None where a month has no figure."""
    pairs = [(m, v) for m, v in zip(months, values) if v is not None]
    daily = [None if v is None else round(v / days_in(m), 2) for m, v in zip(months, values)]
    return daily, (round(sum(v for _m, v in pairs) / sum(days_in(m) for m, _v in pairs), 2) if pairs else None)


def _block(plant: str, by_type: dict, fy_months: list, rakes_per_day: bool = False) -> dict:
    rows = []
    for t, by_month in by_type.items():
        months = [by_month.get(m) for m in fy_months]
        present = [v for v in months if v is not None]
        rows.append({"type": t, "months": months, "fytd": sum(present) if present else None})
    rows.sort(key=lambda r: -(r["fytd"] or 0))
    totals = []
    for i in range(len(fy_months)):
        vals = [r["months"][i] for r in rows if r["months"][i] is not None]
        totals.append(sum(vals) if vals else None)
    present = [v for v in totals if v is not None]
    block = {"plant": plant, "rows": rows, "total": {"months": totals, "fytd": sum(present) if present else None}}
    if rakes_per_day:
        for r in rows + [block["total"]]:
            r["months"], r["fytd"] = per_day(fy_months, r["months"])
    return block


def wagon_type_blocks(types: dict, fy_months: list, groups=PLANTS, total="SAIL", rakes_per_day: bool = False) -> list:
    """One block per plant with wagon-type rows, then SAIL (types summed);
    `groups` / `total` name the blocks when they are not the plants.
    rakes_per_day: the months and FYTD in rakes per day, not rakes."""
    blocks, sail = [], {}
    for p in groups:
        if not types.get(p):
            continue
        blocks.append(_block(p, types[p], fy_months, rakes_per_day))
        for t, by_month in types[p].items():
            for m, v in by_month.items():
                sail.setdefault(t, {})[m] = sail.get(t, {}).get(m, 0) + v
    if blocks:
        blocks.append(_block(total, sail, fy_months, rakes_per_day))
    return blocks


def trend_rows(trend: dict, rows=ALL) -> list:
    """Plant x FY rows (newest FY first), flagging each plant's first row.
    The months and "total" are rakes per day (the total over the days of the
    months that FY has figures for)."""
    out = []
    for p in rows:
        for i, s in enumerate(trend.get(p, [])):
            daily, total = per_day(fy_months(int(s["fy"][:4])), s["months"])
            out.append({"plant": p, "fy": s["fy"], "months": daily, "total": total, "first_of_plant": i == 0})
    return out


def mines_page(month: str) -> dict:
    """Page 40.07's data: iron_ore_rakes.build_report regrouped with the
    same helpers as the plant pages, so both read alike."""
    r = iron_ore_rakes.build_report(month)
    if not r["available"]:
        return {"available": False, "subtitle": mlabel(month),
                "placeholder": f"Iron ore rake file not uploaded for FY {r['fy']}"}
    return {"available": True, "subtitle": f"{mlabel(month)} · FY {r['fy']}", "placeholder": None,
            "month_label": r["month_label"], "fy": r["fy"], "month_labels": month_labels(r["fy_months"]),
            "key_points": r["key_points"], "coverage_note": r["coverage_note"],
            "trend": trend_rows(r["trend"], iron_ore_rakes.ALL),
            "mix": mix_rows(r["wagon_mix"]),
            "blocks": wagon_type_blocks(r["types"], r["fy_months"], iron_ore_rakes.GROUPS, iron_ore_rakes.TOTAL, rakes_per_day=True)}


def generate_rail_logistics(month: str, part: str) -> dict:
    if part == "loading":
        return {"type": "rail_logistics_loading", "title": _TITLES[part], **rail_loading.build_page(month)}
    if part == "mines":
        return {"type": "rail_logistics_mines", "title": _TITLES[part], **mines_page(month)}
    d = rdr.build_report(month)
    page = {"type": f"rail_logistics_{part}", "title": _TITLES[part], "available": bool(d.get("available"))}
    if not page["available"]:
        return {**page, "subtitle": mlabel(month),
                "placeholder": f"Despatch Summary Report for {mlabel(month)} not uploaded"}
    page.update(subtitle=f"{mlabel(month)} · FY {d['fy']}", placeholder=None, month_label=mlabel(month), fy=d["fy"])
    src = d["source"]
    if part == "summary":
        page.update(
            headline=d["headline"],
            key_points=d["key_points"],
            ranking=[{**r, "tint": status_of(r["attainment"])} for r in d["ranking"]],
            run_rate=d["run_rate"],
        )
    elif part == "history":
        page.update(
            trend=trend_rows(d["trend"]),
            month_labels=month_labels(d["fy_months"]),
        )
    else:
        page.update(
            mix=mix_rows(d["wagon_mix"]),
            blocks=wagon_type_blocks(src["types"], d["fy_months"]),
            month_labels=month_labels(d["fy_months"]),
        )
    return page
