"""
Engine abstraction: one connect() that returns either a plain sqlite3
connection or a MySQL connection wrapped to speak the sqlite3 dialect.

Selected by DB_ENGINE in backend/.env ('sqlite' default, or 'mysql').
Call sites keep their existing shape — qmark placeholders, sqlite upsert
syntax, conn.row_factory = sqlite3.Row, except sqlite3.OperationalError —
and the wrapper translates at execute time:

  ?                                  -> %s   (all literal % escaped first)
  ON CONFLICT(..) DO UPDATE SET      -> AS excluded ON DUPLICATE KEY UPDATE
                                        (MySQL 8.0.19+ row alias, so existing
                                        `excluded.col` references work as-is)
  INSERT OR REPLACE / OR IGNORE      -> REPLACE / INSERT IGNORE
  pymysql Programming/OperationalErr -> sqlite3.OperationalError (5 call
                                        sites catch it for missing tables)
  DATETIME/DATE/TIMESTAMP results    -> ISO strings (sqlite semantics)

The two PRAGMA table_info sites and init_db's CREATE TABLEs are handled in
db.py (skipped under MySQL — schema is owned by scripts/mysql_schema.sql).
"""
import os
import re
import sqlite3

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").strip().lower()

_MYSQL_CFG = {
    "host":     os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port":     int(os.environ.get("MYSQL_PORT", "3306")),
    "database": os.environ.get("MYSQL_DB", "mis_reports"),
    "user":     os.environ.get("MYSQL_USER", "mis_app"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
}


# ── SQL translation (sqlite dialect -> MySQL), cached per statement ─────────

_UPSERT_RE = re.compile(r"ON\s+CONFLICT\s*\([^)]*\)\s*DO\s+UPDATE\s+SET", re.I)
_OR_REPLACE_RE = re.compile(r"\bINSERT\s+OR\s+REPLACE\b", re.I)
_OR_IGNORE_RE = re.compile(r"\bINSERT\s+OR\s+IGNORE\b", re.I)
# sqlite GLOB with a literal pattern -> MySQL REGEXP. Charset classes carry
# over verbatim; * -> .*, ? (already %s after qmark translation) -> .
_GLOB_RE = re.compile(r"\bGLOB\s+'([^']*)'", re.I)


def _glob_to_regexp(m):
    pat = m.group(1).replace("*", ".*").replace("%s", ".")
    return f"REGEXP '^{pat}$'"

_translate_cache = {}


def translate_sql(sql: str) -> str:
    out = _translate_cache.get(sql)
    if out is not None:
        return out
    # Literal % first (e.g. LIKE '%SMS%'), THEN qmark -> %s. Safe because the
    # source dialect is qmark-only: any % in the original SQL is literal.
    t = sql.replace("%", "%%").replace("?", "%s")
    t = _UPSERT_RE.sub("AS excluded ON DUPLICATE KEY UPDATE", t)
    t = _OR_REPLACE_RE.sub("REPLACE", t)
    t = _OR_IGNORE_RE.sub("INSERT IGNORE", t)
    t = _GLOB_RE.sub(_glob_to_regexp, t)
    _translate_cache[sql] = t
    return t


# ── sqlite3.Row-compatible row for MySQL results ────────────────────────────

class Row:
    """Supports row[0], row['col'] (case-insensitive like sqlite3.Row),
    iteration over values, len(), keys(), and dict(row)."""
    __slots__ = ("_keys", "_values", "_lower")

    def __init__(self, keys, values):
        self._keys = keys
        self._values = values
        self._lower = None

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        try:
            return self._values[self._keys.index(key)]
        except ValueError:
            if self._lower is None:
                self._lower = [k.lower() for k in self._keys]
            return self._values[self._lower.index(key.lower())]

    def keys(self):
        return list(self._keys)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"Row({dict(zip(self._keys, self._values))!r})"


# ── MySQL wrappers mimicking the sqlite3 API surface used in this codebase ──

def _wrap_error(exc):
    import pymysql
    if isinstance(exc, pymysql.err.IntegrityError):
        return sqlite3.IntegrityError(str(exc))
    if isinstance(exc, (pymysql.err.ProgrammingError, pymysql.err.OperationalError)):
        return sqlite3.OperationalError(str(exc))
    return exc


class CursorWrapper:
    def __init__(self, cursor, conn_wrapper):
        self._cur = cursor
        self._conn = conn_wrapper

    # -- execution ----------------------------------------------------------
    def execute(self, sql, params=()):
        try:
            self._cur.execute(translate_sql(sql), tuple(params) or None)
        except Exception as e:  # noqa: BLE001 - re-raise as sqlite3 error
            raise _wrap_error(e) from e
        return self

    def executemany(self, sql, seq_of_params):
        try:
            self._cur.executemany(translate_sql(sql), [tuple(p) for p in seq_of_params])
        except Exception as e:  # noqa: BLE001
            raise _wrap_error(e) from e
        return self

    # -- results ------------------------------------------------------------
    def _wrap(self, row):
        if row is None or self._conn.row_factory is None:
            return row
        keys = [d[0] for d in self._cur.description]
        return Row(keys, tuple(row))

    def fetchone(self):
        return self._wrap(self._cur.fetchone())

    def fetchall(self):
        rows = self._cur.fetchall()
        if self._conn.row_factory is None:
            return list(rows)
        keys = [d[0] for d in self._cur.description] if self._cur.description else []
        return [Row(keys, tuple(r)) for r in rows]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size else self._cur.fetchmany()
        if self._conn.row_factory is None:
            return list(rows)
        keys = [d[0] for d in self._cur.description] if self._cur.description else []
        return [Row(keys, tuple(r)) for r in rows]

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                return
            yield row

    # -- attributes ---------------------------------------------------------
    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def close(self):
        self._cur.close()


class ConnWrapper:
    """PyMySQL connection with the sqlite3.Connection surface this codebase
    uses: cursor(), execute(), commit(), rollback(), close(), row_factory."""

    def __init__(self, conn):
        self._conn = conn
        self.row_factory = None

    def cursor(self):
        return CursorWrapper(self._conn.cursor(), self)

    def execute(self, sql, params=()):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _mysql_connect():
    import pymysql
    from pymysql import converters
    conv = converters.conversions.copy()
    # sqlite returns TEXT for stored timestamps; keep string semantics so
    # callers never see datetime objects where they expect strings.
    for ft in (pymysql.constants.FIELD_TYPE.DATETIME,
               pymysql.constants.FIELD_TYPE.DATE,
               pymysql.constants.FIELD_TYPE.TIMESTAMP):
        conv[ft] = str
    try:
        conn = pymysql.connect(
            host=_MYSQL_CFG["host"], port=_MYSQL_CFG["port"],
            user=_MYSQL_CFG["user"], password=_MYSQL_CFG["password"],
            database=_MYSQL_CFG["database"], charset="utf8mb4",
            conv=conv, autocommit=False,
        )
    except Exception as e:  # noqa: BLE001
        raise _wrap_error(e) from e
    return ConnWrapper(conn)


def connect(db_path):
    """Drop-in for sqlite3.connect(DB_PATH): returns a sqlite3 connection or
    a MySQL wrapper depending on DB_ENGINE. db_path is used only by sqlite."""
    if DB_ENGINE == "mysql":
        return _mysql_connect()
    return sqlite3.connect(db_path)
