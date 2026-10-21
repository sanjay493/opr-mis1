"""Miscellaneous small repositories:
- market_price_trend_monthly ("Movement of Key Prices - International",
  page 2.41) and macro_indicators_monthly ("India Macro Economic
  Indicators", page 2.42), both entered via /data-entry/market-intel or the
  market-commentary PDF upload;
- pdf_item_alias (learned PDF label -> item corrections);
- rail_prod_despatch (page 18.5), ready_reckoner_pages (Annexure-1/2),
  major_unit_daily_record (Annexure-3);
- power_data_table (Power-OIS), steel_sector_performance_table (JPC
  releases), the bf_benchmark_* tables, and the cover_photos /
  report_cover_settings cover library.

The db.py functions moved here verbatim (re-exported from db.py). The named
queries after them are the statements that used to live inline in main.py
/ api_*.py / page_*.py / cover_store.py / scripts, moved verbatim.
"""
import json
from typing import Any, Dict, List, Optional

import activity_context
from dbengine import connect
from repo import version as _ver
from repo import conn as rc
from repo.conn import row_dict as _row_dict


# ── "Movement of Key Prices - International" (page 2.41) ───────────────────
# Backing store for page_market_prices.py + /data-entry/market-intel. See
# scripts/migrate_add_market_intel.sql.

def get_market_price_trend(report_months: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {report_month: {series_code: value}}."""
    conn = connect()
    cur = conn.cursor()
    out = {m: {} for m in report_months}
    if report_months:
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(f"SELECT report_month, series_code, value FROM market_price_trend_monthly "
                    f"WHERE report_month IN ({ph})", report_months)
        for rm, series, value in cur.fetchall():
            out.setdefault(rm, {})[series] = value
    conn.close()
    return out


def save_market_price_trend(rows: List[Dict[str, Any]]) -> int:
    """Upsert market_price_trend_monthly rows: {report_month, series_code, value}."""
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO market_price_trend_monthly (report_month, series_code, value)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value = new.value
        """, (r["report_month"], r["series_code"], r.get("value")))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return len(rows)


# ── "India Macro Economic Indicators" (page 2.42) ───────────────────────────
# Backing store for page_macro_indicators.py + /data-entry/market-intel. See
# scripts/migrate_add_market_intel.sql.

def get_macro_indicators(report_months: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {report_month: {metric_code: value}}."""
    conn = connect()
    cur = conn.cursor()
    out = {m: {} for m in report_months}
    if report_months:
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(f"SELECT report_month, metric_code, value FROM macro_indicators_monthly "
                    f"WHERE report_month IN ({ph})", report_months)
        for rm, metric, value in cur.fetchall():
            out.setdefault(rm, {})[metric] = value
    conn.close()
    return out


def save_macro_indicators(rows: List[Dict[str, Any]]) -> int:
    """Upsert macro_indicators_monthly rows: {report_month, metric_code, value}."""
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO macro_indicators_monthly (report_month, metric_code, value)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value = new.value
        """, (r["report_month"], r["metric_code"], r.get("value")))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return len(rows)


# ── Moved from db.py: pdf_item_alias, rail, ready reckoner, major units ─────

def get_pdf_item_aliases(plant: str) -> Dict[str, Any]:
    """User-saved PDF label corrections for a plant: {pdf_label: (item_name, convert_t)}."""
    conn = connect()
    rows = conn.execute("""
        SELECT pdf_label, item_name, convert_t FROM pdf_item_alias WHERE plant_name = %s
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
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM pdf_item_alias WHERE plant_name=%s AND pdf_label=%s",
        (plant, pdf_label))
    conn.execute("""
        INSERT INTO pdf_item_alias (plant_name, pdf_label, item_name, convert_t)
        VALUES (%s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE item_name = new.item_name, convert_t = new.convert_t
    """, (plant, pdf_label, item_name, convert_t))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    new = {"plant_name": plant, "pdf_label": pdf_label, "item_name": item_name, "convert_t": convert_t}
    activity_context.record(f"pdf_item_alias/{plant}/{pdf_label}", old, new)


# ── "Rail Production & Dispatch from BSP" (page 18.5) ──────────────────────
# Backing store for page_rail_report.py + /data-entry/rail-report. See
# scripts/migrate_add_rail_report.sql.

def get_rail_report_data(fys: List[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """-> {financial_year: {metric: {"value": v, "note": n}}}."""
    conn = connect()
    cur = conn.cursor()
    out = {fy: {} for fy in fys}
    if fys:
        ph = ",".join(["%s"] * len(fys))
        cur.execute(f"SELECT financial_year, metric, value, note FROM rail_prod_despatch "
                    f"WHERE financial_year IN ({ph})", fys)
        for fy, metric, value, note in cur.fetchall():
            out.setdefault(fy, {})[metric] = {"value": value, "note": note}
    conn.close()
    return out


def save_rail_report_data(rows: List[Dict[str, Any]]) -> int:
    """Upsert rail_prod_despatch rows: {financial_year, metric, value, note}."""
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO rail_prod_despatch (financial_year, metric, value, note)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                value = new.value, note = new.note
        """, (r["financial_year"], r["metric"], r.get("value"), r.get("note")))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return len(rows)


# ── "Ready Reckoner" (Annexure-1: 5 ISPs / Annexure-2: 3 SSPs) ─────────────
# Backing store for page_ready_reckoner.py + its editor (/data-entry/ready-
# reckoner). See scripts/migrate_ready_reckoner_structured.sql. Not month-
# scoped — see this table's own comment in init_db().
#
# capacity_rows/product_mix_headers/product_mix_rows store PLAIN DATA only
# (JSON, no HTML/markup/style of any kind) — per direct instruction,
# 2026-09-21: the previous design (capacity_html/product_mix_html, raw
# editor-authored HTML strings rendered with Jinja's |safe) let formatting
# leak into the stored content itself. All presentation (colors, bold
# totals, line breaks) is now applied at render time instead — React in the
# live preview/editor, Jinja+CSS in the PDF template (ready_reckoner_
# plant.html) — never stored. See scripts/migrate_ready_reckoner_
# structured.py for the one-time migration that parsed the old HTML into
# this shape.
#
# Shapes (all json.dumps'd into TEXT columns, json.loads'd back out below):
#   capacity_rows:       [{"item": str, "details": str, "capacity": str, "is_total": bool}, ...]
#   product_mix_headers: [str, ...]                 -- this plant's own column titles
#   product_mix_rows:    [{"cells": [str, ...], "is_total": bool}, ...]  -- len(cells) == len(headers)
# product_mix_caption is plain TEXT (not JSON) — a one-line note some plants
# carry above their Product Mix table (e.g. BSL's "representative grade
# families per product — see full spec sheet for exhaustive list"); most
# plants leave it blank.
# A cell's "\n" means a line break (rendered as <br> at display time), never
# literal HTML.

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
        f"SELECT {','.join(_READY_RECKONER_COLS)} FROM ready_reckoner_pages "
        f"ORDER BY plant_group, sort_order, plant_code"
    )
    rows = [_decode_ready_reckoner_row(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_ready_reckoner_page(plant_code: str) -> Optional[dict]:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {','.join(_READY_RECKONER_COLS)} FROM ready_reckoner_pages WHERE plant_code = %s",
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
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ready_reckoner_pages (plant_code, plant_name, plant_group, sort_order)
        VALUES (%s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            plant_name = new.plant_name, plant_group = new.plant_group,
            sort_order = new.sort_order
    """, (row["plant_code"], row.get("plant_name"), row["plant_group"], int(row.get("sort_order") or 0)))
    _ver.bump(conn)
    conn.commit()
    conn.close()


def save_ready_reckoner_content(
    plant_code: str, capacity_rows: Optional[list] = None,
    product_mix_headers: Optional[list] = None, product_mix_rows: Optional[list] = None,
    product_mix_caption: Optional[str] = None, updated_by: str = "",
) -> None:
    """Updates one or more of the plain-data fields for one plant, from the
    /data-entry/ready-reckoner form's Save action. None (not just an empty
    list) means "leave this field alone" — the capacity editor's Save action
    only ever sends capacity_rows, and must NOT blank out product_mix_*
    just because those fields weren't part of this particular payload.
    product_mix_headers and product_mix_rows are always sent together by
    the editor (changing column count means both change), but are still
    independently optional here for the same reason. A plain UPDATE, not an
    upsert: the row always already exists by this point (created by the
    one-time backfill via upsert_ready_reckoner_master, which owns
    plant_name/plant_group/sort_order) — MySQL's ON DUPLICATE KEY UPDATE
    still validates every column in the INSERT list against NOT NULL
    constraints even when it ends up taking the UPDATE branch, so a
    partial insert (omitting plant_group here) fails outright rather than
    falling through."""
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
    cur = conn.cursor()
    cur.execute(f"UPDATE ready_reckoner_pages SET {', '.join(sets)} WHERE plant_code = %s", args)
    _ver.bump(conn)
    conn.commit()
    conn.close()


def save_ready_reckoner_image(plant_code: str, image_path: str, updated_by: str) -> None:
    """Updates just the process-flow diagram's file path for one plant, from
    the inline editor's image-upload control. Same plain-UPDATE reasoning
    as save_ready_reckoner_content."""
    import datetime as _dt
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        UPDATE ready_reckoner_pages
        SET process_flow_image_path = %s, updated_by = %s, updated_at = %s
        WHERE plant_code = %s
    """, (image_path, updated_by, _dt.datetime.now().isoformat(timespec="seconds"), plant_code))
    _ver.bump(conn)
    conn.commit()
    conn.close()


# ── Annexure-3 : 5 ISPs Major Units Records — Daily best (see
# major_unit_daily_record's own comment above and page_major_unit_records.py) ──

_MAJOR_UNIT_DAILY_COLS = (
    "plant_code", "unit_label", "unit_of_measure", "value",
    "record_date", "remarks", "sort_order", "updated_by", "updated_at",
)


def get_major_unit_daily_records(plant_code: str) -> List[dict]:
    """-> every unit row for one plant, in display order."""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {','.join(_MAJOR_UNIT_DAILY_COLS)} FROM major_unit_daily_record "
        f"WHERE plant_code = %s ORDER BY sort_order",
        (plant_code,),
    )
    rows = [dict(zip(_MAJOR_UNIT_DAILY_COLS, r)) for r in cur.fetchall()]
    conn.close()
    return rows


def get_major_unit_daily_records_all() -> Dict[str, Dict[str, dict]]:
    """-> {plant_code: {unit_label: row_dict}} for every plant — used by
    page_major_unit_records.generate_major_unit_page to look up one plant's
    Daily figures alongside its live-computed Annual/Monthly bests."""
    conn = connect()
    cur = conn.cursor()
    cur.execute(f"SELECT {','.join(_MAJOR_UNIT_DAILY_COLS)} FROM major_unit_daily_record")
    out: Dict[str, Dict[str, dict]] = {}
    for r in cur.fetchall():
        d = dict(zip(_MAJOR_UNIT_DAILY_COLS, r))
        out.setdefault(d["plant_code"], {})[d["unit_label"]] = d
    conn.close()
    return out


def save_major_unit_daily_record(plant_code: str, unit_label: str, value: Optional[float],
                                  unit_of_measure: Optional[str], record_date: Optional[str],
                                  remarks: Optional[str], sort_order: int, updated_by: str = "") -> None:
    """Upsert one unit's Daily best — used by both the one-time backfill
    (scripts/backfill_major_unit_daily_records.py) and the
    /data-entry/major-unit-daily editor (see main.py's
    /api/major-unit-daily/{plant_code} POST)."""
    import datetime as _dt
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO major_unit_daily_record
            (plant_code, unit_label, unit_of_measure, value, record_date,
             remarks, sort_order, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            unit_of_measure = new.unit_of_measure, value = new.value,
            record_date = new.record_date, remarks = new.remarks,
            sort_order = new.sort_order, updated_by = new.updated_by,
            updated_at = new.updated_at
    """, (plant_code, unit_label, unit_of_measure, value, record_date, remarks,
          sort_order, updated_by, _dt.datetime.now().isoformat(timespec="seconds")))
    _ver.bump(conn)
    conn.commit()
    conn.close()


# ── Named queries (moved verbatim from their callers) ───────────────────────
# `cur` parameters take the caller's cursor and `conn` parameters a
# db.connect() connection (conn.execute opens a fresh cursor, as the caller
# did), so the caller's connection, transaction, commit point and row type
# are unchanged. Nothing taking a cursor or connection commits.

# ── power_data_table ("Power-OIS"; page_power_data, api_power_omi) ──────────

_POWER_TABLE = "power_data_table"


def power_value_row(cur, report_month, plant_name, item_name):
    """fetchone() of (value,) for one power figure.
    api_power_omi._existing_conflicts."""
    cur.execute(
                "SELECT value FROM power_data_table "
                "WHERE report_month = %s AND plant_name = %s AND item_name = %s",
                (report_month, plant_name, item_name),
            )
    return cur.fetchone()


def upsert_power_value(cur, report_month, plant_name, item_name, value):
    """Upsert one power figure on the caller's cursor; the caller commits.
    api_power_omi POST /insert."""
    _ver.bump(cur)
    cur.execute("""
                INSERT INTO power_data_table (report_month, plant_name, item_name, value)
                VALUES (%s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE value = new.value
            """, (report_month, plant_name, item_name, value))


def power_rows_for_months(cur, months):
    """fetchall() of (report_month, plant_name, item_name, value) for the
    months. page_power_data.generate_power_data."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(
            f"SELECT report_month, plant_name, item_name, value FROM {_POWER_TABLE} "
            f"WHERE report_month IN ({ph})",
            months,
        )
    return cur.fetchall()


def power_plants_for_month(report_month):
    """fetchall() of (plant_name,) with any power row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute(f"SELECT DISTINCT plant_name FROM {_POWER_TABLE} WHERE report_month = %s",
                    [report_month])
        return cur.fetchall()


# ── steel_sector_performance_table (JPC release archive) ────────────────────

def upsert_steel_sector_performance(cur, report_month, data_json, source_file, created_at):
    """Archive one release's preview JSON on the caller's cursor; the caller
    commits. main POST /api/steel-sector-performance/confirm."""
    _ver.bump(cur)
    cur.execute("""
            INSERT INTO steel_sector_performance_table (report_month, data_json, source_file, created_at)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                data_json = new.data_json,
                source_file = new.source_file,
                created_at = new.created_at
        """, (report_month, data_json, source_file, created_at))


def steel_sector_latest_row(cur, report_month):
    """fetchone() of (report_month, data_json, source_file) for the newest
    release at or before report_month. page_steel_sector_performance._load_row."""
    cur.execute("""
            SELECT report_month, data_json, source_file FROM steel_sector_performance_table
            WHERE report_month <= %s
            ORDER BY report_month DESC LIMIT 1
        """, (report_month,))
    return cur.fetchone()


def steel_sector_data_json_rows(cur):
    """fetchall() of (data_json,) for every release, oldest first.
    page_steel_sector_performance (trend series)."""
    cur.execute("SELECT data_json FROM steel_sector_performance_table ORDER BY report_month")
    return cur.fetchall()


def steel_sector_any_row(report_month):
    """True when steel_sector_performance_table has a row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM steel_sector_performance_table WHERE report_month = %s LIMIT 1",
                    [report_month])
        return bool(cur.fetchall())


# ── major_unit_daily_record (beyond the moved db.py functions) ──────────────

def major_unit_daily_values(conn, plant_code):
    """fetchall() of (unit_label, value) for one plant.
    api_production_loss._unit_weights."""
    return conn.execute("SELECT unit_label, value FROM major_unit_daily_record WHERE plant_code=%s",
                        (plant_code,)).fetchall()


def major_unit_daily_label_row(cur, plant_code, unit_label):
    """fetchone() of (value, record_date, updated_by, updated_at) for one
    unit label. scripts/rename_major_unit_labels."""
    cur.execute(
                "SELECT value, record_date, updated_by, updated_at "
                "FROM major_unit_daily_record WHERE plant_code = %s AND unit_label = %s",
                (plant_code, unit_label),
            )
    return cur.fetchone()


def rename_major_unit_label(cur, new_label, plant_code, old_label):
    """Rename one unit label on the caller's cursor; the caller commits and
    reads cur.rowcount. scripts/rename_major_unit_labels."""
    _ver.bump(cur)
    cur.execute(
                "UPDATE major_unit_daily_record SET unit_label = %s "
                "WHERE plant_code = %s AND unit_label = %s",
                (new_label, plant_code, old_label),
            )


# ── bf_benchmark_sail_meta / _external_bf / _external_data ──────────────────
# (api_bf_benchmark, page_bf_large_annexure)

def bf_sail_working_volume_rows(cur):
    """fetchall() of (plant, unit, working_volume_m3).
    api_bf_benchmark get_params / _sail_working_volumes."""
    cur.execute("SELECT plant, unit, working_volume_m3 FROM bf_benchmark_sail_meta")
    return cur.fetchall()


def bf_sail_meta_rows(cur):
    """fetchall() of (plant, unit, working_volume_m3, updated_at), ordered.
    api_bf_benchmark GET /sail-meta."""
    cur.execute("SELECT plant, unit, working_volume_m3, updated_at FROM bf_benchmark_sail_meta ORDER BY plant, unit")
    return cur.fetchall()


def upsert_bf_sail_meta(cur, plant, unit, working_volume_m3, updated_at):
    """Upsert one SAIL BF's Working Volume on the caller's cursor; the caller
    commits. api_bf_benchmark PATCH /sail-meta."""
    _ver.bump(cur)
    cur.execute(
        "INSERT INTO bf_benchmark_sail_meta (plant, unit, working_volume_m3, updated_at) VALUES (%s, %s, %s, %s) "
        "AS new ON DUPLICATE KEY UPDATE working_volume_m3=new.working_volume_m3, updated_at=new.updated_at",
        (plant, unit, working_volume_m3, updated_at),
    )


def bf_sail_working_volume_row(cur, plant, unit):
    """fetchone() of (working_volume_m3,) for one SAIL BF.
    page_bf_large_annexure._sail_static_working_volume."""
    cur.execute(
            "SELECT working_volume_m3 FROM bf_benchmark_sail_meta WHERE plant=%s AND unit=%s",
            (plant, unit),
        )
    return cur.fetchone()


def external_bf_list_rows(cur, active_only):
    """fetchall() of (id, name, company, location, working_volume_m3, active,
    created_at, latest FY) by name. api_bf_benchmark GET /external-bfs."""
    sql = (
        "SELECT b.id, b.name, b.company, b.location, b.working_volume_m3, b.active, b.created_at, "
        "(SELECT MAX(d.report_month) FROM bf_benchmark_external_data d WHERE d.external_bf_id=b.id) "
        "FROM bf_benchmark_external_bf b"
    )
    if active_only:
        sql += " WHERE b.active=1"
    sql += " ORDER BY b.name"
    cur.execute(sql)
    return cur.fetchall()


def insert_external_bf(cur, name, company, location, created_at):
    """Insert one non-SAIL BF on the caller's cursor; the caller commits and
    reads cur.lastrowid. api_bf_benchmark POST /external-bfs."""
    _ver.bump(cur)
    cur.execute(
        "INSERT INTO bf_benchmark_external_bf (name, company, location, active, created_at) VALUES (%s, %s, %s, 1, %s)",
        (name, company, location, created_at),
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
            f"SELECT id, name, company, location, working_volume_m3 FROM bf_benchmark_external_bf WHERE id IN ({ph})",
            bf_ids,
        )
    return cur.fetchall()


def external_bf_data_row(cur, bf_id, fy):
    """fetchone() of (param_json,) for one non-SAIL BF's FY entry.
    api_bf_benchmark GET/POST .../entry, _external_bf_values."""
    cur.execute(
        "SELECT param_json FROM bf_benchmark_external_data WHERE external_bf_id=%s AND report_month=%s",
        (bf_id, fy),
    )
    return cur.fetchone()


def update_external_bf_data(cur, param_json, updated_at, bf_id, fy):
    """Overwrite one FY entry's JSON on the caller's cursor; the caller
    commits. api_bf_benchmark POST .../entry."""
    _ver.bump(cur)
    cur.execute(
            "UPDATE bf_benchmark_external_data SET param_json=%s, updated_at=%s "
            "WHERE external_bf_id=%s AND report_month=%s",
            (param_json, updated_at, bf_id, fy),
        )


def insert_external_bf_data(cur, bf_id, fy, param_json, now):
    """Insert one FY entry on the caller's cursor; the caller commits.
    api_bf_benchmark POST .../entry."""
    _ver.bump(cur)
    cur.execute(
            "INSERT INTO bf_benchmark_external_data (external_bf_id, report_month, param_json, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (bf_id, fy, param_json, now, now),
        )


# ── cover_photos / report_cover_settings (cover_store) ──────────────────────
# Self-contained: each call opens its own connection, as cover_store's
# _query / _execute did (one commit per write).

COVER_PHOTO_COLS = ("id", "filename", "thumb_filename", "original_name", "width", "height",
                    "uploaded_by", "uploaded_at", "is_active")
COVER_SETTING_COLS = ("report_month", "design", "photo_mode", "photo_id", "updated_by", "updated_at")


def _cover_query(sql: str, args=()) -> list:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, args)
        return cur.fetchall()
    finally:
        conn.close()


def _cover_execute(sql: str, args=()):
    """Run one cover write and commit; returns its lastrowid."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, args)
        _ver.bump(conn)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def insert_cover_photo(filename, thumb_filename, original_name, width, height, uploaded_by, uploaded_at):
    """Insert one active photo; returns its id. cover_store.add_photo."""
    return _cover_execute(
            "INSERT INTO cover_photos (filename, thumb_filename, original_name, width, height,"
            " uploaded_by, uploaded_at, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s, 1)",
            (filename, thumb_filename, original_name, width, height, uploaded_by, uploaded_at),
        )


def cover_photo_rows(photo_id):
    """fetchall() of COVER_PHOTO_COLS for one photo. cover_store.get_photo."""
    return _cover_query(f"SELECT {', '.join(COVER_PHOTO_COLS)} FROM cover_photos WHERE id = %s", (photo_id,))


def active_cover_photo_rows_newest_first():
    """fetchall() of COVER_PHOTO_COLS for active photos, newest first.
    cover_store.list_photos."""
    return _cover_query(f"SELECT {', '.join(COVER_PHOTO_COLS)} FROM cover_photos WHERE is_active = 1 ORDER BY id DESC")


def active_cover_photo_rows():
    """fetchall() of COVER_PHOTO_COLS for active photos (no order).
    cover_store._active_photo_ids."""
    return _cover_query(f"SELECT {', '.join(COVER_PHOTO_COLS)} FROM cover_photos WHERE is_active = 1")


def cover_photo_usage_rows():
    """fetchall() of (photo_id, months using it). cover_store.list_photos."""
    return _cover_query(
        "SELECT photo_id, COUNT(*) FROM report_cover_settings WHERE photo_id IS NOT NULL GROUP BY photo_id")


def deactivate_cover_photo(photo_id):
    """Take one photo out of the library. cover_store.deactivate_photo."""
    _cover_execute("UPDATE cover_photos SET is_active = 0 WHERE id = %s", (photo_id,))


def cover_setting_rows(report_month):
    """fetchall() of COVER_SETTING_COLS for the month. cover_store.get_setting."""
    return _cover_query(f"SELECT {', '.join(COVER_SETTING_COLS)} FROM report_cover_settings WHERE report_month = %s",
                        (report_month,))


def replace_cover_setting(report_month, design, photo_mode, photo_id, updated_by, updated_at):
    """Save the month's cover choice. cover_store.save_setting."""
    _cover_execute(
        "REPLACE INTO report_cover_settings"
        " (report_month, design, photo_mode, photo_id, updated_by, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
        (report_month, design, photo_mode, photo_id, updated_by, updated_at),
    )
