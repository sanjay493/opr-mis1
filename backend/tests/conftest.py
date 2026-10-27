"""Shared pytest configuration for backend tests.

Makes the backend package importable and adds the --update-goldens flag
used by the golden-file extraction tests to (re)generate expected output.
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


_SAMPLE_ROOTS = [
    Path(p) for p in (
        __import__("os").environ.get("REPORT_FORMAT_DIR"),
        str(BACKEND_DIR.parent / "Report_format"),
        r"G:\My Drive\Report_format",   # the shared Report_format folder (Google Drive)
    ) if p
]


def find_sample(relative):
    """First existing copy of a sample file (path relative to Report_format/)
    across REPORT_FORMAT_DIR, the repo's Report_format/ and the shared
    Google Drive Report_format folder — or None."""
    for root in _SAMPLE_ROOTS:
        candidate = root / relative
        if candidate.exists():
            return candidate
    return None


def pytest_addoption(parser):
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="Regenerate the golden JSON files from current extractor output "
             "instead of comparing against them.",
    )


@pytest.fixture
def update_goldens(request):
    return request.config.getoption("--update-goldens")


# ── MySQL test databases ────────────────────────────────────────────────────
# Opt-in: only tests that request a fixture below touch MySQL. Throwaway
# schemas `mis_reports_test_*` are built with a dedicated user
# (MYSQL_TEST_USER / MYSQL_TEST_PASSWORD in backend/.env) that is granted
# rights ONLY on `mis_reports\_test\_%`. Nothing here ever connects to
# `mis_reports`, `mis_reports_v2` or `mis_reports_baseline`.
#
#   mysql_db      the app's schema (v2: scripts/v2/schema_v2.sql +
#                 seed_cal_month.sql), wired into dbengine / repo.conn,
#                 data tables emptied, plant master seeded. What app tests use.
#   mysql_v2_db   a raw autocommit connection to that same v2 schema
#                 (schema tests, the migration / verify tools' target).
#   mysql_v1_db   the pre-Task-7 v1 schema (tests/fixtures/schema_v1.sql +
#                 data_version / perf-index migrations), wired into the DB
#                 layer. ONLY for the v1 SOURCE of tools/migrate_v1_to_v2 /
#                 verify_v2 and the frozen v1 oracle (tests/_v1_frozen) of
#                 the dual-DB equivalence tests.

import os

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

_TEST_DB_PREFIX = "mis_reports_test_"
_SCHEMA_V1 = Path(__file__).resolve().parent / "fixtures" / "schema_v1.sql"
# Migrations applied on top of schema_v1 (the v1 live schema dump), in order.
V1_MIGRATION_DIR = BACKEND_DIR / "scripts"
_V1_MIGRATIONS = (
    V1_MIGRATION_DIR / "migrate_add_data_version.sql",
    V1_MIGRATION_DIR / "migrate_add_perf_indexes.sql",
)


def _test_cfg():
    user = os.environ.get("MYSQL_TEST_USER")
    password = os.environ.get("MYSQL_TEST_PASSWORD")
    if not user or not password:
        pytest.fail("mysql_db fixture: MYSQL_TEST_USER / MYSQL_TEST_PASSWORD are not set "
                    "in backend/.env (see .env.example)", pytrace=False)
    return {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": user,
        "password": password,
    }


def _admin_connect(cfg, database=None, multi=False):
    import pymysql
    from pymysql.constants import CLIENT
    try:
        return pymysql.connect(
            host=cfg["host"], port=cfg["port"], user=cfg["user"], password=cfg["password"],
            database=database, charset="utf8mb4", autocommit=True, ssl_disabled=True,
            client_flag=CLIENT.MULTI_STATEMENTS if multi else 0,
        )
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"mysql_db fixture: cannot connect to MySQL at {cfg['host']}:{cfg['port']} "
                    f"as {cfg['user']!r}: {e}. Start MySQL and check MYSQL_* in backend/.env.",
                    pytrace=False)


def _assert_test_schema(name):
    assert name and name.startswith(_TEST_DB_PREFIX), (
        f"refusing to touch database {name!r}: tests may only use {_TEST_DB_PREFIX}* schemas")


def _wire_app(monkeypatch, cfg, name):
    """Point dbengine (and so repo.conn) at schema `name` for one test; the
    pool may hold connections opened against another database, so drop them."""
    import dbengine
    monkeypatch.setenv("MYSQL_DB", name)
    for key, val in (("host", cfg["host"]), ("port", cfg["port"]), ("user", cfg["user"]),
                     ("password", cfg["password"]), ("database", name)):
        monkeypatch.setitem(dbengine._MYSQL_CFG, key, val)
    dbengine._pool_clear()


@pytest.fixture(scope="session")
def _mysql_v1_schema():
    cfg = _test_cfg()
    name = f"{_TEST_DB_PREFIX}{os.getpid()}"
    _assert_test_schema(name)
    conn = _admin_connect(cfg, multi=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
            cur.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4")
            cur.execute(f"USE `{name}`")
            for script in (_SCHEMA_V1, *_V1_MIGRATIONS):
                cur.execute(script.read_text(encoding="utf-8"))
                while cur.nextset():
                    pass
    except BaseException:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
        conn.close()
        raise
    conn.close()
    try:
        yield name
    finally:
        _assert_test_schema(name)
        conn = _admin_connect(cfg)
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
        conn.close()


SCHEMA_V2_DIR = BACKEND_DIR / "scripts" / "v2"
SCHEMA_V2_FILES = (SCHEMA_V2_DIR / "schema_v2.sql", SCHEMA_V2_DIR / "seed_cal_month.sql")


def _apply_sql_files(cur, files):
    for script in files:
        cur.execute(script.read_text(encoding="utf-8"))
        while cur.nextset():
            pass


@pytest.fixture(scope="session")
def mysql_v2_db():
    """A throwaway `mis_reports_test_v2_<pid>` schema built ONCE per run from
    scripts/v2/schema_v2.sql + seed_cal_month.sql (the v2 DDL, slow to apply).
    Yields an autocommit pymysql connection to it; dropped at the end. Tests
    that write must isolate themselves (test_schema_v2's `tx` fixture rolls
    every write back). The `mysql_db` fixture uses this same schema and
    leaves it as built after each test."""
    cfg = _test_cfg()
    name = f"{_TEST_DB_PREFIX}v2_{os.getpid()}"
    _assert_test_schema(name)
    conn = _admin_connect(cfg, multi=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
            cur.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
            cur.execute(f"USE `{name}`")
            _apply_sql_files(cur, SCHEMA_V2_FILES)
        yield conn
    finally:
        _assert_test_schema(name)
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
        conn.close()


def _clear_caches():
    import data_version
    data_version.clear_caches()


@pytest.fixture
def mysql_db(mysql_v2_db, monkeypatch):
    """Empty v2 schema in a throwaway MySQL database (the session's
    mysql_v2_db schema), wired into the app's DB layer (dbengine /
    repo.conn) for the duration of the test. Data tables start empty; the
    seeded calendar (cal_month), the plant master as mis_reports_v2 holds it
    (tests/v2dual.PLANTS) and data_version (1, 1) are present. Returns the
    schema name. Afterwards the schema is left as schema_v2.sql built it."""
    from v2dual import reset_v2, restore_v2

    with mysql_v2_db.cursor() as cur:
        cur.execute("SELECT DATABASE()")
        name = cur.fetchone()[0]
        _assert_test_schema(name)
        reset_v2(cur)
    _wire_app(monkeypatch, _test_cfg(), name)
    # the in-process caches keyed on data_version start empty, so no test
    # can see another test's cached pages.
    _clear_caches()

    yield name
    import dbengine
    dbengine._pool_clear()
    with mysql_v2_db.cursor() as cur:
        restore_v2(cur)


@pytest.fixture
def mysql_v1_db(_mysql_v1_schema, monkeypatch):
    """Empty v1 schema (tests/fixtures/schema_v1.sql) in a throwaway MySQL
    database, wired into the app's DB layer for the duration of the test.
    Only the frozen v1 oracle (tests/_v1_frozen) can read or write it; the
    app's repo modules are v2. Returns the schema name."""
    import dbengine

    name = _mysql_v1_schema
    cfg = _test_cfg()
    _assert_test_schema(name)
    _wire_app(monkeypatch, cfg, name)

    conn = _admin_connect(cfg, database=name)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            _assert_test_schema(cur.fetchone()[0])
            cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
            tables = [r[0] for r in cur.fetchall()]
            # TRUNCATE is a slow DDL (~1s/table here), so only truncate tables
            # that hold rows or have advanced an AUTO_INCREMENT counter.
            cur.execute("SET SESSION information_schema_stats_expiry = 0")
            cur.execute("SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = DATABASE() AND auto_increment > 1")
            dirty = {r[0] for r in cur.fetchall()}
            for t in tables:
                if t in dirty:
                    continue
                cur.execute(f"SELECT EXISTS(SELECT 1 FROM `{t}`)")
                if cur.fetchone()[0]:
                    dirty.add(t)
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for t in sorted(dirty):
                cur.execute(f"TRUNCATE TABLE `{t}`")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            if "data_version" in tables:
                cur.execute("INSERT IGNORE INTO data_version (id, n) VALUES (1, 1)")
    finally:
        conn.close()
    _clear_caches()

    yield name
    dbengine._pool_clear()


@pytest.fixture
def dual(mysql_v1_db, mysql_v2_db):
    """tests/v2dual.Dual: the v1 test schema (mysql_v1_db, the frozen v1
    oracle's side) and the v2 test schema (mysql_v2_db, the app's side),
    both emptied, for the v1-vs-v2 repository equivalence tests."""
    from v2dual import Dual
    d = Dual(mysql_v1_db, mysql_v2_db)
    yield d
    d.restore()        # the v2 schema is session-wide: leave it as built


@pytest.fixture
def v2seed(mysql_db, mysql_v2_db):
    """tests/v2dual.V2Seed on the app's (mysql_db) v2 schema: seed v1-shaped
    rows as the migration would load them, for tests ported from v1 seeding."""
    from v2dual import V2Seed
    return V2Seed(mysql_v2_db)


# ── tests that read the live database's data ────────────────────────────────
# A few tests read real data (the rake detention Wagon Types registry and
# history, the Sep'26 Secretary Review reference deck). They read
# MYSQL_LIVE_V2_DB when set (a copy), else the live v2 database named by
# MYSQL_DB, else mis_reports_v2. The rehearsal copy they used before the
# cut-over was dropped on 2026-10-28. Read-only use.

def live_v2_db_name():
    override = os.environ.get("MYSQL_LIVE_V2_DB")
    if override:
        return override
    name = os.environ.get("MYSQL_DB", "")
    if name.lower().startswith("mis_reports_v2"):
        return name
    return "mis_reports_v2"


from contextlib import contextmanager  # noqa: E402


@contextmanager
def use_live_v2_db():
    import dbengine
    prev = dbengine._MYSQL_CFG["database"]
    dbengine._pool_clear()
    dbengine._MYSQL_CFG["database"] = live_v2_db_name()
    try:
        yield
    finally:
        dbengine._pool_clear()
        dbengine._MYSQL_CFG["database"] = prev


@pytest.fixture(scope="module")
def live_db_module():
    """Wire the DB layer to the live v2 data (see live_v2_db_name) for a
    whole test module; request it autouse from the module."""
    with use_live_v2_db():
        yield live_v2_db_name()
