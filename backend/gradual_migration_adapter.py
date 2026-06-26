#!/usr/bin/env python3
"""
Gradual Migration Adapter

Inserts data into BOTH old and new table structures simultaneously.
Allows safe transition from old normalized tables to new JSON tables.

Strategy:
  1. All new extractions insert into BOTH old and new tables
  2. Old tables stay functional (no breaking changes)
  3. Gradually migrate old data to new tables
  4. Eventually deprecate old tables when migration complete

Migration Phases:
  Phase 1: Dual insert (current) - both tables populated
  Phase 2: New table primary, old table secondary
  Phase 3: Old tables read-only (archive)
  Phase 4: Remove old tables
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

sys.path.insert(0, 'excel_extractors')

from db import (
    insert_techno_furnace_data,
    insert_old_techno_data,  # Old table insert function (if exists)
    init_db
)
from techno_json_utils import TechnoPlantCalculator
from parameter_naming import normalize_parameter_name

logger = logging.getLogger(__name__)


class DualInsertionAdapter:
    """Insert into both old and new tables during migration"""

    def __init__(self, plant: str, migration_phase: int = 1):
        """
        Initialize adapter

        Args:
            plant: Plant code (BSP, DSP, RSP, etc.)
            migration_phase: 1=dual insert, 2=new primary, 3=old read-only, 4=old removed
        """
        self.plant = plant.upper()
        self.migration_phase = migration_phase
        self.logger = logging.getLogger(f"{__name__}.{plant}")

    def insert_to_both_tables(
        self,
        furnace_data: Dict[str, Dict[str, Any]],
        param_rows: List[Dict],
        report_month: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Insert extracted data into BOTH old and new tables

        Args:
            furnace_data: New JSON format furnace data
            param_rows: Old format parameter rows (from extractor)
            report_month: Report month (YYYY-MM)

        Returns:
            (success, migration_report)
        """

        migration_report = {
            'plant': self.plant,
            'month': report_month,
            'phase': self.migration_phase,
            'timestamp': datetime.now().isoformat(),
            'old_table': {'inserted': 0, 'failed': 0, 'errors': []},
            'new_table': {'inserted': 0, 'failed': 0, 'errors': []},
            'plant_consolidated': False
        }

        print(f"\n{'='*80}")
        print(f"DUAL INSERTION - GRADUAL MIGRATION")
        print(f"{'='*80}")
        print(f"\nPlant: {self.plant}")
        print(f"Month: {report_month}")
        print(f"Migration Phase: {self.migration_phase}")

        # Phase 1 & 2: Insert into both tables
        if self.migration_phase <= 2:
            print(f"\n[STEP 1] Insert into OLD tables (backward compatibility)...")
            self._insert_old_tables(param_rows, report_month, migration_report)

            print(f"\n[STEP 2] Insert into NEW JSON tables (techno_furnace_data)...")
            self._insert_new_tables(furnace_data, report_month, migration_report)

        # Phase 3: Old table read-only
        elif self.migration_phase == 3:
            print(f"\n[WARNING] Phase 3: Old tables are READ-ONLY")
            print(f"[STEP 1] Inserting into NEW JSON tables only...")
            self._insert_new_tables(furnace_data, report_month, migration_report)

        # Phase 4: Old tables removed
        elif self.migration_phase >= 4:
            print(f"\n[INFO] Phase 4: Old tables removed")
            print(f"[STEP 1] Inserting into NEW JSON tables only...")
            self._insert_new_tables(furnace_data, report_month, migration_report)

        # Auto-calculate plant consolidated
        print(f"\n[STEP 3] Calculate plant consolidated...")
        self._calculate_plant_consolidated(report_month, migration_report)

        # Print migration report
        self._print_migration_report(migration_report)

        success = (
            migration_report['old_table']['failed'] == 0 and
            migration_report['new_table']['failed'] == 0
        )

        return success, migration_report

    def _insert_old_tables(
        self,
        param_rows: List[Dict],
        report_month: str,
        migration_report: Dict
    ):
        """Insert into old normalized tables"""

        try:
            # Try to call old insert function if it exists
            from db import insert_old_techno_data

            inserted = 0
            for row in param_rows:
                if row.get('actual') is None:
                    continue

                try:
                    insert_old_techno_data(
                        plant=self.plant,
                        report_month=report_month,
                        parameter=row.get('parameter'),
                        value=row.get('actual'),
                        unit=row.get('unit'),
                        section=row.get('section')
                    )
                    inserted += 1
                except Exception as e:
                    migration_report['old_table']['errors'].append(str(e))
                    migration_report['old_table']['failed'] += 1

            migration_report['old_table']['inserted'] = inserted
            print(f"  ✓ Inserted {inserted} parameters into old tables")

        except ImportError:
            print(f"  ⊘ Old table insert function not available")
            print(f"    (insert_old_techno_data not found in db module)")
            migration_report['old_table']['inserted'] = 0

        except Exception as e:
            print(f"  ✗ Error inserting into old tables: {e}")
            migration_report['old_table']['errors'].append(str(e))
            migration_report['old_table']['failed'] += 1

    def _insert_new_tables(
        self,
        furnace_data: Dict[str, Dict[str, Any]],
        report_month: str,
        migration_report: Dict
    ):
        """Insert into new JSON tables"""

        inserted_count = 0
        failed_count = 0

        for furnace, params in furnace_data.items():
            if not params:
                continue

            try:
                insert_techno_furnace_data(self.plant, furnace, report_month, params)
                print(f"  ✓ {furnace}: {len(params)} parameters")
                inserted_count += 1

            except Exception as e:
                error_msg = f"{furnace}: {str(e)}"
                migration_report['new_table']['errors'].append(error_msg)
                print(f"  ✗ {furnace}: ERROR - {str(e)}")
                failed_count += 1

        migration_report['new_table']['inserted'] = inserted_count
        migration_report['new_table']['failed'] = failed_count

    def _calculate_plant_consolidated(
        self,
        report_month: str,
        migration_report: Dict
    ):
        """Calculate plant consolidated from furnace data"""

        try:
            calc = TechnoPlantCalculator()
            plant_data, calc_details = calc.calculate_plant_consolidated(
                self.plant, report_month
            )

            if plant_data:
                print(f"  ✓ Calculated: {len(plant_data)} parameters")
                migration_report['plant_consolidated'] = True
            else:
                print(f"  ⊘ No data to calculate")

        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")
            migration_report['plant_consolidated'] = False

    def _print_migration_report(self, report: Dict):
        """Print detailed migration report"""

        print(f"\n{'='*80}")
        print(f"MIGRATION REPORT")
        print(f"{'='*80}\n")

        print(f"Plant: {report['plant']}")
        print(f"Month: {report['month']}")
        print(f"Phase: {report['phase']}")
        print(f"Time: {report['timestamp']}\n")

        print("OLD TABLE RESULTS:")
        print(f"  Inserted: {report['old_table']['inserted']}")
        print(f"  Failed: {report['old_table']['failed']}")
        if report['old_table']['errors']:
            for error in report['old_table']['errors'][:3]:
                print(f"    • {error}")

        print("\nNEW TABLE RESULTS (JSON):")
        print(f"  Inserted: {report['new_table']['inserted']}")
        print(f"  Failed: {report['new_table']['failed']}")
        if report['new_table']['errors']:
            for error in report['new_table']['errors'][:3]:
                print(f"    • {error}")

        print(f"\nPlant Consolidated: {'✓ YES' if report['plant_consolidated'] else '✗ NO'}")

        if report['old_table']['failed'] == 0 and report['new_table']['failed'] == 0:
            print(f"\n✓ MIGRATION SUCCESSFUL")
        else:
            print(f"\n⚠️  MIGRATION COMPLETED WITH ERRORS")

        print(f"{'='*80}\n")


class MigrationTracker:
    """Track migration progress"""

    MIGRATION_LOG = Path('backend/migration_log.json')

    @staticmethod
    def log_migration(report: Dict):
        """Log migration in migration log file"""
        import json

        # Load existing log
        if MigrationTracker.MIGRATION_LOG.exists():
            with open(MigrationTracker.MIGRATION_LOG, 'r') as f:
                log = json.load(f)
        else:
            log = {'migrations': []}

        # Add this migration
        log['migrations'].append(report)

        # Save
        with open(MigrationTracker.MIGRATION_LOG, 'w') as f:
            json.dump(log, f, indent=2)

    @staticmethod
    def get_migration_summary() -> Dict:
        """Get summary of all migrations"""
        import json

        if not MigrationTracker.MIGRATION_LOG.exists():
            return {
                'total_migrations': 0,
                'successful': 0,
                'with_errors': 0,
                'plants_migrated': set(),
                'migration_status': {}
            }

        with open(MigrationTracker.MIGRATION_LOG, 'r') as f:
            log = json.load(f)

        migrations = log.get('migrations', [])

        summary = {
            'total_migrations': len(migrations),
            'successful': sum(1 for m in migrations if m['old_table']['failed'] == 0 and m['new_table']['failed'] == 0),
            'with_errors': sum(1 for m in migrations if m['old_table']['failed'] > 0 or m['new_table']['failed'] > 0),
            'plants_migrated': set(),
            'migration_status': {}
        }

        # Group by plant
        for migration in migrations:
            plant = migration['plant']
            summary['plants_migrated'].add(plant)

            if plant not in summary['migration_status']:
                summary['migration_status'][plant] = {
                    'total': 0,
                    'successful': 0,
                    'months': []
                }

            summary['migration_status'][plant]['total'] += 1
            summary['migration_status'][plant]['months'].append(migration['month'])

            if migration['old_table']['failed'] == 0 and migration['new_table']['failed'] == 0:
                summary['migration_status'][plant]['successful'] += 1

        summary['plants_migrated'] = list(summary['plants_migrated'])

        return summary

    @staticmethod
    def print_migration_status():
        """Print migration progress"""
        summary = MigrationTracker.get_migration_summary()

        print(f"\n{'='*80}")
        print(f"MIGRATION STATUS")
        print(f"{'='*80}\n")

        print(f"Total migrations: {summary['total_migrations']}")
        print(f"Successful: {summary['successful']}")
        print(f"With errors: {summary['with_errors']}")
        print(f"Plants migrated: {len(summary['plants_migrated'])}\n")

        for plant in sorted(summary['plants_migrated']):
            status = summary['migration_status'][plant]
            success_rate = (status['successful'] / status['total'] * 100) if status['total'] > 0 else 0
            print(f"{plant}: {status['successful']}/{status['total']} successful ({success_rate:.0f}%)")
            print(f"  Months: {', '.join(sorted(status['months']))}")

        print(f"\n{'='*80}\n")


def dual_extract_and_insert(
    plant: str,
    extractor_type: str,
    excel_file: str,
    report_month: str,
    extractor_module: Any = None,
    auto_insert: bool = False,
    migration_phase: int = 1
) -> bool:
    """
    Main workflow: Extract once, insert to both tables

    Args:
        plant: Plant code
        extractor_type: Extractor type (oisco, techno, etc.)
        excel_file: Excel file path
        report_month: Report month
        extractor_module: Pre-loaded extractor module (optional)
        auto_insert: Auto-insert without confirmation
        migration_phase: Migration phase (1-4)

    Returns:
        Success status
    """

    init_db()

    # Step 1: Extract (once!)
    print(f"\n{'='*80}")
    print(f"EXTRACTION - {plant} {extractor_type.upper()}")
    print(f"{'='*80}")

    if extractor_module is None:
        # Load dynamically
        try:
            module_name = f'excel_extractor_{plant.lower()}_{extractor_type}'
            extractor_module = __import__(module_name)
        except ImportError as e:
            print(f"✗ Could not load extractor: {e}")
            return False

    try:
        result = extractor_module.extract_preview(excel_file, report_month)
        param_rows = result.get('techno_param_rows', [])

        if not param_rows:
            print(f"✗ No parameters extracted")
            return False

        print(f"✓ Extracted {len(param_rows)} parameters\n")

    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        return False

    # Step 2: Convert to new JSON format
    print(f"Converting to JSON format...")

    furnace_data = {}
    for row in param_rows:
        value = row.get('actual')

        if value is None:
            continue

        # Identify furnace
        furnace = _identify_furnace(row)

        # Normalize parameter
        param_name = normalize_parameter_name(row.get('parameter', ''))

        if not param_name or not furnace:
            continue

        if furnace not in furnace_data:
            furnace_data[furnace] = {}

        furnace_data[furnace][param_name] = {
            'value': float(value),
            'unit': row.get('unit', ''),
            'source': 'Excel-Extracted',
            'section': row.get('section', ''),
        }

    print(f"✓ Converted to {sum(len(v) for v in furnace_data.values())} JSON parameters\n")

    # Step 3: Show preview
    print(f"Preview of data to insert:")
    for furnace in sorted(furnace_data.keys()):
        params = furnace_data[furnace]
        print(f"  {furnace}: {len(params)} parameters")

    # Step 4: Confirm
    if not auto_insert:
        response = input(f"\nInsert to both OLD and NEW tables? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Cancelled")
            return False

    # Step 5: Insert to both tables
    adapter = DualInsertionAdapter(plant, migration_phase=migration_phase)
    success, report = adapter.insert_to_both_tables(furnace_data, param_rows, report_month)

    # Step 6: Log migration
    MigrationTracker.log_migration(report)

    return success


def _identify_furnace(row: Dict) -> Optional[str]:
    """Identify furnace from row"""
    param = str(row.get('parameter', '')).upper()
    section = str(row.get('section', '')).upper()
    search_text = param + ' ' + section

    furnace_patterns = {
        'BF-1': ['BF-1', 'BF 1', 'BF#1'],
        'BF-2': ['BF-2', 'BF 2', 'BF#2'],
        'BF-3': ['BF-3', 'BF 3', 'BF#3'],
        'BF-4': ['BF-4', 'BF 4', 'BF#4'],
        'BF-5': ['BF-5', 'BF 5', 'BF#5'],
        'BF-6': ['BF-6', 'BF 6', 'BF#6'],
        'BF-7': ['BF-7', 'BF 7', 'BF#7'],
        'BF-8': ['BF-8', 'BF 8', 'BF#8'],
    }

    for furnace, patterns in furnace_patterns.items():
        for pattern in patterns:
            if pattern in search_text:
                return furnace

    return None


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Gradual Migration Adapter')
    parser.add_argument('--status', action='store_true', help='Show migration status')
    parser.add_argument('--phase', type=int, default=1, help='Migration phase (1-4)')

    args = parser.parse_args()

    if args.status:
        MigrationTracker.print_migration_status()
    else:
        print("Use: python gradual_migration_adapter.py --status")
