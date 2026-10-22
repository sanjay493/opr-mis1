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
