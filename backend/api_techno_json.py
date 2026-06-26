"""
API endpoints for JSON-based techno data (furnace/plant level)
Integrated into main.py as additional routes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any, Optional
import json
import sqlite3
from db import (
    get_techno_furnace_data,
    get_techno_plant_data,
    get_techno_sail_consolidated,
    insert_techno_furnace_data,
    insert_techno_plant_data,
    insert_techno_sail_consolidated,
    DB_PATH,
    init_db
)
from techno_json_utils import TechnoPlantCalculator, TechnoSAILCalculator

router = APIRouter(prefix="/api", tags=["techno-json"])

PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']


# ===========================================================================
# Metadata Endpoints
# ===========================================================================

@router.get("/techno-available-data")
async def get_available_data():
    """
    Get available plants and months in database

    Returns:
        {
            "plants": ["BSP", "DSP", "RSP"],
            "months": {
                "BSP": ["2025-05", "2026-05"],
                "RSP": ["2026-04"],
                ...
            }
        }
    """
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get unique plants and months from techno_furnace_data
        cursor.execute("""
            SELECT DISTINCT plant, report_month
            FROM techno_furnace_data
            ORDER BY plant, report_month DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        # Group by plant
        plants_set = set()
        months_by_plant = {}

        for row in rows:
            plant = row['plant']
            month = row['report_month']

            plants_set.add(plant)
            if plant not in months_by_plant:
                months_by_plant[plant] = []
            if month not in months_by_plant[plant]:
                months_by_plant[plant].append(month)

        # Sort months descending
        for plant in months_by_plant:
            months_by_plant[plant].sort(reverse=True)

        return {
            "status": "success",
            "plants": sorted(list(plants_set)),
            "months": months_by_plant
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Furnace-level Data Endpoints
# ===========================================================================

@router.get("/techno-furnace-data")
async def get_furnace_data(
    plant: str = Query(..., description="Plant code: BSP, DSP, RSP, BSL, ISP"),
    report_month: str = Query(..., description="Report month in YYYY-MM format"),
    furnace: Optional[str] = Query(None, description="Optional specific furnace, e.g., BF-1")
):
    """
    Get furnace-level techno data (individual furnace parameters)

    Query params:
      - plant: "BSP"
      - report_month: "2026-06"
      - furnace: "BF-1" (optional)

    Returns: {furnace: {param: {value, unit, source, ...}}}
    """
    try:
        init_db()
        result = get_techno_furnace_data(plant, report_month, furnace)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No furnace data found for {plant} - {report_month}"
            )

        return {
            'plant': plant,
            'report_month': report_month,
            'furnaces': result,
            'count': len(result)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/techno-furnace-data-insert")
async def insert_furnace_data(
    plant: str = Query(...),
    furnace: str = Query(...),
    report_month: str = Query(...),
    data: Dict[str, Any] = None
):
    """
    Insert or update furnace-level data

    Body:
    {
      "plant": "BSP",
      "furnace": "BF-1",
      "report_month": "2026-06",
      "data": {
        "Coke Rate": {"value": 300.0, "unit": "Kg/THM"},
        "BF Productivity": {"value": 2.10, "unit": "T/m³/day"},
        "HM Production": {"value": 10000.0, "unit": "T", "source": "PDF"}
      }
    }
    """
    try:
        if not data:
            raise ValueError("Data cannot be empty")

        init_db()
        insert_techno_furnace_data(plant, furnace, report_month, data)

        return {
            'status': 'ok',
            'message': f'Furnace data inserted: {plant} - {furnace} - {report_month}',
            'plant': plant,
            'furnace': furnace,
            'report_month': report_month
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Plant-level Consolidated Data Endpoints
# ===========================================================================

@router.get("/techno-plant-data")
async def get_plant_data(
    plant: str = Query(..., description="Plant code: BSP, DSP, RSP, BSL, ISP"),
    report_month: str = Query(..., description="Report month in YYYY-MM format")
):
    """
    Get plant-level consolidated techno data (calculated from furnaces)

    Query params:
      - plant: "BSP"
      - report_month: "2026-06"

    Returns: {data: {param: {value, unit, calculation_method, ...}}, calculation_details: {...}}
    """
    try:
        init_db()
        result = get_techno_plant_data(plant, report_month)

        if not result or not result['data']:
            raise HTTPException(
                status_code=404,
                detail=f"No plant data found for {plant} - {report_month}"
            )

        return {
            'plant': plant,
            'report_month': report_month,
            'data': result['data'],
            'calculation_details': result['calculation_details'],
            'parameter_count': len(result['data'])
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/techno-plant-data-calculate")
async def calculate_plant_data(
    plant: str = Query(...),
    report_month: str = Query(...)
):
    """
    Calculate plant-level consolidated data from furnace data

    This endpoint:
    1. Fetches all furnace data for the plant
    2. Calculates weighted average (using HM Production as weight)
    3. Saves to techno_plant_data table

    Returns: {status, plant_data, calculation_details}
    """
    try:
        init_db()

        calculator = TechnoPlantCalculator()
        plant_data, calc_details = calculator.calculate_plant_consolidated(plant, report_month)

        if not plant_data:
            raise HTTPException(
                status_code=404,
                detail=f"No furnace data available to calculate plant consolidated for {plant} - {report_month}"
            )

        # Save to database
        insert_techno_plant_data(plant, report_month, plant_data, calc_details)

        return {
            'status': 'ok',
            'message': f'Plant consolidated calculated for {plant} - {report_month}',
            'plant': plant,
            'report_month': report_month,
            'parameters_calculated': len(plant_data),
            'data': plant_data,
            'calculation_details': calc_details
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# SAIL Consolidated Data Endpoints
# ===========================================================================

@router.get("/techno-sail-data")
async def get_sail_data(
    report_month: str = Query(..., description="Report month in YYYY-MM format")
):
    """
    Get SAIL consolidated techno data (all 5 plants aggregated)

    Query params:
      - report_month: "2026-06"

    Returns: {data: {param: value}, calculation_method: {param: method}}
    """
    try:
        init_db()
        result = get_techno_sail_consolidated(report_month)

        if not result or not result['data']:
            raise HTTPException(
                status_code=404,
                detail=f"No SAIL data found for {report_month}"
            )

        return {
            'report_month': report_month,
            'data': result['data'],
            'calculation_method': result['calculation_method'],
            'parameter_count': len(result['data'])
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/techno-sail-data-calculate")
async def calculate_sail_data(
    report_month: str = Query(...)
):
    """
    Calculate SAIL consolidated data from all 5 plants

    This endpoint:
    1. Fetches plant-level data for all 5 plants
    2. Calculates SAIL consolidated (weighted avg or direct SAIL value)
    3. Saves to techno_sail_consolidated table

    Returns: {status, sail_data, calculation_method}
    """
    try:
        init_db()

        calculator = TechnoSAILCalculator()
        sail_data, calc_method = calculator.calculate_sail_consolidated(report_month)

        if not sail_data:
            raise HTTPException(
                status_code=404,
                detail=f"No plant data available to calculate SAIL consolidated for {report_month}"
            )

        # Save to database
        insert_techno_sail_consolidated(report_month, sail_data, calc_method)

        return {
            'status': 'ok',
            'message': f'SAIL consolidated calculated for {report_month}',
            'report_month': report_month,
            'parameters_calculated': len(sail_data),
            'data': sail_data,
            'calculation_method': calc_method
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Utility Endpoints
# ===========================================================================

@router.get("/techno-parameters-list")
async def get_all_parameters():
    """
    Get list of all available techno parameters across all furnace data

    Returns: {parameters: [list of unique parameter names]}
    """
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get unique parameters from furnace data
        cursor.execute("""
            SELECT DISTINCT json_extract(data, '$') as params
            FROM techno_furnace_data
        """)

        all_params = set()
        rows = cursor.fetchall()

        for row in rows:
            if row[0]:
                try:
                    data = json.loads(row[0])
                    all_params.update(data.keys())
                except (json.JSONDecodeError, TypeError):
                    continue

        conn.close()

        # Remove non-display parameters
        exclude_params = {'HM Production'}
        parameters = sorted([p for p in all_params if p not in exclude_params])

        return {
            'parameters': parameters,
            'count': len(parameters)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/techno-months-available")
async def get_available_months(plant: Optional[str] = Query(None)):
    """
    Get available report months in the techno_furnace_data table

    Returns: {months: [list of YYYY-MM strings]}
    """
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if plant:
            cursor.execute("""
                SELECT DISTINCT report_month
                FROM techno_furnace_data
                WHERE plant = ?
                ORDER BY report_month DESC
            """, [plant])
        else:
            cursor.execute("""
                SELECT DISTINCT report_month
                FROM techno_furnace_data
                ORDER BY report_month DESC
            """)

        rows = cursor.fetchall()
        conn.close()

        months = [row[0] for row in rows]

        return {
            'months': months,
            'count': len(months)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/techno-furnaces-for-plant")
async def get_furnaces_for_plant(
    plant: str = Query(...),
    report_month: Optional[str] = Query(None)
):
    """
    Get list of furnaces for a plant

    Returns: {furnaces: [list of furnace names]}
    """
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if report_month:
            cursor.execute("""
                SELECT DISTINCT furnace
                FROM techno_furnace_data
                WHERE plant = ? AND report_month = ?
                ORDER BY furnace
            """, [plant, report_month])
        else:
            cursor.execute("""
                SELECT DISTINCT furnace
                FROM techno_furnace_data
                WHERE plant = ?
                ORDER BY furnace
            """, [plant])

        rows = cursor.fetchall()
        conn.close()

        furnaces = [row[0] for row in rows]

        return {
            'plant': plant,
            'report_month': report_month,
            'furnaces': furnaces,
            'count': len(furnaces)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
