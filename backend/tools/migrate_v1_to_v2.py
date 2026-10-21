"""Migrate a v1 MySQL database into an empty-schema v2 database (Task 6).

    python -m tools.migrate_v1_to_v2 --src mis_reports_baseline --dst mis_reports_v2_rehearsal \\
        [--src-defaults-file C:/mysql/backup.cnf] [--dst-defaults-file ...]

migrate(src_db, dst_db) is idempotent: it reads and converts the whole v1
database first (nothing is written if any value cannot be carried exactly:
a month outside cal_month, a timestamp that would not render back, an
unknown plant or v1 table, ...), then empties every dst table except the
seeded cal_month (data_version is overwritten), and loads everything in one
transaction. The dst must already hold the v2 DDL (scripts/v2/schema_v2.sql
+ seed_cal_month.sql).

The value rules (timestamps, techno blobs, narrative text, production
has_* flags) live in repo/v2codec.py, shared with verify_v2 and Task 7.
Never point --dst at mis_reports or mis_reports_baseline; the src is opened
READ ONLY.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymysql
from pymysql.constants import FIELD_TYPE

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from repo import v2codec as vc  # noqa: E402

PROTECTED_DBS = {"mis_reports", "mis_reports_baseline"}


class MigrationError(RuntimeError):
    """The v1 data cannot be carried into v2 exactly; nothing was written."""


# ── connections ─────────────────────────────────────────────────────────────

def _env_cfg() -> Dict[str, Any]:
    try:
        from dotenv import load_dotenv
        load_dotenv(BACKEND / ".env")
    except ImportError:  # pragma: no cover
        pass
    return {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "mis_app"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
    }


def connect(db: str, cfg: Optional[Dict[str, Any]] = None):
    """A pymysql connection to `db`. cfg: {host, port, user, password} or
    {read_default_file: path} (a mysql option file); default: backend/.env.
    DATETIME / DATE come back as strings, as through dbengine."""
    cfg = dict(cfg or _env_cfg())
    conv = pymysql.converters.conversions.copy()
    for ft in (FIELD_TYPE.DATETIME, FIELD_TYPE.DATE, FIELD_TYPE.TIMESTAMP):
        conv[ft] = str
    return pymysql.connect(database=db, charset="utf8mb4", autocommit=False,
                           ssl_disabled=True, conv=conv, **cfg)


# ── masters ─────────────────────────────────────────────────────────────────

# Every v1 column holding a plant string (extraction_log.plant_name is a free
# label and stays one). The plant master is exactly the distinct strings here.
PLANT_COLUMNS: List[Tuple[str, str]] = [
    ("production_table", "plant_name"), ("production_plan_table", "plant_name"),
    ("mou_plan_table", "plant_name"), ("item_capacity_table", "plant_name"),
    ("pdf_item_alias", "plant_name"), ("power_data_table", "plant_name"),
    ("stock_table", "plant_name"), ("ipt_table", "from_plant"), ("ipt_table", "to_plant"),
    ("techno_data", "plant"), ("techno_plan_fy", "plant_name"), ("board_note_manual_text", "plant"),
    ("do_letter_remark_table", "plant_name"), ("special_steel_orders", "plant_name"),
    ("special_steel_abp_table", "plant_name"), ("special_steel_grade_clubs", "plant_name"),
    ("special_steel_phys_meta", "plant"), ("special_steel_phys_perf", "plant"),
    ("special_steel_ipt_requirement", "from_plant"), ("special_steel_ipt_requirement", "to_plant"),
    ("cost_trend_annual", "plant"), ("cost_trend_monthly", "plant"),
    ("rake_detention_master", "plant"), ("rake_detention_summary", "plant"),
    ("rake_detention_annual", "plant"), ("bf_benchmark_sail_meta", "plant"),
    ("capital_repair_table", "plant"), ("breakdown_table", "plant"),
    ("major_unit_daily_record", "plant_code"), ("ready_reckoner_pages", "plant_code"),
]

# Every v1 column holding a production / plan / MoU item name.
ITEM_COLUMNS: List[Tuple[str, str]] = [
    ("production_table", "item_name"), ("production_plan_table", "item_name"),
    ("mou_plan_table", "item_name"), ("item_capacity_table", "item_name"),
    ("pdf_item_alias", "item_name"), ("do_letter_remark_table", "item_name"),
]

# Every v1 (plant column, unit column) pair.
UNIT_COLUMNS: List[Tuple[str, str, str]] = [
    ("techno_data", "plant", "unit"), ("techno_plan_fy", "plant_name", "unit"),
    ("breakdown_table", "plant", "unit_name"), ("capital_repair_table", "plant", "unit_name"),
    ("bf_benchmark_sail_meta", "plant", "unit"), ("major_unit_daily_record", "plant_code", "unit_label"),
]

# plant_kind / sort_order of every plant string v1 holds. A plant string not
# listed here stops the migration (add it rather than guess its kind).
PLANT_KIND: Dict[str, str] = {
    "BSP": "integrated", "DSP": "integrated", "RSP": "integrated", "BSL": "integrated",
    "ISP": "integrated", "ASP": "special", "SSP": "special", "VISL": "special", "VISP": "special",
    "CFP": "special", "SAIL": "aggregate", "SSPs": "aggregate",
}
PLANT_ORDER = list(PLANT_KIND)


# ── simple tables: v1 table -> v2 table, column by column ───────────────────
# Each column is (v2 column, v1 column, kind):
#   None     copied verbatim
#   month    copied; must be a cal_month report_month
#   ts       v1 VARCHAR timestamp -> DATETIME by vc.TS_COLUMNS[v2 table.column]
#   mixed    ts of a TS_PLAIN_FLAGS column; ('flag') its per-row plain flag
#   date     v1 'YYYY-MM-DD' -> DATE
#   item     item name -> item_id
#   unit:<plant column>  unit string -> unit_id of (plant, unit); NULL stays NULL

def _cols(*spec):
    out = []
    for s in spec:
        if isinstance(s, str):
            out.append((s, s, None))
        elif len(s) == 2:
            out.append((s[0], s[0], s[1]))
        else:
            out.append(tuple(s))
    return out


SIMPLE: List[Tuple[str, str, list]] = [
    ("item_capacity_table", "item_capacity", _cols(
        "id", ("plant_code", "plant_name", None), ("item_id", "item_name", "item"),
        ("effective_month", "month"), "annual_capacity", "reason", "created_by", ("created_at", "ts"),
        "updated_by", ("updated_at", "ts"))),
    ("pdf_item_alias", "pdf_item_alias", _cols(
        ("plant_code", "plant_name", None), "pdf_label", ("item_id", "item_name", "item"), "convert_t")),
    ("power_data_table", "power_monthly", _cols(
        ("report_month", "month"), ("plant_code", "plant_name", None), ("power_item", "item_name", None),
        "value")),
    ("stock_table", "stock_monthly", _cols(
        ("report_month", "stock_month", "month"), ("plant_code", "plant_name", None), "item_type",
        "stock_type", "stock")),
    ("ipt_table", "ipt_monthly", _cols(
        ("report_month", "month"), "item", ("from_plant_code", "from_plant", None),
        ("to_plant_code", "to_plant", None), "unit", "sort_order", "plan", "actual", "plan_tonnage",
        "actual_tonnage")),
    ("techno_plan_fy", "techno_plan_fy", _cols(
        ("plant_code", "plant_name", None), ("unit_id", "unit", "unit:plant_name"), "fy", "techno_json",
        "is_user_supplied", "calculated_json", "calculation_method", "created_at", "updated_at",
        "created_by")),
    ("special_steel_orders", "special_steel_order", _cols(
        ("report_month", "month"), ("plant_code", "plant_name", None), "product", "quality_grade",
        "section", "sort_order", "order_qty", "actual_despatch")),
    ("special_steel_abp_table", "special_steel_abp", _cols(
        ("report_month", "month"), ("plant_code", "plant_name", None), "abp_qty")),
    ("special_steel_grade_clubs", "special_steel_grade_club", _cols(
        ("plant_code", "plant_name", None), "product", "quality_grade", "club_label", ("created_at", "ts"))),
    ("special_steel_phys_meta", "special_steel_phys_meta", _cols(
        ("plant_code", "plant", None), "series", "capacity_kt", "best_actual_kt", "best_year", "remark",
        "sort_order")),
    ("special_steel_phys_perf", "special_steel_phys_perf", _cols(
        ("fy", "financial_year", None), ("plant_code", "plant", None), "series", "metric", "value_kt")),
    ("special_steel_ipt_requirement", "special_steel_ipt_requirement", _cols(
        ("fy", "financial_year", None), "item", ("from_plant_code", "from_plant", None),
        ("to_plant_code", "to_plant", None), "plan_kt", "sort_order")),
    ("cost_trend_annual", "cost_trend_annual", _cols(
        "fy", "product", "cost_type", ("plant_code", "plant", None), "value")),
    ("cost_trend_monthly", "cost_trend_monthly", _cols(
        ("report_month", "month"), "product", "cost_type", ("plant_code", "plant", None), "month_value",
        "till_month_value")),
    ("rake_detention_master", "rake_detention_master", _cols(
        "id", ("plant_code", "plant", None), "section", "commodity", "wagon_type", "row_label", "is_total",
        "direction", "freetime_hours", "freetime_effective_from", "sort_order", "is_active")),
    ("rake_detention_monthly", "rake_detention_monthly", _cols(
        ("report_month", "month"), "master_id", "value_hours")),
    ("rake_detention_summary", "rake_detention_summary", _cols(
        ("report_month", "month"), "period_row", ("plant_code", "plant", None), "value")),
    ("rake_detention_annual", "rake_detention_annual", _cols(
        ("plant_code", "plant", None), ("fy", "financial_year", None), "avg_hours")),
    ("macro_indicators_monthly", "macro_indicator_monthly", _cols(
        ("report_month", "month"), "metric_code", "value")),
    ("market_price_trend_monthly", "market_price_monthly", _cols(
        ("report_month", "month"), "series_code", "value")),
    ("sail_sales_table", "sail_sales_monthly", _cols(
        ("report_month", "month"), "item_name", "data_json")),
    ("sail_stock_snapshot_table", "sail_stock_snapshot", _cols(
        ("snapshot_date", "date"), "item_name", "value")),
    ("steel_sector_performance_table", "steel_sector_performance", _cols(
        ("report_month", "month"), "data_json", "source_file", ("created_at", "ts"))),
    ("rail_prod_despatch", "rail_prod_despatch", _cols(
        ("fy", "financial_year", None), "metric", "value", "note")),
    ("mine_groups_master", "mine_group", _cols("group_code", "group_name", "sort_order")),
    ("mines_master", "mine", _cols("mine_code", "mine_name", "group_code", "is_active", "sort_order")),
    ("mine_materials_master", "mine_material", _cols(
        "material_code", "material_name", "material_category", "has_production",
        "counts_in_total_production", "sort_order")),
    ("mine_end_uses_master", "mine_end_use", _cols(
        "end_use_code", "end_use_name", "sort_order", "tracks_actual")),
    ("mines_production_monthly", "mine_production_monthly", _cols(
        ("report_month", "month"), "mine_code", "material_code", "qty_actual", "qty_plan")),
    ("mines_despatch_actual_monthly", "mine_despatch_actual_monthly", _cols(
        ("report_month", "month"), "mine_code", "material_code", "transport_mode", "end_use_code",
        "qty_actual")),
    ("mines_despatch_plan_monthly", "mine_despatch_plan_monthly", _cols(
        ("report_month", "month"), "mine_code", "material_code", "end_use_code", "qty_plan")),
    ("mines_booked_qty_actual_monthly", "mine_booked_qty_actual_monthly", _cols(
        ("report_month", "month"), "mine_code", "material_code", "transport_mode", "qty_actual")),
    ("mines_booked_qty_plan_monthly", "mine_booked_qty_plan_monthly", _cols(
        ("report_month", "month"), "mine_code", "material_code", "qty_plan")),
    ("sail_mines_monthly", "sail_mines_monthly", _cols(
        ("report_month", "month"), "section", "item", "month_actual", "month_plan")),
    ("bf_benchmark_external_bf", "bf_benchmark_external_bf", _cols(
        "id", "name", "company", "location", "working_volume_m3", "active", ("created_at", "mixed"),
        ("created_at_plain", "created_at", "flag"), "created_by")),
    ("bf_benchmark_external_data", "bf_benchmark_external_data", _cols(
        "id", "external_bf_id", ("fy", "report_month", None), "param_json", ("created_at", "mixed"),
        ("updated_at", "mixed"), ("created_at_plain", "created_at", "flag"),
        ("updated_at_plain", "updated_at", "flag"))),
    ("bf_benchmark_sail_meta", "bf_benchmark_sail_meta", _cols(
        ("plant_code", "plant", None), ("unit_id", "unit", "unit:plant"), "working_volume_m3",
        ("updated_at", "ts"))),
    ("capital_repair_table", "capital_repair", _cols(
        "id", ("plant_code", "plant", None), "fy", "shop", "equipment", "unit_type",
        ("unit_id", "unit_name", "unit:plant"), "sms_subtag", "activity", "schedule_days",
        ("actual_start", "date"), ("actual_end", "date"), "actual_ongoing", "planned_days", "period",
        "actual", "sort_order")),
    ("breakdown_table", "breakdown", _cols(
        "id", ("plant_code", "plant", None), "unit_type", ("unit_id", "unit_name", "unit:plant"),
        "sms_subtag", "start_ts", "end_ts", "is_ongoing", "cause", "hours_lost_override",
        "capital_repair_id", "created_by", ("created_at", "ts"), "updated_by", ("updated_at", "ts"))),
    ("major_unit_daily_record", "major_unit_daily_record", _cols(
        "plant_code", ("unit_id", "unit_label", "unit:plant_code"), "unit_of_measure", "value",
        ("record_date", "date"), "remarks", "sort_order", "updated_by", ("updated_at", "ts"))),
    ("ready_reckoner_pages", "ready_reckoner_page", _cols(
        "plant_code", "plant_name", "plant_group", "process_flow_image_path", "sort_order", "updated_by",
        "updated_at", "capacity_rows", "product_mix_headers", "product_mix_rows", "product_mix_caption")),
    ("page_configs", "page_config", _cols(("report_month", "month"), "page_number", "page_data")),
    ("cover_photos", "cover_photo", _cols(
        "id", "filename", "thumb_filename", "original_name", "width", "height",
        ("created_by", "uploaded_by", None), ("created_at", "uploaded_at", "ts"), "is_active")),
    ("report_cover_settings", "report_cover_setting", _cols(
        ("report_month", "month"), "design", "photo_mode", "photo_id", "updated_by", ("updated_at", "ts"))),
    ("users", "app_user", _cols(
        "id", "email", "password_hash", "name", "role", "profile_pic", ("created_at", "ts"),
        ("updated_at", "ts"), "allowed_pages", "can_delete")),
    ("allowed_emails", "allowed_email", _cols(
        "email", ("created_by", "added_by", None), ("created_at", "added_at", "ts"), "barred", "barred_by",
        ("barred_at", "ts"))),
    ("otp_codes", "otp_code", _cols(
        "id", "email", "purpose", "code_hash", ("expires_at", "ts"), "used", ("created_at", "ts"))),
    ("activity_log", "activity_log", _cols(
        "id", "user_email", "user_name", "action", "entity", "details", ("created_at", "timestamp", "ts"))),
    ("page_visits", "page_visit", _cols(
        "id", ("created_at", "timestamp", "ts"), "ip_address", "user_email", "user_name", "path")),
    ("admin_notifications", "admin_notification", _cols(
        "id", ("created_at", "ts"), "kind", "user_email", "user_name", "ip_address", "path")),
    ("extraction_log", "extraction_log", _cols(
        "id", ("created_at", "logged_at", "ts"), "plant_name", "report_month", "file_name", "sheet_name",
        "source_type", "items_extracted")),
    ("todo_jobs", "todo_job", _cols(
        "id", "subject", "details", "recipient", ("due_date", "date"), "priority", "status",
        ("created_at", "ts"), ("completed_at", "ts"), "remark")),
    ("daily_work_log", "daily_work_log", _cols(
        "id", ("work_date", "date"), "description", "remarks", ("created_at", "ts"))),
]

PRODUCTION_TABLES = tuple(vc.PRODUCTION_SOURCES)
TEXT_TABLES = tuple(vc.TEXT_TABLE_SCOPE)
DROPPED = ("ipt_data_json", "production_data_json", "production_plan_json", "special_steel_json",
           "stock_data_json")
HANDLED = ({t for t, _, _ in SIMPLE} | set(PRODUCTION_TABLES) | set(TEXT_TABLES) | set(DROPPED)
           | {"techno_data", "data_version"})

# v2 tables in FK load order (parents first). cal_month is never touched.
LOAD_ORDER = [
    "plant", "item", "plant_unit", "production_monthly", "techno_upload", "techno_value", "report_text",
] + [v2 for _, v2, _ in SIMPLE]


# ── read + convert (no writes) ──────────────────────────────────────────────

def _fetch(cur, table) -> Tuple[List[str], List[tuple]]:
    cur.execute(f"SELECT * FROM `{table}`")
    cols = [d[0] for d in cur.description]
    return cols, list(cur.fetchall())


class _Plan:
    """Everything to write: v2 table -> (columns, rows)."""

    def __init__(self):
        self.tables: Dict[str, Tuple[List[str], List[tuple]]] = {}
        self.data_version: Optional[int] = None
        self.errors: List[str] = []

    def error(self, msg):
        self.errors.append(msg)


def _row_id(table, cols, row) -> str:
    return f"{table} row {dict(zip(cols, row))!r}"


def build_plan(src_cur, cal_months: set) -> _Plan:
    plan = _Plan()
    src_cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
    v1_tables = {r[0] for r in src_cur.fetchall()}
    unknown = sorted(v1_tables - HANDLED)
    if unknown:
        plan.error(f"v1 tables with no v2 mapping: {unknown}")
    missing = sorted(HANDLED - v1_tables - {"data_version"})
    if missing:
        plan.error(f"v1 tables missing from the source: {missing}")
    if plan.errors:
        return plan

    data: Dict[str, Tuple[List[str], List[tuple]]] = {}
    for t in sorted(HANDLED - set(DROPPED)):
        if t in v1_tables:
            data[t] = _fetch(src_cur, t)

    def col_values(table, col):
        cols, rows = data[table]
        i = cols.index(col)
        return [r[i] for r in rows]

    def check_month(table, cols, row, value):
        if value not in cal_months:
            plan.error(f"{_row_id(table, cols, row)}: month {value!r} is outside cal_month")

    # plant
    plant_names = {}
    if "ready_reckoner_pages" in data:
        cols, rows = data["ready_reckoner_pages"]
        for r in rows:
            d = dict(zip(cols, r))
            plant_names[d["plant_code"]] = d["plant_name"]
    plants = set()
    for t, c in PLANT_COLUMNS:
        plants.update(col_values(t, c))
    for p in sorted(plants):
        if p not in PLANT_KIND:
            where = [f"{t}.{c}" for t, c in PLANT_COLUMNS if p in col_values(t, c)]
            plan.error(f"plant string {p!r} (in {where}) has no plant_kind: add it to PLANT_KIND")
    plan.tables["plant"] = (["plant_code", "plant_name", "plant_kind", "sort_order"], [
        (p, plant_names.get(p), PLANT_KIND.get(p), PLANT_ORDER.index(p) + 1 if p in PLANT_KIND else 0)
        for p in sorted(plants, key=lambda p: (PLANT_ORDER.index(p) if p in PLANT_KIND else 99, p))])

    # item (ids deterministic: byte order of the names)
    names = set()
    for t, c in ITEM_COLUMNS:
        names.update(col_values(t, c))
    item_id = {n: i for i, n in enumerate(sorted(names, key=lambda s: s.encode("utf-8")), 1)}
    plan.tables["item"] = (["item_id", "item_name", "uom"], [(i, n, None) for n, i in item_id.items()])

    # plant_unit; unit_type = the single breakdown / capital-repair type, else NULL
    pairs = set()
    for t, pc, uc in UNIT_COLUMNS:
        pairs.update((p, u) for p, u in zip(col_values(t, pc), col_values(t, uc)) if u is not None)
    types = defaultdict(set)
    for t in ("breakdown_table", "capital_repair_table"):
        uc = "unit_name"
        for p, u, ty in zip(col_values(t, "plant"), col_values(t, uc), col_values(t, "unit_type")):
            if u is not None and ty is not None:
                types[(p, u)].add(ty)
    unit_id = {pu: i for i, pu in enumerate(
        sorted(pairs, key=lambda pu: (pu[0].encode("utf-8"), pu[1].encode("utf-8"))), 1)}
    plan.tables["plant_unit"] = (["unit_id", "plant_code", "unit_code", "unit_type"], [
        (i, p, u, next(iter(types[(p, u)])) if len(types[(p, u)]) == 1 else None)
        for (p, u), i in unit_id.items()])

    # production_monthly
    prod: Dict[tuple, Dict[str, Any]] = {}
    for t, (vcol, flag) in vc.PRODUCTION_SOURCES.items():
        cols, rows = data[t]
        for r in rows:
            d = dict(zip(cols, r))
            check_month(t, cols, r, d["report_month"])
            key = (d["report_month"], d["plant_name"], d["item_name"])
            rec = prod.setdefault(key, {})
            rec[vcol] = d["month_actual"]
            rec[flag] = 1
    plan.tables["production_monthly"] = (
        ["report_month", "plant_code", "item_id", "actual", "abp_plan", "mou_plan",
         "has_actual", "has_abp", "has_mou"],
        [(m, p, item_id[i], rec.get("actual"), rec.get("abp_plan"), rec.get("mou_plan"),
          rec.get("has_actual", 0), rec.get("has_abp", 0), rec.get("has_mou", 0))
         for (m, p, i), rec in prod.items()])

    # techno_upload + techno_value
    uploads, values = [], []
    cols, rows = data["techno_data"]
    for r in rows:
        d = dict(zip(cols, r))
        check_month("techno_data", cols, r, d["report_month"])
        uid = unit_id[(d["plant"], d["unit"])]
        try:
            has_m, has_t, leaves = vc.encode_techno(d["techno_json"])
            created = vc.parse_ts(vc.TS_COLUMNS["techno_upload.created_at"][1], d["created_at"])
        except (vc.CodecError, ValueError) as e:
            plan.error(f"{_row_id('techno_data', cols, r)}: {e}")
            continue
        uploads.append((d["report_month"], d["plant"], uid, has_m, has_t, d["source_file"], created))
        values.extend((d["report_month"], d["plant"], uid) + leaf for leaf in leaves)
    plan.tables["techno_upload"] = (["report_month", "plant_code", "unit_id", "has_month", "has_till_month",
                                     "source_file", "created_at"], uploads)
    plan.tables["techno_value"] = (["report_month", "plant_code", "unit_id", "period", "param_key", "num",
                                    "is_int", "raw"], values)

    # report_text (ids deterministic: scope order, then v1 primary-key order)
    texts = []
    for scope, spec in vc.TEXT_SCOPES.items():
        cols, rows = data[spec["table"]]
        encoded = []
        for r in rows:
            d = dict(zip(cols, r))
            try:
                encoded.extend(vc.encode_text_row(scope, d))
            except (vc.CodecError, ValueError, KeyError) as e:
                plan.error(f"{_row_id(spec['table'], cols, r)}: {e}")
        encoded.sort(key=lambda x: (x["period"], x["plant_code"] or "", x["item_name"] or "",
                                    x["block_key"], x["seq"]))
        for x in encoded:
            if x["item_name"] is not None and x["item_name"] not in item_id:
                plan.error(f"{spec['table']}: item {x['item_name']!r} not in the item master")
                continue
            texts.append((scope, x["period"], x["block_key"], x["plant_code"],
                          item_id.get(x["item_name"]) if x["item_name"] is not None else None,
                          x["seq"], x["text"], x["updated_by"], x["updated_at"]))
    plan.tables["report_text"] = (["id", "scope", "period", "block_key", "plant_code", "item_id", "seq",
                                   "text", "updated_by", "updated_at"],
                                  [(i,) + t for i, t in enumerate(texts, 1)])

    # simple tables
    for v1t, v2t, spec in SIMPLE:
        cols, rows = data[v1t]
        missing_cols = [c1 for _, c1, _ in spec if c1 not in cols]
        if missing_cols:
            plan.error(f"{v1t}: v1 columns {missing_cols} not found")
            continue
        idx = {c: i for i, c in enumerate(cols)}
        out = []
        for r in rows:
            vals = []
            ok = True
            for c2, c1, kind in spec:
                v = r[idx[c1]]
                try:
                    if kind is None:
                        pass
                    elif kind == "month":
                        check_month(v1t, cols, r, v)
                    elif kind == "ts":
                        v = vc.parse_ts(vc.TS_COLUMNS[f"{v2t}.{c2}"][1], v)
                    elif kind == "mixed":
                        v = vc.parse_ts_mixed(v)[0]
                    elif kind == "flag":
                        v = vc.parse_ts_mixed(v)[1]
                    elif kind == "date":
                        assert f"{v2t}.{c2}" in vc.DATE_COLUMNS, f"{v2t}.{c2}"
                        v = vc.parse_date(v)
                    elif kind == "item":
                        v = item_id[v]
                    elif kind.startswith("unit:"):
                        v = None if v is None else unit_id[(r[idx[kind[5:]]], v)]
                    else:
                        raise AssertionError(kind)
                except (vc.CodecError, KeyError) as e:
                    plan.error(f"{_row_id(v1t, cols, r)}: column {c1}: {e}")
                    ok = False
                vals.append(v)
            if ok:
                out.append(tuple(vals))
        plan.tables[v2t] = ([c2 for c2, _, _ in spec], out)

    if "data_version" in data:
        cols, rows = data["data_version"]
        plan.data_version = dict(zip(cols, rows[0]))["n"] if rows else None
    return plan


# ── write ───────────────────────────────────────────────────────────────────

def _dirty_tables(cur) -> List[str]:
    """dst tables holding rows or an advanced AUTO_INCREMENT (TRUNCATE is a
    slow DDL here, so only those are truncated)."""
    cur.execute("SET SESSION information_schema_stats_expiry = 0")
    cur.execute("SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'")
    tables = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND auto_increment > 1")
    dirty = {r[0] for r in cur.fetchall()}
    for t in tables:
        if t not in dirty:
            cur.execute(f"SELECT EXISTS(SELECT 1 FROM `{t}`)")
            if cur.fetchone()[0]:
                dirty.add(t)
    return sorted(dirty - {"cal_month", "data_version"})


def _empty_dst(cur, data_version_n=1):
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    try:
        for t in _dirty_tables(cur):
            cur.execute(f"TRUNCATE TABLE `{t}`")
    finally:
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    cur.execute("INSERT INTO data_version (id, n) VALUES (1, %s) AS new ON DUPLICATE KEY UPDATE n = new.n",
                (data_version_n,))


def _insert(cur, table, cols, rows, chunk=1000):
    if not rows:
        return
    sql = (f"INSERT INTO `{table}` ({', '.join(f'`{c}`' for c in cols)}) "
           f"VALUES ({', '.join(['%s'] * len(cols))})")
    cur.execute("SAVEPOINT load_table")
    try:
        for i in range(0, len(rows), chunk):
            cur.executemany(sql, rows[i:i + chunk])
    except pymysql.MySQLError as e:
        # name the offending row: replay one by one up to the failure
        cur.execute("ROLLBACK TO SAVEPOINT load_table")
        for r in rows:
            try:
                cur.execute(sql, r)
            except pymysql.MySQLError as e1:
                raise MigrationError(f"{table}: {e1} -- row {dict(zip(cols, r))!r}") from e1
        raise MigrationError(f"{table}: {e}") from e


def _check_dst(dst_db, src_db):
    if not dst_db or dst_db in PROTECTED_DBS or dst_db == src_db:
        raise MigrationError(f"refusing to write database {dst_db!r}")


def migrate(src_db: str, dst_db: str, *, src_cfg: Optional[dict] = None,
            dst_cfg: Optional[dict] = None) -> None:
    """Load v1 `src_db` into v2 `dst_db` (see the module docstring)."""
    _check_dst(dst_db, src_db)
    src = connect(src_db, src_cfg)
    dst = connect(dst_db, dst_cfg)
    try:
        with src.cursor() as s, dst.cursor() as d:
            s.execute("SET SESSION TRANSACTION READ ONLY")
            s.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            d.execute("SHOW TABLES LIKE 'techno_value'")
            if not d.fetchone():
                raise MigrationError(f"{dst_db!r} has no v2 schema (no techno_value table)")
            s.execute("SHOW TABLES LIKE 'techno_data'")
            if not s.fetchone():
                raise MigrationError(f"{src_db!r} has no v1 schema (no techno_data table)")
            d.execute("SELECT report_month FROM cal_month")
            cal_months = {r[0] for r in d.fetchall()}
            if not cal_months:
                raise MigrationError(f"{dst_db!r}: cal_month is empty (run seed_cal_month.sql)")

            plan = build_plan(s, cal_months)
            src.rollback()
            if plan.errors:
                shown = "\n  ".join(plan.errors[:50])
                more = f"\n  ... and {len(plan.errors) - 50} more" if len(plan.errors) > 50 else ""
                raise MigrationError(f"v1 data cannot be migrated exactly ({len(plan.errors)} "
                                     f"problems); nothing was written:\n  {shown}{more}")

            _empty_dst(d, plan.data_version or 1)
            dst.commit()
            for t in LOAD_ORDER:
                cols, rows = plan.tables[t]
                _insert(d, t, cols, rows)
            dst.commit()
    except BaseException:
        dst.rollback()
        raise
    finally:
        src.close()
        dst.close()


def clear_dst(dst_db: str, *, dst_cfg: Optional[dict] = None) -> None:
    """Empty every v2 table except cal_month; data_version back to (1, 1)."""
    _check_dst(dst_db, None)
    dst = connect(dst_db, dst_cfg)
    try:
        with dst.cursor() as d:
            _empty_dst(d, 1)
        dst.commit()
    finally:
        dst.close()


def _cfg_from_args(defaults_file):
    return {"read_default_file": defaults_file} if defaults_file else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", required=True, help="v1 database (read only)")
    ap.add_argument("--dst", required=True, help="v2 database (emptied, then loaded)")
    ap.add_argument("--src-defaults-file", help="mysql option file for the source connection")
    ap.add_argument("--dst-defaults-file", help="mysql option file for the destination connection")
    a = ap.parse_args(argv)
    migrate(a.src, a.dst, src_cfg=_cfg_from_args(a.src_defaults_file),
            dst_cfg=_cfg_from_args(a.dst_defaults_file))
    print(f"migrated {a.src} -> {a.dst}")


if __name__ == "__main__":
    main()
