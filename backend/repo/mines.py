"""Mines repository on the v2 schema: the iron-ore mine masters (mine_group,
mine, mine_material, mine_end_use), the mine-level monthly facts
(mine_production_monthly, mine_despatch_actual_monthly,
mine_despatch_plan_monthly, mine_booked_qty_actual_monthly,
mine_booked_qty_plan_monthly) and sail_mines_monthly. v1's tables were
already normalised; v2 renames them to singular nouns and keeps every
column name, so rows come back with v1's keys unchanged.

Same public names, signatures, return shapes and exceptions as
repo/mines.py.

ORDER. Reads with an ORDER BY keep it, plus the primary key as a tie-break
(no ties in today's masters). Reads without one were served in v1 by the
primary key, which v2 repeats; that order is explicit here. The group
rollups build their output by iterating Python sets of group codes, exactly
as v1's code does (same statements, same row order into the same dicts),
so with PYTHONHASHSEED fixed their key order is v1's.

WRITES. One bump per call, first (skipped in a dry run), as v1 (also for an
empty batch). The month is cut to CHAR(7) as MySQL cut it (_keys.fit_month)
and created in cal_month when missing (_keys.ensure_month), checked only
when a row is written (an empty batch never touched it in v1). The
mine / material / end-use foreign keys were declared in v1 too: a missing
master row raises v1's 1452 message (_keys.v1_fk_errors), naming the
constraint v1 would have named first (_first_failing).

Two reads cannot follow v1's plan by an ORDER BY alone:
get_iron_ore_despatch_mix is summed in Python along the primary key (a
PARITY SHIM, see there), and get_iron_ore_mines_series is compared as
deep_unordered in tools/repo_oracle.py COMPARE_MODE (v1's join order was a
per-call cost choice; parity_exceptions.md §1b).
"""
from typing import Any, Dict, List

from dbengine import connect
from repo import conn as rc
from repo import version as _ver
from repo import _keys


def _fk(table, n, col, ref):
    return (table, f"{table}_ibfk_{n}", col, ref, col)


_V1_FKS = {
    "fk_mine_prod_mine": _fk("mines_production_monthly", 1, "mine_code", "mines_master"),
    "fk_mine_prod_material": _fk("mines_production_monthly", 2, "material_code", "mine_materials_master"),
    "fk_mine_desp_act_mine": _fk("mines_despatch_actual_monthly", 1, "mine_code", "mines_master"),
    "fk_mine_desp_act_material": _fk("mines_despatch_actual_monthly", 2, "material_code", "mine_materials_master"),
    "fk_mine_desp_act_end_use": _fk("mines_despatch_actual_monthly", 3, "end_use_code", "mine_end_uses_master"),
    "fk_mine_desp_plan_mine": _fk("mines_despatch_plan_monthly", 1, "mine_code", "mines_master"),
    "fk_mine_desp_plan_material": _fk("mines_despatch_plan_monthly", 2, "material_code", "mine_materials_master"),
    "fk_mine_desp_plan_end_use": _fk("mines_despatch_plan_monthly", 3, "end_use_code", "mine_end_uses_master"),
    "fk_mine_booked_act_mine": _fk("mines_booked_qty_actual_monthly", 1, "mine_code", "mines_master"),
    "fk_mine_booked_act_material": _fk("mines_booked_qty_actual_monthly", 2, "material_code",
                                       "mine_materials_master"),
    "fk_mine_booked_plan_mine": _fk("mines_booked_qty_plan_monthly", 1, "mine_code", "mines_master"),
    "fk_mine_booked_plan_material": _fk("mines_booked_qty_plan_monthly", 2, "material_code",
                                        "mine_materials_master"),
}


def _fk_checks(prefix, mine_code, material_code, end_use_code=None):
    """The row's FK checks in v1's constraint order (ibfk_1 mine, ibfk_2
    material, ibfk_3 end use)."""
    out = [(f"fk_mine_{prefix}_mine", "mine", "mine_code", mine_code),
           (f"fk_mine_{prefix}_material", "mine_material", "material_code", material_code)]
    if end_use_code is not None:
        out.append((f"fk_mine_{prefix}_end_use", "mine_end_use", "end_use_code", end_use_code))
    return out


def _first_failing(cur, checks):
    """InnoDB reports a row's first failing constraint in name order, and
    v2's names order differently from v1's: the v2 name of the first master
    missing in v1's order (after a failed INSERT, on the same transaction)."""
    for name, table, col, value in checks:
        if cur.execute(f"SELECT 1 FROM {table} WHERE {col} = %s", (value,)).fetchone() is None:
            return name
    return None


def _month_for_write(cur, stored_month):
    """v1's report_month checks for a row about to be written, then the
    cal_month row (created when missing)."""
    _keys.fits("report_month", stored_month, 7, nullable=False)
    _keys.check_month(stored_month)
    _keys.ensure_month(cur, stored_month, bump=False)


# ── Moved from db.py ─────────────────────────────────────────────────────────

def get_sail_mines_monthly(report_months: List[str]) -> Dict[str, Any]:
    """{report_month: {section: {item: {"actual": v, "plan": v}}}} for the
    given months — used both by page_sail_mines.py (YTD/CPLY roll-up) and
    the data-entry form's pre-fill."""
    conn = connect()
    try:
        cur = conn.cursor()
        out = {m: {} for m in report_months}
        if report_months:
            ph = ",".join(["%s"] * len(report_months))
            cur.execute(
                f"SELECT report_month, section, item, month_actual, month_plan "
                f"FROM sail_mines_monthly WHERE report_month IN ({ph}) ORDER BY report_month, section, item",
                report_months,
            )
            for rm, section, item, act, plan in cur.fetchall():
                out.setdefault(rm, {}).setdefault(section, {})[item] = {"actual": act, "plan": plan}
    finally:
        conn.close()
    return out


def save_sail_mines_monthly(report_month: str, entries: List[Dict[str, Any]]) -> int:
    """Upsert a batch of {section, item, actual, plan} entries for one
    report_month (the data-entry form submits every cell it's editing in
    one call)."""
    stored_month = _keys.fit_month(report_month)
    conn = connect()
    try:
        cur = conn.cursor()
        saved = 0
        _ver.bump(cur)
        for e in entries:
            row = (stored_month, e["section"], e["item"], e.get("actual"), e.get("plan"))
            _month_for_write(cur, stored_month)
            cur.execute("""
                INSERT INTO sail_mines_monthly (report_month, section, item, month_actual, month_plan)
                VALUES (%s, %s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE month_actual = new.month_actual, month_plan = new.month_plan
            """, row)
            saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved


def get_mines_masters() -> Dict[str, Any]:
    """Groups/mines/materials/end-uses (+ the fixed Rail/Road transport
    modes) for the Mines Production & Despatch entry form and reports."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT group_code, group_name FROM mine_group ORDER BY sort_order, group_code")
        groups = [{"group_code": r[0], "group_name": r[1]} for r in cur.fetchall()]
        cur.execute("SELECT mine_code, mine_name, group_code, is_active FROM mine ORDER BY sort_order, mine_code")
        mines = [{"mine_code": r[0], "mine_name": r[1], "group_code": r[2], "is_active": bool(r[3])}
                 for r in cur.fetchall()]
        cur.execute(
            "SELECT material_code, material_name, material_category, has_production, counts_in_total_production "
            "FROM mine_material ORDER BY sort_order, material_code"
        )
        materials = [
            {
                "material_code": r[0], "material_name": r[1], "material_category": r[2],
                "has_production": bool(r[3]), "counts_in_total_production": bool(r[4]),
            }
            for r in cur.fetchall()
        ]
        cur.execute("SELECT end_use_code, end_use_name, tracks_actual FROM mine_end_use "
                    "ORDER BY sort_order, end_use_code")
        end_uses = [{"end_use_code": r[0], "end_use_name": r[1], "tracks_actual": bool(r[2])}
                    for r in cur.fetchall()]
    finally:
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
    for one mine/report_month — used to pre-fill the entry form (see
    repo/mines.py)."""
    conn = connect()
    try:
        cur = conn.cursor()
        key = (report_month, mine_code)

        production = {}
        cur.execute("SELECT material_code, qty_actual, qty_plan FROM mine_production_monthly "
                    "WHERE report_month=%s AND mine_code=%s ORDER BY material_code", key)
        for material_code, actual, plan in cur.fetchall():
            production[material_code] = {"actual": actual, "plan": plan}

        despatch = {}
        cur.execute("SELECT material_code, transport_mode, end_use_code, qty_actual "
                    "FROM mine_despatch_actual_monthly WHERE report_month=%s AND mine_code=%s "
                    "ORDER BY material_code, transport_mode, end_use_code", key)
        for material_code, mode, end_use, actual in cur.fetchall():
            despatch.setdefault(material_code, {}).setdefault(mode, {})[end_use] = {"actual": actual}

        despatch_plan = {}
        cur.execute("SELECT material_code, end_use_code, qty_plan "
                    "FROM mine_despatch_plan_monthly WHERE report_month=%s AND mine_code=%s "
                    "ORDER BY material_code, end_use_code", key)
        for material_code, end_use, plan in cur.fetchall():
            despatch_plan.setdefault(material_code, {})[end_use] = plan

        booked_qty = {}
        cur.execute("SELECT material_code, transport_mode, qty_actual "
                    "FROM mine_booked_qty_actual_monthly WHERE report_month=%s AND mine_code=%s "
                    "ORDER BY material_code, transport_mode", key)
        for material_code, mode, actual in cur.fetchall():
            booked_qty.setdefault(material_code, {})[mode] = {"actual": actual}

        booked_qty_plan = {}
        cur.execute("SELECT material_code, qty_plan FROM mine_booked_qty_plan_monthly "
                    "WHERE report_month=%s AND mine_code=%s ORDER BY material_code", key)
        for material_code, plan in cur.fetchall():
            booked_qty_plan[material_code] = plan
    finally:
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
    """Upsert one mine/month's changed production, despatch Actual / Plan and
    booked-quantity Actual / Plan rows in one call (see repo/mines.py)."""
    booked_qty_entries = booked_qty_entries or []
    booked_qty_plan_entries = booked_qty_plan_entries or []
    stored_month = _keys.fit_month(report_month)
    conn = connect()
    try:
        cur = conn.cursor()
        saved = 0
        _ver.bump(cur)
        current = []        # (v2 constraint, master table, column, value) of the row being written, v1's order
        with _keys.v1_fk_errors(_V1_FKS, lambda: _first_failing(cur, current)):
            for e in production_entries:
                row = (stored_month, mine_code, e["material_code"], e.get("actual"), e.get("plan"))
                current[:] = _fk_checks("prod", mine_code, e["material_code"])
                _month_for_write(cur, stored_month)
                cur.execute("""
                    INSERT INTO mine_production_monthly (report_month, mine_code, material_code, qty_actual, qty_plan)
                    VALUES (%s, %s, %s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE qty_actual = new.qty_actual, qty_plan = new.qty_plan
                """, row)
                saved += 1
            for e in despatch_entries:
                row = (stored_month, mine_code, e["material_code"], e["transport_mode"], e["end_use_code"],
                       e.get("actual"))
                current[:] = _fk_checks("desp_act", mine_code, e["material_code"], e["end_use_code"])
                _month_for_write(cur, stored_month)
                cur.execute("""
                    INSERT INTO mine_despatch_actual_monthly
                        (report_month, mine_code, material_code, transport_mode, end_use_code, qty_actual)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE qty_actual = new.qty_actual
                """, row)
                saved += 1
            for e in despatch_plan_entries:
                row = (stored_month, mine_code, e["material_code"], e["end_use_code"], e.get("plan"))
                current[:] = _fk_checks("desp_plan", mine_code, e["material_code"], e["end_use_code"])
                _month_for_write(cur, stored_month)
                cur.execute("""
                    INSERT INTO mine_despatch_plan_monthly
                        (report_month, mine_code, material_code, end_use_code, qty_plan)
                    VALUES (%s, %s, %s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE qty_plan = new.qty_plan
                """, row)
                saved += 1
            for e in booked_qty_entries:
                row = (stored_month, mine_code, e["material_code"], e["transport_mode"], e.get("actual"))
                current[:] = _fk_checks("booked_act", mine_code, e["material_code"])
                _month_for_write(cur, stored_month)
                cur.execute("""
                    INSERT INTO mine_booked_qty_actual_monthly
                        (report_month, mine_code, material_code, transport_mode, qty_actual)
                    VALUES (%s, %s, %s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE qty_actual = new.qty_actual
                """, row)
                saved += 1
            for e in booked_qty_plan_entries:
                row = (stored_month, mine_code, e["material_code"], e.get("plan"))
                current[:] = _fk_checks("booked_plan", mine_code, e["material_code"])
                _month_for_write(cur, stored_month)
                cur.execute("""
                    INSERT INTO mine_booked_qty_plan_monthly (report_month, mine_code, material_code, qty_plan)
                    VALUES (%s, %s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE qty_plan = new.qty_plan
                """, row)
                saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved


# The group rollups below are v1's code with the v2 table names; the
# statements' row order (GROUP BY report_month, group_code) is explicit.
_PROD_SUMS = """
    SELECT p.report_month, mm.group_code, SUM(p.qty_actual), SUM(p.qty_plan)
    FROM mine_production_monthly p
    JOIN mine mm ON mm.mine_code = p.mine_code
    WHERE p.report_month IN ({ph})
    GROUP BY p.report_month, mm.group_code
    ORDER BY p.report_month, mm.group_code
"""
_PROD_EXTRA = """
    AND ({a}.material_code = 'PELLETS'
         OR ({a}.material_code = 'DUMP_FINES' AND {a}.end_use_code IN ('SALES', 'CAPTIVE', 'UNALLOCATED'))
         OR ({a}.material_code = 'TAILINGS' AND {a}.end_use_code IN ('SALES', 'UNALLOCATED')))
"""


def _group_sums(cur, table, alias, qty, months, extra=""):
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
        SELECT {alias}.report_month, mm.group_code, SUM({alias}.{qty})
        FROM {table} {alias}
        JOIN mine mm ON mm.mine_code = {alias}.mine_code
        WHERE {alias}.report_month IN ({ph}) {extra}
        GROUP BY {alias}.report_month, mm.group_code
        ORDER BY {alias}.report_month, mm.group_code
    """, months)
    return cur.fetchall()


def get_iron_ore_group_rollup_monthly(report_months: List[str]) -> Dict[str, Any]:
    """Group-level (JGoM/OGoM/CGoM) Iron Ore Production & Despatch, rolled
    up from the mine-level tables via mine.group_code, in
    get_sail_mines_monthly's shape (item = group_code). Production = fresh
    Lump+Fines plus the despatch-only components (Dump Fines to SALES /
    CAPTIVE / UNALLOCATED, Tailings to SALES / UNALLOCATED, Pellets of any
    end use); Despatch = every material's despatch Actual / Plan per group
    (see repo/mines.py for the business rules)."""
    conn = connect()
    try:
        cur = conn.cursor()
        out = {m: {"iron_ore_prod": {}, "iron_ore_despatch": {}} for m in report_months}
        if not report_months:
            return out

        prod_actual, prod_plan = {}, {}
        cur.execute(_PROD_SUMS.format(ph=",".join(["%s"] * len(report_months))), report_months)
        for rm, group_code, actual, plan in cur.fetchall():
            prod_actual.setdefault(rm, {})[group_code] = actual
            prod_plan.setdefault(rm, {})[group_code] = plan

        for rm, group_code, actual in _group_sums(cur, "mine_despatch_actual_monthly", "d", "qty_actual",
                                                  report_months, _PROD_EXTRA.format(a="d")):
            prod_actual.setdefault(rm, {})[group_code] = (prod_actual.get(rm, {}).get(group_code) or 0) + (actual or 0)

        for rm, group_code, plan in _group_sums(cur, "mine_despatch_plan_monthly", "pl", "qty_plan",
                                                report_months, _PROD_EXTRA.format(a="pl")):
            prod_plan.setdefault(rm, {})[group_code] = (prod_plan.get(rm, {}).get(group_code) or 0) + (plan or 0)

        for rm in report_months:
            groups = set(prod_actual.get(rm, {})) | set(prod_plan.get(rm, {}))
            for group_code in groups:
                out[rm]["iron_ore_prod"][group_code] = {
                    "actual": prod_actual.get(rm, {}).get(group_code),
                    "plan": prod_plan.get(rm, {}).get(group_code),
                }

        despatch_actual = {}
        for rm, group_code, actual in _group_sums(cur, "mine_despatch_actual_monthly", "d", "qty_actual",
                                                  report_months):
            despatch_actual.setdefault(rm, {})[group_code] = actual

        despatch_plan = {}
        for rm, group_code, plan in _group_sums(cur, "mine_despatch_plan_monthly", "pl", "qty_plan", report_months):
            despatch_plan.setdefault(rm, {})[group_code] = plan

        for rm in report_months:
            groups = set(despatch_actual.get(rm, {})) | set(despatch_plan.get(rm, {}))
            for group_code in groups:
                out[rm]["iron_ore_despatch"][group_code] = {
                    "actual": despatch_actual.get(rm, {}).get(group_code),
                    "plan": despatch_plan.get(rm, {}).get(group_code),
                }
    finally:
        conn.close()
    return out


def get_iron_ore_despatch_mix(report_months: List[str]) -> Dict[str, float]:
    """SAIL-wide Iron Ore despatch actual summed across every mine, material
    and transport mode, grouped by end_use_code: {end_use_code:
    total_qty_actual} in '000 T; an end use with no despatch is omitted."""
    conn = connect()
    try:
        cur = conn.cursor()
        out: Dict[str, float] = {}
        if not report_months:
            return out
        ph = ",".join(["%s"] * len(report_months))
        # PARITY SHIM: v1's GROUP BY end_use_code (no ORDER BY) aggregated in a
        # temporary table along a PRIMARY range scan (EXPLAIN on the v1 data),
        # so the groups came out in first-appearance order along the primary
        # key and each SUM added its rows in that order. The rows are read in
        # that order and summed here the same way (a double accumulator that
        # skips NULLs, NULL when all are NULL), which gives v1's order and bits.
        cur.execute(f"""
            SELECT end_use_code, qty_actual
            FROM mine_despatch_actual_monthly
            WHERE report_month IN ({ph})
            ORDER BY report_month, mine_code, material_code, transport_mode, end_use_code
        """, report_months)
        sums: Dict[str, Any] = {}
        for end_use, qty in cur.fetchall():
            if end_use not in sums:
                sums[end_use] = None
            if qty is not None:
                sums[end_use] = qty if sums[end_use] is None else sums[end_use] + qty
        for end_use, total in sums.items():
            if total is not None:
                out[end_use] = total
    finally:
        conn.close()
    return out


def get_iron_ore_sales_group_rollup_monthly(report_months: List[str]) -> Dict[str, Any]:
    """Group-level Sales of Iron Ore — Booked Quantity (all materials and
    modes) and Despatch to the SALES end use — per group, in
    get_iron_ore_group_rollup_monthly's shape (see repo/mines.py)."""
    conn = connect()
    try:
        cur = conn.cursor()
        out = {m: {"iron_ore_sales": {}, "iron_ore_sales_despatch": {}} for m in report_months}
        if not report_months:
            return out

        booked_actual = {}
        for rm, group_code, actual in _group_sums(cur, "mine_booked_qty_actual_monthly", "b", "qty_actual",
                                                  report_months):
            booked_actual.setdefault(rm, {})[group_code] = actual

        booked_plan = {}
        for rm, group_code, plan in _group_sums(cur, "mine_booked_qty_plan_monthly", "p", "qty_plan", report_months):
            booked_plan.setdefault(rm, {})[group_code] = plan

        for rm in report_months:
            groups = set(booked_actual.get(rm, {})) | set(booked_plan.get(rm, {}))
            for group_code in groups:
                out[rm]["iron_ore_sales"][group_code] = {
                    "actual": booked_actual.get(rm, {}).get(group_code),
                    "plan": booked_plan.get(rm, {}).get(group_code),
                }

        sales_desp_actual = {}
        for rm, group_code, actual in _group_sums(cur, "mine_despatch_actual_monthly", "d", "qty_actual",
                                                  report_months, "AND d.end_use_code = 'SALES'"):
            sales_desp_actual.setdefault(rm, {})[group_code] = actual

        sales_desp_plan = {}
        for rm, group_code, plan in _group_sums(cur, "mine_despatch_plan_monthly", "pl", "qty_plan",
                                                report_months, "AND pl.end_use_code = 'SALES'"):
            sales_desp_plan.setdefault(rm, {})[group_code] = plan

        for rm in report_months:
            groups = set(sales_desp_actual.get(rm, {})) | set(sales_desp_plan.get(rm, {}))
            for group_code in groups:
                out[rm]["iron_ore_sales_despatch"][group_code] = {
                    "actual": sales_desp_actual.get(rm, {}).get(group_code),
                    "plan": sales_desp_plan.get(rm, {}).get(group_code),
                }
    finally:
        conn.close()
    return out


def get_iron_ore_mines_series(report_months: List[str]) -> Dict[str, Any]:
    """Flat month-wise mine-level Iron Ore rows for /reports/iron-ore-mines
    (production / despatch / despatch_plan lists; see repo/mines.py)."""
    conn = connect()
    try:
        cur = conn.cursor()
        out = {"production": [], "despatch": [], "despatch_plan": []}
        if not report_months:
            return out
        ph = ",".join(["%s"] * len(report_months))

        cur.execute(f"""
            SELECT p.report_month, p.mine_code, mm.group_code, p.material_code,
                   p.qty_actual, p.qty_plan
            FROM mine_production_monthly p
            JOIN mine mm ON mm.mine_code = p.mine_code
            WHERE p.report_month IN ({ph})
            ORDER BY p.report_month, p.mine_code, p.material_code
        """, report_months)
        for rm, mine, grp, mat, act, plan in cur.fetchall():
            out["production"].append({
                "report_month": rm, "mine_code": mine, "group_code": grp,
                "material_code": mat, "actual": act, "plan": plan,
            })

        cur.execute(f"""
            SELECT d.report_month, d.mine_code, mm.group_code, d.material_code,
                   d.transport_mode, d.end_use_code, d.qty_actual
            FROM mine_despatch_actual_monthly d
            JOIN mine mm ON mm.mine_code = d.mine_code
            WHERE d.report_month IN ({ph})
            ORDER BY d.report_month, d.mine_code, d.material_code, d.transport_mode, d.end_use_code
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
            FROM mine_despatch_plan_monthly pl
            JOIN mine mm ON mm.mine_code = pl.mine_code
            WHERE pl.report_month IN ({ph})
            ORDER BY pl.report_month, pl.mine_code, pl.material_code, pl.end_use_code
        """, report_months)
        for rm, mine, grp, mat, eu, plan in cur.fetchall():
            out["despatch_plan"].append({
                "report_month": rm, "mine_code": mine, "group_code": grp,
                "material_code": mat, "end_use_code": eu, "plan": plan,
            })
    finally:
        conn.close()
    return out


# ── Named queries ─────────────────────────────────────────────────────────────

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
    cur.execute("SELECT group_code, group_name FROM mine_group ORDER BY sort_order, group_code")
    return cur.fetchall()


def mine_rows(cur):
    """(mine_code, mine_name, group_code, is_active) for every mine, active
    or not, in sort order."""
    cur.execute("SELECT mine_code, mine_name, group_code, is_active FROM mine "
                "ORDER BY sort_order, mine_code")
    return cur.fetchall()


def material_rows(cur):
    """(material_code, material_name) in sort order."""
    cur.execute("SELECT material_code, material_name FROM mine_material ORDER BY sort_order, material_code")
    return cur.fetchall()


def production_rows(cur, months):
    """(mine_code, material_code, report_month, qty_actual, qty_plan)."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT mine_code, material_code, report_month, qty_actual, qty_plan "
                f"FROM mine_production_monthly WHERE report_month IN ({ph}) "
                f"ORDER BY report_month, mine_code, material_code", months)
    return cur.fetchall()


def despatch_actual_rows(cur, months):
    """(mine_code, material_code, end_use_code, report_month, qty_actual),
    one row per transport mode."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT mine_code, material_code, end_use_code, report_month, qty_actual "
                f"FROM mine_despatch_actual_monthly WHERE report_month IN ({ph}) "
                f"ORDER BY report_month, mine_code, material_code, transport_mode, end_use_code", months)
    return cur.fetchall()


def despatch_plan_rows(cur, months):
    """(mine_code, material_code, end_use_code, report_month, qty_plan)."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT mine_code, material_code, end_use_code, report_month, qty_plan "
                f"FROM mine_despatch_plan_monthly WHERE report_month IN ({ph}) "
                f"ORDER BY report_month, mine_code, material_code, end_use_code", months)
    return cur.fetchall()


def booked_actual_rows(cur, months):
    """(mine_code, material_code, report_month, qty_actual), one row per
    transport mode."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT mine_code, material_code, report_month, qty_actual "
                f"FROM mine_booked_qty_actual_monthly WHERE report_month IN ({ph}) "
                f"ORDER BY report_month, mine_code, material_code, transport_mode", months)
    return cur.fetchall()


def booked_plan_rows(cur, months):
    """(mine_code, material_code, report_month, qty_plan)."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT mine_code, material_code, report_month, qty_plan "
                f"FROM mine_booked_qty_plan_monthly WHERE report_month IN ({ph}) "
                f"ORDER BY report_month, mine_code, material_code", months)
    return cur.fetchall()


def sail_rows(cur, months):
    """(section, item, report_month, month_actual, month_plan) from
    sail_mines_monthly."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"SELECT section, item, report_month, month_actual, month_plan "
                f"FROM sail_mines_monthly WHERE report_month IN ({ph}) "
                f"ORDER BY report_month, section, item", months)
    return cur.fetchall()
