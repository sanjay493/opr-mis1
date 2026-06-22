"""
Compute and persist shop-level BF aggregate rows from per-furnace data.

Called after extraction when a plant has per-furnace techno rows in techno_monthly
but the source file does not directly supply a shop average.  Also used to
re-compute existing shop averages from scratch for verification.

Aggregation rules (per user requirement):
  - Rate parameters (Coke Rate, Nut Coke Rate, CDI Rate, Fuel Rate,
    Sinter/Pellet in Burden, Si/S in HM):  weighted average by furnace HM production
  - BF Productivity:                        harmonic mean  weighted by HM production
  - Blast Temperature:                      simple average (production weighting not standard)

HM production weights come from production_table when available, falling back
to equal weighting when furnace-level production is absent.

Design principle — primary vs secondary writes:
  Source extractors write raw per-furnace values (primary).
  This module writes shop-aggregate rows (secondary, lower priority = 4).
  shop rows written here will NOT overwrite a value already stored at priority >= 4,
  so directly-extracted shop averages (priority 5, the default) always win.
"""

import sqlite3
from typing import Dict, List, Optional, Tuple

# Section name in IRON_MAKING → MAJOR section name (for mirroring computed Avg to MAJOR)
_SECTION_TO_MAJOR = {
    "BF Coke Rate":    "Coke Rate",
    "Nut Coke Rate":   "Nut Coke Consumption",
    "CDI":             "CDI Rate",
    "Fuel Rate":       "Fuel Rate",
    "Sinter in Burden": "Sinter in Burden",
    "Pellet in Burden": "Pellet in Burden",
    "BF Productivity": "BF Productivity (Working Volume)",
}
# Plant label in IRON_MAKING shop row → MAJOR row_label
_SHOP_LABEL_TO_MAJOR_ROW = {
    "BSP Plant Shop": "BSP", "DSP Plant Shop": "DSP", "RSP Plant Shop": "RSP",
    "BSL Plant Shop": "BSL", "ISP Plant Shop": "ISP",
}

# ── Parameters that use weighted average ────────────────────────────────────
_WEIGHTED_SECTIONS = frozenset({
    "BF Coke Rate", "Nut Coke Rate", "CDI", "Fuel Rate",
    "Sinter in Burden", "Pellet in Burden", "Si in HM", "S in HM",
})
# Parameters that use harmonic mean (weighted by production)
_HARMONIC_SECTIONS = frozenset({"BF Productivity"})
# Parameters that use simple average
_SIMPLE_SECTIONS = frozenset({"HBT"})

# Fallback hardcoded furnace→production_item mapping for plants where
# production_table has per-furnace entries (overrides equal-weight fallback).
# Format: { plant_code: { unit_name: production_item_name_in_production_table } }
_PROD_ITEM_MAP: Dict[str, Dict[str, Optional[str]]] = {
    "DSP": {"BF-2": "BF#2", "BF-3": "BF#3", "BF-4": "BF#4"},
    "RSP": {"BF-1": "BF-1", "BF-5": "BF-5"},
}


def _load_plant_furnaces(conn: sqlite3.Connection, plant: str
                          ) -> Tuple[List[Tuple[str, Optional[str]]], str]:
    """
    Load per-furnace (non-shop) BF units for a plant from plant_units table.
    Returns ([(display_label, prod_item_or_None), ...], shop_display_label).
    Automatically picks up newly added furnaces from the registry.
    """
    cur = conn.execute(
        "SELECT unit_name, display_label, is_shop FROM plant_units "
        "WHERE plant_code=? AND unit_type='BF' AND is_active=1 ORDER BY sort_order",
        (plant,),
    )
    rows = cur.fetchall()
    furnaces = []
    shop_label = f"{plant} Plant Shop"
    prod_map = _PROD_ITEM_MAP.get(plant, {})
    for unit_name, display_label, is_shop in rows:
        if is_shop:
            shop_label = display_label
        else:
            prod_item = prod_map.get(unit_name)
            furnaces.append((display_label, prod_item))
    return furnaces, shop_label


def _get_production(conn: sqlite3.Connection, plant: str, item: str,
                    report_month: str) -> Optional[float]:
    cur = conn.execute(
        "SELECT month_actual FROM production_table "
        "WHERE plant_name=? AND item_name=? AND report_month=?",
        (plant, item, report_month),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _weighted_avg(vals_weights: List[Tuple[float, float]]) -> Optional[float]:
    """Weighted arithmetic mean; equal weights if all weights are None/0."""
    valid = [(v, w) for v, w in vals_weights if v is not None]
    if not valid:
        return None
    total_w = sum(w for _, w in valid if w)
    if total_w:
        return sum(v * w for v, w in valid if w) / total_w
    # Fall back to simple average when no production weights
    return sum(v for v, _ in valid) / len(valid)


def _harmonic_mean(vals_weights: List[Tuple[float, float]]) -> Optional[float]:
    """Weighted harmonic mean: sum(w) / sum(w/v)."""
    valid = [(v, w) for v, w in vals_weights if v is not None and v > 0]
    if not valid:
        return None
    total_w = sum(w for _, w in valid if w)
    if total_w:
        denom = sum(w / v for v, w in valid if w and v > 0)
        return total_w / denom if denom else None
    # Equal-weight harmonic mean
    n = len(valid)
    denom = sum(1.0 / v for v, _ in valid)
    return n / denom if denom else None


def _simple_avg(vals: List[Optional[float]]) -> Optional[float]:
    valid = [v for v in vals if v is not None]
    return sum(valid) / len(valid) if valid else None


def compute_bf_shop_averages(conn: sqlite3.Connection, report_month: str,
                              plants: Optional[List[str]] = None) -> int:
    """
    Compute shop-level BF aggregate rows for each plant and write to techno_monthly.

    Skips ISP (single furnace) and any plant with fewer than 2 furnaces with data.
    Returns count of rows written/updated.

    Priority: written at source_priority=4 so they do NOT overwrite primary-source
    shop averages (priority 5).
    """
    if plants is None:
        plants = ["BSP", "DSP", "RSP"]
        # BSL excluded: the BF Performance PDF provides both per-furnace and Plant Shop
        # monthly values directly at priority 5, so no computed fallback is needed.

    sections = _WEIGHTED_SECTIONS | _HARMONIC_SECTIONS | _SIMPLE_SECTIONS
    written = 0

    for plant in plants:
        furnaces, shop_label = _load_plant_furnaces(conn, plant)
        if len(furnaces) < 2:
            continue

        for section in sections:
            # Collect per-furnace values and production weights
            vals_weights: List[Tuple[Optional[float], float]] = []
            for fce_label, prod_item in furnaces:
                # Look up param_id for this furnace in this section
                cur = conn.execute(
                    "SELECT p.param_id FROM techno_param_master p "
                    "WHERE p.group_code='IRON_MAKING' AND p.section=? "
                    "AND p.row_label=?",
                    (section, fce_label),
                )
                row = cur.fetchone()
                if not row:
                    continue
                param_id = row[0]
                # Get the actual value for this month
                cur2 = conn.execute(
                    "SELECT actual FROM techno_monthly "
                    "WHERE param_id=? AND report_month=?",
                    (param_id, report_month),
                )
                val_row = cur2.fetchone()
                val = val_row[0] if val_row else None
                # Get production weight
                weight = 0.0
                if prod_item:
                    w = _get_production(conn, plant, prod_item, report_month)
                    if w:
                        weight = w
                vals_weights.append((val, weight))

            # Need at least 2 furnaces with values to compute shop avg
            n_with_val = sum(1 for v, _ in vals_weights if v is not None)
            if n_with_val < 2:
                continue

            # Compute aggregate
            if section in _HARMONIC_SECTIONS:
                agg = _harmonic_mean(vals_weights)
            elif section in _WEIGHTED_SECTIONS:
                agg = _weighted_avg(vals_weights)
            else:  # _SIMPLE_SECTIONS
                agg = _simple_avg([v for v, _ in vals_weights])

            if agg is None:
                continue

            # Ensure shop param_master row exists
            from db import get_or_create_techno_param, save_techno_monthly
            # Find the unit from one of the furnace rows
            cur3 = conn.execute(
                "SELECT unit FROM techno_param_master "
                "WHERE group_code='IRON_MAKING' AND section=? AND row_label!=? LIMIT 1",
                (section, shop_label),
            )
            unit_row = cur3.fetchone()
            unit = unit_row[0] if unit_row else ""

            sort_order_map = {
                "BF Coke Rate": 48, "Nut Coke Rate": 58, "CDI": 10,
                "Fuel Rate": 109, "Sinter in Burden": 119, "Pellet in Burden": 129,
                "Si in HM": 79, "S in HM": 89, "BF Productivity": 68,
                "HBT": 99,
            }
            so = sort_order_map.get(section, 999)

            param_id = get_or_create_techno_param(
                "IRON_MAKING", section, shop_label, unit, so
            )
            save_techno_monthly(param_id, report_month, round(agg, 4), None,
                                source_priority=4)
            # Mirror to canonical MAJOR param at priority 4 (won't overwrite manual p5 entries)
            major_section = _SECTION_TO_MAJOR.get(section)
            major_row = _SHOP_LABEL_TO_MAJOR_ROW.get(shop_label)
            if major_section and major_row:
                cur_maj = conn.execute(
                    "SELECT param_id FROM techno_param_master "
                    "WHERE group_code='MAJOR' AND section=? AND row_label=?",
                    (major_section, major_row),
                )
                maj_row = cur_maj.fetchone()
                if maj_row:
                    save_techno_monthly(maj_row[0], report_month, round(agg, 4), None,
                                        source_priority=4)
            written += 1

    return written


def compute_fuel_rate_fallback(conn: sqlite3.Connection, report_month: str) -> int:
    """For each IRON_MAKING furnace/plant row that has no Fuel Rate but has all three
    of BF Coke Rate + Nut Coke Rate + CDI, write Fuel Rate = sum of the three at
    source_priority=3 (lower than any extracted value so it's always overridable).
    Returns count of rows written.
    """
    from db import get_or_create_techno_param, save_techno_monthly

    cur = conn.execute(
        "SELECT DISTINCT row_label FROM techno_param_master "
        "WHERE group_code='IRON_MAKING' AND section='Fuel Rate'"
    )
    known_labels = {r[0] for r in cur.fetchall()}

    cur = conn.execute(
        "SELECT DISTINCT row_label FROM techno_param_master "
        "WHERE group_code='IRON_MAKING' AND section='BF Coke Rate'"
    )
    coke_labels = {r[0] for r in cur.fetchall()}

    written = 0
    for label in coke_labels:
        def _val(section):
            cur2 = conn.execute(
                "SELECT tm.actual FROM techno_monthly tm "
                "JOIN techno_param_master pm ON pm.param_id=tm.param_id "
                "WHERE pm.group_code='IRON_MAKING' AND pm.section=? "
                "AND pm.row_label=? AND tm.report_month=?",
                (section, label, report_month),
            )
            row = cur2.fetchone()
            return row[0] if row else None

        coke = _val("BF Coke Rate")
        nut  = _val("Nut Coke Rate")
        cdi  = _val("CDI")
        if coke is None or nut is None or cdi is None:
            continue

        existing_fr = _val("Fuel Rate")
        if existing_fr is not None:
            continue

        fuel = round(coke + nut + cdi, 4)
        param_id = get_or_create_techno_param("IRON_MAKING", "Fuel Rate", label, "Kg/THM", 109)
        save_techno_monthly(param_id, report_month, fuel, None, source_priority=3)
        written += 1

    return written


def recompute_all_months(conn: sqlite3.Connection,
                         plants: Optional[List[str]] = None) -> Dict[str, int]:
    """Recompute shop averages for all months that have per-furnace data."""
    cur = conn.execute("SELECT DISTINCT report_month FROM techno_monthly ORDER BY report_month")
    months = [r[0] for r in cur.fetchall()]
    results = {}
    for month in months:
        n = compute_bf_shop_averages(conn, month, plants)
        if n:
            results[month] = n
    return results
