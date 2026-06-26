#!/usr/bin/env python3
"""Test the new JSON schema implementation."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import db
import json
import sqlite3

def test_schema_creation():
    """Test that new JSON tables are created."""
    print("=" * 80)
    print("TEST 1: Schema Creation")
    print("=" * 80)

    db.init_db()

    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()

    # Check if new tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_json'")
    tables = [r[0] for r in cursor.fetchall()]

    expected_tables = [
        'production_data_json',
        'production_plan_json',
        'special_steel_json',
        'stock_data_json',
        'ipt_data_json'
    ]

    for table in expected_tables:
        if table in tables:
            print(f"[OK] {table} exists")
        else:
            print(f"[FAIL] {table} NOT FOUND")

    conn.close()
    print()


def test_old_tables():
    """Check what data is in old tables."""
    print("=" * 80)
    print("TEST 2: Existing Data in Old Tables")
    print("=" * 80)

    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM production_table")
        prod_count = cursor.fetchone()[0]
        print(f"production_table: {prod_count} records")
    except Exception as e:
        print(f"production_table: Error - {e}")

    try:
        cursor.execute("SELECT COUNT(*) FROM production_plan_table")
        plan_count = cursor.fetchone()[0]
        print(f"production_plan_table: {plan_count} records")
    except Exception as e:
        print(f"production_plan_table: Error - {e}")

    try:
        cursor.execute("SELECT COUNT(*) FROM special_steel_orders")
        ss_count = cursor.fetchone()[0]
        print(f"special_steel_orders: {ss_count} records")
    except Exception as e:
        print(f"special_steel_orders: Error - {e}")

    try:
        cursor.execute("SELECT COUNT(*) FROM stock_table")
        stock_count = cursor.fetchone()[0]
        print(f"stock_table: {stock_count} records")
    except Exception as e:
        print(f"stock_table: Error - {e}")

    try:
        cursor.execute("SELECT COUNT(*) FROM ipt_table")
        ipt_count = cursor.fetchone()[0]
        print(f"ipt_table: {ipt_count} records")
    except Exception as e:
        print(f"ipt_table: Error - {e}")

    conn.close()
    print()


def test_extraction():
    """Test extraction to JSON."""
    print("=" * 80)
    print("TEST 3: Data Extraction to JSON")
    print("=" * 80)

    from json_extractor_adapter import extract_all_months_to_json

    results = extract_all_months_to_json()

    print(f"Production months: {results['production_months']}")
    print(f"Production plan months: {results['production_plan_months']}")
    print(f"Special steel months: {results['special_steel_months']}")
    print(f"Stock months: {results['stock_months']}")
    print(f"IPT months: {results['ipt_months']}")
    print()


def test_json_data():
    """Test JSON data structure and round-trip."""
    print("=" * 80)
    print("TEST 4: JSON Data Structure & Round-Trip")
    print("=" * 80)

    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()

    # Test production data
    cursor.execute("SELECT report_month, data FROM production_data_json LIMIT 1")
    row = cursor.fetchone()
    if row:
        month, json_str = row
        print(f"\nProduction data ({month}):")
        data = json.loads(json_str)
        print(f"  Type: {type(data)}")
        print(f"  Plants: {list(data.keys())}")
        for plant in list(data.keys())[:1]:
            print(f"  {plant} items: {len(data[plant])}")
            for item in list(data[plant].keys())[:3]:
                print(f"    {item}: {data[plant][item]}")
        print(f"[OK] JSON deserialize OK")
    else:
        print("[FAIL] No production data found")

    # Test special steel data
    cursor.execute("SELECT report_month, data FROM special_steel_json LIMIT 1")
    row = cursor.fetchone()
    if row:
        month, json_str = row
        print(f"\nSpecial Steel data ({month}):")
        data = json.loads(json_str)
        print(f"  Type: {type(data)}")
        print(f"  Plants: {list(data.keys())}")
        for plant in list(data.keys())[:1]:
            print(f"  {plant} records: {len(data[plant])}")
            if data[plant]:
                print(f"    Sample: {data[plant][0]}")
        print(f"[OK] JSON deserialize OK")
    else:
        print("[FAIL] No special steel data found")

    conn.close()
    print()


def test_query_helpers():
    """Test query helper functions."""
    print("=" * 80)
    print("TEST 5: Query Helper Functions")
    print("=" * 80)

    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()

    # Get first available month
    cursor.execute("SELECT report_month FROM production_data_json LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        month = row[0]
        print(f"Testing with month: {month}")

        # Test helper function
        data = db.get_production_data_json(month)
        if data:
            print(f"[OK] get_production_data_json() returned data")
            print(f"  Plants: {list(data.keys())}")
        else:
            print(f"[FAIL] get_production_data_json() returned None")

        plan_data = db.get_production_plan_json(month)
        if plan_data:
            print(f"[OK] get_production_plan_json() returned data")
            print(f"  Plants: {list(plan_data.keys())}")
        else:
            print(f"[FAIL] get_production_plan_json() returned None")
    else:
        print("[FAIL] No months available in database")

    print()


if __name__ == '__main__':
    try:
        test_schema_creation()
        test_old_tables()
        test_extraction()
        test_json_data()
        test_query_helpers()

        print("=" * 80)
        print("[OK] ALL TESTS COMPLETED")
        print("=" * 80)
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
