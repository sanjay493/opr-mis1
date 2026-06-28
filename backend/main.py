import os
import json
import sqlite3
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

import db
from models import PDFRequest, ProductionEntry, ProductionEntryRequest, SpecialSteelSaveRequest
from report_utils import compute_item_row, blank_out_page_data
from page4 import generate_page4_rows
from page5_6 import generate_page5_rows, generate_page6_rows
from page7_13 import generate_trend_page_rows, generate_combined_trend_items, TREND_PAGES
from page17_concast import generate_concast_data
from page_prod_by_process import generate_prod_by_process
from page_catwise_saleable import generate_catwise_saleable
from page_segment_wise import generate_segment_wise
from page_special_steel import generate_special_steel_plant, generate_special_steel_sail, generate_special_steel_isp_sail
from page_opening_stock import generate_opening_stock
from page_ipt import generate_ipt
from page_techno import (generate_techno, TECHNO_PAGES, generate_summary_te_table,
                          generate_summary_chart_data, compute_sail_targets,
                          generate_major_techno_from_db, generate_techno_from_db)
from page_records import generate_records

def _safe_te_table(month):
    try:
        return generate_summary_te_table(month)
    except Exception:
        return []

def _safe_chart_data(month):
    try:
        return generate_summary_chart_data(month)
    except Exception:
        return {}

def _safe_techno(month, pg):
    try:
        return generate_techno(month, pg)
    except Exception:
        if pg == 27:
            try:
                return generate_major_techno_from_db(month)
            except Exception:
                pass
        elif 28 <= pg <= 35:
            try:
                return generate_techno_from_db(month, pg)
            except Exception:
                pass
        return {}
from pdf import build_pdf_response
from layout_loader import load_layout_config
from api_file_upload import router as upload_router
from api_rsp_techno import router as rsp_techno_router
from api_bsp_techno import router as bsp_techno_router
from api_isp_techno import router as isp_techno_router
from api_dsp_techno import router as dsp_techno_router
from api_unified_techno import router as unified_techno_router
from api_techno_manual import router as techno_manual_router

db.init_db()

# Mapping of IRON_MAKING param_ids to their corresponding MAJOR param_ids.
# With recent consolidation of BF params, they share param_ids between groups.
# This mapping is empty since params are now linked via many-to-many group membership.
_IM_AVG_TO_MAJOR = {}

app = FastAPI(
    title="SAIL OMI MIS Report Generator Backend",
    description="Python API backend to compile and export SAIL MIS reports using WeasyPrint.",
)

allowed_origins = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:3001", "http://127.0.0.1:3001",
    "http://localhost:8000", "http://127.0.0.1:8000",  # Dashboard
    "file://",  # File protocol for local HTML
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

# Include file upload router
app.include_router(upload_router)

# Include RSP, BSP, ISP, and DSP Technopara routers
app.include_router(rsp_techno_router)
app.include_router(bsp_techno_router)
app.include_router(isp_techno_router)
app.include_router(dsp_techno_router)
app.include_router(unified_techno_router)
app.include_router(techno_manual_router)

# Serve dashboard
@app.get("/dashboard")
async def get_dashboard():
    """Serve the Techno JSON Dashboard"""
    dashboard_path = Path(__file__).parent / "dashboard.html"
    if dashboard_path.exists():
        return FileResponse(dashboard_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Dashboard not found")

# Serve upload page
@app.get("/upload")
async def get_upload_page():
    """Serve the File Upload page"""
    upload_path = Path(__file__).parent / "upload.html"
    if upload_path.exists():
        return FileResponse(upload_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Upload page not found")

FRONTEND_DATA_PATH = os.path.join(os.path.dirname(__file__), "mis_data.json")


# ---------------------------------------------------------------------------
# Layout config
# ---------------------------------------------------------------------------

@app.get("/api/layout-config")
def get_layout_config():
    return load_layout_config()


# ---------------------------------------------------------------------------
# Report data
# ---------------------------------------------------------------------------

@app.get("/api/data")
def get_data(month: str = "2025-11"):
    if not os.path.exists(FRONTEND_DATA_PATH):
        raise HTTPException(status_code=404, detail="Template data source not found.")
    try:
        pages_config = db.get_all_page_configs(month)
        if not pages_config:
            with open(FRONTEND_DATA_PATH, "r", encoding="utf-8-sig") as f:
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
                    page["te_table"] = _safe_te_table(month)
                    page["chart_data"] = _safe_chart_data(month)
                if page.get("page") == 4 or page.get("type") == "page4_table":
                    page["rows"] = generate_page4_rows(month)
                if page.get("page") == 5:
                    page["rows"] = generate_page5_rows(month)
                    page["type"] = "performance_summary_table"
                if page.get("page") == 6:
                    page["rows"] = generate_page6_rows(month)
                    page["type"] = "performance_summary_table"
                pg = page.get("page")
                if isinstance(pg, int) and 7 <= pg <= 12:
                    cfg = TREND_PAGES.get(pg, {})
                    if cfg.get("combined_items"):
                        # Page 11: Pig Iron + Finished Steel combined
                        page["type"] = "trend_combined"
                        page["title"] = f"MONTH-WISE PRODUCTION TREND : {cfg.get('display', '')}"
                        page["item_display"] = cfg.get("display", "")
                        page["unit"] = ""
                        page["rows"] = []
                        page["items"] = generate_combined_trend_items(month, pg)
                    else:
                        page["type"] = "trend_yearly"
                        page["title"] = f"MONTH-WISE PRODUCTION TREND : {cfg.get('display', '')}"
                        page["item_display"] = cfg.get("display", "")
                        page["unit"] = cfg.get("unit", "")
                        page["rows"] = generate_trend_page_rows(month, pg)
                if pg == 13:
                    page["type"] = "concast_performance"
                    page["title"] = "CONCAST PRODUCTION PERFORMANCE"
                    page["subtitle"] = ""
                    page["rows"] = []
                    page["headers"] = []
                    concast = generate_concast_data(month)
                    page["monthly"] = concast["monthly"]
                    page["ytd"]     = concast["ytd"]
                if pg == 14:
                    page["type"] = "prod_by_process"
                    page["title"] = "PRODUCTION BY PROCESS"
                    pbp = generate_prod_by_process(month)
                    page["monthly"]      = pbp["monthly"]
                    page["monthly_prev"] = pbp["monthly_prev"]
                    page["ytd"]          = pbp["ytd"]
                    page["ytd_prev"]     = pbp["ytd_prev"]
                if pg in (15, 16, 17, 18):
                    import datetime as _dt
                    dt = _dt.datetime.strptime(month, "%Y-%m")
                    page["month_label"] = dt.strftime("%b'%y")
                    page["cply_label"]  = _dt.datetime(dt.year - 1, dt.month, 1).strftime("%b'%y")
                if pg == 15:
                    page["type"]     = "catwise_saleable"
                    page["title"]    = "CATEGORY WISE PRODUCTION OF SALEABLE STEEL"
                    page["subtitle"] = "BHILAI STEEL PLANT"
                    page["sections"] = generate_catwise_saleable(month, ["BSP"])
                if pg == 16:
                    page["type"]     = "catwise_saleable"
                    page["title"]    = "CATEGORY WISE PRODUCTION OF SALEABLE STEEL"
                    page["subtitle"] = ""
                    page["sections"] = generate_catwise_saleable(month, ["DSP", "RSP"])
                if pg == 17:
                    page["type"]     = "catwise_saleable"
                    page["title"]    = "CATEGORY WISE PRODUCTION OF SALEABLE STEEL"
                    page["subtitle"] = ""
                    page["sections"] = generate_catwise_saleable(month, ["BSL", "ISP"])
                if pg == 18:
                    page["type"]        = "segment_wise"
                    page["title"]       = "SEGMENT WISE PRODUCTION"
                    sw = generate_segment_wise(month)
                    page["rows"]        = sw["rows"]

        # Always regenerate special steel pages (data from special_steel_orders,
        # independent of production_table / production_plan_table)
        import datetime as _dt
        _dt_obj = _dt.datetime.strptime(month, "%Y-%m")
        _ml = _dt_obj.strftime("%b'%y")
        _cl = _dt.datetime(_dt_obj.year - 1, _dt_obj.month, 1).strftime("%b'%y")
        _SPECIAL_PLANTS = {19: "BSP", 20: "DSP", 21: "RSP", 22: "BSL"}
        # Page 24 is merged into page 23 (ISP + SAIL combined on one page)
        pages_config = [p for p in pages_config if p.get("page") != 24]
        for page in pages_config:
            pg = page.get("page")
            if pg in _SPECIAL_PLANTS:
                page["month_label"] = _ml
                page["cply_label"]  = _cl
                ss = generate_special_steel_plant(month, _SPECIAL_PLANTS[pg])
                page.update(ss)
                page["type"] = "special_steel"
            if pg == 23:
                page.update(generate_special_steel_isp_sail(month))
                page["type"] = "special_steel"
            if pg == 25:
                page.update(generate_opening_stock(month))
                page["type"] = "opening_stock"
            if pg == 26:
                page.update(generate_ipt(month))
                page["type"] = "ipt_status"
            if pg in TECHNO_PAGES:
                page.update(_safe_techno(month, pg))
                page["type"] = "techno_params"

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
    import datetime as _dt
    enriched = []
    for page in request.pages:
        p = page.dict()
        pg = p.get("page", 0)
        if pg == 3 or p.get("type") == "summary":
            p["te_table"] = _safe_te_table(request.month)
        if pg == 13:
            concast = generate_concast_data(request.month)
            p["monthly"] = concast["monthly"]
            p["ytd"]     = concast["ytd"]
        if pg == 14:
            pbp = generate_prod_by_process(request.month)
            p["monthly"]      = pbp["monthly"]
            p["monthly_prev"] = pbp["monthly_prev"]
            p["ytd"]          = pbp["ytd"]
            p["ytd_prev"]     = pbp["ytd_prev"]
        if pg in (15, 16, 17, 18, 19, 20, 21, 22, 23, 24):
            dt = _dt.datetime.strptime(request.month, "%Y-%m")
            p["month_label"] = dt.strftime("%b'%y")
            p["cply_label"]  = _dt.datetime(dt.year - 1, dt.month, 1).strftime("%b'%y")
        if pg == 15:
            p["type"]     = "catwise_saleable"
            p["sections"] = generate_catwise_saleable(request.month, ["BSP"])
        if pg == 16:
            p["type"]     = "catwise_saleable"
            p["sections"] = generate_catwise_saleable(request.month, ["DSP", "RSP"])
        if pg == 17:
            p["type"]     = "catwise_saleable"
            p["sections"] = generate_catwise_saleable(request.month, ["BSL", "ISP"])
        if pg == 18:
            p["type"]        = "segment_wise"
            p["rows"]        = generate_segment_wise(request.month)["rows"]
        _SP = {19: "BSP", 20: "DSP", 21: "RSP", 22: "BSL"}
        if pg in _SP:
            ss = generate_special_steel_plant(request.month, _SP[pg])
            p.update(ss); p["type"] = "special_steel"
        if pg == 23:
            p.update(generate_special_steel_isp_sail(request.month))
            p["type"] = "special_steel"
        if pg == 24:
            continue  # merged into page 23
        if pg == 25:
            p.update(generate_opening_stock(request.month))
            p["type"] = "opening_stock"
        if pg == 26:
            p.update(generate_ipt(request.month))
            p["type"] = "ipt_status"
        if pg in TECHNO_PAGES:
            p.update(_safe_techno(request.month, pg))
            p["type"] = "techno_params"
        enriched.append(p)
    # Layout and typography now come from backend layout_config.json only; ignore frontend overrides
    return await build_pdf_response(request, pages_override=enriched, page_layouts=None, font_config=None)


# ---------------------------------------------------------------------------
# Special Steel manual entry
# ---------------------------------------------------------------------------

@app.get("/api/special-steel-manual")
def get_special_steel_manual(plant: str = Query(...), month: str = Query(...)):
    """Return all special_steel_orders rows for a plant+month for manual editing."""
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT product, quality_grade, section, sort_order, order_qty, actual_despatch
            FROM special_steel_orders
            WHERE report_month=? AND plant_name=?
            ORDER BY sort_order ASC, product ASC, quality_grade ASC
        """, (month, plant))
        rows = [
            {"product": r[0], "quality_grade": r[1], "section": r[2],
             "sort_order": r[3], "order_qty": r[4], "actual_despatch": r[5]}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
    return {"rows": rows, "plant": plant, "month": month}


@app.post("/api/special-steel-manual/save")
def save_special_steel_manual(request: SpecialSteelSaveRequest):
    """Replace all special steel rows for a plant+month with the supplied data."""
    db.clear_special_steel_orders(request.month, request.plant)
    for i, r in enumerate(request.rows):
        db.save_special_steel_entry(
            request.month, request.plant,
            r.product, r.quality_grade,
            i,
            r.order_qty, r.actual_despatch,
            section=r.section,
        )
    return {"status": "success", "saved": len(request.rows)}


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
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "excel_extractors")))

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

        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "excel_extractors")))

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
# ABP Plan: preview (no DB write) + confirm (insert into production_plan_table)
# ---------------------------------------------------------------------------

_PLAN_PREVIEW_PLANTS = ("RSP", "ISP", "BSP", "DSP", "BSL", "ASP_SSP_VISL", "ASP")
_PLAN_EXCEL_PLANTS   = ("RSP", "ISP", "BSP", "DSP", "BSL", "ASP_SSP_VISL")
_PLAN_UNIT_OVERRIDE  = {"Oven Pushing(nos/d)": "nos/d"}   # all other items → '000T

_PLAN_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS production_plan_table (
    report_month TEXT NOT NULL,
    plant_name   TEXT NOT NULL,
    item_name    TEXT NOT NULL,
    month_actual REAL,
    PRIMARY KEY (report_month, plant_name, item_name)
)"""


@app.post("/api/preview-plan")
async def preview_plan(
    file: UploadFile = File(...),
    plant_name: str = Form(...),
    financial_year: str = Form(...),
):
    """Extract ABP plan rows without writing to the real DB.
    Returns plan_rows ready for display; caller confirms via /api/confirm-plan."""
    import shutil, tempfile, sys, asyncio, concurrent.futures, sqlite3 as _sql

    if plant_name not in _PLAN_PREVIEW_PLANTS:
        raise HTTPException(status_code=400,
                            detail=f"Plan preview not supported for plant '{plant_name}'.")

    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    suffix = os.path.splitext(file.filename or "")[1] or (".pdf" if plant_name == "ASP" else ".xlsx")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "excel_extractors")))
        loop = asyncio.get_running_loop()

        if plant_name == "ASP":
            # ASP ABP Plan is a PDF — use existing PDF preview extractor
            import excel_extractor_asp_ssp_visl_plan as _asp_mod
            fy_start = int(financial_year.split("-")[0])
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(
                    pool, lambda: _asp_mod.extract_preview_pdf(tmp_path, f"{fy_start}-04"))
            return result

        # Excel plants — redirect writes to a temp SQLite, then read back rows
        tmp_db_fd, tmp_db_path = tempfile.mkstemp(suffix=".db", dir=temp_dir)
        os.close(tmp_db_fd)
        try:
            # Set up minimal schema in the temp DB
            _c = _sql.connect(tmp_db_path)
            _c.execute(_PLAN_TABLE_DDL)
            _c.commit()
            _c.close()

            # Load module and patch its DB_PATH to the temp file
            if plant_name == "RSP":
                import excel_extractor_rsp_plan as _mod
            elif plant_name == "ISP":
                import excel_extractor_isp_plan as _mod
            elif plant_name == "BSP":
                import excel_extractor_bsp_plan as _mod
            elif plant_name == "BSL":
                import excel_extractor_bsl_plan as _mod
            elif plant_name == "ASP_SSP_VISL":
                import excel_extractor_asp_ssp_visl_plan as _mod
            else:
                import excel_extractor_dsp_plan as _mod

            orig_db = _mod.DB_PATH
            _mod.DB_PATH = tmp_db_path
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    ok = await loop.run_in_executor(
                        pool, lambda: _mod.extract_and_save_excel_plan(tmp_path, financial_year))
                if not ok:
                    raise Exception(f"{plant_name} plan extractor returned failure.")
            finally:
                _mod.DB_PATH = orig_db

            # Read written rows from the temp DB
            _c = _sql.connect(tmp_db_path)
            rows = _c.execute(
                "SELECT plant_name, item_name, report_month, month_actual "
                "FROM production_plan_table "
                "ORDER BY plant_name, item_name, report_month"
            ).fetchall()
            _c.close()

            plan_rows = [
                {
                    "item_name": r[1],
                    "month":     r[2],
                    "value":     r[3],
                    "unit":      _PLAN_UNIT_OVERRIDE.get(r[1], "'000T"),
                    "plant":     r[0],
                    "status":    "ok" if r[3] is not None else "skip",
                }
                for r in rows
            ]
            ok_count = sum(1 for r in plan_rows if r["status"] == "ok")
            if ok_count == 0:
                raise ValueError(f"No data extracted from {plant_name} plan file.")

            return {
                "plant":          plant_name,
                "financial_year": financial_year,
                "plan_rows":      plan_rows,
                "source_type":    f"{plant_name} ABP Plan Excel",
                "sheets":         "",
                "workbook_sheets": [],
            }
        finally:
            try:
                os.unlink(tmp_db_path)
            except Exception:
                pass

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@app.post("/api/confirm-plan")
async def confirm_plan(payload: dict):
    """Insert confirmed ABP plan rows into production_plan_table."""
    plan_rows = payload.get("plan_rows", [])
    if not plan_rows:
        raise HTTPException(status_code=400, detail="No plan rows provided.")
    try:
        DB_PATH = db.DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        saved = 0
        for r in plan_rows:
            if r.get("status") != "ok" or r.get("value") is None:
                continue
            cur.execute("""
                INSERT INTO production_plan_table (report_month, plant_name, item_name, month_actual)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, plant_name, item_name)
                DO UPDATE SET month_actual = excluded.month_actual
            """, (r["month"], r.get("plant", ""), r["item_name"], r["value"]))
            saved += 1
        conn.commit()
        conn.close()
        return {
            "status":  "success",
            "saved":   saved,
            "message": f"Inserted {saved} plan rows into production_plan_table.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Unified RSP extraction (preview → confirm → insert into respective tables)
# ---------------------------------------------------------------------------

@app.post("/api/extract-preview")
async def extract_preview_endpoint(
    file: UploadFile = File(...),
    plant_name: str = Form(...),
    month: str = Form(...),
    extract_block: str = Form("all"),
    all_months: str = Form(default="false"),
):
    """Extract production + techno data from an RSP report for review.
    Returns previews only — nothing is written to the DB."""
    import shutil
    import tempfile
    import sys

    if plant_name not in ("RSP", "DSP", "ISP", "BSP", "ASP", "SSP", "VISL", "BSL", "ASP-Plan"):
        raise HTTPException(status_code=400,
                            detail=f"Preview extraction not supported for {plant_name}.")

    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    suffix = os.path.splitext(file.filename)[1]
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "excel_extractors")))

        import asyncio, concurrent.futures
        loop = asyncio.get_running_loop()
        all_months_bool = all_months.lower() == "true"

        if plant_name == "DSP":
            import excel_extractor_dsp
            aliases = db.get_pdf_item_aliases("DSP")
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                # Try with all_months parameter first, fall back if not supported
                try:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            pool,
                            lambda: excel_extractor_dsp.extract_preview(
                                tmp_path, month, aliases=aliases, block=extract_block, all_months=all_months_bool)
                        ),
                        timeout=300.0,
                    )
                except TypeError as e:
                    if "all_months" in str(e):
                        # Fall back to calling without all_months parameter
                        result = await asyncio.wait_for(
                            loop.run_in_executor(
                                pool,
                                lambda: excel_extractor_dsp.extract_preview(
                                    tmp_path, month, aliases=aliases, block=extract_block)
                            ),
                            timeout=300.0,
                        )
                    else:
                        raise
            except asyncio.TimeoutError:
                raise HTTPException(status_code=504,
                    detail="PDF extraction timed out after 5 minutes. "
                           "The PDF may be too complex or very large. "
                           "Check backend/extraction_errors.log for details.")
            finally:
                pool.shutdown(wait=False)
        elif plant_name == "ISP":
            import excel_extractor_isp
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(
                    pool,
                    lambda: excel_extractor_isp.extract_preview(tmp_path, month)
                )
        elif plant_name == "BSP":
            # Unified BSP extractor — auto-detects: Special Steel / OISCO / 3-page-Tech
            import excel_extractor_bsp as _bsp_mod
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(
                    pool,
                    lambda: _bsp_mod.extract_preview(tmp_path, month)
                )
        elif plant_name == "ASP":
            _ext = os.path.splitext(file.filename or "")[1].lower()
            if _ext in (".xlsx", ".xls"):
                import excel_extractor_asp as _asp_mod
            else:
                import pdf_extractor_asp as _asp_mod
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(
                    pool,
                    lambda: _asp_mod.extract_preview(tmp_path, month)
                )
        elif plant_name == "SSP":
            import pdf_extractor_ssp as _ssp_mod
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(
                    pool,
                    lambda: _ssp_mod.extract_preview(tmp_path, month)
                )
        elif plant_name == "VISL":
            import pdf_extractor_visl as _visl_mod
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(
                    pool,
                    lambda: _visl_mod.extract_preview(tmp_path, month)
                )
        elif plant_name == "ASP-Plan":
            import excel_extractor_asp_ssp_visl_plan as _asp_plan_mod
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(
                    pool,
                    lambda: _asp_plan_mod.extract_preview_pdf(tmp_path, month)
                )
        elif plant_name == "BSL":
            import excel_extractor_bsl as _bsl_mod
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(
                    pool,
                    lambda: _bsl_mod.extract_preview(tmp_path, month)
                )
        else:
            import excel_extractor_rsp
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(
                    pool,
                    lambda: excel_extractor_rsp.extract_preview(tmp_path, month)
                )
        result["file_name"] = file.filename
        return result
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except BaseException as e:
        import traceback, datetime
        tb_text = traceback.format_exc()
        traceback.print_exc()
        # Write full traceback to a file so it's visible even without a terminal
        try:
            log_path = os.path.join(os.path.dirname(__file__), "extraction_errors.log")
            with open(log_path, "a", encoding="utf-8") as _lf:
                _lf.write(f"\n{'='*60}\n{datetime.datetime.now()}\n")
                _lf.write(f"plant={plant_name}  month={month}\n")
                _lf.write(tb_text)
        except Exception:
            pass
        short_msg = str(e) or "(no message)"
        if len(short_msg) > 400:
            short_msg = short_msg[:400] + "..."
        raise HTTPException(
            status_code=500,
            detail=f"Preview extraction failed: {type(e).__name__}: {short_msg}"
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@app.post("/api/confirm-extraction")
async def confirm_extraction(payload: dict):
    """Insert user-confirmed preview rows into their respective tables:
    production_rows → production_table, plan_rows → production_plan_table,
    techno_rows → techno_table, techno_param_rows → techno_param_master / techno_monthly."""
    try:
        month = payload.get("month")
        plant = payload.get("plant", "RSP")
        if not month:
            raise HTTPException(status_code=400, detail="month is required")

        saved_prod = saved_plan = saved_te = saved_mill = 0

        conn = sqlite3.connect(db.DB_PATH)
        cur = conn.cursor()
        try:
            for r in payload.get("production_rows", []):
                cur.execute("""
                    INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(report_month, plant_name, item_name)
                    DO UPDATE SET month_actual = excluded.month_actual
                """, (month, plant, r.get("item_name"), r.get("value")))
                if r.get("value") is not None:
                    saved_prod += 1

            for r in payload.get("plan_rows", []):
                if r.get("status") != "ok" or r.get("value") is None:
                    continue
                cur.execute("""
                    INSERT INTO production_plan_table (report_month, plant_name, item_name, month_actual)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(report_month, plant_name, item_name)
                    DO UPDATE SET month_actual = excluded.month_actual
                """, (r["month"], r.get("plant", plant), r["item_name"], r["value"]))
                saved_plan += 1

            for r in payload.get("techno_rows", []):
                # Legacy preview format: (plant_name, parameter_name) → look up param_id
                cur.execute(
                    "SELECT param_id FROM techno_param WHERE row_label=? AND param_name=?",
                    (plant, r.get("parameter", "")),
                )
                row = cur.fetchone()
                if row and r.get("month_actual") is not None:
                    cur.execute("""
                        INSERT INTO techno_actuals (report_month, param_id, actual, source)
                        VALUES (?, ?, ?, 'excel')
                        ON CONFLICT(report_month, param_id) DO UPDATE SET
                            actual = excluded.actual, source = excluded.source
                    """, (month, row[0], r["month_actual"]))
                    saved_te += 1
            conn.commit()
        finally:
            conn.close()

        # Persist inline item_name corrections made on the preview so future
        # extractions for this plant map those PDF labels automatically.
        saved_aliases = 0
        for o in payload.get("item_overrides", []):
            if o.get("pdf_label") and o.get("item_name"):
                db.save_pdf_item_alias(plant, o["pdf_label"], o["item_name"],
                                       1 if o.get("convert_t", 1) else 0)
                saved_aliases += 1

        for r in payload.get("techno_param_rows", []):
            if r.get("actual") is None and r.get("cum_actual") is None:
                continue
            pid = db.get_or_create_techno_param(
                r.get("group_code", ""), r.get("section", ""), r.get("parameter", ""),
                r.get("unit", ""), r.get("sort_order", 0))
            src_pri = r.get("source_priority", 5)
            db.save_techno_value(month, pid, r.get("actual"),
                                 till_month_actual=r.get("cum_actual"),
                                 source_priority=src_pri)
            # Mirror to canonical MAJOR param at priority 4 (won't overwrite manual priority-5 entries)
            major_pid = _IM_AVG_TO_MAJOR.get(pid)
            if major_pid:
                db.save_techno_value(month, major_pid, r.get("actual"), r.get("cum_actual"),
                                     source_priority=4)
            saved_mill += 1

        saved_ss = 0
        _ss_rows_to_save = [r for r in payload.get("special_steel_rows", []) if r.get("status") == "ok"]
        if _ss_rows_to_save:
            db.clear_special_steel_orders(month, plant)
        for r in _ss_rows_to_save:
            db.save_special_steel_entry(
                month, plant,
                r.get("product", ""), r.get("quality_grade", ""),
                r.get("sort_order", 0),
                r.get("order_qty"), r.get("actual_despatch"),
                section=r.get("section", ""),
            )
            saved_ss += 1

        saved_stock = 0
        for r in payload.get("stock_rows", []):
            if r.get("value") is None:
                continue
            db.save_stock_entry(
                r["stock_month"], r.get("plant", plant),
                r["item_type"], r.get("stock_type", ""),
                r.get("value"),
            )
            saved_stock += 1

        total = saved_prod + saved_plan + saved_te + saved_mill + saved_ss + saved_stock
        if total:
            db.log_extraction(plant, month, payload.get("file_name", ""),
                              payload.get("sheets", ""),
                              payload.get("source_type", "Preview Confirmed"), total)
        # Recompute BF shop averages for plants that have per-furnace cross-plant data.
        # Runs at priority 4 so direct-extracted shop rows (priority 5) are never overwritten.
        agg_written = 0
        if plant in ("BSL", "DSP", "RSP", "BSP"):
            try:
                import sqlite3 as _sqlite3
                from techno_aggregates import compute_bf_shop_averages as _bf_agg
                _conn = _sqlite3.connect(db.DB_PATH)
                agg_written = _bf_agg(_conn, month, plants=[plant])
                _conn.close()
            except Exception:
                pass  # aggregation failure must not block the main save

        msg = (f"Inserted {saved_prod} production, {saved_plan} plan, {saved_te} techno, "
               f"{saved_mill} mill techno, {saved_ss} special steel, {saved_stock} opening stock values for {plant} {month}.")
        if agg_written:
            msg += f" Computed {agg_written} BF shop aggregate row(s)."
        if saved_aliases:
            msg += f" Remembered {saved_aliases} item-name mapping(s) for future extractions."
        return {
            "status": "success",
            "saved_production": saved_prod,
            "saved_plan": saved_plan,
            "saved_techno": saved_te,
            "saved_mill_techno": saved_mill,
            "saved_special_steel": saved_ss,
            "saved_stock": saved_stock,
            "saved_aliases": saved_aliases,
            "message": msg,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Insertion failed: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Techno parameter extraction (preview → confirm → insert)
# ---------------------------------------------------------------------------

@app.post("/api/extract-techno")
async def extract_techno_preview(
    file: UploadFile = File(...),
    plant_name: str = Form(...),
    month: str = Form(...),
):
    """Extract techno parameters from an uploaded plant report.
    Returns a preview only — nothing is written to the DB."""
    import shutil
    import tempfile
    import sys

    if plant_name != "RSP":
        raise HTTPException(status_code=400,
                            detail=f"Techno extraction is currently only supported for RSP, not {plant_name}.")

    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    suffix = os.path.splitext(file.filename)[1]
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "excel_extractors")))
        import excel_extractor_rsp_techno
        result = excel_extractor_rsp_techno.extract_techno(tmp_path, month)
        result["file_name"] = file.filename
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Techno extraction failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@app.post("/api/techno-entries")
async def save_techno_entries(payload: dict):
    """Insert previously previewed techno rows into the DB (user-confirmed)."""
    month = payload.get("month")
    rows = payload.get("rows", [])
    if not month or not rows:
        raise HTTPException(status_code=400, detail="month and rows are required")

    saved = 0
    for r in rows:
        if r.get("actual") is None and r.get("cum_actual") is None:
            continue
        pid = db.get_or_create_techno_param(
            r.get("group_code", ""), r.get("section", ""), r.get("parameter", ""),
            r.get("unit", ""), r.get("sort_order", 0))
        db.save_techno_value(month, pid, r.get("actual"), r.get("cum_actual"))
        saved += 1

    plant = payload.get("plant", "")
    if saved:
        db.log_extraction(plant, month, payload.get("file_name", ""), "techno",
                          "techno_params", saved)
    agg_written = 0
    if plant in ("BSL", "DSP", "RSP", "BSP"):
        try:
            import sqlite3 as _sqlite3
            from techno_aggregates import compute_bf_shop_averages as _bf_agg
            _conn = _sqlite3.connect(db.DB_PATH)
            agg_written = _bf_agg(_conn, month, plants=[plant])
            _conn.close()
        except Exception:
            pass
    return {"status": "success", "saved": saved,
            "message": (f"Inserted {saved} techno parameter values for {plant} {month}."
                        + (f" Computed {agg_written} BF shop aggregate row(s)." if agg_written else ""))}


# ---------------------------------------------------------------------------
# Production data entry
# ---------------------------------------------------------------------------

@app.get("/api/extraction-log")
async def get_extraction_log(limit: int = 60):
    return {"logs": db.get_extraction_logs(limit=limit)}


@app.post("/api/debug-column-detection")
async def debug_column_detection(
    file: UploadFile = File(...),
    month: str = Form(...),
):
    """Debug endpoint: Show which columns are detected for production extraction."""
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

        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "excel_extractors")))

        import asyncio, concurrent.futures
        loop = asyncio.get_running_loop()

        import excel_extractor_dsp

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            # Try extracting with all_months, fall back if not supported
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        pool,
                        lambda: excel_extractor_dsp.extract_preview(
                            tmp_path, month, block="production", all_months=True)
                    ),
                    timeout=300.0,
                )
            except TypeError as e:
                if "all_months" in str(e):
                    # Fall back to single month extraction
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            pool,
                            lambda: excel_extractor_dsp.extract_preview(
                                tmp_path, month, block="production")
                        ),
                        timeout=300.0,
                    )
                else:
                    raise
        finally:
            pool.shutdown(wait=False)

        # Return production rows grouped by item
        prod_data = result.get("production_rows", [])

        return {
            "month": month,
            "pdf_report_month": result.get("pdf_report_month"),
            "total_rows": len(prod_data),
            "rows": prod_data,
            "note": "All-months extraction - check if multiple months per item, and which month value appears"
        }

    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__,
        }

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass


@app.post("/api/debug-techno-extraction")
async def debug_techno_extraction(
    file: UploadFile = File(...),
    month: str = Form(...),
):
    """Debug endpoint: Extract and return techno data with detailed column info."""
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

        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "excel_extractors")))

        import asyncio, concurrent.futures
        loop = asyncio.get_running_loop()

        import excel_extractor_dsp
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    pool,
                    lambda: excel_extractor_dsp.extract_preview(
                        tmp_path, month, block="techno")
                ),
                timeout=300.0,
            )
        finally:
            pool.shutdown(wait=False)

        # Return only techno data
        techno_data = result.get("techno_param_rows", [])

        # Group by section for easier debugging
        by_section = {}
        for row in techno_data:
            section = row.get("section", "Unknown")
            if section not in by_section:
                by_section[section] = []
            by_section[section].append(row)

        return {
            "month": month,
            "total_rows": len(techno_data),
            "by_section": {
                section: {
                    "count": len(rows),
                    "rows": rows
                }
                for section, rows in by_section.items()
            },
            "raw_rows": techno_data,
        }

    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__,
        }

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass


@app.get("/api/item-mapping-suggestions")
async def get_item_mapping_suggestions(plant: str):
    """Get all previously extracted item names and their PDF label mappings.

    Returns:
      {
        "items": ["Total Sinter", "Hot Metal", ...],  # All item names extracted for this plant
        "aliases": {pdf_label: (item_name, convert_t), ...}  # Saved PDF label → item mappings
      }
    """
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()

    # Get all unique item names for this plant
    cursor.execute(
        "SELECT DISTINCT item_name FROM production_table WHERE plant_name = ? ORDER BY item_name",
        (plant,)
    )
    items = [row[0] for row in cursor.fetchall()]

    conn.close()

    # Get aliases
    aliases = db.get_pdf_item_aliases(plant)

    return {
        "items": items,
        "aliases": {k: list(v) for k, v in aliases.items()}  # Convert tuples to lists for JSON
    }


@app.post("/api/save-item-alias")
async def save_item_alias(payload: dict):
    """Save a PDF label → item name mapping for future extractions.

    Payload:
      {
        "plant": "DSP",
        "pdf_label": "1 nos total",
        "item_name": "Oven Pushing(nos/d)",
        "convert_t": 0
      }
    """
    try:
        plant = payload.get("plant", "")
        pdf_label = payload.get("pdf_label", "")
        item_name = payload.get("item_name", "")
        convert_t = int(payload.get("convert_t", 1))

        if not all([plant, pdf_label, item_name]):
            raise ValueError("Missing required fields: plant, pdf_label, item_name")

        db.save_pdf_item_alias(plant, pdf_label, item_name, convert_t)
        return {"message": f"Saved alias: {pdf_label} → {item_name}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def normalize_item_name(name):
    """Normalize item names to consistent format"""
    if not name:
        return name
    # Convert BF-X to BF#X (remove hyphen before hash)
    name = name.replace('BF-', 'BF#')
    # Standardize spacing and capitalization for common items
    name = name.replace('Oven Pushing(nos/d)', 'Oven Pushing (nos/day)')
    name = name.replace('BILLET', 'Billet')
    name = name.replace('BILLET for Sale', 'Billet for Sale')
    name = name.replace('BOTTOM_POURING_INGOT', 'Bottom Pouring Ingot')
    # Standardize Semis Steel to Saleable Semis
    name = name.replace('Semis Steel', 'Saleable Semis')
    return name.strip()

# Custom sort order for production items
PRODUCTION_ITEM_ORDER = [
    'Oven Pushing (nos/day)',
    'SP-1',
    'SP-2',
    'Total Sinter',
    'BF#2',
    'BF#3',
    'BF#4',
    'Hot Metal',
    'Hot Metal to ASP',
    'Hot Metal to PCM',
    'Billet Caster',
    'Bloom Caster',
    'BRC Bloom',
    'BRC Round',
    'Round Production',
    'BRC',
    'Total Caster',
    'Bottom Pouring Ingot',
    'Total Crude Steel',
    'Pig Iron',
    'WAP',
    'wheel plant',
    'Axle plant',
    'MM',
    'MSM',
    'Finished Steel',
    'Billet for Sale',
    'Blooms for Sale',
    'Saleable Semis',
    'Saleable Steel',
]

@app.get("/api/production-items")
async def get_production_items(plant: str, month: str):
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT item_name, month_actual FROM production_plan_table WHERE plant_name = ? AND report_month = ? ORDER BY item_name",
        (plant, month),
    )
    plan_rows = {}
    for row in cursor.fetchall():
        normalized = normalize_item_name(row[0])
        plan_rows[normalized] = row[1]

    cursor.execute(
        "SELECT item_name, month_actual FROM production_table WHERE plant_name = ? AND report_month = ?",
        (plant, month),
    )
    actual_rows = {}
    for row in cursor.fetchall():
        normalized = normalize_item_name(row[0])
        actual_rows[normalized] = row[1]

    conn.close()

    all_items = set(plan_rows.keys()) | set(actual_rows.keys())

    # Sort items using custom order, with remaining items at the end
    def sort_key(item):
        try:
            return PRODUCTION_ITEM_ORDER.index(item)
        except ValueError:
            # Items not in the custom order appear at the end, sorted alphabetically
            return len(PRODUCTION_ITEM_ORDER) + hash(item)

    sorted_items = sorted(all_items, key=sort_key)

    return {
        "items": [
            {
                "item_name": name,
                "plan_value": plan_rows.get(name),
                "actual_value": actual_rows.get(name),
            }
            for name in sorted_items
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


@app.get("/api/conversion-data")
async def get_conversion_data(fy_start: str = Query(...)):
    """Return Conversion (SAIL) actuals for all 12 months of a financial year."""
    try:
        y = int(fy_start)
    except ValueError:
        return {"data": {}}
    months = [
        f"{y}-04", f"{y}-05", f"{y}-06", f"{y}-07", f"{y}-08", f"{y}-09",
        f"{y}-10", f"{y}-11", f"{y}-12",
        f"{y+1}-01", f"{y+1}-02", f"{y+1}-03",
    ]
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    phs = ",".join("?" for _ in months)
    cur.execute(
        f"SELECT report_month, month_actual FROM production_table "
        f"WHERE plant_name='SAIL' AND item_name='Conversion' AND report_month IN ({phs})",
        months,
    )
    data = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()
    return {"data": {m: data.get(m) for m in months}}


@app.post("/api/conversion-entry")
async def save_conversion_entry(payload: dict):
    """Save Conversion (SAIL) monthly actuals."""
    entries = payload.get("entries", [])
    saved = 0
    for e in entries:
        month = str(e.get("month", "")).strip()
        value = e.get("value")
        if not month or value is None:
            continue
        db.save_production_actual(month, "SAIL", "Conversion", float(value))
        saved += 1
    return {"status": "success", "saved": saved}


@app.get("/api/stock-data")
async def get_stock_data(plant: str = Query(...), stock_month: str = Query(...)):
    """Return all stock entries for a plant + stock_month."""
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT item_type, stock_type, stock FROM stock_table "
        "WHERE plant_name=? AND stock_month=? ORDER BY item_type, stock_type",
        (plant, stock_month),
    )
    rows = [{"item_type": r[0], "stock_type": r[1] or "", "stock": r[2]} for r in cur.fetchall()]
    conn.close()
    return {"plant": plant, "stock_month": stock_month, "data": rows}


@app.post("/api/stock-entry")
async def save_stock_entry_manual(payload: dict):
    """Upsert one or more stock entries manually. Values must be in '000T."""
    entries = payload.get("entries", [])
    saved = 0
    for e in entries:
        plant      = str(e.get("plant", "")).strip()
        stock_month = str(e.get("stock_month", "")).strip()
        item_type  = str(e.get("item_type", "")).strip()
        stock_type = str(e.get("stock_type", "")).strip()
        stock      = e.get("stock")
        if not plant or not stock_month or not item_type:
            continue
        db.save_stock_entry(stock_month, plant, item_type, stock_type,
                            float(stock) if stock is not None else None)
        saved += 1
    return {"status": "success", "saved": saved,
            "message": f"Saved {saved} opening stock entry/entries."}


@app.get("/api/techno-targets")
async def get_techno_targets(fy: str = Query("2026-27")):
    """
    Return SAIL consolidated techno plan/targets for the given FY.
    Migration endpoint: Uses new techno_sail_plan structure.
    Response: { fy, data: {param: value} }
    """
    try:
        # Convert FY to report_month format (e.g., "2026-27" -> "2026-03" for March of that FY)
        fy_year = int(fy.split('-')[0])
        report_month = f"{fy_year}-03"  # FY targets stored as March of that year

        plan_data = db.get_sail_techno_plan(report_month)
        return {"fy": fy, "report_month": report_month, "data": plan_data}
    except Exception as e:
        return {"fy": fy, "data": {}, "error": str(e)}


@app.post("/api/techno-targets")
async def save_techno_targets(payload: dict):
    """
    Save SAIL consolidated techno plan/targets.
    Migration endpoint: Uses new techno_sail_plan structure.
    Payload: { fy: str, data: {param: value} }
    """
    try:
        fy = payload.get("fy", "")
        data = payload.get("data", {})

        if not fy:
            raise ValueError("fy is required")

        # Convert FY to report_month format
        fy_year = int(fy.split('-')[0])
        report_month = f"{fy_year}-03"  # FY targets stored as March of that year

        db.save_sail_techno_plan(report_month, data)

        return {"status": "success", "fy": fy, "report_month": report_month, "saved": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Plant registry and unit-type catalogue
# ---------------------------------------------------------------------------

@app.get("/api/plant-units")
async def api_plant_units(plant_code: str = Query(None), unit_type: str = Query(None)):
    """
    Return plant_units rows.  Filter by plant_code and/or unit_type.
    Response: { units: [{unit_id, plant_code, unit_type, unit_name, display_label, is_shop}] }
    """
    from plant_registry import get_plant_units
    conn = sqlite3.connect(db.DB_PATH)
    units = get_plant_units(conn, plant_code=plant_code, unit_type=unit_type)
    conn.close()
    return {"units": units}


@app.get("/api/param-types")
async def api_param_types(unit_type: str = Query(None)):
    """
    Return techno_param_types rows (standard parameter catalogue per unit type).
    Response: { param_types: [{type_id, unit_type, param_name, unit_of_meas, agg_method, sort_order}] }
    """
    from plant_registry import get_param_types
    conn = sqlite3.connect(db.DB_PATH)
    pts = get_param_types(conn, unit_type=unit_type)
    conn.close()
    return {"param_types": pts}


# ---------------------------------------------------------------------------
# Techno group metadata
# ---------------------------------------------------------------------------

_GROUP_META = {
    'IRON_MAKING': {'label': 'Iron Making — Blast Furnace',  'type': 'entry'},
    'COKE_SINTER': {'label': 'Coke & Sinter',                 'type': 'entry'},
    'SMS':         {'label': 'Steel Making — SMS',            'type': 'entry'},
    'MILL_BSP':    {'label': 'Mills — BSP',                   'type': 'entry'},
    'MILL_DSP':    {'label': 'Mills — DSP',                   'type': 'entry'},
    'MILL_RSP':    {'label': 'Mills — RSP',                   'type': 'entry'},
    'MILL_BSL':    {'label': 'Mills — BSL',                   'type': 'entry'},
    'MILL_ISP':    {'label': 'Mills — ISP',                   'type': 'entry'},
    'MILLS':       {'label': 'Mills — All Plants',            'type': 'entry'},
    'GENERAL':     {'label': 'General / Plant-level',         'type': 'entry'},
    'MAJOR':       {'label': 'Major — Page 27 Display',       'type': 'page'},
}

# ---------------------------------------------------------------------------
# Techno manual data entry
# ---------------------------------------------------------------------------

@app.get("/api/production-records")
async def get_production_records():
    """Return best/2nd-best production stats by month, quarter, half, and top-5 years."""
    try:
        return generate_records()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-groups")
async def get_techno_groups():
    """Return distinct group_codes with labels and types."""
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT group_code, COUNT(*) as cnt
        FROM techno_param_group
        GROUP BY group_code
        ORDER BY group_code
    """)
    rows = []
    for group_code, cnt in cur.fetchall():
        meta = _GROUP_META.get(group_code, {'label': group_code, 'type': 'entry'})
        rows.append({
            "group_code": group_code,
            "label": meta['label'],
            "type": meta['type'],
            "param_count": cnt
        })
    conn.close()
    return {"groups": rows}


@app.get("/api/techno-monthly-data")
async def get_techno_monthly_data(group_code: str = Query(...), month: str = Query(...)):
    """Return all params for a group with their current monthly actual and till_month_actual."""
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT p.param_name, p.row_label, p.unit, p.param_id, g.sort_order,
               a.actual, a.till_month_actual, a.source
        FROM techno_param p
        JOIN techno_param_group g ON p.param_id = g.param_id
        LEFT JOIN techno_actuals a ON a.param_id = p.param_id AND a.report_month = ?
        WHERE g.group_code = ?
        ORDER BY g.sort_order, p.param_id
    """, (month, group_code))
    rows = cur.fetchall()
    conn.close()

    sections_map = {}
    section_order = []
    for param_name, row_label, unit, param_id, _, actual, till_month_actual, source in rows:
        if param_name not in sections_map:
            sections_map[param_name] = {"section": param_name, "unit": unit, "rows": []}
            section_order.append(param_name)
        sections_map[param_name]["rows"].append({
            "param_id": param_id,
            "row_label": row_label,
            "unit": unit,
            "actual": actual,
            "till_month_actual": till_month_actual,
            "source": source,
        })

    return {
        "group_code": group_code,
        "month": month,
        "sections": [sections_map[s] for s in section_order],
    }


@app.post("/api/techno-manual-save")
async def save_techno_manual(payload: dict):
    """
    Save manually entered techno values.
    Payload: { group_code, month, rows: [{param_id, actual, till_month_actual}] }
    """
    month = payload.get("month", "")
    rows = payload.get("rows", [])
    if not month or not rows:
        raise HTTPException(status_code=400, detail="month and rows are required")

    saved = 0
    cleared = 0
    for r in rows:
        param_id = r.get("param_id")
        if param_id is None:
            continue
        clear = r.get("clear", False)

        if clear:
            conn = sqlite3.connect(db.DB_PATH)
            conn.execute("DELETE FROM techno_actuals WHERE param_id=? AND report_month=?",
                         (param_id, month))
            conn.commit()
            conn.close()
            cleared += 1
            continue

        def _flt(x):
            try:
                return float(x) if x not in (None, "", "–", "-") else None
            except (ValueError, TypeError):
                return None

        actual           = _flt(r.get("actual"))
        till_month_actual = _flt(r.get("till_month_actual"))

        if actual is None and till_month_actual is None:
            continue

        db.save_techno_monthly(param_id, month, actual, till_month_actual, source_priority=5)
        saved += 1

    return {
        "status": "success",
        "saved": saved,
        "cleared": cleared,
        "message": f"Saved {saved} value(s), cleared {cleared} value(s) for {month}.",
    }


@app.get("/api/sail-sms-params")
def get_sail_sms_params(month: str = Query(..., description="YYYY-MM")):
    """
    Calculate SAIL consolidated SMS parameters (Hot Metal Consumption, Scrap Consumption)
    using weighted average by Crude Steel production.

    Returns: {
        "month": "2026-03",
        "sail_params": {
            "Hot Metal Consumption": {
                "actual": 1042.90,
                "till_month_actual": 1042.35,
                "source": "calculated",  # or "db"
                "unit": "Kg/TCS"
            },
            "Scrap Consumption": { ... }
        }
    }
    """

    SMS_SHOPS = [
        "BSP SMS-2", "BSP SMS-3", "DSP SMS",
        "RSP SMS-1", "RSP SMS-2",
        "BSL SMS-1", "BSL SMS-2",
        "ISP SMS-1",
    ]

    SMS_SHOP_PLANT = {
        "BSP SMS-2": "BSP", "BSP SMS-3": "BSP", "DSP SMS": "DSP",
        "RSP SMS-1": "RSP", "RSP SMS-2": "RSP",
        "BSL SMS-1": "BSL", "BSL SMS-2": "BSL", "ISP SMS-1": "ISP",
    }

    SMS_PARAMS = ["Hot Metal Consumption", "Scrap Consumption"]

    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()

    result = {"month": month, "sail_params": {}}

    # First check if SAIL values exist in DB
    cursor.execute(
        """SELECT p.param_name, a.actual, a.till_month_actual
           FROM techno_actuals a
           JOIN techno_param p ON a.param_id = p.param_id
           WHERE p.row_label = 'SAIL'
             AND a.report_month = ?
             AND p.param_name IN ('Hot Metal Consumption', 'Scrap Consumption')""",
        (month,)
    )

    db_values = {}
    for param_name, actual, till_month in cursor.fetchall():
        db_values[param_name] = (actual, till_month, "db")

    # Get SMS shop values
    cursor.execute(
        """SELECT p.row_label, p.param_name, a.actual, a.till_month_actual
           FROM techno_actuals a
           JOIN techno_param p ON a.param_id = p.param_id
           WHERE p.param_name IN ('Hot Metal Consumption', 'Scrap Consumption')
             AND a.report_month = ?
             AND p.row_label IN ({})""".format(','.join(['?' for _ in SMS_SHOPS])),
        [month] + SMS_SHOPS
    )

    sms_values = {}
    for shop, param_name, actual, till_month in cursor.fetchall():
        if param_name not in sms_values:
            sms_values[param_name] = {}
        sms_values[param_name][shop] = (actual, till_month)

    # Get Crude Steel production (monthly and YTD)
    cursor.execute(
        """SELECT plant_name, month_actual
           FROM production_table
           WHERE item_name = 'Total Crude Steel'
             AND report_month = ?""",
        (month,)
    )

    cs_monthly = {}
    for plant, value in cursor.fetchall():
        if value is not None:
            cs_monthly[plant] = value

    # Get YTD Crude Steel (sum from Apr to this month)
    # Extract year and month from the month string
    year, month_num = month.split('-')
    year, month_num = int(year), int(month_num)

    # Build list of months from Apr (04) of previous year to current month
    ytd_months = []
    if month_num >= 4:
        # Same fiscal year
        for m in range(4, month_num + 1):
            ytd_months.append(f"{year}-{m:02d}")
    else:
        # Previous fiscal year started in Apr of previous year
        prev_year = year - 1
        for m in range(4, 13):
            ytd_months.append(f"{prev_year}-{m:02d}")
        for m in range(1, month_num + 1):
            ytd_months.append(f"{year}-{m:02d}")

    cursor.execute(
        """SELECT plant_name, SUM(month_actual) as ytd_cs
           FROM production_table
           WHERE item_name = 'Total Crude Steel'
             AND report_month IN ({})
           GROUP BY plant_name""".format(','.join(['?' for _ in ytd_months])),
        ytd_months
    )

    cs_ytd = {}
    for plant, value in cursor.fetchall():
        if value is not None:
            cs_ytd[plant] = value

    conn.close()

    # Calculate weighted averages for each parameter
    for param_name in SMS_PARAMS:
        # Check if value exists in DB
        if param_name in db_values:
            actual, till_month, source = db_values[param_name]
            result["sail_params"][param_name] = {
                "actual": actual,
                "till_month_actual": till_month,
                "source": source,
                "unit": "Kg/TCS"
            }
            continue

        # Calculate if not in DB
        if param_name not in sms_values or not sms_values[param_name]:
            continue

        shop_values = sms_values[param_name]

        # Count shops per plant
        shops_per_plant = {}
        for shop in SMS_SHOPS:
            plant = SMS_SHOP_PLANT[shop]
            shops_per_plant[plant] = shops_per_plant.get(plant, 0) + 1

        # Calculate weighted averages directly from SMS shops
        # Each shop gets equal share of its plant's CS production
        monthly_sum = 0.0
        total_cs_monthly_sum = 0.0
        ytd_sum = 0.0
        total_cs_ytd_sum = 0.0

        for shop in SMS_SHOPS:
            if shop not in shop_values:
                continue

            actual, till = shop_values[shop]
            plant = SMS_SHOP_PLANT[shop]

            # Each shop gets equal share of plant's CS
            cs_m = cs_monthly.get(plant, 0) / shops_per_plant[plant]
            cs_y = cs_ytd.get(plant, 0) / shops_per_plant[plant]

            if actual is not None:
                monthly_sum += actual * cs_m
                total_cs_monthly_sum += cs_m

            if till is not None:
                ytd_sum += till * cs_y
                total_cs_ytd_sum += cs_y

        actual_value = monthly_sum / total_cs_monthly_sum if total_cs_monthly_sum > 0 else None
        till_value = ytd_sum / total_cs_ytd_sum if total_cs_ytd_sum > 0 else None

        if actual_value is not None or till_value is not None:
            result["sail_params"][param_name] = {
                "actual": actual_value,
                "till_month_actual": till_value,
                "source": "calculated",
                "unit": "Kg/TCS"
            }

    return result


# ---------------------------------------------------------------------------
# IPT (Inter-Plant Transfer) data entry
# ---------------------------------------------------------------------------

@app.get("/api/ipt-entries")
def get_ipt_entries(month: str = Query(..., description="YYYY-MM")):
    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        SELECT item, from_plant, to_plant, unit, sort_order,
               plan, actual, plan_tonnage, actual_tonnage
        FROM ipt_table WHERE report_month = ?
        ORDER BY sort_order, item, from_plant, to_plant
    """, (month,))
    rows = [
        {"item": r[0], "from_plant": r[1], "to_plant": r[2],
         "unit": r[3], "sort_order": r[4] if r[4] is not None else 0,
         "plan": r[5], "actual": r[6],
         "plan_tonnage": r[7], "actual_tonnage": r[8]}
        for r in cur.fetchall()
    ]
    conn.close()
    return {"month": month, "rows": rows}


@app.post("/api/ipt-entry")
async def save_ipt_entry_api(payload: dict):
    month = payload.get("month", "")
    if not month:
        raise HTTPException(status_code=400, detail="month is required")

    def _flt(v):
        try:
            return float(v) if v not in (None, "", "-", "--") else None
        except (ValueError, TypeError):
            return None

    try:
        db.save_ipt_entry(
            month=month,
            item=payload["item"],
            from_plant=payload["from_plant"],
            to_plant=payload["to_plant"],
            unit=payload.get("unit", "T"),
            sort_order=int(payload.get("sort_order") or 0),
            plan=_flt(payload.get("plan")),
            actual=_flt(payload.get("actual")),
            plan_tonnage=_flt(payload.get("plan_tonnage")),
            actual_tonnage=_flt(payload.get("actual_tonnage")),
        )
        return {"status": "ok", "message": "Saved."}
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ipt-delete")
async def delete_ipt_entry_api(payload: dict):
    month      = payload.get("month", "")
    item       = payload.get("item", "")
    from_plant = payload.get("from_plant", "")
    to_plant   = payload.get("to_plant", "")
    if not all([month, item, from_plant, to_plant]):
        raise HTTPException(status_code=400, detail="month, item, from_plant, to_plant required")
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute(
        "DELETE FROM ipt_table WHERE report_month=? AND item=? AND from_plant=? AND to_plant=?",
        (month, item, from_plant, to_plant),
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Deleted."}


@app.get("/api/techno-parameters")
async def get_techno_parameters():
    """Get list of all available techno parameters"""
    try:
        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT param_name FROM techno_param
            WHERE param_name IS NOT NULL AND param_name != ''
            ORDER BY param_name
        """)
        rows = cursor.fetchall()
        conn.close()
        parameters = [row['param_name'] for row in rows]
        return {"parameters": parameters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-data")
async def get_techno_data(plants: str = Query(""), parameters: str = Query("")):
    """Get techno data for selected plants and parameters
    Query params:
      - plants: comma-separated plant codes (e.g., "BSP,RSP,DSP")
      - parameters: comma-separated parameter names
    """
    try:
        if not plants or not parameters:
            raise HTTPException(status_code=400, detail="plants and parameters parameters required")

        plant_list = [p.strip() for p in plants.split(',') if p.strip()]
        param_list = [p.strip() for p in parameters.split(',') if p.strip()]

        if not plant_list or not param_list:
            raise HTTPException(status_code=400, detail="At least one plant and parameter required")

        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get techno data for selected plants and parameters
        placeholders_plants = ','.join('?' * len(plant_list))
        placeholders_params = ','.join('?' * len(param_list))

        cursor.execute(f"""
            SELECT
                tp.param_name,
                tp.row_label as plant,
                ta.report_month,
                ta.actual,
                ta.till_month_actual
            FROM techno_actuals ta
            JOIN techno_param tp ON ta.param_id = tp.param_id
            WHERE tp.row_label IN ({placeholders_plants})
              AND tp.param_name IN ({placeholders_params})
            ORDER BY tp.param_name, tp.row_label, ta.report_month
        """, plant_list + param_list)

        rows = cursor.fetchall()
        conn.close()

        # Format data by plant and parameter
        data = {}
        for row in rows:
            param = row['param_name']
            plant = row['plant']
            month = row['report_month']
            value = row['actual']

            if plant not in data:
                data[plant] = {}
            if param not in data[plant]:
                data[plant][param] = {}

            data[plant][param][month] = value

        # For "All" plants, try to get SAIL consolidated values
        # Also add SAIL data if not already included
        if 'all' in [p.lower() for p in plant_list]:
            # Fetch SAIL data
            cursor.execute(f"""
                SELECT
                    tp.param_name,
                    ta.report_month,
                    ta.actual
                FROM techno_actuals ta
                JOIN techno_param tp ON ta.param_id = tp.param_id
                WHERE tp.row_label = 'SAIL'
                  AND tp.param_name IN ({placeholders_params})
                ORDER BY tp.param_name, ta.report_month
            """, param_list)

            sail_rows = cursor.fetchall()
            if 'SAIL' not in data:
                data['SAIL'] = {}
            for row in sail_rows:
                param = row['param_name']
                month = row['report_month']
                value = row['actual']
                if param not in data['SAIL']:
                    data['SAIL'][param] = {}
                data['SAIL'][param][month] = value

        return {"data": data, "plants": plant_list, "parameters": param_list, "has_sail": 'SAIL' in data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Techno Plan (Targets) API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/techno-plan")
async def get_techno_plan(plant: str = Query(...), report_month: str = Query(...)):
    """
    Get techno plan data for a plant/month.
    Response: { plant, report_month, data: {unit: {param: value}} }
    """
    try:
        plan_data = db.get_techno_plan(plant, report_month)
        return {"plant": plant, "report_month": report_month, "data": plan_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/techno-plan")
async def save_techno_plan(payload: dict):
    """
    Save techno plan data.
    Payload: { plant, report_month, unit, techno_json, source_file? }
    """
    try:
        plant = payload.get("plant")
        report_month = payload.get("report_month")
        unit = payload.get("unit", "")
        techno_json = payload.get("techno_json", "{}")
        source_file = payload.get("source_file", "")

        if not all([plant, report_month]):
            raise ValueError("plant and report_month required")

        if isinstance(techno_json, dict):
            techno_json = json.dumps(techno_json)

        db.save_techno_plan(plant, report_month, unit, techno_json, source_file)
        return {"status": "success", "plant": plant, "report_month": report_month}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-plant-plan")
async def get_techno_plant_plan(plant: str = Query(...), report_month: str = Query(...)):
    """
    Get aggregated plant-level techno plan data.
    Response: { plant, report_month, data: {param: {value, unit, ...}} }
    """
    try:
        plan_data = db.get_techno_plant_plan(plant, report_month)
        return {"plant": plant, "report_month": report_month, "data": plan_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/techno-plant-plan")
async def save_techno_plant_plan(payload: dict):
    """
    Save aggregated plant-level techno plan data.
    Payload: { plant, report_month, data: {param: {value, unit, ...}}, calculation_details? }
    """
    try:
        plant = payload.get("plant")
        report_month = payload.get("report_month")
        data = payload.get("data", {})
        calculation_details = payload.get("calculation_details")

        if not all([plant, report_month]):
            raise ValueError("plant and report_month required")

        db.save_techno_plant_plan(plant, report_month, data, calculation_details)
        return {"status": "success", "plant": plant, "report_month": report_month}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sail-techno-plan")
async def get_sail_techno_plan(report_month: str = Query(...)):
    """
    Get SAIL consolidated techno plan data.
    Response: { report_month, data: {param: {value, unit, ...}} }
    """
    try:
        plan_data = db.get_sail_techno_plan(report_month)
        return {"report_month": report_month, "data": plan_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sail-techno-plan")
async def save_sail_techno_plan(payload: dict):
    """
    Save SAIL consolidated techno plan data.
    Payload: { report_month, data: {param: {value, unit, ...}} }
    """
    try:
        report_month = payload.get("report_month")
        data = payload.get("data", {})

        if not report_month:
            raise ValueError("report_month required")

        db.save_sail_techno_plan(report_month, data)
        return {"status": "success", "report_month": report_month}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-plan-months")
async def list_techno_plan_months(plant: str = Query(None)):
    """
    List available months in techno_plan table, optionally filtered by plant.
    Response: { months: ["2026-04", "2026-05", ...] }
    """
    try:
        months = db.list_techno_plan_months(plant)
        return {"months": months}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-major-parameters")
async def get_techno_major_parameters():
    """
    Get list of MAJOR techno-economic parameters grouped by type.
    BF params: weighted by plant HM production
    SMS params: weighted by plant Crude Steel production
    Response: { bf_params: [...], sms_params: [...] }
    """
    bf_params = [
        {"name": "Coal to Hot Metal", "unit": "kg/kg"},
        {"name": "Coke Rate", "unit": "kg/thm"},
        {"name": "Nut Coke Rate", "unit": "kg/thm"},
        {"name": "CDI Rate", "unit": "kg/thm"},
        {"name": "Fuel Rate", "unit": "kg/thm"},
        {"name": "Sinter in Burden", "unit": "%"},
        {"name": "Pellet in Burden", "unit": "%"},
        {"name": "BF Productivity", "unit": "t/m³/day"},
        {"name": "Specific Energy Consumption", "unit": "Gcal/tcs"},
    ]
    sms_params = [
        {"name": "Hot Metal Consumption", "unit": "kg/tcs"},
        {"name": "Scrap Consumption", "unit": "kg/tcs"},
        {"name": "TMI", "unit": "kg/tcs"},
    ]
    sms_shops = [
        "BSP SMS-2", "BSP SMS-3",
        "DSP SMS",
        "RSP SMS-1", "RSP SMS-2",
        "BSL SMS-1", "BSL SMS-2",
        "ISP SMS-1",
    ]
    return {
        "bf_params": bf_params,
        "sms_params": sms_params,
        "sms_shops": sms_shops,
    }


@app.get("/api/techno-sail-targets")
async def get_techno_sail_targets(fy: str = Query("2026-27")):
    """
    Get SAIL techno targets for a given FY.
    Response: { fy, report_month, targets: {param: value} }
    """
    try:
        fy_year = int(fy.split("-")[0])
        report_month = f"{fy_year}-03"

        targets = db.get_sail_techno_plan(report_month)
        return {"fy": fy, "report_month": report_month, "targets": targets}
    except Exception as e:
        return {"fy": fy, "targets": {}, "error": str(e)}


@app.post("/api/techno-sail-targets")
async def save_techno_sail_targets(payload: dict):
    """
    Save SAIL techno targets.
    Payload: { fy: str, targets: {param: value} }
    """
    try:
        fy = payload.get("fy", "")
        targets = payload.get("targets", {})

        if not fy:
            raise ValueError("fy is required")

        fy_year = int(fy.split("-")[0])
        report_month = f"{fy_year}-03"

        db.save_sail_techno_plan(report_month, targets)
        return {"status": "success", "fy": fy, "report_month": report_month}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/techno-recalculate-sail")
async def recalculate_sail_targets(payload: dict):
    """
    Recalculate SAIL targets from plant-level targets.
    Payload: { fy: str }
    """
    try:
        fy = payload.get("fy", "")
        if not fy:
            raise ValueError("fy is required")

        from page_techno import compute_sail_targets
        computed = compute_sail_targets(fy)

        return {"status": "success", "fy": fy, "computed": computed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-plant-targets")
async def get_techno_plant_targets(fy: str = Query("2026-27"), plant: str = Query(None)):
    """
    Get plant-level techno targets for a given FY.
    If plant specified, return targets for that plant only.
    Otherwise return for all 5 plants.
    Response: { fy, report_month, plants: {plant: {param: value}} }
    """
    try:
        fy_year = int(fy.split("-")[0])
        report_month = f"{fy_year}-03"

        plants_to_fetch = [plant] if plant else ["BSP", "DSP", "RSP", "BSL", "ISP"]
        result = {}

        for p in plants_to_fetch:
            plant_data = db.get_techno_plant_plan(p, report_month)
            result[p] = {}
            for param_name, param_info in plant_data.items():
                if isinstance(param_info, dict):
                    value = param_info.get('value')
                else:
                    value = param_info
                if value is not None:
                    result[p][param_name] = value

        return {"fy": fy, "report_month": report_month, "plants": result}
    except Exception as e:
        return {"fy": fy, "plants": {}, "error": str(e)}


@app.post("/api/techno-plant-targets")
async def save_techno_plant_targets(payload: dict):
    """
    Save plant-level techno targets.
    Payload: { fy: str, plants: {plant: {param: value}} }
    """
    try:
        fy = payload.get("fy", "")
        plants_data = payload.get("plants", {})

        if not fy:
            raise ValueError("fy is required")

        fy_year = int(fy.split("-")[0])
        report_month = f"{fy_year}-03"

        saved_count = 0
        for plant, params in plants_data.items():
            if params:
                db.save_techno_plant_plan(plant, report_month, params)
                saved_count += 1

        return {"status": "success", "fy": fy, "report_month": report_month, "plants_saved": saved_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-sms-targets")
async def get_techno_sms_targets(fy: str = Query("2026-27")):
    """
    Get SMS-wise (shop-wise) techno targets for a given FY.
    Response: { fy, report_month, sms_shops: {shop: {param: value}} }
    """
    try:
        fy_year = int(fy.split("-")[0])
        report_month = f"{fy_year}-03"

        sms_shops = [
            "BSP SMS-2", "BSP SMS-3",
            "DSP SMS",
            "RSP SMS-1", "RSP SMS-2",
            "BSL SMS-1", "BSL SMS-2",
            "ISP SMS-1",
        ]
        result = {}

        for shop in sms_shops:
            shop_data = db.get_techno_plan(shop.split()[0], report_month)
            if shop_data:
                result[shop] = {}
                shop_json = shop_data if isinstance(shop_data, dict) else {}
                for param_name, param_value in shop_json.items():
                    if param_value is not None:
                        result[shop][param_name] = param_value

        return {"fy": fy, "report_month": report_month, "sms_shops": result}
    except Exception as e:
        return {"fy": fy, "sms_shops": {}, "error": str(e)}


@app.post("/api/techno-sms-targets")
async def save_techno_sms_targets(payload: dict):
    """
    Save SMS-wise (shop-wise) techno targets.
    Payload: { fy: str, sms_shops: {shop: {param: value}} }
    """
    try:
        fy = payload.get("fy", "")
        sms_data = payload.get("sms_shops", {})

        if not fy:
            raise ValueError("fy is required")

        fy_year = int(fy.split("-")[0])
        report_month = f"{fy_year}-03"

        saved_count = 0
        for shop, params in sms_data.items():
            if params:
                plant = shop.split()[0]  # Extract plant from "BSP SMS-2"
                unit = shop
                db.save_techno_plan(plant, report_month, unit, json.dumps(params))
                saved_count += 1

        return {"status": "success", "fy": fy, "report_month": report_month, "shops_saved": saved_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/techno-recalculate-sail-weighted")
async def recalculate_sail_weighted(payload: dict):
    """
    Recalculate SAIL targets using weighted averages based on production targets.

    BF Parameters: Weighted by Plant Hot Metal production target
    SMS Parameters: Weighted by Plant Crude Steel production target

    Payload: { fy: str }
    Response: { status, fy, sail_bf: {param: value}, sail_sms: {param: value} }
    """
    try:
        fy = payload.get("fy", "")
        if not fy:
            raise ValueError("fy is required")

        fy_year = int(fy.split("-")[0])
        report_month = f"{fy_year}-03"

        # Get all months of this FY for production targets
        months = (
            [f"{fy_year}-{m:02d}" for m in range(4, 13)] +
            [f"{fy_year + 1}-{m:02d}" for m in range(1, 4)]
        )

        conn = sqlite3.connect(db.DB_PATH)
        cur = conn.cursor()

        # Fetch HM production targets by plant (for BF params)
        ph = ",".join("?" * len(months))
        cur.execute(f"""
            SELECT plant_name, SUM(month_actual)
            FROM production_plan_table
            WHERE report_month IN ({ph}) AND item_name = 'Hot Metal'
              AND plant_name IN ('BSP','DSP','RSP','BSL','ISP')
            GROUP BY plant_name
        """, months)
        hm_weights = {row[0]: row[1] for row in cur.fetchall() if row[1]}

        # Fetch CS production targets by plant (for SMS params)
        cur.execute(f"""
            SELECT plant_name, SUM(month_actual)
            FROM production_plan_table
            WHERE report_month IN ({ph}) AND item_name = 'Total Crude Steel'
              AND plant_name IN ('BSP','DSP','RSP','BSL','ISP')
            GROUP BY plant_name
        """, months)
        cs_weights = {row[0]: row[1] for row in cur.fetchall() if row[1]}

        # Simple weighted average for all SMS shops
        # SAIL = Σ(Shop_Value × Shop_Production) / Σ(Shop_Production)
        shop_to_plant = {
            "BSP SMS-2": "BSP", "BSP SMS-3": "BSP",
            "DSP SMS": "DSP",
            "RSP SMS-1": "RSP", "RSP SMS-2": "RSP",
            "BSL SMS-1": "BSL", "BSL SMS-2": "BSL",
            "ISP SMS-1": "ISP",
        }

        # Fetch SMS-wise Crude Steel production for each shop
        shop_cs_weights = {}
        for shop, plant in shop_to_plant.items():
            # Extract SMS identifier: "BSP SMS-2" → "SMS-2"
            shop_parts = shop.split()
            sms_identifier = " ".join(shop_parts[1:]) if len(shop_parts) > 1 else shop

            # Sum all items matching SMS identifier (e.g., "SMS-2", "SMS-2 BLOOM", "SMS-2 CCM-1")
            cur.execute(f"""
                SELECT SUM(month_actual)
                FROM production_plan_table
                WHERE report_month IN ({ph})
                  AND (item_name = ? OR item_name LIKE ?)
                  AND plant_name = ?
            """, months + [sms_identifier, sms_identifier + " %", plant])

            result = cur.fetchone()
            shop_cs_weights[shop] = result[0] if result[0] else 0

        # Store metadata about production targets used
        production_metadata = {
            "source": "production_plan_table",
            "fy": fy,
            "months_included": months,
            "hm_item": "Hot Metal",
            "cs_item": "Total Crude Steel",
            "hm_weights": hm_weights,
            "cs_weights": cs_weights,
            "shop_cs_weights": {shop: round(w, 2) for shop, w in shop_cs_weights.items()},
            "shop_to_plant": shop_to_plant
        }

        # Get plant-level BF targets
        plants = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']
        bf_targets = {}
        for plant in plants:
            plant_data = db.get_techno_plant_plan(plant, report_month)
            if plant_data:
                for param, value in plant_data.items():
                    v = value.get('value') if isinstance(value, dict) else value
                    if v is not None:
                        if param not in bf_targets:
                            bf_targets[param] = []
                        weight = hm_weights.get(plant, 0)
                        if weight:
                            bf_targets[param].append((v, weight))

        # Calculate weighted averages for BF params with calculation details
        sail_bf = {}
        bf_calc_steps = {}
        for param, values in bf_targets.items():
            if param == "BF Productivity":
                # Harmonic mean for BF Productivity
                num = sum(w for v, w in values)
                denom = sum(w / v if v > 0 else 0 for v, w in values)
                sail_bf[param] = round(num / denom, 3) if denom > 0 else None
                # Store calculation details
                bf_calc_steps[param] = {
                    "formula": "Harmonic Mean: Total HM / Σ(HM/Productivity)",
                    "values": [{"plant": plants[i], "value": v, "hm_weight": w, "reciprocal": round(w/v, 6) if v > 0 else 0} for i, (v, w) in enumerate(values)],
                    "total_hm": num,
                    "sum_reciprocal": round(denom, 6),
                    "result": sail_bf[param]
                }
            elif param == "Fuel Rate":
                # Skip Fuel Rate here - will calculate as Coke + Nut Coke + CDI
                continue
            else:
                # Arithmetic mean for other BF params
                total_val = sum(v * w for v, w in values)
                total_weight = sum(w for v, w in values)
                sail_bf[param] = round(total_val / total_weight, 3) if total_weight else None
                # Store calculation details for Coke Rate
                if param == "Coke Rate":
                    bf_calc_steps[param] = {
                        "formula": "Weighted Average: Σ(Value × HM_Weight) / Σ(HM_Weight)",
                        "values": [{"plant": plants[i], "value": v, "hm_weight": w, "product": round(v*w, 2)} for i, (v, w) in enumerate(values)],
                        "sum_products": round(total_val, 2),
                        "sum_weights": total_weight,
                        "result": sail_bf[param]
                    }

        # Calculate Fuel Rate = Coke Rate + Nut Coke Rate + CDI Rate
        coke_sail = sail_bf.get("Coke Rate")
        nut_coke_sail = sail_bf.get("Nut Coke Rate")
        cdi_sail = sail_bf.get("CDI Rate")
        if coke_sail is not None and nut_coke_sail is not None and cdi_sail is not None:
            sail_bf["Fuel Rate"] = round(coke_sail + nut_coke_sail + cdi_sail, 3)

        # SMS shops and their mapping (shop_cs_weights already fetched above)
        sms_shops = [
            "BSP SMS-2", "BSP SMS-3",
            "DSP SMS",
            "RSP SMS-1", "RSP SMS-2",
            "BSL SMS-1", "BSL SMS-2",
            "ISP SMS-1",
        ]

        # Get SMS targets and calculate weighted avg by shop-wise CS production
        sms_targets = {}
        for param in ["Hot Metal Consumption", "Scrap Consumption"]:
            sms_targets[param] = []
            for shop in sms_shops:
                plant = shop.split()[0]
                # Get shop-level data from techno_plan (unit field contains shop name)
                shop_data = db.get_techno_plan(plant, report_month)
                if isinstance(shop_data, dict):
                    param_val = shop_data.get(param)
                    if param_val is not None:
                        weight = shop_cs_weights.get(shop, 0)
                        if weight:
                            sms_targets[param].append((param_val, weight))

        # Calculate weighted averages for SMS params using shop CS weights
        sail_sms = {}
        sms_calc_steps = {}
        sms_shop_mapping = {
            "BSP SMS-2": "BSP", "BSP SMS-3": "BSP",
            "DSP SMS": "DSP",
            "RSP SMS-1": "RSP", "RSP SMS-2": "RSP",
            "BSL SMS-1": "BSL", "BSL SMS-2": "BSL",
            "ISP SMS-1": "ISP",
        }

        for param, values in sms_targets.items():
            if values:
                total_val = sum(v * w for v, w in values)
                total_weight = sum(w for v, w in values)
                sail_sms[param] = round(total_val / total_weight, 3) if total_weight else None

                # Store calculation details for HM Consumption and Scrap
                if param in ["Hot Metal Consumption", "Scrap Consumption"]:
                    shop_details = []
                    for shop, (v, w) in zip(sms_shops, values):
                        shop_details.append({
                            "shop": shop,
                            "plant": sms_shop_mapping.get(shop),
                            "value": v,
                            "cs_weight": round(w, 2),
                            "product": round(v*w, 2)
                        })
                    sms_calc_steps[param] = {
                        "formula": "Weighted Average: Σ(Shop_Value × Shop_CS) / Σ(Shop_CS)",
                        "description": "Simple weighted average: each SMS shop value weighted by its actual Crude Steel production",
                        "shops": shop_details,
                        "sum_products": round(total_val, 2),
                        "sum_weights": round(total_weight, 2),
                        "result": sail_sms[param]
                    }

        # Calculate TMI as HM + Scrap
        if "Hot Metal Consumption" in sail_sms and "Scrap Consumption" in sail_sms:
            hm = sail_sms["Hot Metal Consumption"]
            sc = sail_sms["Scrap Consumption"]
            if hm is not None and sc is not None:
                sail_sms["TMI"] = round(hm + sc, 3)
                sms_calc_steps["TMI"] = {
                    "formula": "TMI = HM Consumption + Scrap Consumption",
                    "hm_consumption": hm,
                    "scrap_consumption": sc,
                    "result": sail_sms["TMI"]
                }

        conn.close()

        # Save computed SAIL values
        db.save_sail_techno_plan(report_month, {**sail_bf, **sail_sms})

        return {
            "status": "success",
            "fy": fy,
            "report_month": report_month,
            "sail_bf": sail_bf,
            "sail_sms": sail_sms,
            "bf_calculations": bf_calc_steps,
            "sms_calculations": sms_calc_steps,
            "production_metadata": production_metadata,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8082))
    uvicorn.run(app, host="0.0.0.0", port=port)
