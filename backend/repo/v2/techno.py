"""Techno repository on the v2 schema (techno_upload + techno_value +
plant_unit, and techno_plan_fy).

Same public names, signatures, return shapes and exceptions as
repo/techno.py (v1: techno_data (id, plant, report_month, unit, techno_json
JSON, source_file, created_at VARCHAR) and techno_plan_fy (plant_name, unit,
fy, ...)). v2 holds a v1 blob as one techno_upload row (has_month /
has_till_month, source_file, created_at + created_at_iso) plus one
techno_value row per leaf (repo.v2codec encode_techno / decode_techno);
units are plant_unit rows (unit_id).

BLOBS COME BACK AS v1's TEXT. _TEXT rebuilds the JSON text v1's
techno_json column handed back, by MySQL itself: JSON_OBJECTAGG /
JSON_OBJECT over the leaves (int leaves cast to SIGNED, float leaves to a
JSON double, raw leaves - strings, objects, bools, explicit nulls, -0.0,
ints beyond 2^53 - as stored), so it is MySQL's own serialisation of the
same JSON value: byte for byte what v1 stored (checked on all 5,273 blobs
of the rehearsal copy), keys in the MySQL-JSON normalised order that
TECHNO_LEAF_ORDER_BY describes. The cursor helpers, the report_context bulk
load and json_cell return that text; the dict reads (blobs,
get_techno_data, get_sail_techno_actuals) json.loads it as v1 did, so every
leaf keeps its type (5 int, 5.0 float). The write paths' locking read of
one stored blob (merge, recompute, activity-log old state) decodes its leaf
rows with v2codec.decode_techno (same dict; ORDER BY TECHNO_LEAF_ORDER_BY).

ROW ORDER. techno_upload.seq is v1's techno_data.id (loaded by the
migration, AUTO_INCREMENT after it, kept by an upsert as v1 kept id).
Reads v1 served in id order (idx_techno_month (report_month, id) or a
PRIMARY scan) ORDER BY seq; months_signature_row reads MAX(seq). Reads
with a v1 ORDER BY keep it (unit compared under ai_ci, as v1); reads v1
served through uq_techno (plant, report_month, unit) have an explicit ORDER
BY reproducing that index order.

UNITS. plant_unit.unit_code is utf8mb4_0900_bin: each case variant is its
own unit row with its exact text, as v1 kept the caller's spelling per row.
Reads match `pu.unit_code COLLATE utf8mb4_0900_ai_ci` (_UC) or fold(), as
v1's ai_ci column did. Writes follow the production rule (repo/v2/_keys.py):
after the bump, a locking ai_ci lookup of the stored row of (month, plant,
unit); when there is one, its unit (and plant spelling) is reused, as v1's
ON DUPLICATE KEY UPDATE kept the stored key; otherwise the unit is resolved
by the EXACT string and created when missing (unit_type NULL). The plans
(techno_plan_fy, v1 key (plant_name, unit, fy) under ai_ci) follow the
same rule per (plant, fy). A unit longer than v1's VARCHAR(32) raises v1's
DataError 1406 before anything is written.

WRITES (every write bumps data_version first; none in a dry run)
  - created_at: the NOW() writer (_raw_upsert_techno_data, so upsert /
    merge_upsert / the recompute) stores NOW() with created_at_iso = 0
    (renders 'YYYY-MM-DD HH:MM:SS'); the datetime.now().isoformat() writers
    (save_techno_data_from_extraction, save_techno_json,
    save_sail_techno_actuals) store that datetime (microseconds kept) with
    created_at_iso = 1 (renders as isoformat()), per v2codec TS_FLAGGED.
  - merge_upsert_techno_data is one transaction: bump, locking read of the
    stored blob, the v1 merge in Python, then the write chain (raw write,
    tmi / fuel_rate recompute, extraction log) on the same connection.
  - Months / plants: repo/v2/_keys.py ensure_month / ensure_plant.
"""
import copy
import functools
import itertools
import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import pymysql

import activity_context
import report_context
from dbengine import connect
from report_context import fold
from repo import version as _ver
from repo import conn as rc
from repo.v2 import _keys
from repo.v2.production import _row_like
from repo.v2codec import TECHNO_LEAF_ORDER_BY, decode_techno, encode_techno, render_ts_flagged

_V1_UNIT_LEN = 32          # v1 techno_data.unit / techno_plan_fy.unit VARCHAR(32)


def _in(col, vals):
    return f"{col} IN ({', '.join(['%s'] * len(vals))})"


def _ph(vals):
    return ",".join(["%s"] * len(vals))


# ── SQL building blocks ─────────────────────────────────────────────────────

_U = "techno_upload u JOIN plant_unit pu ON pu.unit_id = u.unit_id"
# v1's unit comparison (techno_data.unit / techno_plan_fy.unit were ai_ci)
_UC = "pu.unit_code COLLATE utf8mb4_0900_ai_ci"

_LEAF_VAL = ("CASE WHEN v.raw IS NOT NULL THEN v.raw "
             "WHEN v.is_int = 1 THEN CAST(CAST(v.num AS SIGNED) AS JSON) "
             "ELSE CAST(v.num AS JSON) END")


def _period_obj(period, alias):
    return (f"LEFT JOIN LATERAL (SELECT JSON_OBJECTAGG(v.param_key, {_LEAF_VAL}) AS obj "
            "FROM techno_value v WHERE v.report_month = u.report_month AND v.plant_code = u.plant_code "
            f"AND v.unit_id = u.unit_id AND v.period = '{period}') {alias} ON TRUE")


# FROM clause for _TEXT: the uploads with their unit and both period objects.
_TU = f"{_U} {_period_obj('month', 'tm')} {_period_obj('till_month', 'tt')}"
# The v1 techno_json text of the upload row u (see the module docstring).
_TEXT = ("CASE WHEN u.has_month = 1 AND u.has_till_month = 1 "
         "THEN JSON_OBJECT('month', COALESCE(tm.obj, JSON_OBJECT()), 'till_month', COALESCE(tt.obj, JSON_OBJECT())) "
         "WHEN u.has_month = 1 THEN JSON_OBJECT('month', COALESCE(tm.obj, JSON_OBJECT())) "
         "WHEN u.has_till_month = 1 THEN JSON_OBJECT('till_month', COALESCE(tt.obj, JSON_OBJECT())) "
         "ELSE JSON_OBJECT() END")

# Leaves of the selected uploads, for decode_techno: (report_month, plant,
# unit, has_month, has_till_month, period, param_key, num, is_int, raw,
# source_file, unit_id); an upload without leaves gives one row with period NULL.
_LEAVES = ("SELECT u.report_month, u.plant_code, pu.unit_code, u.has_month, u.has_till_month, "
           "v.period, v.param_key, v.num, v.is_int, v.raw, u.source_file, u.unit_id "
           f"FROM {_U} LEFT JOIN techno_value v ON v.report_month = u.report_month "
           "AND v.plant_code = u.plant_code AND v.unit_id = u.unit_id")
# v2codec.TECHNO_LEAF_ORDER_BY on the techno_value alias v
assert TECHNO_LEAF_ORDER_BY == "period, LENGTH(param_key), param_key"
_LEAF_ORDER = "v.period, LENGTH(v.param_key), v.param_key"


def _decoded(rows):
    """_LEAVES rows (grouped by upload, in order) -> [((month, plant, unit), blob dict)]."""
    out = []
    key = None
    leaves = flags = None
    for r in rows:
        k = (r[0], r[1], r[2])
        if k != key:
            if key is not None:
                out.append((key, decode_techno(flags[0], flags[1], leaves)))
            key, flags, leaves = k, (r[3], r[4]), []
        if r[5] is not None:
            leaves.append((r[5], r[6], r[7], r[8], r[9]))
    if key is not None:
        out.append((key, decode_techno(flags[0], flags[1], leaves)))
    return out


def _blobs_sql(cur, where, params, order):
    """[((month, plant, unit), blob dict)] of the uploads matching `where`,
    in `order`: v1's own path, json.loads of the techno_json text (_TEXT,
    byte-identical to v1's), which is 3-4x faster than decoding the leaf
    rows in Python (pymysql parses every row in Python) and gives the same
    dicts (key order and leaf types)."""
    cur.execute(f"SELECT u.report_month, u.plant_code, pu.unit_code, {_TEXT} FROM {_TU} "
                f"WHERE {where} ORDER BY {order}", list(params))
    return [((r[0], r[1], r[2]), _parse(r[3])) for r in cur.fetchall()]


# ── report_context bulk load ────────────────────────────────────────────────
# Inside report_context.activate(), techno reads whose month falls in the
# context's window are served from one load of the window's rows (ORDER BY
# report_month, plant, unit, as v1). The JSON text is kept and parsed on
# every read, so each caller gets fresh objects, as from SQL. Reads on a
# caller-supplied connection (conn=..., writers mid-transaction) always use
# SQL.

def _bulk_load(first, last):
    """{(report_month, fold(plant)): [(plant, unit, techno_json text), ...]}
    in unit order, for first <= report_month <= last."""
    out = {}
    with rc.cursor() as cur:
        cur.execute(
            f"SELECT u.report_month, u.plant_code, pu.unit_code, {_TEXT} FROM {_TU} "
            f"WHERE u.report_month BETWEEN %s AND %s ORDER BY u.report_month, u.plant_code, {_UC}",
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
    report_month: (techno_json text,) or None.

    Read-only helper. Inside a context it ignores `cur` and reads the
    committed snapshot the context loaded (never `cur`'s own uncommitted
    writes); a repo write switches the context off for the rest of the
    request, after which it reads on `cur` again."""
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
    stored JSON does not parse. A missing key means there is no row. The
    dict's order is unspecified (v2: deterministic, by month, then v1's id
    order (seq), as v1's idx_techno_month read)."""
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
    where = [_in("u.report_month", months)]
    params = list(months)
    if plants is not None:
        where.append(_in("u.plant_code", plants))
        params += plants
    if units is not None:
        where.append(_in(_UC, units))
        params += units
    with rc.cursor() as cur:
        rows = _blobs_sql(cur, " AND ".join(where), params, "u.report_month, u.seq")
    return dict(rows)


def merge_upsert(month: str, plant: str, unit: str, blob: Dict[str, Any],
                 source_file: str = "") -> None:
    """Merge `blob` ({"month": {...}, "till_month": {...}}) into the stored
    row for (month, plant, unit): read the existing blob, merge in Python
    (new non-null values win, a null keeps the stored value), write back.
    Same semantics as merge_upsert_techno_data, including the derived-param
    recompute and the extraction-log entry."""
    merge_upsert_techno_data(plant, month, unit, blob, source_file)


# ── write primitives ────────────────────────────────────────────────────────

def _check_unit(unit):
    """v1's VARCHAR(32) unit column (strict sql_mode): DataError 1406."""
    if isinstance(unit, str) and len(unit) > _V1_UNIT_LEN:
        raise pymysql.err.DataError(1406, "Data too long for column 'unit' at row 1")


def _unit_id_for_write(cur, plant, unit, *, bump):
    """unit_id of the unit spelled EXACTLY `unit` (unit_code is binary) of
    `plant`, created when missing (unit_type NULL). Locking reads. Callers
    first look for a stored row whose unit matches under ai_ci (v1's
    uq_techno rule) and reuse its unit; this is the otherwise-branch."""
    if bump:
        _ver.bump(cur)
    sql = "SELECT unit_id FROM plant_unit WHERE plant_code = %s AND unit_code = %s FOR SHARE"
    row = cur.execute(sql, (plant, unit)).fetchone()
    if row is None:
        cur.execute("INSERT INTO plant_unit (plant_code, unit_code) VALUES (%s, %s) AS new "
                    "ON DUPLICATE KEY UPDATE unit_code = plant_unit.unit_code", (plant, unit))
        row = cur.execute(sql, (plant, unit)).fetchone()
    return row[0]


def _stored(cur, plant, report_month, unit):
    """The stored row of (plant, month, unit), matched under ai_ci as v1's
    uq_techno did, as (blob dict, source_file, stored plant spelling,
    stored unit spelling, unit_id), or None. Write paths only (after the
    bump): a locking read of the upload and its leaves."""
    cur.execute(f"{_LEAVES} WHERE u.plant_code = %s AND u.report_month = %s AND pu.plant_code = %s "
                f"AND {_UC} = %s ORDER BY {_LEAF_ORDER} FOR UPDATE OF u, v FOR SHARE OF pu",
                (plant, report_month, plant, unit))
    rows = cur.fetchall()
    if not rows:
        return None
    (_m, stored_plant, stored_unit), blob = _decoded(rows)[0]
    return blob, rows[0][10], stored_plant, stored_unit, rows[0][11]


_UPLOAD_PUT = ("INSERT INTO techno_upload (report_month, plant_code, unit_id, has_month, has_till_month, "
               "source_file, created_at, created_at_iso) VALUES (%s, %s, %s, %s, %s, %s, {at}, %s) AS new "
               "ON DUPLICATE KEY UPDATE has_month = new.has_month, has_till_month = new.has_till_month, "
               "source_file = new.source_file, created_at = new.created_at, created_at_iso = new.created_at_iso")


def _put_blob(cur, plant, report_month, unit, techno_json, source_file, created_at, *, bump, transform=None):
    """Replace the whole stored blob of (plant, month, unit), as v1's
    INSERT ... ON DUPLICATE KEY UPDATE techno_json, source_file, created_at
    did (an existing row keeps its plant spelling). created_at None = NOW()
    (created_at_iso 0), else that datetime (created_at_iso 1).

    transform (read-modify-write in one transaction): called after the bump
    with the locking read of the stored row (_stored(): blob, source_file,
    plant, unit) or None; returns the (techno_json, source_file) to write,
    or None to write nothing.

    Returns None when nothing was written, else (old, techno_json,
    source_file): old is the stored (blob, source_file) replaced, or None."""
    leaves = None if transform else encode_techno(techno_json)
    _keys.check_month(report_month)
    _check_unit(unit)
    if bump:
        _ver.bump(cur)
    _keys.ensure_month(cur, report_month, bump=False)
    _keys.ensure_plant(cur, plant, bump=False)
    stored = _stored(cur, plant, report_month, unit)
    # v1's ON DUPLICATE KEY kept the stored (ai_ci-equal) key; else the exact spelling
    unit_id = stored[4] if stored is not None else _unit_id_for_write(cur, plant, unit, bump=False)
    if transform:
        put = transform(stored)
        if put is None:
            return None
        techno_json, source_file = put
        leaves = encode_techno(techno_json)
    has_month, has_till, leaves = leaves
    if stored is None:
        old, stored_plant = None, plant
    else:
        old, stored_plant = stored[:2], stored[2]
        cur.execute("DELETE FROM techno_value WHERE report_month = %s AND plant_code = %s AND unit_id = %s",
                    (report_month, stored_plant, unit_id))
    if created_at is None:
        cur.execute(_UPLOAD_PUT.format(at="NOW()"),
                    (report_month, stored_plant, unit_id, has_month, has_till, source_file, 0))
    else:
        cur.execute(_UPLOAD_PUT.format(at="%s"),
                    (report_month, stored_plant, unit_id, has_month, has_till, source_file, created_at, 1))
    if leaves:
        cur.executemany("INSERT INTO techno_value (report_month, plant_code, unit_id, period, param_key, "
                        "num, is_int, raw) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        [(report_month, stored_plant, unit_id) + leaf for leaf in leaves])
    return old, techno_json, source_file


def _iso_write(plant, report_month, unit, techno_json, source_file):
    """One isoformat() writer: replace the blob, created_at =
    datetime.now() (rendered back as its isoformat()), own transaction."""
    conn = connect()
    try:
        now = datetime.now()
        _put_blob(conn.cursor(), plant, report_month, unit, techno_json, source_file, now, bump=True)
        conn.commit()
    finally:
        conn.close()


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
    _iso_write(plant, report_month, unit, techno_json, source_file)


def save_techno_json(plant: str, report_month: str, unit: str,
                     techno_json: dict, source_file: str = ""):
    """Save a pre-built techno_json dict directly to techno_data table."""
    _iso_write(plant, report_month, unit, techno_json, source_file)


# ============================================================================
# Techno Data helpers  (techno_data table — all plants)
# ============================================================================

def _raw_write(conn, plant, report_month, unit, techno_json, source_file, transform=None):
    """_put_blob with created_at = NOW() on conn's transaction (uncommitted),
    then the activity-log old/new of v1's _raw_upsert_techno_data. Returns
    the blob written, or None when transform wrote nothing."""
    put = _put_blob(conn.cursor(), plant, report_month, unit, techno_json, source_file, None,
                    bump=True, transform=transform)
    if put is None:
        return None
    old, techno_json, source_file = put
    if old is not None:
        old = {"techno_json": old[0], "source_file": old[1]}
    new = {"techno_json": techno_json, "source_file": source_file}
    activity_context.record(f"techno_data/{plant}/{unit}/{report_month}", old, new)
    return techno_json


def _owned(conn, fn):
    """fn(conn) on `conn` (the caller commits), or on a connection of its
    own committed as one transaction."""
    if conn is not None:
        return fn(conn)
    conn = connect()
    try:
        out = fn(conn)
        conn.commit()
        return out
    finally:
        conn.close()


def _raw_upsert_techno_data(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str = '', conn=None):
    """Bare INSERT/UPDATE with no post-save hooks (see repo/techno.py):
    replace the stored blob, created_at = NOW(), then record the activity
    log old/new. `conn`, if given, is reused and NOT committed (the caller
    owns the transaction); otherwise one transaction of its own."""
    _owned(conn, lambda c: _raw_write(c, plant, report_month, unit, techno_json, source_file))


def upsert_techno_data(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str = '', conn=None):
    """Insert or replace techno data for one plant/unit/month, then the
    tmi / fuel_rate recompute and the extraction-log entry (see
    repo/techno.py). With `conn` everything runs on it, uncommitted;
    without, the chain is one transaction of its own."""
    _owned(conn, lambda c: _upsert_chain(c, plant, report_month, unit, techno_json, source_file))


def _upsert_chain(conn, plant, report_month, unit, techno_json, source_file, transform=None):
    """v1's upsert_techno_data on conn: the raw write (or, with transform,
    the read-modify-write), the recompute, the extraction-log entry (of the
    blob written, before the recompute, as v1)."""
    techno_json = _raw_write(conn, plant, report_month, unit, techno_json, source_file, transform)
    _maybe_recompute_derived_params(plant, report_month, unit, conn=conn)
    _log_techno_save(plant, report_month, unit, techno_json, source_file, conn=conn)


def _log_techno_save(plant: str, report_month: str, unit: str, techno_json: Dict, source_file: str, conn=None) -> None:
    """Audit-log every techno save through the extraction_log table (see
    repo/techno.py). Bound at call time to repo.ops.log_extraction (v1 went
    through the db.py re-export, which Task 7g removes)."""
    try:
        from repo import ops  # bind at call time, as v1 bound db
        items = len(techno_json.get("month", {})) + len(techno_json.get("till_month", {}))
        ops.log_extraction(
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


# tmi and fuel_rate are physically derived (see repo/techno.py):
#   tmi        = specific_hm_consumption + specific_scrap_consumption
#   fuel_rate  = coke_rate + nut_coke_rate + cdi   (nut_coke_rate may be 0/absent)
_TMI_INPUT_KEYS = ("specific_hm_consumption", "specific_scrap_consumption")
_FUEL_RATE_INPUT_KEYS = ("coke_rate", "cdi")  # nut_coke_rate optional, defaults to 0


def _derived(data):
    """v1's recompute over a stored blob: (updated, changed)."""
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
    return updated, changed


def _recompute(unit):
    """_put_blob transform: v1's recompute of the locked stored row; None
    (write nothing) when there is no row, the caller's unit spelling is
    not the stored one (v1 read get_techno_data(...).get(unit)), the blob
    is empty, or nothing changes. The stored source_file is kept."""
    def transform(stored):
        if stored is None or stored[3] != unit or not stored[0]:
            return None
        updated, changed = _derived(stored[0])
        return (updated, stored[1]) if changed else None
    return transform


def _maybe_recompute_derived_params(plant: str, report_month: str, unit: str, conn=None) -> None:
    """Recompute tmi/fuel_rate for this (plant, report_month, unit) from
    whatever inputs are currently stored, and overwrite the stored value if
    it differs (v1 rule, repo/techno.py; written with created_at = NOW() and
    an activity-log entry, as v1's _raw_upsert_techno_data). A plain read
    decides whether anything changes (no bump for a no-op); a change is a
    read-modify-write: bump, locking re-read, recompute, write.
    `conn`: see merge_upsert_techno_data.

    Failures: as v1, a failed recompute is printed and swallowed, and the
    main write stands. On a caller's connection (the write chain's shared
    transaction) the recompute runs inside a SAVEPOINT and a failure rolls
    back to it, so no half-written blob (leaves deleted, new ones not yet
    inserted) is ever committed. A deadlock (1213) or lock wait timeout
    (1205) is re-raised: MySQL has rolled back (1213) or may roll back the
    whole transaction, so the caller must see it fail."""
    try:
        data = get_techno_data(plant, report_month, unit, conn=conn).get(unit, {})
        if not data or not _derived(data)[1]:
            return

        def write(c):
            return _raw_write(c, plant, report_month, unit, None, None, _recompute(unit))
        if conn is None:
            _owned(None, write)                 # own transaction: a failure commits nothing
        else:
            _in_savepoint(conn, write)
    except Exception as e:
        if _is_lock_error(e):
            raise
        print(f"[db] tmi/fuel_rate recompute failed for {plant}/{report_month}/{unit}: {e}")


_LOCK_ERRORS = (1205, 1213)       # ER_LOCK_WAIT_TIMEOUT, ER_LOCK_DEADLOCK
_savepoint_ids = itertools.count(1)


def _is_lock_error(e) -> bool:
    args = getattr(e, "args", None)
    return bool(args) and args[0] in _LOCK_ERRORS


def _in_savepoint(conn, fn):
    """fn(conn) inside a SAVEPOINT of conn's transaction: rolled back to it
    when fn raises (the exception propagates), released otherwise."""
    name = f"techno_recompute_{next(_savepoint_ids)}"
    cur = conn.cursor()
    cur.execute(f"SAVEPOINT {name}")
    try:
        out = fn(conn)
    except BaseException:
        try:
            cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
        except Exception:  # noqa: BLE001 - e.g. a deadlock already rolled the transaction back
            pass
        raise
    cur.execute(f"RELEASE SAVEPOINT {name}")
    return out


# unit names that feed the SAIL BF_Shop rollup (see repo/techno.py).
_SAIL_BF_UNITS = ("BF_Shop", "BF-5")


def _merged(existing, new_techno_json, clear_keys):
    """v1's merge (repo/techno.py merge_upsert_techno_data), verbatim."""
    if existing is None:
        return new_techno_json
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
    return merged


def merge_upsert_techno_data(plant: str, report_month: str, unit: str, new_techno_json: Dict, source_file: str = '', conn=None, clear_keys: Optional[Dict[str, list]] = None):
    """Merge new_techno_json into any existing row (non-null values win;
    existing non-null kept if new value is null), with v1's clear_keys and
    source_file rules (repo/techno.py):
      - no stored row: new_techno_json is stored as given (its None leaves
        become explicit JSON nulls; a missing period stays missing);
      - a stored row: BOTH periods are rebuilt (a period the stored blob
        lacked becomes {}): stored keys, minus clear_keys[period], then the
        new non-null values over them; keys of the new blob that are None
        and not stored are dropped;
      - source_file is always replaced by the new one, created_at := NOW();
      - then the tmi / fuel_rate recompute and the extraction-log entry.
    One transaction: bump, locking read of the stored row, merge, write,
    recompute, log. With `conn` it runs on it and the caller commits."""
    def merge(stored):
        return _merged(None if stored is None else stored[0], new_techno_json, clear_keys), source_file
    _owned(conn, lambda c: _upsert_chain(c, plant, report_month, unit, None, source_file, merge))


def enrich_techno_records_with_db(records: List[Dict[str, Any]], plant: str, report_month: str, conn=None) -> List[Dict[str, Any]]:
    """Attach 'db_json' (current techno_data {month:{}, till_month:{}} for the
    same plant/unit/report_month, or empty dicts if none exists yet) to each
    preview record in-place (see repo/techno.py)."""
    if not records:
        return records
    existing = get_techno_data(plant, report_month, conn=conn)
    for r in records:
        r["db_json"] = existing.get(r.get("unit"), {"month": {}, "till_month": {}})
    return records


def get_techno_data(plant: str, report_month: str, unit: str = None, conn=None) -> Dict:
    """Return {unit: {month: {...}, till_month: {...}}} for a given plant/month,
    ordered by unit. `conn`: read on that connection (its row_factory is left
    as it was). Without `conn`, served from the active report_context's bulk
    load when it covers report_month."""
    if conn is None:
        served = _units_from_bulk(plant, report_month, unit)
        if served is not None:
            return served
    where = "u.plant_code = %s AND u.report_month = %s"
    params = [plant, report_month]
    if unit:
        where += " AND pu.plant_code = %s AND pu.unit_code COLLATE utf8mb4_0900_ai_ci = %s"
        params += [plant, unit]
    if conn is None:
        with rc.cursor() as cur:
            rows = _blobs_sql(cur, where, params, _UC)
    else:
        rows = _blobs_sql(conn.cursor(), where, params, _UC)
    return {k[2]: blob for k, blob in rows}


def get_sail_techno_actuals(report_month: str) -> Dict[str, Any]:
    """Fetch SAIL consolidated techno actuals (stored, not calculated).
    Returns: {unit: {month: {...}, till_month: {...}}} where unit is typically 'Shop'
    """
    served = _units_from_bulk("SAIL", report_month)
    if served is not None:
        return served
    with rc.cursor() as cur:
        rows = _blobs_sql(cur, "u.plant_code = 'SAIL' AND u.report_month = %s", [report_month], _UC)
    return {k[2]: blob for k, blob in rows}


def save_sail_techno_actuals(report_month: str, unit: str, techno_json: Dict,
                             calculation_details: Dict = None, source_file: str = ""):
    """Save SAIL consolidated techno actuals with calculation metadata
    (calculation_details is not stored, as in v1)."""
    _iso_write("SAIL", report_month, unit, techno_json, source_file)


def get_techno_months(plant: str = None) -> List[str]:
    """Return distinct report_month values in techno_data, newest first.
    Optionally filter by plant."""
    with rc.cursor() as cur:
        if plant:
            cur.execute("SELECT DISTINCT report_month FROM techno_upload WHERE plant_code = %s "
                        "ORDER BY report_month DESC", [plant])
        else:
            cur.execute("SELECT DISTINCT report_month FROM techno_upload ORDER BY report_month DESC")
        return [row[0] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Techno Plan (Targets) Functions - techno_plan_fy
# ---------------------------------------------------------------------------

_P = "techno_plan_fy p JOIN plant_unit pu ON pu.unit_id = p.unit_id"


def _plan_entry(row, with_method):
    try:
        out = {
            'data': json.loads(row[0]) if row[0] else {},
            'is_user_supplied': bool(row[1]),
            'calculated': json.loads(row[2]) if row[2] else {},
        }
        if with_method:
            out['calculation_method'] = json.loads(row[3]) if row[3] else {}
        return out
    except json.JSONDecodeError:
        out = {'data': {}, 'is_user_supplied': False, 'calculated': {}}
        if with_method:
            out['calculation_method'] = {}
        return out


def _plan_empty(with_method):
    out = {'data': {}, 'is_user_supplied': False, 'calculated': {}}
    if with_method:
        out['calculation_method'] = {}
    return out


def get_techno_plan(plant: str, fy: str, unit: str = "") -> Dict[str, Any]:
    """Fetch techno plan data from unified techno_plan_fy table.
    If unit specified, returns that specific unit's data.
    Otherwise returns all units for the plant.

    Cached per (plant, fy, unit) for the process lifetime; save_techno_plan()
    clears the cache on write. Returns a deep copy."""
    return copy.deepcopy(_get_techno_plan_cached(plant, fy, unit))


@functools.lru_cache(maxsize=None)
def _get_techno_plan_cached(plant: str, fy: str, unit: str = "") -> Dict[str, Any]:
    with rc.cursor() as cur:
        if unit:
            row = cur.execute(
                f"SELECT p.techno_json, p.is_user_supplied, p.calculated_json FROM {_P} "
                "WHERE p.plant_code = %s AND p.fy = %s AND pu.plant_code = %s AND pu.unit_code COLLATE utf8mb4_0900_ai_ci = %s",
                (plant, fy, plant, unit)).fetchone()
            return _plan_entry(row, False) if row else _plan_empty(False)
        rows = cur.execute(
            f"SELECT p.techno_json, p.is_user_supplied, p.calculated_json, pu.unit_code FROM {_P} "
            f"WHERE p.plant_code = %s AND p.fy = %s ORDER BY {_UC}", (plant, fy)).fetchall()
    return {row[3]: _plan_entry(row, False) for row in rows}


def save_techno_plan(plant: str, fy: str, unit: str, techno_json: Dict,
                    is_user_supplied: bool = False, calculated_json: Dict = None,
                    calculation_method: Dict = None, created_by: str = ""):
    """Save or update techno plan data for a plant/unit/FY (the only write
    path into techno_plan_fy; see repo/techno.py)."""
    _check_unit(unit)
    now = datetime.now().isoformat()
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        _keys.ensure_plant(cur, plant, bump=False)
        # v1's PRIMARY (plant_name, unit, fy) compared under ai_ci: a stored
        # plan of an ai_ci-equal unit is updated (its unit kept); otherwise
        # the unit is resolved by the exact spelling
        old = cur.execute(f"SELECT p.techno_json, p.is_user_supplied, p.calculated_json, p.calculation_method, "
                          f"p.unit_id FROM {_P} WHERE p.plant_code = %s AND p.fy = %s AND {_UC} = %s "
                          "FOR UPDATE OF p FOR SHARE OF pu", (plant, fy, unit)).fetchone()
        if old is not None:
            unit_id = old[4]
            old = dict(zip(("techno_json", "is_user_supplied", "calculated_json", "calculation_method"), old[:4]))
        else:
            unit_id = _unit_id_for_write(cur, plant, unit, bump=False)
        cur.execute("""
            INSERT INTO techno_plan_fy
                (plant_code, unit_id, fy, techno_json, is_user_supplied, calculated_json, calculation_method, created_by, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                techno_json = new.techno_json,
                is_user_supplied = new.is_user_supplied,
                calculated_json = new.calculated_json,
                calculation_method = new.calculation_method,
                updated_at = new.updated_at
        """, (plant, unit_id, fy, json.dumps(techno_json), int(is_user_supplied),
              json.dumps(calculated_json or {}), json.dumps(calculation_method or {}), created_by, now, now))
        conn.commit()
    finally:
        conn.close()

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
    """Fetch plant-level techno plan data (unit='Shop') for a FY. Cached."""
    return copy.deepcopy(_get_techno_plant_plan_cached(plant, fy))


_SHOP_PLAN_SQL = (f"SELECT p.techno_json, p.is_user_supplied, p.calculated_json, p.calculation_method FROM {_P} "
                  "WHERE p.plant_code = %s AND p.fy = %s AND pu.plant_code = %s AND pu.unit_code COLLATE utf8mb4_0900_ai_ci = 'Shop'")


@functools.lru_cache(maxsize=None)
def _get_techno_plant_plan_cached(plant: str, fy: str) -> Dict[str, Any]:
    with rc.cursor() as cur:
        row = cur.execute(_SHOP_PLAN_SQL, (plant, fy, plant)).fetchone()
    return _plan_entry(row, True) if row else _plan_empty(True)


def save_techno_plant_plan(plant: str, fy: str, data: Dict, is_user_supplied: bool = False,
                          calculated_json: Dict = None, calculation_method: Dict = None, created_by: str = ""):
    """Save or update plant-level techno plan data (unit='Shop') for a FY."""
    save_techno_plan(plant, fy, 'Shop', data, is_user_supplied, calculated_json, calculation_method, created_by)


def get_sail_techno_plan(fy: str) -> Dict[str, Any]:
    """Fetch SAIL consolidated techno plan data (plant 'SAIL', unit 'Shop') for a FY. Cached."""
    return copy.deepcopy(_get_sail_techno_plan_cached(fy))


@functools.lru_cache(maxsize=None)
def _get_sail_techno_plan_cached(fy: str) -> Dict[str, Any]:
    with rc.cursor() as cur:
        row = cur.execute(_SHOP_PLAN_SQL, ("SAIL", fy, "SAIL")).fetchone()
    return _plan_entry(row, True) if row else _plan_empty(True)


def save_sail_techno_plan(fy: str, data: Dict, is_user_supplied: bool = False,
                         calculated_json: Dict = None, calculation_method: Dict = None, created_by: str = ""):
    """Save or update SAIL consolidated techno plan data (plant_name='SAIL', unit='Shop') for a FY."""
    save_techno_plan('SAIL', fy, 'Shop', data, is_user_supplied, calculated_json, calculation_method, created_by)


def list_techno_plan_fys(plant: str = None) -> List[str]:
    """List distinct FYs in techno_plan_fy table, optionally filtered by plant."""
    with rc.cursor() as cur:
        if plant:
            cur.execute("SELECT DISTINCT fy FROM techno_plan_fy WHERE plant_code = %s ORDER BY fy DESC", (plant,))
        else:
            cur.execute("SELECT DISTINCT fy FROM techno_plan_fy ORDER BY fy DESC")
        return [row[0] for row in cur.fetchall()]


# ── Named queries (cursor-level) ────────────────────────────────────────────
# Each runs on the caller's cursor (so the caller's connection, transaction
# and row type are unchanged) and returns fetchall() / fetchone() with v1's
# column names. Orders: see the module docstring.

def units_for_plant_month(cur, plant, report_month):
    """fetchall() of (unit,) for one plant/month, ordered by unit."""
    cur.execute(f"SELECT pu.unit_code AS unit FROM {_U} WHERE u.plant_code = %s AND u.report_month = %s "
                "ORDER BY pu.unit_code COLLATE utf8mb4_0900_ai_ci", [plant, report_month])
    return cur.fetchall()


def distinct_plants(cur):
    """fetchall() of (plant,), every plant with a techno_data row."""
    cur.execute("SELECT DISTINCT plant_code AS plant FROM techno_upload ORDER BY plant")
    return cur.fetchall()


def distinct_report_months(cur):
    """fetchall() of (report_month,), every month with a techno_data row
    (v1: idx_techno_month order, ascending)."""
    cur.execute("SELECT DISTINCT report_month FROM techno_upload ORDER BY report_month")
    return cur.fetchall()


def distinct_units_for_plant(cur, plant):
    """fetchall() of (unit,) stored for a plant (non-empty units only), in
    v1's order: DISTINCT (ai_ci) over uq_techno (plant, report_month, unit),
    i.e. each ai_ci unit once, spelled as in its first row, by that row's
    month, then unit."""
    cur.execute(f"SELECT unit FROM (SELECT pu.unit_code AS unit, u.report_month AS m, ROW_NUMBER() OVER "
                f"(PARTITION BY {_UC} ORDER BY u.report_month) AS rn FROM {_U} "
                f"WHERE u.plant_code = %s AND {_UC} != '') AS t "
                "WHERE rn = 1 ORDER BY m, unit COLLATE utf8mb4_0900_ai_ci", (plant,))
    return cur.fetchall()


def bf_shop_rows(cur, report_month):
    """fetchall() of (plant, unit, techno_json) for the BF_Shop / BF-5 units
    (v1: idx_techno_month, id order = seq)."""
    cur.execute(f"SELECT u.plant_code AS plant, pu.unit_code AS unit, {_TEXT} AS techno_json FROM {_TU} "
                f"WHERE u.report_month = %s AND {_UC} IN ('BF_Shop', 'BF-5') ORDER BY u.seq", [report_month])
    return cur.fetchall()


def plant_unit_month_rows(cur, plant, unit, months):
    """fetchall() of (report_month, techno_json) for one plant/unit over
    months (v1: uq_techno order, by month)."""
    cur.execute(f"SELECT u.report_month, {_TEXT} AS techno_json FROM {_TU} "
                f"WHERE pu.plant_code = %s AND {_UC} = %s AND u.plant_code = %s "
                f"AND u.report_month IN ({_ph(months)}) ORDER BY u.report_month",
                (plant, unit, plant, *months))
    return cur.fetchall()


def plant_units_month_rows(cur, plant, units, months):
    """fetchall() of (unit, report_month, techno_json) for one plant over
    units x months (v1: uq_techno order, by month then unit, in 95 of the 96
    recorded calls; see tools/repo_oracle COMPARE_MODE)."""
    cur.execute(f"SELECT pu.unit_code AS unit, u.report_month, {_TEXT} AS techno_json FROM {_TU} "
                f"WHERE u.plant_code = %s AND {_UC} IN ({_ph(units)}) "
                f"AND u.report_month IN ({_ph(months)}) ORDER BY u.report_month, {_UC}",
                (plant, *units, *months))
    return cur.fetchall()


def json_row(cur, plant, report_month, unit):
    """fetchone() of (techno_json,) for one plant/month/unit, or None."""
    cur.execute(f"SELECT {_TEXT} AS techno_json FROM {_TU} WHERE u.plant_code = %s AND u.report_month = %s "
                f"AND pu.plant_code = %s AND {_UC} = %s", (plant, report_month, plant, unit))
    return cur.fetchone()


def all_json(cur):
    """fetchall() of (techno_json,) for every techno_data row (v1: PRIMARY
    scan, id order = seq)."""
    cur.execute(f"SELECT {_TEXT} AS techno_json FROM {_TU} ORDER BY u.seq")
    return cur.fetchall()


def rows_for_plants(cur, plants):
    """fetchall() of (plant, report_month, unit, techno_json) for the given
    plants, ordered by plant, report_month (then id order = seq)."""
    cur.execute(f"SELECT u.plant_code AS plant, u.report_month, pu.unit_code AS unit, {_TEXT} AS techno_json "
                f"FROM {_TU} WHERE u.plant_code IN ({_ph(plants)}) "
                "ORDER BY u.plant_code, u.report_month, u.seq", plants)
    return cur.fetchall()


def sail_rows(cur):
    """fetchall() of (report_month, techno_json) for plant='SAIL', by month
    (then id order = seq)."""
    cur.execute(f"SELECT u.report_month, {_TEXT} AS techno_json FROM {_TU} WHERE u.plant_code = 'SAIL' "
                "ORDER BY u.report_month, u.seq")
    return cur.fetchall()


def sail_unit_rows(cur, unit):
    """fetchall() of (report_month, techno_json) for plant='SAIL' and one
    unit, oldest month first."""
    cur.execute(f"SELECT u.report_month, {_TEXT} AS techno_json FROM {_TU} "
                f"WHERE pu.plant_code = 'SAIL' AND {_UC} = %s AND u.plant_code = 'SAIL' "
                "ORDER BY u.report_month ASC", [unit])
    return cur.fetchall()


def coal_blend_rows(cur, report_month, plants):
    """fetchall() of (plant, unit, techno_json) for the Coal_Consumption /
    General units of the given plants in one month (v1: uq_techno order)."""
    cur.execute(f"SELECT u.plant_code AS plant, pu.unit_code AS unit, {_TEXT} AS techno_json FROM {_TU} "
                f"WHERE u.report_month = %s AND {_UC} IN ('Coal_Consumption','General') "
                f"AND u.plant_code IN ({_ph(plants)}) ORDER BY u.plant_code, {_UC}",
                [report_month, *plants])
    return cur.fetchall()


def plants_month_rows(cur, report_month, plants):
    """fetchall() of (plant, unit, techno_json) for the given plants in one
    month (v1: idx_techno_month, id order = seq)."""
    cur.execute(f"SELECT u.plant_code AS plant, pu.unit_code AS unit, {_TEXT} AS techno_json FROM {_TU} "
                f"WHERE u.report_month = %s AND u.plant_code IN ({_ph(plants)}) ORDER BY u.seq",
                [report_month, *plants])
    return cur.fetchall()


def unit_plants_months_rows(cur, unit, plants, months):
    """fetchall() of (plant, report_month, techno_json) for one unit over
    plants x months (v1: uq_techno order)."""
    cur.execute(f"SELECT u.plant_code AS plant, u.report_month, {_TEXT} AS techno_json FROM {_TU} "
                f"WHERE {_UC} = %s AND u.plant_code IN ({_ph(plants)}) "
                f"AND u.report_month IN ({_ph(months)}) ORDER BY u.plant_code, u.report_month",
                [unit, *plants, *months])
    return cur.fetchall()


def month_rows(cur, report_month):
    """fetchall() of (plant, unit, techno_json) for every row of one month
    (v1: idx_techno_month, id order = seq)."""
    cur.execute(f"SELECT u.plant_code AS plant, pu.unit_code AS unit, {_TEXT} AS techno_json FROM {_TU} "
                "WHERE u.report_month = %s ORDER BY u.seq", [report_month])
    return cur.fetchall()


def rows_for_months(cur, months):
    """fetchall() of (plant, report_month, unit, techno_json) for the months
    (v1 had no ORDER BY and two plans; by month, then id order = seq)."""
    cur.execute(f"SELECT u.plant_code AS plant, u.report_month, pu.unit_code AS unit, {_TEXT} AS techno_json "
                f"FROM {_TU} WHERE u.report_month IN ({_ph(months)}) ORDER BY u.report_month, u.seq", months)
    return cur.fetchall()


def non_sail_rows(cur):
    """fetchall() of (plant, unit, techno_json) for every non-SAIL row (id order = seq)."""
    cur.execute(f"SELECT u.plant_code AS plant, pu.unit_code AS unit, {_TEXT} AS techno_json FROM {_TU} "
                "WHERE u.plant_code != 'SAIL' ORDER BY u.seq")
    return cur.fetchall()


def general_rows_with_source(cur):
    """fetchall() of (plant, report_month, unit, techno_json, source_file)
    for every unit='General' row (id order = seq)."""
    cur.execute(f"SELECT u.plant_code AS plant, u.report_month, pu.unit_code AS unit, {_TEXT} AS techno_json, "
                f"u.source_file FROM {_TU} WHERE {_UC} = 'General' ORDER BY u.seq")
    return cur.fetchall()


def months_signature_row(cur, months):
    """fetchone() of (COUNT(*), MAX(id), MAX(created_at)) over the months:
    MAX(seq) is v1's MAX(id); MAX(created_at) is the maximum of the v1
    strings (render_ts_flagged), as v1's VARCHAR MAX compared them (the two
    formats differ only at ' ' vs 'T' and a trailing fraction, where ai_ci
    and code-point order agree)."""
    cur.execute(f"SELECT seq, created_at, created_at_iso FROM techno_upload "
                f"WHERE report_month IN ({_ph(months)})", months)
    rows = cur.fetchall()
    stamps = [s for s in (render_ts_flagged("techno_upload.created_at", r[1], r[2]) for r in rows)
              if s is not None]
    return _row_like(cur, ("COUNT(*)", "MAX(id)", "MAX(created_at)"),
                     (len(rows), max((r[0] for r in rows), default=None), max(stamps) if stamps else None))


def five_plant_unit_rows(cur, units):
    """fetchall() of (plant, report_month, unit, techno_json) for the 5 ISPs
    and the given units (v1: id order = seq)."""
    cur.execute(f"SELECT u.plant_code AS plant, u.report_month, pu.unit_code AS unit, {_TEXT} AS techno_json "
                f"FROM {_TU} WHERE u.plant_code IN ('BSP','DSP','RSP','BSL','ISP') "
                f"AND {_UC} IN ({_ph(units)}) ORDER BY u.seq", units)
    return cur.fetchall()


def five_plant_first_month_row(cur):
    """fetchone() of (MIN(report_month),) over the 5 ISPs."""
    cur.execute("SELECT MIN(report_month) FROM techno_upload WHERE plant_code IN "
                "('BSP','DSP','RSP','BSL','ISP')")
    return cur.fetchone()


def five_plant_first_months(cur):
    """fetchall() of (plant, MIN(report_month)) for each of the 5 ISPs, by plant."""
    cur.execute("SELECT plant_code AS plant, MIN(report_month) FROM techno_upload WHERE plant_code IN "
                "('BSP','DSP','RSP','BSL','ISP') GROUP BY plant_code ORDER BY plant_code")
    return cur.fetchall()


# techno_plan_fy

def plan_json_row(cur, plant, unit, fy):
    """fetchone() of (techno_json,) for one plant/unit/FY plan, or None."""
    cur.execute(f"SELECT p.techno_json FROM {_P} WHERE p.plant_code = %s AND pu.plant_code = %s "
                "AND pu.unit_code COLLATE utf8mb4_0900_ai_ci = %s AND p.fy = %s", (plant, plant, unit, fy))
    return cur.fetchone()


def plan_plants_rows(cur, plants, fy, unit):
    """fetchall() of (plant_name, techno_json) for the plants' plan rows
    (v1: PRIMARY (plant_name, unit, fy) order)."""
    cur.execute(f"SELECT p.plant_code AS plant_name, p.techno_json FROM {_P} "
                f"WHERE p.plant_code IN ({_ph(plants)}) AND p.fy = %s AND pu.unit_code COLLATE utf8mb4_0900_ai_ci = %s "
                "ORDER BY p.plant_code", (*plants, fy, unit))
    return cur.fetchall()


def plan_rows_for_fy(cur, fy):
    """fetchall() of (plant_name, unit, techno_json) for every plan row of a
    FY (v1: PRIMARY (plant_name, unit, fy) order)."""
    cur.execute(f"SELECT p.plant_code AS plant_name, pu.unit_code AS unit, p.techno_json FROM {_P} "
                f"WHERE p.fy = %s ORDER BY p.plant_code, {_UC}", (fy,))
    return cur.fetchall()


# ── Registry tables (plant_registry.seed_plant_registry,
#    techno_registry.migrate_units; neither is called anywhere, and these
#    tables are in neither the v1 nor the v2 MySQL schema: the same SQL, so
#    the same "table doesn't exist" error) ──────────────────────────────────

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
