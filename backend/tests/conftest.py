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


# ── MySQL test database ─────────────────────────────────────────────────────
# Opt-in: only tests that request `mysql_db` touch MySQL. A throwaway schema
# `mis_reports_test_<pid>` is built from tests/fixtures/schema_v1.sql (an exact
# --no-data dump of the live schema) with a dedicated user (MYSQL_TEST_USER /
# MYSQL_TEST_PASSWORD in backend/.env) that is granted rights ONLY on
# `mis_reports\_test\_%`. Nothing here ever connects to `mis_reports` or
# `mis_reports_baseline`.

import os

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

_TEST_DB_PREFIX = "mis_reports_test_"
_SCHEMA_V1 = Path(__file__).resolve().parent / "fixtures" / "schema_v1.sql"


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


@pytest.fixture(scope="session")
def _mysql_test_schema():
    cfg = _test_cfg()
    name = f"{_TEST_DB_PREFIX}{os.getpid()}"
    _assert_test_schema(name)
    conn = _admin_connect(cfg, multi=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
            cur.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4")
            cur.execute(f"USE `{name}`")
            cur.execute(_SCHEMA_V1.read_text(encoding="utf-8"))
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


@pytest.fixture
def mysql_db(_mysql_test_schema, monkeypatch):
    """Empty v1 schema in a throwaway MySQL database, wired into the app's DB
    layer (db.connect() / dbengine / repo.conn) for the duration of the test.
    Returns the schema name."""
    import dbengine

    name = _mysql_test_schema
    cfg = _test_cfg()
    _assert_test_schema(name)

    # dbengine reads these module-level values at connect time; the pool may
    # hold connections opened against another database, so drop them.
    monkeypatch.setenv("MYSQL_DB", name)
    monkeypatch.setattr(dbengine, "DB_ENGINE", "mysql")
    for key, val in (("host", cfg["host"]), ("port", cfg["port"]), ("user", cfg["user"]),
                     ("password", cfg["password"]), ("database", name)):
        monkeypatch.setitem(dbengine._MYSQL_CFG, key, val)
    dbengine._pool_clear()

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
    finally:
        conn.close()

    yield name
    dbengine._pool_clear()
