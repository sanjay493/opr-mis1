"""Ruling R4: no SQL outside backend/repo/.

Scans the app's Python sources (backend/*.py, backend/excel_extractors/**,
backend/techno_project/**; not repo/, tests/, scripts/, tools/, venv or
__pycache__) for SQL in *string constants* -- comments never reach the AST,
and docstrings (a bare string statement) are skipped, so prose does not
trigger it. Each string constant (adjacent literals are already one
constant; an f-string's literal parts are joined with a placeholder for
each {...}; a `+` chain with a string part is joined the same way) is
matched against

    \\b(SELECT|INSERT|UPDATE|DELETE)\\b.+\\b(FROM|INTO|SET)\\b

case-sensitively, with DOTALL so a statement split over several lines of a
triple-quoted literal is caught too. The test passes when nothing is found.
"""
import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

SQL_RE = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b.+\b(FROM|INTO|SET)\b", re.DOTALL)
# Statements the R4 pattern can't see (no FROM / INTO / SET after the verb,
# or a verb it doesn't list). Case-insensitive: these are rare enough in
# prose that any hit deserves a look.
SQL_EXTRA_RE = re.compile(r"\b(REPLACE\s+INTO|SHOW\s+TABLES|GET_LOCK|RELEASE_LOCK|INSERT\s+IGNORE)\b",
                          re.IGNORECASE)
PATTERNS = (SQL_RE, SQL_EXTRA_RE)

EXCLUDED_DIRS = {"repo", "tests", "scripts", "tools", "venv", "__pycache__"}

# (path relative to backend/, text the matched string starts with) -> reason.
# An entry excuses exactly that string, nothing else in the file. Keep minimal.
ALLOW = {
    ("api_admin_backup.py", r"INSERT INTO `(\w+)` VALUES (.*);"):
        "a regex that counts rows in a mysqldump file (_INSERT_LINE_RE); "
        "it parses dump text and is never executed",
}


def _source_files():
    files = list(BACKEND.glob("*.py"))
    for sub in ("excel_extractors", "techno_project"):
        files += (BACKEND / sub).rglob("*.py")
    out = []
    for f in files:
        rel = f.relative_to(BACKEND)
        if any(part in EXCLUDED_DIRS for part in rel.parts[:-1]):
            continue
        out.append(f)
    return sorted(out)


def _docstring_ids(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Constant, ast.JoinedStr)):
            ids.add(id(node.value))
    return ids


def _flatten(node):
    """Text of a string constant, an f-string (each {...} becomes "{}") or a
    `+` chain with at least one string part (each non-string operand becomes
    "{}"), else None."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}"
                       for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _flatten(node.left), _flatten(node.right)
        if left is None and right is None:
            return None
        return (left if left is not None else "{}") + (right if right is not None else "{}")
    return None


def _string_constants(tree):
    """(lineno, text) for every non-docstring string constant, f-string and
    string `+` chain (so a statement built as "SELECT a, " + cols + " FROM t"
    is seen whole)."""
    skip = _docstring_ids(tree)
    inside_fstring = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for v in node.values:
                inside_fstring.add(id(v))
    for node in ast.walk(tree):
        if id(node) in skip or id(node) in inside_fstring:
            continue
        if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp)):
            text = _flatten(node)
            if text is not None:
                yield node.lineno, text


def find_sql(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits = []
    seen = set()
    for lineno, text in _string_constants(tree):
        for pattern in PATTERNS:
            m = pattern.search(text)
            if not m:
                continue
            snippet = " ".join(text[m.start():m.start() + 80].split())
            if (lineno, snippet) not in seen:
                seen.add((lineno, snippet))
                hits.append((lineno, snippet))
    return hits


def _allowed(rel, snippet):
    return any(rel == path and snippet.startswith(prefix) for path, prefix in ALLOW)


def scan():
    found = []
    for f in _source_files():
        rel = f.relative_to(BACKEND).as_posix()
        for lineno, snippet in find_sql(f):
            if not _allowed(rel, snippet):
                found.append(f"{rel}:{lineno}: {snippet}")
    return found


def test_scanner_detects_sql_and_ignores_prose(tmp_path):
    p = tmp_path / "m.py"
    p.write_text(
        '"""Module doc: SELECT x FROM y is prose here."""\n'
        "# SELECT a FROM b in a comment\n"
        "def f(cur, t):\n"
        '    """Docstring: DELETE rows FROM the table."""\n'
        '    cur.execute("SELECT a "\n'
        '                "FROM b WHERE c=%s", (1,))\n'
        '    cur.execute(f"""\n'
        "        UPDATE {t}\n"
        '        SET a = %s""", (2,))\n'
        '    msg = "select a from b"\n'
        '    label = "INSERT"\n'
        '    cur.execute("SELECT a, " + ", ".join(t) + " FROM b", ())\n'
        '    cur.execute("select get_lock(%s, 0)", ("x",))\n'
        '    cur.execute("SHOW TABLES")\n'
        '    cur.execute("replace into t (a) values (%s)", (1,))\n'
        '    note = "replace the tables shown"\n',
        encoding="utf-8",
    )
    hits = find_sql(p)
    assert sorted(h[0] for h in hits) == [5, 7, 12, 13, 14, 15], hits


def test_hits_on_one_line_are_kept_per_snippet(tmp_path):
    """Two statements whose strings start on the same line are both reported
    (dedupe is on (line, snippet), not line alone)."""
    p = tmp_path / "m.py"
    p.write_text('x = ("SELECT a FROM b", "DELETE FROM c")\n', encoding="utf-8")
    assert [s for _, s in find_sql(p)] == ["SELECT a FROM b", "DELETE FROM c"]


def test_allow_list_entries_still_match():
    """Every allow-list entry still excuses a real string (no stale entries)."""
    for path, prefix in ALLOW:
        snippets = [s for _, s in find_sql(BACKEND / path)]
        assert any(s.startswith(prefix) for s in snippets), (path, prefix)


def test_no_sql_outside_repo():
    found = scan()
    assert not found, "SQL outside backend/repo/:\n" + "\n".join(found)
