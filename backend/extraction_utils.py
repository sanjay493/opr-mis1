"""Shared utilities for extraction across all plant extractors."""

from typing import Dict, Tuple, Optional, List, Any, Union


def calculate_tmi_consumption(
    techno_values: Union[
        Dict[str, Tuple[Optional[float], Optional[float]]],
        List[Dict[str, Any]]
    ]
) -> Union[
    Dict[str, Tuple[Optional[float], Optional[float]]],
    List[Dict[str, Any]]
]:
    """
    Calculate Total Metallic Input (TMI) / Total Metallic Charge as HM Consumption + Scrap Consumption.

    This function automatically finds all HM consumption and Scrap consumption pairs
    and calculates the corresponding TMI values. Supports parameter names with variations like:
    - "Hot Metal Consumption"
    - "HM consumption per ton of crude steel"
    - "Total Metallic Charge"
    - "TMI consumption per ton of crude steel"

    Args:
        techno_values: Either:
            - Dict mapping parameter name to (month_val, ytd_val) tuples, OR
            - List of dicts with 'parameter', 'actual', 'cum_actual' fields

    Returns:
        Updated structure with calculated TMI/Total Metallic Charge values
    """
    # Patterns for HM consumption parameter names
    hm_patterns = [
        "Hot Metal Consumption",
        "HM consumption per ton of crude steel",
        "HM Consumption",
        "Hot Metal",
    ]

    # Patterns for Scrap consumption
    scrap_patterns = [
        "Scrap consumption per ton of crude steel",
        "Scrap Consumption",
        "Scrap",
    ]

    # Patterns for TMI/Total Metallic Charge
    tmi_patterns = [
        "TMI consumption per ton of crude steel",
        "Total Metallic Charge",
        "TMI Consumption",
    ]

    def normalize(s: str) -> str:
        """Normalize parameter name for comparison."""
        return s.lower().strip()

    # Handle list of row dicts (BSP-style)
    if isinstance(techno_values, list):
        return _calculate_tmi_rows(techno_values, hm_patterns, scrap_patterns, tmi_patterns, normalize)

    # Handle dict format (RSP-style)
    # Iterate through all parameters looking for HM Consumption
    for param_key in list(techno_values.keys()):
        norm_param = normalize(param_key)

        # Check if this is an HM consumption parameter
        is_hm = any(normalize(pat) in norm_param for pat in hm_patterns)
        if not is_hm:
            continue

        # Extract the prefix (e.g., "SMS-II", "SMS-III", "SMS-1", "SMS-2")
        # Find the prefix by looking for the first word(s) before "Hot Metal" or "HM consumption"
        for hm_pat in hm_patterns:
            if normalize(hm_pat) in norm_param:
                prefix = param_key[:param_key.lower().find(hm_pat)].strip()
                break

        if not prefix:
            continue

        hm_month, hm_ytd = techno_values.get(param_key, (None, None))

        # Find corresponding Scrap consumption parameter
        scrap_key = None
        for existing_param in techno_values.keys():
            if existing_param.startswith(prefix) and any(
                normalize(pat) in normalize(existing_param) for pat in scrap_patterns
            ):
                scrap_key = existing_param
                break

        if not scrap_key:
            continue

        scrap_month, scrap_ytd = techno_values.get(scrap_key, (None, None))

        # Find corresponding TMI/Total Metallic Charge parameter
        tmi_key = None
        for existing_param in techno_values.keys():
            if existing_param.startswith(prefix) and any(
                normalize(pat) in normalize(existing_param) for pat in tmi_patterns
            ):
                tmi_key = existing_param
                break

        if not tmi_key:
            continue

        # Calculate TMI = HM + Scrap
        calc_month = None
        if hm_month is not None and scrap_month is not None:
            calc_month = round(hm_month + scrap_month, 3)

        calc_ytd = None
        if hm_ytd is not None and scrap_ytd is not None:
            calc_ytd = round(hm_ytd + scrap_ytd, 3)

        # Update TMI value if we have at least one calculated value
        if calc_month is not None or calc_ytd is not None:
            old_month, old_ytd = techno_values.get(tmi_key, (None, None))
            new_month = calc_month if calc_month is not None else old_month
            new_ytd = calc_ytd if calc_ytd is not None else old_ytd
            techno_values[tmi_key] = (new_month, new_ytd)

    return techno_values


def _calculate_tmi_rows(
    rows: List[Dict[str, Any]],
    hm_patterns: List[str],
    scrap_patterns: List[str],
    tmi_patterns: List[str],
    normalize,
) -> List[Dict[str, Any]]:
    """Calculate TMI for list of row dicts (BSP/SAIL style with 'parameter', 'actual', 'cum_actual')."""
    # Build lookup maps by parameter name
    param_to_row = {}
    for row in rows:
        param_name = row.get("parameter", "")
        if param_name:
            param_to_row[param_name] = row

    # Find HM/Scrap/TMI sets by section prefix
    for param_name in list(param_to_row.keys()):
        norm_param = normalize(param_name)

        # Check if this is an HM consumption parameter
        is_hm = any(normalize(pat) in norm_param for pat in hm_patterns)
        if not is_hm:
            continue

        # Extract the prefix (e.g., "SMS-II", "SMS-III")
        # Find the prefix by looking for the first word(s) before "Hot Metal" or similar
        prefix = None
        for hm_pat in hm_patterns:
            if normalize(hm_pat) in norm_param:
                idx = param_name.lower().find(hm_pat.lower())
                if idx >= 0:
                    prefix = param_name[:idx].strip()
                    break

        if not prefix:
            continue

        hm_row = param_to_row[param_name]
        hm_actual = hm_row.get("actual")
        hm_cum = hm_row.get("cum_actual")

        # Find corresponding Scrap consumption parameter
        scrap_row = None
        for other_param in param_to_row.keys():
            if other_param.startswith(prefix) and any(
                normalize(pat) in normalize(other_param) for pat in scrap_patterns
            ):
                scrap_row = param_to_row[other_param]
                break

        if not scrap_row:
            continue

        scrap_actual = scrap_row.get("actual")
        scrap_cum = scrap_row.get("cum_actual")

        # Find corresponding TMI/Total Metallic Charge parameter
        tmi_row = None
        for other_param in param_to_row.keys():
            if other_param.startswith(prefix) and any(
                normalize(pat) in normalize(other_param) for pat in tmi_patterns
            ):
                tmi_row = param_to_row[other_param]
                break

        if not tmi_row:
            continue

        # Calculate TMI = HM + Scrap
        if hm_actual is not None and scrap_actual is not None:
            tmi_row["actual"] = round(hm_actual + scrap_actual, 3)

        if hm_cum is not None and scrap_cum is not None:
            tmi_row["cum_actual"] = round(hm_cum + scrap_cum, 3)

    return rows
