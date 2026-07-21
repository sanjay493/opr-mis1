"""Per-request collector of old/new row snapshots for editor-triggered writes.

EditorAdminGateMiddleware (main.py) calls start() before handing a gated
request to its endpoint, and pop() after the endpoint returns, to build a
detailed activity_log entry. db.py's save/delete helpers (and the handful of
routers that write outside db.py, e.g. api_todo.py/api_worklog.py) call
record() around each write. A plain ContextVar is enough for per-request
isolation: FastAPI/Starlette runs each request in its own asyncio Task, and
tasks get their own copy of the context.
"""
import contextvars
from typing import Optional

_changes: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar(
    "activity_changes", default=None
)


def start() -> None:
    """Begin collecting changes for the current request."""
    _changes.set([])


def record(unit: str, old: Optional[dict], new: Optional[dict]) -> None:
    """Record one row-level change: unit identifies which record (e.g.
    'BSP/Hot Metal/2026-06'), old/new are the row before/after as plain
    dicts (None for old on insert, None for new on delete). No-op if
    nothing is currently collecting (e.g. a script or test calling a save
    function outside a gated request)."""
    lst = _changes.get()
    if lst is not None:
        lst.append({"unit": unit, "old": old, "new": new})


def pop() -> list:
    """Return and clear the changes collected for the current request."""
    lst = _changes.get()
    return lst if lst is not None else []
