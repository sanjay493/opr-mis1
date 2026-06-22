import json
import os
from typing import Any, Dict

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "layout_config.json")


def load_layout_config() -> Dict[str, Any]:
    """Return {"global": {...}, "pages": {...}} from layout_config.json.
    Re-reads the file every call so edits take effect without a restart."""
    if not os.path.exists(_CONFIG_PATH):
        return {"global": {}, "pages": {}}
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "global": data.get("global", {}),
        "pages":  data.get("pages",  {}),
    }
