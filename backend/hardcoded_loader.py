"""Loader for hardcoded_config.json — report figures that have no DB source
yet (hand-transcribed values, period-locked stopgaps).

The JSON file is the single source of truth; there is deliberately no
code-level fallback copy, so a missing/broken file fails loudly rather than
silently rendering stale numbers. Re-reads the file on every call so edits
take effect without a restart (same convention as colors_loader /
layout_loader). The consumers (page_sail_mines, page_special_steel_physical,
page_key_parameters) are not hot paths.
"""
import json
import os
from typing import Any, Dict

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "hardcoded_config.json")


def _strip_doc(obj: Any) -> Any:
    """Drop every key named '_doc' (or starting with '_doc'), recursively."""
    if isinstance(obj, dict):
        return {k: _strip_doc(v) for k, v in obj.items() if not k.startswith("_doc")}
    if isinstance(obj, list):
        return [_strip_doc(v) for v in obj]
    return obj


def load_hardcoded_config() -> Dict[str, Any]:
    """Full config dict, '_doc' keys stripped at every level."""
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return _strip_doc(json.load(f))


def section(name: str) -> Dict[str, Any]:
    """One top-level section (e.g. 'sail_mines'). KeyError if it's absent —
    an absent section means the config file is wrong, not an empty default."""
    return load_hardcoded_config()[name]
