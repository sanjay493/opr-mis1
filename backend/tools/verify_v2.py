"""Verify a v2 database against the v1 database it was migrated from (Task 6b).

    python -m tools.verify_v2 --src mis_reports_baseline --dst mis_reports_v2_rehearsal \\
        [--src-defaults-file C:/mysql/backup.cnf] [--dst-defaults-file ...]

verify(src_db, dst_db) -> list of problems (empty = OK); the CLI prints them
and exits 1 when there are any. Both sides are opened in a consistent
READ ONLY transaction: verify never writes.

Checks:
  * FULL ROUND-TRIP. Every v2 table is decoded back to the v1 shape through
    repo.v2codec and compared with the v1 rows value by value (type and
    value), keyed by the natural key (plant / item / unit by NAME, never by
    id): the 3 production tables (absent vs NULL via has_*), every techno
    blob (== json.loads(v1), the type of each leaf, key order at every level,
    source_file, created_at), the 9 narrative scopes (decoded, and the
    report_text rows compared exactly with the v1 rows' encoding, so the
    fields the decoder does not read are checked too), and every other
    table column by column (every timestamp re-rendered to the exact v1
    string and its stored DATETIME equal to the parsed v1 value, page_data
    byte for byte). Every v1 column must be carried somewhere.
  * Independence from migrate's own map: every column rename in
    migrate's SIMPLE map must match the hand-written EXPECTED_RENAMES (both
    directions), and every column of every v2 table must be covered by the
    map, NON_SIMPLE_V2_COLUMNS or SYNTHESISED_V2_COLUMNS.
  * Canonical forms the decoders cannot see: production has_*=0 -> value
    NULL; (month, plant, ai_ci item name) unique among has_actual=1 rows; techno leaves with raw -> num NULL, is_int 0; is_int=1 -> integral.
  * Row counts per table, allowing for the documented merges / splits.
  * SUM (and count) of every numeric column per (month or fy, plant).
  * JSON_VALID on every JSON column and on page_config.page_data.
  * FK orphans: an explicit NOT EXISTS query per declared FK (the load may
    have run with FOREIGN_KEY_CHECKS=0), and every FK of schema_v2.sql must
    be declared in dst. Deliberate non-FKs (extraction_log.plant_name /
    report_month, breakdown.capital_repair_id) are not FKs and not checked.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from repo import v2codec as vc  # noqa: E402
from tools import migrate_v1_to_v2 as mig  # noqa: E402

SCHEMA_V2 = BACKEND / "scripts" / "v2" / "schema_v2.sql"
MAX_PER_CHECK = 20

# v1 columns deliberately not carried into v2 (any other uncarried v1 column
# is reported as data loss).
DROPPED_V1_COLUMNS: Dict[str, set] = {}     # techno_data.id is carried as techno_upload.seq (7c)

# Every v1 -> v2 column rename of the SIMPLE tables, written by hand from
# tests/fixtures/schema_v1.sql vs scripts/v2/schema_v2.sql (NOT derived from
# migrate's map): verify checks migrate's map against it, so a mispaired
# column in the map cannot pass both tools. (v1 table, v1 column) -> v2 column.
# The *_plain flags are not renames of their own: each is derived from the
# v1 timestamp column named here.
EXPECTED_RENAMES: Dict[Tuple[str, str], str] = {
    ("item_capacity_table", "plant_name"): "plant_code",
    ("item_capacity_table", "item_name"): "item_id",
    ("pdf_item_alias", "plant_name"): "plant_code",
    ("pdf_item_alias", "item_name"): "item_id",
    ("power_data_table", "plant_name"): "plant_code",
    ("power_data_table", "item_name"): "power_item",
    ("stock_table", "stock_month"): "report_month",
    ("stock_table", "plant_name"): "plant_code",
    ("ipt_table", "from_plant"): "from_plant_code",
    ("ipt_table", "to_plant"): "to_plant_code",
    ("techno_plan_fy", "plant_name"): "plant_code",
    ("techno_plan_fy", "unit"): "unit_id",
    ("special_steel_orders", "plant_name"): "plant_code",
    ("special_steel_abp_table", "plant_name"): "plant_code",
    ("special_steel_grade_clubs", "plant_name"): "plant_code",
    ("special_steel_phys_meta", "plant"): "plant_code",
    ("special_steel_phys_perf", "financial_year"): "fy",
    ("special_steel_phys_perf", "plant"): "plant_code",
    ("special_steel_ipt_requirement", "financial_year"): "fy",
    ("special_steel_ipt_requirement", "from_plant"): "from_plant_code",
    ("special_steel_ipt_requirement", "to_plant"): "to_plant_code",
    ("cost_trend_annual", "plant"): "plant_code",
    ("cost_trend_monthly", "plant"): "plant_code",
    ("rake_detention_master", "plant"): "plant_code",
    ("rake_detention_summary", "plant"): "plant_code",
    ("rake_detention_annual", "plant"): "plant_code",
    ("rake_detention_annual", "financial_year"): "fy",
    ("rail_prod_despatch", "financial_year"): "fy",
    ("bf_benchmark_external_bf", "created_at"): "created_at_plain",      # flag
    ("bf_benchmark_external_data", "report_month"): "fy",
    ("bf_benchmark_external_data", "created_at"): "created_at_plain",    # flag
    ("bf_benchmark_external_data", "updated_at"): "updated_at_plain",    # flag
    ("bf_benchmark_sail_meta", "plant"): "plant_code",
    ("bf_benchmark_sail_meta", "unit"): "unit_id",
    ("capital_repair_table", "plant"): "plant_code",
    ("capital_repair_table", "unit_name"): "unit_id",
    ("breakdown_table", "plant"): "plant_code",
    ("breakdown_table", "unit_name"): "unit_id",
    ("major_unit_daily_record", "unit_label"): "unit_id",
    ("cover_photos", "uploaded_by"): "created_by",
    ("cover_photos", "uploaded_at"): "created_at",
    ("allowed_emails", "added_by"): "created_by",
    ("allowed_emails", "added_at"): "created_at",
    ("activity_log", "timestamp"): "created_at",
    ("page_visits", "timestamp"): "created_at",
    ("extraction_log", "logged_at"): "created_at",
}

# The columns of the v2 tables outside the SIMPLE map, each read by one of
# verify's own checks (masters / production / techno / text), written by hand.
# report_text.plant_key / item_key are generated columns (unique-key helpers).
NON_SIMPLE_V2_COLUMNS: Dict[str, set] = {
    "plant": {"plant_code", "plant_name", "plant_kind", "sort_order"},
    "item": {"item_id", "item_name", "uom"},
    "plant_unit": {"unit_id", "plant_code", "unit_code", "unit_type"},
    "production_monthly": {"report_month", "plant_code", "item_id", "actual", "abp_plan", "mou_plan",
                           "has_actual", "has_abp", "has_mou"},
    "techno_upload": {"report_month", "plant_code", "unit_id", "has_month", "has_till_month",
                      "source_file", "created_at", "created_at_iso", "seq"},
    "techno_value": {"report_month", "plant_code", "unit_id", "period", "param_key", "num", "is_int", "raw"},
    "report_text": {"id", "scope", "period", "block_key", "plant_code", "item_id", "seq", "text",
                    "updated_by", "updated_at", "plant_key", "item_key"},
}

# v2 columns of SIMPLE tables that are synthesised or left at their default
# (no v1 source, so outside the map). None today; list any new one here.
SYNTHESISED_V2_COLUMNS: Dict[str, set] = {}

_NUMERIC = {"tinyint", "smallint", "mediumint", "int", "bigint", "decimal", "float", "double"}
_GROUP_COLS = ("report_month", "fy", "plant_code")


class VerifyError(RuntimeError):
    """verify refused to run (a guard)."""


def _key(t):
    return repr(tuple(t))


def _same(a, b) -> bool:
    return type(a) is type(b) and a == b


def _close(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    a, b = float(a), float(b)
    return a == b or abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def _diff(a, b, path="$") -> List[str]:
    """v1 value a vs decoded v2 value b: type, value and key order, deep."""
    if type(a) is not type(b):
        return [f"{path}: type v1 {type(a).__name__} != v2 {type(b).__name__} ({a!r} vs {b!r})"]
    if isinstance(a, dict):
        out = []
        missing = [k for k in a if k not in b]
        extra = [k for k in b if k not in a]
        if missing:
            out.append(f"{path}: keys missing in v2 {missing!r}")
        if extra:
            out.append(f"{path}: keys only in v2 {extra!r}")
        common_a = [k for k in a if k in b]
        common_b = [k for k in b if k in a]
        if common_a != common_b:
            out.append(f"{path}: key order v1 {common_a!r} != v2 {common_b!r}")
        for k in common_a:
            out.extend(_diff(a[k], b[k], f"{path}.{k}"))
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}: list length v1 {len(a)} != v2 {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(_diff(x, y, f"{path}[{i}]"))
        return out
    if a != b or (isinstance(a, float) and math.copysign(1, a) != math.copysign(1, b)):
        return [f"{path}: v1 {a!r} != v2 {b!r}"]
    return []


def _as_dt(value):
    return None if value is None else vc._as_datetime(value)


def map_problems() -> List[str]:
    """migrate's SIMPLE map vs EXPECTED_RENAMES, both directions."""
    out = []
    renames = {}
    for v1t, v2t, spec in mig.SIMPLE:
        for c2, c1, _ in spec:
            if c1 != c2:
                renames[(v1t, c1, c2)] = True
                if EXPECTED_RENAMES.get((v1t, c1)) != c2:
                    out.append(f"map: {v1t}.{c1} -> {v2t}.{c2} is not an expected rename")
    for (v1t, c1), c2 in EXPECTED_RENAMES.items():
        if (v1t, c1, c2) not in renames:
            out.append(f"map: expected rename {v1t}.{c1} -> {c2} is not in migrate's map")
    return out


class _Verifier:
    def __init__(self, s, d):
        self.s, self.d = s, d
        self.problems: List[str] = []
        self.counts: Dict[str, Tuple[int, int]] = {}
        self.fk_checked = 0
        self.json_checked = 0
        self.items: Dict[int, str] = {}
        self.units: Dict[int, Tuple[str, str]] = {}
        self.techno_sums: Dict[tuple, Tuple[float, int]] = {}

    # ── helpers ─────────────────────────────────────────────────────────────
    def add(self, label: str, msgs: List[str]):
        self.problems.extend(msgs[:MAX_PER_CHECK])
        if len(msgs) > MAX_PER_CHECK:
            self.problems.append(f"{label}: ... and {len(msgs) - MAX_PER_CHECK} more")

    @staticmethod
    def _q(cur, sql, params=()):
        cur.execute(sql, params)
        cols = [x[0] for x in cur.description]
        return cols, list(cur.fetchall())

    def _dicts(self, cur, sql, params=()):
        cols, rows = self._q(cur, sql, params)
        return [dict(zip(cols, r)) for r in rows]

    def _count(self, v2t, expected):
        self.d.execute(f"SELECT COUNT(*) FROM `{v2t}`")
        actual = self.d.fetchone()[0]
        self.counts[v2t] = (expected, actual)
        if expected != actual:
            self.problems.append(f"row count {v2t}: v1 {expected} != v2 {actual}")

    def _v1_columns(self, table) -> List[str]:
        self.s.execute(f"SELECT * FROM `{table}` LIMIT 0")
        return [x[0] for x in self.s.description]

    def _coverage(self, table, carried):
        lost = [c for c in self._v1_columns(table)
                if c not in carried and c not in DROPPED_V1_COLUMNS.get(table, set())]
        if lost:
            self.problems.append(f"{table}: v1 columns {lost} are not carried into v2")

    def _item_name(self, item_id):
        return self.items.get(item_id, f"<item_id {item_id} not in item>")

    # ── tables present ──────────────────────────────────────────────────────
    def tables(self):
        self.s.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        v1 = {r[0] for r in self.s.fetchall()}
        unknown = sorted(v1 - mig.HANDLED)
        missing = sorted(mig.HANDLED - v1 - {"data_version"})
        if unknown:
            self.problems.append(f"v1 tables with no v2 mapping: {unknown}")
        if missing:
            self.problems.append(f"v1 tables missing from the source: {missing}")
        self.d.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        v2 = {r[0] for r in self.d.fetchall()}
        want = set(mig.LOAD_ORDER) | {"cal_month", "data_version"}
        if v2 != want:
            self.problems.append(f"v2 tables differ from the v2 model: missing {sorted(want - v2)}, "
                                 f"unexpected {sorted(v2 - want)}")
        self.d.execute("SELECT COUNT(*) FROM cal_month")
        if not self.d.fetchone()[0]:
            self.problems.append("cal_month is empty")

    # ── migrate's map vs the hand-written oracle; v2 column completeness ────
    def mapping(self):
        self.problems.extend(map_problems())

    def columns(self):
        self.d.execute("SELECT table_name, column_name FROM information_schema.columns "
                       "WHERE table_schema = DATABASE()")
        have = defaultdict(set)
        for t, c in self.d.fetchall():
            have[t].add(c)
        covered = {t: set(cols) for t, cols in NON_SIMPLE_V2_COLUMNS.items()}
        for _, v2t, spec in mig.SIMPLE:
            covered[v2t] = {c2 for c2, _, _ in spec} | SYNTHESISED_V2_COLUMNS.get(v2t, set())
        msgs = []
        for t in sorted(covered):
            msgs += [f"v2 column {t}.{c} is not covered by the v1 -> v2 map" for c in sorted(have[t] - covered[t])]
            msgs += [f"v2 column {t}.{c} is mapped but missing from dst" for c in sorted(covered[t] - have[t])]
        self.add("columns", msgs)

    # ── masters ─────────────────────────────────────────────────────────────
    def _distinct(self, cols_sql_list):
        out = set()
        for sql in cols_sql_list:
            self.s.execute(sql)
            out.update(tuple(x.decode("utf-8") for x in r) for r in self.s.fetchall())
        return out

    def masters(self):
        plants = {p for (p,) in self._distinct(
            f"SELECT DISTINCT CAST(`{c}` AS BINARY) FROM `{t}` WHERE `{c}` IS NOT NULL"
            for t, c in mig.PLANT_COLUMNS)}
        items = {i for (i,) in self._distinct(
            f"SELECT DISTINCT CAST(`{c}` AS BINARY) FROM `{t}` WHERE `{c}` IS NOT NULL"
            for t, c in mig.ITEM_COLUMNS)}
        units = self._distinct(
            f"SELECT DISTINCT CAST(`{p}` AS BINARY), CAST(`{u}` AS BINARY) FROM `{t}` WHERE `{u}` IS NOT NULL"
            for t, p, u in mig.UNIT_COLUMNS)

        self.d.execute("SELECT plant_code FROM plant")
        v2_plants = [r[0] for r in self.d.fetchall()]
        self.d.execute("SELECT item_id, item_name FROM item")
        self.items = dict(self.d.fetchall())
        self.d.execute("SELECT unit_id, plant_code, unit_code FROM plant_unit")
        self.units = {r[0]: (r[1], r[2]) for r in self.d.fetchall()}

        for name, want, got in (("plant", plants, v2_plants), ("item", items, list(self.items.values())),
                                ("plant_unit", units, list(self.units.values()))):
            msgs = [f"{name}: {x!r} is in v1 but not in the v2 master" for x in sorted(want - set(got))]
            msgs += [f"{name}: {x!r} is in the v2 master but in no v1 column" for x in sorted(set(got) - want)]
            msgs += [f"{name}: {x!r} appears {n} times" for x, n in Counter(got).items() if n > 1]
            self.add(name, msgs)
            self._count(name, len(want))

    # ── production ──────────────────────────────────────────────────────────
    def production(self):
        rows = self._dicts(self.d, "SELECT * FROM production_monthly")
        union = set()
        canon = []
        decoded = {t: {} for t in vc.PRODUCTION_SOURCES}
        flagged = Counter()
        for r in rows:
            key = (r["report_month"], r["plant_code"], self._item_name(r["item_id"]))
            flags = 0
            for t, (col, flag) in vc.PRODUCTION_SOURCES.items():
                if r[flag]:
                    flags += 1
                    flagged[t] += 1
                    decoded[t][key] = r[col]
                elif r[col] is not None:
                    canon.append(f"production_monthly row {key!r}: {flag}=0 but {col}={r[col]!r}")
            if not flags:
                canon.append(f"production_monthly row {key!r}: no has_* flag set")
        # the item master keeps case variants apart (utf8mb4_0900_bin), but the
        # tables read a name case-insensitively (ai_ci): one actual per
        # (month, plant, item name) must remain.
        self.d.execute(
            "SELECT p.report_month, p.plant_code, MIN(i.item_name), COUNT(*) FROM production_monthly p "
            "JOIN item i ON i.item_id = p.item_id WHERE p.has_actual = 1 "
            "GROUP BY p.report_month, p.plant_code, i.item_name COLLATE utf8mb4_0900_ai_ci "
            "HAVING COUNT(*) > 1")
        canon += [f"production_monthly: {n} has_actual rows for ({m!r}, {p!r}, item {nm!r}) "
                  f"that differ only in letter case or accents" for m, p, nm, n in self.d.fetchall()]
        self.add("production_monthly", canon)
        for t, (col, flag) in vc.PRODUCTION_SOURCES.items():
            self._coverage(t, {"report_month", "plant_name", "item_name", "month_actual"})
            src = {}
            self.s.execute(f"SELECT report_month, plant_name, item_name, month_actual FROM `{t}`")
            v1rows = self.s.fetchall()
            for m, p, i, v in v1rows:
                src[(m, p, i)] = v
            union |= set(src)
            got = decoded[t]
            msgs = []
            if len(src) != len(v1rows):
                msgs.append(f"{t}: {len(v1rows) - len(src)} duplicate v1 key(s) collapsed")
            if len(got) != flagged[t]:
                msgs.append(f"{t}: {flagged[t] - len(got)} duplicate v2 key(s) collapsed")
            msgs += [f"{t}: row {k!r} missing in v2" for k in src if k not in got]
            msgs += [f"{t}: row {k!r} in v2 has no v1 row" for k in got if k not in src]
            msgs += [f"{t}: row {k!r} month_actual: v1 {src[k]!r} != v2 {got[k]!r}"
                     for k in src if k in got and not _same(src[k], got[k])]
            self.add(t, msgs)
        self._count("production_monthly", len(union))

    # ── techno ──────────────────────────────────────────────────────────────
    def techno(self):
        self._coverage("techno_data", {"id", "plant", "report_month", "unit", "techno_json", "source_file",
                                       "created_at"})
        uploads = {}
        msgs = []
        up_rows = self._dicts(self.d, "SELECT * FROM techno_upload")
        for r in up_rows:
            plant, code = self.units.get(r["unit_id"], (None, f"<unit_id {r['unit_id']} not in plant_unit>"))
            if plant is not None and plant != r["plant_code"]:
                msgs.append(f"techno_upload ({r['plant_code']!r}, {r['report_month']!r}): unit_id "
                            f"{r['unit_id']} belongs to plant {plant!r}")
            uploads[(r["plant_code"], r["report_month"], code)] = r
        if len(uploads) != len(up_rows):
            msgs.append(f"techno_upload: {len(up_rows) - len(uploads)} duplicate (plant, month, unit name) "
                        "key(s) collapsed")
        # plant_unit.unit_code is binary, but v1's uq_techno (plant, report_month,
        # unit) was ai_ci: one (month, plant) can never hold two ai_ci-equal units
        self.d.execute("SELECT u.report_month, u.plant_code, "
                       "GROUP_CONCAT(pu.unit_code ORDER BY pu.unit_code SEPARATOR ' | ') "
                       "FROM techno_upload u JOIN plant_unit pu ON pu.unit_id = u.unit_id "
                       "GROUP BY u.report_month, u.plant_code, pu.unit_code COLLATE utf8mb4_0900_ai_ci "
                       "HAVING COUNT(*) > 1")
        msgs += [f"techno_upload ({p!r}, {m!r}): ai_ci-duplicate units {units}"
                 for m, p, units in self.d.fetchall()]
        id_key = {(r["report_month"], r["plant_code"], r["unit_id"]): k for k, r in uploads.items()}

        leaves = defaultdict(list)
        self.d.execute("SELECT report_month, plant_code, unit_id, period, param_key, num, is_int, raw "
                       "FROM techno_value ORDER BY report_month, plant_code, unit_id, "
                       f"{vc.TECHNO_LEAF_ORDER_BY}")
        for m, p, u, period, pk, num, is_int, raw in self.d.fetchall():
            key = id_key.get((m, p, u))
            if key is None:
                key = (p, m, self.units.get(u, (None, f"<unit_id {u}>"))[1])
                msgs.append(f"techno_value {key!r} {period}.{pk!r}: no techno_upload row")
                continue
            if raw is not None and (num is not None or is_int):
                msgs.append(f"techno_value {key!r} {period}.{pk!r}: raw leaf with num {num!r}, is_int {is_int}")
            elif raw is None and num is None:
                msgs.append(f"techno_value {key!r} {period}.{pk!r}: neither num nor raw")
            elif raw is None and is_int and num != int(num):
                msgs.append(f"techno_value {key!r} {period}.{pk!r}: is_int=1 but num {num!r}")
            leaves[key].append((period, pk, num, is_int, raw))

        n_leaves = 0
        sums: Dict[tuple, List] = defaultdict(lambda: [[], 0])
        self.s.execute("SELECT plant, report_month, unit, techno_json, source_file, created_at, id "
                       "FROM techno_data")
        seen = set()
        v1_techno = self.s.fetchall()
        for plant, month, unit, blob, source_file, created_at, v1_id in v1_techno:
            key = (plant, month, unit)
            if key in seen:
                msgs.append(f"techno_data {key!r}: duplicate v1 key")
            seen.add(key)
            want = json.loads(blob)
            for period in vc.TECHNO_PERIODS:
                for v in (want.get(period) or {}).values() if isinstance(want.get(period), dict) else ():
                    n_leaves += 1
                    try:
                        num = vc.encode_leaf(v)[0]
                    except vc.CodecError:
                        num = None
                    if num is not None:
                        sums[(month, plant)][0].append(num)
                        sums[(month, plant)][1] += 1
            up = uploads.get(key)
            if up is None:
                msgs.append(f"techno_data {key!r}: missing in v2")
                continue
            rows = leaves.get(key, [])
            if rows != sorted(rows, key=lambda x: vc.techno_key_order(x[0], x[1])):
                msgs.append(f"techno_data {key!r}: SQL leaf order ({vc.TECHNO_LEAF_ORDER_BY}) "
                            "differs from the codec order")
            try:
                got = vc.decode_techno(up["has_month"], up["has_till_month"], rows)
            except vc.CodecError as e:
                msgs.append(f"techno_data {key!r}: cannot decode: {e}")
                continue
            msgs.extend(f"techno_data {key!r}: {m}" for m in _diff(want, got))
            if not _same(v1_id, up["seq"]):
                msgs.append(f"techno_data {key!r}: id v1 {v1_id!r} != v2 seq {up['seq']!r}")
            if not _same(source_file, up["source_file"]):
                msgs.append(f"techno_data {key!r}: source_file v1 {source_file!r} != v2 {up['source_file']!r}")
            try:
                rendered = vc.render_ts_flagged("techno_upload.created_at", up["created_at"],
                                                up["created_at_iso"])
                exact = vc.parse_ts_flagged("techno_upload.created_at", created_at)
            except (vc.CodecError, ValueError) as e:
                msgs.append(f"techno_data {key!r}: created_at: {e}")
            else:
                if rendered != created_at:
                    msgs.append(f"techno_data {key!r}: created_at v1 {created_at!r} != v2 {rendered!r}")
                elif (_as_dt(up["created_at"]), up["created_at_iso"]) != exact:
                    msgs.append(f"techno_data {key!r}: created_at stored {up['created_at']!r} "
                                f"(flag {up['created_at_iso']}) != parsed v1 {exact!r}")
        msgs += [f"techno_upload {k!r} in v2 has no v1 techno_data row" for k in uploads if k not in seen]
        self.add("techno", msgs)
        self.techno_sums = {k: (math.fsum(v[0]), v[1]) for k, v in sums.items()}
        self._count("techno_upload", len(v1_techno))
        self._count("techno_value", n_leaves)

    # ── narrative text ──────────────────────────────────────────────────────
    def text(self):
        expected_total = 0
        for scope, spec in vc.TEXT_SCOPES.items():
            table = spec["table"]
            v1cols = vc.v1_text_columns(scope)
            self._coverage(table, set(v1cols))
            src = self._dicts(self.s, f"SELECT {', '.join(f'`{c}`' for c in v1cols)} FROM `{table}`")
            v2rows = self._dicts(self.d, "SELECT period, block_key, plant_code, item_id, seq, text, updated_by, "
                                         "updated_at FROM report_text WHERE scope = %s", (scope,))
            for r in v2rows:
                r["item_name"] = None if r["item_id"] is None else self._item_name(r.pop("item_id"))
                r.pop("item_id", None)
            msgs = []

            # (a) decode v2 -> v1 rows, keyed by the v1 primary key
            pk = vc.text_v1_key(scope)
            try:
                got = vc.decode_text_rows(scope, v2rows)
            except (vc.CodecError, ValueError, KeyError) as e:
                msgs.append(f"{table}: cannot decode report_text scope {scope}: {e}")
                got = []
            want_by = defaultdict(list)
            for r in src:
                want_by[tuple(r[c] for c in pk)].append(r)
            got_by = defaultdict(list)
            for r in got:
                got_by[tuple(r[c] for c in pk)].append(r)
            for k, ws in want_by.items():
                gs = got_by.get(k, [])
                if not gs:
                    msgs.append(f"{table}: row {k!r} missing in v2")
                elif len(ws) == 1 and len(gs) == 1:
                    for c in v1cols:
                        if not _same(ws[0][c], gs[0][c]):
                            msgs.append(f"{table}: row {k!r} {c}: v1 {ws[0][c]!r} != v2 {gs[0][c]!r}")
                elif Counter(map(_key, (w.values() for w in ws))) != Counter(map(_key, (g.values() for g in gs))):
                    msgs.append(f"{table}: rows {k!r} differ: v1 {ws!r} != v2 {gs!r}")
            msgs += [f"{table}: row {k!r} in v2 has no v1 row" for k in got_by if k not in want_by]

            # (b) the stored rows == the encoding of the v1 rows (fields the
            #     decoder does not read: block_key / seq / plant / item of
            #     constant scopes, the stamp of every row of a wide period)
            fields = ("period", "block_key", "plant_code", "item_name", "seq", "text", "updated_by", "updated_at")
            want_enc = Counter()
            for r in src:
                try:
                    for e in vc.encode_text_row(scope, r):
                        want_enc[tuple(e[f] for f in fields)] += 1
                except (vc.CodecError, ValueError) as e:
                    msgs.append(f"{table}: v1 row {r!r} cannot be encoded: {e}")
            got_enc = Counter()
            for r in v2rows:
                got_enc[tuple(_as_dt(r[f]) if f == "updated_at" else r[f] for f in fields)] += 1
            for t in sorted((want_enc - got_enc), key=repr):
                msgs.append(f"report_text {scope}: expected row {dict(zip(fields, t))!r} missing from v2")
            for t in sorted((got_enc - want_enc), key=repr):
                msgs.append(f"report_text {scope}: v2 row {dict(zip(fields, t))!r} is not the encoding of a v1 row")
            expected_total += sum(want_enc.values())
            self.add(f"report_text {scope}", msgs)
        self._count("report_text", expected_total)

    # ── every other table ───────────────────────────────────────────────────
    def _primary_keys(self):
        self.d.execute("SELECT table_name, column_name FROM information_schema.statistics "
                       "WHERE table_schema = DATABASE() AND index_name = 'PRIMARY' "
                       "ORDER BY table_name, seq_in_index")
        pks = defaultdict(list)
        for t, c in self.d.fetchall():
            pks[t].append(c)
        return pks

    def simple(self):
        pks = self._primary_keys()
        for v1t, v2t, spec in mig.SIMPLE:
            self._coverage(v1t, {c1 for _, c1, _ in spec})
            v1cols, v1rows = self._q(self.s, f"SELECT * FROM `{v1t}`")
            missing = [c1 for _, c1, _ in spec if c1 not in v1cols]
            if missing:
                self.problems.append(f"{v1t}: v1 columns {missing} not found")
                continue
            v2cols = [c2 for c2, _, _ in spec]
            _, v2rows = self._q(self.d, f"SELECT {', '.join(f'`{c}`' for c in v2cols)} FROM `{v2t}`")
            c2_of_c1 = {c1: c2 for c2, c1, k in spec if k is None or k == "month"}
            flag_col = {k[5:]: c2 for c2, _, k in spec if k and k.startswith("flag:")}
            labels = [c2 if (k and k.startswith("flag:")) else c1 for c2, c1, k in spec]
            i1 = {c: i for i, c in enumerate(v1cols)}
            i2 = {c: i for i, c in enumerate(v2cols)}
            msgs = []

            def v1_side(r):
                out = []
                for c2, c1, kind in spec:
                    v = r[i1[c1]]
                    if kind and kind.startswith("flag:"):
                        try:
                            v = vc.parse_ts_flagged(f"{v2t}.{kind[5:]}", v)[1]
                        except vc.CodecError:
                            v = "<unparseable v1 timestamp>"
                    out.append(v)
                return tuple(out)

            def v2_side(r):
                out = []
                for c2, c1, kind in spec:
                    v = r[i2[c2]]
                    if kind == "ts":
                        v = vc.render_ts(vc.TS_COLUMNS[f"{v2t}.{c2}"][1], v)
                    elif kind == "mixed":
                        v = vc.render_ts_flagged(f"{v2t}.{c2}", v, r[i2[flag_col[c2]]])
                    elif kind == "date":
                        v = vc.render_date(v)
                    elif kind == "item":
                        v = self._item_name(v)
                    elif kind and kind.startswith("unit:"):
                        if v is not None:
                            plant, code = self.units.get(v, (None, f"<unit_id {v} not in plant_unit>"))
                            row_plant = r[i2[c2_of_c1[kind[5:]]]]
                            if plant is not None and plant != row_plant:
                                msgs.append(f"{v2t}: unit_id {v} belongs to plant {plant!r}, row plant "
                                            f"{row_plant!r}")
                            v = code
                    out.append(v)
                return tuple(out)

            def exact_ts(w, raw):
                """Stored DATETIMEs equal the parsed v1 values (the render
                can hide sub-format differences, e.g. a fraction in a
                seconds-only column)."""
                out = []
                for (c2, c1, kind), v1v, v2v in zip(spec, w, raw):
                    try:
                        if kind == "ts":
                            want = vc.parse_ts(vc.TS_COLUMNS[f"{v2t}.{c2}"][1], v1v)
                        elif kind == "mixed":
                            want = vc.parse_ts_flagged(f"{v2t}.{c2}", v1v)[0]
                        elif kind == "date":
                            want = vc.parse_date(v1v)
                            v2v = None if v2v is None else vc._dt.date.fromisoformat(str(v2v)[:10])
                            if want != v2v:
                                out.append((c1, want, v2v))
                            continue
                        else:
                            continue
                    except (vc.CodecError, ValueError) as e:
                        out.append((c1, f"<v1 {v1v!r} cannot be parsed: {e}>", v2v))
                        continue
                    if want != _as_dt(v2v):
                        out.append((c1, want, v2v))
                return out

            pk = pks.get(v2t, [])
            kidx = [v2cols.index(c) for c in pk] if pk and all(c in v2cols for c in pk) else None

            def keyof(t):
                return tuple(t[i] for i in kidx) if kidx is not None else t

            want_by = defaultdict(list)
            for r in v1rows:
                w = v1_side(r)
                want_by[keyof(w)].append(w)
            got_by = defaultdict(list)
            for r in v2rows:
                try:
                    g = v2_side(r)
                except (vc.CodecError, ValueError) as e:
                    msgs.append(f"{v1t} -> {v2t}: v2 row {r!r} cannot be decoded: {e}")
                    continue
                got_by[keyof(g)].append((g, r))
            name = f"{v1t} -> {v2t}"
            for k, ws in want_by.items():
                gs = got_by.get(k, [])
                if not gs:
                    msgs.append(f"{name}: row {k!r} missing in v2")
                elif len(ws) == 1 and len(gs) == 1:
                    w, (g, raw) = ws[0], gs[0]
                    for lab, a, b in zip(labels, w, g):
                        if not _same(a, b):
                            msgs.append(f"{name}: row {k!r} {lab}: v1 {a!r} != v2 {b!r}")
                    for lab, want, stored in exact_ts(w, raw):
                        if isinstance(want, str):
                            msgs.append(f"{name}: row {k!r} {lab}: unparseable v1 timestamp {want[1:-1]}")
                        else:
                            msgs.append(f"{name}: row {k!r} {lab}: stored {stored!r} != parsed v1 {want!r}")
                elif Counter(map(_key, ws)) != Counter(_key(g) for g, _ in gs):
                    msgs.append(f"{name}: rows {k!r} differ: v1 {ws!r} != v2 {[g for g, _ in gs]!r}")
            msgs += [f"{name}: row {k!r} in v2 has no v1 row" for k in got_by if k not in want_by]
            self.add(name, msgs)
            self._count(v2t, len(v1rows))

    def data_version(self):
        self.s.execute("SHOW TABLES LIKE 'data_version'")
        want = 1
        if self.s.fetchone():
            self.s.execute("SELECT n FROM data_version")
            r = self.s.fetchone()
            want = r[0] if r else 1
        self.d.execute("SELECT id, n FROM data_version")
        got = self.d.fetchall()
        if [tuple(r) for r in got] != [(1, want)]:
            self.problems.append(f"data_version: v1 n={want} != v2 {[tuple(r) for r in got]!r}")

    # ── aggregates ──────────────────────────────────────────────────────────
    def _sum_compare(self, label, v1sql, v2sql, ngroup):
        """Both queries: ngroup group columns then the aggregates, in the
        same order."""
        _, a = self._q(self.s, v1sql)
        _, b = self._q(self.d, v2sql)
        want = {tuple(r[:ngroup]): r[ngroup:] for r in a}
        got = {tuple(r[:ngroup]): r[ngroup:] for r in b}
        msgs = []
        for k in sorted(set(want) | set(got), key=repr):
            w, g = want.get(k), got.get(k)
            if w is None or g is None:
                msgs.append(f"SUM {label} at {k!r}: group only in {'v2' if w is None else 'v1'}")
                continue
            for i, (x, y) in enumerate(zip(w, g)):
                if not _close(x, y):
                    msgs.append(f"SUM {label} at {k!r} [{i}]: v1 {x!r} != v2 {y!r}")
        self.add(f"SUM {label}", msgs)

    def sums(self):
        # production: per source table, per (month, plant)
        for t, (col, flag) in vc.PRODUCTION_SOURCES.items():
            self._sum_compare(
                f"production_monthly.{col} vs {t}.month_actual",
                f"SELECT report_month, plant_name, SUM(month_actual), COUNT(*), COUNT(month_actual) FROM `{t}` "
                "GROUP BY report_month, plant_name",
                f"SELECT report_month, plant_code, SUM({col}), SUM({flag}), COUNT({col}) FROM production_monthly "
                f"WHERE {flag} = 1 GROUP BY report_month, plant_code", 2)
        # techno: numeric leaves per (month, plant)
        self.d.execute("SELECT report_month, plant_code, SUM(num), COUNT(num) FROM techno_value "
                       "GROUP BY report_month, plant_code")
        got = {(m, p): (s, n) for m, p, s, n in self.d.fetchall()}
        msgs = []
        for k in sorted(set(got) | set(self.techno_sums), key=repr):
            w, g = self.techno_sums.get(k, (None, 0)), got.get(k, (None, 0))
            if w[1] != g[1] or not _close(w[0] if w[1] else None, g[0] if g[1] else None):
                msgs.append(f"SUM techno_value.num at {k!r}: v1 {w!r} != v2 {g!r}")
        self.add("SUM techno_value", msgs)
        # every other table: each verbatim numeric column, per (month / fy, plant)
        self.d.execute("SELECT table_name, column_name, data_type FROM information_schema.columns "
                       "WHERE table_schema = DATABASE()")
        types = {(t, c): dt.lower() for t, c, dt in self.d.fetchall()}
        for v1t, v2t, spec in mig.SIMPLE:
            group = [(c2, c1) for c2, c1, k in spec if c2 in _GROUP_COLS and k in (None, "month")]
            nums = [(c2, c1) for c2, c1, k in spec if k is None and c2 not in _GROUP_COLS
                    and types.get((v2t, c2)) in _NUMERIC]
            if not nums:
                continue
            g1 = ", ".join(f"`{c1}`" for _, c1 in group)
            g2 = ", ".join(f"`{c2}`" for c2, _ in group)
            a1 = ", ".join(f"SUM(`{c1}`), COUNT(`{c1}`)" for _, c1 in nums)
            a2 = ", ".join(f"SUM(`{c2}`), COUNT(`{c2}`)" for c2, _ in nums)
            self._sum_compare(
                f"{v2t}({', '.join(c for c, _ in nums)})",
                f"SELECT {g1 + ', ' if g1 else ''}{a1} FROM `{v1t}`" + (f" GROUP BY {g1}" if g1 else ""),
                f"SELECT {g2 + ', ' if g2 else ''}{a2} FROM `{v2t}`" + (f" GROUP BY {g2}" if g2 else ""),
                len(group))

    def json_valid(self):
        self.d.execute("SELECT table_name, column_name FROM information_schema.columns "
                       "WHERE table_schema = DATABASE() AND data_type = 'json' ORDER BY table_name, column_name")
        cols = [tuple(r) for r in self.d.fetchall()] + [("page_config", "page_data")]
        for t, c in cols:
            self.d.execute(f"SELECT COUNT(*) FROM `{t}` WHERE `{c}` IS NOT NULL AND NOT JSON_VALID(`{c}`)")
            n = self.d.fetchone()[0]
            self.json_checked += 1
            if n:
                self.problems.append(f"JSON_VALID {t}.{c}: {n} invalid value(s)")

    def fk_orphans(self):
        self.d.execute("SELECT constraint_name, table_name, column_name, referenced_table_name, "
                       "referenced_column_name FROM information_schema.key_column_usage "
                       "WHERE table_schema = DATABASE() AND referenced_table_name IS NOT NULL "
                       "ORDER BY table_name, constraint_name, ordinal_position")
        fks: Dict[tuple, Dict[str, Any]] = {}
        for name, t, c, rt, rc in self.d.fetchall():
            fk = fks.setdefault((t, name), {"parent": rt, "cols": [], "refs": []})
            fk["cols"].append(c)
            fk["refs"].append(rc)
        declared = set(re.findall(r"CONSTRAINT\s+(\w+)\s+FOREIGN KEY", SCHEMA_V2.read_text(encoding="utf-8")))
        present = {name for _, name in fks}
        if declared - present:
            self.problems.append(f"FKs of schema_v2.sql not declared in dst: {sorted(declared - present)}")
        for (t, name), fk in sorted(fks.items()):
            notnull = " AND ".join(f"c.`{c}` IS NOT NULL" for c in fk["cols"])
            match = " AND ".join(f"p.`{r}` = c.`{c}`" for c, r in zip(fk["cols"], fk["refs"]))
            self.d.execute(f"SELECT COUNT(*) FROM `{t}` c WHERE {notnull} AND NOT EXISTS "
                           f"(SELECT 1 FROM `{fk['parent']}` p WHERE {match})")
            n = self.d.fetchone()[0]
            self.fk_checked += 1
            if n:
                self.problems.append(f"FK {name}: {n} orphan row(s) in {t}({', '.join(fk['cols'])}) -> "
                                     f"{fk['parent']}({', '.join(fk['refs'])})")


def _open_read_only(db, cfg):
    conn = mig.connect(db, cfg)
    cur = conn.cursor()
    cur.execute("SET SESSION TRANSACTION READ ONLY")
    cur.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
    return conn, cur


def _has_table(cur, name):
    cur.execute("SHOW TABLES LIKE %s", (name,))
    return cur.fetchone() is not None


def verify(src_db: str, dst_db: str, *, src_cfg: Optional[dict] = None, dst_cfg: Optional[dict] = None,
           report: Optional[dict] = None) -> List[str]:
    """Problems found comparing v2 `dst_db` with v1 `src_db` (empty = OK).
    Read only on both sides. `report`, if given, receives counts
    {v2 table: (expected from v1, actual)}, timings and check totals."""
    if not src_db or not dst_db or src_db.lower() == dst_db.lower():
        raise VerifyError(f"src and dst are the same database ({src_db!r}, {dst_db!r})")
    src, s = _open_read_only(src_db, src_cfg)
    try:
        dst, d = _open_read_only(dst_db, dst_cfg)
        try:
            if not _has_table(d, "techno_value") or _has_table(d, "techno_data"):
                raise VerifyError(f"{dst_db!r} is not a v2 schema")
            if not _has_table(s, "techno_data") or _has_table(s, "techno_value"):
                raise VerifyError(f"{src_db!r} is not a v1 schema")
            v = _Verifier(s, d)
            timings = {}
            for step in ("tables", "mapping", "columns", "masters", "production", "techno", "text", "simple", "data_version",
                         "sums", "json_valid", "fk_orphans"):
                t0 = time.perf_counter()
                getattr(v, step)()
                timings[step] = round(time.perf_counter() - t0, 2)
            if report is not None:
                report.update(counts=v.counts, timings=timings, fk_checked=v.fk_checked,
                              json_checked=v.json_checked)
            return v.problems
        finally:
            dst.rollback()
            dst.close()
    finally:
        src.rollback()
        src.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", required=True, help="v1 database (read only)")
    ap.add_argument("--dst", required=True, help="v2 database (read only)")
    ap.add_argument("--src-defaults-file", help="mysql option file for the source connection")
    ap.add_argument("--dst-defaults-file", help="mysql option file for the destination connection")
    a = ap.parse_args(argv)
    report: Dict[str, Any] = {}
    t0 = time.perf_counter()
    try:
        problems = verify(a.src, a.dst, src_cfg=mig._cfg_from_args(a.src_defaults_file),
                          dst_cfg=mig._cfg_from_args(a.dst_defaults_file), report=report)
    except VerifyError as e:
        print(f"verify refused: {e}")
        return 1
    took = time.perf_counter() - t0
    for t, (want, got) in sorted(report.get("counts", {}).items()):
        print(f"  {t:34s} v1-expected {want:>7}  v2 {got:>7}{'' if want == got else '  MISMATCH'}")
    print(f"timings (s): {report.get('timings')}")
    print(f"FKs checked: {report.get('fk_checked')}, JSON columns checked: {report.get('json_checked')}")
    for p in problems:
        print(f"PROBLEM: {p}")
    print(f"verify {a.src} -> {a.dst}: {len(problems)} problem(s) in {took:.1f} s")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
