import json
import os
from typing import Any, Dict

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "layout_config.json")

_RESERVED_KEYS = {k for k in ("_doc", "_doc_table", "_doc_groups") }


def _expand_page_key(key: str):
    """'7-13' -> [7,8,...,13]; '5,6,9' -> [5,6,9]; '9' -> [9]."""
    pages = []
    for part in key.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            pages.extend(range(int(lo), int(hi) + 1))
        else:
            pages.append(int(part))
    return pages


def _normalize_table(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Build a {thead, th, tbody, td} dict from an entry's 'table' object,
    falling back to the legacy flat 'fontSize' (applies to all four) when
    'table' isn't given. Mirrors th->thead and td->tbody when only one of
    each pair is set, since header/body row-groups almost always match
    their cell size."""
    table = dict(entry.get("table") or {})
    if not table and entry.get("fontSize") is not None:
        fs = entry["fontSize"]
        table = {"th": fs, "td": fs}
    if "th" in table and "thead" not in table:
        table["thead"] = table["th"]
    if "td" in table and "tbody" not in table:
        table["tbody"] = table["td"]
    return table


def load_layout_config() -> Dict[str, Any]:
    """Return {"global": {...}, "pages": {...}} from layout_config.json.
    Re-reads the file every call so edits take effect without a restart.

    Page keys may be a single page number ("9"), a hyphen range ("7-13"),
    or a comma list ("5,6,9") — all expanded here into one resolved entry
    per page number, each carrying a normalized "table" dict with
    thead/th/tbody/td point sizes. Group keys are applied first; a more
    specific single-page key overrides a group's values for that page.
    """
    if not os.path.exists(_CONFIG_PATH):
        return {"global": {}, "pages": {}}
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)

    raw_pages = {k: v for k, v in data.get("pages", {}).items() if k not in _RESERVED_KEYS}

    # Groups (ranges/lists) are expanded first; explicit single-page keys
    # are applied afterward so they win when they overlap a group.
    group_keys  = [k for k in raw_pages if not k.strip().isdigit()]
    single_keys = [k for k in raw_pages if k.strip().isdigit()]

    expanded: Dict[str, Dict[str, Any]] = {}
    for key in group_keys + single_keys:
        entry = raw_pages[key]
        table = _normalize_table(entry)
        other = {k: v for k, v in entry.items() if k not in ("table", "fontSize")}
        for pg in _expand_page_key(key):
            pg_key = str(pg)
            merged = dict(expanded.get(pg_key, {}))
            merged.update(other)
            merged["table"] = {**merged.get("table", {}), **table}
            expanded[pg_key] = merged

    global_cfg = dict(data.get("global", {}))
    global_cfg["table"] = _normalize_table(global_cfg)

    return {
        "global": global_cfg,
        "pages":  expanded,
    }
