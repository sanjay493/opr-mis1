#!/usr/bin/env python3
"""
Populate New JSON Schema

Workflow:
  1. Initialize database (create new JSON tables)
  2. Extract all data from old tables to new JSON tables
  3. Verify extraction completeness
  4. Generate extraction report
"""

import sys
import os
import logging
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

import db
from json_extractor_adapter import extract_all_months_to_json
import sqlite3
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("populate_json_schema")


def initialize_schema():
    """Initialize the database and create new JSON tables."""
    logger.info("Initializing database schema...")
    db.init_db()
    logger.info("✓ Database schema initialized")


def verify_extraction():
    """Verify that all data was extracted correctly."""
    logger.info("\nVerifying extraction...")

    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()

    stats = {}

    # Check production data
    cursor.execute("SELECT COUNT(*) FROM production_data_json")
    prod_count = cursor.fetchone()[0]
    stats['production_records'] = prod_count
    logger.info(f"  Production data: {prod_count} records")

    # Check production plans
    cursor.execute("SELECT COUNT(*) FROM production_plan_json")
    plan_count = cursor.fetchone()[0]
    stats['plan_records'] = plan_count
    logger.info(f"  Production plans: {plan_count} records")

    # Check special steel
    cursor.execute("SELECT COUNT(*) FROM special_steel_json")
    ss_count = cursor.fetchone()[0]
    stats['special_steel_records'] = ss_count
    logger.info(f"  Special steel: {ss_count} records")

    # Check stock
    cursor.execute("SELECT COUNT(*) FROM stock_data_json")
    stock_count = cursor.fetchone()[0]
    stats['stock_records'] = stock_count
    logger.info(f"  Stock data: {stock_count} records")

    # Check IPT
    cursor.execute("SELECT COUNT(*) FROM ipt_data_json")
    ipt_count = cursor.fetchone()[0]
    stats['ipt_records'] = ipt_count
    logger.info(f"  IPT data: {ipt_count} records")

    # Check distinct months
    cursor.execute("SELECT COUNT(DISTINCT report_month) FROM production_data_json")
    prod_months = cursor.fetchone()[0]
    logger.info(f"\n  Production data months: {prod_months}")

    cursor.execute("SELECT COUNT(DISTINCT report_month) FROM production_plan_json")
    plan_months = cursor.fetchone()[0]
    logger.info(f"  Production plan months: {plan_months}")

    cursor.execute("SELECT COUNT(DISTINCT report_month) FROM special_steel_json")
    ss_months = cursor.fetchone()[0]
    logger.info(f"  Special steel months: {ss_months}")

    cursor.execute("SELECT COUNT(DISTINCT stock_month) FROM stock_data_json")
    stock_months = cursor.fetchone()[0]
    logger.info(f"  Stock months: {stock_months}")

    cursor.execute("SELECT COUNT(DISTINCT report_month) FROM ipt_data_json")
    ipt_months = cursor.fetchone()[0]
    logger.info(f"  IPT months: {ipt_months}")

    conn.close()

    stats['production_months'] = prod_months
    stats['plan_months'] = plan_months
    stats['ss_months'] = ss_months
    stats['stock_months'] = stock_months
    stats['ipt_months'] = ipt_months

    return stats


def sample_json_data():
    """Sample some JSON data to verify structure."""
    logger.info("\nSampling JSON data structure...")

    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()

    # Sample production data
    cursor.execute("SELECT report_month, data FROM production_data_json LIMIT 1")
    row = cursor.fetchone()
    if row:
        month, data = row
        logger.info(f"\n  Production data sample ({month}):")
        data_dict = json.loads(data)
        for plant, items in list(data_dict.items())[:1]:
            logger.info(f"    {plant}: {len(items)} items")
            for item, value in list(items.items())[:3]:
                logger.info(f"      {item}: {value}")

    # Sample special steel
    cursor.execute("SELECT report_month, data FROM special_steel_json LIMIT 1")
    row = cursor.fetchone()
    if row:
        month, data = row
        logger.info(f"\n  Special steel sample ({month}):")
        data_dict = json.loads(data)
        for plant, records in list(data_dict.items())[:1]:
            logger.info(f"    {plant}: {len(records)} records")
            if records:
                logger.info(f"      {records[0]}")

    conn.close()


def main():
    """Main execution."""
    logger.info("=" * 80)
    logger.info("POPULATE NEW JSON SCHEMA")
    logger.info("=" * 80)

    try:
        # Step 1: Initialize schema
        initialize_schema()

        # Step 2: Extract all data
        logger.info("\nExtracting all data from old tables to new JSON tables...")
        results = extract_all_months_to_json()

        logger.info(f"\nExtraction Results:")
        logger.info(f"  Production months extracted: {results['production_months']}")
        logger.info(f"  Production plan months extracted: {results['production_plan_months']}")
        logger.info(f"  Special steel months extracted: {results['special_steel_months']}")
        logger.info(f"  Stock months extracted: {results['stock_months']}")
        logger.info(f"  IPT months extracted: {results['ipt_months']}")

        # Step 3: Verify extraction
        stats = verify_extraction()

        # Step 4: Sample data
        sample_json_data()

        # Step 5: Summary
        logger.info("\n" + "=" * 80)
        logger.info("✓ POPULATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"\nNew JSON Schema Statistics:")
        logger.info(f"  Total production records: {stats['production_records']}")
        logger.info(f"  Total plan records: {stats['plan_records']}")
        logger.info(f"  Total special steel records: {stats['special_steel_records']}")
        logger.info(f"  Total stock records: {stats['stock_records']}")
        logger.info(f"  Total IPT records: {stats['ipt_records']}")
        logger.info(f"\n  Total records across all tables: {sum([v for k, v in stats.items() if k.endswith('_records')])}")

        return 0

    except Exception as e:
        logger.error(f"✗ POPULATION FAILED: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
