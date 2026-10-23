"""Every repo function that writes calls the data_version bump.

Parity snapshots only read, so they can't see a write path that forgets to
bump (and a cache that then serves stale pages). This scans backend/repo/
with the AST: any function holding a write statement (a string constant,
f-string or module-level SQL constant it names, starting INSERT / UPDATE /
DELETE / REPLACE) must call `_ver.bump(...)` itself. The exempt functions
write only accounts / audit / traffic / to-do tables that no report page
reads, so bumping there would only throw caches away.
"""
import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent / "repo"


def repo_sources():
    """(module key, path) of every repo module: repo/<m>.py as "<m>", and
    the Task 7 v2 implementations repo/v2/<m>.py as "v2.<m>"."""
    out = [(p.stem, p) for p in sorted(REPO.glob("*.py"))]
    out += [(f"v2.{p.stem}", p) for p in sorted((REPO / "v2").glob("*.py"))]
    return out

WRITE_RE = re.compile(r"^\s*(INSERT|UPDATE|DELETE|REPLACE)\b")

# (module, function) -> reason. Tables: users, allowed_emails, otp_codes,
# activity_log, page_visits, admin_notifications, todo_jobs, daily_work_log.
EXEMPT = {
    ("ops", "log_page_visit"): "page_visits",
    ("ops", "_add_admin_notification"): "admin_notifications",
    ("ops", "log_activity"): "activity_log",
    ("ops", "otp_invalidate_unused"): "otp_codes",
    ("ops", "otp_insert"): "otp_codes",
    ("ops", "otp_mark_used"): "otp_codes",
    ("ops", "insert_user"): "users",
    ("ops", "update_password"): "users",
    ("ops", "update_user_fields"): "users",
    ("ops", "set_user_permissions"): "users",
    ("ops", "set_user_role"): "users",
    ("ops", "delete_user"): "users",
    ("ops", "upsert_allowed_email"): "allowed_emails",
    ("ops", "delete_allowed_email"): "allowed_emails",
    ("ops", "set_allowed_email_barred"): "allowed_emails",
    ("ops", "insert_todo_job"): "todo_jobs",
    ("ops", "update_todo_job"): "todo_jobs",
    ("ops", "complete_todo_job"): "todo_jobs",
    ("ops", "reopen_todo_job"): "todo_jobs",
    ("ops", "delete_todo_job"): "todo_jobs",
    ("ops", "insert_worklog_entry"): "daily_work_log",
    ("ops", "update_worklog_entry"): "daily_work_log",
    ("ops", "delete_worklog_entry"): "daily_work_log",
    ("version", "bump"): "the bump itself",
    ("version", "set_fresh"): "the post-restore reset",
}


# the v2 implementation keeps v1's exemptions (Task 7f)
EXEMPT.update({("v2." + m, f): why for (m, f), why in list(EXEMPT.items()) if m == "ops"})


def _text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}"
                       for v in node.values)
    return None


def _docstrings(tree):
    return {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)}


def _module_write_constants(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            t = _text(node.value)
            if t and WRITE_RE.search(t):
                names.add(node.targets[0].id)
    return names


def _writes(fn, docs, write_names):
    for node in ast.walk(fn):
        if id(node) in docs:
            continue
        t = _text(node)
        if t and WRITE_RE.search(t):
            return True
        if isinstance(node, ast.Name) and node.id in write_names:
            return True
    return False


def _calls_bump(fn):
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "bump" \
                    and isinstance(f.value, ast.Name) and f.value.id == "_ver":
                return True
    return False


def _called_names(fn):
    return {n.func.id for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def _bumps(fn):
    """fn calls _ver.bump itself, or a same-module helper that does (e.g.
    misc._cover_execute, which runs every cover write)."""
    return fn._bumps


def _write_functions():
    out = {}
    for stem, path in repo_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstrings(tree)
        write_names = _module_write_constants(tree)
        funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        bumpers = {name for name, f in funcs.items() if _calls_bump(f)}
        for f in funcs.values():
            f._bumps = f.name in bumpers or bool(_called_names(f) & bumpers)
        for f in funcs.values():
            if _writes(f, docs, write_names):
                out[(stem, f.name)] = f
    return out


# ── bump-first ordering ─────────────────────────────────────────────────────
# Every writer takes the data_version row lock BEFORE any data-row lock, so
# two concurrent writers always lock in the same order and cannot deadlock
# on it (MySQL error 1213).

def _is_bump(call):
    f = call.func
    return isinstance(f, ast.Attribute) and f.attr == "bump" \
        and isinstance(f.value, ast.Name) and f.value.id == "_ver"


def _local_write_names(fn):
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            t = _text(node.value)
            if t and WRITE_RE.search(t):
                names |= {x.id for x in targets if isinstance(x, ast.Name)}
    return names


def _is_write_sql(arg, write_names):
    t = _text(arg)
    if t is not None:
        return bool(WRITE_RE.search(t))
    if isinstance(arg, ast.Name):
        return arg.id in write_names
    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) \
            and arg.func.attr == "format" and isinstance(arg.func.value, ast.Name):
        return arg.func.value.id in write_names
    return False


def write_and_bump_calls(tree):
    """(function, first write call, first direct _ver.bump call) for each
    module-level function that executes write SQL; a write call is an
    execute / executemany whose SQL is a write statement."""
    module_names = _module_write_constants(tree)
    for fn in tree.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # A SQL parameter counts as a write: a generic executor such as
        # misc._cover_execute runs whatever write its callers pass.
        params = {a.arg for a in fn.args.args}
        names = module_names | _local_write_names(fn) | params
        calls = sorted((n for n in ast.walk(fn) if isinstance(n, ast.Call)),
                       key=lambda n: (n.lineno, n.col_offset))
        write = next((c for c in calls
                      if isinstance(c.func, ast.Attribute) and c.func.attr in ("execute", "executemany")
                      and c.args and _is_write_sql(c.args[0], names)), None)
        bump = next((c for c in calls if _is_bump(c)), None)
        if write is not None or bump is not None:
            yield fn, write, bump


def enclosing_stmt(body, lineno):
    """The statement in `body` holding line `lineno`, descending into try /
    with bodies (straight-line code) but not into loops or branches."""
    for stmt in body:
        if stmt.lineno <= lineno <= stmt.end_lineno:
            if isinstance(stmt, (ast.Try, ast.With)) and stmt.body \
                    and stmt.body[0].lineno <= lineno <= stmt.body[-1].end_lineno:
                return enclosing_stmt(stmt.body, lineno)
            return stmt
    raise LookupError(lineno)


def test_bump_precedes_the_first_write():
    late, unseen = [], []
    for stem, path in repo_sources():
        if stem == "version":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn, write, bump in write_and_bump_calls(tree):
            if bump is None:
                continue                      # exempt, or bumps through a helper
            if write is None:
                unseen.append(f"{stem}.{fn.name}")
            elif (bump.lineno, bump.col_offset) > (write.lineno, write.col_offset):
                late.append(f"{stem}.{fn.name}: bump L{bump.lineno} after write L{write.lineno}")
    assert late == []
    assert unseen == []


def test_scan_finds_the_known_writers():
    found = _write_functions()
    for key in [("production", "upsert"), ("production", "upsert_row"),
                ("production", "save_production_actual"), ("techno", "save_techno_plan"),
                ("ops", "log_extraction"), ("misc", "replace_cover_setting"),
                ("text", "save_texts"), ("breakdown", "delete_cr_row"),
                ("v2.production", "_put"), ("v2.production", "_clear"),
                ("v2.capacity", "save_capacity_entry")]:
        assert key in found, key
    assert len(found) > 100


def test_every_repo_write_function_bumps():
    missing = sorted(f"{m}.{f}" for (m, f), node in _write_functions().items()
                     if (m, f) not in EXEMPT and not _bumps(node))
    assert missing == []


def test_exemptions_are_live_and_do_not_bump():
    found = _write_functions()
    stale = sorted(k for k in EXEMPT if k not in found)
    assert stale == []
    bumping = sorted(f"{m}.{f}" for (m, f) in EXEMPT
                     if m != "version" and _bumps(found[(m, f)]))
    assert bumping == []
