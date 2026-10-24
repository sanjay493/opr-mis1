"""Which schema generation a database is, by its tables.

    schema_state(cur)      -> (has_v2, has_v1)
    assert_v2_schema(cur)  raises SchemaVersionError unless v2 and not v1

v2 has `techno_value` and no `techno_data`; the old v1 schema has the
reverse. Used by the app's startup check (main.py) and by
tools/migrate_v1_to_v2 before it writes anything. `cur` is any cursor with
execute()/fetchone() (a PyMySQL cursor or repo.conn.Cursor).
"""


class SchemaVersionError(RuntimeError):
    pass


def _has_table(cur, name) -> bool:
    cur.execute("SHOW TABLES LIKE %s", (name,))
    return cur.fetchone() is not None


def schema_state(cur):
    """(has techno_value, has techno_data) in the current database."""
    return _has_table(cur, "techno_value"), _has_table(cur, "techno_data")


def v2_problem(cur):
    """None when the current database is a v2 schema, else a short reason."""
    has_v2, has_v1 = schema_state(cur)
    if has_v2 and not has_v1:
        return None
    return (f"not a v2 schema (techno_value {'present' if has_v2 else 'missing'}, "
            f"techno_data {'present' if has_v1 else 'absent'})")


def assert_v2_schema(cur, db_name=None):
    problem = v2_problem(cur)
    if problem:
        raise SchemaVersionError(f"database {db_name!r}: {problem}" if db_name else problem)


def require_v2_at_startup():
    """App startup guard: refuse to run on a v1 (or empty) database. A database
    that cannot be reached is only logged, as before; the first request then
    reports it."""
    import logging

    import dbengine
    from repo import conn as rc

    name = dbengine._MYSQL_CFG.get("database")
    try:
        with rc.cursor() as cur:
            problem = v2_problem(cur)
    except dbengine.OperationalError:
        logging.getLogger(__name__).exception("startup schema check: cannot reach database %r", name)
        return
    if problem:
        raise SchemaVersionError(
            f"Refusing to start: database {name!r} is {problem}. This code needs the v2 schema "
            f"(mis_reports_v2). Check MYSQL_DB in backend/.env; see docs/DB_V2_CUTOVER.md.")
