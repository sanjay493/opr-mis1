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
    for path in sorted(REPO.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstrings(tree)
        write_names = _module_write_constants(tree)
        funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        bumpers = {name for name, f in funcs.items() if _calls_bump(f)}
        for f in funcs.values():
            f._bumps = f.name in bumpers or bool(_called_names(f) & bumpers)
        for f in funcs.values():
            if _writes(f, docs, write_names):
                out[(path.stem, f.name)] = f
    return out


def test_scan_finds_the_known_writers():
    found = _write_functions()
    for key in [("production", "upsert"), ("production", "upsert_row"),
                ("production", "save_production_actual"), ("techno", "save_techno_plan"),
                ("ops", "log_extraction"), ("misc", "replace_cover_setting"),
                ("text", "save_texts"), ("breakdown", "delete_cr_row")]:
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
