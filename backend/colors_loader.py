import json
import os
from typing import Any, Dict

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "colors_config.json")

_RESERVED_KEYS_PREFIX = "_doc"

# Fallback values used only for keys missing from colors_config.json (e.g. the
# file was hand-edited and a key was deleted) so a typo never breaks rendering.
_DEFAULTS: Dict[str, str] = {
    "table_header_bg":             "transparent",
    "table_header_bg_qtr":         "transparent",
    "table_header_bg_total":       "transparent",
    "table_header_bg_section":     "transparent",

    "highlight_actual_bg":         "#dbeafe",
    "highlight_actual_border":     "#1d4ed8",
    "highlight_cumulative_bg":     "#d1fae5",
    "highlight_planned_band_bg":   "#eff6ff",
    "highlight_target_band_bg":    "#fef9c3",
    "highlight_achieved_band_bg":  "#dcfce7",
    "highlight_shortfall_band_bg": "#fed7aa",
    "highlight_info_band_bg":      "#e0f2fe",
    "highlight_agg_sail_bg":       "#bbf7d0",
    "highlight_agg_5plants_bg":    "#fef08a",
    "highlight_qtr_col_bg":        "#f0f5ff",
    "highlight_total_col_bg":      "#e8f0fb",
    "highlight_plant_label_bg":    "#e8edf3",
    "highlight_group_label_bg":    "#f8fafc",
    "highlight_pct_row_bg":        "#f1f5f9",
    "highlight_section_data_bg":   "#eff6ff",
    "highlight_alt_section_bg":    "transparent",
    "highlight_bold_row_bg":       "#eef2f6",
    "highlight_default_row_bg":    "transparent",

    "border_light":     "#cbd5e1",
    "border_medium":    "#94a3b8",
    "border_dark":      "#334155",
    "border_darkest":   "#1e293b",
    "border_black":     "#000000",
    "border_divider":   "#e2e8f0",
    "border_group_top": "#374151",
    "border_heavy":     "#64748b",
    "border_green":     "#2d5016",
    "border_slate_sep": "#5a7fa0",
    "border_header":    "#93c5fd",
    "border_cumulative_col": "#96ae83",

    "text_primary":        "#0f172a",
    "text_secondary":      "#475569",
    "text_muted":          "#64748b",
    "text_faint":          "#94a3b8",
    "text_accent_navy":    "#060177",
    "text_black":          "#000000",
    "text_white":          "#ffffff",
    "text_dark_gray":      "#333333",
    "text_variance_green": "#064e3b",
    "text_variance_blue":  "#1e40af",
    "text_plant_cell":     "#1e3a5f",
    "text_heading_dark":   "#1e293b",

    "misc_white":                 "#ffffff",
    "misc_accent_blue":           "#0284c7",
    "misc_highlights_box_bg":     "#f8fafc",
    "misc_highlights_box_border": "#0284c7",
}


def load_colors_config() -> Dict[str, Any]:
    """Return the {role_name: css_color} map from colors_config.json.

    Re-reads the file every call so edits take effect without a restart.
    Falls back to the built-in defaults for any key missing from the file
    (or if the file itself is missing), so a hand-edit typo never breaks
    PDF generation.
    """
    colors = dict(_DEFAULTS)
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k.startswith(_RESERVED_KEYS_PREFIX):
                continue
            colors[k] = v
    return colors
