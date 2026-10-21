"""Techno repository: techno_data (per plant / unit / month JSON blob) and
techno_plan_fy (per plant / unit / FY plan JSON).

Primitives (the contract later tasks build on):
    blobs(months, plants=None, units=None)
        -> {(month, plant, unit): {"month": {...}, "till_month": {...}}}
    merge_upsert(month, plant, unit, blob, source_file)

The get_/save_/upsert_ functions below were moved verbatim from db.py (and
are re-exported there); the named queries further down used to live inline
in page / api / script modules, moved here verbatim.
"""
import copy
import functools
import json
from typing import Any, Dict, Iterable, List, Optional

import activity_context
import report_context
from dbengine import Row, connect
from report_context import fold
from repo import version as _ver
from repo import conn as rc
from repo.conn import row_dict as _row_dict


def _in(col, vals):
    return f"{col} IN ({', '.join(['%s'] * len(vals))})"


# ── report_context bulk load ────────────────────────────────────────────────
# Inside report_context.activate(), techno_data reads whose month falls in
# the context's window are served from one load of the window's rows
# (ORDER BY report_month, plant, unit: the unit order get_techno_data's
# ORDER BY unit gives). The stored JSON text is kept and parsed on every
# read, so each caller gets fresh objects, as from SQL. Reads on a
# caller-supplied connection (conn=..., writers mid-transaction) always
# use SQL.

def _bulk_load(first, last):
    """{(report_month, fold(plant)): [(plant, unit, techno_json text), ...]}
    in unit order, for first <= report_month <= last."""
    out = {}
    with rc.cursor() as cur:
        cur.execute(
            "SELECT report_month, plant, unit, techno_json FROM techno_data "
            "WHERE report_month BETWEEN %s AND %s ORDER BY report_month, plant, unit",
            (first, last))
        for r in cur.fetchall():
            out.setdefault((r[0], fold(r[1])), []).append((r[1], r[2], r[3]))
    return out


def _bulk(months):
    ctx = report_context.covering(months)
    if ctx is None:
        return None
    return ctx.load("techno", _bulk_load)


def _parse(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


def _units_from_bulk(plant, report_month, unit=None):
    """get_techno_data's {unit: json} from the bulk load, or None when the
    active context does not cover report_month."""
    bulk = _bulk((report_month,))
    if bulk is None:
        return None
    result = {}
    for _plant, u, text in bulk.get((report_month, fold(plant)), ()):
        if unit and fold(u) != fold(unit):
            continue
        result[u] = _parse(text)
    return result


def json_cell(cur, plant, report_month, unit):
    """json_row(), served from the active report_context when it covers
    report_month: (techno_json text,) or None."""
    bulk = _bulk((report_month,))
    if bulk is None:
        return json_row(cur, plant, report_month, unit)
    fu = fold(unit)
    for _plant, u, text in bulk.get((report_month, fold(plant)), ()):
        if fold(u) == fu:
            return (text,)
    return None


def blobs(months: Iterable[str], plants: Iterable[str] | None = None,
          units: Iterable[str] | None = None) -> Dict[tuple, Dict[str, Any]]:
    """{(report_month, plant, unit): techno_json} for the given months, plants
    and units (None = all). Each value is exactly what get_techno_data returns
    for that unit: the stored JSON as-is (a row holding only "month" has no
    "till_month" key; JSON null stays None; ints stay int), or {} when the
    stored JSON does not parse. A missing key means there is no row."""
    months = list(months)
    plants = None if plants is None else list(plants)
    units = None if units is None else list(units)
    if not months or plants == [] or units == []:
        return {}
    bulk = _bulk(months)
    if bulk is not None:
        mset = set(months)
        pset = None if plants is None else {fold(p) for p in plants}
        uset = None if units is None else {fold(u) for u in units}
        return {(m, plant, unit): _parse(text)
                for (m, fp), rows in bulk.items() if m in mset and (pset is None or fp in pset)
                for plant, unit, text in rows if uset is None or fold(unit) in uset}
    where = [_in("report_month", months)]
    params = list(months)
    if plants is not None:
        where.append(_in("plant", plants))
        params += plants
    if units is not None:
        where.append(_in("unit", units))
        params += units
    with rc.cursor() as cur:
        cur.execute(
            "SELECT report_month, plant, unit, techno_json FROM techno_data "
            f"WHERE {' AND '.join(where)}", params)
        rows = cur.fetchall()
    result = {}
    for r in rows:
        try:
            result[(r[0], r[1], r[2])] = json.loads(r[3])
        except (json.JSONDecodeError, TypeError):
            result[(r[0], r[1], r[2])] = {}
    return result


def merge_upsert(month: str, plant: str, unit: str, blob: Dict[str, Any],
                 source_file: str = "") -> None:
    """Merge `blob` ({"month": {...}, "till_month": {...}}) into the stored
    row for (month, plant, unit): read the existing blob, merge in Python
    (new non-null values win, a null keeps the stored value), write back.
    Same semantics as merge_upsert_techno_data, including the derived-param
    recompute and the extraction-log entry."""
    merge_upsert_techno_data(plant, month, unit, blob, source_file)


# ── Moved from db.py ─────────────────────────────────────────────────────

def save_techno_data_from_extraction(plant: str, report_month: str, extracted_rows: List[Dict[str, Any]],
                                     unit: str = "BF_Shop", source_file: str = ""):
    """Save extracted techno data to techno_data table.

    Args:
        plant: Plant name (BSP, DSP, RSP, BSL, ISP)
        report_month: YYYY-MM format
        extracted_rows: List of dicts with keys like {'parameter', 'actual', 'cum_actual', 'key', ...}
        unit: Unit name (default "BF_Shop")
        source_file: Source file name for audit trail
    """
    import json
    from datetime import datetime


    # Build JSON structure from extracted rows
    month_data = {}
    till_month_data = {}

    for row in extracted_rows:
        if row.get('actual') is not None:
            key = row.get('key') or row.get('parameter', '').lower().replace(' ', '_')
            month_data[key] = row['actual']
        if row.get('cum_actual') is not None:
            key = row.get('key') or row.get('parameter', '').lower().replace(' ', '_')
            till_month_data[key] = row['cum_actual']

    techno_json = {
        "month": month_data,
        "till_month": till_month_data
    }

    conn = connect()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    _ver.bump(conn)
    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            techno_json = new.techno_json,
            source_file = new.source_file,
            created_at = new.created_at
    """, (plant, report_month, unit, json.dumps(techno_json), source_file, now))

    conn.commit()
    conn.close()


def save_techno_json(plant: str, report_month: str, unit: str,
                     techno_json: dict, source_file: str = ""):
    """Save a pre-built techno_json dict directly to techno_data table."""
    import json
    from datetime import datetime
    conn = connect()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    _ver.bump(conn)
    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            techno_json = new.techno_json,
            source_file = new.source_file,
            created_at  = new.created_at
    """, (plant, report_month, unit, json.dumps(techno_json), source_file, now))
    conn.commit()
    conn.close()



# ============================================================================
# Techno Data helpers  (techno_data table — all plants)
# ============================================================================

def _raw_upsert_techno_data(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str = '', conn=None):
    """Bare INSERT/UPDATE with no post-save hooks — used by upsert_techno_data
    itself and by _maybe_recompute_derived_params (which must write its
    recomputed values without re-triggering itself).

    This is the one function every techno_data write funnels through
    (extraction, manual entry, SAIL rollup, derived-param recompute), so it's
    the single hook point for activity-log old/new capture across all plant
    techno routers.

    `conn`, if given, is reused instead of opening a fresh connection (and
    left open for the caller to close) — see merge_upsert_techno_data's
    docstring for why. Every other caller passes nothing and gets the
    original open-write-close-per-call behavior, unchanged.

    When `conn` is reused, this does NOT call conn.commit() — the caller
    owns the transaction boundary and must commit explicitly. This matters:
    this MySQL instance has innodb_flush_log_at_trx_commit=1 + sync_binlog=1
    (full fsync-per-commit durability), measured at ~150ms per commit on
    this machine — a bulk save that committed after every single write (as
    this function did unconditionally before) spent most of its ~30 second
    duration on fsyncs, not connection or query overhead. Batching many
    writes under one commit (see /api/techno/insert-months) cuts that
    proportionally without touching the server's durability settings."""
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    old = _row_dict(conn,
        "SELECT techno_json, source_file FROM techno_data WHERE plant=%s AND report_month=%s AND unit=%s",
        (plant, report_month, unit))
    cursor = conn.cursor()
    _ver.bump(conn)
    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE
            techno_json = new.techno_json,
            source_file = new.source_file,
            created_at  = NOW()
    """, (plant, report_month, unit, json.dumps(techno_json), source_file))
    if owns_conn:
        conn.commit()
        conn.close()
    if old is not None:
        old = {**old, "techno_json": json.loads(old["techno_json"])}
    new = {"techno_json": techno_json, "source_file": source_file}
    activity_context.record(f"techno_data/{plant}/{unit}/{report_month}", old, new)


def upsert_techno_data(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str = '', conn=None):
    """Insert or replace techno data for one plant/unit/month.

    SAIL's BF_Shop rollup is no longer auto-refreshed here on every
    contributing plant's save (see api_techno_manual.py's _apply_sail_bf) —
    it's now a read-time fallback used wherever SAIL techno data is
    displayed, computed only when no row already exists in techno_data for
    plant='SAIL'. Call the /sail/calculate endpoint explicitly if you
    deliberately want to publish a calculated SAIL BF_Shop figure into the DB.

    `conn`: see merge_upsert_techno_data's docstring.
    """
    _raw_upsert_techno_data(plant, report_month, unit, techno_json, source_file, conn=conn)
    _maybe_recompute_derived_params(plant, report_month, unit, conn=conn)
    _log_techno_save(plant, report_month, unit, techno_json, source_file, conn=conn)


def _log_techno_save(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str, conn=None) -> None:
    """Audit-log every techno_data save through the extraction_log table, the
    same table /upload's log panel reads — the /data-entry/techno page had no
    equivalent trail before this, since none of its API routers ever called
    log_extraction. Hooked here (the one function every techno save path
    funnels through: extraction inserts, manual entry, and the SAIL BF_Shop
    auto-refresh) so it can't be missed by adding a new save path later."""
    try:
        import db  # db imports this module; bind at call time
        items = len(techno_json.get("month", {})) + len(techno_json.get("till_month", {}))
        db.log_extraction(
            plant=plant,
            report_month=report_month,
            file_name=source_file or "(manual entry)",
            sheet_name=unit,
            source_type="Techno Data",
            items_extracted=items,
            conn=conn,
        )
    except Exception as e:
        print(f"[db] techno save logging failed for {plant}/{report_month}/{unit}: {e}")


# tmi and fuel_rate are physically derived, never independently measured:
#   tmi        = specific_hm_consumption + specific_scrap_consumption
#   fuel_rate  = coke_rate + nut_coke_rate + cdi   (nut_coke_rate may be 0/absent)
# Different extractors historically extracted these straight from whatever a
# source file happened to report under a "TMI"/"Fuel Rate" label — sometimes
# correctly recomputed (RSP's/BSP's excel extractors), sometimes a raw
# extracted figure that could disagree with the app's own HM/Scrap or
# Coke/Nut-Coke/CDI numbers, and sometimes silently absent altogether (BSL,
# ISP's month-end path, DSP's month-end path — DSP's PDF path even LOOKED
# computed but was a no-op since no placeholder row existed to overwrite).
# Recomputing centrally here, on every save, guarantees the stored value
# always matches the plant's own current inputs regardless of which
# extractor/path last touched this unit. Both periods ("month" and
# "till_month") are computed independently as plain sums — valid because
# fuel_rate's inputs (coke_rate/nut_coke_rate/cdi) and tmi's inputs
# (specific_hm_consumption/specific_scrap_consumption) share the same
# production-weighted cumulative basis in techno_cumulative.CUMULATIVE_RULES,
# so the weighted average of a sum equals the sum of the weighted averages —
# the stored till_month values for the inputs are already correct weighted
# cumulatives, so summing them needs no separate re-weighting.
_TMI_INPUT_KEYS = ("specific_hm_consumption", "specific_scrap_consumption")
_FUEL_RATE_INPUT_KEYS = ("coke_rate", "cdi")  # nut_coke_rate optional, defaults to 0


def _maybe_recompute_derived_params(plant: str, report_month: str, unit: str, conn=None) -> None:
    """Recompute tmi/fuel_rate for this (plant, report_month, unit) from
    whatever inputs are currently stored, and overwrite the stored value if
    it differs. Writes via _raw_upsert_techno_data (never upsert_techno_data)
    so this cannot re-trigger itself; safe to call unconditionally after
    every save since it's a no-op once the stored value already matches.

    `conn`: see merge_upsert_techno_data's docstring."""
    try:
        data = get_techno_data(plant, report_month, unit, conn=conn).get(unit, {})
        if not data:
            return
        owns_conn = conn is None
        if owns_conn:
            conn = connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT source_file FROM techno_data WHERE plant=%s AND report_month=%s AND unit=%s",
                (plant, report_month, unit),
            )
            row = cur.fetchone()
            existing_source_file = row[0] if row else ''

            updated = {"month": dict(data.get("month", {})), "till_month": dict(data.get("till_month", {}))}
            changed = False
            for period in ("month", "till_month"):
                d = updated[period]
                hm, scrap = d.get(_TMI_INPUT_KEYS[0]), d.get(_TMI_INPUT_KEYS[1])
                if isinstance(hm, (int, float)) and isinstance(scrap, (int, float)):
                    new_tmi = round(hm + scrap, 4)
                    if d.get("tmi") != new_tmi:
                        d["tmi"] = new_tmi
                        changed = True
                coke, cdi = d.get(_FUEL_RATE_INPUT_KEYS[0]), d.get(_FUEL_RATE_INPUT_KEYS[1])
                if isinstance(coke, (int, float)) and isinstance(cdi, (int, float)):
                    nut_coke = d.get("nut_coke_rate")
                    nut_coke = nut_coke if isinstance(nut_coke, (int, float)) else 0
                    new_fuel = round(coke + nut_coke + cdi, 4)
                    if d.get("fuel_rate") != new_fuel:
                        d["fuel_rate"] = new_fuel
                        changed = True
            if changed:
                # conn is still open here regardless of owns_conn — closing
                # early (before this write) was the bug: _raw_upsert_techno_data
                # sees a non-None conn and assumes the caller owns/commits it,
                # so we must commit ourselves when we're the owner.
                _raw_upsert_techno_data(plant, report_month, unit, updated, source_file=existing_source_file, conn=conn)
                if owns_conn:
                    conn.commit()
        finally:
            if owns_conn:
                conn.close()
    except Exception as e:
        print(f"[db] tmi/fuel_rate recompute failed for {plant}/{report_month}/{unit}: {e}")


# unit names that feed the SAIL BF_Shop rollup — 'BF_Shop' for most plants,
# 'BF-5' for ISP (single-furnace plant, no separate BF_Shop row ever stored).
# No longer auto-refreshed on every contributing plant's save (removed from
# upsert_techno_data above) — see api_techno_manual.py's _apply_sail_bf for
# the explicit calculate-and-store path, and page_techno.py's
# calculate_sail_actuals for the read-time fallback.
_SAIL_BF_UNITS = ("BF_Shop", "BF-5")


def merge_upsert_techno_data(plant: str, report_month: str, unit: str, new_techno_json: Dict, source_file: str = '', conn=None, clear_keys: Optional[Dict[str, list]] = None):
    """Merge new_techno_json into any existing row (non-null values win; existing non-null kept if new value is null).
    Use this when multiple source files contribute different parameters to the same plant/unit/month.

    clear_keys: optional {"month": [key, ...], "till_month": [key, ...]} —
    keys to actually DELETE from the existing stored row before applying
    new_techno_json, for a caller that needs to distinguish "this key
    wasn't part of the request" (leave alone, the normal null-keeps-
    existing rule below) from "this key was explicitly cleared" (remove
    it). Without this, a manual-entry form clearing a field to blank had
    no way to ever delete a previously-saved value — the null-keeps-
    existing rule made the old value silently reappear on next load (see
    api_techno_manual.py's SaveRequest.clear_month_keys/clear_till_keys,
    the only caller that passes this today).

    `conn`: pass an already-open connection to reuse it for this call (and
    every downstream upsert_techno_data/_raw_upsert_techno_data/
    _maybe_recompute_derived_params/_log_techno_save/log_extraction call)
    instead of opening a fresh one — the caller is then responsible for
    closing it. Every one of those functions defaults to `conn=None` and
    opens+closes its own connection exactly as before when not given one,
    so this is purely additive: existing single-call sites are unaffected.
    Added for bulk saves (dozens-to-hundreds of units in one request, e.g.
    /api/techno/insert-months' 12-month "backfill" feature) — each unit-save
    was opening 4-5 separate DB connections (one per SELECT/INSERT across
    this whole call chain), which measured as the actual cause of a ~30
    second request duration for a 12-month save; long enough that the
    Next.js dev server's proxy was resetting the connection before the
    (successfully completing) response could get back to it."""
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT techno_json FROM techno_data WHERE plant=%s AND report_month=%s AND unit=%s",
        [plant, report_month, unit],
    )
    row = cursor.fetchone()
    if owns_conn:
        conn.close()

    if row:
        existing = json.loads(row[0])
        merged: Dict = {}
        for period in ("month", "till_month"):
            base = dict(existing.get(period, {}))
            for k in (clear_keys or {}).get(period, []):
                base.pop(k, None)
            for k, v in new_techno_json.get(period, {}).items():
                if v is not None:
                    base[k] = v        # new non-null overwrites
                # if v is None, keep existing value (base already has it)
            merged[period] = base
    else:
        merged = new_techno_json

    upsert_techno_data(plant, report_month, unit, merged, source_file, conn=(conn if not owns_conn else None))




def enrich_techno_records_with_db(records: List[Dict[str, Any]], plant: str, report_month: str, conn=None) -> List[Dict[str, Any]]:
    """Attach 'db_json' (current techno_data {month:{}, till_month:{}} for the
    same plant/unit/report_month, or empty dicts if none exists yet) to each
    preview record in-place. Used by techno upload preview endpoints so the UI
    can show DB-vs-extracted side by side, for both month and cumulative
    values, before the user confirms the insert.

    `conn`: see merge_upsert_techno_data's docstring — lets a multi-month
    preview (e.g. /api/techno/preview-months) reuse one connection instead
    of opening a fresh one per month."""
    if not records:
        return records
    existing = get_techno_data(plant, report_month, conn=conn)
    for r in records:
        r["db_json"] = existing.get(r.get("unit"), {"month": {}, "till_month": {}})
    return records


def get_techno_data(plant: str, report_month: str, unit: str = None, conn=None) -> Dict:
    """Return {unit: {month: {...}, till_month: {...}}} for a given plant/month.

    `conn`: see merge_upsert_techno_data's docstring. When reusing a passed-in
    connection, its row_factory is saved and restored afterward rather than
    being permanently switched to Row, since a shared connection may
    be reused by other callers (plain tuple rows) later in the same batch.

    Without `conn`, served from the active report_context's bulk load when
    it covers report_month."""
    if conn is None:
        served = _units_from_bulk(plant, report_month, unit)
        if served is not None:
            return served
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    prev_factory = conn.row_factory
    conn.row_factory = Row
    cursor = conn.cursor()

    if unit:
        cursor.execute(
            "SELECT unit, techno_json FROM techno_data WHERE plant = %s AND report_month = %s AND unit = %s",
            [plant, report_month, unit]
        )
    else:
        cursor.execute(
            "SELECT unit, techno_json FROM techno_data WHERE plant = %s AND report_month = %s ORDER BY unit",
            [plant, report_month]
        )

    rows = cursor.fetchall()
    if owns_conn:
        conn.close()
    else:
        conn.row_factory = prev_factory

    result = {}
    for row in rows:
        try:
            result[row['unit']] = json.loads(row['techno_json'])
        except (json.JSONDecodeError, TypeError):
            result[row['unit']] = {}
    return result


def get_sail_techno_actuals(report_month: str) -> Dict[str, Any]:
    """Fetch SAIL consolidated techno actuals (stored, not calculated).
    Returns: {unit: {month: {...}, till_month: {...}}} where unit is typically 'Shop'
    """
    served = _units_from_bulk("SAIL", report_month)
    if served is not None:
        return served
    conn = connect()
    conn.row_factory = Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT unit, techno_json FROM techno_data WHERE plant = 'SAIL' AND report_month = %s ORDER BY unit",
        [report_month]
    )
    rows = cursor.fetchall()
    conn.close()

    result = {}
    for row in rows:
        try:
            result[row['unit']] = json.loads(row['techno_json'])
        except (json.JSONDecodeError, TypeError):
            result[row['unit']] = {}
    return result


def save_sail_techno_actuals(report_month: str, unit: str, techno_json: Dict,
                             calculation_details: Dict = None, source_file: str = ""):
    """Save SAIL consolidated techno actuals with calculation metadata."""
    from datetime import datetime
    now = datetime.now().isoformat()

    conn = connect()
    cursor = conn.cursor()

    _ver.bump(conn)
    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            techno_json = new.techno_json,
            source_file = new.source_file,
            created_at = new.created_at
    """, ("SAIL", report_month, unit, json.dumps(techno_json), source_file, now))

    # Store calculation details separately if provided
    if calculation_details:
        # Store in a JSON comment or separate table (for now embed in the unit name or metadata)
        # Alternative: Create techno_calc_metadata table
        pass

    conn.commit()
    conn.close()


def get_techno_months(plant: str = None) -> List[str]:
    """Return distinct report_month values in techno_data, newest first.
    Optionally filter by plant."""
    conn = connect()
    cursor = conn.cursor()
    if plant:
        cursor.execute(
            "SELECT DISTINCT report_month FROM techno_data WHERE plant = %s ORDER BY report_month DESC",
            [plant]
        )
    else:
        cursor.execute(
            "SELECT DISTINCT report_month FROM techno_data ORDER BY report_month DESC"
        )
    months = [row[0] for row in cursor.fetchall()]
    conn.close()
    return months


# ---------------------------------------------------------------------------
# Techno Plan (Targets) Functions - Uses techno_plan tables
# ---------------------------------------------------------------------------

def get_techno_plan(plant: str, fy: str, unit: str = "") -> Dict[str, Any]:
    """Fetch techno plan data from unified techno_plan_fy table.
    If unit specified, returns that specific unit's data.
    Otherwise returns all units for the plant.

    Cached per (plant, fy, unit) for the process lifetime - report generation
    (page_techno.py) calls this dozens of times per request with the same
    args (once per parameter row), which used to mean a fresh MySQL round
    trip each time. save_techno_plan() clears the cache on write. Returns a
    deep copy so callers can freely mutate their result without corrupting
    the cached entry."""
    return copy.deepcopy(_get_techno_plan_cached(plant, fy, unit))


@functools.lru_cache(maxsize=None)
def _get_techno_plan_cached(plant: str, fy: str, unit: str = "") -> Dict[str, Any]:
    conn = connect()
    conn.row_factory = Row
    cur = conn.cursor()

    if unit:
        cur.execute(
            "SELECT techno_json, is_user_supplied, calculated_json FROM techno_plan_fy WHERE plant_name = %s AND fy = %s AND unit = %s",
            (plant, fy, unit)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            try:
                return {
                    'data': json.loads(row['techno_json']) if row['techno_json'] else {},
                    'is_user_supplied': bool(row['is_user_supplied']),
                    'calculated': json.loads(row['calculated_json']) if row['calculated_json'] else {}
                }
            except json.JSONDecodeError:
                return {'data': {}, 'is_user_supplied': False, 'calculated': {}}
        return {'data': {}, 'is_user_supplied': False, 'calculated': {}}
    else:
        cur.execute(
            "SELECT unit, techno_json, is_user_supplied, calculated_json FROM techno_plan_fy WHERE plant_name = %s AND fy = %s ORDER BY unit",
            (plant, fy)
        )
        rows = cur.fetchall()
        conn.close()
        result = {}
        for row in rows:
            try:
                result[row['unit']] = {
                    'data': json.loads(row['techno_json']) if row['techno_json'] else {},
                    'is_user_supplied': bool(row['is_user_supplied']),
                    'calculated': json.loads(row['calculated_json']) if row['calculated_json'] else {}
                }
            except json.JSONDecodeError:
                result[row['unit']] = {'data': {}, 'is_user_supplied': False, 'calculated': {}}
        return result


def save_techno_plan(plant: str, fy: str, unit: str, techno_json: Dict,
                    is_user_supplied: bool = False, calculated_json: Dict = None,
                    calculation_method: Dict = None, created_by: str = ""):
    """Save or update techno plan data for a plant/unit/FY in unified table.

    This is the only write path into techno_plan_fy (save_techno_plant_plan
    and save_sail_techno_plan both delegate here), so it's the single hook
    point for activity-log old/new capture across the whole techno-plan
    family (/api/techno-plan, /api/techno-plant-plan, /api/sail-techno-plan)."""
    conn = connect()
    old = _row_dict(conn,
        "SELECT techno_json, is_user_supplied, calculated_json, calculation_method FROM techno_plan_fy WHERE plant_name=%s AND unit=%s AND fy=%s",
        (plant, unit, fy))
    cur = conn.cursor()
    from datetime import datetime
    now = datetime.now().isoformat()

    _ver.bump(conn)
    cur.execute("""
        INSERT INTO techno_plan_fy
            (plant_name, unit, fy, techno_json, is_user_supplied, calculated_json, calculation_method, created_by, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            techno_json = new.techno_json,
            is_user_supplied = new.is_user_supplied,
            calculated_json = new.calculated_json,
            calculation_method = new.calculation_method,
            updated_at = new.updated_at
    """, (plant, unit, fy, json.dumps(techno_json), int(is_user_supplied),
          json.dumps(calculated_json or {}), json.dumps(calculation_method or {}), created_by, now, now))
    conn.commit()
    conn.close()

    # This is the only write path into techno_plan_fy (save_techno_plant_plan
    # and save_sail_techno_plan both delegate here) - clear all three read
    # caches so the next request sees the update instead of a stale entry.
    _get_techno_plan_cached.cache_clear()
    _get_techno_plant_plan_cached.cache_clear()
    _get_sail_techno_plan_cached.cache_clear()

    if old is not None:
        for key in ("techno_json", "calculated_json", "calculation_method"):
            if old.get(key):
                old[key] = json.loads(old[key])
    new = {"techno_json": techno_json, "is_user_supplied": bool(is_user_supplied),
           "calculated_json": calculated_json or {}, "calculation_method": calculation_method or {}}
    activity_context.record(f"techno_plan_fy/{plant}/{unit}/{fy}", old, new)


def get_techno_plant_plan(plant: str, fy: str) -> Dict[str, Any]:
    """Fetch plant-level techno plan data (unit='Shop') for a FY.
    Cached - see get_techno_plan() docstring for why and invalidation."""
    return copy.deepcopy(_get_techno_plant_plan_cached(plant, fy))


@functools.lru_cache(maxsize=None)
def _get_techno_plant_plan_cached(plant: str, fy: str) -> Dict[str, Any]:
    conn = connect()
    conn.row_factory = Row
    cur = conn.cursor()
    cur.execute(
        "SELECT techno_json, is_user_supplied, calculated_json, calculation_method FROM techno_plan_fy WHERE plant_name = %s AND fy = %s AND unit = 'Shop'",
        (plant, fy)
    )
    row = cur.fetchone()
    conn.close()

    if row:
        try:
            return {
                'data': json.loads(row['techno_json']) if row['techno_json'] else {},
                'is_user_supplied': bool(row['is_user_supplied']),
                'calculated': json.loads(row['calculated_json']) if row['calculated_json'] else {},
                'calculation_method': json.loads(row['calculation_method']) if row['calculation_method'] else {}
            }
        except json.JSONDecodeError:
            return {'data': {}, 'is_user_supplied': False, 'calculated': {}, 'calculation_method': {}}
    return {'data': {}, 'is_user_supplied': False, 'calculated': {}, 'calculation_method': {}}


def save_techno_plant_plan(plant: str, fy: str, data: Dict, is_user_supplied: bool = False,
                          calculated_json: Dict = None, calculation_method: Dict = None, created_by: str = ""):
    """Save or update plant-level techno plan data (unit='Shop') for a FY."""
    save_techno_plan(plant, fy, 'Shop', data, is_user_supplied, calculated_json, calculation_method, created_by)


def get_sail_techno_plan(fy: str) -> Dict[str, Any]:
    """Fetch SAIL consolidated techno plan data (plant_name='SAIL', unit='Shop') for a FY.
    Cached - see get_techno_plan() docstring for why and invalidation."""
    return copy.deepcopy(_get_sail_techno_plan_cached(fy))


@functools.lru_cache(maxsize=None)
def _get_sail_techno_plan_cached(fy: str) -> Dict[str, Any]:
    conn = connect()
    conn.row_factory = Row
    cur = conn.cursor()
    cur.execute(
        "SELECT techno_json, is_user_supplied, calculated_json, calculation_method FROM techno_plan_fy WHERE plant_name = 'SAIL' AND fy = %s AND unit = 'Shop'",
        (fy,)
    )
    row = cur.fetchone()
    conn.close()

    if row:
        try:
            return {
                'data': json.loads(row['techno_json']) if row['techno_json'] else {},
                'is_user_supplied': bool(row['is_user_supplied']),
                'calculated': json.loads(row['calculated_json']) if row['calculated_json'] else {},
                'calculation_method': json.loads(row['calculation_method']) if row['calculation_method'] else {}
            }
        except json.JSONDecodeError:
            return {'data': {}, 'is_user_supplied': False, 'calculated': {}, 'calculation_method': {}}
    return {'data': {}, 'is_user_supplied': False, 'calculated': {}, 'calculation_method': {}}


def save_sail_techno_plan(fy: str, data: Dict, is_user_supplied: bool = False,
                         calculated_json: Dict = None, calculation_method: Dict = None, created_by: str = ""):
    """Save or update SAIL consolidated techno plan data (plant_name='SAIL', unit='Shop') for a FY."""
    save_techno_plan('SAIL', fy, 'Shop', data, is_user_supplied, calculated_json, calculation_method, created_by)


def list_techno_plan_fys(plant: str = None) -> List[str]:
    """List distinct FYs in techno_plan_fy table, optionally filtered by plant."""
    conn = connect()
    cursor = conn.cursor()

    if plant:
        cursor.execute(
            "SELECT DISTINCT fy FROM techno_plan_fy WHERE plant_name = %s ORDER BY fy DESC",
            (plant,)
        )
    else:
        cursor.execute(
            "SELECT DISTINCT fy FROM techno_plan_fy ORDER BY fy DESC"
        )
    fys = [row[0] for row in cursor.fetchall()]
    conn.close()
    return fys


# ── Named queries moved from page / api / script modules ────────────────
# Cursor-level: each runs on the caller's cursor (so the caller's
# connection, transaction and row type are unchanged) and returns
# fetchall() / fetchone() exactly as the inline code did.

def _ph(vals):
    return ",".join(["%s"] * len(vals))


def units_for_plant_month(cur, plant, report_month):
    """fetchall() of (unit,) for one plant/month, ordered by unit."""
    cur.execute(
        "SELECT unit FROM techno_data WHERE plant = %s AND report_month = %s ORDER BY unit",
        [plant, report_month],
    )
    return cur.fetchall()


def distinct_plants(cur):
    """fetchall() of (plant,), every plant with a techno_data row."""
    cur.execute("SELECT DISTINCT plant FROM techno_data ORDER BY plant")
    return cur.fetchall()


def distinct_report_months(cur):
    """fetchall() of (report_month,), every month with a techno_data row."""
    cur.execute("SELECT DISTINCT report_month FROM techno_data")
    return cur.fetchall()


def distinct_units_for_plant(cur, plant):
    """fetchall() of (unit,) stored for a plant (non-empty units only)."""
    cur.execute(
        "SELECT DISTINCT unit FROM techno_data WHERE plant=%s AND unit IS NOT NULL AND unit != ''",
        (plant,),
    )
    return cur.fetchall()


def bf_shop_rows(cur, report_month):
    """fetchall() of (plant, unit, techno_json) for the BF_Shop / BF-5 units."""
    cur.execute(
        "SELECT plant, unit, techno_json FROM techno_data "
        "WHERE report_month=%s AND unit IN ('BF_Shop', 'BF-5')",
        [report_month],
    )
    return cur.fetchall()


def plant_unit_month_rows(cur, plant, unit, months):
    """fetchall() of (report_month, techno_json) for one plant/unit over months."""
    cur.execute(
        f"SELECT report_month, techno_json FROM techno_data "
        f"WHERE plant=%s AND unit=%s AND report_month IN ({_ph(months)})",
        (plant, unit, *months),
    )
    return cur.fetchall()


def plant_units_month_rows(cur, plant, units, months):
    """fetchall() of (unit, report_month, techno_json) for one plant over
    units x months."""
    cur.execute(
        f"SELECT unit, report_month, techno_json FROM techno_data "
        f"WHERE plant=%s AND unit IN ({_ph(units)}) AND report_month IN ({_ph(months)})",
        (plant, *units, *months),
    )
    return cur.fetchall()


def json_row(cur, plant, report_month, unit):
    """fetchone() of (techno_json,) for one plant/month/unit, or None."""
    cur.execute(
        "SELECT techno_json FROM techno_data WHERE plant=%s AND report_month=%s AND unit=%s",
        (plant, report_month, unit),
    )
    return cur.fetchone()


def all_json(cur):
    """fetchall() of (techno_json,) for every techno_data row."""
    cur.execute("SELECT techno_json FROM techno_data")
    return cur.fetchall()


def rows_for_plants(cur, plants):
    """fetchall() of (plant, report_month, unit, techno_json) for the given
    plants, ordered by plant, report_month."""
    cur.execute(f"""
            SELECT plant, report_month, unit, techno_json
            FROM techno_data
            WHERE plant IN ({_ph(plants)})
            ORDER BY plant, report_month
        """, plants)
    return cur.fetchall()


def sail_rows(cur):
    """fetchall() of (report_month, techno_json) for plant='SAIL', by month."""
    cur.execute("""
                SELECT report_month, techno_json
                FROM techno_data
                WHERE plant = 'SAIL'
                ORDER BY report_month
            """)
    return cur.fetchall()


def sail_unit_rows(cur, unit):
    """fetchall() of (report_month, techno_json) for plant='SAIL' and one
    unit, oldest month first."""
    cur.execute(
        "SELECT report_month, techno_json FROM techno_data "
        "WHERE plant='SAIL' AND unit=%s ORDER BY report_month ASC",
        [unit],
    )
    return cur.fetchall()


def coal_blend_rows(cur, report_month, plants):
    """fetchall() of (plant, unit, techno_json) for the Coal_Consumption /
    General units of the given plants in one month."""
    cur.execute(
        f"SELECT plant, unit, techno_json FROM techno_data "
        f"WHERE report_month=%s AND unit IN ('Coal_Consumption','General') AND plant IN ({_ph(plants)})",
        [report_month, *plants],
    )
    return cur.fetchall()


def plants_month_rows(cur, report_month, plants):
    """fetchall() of (plant, unit, techno_json) for the given plants in one month."""
    cur.execute(
        f"SELECT plant, unit, techno_json FROM techno_data "
        f"WHERE report_month=%s AND plant IN ({_ph(plants)})",
        [report_month, *plants],
    )
    return cur.fetchall()


def unit_plants_months_rows(cur, unit, plants, months):
    """fetchall() of (plant, report_month, techno_json) for one unit over
    plants x months."""
    cur.execute(
        f"SELECT plant, report_month, techno_json FROM techno_data "
        f"WHERE unit=%s AND plant IN ({_ph(plants)}) AND report_month IN ({_ph(months)})",
        [unit, *plants, *months],
    )
    return cur.fetchall()


def month_rows(cur, report_month):
    """fetchall() of (plant, unit, techno_json) for every row of one month."""
    cur.execute("SELECT plant, unit, techno_json FROM techno_data WHERE report_month = %s", [report_month])
    return cur.fetchall()


def rows_for_months(cur, months):
    """fetchall() of (plant, report_month, unit, techno_json) for the months."""
    cur.execute(
        f"SELECT plant, report_month, unit, techno_json FROM techno_data WHERE report_month IN ({_ph(months)})",
        months,
    )
    return cur.fetchall()


def non_sail_rows(cur):
    """fetchall() of (plant, unit, techno_json) for every non-SAIL row."""
    cur.execute("SELECT plant, unit, techno_json FROM techno_data WHERE plant != 'SAIL'")
    return cur.fetchall()


def general_rows_with_source(cur):
    """fetchall() of (plant, report_month, unit, techno_json, source_file)
    for every unit='General' row."""
    cur.execute(
        "SELECT plant, report_month, unit, techno_json, source_file "
        "FROM techno_data WHERE unit = 'General'"
    )
    return cur.fetchall()


def months_signature_row(cur, months):
    """fetchone() of (COUNT(*), MAX(id), MAX(created_at)) over the months."""
    cur.execute(f"SELECT COUNT(*), MAX(id), MAX(created_at) FROM techno_data WHERE report_month IN ({_ph(months)})",
                months)
    return cur.fetchone()


def five_plant_unit_rows(cur, units):
    """fetchall() of (plant, report_month, unit, techno_json) for the 5 ISPs
    and the given units."""
    cur.execute(f"SELECT plant, report_month, unit, techno_json FROM techno_data "
                f"WHERE plant IN ('BSP','DSP','RSP','BSL','ISP') AND unit IN ({_ph(units)})",
                units)
    return cur.fetchall()


def five_plant_first_month_row(cur):
    """fetchone() of (MIN(report_month),) over the 5 ISPs."""
    cur.execute("SELECT MIN(report_month) FROM techno_data WHERE plant IN "
                "('BSP','DSP','RSP','BSL','ISP')")
    return cur.fetchone()


def five_plant_first_months(cur):
    """fetchall() of (plant, MIN(report_month)) for each of the 5 ISPs."""
    cur.execute("SELECT plant, MIN(report_month) FROM techno_data WHERE plant IN "
                "('BSP','DSP','RSP','BSL','ISP') GROUP BY plant")
    return cur.fetchall()


# techno_plan_fy

def plan_json_row(cur, plant, unit, fy):
    """fetchone() of (techno_json,) for one plant/unit/FY plan, or None."""
    cur.execute(
        "SELECT techno_json FROM techno_plan_fy WHERE plant_name=%s AND unit=%s AND fy=%s",
        (plant, unit, fy),
    )
    return cur.fetchone()


def plan_plants_rows(cur, plants, fy, unit):
    """fetchall() of (plant_name, techno_json) for the plants' plan rows."""
    cur.execute(
        f"SELECT plant_name, techno_json FROM techno_plan_fy "
        f"WHERE plant_name IN ({_ph(plants)}) AND fy=%s AND unit=%s",
        (*plants, fy, unit),
    )
    return cur.fetchall()


def plan_rows_for_fy(cur, fy):
    """fetchall() of (plant_name, unit, techno_json) for every plan row of a FY."""
    cur.execute(
        "SELECT plant_name, unit, techno_json FROM techno_plan_fy WHERE fy = %s",
        (fy,)
    )
    return cur.fetchall()


# ── Registry tables (plant_registry.seed_plant_registry,
#    techno_registry.migrate_units; neither is called anywhere, and these
#    tables are not in the MySQL schema) ─────────────────────────────────────

def insert_ignore_plant_unit(cur, plant_code, unit_type, unit_name, display_label, is_shop, sort_order):
    """INSERT IGNORE one plant_units row on the caller's cursor; the caller
    reads cur.rowcount and commits. plant_registry.seed_plant_registry."""
    _ver.bump(cur)
    cur.execute("""
            INSERT IGNORE INTO plant_units
                (plant_code, unit_type, unit_name, display_label, is_shop, is_active, sort_order)
            VALUES (%s, %s, %s, %s, %s, 1, %s)
        """, (plant_code, unit_type, unit_name, display_label, is_shop, sort_order))


def insert_ignore_param_type(cur, unit_type, param_name, unit_of_meas, agg_method, sort_order):
    """INSERT IGNORE one techno_param_types row on the caller's cursor; the
    caller reads cur.rowcount and commits. plant_registry.seed_plant_registry."""
    _ver.bump(cur)
    cur.execute("""
            INSERT IGNORE INTO techno_param_types
                (unit_type, param_name, unit_of_meas, agg_method, sort_order)
            VALUES (%s, %s, %s, %s, %s)
        """, (unit_type, param_name, unit_of_meas, agg_method, sort_order))


def param_master_unit_rows(cur):
    """fetchall() of (param_id, group_code, section, unit) from
    techno_param_master. techno_registry.migrate_units."""
    cur.execute("SELECT param_id, group_code, section, unit FROM techno_param_master")
    return cur.fetchall()


def update_param_master_unit(cur, unit, param_id):
    """Set one techno_param_master row's unit on the caller's cursor; the
    caller commits. techno_registry.migrate_units."""
    _ver.bump(cur)
    cur.execute(
                "UPDATE techno_param_master SET unit=%s WHERE param_id=%s",
                (unit, param_id),
            )
