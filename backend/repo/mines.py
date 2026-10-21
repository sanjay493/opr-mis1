"""Mines repository: the iron-ore mine masters (mine_groups_master,
mines_master, mine_materials_master, mine_end_uses_master), the mine-level
monthly facts (mines_production_monthly, mines_despatch_actual_monthly,
mines_despatch_plan_monthly, mines_booked_qty_actual_monthly,
mines_booked_qty_plan_monthly) and the SAIL-level sail_mines_monthly grid.

The db.py functions moved here verbatim (re-exported from db.py). The named
cursor-level queries further down are the statements that used to live
inline in mines_performance.py, moved verbatim: each runs on the caller's
cursor and returns the plain fetchall() result.
"""
from typing import Any, Dict, List

from dbengine import connect
from repo import version as _ver
from repo import conn as rc


# ── Moved from db.py ─────────────────────────────────────────────────────────

def get_sail_mines_monthly(report_months: List[str]) -> Dict[str, Any]:
    """{report_month: {section: {item: {"actual": v, "plan": v}}}} for the
    given months — used both by page_sail_mines.py (YTD/CPLY roll-up) and
    the data-entry form's pre-fill."""
    conn = connect()
    cur = conn.cursor()
    out = {m: {} for m in report_months}
    if report_months:
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(
            f"SELECT report_month, section, item, month_actual, month_plan "
            f"FROM sail_mines_monthly WHERE report_month IN ({ph})",
            report_months,
        )
        for rm, section, item, act, plan in cur.fetchall():
            out.setdefault(rm, {}).setdefault(section, {})[item] = {"actual": act, "plan": plan}
    conn.close()
    return out


def save_sail_mines_monthly(report_month: str, entries: List[Dict[str, Any]]) -> int:
    """Upsert a batch of {section, item, actual, plan} entries for one
    report_month (the data-entry form submits every cell it's editing in
    one call)."""
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for e in entries:
        cur.execute("""
            INSERT INTO sail_mines_monthly (report_month, section, item, month_actual, month_plan)
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE month_actual = new.month_actual, month_plan = new.month_plan
        """, (report_month, e["section"], e["item"], e.get("actual"), e.get("plan")))
        saved += 1
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return saved


def get_mines_masters() -> Dict[str, Any]:
    """Groups/mines/materials/end-uses (+ the fixed Rail/Road transport
    modes) for the Mines Production & Despatch entry form and reports.
    DB-backed (not a Python registry) so a mine/material/end-use can be
    added or deactivated later without a code change."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT group_code, group_name FROM mine_groups_master ORDER BY sort_order")
    groups = [{"group_code": r[0], "group_name": r[1]} for r in cur.fetchall()]
    cur.execute("SELECT mine_code, mine_name, group_code, is_active FROM mines_master ORDER BY sort_order")
    mines = [{"mine_code": r[0], "mine_name": r[1], "group_code": r[2], "is_active": bool(r[3])} for r in cur.fetchall()]
    cur.execute(
        "SELECT material_code, material_name, material_category, has_production, counts_in_total_production "
        "FROM mine_materials_master ORDER BY sort_order"
    )
    materials = [
        {
            "material_code": r[0], "material_name": r[1], "material_category": r[2],
            "has_production": bool(r[3]), "counts_in_total_production": bool(r[4]),
        }
        for r in cur.fetchall()
    ]
    cur.execute("SELECT end_use_code, end_use_name, tracks_actual FROM mine_end_uses_master ORDER BY sort_order")
    end_uses = [{"end_use_code": r[0], "end_use_name": r[1], "tracks_actual": bool(r[2])} for r in cur.fetchall()]
    conn.close()
    return {
        "groups": groups, "mines": mines, "materials": materials, "end_uses": end_uses,
        "transport_modes": [{"mode_code": "RAIL", "mode_name": "Rail"}, {"mode_code": "ROAD", "mode_name": "Road"}],
    }


def get_mines_production_despatch_monthly(report_month: str, mine_code: str) -> Dict[str, Any]:
    """{"production": {material_code: {"actual": v, "plan": v}},
        "despatch": {material_code: {mode_code: {end_use_code: {"actual": v}}}},
        "despatch_plan": {material_code: {end_use_code: v}},
        "booked_qty": {material_code: {mode_code: {"actual": v}}},
        "booked_qty_plan": {material_code: v}}
    for one mine/report_month — used to pre-fill the entry form. despatch
    (Actual) is per transport_mode; despatch_plan is per material x end_use
    only — Plan doesn't split Rail/Road, per direct instruction. booked_qty
    (Sales only — no end_use dimension, see mines_booked_qty_actual_monthly)
    follows the same Actual-per-mode / Plan-with-no-mode-split shape."""
    conn = connect()
    cur = conn.cursor()

    production = {}
    cur.execute(
        "SELECT material_code, qty_actual, qty_plan FROM mines_production_monthly WHERE report_month=%s AND mine_code=%s",
        (report_month, mine_code),
    )
    for material_code, actual, plan in cur.fetchall():
        production[material_code] = {"actual": actual, "plan": plan}

    despatch = {}
    cur.execute(
        "SELECT material_code, transport_mode, end_use_code, qty_actual "
        "FROM mines_despatch_actual_monthly WHERE report_month=%s AND mine_code=%s",
        (report_month, mine_code),
    )
    for material_code, mode, end_use, actual in cur.fetchall():
        despatch.setdefault(material_code, {}).setdefault(mode, {})[end_use] = {"actual": actual}

    despatch_plan = {}
    cur.execute(
        "SELECT material_code, end_use_code, qty_plan "
        "FROM mines_despatch_plan_monthly WHERE report_month=%s AND mine_code=%s",
        (report_month, mine_code),
    )
    for material_code, end_use, plan in cur.fetchall():
        despatch_plan.setdefault(material_code, {})[end_use] = plan

    booked_qty = {}
    cur.execute(
        "SELECT material_code, transport_mode, qty_actual "
        "FROM mines_booked_qty_actual_monthly WHERE report_month=%s AND mine_code=%s",
        (report_month, mine_code),
    )
    for material_code, mode, actual in cur.fetchall():
        booked_qty.setdefault(material_code, {})[mode] = {"actual": actual}

    booked_qty_plan = {}
    cur.execute(
        "SELECT material_code, qty_plan FROM mines_booked_qty_plan_monthly WHERE report_month=%s AND mine_code=%s",
        (report_month, mine_code),
    )
    for material_code, plan in cur.fetchall():
        booked_qty_plan[material_code] = plan

    conn.close()
    return {
        "production": production, "despatch": despatch, "despatch_plan": despatch_plan,
        "booked_qty": booked_qty, "booked_qty_plan": booked_qty_plan,
    }


def save_mines_production_despatch_monthly(
    report_month: str, mine_code: str,
    production_entries: List[Dict[str, Any]], despatch_entries: List[Dict[str, Any]],
    despatch_plan_entries: List[Dict[str, Any]],
    booked_qty_entries: List[Dict[str, Any]] = None,
    booked_qty_plan_entries: List[Dict[str, Any]] = None,
) -> int:
    """Upsert one mine/month's changed production rows ({material_code,
    actual, plan}), despatch Actual rows ({material_code, transport_mode,
    end_use_code, actual}), despatch Plan rows ({material_code,
    end_use_code, plan}), booked-quantity Actual rows ({material_code,
    transport_mode, actual}), and booked-quantity Plan rows ({material_code,
    plan}) in one call — the entry form submits every cell it's editing,
    mirroring save_sail_mines_monthly's batch shape. Actual and Plan are
    separate tables/params because they're different grains: Actual is per
    transport_mode, Plan has no Rail/Road split (true for both despatch and
    booked quantity)."""
    booked_qty_entries = booked_qty_entries or []
    booked_qty_plan_entries = booked_qty_plan_entries or []
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for e in production_entries:
        cur.execute("""
            INSERT INTO mines_production_monthly (report_month, mine_code, material_code, qty_actual, qty_plan)
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE qty_actual = new.qty_actual, qty_plan = new.qty_plan
        """, (report_month, mine_code, e["material_code"], e.get("actual"), e.get("plan")))
        saved += 1
    for e in despatch_entries:
        cur.execute("""
            INSERT INTO mines_despatch_actual_monthly
                (report_month, mine_code, material_code, transport_mode, end_use_code, qty_actual)
            VALUES (%s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE qty_actual = new.qty_actual
        """, (
            report_month, mine_code, e["material_code"], e["transport_mode"], e["end_use_code"], e.get("actual"),
        ))
        saved += 1
    for e in despatch_plan_entries:
        cur.execute("""
            INSERT INTO mines_despatch_plan_monthly
                (report_month, mine_code, material_code, end_use_code, qty_plan)
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE qty_plan = new.qty_plan
        """, (report_month, mine_code, e["material_code"], e["end_use_code"], e.get("plan")))
        saved += 1
    for e in booked_qty_entries:
        cur.execute("""
            INSERT INTO mines_booked_qty_actual_monthly
                (report_month, mine_code, material_code, transport_mode, qty_actual)
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE qty_actual = new.qty_actual
        """, (report_month, mine_code, e["material_code"], e["transport_mode"], e.get("actual")))
        saved += 1
    for e in booked_qty_plan_entries:
        cur.execute("""
            INSERT INTO mines_booked_qty_plan_monthly (report_month, mine_code, material_code, qty_plan)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE qty_plan = new.qty_plan
        """, (report_month, mine_code, e["material_code"], e.get("plan")))
        saved += 1
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return saved


def get_iron_ore_group_rollup_monthly(report_months: List[str]) -> Dict[str, Any]:
    """Group-level (JGoM/OGoM/CGoM) Iron Ore Production & Despatch, rolled
    up from the mine-level tables (mines_production_monthly,
    mines_despatch_actual_monthly, mines_despatch_plan_monthly) via
    mines_master.group_code. Returns the same
    {report_month: {section: {item: {"actual": v, "plan": v}}}} shape as
    get_sail_mines_monthly (item = group_code) so page_sail_mines.py's
    existing YTD/CPLY roll-up logic (_leaf_values/_ytd_sum) works
    unchanged against it.

    This REPLACES sail_mines_monthly as the source for the 'iron_ore_prod'
    and 'iron_ore_despatch' sections only (per direct instruction,
    2026-08-26 — the mine-level entry form is now the single source of
    truth for Iron Ore Production/Despatch; every other section still comes
    from sail_mines_monthly as before). Despatch = ALL materials' (fresh +
    legacy) despatch Actual summed per group (Rail+Road combined) and Plan
    summed per group (Plan has no Rail/Road split — see
    mines_despatch_plan_monthly).

    Production = fresh Lump+Fines actual/plan (the only materials
    mine_materials_master flags has_production=1 for) PLUS despatch-only
    components that have no production entry of their own, so they're
    counted at the point they leave the mine instead: Dump Fines despatched
    to SALES, CAPTIVE or UNALLOCATED end_use (currently only GUA sends Dump
    Fines CAPTIVE — per direct instruction, 2026-09-17, that tonnage is now
    counted as production too, reversing the 2026-09-12 exclusion), Tailings
    despatched to end_use SALES or UNALLOCATED (legacy recovered material
    sold off, not part of planned Lump/Fines output — no CAPTIVE flow
    exists for Tailings), and Pellets despatch of any end_use (SAIL's
    pellet plants, currently only DALLI, have no separate "production"
    entry at all — their despatch figure, to SALES or CAPTIVE alike, IS
    their production). UNALLOCATED (a despatch-PLAN quantity with no
    destination yet, per direct instruction 2026-10-17) counts toward Dump
    Fines/Tailings here the same as a real destination would — it's
    despatch that hasn't been attributed to Captive/Sales yet, not
    despatch that didn't happen."""
    conn = connect()
    cur = conn.cursor()
    out = {m: {"iron_ore_prod": {}, "iron_ore_despatch": {}} for m in report_months}
    if not report_months:
        conn.close()
        return out
    ph = ",".join(["%s"] * len(report_months))

    prod_actual, prod_plan = {}, {}
    cur.execute(f"""
        SELECT p.report_month, mm.group_code, SUM(p.qty_actual), SUM(p.qty_plan)
        FROM mines_production_monthly p
        JOIN mines_master mm ON mm.mine_code = p.mine_code
        WHERE p.report_month IN ({ph})
        GROUP BY p.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual, plan in cur.fetchall():
        prod_actual.setdefault(rm, {})[group_code] = actual
        prod_plan.setdefault(rm, {})[group_code] = plan

    cur.execute(f"""
        SELECT d.report_month, mm.group_code, SUM(d.qty_actual)
        FROM mines_despatch_actual_monthly d
        JOIN mines_master mm ON mm.mine_code = d.mine_code
        WHERE d.report_month IN ({ph})
          AND (d.material_code = 'PELLETS'
               OR (d.material_code = 'DUMP_FINES' AND d.end_use_code IN ('SALES', 'CAPTIVE', 'UNALLOCATED'))
               OR (d.material_code = 'TAILINGS' AND d.end_use_code IN ('SALES', 'UNALLOCATED')))
        GROUP BY d.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual in cur.fetchall():
        prod_actual.setdefault(rm, {})[group_code] = (prod_actual.get(rm, {}).get(group_code) or 0) + (actual or 0)

    cur.execute(f"""
        SELECT pl.report_month, mm.group_code, SUM(pl.qty_plan)
        FROM mines_despatch_plan_monthly pl
        JOIN mines_master mm ON mm.mine_code = pl.mine_code
        WHERE pl.report_month IN ({ph})
          AND (pl.material_code = 'PELLETS'
               OR (pl.material_code = 'DUMP_FINES' AND pl.end_use_code IN ('SALES', 'CAPTIVE', 'UNALLOCATED'))
               OR (pl.material_code = 'TAILINGS' AND pl.end_use_code IN ('SALES', 'UNALLOCATED')))
        GROUP BY pl.report_month, mm.group_code
    """, report_months)
    for rm, group_code, plan in cur.fetchall():
        prod_plan.setdefault(rm, {})[group_code] = (prod_plan.get(rm, {}).get(group_code) or 0) + (plan or 0)

    for rm in report_months:
        groups = set(prod_actual.get(rm, {})) | set(prod_plan.get(rm, {}))
        for group_code in groups:
            out[rm]["iron_ore_prod"][group_code] = {
                "actual": prod_actual.get(rm, {}).get(group_code),
                "plan": prod_plan.get(rm, {}).get(group_code),
            }

    despatch_actual = {}
    cur.execute(f"""
        SELECT d.report_month, mm.group_code, SUM(d.qty_actual)
        FROM mines_despatch_actual_monthly d
        JOIN mines_master mm ON mm.mine_code = d.mine_code
        WHERE d.report_month IN ({ph})
        GROUP BY d.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual in cur.fetchall():
        despatch_actual.setdefault(rm, {})[group_code] = actual

    despatch_plan = {}
    cur.execute(f"""
        SELECT pl.report_month, mm.group_code, SUM(pl.qty_plan)
        FROM mines_despatch_plan_monthly pl
        JOIN mines_master mm ON mm.mine_code = pl.mine_code
        WHERE pl.report_month IN ({ph})
        GROUP BY pl.report_month, mm.group_code
    """, report_months)
    for rm, group_code, plan in cur.fetchall():
        despatch_plan.setdefault(rm, {})[group_code] = plan

    for rm in report_months:
        groups = set(despatch_actual.get(rm, {})) | set(despatch_plan.get(rm, {}))
        for group_code in groups:
            out[rm]["iron_ore_despatch"][group_code] = {
                "actual": despatch_actual.get(rm, {}).get(group_code),
                "plan": despatch_plan.get(rm, {}).get(group_code),
            }

    conn.close()
    return out


def get_iron_ore_despatch_mix(report_months: List[str]) -> Dict[str, float]:
    """SAIL-wide Iron Ore despatch actual summed across every mine, material
    and transport mode, grouped by end_use_code (CAPTIVE / SALES /
    PELLET_CONV) — the source for page_sail_mines.py's despatch-mix donuts
    (per direct instruction, 2026-09-17, replacing the earlier hand-
    maintained hardcoded_config.json snapshot). Returns {end_use_code:
    total_qty_actual} in '000 T; an end_use_code with no despatch at all
    across these months is simply omitted rather than returned as 0."""
    conn = connect()
    cur = conn.cursor()
    out: Dict[str, float] = {}
    if not report_months:
        conn.close()
        return out
    ph = ",".join(["%s"] * len(report_months))
    cur.execute(f"""
        SELECT end_use_code, SUM(qty_actual)
        FROM mines_despatch_actual_monthly
        WHERE report_month IN ({ph})
        GROUP BY end_use_code
    """, report_months)
    for end_use, total in cur.fetchall():
        if total is not None:
            out[end_use] = total
    conn.close()
    return out


def get_iron_ore_sales_group_rollup_monthly(report_months: List[str]) -> Dict[str, Any]:
    """Group-level (JGoM/OGoM/CGoM) Sales of Iron Ore — Booked Quantity &
    Despatch, rolled up via mines_master.group_code. Same
    {report_month: {section: {item: {"actual": v, "plan": v}}}} shape as
    get_iron_ore_group_rollup_monthly (item = group_code).

    REPLACES the old flat sail_mines_monthly 'iron_ore_sales' section
    (which had 2 SAIL-wide rows, "Auction"/"Despatch", no per-group
    breakdown) with a per-group breakdown for both rows, per direct
    instruction (2026-08-26) — "Auction" is renamed "Booked Quantity" and
    now comes from mines_booked_qty_actual_monthly /
    mines_booked_qty_plan_monthly (all materials/modes summed per group).
    "Despatch" here means despatch to the SALES end-use specifically (NOT
    all end-uses like get_iron_ore_group_rollup_monthly's despatch section)
    — it's mines_despatch_actual_monthly/mines_despatch_plan_monthly
    filtered to end_use_code='SALES' and summed per group, reusing data
    already entered on the Despatch — Sales to 3rd Party table rather than
    needing any new input."""
    conn = connect()
    cur = conn.cursor()
    out = {m: {"iron_ore_sales": {}, "iron_ore_sales_despatch": {}} for m in report_months}
    if not report_months:
        conn.close()
        return out
    ph = ",".join(["%s"] * len(report_months))

    booked_actual = {}
    cur.execute(f"""
        SELECT b.report_month, mm.group_code, SUM(b.qty_actual)
        FROM mines_booked_qty_actual_monthly b
        JOIN mines_master mm ON mm.mine_code = b.mine_code
        WHERE b.report_month IN ({ph})
        GROUP BY b.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual in cur.fetchall():
        booked_actual.setdefault(rm, {})[group_code] = actual

    booked_plan = {}
    cur.execute(f"""
        SELECT p.report_month, mm.group_code, SUM(p.qty_plan)
        FROM mines_booked_qty_plan_monthly p
        JOIN mines_master mm ON mm.mine_code = p.mine_code
        WHERE p.report_month IN ({ph})
        GROUP BY p.report_month, mm.group_code
    """, report_months)
    for rm, group_code, plan in cur.fetchall():
        booked_plan.setdefault(rm, {})[group_code] = plan

    for rm in report_months:
        groups = set(booked_actual.get(rm, {})) | set(booked_plan.get(rm, {}))
        for group_code in groups:
            out[rm]["iron_ore_sales"][group_code] = {
                "actual": booked_actual.get(rm, {}).get(group_code),
                "plan": booked_plan.get(rm, {}).get(group_code),
            }

    sales_desp_actual = {}
    cur.execute(f"""
        SELECT d.report_month, mm.group_code, SUM(d.qty_actual)
        FROM mines_despatch_actual_monthly d
        JOIN mines_master mm ON mm.mine_code = d.mine_code
        WHERE d.report_month IN ({ph}) AND d.end_use_code = 'SALES'
        GROUP BY d.report_month, mm.group_code
    """, report_months)
    for rm, group_code, actual in cur.fetchall():
        sales_desp_actual.setdefault(rm, {})[group_code] = actual

    sales_desp_plan = {}
    cur.execute(f"""
        SELECT pl.report_month, mm.group_code, SUM(pl.qty_plan)
        FROM mines_despatch_plan_monthly pl
        JOIN mines_master mm ON mm.mine_code = pl.mine_code
        WHERE pl.report_month IN ({ph}) AND pl.end_use_code = 'SALES'
        GROUP BY pl.report_month, mm.group_code
    """, report_months)
    for rm, group_code, plan in cur.fetchall():
        sales_desp_plan.setdefault(rm, {})[group_code] = plan

    for rm in report_months:
        groups = set(sales_desp_actual.get(rm, {})) | set(sales_desp_plan.get(rm, {}))
        for group_code in groups:
            out[rm]["iron_ore_sales_despatch"][group_code] = {
                "actual": sales_desp_actual.get(rm, {}).get(group_code),
                "plan": sales_desp_plan.get(rm, {}).get(group_code),
            }

    conn.close()
    return out


def get_iron_ore_mines_series(report_months: List[str]) -> Dict[str, Any]:
    """Flat month-wise mine-level Iron Ore rows for the reports page
    (/reports/iron-ore-mines) — no roll-up, the frontend groups by
    scope/material/mode itself. All quantities are '000 T.

      production:     [{report_month, mine_code, group_code, material_code,
                        actual, plan}]  — LUMP / FINES only
      despatch:       [{report_month, mine_code, group_code, material_code,
                        transport_mode, end_use_code, actual}]
                        — LUMP / FINES / DUMP_FINES / TAILINGS / PELLETS,
                          mode RAIL / ROAD
      despatch_plan:  [{report_month, mine_code, group_code, material_code,
                        end_use_code, plan}]  — Plan has no Rail/Road split
    """
    conn = connect()
    cur = conn.cursor()
    out = {"production": [], "despatch": [], "despatch_plan": []}
    if not report_months:
        conn.close()
        return out
    ph = ",".join(["%s"] * len(report_months))

    cur.execute(f"""
        SELECT p.report_month, p.mine_code, mm.group_code, p.material_code,
               p.qty_actual, p.qty_plan
        FROM mines_production_monthly p
        JOIN mines_master mm ON mm.mine_code = p.mine_code
        WHERE p.report_month IN ({ph})
    """, report_months)
    for rm, mine, grp, mat, act, plan in cur.fetchall():
        out["production"].append({
            "report_month": rm, "mine_code": mine, "group_code": grp,
            "material_code": mat, "actual": act, "plan": plan,
        })

    cur.execute(f"""
        SELECT d.report_month, d.mine_code, mm.group_code, d.material_code,
               d.transport_mode, d.end_use_code, d.qty_actual
        FROM mines_despatch_actual_monthly d
        JOIN mines_master mm ON mm.mine_code = d.mine_code
        WHERE d.report_month IN ({ph})
    """, report_months)
    for rm, mine, grp, mat, mode, eu, act in cur.fetchall():
        out["despatch"].append({
            "report_month": rm, "mine_code": mine, "group_code": grp,
            "material_code": mat, "transport_mode": mode, "end_use_code": eu,
            "actual": act,
        })

    cur.execute(f"""
        SELECT pl.report_month, pl.mine_code, mm.group_code, pl.material_code,
               pl.end_use_code, pl.qty_plan
        FROM mines_despatch_plan_monthly pl
        JOIN mines_master mm ON mm.mine_code = pl.mine_code
        WHERE pl.report_month IN ({ph})
    """, report_months)
    for rm, mine, grp, mat, eu, plan in cur.fetchall():
        out["despatch_plan"].append({
            "report_month": rm, "mine_code": mine, "group_code": grp,
            "material_code": mat, "end_use_code": eu, "plan": plan,
        })

    conn.close()
    return out



# ── Named queries ─────────────────────────────────────────────────────────────

# sail_mines_monthly presence (page_missing_data). Self-contained, like
# repo.special_steel.abp_any_row.

def sail_mines_any_row(report_month):
    """True when sail_mines_monthly has any row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM sail_mines_monthly WHERE report_month = %s LIMIT 1",
                    [report_month])
        return bool(cur.fetchall())


# mines_performance._load: every master and series it needs, read once on
# the caller's cursor. Each returns the plain fetchall().

def group_rows(cur):
    """(group_code, group_name) in sort order."""
    cur.execute("SELECT group_code, group_name FROM mine_groups_master ORDER BY sort_order")
    return cur.fetchall()


def mine_rows(cur):
    """(mine_code, mine_name, group_code, is_active) for every mine, active
    or not, in sort order."""
    cur.execute("SELECT mine_code, mine_name, group_code, is_active FROM mines_master "
                "ORDER BY sort_order")
    return cur.fetchall()


def material_rows(cur):
    """(material_code, material_name) in sort order."""
    cur.execute("SELECT material_code, material_name FROM mine_materials_master ORDER BY sort_order")
    return cur.fetchall()


def production_rows(cur, months):
    """(mine_code, material_code, report_month, qty_actual, qty_plan)."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT mine_code, material_code, report_month, qty_actual, qty_plan "
                f"FROM mines_production_monthly WHERE report_month IN ({ph})", months)
    return cur.fetchall()


def despatch_actual_rows(cur, months):
    """(mine_code, material_code, end_use_code, report_month, qty_actual),
    one row per transport mode."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT mine_code, material_code, end_use_code, report_month, qty_actual "
                f"FROM mines_despatch_actual_monthly WHERE report_month IN ({ph})", months)
    return cur.fetchall()


def despatch_plan_rows(cur, months):
    """(mine_code, material_code, end_use_code, report_month, qty_plan)."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT mine_code, material_code, end_use_code, report_month, qty_plan "
                f"FROM mines_despatch_plan_monthly WHERE report_month IN ({ph})", months)
    return cur.fetchall()


def booked_actual_rows(cur, months):
    """(mine_code, material_code, report_month, qty_actual), one row per
    transport mode."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT mine_code, material_code, report_month, qty_actual "
                f"FROM mines_booked_qty_actual_monthly WHERE report_month IN ({ph})", months)
    return cur.fetchall()


def booked_plan_rows(cur, months):
    """(mine_code, material_code, report_month, qty_plan)."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT mine_code, material_code, report_month, qty_plan "
                f"FROM mines_booked_qty_plan_monthly WHERE report_month IN ({ph})", months)
    return cur.fetchall()


def sail_rows(cur, months):
    """(section, item, report_month, month_actual, month_plan) from
    sail_mines_monthly."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT section, item, report_month, month_actual, month_plan "
                f"FROM sail_mines_monthly WHERE report_month IN ({ph})", months)
    return cur.fetchall()
