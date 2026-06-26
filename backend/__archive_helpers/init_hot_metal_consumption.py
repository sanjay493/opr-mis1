#!/usr/bin/env python3
"""
Initialize "Hot Metal Consumption" techno-economic parameters in the database.

This script creates techno_param entries for Hot Metal Consumption tracking
across plants and their blast furnaces.

Usage:
    python init_hot_metal_consumption.py
"""

import sqlite3
import os
from constants import ALL_PLANTS

DB_PATH = os.path.join(os.path.dirname(__file__), "mis_reports.db")

# Define Hot Metal Consumption parameters
# Format: (param_name, row_label, unit, group_code, sort_order)
HOT_METAL_CONSUMPTION_PARAMS = [
    # Major SAIL-wide parameter
    ("Hot Metal Consumption", "SAIL", "T", "MAJOR", 100),

    # Plant-level summaries
    ("Hot Metal Consumption", "BSP", "T", "IRON_MAKING", 101),
    ("Hot Metal Consumption", "DSP", "T", "IRON_MAKING", 102),
    ("Hot Metal Consumption", "RSP", "T", "IRON_MAKING", 103),
    ("Hot Metal Consumption", "BSL", "T", "IRON_MAKING", 104),
    ("Hot Metal Consumption", "ISP", "T", "IRON_MAKING", 105),

    # Shop-level (if available)
    ("Hot Metal Consumption", "BSP Blast Furnace", "T", "IRON_MAKING", 106),
    ("Hot Metal Consumption", "DSP Blast Furnace", "T", "IRON_MAKING", 107),
    ("Hot Metal Consumption", "RSP Blast Furnace", "T", "IRON_MAKING", 108),
]

def init_hot_metal_consumption():
    """Create Hot Metal Consumption parameter entries in the database."""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='techno_param'"
        )
        if not cursor.fetchone():
            print("Error: techno_param table does not exist. Run init_db() first.")
            return False

        inserted = 0
        skipped = 0

        for param_name, row_label, unit, group_code, sort_order in HOT_METAL_CONSUMPTION_PARAMS:
            try:
                # Check if parameter already exists
                cursor.execute(
                    "SELECT param_id FROM techno_param WHERE param_name=? AND row_label=?",
                    (param_name, row_label)
                )

                if cursor.fetchone():
                    print(f"[OK] Already exists: {param_name} -> {row_label}")
                    skipped += 1
                    continue

                # Insert new parameter
                cursor.execute(
                    """INSERT INTO techno_param (param_name, row_label, unit, sort_order)
                       VALUES (?, ?, ?, ?)""",
                    (param_name, row_label, unit, sort_order)
                )
                param_id = cursor.lastrowid

                # Add to group
                cursor.execute(
                    """INSERT OR IGNORE INTO techno_param_group (param_id, group_code)
                       VALUES (?, ?)""",
                    (param_id, group_code)
                )

                print(f"[+] Created: {param_name} -> {row_label} ({unit}) [ID: {param_id}]")
                inserted += 1

            except sqlite3.IntegrityError as e:
                print(f"[!] Duplicate or constraint error: {param_name} -> {row_label}")
                skipped += 1
                continue

        conn.commit()
        print(f"\n[SUCCESS] Initialization complete:")
        print(f"   Inserted: {inserted}")
        print(f"   Skipped (already exist): {skipped}")
        return True

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = init_hot_metal_consumption()
    exit(0 if success else 1)
