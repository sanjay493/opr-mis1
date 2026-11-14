"""
"Rail Logistics – Rake Despatch" — three portrait MIS PDF pages, right after
Capital Repair (pages 36-40), right before Details of Rakes Detention.
A selection of the web report (Reports > Rail Logistics > Rake Despatch):

  40.1 Summary              — headline cards, slag/coke/sinter/slab by plant,
                              key points, plan attainment (no Status column;
                              the attainment cell is tinted instead), run-rate
  40.2 Performance history  — records & seasonality, seven-year monthly trend,
                              export programme vs actual
  40.3 Wagon types          — wagon-type mix per plant, FY rakes by wagon type

Every figure comes from rake_despatch_report.build_report(month); this module
only regroups it for the page layout, so the PDF and the web report always
agree. No upload for the month -> each page prints its title and a
"not uploaded" line.
"""
import rake_despatch_report as rdr
from rake_despatch_report import ALL, PLANTS, mlabel, status_of

PAGE_IDS = {40.1: "summary", 40.2: "history", 40.3: "wagon"}

_TITLES = {
    "summary": "Rail Logistics – Rake Despatch: Summary",
    "history": "Rail Logistics – Rake Despatch: Performance History",
    "wagon": "Rail Logistics – Rake Despatch: Wagon Types",
}
_COMMODITIES = ("slag", "coke", "sinter")
_FIELDS = ("plan_avg_day", "avg_day", "cumm")


def fmt(v, nd=0) -> str:
    """Table cell text: "–" for a missing value."""
    return "–" if v is None else f"{v:.{nd}f}"


def month_labels(fy_months: list) -> list:
    return [mlabel(m)[:3] for m in fy_months]


def commodity_rows(position: dict, slab: list, month: str) -> list:
    """Plan/day, avg/day and cumulative per plant + SAIL for slag, coke and
    sinter (page-1 position), and slab: rakes despatched from the plant this
    month (the slab rows summed), avg/day = those rakes / days in the month.
    The source has no slab plan, so its plan/day is always None."""
    sent = {}
    for r in slab:
        sent[r["from_plant_code"]] = sent.get(r["from_plant_code"], 0) + r["rakes"]
    if sent:
        sent["SAIL"] = sum(sent.values())
    days = rdr.days_in(month)
    rows = []
    for p in ALL:
        row = {"plant": p, **{c: {f: position.get(p, {}).get(f"{c}_{f}") for f in _FIELDS} for c in _COMMODITIES}}
        cumm = sent.get(p)
        row["slab"] = {"plan_avg_day": None, "avg_day": None if cumm is None else round(cumm / days, 2), "cumm": cumm}
        rows.append(row)
    return rows


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


def _block(plant: str, by_type: dict, fy_months: list) -> dict:
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
    return {"plant": plant, "rows": rows, "total": {"months": totals, "fytd": sum(present) if present else None}}


def wagon_type_blocks(types: dict, fy_months: list) -> list:
    """One block per plant with wagon-type rows, then SAIL (types summed)."""
    blocks, sail = [], {}
    for p in PLANTS:
        if not types.get(p):
            continue
        blocks.append(_block(p, types[p], fy_months))
        for t, by_month in types[p].items():
            for m, v in by_month.items():
                sail.setdefault(t, {})[m] = sail.get(t, {}).get(m, 0) + v
    if blocks:
        blocks.append(_block("SAIL", sail, fy_months))
    return blocks


def _with(value, label) -> str:
    return "–" if value is None else f"{value:g} ({label})"


def records_rows(records: list) -> list:
    """Records & seasonality with the (month, rakes) pairs written out as text."""
    out = []
    for r in records:
        best, worst = r["same_month_best"], r["same_month_worst"]
        out.append({
            "plant": r["plant"],
            "actual": r["actual"],
            "rank": f"{r['same_month_rank']} of {r['same_month_count']}" if r["same_month_rank"] else "–",
            "same_best": _with(best[1], best[0] and mlabel(best[0])),
            "same_worst": _with(worst[1], worst[0] and mlabel(worst[0])),
            "best_month": _with(r["best_month"]["rakes"], r["best_month"]["month"] and mlabel(r["best_month"]["month"])),
            "best_fy": _with(r["best_fy"]["rakes"], r["best_fy"]["fy"]),
            "is_best_month_ever": r["is_best_month_ever"],
        })
    return out


def trend_rows(trend: dict) -> list:
    """Plant x FY rows (newest FY first), flagging each plant's first row."""
    return [{"plant": p, "fy": s["fy"], "months": s["months"], "total": s["total"], "first_of_plant": i == 0}
            for p in ALL for i, s in enumerate(trend.get(p, []))]


def export_rows(export: list) -> list:
    """The export table, or [] when the month has no programme or actual at all."""
    return export if any(r.get("prog") or r.get("actual") for r in export) else []


def generate_rail_logistics(month: str, part: str) -> dict:
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
            commodity=commodity_rows(src["position"], src["slab"], month),
            key_points=d["key_points"],
            ranking=[{**r, "tint": status_of(r["attainment"])} for r in d["ranking"]],
            run_rate=d["run_rate"],
        )
    elif part == "history":
        page.update(
            records=records_rows(d["records"]),
            trend=trend_rows(d["trend"]),
            month_labels=month_labels(d["fy_months"]),
            export=export_rows(d["export"]),
            export_plants=PLANTS,
        )
    else:
        page.update(
            mix=mix_rows(d["wagon_mix"]),
            blocks=wagon_type_blocks(src["types"], d["fy_months"]),
            month_labels=month_labels(d["fy_months"]),
        )
    return page
