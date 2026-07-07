"""
Unified Techno Extractor API - supports RSP, BSP, ISP
Extracts from mapped Excel files and inserts into common techno_data table (JSON column)
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

# Make techno_project importable
_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from db import init_db, upsert_techno_data, get_techno_data, get_techno_months, enrich_techno_records_with_db

router = APIRouter(prefix="/api/techno", tags=["unified-techno"])


def _get_extractor(plant: str):
    """Get the appropriate extractor for the plant."""
    if plant.upper() == "RSP":
        from rsp_technopara_extractor import TechnoExtractor
        return TechnoExtractor
    elif plant.upper() == "BSP":
        from bsp_extractor import BspTechnoExtractor
        return BspTechnoExtractor
    elif plant.upper() == "ISP":
        from isp_technopara_extractor import IspTechnoExtractor
        return IspTechnoExtractor
    elif plant.upper() == "DSP":
        from dsp_technopara_extractor import DspTechnoExtractor
        return DspTechnoExtractor
    elif plant.upper() == "BSL":
        from bsl_technopara_extractor import BslTechnoExtractor
        return BslTechnoExtractor
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Plant '{plant}' not supported. Supported: RSP, BSP, ISP, DSP, BSL"
        )


def _map_units(filename: str, nested: bool = False) -> set:
    """Collect unit names from a technopara map JSON (skipping _comment keys)."""
    try:
        with open(Path(_TP_DIR) / filename, encoding="utf-8") as f:
            m = json.load(f)
    except Exception:
        return set()
    if nested:  # {sheet: {unit: {...}}}
        return {u for units in m.values() if isinstance(units, dict) for u in units}
    return {k for k in m if not k.startswith("_")}


# DSP/BSL extractors derive unit names from file content rather than a map,
# so their legitimate units are listed explicitly.
_CONTENT_DERIVED_UNITS = {
    "DSP": {
        "BF-2", "BF-3", "BF-4", "BF_Shop", "SMS", "SMS-2", "Sinter",
        "Coke Ovens", "General", "MSM", "Merchant Mill",
        "Wheel Plant", "Axle Plant",
    },
    "BSL": {
        "BF-1", "BF-2", "BF-3", "BF-4", "BF-5", "BF_Shop",
        "SMS", "SMS-I", "SMS-II", "Sinter", "Coke Ovens",
        "CRM 1&2", "CRM 3", "HSM", "General",
    },
}


def allowed_units(plant: str) -> set:
    """Units the plant's extractor can legitimately produce.

    Guards /insert against saving records extracted for one plant under
    another (e.g. RSP-shaped SMS-1 data stamped as ISP).
    """
    plant = plant.upper()
    if plant == "RSP":
        return _map_units("rsp_technopara_map.json")
    if plant == "ISP":
        return _map_units("isp_technopara_map.json", nested=True)
    if plant == "BSP":
        return _map_units("bsp_techno_map.json") | _map_units("bsp_oisco_map.json")
    return _CONTENT_DERIVED_UNITS.get(plant, set())


def validate_units_for_plant(plant: str, units) -> None:
    """Raise 422 if any unit is not one the plant's extractor produces."""
    allowed = allowed_units(plant)
    if not allowed:
        return
    bad = sorted(set(units) - allowed)
    if bad:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Units {bad} are not valid for {plant.upper()} — the records were "
                f"likely previewed with a different plant selected. Re-run the "
                f"preview with the correct plant. Valid {plant.upper()} units: "
                f"{sorted(allowed)}"
            ),
        )


def _validate_month(report_month: str):
    """Validate month format YYYY-MM."""
    try:
        y, m = report_month.split('-')
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="report_month must be in YYYY-MM format, e.g. '2026-05'"
        )


@router.post("/extract")
async def extract_techno(
    plant: str = Form(..., description="Plant: RSP, BSP, ISP, DSP"),
    file: UploadFile = File(...),
    report_month: str = Form(..., description="Report month in YYYY-MM format, e.g. 2026-05 (optional for DSP)"),
):
    """
    Extract techno data from Excel/PDF file and save to techno_data table.

    Supports: RSP (Excel), BSP (Excel), ISP (Excel), DSP (PDF)
    Automatically routes to appropriate extractor based on plant parameter.

    Form fields:
      - plant: "RSP" or "BSP" or "ISP"
      - file: .xlsx Excel file (mapped according to plant)
      - report_month: "2026-05"

    Returns: { status, plant, report_month, units_extracted, records }
    """
    _validate_month(report_month)

    try:
        ExtractorClass = _get_extractor(plant)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        # Initialize extractor and extract data
        extractor = ExtractorClass(tmp.name, report_month=report_month)
        records = extractor.extract()

        if not records:
            raise HTTPException(
                status_code=422,
                detail=f"No data extracted from {plant} file. Verify file format and mapping."
            )

        # Save to database
        init_db()
        saved_count = 0

        for rec in records:
            try:
                upsert_techno_data(
                    plant=rec["plant"],
                    report_month=rec["report_month"],
                    unit=rec["unit"],
                    techno_json=rec["techno_json"],
                    source_file=file.filename or "",
                )
                saved_count += 1
            except Exception as e:
                print(f"Warning: Could not save {rec['unit']}: {e}")

        # AUTO-TRIGGER: Calculate and store SAIL actuals after extraction completes
        sail_calc_status = "pending"
        try:
            from page_techno import calculate_and_store_sail_actuals
            sail_result = calculate_and_store_sail_actuals(report_month)
            if sail_result['success']:
                sail_calc_status = "completed"
                print(f"✓ SAIL actuals auto-calculated for {report_month}")
            else:
                sail_calc_status = "failed"
                print(f"⚠ SAIL calculation failed: {sail_result['message']}")
        except Exception as e:
            sail_calc_status = "error"
            print(f"⚠ Error auto-calculating SAIL: {e}")

        return {
            "status": "ok",
            "plant": plant,
            "report_month": report_month,
            "source_file": file.filename or "",
            "units_extracted": len(records),
            "units_saved": saved_count,
            "units": [rec['unit'] for rec in records],
            "sail_actuals": sail_calc_status,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@router.post("/preview")
async def preview_techno(
    plant: str = Form(..., description="Plant: RSP, BSP, ISP, DSP"),
    file: UploadFile = File(...),
    report_month: str = Form("", description="Report month in YYYY-MM format (optional for DSP auto-detect)"),
):
    """
    Preview extracted techno data without saving to database.

    Same as /extract but returns data for review without DB insert.
    """
    _validate_month(report_month)

    try:
        ExtractorClass = _get_extractor(plant)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        extractor = ExtractorClass(tmp.name, report_month=report_month)
        records = extractor.extract()

        if not records:
            raise HTTPException(
                status_code=422,
                detail=f"No data extracted from {plant} file."
            )

        preview_records = [
            {"unit": rec["unit"], "techno_json": rec["techno_json"]}
            for rec in records
        ]
        total_params = sum(
            len(r["techno_json"].get("month", {})) for r in preview_records
        )
        # Use the extractor's own detected month (authoritative for DSP-style
        # auto-detect) rather than the raw input, which may be blank.
        resolved_month = records[0].get("report_month") or report_month

        # Attach current DB values so the UI can show DB-vs-extracted side by
        # side (month and cumulative) before the user confirms the insert.
        enrich_techno_records_with_db(preview_records, plant, resolved_month)

        return {
            "status": "preview",
            "plant": plant,
            "report_month": resolved_month,
            "source_file": file.filename or "",
            "units_extracted": len(preview_records),
            "total_params": total_params,
            "records": preview_records,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@router.post("/insert")
async def insert_techno(payload: dict):
    """
    Save previously-previewed records to the techno_data table.

    Body: { plant, report_month, source_file, records: [{unit, techno_json}] }
    Use after POST /preview so the user can review extracted values first.
    """
    plant        = payload.get("plant", "")
    report_month = payload.get("report_month", "")
    source_file  = payload.get("source_file", "")
    records      = payload.get("records", [])

    _validate_month(report_month)
    if not records:
        raise HTTPException(status_code=400, detail="No records to insert")
    validate_units_for_plant(plant, (rec.get("unit", "") for rec in records))

    init_db()
    saved_count = 0
    for rec in records:
        try:
            upsert_techno_data(
                plant=plant,
                report_month=report_month,
                unit=rec["unit"],
                techno_json=rec["techno_json"],
                source_file=source_file,
            )
            saved_count += 1
        except Exception as e:
            print(f"Warning: Could not save {rec.get('unit')}: {e}")

    sail_calc_status = "pending"
    try:
        from page_techno import calculate_and_store_sail_actuals
        sail_result = calculate_and_store_sail_actuals(report_month)
        sail_calc_status = "completed" if sail_result["success"] else "failed"
    except Exception as e:
        sail_calc_status = "error"
        print(f"⚠ Error auto-calculating SAIL: {e}")

    return {
        "status": "ok",
        "plant": plant,
        "report_month": report_month,
        "source_file": source_file,
        "units_extracted": len(records),
        "units_saved": saved_count,
        "units": [rec["unit"] for rec in records],
        "sail_actuals": sail_calc_status,
    }


@router.get("/data")
async def get_data(
    plant: str = Query(..., description="Plant: RSP, BSP, ISP, DSP"),
    report_month: str = Query(..., description="Report month: YYYY-MM"),
    unit: Optional[str] = Query(None, description="Optional: specific unit name"),
):
    """
    Retrieve techno data from common techno_data table.
    Works for all plants (RSP, BSP, ISP, DSP).
    """
    _validate_month(report_month)

    try:
        init_db()
        result = get_techno_data(plant, report_month, unit)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No techno data found for {plant} in {report_month}"
            )

        return {
            "plant": plant,
            "report_month": report_month,
            "unit_count": len(result),
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/months")
async def get_months(
    plant: Optional[str] = Query(None, description="Filter by plant: RSP, BSP, ISP, DSP"),
):
    """
    List available report months for a plant or all plants.
    """
    try:
        init_db()
        months = get_techno_months(plant)
        return {
            "plant": plant or "all",
            "months": months,
            "count": len(months)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plants")
async def get_plants():
    """
    Get list of plants with available techno data.
    """
    try:
        init_db()
        import sqlite3
        from db import DB_PATH

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT plant FROM techno_data ORDER BY plant")
        plants = [row[0] for row in cursor.fetchall()]
        conn.close()

        return {"plants": plants, "count": len(plants)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
