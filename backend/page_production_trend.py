"""
FY-wise / Calendar-Year-wise trend of Hot Metal, Crude Steel, Finished Steel
and Saleable Steel (frontend: /reports/production-trend), selectable by
plant group -- SAIL (5 integrated plants), SAIL (8 plants), or an individual
plant.

Reads production_table the same way page7_13.py's TREND_PAGES does (same
db_item names, same live-sum-vs-stored-SAIL-snapshot handling for Finished
Steel, same SSP/VISL Finished-Steel-from-Saleable-Steel fallback), but
reshapes it into one row per year across all 4 items instead of one PDF
page per item with every plant group shown at once.
"""
import db
from constants import ALL_PLANTS

SAIL_5 = ["BSP", "DSP", "RSP", "BSL", "ISP"]
SAIL_8 = ALL_PLANTS  # ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL']

TREND_ITEMS = [
    ("Hot Metal", "hot_metal"),
    ("Total Crude Steel", "crude_steel"),
    ("Finished Steel", "finished_steel"),
    ("Saleable Steel", "saleable_steel"),
]

# Some months, SSP/VISL report Finished Steel only under "Saleable Steel" --
# same fold page7_13.py's _FS_ALIAS applies for its SAIL trend pages.
_FS_ALIAS_PLANTS = frozenset({"SSP", "VISL"})


def list_groups():
    """Ordered (value, label) options for the plant-group selector."""
    groups = [
        {"value": "sail5", "label": "SAIL (5 Plants)"},
        {"value": "sail8", "label": "SAIL (8 Plants)"},
    ]
    groups += [{"value": p, "label": p} for p in SAIL_8]
    return groups


def resolve_group(group: str):
    """Returns (plant_list, group_label, use_sail_direct) or None if group is invalid."""
    if group == "sail5":
        return SAIL_5, "SAIL (5 Plants)", False
    if group == "sail8":
        return SAIL_8, "SAIL (8 Plants)", True
    if group in SAIL_8:
        return [group], group, False
    return None


def _year_key_label(report_month: str, basis: str):
    y, m = int(report_month[:4]), int(report_month[5:7])
    if basis == "cy":
        return y, str(y)
    fy = y if m >= 4 else y - 1
    return fy, f"{fy}-{str(fy + 1)[2:]}"


def get_trend_data(basis: str, group: str) -> dict:
    resolved = resolve_group(group)
    if resolved is None:
        raise ValueError(f"invalid group: {group}")
    plants, group_label, use_sail_direct = resolved

    db_items = [it for it, _ in TREND_ITEMS]
    phs_items = ",".join("?" for _ in db_items)
    phs_plants = ",".join("?" for _ in plants)

    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT plant_name, item_name, report_month, month_actual FROM production_table "
        f"WHERE item_name IN ({phs_items}) AND plant_name IN ({phs_plants})",
        db_items + plants,
    )
    data = {it: {} for it in db_items}
    for plant, item, rm, val in cur.fetchall():
        if val is None:
            continue
        data[item].setdefault(plant, {})[rm] = val

    alias_plants = [p for p in plants if p in _FS_ALIAS_PLANTS]
    if alias_plants:
        aphs = ",".join("?" for _ in alias_plants)
        cur.execute(
            f"SELECT plant_name, report_month, month_actual FROM production_table "
            f"WHERE item_name='Saleable Steel' AND plant_name IN ({aphs})",
            alias_plants,
        )
        for plant, rm, val in cur.fetchall():
            if val is None:
                continue
            data["Finished Steel"].setdefault(plant, {}).setdefault(rm, val)

    sail_direct = {}
    if use_sail_direct:
        cur.execute(
            f"SELECT item_name, report_month, month_actual FROM production_table "
            f"WHERE item_name IN ({phs_items}) AND plant_name='SAIL'",
            db_items,
        )
        for item, rm, val in cur.fetchall():
            if val is not None:
                sail_direct.setdefault(item, {})[rm] = val
    conn.close()

    all_months = set()
    for it in db_items:
        for plant in plants:
            all_months.update(data[it].get(plant, {}).keys())
        all_months.update(sail_direct.get(it, {}).keys())

    years = {}  # year_key -> {"label": str, "months": set()}
    for rm in all_months:
        yk, lbl = _year_key_label(rm, basis)
        years.setdefault(yk, {"label": lbl, "months": set()})["months"].add(rm)

    def month_value(item, month):
        plant_vals = [data[item].get(p, {}).get(month) for p in plants]
        live = sum(v for v in plant_vals if v is not None) if any(v is not None for v in plant_vals) else None
        if not use_sail_direct:
            return live
        direct = sail_direct.get(item, {}).get(month)
        if item == "Finished Steel":
            # Prefer a live sum only when every plant reported that month,
            # else fall back to the stored SAIL snapshot -- mirrors
            # page7_13.py's _live_sum_or_sail_fallback / prefer_live_sum,
            # since Finished Steel's stored SAIL row goes stale the moment
            # a constituent plant's own figure is corrected afterwards.
            if all(v is not None for v in plant_vals):
                return sum(plant_vals)
            return direct
        return direct if direct is not None else live

    rows = []
    for yk in sorted(years.keys(), reverse=True):
        months = years[yk]["months"]
        row = {"year_key": yk, "year_label": years[yk]["label"]}
        for item, key in TREND_ITEMS:
            vals = [month_value(item, m) for m in months]
            nz = [v for v in vals if v is not None]
            row[key] = round(sum(nz), 3) if nz else None
        rows.append(row)

    return {
        "basis": basis,
        "group": group,
        "group_label": group_label,
        "items": [{"item_name": disp, "key": key} for disp, key in TREND_ITEMS],
        "years": rows,
    }
