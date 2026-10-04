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
    "table_header_bg_hh":          "transparent",
    "table_header_bg_total":       "transparent",
    "table_header_bg_section":     "transparent",

    "highlight_capacity_bg":       "#fee2e2",
    "highlight_actual_bg":         "#dbeafe",
    "highlight_actual_border":     "#1d4ed8",
    "highlight_cumulative_bg":     "#d1fae5",
    "highlight_planned_band_bg":   "#eff6ff",
    "highlight_target_band_bg":    "#fef9c3",
    "highlight_achieved_band_bg":  "#dcfce7",
    "highlight_shortfall_band_bg": "#fed7aa",
    "highlight_info_band_bg":      "#f0f9ff",
    "highlight_agg_sail_bg":       "#bbf7d0",
    "highlight_agg_5plants_bg":    "#fef08a",
    "highlight_qtr_col_bg":        "#dce8fa",
    "highlight_hh_col_bg":         "#d1fae5",
    "highlight_total_col_bg":      "#eae1f5",
    "highlight_plant_label_bg":    "#d1d5db",

    "page4_cap_bg":     "#F8CBAD",
    "page4_cap_text":   "#843C0C",
    "page4_app_bg":     "#FFF2CC",
    "page4_app_text":   "#7F6000",
    "page4_app_border": "#BF9000",
    "page4_act_bg":     "#C6EFCE",
    "page4_act_text":   "#006100",

    "techno_cat_fuel_bg":          "#fde2c8",
    "techno_cat_energy_bg":        "#fff3c4",
    "techno_cat_process_bg":       "#cfe8ff",
    "techno_cat_burden_bg":        "#d9f2d0",
    "techno_cat_environment_bg":   "#cdf0ea",
    "techno_cat_blend_bg":         "#e5e0f5",

    "techno_tep_header_text":      "#1f2937",
    "techno_tep_target_bg":        "#fff4e5",
    "techno_tep_target_text":      "#7a3e00",
    "techno_tep_month_bg":         "#e5f0fa",
    "techno_tep_month_text":       "#003a70",
    "techno_tep_cum_bg":           "#f0f6fc",
    "techno_tep_cum_text":         "#003a70",
    "techno_tep_total_row_bg":     "#dcebf7",
    "techno_tep_total_row_text":   "#002b55",

    "plant_color_bsp":  "#a9c5ec",
    "plant_color_dsp":  "#f1d0a1",
    "plant_color_rsp":  "#cbb5e6",
    "plant_color_bsl":  "#f2b1c7",
    "plant_color_isp":  "#9fd3e0",
    "plant_color_asp":  "#b9dd9c",
    "plant_color_ssp":  "#e8bb9c",
    "plant_color_visl": "#afbdd0",
    "highlight_group_label_bg":    "#f8fafc",
    "highlight_pct_row_bg":        "#f1f5f9",
    "highlight_section_data_bg":   "#eff6ff",
    "highlight_alt_section_bg":    "transparent",
    "highlight_bold_row_bg":       "#eef2f6",
    "highlight_default_row_bg":    "transparent",
    "highlight_best_ever_bg":      "#fde68a",
    "highlight_best_month_border_light": "#94a3b8",

    "border_light":     "#cbd5e1",
    "border_medium":    "#94a3b8",
    "border_dark":      "#334155",
    "border_darkest":   "#1e293b",
    "border_black":     "#000000",
    "border_divider":   "#e2e8f0",
    "border_group_top": "#374151",
    "border_heavy":     "#64748b",
    "border_green":     "#2d5016",
    "border_darkred":   "#8B0000",
    "border_slate_sep": "#5a7fa0",
    "border_header":    "#93c5fd",
    "border_cumulative_col": "#96ae83",

    "text_primary":        "#0f172a",
    "text_secondary":      "#475569",
    "text_muted":          "#64748b",
    "text_faint":          "#94a3b8",
    "text_accent_navy":    "#060177",
    "highlight_report_fy_text": "#0000ff",
    "text_black":          "#000000",
    "text_white":          "#ffffff",
    "text_dark_gray":      "#333333",
    "text_variance_green": "#064e3b",
    "text_variance_blue":  "#1e40af",
    "text_variance_red":   "#9a3412",
    "text_rust_brown":     "#B7410E",
    "text_plant_cell":     "#1e3a5f",
    "text_heading_dark":   "#1e293b",

    "misc_white":                 "#ffffff",
    "misc_accent_blue":           "#0284c7",
    "misc_highlights_box_bg":     "#f8fafc",
    "misc_highlights_box_border": "#0284c7",

    "cover_navy_dark":       "#000c48",
    "cover_label":           "#000000",
    "cover_value":           "#722F99",
    "cover_royal_blue":      "#0047c8",
    "cover_badge_navy":      "#002691",
    "cover_kpi_card_bg":     "#f8fafc",
    "cover_kpi_card_border": "#e2e8f0",
    "cover_molten_red":      "#e8380d",

    "khv_banner_bg":            "#0f2a5c",
    "khv_badge_bg":             "#0047c8",
    "khv_achieve_header_bg":    "#1e7e34",
    "khv_achieve_box_bg":       "#f0fdf4",
    "khv_achieve_box_border":   "#86efac",
    "khv_shortfall_header_bg":  "#b91c1c",
    "khv_shortfall_box_bg":     "#fef2f2",
    "khv_shortfall_box_border": "#fca5a5",
    "khv_focus_header_bg":      "#0f2a5c",
    "khv_focus_box_bg":         "#f8fafc",
    "khv_va_header_bg":         "#0369a1",
    "khv_va_box_bg":            "#f0f9ff",
    "khv_assessment_green":     "#16a34a",
    "khv_assessment_amber":     "#d97706",
    "khv_assessment_red":       "#dc2626",
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
