"""
Utilities for fetching production data from production_table
Handles furnace-wise and plant-level HM production lookups
"""

import sqlite3
from typing import Optional
from db import DB_PATH


def get_hm_production_for_furnace(plant: str, furnace: str, report_month: str) -> Optional[float]:
    """
    Get Hot Metal production for specific furnace from production_table

    Priority:
    1. Try exact furnace name (e.g., "BF-1")
    2. Try with hyphen->hash conversion (e.g., "BF#1")
    3. Try uppercase (e.g., "BF-1")

    Returns: HM production value or None
    """

    conn = db.connect()
    cursor = conn.cursor()

    possible_names = [
        furnace,                    # "BF-1"
        furnace.replace('-', '#'),  # "BF#1"
        furnace.upper(),            # "BF-1" (already upper in most cases)
        furnace.replace('-', ' '),  # "BF 1" (some PDFs use spaces)
    ]

    for item_name in possible_names:
        cursor.execute("""
            SELECT month_actual FROM production_table
            WHERE plant_name = ? AND item_name = ? AND report_month = ?
        """, [plant, item_name, report_month])

        result = cursor.fetchone()
        if result:
            conn.close()
            return float(result[0])

    conn.close()
    return None


def get_plant_hm_production(plant: str, report_month: str) -> Optional[float]:
    """
    Get plant-level Hot Metal production from production_table

    Returns: Total HM production for the plant or None
    """

    conn = db.connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT month_actual FROM production_table
        WHERE plant_name = ? AND item_name = 'Hot Metal' AND report_month = ?
    """, [plant, report_month])

    result = cursor.fetchone()
    conn.close()

    return float(result[0]) if result else None


def allocate_plant_hm_to_furnaces(plant: str, report_month: str, num_furnaces: int) -> Optional[float]:
    """
    Get per-furnace HM production by dividing plant total by number of furnaces

    This is used as fallback when furnace-wise data is not available

    Returns: HM production per furnace (plant_total / num_furnaces) or None
    """

    plant_hm = get_plant_hm_production(plant, report_month)

    if plant_hm and num_furnaces > 0:
        return plant_hm / num_furnaces

    return None


def get_furnace_production_variants(plant: str, report_month: str, base_name: str) -> dict:
    """
    Get all production variants for a furnace (useful for debugging)

    Returns: {variant_name: value} for all possible name combinations
    """

    variants = {
        'BF-X format': None,
        'BF#X format': None,
        'BF X format': None,
        'BF-X UPPER': None,
        'Plant Total HM': None,
    }

    conn = db.connect()
    cursor = conn.cursor()

    # Try different formats
    patterns = [
        base_name,
        base_name.replace('-', '#'),
        base_name.replace('-', ' '),
        base_name.upper(),
    ]

    for i, pattern in enumerate(patterns):
        cursor.execute("""
            SELECT month_actual FROM production_table
            WHERE plant_name = ? AND item_name = ? AND report_month = ?
        """, [plant, pattern, report_month])

        result = cursor.fetchone()
        if result:
            variants[list(variants.keys())[i]] = float(result[0])

    # Get plant total
    cursor.execute("""
        SELECT month_actual FROM production_table
        WHERE plant_name = ? AND item_name = 'Hot Metal' AND report_month = ?
    """, [plant, report_month])

    result = cursor.fetchone()
    if result:
        variants['Plant Total HM'] = float(result[0])

    conn.close()

    return {k: v for k, v in variants.items() if v is not None}
