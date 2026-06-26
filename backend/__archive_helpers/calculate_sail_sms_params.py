#!/usr/bin/env python3
"""
Calculate SAIL consolidated SMS parameters (Hot Metal Consumption, Scrap Consumption, TMI)
using weighted average by Crude Steel production.

This script computes missing SAIL values and saves them to techno_actuals table.

Usage:
    python calculate_sail_sms_params.py
    python calculate_sail_sms_params.py --month 2026-03
    python calculate_sail_sms_params.py --month 2026-03 --force
"""

import sqlite3
import os
import sys
import argparse
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), "mis_reports.db")

SMS_SHOPS = [
    "BSP SMS-2", "BSP SMS-3", "DSP SMS",
    "RSP SMS-1", "RSP SMS-2",
    "BSL SMS-1", "BSL SMS-2",
    "ISP SMS-1",
]

SMS_SHOP_PLANT = {
    "BSP SMS-2": "BSP", "BSP SMS-3": "BSP", "DSP SMS": "DSP",
    "RSP SMS-1": "RSP", "RSP SMS-2": "RSP",
    "BSL SMS-1": "BSL", "BSL SMS-2": "BSL", "ISP SMS-1": "ISP",
}

SMS_PARAMS = ["Hot Metal Consumption", "Scrap Consumption", "TMI"]


def get_months_to_process(conn, month_filter=None):
    """Get list of months with SMS data."""
    cursor = conn.cursor()

    if month_filter:
        cursor.execute(
            """SELECT DISTINCT report_month
               FROM techno_actuals a
               JOIN techno_param p ON a.param_id = p.param_id
               WHERE p.param_name IN ('Hot Metal Consumption', 'Scrap Consumption', 'TMI')
                 AND a.report_month = ?
               ORDER BY report_month DESC""",
            (month_filter,)
        )
    else:
        cursor.execute(
            """SELECT DISTINCT report_month
               FROM techno_actuals a
               JOIN techno_param p ON a.param_id = p.param_id
               WHERE p.param_name IN ('Hot Metal Consumption', 'Scrap Consumption', 'TMI')
               ORDER BY report_month DESC
               LIMIT 12"""
        )

    return [row[0] for row in cursor.fetchall()]


def get_crude_steel_by_plant(conn, month):
    """Get Crude Steel production by plant for a month."""
    cursor = conn.cursor()
    cursor.execute(
        """SELECT plant_name, month_actual
           FROM production_table
           WHERE item_name = 'Total Crude Steel'
             AND report_month = ?""",
        (month,)
    )

    result = {}
    for plant_name, value in cursor.fetchall():
        if value is not None:
            result[plant_name] = value
    return result


def get_sms_param_values(conn, month, param_name):
    """Get SMS shop values for a parameter."""
    cursor = conn.cursor()
    cursor.execute(
        """SELECT p.row_label, a.actual, a.till_month_actual
           FROM techno_actuals a
           JOIN techno_param p ON a.param_id = p.param_id
           WHERE p.param_name = ?
             AND a.report_month = ?
             AND p.row_label IN ({})""".format(
                 ','.join(['?' for _ in SMS_SHOPS])
             ),
        [param_name, month] + SMS_SHOPS
    )

    result = {}
    for shop, actual, till_month in cursor.fetchall():
        result[shop] = (actual, till_month)
    return result


def calculate_weighted_average(values_by_shop, weights_by_plant):
    """Calculate weighted average for SMS shops by Crude Steel production."""

    # Group values by plant
    by_plant = defaultdict(list)
    for shop in SMS_SHOPS:
        if shop in values_by_shop:
            plant = SMS_SHOP_PLANT[shop]
            actual, till_month = values_by_shop[shop]
            if actual is not None:
                by_plant[plant].append((actual, till_month))

    # Calculate plant average (average of shops in that plant)
    plant_values = {}
    for plant, values in by_plant.items():
        if values:
            avg_actual = sum(v[0] for v in values) / len(values)
            avg_till = sum(v[1] for v in values if v[1] is not None) / len([v for v in values if v[1] is not None]) if any(v[1] is not None for v in values) else None
            plant_values[plant] = (avg_actual, avg_till)

    # Weight by Crude Steel production
    total_cs = sum(weights_by_plant.get(p, 0) for p in plant_values.keys())

    if total_cs == 0:
        return None, None

    weighted_actual = sum(
        plant_values[plant][0] * weights_by_plant.get(plant, 0)
        for plant in plant_values.keys()
    ) / total_cs

    weighted_till = sum(
        plant_values[plant][1] * weights_by_plant.get(plant, 0)
        for plant in plant_values.keys()
        if plant_values[plant][1] is not None
    ) / total_cs if any(plant_values[p][1] is not None for p in plant_values) else None

    return weighted_actual, weighted_till


def get_sail_param_id(conn, param_name):
    """Get param_id for SAIL SMS parameter."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT param_id FROM techno_param WHERE row_label = 'SAIL' AND param_name = ?",
        (param_name,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def save_or_update_sail_value(conn, param_id, month, actual, till_month):
    """Save or update SAIL value in techno_actuals."""
    cursor = conn.cursor()

    # Check if exists
    cursor.execute(
        "SELECT 1 FROM techno_actuals WHERE param_id = ? AND report_month = ?",
        (param_id, month)
    )

    if cursor.fetchone():
        # Update
        cursor.execute(
            """UPDATE techno_actuals
               SET actual = ?, till_month_actual = ?
               WHERE param_id = ? AND report_month = ?""",
            (actual, till_month, param_id, month)
        )
    else:
        # Insert
        cursor.execute(
            """INSERT INTO techno_actuals (param_id, report_month, actual, till_month_actual)
               VALUES (?, ?, ?, ?)""",
            (param_id, month, actual, till_month)
        )

    conn.commit()


def calculate_and_save(conn, month, force=False):
    """Calculate and save SAIL SMS parameters for a month."""

    print(f"\nProcessing month: {month}")
    print("-" * 60)

    # Get Crude Steel weights
    cs_by_plant = get_crude_steel_by_plant(conn, month)
    if not cs_by_plant:
        print(f"  [SKIP] No Crude Steel data for {month}")
        return False

    print(f"  Crude Steel by plant: {cs_by_plant}")

    saved_count = 0

    for param_name in SMS_PARAMS:
        # Get SMS shop values
        shop_values = get_sms_param_values(conn, month, param_name)

        if not shop_values:
            print(f"  [{param_name}] No SMS shop data found")
            continue

        print(f"  [{param_name}] Found {len(shop_values)} shops: ", end="")
        for shop in shop_values:
            print(f"{shop}={shop_values[shop][0]}", end=" | ")
        print()

        # Calculate weighted average
        weighted_actual, weighted_till = calculate_weighted_average(shop_values, cs_by_plant)

        if weighted_actual is None:
            print(f"    [ERROR] Could not calculate weighted average")
            continue

        # Get SAIL param_id
        param_id = get_sail_param_id(conn, param_name)
        if param_id is None:
            print(f"    [ERROR] No SAIL param_id for {param_name}")
            continue

        # Check if exists
        cursor = conn.cursor()
        cursor.execute(
            "SELECT actual FROM techno_actuals WHERE param_id = ? AND report_month = ?",
            (param_id, month)
        )
        existing = cursor.fetchone()

        if existing and not force:
            print(f"    [SKIP] Value already exists: {existing[0]}")
            continue

        # Save
        save_or_update_sail_value(conn, param_id, month, weighted_actual, weighted_till)
        print(f"    [SAVED] Weighted Avg = {weighted_actual:.2f} (YTD: {weighted_till})")
        saved_count += 1

    return saved_count > 0


def main():
    parser = argparse.ArgumentParser(description="Calculate and save SAIL SMS parameters")
    parser.add_argument("--month", help="Specific month (YYYY-MM)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing values")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)

    try:
        months = get_months_to_process(conn, args.month)

        if not months:
            print("No months with SMS data found")
            return False

        print(f"\n{'='*60}")
        print("Calculate SAIL SMS Parameters (Weighted by Crude Steel)")
        print(f"{'='*60}")
        print(f"Processing {len(months)} month(s): {months}")

        total_saved = 0
        for month in months:
            if calculate_and_save(conn, month, args.force):
                total_saved += 1

        print(f"\n{'='*60}")
        print(f"Completed: {total_saved} month(s) processed")
        print(f"{'='*60}")
        return True

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
