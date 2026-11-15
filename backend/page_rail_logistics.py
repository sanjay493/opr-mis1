"""
"Rail Logistics" — four portrait MIS PDF pages, right after Capital Repair
(pages 36-40), right before Details of Rakes Detention.

  40.05 Monthly rail loading — SAIL's rail loading by commodity, month by
                              month (rail_loading.py; its own table, not the
                              Despatch Summary Report)

then a selection of the web report (Reports > Rail Logistics > Rake Despatch),
the steel rakes despatched from the plants:

  40.1 Summary              — headline cards, key points, plan attainment (no
                              Status column; the attainment cell is tinted
                              instead), run-rate
  40.2 Performance history  — seven-year monthly trend, export programme vs
                              actual (Nepal / Port / Total)
  40.3 Wagon types          — wagon-type mix per plant, FY rakes by wagon type

Slag, coke and sinter are on 40.05 only; nothing is printed twice.

Every 40.1-40.3 figure comes from rake_despatch_report.build_report(month); this module
only regroups it for the page layout, so the PDF and the web report always
agree. No upload for the month -> each page prints its title and a
"not uploaded" line.
"""
import rail_loading
import rake_despatch_report as rdr
from rake_despatch_report import ALL, PLANTS, mlabel, status_of

PAGE_IDS = {40.05: "loading", 40.1: "summary", 40.2: "history", 40.3: "wagon"}   # print order

_TITLES = {
    "loading": "Rail Logistics – Monthly Rail Loading",
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


def trend_rows(trend: dict) -> list:
    """Plant x FY rows (newest FY first), flagging each plant's first row."""
    return [{"plant": p, "fy": s["fy"], "months": s["months"], "total": s["total"], "first_of_plant": i == 0}
            for p in ALL for i, s in enumerate(trend.get(p, []))]


_EXPORT_LABELS = {"TOTAL NEPAL": "Nepal", "TOTAL PORT": "Port", "GRAND TOTAL": "Total"}


def export_rows(export: list) -> list:
    """The export table cut down to Nepal, Port and Total (the report's group
    totals; the single destinations are left to the web report), or [] when
    the month has no programme or actual at all."""
    if not any(r.get("prog") or r.get("actual") for r in export):
        return []
    return [{**r, "destination": _EXPORT_LABELS[r["destination"]], "is_total": r["destination"] == "GRAND TOTAL"}
            for r in export if r.get("is_total") and r["destination"] in _EXPORT_LABELS]


def generate_rail_logistics(month: str, part: str) -> dict:
    if part == "loading":
        return {"type": "rail_logistics_loading", "title": _TITLES[part], **rail_loading.build_page(month)}
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
