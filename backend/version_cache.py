"""In-process LRU keyed on data_version (see data_version.py).

    cache = VersionedCache(maxsize=512)
    value = cache.get_or_compute(("2026-08", 4), "rows", lambda: build())

Entries live under key + (data_version,); each entry is a dict of parts
(one page can hold several computed pieces). A write bumps data_version, so
old entries are simply never asked for again and age out of the LRU.

Values are deep-copied on store and on every hit: callers mutate page dicts
(enrichment does), and nothing a caller does to a returned value may reach
the cache. With no data_version (table missing) nothing is cached.
"""
from collections import OrderedDict
import copy
import threading

import data_version


class VersionedCache:
    def __init__(self, maxsize: int):
        self.maxsize = maxsize
        self._entries = OrderedDict()   # key + (version,) -> {part: value}
        self._lock = threading.Lock()
        data_version.on_clear(self.clear)

    def get_or_compute(self, key: tuple, part, compute):
        version = data_version.current()
        if version is None:
            return compute()
        full_key = key + (version,)
        with self._lock:
            entry = self._entries.get(full_key)
            if entry is not None:
                self._entries.move_to_end(full_key)
            hit = entry is not None and part in entry
            stored = entry[part] if hit else None
        if hit:
            # Stored values are never mutated, so copying outside the lock is safe.
            return copy.deepcopy(stored)
        value = compute()
        stored = copy.deepcopy(value)
        with self._lock:
            entry = self._entries.get(full_key)
            if entry is None:
                entry = self._entries[full_key] = {}
            self._entries.move_to_end(full_key)
            entry[part] = stored
            while len(self._entries) > self.maxsize:
                self._entries.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def keys(self) -> list:
        with self._lock:
            return list(self._entries)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
