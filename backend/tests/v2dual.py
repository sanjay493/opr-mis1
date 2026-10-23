"""Dual-DB equivalence helper for the Task 7 v2 repositories.

    def test_x(dual):                       # fixture in tests/conftest.py
        dual.seed_production([("actual", "2025-04", "BSP", "Hot Metal", 1.5)])
        r1, r2 = dual.both(lambda m: m.value_row(...), v1=repo.production, v2=repo.v2.production)
        assert r1 == r2

The same logical data is seeded into the v1 test schema (mysql_db) and the
v2 test schema (mysql_v2_db). `dual.v1()` / `dual.v2()` point the app's DB
layer (dbengine / repo.conn) at one of them; `dual.both(fn)` runs fn on
each side with that side's module and returns (v1 result, v2 result).
Writes go through the modules under test, then each side reads back with
its own module.

Every test starts from empty data tables on both sides (the v2 side keeps
cal_month and gets the plant master re-seeded).
"""
from contextlib import contextmanager

import dbengine

# The v2 plant master as mis_reports_v2 holds it (plant_name is not read by
# the repositories; it is synthesised NULL for most plants).
PLANTS = [("BSP", "integrated", 1), ("DSP", "integrated", 2), ("RSP", "integrated", 3),
          ("BSL", "integrated", 4), ("ISP", "integrated", 5), ("ASP", "special", 6),
          ("SSP", "special", 7), ("VISL", "special", 8), ("VISP", "special", 9),
          ("CFP", "special", 10), ("SAIL", "aggregate", 11), ("SSPs", "aggregate", 12)]

_KEEP_V2 = {"cal_month"}

_V1_TABLE = {"actual": "production_table", "abp": "production_plan_table", "mou": "mou_plan_table"}
_V2_COLS = {"actual": ("actual", "has_actual"), "abp": ("abp_plan", "has_abp"), "mou": ("mou_plan", "has_mou")}


_AUTO_INC = {}      # schema -> tables with an AUTO_INCREMENT column


def _empty_tables(cur, keep=()):
    """Empty every non-empty base table but `keep`: DELETE (fast on tiny
    tables), or TRUNCATE where an AUTO_INCREMENT counter must restart, so
    new ids come out as they do on the freshly truncated v1 side."""
    cur.execute("SELECT DATABASE()")
    schema = cur.fetchone()[0]
    if schema not in _AUTO_INC:
        cur.execute("SELECT table_name FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND extra LIKE '%%auto_increment%%'")
        _AUTO_INC[schema] = {r[0] for r in cur.fetchall()}
    cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
    tables = [r[0] for r in cur.fetchall() if r[0] not in keep]
    dirty = []
    for t in tables:
        cur.execute(f"SELECT EXISTS(SELECT 1 FROM `{t}`)")
        if cur.fetchone()[0]:
            dirty.append(t)
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in sorted(dirty):
        cur.execute(f"{'TRUNCATE TABLE' if t in _AUTO_INC[schema] else 'DELETE FROM'} `{t}`")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")


class Dual:
    def __init__(self, v1_name, v2_conn):
        self.v1_name = v1_name
        self.v2_conn = v2_conn
        with v2_conn.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            self.v2_name = cur.fetchone()[0]
        assert self.v2_name.startswith("mis_reports_test_"), self.v2_name
        self._reset_v2()

    # -- databases ------------------------------------------------------------
    def _reset_v2(self):
        with self.v2_conn.cursor() as cur:
            _empty_tables(cur, keep=_KEEP_V2)
            cur.executemany("INSERT INTO plant (plant_code, plant_kind, sort_order) VALUES (%s, %s, %s)", PLANTS)
            cur.execute("INSERT INTO data_version (id, n) VALUES (1, 1)")

    def restore(self):
        """Teardown: leave the session-wide v2 schema as schema_v2.sql +
        seed_cal_month.sql built it (data tables empty, the seeded
        1960-04..2040-03 calendar only, data_version (1, 1)), so tests that
        share mysql_v2_db after a dual test (test_schema_v2) see it pristine."""
        with self.v2_conn.cursor() as cur:
            _empty_tables(cur, keep=_KEEP_V2)
            cur.execute("DELETE FROM cal_month WHERE report_month NOT BETWEEN '1960-04' AND '2040-03'")
            cur.execute("INSERT INTO data_version (id, n) VALUES (1, 1)")

    @contextmanager
    def _use(self, name):
        prev = dbengine._MYSQL_CFG["database"]
        dbengine._pool_clear()
        dbengine._MYSQL_CFG["database"] = name
        try:
            yield
        finally:
            dbengine._pool_clear()
            dbengine._MYSQL_CFG["database"] = prev

    def v1(self):
        return self._use(self.v1_name)

    def v2(self):
        return self._use(self.v2_name)

    def both(self, fn, *, v1, v2):
        """(fn(v1 module) on the v1 DB, fn(v2 module) on the v2 DB)."""
        with self.v1():
            r1 = fn(v1)
        with self.v2():
            r2 = fn(v2)
        return r1, r2

    def sql(self, side, sql, params=()):
        """Run raw SQL on one side (test setup / inspection); returns fetchall()."""
        with (self.v1() if side == 1 else self.v2()):
            conn = dbengine.connect()
            try:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall() if cur.description else None
                conn.commit()
                return rows
            finally:
                conn.close()

    def sql_many(self, side, sql, rows):
        """executemany on one side, in one transaction."""
        with (self.v1() if side == 1 else self.v2()):
            conn = dbengine.connect()
            try:
                conn.cursor().executemany(sql, rows)
                conn.commit()
            finally:
                conn.close()

    def data_version(self, side):
        return self.sql(side, "SELECT n FROM data_version WHERE id = 1")[0][0]

    # -- seeding ----------------------------------------------------------------
    def _v2_item(self, cur, name):
        cur.execute("INSERT IGNORE INTO item (item_name) VALUES (%s)", (name,))
        cur.execute("SELECT item_id FROM item WHERE item_name = %s", (name,))
        return cur.fetchone()[0]

    def seed_production(self, rows):
        """rows: (measure, report_month, plant, item, value) -> the v1 table
        of the measure, and the v2 production_monthly row's measure + flag."""
        for measure in _V1_TABLE:
            mine = [r[1:] for r in rows if r[0] == measure]
            if mine:
                self.sql_many(1, f"INSERT INTO {_V1_TABLE[measure]} (report_month, plant_name, item_name, "
                                 "month_actual) VALUES (%s, %s, %s, %s)", mine)
        with self.v2_conn.cursor() as cur:
            for measure, month, plant, item, value in rows:
                col, flag = _V2_COLS[measure]
                item_id = self._v2_item(cur, item)
                cur.execute(f"INSERT INTO production_monthly (report_month, plant_code, item_id, {col}, {flag}) "
                            "VALUES (%s, %s, %s, %s, 1) AS new "
                            f"ON DUPLICATE KEY UPDATE {col} = new.{col}, {flag} = 1",
                            (month, plant, item_id, value))

    def seed_capacity(self, rows):
        """rows: (id, plant, item, effective_month, annual_capacity, reason,
        created_by, created_at_iso, updated_by, updated_at_iso)."""
        self.sql_many(1, "INSERT INTO item_capacity_table (id, plant_name, item_name, effective_month, "
                         "annual_capacity, reason, created_by, created_at, updated_by, updated_at) "
                         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", rows)
        with self.v2_conn.cursor() as cur:
            for r in rows:
                item_id = self._v2_item(cur, r[2])
                cur.execute("INSERT INTO item_capacity (id, plant_code, item_id, effective_month, "
                            "annual_capacity, reason, created_by, created_at, updated_by, updated_at) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (r[0], r[1], item_id) + tuple(r[3:]))


    def _v2_unit(self, cur, plant, unit):
        cur.execute("INSERT IGNORE INTO plant_unit (plant_code, unit_code) VALUES (%s, %s)", (plant, unit))
        cur.execute("SELECT unit_id FROM plant_unit WHERE plant_code = %s AND unit_code = %s", (plant, unit))
        return cur.fetchone()[0]

    def seed_techno(self, rows):
        """rows: (report_month, plant, unit, blob (dict or JSON text),
        source_file, created_at as the v1 string: NOW() form or isoformat()).
        v1: techno_data rows in this order (ids ascending); v2: the
        techno_upload + techno_value rows the migration would load
        (repo.v2codec encode_techno / parse_ts_flagged)."""
        import json
        from repo.v2codec import encode_techno, parse_ts_flagged
        self.sql_many(1, "INSERT INTO techno_data (plant, report_month, unit, techno_json, source_file, created_at) "
                         "VALUES (%s, %s, %s, %s, %s, %s)",
                      [(p, m, u, b if isinstance(b, str) else json.dumps(b), sf, at) for m, p, u, b, sf, at in rows])
        with self.v2_conn.cursor() as cur:
            for m, p, u, b, sf, at in rows:
                unit_id = self._v2_unit(cur, p, u)
                has_m, has_t, leaves = encode_techno(b)
                ts, iso = parse_ts_flagged("techno_upload.created_at", at)
                cur.execute("INSERT INTO techno_upload (report_month, plant_code, unit_id, has_month, has_till_month, "
                            "source_file, created_at, created_at_iso) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (m, p, unit_id, has_m, has_t, sf, ts, iso))
                cur.executemany("INSERT INTO techno_value (report_month, plant_code, unit_id, period, param_key, "
                                "num, is_int, raw) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                                [(m, p, unit_id) + leaf for leaf in leaves])

    def seed_techno_plan(self, rows):
        """rows: (plant, unit, fy, techno_json dict, is_user_supplied,
        calculated_json dict or None, calculation_method dict or None)."""
        import json

        def j(v):
            return None if v is None else json.dumps(v)
        self.sql_many(1, "INSERT INTO techno_plan_fy (plant_name, unit, fy, techno_json, is_user_supplied, "
                         "calculated_json, calculation_method) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                      [(p, u, fy, j(t), us, j(c), j(cm)) for p, u, fy, t, us, c, cm in rows])
        with self.v2_conn.cursor() as cur:
            for p, u, fy, t, us, c, cm in rows:
                cur.execute("INSERT INTO techno_plan_fy (plant_code, unit_id, fy, techno_json, is_user_supplied, "
                            "calculated_json, calculation_method) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (p, self._v2_unit(cur, p, u), fy, j(t), us, j(c), j(cm)))

    def seed_text(self, scope, rows):
        """rows: v1 rows of the scope's table as {column: value} (timestamps
        as the v1 strings). v1: inserted into that table; v2: the
        report_text rows the migration would load (repo.v2codec
        encode_text_row; items by exact name)."""
        from repo.v2codec import TEXT_SCOPES, encode_text_row, v1_text_columns
        cols = v1_text_columns(scope)
        self.sql_many(1, f"INSERT INTO {TEXT_SCOPES[scope]['table']} ({', '.join(cols)}) "
                         f"VALUES ({', '.join(['%s'] * len(cols))})",
                      [tuple(r.get(c) for c in cols) for r in rows])
        with self.v2_conn.cursor() as cur:
            for r in rows:
                for x in encode_text_row(scope, r):
                    item_id = None if x["item_name"] is None else self._v2_item(cur, x["item_name"])
                    cur.execute("INSERT INTO report_text (scope, period, block_key, plant_code, item_id, seq, "
                                "text, updated_by, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                (scope, x["period"], x["block_key"], x["plant_code"], item_id, x["seq"],
                                 x["text"], x["updated_by"], x["updated_at"]))

    def seed_simple(self, v1_table, rows):
        """rows: v1 rows of one SIMPLE table of tools/migrate_v1_to_v2 as
        {v1 column: value} (timestamps / dates as the v1 strings; omitted
        columns take the table default on both sides). v1: inserted as
        given; v2: the row the migration would load (renamed columns,
        DATETIME / DATE parsed by repo.v2codec). Plants the v2 master lacks
        are added ('external'), as a v2 write would add them."""
        from repo import v2codec as vc
        from tools.migrate_v1_to_v2 import SIMPLE
        spec = {v1t: (v2t, cols) for v1t, v2t, cols in SIMPLE}[v1_table]
        v2t, cols = spec
        for r in rows:
            c1 = list(r)
            self.sql(1, f"INSERT INTO {v1_table} ({', '.join(c1)}) VALUES ({', '.join(['%s'] * len(c1))})",
                     tuple(r[c] for c in c1))
        with self.v2_conn.cursor() as cur:
            for r in rows:
                names, vals = [], []
                for c2, c1, kind in cols:
                    if c1 not in r:
                        continue
                    v = r[c1]
                    if kind == "ts":
                        v = vc.parse_ts(vc.TS_COLUMNS[f"{v2t}.{c2}"][1], v)
                    elif kind == "date":
                        v = vc.parse_date(v)
                    elif kind not in (None, "month"):
                        raise NotImplementedError(kind)
                    if c2 in ("plant_code", "from_plant_code", "to_plant_code") and v is not None:
                        cur.execute("INSERT IGNORE INTO plant (plant_code, plant_kind, sort_order) "
                                    "VALUES (%s, 'external', 0)", (v,))
                    if kind == "month" and v is not None:
                        from repo.v2._keys import cal_month_row
                        cur.execute("INSERT IGNORE INTO cal_month (report_month, month_start, fy, fy_month, "
                                    "quarter, half) VALUES (%s, %s, %s, %s, %s, %s)", cal_month_row(v))
                    names.append(c2)
                    vals.append(v)
                cur.execute(f"INSERT INTO {v2t} ({', '.join(names)}) VALUES ({', '.join(['%s'] * len(names))})",
                            vals)

    def stored(self, v1_table, skip=()):
        """(v1 rows, v2 rows) of one SIMPLE table, each a sorted list of
        tuples in v1 column order; v2 values rendered back to the v1 form
        (DATETIME by repo.v2codec's column format, DATE as 'YYYY-MM-DD').
        `skip`: v1 columns left out (e.g. NOW()-written timestamps)."""
        from repo import v2codec as vc
        from tools.migrate_v1_to_v2 import SIMPLE
        v2t, cols = {v1t: (v2t, cols) for v1t, v2t, cols in SIMPLE}[v1_table]
        cols = [c for c in cols if c[1] not in skip]
        r1 = self.sql(1, f"SELECT {', '.join(c1 for _, c1, _ in cols)} FROM {v1_table}")
        r2 = self.sql(2, f"SELECT {', '.join(c2 for c2, _, _ in cols)} FROM {v2t}")

        def back(row):
            out = []
            for (c2, _, kind), v in zip(cols, row):
                if kind == "ts":
                    v = vc.render_ts(vc.TS_COLUMNS[f"{v2t}.{c2}"][1], v)
                elif kind == "date":
                    v = vc.render_date(v)
                out.append(v)
            return tuple(out)
        return sorted((tuple(r) for r in r1), key=repr), sorted((back(r) for r in r2), key=repr)


def canon(v):
    """Order- and type-preserving text of a result (the oracle's canonical form)."""
    from tools import repo_oracle as ro
    return ro.dumps(ro.canonical(v))


def outcome(fn):
    """("ok", canon(result)) or (exception type name, canon(args))."""
    try:
        return ("ok", canon(fn()))
    except Exception as e:      # noqa: BLE001
        return (type(e).__name__, canon(list(e.args)))


def record_activity(monkeypatch):
    """activity_context.record calls as a list of (unit, canon(old), canon(new))."""
    import activity_context
    calls = []
    monkeypatch.setattr(activity_context, "record",
                        lambda unit, old, new: calls.append((unit, canon(old), canon(new))))
    return calls


def run_step(dual, v1, v2, fn, *, reads, tables=(), activity=None, skip=()):
    """fn(module) on each side (v1 module on the v1 DB, v2 on v2): the same
    outcome (result, or exception type and args) and the same activity
    entries; then every read (reads(module) -> {key: value}, compared in
    canonical form) and the stored rows of each v1 table in `tables` agree.
    Returns the outcome."""
    got = []
    for side, mod in ((dual.v1, v1), (dual.v2, v2)):
        if activity is not None:
            activity.clear()
        with side():
            o = outcome(lambda: fn(mod))
        got.append((o, list(activity or ())))
    assert got[0] == got[1], got
    assert_same_reads(dual, v1, v2, reads)
    for t in tables:
        a, b = dual.stored(t, skip=skip)
        assert a == b, (t, a, b)
    return got[0][0]


def assert_same_reads(dual, v1, v2, reads):
    r1, r2 = dual.both(lambda m: {k: canon(v) for k, v in reads(m).items()}, v1=v1, v2=v2)
    assert set(r1) == set(r2)
    diff = [k for k in r1 if r1[k] != r2[k]]
    assert not diff, [(k, r1[k], r2[k]) for k in diff[:5]]
    return r1


def on_cursor(fn, row_factory=None, commit=False):
    """fn(module, cur) on a fresh db.connect() cursor (committed if asked)."""
    def run(mod):
        conn = dbengine.connect()
        conn.row_factory = row_factory
        try:
            out = fn(mod, conn.cursor())
            if commit:
                conn.commit()
            return out
        finally:
            conn.close()
    return run


def as_plain(v):
    """Rows / Row objects / tuples -> plain comparable Python values."""
    if isinstance(v, dbengine.Row):
        return ("Row", tuple(v.keys()), tuple(as_plain(x) for x in v))
    if isinstance(v, (list, tuple)):
        return type(v)(as_plain(x) for x in v)
    if isinstance(v, dict):
        return {k: as_plain(x) for k, x in v.items()}
    return v


def multiset(rows):
    """A result's rows as a sorted list, for reads whose v1 SQL has no ORDER
    BY: their order is whatever access path MySQL picks, which differs
    between the tiny test schemas and the real data (the oracle replay
    proves the order on the real data)."""
    return sorted((as_plain(r) for r in rows), key=repr)
