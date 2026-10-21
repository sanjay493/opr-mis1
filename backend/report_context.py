"""Request-scoped bulk loads for building report pages.

    with report_context.activate("2026-08"):
        rows = generate_page4_rows("2026-08")

Inside the block, repo.production / repo.techno serve per-month reads from
ONE bulk load of every row for the window (all production measures, and
techno_data), instead of one query per (plant, item, month):

    window = <FY start of the CPLY month> .. <FY end of the report month>

(FY end, not the report month itself: Annual APP and the FY plan columns
read the whole current FY's plan.) Reads for months outside the window
fall through to SQL unchanged. History range queries (records, trends)
are memoised per call signature with ctx.memo().

Loading is lazy: nothing is read until the first repo call that the
window covers, so a request served wholly from main's page cache does no
bulk work. The context knows nothing about SQL; each repo module passes
its own loader (ctx.load(name, loader)).

Writes: every repo write calls repo.version.bump() first, which calls
invalidate_current(): the active context drops everything it loaded and
reloads on the next read, so a request never reads its own stale bulk
data. Inside the preview dry run (repo.conn.rollback_tx) no context is
served (current() is None): reads there must see that connection's
uncommitted state.

Matching: MySQL compares plant / item / unit names with
utf8mb4_0900_ai_ci (case- and accent-insensitive), so the bulk data is
keyed on fold(name) for lookups, and keeps the stored spelling for
results that return it.
"""
from contextlib import contextmanager
import contextvars
import threading
import unicodedata

import dbengine

_current = contextvars.ContextVar("report_context", default=None)


def fold(name):
    """Key under which MySQL's utf8mb4_0900_ai_ci treats two names as equal
    (case- and accent-insensitive; NO PAD, so spaces stay significant)."""
    if not isinstance(name, str):
        return name
    if name.isascii():
        return name.casefold()
    decomposed = unicodedata.normalize("NFKD", name)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _month_index(month):
    return int(month[:4]) * 12 + int(month[5:7]) - 1


def _month_at(idx):
    return f"{idx // 12}-{idx % 12 + 1:02d}"


def window(report_month):
    """(first, last) month of the bulk window for report_month."""
    y, m = int(report_month[:4]), int(report_month[5:7])
    fy = y if m >= 4 else y - 1
    return f"{fy - 1}-04", f"{fy + 1}-03"


class ReportContext:
    def __init__(self, report_month):
        self.report_month = report_month
        try:
            self.first, self.last = window(report_month)
        except (TypeError, ValueError, IndexError):
            # Not a YYYY-MM month: cover nothing, every read runs its SQL
            # (and fails or not exactly as it did without a context).
            self.first = self.last = None
            self.months = frozenset()
        else:
            lo, hi = _month_index(self.first), _month_index(self.last)
            self.months = frozenset(_month_at(i) for i in range(lo, hi + 1))
        self._loaded = {}            # loader name -> loaded data
        self._memo = {}              # call signature -> result
        self._lock = threading.Lock()
        self.loads = 0               # bulk loads done (tests)

    def covers(self, months) -> bool:
        """True when every month is inside the bulk window."""
        months = list(months) if not isinstance(months, (set, frozenset)) else months
        return bool(months) and all(m in self.months for m in months)

    def load(self, name, loader):
        """loader(first, last), run once per context (until invalidated)."""
        with self._lock:
            if name in self._loaded:
                return self._loaded[name]
        data = loader(self.first, self.last)
        with self._lock:
            self._loaded.setdefault(name, data)
            self.loads += 1
            return self._loaded[name]

    def memo(self, key, compute):
        """compute(), once per key for this context (until invalidated).
        Callers must not mutate the result (return copies if they might)."""
        with self._lock:
            if key in self._memo:
                return self._memo[key]
        value = compute()
        with self._lock:
            return self._memo.setdefault(key, value)

    def invalidate(self) -> None:
        with self._lock:
            self._loaded.clear()
            self._memo.clear()


def current():
    """The active context, or None (none active, or inside the dry run)."""
    ctx = _current.get()
    if ctx is None or dbengine._shared_raw.get() is not None:
        return None
    return ctx


def covering(months):
    """The active context if it covers every month in `months`, else None."""
    ctx = current()
    if ctx is None:
        return None
    return ctx if ctx.covers(months) else None


def invalidate_current() -> None:
    """Called by every repo write (repo.version.bump): drop the active
    context's bulk data so the next read reloads it."""
    ctx = _current.get()
    if ctx is not None:
        ctx.invalidate()


@contextmanager
def activate(report_month: str):
    """Serve bulk reads for report_month's window inside the block. An
    already-active context for the same month is reused (nested pages and
    the request handler share one load)."""
    active = _current.get()
    if active is not None and active.report_month == report_month:
        yield active
        return
    ctx = ReportContext(report_month)
    token = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)
