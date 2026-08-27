"""
Special Steel Plants Physical Performance (ASP / SSP / VISP) — a landscape
report page reproducing Report_format/Special Steel Production history
comprehensive.pdf.

Per plant, one row per series:
  ASP  : Crude Steel, Saleable Steel
  SSP  : Crude Steel, Saleable Steel, Stainless Steel, Carbon steel
  VISP : Saleable Steel

Columns: Capacity · Best Achieved (Actual + FY) · FY actuals 2014-15 →
(prev-FY − 1) · prev FY (APP / Actual / %Ful / %Growth vs the FY before) ·
current FY (ABP / %growth w.r.t. prev-FY actual / %growth w.r.t. prev-FY APP).
Plus the free-text notes and the annual "IPT requirement" list.

Data source: special_steel_phys_perf / _meta / _note /
special_steel_ipt_requirement (seeded by
scripts/backfill_special_steel_physical.py, maintained via
/data-entry/special-steel-physical and /data-entry/special-steel-ipt).
Stored figures are '000 T; this page displays Tonnes (× 1000).

Used by both the numbered PDF page (main.py's SS_PHYSICAL_PAGE_ID dispatch)
and the standalone web report (/api/special-steel-physical).
"""
import db

HISTORY_START_FY_YEAR = 2014  # first history column (2014-15), per the PDF

_PLANT_ORDER = ["ASP", "SSP", "VISP"]
_SERIES_LABEL = {
    "CRUDE": "Crude Steel", "SALEABLE": "Saleable Steel",
    "STAINLESS": "Stainless Steel", "CARBON": "Carbon steel",
}


def _fy_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _fy_start_year(fy_label: str) -> int:
    return int(fy_label[:4])


def _t(v_kt):
    """'000 T -> Tonnes."""
    return None if v_kt is None else v_kt * 1000.0


def _fmt(v):
    return "" if v is None else f"{v:,.0f}"


def _pct(a, b):
    if a is None or not b:
        return ""
    return f"{(a / b * 100):.0f}"


def _growth(cur, prev):
    if cur is None or prev is None or prev == 0:
        return ""
    return f"{((cur - prev) / abs(prev) * 100):.0f}"


def _ipt_item_rowspans(rows):
    """In place: first row of a run sharing `item` gets item_rowspan = run
    length, the rest get 0 (cell merged into the first)."""
    i, n = 0, len(rows)
    while i < n:
        j = i
        while j + 1 < n and rows[j + 1]["item"] == rows[i]["item"]:
            j += 1
        rows[i]["item_rowspan"] = j - i + 1
        for k in range(i + 1, j + 1):
            rows[k]["item_rowspan"] = 0
        i = j + 1


def generate_special_steel_physical(report_month: str) -> dict:
    cur_fy = db.get_fy_for_month(report_month)
    cur_start = _fy_start_year(cur_fy)
    prev_fy = _fy_label(cur_start - 1)
    prev_prev_fy = _fy_label(cur_start - 2)
    history_fys = [_fy_label(y) for y in range(HISTORY_START_FY_YEAR, cur_start - 1)]

    meta, perf = db.get_ss_phys_perf()

    sections = []
    for plant in _PLANT_ORDER:
        series_here = sorted(
            (s for (p, s) in meta if p == plant),
            key=lambda s: meta[(plant, s)]["sort_order"],
        )
        rows = []
        for series in series_here:
            m = meta[(plant, series)]

            def a(fy):
                return _t(perf.get((fy, plant, series, "actual")))

            def pl(fy):
                return _t(perf.get((fy, plant, series, "plan")))

            prev_app, prev_actual = pl(prev_fy), a(prev_fy)
            cur_abp = pl(cur_fy)
            rows.append({
                "series_label": _SERIES_LABEL.get(series, series),
                "capacity": _fmt(_t(m["capacity_kt"])),
                "best_actual": _fmt(_t(m["best_actual_kt"])),
                "best_year": m["best_year"] or "",
                "remark": m["remark"] or "",
                "history": {fy: _fmt(a(fy)) for fy in history_fys},
                "prev_app": _fmt(prev_app),
                "prev_actual": _fmt(prev_actual),
                "prev_pct_ful": _pct(prev_actual, prev_app),
                "prev_pct_growth": _growth(prev_actual, a(prev_prev_fy)),
                "cur_abp": _fmt(cur_abp),
                "cur_growth_vs_prev_actual": _growth(cur_abp, prev_actual),
                "cur_growth_vs_prev_app": _growth(cur_abp, prev_app),
            })
        if rows:
            sections.append({"plant": plant, "rows": rows})

    notes = [t for _so, t in db.get_ss_phys_notes(cur_fy)]

    ipt_rows = [
        {"item": r["item"], "from": r["from_plant"], "to": r["to_plant"],
         "plan": ("" if r["plan_kt"] is None else f"{r['plan_kt']:g}")}
        for r in db.get_ss_ipt_requirement(cur_fy)
    ]
    _ipt_item_rowspans(ipt_rows)

    return {
        "type": "special_steel_physical",
        "title": "Special Steel Plants Physical Performance",
        "unit": "Tonnes",
        "cur_fy": cur_fy,
        "prev_fy": prev_fy,
        "prev_fy_short": prev_fy[2:],
        "cur_fy_short": cur_fy[2:],
        "history_fys": history_fys,
        "sections": sections,
        "notes": notes,
        "ipt_title": f"Special Steel Plants IPT requirement {cur_fy}",
        "ipt_rows": ipt_rows,
    }
