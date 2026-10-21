"""Data version: a counter every repo write bumps in its own transaction
(table data_version, SQL in repo/version.py). In-process caches key on it,
so a write anywhere invalidates them without any explicit cache clearing.

    current()      the version, or None when the table is missing or inside
                   the preview dry run (callers then skip caching and
                   always recompute). Inside pinned()
                   it is read once and reused for the whole block.
    bump(cur=None) n := n + 1, on `cur` (joining its transaction) or in a
                   transaction of its own.
    pinned()       read current() once per request: page builds inside the
                   block all key on the same version.
    after_restore() after an import that bypassed repo writes (admin
                   restore): move n to a value never used before and clear
                   every registered in-process cache.
"""
from contextlib import contextmanager
import contextvars

from repo import version as _rv

_UNSET = object()
_pinned = contextvars.ContextVar("data_version_pinned", default=_UNSET)
_clear_hooks = []
_max_seen = 0     # highest n this process has read; a floor for after_restore


def current():
    # Inside the preview dry run (repo.conn.rollback_tx) caching is off: a
    # read there must never key a cache on that connection's uncommitted state.
    if _rv.in_dry_run():
        return None
    pinned = _pinned.get()
    if pinned is not _UNSET:
        return pinned
    return _read()


def _read():
    global _max_seen
    n = _rv.read()
    # Unlocked read-modify-write: benign, it only ever raises a floor
    # (a lost update just leaves after_restore a slightly lower one).
    if n is not None and n > _max_seen:
        _max_seen = n
    return n


def bump(cur=None) -> None:
    if cur is not None:
        _rv.bump(cur)
        return
    from repo import conn as rc
    with rc.tx() as c:
        _rv.bump(c)


@contextmanager
def pinned():
    """Read the version once; current() returns that value inside the block.
    Nested blocks reuse the outer value."""
    if _pinned.get() is not _UNSET:
        yield _pinned.get()
        return
    token = _pinned.set(_read())
    try:
        yield _pinned.get()
    finally:
        _pinned.reset(token)


def on_clear(fn):
    """Register fn() to run on after_restore() (an in-process cache's clear)."""
    _clear_hooks.append(fn)
    return fn


def clear_caches() -> None:
    for fn in _clear_hooks:
        fn()


def after_restore() -> None:
    """The restored dump may carry an older n. Move n past every value used
    so far: GREATEST(n + 1, now in microseconds, highest n this process has
    seen + 1). Normal bumps add 1, so they stay below the clock unless more
    than one write per microsecond has happened since the last restore.
    Then clear the in-process caches."""
    try:
        _rv.set_fresh(max(_rv.now_us(), _max_seen + 1))
    finally:
        clear_caches()
