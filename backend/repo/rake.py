"""Rake detention repository on the v2 schema: rake_detention_master (the
row registry), rake_detention_monthly, rake_detention_summary and
rake_detention_annual (v1 plant -> plant_code, financial_year -> fy).

Same public names, signatures, return shapes and exceptions as
repo/rake.py. freetime_effective_from stays CHAR(10) text, so '' and NULL
stay distinct, as in v1.

ORDER. get_rake_detention_master keeps v1's ORDER BY. The other reads had
none; their v1 order came from the primary key (or, for the trend, v1's
master_id index plus the primary key), which fixes the insertion order of
the returned dicts, so it is explicit here: monthly by master_id, trend
by (master_id, report_month), summary by (period_row, plant), annual by
(plant, fy), each under the same ai_ci collation as v1.

WRITES. One bump per call, first (skipped in a dry run), as v1 (also for an
empty batch). The renamed columns are checked against v1's limits where
v1's statement would have failed, raising v1's errors (1048 / 1406 naming
plant / financial_year); the other columns keep v1's names and widths,
so MySQL raises v1's own error for them. Months and FYs are cut to CHAR(7)
as MySQL cut them (_keys.fit_month / fit_fy); missing cal_month / plant
rows are created (_keys.ensure_month / ensure_plant). rake_detention_monthly
.master_id was a declared FK in v1 too: a missing master raises v1's 1452
message (_keys.v1_fk_errors).
"""
from typing import Any, Dict, List, Optional

import activity_context
from dbengine import connect
from repo import version as _ver
from repo import _keys

_RAKE_MASTER_COLS = (
    "id", "plant", "section", "commodity", "wagon_type", "row_label",
    "is_total", "direction", "freetime_hours", "freetime_effective_from",
    "sort_order", "is_active",
)
_SELECT_COLS = ",".join("plant_code" if c == "plant" else c for c in _RAKE_MASTER_COLS)
_V1_FKS = {"fk_rake_monthly_master": ("rake_detention_monthly", "rake_detention_monthly_ibfk_1", "master_id",
                                      "rake_detention_master", "id")}


def get_rake_detention_master(plants: Optional[List[str]] = None, active_only: bool = True) -> List[dict]:
    """-> list of master rows (dicts, _RAKE_MASTER_COLS keys), ordered for
    display. active_only=False is for the data-entry UI, which also needs
    to show/reactivate a retired wagon type."""
    conn = connect()
    try:
        cur = conn.cursor()
        where, args = [], []
        if plants:
            where.append(f"plant_code IN ({','.join(['%s'] * len(plants))})")
            args.extend(plants)
        if active_only:
            where.append("is_active = 1")
        sql = f"SELECT {_SELECT_COLS} FROM rake_detention_master"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY plant_code, section, sort_order, id"
        cur.execute(sql, args)
        rows = [dict(zip(_RAKE_MASTER_COLS, r)) for r in cur.fetchall()]
    finally:
        conn.close()
    return _group_rake_master_rows(rows)


def _group_rake_master_rows(rows: List[dict]) -> List[dict]:
    """Regroups rows so every row sharing the same (plant, section,
    commodity) is contiguous, at that commodity's first-seen slot within
    its section; is_total rows last within their section (v1's rule, see
    repo/rake.py)."""
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
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        plant = row["plant"]
        values = (
            plant, row["section"], row.get("commodity"), row.get("wagon_type"), row["row_label"],
            int(bool(row.get("is_total"))), row.get("direction"), row.get("freetime_hours"),
            row.get("freetime_effective_from"), int(row.get("sort_order") or 0),
            int(bool(row.get("is_active", True))),
        )
        _keys.fits("plant", plant, 8, nullable=False)      # v1's first column (UPDATE and INSERT)
        _keys.ensure_plant(cur, plant, bump=False)
        if row.get("id"):
            cur.execute("""
                UPDATE rake_detention_master SET
                    plant_code = %s, section = %s, commodity = %s, wagon_type = %s, row_label = %s,
                    is_total = %s, direction = %s, freetime_hours = %s, freetime_effective_from = %s,
                    sort_order = %s, is_active = %s
                WHERE id = %s
            """, values + (row["id"],))
            row_id = row["id"]
        else:
            cur.execute("""
                INSERT INTO rake_detention_master
                    (plant_code, section, commodity, wagon_type, row_label, is_total, direction,
                     freetime_hours, freetime_effective_from, sort_order, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, values)
            row_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return row_id


def deactivate_rake_detention_master_row(master_id: int) -> None:
    """Retires a wagon type without deleting its history (is_active=0; its
    saved rake_detention_monthly values stay intact)."""
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        cur.execute("UPDATE rake_detention_master SET is_active = 0 WHERE id = %s", (master_id,))
        conn.commit()
    finally:
        conn.close()


def get_rake_detention_monthly(report_month: str, master_ids: Optional[List[int]] = None) -> Dict[int, float]:
    """-> {master_id: value_hours} for one report_month."""
    conn = connect()
    try:
        cur = conn.cursor()
        sql = "SELECT master_id, value_hours FROM rake_detention_monthly WHERE report_month = %s"
        args = [report_month]
        if master_ids:
            sql += f" AND master_id IN ({','.join(['%s'] * len(master_ids))})"
            args.extend(master_ids)
        cur.execute(sql + " ORDER BY master_id", args)
        out = {mid: val for mid, val in cur.fetchall()}
    finally:
        conn.close()
    return out


def save_rake_detention_monthly(report_month: str, rows: List[Dict[str, Any]]) -> int:
    """Upsert rake_detention_monthly rows: {master_id, value_hours} for report_month."""
    stored_month = _keys.fit_month(report_month)
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        for r in rows:
            master_id, value = r["master_id"], r.get("value_hours")
            _keys.fits("report_month", stored_month, 7, nullable=False)
            _keys.check_month(stored_month)
            _keys.ensure_month(cur, stored_month, bump=False)
            with _keys.v1_fk_errors(_V1_FKS):
                cur.execute("""
                    INSERT INTO rake_detention_monthly (report_month, master_id, value_hours)
                    VALUES (%s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE value_hours = new.value_hours
                """, (stored_month, master_id, value))
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def get_rake_detention_trend(master_ids: List[int]) -> Dict[int, Dict[str, float]]:
    """-> {master_id: {report_month: value_hours}} across every month on
    record (page 4's multi-year "Overall Wagon" trend)."""
    conn = connect()
    try:
        cur = conn.cursor()
        out: Dict[int, Dict[str, float]] = {mid: {} for mid in master_ids}
        if master_ids:
            ph = ",".join(["%s"] * len(master_ids))
            cur.execute(
                f"SELECT master_id, report_month, value_hours FROM rake_detention_monthly "
                f"WHERE master_id IN ({ph}) ORDER BY master_id, report_month", master_ids,
            )
            for mid, rm, val in cur.fetchall():
                out.setdefault(mid, {})[rm] = val
    finally:
        conn.close()
    return out


def get_rake_detention_summary(report_month: str) -> Dict[str, Dict[str, float]]:
    """-> {period_row: {plant: value}} for one 'UPTO <report_month>' snapshot."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT period_row, plant_code, value FROM rake_detention_summary WHERE report_month = %s "
            "ORDER BY period_row, plant_code",
            (report_month,),
        )
        out: Dict[str, Dict[str, float]] = {}
        for period_row, plant, value in cur.fetchall():
            out.setdefault(period_row, {})[plant] = value
    finally:
        conn.close()
    return out


def save_rake_detention_summary(report_month: str, rows: List[Dict[str, Any]]) -> int:
    """Upsert rake_detention_summary rows: {period_row, plant, value} for report_month."""
    stored_month = _keys.fit_month(report_month)
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        for r in rows:
            period_row, plant, value = r["period_row"], r["plant"], r.get("value")
            _keys.fits("report_month", stored_month, 7, nullable=False)
            _keys.fits("period_row", period_row, 24, nullable=False)
            _keys.fits("plant", plant, 8, nullable=False)
            _keys.check_month(stored_month)
            _keys.ensure_month(cur, stored_month, bump=False)
            _keys.ensure_plant(cur, plant, bump=False)
            cur.execute("""
                INSERT INTO rake_detention_summary (report_month, period_row, plant_code, value)
                VALUES (%s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE value = new.value
            """, (stored_month, period_row, plant, value))
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def get_rake_detention_annual(plants: List[str], fys: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {plant: {financial_year: avg_hours}} — page 4's per-FY "APR-MAR" column."""
    conn = connect()
    try:
        cur = conn.cursor()
        out = {p: {} for p in plants}
        if plants and fys:
            ph_p, ph_f = ",".join(["%s"] * len(plants)), ",".join(["%s"] * len(fys))
            cur.execute(
                f"SELECT plant_code, fy, avg_hours FROM rake_detention_annual "
                f"WHERE plant_code IN ({ph_p}) AND fy IN ({ph_f}) ORDER BY plant_code, fy", plants + fys,
            )
            for plant, fy, val in cur.fetchall():
                out.setdefault(plant, {})[fy] = val
    finally:
        conn.close()
    return out


def save_rake_detention_annual(rows: List[Dict[str, Any]]) -> int:
    """Upsert rake_detention_annual rows: {plant, financial_year, avg_hours}."""
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        for r in rows:
            plant, fy, value = r["plant"], _keys.fit_fy(r["financial_year"]), r.get("avg_hours")
            _keys.fits("plant", plant, 8, nullable=False)
            _keys.fits("financial_year", fy, 7, nullable=False)
            _keys.ensure_plant(cur, plant, bump=False)
            cur.execute("""
                INSERT INTO rake_detention_annual (plant_code, fy, avg_hours)
                VALUES (%s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE avg_hours = new.avg_hours
            """, (plant, fy, value))
        conn.commit()
    finally:
        conn.close()
    return len(rows)


# ── Rake despatch (Despatch Summary Report; api_rake_despatch) ──────────────
# v2-only tables: rake_despatch_upload / _type / _history / _position,
# rake_slab_despatch, rake_export_despatch. Plant rows only; SAIL is summed
# by the caller.

def _dict_rows(cur, sql, args=()):
    cur.execute(sql, args)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _read(sql, args=()):
    conn = connect()
    try:
        return _dict_rows(conn.cursor(), sql, args)
    finally:
        conn.close()


def rake_despatch_months() -> List[dict]:
    """Uploaded months, newest first: [{report_month, as_on, source_file, created_at, created_by}]."""
    return _read("SELECT report_month, as_on, source_file, created_at, created_by"
                 " FROM rake_despatch_upload ORDER BY report_month DESC")


def rake_despatch_upload(report_month: str) -> Optional[dict]:
    """The month's upload row ({report_month, as_on, slab_note, source_file, created_at, created_by}) or None."""
    rows = _read("SELECT report_month, as_on, slab_note, source_file, created_at, created_by"
                 " FROM rake_despatch_upload WHERE report_month = %s", (report_month,))
    return rows[0] if rows else None


def rake_despatch_position_rows(report_month: str) -> List[dict]:
    """[{plant_code, metric, value}] for the month's page-1 position."""
    return _read("SELECT plant_code, metric, value FROM rake_despatch_position"
                 " WHERE report_month = %s ORDER BY plant_code, metric", (report_month,))


def rake_slab_despatch_rows(report_month: str) -> List[dict]:
    """[{from_plant_code, to_plant_code, rakes, qty_mt}] for the month."""
    return _read("SELECT from_plant_code, to_plant_code, rakes, qty_mt FROM rake_slab_despatch"
                 " WHERE report_month = %s ORDER BY from_plant_code, to_plant_code", (report_month,))


def rake_export_despatch_rows(report_month: str) -> List[dict]:
    """[{destination, plant_code, dest_group, sort_order, prog, actual}] for the month, printed order."""
    return _read("SELECT destination, plant_code, dest_group, sort_order, prog, actual"
                 " FROM rake_export_despatch WHERE report_month = %s ORDER BY sort_order, plant_code",
                 (report_month,))


def rake_despatch_type_rows(first_month: str, last_month: str) -> List[dict]:
    """[{report_month, plant_code, wagon_type, rakes}] for first_month..last_month."""
    return _read("SELECT report_month, plant_code, wagon_type, rakes FROM rake_despatch_type"
                 " WHERE report_month BETWEEN %s AND %s ORDER BY report_month, plant_code, wagon_type",
                 (first_month, last_month))


def rake_despatch_history_rows(first_month: str, last_month: str) -> List[dict]:
    """[{report_month, plant_code, rakes}] (page-5 plant totals) for first_month..last_month."""
    return _read("SELECT report_month, plant_code, rakes FROM rake_despatch_history"
                 " WHERE report_month BETWEEN %s AND %s ORDER BY report_month, plant_code",
                 (first_month, last_month))


def save_rake_despatch(data: Dict[str, Any], source_file: Optional[str], user: Optional[str]) -> dict:
    """Save one Despatch Summary Report (pdf_extractor_rake_despatch.extract's
    shape) in one transaction. The month's page-1 position, slab and export
    rows are replaced; wagon-type rows are replaced for every month the file
    carries; page-5 history is upserted month by month.
    -> {"report_month", "type_months", "history_months"}."""
    month = _keys.fit_month(data["report_month"])
    _keys.check_month(month)
    _keys.fits("slab_note", data.get("slab_note"), 255)
    _keys.fits("source_file", source_file, 255)
    _keys.fits("created_by", user, 190)
    type_months = sorted(data.get("types") or {})
    history_months = sorted(data.get("history") or {})
    for m in type_months + history_months:
        _keys.check_month(m)
    for m in type_months:
        for plant, by_type in data["types"][m].items():
            _keys.fits("plant_code", plant, 8, nullable=False)
            for wagon in by_type:
                _keys.fits("wagon_type", wagon, 16, nullable=False)
    for e in data.get("export") or []:
        _keys.fits("destination", e["destination"], 48, nullable=False)
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        for m in sorted({month, *type_months, *history_months}):
            _keys.ensure_month(cur, m, bump=False)
        cur.execute("INSERT INTO rake_despatch_upload (report_month, as_on, slab_note, source_file, created_at,"
                    " created_by) VALUES (%s, %s, %s, %s, NOW(6), %s) AS new ON DUPLICATE KEY UPDATE"
                    " as_on = new.as_on, slab_note = new.slab_note, source_file = new.source_file,"
                    " created_at = new.created_at, created_by = new.created_by",
                    (month, data["as_on"], data.get("slab_note"), source_file, user))
        for table in ("rake_despatch_position", "rake_slab_despatch", "rake_export_despatch"):
            cur.execute(f"DELETE FROM {table} WHERE report_month = %s", (month,))
        pos = [(month, plant, metric, value)
               for plant, metrics in (data.get("position") or {}).items()
               for metric, value in metrics.items()]
        if pos:
            cur.executemany("INSERT INTO rake_despatch_position (report_month, plant_code, metric, value)"
                            " VALUES (%s, %s, %s, %s)", pos)
        slab = [(month, s["from"], s["to"], s["rakes"], s.get("qty_mt")) for s in data.get("slab") or []]
        if slab:
            cur.executemany("INSERT INTO rake_slab_despatch (report_month, from_plant_code, to_plant_code, rakes,"
                            " qty_mt) VALUES (%s, %s, %s, %s, %s)", slab)
        export = [(month, e["destination"], e["plant"], e["group"], e["sort_order"], e.get("prog"), e.get("actual"))
                  for e in data.get("export") or []]
        if export:
            cur.executemany("INSERT INTO rake_export_despatch (report_month, destination, plant_code, dest_group,"
                            " sort_order, prog, actual) VALUES (%s, %s, %s, %s, %s, %s, %s)", export)
        for m in type_months:
            cur.execute("DELETE FROM rake_despatch_type WHERE report_month = %s", (m,))
            rows = [(m, plant, wagon, rakes) for plant, by_type in data["types"][m].items()
                    for wagon, rakes in by_type.items()]
            if rows:
                cur.executemany("INSERT INTO rake_despatch_type (report_month, plant_code, wagon_type, rakes)"
                                " VALUES (%s, %s, %s, %s)", rows)
        hist = [(m, plant, rakes) for m in history_months for plant, rakes in data["history"][m].items()]
        if hist:
            cur.executemany("INSERT INTO rake_despatch_history (report_month, plant_code, rakes) VALUES (%s, %s, %s)"
                            " AS new ON DUPLICATE KEY UPDATE rakes = new.rakes", hist)
        conn.commit()
    finally:
        conn.close()
    activity_context.record(f"rake_despatch/{month}", None,
                            {"source_file": source_file, "type_months": len(type_months),
                             "history_months": len(history_months)})
    return {"report_month": month, "type_months": type_months, "history_months": history_months}
