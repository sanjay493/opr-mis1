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
from fastapi.concurrency import run_in_threadpool

# Make techno_project importable
_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from db import init_db, merge_upsert_techno_data, get_techno_data, get_techno_months, enrich_techno_records_with_db, connect as db_connect

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
        from rsp_technopara_sections import ALL_UNITS
        return set(ALL_UNITS)
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
                merge_upsert_techno_data(
                    plant=rec["plant"],
                    report_month=rec["report_month"],
                    unit=rec["unit"],
                    new_techno_json=rec["techno_json"],
                    source_file=file.filename or "",
                )
                saved_count += 1
            except Exception as e:
                print(f"Warning: Could not save {rec['unit']}: {e}")

        # SAIL techno actuals are no longer auto-calculated/stored here —
        # calculate_sail_actuals() (page_techno.py) is used as a read-time
        # fallback wherever SAIL data is displayed instead.

        return {
            "status": "ok",
            "plant": plant,
            "report_month": report_month,
            "source_file": file.filename or "",
            "units_extracted": len(records),
            "units_saved": saved_count,
            "units": [rec['unit'] for rec in records],
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
            merge_upsert_techno_data(
                plant=plant,
                report_month=report_month,
                unit=rec["unit"],
                new_techno_json=rec["techno_json"],
                source_file=source_file,
            )
            saved_count += 1
        except Exception as e:
            print(f"Warning: Could not save {rec.get('unit')}: {e}")

    # SAIL techno actuals are no longer auto-calculated/stored here —
    # calculate_sail_actuals() (page_techno.py) is used as a read-time
    # fallback wherever SAIL data is displayed instead.

    return {
        "status": "ok",
        "plant": plant,
        "report_month": report_month,
        "source_file": source_file,
        "units_extracted": len(records),
        "units_saved": saved_count,
        "units": [rec["unit"] for rec in records],
    }


# Plants whose extractor is built around one workbook that carries every FY
# month as its own column (so one upload can supply several months at once).
# Only ISP today — see IspTechnoExtractor.extract_available_months.
_MULTI_MONTH_PLANTS = {"ISP"}


@router.post("/preview-months")
async def preview_techno_months(
    plant: str = Form(..., description="Plant — only ISP currently supports multi-month extraction"),
    file: UploadFile = File(...),
    upto_month: str = Form(..., description="Extract every FY month from April through this month (YYYY-MM) that the file has a column for"),
):
    """
    Preview extracted techno data for EVERY FY month from April through
    upto_month in one pass over a single uploaded workbook — lets a later
    cumulative file (e.g. the FY-end closing report, or any file spanning
    several months) backfill/refresh earlier months whose figures were
    revised before the FY closed. Does NOT write to the database; follow
    with POST /insert-months after review, same as the single-month
    /preview + /insert pair.
    """
    _validate_month(upto_month)
    if plant.upper() not in _MULTI_MONTH_PLANTS:
        raise HTTPException(
            status_code=400,
            detail=f"Multi-month extraction is only supported for {sorted(_MULTI_MONTH_PLANTS)} currently.",
        )

    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        # Extracting up to 12 months from one workbook, then a DB round-trip
        # per month to enrich with current values, is genuinely slow (tens
        # of seconds) — all synchronous/blocking code. Running it directly
        # in this async endpoint would freeze the single event loop for
        # that whole time, starving every other connection this worker
        # holds; confirmed in practice as the underlying cause of "socket
        # hang up"/ECONNRESET errors from the Next.js dev proxy on the
        # sibling /insert-months endpoint. run_in_threadpool hands the
        # blocking work to a worker thread so the event loop stays live.
        def _extract_and_enrich():
            from isp_technopara_extractor import IspTechnoExtractor
            extractor = IspTechnoExtractor(tmp.name)
            result = extractor.extract_available_months(upto_month)
            conn = db_connect()
            try:
                per_month = {}
                for rm, records in result["records_by_month"].items():
                    preview_records = [
                        {"unit": rec["unit"], "techno_json": rec["techno_json"]}
                        for rec in records
                    ]
                    enrich_techno_records_with_db(preview_records, plant, rm, conn=conn)
                    per_month[rm] = {
                        "units_extracted": len(preview_records),
                        "total_params": sum(len(r["techno_json"].get("month", {})) for r in preview_records),
                        "records": preview_records,
                    }
                return result, per_month
            finally:
                conn.close()

        result, per_month = await run_in_threadpool(_extract_and_enrich)

        if not result["records_by_month"]:
            raise HTTPException(
                status_code=422,
                detail="No data extracted for any month in range — verify the file and the selected month.",
            )

        return {
            "status": "preview",
            "plant": plant,
            "source_file": file.filename or "",
            "months": result["months"],
            "skipped_months": result["skipped_months"],
            "per_month": per_month,
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


@router.post("/insert-months")
async def insert_techno_months(payload: dict):
    """
    Save previously-previewed multi-month records (from POST /preview-months)
    to the techno_data table — one merge_upsert_techno_data call per
    (month, unit), same merge-safe semantics as POST /insert.

    Body: { plant, source_file, months: [{report_month, records: [{unit, techno_json}]}] }
    """
    plant       = payload.get("plant", "")
    source_file = payload.get("source_file", "")
    months      = payload.get("months", [])

    if not months:
        raise HTTPException(status_code=400, detail="No months to insert")
    for m in months:
        _validate_month(m.get("report_month", ""))
    validate_units_for_plant(
        plant,
        (rec.get("unit", "") for m in months for rec in m.get("records", [])),
    )

    # A bulk save is ~10 units x however many months = dozens of individual
    # writes. Confirmed by direct measurement: each merge_upsert_techno_data
    # call opens 4-5 SEPARATE DB connections across its own call chain
    # (merge_upsert_techno_data -> upsert_techno_data ->
    # _raw_upsert_techno_data / _maybe_recompute_derived_params /
    # _log_techno_save -> log_extraction), which for 120 units (12 months x
    # 10 units) meant 500+ connection round-trips and a ~30 second request —
    # long enough that the Next.js dev server's proxy reset the connection
    # before the (successfully completing) response could get back to it,
    # even after moving this work off the event loop (run_in_threadpool,
    # below) confirmed the backend itself stayed responsive throughout.
    # Reuse ONE connection for the whole batch via each function's optional
    # `conn` parameter (see merge_upsert_techno_data's docstring) — every
    # other caller of these functions omits `conn` and is unaffected.
    #
    # Also: a catch-all here (matching preview-months) so anything that
    # escapes the per-record try/except below still comes back as a JSON
    # error instead of Starlette's plain-text "Internal Server Error" (which
    # the frontend's res.json() previously choked on).
    def _save_all():
        init_db()
        conn = db_connect()
        try:
            saved = {}
            for m in months:
                report_month = m["report_month"]
                saved_count = 0
                for rec in m.get("records", []):
                    try:
                        merge_upsert_techno_data(
                            plant=plant,
                            report_month=report_month,
                            unit=rec["unit"],
                            new_techno_json=rec["techno_json"],
                            source_file=source_file,
                            conn=conn,
                        )
                        saved_count += 1
                    except Exception as e:
                        print(f"Warning: Could not save {plant}/{report_month}/{rec.get('unit')}: {e}")
                # One commit per month rather than per unit-write (each
                # commit is a full fsync on this DB — see
                # _raw_upsert_techno_data's docstring) — cuts fsync count
                # ~20x for a 10-unit month while still checkpointing
                # progress periodically instead of one giant all-or-nothing
                # transaction for the whole request.
                conn.commit()
                saved[report_month] = saved_count
            return saved
        finally:
            conn.close()

    try:
        saved = await run_in_threadpool(_save_all)
        return {
            "status": "ok",
            "plant": plant,
            "source_file": source_file,
            "saved": saved,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT plant FROM techno_data ORDER BY plant")
        plants = [row[0] for row in cursor.fetchall()]
        conn.close()

        return {"plants": plants, "count": len(plants)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
