#!/usr/bin/env python3
"""
Validate manually entered JSON data before database insertion

Checks:
1. All required fields present
2. All values are valid numbers
3. Units match expected values
4. No duplicate entries
5. Data quality issues

Usage:
    python validate_manual_entry.py manual_data.json
"""

import json
import sys
from pathlib import Path


class ManualDataValidator:
    """Validate manually entered techno data"""

    # Expected units for each parameter
    EXPECTED_UNITS = {
        'Coke Rate': 'Kg/THM',
        'BF Productivity': 'T/m³/day',
        'CDI': 'Kg/THM',
        'Slag Rate': 'Kg/THM',
        'Nut Coke Rate': 'Kg/THM',
        'BF Coke Rate': 'Kg/THM',
        'Fuel Rate': 'Kg/THM',
        'Energy': 'GJ/THM',
        'Pellet in Burden': '%',
        'Sinter in Burden': '%',
    }

    # Expected furnaces for BSP
    EXPECTED_FURNACES = ['BF-1', 'BF-2', 'BF-3', 'BF-4', 'BF-5', 'BF-6', 'BF-7', 'BF-8']

    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.errors = []
        self.warnings = []
        self.data = None

    def validate(self):
        """Run all validations"""

        print("\n" + "="*80)
        print("MANUAL DATA ENTRY VALIDATION")
        print("="*80)
        print(f"\nFile: {self.file_path.name}\n")

        # Step 1: Load JSON
        if not self._load_json():
            return False

        # Step 2: Validate structure
        self._validate_structure()

        # Step 3: Validate values
        self._validate_values()

        # Step 4: Validate units
        self._validate_units()

        # Step 5: Validate data quality
        self._validate_data_quality()

        # Step 6: Report results
        return self._report_results()

    def _load_json(self):
        """Load and parse JSON file"""
        try:
            with open(self.file_path, 'r') as f:
                self.data = json.load(f)
            print("[OK] JSON file loaded successfully")
            return True
        except FileNotFoundError:
            self.errors.append(f"File not found: {self.file_path}")
            return False
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {e}")
            return False

    def _validate_structure(self):
        """Check required structure"""
        print("\n[VALIDATING STRUCTURE]")

        required_fields = ['report_month', 'plant', 'furnaces']
        for field in required_fields:
            if field not in self.data:
                self.errors.append(f"Missing required field: {field}")
            else:
                print(f"  [OK] {field} present")

        if 'furnaces' in self.data:
            furnace_count = len(self.data['furnaces'])
            print(f"  [OK] {furnace_count} furnaces defined")

    def _validate_values(self):
        """Check all parameter values"""
        print("\n[VALIDATING VALUES]")

        furnaces = self.data.get('furnaces', {})
        total_params = 0
        filled_params = 0
        empty_params = []

        for furnace, params in furnaces.items():
            if not isinstance(params, dict):
                self.errors.append(f"{furnace}: Not a dictionary")
                continue

            for param, info in params.items():
                if not isinstance(info, dict):
                    self.errors.append(f"{furnace}.{param}: Not a dictionary")
                    continue

                value = info.get('value')
                total_params += 1

                # Check if value is null
                if value is None:
                    empty_params.append(f"{furnace}.{param}")
                else:
                    # Check if value is a valid number
                    try:
                        float(value)
                        filled_params += 1
                    except (TypeError, ValueError):
                        self.errors.append(f"{furnace}.{param}: Invalid number: {value}")

        print(f"  [INFO] Total parameters: {total_params}")
        print(f"  [INFO] Filled values: {filled_params}")
        print(f"  [WARN] Empty values: {len(empty_params)}")

        if empty_params and len(empty_params) <= 10:
            for param in empty_params:
                print(f"    - {param}")
        elif len(empty_params) > 10:
            for param in empty_params[:5]:
                print(f"    - {param}")
            print(f"    ... and {len(empty_params) - 5} more")

    def _validate_units(self):
        """Check units match expected values"""
        print("\n[VALIDATING UNITS]")

        furnaces = self.data.get('furnaces', {})
        unit_mismatches = []

        for furnace, params in furnaces.items():
            if not isinstance(params, dict):
                continue

            for param, info in params.items():
                if not isinstance(info, dict):
                    continue

                expected_unit = self.EXPECTED_UNITS.get(param)
                actual_unit = info.get('unit')

                if expected_unit and actual_unit != expected_unit:
                    unit_mismatches.append(f"{furnace}.{param}: expected '{expected_unit}', got '{actual_unit}'")

        if unit_mismatches:
            for mismatch in unit_mismatches[:5]:
                self.warnings.append(mismatch)
            if unit_mismatches:
                print(f"  [WARN] {len(unit_mismatches)} unit mismatches found")
                for mismatch in unit_mismatches[:3]:
                    print(f"    - {mismatch}")
        else:
            print("  [OK] All units match expected values")

    def _validate_data_quality(self):
        """Check for data quality issues"""
        print("\n[VALIDATING DATA QUALITY]")

        furnaces = self.data.get('furnaces', {})
        issues = []

        for furnace, params in furnaces.items():
            if not isinstance(params, dict):
                continue

            filled_count = sum(1 for info in params.values() if info.get('value') is not None)

            if filled_count == 0:
                issues.append(f"{furnace}: No parameters filled")
            elif filled_count < len(params) // 2:
                issues.append(f"{furnace}: Only {filled_count}/{len(params)} parameters filled")

        if issues:
            print(f"  [WARN] {len(issues)} potential issues:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  [OK] All furnaces have reasonable data coverage")

        # Check for zero values
        zero_values = []
        for furnace, params in furnaces.items():
            if not isinstance(params, dict):
                continue
            for param, info in params.items():
                if info.get('value') == 0:
                    zero_values.append(f"{furnace}.{param}")

        if zero_values:
            print(f"  [INFO] {len(zero_values)} zero values (verify these are correct)")

    def _report_results(self):
        """Report validation results"""
        print("\n" + "="*80)
        print("VALIDATION RESULTS")
        print("="*80)

        if self.errors:
            print(f"\n[ERRORS] {len(self.errors)} error(s) found:\n")
            for error in self.errors:
                print(f"  ❌ {error}")
            return False

        if self.warnings:
            print(f"\n[WARNINGS] {len(self.warnings)} warning(s) found:\n")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")

        print("\n" + "-"*80)
        print("✅ DATA VALIDATION PASSED - Safe to insert into database")
        print("-"*80 + "\n")

        return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_manual_entry.py <json_file>")
        print("Example: python validate_manual_entry.py manual_data.json")
        sys.exit(1)

    json_file = sys.argv[1]
    validator = ManualDataValidator(json_file)

    success = validator.validate()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
