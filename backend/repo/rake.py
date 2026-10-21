"""Rake detention repository: rake_detention_master (the row registry),
rake_detention_monthly, rake_detention_summary and rake_detention_annual.
Feeds page_rake_detention.py and page_key_parameters.py; written by
/data-entry/rake-detention and the backfill scripts.

The db.py functions moved here verbatim (re-exported from db.py).
"""
from typing import Any, Dict, List, Optional

from dbengine import connect
from repo import version as _ver


# ── "Details of Rakes Detention Plant Wise" (RAKE_DETENTION_* pages) ───────
# Backing store for page_rake_detention.py + /data-entry/rake-detention. See
# scripts/migrate_add_rake_detention.sql / scripts/backfill_rake_detention.py.

_RAKE_MASTER_COLS = (
    "id", "plant", "section", "commodity", "wagon_type", "row_label",
    "is_total", "direction", "freetime_hours", "freetime_effective_from",
    "sort_order", "is_active",
)


def get_rake_detention_master(plants: Optional[List[str]] = None, active_only: bool = True) -> List[dict]:
    """-> list of master rows (dicts, _RAKE_MASTER_COLS keys), ordered for
    display. active_only=False is for the data-entry UI, which also needs
    to show/reactivate a retired wagon type."""
    conn = connect()
    cur = conn.cursor()
    where, args = [], []
    if plants:
        where.append(f"plant IN ({','.join(['%s'] * len(plants))})")
        args.extend(plants)
    if active_only:
        where.append("is_active = 1")
    sql = f"SELECT {','.join(_RAKE_MASTER_COLS)} FROM rake_detention_master"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY plant, section, sort_order, id"
    cur.execute(sql, args)
    rows = [dict(zip(_RAKE_MASTER_COLS, r)) for r in cur.fetchall()]
    conn.close()
    return _group_rake_master_rows(rows)


def _group_rake_master_rows(rows: List[dict]) -> List[dict]:
    """Regroups rows so every row sharing the same (plant, section,
    commodity) is always contiguous, at that commodity's first-seen slot
    within its section — commodity grouping, not sort_order alone, is
    what the printed report's rowspan-merged Commodity column (see
    rake_detention_detail.html) actually depends on, and a bare
    "ORDER BY sort_order" can't guarantee that on its own: a newly added
    row can only be given a sort_order that's safely between its OWN
    commodity's neighbours, never one that's also guaranteed to fall
    outside every OTHER commodity's own range in the same section —
    collide with the very next commodity's own starting value (confirmed
    by a real add: e.g. Ind.Coking Coal's rows 1-3, Imp.Coking Coal's rows
    4-6 — a new Ind.Coking Coal row given sort_order 4 lands ON Imp.Coking
    Coal's own first row, splitting Imp.Coking Coal's group in two on the
    printed page) and there's no sort_order value that avoids every
    possible future collision like that. Grouping by the commodity value
    itself has no such blind spot, and self-heals any row that already
    landed in the wrong spot for this same reason (its commodity string
    still matches, so it rejoins that group here regardless of its own
    sort_order). Sort_order still decides ordering WITHIN one commodity's
    own rows (e.g. BSP Inward's Ind.Coking Coal group still prints
    BOXN/BOST/BOSM, its own original order, not alphabetical); is_total
    rows always sort last within their section, same as before."""
    section_buckets = {}  # (plant, section) -> {"totals": [...], "by_commodity": {commodity: [rows]}}
    for r in rows:
        bucket = section_buckets.setdefault((r["plant"], r["section"]), {"totals": [], "by_commodity": {}})
        if r["is_total"]:
            bucket["totals"].append(r)
        else:
            bucket["by_commodity"].setdefault(r["commodity"], []).append(r)

    out = []
    for bucket in section_buckets.values():
        for commodity_rows in bucket["by_commodity"].values():
            out.extend(commodity_rows)
        out.extend(bucket["totals"])
    return out


def save_rake_detention_master_row(row: Dict[str, Any]) -> int:
    """Insert (row.get('id') falsy) or update (id given) one master row.
    Returns the row's id. This is the "add a wagon type later" provision —
    called from /data-entry/rake-detention, never needs a code change."""
    conn = connect()
    cur = conn.cursor()
    if row.get("id"):
        cur.execute("""
            UPDATE rake_detention_master SET
                plant = %s, section = %s, commodity = %s, wagon_type = %s, row_label = %s,
                is_total = %s, direction = %s, freetime_hours = %s, freetime_effective_from = %s,
                sort_order = %s, is_active = %s
            WHERE id = %s
        """, (
            row["plant"], row["section"], row.get("commodity"), row.get("wagon_type"), row["row_label"],
            int(bool(row.get("is_total"))), row.get("direction"), row.get("freetime_hours"),
            row.get("freetime_effective_from"), int(row.get("sort_order") or 0),
            int(bool(row.get("is_active", True))), row["id"],
        ))
        row_id = row["id"]
    else:
        cur.execute("""
            INSERT INTO rake_detention_master
                (plant, section, commodity, wagon_type, row_label, is_total, direction,
                 freetime_hours, freetime_effective_from, sort_order, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row["plant"], row["section"], row.get("commodity"), row.get("wagon_type"), row["row_label"],
            int(bool(row.get("is_total"))), row.get("direction"), row.get("freetime_hours"),
            row.get("freetime_effective_from"), int(row.get("sort_order") or 0),
            int(bool(row.get("is_active", True))),
        ))
        row_id = cur.lastrowid
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return row_id


def deactivate_rake_detention_master_row(master_id: int) -> None:
    """Retires a wagon type without deleting its history (is_active=0 —
    get_rake_detention_master's default active_only=True then skips it on
    future months, but every already-saved rake_detention_monthly value
    stays intact)."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("UPDATE rake_detention_master SET is_active = 0 WHERE id = %s", (master_id,))
    _ver.bump(conn)
    conn.commit()
    conn.close()


def get_rake_detention_monthly(report_month: str, master_ids: Optional[List[int]] = None) -> Dict[int, float]:
    """-> {master_id: value_hours} for one report_month."""
    conn = connect()
    cur = conn.cursor()
    sql = "SELECT master_id, value_hours FROM rake_detention_monthly WHERE report_month = %s"
    args = [report_month]
    if master_ids:
        sql += f" AND master_id IN ({','.join(['%s'] * len(master_ids))})"
        args.extend(master_ids)
    cur.execute(sql, args)
    out = {mid: val for mid, val in cur.fetchall()}
    conn.close()
    return out


def save_rake_detention_monthly(report_month: str, rows: List[Dict[str, Any]]) -> int:
    """Upsert rake_detention_monthly rows: {master_id, value_hours} for report_month."""
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO rake_detention_monthly (report_month, master_id, value_hours)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value_hours = new.value_hours
        """, (report_month, r["master_id"], r.get("value_hours")))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return len(rows)


def get_rake_detention_trend(master_ids: List[int]) -> Dict[int, Dict[str, float]]:
    """-> {master_id: {report_month: value_hours}} across every month on
    record — used for page 4's multi-year "Overall Wagon" trend, where the
    granular per-plant "Overall Wagon" master row is the only one that
    realistically has years of history behind it."""
    conn = connect()
    cur = conn.cursor()
    out: Dict[int, Dict[str, float]] = {mid: {} for mid in master_ids}
    if master_ids:
        ph = ",".join(["%s"] * len(master_ids))
        cur.execute(
            f"SELECT master_id, report_month, value_hours FROM rake_detention_monthly "
            f"WHERE master_id IN ({ph})", master_ids,
        )
        for mid, rm, val in cur.fetchall():
            out.setdefault(mid, {})[rm] = val
    conn.close()
    return out


def get_rake_detention_summary(report_month: str) -> Dict[str, Dict[str, float]]:
    """-> {period_row: {plant: value}} for one 'UPTO <report_month>' snapshot."""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT period_row, plant, value FROM rake_detention_summary WHERE report_month = %s",
        (report_month,),
    )
    out: Dict[str, Dict[str, float]] = {}
    for period_row, plant, value in cur.fetchall():
        out.setdefault(period_row, {})[plant] = value
    conn.close()
    return out


def save_rake_detention_summary(report_month: str, rows: List[Dict[str, Any]]) -> int:
    """Upsert rake_detention_summary rows: {period_row, plant, value} for report_month."""
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO rake_detention_summary (report_month, period_row, plant, value)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value = new.value
        """, (report_month, r["period_row"], r["plant"], r.get("value")))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return len(rows)


def get_rake_detention_annual(plants: List[str], fys: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {plant: {financial_year: avg_hours}} — page 4's per-FY "APR-MAR" column."""
    conn = connect()
    cur = conn.cursor()
    out = {p: {} for p in plants}
    if plants and fys:
        ph_p, ph_f = ",".join(["%s"] * len(plants)), ",".join(["%s"] * len(fys))
        cur.execute(
            f"SELECT plant, financial_year, avg_hours FROM rake_detention_annual "
            f"WHERE plant IN ({ph_p}) AND financial_year IN ({ph_f})", plants + fys,
        )
        for plant, fy, val in cur.fetchall():
            out.setdefault(plant, {})[fy] = val
    conn.close()
    return out


def save_rake_detention_annual(rows: List[Dict[str, Any]]) -> int:
    """Upsert rake_detention_annual rows: {plant, financial_year, avg_hours}."""
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO rake_detention_annual (plant, financial_year, avg_hours)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE avg_hours = new.avg_hours
        """, (r["plant"], r["financial_year"], r.get("avg_hours")))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return len(rows)

