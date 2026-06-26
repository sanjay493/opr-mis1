#!/usr/bin/env python3
"""
JSON Extractor Adapter

Wraps existing extractors to serialize their output to the new JSON schema.
Reuses all existing extraction logic without modification.

Workflow:
  1. Call existing extractor function
  2. Format output as JSON
  3. Insert into new JSON tables
"""

import sys
import os
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

import db

logger = logging.getLogger("json_extractor_adapter")


class ProductionDataAccumulator:
    """Accumulates production data from old normalized format to JSON."""

    def __init__(self):
        self.data: Dict[str, Dict[str, float]] = {}  # {plant: {item: value}}

    def add_record(self, plant_name: str, item_name: str, value: Optional[float]):
        """Add a production record."""
        if plant_name not in self.data:
            self.data[plant_name] = {}
        self.data[plant_name][item_name] = value

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.data, indent=2)

    def get_dict(self) -> Dict:
        """Get as dict (for testing)."""
        return self.data


class SpecialSteelAccumulator:
    """Accumulates special steel orders from old normalized format to JSON."""

    def __init__(self):
        self.data: Dict[str, List[Dict]] = {}  # {plant: [records]}

    def add_record(self, plant_name: str, product: str, quality_grade: str,
                   section: str, sort_order: int, order_qty: Optional[float],
                   actual_despatch: Optional[float]):
        """Add a special steel record."""
        if plant_name not in self.data:
            self.data[plant_name] = []
        self.data[plant_name].append({
            'product': product,
            'quality_grade': quality_grade,
            'section': section,
            'sort_order': sort_order,
            'order_qty': order_qty,
            'actual_despatch': actual_despatch
        })

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.data, indent=2)

    def get_dict(self) -> Dict:
        """Get as dict."""
        return self.data


class StockDataAccumulator:
    """Accumulates stock data from old normalized format to JSON."""

    def __init__(self):
        self.data: Dict[str, Dict[str, Dict[str, float]]] = {}  # {plant: {item_type: {stock_type: value}}}

    def add_record(self, plant_name: str, item_type: str, stock_type: str, stock: Optional[float]):
        """Add a stock record."""
        if plant_name not in self.data:
            self.data[plant_name] = {}
        if item_type not in self.data[plant_name]:
            self.data[plant_name][item_type] = {}
        self.data[plant_name][item_type][stock_type] = stock

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.data, indent=2)

    def get_dict(self) -> Dict:
        """Get as dict."""
        return self.data


class IPTDataAccumulator:
    """Accumulates IPT data from old normalized format to JSON."""

    def __init__(self):
        self.data: Dict[str, List[Dict]] = {}  # {item: [records]}

    def add_record(self, item: str, from_plant: str, to_plant: str, unit: str,
                   sort_order: int, plan: Optional[float], actual: Optional[float],
                   plan_tonnage: Optional[float], actual_tonnage: Optional[float]):
        """Add an IPT record."""
        if item not in self.data:
            self.data[item] = []
        self.data[item].append({
            'from_plant': from_plant,
            'to_plant': to_plant,
            'unit': unit,
            'sort_order': sort_order,
            'plan': plan,
            'actual': actual,
            'plan_tonnage': plan_tonnage,
            'actual_tonnage': actual_tonnage
        })

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.data, indent=2)

    def get_dict(self) -> Dict:
        """Get as dict."""
        return self.data


# ============================================================================
# Extraction wrappers that read from old tables and write to new JSON tables
# ============================================================================

def extract_production_to_json(report_month: str) -> bool:
    """Extract production actuals from old table to new JSON table."""
    try:
        db.init_db()

        # Query old table
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT plant_name, item_name, month_actual FROM production_table WHERE report_month = ?",
            (report_month,)
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            logger.warning(f"No production data found for {report_month}")
            return False

        # Accumulate to JSON format
        acc = ProductionDataAccumulator()
        for plant, item, value in rows:
            acc.add_record(plant, item, value)

        # Insert to new JSON table
        success = db.insert_production_data_json(report_month, acc.get_dict(), source='migrated')
        if success:
            logger.info(f"Extracted production data for {report_month}: {len(rows)} records")
        return success

    except Exception as e:
        logger.error(f"Error extracting production data: {e}")
        return False


def extract_production_plan_to_json(report_month: str) -> bool:
    """Extract production plans from old table to new JSON table."""
    try:
        db.init_db()

        # Query old table
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT plant_name, item_name, month_actual FROM production_plan_table WHERE report_month = ?",
            (report_month,)
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            logger.warning(f"No production plan data found for {report_month}")
            return False

        # Accumulate to JSON format
        acc = ProductionDataAccumulator()
        for plant, item, value in rows:
            acc.add_record(plant, item, value)

        # Insert to new JSON table
        success = db.insert_production_plan_json(report_month, acc.get_dict(), source='migrated')
        if success:
            logger.info(f"Extracted production plan data for {report_month}: {len(rows)} records")
        return success

    except Exception as e:
        logger.error(f"Error extracting production plan data: {e}")
        return False


def extract_special_steel_to_json(report_month: str) -> bool:
    """Extract special steel orders from old table to new JSON table."""
    try:
        db.init_db()

        # Query old table
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plant_name, product, quality_grade, section, sort_order, order_qty, actual_despatch
            FROM special_steel_orders WHERE report_month = ?
        """, (report_month,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            logger.warning(f"No special steel data found for {report_month}")
            return False

        # Accumulate to JSON format
        acc = SpecialSteelAccumulator()
        for plant, product, grade, section, sort_order, qty, despatch in rows:
            acc.add_record(plant, product, grade, section, sort_order, qty, despatch)

        # Insert to new JSON table
        success = db.insert_special_steel_json(report_month, acc.get_dict(), source='migrated')
        if success:
            logger.info(f"Extracted special steel data for {report_month}: {len(rows)} records")
        return success

    except Exception as e:
        logger.error(f"Error extracting special steel data: {e}")
        return False


def extract_stock_to_json(stock_month: str) -> bool:
    """Extract stock data from old table to new JSON table."""
    try:
        db.init_db()

        # Query old table
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plant_name, item_type, stock_type, stock
            FROM stock_table WHERE stock_month = ?
        """, (stock_month,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            logger.warning(f"No stock data found for {stock_month}")
            return False

        # Accumulate to JSON format
        acc = StockDataAccumulator()
        for plant, item_type, stock_type, stock in rows:
            acc.add_record(plant, item_type, stock_type, stock)

        # Insert to new JSON table
        success = db.insert_stock_data_json(stock_month, acc.get_dict(), source='migrated')
        if success:
            logger.info(f"Extracted stock data for {stock_month}: {len(rows)} records")
        return success

    except Exception as e:
        logger.error(f"Error extracting stock data: {e}")
        return False


def extract_ipt_to_json(report_month: str) -> bool:
    """Extract IPT data from old table to new JSON table."""
    try:
        db.init_db()

        # Query old table
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT item, from_plant, to_plant, unit, sort_order, plan, actual, plan_tonnage, actual_tonnage
            FROM ipt_table WHERE report_month = ?
        """, (report_month,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            logger.warning(f"No IPT data found for {report_month}")
            return False

        # Accumulate to JSON format
        acc = IPTDataAccumulator()
        for item, from_plant, to_plant, unit, sort_order, plan, actual, plan_tonnage, actual_tonnage in rows:
            acc.add_record(item, from_plant, to_plant, unit, sort_order, plan, actual, plan_tonnage, actual_tonnage)

        # Insert to new JSON table
        success = db.insert_ipt_data_json(report_month, acc.get_dict(), source='migrated')
        if success:
            logger.info(f"Extracted IPT data for {report_month}: {len(rows)} records")
        return success

    except Exception as e:
        logger.error(f"Error extracting IPT data: {e}")
        return False


# ============================================================================
# Bulk extraction for all available months
# ============================================================================

def extract_all_months_to_json() -> Dict[str, int]:
    """Extract all data from old tables to new JSON tables."""
    import sqlite3

    db.init_db()
    results = {
        'production_months': 0,
        'production_plan_months': 0,
        'special_steel_months': 0,
        'stock_months': 0,
        'ipt_months': 0,
        'total_records': 0
    }

    try:
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()

        # Get unique months from old tables
        cursor.execute("SELECT DISTINCT report_month FROM production_table ORDER BY report_month")
        prod_months = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT report_month FROM production_plan_table ORDER BY report_month")
        plan_months = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT report_month FROM special_steel_orders ORDER BY report_month")
        ss_months = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT stock_month FROM stock_table ORDER BY stock_month")
        stock_months = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT report_month FROM ipt_table ORDER BY report_month")
        ipt_months = [r[0] for r in cursor.fetchall()]

        conn.close()

        # Extract each month
        for month in prod_months:
            if extract_production_to_json(month):
                results['production_months'] += 1

        for month in plan_months:
            if extract_production_plan_to_json(month):
                results['production_plan_months'] += 1

        for month in ss_months:
            if extract_special_steel_to_json(month):
                results['special_steel_months'] += 1

        for month in stock_months:
            if extract_stock_to_json(month):
                results['stock_months'] += 1

        for month in ipt_months:
            if extract_ipt_to_json(month):
                results['ipt_months'] += 1

        logger.info(f"Bulk extraction complete: {results}")
        return results

    except Exception as e:
        logger.error(f"Error in bulk extraction: {e}")
        return results


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    results = extract_all_months_to_json()
    print(f"\nExtraction Summary:")
    print(f"  Production months: {results['production_months']}")
    print(f"  Production plan months: {results['production_plan_months']}")
    print(f"  Special steel months: {results['special_steel_months']}")
    print(f"  Stock months: {results['stock_months']}")
    print(f"  IPT months: {results['ipt_months']}")
