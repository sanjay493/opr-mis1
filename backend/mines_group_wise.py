"""
Iron Ore Mines -- Mine & Group-wise (FY): a workbook-style reshape of the
same mine-level Production & Despatch tables that back
/reports/iron-ore-mines (mines_production_monthly, mines_despatch_actual_
monthly, mines_despatch_plan_monthly) -- no new tables, no new ingestion.

Rows are mine -> commodity (Production) or mine -> commodity -> destination
(Despatch), with Mine Total / Group Total / SAIL Total rows; columns are
the FY's 12 months (Plan | Actual) plus an FY Total. Despatch Actual sums
Rail+Road per material x end-use (this layout, unlike /reports/iron-ore-
mines, does not split by transport mode); despatch Plan already has no
mode split.

generate(fy_start) -> {"fy_label", "months", "production", "despatch",
                        "reported_production"}
  each section: {"groups": [{group_code, group_name,
      "mines": [{mine_code, mine_name, "rows": [...], "total": cells}],
      "total": cells}], "sail_total": cells}
  row = {"material_code", "material_name", ["end_use_code", "end_use_name"],
         "months": {month: {"plan","actual"}}, "fy_total": {"plan","actual"}}
  cells (mine/group/SAIL total) = {"months": {...}, "fy_total": {...}}

reported_production's rows are Fresh Production (Lump+Fines) plus whichever
legacy despatch pieces count toward it -- the same fixed rule as
mines_performance.py's REPORTED_PARTS (Pellets: any destination; Dump
Fines: Captive+Sales+Unallocated; Tailings: Sales+Unallocated -- Unallocated
is despatch not yet attributed to a destination, not despatch that didn't
happen, so it counts the same as a real destination would here). Kept in
sync by hand with that module, not shared code, since the two build
differently-shaped output.
"""
from repo import mines as rmn

REPORTED_PARTS = (
    ("FRESH", "Fresh Production (Lump+Fines)", None, None),
    ("PELLETS_DESP", "Pellets Despatch", "PELLETS", None),
    ("DUMP_FINES_DESP", "Dump Fines Despatch", "DUMP_FINES", ("CAPTIVE", "SALES", "UNALLOCATED")),
    ("TAILINGS_DESP", "Tailings Despatch", "TAILINGS", ("SALES", "UNALLOCATED")),
)


def _months(fy_start: int):
    return [f"{fy_start}-{m:02d}" for m in range(4, 13)] + [f"{fy_start + 1}-{m:02d}" for m in range(1, 4)]


def _sum(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def _empty_cells(months):
    return {m: {"plan": None, "actual": None} for m in months}


def _add(dst, month, plan, actual):
    c = dst[month]
    if plan is not None:
        c["plan"] = (c["plan"] or 0) + plan
    if actual is not None:
        c["actual"] = (c["actual"] or 0) + actual


def _fy_total(cells, months):
    return {
        "plan": _sum(cells[m]["plan"] for m in months),
        "actual": _sum(cells[m]["actual"] for m in months),
    }


def _has_data(cells, months):
    return any(cells[m]["plan"] is not None or cells[m]["actual"] is not None for m in months)


def _accumulate_total(total_cells, row_cells, months):
    for m in months:
        _add(total_cells, m, row_cells[m]["plan"], row_cells[m]["actual"])


def _combine(cells_list, months):
    out = _empty_cells(months)
    for c in cells_list:
        _accumulate_total(out, c, months)
    return out


def generate(fy_start: int) -> dict:
    months = _months(fy_start)
    masters = rmn.get_mines_masters()
    raw = rmn.get_iron_ore_mines_series(months)

    mat_order = [m["material_code"] for m in masters["materials"]]
    mat_name = {m["material_code"]: m["material_name"] for m in masters["materials"]}
    prod_materials = [m["material_code"] for m in masters["materials"] if m["has_production"]]
    eu_order = [e["end_use_code"] for e in masters["end_uses"]]
    eu_name = {e["end_use_code"]: e["end_use_name"] for e in masters["end_uses"]}
    mines_by_group = {}
    for m in masters["mines"]:
        if m["is_active"]:
            mines_by_group.setdefault(m["group_code"], []).append(m)

    prod_cells = {}
    for r in raw["production"]:
        key = (r["mine_code"], r["material_code"])
        prod_cells.setdefault(key, _empty_cells(months))
        _add(prod_cells[key], r["report_month"], r["plan"], r["actual"])

    desp_cells = {}
    for r in raw["despatch"]:
        key = (r["mine_code"], r["material_code"], r["end_use_code"])
        desp_cells.setdefault(key, _empty_cells(months))
        _add(desp_cells[key], r["report_month"], None, r["actual"])
    for r in raw["despatch_plan"]:
        key = (r["mine_code"], r["material_code"], r["end_use_code"])
        desp_cells.setdefault(key, _empty_cells(months))
        _add(desp_cells[key], r["report_month"], r["plan"], None)

    def build_section(row_keys_for_mine, row_builder):
        sail_total = _empty_cells(months)
        groups_out = []
        for g in masters["groups"]:
            group_total = _empty_cells(months)
            mines_out = []
            for mine in mines_by_group.get(g["group_code"], []):
                mine_total = _empty_cells(months)
                rows_out = []
                for key, row in row_keys_for_mine(mine["mine_code"]):
                    if not _has_data(row, months):
                        continue
                    _accumulate_total(mine_total, row, months)
                    rows_out.append(row_builder(key, row))
                mines_out.append({
                    "mine_code": mine["mine_code"], "mine_name": mine["mine_name"],
                    "rows": rows_out,
                    "total": {"months": mine_total, "fy_total": _fy_total(mine_total, months)},
                })
                _accumulate_total(group_total, mine_total, months)
            groups_out.append({
                "group_code": g["group_code"], "group_name": g["group_name"],
                "mines": mines_out,
                "total": {"months": group_total, "fy_total": _fy_total(group_total, months)},
            })
            _accumulate_total(sail_total, group_total, months)
        return {
            "groups": groups_out,
            "sail_total": {"months": sail_total, "fy_total": _fy_total(sail_total, months)},
        }

    def prod_keys_for_mine(mine_code):
        for mat in prod_materials:
            yield mat, prod_cells.get((mine_code, mat), _empty_cells(months))

    def prod_row(mat, cells):
        return {
            "material_code": mat, "material_name": mat_name[mat],
            "months": cells, "fy_total": _fy_total(cells, months),
        }

    def desp_keys_for_mine(mine_code):
        for mat in mat_order:
            for eu in eu_order:
                yield (mat, eu), desp_cells.get((mine_code, mat, eu), _empty_cells(months))

    def desp_row(key, cells):
        mat, eu = key
        return {
            "material_code": mat, "material_name": mat_name[mat],
            "end_use_code": eu, "end_use_name": eu_name[eu],
            "months": cells, "fy_total": _fy_total(cells, months),
        }

    reported_label = {code: label for code, label, _mat, _eus in REPORTED_PARTS}

    def reported_keys_for_mine(mine_code):
        for code, _label, mat, eus in REPORTED_PARTS:
            if mat is None:  # FRESH: fresh Lump+Fines production, not despatch
                cells = _combine([prod_cells.get((mine_code, m), _empty_cells(months)) for m in prod_materials], months)
            else:
                cells = _combine([desp_cells.get((mine_code, mat, eu), _empty_cells(months)) for eu in (eus or eu_order)], months)
            yield code, cells

    def reported_row(code, cells):
        return {
            "material_code": code, "material_name": reported_label[code],
            "months": cells, "fy_total": _fy_total(cells, months),
        }

    return {
        "fy_start": fy_start,
        "fy_label": f"{fy_start}-{str(fy_start + 1)[2:]}",
        "months": months,
        "production": build_section(prod_keys_for_mine, prod_row),
        "despatch": build_section(desp_keys_for_mine, desp_row),
        "reported_production": build_section(reported_keys_for_mine, reported_row),
    }
