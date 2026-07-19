"""
Utilities for JSON-based techno data extraction and calculation
Handles furnace-wise data, HM production weighting, and plant consolidation
"""

import sqlite3
import json
from typing import Dict, List, Any, Optional, Tuple
from db import DB_PATH, insert_techno_furnace_data, insert_techno_plant_data, get_techno_furnace_data
from production_utils import get_hm_production_for_furnace, get_plant_hm_production


class TechnoFurnaceExtractor:
    """Base class for extracting furnace-wise techno data from PDF/Excel"""

    PARAM_UNITS = {
        # Standard blast furnace parameters
        'Coke Rate': 'Kg/THM',
        'BF Productivity': 'T/m³/day',
        'CDI Rate': 'Kg/THM',
        'Fuel Rate': 'Kg/THM',
        'O2 Enrichment': '%',
        'Sinter in Burden': '%',
        'Pellet in Burden': '%',
        'BF Coke Rate': 'Kg/THM',
        'Slag Rate': 'Kg/THM',
        'Hot Blast Temp': '°C',

        # SMS parameters
        'SMS Productivity': 'T/hr',
        'Oxygen Consumption': 'm³/THM',
        'Refractory Consumption': 'Kg/THM',

        # Weight for calculation (IMPORTANT!)
        'HM Production': 'T',
    }

    def __init__(self, plant: str):
        self.plant = plant

    def extract_furnace_data(self, pdf_rows, report_month: str) -> List[Dict[str, Any]]:
        """
        Extract furnace-level data from PDF/Excel rows

        Returns: List of furnace records
        [{
            'plant': 'BSP',
            'furnace': 'BF-1',
            'report_month': '2026-06',
            'data': {
                'Coke Rate': {'value': 300.0, 'unit': 'Kg/THM'},
                'HM Production': {'value': 10000.0, 'unit': 'T', 'source': 'PDF'}
            }
        }, ...]
        """
        furnaces = self._identify_furnaces(pdf_rows)
        furnace_records = []

        for furnace in furnaces:
            data = {}

            for param, unit in self.PARAM_UNITS.items():
                value = self._extract_param_for_furnace(pdf_rows, furnace, param)

                if value is not None:
                    data[param] = {
                        'value': float(value),
                        'unit': unit,
                        'source': 'PDF'
                    }

            # If HM Production not extracted, try to fetch from production_table
            if 'HM Production' not in data:
                hm_value = get_hm_production_for_furnace(self.plant, furnace, report_month)
                if hm_value:
                    data['HM Production'] = {
                        'value': hm_value,
                        'unit': 'T',
                        'source': 'production_table'
                    }

            furnace_record = {
                'plant': self.plant,
                'furnace': furnace,
                'report_month': report_month,
                'data': data
            }

            furnace_records.append(furnace_record)

        return furnace_records

    def save_furnace_data(self, furnace_records: List[Dict[str, Any]]):
        """Save extracted furnace records to database"""
        for record in furnace_records:
            insert_techno_furnace_data(
                plant=record['plant'],
                furnace=record['furnace'],
                report_month=record['report_month'],
                data=record['data']
            )

    def _identify_furnaces(self, pdf_rows) -> List[str]:
        """Override in subclass to identify furnaces from PDF"""
        raise NotImplementedError

    def _extract_param_for_furnace(self, pdf_rows, furnace: str, param: str) -> Optional[float]:
        """Override in subclass to extract specific parameter for furnace"""
        raise NotImplementedError


class TechnoPlantCalculator:
    """Calculate plant-level consolidated data from furnace-wise data"""

    PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']

    def calculate_plant_consolidated(self, plant: str, report_month: str) -> Tuple[Dict, Dict]:
        """
        Calculate plant-level consolidated data from furnace data

        Priority:
        1. Check legacy/old data in techno_actuals (if exists, use that)
        2. Calculate from furnace data (if no legacy data)

        Args:
            plant: "BSP", "DSP", etc.
            report_month: "2026-06"

        Returns: (plant_data, calculation_details)
            plant_data: {param: {value, unit, calculation_method, furnaces_used}}
            calculation_details: {param: {formula, furnaces, total_weight, ...}}
        """

        # Get all furnace data for this plant-month
        furnace_data = get_techno_furnace_data(plant, report_month)

        if not furnace_data:
            return {}, {}

        plant_data = {}
        calculation_details = {}

        # Get all unique parameters across all furnaces
        all_params = set()
        for f_data in furnace_data.values():
            all_params.update(f_data.keys())

        # Process each parameter
        for param in sorted(all_params):
            if param == 'HM Production':
                # Don't include HM Production in final plant data
                continue

            result = self._calculate_parameter(plant, param, furnace_data, report_month)

            if result:
                value, method, details = result
                plant_data[param] = {
                    'value': round(value, 2),
                    'unit': furnace_data[list(furnace_data.keys())[0]][param]['unit'] if param in furnace_data[list(furnace_data.keys())[0]] else 'N/A',
                    'calculation_method': method,
                    'furnaces_used': len(details.get('furnaces', [])) if 'furnaces' in details else 0,
                    'source': 'legacy' if method == 'legacy_data' else 'calculated'
                }
                calculation_details[param] = details

        return plant_data, calculation_details

    def _calculate_parameter(self, plant: str, param: str, furnace_data: Dict, report_month: str) -> Optional[Tuple[float, str, Dict]]:
        """
        Calculate single parameter for plant

        Priority:
        1. Check legacy data in techno_actuals (if exists, use that)
        2. Calculate from furnace data (if no legacy data)

        Returns: (value, method, details) or None if not enough data
        """

        # PRIORITY 1: Check legacy/old data in techno_actuals
        legacy_value = self._get_legacy_plant_value(plant, param, report_month)
        if legacy_value is not None:
            details = {
                'formula': 'legacy_data',
                'source': 'techno_actuals',
                'note': 'Using existing legacy data (takes priority)'
            }
            return legacy_value, 'legacy_data', details

        # PRIORITY 2: Calculate from furnace data
        values_with_weights = []
        values_simple = []
        furnaces_list = []

        for furnace, f_data in furnace_data.items():
            if param not in f_data:
                continue

            value = f_data[param]['value']
            values_simple.append(value)
            furnaces_list.append(furnace)

            # Check if HM Production exists for weighting
            if 'HM Production' in f_data:
                hm_prod = f_data['HM Production']['value']
                values_with_weights.append({
                    'value': value,
                    'weight': hm_prod,
                    'furnace': furnace
                })

        if not values_simple:
            return None

        # Calculate weighted average if all furnaces have HM Production
        if values_with_weights and len(values_with_weights) == len(values_simple):
            total_value = sum(v['value'] * v['weight'] for v in values_with_weights)
            total_weight = sum(v['weight'] for v in values_with_weights)

            if total_weight > 0:
                result_value = total_value / total_weight

                details = {
                    'formula': 'weighted_average',
                    'weight_parameter': 'HM_Production',
                    'furnaces': [v['furnace'] for v in values_with_weights],
                    'total_weight': total_weight,
                    'calculation': ' + '.join(
                        [f"({v['value']}×{v['weight']})" for v in values_with_weights]
                    ) + f" / {total_weight}",
                    'note': 'Calculated from furnace data (no legacy data found)'
                }

                return result_value, 'weighted_average_by_hm_production', details

        # Fallback: Simple average
        if values_simple:
            result_value = sum(values_simple) / len(values_simple)

            details = {
                'formula': 'simple_average',
                'furnaces': furnaces_list,
                'count': len(values_simple),
                'reason': 'Some furnaces missing HM Production',
                'note': 'Calculated from furnace data (no legacy data found)'
            }

            return result_value, 'simple_average', details

        return None

    def _get_legacy_plant_value(self, plant: str, param: str, report_month: str) -> Optional[float]:
        """
        DISABLED: Use extracted data instead of legacy

        Legacy data was inaccurate. Extracted values from source files are authoritative:
        - Coke Rate: 428.5 (extracted) vs 428.13 (legacy) - extracted is correct
        - Plant values are given directly in source files, not calculated

        Returns: None (always use new extracted data)
        """
        return None

    def save_plant_consolidated(self, plant: str, report_month: str):
        """Calculate and save plant consolidated data"""
        plant_data, calc_details = self.calculate_plant_consolidated(plant, report_month)

        if plant_data:
            insert_techno_plant_data(
                plant=plant,
                report_month=report_month,
                data=plant_data,
                calculation_details=calc_details
            )

            return True
        return False


class TechnoSAILCalculator:
    """Calculate SAIL consolidated data from 5 plants"""

    PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']

    def calculate_sail_consolidated(self, report_month: str) -> Tuple[Dict, Dict]:
        """
        Calculate SAIL consolidated values for all 5 plants

        Priority 1: Use legacy SAIL direct value (if available in old techno_actuals)
        Priority 2: Calculate from 5 plants using their plant-consolidated values
        Priority 3: Fall back to simple average if needed

        Returns: (sail_data, calculation_method)
        """
        from db import insert_techno_sail_consolidated

        sail_data = {}
        calculation_method = {}

        # Get all unique parameters across all plants
        all_params = set()

        for plant in self.PLANTS:
            conn = db.connect()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT DISTINCT json_extract(data, '$')
                FROM techno_plant_data
                WHERE plant = ? AND report_month = ?
            """, [plant, report_month])

            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                if row[0]:
                    data = json.loads(row[0])
                    all_params.update(data.keys())

        # Calculate each parameter
        for param in sorted(all_params):
            # Try SAIL direct value first
            sail_value = self._get_sail_direct_value(param, report_month)

            if sail_value is not None:
                sail_data[param] = round(sail_value, 2)
                calculation_method[param] = 'SAIL_direct'
            else:
                # Calculate average of 5 plants
                avg_value = self._calculate_plant_average(param, report_month)

                if avg_value is not None:
                    sail_data[param] = round(avg_value, 2)
                    calculation_method[param] = 'avg_5_plants'

        return sail_data, calculation_method

    def _get_sail_direct_value(self, param: str, report_month: str) -> Optional[float]:
        """
        Get legacy SAIL direct value from old techno_actuals table

        This is PRIORITY 1 - legacy data takes precedence over calculated values

        Returns: value if found in legacy table, None otherwise
        """
        try:
            conn = db.connect()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT ta.actual
                FROM techno_actuals ta
                JOIN techno_param tp ON ta.param_id = tp.param_id
                WHERE ta.report_month = ?
                  AND tp.row_label = 'SAIL'
                  AND tp.param_name = ?
            """, [report_month, param])

            row = cursor.fetchone()
            conn.close()

            if row and row[0] is not None:
                return float(row[0])

        except Exception as e:
            import logging
            logging.warning(f"Error checking legacy SAIL data for {param}: {e}")

        return None

    def _calculate_plant_average(self, param: str, report_month: str) -> Optional[float]:
        """Calculate simple average of 5 plants"""
        values = []

        for plant in self.PLANTS:
            conn = db.connect()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT json_extract(data, ?) as value
                FROM techno_plant_data
                WHERE plant = ? AND report_month = ?
            """, [f'$."{param}".value', plant, report_month])

            row = cursor.fetchone()
            conn.close()

            if row and row[0] is not None:
                try:
                    values.append(float(row[0]))
                except (ValueError, TypeError):
                    continue

        if values:
            return sum(values) / len(values)

        return None

    def save_sail_consolidated(self, report_month: str):
        """Calculate and save SAIL consolidated data"""
        from db import insert_techno_sail_consolidated

        sail_data, calc_method = self.calculate_sail_consolidated(report_month)

        if sail_data:
            insert_techno_sail_consolidated(
                report_month=report_month,
                data=sail_data,
                calculation_method=calc_method
            )

            return True
        return False


# Convenience functions
def extract_and_save_furnace_data(extractor: TechnoFurnaceExtractor, pdf_rows, report_month: str):
    """Extract furnace data and save to database"""
    furnace_records = extractor.extract_furnace_data(pdf_rows, report_month)
    extractor.save_furnace_data(furnace_records)
    return len(furnace_records)


def calculate_and_save_plant_consolidated(plant: str, report_month: str):
    """Calculate plant consolidated data and save to database"""
    calculator = TechnoPlantCalculator()
    return calculator.save_plant_consolidated(plant, report_month)


def calculate_and_save_sail_consolidated(report_month: str):
    """Calculate SAIL consolidated data and save to database"""
    calculator = TechnoSAILCalculator()
    return calculator.save_sail_consolidated(report_month)


def process_complete_extraction(extractor: TechnoFurnaceExtractor, pdf_rows, report_month: str):
    """
    Complete extraction flow:
    1. Extract furnace data
    2. Calculate plant consolidated
    3. Calculate SAIL consolidated (if all 5 plants have data)
    """
    plant = extractor.plant

    # Step 1: Extract and save furnace data
    count = extract_and_save_furnace_data(extractor, pdf_rows, report_month)
    print(f"✅ Extracted {count} furnace records for {plant} - {report_month}")

    # Step 2: Calculate plant consolidated
    if calculate_and_save_plant_consolidated(plant, report_month):
        print(f"✅ Plant consolidated calculated for {plant} - {report_month}")

    # Step 3: Calculate SAIL consolidated (after all plants processed)
    # This should be called separately after all 5 plants are done
    print(f"ℹ️  Call calculate_and_save_sail_consolidated('{report_month}') after all plants are processed")

    return count
