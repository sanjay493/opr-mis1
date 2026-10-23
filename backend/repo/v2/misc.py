"""Miscellaneous small repositories on the v2 schema: market_price_monthly,
macro_indicator_monthly, pdf_item_alias, rail_prod_despatch,
ready_reckoner_page, major_unit_daily_record, power_monthly,
steel_sector_performance, the bf_benchmark_* tables and the cover_photo /
report_cover_setting library.

Same public names, signatures, return shapes, row types and exceptions as
repo/misc.py. Renamed columns are aliased back to their v1 names
(power_data_table.plant_name / item_name, pdf_item_alias.plant_name /
item_name, rail_prod_despatch.financial_year, bf_benchmark_*.plant / unit /
report_month, cover_photos.uploaded_by / uploaded_at, major_unit
unit_label).

TIMESTAMPS. Columns that were v1 text and are DATETIME now are rendered
back to the exact v1 string (repo.v2codec formats): in SQL for the
cursor-level readers, so the rows keep the caller's own row type
(_iso), in Python for the dict readers. The writers that take the v1
string (bf_benchmark_*, cover_photo, steel_sector_performance) store it
through the codec parser, so it renders back unchanged; a string that is
not in the column's canonical form is refused (OutOfModelError,
parity_exceptions.md §2). bf_benchmark_external_* store which of their two
v1 forms (UTC ISO, plain 'YYYY-MM-DD HH:MM:SS') each value had in the
*_at_plain flag. major_unit_daily_record.updated_at, report_cover_setting
and cover_photo keep the writer's form (ISO to seconds, plain).

UNITS. plant_unit.unit_code is utf8mb4_0900_bin. Reads compare units under
`COLLATE utf8mb4_0900_ai_ci`, as v1's columns did. major_unit_daily_record
and bf_benchmark_sail_meta were keyed by (plant, unit) under ai_ci: an
upsert onto a stored ai_ci twin updates that row and keeps its spelling
(a locking lookup after the bump), otherwise the exact spelling is
resolved or created (_keys.exact_unit_id).

DATES. major_unit_daily_record.record_date was VARCHAR(10), now a DATE: a
string that is not a canonical 'YYYY-MM-DD' is refused (OutOfModelError;
the data-entry form takes free text, see parity_exceptions.md §2).

ORDER. Reads v1 served without an ORDER BY from the primary key have an
explicit ORDER BY reproducing it.

WRITES. One bump per call, first (also for an empty batch); v1 column
limits are checked where the v1 column differs in name or width from v2's
(_keys.fits: 1048 / 1406 with v1's column names); months, plants, items
and units are resolved or created after the bump.
"""
import json
from typing import Any, Dict, List, Optional

import pymysql

import activity_context
from dbengine import connect
from repo import version as _ver
from repo import conn as rc
from repo.conn import row_dict as _row_dict
from repo.v2 import _keys
from repo.v2codec import (CodecError, ISO_LOCAL, ISO_SECONDS, ISO_UTC, SQL_SECONDS, parse_date, parse_ts,
                          parse_ts_flagged, render_ts)

_UC = "pu.unit_code COLLATE utf8mb4_0900_ai_ci"


_iso = _keys.iso_sql
_stamp = _keys.stamp


def _stamp_flagged(column, value):
    """(datetime, plain flag) of a bf_benchmark_external_* timestamp string."""
    if value is None:
        return None, 0
    try:
        return parse_ts_flagged(f"bf_benchmark_external_{column.split('.')[0]}.{column.split('.')[1]}", value)
    except (CodecError, TypeError):
        raise _keys.OutOfModelError(f"{column} {value!r} is neither a UTC ISO nor a plain "
                                    "'YYYY-MM-DD HH:MM:SS' timestamp") from None


# ── "Movement of Key Prices - International" (page 2.41) ───────────────────

def get_market_price_trend(report_months: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {report_month: {series_code: value}}."""
    conn = connect()
    cur = conn.cursor()
    out = {m: {} for m in report_months}
    if report_months:
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(f"SELECT report_month, series_code, value FROM market_price_monthly "
                    f"WHERE report_month IN ({ph}) ORDER BY report_month, series_code", report_months)
        for rm, series, value in cur.fetchall():
            out.setdefault(rm, {})[series] = value
    conn.close()
    return out


def save_market_price_trend(rows: List[Dict[str, Any]]) -> int:
    """Upsert market_price_trend_monthly rows: {report_month, series_code, value}."""
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        for r in rows:
            args = (r["report_month"], r["series_code"], r.get("value"))
            month = _keys.fit_month(args[0])
            _keys.ensure_month(cur, month, bump=False)
            cur.execute("""
                INSERT INTO market_price_monthly (report_month, series_code, value)
                VALUES (%s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE value = new.value
            """, (month,) + args[1:])
        conn.commit()
    finally:
        conn.close()
    return len(rows)


# ── "India Macro Economic Indicators" (page 2.42) ───────────────────────────

def get_macro_indicators(report_months: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {report_month: {metric_code: value}}."""
    conn = connect()
    cur = conn.cursor()
    out = {m: {} for m in report_months}
    if report_months:
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(f"SELECT report_month, metric_code, value FROM macro_indicator_monthly "
                    f"WHERE report_month IN ({ph}) ORDER BY report_month, metric_code", report_months)
        for rm, metric, value in cur.fetchall():
            out.setdefault(rm, {})[metric] = value
    conn.close()
    return out


def save_macro_indicators(rows: List[Dict[str, Any]]) -> int:
    """Upsert macro_indicators_monthly rows: {report_month, metric_code, value}."""
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        for r in rows:
            args = (r["report_month"], r["metric_code"], r.get("value"))
            month = _keys.fit_month(args[0])
            _keys.ensure_month(cur, month, bump=False)
            cur.execute("""
                INSERT INTO macro_indicator_monthly (report_month, metric_code, value)
                VALUES (%s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE value = new.value
            """, (month,) + args[1:])
        conn.commit()
    finally:
        conn.close()
    return len(rows)


# ── Moved from db.py: pdf_item_alias, rail, ready reckoner, major units ─────

def get_pdf_item_aliases(plant: str) -> Dict[str, Any]:
    """User-saved PDF label corrections for a plant: {pdf_label: (item_name, convert_t)}."""
    conn = connect()
    rows = conn.execute("""
        SELECT a.pdf_label, i.item_name, a.convert_t FROM pdf_item_alias a JOIN item i ON i.item_id = a.item_id
        WHERE a.plant_code = %s ORDER BY a.pdf_label
    """, (plant,)).fetchall()
    conn.close()
    return {r[0]: (r[1], r[2]) for r in rows}


def save_pdf_item_alias(plant: str, pdf_label: str, item_name: str, convert_t: int = 1):
    """Upsert a PDF label → item_name correction so future extractions map it automatically."""
    # Count-type items (e.g. "Oven Pushing(nos/d)") are plain numbers, never
    # tonnes — force convert_t=0 so no caller (stale UI tab, mapping
    # suggestions, re-confirm) can re-poison the alias with a ÷1000 flag.
    if "(nos" in (item_name or "").lower():
        convert_t = 0
    _keys.fits("plant_name", plant, 32, nullable=False)
    _keys.fits("pdf_label", pdf_label, 160, nullable=False)
    _keys.fits("item_name", item_name, 64, nullable=False)
    _keys.check_plant_model(plant, "plant_name", 32)
    conn = connect()
    try:
        old = _row_dict(conn,
            "SELECT a.plant_code AS plant_name, a.pdf_label, i.item_name, a.convert_t "
            "FROM pdf_item_alias a JOIN item i ON i.item_id = a.item_id "
            "WHERE a.plant_code=%s AND a.pdf_label=%s", (plant, pdf_label))
        cur = conn.cursor()
        _ver.bump(cur)
        _keys.ensure_plant(cur, plant, bump=False)
        item_id = _keys.exact_item_id(cur, item_name, lock=True)
        if item_id is None:
            cur.execute("INSERT INTO item (item_name) VALUES (%s) AS new "
                        "ON DUPLICATE KEY UPDATE item_name = item.item_name", (item_name,))
            item_id = _keys.exact_item_id(cur, item_name, lock=True)
        cur.execute("""
            INSERT INTO pdf_item_alias (plant_code, pdf_label, item_id, convert_t)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE item_id = new.item_id, convert_t = new.convert_t
        """, (plant, pdf_label, item_id, convert_t))
        conn.commit()
    finally:
        conn.close()
    new = {"plant_name": plant, "pdf_label": pdf_label, "item_name": item_name, "convert_t": convert_t}
    activity_context.record(f"pdf_item_alias/{plant}/{pdf_label}", old, new)


# ── "Rail Production & Dispatch from BSP" (page 18.5) ──────────────────────

def get_rail_report_data(fys: List[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """-> {financial_year: {metric: {"value": v, "note": n}}}."""
    conn = connect()
    cur = conn.cursor()
    out = {fy: {} for fy in fys}
    if fys:
        ph = ",".join(["%s"] * len(fys))
        cur.execute(f"SELECT fy, metric, value, note FROM rail_prod_despatch "
                    f"WHERE fy IN ({ph}) ORDER BY fy, metric", fys)
        for fy, metric, value, note in cur.fetchall():
            out.setdefault(fy, {})[metric] = {"value": value, "note": note}
    conn.close()
    return out


def save_rail_report_data(rows: List[Dict[str, Any]]) -> int:
    """Upsert rail_prod_despatch rows: {financial_year, metric, value, note}."""
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        for r in rows:
            args = (r["financial_year"], r["metric"], r.get("value"), r.get("note"))
            _keys.fits("financial_year", args[0], 7, nullable=False)
            cur.execute("""
                INSERT INTO rail_prod_despatch (fy, metric, value, note)
                VALUES (%s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE
                    value = new.value, note = new.note
            """, (_keys.fit_fy(args[0]),) + args[1:])
        conn.commit()
    finally:
        conn.close()
    return len(rows)


# ── "Ready Reckoner" (Annexure-1: 5 ISPs / Annexure-2: 3 SSPs) ─────────────

_READY_RECKONER_COLS = (
    "plant_code", "plant_name", "plant_group", "process_flow_image_path",
    "capacity_rows", "product_mix_headers", "product_mix_rows", "product_mix_caption",
    "sort_order", "updated_by", "updated_at",
)

_READY_RECKONER_JSON_COLS = ("capacity_rows", "product_mix_headers", "product_mix_rows")


def _decode_ready_reckoner_row(row: tuple) -> dict:
    d = dict(zip(_READY_RECKONER_COLS, row))
    for col in _READY_RECKONER_JSON_COLS:
        d[col] = json.loads(d[col]) if d.get(col) else []
    d["product_mix_caption"] = d.get("product_mix_caption") or ""
    return d


def get_ready_reckoner_pages() -> List[dict]:
    """-> every plant's row (dict, _READY_RECKONER_COLS keys, JSON columns
    already decoded to lists), ordered for display (ISPs then SSPs, each
    group in its own sort_order)."""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {','.join(_READY_RECKONER_COLS)} FROM ready_reckoner_page "
        f"ORDER BY plant_group, sort_order, plant_code"
    )
    rows = [_decode_ready_reckoner_row(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_ready_reckoner_page(plant_code: str) -> Optional[dict]:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {','.join(_READY_RECKONER_COLS)} FROM ready_reckoner_page WHERE plant_code = %s",
        (plant_code,),
    )
    row = cur.fetchone()
    conn.close()
    return _decode_ready_reckoner_row(row) if row else None


def upsert_ready_reckoner_master(row: Dict[str, Any]) -> None:
    """Insert or update the non-editable identity fields of one plant's row
    (plant_name/plant_group/sort_order) — used by the one-time backfill, not
    the inline editor (which only ever touches content via the functions
    below)."""
    args = (row["plant_code"], row.get("plant_name"), row["plant_group"], int(row.get("sort_order") or 0))
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        _keys.ensure_plant(cur, args[0], bump=False)
        cur.execute("""
            INSERT INTO ready_reckoner_page (plant_code, plant_name, plant_group, sort_order)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                plant_name = new.plant_name, plant_group = new.plant_group,
                sort_order = new.sort_order
        """, args)
        conn.commit()
    finally:
        conn.close()


def save_ready_reckoner_content(
    plant_code: str, capacity_rows: Optional[list] = None,
    product_mix_headers: Optional[list] = None, product_mix_rows: Optional[list] = None,
    product_mix_caption: Optional[str] = None, updated_by: str = "",
) -> None:
    """Updates one or more of the plain-data fields for one plant, from the
    /data-entry/ready-reckoner form's Save action. None (not just an empty
    list) means "leave this field alone". A plain UPDATE, not an upsert: the
    row always already exists by this point."""
    import datetime as _dt
    sets, args = [], []
    if capacity_rows is not None:
        sets.append("capacity_rows = %s")
        args.append(json.dumps(capacity_rows))
    if product_mix_headers is not None:
        sets.append("product_mix_headers = %s")
        args.append(json.dumps(product_mix_headers))
    if product_mix_rows is not None:
        sets.append("product_mix_rows = %s")
        args.append(json.dumps(product_mix_rows))
    if product_mix_caption is not None:
        sets.append("product_mix_caption = %s")
        args.append(product_mix_caption)
    if not sets:
        return
    sets += ["updated_by = %s", "updated_at = %s"]
    args += [updated_by, _dt.datetime.now().isoformat(timespec="seconds"), plant_code]
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        cur.execute(f"UPDATE ready_reckoner_page SET {', '.join(sets)} WHERE plant_code = %s", args)
        conn.commit()
    finally:
        conn.close()


def save_ready_reckoner_image(plant_code: str, image_path: str, updated_by: str) -> None:
    """Updates just the process-flow diagram's file path for one plant, from
    the inline editor's image-upload control. Same plain-UPDATE reasoning
    as save_ready_reckoner_content."""
    import datetime as _dt
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        cur.execute("""
            UPDATE ready_reckoner_page
            SET process_flow_image_path = %s, updated_by = %s, updated_at = %s
            WHERE plant_code = %s
        """, (image_path, updated_by, _dt.datetime.now().isoformat(timespec="seconds"), plant_code))
        conn.commit()
    finally:
        conn.close()


# ── Annexure-3 : 5 ISPs Major Units Records — Daily best ───────────────────

_MAJOR_UNIT_DAILY_COLS = (
    "plant_code", "unit_label", "unit_of_measure", "value",
    "record_date", "remarks", "sort_order", "updated_by", "updated_at",
)
_MU_SELECT = ("SELECT m.plant_code, pu.unit_code AS unit_label, m.unit_of_measure, m.value, m.record_date, "
              "m.remarks, m.sort_order, m.updated_by, m.updated_at "
              "FROM major_unit_daily_record m JOIN plant_unit pu ON pu.unit_id = m.unit_id")


def _mu_dict(r) -> dict:
    d = dict(zip(_MAJOR_UNIT_DAILY_COLS, r))
    d["updated_at"] = render_ts(ISO_SECONDS, d["updated_at"])
    return d


def get_major_unit_daily_records(plant_code: str) -> List[dict]:
    """-> every unit row for one plant, in display order."""
    conn = connect()
    cur = conn.cursor()
    cur.execute(f"{_MU_SELECT} WHERE m.plant_code = %s ORDER BY m.sort_order, {_UC}", (plant_code,))
    rows = [_mu_dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_major_unit_daily_records_all() -> Dict[str, Dict[str, dict]]:
    """-> {plant_code: {unit_label: row_dict}} for every plant — used by
    page_major_unit_records.generate_major_unit_page to look up one plant's
    Daily figures alongside its live-computed Annual/Monthly bests."""
    conn = connect()
    cur = conn.cursor()
    cur.execute(f"{_MU_SELECT} ORDER BY m.plant_code, {_UC}")
    out: Dict[str, Dict[str, dict]] = {}
    for r in cur.fetchall():
        d = _mu_dict(r)
        out.setdefault(d["plant_code"], {})[d["unit_label"]] = d
    conn.close()
    return out


def _stored_unit_id(cur, table, plant, unit):
    """unit_id of the row of `table` (keyed by plant and unit) whose unit
    matches `unit` under ai_ci, as v1's key did; else the unit spelled
    exactly `unit`, created when missing. Locking reads, after the bump."""
    row = cur.execute(f"SELECT t.unit_id FROM {table} t JOIN plant_unit pu ON pu.unit_id = t.unit_id "
                      f"WHERE t.plant_code = %s AND {_UC} = %s FOR UPDATE OF t FOR SHARE OF pu",
                      (plant, unit)).fetchone()
    return row[0] if row is not None else _keys.exact_unit_id(cur, plant, unit, bump=False)


_day = _keys.day


def save_major_unit_daily_record(plant_code: str, unit_label: str, value: Optional[float],
                                  unit_of_measure: Optional[str], record_date: Optional[str],
                                  remarks: Optional[str], sort_order: int, updated_by: str = "") -> None:
    """Upsert one unit's Daily best — used by both the one-time backfill
    (scripts/backfill_major_unit_daily_records.py) and the
    /data-entry/major-unit-daily editor (see main.py's
    /api/major-unit-daily/{plant_code} POST)."""
    import datetime as _dt
    updated_at = _dt.datetime.now().isoformat(timespec="seconds")
    _keys.fits("plant_code", plant_code, 8, nullable=False)
    _keys.fits("unit_label", unit_label, 64, nullable=False)
    _keys.fits("unit_of_measure", unit_of_measure, 16)
    _keys.fits("record_date", record_date, 10)
    _keys.fits("updated_by", updated_by, 128)
    day = _day("record_date", record_date)
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        _keys.ensure_plant(cur, plant_code, bump=False)
        unit_id = _stored_unit_id(cur, "major_unit_daily_record", plant_code, unit_label)
        cur.execute("""
            INSERT INTO major_unit_daily_record
                (plant_code, unit_id, unit_of_measure, value, record_date,
                 remarks, sort_order, updated_by, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                unit_of_measure = new.unit_of_measure, value = new.value,
                record_date = new.record_date, remarks = new.remarks,
                sort_order = new.sort_order, updated_by = new.updated_by,
                updated_at = new.updated_at
        """, (plant_code, unit_id, unit_of_measure, value, day, remarks,
              sort_order, updated_by, updated_at))
        conn.commit()
    finally:
        conn.close()


# ── Named queries (moved verbatim from their callers) ───────────────────────

# ── power_data_table ("Power-OIS"; page_power_data, api_power_omi) ──────────

def power_value_row(cur, report_month, plant_name, item_name):
    """fetchone() of (value,) for one power figure.
    api_power_omi._existing_conflicts."""
    cur.execute(
                "SELECT value FROM power_monthly "
                "WHERE report_month = %s AND plant_code = %s AND power_item = %s",
                (report_month, plant_name, item_name),
            )
    return cur.fetchone()


def upsert_power_value(cur, report_month, plant_name, item_name, value):
    """Upsert one power figure on the caller's cursor; the caller commits.
    api_power_omi POST /insert."""
    stored_month = _keys.fit_month(report_month)
    _keys.check_month(stored_month)
    _keys.fits("plant_name", plant_name, 32, nullable=False)
    _keys.fits("item_name", item_name, 64, nullable=False)
    _keys.check_plant_model(plant_name, "plant_name", 32)
    _ver.bump(cur)
    _keys.ensure_month(cur, stored_month, bump=False)
    _keys.ensure_plant(cur, plant_name, bump=False)
    cur.execute("""
                INSERT INTO power_monthly (report_month, plant_code, power_item, value)
                VALUES (%s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE value = new.value
            """, (stored_month, plant_name, item_name, value))


def power_rows_for_months(cur, months):
    """fetchall() of (report_month, plant_name, item_name, value) for the
    months. page_power_data.generate_power_data."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(
            f"SELECT report_month, plant_code AS plant_name, power_item AS item_name, value FROM power_monthly "
            f"WHERE report_month IN ({ph}) ORDER BY report_month, plant_code, power_item",
            months,
        )
    return cur.fetchall()


def power_plants_for_month(report_month):
    """fetchall() of (plant_name,) with any power row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT DISTINCT plant_code AS plant_name FROM power_monthly WHERE report_month = %s "
                    "ORDER BY plant_code", [report_month])
        return cur.fetchall()


# ── steel_sector_performance_table (JPC release archive) ────────────────────

def upsert_steel_sector_performance(cur, report_month, data_json, source_file, created_at):
    """Archive one release's preview JSON on the caller's cursor; the caller
    commits. main POST /api/steel-sector-performance/confirm."""
    stored_month = _keys.fit_month(report_month)
    _keys.check_month(stored_month)
    _keys.fits("source_file", source_file, 255)
    _keys.fits("created_at", created_at, 32)
    stamp = _stamp(ISO_LOCAL, created_at, "created_at")
    _ver.bump(cur)
    _keys.ensure_month(cur, stored_month, bump=False)
    try:
        cur.execute("""
            INSERT INTO steel_sector_performance (report_month, data_json, source_file, created_at)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                data_json = new.data_json,
                source_file = new.source_file,
                created_at = new.created_at
        """, (stored_month, data_json, source_file, stamp))
    except (pymysql.err.DataError, pymysql.err.OperationalError) as e:
        if e.args and e.args[0] == 3140:      # v1's message names v1's table
            raise type(e)(e.args[0], str(e.args[1]).replace(
                "'steel_sector_performance.", "'steel_sector_performance_table.")) from None
        raise


def steel_sector_latest_row(cur, report_month):
    """fetchone() of (report_month, data_json, source_file) for the newest
    release at or before report_month. page_steel_sector_performance._load_row."""
    cur.execute("""
            SELECT report_month, data_json, source_file FROM steel_sector_performance
            WHERE report_month <= %s
            ORDER BY report_month DESC LIMIT 1
        """, (report_month,))
    return cur.fetchone()


def steel_sector_data_json_rows(cur):
    """fetchall() of (data_json,) for every release, oldest first.
    page_steel_sector_performance (trend series)."""
    cur.execute("SELECT data_json FROM steel_sector_performance ORDER BY report_month")
    return cur.fetchall()


def steel_sector_any_row(report_month):
    """True when steel_sector_performance_table has a row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM steel_sector_performance WHERE report_month = %s LIMIT 1",
                    [report_month])
        return bool(cur.fetchall())


# ── major_unit_daily_record (beyond the moved db.py functions) ──────────────

def major_unit_daily_values(conn, plant_code):
    """fetchall() of (unit_label, value) for one plant.
    api_production_loss._unit_weights."""
    return conn.execute("SELECT pu.unit_code AS unit_label, m.value FROM major_unit_daily_record m "
                        f"JOIN plant_unit pu ON pu.unit_id = m.unit_id WHERE m.plant_code=%s ORDER BY {_UC}",
                        (plant_code,)).fetchall()


def major_unit_daily_label_row(cur, plant_code, unit_label):
    """fetchone() of (value, record_date, updated_by, updated_at) for one
    unit label. scripts/rename_major_unit_labels."""
    cur.execute(
                f"SELECT m.value, m.record_date, m.updated_by, {_iso('m.updated_at', ISO_SECONDS)} AS updated_at "
                f"FROM major_unit_daily_record m JOIN plant_unit pu ON pu.unit_id = m.unit_id "
                f"WHERE m.plant_code = %s AND {_UC} = %s",
                (plant_code, unit_label),
            )
    return cur.fetchone()


def rename_major_unit_label(cur, new_label, plant_code, old_label):
    """Rename one unit label on the caller's cursor; the caller commits and
    reads cur.rowcount. scripts/rename_major_unit_labels."""
    _ver.bump(cur)
    row = cur.execute(f"SELECT m.unit_id FROM major_unit_daily_record m JOIN plant_unit pu ON pu.unit_id = m.unit_id "
                      f"WHERE m.plant_code = %s AND {_UC} = %s FOR UPDATE OF m FOR SHARE OF pu",
                      (plant_code, old_label)).fetchone()
    unit_id, new_id = (-1, -1) if row is None else (row[0], None)
    if row is not None:
        _keys.fits("unit_label", new_label, 64, nullable=False)
        clash = cur.execute(f"SELECT 1 FROM major_unit_daily_record m JOIN plant_unit pu ON pu.unit_id = m.unit_id "
                            f"WHERE m.plant_code = %s AND {_UC} = %s AND m.unit_id <> %s FOR SHARE OF m",
                            (plant_code, new_label, unit_id)).fetchone()
        if clash is not None:        # v1's primary key (plant_code, unit_label), ai_ci
            raise pymysql.err.IntegrityError(
                1062, f"Duplicate entry '{plant_code}-{new_label}' for key 'major_unit_daily_record.PRIMARY'")
        new_id = _keys.exact_unit_id(cur, plant_code, new_label, bump=False)
    cur.execute("UPDATE major_unit_daily_record SET unit_id = %s WHERE plant_code = %s AND unit_id = %s",
                (new_id, plant_code, unit_id))


# ── bf_benchmark_sail_meta / _external_bf / _external_data ──────────────────

def bf_sail_working_volume_rows(cur):
    """fetchall() of (plant, unit, working_volume_m3).
    api_bf_benchmark get_params / _sail_working_volumes."""
    cur.execute("SELECT b.plant_code AS plant, pu.unit_code AS unit, b.working_volume_m3 "
                "FROM bf_benchmark_sail_meta b JOIN plant_unit pu ON pu.unit_id = b.unit_id "
                f"ORDER BY b.plant_code, {_UC}")
    return cur.fetchall()


def bf_sail_meta_rows(cur):
    """fetchall() of (plant, unit, working_volume_m3, updated_at), ordered.
    api_bf_benchmark GET /sail-meta."""
    cur.execute("SELECT b.plant_code AS plant, pu.unit_code AS unit, b.working_volume_m3, "
                f"{_iso('b.updated_at', ISO_UTC)} AS updated_at "
                "FROM bf_benchmark_sail_meta b JOIN plant_unit pu ON pu.unit_id = b.unit_id "
                f"ORDER BY b.plant_code, {_UC}")
    return cur.fetchall()


def upsert_bf_sail_meta(cur, plant, unit, working_volume_m3, updated_at):
    """Upsert one SAIL BF's Working Volume on the caller's cursor; the caller
    commits. api_bf_benchmark PATCH /sail-meta."""
    _keys.fits("plant", plant, 32, nullable=False)
    _keys.fits("unit", unit, 32, nullable=False)
    _keys.fits("updated_at", updated_at, 40)
    _keys.check_plant_model(plant, "plant", 32)
    stamp = _stamp(ISO_UTC, updated_at, "updated_at")
    _ver.bump(cur)
    _keys.ensure_plant(cur, plant, bump=False)
    unit_id = _stored_unit_id(cur, "bf_benchmark_sail_meta", plant, unit)
    cur.execute(
        "INSERT INTO bf_benchmark_sail_meta (plant_code, unit_id, working_volume_m3, updated_at) "
        "VALUES (%s, %s, %s, %s) "
        "AS new ON DUPLICATE KEY UPDATE working_volume_m3=new.working_volume_m3, updated_at=new.updated_at",
        (plant, unit_id, working_volume_m3, stamp),
    )


def bf_sail_working_volume_row(cur, plant, unit):
    """fetchone() of (working_volume_m3,) for one SAIL BF.
    page_bf_large_annexure._sail_static_working_volume."""
    cur.execute(
            "SELECT b.working_volume_m3 FROM bf_benchmark_sail_meta b JOIN plant_unit pu ON pu.unit_id = b.unit_id "
            f"WHERE b.plant_code=%s AND {_UC}=%s",
            (plant, unit),
        )
    return cur.fetchone()


def external_bf_list_rows(cur, active_only):
    """fetchall() of (id, name, company, location, working_volume_m3, active,
    created_at, latest FY) by name. api_bf_benchmark GET /external-bfs."""
    created = ("IF(b.created_at_plain = 1, " + _iso("b.created_at", SQL_SECONDS) + ", "
               + _iso("b.created_at", ISO_UTC) + ")")
    sql = (
        "SELECT b.id, b.name, b.company, b.location, b.working_volume_m3, b.active, "
        + created + " AS created_at, "
        "(SELECT MAX(d.fy) FROM bf_benchmark_external_data d WHERE d.external_bf_id=b.id) "
        "FROM bf_benchmark_external_bf b"
    )
    if active_only:
        sql += " WHERE b.active=1"
    sql += " ORDER BY b.name, b.id"
    cur.execute(sql)
    return cur.fetchall()


def insert_external_bf(cur, name, company, location, created_at):
    """Insert one non-SAIL BF on the caller's cursor; the caller commits and
    reads cur.lastrowid. api_bf_benchmark POST /external-bfs."""
    _keys.fits("created_at", created_at, 40, nullable=False)
    stamp, plain = _stamp_flagged("bf.created_at", created_at)
    _ver.bump(cur)
    cur.execute(
        "INSERT INTO bf_benchmark_external_bf (name, company, location, active, created_at, created_at_plain) "
        "VALUES (%s, %s, %s, 1, %s, %s)",
        (name, company, location, stamp, plain),
    )


def external_bf_id_row(cur, bf_id):
    """fetchone() of (id,) when the non-SAIL BF exists.
    api_bf_benchmark PATCH /external-bfs/{id}, POST .../entry."""
    cur.execute("SELECT id FROM bf_benchmark_external_bf WHERE id=%s", (bf_id,))
    return cur.fetchone()


def update_external_bf(cur, fields, params):
    """Update the "col=%s" `fields` of one non-SAIL BF (`params` ends with
    its id) on the caller's cursor; the caller commits.
    api_bf_benchmark PATCH /external-bfs/{id}."""
    _ver.bump(cur)
    cur.execute(f"UPDATE bf_benchmark_external_bf SET {', '.join(fields)} WHERE id=%s", params)


def external_bf_meta_rows(cur, bf_ids):
    """fetchall() of (id, name, company, location, working_volume_m3) for the
    ids. api_bf_benchmark.build_compare."""
    ph = ",".join(["%s"] * len(bf_ids))
    cur.execute(
            f"SELECT id, name, company, location, working_volume_m3 FROM bf_benchmark_external_bf "
            f"WHERE id IN ({ph}) ORDER BY id",
            bf_ids,
        )
    return cur.fetchall()


def external_bf_data_row(cur, bf_id, fy):
    """fetchone() of (param_json,) for one non-SAIL BF's FY entry.
    api_bf_benchmark GET/POST .../entry, _external_bf_values."""
    cur.execute(
        "SELECT param_json FROM bf_benchmark_external_data WHERE external_bf_id=%s AND fy=%s",
        (bf_id, fy),
    )
    return cur.fetchone()


def update_external_bf_data(cur, param_json, updated_at, bf_id, fy):
    """Overwrite one FY entry's JSON on the caller's cursor; the caller
    commits. api_bf_benchmark POST .../entry."""
    _keys.fits("updated_at", updated_at, 40)
    stamp, plain = _stamp_flagged("data.updated_at", updated_at)
    _ver.bump(cur)
    cur.execute(
            "UPDATE bf_benchmark_external_data SET param_json=%s, updated_at=%s, updated_at_plain=%s "
            "WHERE external_bf_id=%s AND fy=%s",
            (param_json, stamp, plain, bf_id, fy),
        )


def insert_external_bf_data(cur, bf_id, fy, param_json, now):
    """Insert one FY entry on the caller's cursor; the caller commits.
    api_bf_benchmark POST .../entry. A duplicate (bf, fy) raises v1's 1062
    text (its key was named uq_bf_benchmark_ext)."""
    _keys.fits("report_month", fy, 7, nullable=False)
    _keys.fits("created_at", now, 40)
    stamp, plain = _stamp_flagged("data.created_at", now)
    _ver.bump(cur)
    try:
        cur.execute(
                "INSERT INTO bf_benchmark_external_data (external_bf_id, fy, param_json, created_at, updated_at, "
                "created_at_plain, updated_at_plain) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (bf_id, _keys.fit_fy(fy), param_json, stamp, stamp, plain, plain),
            )
    except pymysql.err.IntegrityError as e:
        if e.args and e.args[0] == 1062:       # v1 named its unique key uq_bf_benchmark_ext
            raise type(e)(e.args[0], str(e.args[1]).replace(
                "bf_benchmark_external_data.uq_bf_external_data",
                "bf_benchmark_external_data.uq_bf_benchmark_ext")) from None
        raise


# ── cover_photos / report_cover_settings (cover_store) ──────────────────────
# Self-contained: each call opens its own connection, as cover_store's
# _query / _execute did (one commit per write).

COVER_PHOTO_COLS = ("id", "filename", "thumb_filename", "original_name", "width", "height",
                    "uploaded_by", "uploaded_at", "is_active")
COVER_SETTING_COLS = ("report_month", "design", "photo_mode", "photo_id", "updated_by", "updated_at")
_COVER_PHOTO_SELECT = ("SELECT id, filename, thumb_filename, original_name, width, height, "
                       f"created_by AS uploaded_by, {_iso('created_at', SQL_SECONDS)} AS uploaded_at, "
                       "is_active FROM cover_photo")


def _cover_query(sql: str, args=()) -> list:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, args)
        return cur.fetchall()
    finally:
        conn.close()


def _cover_execute(sql: str, args=(), prepare=None):
    """Run one cover write and commit; returns its lastrowid. `prepare(cur)`
    runs after the bump (month / master rows the write needs)."""
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        if prepare is not None:
            prepare(cur)
        cur.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def insert_cover_photo(filename, thumb_filename, original_name, width, height, uploaded_by, uploaded_at):
    """Insert one active photo; returns its id. cover_store.add_photo."""
    _keys.fits("filename", filename, 64, nullable=False)
    _keys.fits("thumb_filename", thumb_filename, 64, nullable=False)
    _keys.fits("original_name", original_name, 255, nullable=False)
    _keys.fits("uploaded_by", uploaded_by, 255)
    _keys.fits("uploaded_at", uploaded_at, 19)
    stamp = _stamp(SQL_SECONDS, _keys.fit_char(uploaded_at, 19), "uploaded_at")
    return _cover_execute(
            "INSERT INTO cover_photo (filename, thumb_filename, original_name, width, height,"
            " created_by, created_at, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s, 1)",
            (filename, thumb_filename, original_name, width, height, uploaded_by, stamp),
        )


def cover_photo_rows(photo_id):
    """fetchall() of COVER_PHOTO_COLS for one photo. cover_store.get_photo."""
    return _cover_query(f"{_COVER_PHOTO_SELECT} WHERE id = %s", (photo_id,))


def active_cover_photo_rows_newest_first():
    """fetchall() of COVER_PHOTO_COLS for active photos, newest first.
    cover_store.list_photos."""
    return _cover_query(f"{_COVER_PHOTO_SELECT} WHERE is_active = 1 ORDER BY id DESC")


def active_cover_photo_rows():
    """fetchall() of COVER_PHOTO_COLS for active photos (no order).
    cover_store._active_photo_ids."""
    return _cover_query(f"{_COVER_PHOTO_SELECT} WHERE is_active = 1 ORDER BY id")


def cover_photo_usage_rows():
    """fetchall() of (photo_id, months using it). cover_store.list_photos.

    PARITY SHIM: v1's GROUP BY (temporary table, no ORDER BY) returned the
    groups in first-appearance order along the primary-key scan
    (report_month); ORDER BY MIN(report_month) reproduces it."""
    return _cover_query(
        "SELECT photo_id, COUNT(*) FROM report_cover_setting WHERE photo_id IS NOT NULL "
        "GROUP BY photo_id ORDER BY MIN(report_month), photo_id")


def deactivate_cover_photo(photo_id):
    """Take one photo out of the library. cover_store.deactivate_photo."""
    _cover_execute("UPDATE cover_photo SET is_active = 0 WHERE id = %s", (photo_id,))


def cover_setting_rows(report_month):
    """fetchall() of COVER_SETTING_COLS for the month. cover_store.get_setting."""
    return _cover_query(
        f"SELECT report_month, design, photo_mode, photo_id, updated_by, "
        f"{_iso('updated_at', SQL_SECONDS)} AS updated_at FROM report_cover_setting WHERE report_month = %s",
        (report_month,))


def replace_cover_setting(report_month, design, photo_mode, photo_id, updated_by, updated_at):
    """Save the month's cover choice. cover_store.save_setting."""
    month = _keys.fit_month(report_month)
    _keys.check_month(month)
    _keys.fits("design", design, 24, nullable=False)
    _keys.fits("photo_mode", photo_mode, 8, nullable=False)
    _keys.fits("updated_by", updated_by, 255)
    _keys.fits("updated_at", updated_at, 19)
    stamp = _stamp(SQL_SECONDS, _keys.fit_char(updated_at, 19), "updated_at")
    _cover_execute(
        "REPLACE INTO report_cover_setting"
        " (report_month, design, photo_mode, photo_id, updated_by, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
        (month, design, photo_mode, photo_id, updated_by, stamp),
        prepare=lambda cur: _keys.ensure_month(cur, month, bump=False),
    )
