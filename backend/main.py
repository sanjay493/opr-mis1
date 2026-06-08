import os
import json
import sqlite3
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

import db
from models import PDFRequest, ProductionEntry, ProductionEntryRequest
from report_utils import compute_item_row, blank_out_page_data
from page4 import generate_page4_rows
from page5_6 import generate_page5_rows, generate_page6_rows
from pdf import build_pdf_response

db.init_db()

app = FastAPI(
    title="SAIL OMI MIS Report Generator Backend",
    description="Python API backend to compile and export SAIL MIS reports using WeasyPrint.",
)

allowed_origins = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:3001", "http://127.0.0.1:3001",
]
frontend_origin = os.environ.get("FRONTEND_ORIGIN")
if frontend_origin:
    allowed_origins.append(frontend_origin)

frontend_port = os.environ.get("FRONTEND_PORT")
if frontend_port:
    allowed_origins.extend([
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

FRONTEND_DATA_PATH = os.path.join(os.path.dirname(__file__), "mis_data.json")


# ---------------------------------------------------------------------------
# Report data
# ---------------------------------------------------------------------------

@app.get("/api/data")
def get_data(month: str = "November 2025"):
    if not os.path.exists(FRONTEND_DATA_PATH):
        raise HTTPException(status_code=404, detail="Template data source not found.")
    try:
        pages_config = db.get_all_page_configs(month)
        if not pages_config:
            with open(FRONTEND_DATA_PATH, "r", encoding="utf-8") as f:
                pages_config = json.load(f)
            pages_config = blank_out_page_data(pages_config)

        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM production_table WHERE report_month = ?", (month,))
        has_actuals = cursor.fetchone()[0] > 0
        cursor.execute("SELECT COUNT(*) FROM production_plan_table WHERE report_month = ?", (month,))
        has_plans = cursor.fetchone()[0] > 0
        conn.close()

        if has_actuals or has_plans:
            for page in pages_config:
                if page.get("page") == 3 or page.get("type") == "summary":
                    for row in page.get("production_table", []):
                        row["values"] = compute_item_row(month, row.get("item"))
                if page.get("page") == 4 or page.get("type") == "page4_table":
                    page["rows"] = generate_page4_rows(month)
                if page.get("page") == 5:
                    page["rows"] = generate_page5_rows(month)
                    page["type"] = "performance_summary_table"
                if page.get("page") == 6:
                    page["rows"] = generate_page6_rows(month)
                    page["type"] = "performance_summary_table"

        return pages_config
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to read data source: {str(e)}")


@app.post("/api/data")
def save_data(request: PDFRequest):
    try:
        for page in request.pages:
            db.save_page_config(request.month, page.page, page.dict())

            if page.page == 3 or page.type == "summary":
                for row in (page.production_table or []):
                    item_name = row.get("item")
                    vals = row.get("values", [])
                    if len(vals) < 2:
                        continue

                    def parse_val(val_str):
                        if not val_str or not val_str.strip():
                            return None
                        try:
                            return float(val_str.strip())
                        except ValueError:
                            return None

                    db_item = item_name
                    if item_name == "Crude Steel":
                        db_item = "Total Crude Steel"
                    elif item_name == "Finish Steel":
                        db_item = "Finished Steel"

                    db.save_production_plan(request.month, "SAIL", db_item, parse_val(vals[0]))
                    db.save_production_actual(request.month, "SAIL", db_item, parse_val(vals[1]))

        return {"status": "success", "message": f"Successfully saved data for {request.month}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save data: {str(e)}")


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

@app.post("/api/generate-pdf")
async def generate_pdf(request: PDFRequest):
    return await build_pdf_response(request)


# ---------------------------------------------------------------------------
# Excel ingestion
# ---------------------------------------------------------------------------

@app.post("/api/upload-excel")
async def upload_excel(
    file: UploadFile = File(...),
    plant_name: str = Form(...),
    month: str = Form(...),
):
    import shutil
    import tempfile
    import sys

    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    suffix = os.path.splitext(file.filename)[1]
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        if plant_name not in ("RSP", "ISP", "BSP", "BSL", "DSP"):
            raise ValueError(
                f"Excel extraction is currently only supported for RSP, ISP, BSP, BSL, and DSP, not {plant_name}."
            )

        original_filename = file.filename or "unknown"
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

        if plant_name == "RSP":
            import excel_extractor_rsp
            success = excel_extractor_rsp.extract_and_save_excel(tmp_path, month, source_file_name=original_filename)
            msg = "RSP data extracted successfully. File type auto-detected from sheet names."
        elif plant_name == "ISP":
            import excel_extractor_isp
            success = excel_extractor_isp.extract_and_save_excel(tmp_path, month, source_file_name=original_filename)
            msg = "ISP data extracted. Morning Report: month auto-detected from K5. Final Monthly: month from selector."
        elif plant_name == "BSP":
            import excel_extractor_bsp
            success = excel_extractor_bsp.extract_and_save_excel(tmp_path, month, source_file_name=original_filename)
            msg = "BSP production actuals extracted. Report month auto-detected from cell N1 in sheet S1."
        elif plant_name == "BSL":
            import excel_extractor_bsl
            success = excel_extractor_bsl.extract_and_save_excel(tmp_path, month, source_file_name=original_filename)
            msg = "BSL production actuals extracted. Report month auto-detected from cell O1 in sheet DPR."
        else:
            import excel_extractor_dsp
            success = excel_extractor_dsp.extract_and_save_excel(tmp_path, month, source_file_name=original_filename)
            msg = "DSP production actuals extracted. Report month auto-detected from date in MCR-I report header."

        if not success:
            raise Exception(f"{plant_name} Excel extractor returned failure state.")

        return {"status": "success", "message": msg}

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as unlink_err:
                print(f"Failed to delete temp file {tmp_path}: {unlink_err}")


@app.post("/api/upload-excel-plan")
async def upload_excel_plan(
    file: UploadFile = File(...),
    plant_name: str = Form(...),
    financial_year: str = Form(...),
):
    import shutil
    import tempfile
    import sys

    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    suffix = os.path.splitext(file.filename)[1]
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        if plant_name not in ("RSP", "ISP", "BSP", "DSP", "BSL", "ASP_SSP_VISL"):
            raise ValueError(
                f"Plan Excel extraction is currently only supported for RSP, ISP, BSP, DSP, BSL and ASP_SSP_VISL, not {plant_name}."
            )

        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

        if plant_name == "RSP":
            import excel_extractor_rsp_plan
            success = excel_extractor_rsp_plan.extract_and_save_excel_plan(tmp_path, financial_year)
        elif plant_name == "ISP":
            import excel_extractor_isp_plan
            success = excel_extractor_isp_plan.extract_and_save_excel_plan(tmp_path, financial_year)
        elif plant_name == "BSP":
            import excel_extractor_bsp_plan
            success = excel_extractor_bsp_plan.extract_and_save_excel_plan(tmp_path, financial_year)
        elif plant_name == "BSL":
            import excel_extractor_bsl_plan
            success = excel_extractor_bsl_plan.extract_and_save_excel_plan(tmp_path, financial_year)
        elif plant_name == "ASP_SSP_VISL":
            import excel_extractor_asp_ssp_visl_plan
            success = excel_extractor_asp_ssp_visl_plan.extract_and_save_excel_plan(tmp_path, financial_year)
        else:
            import excel_extractor_dsp_plan
            success = excel_extractor_dsp_plan.extract_and_save_excel_plan(tmp_path, financial_year)

        if not success:
            raise Exception(f"{plant_name} Plan Excel extractor returned failure state.")

        return {
            "status": "success",
            "message": f"Successfully extracted planned target metrics for {plant_name} for Financial Year {financial_year}.",
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as unlink_err:
                print(f"Failed to delete temp file {tmp_path}: {unlink_err}")


# ---------------------------------------------------------------------------
# Production data entry
# ---------------------------------------------------------------------------

@app.get("/api/extraction-log")
async def get_extraction_log(limit: int = 60):
    return {"logs": db.get_extraction_logs(limit=limit)}


@app.get("/api/production-items")
async def get_production_items(plant: str, month: str):
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT item_name, month_actual FROM production_plan_table WHERE plant_name = ? AND report_month = ? ORDER BY item_name",
        (plant, month),
    )
    plan_rows = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.execute(
        "SELECT item_name, month_actual FROM production_table WHERE plant_name = ? AND report_month = ?",
        (plant, month),
    )
    actual_rows = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    all_items = sorted(set(plan_rows.keys()) | set(actual_rows.keys()))
    return {
        "items": [
            {
                "item_name": name,
                "plan_value": plan_rows.get(name),
                "actual_value": actual_rows.get(name),
            }
            for name in all_items
        ],
        "plant": plant,
        "month": month,
    }


@app.post("/api/production-entry")
async def save_production_entry(request: ProductionEntryRequest):
    saved = []
    for entry in request.entries:
        if entry.actual_value is not None:
            db.save_production_actual(request.month, request.plant, entry.item_name, entry.actual_value)
            saved.append(f"actual:{entry.item_name}")
        if entry.plan_value is not None:
            db.save_production_plan(request.month, request.plant, entry.item_name, entry.plan_value)
            saved.append(f"plan:{entry.item_name}")
    return {"status": "success", "saved": saved, "count": len(saved)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8082))
    uvicorn.run(app, host="0.0.0.0", port=port)
