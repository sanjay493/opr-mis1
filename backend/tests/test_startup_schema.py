"""Startup schema guard: the app refuses to start on a v1 database."""
import inspect

import pytest
from fastapi.testclient import TestClient

from repo import schema as rsch


def test_v2_database_passes(mysql_db):
    rsch.require_v2_at_startup()           # no exception


def test_v1_database_is_refused(mysql_v1_db):
    with pytest.raises(rsch.SchemaVersionError) as e:
        rsch.require_v2_at_startup()
    msg = str(e.value)
    assert "Refusing to start" in msg and mysql_v1_db in msg
    assert "techno_value missing" in msg and "techno_data present" in msg


def test_app_lifespan_refuses_v1(mysql_v1_db):
    import main
    with pytest.raises(rsch.SchemaVersionError):
        with TestClient(main.app):
            pass


def test_app_lifespan_starts_on_v2(mysql_db):
    import main
    with TestClient(main.app):
        pass


def test_default_database_is_v2():
    import dbengine
    assert 'os.environ.get("MYSQL_DB", "mis_reports_v2")' in inspect.getsource(dbengine)
