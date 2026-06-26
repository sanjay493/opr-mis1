#!/usr/bin/env python3
"""
Batch Automation - Run extractions automatically for all plants

Features:
1. Auto-detect mappings for all Excel files
2. Extract all plants in one command
3. Schedule daily/weekly runs
4. Log all extractions

Usage:
    python batch_automation.py auto-detect   # Generate all mappings
    python batch_automation.py extract       # Extract all plants
    python batch_automation.py setup-daily   # Schedule daily extraction
"""

import json
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple


class BatchAutomationConfig:
    """Manage batch automation configuration"""

    CONFIG_FILE = Path('backend/batch_automation_config.json')

    DEFAULT_CONFIG = {
        "enabled": True,
        "excel_folder": "Report_format/Monthly",
        "output_folder": "backend",
        "log_folder": "backend/logs",
        "schedule": {
            "enabled": False,
            "frequency": "daily",  # daily, weekly, monthly
            "time": "09:00",
            "day_of_week": None,  # 0=Monday, 6=Sunday (for weekly)
            "day_of_month": None,  # 1-31 (for monthly)
        },
        "extraction": {
            "auto_insert": False,  # Require confirmation before insert
            "verify": True,        # Verify after insert
            "notify": False,       # Send notifications
        },
        "plants": [
            {"code": "BSP", "enabled": True},
            {"code": "DSP", "enabled": True},
            {"code": "RSP", "enabled": True},
            {"code": "BSL", "enabled": True},
            {"code": "ISP", "enabled": True},
        ]
    }

    @staticmethod
    def load_or_create():
        """Load config or create default"""
        if BatchAutomationConfig.CONFIG_FILE.exists():
            with open(BatchAutomationConfig.CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            return BatchAutomationConfig.DEFAULT_CONFIG

    @staticmethod
    def save(config: Dict):
        """Save config to file"""
        BatchAutomationConfig.CONFIG_FILE.parent.mkdir(exist_ok=True)
        with open(BatchAutomationConfig.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✓ Config saved: {BatchAutomationConfig.CONFIG_FILE}")


class BatchExtractor:
    """Extract from all plants in batch"""

    def __init__(self, config: Dict):
        self.config = config
        self.log_folder = Path(config['log_folder'])
        self.log_folder.mkdir(parents=True, exist_ok=True)
        self.setup_logging()

    def setup_logging(self):
        """Setup logging to file"""
        log_file = self.log_folder / f"extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

        self.logger = logging.getLogger(__name__)
        self.logger.info("Batch extraction started")

    def extract_all_plants(self) -> Dict[str, bool]:
        """
        Extract from all enabled plants

        Returns:
            {plant: success, ...}
        """
        print("\n" + "="*80)
        print("BATCH EXTRACTION")
        print("="*80)

        results = {}

        for plant_config in self.config['plants']:
            plant_code = plant_config['code']

            if not plant_config.get('enabled', True):
                print(f"\n{plant_code}: SKIPPED (disabled)")
                results[plant_code] = None
                continue

            print(f"\n{plant_code}: ", end="")

            # Find mapping file
            mapping_file = Path('backend') / f"{plant_code.lower()}_auto_mapping.json"

            if not mapping_file.exists():
                print(f"✗ Mapping not found: {mapping_file.name}")
                self.logger.warning(f"{plant_code}: Mapping file not found")
                results[plant_code] = False
                continue

            # Run extraction
            try:
                cmd = [
                    sys.executable,
                    'backend/extract_and_insert.py',
                    str(mapping_file),
                    '--no-confirm' if self.config['extraction']['auto_insert'] else ''
                ]

                # Remove empty strings
                cmd = [c for c in cmd if c]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=Path.cwd()
                )

                if result.returncode == 0:
                    print("✓ SUCCESS")
                    self.logger.info(f"{plant_code}: Extraction successful")
                    results[plant_code] = True
                else:
                    print(f"✗ FAILED")
                    print(f"  Error: {result.stderr}")
                    self.logger.error(f"{plant_code}: {result.stderr}")
                    results[plant_code] = False

            except Exception as e:
                print(f"✗ ERROR: {e}")
                self.logger.error(f"{plant_code}: {str(e)}")
                results[plant_code] = False

        # Summary
        self._print_summary(results)

        return results

    def _print_summary(self, results: Dict[str, bool]):
        """Print extraction summary"""
        print("\n" + "="*80)
        print("BATCH EXTRACTION SUMMARY")
        print("="*80 + "\n")

        success_count = sum(1 for v in results.values() if v is True)
        failed_count = sum(1 for v in results.values() if v is False)
        skipped_count = sum(1 for v in results.values() if v is None)

        print(f"Success: {success_count}")
        print(f"Failed:  {failed_count}")
        print(f"Skipped: {skipped_count}")
        print(f"Total:   {len(results)}\n")

        for plant, success in sorted(results.items()):
            if success is True:
                print(f"  ✓ {plant}")
            elif success is False:
                print(f"  ✗ {plant}")
            else:
                print(f"  ⊘ {plant}")


class AutoDetectBatch:
    """Auto-detect mappings for all plants"""

    def __init__(self, config: Dict):
        self.config = config

    def detect_all(self) -> int:
        """
        Auto-detect mappings for all plants

        Returns:
            Number of mappings created
        """
        print("\n" + "="*80)
        print("AUTO-DETECT BATCH")
        print("="*80)

        cmd = [
            sys.executable,
            'backend/auto_cell_detector.py',
            '--batch',
            self.config['excel_folder']
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )

            print(result.stdout)

            if result.returncode == 0:
                print("\n✓ Auto-detection complete")
                return 0
            else:
                print(f"\n✗ Auto-detection failed")
                print(result.stderr)
                return 1

        except Exception as e:
            print(f"✗ Error: {e}")
            return 1


class SchedulingSetup:
    """Setup scheduled extractions (Windows Task Scheduler)"""

    @staticmethod
    def setup_daily_windows():
        """Setup daily extraction on Windows Task Scheduler"""
        print("\n" + "="*80)
        print("SETUP DAILY EXTRACTION (Windows Task Scheduler)")
        print("="*80 + "\n")

        task_name = "SAIL_MIS_Techno_Extraction"
        script_path = Path.cwd() / "backend" / "batch_automation.py"
        python_exe = sys.executable

        # Create batch file wrapper
        batch_file = Path.cwd() / "run_extraction.bat"
        batch_content = f"""@echo off
cd {Path.cwd()}
{python_exe} backend\\batch_automation.py extract
"""
        batch_file.write_text(batch_content)

        print(f"Created wrapper script: {batch_file.name}")
        print(f"\nTo schedule daily extraction at 9:00 AM:")
        print(f"\n1. Open Task Scheduler (Win+R → taskschd.msc)")
        print(f"2. Right-click Task Scheduler Library → New Task")
        print(f"3. General tab:")
        print(f"   - Name: {task_name}")
        print(f"   - Description: Auto-extract techno data from Excel")
        print(f"   - Run with highest privileges: ✓")
        print(f"\n4. Triggers tab:")
        print(f"   - New → Daily")
        print(f"   - Time: 09:00:00")
        print(f"   - Every 1 day")
        print(f"\n5. Actions tab:")
        print(f"   - Program: {batch_file}")
        print(f"   - Start in: {Path.cwd()}")
        print(f"\n6. Click OK and enter your Windows password")

        print(f"\n{'='*80}")
        print("✓ Manual setup steps above")
        print("="*80)

        print(f"\nAlternatively, run this PowerShell command as Administrator:")
        print(f"\nRegister-ScheduledTask -TaskName '{task_name}' \\")
        print(f"  -Trigger (New-ScheduledTaskTrigger -Daily -At 09:00) \\")
        print(f"  -Action (New-ScheduledTaskAction -Execute '{batch_file.absolute()}') \\")
        print(f"  -Force")


def main():
    if len(sys.argv) < 2:
        print("Usage: python batch_automation.py <command>")
        print("\nCommands:")
        print("  auto-detect     Auto-detect mappings for all plants")
        print("  extract         Extract from all plants")
        print("  setup-daily     Setup daily scheduled extraction")
        print("  config          Show configuration")
        print("  config-edit     Edit configuration")
        sys.exit(1)

    command = sys.argv[1]
    config = BatchAutomationConfig.load_or_create()

    if command == 'auto-detect':
        detector = AutoDetectBatch(config)
        sys.exit(detector.detect_all())

    elif command == 'extract':
        extractor = BatchExtractor(config)
        results = extractor.extract_all_plants()
        all_success = all(v is True for v in results.values())
        sys.exit(0 if all_success else 1)

    elif command == 'setup-daily':
        SchedulingSetup.setup_daily_windows()

    elif command == 'config':
        print("\n" + "="*80)
        print("BATCH AUTOMATION CONFIG")
        print("="*80 + "\n")
        print(json.dumps(config, indent=2))

    elif command == 'config-edit':
        print("\n" + "="*80)
        print("EDIT CONFIGURATION")
        print("="*80 + "\n")

        # Simple edit interface
        print("Configuration options:")
        print("  1. Enable/disable plants")
        print("  2. Setup daily schedule")
        print("  3. Configure auto-insert")
        print("  4. Reset to defaults\n")

        option = input("Choose option (1-4): ").strip()

        if option == '1':
            print("\nPlants:")
            for i, plant_config in enumerate(config['plants']):
                plant_code = plant_config['code']
                enabled = plant_config.get('enabled', True)
                status = "✓" if enabled else "✗"
                print(f"  {i+1}. {status} {plant_code}")

            plant_to_toggle = input("\nEnter plant number to toggle (or press Enter to skip): ").strip()
            if plant_to_toggle.isdigit():
                idx = int(plant_to_toggle) - 1
                if 0 <= idx < len(config['plants']):
                    config['plants'][idx]['enabled'] = not config['plants'][idx]['enabled']
                    BatchAutomationConfig.save(config)

        elif option == '2':
            config['schedule']['enabled'] = True
            config['schedule']['frequency'] = 'daily'
            config['schedule']['time'] = '09:00'
            BatchAutomationConfig.save(config)
            print("✓ Daily schedule enabled at 09:00")

        elif option == '3':
            config['extraction']['auto_insert'] = not config['extraction']['auto_insert']
            BatchAutomationConfig.save(config)
            status = "enabled" if config['extraction']['auto_insert'] else "disabled"
            print(f"✓ Auto-insert {status}")

        elif option == '4':
            config = BatchAutomationConfig.DEFAULT_CONFIG
            BatchAutomationConfig.save(config)
            print("✓ Reset to defaults")


if __name__ == '__main__':
    main()
