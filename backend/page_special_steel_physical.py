"""
Special Steel Plants Physical Performance (ASP / SSP / VISP) — a genuine
A4-landscape report page (spliced in by pdf.py's _LANDSCAPE_TYPES handling),
based on Report_format/Special Steel Production history comprehensive.pdf.

Per plant, one row per series:
  ASP  : Crude Steel, Saleable Steel
  SSP  : Crude Steel, Saleable Steel, Stainless Steel, Carbon steel
  VISP : Saleable Steel

Columns: Capacity · Best Achieved (Actual + FY) · FY actuals 14-15 →
(prev-FY − 1) · prev FY actual (annual) · cur-FY ABP (annual plan) ·
cur-FY YTD block Apr-<report month> (APP · Actual · %FF · CPLY · %Growth) ·
Remarks. Years are shown yy-yy.

Data sources:
  - History / Capacity / Best-Achieved / ABP / notes / IPT list: the editable
    tables special_steel_phys_perf / _meta / _note / special_steel_ipt_requirement
    (seeded by scripts/backfill_special_steel_physical.py, maintained via
    /data-entry/special-steel-physical and /data-entry/special-steel-ipt).
  - prev-FY annual actual and the cur-FY YTD block (Actual / CPLY / APP):
    production_table / production_plan_table, summed over the relevant months
    (plant VISP <- VISL). SSP "Stainless Steel" has no item of its own — it is
    Saleable Steel − Carbon Steel Production (per direct instruction), used
    only when both components have data for the period (a full 12 months for
    the prev-FY annual actual); otherwise the stored figure stands.
Stored figures are '000 T; this page displays Tonnes (× 1000).
"""
import db

HISTORY_START_FY_YEAR = 2014  # first history column (14-15), per the PDF

_PLANT_ORDER = ["ASP", "SSP", "VISP"]
_SERIES_LABEL = {
    "CRUDE": "Crude Steel", "SALEABLE": "Saleable Steel",
    "STAINLESS": "Stainless Steel", "CARBON": "Carbon steel",
}
# plant code used in production_table / production_plan_table
_PLANT_DB = {"ASP": "ASP", "SSP": "SSP", "VISP": "VISL"}
# production_table item_name for each series (Stainless has no clean item)
_SERIES_ITEM = {
    "CRUDE": "Total Crude Steel", "SALEABLE": "Saleable Steel",
    "CARBON": "Carbon Steel Production",
}

_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fy_label(start_year: int) -> str:
    """Full FY key, e.g. 2023 -> '2023-24' — the format stored in
    special_steel_phys_perf.financial_year."""
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _yy(fy_label: str) -> str:
    """Display form: '2023-24' -> '23-24'."""
    return fy_label[2:] if fy_label and len(fy_label) == 7 else (fy_label or "")


def _fy_start_year(fy_label: str) -> int:
    return int(fy_label[:4])


def _fy_months(start_year: int) -> list:
    return ([f"{start_year}-{m:02d}" for m in range(4, 13)]
            + [f"{start_year + 1}-{m:02d}" for m in range(1, 4)])


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


def _prod_sum(cur, table: str, months: list) -> dict:
    """{(plant_db, item): (sum(month_actual), n_months_present)} over `months`,
    restricted to the special-steel plants + series items."""
    if not months:
        return {}
    plants = list(_PLANT_DB.values())
    items = list(_SERIES_ITEM.values())
    ph_p = ",".join("?" * len(plants))
    ph_i = ",".join("?" * len(items))
    ph_m = ",".join("?" * len(months))
    cur.execute(
        f"SELECT plant_name, item_name, COALESCE(SUM(month_actual), 0), "
        f"       COUNT(DISTINCT report_month) "
        f"FROM {table} "
        f"WHERE plant_name IN ({ph_p}) AND item_name IN ({ph_i}) AND report_month IN ({ph_m}) "
        f"  AND month_actual IS NOT NULL "
        f"GROUP BY plant_name, item_name",
        [*plants, *items, *months],
    )
    return {(p, i): (v, n) for p, i, v, n in cur.fetchall()}


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
    prev_start = cur_start - 1
    prev_prev_start = cur_start - 2
    history_starts = list(range(HISTORY_START_FY_YEAR, prev_start))
    history_fys = [_fy_label(y) for y in history_starts]        # full keys
    history_fys_disp = [_yy(fy) for fy in history_fys]          # yy-yy display

    ytd_months = db.get_ytd_months(report_month)
    cply_months = [db.get_cply_month(m) for m in ytd_months]
    ytd_label = f"{_MON[int(ytd_months[0][5:7])]}-{_MON[int(report_month[5:7])]}'{cur_start % 100:02d}"

    meta, perf = db.get_ss_phys_perf()

    conn = db.connect()
    cur = conn.cursor()
    try:
        db_prev_fy = _prod_sum(cur, "production_table", _fy_months(prev_start))
        db_ytd_act = _prod_sum(cur, "production_table", ytd_months)
        db_ytd_cply = _prod_sum(cur, "production_table", cply_months)
        db_ytd_app = _prod_sum(cur, "production_plan_table", ytd_months)
    finally:
        conn.close()

    def _db(store, plant, series, min_months=1):
        """DB value in T, or None when the series has no production_table item
        or fewer than `min_months` months are present (used to require a
        complete 12-month set for the prev-FY annual actual).

        SSP "Stainless Steel" has no production_table item of its own — it is
        derived as Saleable Steel − Carbon Steel Production (per direct
        instruction), and only when BOTH components clear `min_months`."""
        if series == "STAINLESS":
            sal = _db(store, plant, "SALEABLE", min_months)
            carbon = _db(store, plant, "CARBON", min_months)
            return None if sal is None or carbon is None else sal - carbon
        item = _SERIES_ITEM.get(series)
        if item is None:
            return None
        cell = store.get((_PLANT_DB[plant], item))
        if cell is None or cell[1] < min_months:
            return None
        return _t(cell[0])  # '000 T -> T

    sections = []
    for plant in _PLANT_ORDER:
        series_here = sorted(
            (s for (p, s) in meta if p == plant),
            key=lambda s: meta[(plant, s)]["sort_order"],
        )
        rows = []
        for series in series_here:
            m = meta[(plant, series)]

            def seed_actual(fy_label):
                return _t(perf.get((fy_label, plant, series, "actual")))

            # prev-FY annual actual: DB only when a full 12 months are present,
            # else the stored (seed / manually maintained) figure.
            prev_actual = _db(db_prev_fy, plant, series, min_months=12)
            if prev_actual is None:
                prev_actual = seed_actual(_fy_label(prev_start))
            prev_prev_actual = seed_actual(_fy_label(prev_prev_start))

            ytd_actual = _db(db_ytd_act, plant, series)
            ytd_cply = _db(db_ytd_cply, plant, series)
            ytd_app = _db(db_ytd_app, plant, series)
            cur_abp = _t(perf.get((cur_fy, plant, series, "plan")))

            rows.append({
                "series_label": _SERIES_LABEL.get(series, series),
                "capacity": _fmt(_t(m["capacity_kt"])),
                "best_actual": _fmt(_t(m["best_actual_kt"])),
                "best_year": _yy(m["best_year"]),
                "remark": m["remark"] or "",
                "history": {_yy(fy): _fmt(seed_actual(fy)) for fy in history_fys},
                "prev_actual": _fmt(prev_actual),
                "prev_pct_growth": _growth(prev_actual, prev_prev_actual),
                "cur_abp": _fmt(cur_abp),
                "ytd_app": _fmt(ytd_app),
                "ytd_actual": _fmt(ytd_actual),
                "ytd_pct_ful": _pct(ytd_actual, ytd_app),
                "ytd_cply": _fmt(ytd_cply),
                "ytd_growth": _growth(ytd_actual, ytd_cply),
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
        "cur_fy": _yy(cur_fy),
        "prev_fy": _yy(_fy_label(prev_start)),
        "ytd_label": ytd_label,
        "history_fys": history_fys_disp,
        "sections": sections,
        "notes": notes,
        "ipt_title": f"Special Steel Plants IPT requirement {cur_fy}",
        "ipt_rows": ipt_rows,
    }
