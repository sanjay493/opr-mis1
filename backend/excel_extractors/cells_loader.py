"""Loader for excel_cells_config.json.

Re-reads the file on every call so edits take effect without a server restart.
Returns {} (empty dict) on any error so extractors fall back to their defaults.
"""
import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "excel_cells_config.json")


def get_extractor_config(name: str) -> dict:
    """Return the config section for `name`, e.g. 'bsl_dpr', 'isp_morning'."""
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f).get(name, {})
    except Exception:
        return {}
