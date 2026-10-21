"""v1 <-> v2 value codec (ruling R5).

Pure Python, no SQL and no DB access. One definition of every value-level
rule that the v1 -> v2 migration (tools/migrate_v1_to_v2.py), its tests,
verify_v2 (Task 6b) and the Task 7 repositories (repo.techno, repo.ops,
repo.text) must agree on:

  * TIMESTAMPS  v1 VARCHAR timestamps in mixed formats -> DATETIME(6), and
                back to the exact original string (TS_COLUMNS, parse_ts,
                render_ts, DATE_COLUMNS).
  * TECHNO      a v1 techno_data.techno_json blob <-> one techno_upload row
                plus one techno_value row per leaf (encode_techno,
                decode_techno).
  * TEXT        the 9 v1 narrative / note tables <-> report_text rows
                (TEXT_SCOPES, encode_text_row, decode_text_rows).
  * PRODUCTION  which v1 table feeds which production_monthly value and
                has_* flag (PRODUCTION_SOURCES).

The decoders take what the app's DB layer hands back: DATETIME / DATE as the
MySQL text form (dbengine maps them to str, e.g. '2026-08-23 09:41:58.078837'
for DATETIME(6)) or as datetime / date objects; JSON columns as str.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ═════════════════════════════════════════════════════════════════════════════
# TIMESTAMPS
# ═════════════════════════════════════════════════════════════════════════════
#
# Each v1 VARCHAR timestamp column was written by exactly one kind of writer,
# so each column has ONE format. The DATETIME stores the wall-clock value the
# v1 string spelled, never shifted: the UTC columns keep UTC wall time (the
# '+00:00' is dropped on the way in and put back on the way out), the local
# columns keep the naive local (IST) wall time. Rendering a stored value with
# its column's format gives back the v1 string byte for byte; the migration
# checks that for every value and refuses to load a value that does not.
#
# Formats:
#   ISO_UTC      datetime.now(timezone.utc).isoformat()
#                '2026-09-09T05:58:59.243471+00:00'           tz UTC
#   ISO_LOCAL    datetime.now().isoformat()
#                '2026-08-23T09:41:58.078837'                 tz local (IST)
#   ISO_SECONDS  datetime.now().isoformat(timespec="seconds")
#                '2026-09-23T13:41:31'                        tz local (IST)
#   SQL_SECONDS  strftime('%Y-%m-%d %H:%M:%S') or MySQL NOW() in the IST
#                session, or a v1 DATETIME column as dbengine returns it
#                '2026-06-07 22:15:11'                        tz local (IST)
#
# Fractional seconds: Python's isoformat() prints '.ffffff' only when the
# microsecond is non-zero, and every ISO_UTC / ISO_LOCAL writer used plain
# isoformat(). render_ts uses the same isoformat(), so a v1 value written at
# microsecond 0 ('2026-08-23T09:41:58') renders back without a fraction and
# one written at any other microsecond renders back with all six digits. The
# only string this cannot reproduce is an explicit '.000000', which no v1
# writer can produce; parse_ts rejects it (and any other non-canonical form),
# so the migration fails loudly instead of changing it.

ISO_UTC = "iso_utc"
ISO_LOCAL = "iso_local"
ISO_SECONDS = "iso_seconds"
SQL_SECONDS = "sql_seconds"
DATE = "date"

TS_FORMATS = {
    ISO_UTC: "UTC",
    ISO_LOCAL: "local",
    ISO_SECONDS: "local",
    SQL_SECONDS: "local",
}

# v2 "table.column" -> (v1 "table.column", format). tz is TS_FORMATS[format];
# tz_was_utc below is the same fact as a per-column boolean.
# Evidence per column (writer, and the shapes measured on
# mis_reports_baseline 2026-10-22) is in the Task 6a report.
TS_COLUMNS: Dict[str, Tuple[str, str]] = {
    # ops tables: UTC ISO with '+00:00' (auth / admin / ops writers)
    "activity_log.created_at":            ("activity_log.timestamp", ISO_UTC),
    "admin_notification.created_at":      ("admin_notifications.created_at", ISO_UTC),
    "allowed_email.created_at":           ("allowed_emails.added_at", ISO_UTC),
    "allowed_email.barred_at":            ("allowed_emails.barred_at", ISO_UTC),
    "app_user.created_at":                ("users.created_at", ISO_UTC),
    "app_user.updated_at":                ("users.updated_at", ISO_UTC),
    "otp_code.created_at":                ("otp_codes.created_at", ISO_UTC),
    "otp_code.expires_at":                ("otp_codes.expires_at", ISO_UTC),
    "page_visit.created_at":              ("page_visits.timestamp", ISO_UTC),
    "bf_benchmark_sail_meta.updated_at":  ("bf_benchmark_sail_meta.updated_at", ISO_UTC),
    # mixed columns: ISO_UTC, or SQL_SECONDS where the row's *_plain flag is 1
    # (TS_FLAGGED)
    "bf_benchmark_external_bf.created_at":   ("bf_benchmark_external_bf.created_at", ISO_UTC),
    "bf_benchmark_external_data.created_at": ("bf_benchmark_external_data.created_at", ISO_UTC),
    "bf_benchmark_external_data.updated_at": ("bf_benchmark_external_data.updated_at", ISO_UTC),
    # naive local ISO with microseconds
    "breakdown.created_at":               ("breakdown_table.created_at", ISO_LOCAL),
    "breakdown.updated_at":               ("breakdown_table.updated_at", ISO_LOCAL),
    "item_capacity.created_at":           ("item_capacity_table.created_at", ISO_LOCAL),
    "item_capacity.updated_at":           ("item_capacity_table.updated_at", ISO_LOCAL),
    "special_steel_grade_club.created_at": ("special_steel_grade_clubs.created_at", ISO_LOCAL),
    "steel_sector_performance.created_at": ("steel_sector_performance_table.created_at", ISO_LOCAL),
    "todo_job.created_at":                ("todo_jobs.created_at", ISO_LOCAL),
    "todo_job.completed_at":              ("todo_jobs.completed_at", ISO_LOCAL),
    "daily_work_log.created_at":          ("daily_work_log.created_at", ISO_LOCAL),
    # naive local ISO, whole seconds
    "major_unit_daily_record.updated_at": ("major_unit_daily_record.updated_at", ISO_SECONDS),
    # naive local 'YYYY-MM-DD HH:MM:SS'
    "cover_photo.created_at":             ("cover_photos.uploaded_at", SQL_SECONDS),
    "report_cover_setting.updated_at":    ("report_cover_settings.updated_at", SQL_SECONDS),
    "extraction_log.created_at":          ("extraction_log.logged_at", SQL_SECONDS),
    # mixed: SQL_SECONDS, or ISO_LOCAL where created_at_iso is 1 (TS_FLAGGED)
    "techno_upload.created_at":           ("techno_data.created_at", SQL_SECONDS),
    # report_text.updated_at depends on the scope: see TEXT_SCOPES.
}

# Columns whose v1 strings come in two formats, with a per-row flag column:
# v2 column -> (flag column, alternate format). flag 0 = the column's format
# in TS_COLUMNS, flag 1 = the alternate. The two formats of each column never
# share a spelling (' ' vs 'T', '+00:00' vs naive), so the flag is decided
# by which one the v1 string parses in. Writers must set the flag to match
# the form they write (render_ts_flagged reads it back).
#   bf_benchmark_external_*: ISO_UTC now, SQL_SECONDS in legacy rows
#   techno_upload.created_at: NOW() (SQL_SECONDS) in merge_upsert_techno_data,
#     datetime.now().isoformat() (ISO_LOCAL) in the other techno_data writers
TS_FLAGGED: Dict[str, Tuple[str, str]] = {
    "bf_benchmark_external_bf.created_at": ("created_at_plain", SQL_SECONDS),
    "bf_benchmark_external_data.created_at": ("created_at_plain", SQL_SECONDS),
    "bf_benchmark_external_data.updated_at": ("updated_at_plain", SQL_SECONDS),
    "techno_upload.created_at": ("created_at_iso", ISO_LOCAL),
}

# v1 'YYYY-MM-DD' strings -> DATE. v2 "table.column" -> v1 "table.column".
DATE_COLUMNS: Dict[str, str] = {
    "capital_repair.actual_start":      "capital_repair_table.actual_start",
    "capital_repair.actual_end":        "capital_repair_table.actual_end",
    "sail_stock_snapshot.snapshot_date": "sail_stock_snapshot_table.snapshot_date",
    "todo_job.due_date":                "todo_jobs.due_date",
    "daily_work_log.work_date":         "daily_work_log.work_date",
    "major_unit_daily_record.record_date": "major_unit_daily_record.record_date",
}


def tz_was_utc(column: str) -> bool:
    """True when the v2 column's v1 strings were UTC ('+00:00')."""
    return TS_FORMATS[TS_COLUMNS[column][1]] == "UTC"


class CodecError(ValueError):
    """A v1 value the v2 model cannot hold exactly."""


def _as_datetime(value) -> _dt.datetime:
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.date):
        return _dt.datetime(value.year, value.month, value.day)
    return _dt.datetime.fromisoformat(str(value))


def render_ts(fmt: str, value) -> Optional[str]:
    """A stored DATETIME (datetime, or the MySQL text dbengine returns) ->
    the v1 string in format `fmt`. None stays None."""
    if value is None:
        return None
    if fmt == DATE:
        return render_date(value)
    dt = _as_datetime(value)
    if dt.tzinfo is not None:
        raise CodecError(f"stored timestamps are naive, got {value!r}")
    if fmt == ISO_UTC:
        return dt.replace(tzinfo=_dt.timezone.utc).isoformat()
    if fmt == ISO_LOCAL:
        return dt.isoformat()
    if fmt == ISO_SECONDS:
        return dt.isoformat(timespec="seconds")
    if fmt == SQL_SECONDS:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    raise CodecError(f"unknown timestamp format {fmt!r}")


def parse_ts(fmt: str, text) -> Optional[_dt.datetime]:
    """A v1 string in format `fmt` -> the naive datetime to store. Raises
    CodecError unless render_ts(fmt, result) == text exactly."""
    if text is None:
        return None
    if fmt == DATE:
        return parse_date(text)
    if not isinstance(text, str):
        raise CodecError(f"expected a {fmt} string, got {text!r}")
    try:
        dt = _dt.datetime.fromisoformat(text)
    except ValueError as e:
        raise CodecError(f"not a timestamp: {text!r}") from e
    if fmt == ISO_UTC:
        if dt.utcoffset() != _dt.timedelta(0):
            raise CodecError(f"expected a '+00:00' UTC timestamp, got {text!r}")
        dt = dt.replace(tzinfo=None)
    elif dt.tzinfo is not None:
        raise CodecError(f"expected a naive {fmt} timestamp, got {text!r}")
    if render_ts(fmt, dt) != text:
        raise CodecError(f"{text!r} is not in the {fmt} format (would render as "
                         f"{render_ts(fmt, dt)!r})")
    return dt


def parse_ts_flagged(column: str, text) -> Tuple[Optional[_dt.datetime], int]:
    """For the TS_FLAGGED columns: a v1 string in the column's format (flag
    0) or its alternate format (flag 1) -> (datetime, flag)."""
    if text is None:
        return None, 0
    fmt = TS_COLUMNS[column][1]
    alt = TS_FLAGGED[column][1]
    try:
        return parse_ts(fmt, text), 0
    except CodecError:
        return parse_ts(alt, text), 1


def render_ts_flagged(column: str, value, flag) -> Optional[str]:
    fmt = TS_FLAGGED[column][1] if flag else TS_COLUMNS[column][1]
    return render_ts(fmt, value)


def render_date(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        value = value.date()
    if isinstance(value, _dt.date):
        return value.isoformat()
    return _dt.date.fromisoformat(str(value)).isoformat()


def parse_date(text) -> Optional[_dt.date]:
    """A v1 'YYYY-MM-DD' string -> date; raises CodecError for anything that
    would not render back identically ('' included)."""
    if text is None:
        return None
    try:
        d = _dt.date.fromisoformat(str(text))
    except ValueError as e:
        raise CodecError(f"not a YYYY-MM-DD date: {text!r}") from e
    if d.isoformat() != text:
        raise CodecError(f"{text!r} is not in the YYYY-MM-DD format")
    return d


# ═════════════════════════════════════════════════════════════════════════════
# TECHNO
# ═════════════════════════════════════════════════════════════════════════════
#
# v1 techno_json is {period: {param_key: value}} with period in
# ('month', 'till_month'). Each leaf becomes one techno_value row:
#   int    num = value, is_int = 1, raw NULL      (5 stays 5)
#   float  num = value, is_int = 0, raw NULL      (5.0 stays 5.0)
#   other  num NULL, is_int 0, raw = json.dumps(value): a string, an object,
#          a bool, or the JSON literal null (an explicit null key stays
#          distinct from a missing key); also an int beyond +-2^53 (a DOUBLE
#          cannot hold it exactly) and -0.0 (a DOUBLE column may not keep
#          the sign), which then pass through the same MySQL JSON type that
#          v1 stored them in
# techno_upload.has_month / has_till_month record which periods the blob
# had, so {"month": {}} stays distinct from a blob without "month".
#
# Key order: v1 read the blob back from a MySQL JSON column, which normalises
# object keys to (byte length, bytes) order. decode_techno sorts the leaves by
# that rule (TECHNO_LEAF_ORDER_BY is the same rule in SQL for param_key
# utf8mb4_0900_bin), so the rebuilt dict iterates exactly as v1's did.

TECHNO_PERIODS = ("month", "till_month")
TECHNO_LEAF_ORDER_BY = "period, LENGTH(param_key), param_key"
_MAX_EXACT_INT = 2 ** 53


def techno_key_order(period: str, param_key: str):
    return (TECHNO_PERIODS.index(period), len(param_key.encode("utf-8")), param_key.encode("utf-8"))


def encode_leaf(value) -> Tuple[Optional[float], int, Optional[str]]:
    """-> (num, is_int, raw)."""
    if isinstance(value, bool) or value is None or isinstance(value, (str, dict, list)):
        return None, 0, json.dumps(value)
    if isinstance(value, int):
        if abs(value) > _MAX_EXACT_INT:
            return None, 0, json.dumps(value)
        return float(value), 1, None
    if isinstance(value, float):
        if value == 0 and math.copysign(1.0, value) < 0:
            return None, 0, json.dumps(value)      # -0.0: a DOUBLE column may drop the sign
        return value, 0, None
    raise CodecError(f"unsupported techno leaf {value!r}")


def decode_leaf(num, is_int, raw):
    if raw is not None:
        return json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    if num is None:
        raise CodecError("techno_value row with neither num nor raw")
    return int(num) if is_int else float(num)


def encode_techno(blob) -> Tuple[int, int, List[Tuple[str, str, Optional[float], int, Optional[str]]]]:
    """A v1 techno_json value (dict or JSON text) ->
    (has_month, has_till_month, [(period, param_key, num, is_int, raw), ...])."""
    if isinstance(blob, (str, bytes)):
        blob = json.loads(blob)
    if not isinstance(blob, dict):
        raise CodecError(f"techno blob is not an object: {type(blob).__name__}")
    extra = [k for k in blob if k not in TECHNO_PERIODS]
    if extra:
        raise CodecError(f"techno blob has keys other than month / till_month: {extra!r}")
    leaves = []
    for period in TECHNO_PERIODS:
        if period not in blob:
            continue
        values = blob[period]
        if not isinstance(values, dict):
            raise CodecError(f"techno blob {period!r} is not an object: {type(values).__name__}")
        for key, value in values.items():
            if len(key) > 190:
                raise CodecError(f"techno param key longer than 190: {key!r}")
            leaves.append((period, key) + encode_leaf(value))
    return int("month" in blob), int("till_month" in blob), leaves


def decode_techno(has_month, has_till_month, leaves: Iterable) -> Dict[str, Dict[str, Any]]:
    """techno_upload flags + techno_value rows (period, param_key, num, is_int,
    raw), in any order -> the v1 dict, equal to json.loads(v1 techno_json)
    with the same key order and the same type per leaf."""
    out: Dict[str, Dict[str, Any]] = {}
    if has_month:
        out["month"] = {}
    if has_till_month:
        out["till_month"] = {}
    for period, key, num, is_int, raw in sorted(leaves, key=lambda r: techno_key_order(r[0], r[1])):
        if period not in out:
            raise CodecError(f"techno_value row for period {period!r}, which the upload does not have")
        out[period][key] = decode_leaf(num, is_int, raw)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# NARRATIVE TEXT
# ═════════════════════════════════════════════════════════════════════════════
#
# report_text(scope, period, block_key, plant_code, item_id, seq, text,
# updated_by, updated_at) replaces 9 v1 tables, one scope each. The codec
# works on item NAMES (item_name); the caller maps them to / from item_id.
#
#   kind 'wide'   one v1 row per period with one text column per block: each
#                 column becomes a row (block_key = column name), all of them
#                 carrying the row's updated_by / updated_at
#   kind 'keyed'  one v1 row per (period, block_key[, plant, item])
#   kind 'note'   one v1 row per (period, sort_order): block_key 'note',
#                 seq = sort_order

TEXT_SCOPES: Dict[str, Dict[str, Any]] = {
    "page3_narrative": {
        "table": "page3_narrative", "kind": "wide", "period": "report_month",
        "columns": ("production_narrative", "highlights"),
        "updated_by": None, "updated_at": "updated_at", "ts_format": SQL_SECONDS,
    },
    "key_highlights": {
        "table": "key_highlights_narrative", "kind": "wide", "period": "report_month",
        "columns": ("achievements", "shortfalls", "focus_areas"),
        "updated_by": "updated_by", "updated_at": "updated_at", "ts_format": SQL_SECONDS,
    },
    "steel_sales": {
        "table": "steel_sales_highlights", "kind": "wide", "period": "report_month",
        "columns": ("month_items", "ytd_items"),
        "updated_by": "updated_by", "updated_at": "updated_at", "ts_format": SQL_SECONDS,
    },
    "secretary_review": {
        "table": "secretary_review_text", "kind": "keyed", "period": "report_month",
        "block_key": "block_key", "text": "text",
        "updated_at": "updated_at", "ts_format": ISO_SECONDS,
        "v1_columns": ("report_month", "block_key", "text", "updated_at"),
    },
    "board_note": {
        "table": "board_note_manual_text", "kind": "keyed", "period": ("report_fy", "quarter"),
        "block_key": "field", "plant": "plant", "text": "text",
        "v1_columns": ("report_fy", "quarter", "plant", "field", "text"),
    },
    "do_letter": {
        "table": "do_letter_remark_table", "kind": "keyed", "period": "report_month",
        "block_key": ("remark",), "plant": "plant_name", "item": "item_name", "text": "remark",
        "v1_columns": ("report_month", "item_name", "plant_name", "remark"),
    },
    "sail_sales_note": {
        "table": "sail_sales_note_table", "kind": "keyed", "period": "report_month",
        "block_key": ("note",), "text": "note",
        "v1_columns": ("report_month", "note"),
    },
    "rail_note": {
        "table": "rail_prod_despatch_note", "kind": "note", "period": None,
        "text": "note_text", "v1_columns": ("sort_order", "note_text"),
    },
    "ss_phys_note": {
        "table": "special_steel_phys_note", "kind": "note", "period": "financial_year",
        "text": "note_text", "v1_columns": ("financial_year", "sort_order", "note_text"),
    },
}

# v1 table -> scope
TEXT_TABLE_SCOPE = {spec["table"]: scope for scope, spec in TEXT_SCOPES.items()}


def v1_text_columns(scope: str) -> Tuple[str, ...]:
    """The v1 table's columns in table order."""
    spec = TEXT_SCOPES[scope]
    if spec["kind"] == "wide":
        cols = (spec["period"],) + spec["columns"]
        if spec["updated_by"]:
            cols += (spec["updated_by"],)
        return cols + (spec["updated_at"],)
    return spec["v1_columns"]


def board_note_period(fy: str, quarter) -> str:
    return f"{fy}:Q{int(quarter)}"


def split_board_note_period(period: str) -> Tuple[str, int]:
    fy, _, q = period.partition(":")
    return fy, int(q.upper().lstrip("Q"))


def _text_row(period, block_key, text, plant=None, item=None, seq=0, updated_by=None, updated_at=None):
    return {"period": period, "block_key": block_key, "plant_code": plant, "item_name": item,
            "seq": seq, "text": text, "updated_by": updated_by, "updated_at": updated_at}


def encode_text_row(scope: str, row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One v1 row (column -> value, as the app reads it) -> report_text rows
    {period, block_key, plant_code, item_name, seq, text, updated_by,
    updated_at (datetime or None)}."""
    spec = TEXT_SCOPES[scope]
    kind = spec["kind"]
    if kind == "wide":
        by = row.get(spec["updated_by"]) if spec["updated_by"] else None
        at = parse_ts(spec["ts_format"], row.get(spec["updated_at"]))
        return [_text_row(row[spec["period"]], col, row.get(col), updated_by=by, updated_at=at)
                for col in spec["columns"]]
    if kind == "note":
        period = row[spec["period"]] if spec["period"] else ""
        return [_text_row(period, "note", row[spec["text"]], seq=int(row["sort_order"]))]
    if scope == "board_note":
        period = board_note_period(row["report_fy"], row["quarter"])
    else:
        period = row[spec["period"]]
    bk = spec["block_key"]
    block_key = bk[0] if isinstance(bk, tuple) else row[bk]
    at = parse_ts(spec["ts_format"], row.get(spec["updated_at"])) if spec.get("updated_at") else None
    return [_text_row(period, block_key, row.get(spec["text"]),
                      plant=row[spec["plant"]] if spec.get("plant") else None,
                      item=row[spec["item"]] if spec.get("item") else None,
                      updated_at=at)]


def decode_text_rows(scope: str, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """report_text rows of one scope (dicts with the encode_text_row keys;
    updated_at as stored) -> the v1 rows (column -> value, in v1 column
    order), sorted by the v1 primary key."""
    spec = TEXT_SCOPES[scope]
    kind = spec["kind"]
    rows = list(rows)
    out: List[Dict[str, Any]] = []
    if kind == "wide":
        by_period: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            v1 = by_period.get(r["period"])
            if v1 is None:
                v1 = {spec["period"]: r["period"]}
                for col in spec["columns"]:
                    v1[col] = None
                if spec["updated_by"]:
                    v1[spec["updated_by"]] = r["updated_by"]
                v1[spec["updated_at"]] = render_ts(spec["ts_format"], r["updated_at"])
                by_period[r["period"]] = v1
            if r["block_key"] not in spec["columns"]:
                raise CodecError(f"{scope}: unknown block_key {r['block_key']!r}")
            v1[r["block_key"]] = r["text"]
        return [by_period[p] for p in sorted(by_period)]
    for r in rows:
        if kind == "note":
            v1 = {}
            if spec["period"]:
                v1[spec["period"]] = r["period"]
            v1["sort_order"] = r["seq"]
            v1[spec["text"]] = r["text"]
        elif scope == "board_note":
            fy, q = split_board_note_period(r["period"])
            v1 = {"report_fy": fy, "quarter": q, "plant": r["plant_code"],
                  "field": r["block_key"], "text": r["text"]}
        elif scope == "do_letter":
            v1 = {"report_month": r["period"], "item_name": r["item_name"],
                  "plant_name": r["plant_code"], "remark": r["text"]}
        elif scope == "secretary_review":
            v1 = {"report_month": r["period"], "block_key": r["block_key"], "text": r["text"],
                  "updated_at": render_ts(spec["ts_format"], r["updated_at"])}
        else:  # sail_sales_note
            v1 = {"report_month": r["period"], "note": r["text"]}
        out.append({c: v1[c] for c in spec["v1_columns"]})
    pk = text_v1_key(scope)
    out.sort(key=lambda d: tuple(d[c] for c in pk))
    return out


# v1 primary key of each narrative table (wide tables: the period column)
_TEXT_V1_KEY = {"secretary_review": ("report_month", "block_key"),
                "board_note": ("report_fy", "quarter", "plant", "field"),
                "do_letter": ("report_month", "item_name", "plant_name"),
                "sail_sales_note": ("report_month",),
                "rail_note": ("sort_order",),
                "ss_phys_note": ("financial_year", "sort_order")}


def text_v1_key(scope: str) -> Tuple[str, ...]:
    """The v1 primary-key columns of the scope's table."""
    spec = TEXT_SCOPES[scope]
    if spec["kind"] == "wide":
        return (spec["period"],)
    return _TEXT_V1_KEY[scope]


# ═════════════════════════════════════════════════════════════════════════════
# PRODUCTION
# ═════════════════════════════════════════════════════════════════════════════
# v1 table (report_month, plant_name, item_name, month_actual) -> the
# production_monthly value column and its has_* flag. A v1 row sets the flag
# to 1 (even when month_actual is NULL); no v1 row leaves flag 0, value NULL.

PRODUCTION_SOURCES: Dict[str, Tuple[str, str]] = {
    "production_table": ("actual", "has_actual"),
    "production_plan_table": ("abp_plan", "has_abp"),
    "mou_plan_table": ("mou_plan", "has_mou"),
}
