"""Repo oracle: record what every repo read returns on v1, replay it on v2.

    python -m tools.repo_oracle record --db mis_reports_rehearsal --today 2026-10-19 \
        --pass sql|bulk --months 2024-04..2024-05 [--scopes month|nonmonth|all] \
        [--only PATHS] [--exclude PATHS] [--store DIR] [--force]
    python -m tools.repo_oracle replay --module production [--functions a,b] \
        [--limit-diffs 20] [--impl current|v1] [--passes sql,bulk] [--db NAME] [--store DIR]
    python -m tools.repo_oracle report [--store DIR]

Task 7 (ruling R12): v2 implementations were built beside the v1 modules
and proven equal by replaying, call by call, what the v1 modules returned
while the app served the parity endpoint set. Since Task 7g the v2 code IS
repo/<domain>.py (the v1 modules survive only as the test oracle
tests/_v1_frozen/). The v1 recording in the default store is frozen: a new
`record` run wraps the current (v2) repo modules, so it can only make a new
v2 baseline (on a v2 database, into another --store), never a v1 one.

record
    Runs the app in-process (TestClient) on a v1 database and drives exactly
    the endpoints and calls of tools.parity_snapshot (its enumeration,
    expand_calls, months / FY logic, --today pinning, param maps,
    SKIPPED_ENDPOINTS and POST_EXPORTS; no PDF passes). Every public READ
    function of every repo.<domain> module is wrapped: the module attribute
    and every alias already imported elsewhere (`from repo.x import f` in
    db.py, page modules, ...). Each call is stored as (function, canonical
    args, canonical result or exception).

    Caches are off while recording, so every read really runs:
      - data_version.current() is patched to return None, which is the
        existing "no version: do not cache" switch of version_cache: main's
        page cache, page_records' generate_group_records memo and
        report_utils' compute_item_row memo all compute every time.
      - pass "sql": report_context.current() is patched to return None, so
        repo reads never use a context: production.values / blobs /
        records_rows and the *_cell helpers run their SQL fall-through.
      - pass "bulk": report_context works as in production; only calls made
        while a context is active are recorded (tagged with the context's
        report month; anything else is what the sql pass records), plus
        every loader a context runs (ctx.load(name, loader) -> e.g.
        production._bulk_load(first, last)).
    Process-lifetime lru_caches inside repo (techno plan) sit behind public
    wrappers, which are recorded on every call.

    Read-only: every MySQL session the run opens is `SET SESSION TRANSACTION
    READ ONLY`, and WRITE_FUNCTIONS are wrapped only to count calls (the
    count is reported; a write would fail in MySQL).

    Identical (context, function, args) calls are stored once; when an
    identical call returns a different result the function is not
    deterministic and the run reports it (index.json "conflicts").

replay
    Imports repo.<module> (since Task 7g the v2 implementation; --impl v1:
    the frozen v1 copy tests/_v1_frozen/<module>, a sanity check of the
    oracle itself on a v1 database), replays every recorded call with the same args
    (a recorded cursor / connection argument becomes a fresh one on the
    replay DB) and compares canonical results. Bulk-pass records are
    replayed inside a report_context for the recorded month (loaders
    directly). Results are equal when their canonical TEXT is equal (so
    True vs 1 and 5 vs 5.0 differ), except for the functions COMPARE_MODE
    lists (multiset / deep_unordered, each with a caller-audit reason).
    Only return values are compared: what a function does to its arguments
    (e.g. enrich_* filling rows in place) is not, unless it also returns them.
    Prints the first --limit-diffs diffs per function (args, first
    differing row and key) and exits 1 on any diff, unreplayable call, or
    recorded PUBLIC function missing from the implementation (a missing
    _private one, e.g. a loader, is a warning).

Canonical form (type- and order-preserving JSON): str / int / bool / None
as is; float {"$float": repr}; Decimal {"$Decimal": str}; datetime / date /
time {"$datetime": iso}; timedelta; bytes {"$bytes": hex}; list as a list;
tuple {"$tuple": [...]}; set {"$set": sorted}; dict and Row
{"$dict" | "$Row": [[key, type name, value], ...]} in their own order.

Store (default C:\\mysql\\archive\\oracle\\v1):
    <module>.<pass>.jsonl.gz   one record per unique call (gzip members
                               appended per run; a killed run leaves only
                               _staging/ behind, never a torn file)
    <module>.<pass>.keys       "<call key sha1> <result sha256> <sorted-rows sha256>"
    index.json                 runs, per-function call / unique counts,
                               conflicts, write attempts
A result whose canonical JSON is over BIG_LIMIT (1 MB) is stored as
{"sha256", "rows", "head" (first 3), "tail" (last 3), "chunks" (sha256 per
256 rows)} instead of in full.

record and replay re-run themselves with PYTHONHASHSEED=0: a few reads
build dicts by iterating a set of strings, whose order otherwise differs
between processes (and so between recording chunks and the replay).

Databases: an allowlist, case-insensitive: names ending _rehearsal or
starting mis_reports_test_. Everything else (mis_reports, mis_reports_baseline,
mis_reports_v2, ...) is refused before connecting, and the live
SELECT DATABASE() is checked again. --db (or MYSQL_DB) is required.
"""

import argparse
import collections
import contextlib
import datetime as _dt
import enum
import functools
import gzip
import hashlib
import importlib
import inspect
import json
import os
import shutil
import sys
import threading
import time
import uuid
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tools import parity_snapshot as ps  # noqa: E402

DEFAULT_STORE = Path(r"C:\mysql\archive\oracle\v1")
# Allowlist (case-insensitive): rehearsal copies and the test fixture's schemas.
ALLOWED_DB_SUFFIX = "_rehearsal"
ALLOWED_DB_PREFIX = "mis_reports_test_"
PASSES = ("sql", "bulk")
BIG_LIMIT = 1_000_000
BIG_CHUNK = 256

# repo modules with no domain reads of their own (connection plumbing, the
# data_version counter, the v1<->v2 codec).
SHARED_MODULES = ("conn", "version", "v2codec", "_keys", "_mysqlsort")
DOMAIN_MODULES = ("breakdown", "capacity", "cost_trend", "ipt", "mines", "misc", "ops", "pages",
                  "production", "rake", "special_steel", "stock", "techno", "text")

# Public functions that write (hand-maintained; tests/test_repo_oracle.py
# checks it against test_repo_writes_bump's AST write detection: functions
# holding write SQL plus those calling one in the same module). Never recorded.
WRITE_FUNCTIONS = {
    "breakdown": ("cr_renumber", "delete_breakdown_entry", "delete_cr_row", "insert_cr_row",
                  "save_breakdown_entry", "update_breakdown_entry", "update_cr_entry"),
    "capacity": ("delete_capacity_entry", "save_capacity_entry", "update_capacity_entry"),
    "cost_trend": ("save_cost_trend_annual", "save_cost_trend_monthly", "save_cost_trend_monthly_field"),
    "ipt": ("delete_ipt_entry", "save_ipt_entry"),
    "mines": ("save_mines_production_despatch_monthly", "save_sail_mines_monthly"),
    "misc": ("deactivate_cover_photo", "insert_cover_photo", "insert_external_bf", "insert_external_bf_data",
             "rename_major_unit_label", "replace_cover_setting", "save_macro_indicators",
             "save_major_unit_daily_record", "save_market_price_trend", "save_pdf_item_alias",
             "save_rail_report_data", "save_ready_reckoner_content", "save_ready_reckoner_image",
             "update_external_bf", "update_external_bf_data", "upsert_bf_sail_meta", "upsert_power_value",
             "upsert_ready_reckoner_master", "upsert_steel_sector_performance"),
    "ops": ("add_admin_notification", "complete_todo_job", "delete_allowed_email", "delete_todo_job",
            "delete_user", "delete_worklog_entry", "insert_todo_job", "insert_user", "insert_worklog_entry",
            "log_activity", "log_extraction", "log_page_visit", "otp_insert", "otp_invalidate_unused",
            "otp_mark_used", "reopen_todo_job", "set_allowed_email_barred", "set_user_permissions",
            "set_user_role", "update_password", "update_todo_job", "update_user_fields",
            "update_worklog_entry", "upsert_allowed_email"),
    "pages": ("save_page_config",),
    "production": ("delete", "save_production_actual", "save_production_plan", "upsert",
                   "upsert_bsl_furnace_production", "upsert_row"),
    "rake": ("deactivate_rake_detention_master_row", "save_rake_detention_annual",
             "save_rake_detention_master_row", "save_rake_detention_monthly", "save_rake_detention_summary"),
    "special_steel": ("clear_special_steel_orders", "delete_club", "delete_grade_club",
                      "delete_ss_ipt_requirement", "save_special_steel_entry", "save_ss_ipt_requirement",
                      "save_ss_phys_meta", "save_ss_phys_perf", "upsert_abp", "upsert_grade_club"),
    "stock": ("save_stock_entry", "upsert_sales", "upsert_stock_snapshot"),
    "techno": ("insert_ignore_param_type", "insert_ignore_plant_unit", "merge_upsert",
               "merge_upsert_techno_data", "save_sail_techno_actuals", "save_sail_techno_plan",
               "save_techno_data_from_extraction", "save_techno_json", "save_techno_plan",
               "save_techno_plant_plan", "update_param_master_unit", "upsert_techno_data"),
    "text": ("delete_do_letter_remark", "delete_texts", "put", "save_key_highlights_narrative",
             "save_manual_text", "save_page3_narrative", "save_rail_report_notes", "save_ss_phys_notes",
             "save_steel_sales_highlights", "save_texts", "upsert_do_letter_remark", "upsert_sail_sales_note"),
}

# How replay compares a function's result: "module.func" -> (mode, why).
# Modes: "strict" (the default for every function not listed: canonical
# text equality, so order and types count), "multiset" (top-level rows in
# any order), "deep_unordered(depth=N)" (dict items / list elements sorted
# down to depth N; depth 1 = multiset). Every non-strict entry needs a
# caller audit: `why` says why the order never reaches any output. Add an
# entry only after such an audit (an "order" conflict in index.json is a
# reason to audit, never an entry by itself).
COMPARE_MODE = {
    "techno.rows_for_months": (
        "multiset",
        "No ORDER BY; seen returning the same 883 rows in two orders in a trial recording (MySQL chose "
        "an idx_techno_month range scan in one process, a table scan in another). Caller audit: its three "
        "callers (page_techno ~L1215, ~L1883, ~L2971) only build store[(plant, month)][unit] for keyed "
        ".get() lookups; the iterations over store are a per-entry fuel_rate patch (order-independent) and "
        "plant / unit sets that are sorted by _PLANT_ORDER / _VERIFY_BF_PLANTS or tested for membership "
        "against _SMS_UNIT_ORDER. Row order never reaches output."),
    "production._bulk_load": (
        "deep_unordered(depth=2)",
        "{measure: {(month, fold(plant), fold(item)): (plant, item, value)}} from a UNION ALL with no ORDER "
        "BY. Depth 2 = the measure dict and each measure's cells dict; the (plant, item, value) tuples stay "
        "ordered. Caller audit: cell / sum_plants_cell / sum_months_cell / fs_alias_sum and the other "
        "served readers look cells up by key, and _cells_sum walks sorted(set(months)) x sorted folded "
        "plants, so the SUM order is fixed by the code, not by the dict. The only iteration is values() "
        "(cells.items()), whose result order is documented unspecified and which no app module calls."),
    "production.item_plants_range": (
        "multiset",
        "No ORDER BY; v1's row order is a cost-model choice per item: idx_prod_item_month gives (month, "
        "plant), idx_prod_plant_item gives (plant, month) (EXPLAIN on the v1 data: e.g. 'Pig Iron', "
        "'Finished Steel' used the latter), which v2 cannot predict. Caller audit (2026-10-22, Task 7b): "
        "the only caller, page7_13._generate_rows_for_config (4 call sites, ~L360-385), stores each row as "
        "act_data[plant][rm] / plan_data[plant][rm] (dicts pre-built in all_plants order; the Finished Steel "
        "alias patch only fills keys still missing). (plant, month) is unique per call, and every v1 access "
        "path yields each plant's months ascending, so even each inner dict's insertion order is the same "
        "whichever path; nothing else iterates the rows. Row order never reaches output. --impl current "
        "re-run in a fresh process first: 0 diffs, both passes."),
    "techno.plant_units_month_rows": (
        "multiset",
        "No ORDER BY; v1's row order is a cost-model choice per call between its two indexes: uq_techno "
        "(plant, report_month, unit) -> (month, unit), which v2's ORDER BY report_month, unit (ai_ci) "
        "reproduces for 95 of the 96 recorded calls, and idx_techno_month (report_month, id) -> (month, id), "
        "which v1 picked for the call with the longest month list (BSP, 7 units x 16 months, 2016-03; "
        "v2's ORDER BY report_month, seq would reproduce that one and miss 91 others). Same kind of entry as "
        "production.item_plants_range. Caller audit (2026-10-23, Task 7c fix round 1): the only caller, "
        "page_bf_large_annexure._coke_ash_and_sinter_fe (~L456), stores rows[(unit, month)] ((plant, unit, "
        "month) is unique) and reads it only with .get() in fixed all_units / period order. Row order never "
        "reaches output. --impl current re-run in a fresh process first (2026-10-22): 0 diffs, both passes."),
    "mines.get_iron_ore_mines_series": (
        "deep_unordered(depth=2)",
        "{'production' | 'despatch' | 'despatch_plan': [row dict, ...]} from three joins with no ORDER BY. "
        "Depth 2 = the dict and each list; the row dicts stay ordered. v1's row order is a cost-model "
        "choice per call: a PRIMARY range scan ((month, mine, material, ...), which v2's ORDER BY "
        "reproduces for every recorded call but one) or, for the FY 2026-27 despatch_plan (~710 rows; "
        "EXPLAIN on the v1 data, Task 7e1), a nested loop driven from mines_master's group_code index, giving "
        "(group, mine, month, material, end use). v2 cannot predict that choice without fitting today's "
        "row counts. Caller audit (2026-10-23, Task 7e1): mines_group_wise.generate keys every row by "
        "(mine, material[, end use]) and reads the cells in fixed master order (despatch_plan has one row "
        "per key and month, so no sum depends on order); /api/iron-ore-mines/series hands the lists to "
        "frontend reports/iron-ore-mines/View.js, which filters by scope and sums values per month: every "
        "qty_plan in the v1 data is an integer below 2^53, so those sums are exact in any order. The one "
        "visible difference is the JSON row order of that endpoint's despatch_plan list for fy_start=2026 "
        "(listed in tools/parity_exceptions.md). --impl current re-run in a fresh process first: 0 diffs."),
    "breakdown.open_breakdown_rows": (
        "multiset",
        "No ORDER BY; v1's row order is a cost-model choice per call: an idx_breakdown_start range scan "
        "(start_ts, id) for early report months, the idx_breakdown_capital_repair IS NULL ref scan (id) "
        "for others (2 of the 32 recorded calls take the first; ORDER BY id and ORDER BY start_ts, id each "
        "reproduce 30), which v2 cannot predict without fitting today's row counts. Caller audit "
        "(2026-10-23, Task 7e2): the only caller, page_secretary_review_texts._fetch_breakdowns, feeds "
        "unit_summaries, which groups the events by (plant, unit_type, unit_name) into a dict and sorts "
        "the output by that key; per group it sums the point-event hours and merges the intervals (order "
        "independent but for float rounding in the last bit, then rounded to whole days) and keeps the "
        "cause of the first event with the strictly greatest hours, so only two events of one unit with "
        "exactly equal hours could swap their cause. v2 reads in id order. --impl current re-run in a "
        "fresh process first (2026-10-23): 0 diffs."),
    "capacity._capacity_load": (
        "deep_unordered(depth=2)",
        "{(fold(plant), fold(item)): [(effective_month, annual_capacity), ...]} from a SELECT with no "
        "ORDER BY. Depth 2 = the dict and each entry list; the tuples stay ordered. Caller audit: the only "
        "user, get_effective_capacity, looks the list up by key and keeps the entry with the strictly "
        "greatest effective_month <= month. uq_capacity_plant_item_month (plant_name, item_name, "
        "effective_month) is unique under the ai_ci collation that fold() mirrors, so effective_month "
        "never repeats within one list and the pick is the same for any list order."),
}


# Individual recorded calls whose v2 result may differ from v1 in ONE
# accepted way (a controller ruling each): ("module.func", canonical args
# text, canonical kwargs text) -> (relaxation, why). Relaxations:
#   ("ties", (col, ...))  the result is a list of rows; v2 may order rows
#                         whose key (the values at those columns) is equal
#                         differently. Accepted only when the key sequence
#                         is identical AND the rows are the same multiset.
# A listed call that differs in any other way (a value, a type, a key out
# of order, a missing row) is still a DIFF; unlisted calls are compared as
# usual. The user-visible effect of each entry is listed in
# backend/tools/parity_exceptions.md (7g parity must show exactly those).
_CALENDAR_TIES = (
    "Task 7b ruling (a): tie order only. v1 GROUP BY + ORDER BY item_name, mon_num, total DESC sorted "
    "2,700-8,800 groups for a single-plant scope with filesort; they exceed the default "
    "sort_buffer_size (256 KB), so v1 sorted chunks and merged them, and the order of groups with equal "
    "(item, mon_num, total) is an artefact of that buffer size. v2 (repo._mysqlsort) reproduces the "
    "tie order of a sort that fits one buffer - exactly v1's for the other 69 scopes, and v1's own output "
    "for these 5 when run with sort_buffer_size = 64M. Rows, keys and key sequence are equal; only tied "
    "rows swap. Effect: 33 top-2 month labels on the /records single-plant tabs (parity_exceptions.md).")
KNOWN_PARITY_EXCEPTIONS = {
    ("production.records_calendar_month_totals",
     '[{"$cursor":"dbengine","row_factory":null},{"$tuple":["plant_name IN (%s)",["' + plant + '"]]}]',
     "[]"): (("ties", (0, 1, 3)), _CALENDAR_TIES)       # (item_name, mon_num, total)
    for plant in ("BSP", "DSP", "RSP", "BSL", "ISP")
}


def known_exception(module, name, rec):
    """(relaxation, why) when this recorded call is a KNOWN_PARITY_EXCEPTIONS entry, else None."""
    return KNOWN_PARITY_EXCEPTIONS.get((f"{module}.{name}", dumps(rec["a"]), dumps(rec["k"])))


def _row_values(row):
    """A canonical row ($tuple / $Row / $dict / list) -> its values in order."""
    items = _items(row)
    if items is None:
        return None
    if isinstance(row, dict) and next(iter(row)).startswith(("$Row", "$dict")):
        return [it[2] for it in items]
    return list(items)


def within_relaxation(relaxation, expected, got):
    """True when `got` equals `expected` up to `relaxation` (see KNOWN_PARITY_EXCEPTIONS)."""
    kind, cols = relaxation
    if kind != "ties":
        raise ValueError(f"unknown relaxation {kind!r}")
    e_rows, g_rows = _items(expected), _items(got)
    if e_rows is None or g_rows is None or len(e_rows) != len(g_rows):
        return False

    def key(row):
        vals = _row_values(row)
        if vals is None or max(cols) >= len(vals):
            return None
        return dumps([vals[c] for c in cols])
    e_keys, g_keys = [key(r) for r in e_rows], [key(r) for r in g_rows]
    if None in e_keys or e_keys != g_keys:
        return False
    return sorted(dumps(r) for r in e_rows) == sorted(dumps(r) for r in g_rows)


def parse_mode(mode):
    """'strict' | 'multiset' | 'deep_unordered(depth=N)' -> (kind, depth)."""
    import re
    if mode == "strict":
        return "strict", 0
    if mode == "multiset":
        return "multiset", 1
    m = re.fullmatch(r"deep_unordered\(depth=(\d+)\)", mode)
    if m and int(m.group(1)) >= 1:
        return "deep_unordered", int(m.group(1))
    raise ValueError(f"unknown compare mode {mode!r}")


def compare_depth(module, name, overrides=None):
    """0 for strict, else the unordered depth for module.name."""
    entry = (overrides or COMPARE_MODE).get(f"{module}.{name}")
    return 0 if entry is None else parse_mode(entry[0])[1]

# Public non-write functions that are not recorded -> why.
NOT_RECORDED = {
    ("ops", "get_lock_row"): "GET_LOCK: takes a session lock (admin backup); not a data read",
    ("ops", "release_lock"): "RELEASE_LOCK: session lock plumbing; not a data read",
}


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

def public_functions(mod):
    """Names of the public functions defined in `mod` (not imported into it)."""
    return sorted(n for n, f in vars(mod).items()
                  if not n.startswith("_") and inspect.isfunction(unwrap(f))
                  and unwrap(f).__module__ == mod.__name__)


def read_functions(mod, module):
    writes = set(WRITE_FUNCTIONS.get(module, ()))
    return [n for n in public_functions(mod) if n not in writes and (module, n) not in NOT_RECORDED]


def unwrap(f):
    return getattr(f, "__oracle_original__", f)


# ---------------------------------------------------------------------------
# canonical form
# ---------------------------------------------------------------------------

_ROW = None


def _row_class():
    global _ROW
    if _ROW is None:
        import dbengine
        _ROW = dbengine.Row
    return _ROW


def _placeholder(v):
    """{"$cursor": ...} / {"$conn": ...} for a DB handle passed as an arg, else None."""
    import dbengine
    from repo import conn as rc
    if isinstance(v, rc.Cursor):
        return {"$cursor": "repo"}
    if isinstance(v, dbengine.CursorWrapper):
        rf = v._conn.row_factory if v._conn is not None else None
        return {"$cursor": "dbengine", "row_factory": None if rf is None else rf.__name__}
    if isinstance(v, dbengine.ConnWrapper):
        rf = v.row_factory
        return {"$conn": "dbengine", "row_factory": None if rf is None else rf.__name__}
    return None


def _sort_key(c):
    return json.dumps(c, ensure_ascii=False, separators=(",", ":"))


def canonical(v):
    t = type(v)
    if v is None or t is str or t is bool or t is int:
        return v
    if t is float:
        return {"$float": repr(v)}
    if t is list:
        return [canonical(x) for x in v]
    if t is tuple:
        return {"$tuple": [canonical(x) for x in v]}
    if isinstance(v, dict):
        tag = "$dict" if t is dict else f"$dict:{t.__name__}"
        return {tag: [[canonical(k), type(x).__name__, canonical(x)] for k, x in v.items()]}
    Row = _row_class()
    if t is Row:
        return {"$Row": [[k, type(x).__name__, canonical(x)] for k, x in zip(v.keys(), v)]}
    if isinstance(v, enum.Enum):
        return {"$enum": f"{t.__name__}.{v.name}"}
    if isinstance(v, bool):
        return {"$bool:" + t.__name__: bool(v)}
    if isinstance(v, int):
        return {"$int:" + t.__name__: str(v)}
    if isinstance(v, float):
        return {"$float:" + t.__name__: repr(float(v))}
    if isinstance(v, str):
        return {"$str:" + t.__name__: str(v)}
    if isinstance(v, Decimal):
        return {"$Decimal": str(v)}
    if isinstance(v, _dt.datetime):
        return {"$datetime": v.isoformat()}
    if isinstance(v, _dt.date):
        return {"$date": v.isoformat()}
    if isinstance(v, _dt.time):
        return {"$time": v.isoformat()}
    if isinstance(v, _dt.timedelta):
        return {"$timedelta": [v.days, v.seconds, v.microseconds]}
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"$bytes": bytes(v).hex()}
    if isinstance(v, (set, frozenset)):
        tag = "$set" if t is set else "$frozenset"
        return {tag: sorted((canonical(x) for x in v), key=_sort_key)}
    if isinstance(v, tuple):          # namedtuple
        return {f"$tuple:{t.__name__}": [canonical(x) for x in v]}
    if isinstance(v, list):
        return {f"$list:{t.__name__}": [canonical(x) for x in v]}
    ph = _placeholder(v)
    if ph is not None:
        return ph
    return {"$obj": f"{t.__module__}.{t.__qualname__}", "repr": repr(v)[:200]}


def dumps(c) -> str:
    return json.dumps(c, ensure_ascii=False, separators=(",", ":"))


class Unreplayable(Exception):
    """An argument that cannot be rebuilt from its canonical form."""


def decanonical(c, live):
    """Inverse of canonical() for arguments. `live(tag_dict)` builds a DB
    handle for a {"$cursor"} / {"$conn"} placeholder."""
    if c is None or isinstance(c, (str, bool, int)):
        return c
    if isinstance(c, list):
        return [decanonical(x, live) for x in c]
    (tag, val), = c.items() if len(c) == 1 else (("$multi", c),)
    if tag == "$multi":
        if "$cursor" in c or "$conn" in c:
            if live is None:
                raise Unreplayable("DB handle argument")
            return live(c)
        if "$obj" in c:
            raise Unreplayable(f"argument of type {c['$obj']}")
        raise Unreplayable(f"unknown canonical {c!r:.100}")
    if tag == "$float":
        return float(val)
    if tag == "$tuple":
        return tuple(decanonical(x, live) for x in val)
    if tag == "$dict":
        return {decanonical(k, live): decanonical(x, live) for k, _t, x in val}
    if tag == "$Row":
        return _row_class()([k for k, _t, _x in val], tuple(decanonical(x, live) for _k, _t, x in val))
    if tag == "$Decimal":
        return Decimal(val)
    if tag == "$datetime":
        return _dt.datetime.fromisoformat(val)
    if tag == "$date":
        return _dt.date.fromisoformat(val)
    if tag == "$time":
        return _dt.time.fromisoformat(val)
    if tag == "$timedelta":
        return _dt.timedelta(days=val[0], seconds=val[1], microseconds=val[2])
    if tag == "$bytes":
        return bytes.fromhex(val)
    if tag == "$set":
        return {decanonical(x, live) for x in val}
    if tag == "$frozenset":
        return frozenset(decanonical(x, live) for x in val)
    if tag in ("$cursor", "$conn"):
        if live is None:
            raise Unreplayable("DB handle argument")
        return live(c)
    raise Unreplayable(f"cannot rebuild a {tag} argument")


# Exception messages may name the database ("Table 'db.t' doesn't exist"):
# the replay DB has another name, so it is written as <db> on both sides.
_db_name_for_messages = None


def canonical_exception(e):
    msg = str(e)
    if _db_name_for_messages:
        msg = msg.replace(_db_name_for_messages, "<db>")
    t = type(e)
    return {"type": f"{t.__module__}.{t.__qualname__}", "msg": msg}


def _items(c):
    """The row list of a canonical value (list, tuple, dict or Row), else None."""
    if isinstance(c, list):
        return c
    if isinstance(c, dict) and len(c) == 1:
        (tag, val), = c.items()
        if tag.startswith(("$tuple", "$dict", "$Row", "$set", "$frozenset", "$list", "$unordered", "$sorted")) \
                and isinstance(val, list):
            return val
    return None


def _sorted_form(c):
    """c with its top-level rows in a fixed order (for order-free comparison)."""
    items = _items(c)
    if items is None:
        return c
    tag = "$list" if isinstance(c, list) else next(iter(c))
    return {"$sorted:" + tag: sorted(items, key=_sort_key)}


def sorted_hash(c):
    return hashlib.sha256(dumps(_sorted_form(c)).encode("utf-8")).hexdigest()


def big_form(c, text):
    items = _items(c)
    out = {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    if items is None:
        out.update(rows=None, head=[], tail=[], chunks=[])
    else:
        out.update(rows=len(items), head=items[:3], tail=items[-3:] if len(items) > 3 else [],
                   chunks=[hashlib.sha256(dumps(items[i:i + BIG_CHUNK]).encode("utf-8")).hexdigest()[:16]
                           for i in range(0, len(items), BIG_CHUNK)])
    return out


# ---------------------------------------------------------------------------
# store
# ---------------------------------------------------------------------------

class Store:
    def __init__(self, root):
        self.root = Path(root)

    def data_path(self, module, pass_name):
        return self.root / f"{module}.{pass_name}.jsonl.gz"

    def keys_path(self, module, pass_name):
        return self.root / f"{module}.{pass_name}.keys"

    @property
    def index_path(self):
        return self.root / "index.json"

    def load_keys(self, module, pass_name) -> dict:
        """{call key: (result sha256, sorted-rows sha256)}."""
        p = self.keys_path(module, pass_name)
        out = {}
        if p.exists():
            with open(p, encoding="ascii") as f:
                for line in f:
                    k, h, s = line.split()
                    out[k] = (h, s)
        return out

    def iter_records(self, module, pass_name):
        p = self.data_path(module, pass_name)
        if not p.exists():
            return
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    def modules(self):
        return sorted({p.name.split(".")[0] for p in self.root.glob("*.jsonl.gz")})

    def load_index(self) -> dict:
        if self.index_path.exists():
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        return {"runs": [], "functions": {}, "conflicts": [], "write_attempts": {}}

    def save_index(self, idx) -> None:
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(idx, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.index_path)


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

class Recorder:
    """Wraps the read functions of `modules` ({short name: module}) and the
    loaders a report_context runs; stages unique calls under
    store/_staging/<run>/ until commit()."""

    def __init__(self, store_root, pass_name, modules, write_functions=None, run_info=None,
                 not_recorded=None):
        assert pass_name in PASSES
        self.store = Store(store_root)
        self.pass_name = pass_name
        self.modules = dict(modules)
        self.write_functions = {m: set(fs) for m, fs in (write_functions or WRITE_FUNCTIONS).items()}
        self.not_recorded = set(NOT_RECORDED if not_recorded is None else not_recorded)
        self.run_info = dict(run_info or {})
        self.run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.staging = self.store.root / "_staging" / self.run_id
        self.calls = collections.Counter()
        self.unique_new = collections.Counter()
        self.write_calls = collections.Counter()
        self.conflicts = []
        self._keys = {}
        self._new_keys = collections.defaultdict(list)
        self._writers = {}
        self._lock = threading.RLock()
        self._patched = []
        self._active = False
        self._module_by_pyname = {}

    # -- wrapping ------------------------------------------------------------

    def _wrap(self, module, name, fn, write):
        rec = self

        if write:
            @functools.wraps(fn)
            def wrapper(*a, **k):
                if rec._active:
                    with rec._lock:
                        rec.write_calls[(module, name)] += 1
                return fn(*a, **k)
        else:
            @functools.wraps(fn)
            def wrapper(*a, **k):
                if not rec._active:
                    return fn(*a, **k)
                ctx_tag = None
                if rec.pass_name == "bulk":
                    import report_context
                    ctx = report_context.current()
                    if ctx is None:
                        return fn(*a, **k)
                    ctx_tag = ctx.report_month
                return rec._call(module, name, fn, a, k, ctx_tag)
        wrapper.__oracle_original__ = fn
        return wrapper

    def _call(self, module, name, fn, a, k, ctx_tag, has_ctx=True):
        ca = canonical(list(a))
        ck = [[key, canonical(k[key])] for key in sorted(k)]
        try:
            res = fn(*a, **k)
        except Exception as e:
            self.note(module, name, ctx_tag, ca, ck, exc=e, has_ctx=has_ctx)
            raise
        self.note(module, name, ctx_tag, ca, ck, result=res, has_ctx=has_ctx)
        return res

    def install(self):
        import report_context
        originals = {}      # id(original) -> wrapper
        for module, mod in self.modules.items():
            self._module_by_pyname[mod.__name__] = module
            writes = self.write_functions.get(module, set())
            for name in public_functions(mod):
                if (module, name) in self.not_recorded:
                    continue
                fn = unwrap(getattr(mod, name))
                originals[id(fn)] = (fn, self._wrap(module, name, fn, name in writes))
        # Patch the module attributes and every alias already imported elsewhere.
        for pymod in list(sys.modules.values()):
            d = getattr(pymod, "__dict__", None)
            if not isinstance(d, dict) or pymod is sys.modules[__name__]:
                continue
            for attr, val in list(d.items()):
                hit = originals.get(id(val))
                if hit is not None and hit[0] is val:
                    self._patched.append((pymod, attr, val))
                    setattr(pymod, attr, hit[1])
        # Loaders run by report_context (bulk pass).
        if self.pass_name == "bulk":
            orig_load = report_context.ReportContext.load
            rec = self

            def load(ctx_self, name, loader):
                module = rec._module_by_pyname.get(getattr(loader, "__module__", None))
                if module is None or not rec._active:
                    return orig_load(ctx_self, name, loader)

                def recorded(first, last):
                    return rec._call(module, loader.__name__, loader, (first, last), {}, None, has_ctx=False)
                return orig_load(ctx_self, name, recorded)
            self._patched.append((report_context.ReportContext, "load", orig_load))
            report_context.ReportContext.load = load
        self._active = True

    def uninstall(self):
        self._active = False
        for obj, attr, val in reversed(self._patched):
            setattr(obj, attr, val)
        self._patched.clear()

    @contextlib.contextmanager
    def installed(self):
        self.install()
        try:
            yield self
        finally:
            self.uninstall()

    # -- noting calls --------------------------------------------------------

    def _writer(self, module):
        w = self._writers.get(module)
        if w is None:
            self.staging.mkdir(parents=True, exist_ok=True)
            w = gzip.open(self.staging / f"{module}.{self.pass_name}.jsonl.gz", "wt", encoding="utf-8")
            self._writers[module] = w
        return w

    def note(self, module, name, ctx_tag, ca, ck, result=None, exc=None, has_ctx=True):
        bulk_ctx = self.pass_name == "bulk" and has_ctx
        if exc is not None:
            body = {"x": canonical_exception(exc)}
            rc_ = body
            text = dumps(body)
        else:
            rc_ = canonical(result)
            text = dumps(rc_)
        rhash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        key_src = dumps([ctx_tag if bulk_ctx else "-", name, ca, ck])
        khash = hashlib.sha1(key_src.encode("utf-8")).hexdigest()
        with self._lock:
            self.calls[(module, name)] += 1
            keys = self._keys.get(module)
            if keys is None:
                keys = self._keys[module] = self.store.load_keys(module, self.pass_name)
            known = keys.get(khash)
            if known is not None:
                if known[0] != rhash:
                    # Same rows in another order (a query without ORDER BY
                    # whose plan varies) or different values.
                    kind = "order" if sorted_hash(rc_) == known[1] else "value"
                    self.conflicts.append({"module": module, "function": name, "pass": self.pass_name,
                                           "kind": kind, "ctx": ctx_tag, "args": key_src[:500],
                                           "first": known[0], "now": rhash})
                return
            shash = sorted_hash(rc_)
            keys[khash] = (rhash, shash)
            self._new_keys[module].append((khash, rhash, shash))
            self.unique_new[(module, name)] += 1
            rec = {"f": name, "a": ca, "k": ck, "h": rhash, "s": shash}
            if bulk_ctx:
                rec["ctx"] = ctx_tag
            if exc is not None:
                rec["x"] = body["x"]
                line = dumps(rec)
            elif len(text) > BIG_LIMIT:
                rec["big"] = big_form(rc_, text)
                line = dumps(rec)
            else:
                line = dumps(rec)[:-1] + ',"r":' + text + "}"
            self._writer(module).write(line + "\n")

    # -- commit --------------------------------------------------------------

    def commit(self, extra=None):
        """Append the staged records to the store and merge the counts into
        index.json. Returns this run's index entry."""
        with self._lock:
            for w in self._writers.values():
                w.close()
            self._writers.clear()
            self.store.root.mkdir(parents=True, exist_ok=True)
            for module, new in self._new_keys.items():
                staged = self.staging / f"{module}.{self.pass_name}.jsonl.gz"
                with open(self.store.data_path(module, self.pass_name), "ab") as out, open(staged, "rb") as src:
                    shutil.copyfileobj(src, out)
                with open(self.store.keys_path(module, self.pass_name), "a", encoding="ascii") as f:
                    f.writelines(f"{k} {h} {s}\n" for k, h, s in new)
            idx = self.store.load_index()
            for (module, name), n in self.calls.items():
                e = idx["functions"].setdefault(f"{module}.{name}", {}).setdefault(
                    self.pass_name, {"calls": 0, "unique": 0})
                e["calls"] += n
                e["unique"] += self.unique_new.get((module, name), 0)
            for (module, name), n in self.write_calls.items():
                idx["write_attempts"][f"{module}.{name}"] = idx["write_attempts"].get(f"{module}.{name}", 0) + n
            idx["conflicts"].extend(self.conflicts)
            run = {"run_id": self.run_id, "pass": self.pass_name, **self.run_info, **(extra or {}),
                   "calls": sum(self.calls.values()), "unique_new": sum(self.unique_new.values()),
                   "conflicts": len(self.conflicts), "write_attempts": sum(self.write_calls.values())}
            idx["runs"].append(run)
            self.store.save_index(idx)
            self._new_keys.clear()
            if self.staging.exists():
                shutil.rmtree(self.staging)
            try:
                self.staging.parent.rmdir()        # _staging/, when no other run is staged
            except OSError:
                pass
            return run


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------

def _path_str(path):
    return "".join(f"[{p}]" if isinstance(p, int) else f".{p!r}" for p in path)


def _same(a, b):
    """Canonical equality by text (Python's == has True == 1)."""
    return dumps(a) == dumps(b)


def first_diff(a, b, path=()):
    """(path, a_part, b_part) of the first difference, or None. Diagnostics
    only: whether two results are equal is decided by their canonical text."""
    if _same(a, b):
        return None
    ia, ib = _items(a), _items(b)
    if ia is not None and ib is not None and type(a) is type(b) and \
            (not isinstance(a, dict) or list(a) == list(b)):
        for i, (x, y) in enumerate(zip(ia, ib)):
            if not _same(x, y):
                # a dict / Row item: [key, type, value]
                kv = isinstance(a, dict) and any(t in next(iter(a)) for t in ("$dict", "$Row"))
                if kv and isinstance(x, list) and isinstance(y, list) and len(x) == len(y) == 3 \
                        and _same(x[0], y[0]):
                    sub = first_diff(x[2], y[2], path + (i, x[0]))
                    if not _same(x[1], y[1]):
                        return path + (i, x[0]), x, y
                    return sub
                return first_diff(x, y, path + (i,)) or (path + (i,), x, y)
        return path + ("len",), len(ia), len(ib)
    return path, a, b


def _short(c, n=300):
    s = dumps(c)
    return s if len(s) <= n else s[:n] + f"... ({len(s)} chars)"


class _Live:
    """Fresh DB handles for {"$cursor"} / {"$conn"} placeholders, closed after the call."""

    def __init__(self, stack):
        self.stack = stack

    def __call__(self, ph):
        import dbengine
        from repo import conn as rc
        if ph.get("$cursor") == "repo":
            return self.stack.enter_context(rc.cursor())
        if not (ph.get("$cursor") == "dbengine" or ph.get("$conn") == "dbengine"):
            raise Unreplayable(f"unknown DB handle {ph!r}")
        factories = {None: None, "Row": dbengine.Row}
        if ph.get("row_factory") not in factories:
            raise Unreplayable(f"unknown row_factory {ph.get('row_factory')!r}")
        conn = dbengine.connect()
        self.stack.callback(conn.close)
        conn.row_factory = factories[ph.get("row_factory")]
        return conn.cursor() if "$cursor" in ph else conn


class _Contexts:
    """report_context objects for bulk-pass replay, one per recorded month,
    kept (with their loaded data) for the most recent few months."""

    def __init__(self, keep=3):
        self.keep = keep
        self._ctxs = collections.OrderedDict()

    @contextlib.contextmanager
    def enter(self, month):
        import report_context
        ctx = self._ctxs.get(month)
        if ctx is None:
            ctx = self._ctxs[month] = report_context.ReportContext(month)
            while len(self._ctxs) > self.keep:
                self._ctxs.popitem(last=False)
        self._ctxs.move_to_end(month)
        with report_context._enter(ctx):
            yield ctx


def _unordered_form(c, depth):
    """c with dict items / list elements sorted down to `depth` levels
    (1 = top-level rows only). A dict / Row item [key, type, value] is
    sorted as a whole and its value is the next level down."""
    if depth <= 0:
        return c
    items = _items(c)
    if items is None:
        return c
    tag = "$list" if isinstance(c, list) else next(iter(c))
    kv = tag.startswith(("$dict", "$Row"))
    new = [[it[0], it[1], _unordered_form(it[2], depth - 1)] if kv else _unordered_form(it, depth - 1)
           for it in items]
    return {"$unordered:" + tag: sorted(new, key=_sort_key)}


def _compare(rec, got_c, got_text, depth=0):
    """None when equal, else a list of message lines. Equality is canonical
    TEXT equality (the sha256 recorded with the result), so True vs 1 or
    5 vs 5.0 always differ. depth > 0 (COMPARE_MODE): compare the
    _unordered_form of both sides instead."""
    if depth == 0 or "x" in rec:
        if hashlib.sha256(got_text.encode("utf-8")).hexdigest() == rec["h"]:
            return None
        return _explain(rec, got_c, got_text)
    if "big" in rec:
        if depth == 1 and sorted_hash(got_c) == rec["s"]:
            return None
        return [f"  big result differs (or cannot be compared) at unordered depth {depth}: rows expected "
                f"{rec['big']['rows']} got {len(_items(got_c) or [])}"]
    expected = _unordered_form(rec["r"], depth)
    got_u = _unordered_form(got_c, depth)
    if _same(expected, got_u):
        return None
    return _explain({"r": expected}, got_u, None)


def _explain(rec, got_c, got_text):
    """Diagnostic lines for a result that differs from rec."""
    if "big" in rec:
        big = rec["big"]
        g = big_form(got_c, got_text)
        lines = [f"  big result differs (sha256): rows expected {big['rows']} got {g['rows']}"]
        for label in ("head", "tail"):
            if big[label] != g[label]:
                d = first_diff(big[label], g[label])
                lines.append(f"  {label} differs at {_path_str(d[0])}: expected {_short(d[1])} got {_short(d[2])}")
        for i, (x, y) in enumerate(zip(big["chunks"], g["chunks"])):
            if x != y:
                items = _items(got_c) or []
                lines.append(f"  first differing chunk {i} (rows {i * BIG_CHUNK}..{i * BIG_CHUNK + BIG_CHUNK - 1}); "
                             f"got row {i * BIG_CHUNK}: {_short(items[i * BIG_CHUNK] if items else None)}")
                break
        return lines
    expected = {"x": rec["x"]} if "x" in rec else rec["r"]
    d = first_diff(expected, got_c)
    path, e, g = d if d else ((), expected, got_c)
    lines = [f"  at {_path_str(path) or '<result>'}: expected {_short(e)}", f"  {' ' * (len(_path_str(path) or '<result>') + 4)}got      {_short(g)}"]
    if path and isinstance(path[0], int):
        ei, gi = _items(expected), _items(got_c)
        if ei is not None and gi is not None and path[0] < len(ei) and path[0] < len(gi):
            lines.append(f"  expected row: {_short(ei[path[0]])}")
            lines.append(f"  got row:      {_short(gi[path[0]])}")
    return lines


def replay_records(records, impl, module, pass_name, *, functions=None, limit_diffs=20, out=print,
                   contexts=None, stats=None):
    """Replay `records` (one pass of one module) against module object `impl`,
    comparing each result per COMPARE_MODE (strict by default). Only return
    values are compared; what a function does to its arguments is not.
    Returns stats {calls, diffs, missing: {fn: n}, per_function: {fn: [calls, diffs]}}."""
    stats = stats if stats is not None else {"calls": 0, "diffs": 0, "missing": collections.Counter(),
                                             "per_function": {}, "unreplayable": 0, "known": 0}
    contexts = contexts or _Contexts()
    shown = collections.Counter()
    for rec in records:
        name = rec["f"]
        if functions and name not in functions:
            continue
        fn = getattr(impl, name, None)
        if fn is None:
            stats["missing"][name] += 1
            continue
        pf = stats["per_function"].setdefault(name, [0, 0])
        pf[0] += 1
        stats["calls"] += 1
        with contextlib.ExitStack() as stack:
            try:
                args = decanonical(rec["a"], _Live(stack))
                kwargs = {k: decanonical(v, _Live(stack)) for k, v in rec["k"]}
            except Unreplayable as e:
                stats["unreplayable"] += 1
                out(f"UNREPLAYABLE {module}.{name} [{pass_name}] {e}: args {_short(rec['a'])}")
                continue
            if "ctx" in rec:
                stack.enter_context(contexts.enter(rec["ctx"]))
            try:
                got = canonical(fn(*args, **kwargs))
            except Exception as e:      # noqa: BLE001 - compared with the recorded exception
                got = {"x": canonical_exception(e)}
        text = dumps(got)
        problems = _compare(rec, got, text, depth=compare_depth(module, name))
        if problems is None:
            continue
        known = known_exception(module, name, rec)
        if known is not None and "r" in rec and within_relaxation(known[0], rec["r"], got):
            stats["known"] = stats.get("known", 0) + 1
            ctx = f" ctx={rec['ctx']}" if "ctx" in rec else ""
            out(f"KNOWN EXCEPTION {module}.{name} [{pass_name}{ctx}] args {_short(rec['a'], 200)} "
                f"(KNOWN_PARITY_EXCEPTIONS; not a diff)")
            continue
        pf[1] += 1
        stats["diffs"] += 1
        shown[name] += 1
        if shown[name] <= limit_diffs:
            ctx = f" ctx={rec['ctx']}" if "ctx" in rec else ""
            out(f"DIFF {module}.{name} [{pass_name}{ctx}] args {_short(rec['a'], 200)} kwargs {_short(rec['k'], 120)}")
            for line in problems:
                out(line)
    return stats


def replay_module(store_root, module, impl, *, passes=PASSES, functions=None, limit_diffs=20, out=print) -> int:
    """Replay every recorded pass of `module` against `impl`. 0 = no diffs
    and nothing missing, 1 otherwise."""
    store = Store(store_root)
    failed = False
    total = 0
    idx = store.load_index()
    modes = {k.split(".", 1)[1]: v[0] for k, v in COMPARE_MODE.items() if k.split(".", 1)[0] == module}
    for name, mode in sorted(modes.items()):
        kind = parse_mode(mode)[0]
        out(f"{module}.{name}: compared as {'a multiset' if kind == 'multiset' else mode} (COMPARE_MODE)")
    warned = set()
    for c in idx["conflicts"]:
        if c["module"] != module or c["function"] in warned:
            continue
        warned.add(c["function"])
        if c.get("kind") == "order":
            if c["function"] not in modes:
                out(f"WARNING {module}.{c['function']}: v1 row order varied between identical calls; still "
                    f"compared strictly - audit its callers and add a COMPARE_MODE entry if order never reaches output")
        else:
            out(f"WARNING {module}.{c['function']}: v1 returned different values for one call "
                f"(nondeterministic); the first result is the oracle")
    for pass_name in passes:
        if not store.data_path(module, pass_name).exists():
            out(f"{module} [{pass_name}]: no records")
            continue
        t0 = time.time()
        stats = replay_records(store.iter_records(module, pass_name), impl, module, pass_name,
                               functions=functions, limit_diffs=limit_diffs, out=out)
        total += stats["calls"]
        missing_public = 0
        for name, n in sorted(stats["missing"].items()):
            if name.startswith("_"):
                out(f"WARNING {module}.{name} [{pass_name}]: private, {n} recorded call(s), not in "
                    f"{impl.__name__} (not a failure; compared whenever it exists)")
            else:
                missing_public += n
                out(f"MISSING {module}.{name} [{pass_name}]: {n} recorded call(s), not in {impl.__name__}")
        bad = {f: v for f, v in stats["per_function"].items() if v[1]}
        for f, (calls, diffs) in sorted(bad.items()):
            out(f"  {module}.{f} [{pass_name}]: {diffs} of {calls} calls differ")
        out(f"{module} [{pass_name}]: {stats['calls']} calls replayed, {stats['diffs']} diffs, "
            f"{sum(stats['missing'].values())} missing, {stats['unreplayable']} unreplayable, "
            f"{stats.get('known', 0)} known exceptions, {time.time() - t0:.0f}s")
        failed = failed or bool(stats["diffs"] or missing_public or stats["unreplayable"])
    return 1 if failed else 0


# ---------------------------------------------------------------------------
# database selection
# ---------------------------------------------------------------------------

def check_db_name(name):
    """Allow only *_rehearsal and mis_reports_test_* (case-insensitive);
    everything else (mis_reports, mis_reports_baseline, mis_reports_v2, ...)
    is refused."""
    if not name:
        raise SystemExit("no database: pass --db or set MYSQL_DB")
    low = name.strip().lower()
    ok = (low.endswith(ALLOWED_DB_SUFFIX) and len(low) > len(ALLOWED_DB_SUFFIX)) or \
        (low.startswith(ALLOWED_DB_PREFIX) and len(low) > len(ALLOWED_DB_PREFIX))
    if not ok:
        raise SystemExit(f"refusing to run against {name!r}: only *{ALLOWED_DB_SUFFIX} and "
                         f"{ALLOWED_DB_PREFIX}* databases are allowed (e.g. mis_reports_v2_rehearsal)")


def select_database(name):
    """Point dbengine at `name` with every new session READ ONLY, and check
    the live connection is on it."""
    global _db_name_for_messages
    check_db_name(name)
    os.environ["MYSQL_DB"] = name
    import dbengine
    if not getattr(dbengine._open_raw, "__oracle_read_only__", False):
        orig_open = dbengine._open_raw

        def open_read_only():
            raw = orig_open()
            with raw.cursor() as c:
                c.execute("SET SESSION TRANSACTION READ ONLY")
            return raw
        open_read_only.__oracle_read_only__ = True
        dbengine._open_raw = open_read_only
    dbengine._pool_clear()
    actual = ps._select_database(name)
    check_db_name(actual)
    _db_name_for_messages = actual
    return actual


def _db_arg(a):
    return a.db or os.environ.get("MYSQL_DB")


# ---------------------------------------------------------------------------
# record command
# ---------------------------------------------------------------------------

def _drive(client, months, fy_months, scopes, only, exclude, log=print):
    """GET / POST the parity call set for `months`: month-scoped GETs and
    POST_EXPORTS ('month' in scopes), FY / global GETs ('nonmonth')."""
    import main
    known = {p for p, _ in ps.enumerate_get_endpoints(main.app)} | {p for p, _ in ps.POST_EXPORTS}
    unknown = sorted(((only or set()) | set(exclude)) - known)
    if unknown:
        # e.g. Git Bash rewrote "/api/x" to "C:/Program Files/Git/api/x": use MSYS_NO_PATHCONV=1
        raise SystemExit(f"--only/--exclude names no endpoint: {unknown}")
    endpoints = [(p, prm) for p, prm in ps.enumerate_get_endpoints(main.app)
                 if not ps._is_skipped(p) and (not only or p in only) and p not in exclude]
    fys = sorted({ps.fy_start_year(m) for m in fy_months} | {ps.fy_start_year(m) - 1 for m in fy_months})
    pdf_base = ps.parse_months(ps.DEFAULT_PDF_MONTHS)
    slow_fys = sorted({ps.fy_start_year(m) for m in pdf_base} | {ps.fy_start_year(m) - 1 for m in pdf_base})
    dynamic = ps._dynamic_values(client)
    statuses = collections.Counter()
    calls = 0
    timings = collections.Counter()

    def hit(method, url, **kw):
        nonlocal calls
        t1 = time.time()
        r = client.get(url, **kw) if method == "GET" else client.post(url, **kw)
        timings[url if method == "POST" else path] += time.time() - t1
        statuses[r.status_code] += 1
        calls += 1

    if "nonmonth" in scopes:
        for path, params in endpoints:
            scope, variants = ps.expand_calls(path, params, months[0],
                                              slow_fys if path in ps.SLOW_FY_ENDPOINTS else fys, dynamic)
            if variants is None or scope == "month":
                continue
            for call in variants:
                url, q = ps._split_path_params(path, params, call)
                hit("GET", url, params=q)
    if "month" in scopes:
        export_ctx = ps.export_context(client) if not only or any(p in only for p, _ in ps.POST_EXPORTS) else None
        for month in months:
            t_m = time.time()
            for path, params in endpoints:
                scope, variants = ps.expand_calls(path, params, month, fys, dynamic)
                if variants is None or scope != "month":
                    continue
                for call in variants:
                    url, q = ps._split_path_params(path, params, call)
                    hit("GET", url, params=q)
            for path, make in ps.POST_EXPORTS:
                if (only and path not in only) or path in exclude or export_ctx is None:
                    continue
                hit("POST", path, json=make(month, export_ctx))
            log(f"  {month}: {time.time() - t_m:.0f}s")
    return {"http_calls": calls, "statuses": {str(k): v for k, v in sorted(statuses.items())},
            "slowest": [[p, round(s, 1)] for p, s in timings.most_common(8)]}


def _domain_modules():
    return {m: importlib.import_module(f"repo.{m}") for m in DOMAIN_MODULES}


@contextlib.contextmanager
def caches_off(pass_name):
    """data_version.current() -> None (version caches compute every time);
    pass sql: report_context.current() -> None (no bulk serving)."""
    import data_version
    import report_context
    saved = [(data_version, "current", data_version.current)]
    data_version.current = lambda: None
    if pass_name == "sql":
        saved.append((report_context, "current", report_context.current))
        report_context.current = lambda: None
    try:
        yield
    finally:
        for obj, attr, val in reversed(saved):
            setattr(obj, attr, val)


def cmd_record(a) -> int:
    db = _db_arg(a)
    check_db_name(db)
    months = ps.parse_months(a.months)
    fy_months = ps.parse_months(a.fy_months)
    scopes = {"all": {"month", "nonmonth"}}.get(a.scopes, {a.scopes})
    only = {x.strip() for x in a.only.split(",") if x.strip()} or None
    exclude = {x.strip() for x in a.exclude.split(",") if x.strip()}
    today = _dt.date.fromisoformat(a.today) if a.today else None
    spec = {"db": db, "months": months, "scopes": sorted(scopes), "only": sorted(only or []),
            "exclude": sorted(exclude), "today": a.today, "fy_months": a.fy_months,
            "hash_seed": os.environ.get("PYTHONHASHSEED")}
    store = Store(a.store)
    if not a.force:
        for r in store.load_index()["runs"]:
            if r.get("pass") == a.pass_name and r.get("spec") == spec:
                raise SystemExit(f"already recorded ({r['run_id']}); --force to record again")
    select_database(db)
    from fastapi.testclient import TestClient
    import main
    t0 = time.time()
    rec = Recorder(a.store, a.pass_name, _domain_modules(), run_info={"spec": spec})
    with caches_off(a.pass_name), ps.pin_today(today):
        with TestClient(main.app, raise_server_exceptions=False) as client:
            with rec.installed():
                info = _drive(client, months, fy_months, scopes, only, exclude)
    run = rec.commit({"seconds": round(time.time() - t0, 1), **info})
    print(f"recorded [{a.pass_name}] {months[0]}..{months[-1]} {sorted(scopes)}: {info['http_calls']} HTTP calls "
          f"{info['statuses']}, {run['calls']} repo calls, {run['unique_new']} new unique, "
          f"{run['conflicts']} conflicts, {run['write_attempts']} write attempts, {run['seconds']}s")
    for c in rec.conflicts[:20]:
        print(f"  CONFLICT ({c['kind']}) {c['module']}.{c['function']} ctx={c['ctx']} args {c['args'][:200]}")
    for (m, f), n in sorted(rec.write_calls.items()):
        print(f"  WRITE ATTEMPT {m}.{f}: {n}")
    value_conflicts = [c for c in rec.conflicts if c["kind"] != "order"]
    return 1 if value_conflicts or rec.write_calls else 0


# ---------------------------------------------------------------------------
# report / replay commands
# ---------------------------------------------------------------------------

def cmd_report(a) -> int:
    store = Store(a.store)
    idx = store.load_index()
    mods = _domain_modules()
    total = sum(r["calls"] for r in idx["runs"])
    unique = sum(e.get(p, {}).get("unique", 0) for e in idx["functions"].values() for p in PASSES)
    size = sum(p.stat().st_size for p in store.root.glob("*.jsonl.gz"))
    secs = sum(r.get("seconds", 0) for r in idx["runs"])
    print(f"store {store.root}: {len(idx['runs'])} runs, {total} repo calls, {unique} unique, "
          f"{size / 1e6:.1f} MB gz, {secs / 60:.1f} min recording")
    print(f"conflicts (nondeterministic): {len(idx['conflicts'])}; write attempts: {idx['write_attempts']}")
    zero = []
    print(f"{'function':60s} {'sql calls':>10s} {'sql uniq':>9s} {'bulk calls':>10s} {'bulk uniq':>9s}")
    for m, mod in mods.items():
        loaders = sorted(k.split(".", 1)[1] for k in idx["functions"] if k.startswith(m + ".")
                         and k.split(".", 1)[1].startswith("_"))
        for f in read_functions(mod, m) + loaders:
            e = idx["functions"].get(f"{m}.{f}", {})
            s, b = e.get("sql", {}), e.get("bulk", {})
            print(f"{m + '.' + f:60s} {s.get('calls', 0):10d} {s.get('unique', 0):9d} "
                  f"{b.get('calls', 0):10d} {b.get('unique', 0):9d}")
            if not s.get("calls") and not b.get("calls"):
                zero.append(f"{m}.{f}")
    print(f"zero-call read functions ({len(zero)}):")
    for z in zero:
        print(f"  {z}")
    return 0


def cmd_replay(a) -> int:
    db = _db_arg(a)
    select_database(db)
    if a.impl == "v1":
        tests_dir = str(BACKEND_DIR / "tests")
        if tests_dir not in sys.path:
            sys.path.insert(0, tests_dir)
    package = "_v1_frozen" if a.impl == "v1" else "repo"
    try:
        impl = importlib.import_module(f"{package}.{a.module}")
    except ModuleNotFoundError as e:
        print(f"cannot import {package}.{a.module}: {e}")
        return 1
    functions = {x.strip() for x in a.functions.split(",") if x.strip()} or None
    passes = [p.strip() for p in a.passes.split(",") if p.strip()]
    print(f"replay {a.module} against {impl.__name__} on {db} (store {a.store})")
    return replay_module(a.store, a.module, impl, passes=passes, functions=functions, limit_diffs=a.limit_diffs)


HASH_SEED = "0"


def _reexec_with_fixed_hash_seed(argv):
    """record / replay run with PYTHONHASHSEED=0: some repo reads build dicts
    by iterating a set of strings (e.g. mines.get_iron_ore_group_rollup_monthly),
    whose order otherwise changes from one process to the next. Returns the
    child's exit code, or None when the seed is already fixed."""
    if os.environ.get("PYTHONHASHSEED") == HASH_SEED:
        return None
    import subprocess
    env = dict(os.environ, PYTHONHASHSEED=HASH_SEED)
    return subprocess.call([sys.executable, "-m", "tools.repo_oracle", *argv], env=env, cwd=str(BACKEND_DIR))


def main_cli(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("record", "replay"):
        code = _reexec_with_fixed_hash_seed(argv)
        if code is not None:
            return code
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--db", default=None)
    r.add_argument("--pass", dest="pass_name", choices=PASSES, required=True)
    r.add_argument("--months", default=ps.DEFAULT_MONTHS)
    r.add_argument("--fy-months", default=ps.DEFAULT_MONTHS,
                   help="months whose FYs (and the FY before) FY-keyed GETs are driven for (the full parity range)")
    r.add_argument("--scopes", choices=("month", "nonmonth", "all"), default="all")
    r.add_argument("--only", default="")
    r.add_argument("--exclude", default="")
    r.add_argument("--today", default=None)
    r.add_argument("--store", type=Path, default=DEFAULT_STORE)
    r.add_argument("--force", action="store_true")
    p = sub.add_parser("replay")
    p.add_argument("--module", required=True, choices=DOMAIN_MODULES)
    p.add_argument("--functions", default="")
    p.add_argument("--limit-diffs", type=int, default=20)
    p.add_argument("--impl", choices=("current", "v1"), default="current")
    p.add_argument("--passes", default=",".join(PASSES))
    p.add_argument("--db", default=None)
    p.add_argument("--store", type=Path, default=DEFAULT_STORE)
    s = sub.add_parser("report")
    s.add_argument("--store", type=Path, default=DEFAULT_STORE)
    a = ap.parse_args(argv)
    return {"record": cmd_record, "replay": cmd_replay, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main_cli())
