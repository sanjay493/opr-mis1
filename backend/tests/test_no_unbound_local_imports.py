"""Static guard against the pyflakes F823 pattern: a function that imports a
name locally (`from repo import production as rp` inside the function) but
uses that name on an earlier line. The local import makes the name local to
the whole function, so the earlier use raises UnboundLocalError even when a
module-level import of the same name exists."""
import ast
import symtable
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
_SKIP_DIRS = {"venv", "tests", "__pycache__", ".venv", "node_modules"}


def _py_files():
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND)
        if _SKIP_DIRS & set(rel.parts[:-1]):
            continue
        yield p


def _own_nodes(fn):
    """Nodes in fn's own scope (nested defs / lambdas / classes excluded)."""
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                stack.append(child)


def _imported_locals(table):
    """{(name, lineno): {names}} for every function scope: names symtable
    reports as both local and imported."""
    out = {}
    stack = [table]
    while stack:
        t = stack.pop()
        if t.get_type() == "function":
            names = {s.get_name() for s in t.get_symbols() if s.is_local() and s.is_imported()}
            if names:
                out[(t.get_name(), t.get_lineno())] = names
        stack.extend(t.get_children())
    return out


def find_violations(path: Path, src: str = None):
    src = src if src is not None else path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
        table = symtable.symtable(src, str(path), "exec")
    except SyntaxError:
        return []
    targets = _imported_locals(table)
    if not targets:
        return []
    found = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = targets.get((fn.name, fn.lineno))
        if not names:
            # symtable reports a decorated def's line as the `def` line on
            # 3.8+, same as ast; nothing else to try.
            continue
        first_import, first_use = {}, {}
        for node in _own_nodes(fn):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for a in node.names:
                    n = (a.asname or a.name).split(".")[0]
                    if n in names:
                        first_import[n] = min(first_import.get(n, node.lineno), node.lineno)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names:
                first_use[node.id] = min(first_use.get(node.id, node.lineno), node.lineno)
        for n in names:
            if n in first_use and n in first_import and first_use[n] < first_import[n]:
                found.append(f"{path.relative_to(BACKEND) if path.is_absolute() else path}:"
                             f"{fn.name}:{n} (used line {first_use[n]}, imported line {first_import[n]})")
    return found


def test_detector_catches_use_before_local_import():
    src = ("import os\n"
           "def f():\n"
           "    x = os.sep\n"
           "    import os\n"
           "    return x\n"
           "def g():\n"
           "    import os\n"
           "    return os.sep\n")
    v = find_violations(Path("sample.py"), src)
    assert len(v) == 1 and ":f:os " in v[0]


def test_no_name_used_before_its_function_local_import():
    violations = []
    for p in _py_files():
        violations += find_violations(p)
    assert not violations, "names used before their function-local import:\n" + "\n".join(violations)
