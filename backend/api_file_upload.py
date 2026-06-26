#!/usr/bin/env python3
"""
File Upload API - Upload Excel files and auto-populate JSON tables

Endpoints:
  POST /upload - Upload file and extract data
  GET /upload-status - Check upload status
  GET /supported-extractors - List available extractors
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import shutil
from pathlib import Path
import tempfile
import logging
from typing import Dict, List

import sys
sys.path.insert(0, 'excel_extractors')

from smart_extractor_adapter import SmartExtractorAdapter
from db import init_db

router = APIRouter(prefix="/api", tags=["upload"])
logger = logging.getLogger(__name__)

# Supported extractors
SUPPORTED_EXTRACTORS = {
    'BSP': {
        'oisco': 'excel_extractor_bsp_oisco',
        'techno': 'excel_extractor_bsp_techno',
    },
    'DSP': {
        'rsp': 'excel_extractor_dsp_rsp',
    },
    'RSP': {
        'rsp': 'excel_extractor_rsp_rsp',
    },
    'BSL': {
        'rsp': 'excel_extractor_bsl_rsp',
    },
    'ISP': {
        'rsp': 'excel_extractor_isp_rsp',
    },
}

# Track upload status
upload_status = {}


@router.post("/upload")
async def upload_and_extract(
    file: UploadFile = File(...),
    plant: str = Form(...),
    extractor_type: str = Form(...),
    report_month: str = Form(...)
) -> Dict:
    """
    Upload Excel file and auto-extract data into JSON tables

    Args:
        file: Excel file to upload
        plant: Plant code (BSP, DSP, RSP, BSL, ISP)
        extractor_type: Extractor type (oisco, techno, rsp)
        report_month: Report month (YYYY-MM)

    Returns:
        {
            "status": "success|error",
            "message": "...",
            "data": {
                "plant": "BSP",
                "month": "2025-05",
                "furnaces_inserted": 4,
                "plant_data": "from_source|calculated",
                ...
            }
        }
    """

    try:
        plant = plant.upper()
        extractor_type = extractor_type.lower()

        # Validate plant and extractor type
        if plant not in SUPPORTED_EXTRACTORS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported plant: {plant}. Supported: {list(SUPPORTED_EXTRACTORS.keys())}"
            )

        if extractor_type not in SUPPORTED_EXTRACTORS[plant]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported extractor type '{extractor_type}' for {plant}. Supported: {list(SUPPORTED_EXTRACTORS[plant].keys())}"
            )

        # Validate month format
        if not _validate_month_format(report_month):
            raise HTTPException(
                status_code=400,
                detail="Invalid month format. Use YYYY-MM (e.g., 2025-05)"
            )

        logger.info(f"Uploading file: {file.filename} for {plant} ({extractor_type})")

        # Save uploaded file temporarily
        temp_dir = Path(tempfile.gettempdir())
        temp_file = temp_dir / file.filename

        with open(temp_file, "wb") as f:
            shutil.copyfileobj(file.file, f)

        logger.info(f"File saved temporarily: {temp_file}")

        # Load extractor module
        try:
            module_name = SUPPORTED_EXTRACTORS[plant][extractor_type]
            extractor_module = __import__(module_name)
        except ImportError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Extractor not found: {module_name}"
            )

        # Initialize database
        init_db()

        # Extract and insert
        adapter = SmartExtractorAdapter(plant)

        # Capture extraction results
        result = await _extract_with_logging(
            adapter=adapter,
            extractor_module=extractor_module,
            excel_file=str(temp_file),
            report_month=report_month,
            plant=plant,
            extractor_type=extractor_type
        )

        # Clean up temp file
        try:
            temp_file.unlink()
        except:
            pass

        if result['success']:
            logger.info(f"Upload successful: {plant} ({report_month})")
            return {
                "status": "success",
                "message": f"Data extracted and inserted successfully",
                "data": result['details']
            }
        else:
            logger.error(f"Upload failed: {result['error']}")
            raise HTTPException(
                status_code=400,
                detail=f"Extraction failed: {result['error']}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


async def _extract_with_logging(
    adapter,
    extractor_module,
    excel_file: str,
    report_month: str,
    plant: str,
    extractor_type: str
) -> Dict:
    """
    Extract and insert with detailed logging

    Returns:
        {
            "success": bool,
            "error": str (if failed),
            "details": {
                "plant": str,
                "month": str,
                "furnaces_inserted": int,
                "plant_data_source": "from_source|calculated",
                "parameters": {
                    "furnace": int,
                    "plant": int
                }
            }
        }
    """

    try:
        # Extract
        result = extractor_module.extract_preview(excel_file, report_month)
        param_rows = result.get('techno_param_rows', [])

        if not param_rows:
            return {
                "success": False,
                "error": "No parameters extracted from file"
            }

        # Separate furnace vs plant data
        furnace_data = {}
        plant_data_from_source = {}

        for row in param_rows:
            value = row.get('actual')
            if value is None:
                continue

            furnace = adapter._identify_furnace(row)
            from parameter_naming import normalize_parameter_name
            param_name = normalize_parameter_name(row.get('parameter', ''))

            if not param_name:
                continue

            if furnace:
                if furnace not in furnace_data:
                    furnace_data[furnace] = {}
                furnace_data[furnace][param_name] = {
                    'value': float(value),
                    'unit': row.get('unit', ''),
                    'source': 'Excel-Extracted',
                }
            else:
                plant_data_from_source[param_name] = {
                    'value': float(value),
                    'unit': row.get('unit', ''),
                    'source': 'Excel-Extracted',
                }

        # Insert
        from db import insert_techno_furnace_data, insert_techno_plant_data
        from techno_json_utils import TechnoPlantCalculator

        inserted_count = 0
        for furnace, params in furnace_data.items():
            try:
                insert_techno_furnace_data(plant, furnace, report_month, params)
                inserted_count += 1
            except Exception as e:
                logger.error(f"Failed to insert {furnace}: {str(e)}")

        # Handle plant data
        plant_data_source = "none"
        if plant_data_from_source:
            try:
                insert_techno_plant_data(
                    plant=plant,
                    report_month=report_month,
                    data=plant_data_from_source,
                    calculation_details={'method': 'from_source', 'source': 'Excel-Extracted'}
                )
                plant_data_source = "from_source"
            except Exception as e:
                logger.error(f"Failed to insert plant data: {str(e)}")
        elif inserted_count > 0:
            try:
                calc = TechnoPlantCalculator()
                plant_data, calc_details = calc.calculate_plant_consolidated(plant, report_month)
                plant_data_source = "calculated"
            except Exception as e:
                logger.error(f"Failed to calculate plant data: {str(e)}")

        return {
            "success": True,
            "details": {
                "plant": plant,
                "month": report_month,
                "extractor_type": extractor_type,
                "furnaces_inserted": inserted_count,
                "furnace_parameters": sum(len(v) for v in furnace_data.values()),
                "plant_parameters": len(plant_data_from_source),
                "plant_data_source": plant_data_source,
                "timestamp": str(__import__('datetime').datetime.now().isoformat())
            }
        }

    except Exception as e:
        logger.error(f"Extraction error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/supported-extractors")
async def get_supported_extractors() -> Dict:
    """Get list of supported plants and extractors"""

    return {
        "status": "success",
        "extractors": SUPPORTED_EXTRACTORS
    }


@router.get("/upload-status/{upload_id}")
async def get_upload_status(upload_id: str) -> Dict:
    """Get status of a specific upload"""

    if upload_id not in upload_status:
        raise HTTPException(
            status_code=404,
            detail=f"Upload {upload_id} not found"
        )

    return {
        "status": "success",
        "data": upload_status[upload_id]
    }


def _validate_month_format(month: str) -> bool:
    """Validate month format (YYYY-MM)"""

    if not month or len(month) != 7:
        return False

    try:
        year, m = month.split('-')
        int(year)
        int(m)
        return True
    except:
        return False
