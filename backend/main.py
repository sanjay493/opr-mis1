import os
import json
import csv
import io
import re
import sqlite3
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
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
from page_special_steel_trend import generate_special_steel_trend
from page_opening_stock import generate_opening_stock
from page_ipt import generate_ipt
from page_techno import (TECHNO_PAGES, generate_summary_te_table,
                          generate_summary_chart_data, compute_sail_targets,
                          generate_major_techno_from_db, generate_techno_from_db,
                          generate_major_techno_verification, generate_techno_target_columns)
from page_records import generate_records

def _safe_te_table(month):
    try:
        result = generate_summary_te_table(month)
        # Get SAIL plan metadata to check if user-supplied
        fy = int(month[:4])
        m = int(month[5:7])
        fy_year = fy if m >= 4 else fy - 1
        fy_str = f"{fy_year}-{fy_year + 1}"
        sail_plan_result = db.get_sail_techno_plan(fy_str)
        is_user_supplied = sail_plan_result.get('is_user_supplied', False)

        # Return with metadata if it's user-supplied
        if is_user_supplied:
            return {'te_table': result, 'sail_is_user_supplied': True}
        return result
    except Exception:
        return []

def _safe_chart_data(month):
    try:
        return generate_summary_chart_data(month)
    except Exception:
        return {}

def _safe_techno(month, pg):
    try:
        if pg == 27:
            return generate_major_techno_from_db(month)
        elif 28 <= pg <= 35:
            return generate_techno_from_db(month, pg)
        return {}
    except Exception:
        return {}
from pdf import build_pdf_response
from layout_loader import load_layout_config
from api_rsp_techno import router as rsp_techno_router
from api_bsp_techno import router as bsp_techno_router
from api_isp_techno import router as isp_techno_router
from api_dsp_techno import router as dsp_techno_router
from api_unified_techno import router as unified_techno_router
from api_techno_manual import router as techno_manual_router
from api_mcr_techno import router as mcr_techno_router
from api_todo import router as todo_router
from api_worklog import router as worklog_router

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
    "http://localhost", "http://127.0.0.1",
    "http://localhost:3001", "http://127.0.0.1:3001",
    "http://localhost:8000", "http://127.0.0.1:8000",  # Dashboard
    "http://10.135.5.15", "http://10.135.5.15:80",  # LAN frontend on port 80
    "http://10.135.5.15:3000", "http://10.135.5.15:3001",  # LAN access to frontend
    "http://192.168.1.3:3000", "http://192.168.1.3:3001",  # LAN access to frontend
    "http://192.168.1.3:8000", "http://192.168.1.3:8082",  # LAN access to dashboard/API
    "http://10.135.5.15:8000", "http://10.135.5.15:8082",  # LAN access to dashboard/API
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

# Include RSP, BSP, ISP, and DSP Technopara routers
app.include_router(rsp_techno_router)
app.include_router(bsp_techno_router)
app.include_router(isp_techno_router)
app.include_router(dsp_techno_router)
app.include_router(unified_techno_router)
app.include_router(techno_manual_router)
app.include_router(mcr_techno_router)
app.include_router(todo_router)
app.include_router(worklog_router)

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
                    te_result = _safe_te_table(month)
                    # Handle both dict and list returns (for backwards compatibility)
                    if isinstance(te_result, dict) and 'te_table' in te_result:
                        page["te_table"] = te_result['te_table']
                        page["sail_is_user_supplied"] = te_result.get('sail_is_user_supplied', False)
                    else:
                        page["te_table"] = te_result
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
        # Page 24: was "merged into page 23" (stale DB-cached rows from before
        # that merge); now repurposed as the Special Steel trend/performance
        # analysis page (line + bar charts). Strip any stale copy, then insert
        # a fresh placeholder right after page 23 if one isn't already there.
        pages_config = [p for p in pages_config if p.get("page") != 24]
        _idx23 = next((i for i, p in enumerate(pages_config) if p.get("page") == 23), None)
        if _idx23 is not None:
            pages_config.insert(_idx23 + 1, {"page": 24})
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
            if pg == 24:
                page.update(generate_special_steel_trend(month))
            if pg == 25:
                page.update(generate_opening_stock(month))
                page["type"] = "opening_stock"
            if pg == 26:
                page.update(generate_ipt(month))
                page["type"] = "ipt_status"
            if pg in TECHNO_PAGES:
                page.update(_safe_techno(month, pg))
                page["type"] = "techno_params"
                page["orientation"] = "landscape" if 31 <= pg <= 35 else "portrait"

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
    _pages_list = [page.dict() for page in request.pages]
    # Page 24: ensure the trend/performance analysis page is present even for
    # requests built from a page list saved before this page existed.
    if not any(p.get("page") == 24 for p in _pages_list):
        _idx23 = next((i for i, p in enumerate(_pages_list) if p.get("page") == 23), None)
        if _idx23 is not None:
            _pages_list.insert(_idx23 + 1, {"page": 24})
    for p in _pages_list:
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
            p.update(generate_special_steel_trend(request.month))
            p["type"] = "special_steel_trend"
        if pg == 25:
            p.update(generate_opening_stock(request.month))
            p["type"] = "opening_stock"
        if pg == 26:
            p.update(generate_ipt(request.month))
            p["type"] = "ipt_status"
        if pg in TECHNO_PAGES:
            p.update(_safe_techno(request.month, pg))
            p["type"] = "techno_params"
            p["orientation"] = "landscape" if 31 <= pg <= 35 else "portrait"
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
            _ext = os.path.splitext(file.filename or "")[1].lower()
            if _ext in (".png", ".jpg", ".jpeg"):
                # ISP Special Steel arrives as a screenshot of a PPC ISP email,
                # not Excel — OCR it instead.
                import image_extractor_isp_special_steel as _isp_img_mod
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = await loop.run_in_executor(
                        pool,
                        lambda: _isp_img_mod.extract_preview(tmp_path, month)
                    )
            else:
                import excel_extractor_isp
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = await loop.run_in_executor(
                        pool,
                        lambda: excel_extractor_isp.extract_preview(tmp_path, month)
                    )
        elif plant_name == "BSP":
            _ext = os.path.splitext(file.filename or "")[1].lower()
            if _ext == ".pdf":
                # BSP flash monthly PDF — production + techno + closing stock
                import pdf_extractor_bsp_flash as _bsp_mod
            else:
                # Unified BSP Excel extractor — auto-detects:
                # PPC MIS / MIS-2 / Special Steel / OISCO / 3-page-Tech
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
        # Attach current DB values to each production row so the UI can show
        # DB-vs-extracted side by side before the user confirms the insert.
        _resolved_month = result.get("month") or month
        db.enrich_rows_with_db_production(result.get("production_rows", []), plant_name, _resolved_month)
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
                """, (month, plant, normalize_item_name(r.get("item_name")), r.get("value")))
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
                # Note: techno_actuals table no longer exists - skip legacy extraction
                try:
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
                except sqlite3.OperationalError:
                    # techno_actuals table doesn't exist - skip
                    pass
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
    Returns a preview only — nothing is written to the DB.
    Supports: BSL, BSP, DSP, RSP, ISP"""
    import shutil
    import tempfile
    import sys

    # Map plant names to extractor modules
    EXTRACTORS = {
        "BSL": "excel_extractor_bsl",
        "BSP": "excel_extractor_bsp",
        "DSP": "excel_extractor_dsp",
        "RSP": "excel_extractor_rsp_techno",
        "ISP": "excel_extractor_isp",
    }

    if plant_name not in EXTRACTORS:
        raise HTTPException(status_code=400,
                            detail=f"Techno extraction not supported for {plant_name}. "
                                  f"Supported plants: {', '.join(EXTRACTORS.keys())}")

    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    suffix = os.path.splitext(file.filename)[1]
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        # Load the appropriate extractor for the plant
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "excel_extractors")))
        extractor_module = __import__(EXTRACTORS[plant_name])

        # Try extract_preview first (for BSL, other plants), then extract_techno (for RSP)
        if hasattr(extractor_module, 'extract_preview'):
            result = extractor_module.extract_preview(tmp_path, month)
        elif hasattr(extractor_module, 'extract_techno'):
            result = extractor_module.extract_techno(tmp_path, month)
        else:
            raise HTTPException(status_code=400,
                               detail=f"Extractor for {plant_name} has no extract_preview or extract_techno method")

        result["file_name"] = file.filename
        result["plant"] = plant_name
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Techno extraction failed for {plant_name}: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@app.post("/api/bsl-bf-techno/preview")
async def bsl_bf_techno_preview(
    file: UploadFile = File(...),
    month: str = Form(...),
):
    """Extract BSL BF Performance PDF and return editable data preview.

    Returns for-the-MONTH values for all parameters and furnaces, plus the
    financial-year cumulative production and coke rate (the only YTD figures
    the PDF contains).
    """
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

        # Read PDF as text - prefer pdfplumber for better table extraction
        pdf_text = None
        if suffix.lower() == ".pdf":
            try:
                # Try pdfplumber first (better for tables)
                import pdfplumber
                with pdfplumber.open(tmp_path) as pdf:
                    pdf_text = ""
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            pdf_text += text + "\n"
            except:
                try:
                    # Fallback to PyPDF2
                    import PyPDF2
                    with open(tmp_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        pdf_text = ""
                        for page in reader.pages:
                            text = page.extract_text()
                            if text:
                                pdf_text += text + "\n"
                except:
                    raise HTTPException(status_code=400, detail="Could not read PDF. Please install pdfplumber: pip install pdfplumber")
        else:
            raise HTTPException(status_code=400, detail="Please upload a PDF file for BSL BF Performance Report")

        if not pdf_text or len(pdf_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="PDF appears to be empty or unreadable. Check file format.")

        # Extract using BSL MER parser
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "techno_project")))
        from bsl_mer_parser import extract_bsl_mer

        # Extract data
        records = extract_bsl_mer(pdf_text, report_month=month, filename=file.filename)

        # Current DB values per unit, for DB-vs-extracted comparison
        # in the UI before the user confirms the save.
        _existing_bsl = db.get_techno_data("BSL", month)

        # Convert to editable format. The PDF's value pairs are day/month, so
        # the editable grid carries MONTH values; the only genuine FY
        # cumulatives in the report (production, coke rate) ride along as
        # *_ytd fields and are saved into till_month.
        editable_data = []

        _param_keys = [
            "production", "bf_productivity", "coke_rate", "nut_coke_rate", "cdi",
            "fuel_rate", "hot_blast_temp", "o2_enrichment", "slag_rate",
            "sinter_in_burden", "pellet_in_burden",
        ]
        for record in records:
            unit = record['unit']
            techno_json = record['techno_json']
            month_vals = techno_json.get('month', {})
            till_vals  = techno_json.get('till_month', {})
            db_month = _existing_bsl.get(unit, {}).get('month', {})
            db_till  = _existing_bsl.get(unit, {}).get('till_month', {})

            # Map to parameter names for UI
            row = {
                "id": f"{unit}_{month}",
                "unit": unit,
                "db": {
                    **{k: db_month.get(k) for k in _param_keys},
                    "coke_rate_ytd": db_till.get("coke_rate"),
                },
            }
            # production/production_ytd are never stored in techno_data (see
            # save endpoint) - production_table is the only source of truth.
            # production_table stores '000 t; this UI's Production column is
            # in tonnes, so convert back for a like-for-like comparison.
            # BF_Shop has no production_table row of its own, so its "In DB"
            # figure is derived as the sum of the four furnaces.
            if unit.startswith("BF-"):
                _db_prod_kt = db.get_production_actual_value("BSL", unit, month)
                row["db"]["production"] = _db_prod_kt * 1000.0 if _db_prod_kt is not None else None
            elif unit == "BF_Shop":
                _conn = sqlite3.connect(db.DB_PATH)
                _sum_kt = _conn.execute(
                    "SELECT SUM(month_actual) FROM production_table WHERE plant_name='BSL' "
                    "AND report_month=? AND item_name IN ('BF-1','BF-2','BF-4','BF-5')",
                    (month,),
                ).fetchone()[0]
                _conn.close()
                row["db"]["production"] = _sum_kt * 1000.0 if _sum_kt is not None else None
            for k in _param_keys:
                row[k] = month_vals.get(k)
            row["production_ytd"] = till_vals.get("production")
            row["coke_rate_ytd"]  = till_vals.get("coke_rate")
            editable_data.append(row)

        return {
            "status": "success",
            "month": month,
            "file_name": file.filename,
            "data": editable_data,
            "total_records": len(editable_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"BSL BF Performance extraction failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@app.post("/api/bsl-bf-techno/debug")
async def bsl_bf_techno_debug(
    file: UploadFile = File(...),
    month: str = Form(...),
):
    """Debug endpoint: shows raw PDF content and extraction details."""
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

        # Read PDF
        pdf_text = ""
        try:
            import pdfplumber
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pdf_text += text + "\n"
        except:
            try:
                import PyPDF2
                with open(tmp_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text = page.extract_text()
                        if text:
                            pdf_text += text + "\n"
            except:
                raise HTTPException(status_code=400, detail="Could not read PDF")

        # Find production section
        prod_lines = []
        prod_idx = pdf_text.find("PRODUCTION PERFORMANCE")
        if prod_idx > 0:
            qual_idx = pdf_text.find("QUALITY PARAMETERS", prod_idx)
            if qual_idx < 0:
                qual_idx = len(pdf_text)
            prod_section = pdf_text[prod_idx:qual_idx]
            prod_lines = prod_section.split("\n")[0:30]  # First 30 lines

        return {
            "file_name": file.filename,
            "pdf_text_length": len(pdf_text),
            "pdf_preview": pdf_text[0:500],  # First 500 chars
            "production_section_preview": "\n".join(prod_lines),
            "has_production_section": "PRODUCTION PERFORMANCE" in pdf_text,
            "has_quality_section": "QUALITY PARAMETERS" in pdf_text,
            "has_consumption_section": "Consumption" in pdf_text,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass


@app.post("/api/bsl-bf-techno/save")
async def bsl_bf_techno_save(payload: dict):
    """Save edited BSL BF Performance techno data to database."""
    month = payload.get("month")
    data = payload.get("data", [])

    if not month:
        raise HTTPException(status_code=400, detail="Month is required")

    if not data:
        raise HTTPException(status_code=400, detail="No data to save")

    try:
        # Save each record to techno_data table
        _month_keys = [
            "production", "bf_productivity", "coke_rate", "nut_coke_rate", "cdi",
            "fuel_rate", "hot_blast_temp", "o2_enrichment", "slag_rate",
            "sinter_in_burden", "pellet_in_burden",
        ]
        for row in data:
            unit = row.get("unit")
            if not unit:
                continue

            # Furnace-wise month production is saved to production_table
            # below, never to techno_data - production and production_ytd
            # aren't techno-economic parameters, and duplicating them here
            # would just drift out of sync with production_table (the source
            # of truth for the cumulative-weighting code in techno_cumulative.py
            # / techno_aggregates.py). BF_Shop's total, when needed, is derived
            # by summing the four furnaces' production_table rows (see the
            # preview endpoint above) rather than stored separately.
            is_furnace = unit.startswith("BF-")
            month_keys = [k for k in _month_keys if k != "production"]

            # The PDF grid holds for-the-MONTH values; the only genuine
            # techno cumulative here is coke rate (production's FY cumulative
            # isn't persisted - see above).
            techno_json = {
                "month": {k: row.get(k) for k in month_keys},
                "till_month": {
                    "coke_rate": row.get("coke_rate_ytd"),
                },
            }

            # Merge-save: non-null values win, params from other sources
            # (Excel techno upload, manual entry) are preserved.
            db.merge_upsert_techno_data(
                plant="BSL",
                report_month=month,
                unit=unit,
                new_techno_json=techno_json,
                source_file="bsl_bf_pdf",
            )

            # Furnace-wise month production goes to production_table ('000 t,
            # item = unit name) instead of techno_data — the cumulative rules
            # use it as the weight source for furnace-level parameters, same
            # as RSP/DSP/BSP.
            prod = row.get("production")
            if is_furnace and isinstance(prod, (int, float)) and prod > 0:
                conn = sqlite3.connect(db.DB_PATH)
                conn.execute(
                    """INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
                       VALUES (?, 'BSL', ?, ?)
                       ON CONFLICT(report_month, plant_name, item_name)
                       DO UPDATE SET month_actual = excluded.month_actual""",
                    (month, unit, round(prod / 1000.0, 3)),
                )
                conn.commit()
                conn.close()

        return {
            "status": "success",
            "message": f"Saved {len(data)} records for {month}",
            "records_saved": len(data)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save data: {str(e)}")


@app.post("/api/techno-entries")
async def save_techno_entries(payload: dict):
    """Insert previously previewed techno rows into the DB (user-confirmed)."""
    month = payload.get("month")
    rows = payload.get("rows", [])
    plant = payload.get("plant", "")
    file_name = payload.get("file_name", "")

    if not month or not rows:
        raise HTTPException(status_code=400, detail="month and rows are required")

    # Filter out rows with no data
    valid_rows = [r for r in rows if r.get("actual") is not None or r.get("cum_actual") is not None]
    saved = len(valid_rows)

    if saved > 0 and plant:
        # Save all rows to techno_data table in one call
        db.save_techno_data_from_extraction(
            plant=plant,
            report_month=month,
            extracted_rows=valid_rows,
            unit="BF_Shop",
            source_file=file_name
        )
        db.log_extraction(plant, month, file_name, "techno", "techno_params", saved)

    return {"status": "success", "saved": saved,
            "message": f"Inserted {saved} techno parameter values for {plant} {month}."}


# ---------------------------------------------------------------------------
# Production data entry
# ---------------------------------------------------------------------------

@app.get("/api/extraction-log")
async def get_extraction_log(limit: int = 60, plant: str = None, source_type: str = None):
    return {"logs": db.get_extraction_logs(limit=limit, plant=plant, source_type=source_type)}


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
        "SELECT DISTINCT item_name FROM production_table WHERE plant_name = ?",
        (plant,)
    )
    # Process-order the dropdown; sort on the normalized form but keep the
    # raw DB name, since aliases must map to what's actually stored.
    items = sorted(
        (row[0] for row in cursor.fetchall()),
        key=lambda n: production_item_sort_key(normalize_item_name(n)),
    )

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
    # ASP/SSP/VISL plan tables call this "Saleable Despatch"; VISL's actual
    # table calls the same quantity "Saleable Steel Despatch" — unify so a
    # plant's plan and actual land on one query row instead of two.
    if name == 'Saleable Despatch':
        name = 'Saleable Steel Despatch'
    # DSP: fold legacy item names into the ones the extractors now emit
    # (pdf_extractor_dsp.py LABEL_MAP maps "brc bloom"/"brc round" -> these)
    if name == 'BRC Bloom':
        name = 'BRC'
    elif name == 'BRC Round':
        name = 'Round Production'
    return name.strip()

# Custom sort order for production items — process sequence:
# coke oven pushing → sinter → hot metal → crude steel → pig iron → mills
# → secondary mills → finished steel → saleable semis → saleable steel.
# Names must be the post-normalize_item_name() form (BF#x, Billet, etc.).
PRODUCTION_ITEM_ORDER = [
    # 1. Coke oven pushing
    'Oven Pushing (nos/day)',
    'COB#1-5',
    'COB#1-8',
    'COB#6',
    'COB#9-10',
    'COB#10',
    'COB#11',
    # 2. Sinter
    'SP-1',
    'SP-2',
    'SP-3',
    'SP M/c-1',
    'SP M/c-2',
    'Total Sinter',
    # 3. Hot metal
    'BF#1',
    'BF#2',
    'BF#3',
    'BF#4',
    'BF#5',
    'BF#6',
    'BF#7',
    'BF#8',
    'BF#1-7',
    'Hot Metal',
    'Hot Metal to ASP',
    'Hot Metal to PCM',
    # 4. Crude steel (SMS / casters / ingot)
    'SMS-1 CCM-1',
    'SMS-2',
    'SMS-2 CCM-1&2',
    'SMS-2 CCM-3',
    'SMS-2 CCM-4',
    'SMS-2 BLOOM',
    'SMS-2 SLAB',
    'SMS-3',
    'SMS-3 Billet105',
    'SMS-3 Billet150',
    'SMS-3 BLOOM(CV1&2)',
    'SMS CCM-1&2',
    'SMS CCM-3',
    'SMS Total Caster',
    'Billet Caster',
    'Bloom Caster',
    'Round Production',
    'BRC',
    '200 Blooms',
    'Concast',
    'Total Caster',
    'Bottom Pouring Ingot',
    'Ingot Steel',
    'Total Crude Steel',
    # 5. Pig iron
    'Pig Iron',
    # 6. Mills (primary / rolling)
    'MM',
    'MSM',
    'SM',
    'USMILL',
    'BARMILL',
    'BARS',
    'BARS&RODMILL',
    'WRMILL',
    'WIRERODS',
    'PLATEMILL',
    'PLATES',
    'NPM Plate',
    'OPM Plate',
    'HRM',
    'HSM Total HR Coil',
    'HSM HR Coil (Sale)',
    'HSM HR Plate',
    'HSM-2 Total HR Coil',
    'HSM-2 HR Coil (Sale)',
    'HSM-2 HR Plate',
    'HR Sheet',
    'URM_RAIL',
    'URMPRIME',
    'RSM_RAIL',
    'RSMPRIME',
    # 7. Secondary mills
    'CRC&S(1&2)',
    'CRC(3)',
    'CRSALE',
    'CR Saleable',
    'CRNO Coils',
    'GP/GC',
    'GPC3',
    'ERW Pipes',
    'SW Pipes',
    'WAP',
    'wheel plant',
    'Axle plant',
    'FORGINGS',
    # 8. Finished steel
    'Finished Steel',
    # 9. Semis saleable
    'Billet for Sale',
    'Blooms for Sale',
    'Saleable 150 Billets',
    'SEMIS BilletS',
    'SEMIS BLOOM',
    'SEMIS SLABS',
    'Saleable Semis',
    # 10. Saleable steel
    'Saleable Steel',
    'Saleable Steel Despatch',
]

def production_item_sort_key(item):
    """Process-order sort key; items not in the list go last, alphabetically.
    Expects a normalized item name (see normalize_item_name)."""
    try:
        return (PRODUCTION_ITEM_ORDER.index(item), item)
    except ValueError:
        return (len(PRODUCTION_ITEM_ORDER), item)

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

    # Sort items in process order, with remaining items at the end
    sorted_items = sorted(all_items, key=production_item_sort_key)

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

    # SAIL techno actuals are no longer auto-recalculated/stored here on every
    # production update — calculate_sail_actuals() is used as a read-time
    # fallback wherever SAIL data is displayed instead (see page_techno.py).

    return {"status": "success", "saved": saved, "count": len(saved)}


# ── Legacy CSV backfill: SMS-shop items + Total Crude Steel per plant ──────
# SMS-shop breakdown items have real gaps (mostly pre-2023/2024, before the
# per-shop rows started being tracked); Total Crude Steel is already fully
# populated but is included so it can be reviewed/corrected against paper
# legacy records via the same round-trip.
LEGACY_SMS_CRUDE_ITEMS = {
    "ASP":  ["Total Crude Steel"],
    "BSL":  ["SMS-1 CCM-1", "SMS-2 CCM-1&2", "Total Crude Steel"],
    "BSP":  ["SMS-2", "SMS-3", "Total Crude Steel"],
    "DSP":  ["SMS Total Caster", "Total Crude Steel"],
    "ISP":  ["SMS CCM-1&2", "SMS CCM-3", "Total Crude Steel"],
    "RSP":  ["SMS-1 CCM-1", "SMS-2 CCM-1&2", "SMS-2 CCM-3", "SMS-2 CCM-4", "Total Crude Steel"],
    "SSP":  ["Total Crude Steel"],
    "VISL": ["Total Crude Steel"],
}
_LEGACY_START_MONTH = "2022-04"
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _legacy_month_range():
    conn = sqlite3.connect(db.DB_PATH)
    # GLOB filter guards against non-YYYY-MM junk rows in report_month (seen in
    # the wild: a literal CSV header row) which would otherwise win MAX() by
    # sorting after all real dates.
    row = conn.execute(
        "SELECT MAX(report_month) FROM production_table WHERE report_month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'"
    ).fetchone()
    conn.close()
    end_month = row[0] if row and row[0] else _LEGACY_START_MONTH

    months = []
    y, m = (int(x) for x in _LEGACY_START_MONTH.split("-"))
    ey, em = (int(x) for x in end_month.split("-"))
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            m = 1
            y += 1
    return months


@app.get("/api/legacy-sms-crude/template")
async def legacy_sms_crude_template():
    """CSV template for backfilling SMS-shop items and reviewing Total Crude
    Steel from 2022-04 onward. `value` is pre-filled from production_table
    where a row already exists (for review/correction) and left blank where
    it's a genuine gap."""
    months = _legacy_month_range()

    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    existing = {}
    for plant, items in LEGACY_SMS_CRUDE_ITEMS.items():
        placeholders = ",".join("?" * len(items))
        rows = cur.execute(
            f"""SELECT report_month, item_name, month_actual FROM production_table
                WHERE plant_name = ? AND item_name IN ({placeholders}) AND report_month >= ?""",
            (plant, *items, _LEGACY_START_MONTH),
        ).fetchall()
        for report_month, item_name, value in rows:
            existing[(plant, item_name, report_month)] = value
    conn.close()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["report_month", "plant_name", "item_name", "value"])
    for plant, items in LEGACY_SMS_CRUDE_ITEMS.items():
        for item in items:
            for month in months:
                val = existing.get((plant, item, month))
                writer.writerow([month, plant, item, "" if val is None else val])

    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=legacy_sms_crude_steel_template.csv"},
    )


@app.post("/api/legacy-sms-crude/preview")
async def legacy_sms_crude_preview(file: UploadFile = File(...)):
    """Parse an uploaded legacy CSV, validate each row against the
    plant/item whitelist, and diff it against the current production_table
    value. Writes nothing — this is preview only."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV must be UTF-8 encoded.")

    reader = csv.DictReader(io.StringIO(text))
    required_cols = {"report_month", "plant_name", "item_name", "value"}
    if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
        raise HTTPException(400, f"CSV must have columns: {', '.join(sorted(required_cols))}")

    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()

    rows = []
    counts = {"new": 0, "changed": 0, "unchanged": 0, "blank": 0, "invalid": 0}
    for i, raw_row in enumerate(reader, start=2):  # header is row 1
        report_month = (raw_row.get("report_month") or "").strip()
        plant_name = (raw_row.get("plant_name") or "").strip().upper()
        item_name = (raw_row.get("item_name") or "").strip()
        value_str = (raw_row.get("value") or "").strip()

        reason = None
        if not _MONTH_RE.match(report_month):
            reason = f"bad report_month '{report_month}'"
        elif plant_name not in LEGACY_SMS_CRUDE_ITEMS:
            reason = f"unknown plant '{plant_name}'"
        elif item_name not in LEGACY_SMS_CRUDE_ITEMS[plant_name]:
            reason = f"item '{item_name}' not valid for {plant_name}"

        value = None
        if reason is None and value_str != "":
            try:
                value = float(value_str)
            except ValueError:
                reason = f"value '{value_str}' is not a number"

        if reason:
            rows.append({
                "row": i, "report_month": report_month, "plant_name": plant_name,
                "item_name": item_name, "csv_value": value_str, "db_value": None,
                "status": "invalid", "reason": reason,
            })
            counts["invalid"] += 1
            continue

        db_row = cur.execute(
            "SELECT month_actual FROM production_table WHERE report_month=? AND plant_name=? AND item_name=?",
            (report_month, plant_name, item_name),
        ).fetchone()
        db_value = db_row[0] if db_row else None

        if value is None:
            status = "blank"
        elif db_value is None:
            status = "new"
        elif abs(db_value - value) > 1e-6:
            status = "changed"
        else:
            status = "unchanged"
        counts[status] += 1

        rows.append({
            "row": i, "report_month": report_month, "plant_name": plant_name,
            "item_name": item_name, "csv_value": value, "db_value": db_value,
            "status": status, "reason": None,
        })

    conn.close()
    return {"rows": rows, "counts": counts}


@app.post("/api/legacy-sms-crude/confirm")
async def legacy_sms_crude_confirm(payload: dict):
    """Write rows from a previewed legacy CSV into production_table.
    Only rows the client marked apply=true AND that were classified 'new'
    or 'changed' at preview time are written; everything is re-validated
    against the whitelist server-side rather than trusting the client."""
    rows = payload.get("rows", [])
    saved, skipped = 0, 0

    for r in rows:
        if not r.get("apply") or r.get("status") not in ("new", "changed"):
            skipped += 1
            continue

        report_month = str(r.get("report_month", "")).strip()
        plant_name = str(r.get("plant_name", "")).strip().upper()
        item_name = str(r.get("item_name", "")).strip()

        if not _MONTH_RE.match(report_month):
            skipped += 1
            continue
        if plant_name not in LEGACY_SMS_CRUDE_ITEMS or item_name not in LEGACY_SMS_CRUDE_ITEMS[plant_name]:
            skipped += 1
            continue
        try:
            value = float(r.get("csv_value"))
        except (TypeError, ValueError):
            skipped += 1
            continue

        db.save_production_actual(report_month, plant_name, item_name, value)
        saved += 1

    # SAIL techno actuals are a read-time fallback now (see page_techno.py's
    # calculate_sail_actuals), not auto-recalculated/stored on every import.

    return {"status": "success", "saved": saved, "skipped": skipped}


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


PRODUCTION_FY_PLANT_ORDER = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL', 'SAIL']


@app.get("/api/techno-major-monthly")
async def techno_major_monthly(month: str = Query(...)):
    """Plant-wise MAJOR techno parameters for one month — the same values and
    definitions as page 27 of the PDF report, reshaped to
    (parameter → plant rows with for-the-month / till-the-month values)."""
    data = generate_major_techno_from_db(month)
    month_labels = data.get("month_labels") or []
    sections = []
    for sec in data.get("sections", []):
        rows = []
        for r in sec.get("rows", []):
            months = r.get("months") or []
            rows.append({
                "plant":      r.get("label"),
                "unit":       r.get("unit"),
                "target":     r.get("target"),
                "month":      months[-1] if months else "",
                "till_month": r.get("cum"),
                "cply":       r.get("cply"),
                "cum_cply":   r.get("cum_cply"),
            })
        sections.append({"parameter": sec.get("label"), "rows": rows})
    return {
        "month": month,
        "month_label":    month_labels[-1] if month_labels else month,
        "cum_label":      data.get("cum_label", ""),
        "cply_label":     data.get("cply_label", ""),
        "cum_cply_label": data.get("cum_cply_label", ""),
        "target_label":   data.get("target_label", ""),
        "sections": sections,
    }


@app.get("/api/techno-major-verification")
async def techno_major_verification(month: str = Query(...)):
    """MAJOR page (27) parameters, Reported (stored till-month) vs Calculated
    (recomputed from this FY's monthly actuals via the same production-
    weighted rules the "Calculate Cumulative" feature uses), for every plant
    plus the SAIL rollup — flags a deviation whenever the two differ after
    rounding to that parameter's normal display precision."""
    return generate_major_techno_verification(month)


@app.get("/api/production-fys")
async def list_production_fys():
    """List financial years that have actual or plan production data.
    Response: { fys: [{"fy_start": 2026, "label": "2026-27"}, ...] } (newest first)"""
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT report_month FROM production_table
        WHERE report_month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
        UNION
        SELECT DISTINCT report_month FROM production_plan_table
        WHERE report_month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
    """)
    fy_starts = set()
    for (m,) in cur.fetchall():
        year, month = int(m[:4]), int(m[5:7])
        fy_starts.add(year if month >= 4 else year - 1)
    conn.close()
    return {
        "fys": [
            {"fy_start": y, "label": f"{y}-{str(y + 1)[2:]}"}
            for y in sorted(fy_starts, reverse=True)
        ]
    }


@app.get("/api/production-fy")
async def get_production_fy(fy_start: int = Query(...)):
    """Month-wise production for a financial year: all plants, all items,
    actual and plan side by side."""
    months = [f"{fy_start}-{m:02d}" for m in range(4, 13)] + \
             [f"{fy_start + 1}-{m:02d}" for m in range(1, 4)]
    phs = ",".join("?" for _ in months)

    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    # data[plant][item] = {"actual": {month: val}, "plan": {month: val}}
    data = {}
    for table, key in (("production_table", "actual"), ("production_plan_table", "plan")):
        cur.execute(
            f"SELECT plant_name, item_name, report_month, month_actual FROM {table} "
            f"WHERE report_month IN ({phs}) AND plant_name != 'plant_name'",
            months,
        )
        for plant, item, month, value in cur.fetchall():
            item = normalize_item_name(item)
            entry = data.setdefault(plant, {}).setdefault(item, {"actual": {}, "plan": {}})
            entry[key][month] = value
    conn.close()

    def plant_key(p):
        try:
            return (PRODUCTION_FY_PLANT_ORDER.index(p), p)
        except ValueError:
            return (len(PRODUCTION_FY_PLANT_ORDER), p)

    plants = []
    for plant in sorted(data.keys(), key=plant_key):
        items = []
        for item in sorted(data[plant].keys(), key=production_item_sort_key):
            entry = data[plant][item]
            items.append({
                "item_name": item,
                "actual": {m: entry["actual"].get(m) for m in months},
                "plan": {m: entry["plan"].get(m) for m in months},
            })
        plants.append({"plant": plant, "items": items})

    return {
        "fy_start": fy_start,
        "fy_label": f"{fy_start}-{str(fy_start + 1)[2:]}",
        "months": months,
        "plants": plants,
    }


@app.get("/api/production-query-meta")
async def production_query_meta():
    """Plants and available months for the ad-hoc production query page
    (union of production_table and production_plan_table).
    Response: { plants: [...], months: ["2026-06", ...] } (months newest first)"""
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT plant_name, report_month FROM production_table
        WHERE report_month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
          AND plant_name != 'plant_name'
        UNION
        SELECT plant_name, report_month FROM production_plan_table
        WHERE report_month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
          AND plant_name != 'plant_name'
    """)
    plants, months = set(), set()
    for plant, month in cur.fetchall():
        plants.add(plant)
        months.add(month)
    conn.close()

    def plant_key(p):
        try:
            return (PRODUCTION_FY_PLANT_ORDER.index(p), p)
        except ValueError:
            return (len(PRODUCTION_FY_PLANT_ORDER), p)

    return {
        "plants": sorted(plants, key=plant_key),
        "months": sorted(months, reverse=True),
    }


@app.get("/api/production-query-items")
async def production_query_items(plants: str = Query(...)):
    """Distinct (normalized) item names per plant, e.g. ?plants=BSP,RSP.
    Union of actual and plan tables so plan-only units are selectable too.
    Response: { items: {plant: [item, ...]} } in process order."""
    plant_list = [p.strip() for p in plants.split(",") if p.strip()]
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    items = {}
    for plant in plant_list:
        names = set()
        for table in ("production_table", "production_plan_table"):
            cur.execute(
                f"SELECT DISTINCT item_name FROM {table} WHERE plant_name = ?",
                (plant,),
            )
            names.update(normalize_item_name(r[0]) for r in cur.fetchall())
        items[plant] = sorted(names, key=production_item_sort_key)
    conn.close()
    return {"items": items}


@app.post("/api/production-query")
async def production_query(payload: dict):
    """Month-wise plan (APP) and actual for user-selected plant/unit pairs.
    Payload: {"start": "2026-04", "end": "2026-06",
              "units": [{"plant": "BSP", "item": "BF#8"}, ...]}
    Response: {months, series: [{plant, item, plan: {m: v}, actual: {m: v}}]}
    Values are rounded to 3 decimals."""
    start = str(payload.get("start", ""))
    end = str(payload.get("end", ""))
    if not re.fullmatch(r"\d{4}-\d{2}", start) or not re.fullmatch(r"\d{4}-\d{2}", end):
        raise HTTPException(status_code=400, detail="start/end must be YYYY-MM")
    if start > end:
        start, end = end, start

    months = []
    y, m = int(start[:4]), int(start[5:7])
    # Generous backstop only (production_table alone spans 2000-present, and
    # plan data reaches a year ahead) — not a realistic range limit. At 120
    # this silently truncated any query over ~10 years, dropping the tail of
    # the range (e.g. the current FY's plan months) with no error shown.
    while f"{y}-{m:02d}" <= end and len(months) < 600:
        months.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    wanted = []
    seen = set()
    for u in payload.get("units", []):
        plant = str(u.get("plant", "")).strip()
        item = normalize_item_name(str(u.get("item", "")).strip())
        if plant and item and (plant, item) not in seen:
            seen.add((plant, item))
            wanted.append((plant, item))

    series = [{"plant": p, "item": i, "plan": {}, "actual": {}} for p, i in wanted]
    index = {key: s for key, s in zip(wanted, series)}
    plant_set = sorted({p for p, _ in wanted})

    # Units whose ABP plan has no direct row and is instead split into
    # sub-items (normalized names). E.g. BSP SMS-3's plan is stored per
    # caster grade — sum them wherever the unit has no direct plan row.
    PLAN_SOURCE_ALIASES = {
        ("BSP", "SMS-3"): {"SMS-3 Billet105", "SMS-3 Billet150", "SMS-3 BLOOM(CV1&2)"},
    }

    # Stored 'SAIL' rows are 5-integrated-plant totals written by the report
    # pipeline; months it hasn't written yet (e.g. the latest month) are
    # computed on the fly by summing the member plants. Stored rows win.
    SAIL_MEMBER_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
    sail_items = {i for p, i in wanted if p == "SAIL"}

    if wanted and months:
        query_plants = sorted(set(plant_set) | (set(SAIL_MEMBER_PLANTS) if sail_items else set()))
        phs_m = ",".join("?" for _ in months)
        phs_p = ",".join("?" for _ in query_plants)
        alias_plan = {k: {} for k in index if k in PLAN_SOURCE_ALIASES}
        member_sums = {"actual": {}, "plan": {}}  # {(item, month): sum over 5 plants}
        conn = sqlite3.connect(db.DB_PATH)
        cur = conn.cursor()
        for table, key in (("production_table", "actual"), ("production_plan_table", "plan")):
            cur.execute(
                f"SELECT plant_name, item_name, report_month, month_actual FROM {table} "
                f"WHERE report_month IN ({phs_m}) AND plant_name IN ({phs_p})",
                months + query_plants,
            )
            for plant, item, month, value in cur.fetchall():
                norm = normalize_item_name(item)
                s = index.get((plant, norm))
                if s is not None and value is not None:
                    s[key][month] = round(float(value), 3)
                if key == "plan" and value is not None:
                    for (t_plant, t_item), srcs in PLAN_SOURCE_ALIASES.items():
                        if plant == t_plant and norm in srcs and (t_plant, t_item) in alias_plan:
                            ap = alias_plan[(t_plant, t_item)]
                            ap[month] = ap.get(month, 0.0) + float(value)
                if value is not None and norm in sail_items and plant in SAIL_MEMBER_PLANTS:
                    ms = member_sums[key]
                    ms[(norm, month)] = ms.get((norm, month), 0.0) + float(value)
        conn.close()
        # Fill summed sub-item plans only where no direct plan row exists
        for target, ap in alias_plan.items():
            s = index[target]
            for month, v in ap.items():
                if month not in s["plan"]:
                    s["plan"][month] = round(v, 3)
        # Fill SAIL gaps from member-plant sums (stored SAIL rows take precedence)
        for item in sail_items:
            s = index[("SAIL", item)]
            for key in ("actual", "plan"):
                for month in months:
                    if month not in s[key] and (item, month) in member_sums[key]:
                        s[key][month] = round(member_sums[key][(item, month)], 3)

    return {"months": months, "series": series}


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
        plan_data = db.get_sail_techno_plan(fy)
        return {"fy": fy, "data": plan_data}
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

        db.save_sail_techno_plan(fy, data)

        return {"status": "success", "fy": fy, "saved": len(data)}
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
    try:
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
    except sqlite3.OperationalError:
        # Legacy schema not available - return empty results
        rows = []
        conn = sqlite3.connect(db.DB_PATH)
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
            try:
                conn = sqlite3.connect(db.DB_PATH)
                conn.execute("DELETE FROM techno_actuals WHERE param_id=? AND report_month=?",
                             (param_id, month))
                conn.commit()
                conn.close()
                cleared += 1
            except sqlite3.OperationalError:
                # techno_actuals table doesn't exist - skip
                pass
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

    result = {"month": month, "sail_params": {}}
    db_values = {}
    sms_values = {}

    try:
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()

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

        for shop, param_name, actual, till_month in cursor.fetchall():
            if param_name not in sms_values:
                sms_values[param_name] = {}
            sms_values[param_name][shop] = (actual, till_month)
        conn.close()
    except sqlite3.OperationalError:
        # Legacy schema not available - continue with empty values
        pass

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


# Acronym casing for parameter display names derived from techno_json keys.
_PARAM_ACRONYMS = {
    "bf", "cdi", "o2", "co2", "ld", "hm", "sms", "lpg", "cog", "bof",
    "cri", "csr", "cv", "vm", "tmi", "ds", "dsp", "hr", "cbm", "feo",
}

# Different plant extractors settled on different snake_case spellings for
# the same parameter over time (e.g. BSP/RSP write "cdi", an older path wrote
# "cdi_rate") — /api/techno-data's normalized-key lookup below tries every
# alias in order so a plant/month using the "other" spelling isn't silently
# reported as missing.
_PARAM_KEY_ALIASES = {
    "cdi": ["cdi", "cdi_rate", "CDI Rate"],
    "coke_rate": ["coke_rate", "Coke Rate"],
    "fuel_rate": ["fuel_rate", "Fuel Rate"],
    "bf_productivity": ["bf_productivity", "BF Productivity"],
    "specific_energy_consumption": ["specific_energy_consumption", "Specific Energy Consumption"],
    # Same ISP/RSP/BSL key-spelling drift already worked around in
    # page_techno.py's _KEY_ALIASES (generate_major_techno_from_db) — mirrored
    # here so the techno-dashboard's parameter picker doesn't show gaps for
    # months that happen to use the "other" historical spelling.
    "silicon_in_hm": ["silicon_in_hm", "si_in_hm", "si%_in_hm"],
    "sulphur_in_hm": ["sulphur_in_hm", "s_in_hm", "s%_in_hm"],
    "sinter_in_burden": ["sinter_in_burden", "sinter% in burden"],
    "pellet_in_burden": ["pellet_in_burden", "pellet% in burden"],
    "coke_oven_gas_yield": ["coke_oven_gas_yield", "cog_yield"],
    "dry_coal_charge_oven": ["dry_coal_charge_oven", "dry_coal_charge", "dry_coal_charge_per_oven"],
    "ash_in_coke": ["ash_in_coke", "average_ash_in_coke", "ash_in_bf_coke"],
}


def _extract_param_value(month_data: dict, param_key: str):
    """Look up param_key (plus any known aliases) in a techno_json
    month/till_month dict. Also unwraps the legacy SAIL {"value": x, "unit":
    y} shape (from calculate_and_store_sail_actuals) down to a plain number,
    since most callers store a bare number instead."""
    for key in _PARAM_KEY_ALIASES.get(param_key, [param_key]):
        if key in month_data:
            v = month_data[key]
            if isinstance(v, dict):
                v = v.get("value")
            return v
    return None


@app.get("/api/techno-parameters")
async def get_techno_parameters():
    """Get list of all available techno parameters.

    Parameter names live as keys of techno_data.techno_json['month'];
    display names must round-trip through /api/techno-data's
    lower().replace(' ', '_') normalization back to the same key.
    """
    import json
    try:
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT techno_json FROM techno_data")
        keys = set()
        for (techno_json,) in cursor.fetchall():
            try:
                keys.update(json.loads(techno_json).get('month', {}).keys())
            except (json.JSONDecodeError, TypeError):
                pass
        conn.close()

        parameters = set()
        for key in keys:
            words = [
                w.upper() if w in _PARAM_ACRONYMS else w.title()
                for w in key.split('_')
            ]
            display = ' '.join(w for w in words if w)
            # Skip keys (e.g. containing spaces) that would not resolve
            # back to themselves when the frontend requests them.
            if display.lower().replace(' ', '_') == key:
                parameters.add(display)
        return {"parameters": sorted(parameters)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-data")
async def get_techno_data(plants: str = Query(""), parameters: str = Query("")):
    """Get techno data for selected plants and parameters
    Query params:
      - plants: comma-separated plant codes (e.g., "BSP,RSP,DSP")
      - parameters: comma-separated parameter names
    """
    import json
    try:
        if not plants or not parameters:
            raise HTTPException(status_code=400, detail="plants and parameters parameters required")

        plant_list = [p.strip() for p in plants.split(',') if p.strip()]
        param_list = [p.strip() for p in parameters.split(',') if p.strip()]

        if not plant_list or not param_list:
            raise HTTPException(status_code=400, detail="At least one plant and parameter required")

        # Normalize parameter names to match database keys (lowercase, with underscores)
        param_keys = [p.lower().replace(' ', '_') for p in param_list]

        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get techno data for selected plants from new techno_data table
        placeholders = ','.join('?' * len(plant_list))
        cursor.execute(f"""
            SELECT plant, report_month, techno_json
            FROM techno_data
            WHERE plant IN ({placeholders})
            ORDER BY plant, report_month
        """, plant_list)

        rows = cursor.fetchall()
        conn.close()

        # Format data by plant and parameter
        data = {}
        for row in rows:
            plant = row['plant']
            month = row['report_month']
            try:
                techno_json = json.loads(row['techno_json'])
                month_data = techno_json.get('month', {})

                if plant not in data:
                    data[plant] = {}

                # Extract requested parameters
                for param_name, param_key in zip(param_list, param_keys):
                    value = _extract_param_value(month_data, param_key)
                    if value is not None:
                        if param_name not in data[plant]:
                            data[plant][param_name] = {}
                        data[plant][param_name][month] = value
            except (json.JSONDecodeError, TypeError):
                pass

        # For "All" plants or if SAIL not included, fetch SAIL consolidated data
        if 'all' in [p.lower() for p in plant_list] or 'SAIL' in plant_list:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_month, techno_json
                FROM techno_data
                WHERE plant = 'SAIL'
                ORDER BY report_month
            """)
            sail_rows = cursor.fetchall()
            conn.close()

            if 'SAIL' not in data:
                data['SAIL'] = {}

            for row in sail_rows:
                month = row['report_month']
                try:
                    techno_json = json.loads(row['techno_json'])
                    month_data = techno_json.get('month', {})

                    # Extract requested parameters
                    for param_name, param_key in zip(param_list, param_keys):
                        value = _extract_param_value(month_data, param_key)
                        if value is not None:
                            if param_name not in data['SAIL']:
                                data['SAIL'][param_name] = {}
                            data['SAIL'][param_name][month] = value
                except (json.JSONDecodeError, TypeError):
                    pass

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
async def get_techno_plant_plan(plant: str = Query(...), fy: str = Query(...)):
    """
    Get plant-level techno plan data (unit='Shop') for a FY.
    Response: { plant, fy, data: {}, is_user_supplied: bool, calculated: {} }
    """
    try:
        result = db.get_techno_plant_plan(plant, fy)
        return {"plant": plant, "fy": fy, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/techno-plant-plan")
async def save_techno_plant_plan(payload: dict):
    """
    Save plant-level techno plan data for a FY.
    Payload: { plant, fy, data: {param: {value, unit}, ...}, is_user_supplied?: bool, calculated?: {}, calculation_method?: {} }
    """
    try:
        plant = payload.get("plant")
        fy = payload.get("fy")
        data = payload.get("data", {})
        is_user_supplied = payload.get("is_user_supplied", False)
        calculated = payload.get("calculated")
        calculation_method = payload.get("calculation_method")

        if not all([plant, fy]):
            raise ValueError("plant and fy required")

        db.save_techno_plant_plan(plant, fy, data, is_user_supplied, calculated, calculation_method)
        return {"status": "success", "plant": plant, "fy": fy}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sail-techno-plan")
async def get_sail_techno_plan(fy: str = Query(...)):
    """
    Get SAIL consolidated techno plan data for a FY.
    Response: { fy, data: {}, is_user_supplied: bool, calculated: {} (if differs from data) }
    """
    try:
        result = db.get_sail_techno_plan(fy)
        return {"fy": fy, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sail-techno-plan")
async def save_sail_techno_plan(payload: dict):
    """
    Save SAIL consolidated techno plan data for a FY.
    Payload: { fy, data: {param: {value, unit}, ...}, is_user_supplied?: bool, calculated?: {}, calculation_method?: {} }
    """
    try:
        fy = payload.get("fy")
        data = payload.get("data", {})
        is_user_supplied = payload.get("is_user_supplied", False)
        calculated = payload.get("calculated")
        calculation_method = payload.get("calculation_method")

        if not fy:
            raise ValueError("fy required")

        db.save_sail_techno_plan(fy, data, is_user_supplied, calculated, calculation_method)
        return {"status": "success", "fy": fy, "is_user_supplied": is_user_supplied}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/techno-calculate-sail-actuals")
async def calculate_sail_actuals(payload: dict):
    """
    Calculate and store SAIL techno actuals from plant-level data.
    Called after techno extraction or when plant data changes.

    Payload: { report_month: str }
    Response: { success: bool, message: str, sail_data: {...}, calc_details: {...} }
    """
    try:
        report_month = payload.get("report_month")
        if not report_month:
            raise ValueError("report_month required")

        from page_techno import calculate_and_store_sail_actuals
        result = calculate_and_store_sail_actuals(report_month)

        return result
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}", "sail_data": {}, "calc_details": {}}


@app.get("/api/techno-plan-fys")
async def list_techno_plan_fys(plant: str = Query(None)):
    """
    List available FYs in techno_plan table, optionally filtered by plant.
    Response: { fys: ["2026-27", "2027-28", ...] }
    """
    try:
        fys = db.list_techno_plan_fys(plant)
        return {"fys": fys}
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
        {"name": "Coal to Hot Metal", "unit": ""},
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
    Response: { fy, targets: {param: value} }
    """
    try:
        targets = db.get_sail_techno_plan(fy)
        return {"fy": fy, "targets": targets}
    except Exception as e:
        return {"fy": fy, "targets": {}, "error": str(e)}


@app.post("/api/techno-sail-targets")
async def save_techno_sail_targets(payload: dict):
    """
    Save SAIL techno targets for a FY.
    Payload: {
      fy: str,
      targets: {param: value},
      is_user_supplied: bool (optional, default false),
      created_by: str (optional, for audit trail)
    }
    """
    try:
        fy = payload.get("fy", "")
        targets = payload.get("targets", {})
        is_user_supplied = payload.get("is_user_supplied", False)
        created_by = payload.get("created_by", "")

        if not fy:
            raise ValueError("fy is required")

        db.save_sail_techno_plan(fy, targets, is_user_supplied=is_user_supplied, created_by=created_by)

        if is_user_supplied and created_by:
            print(f"[AUDIT] User '{created_by}' supplied SAIL targets for FY {fy}")

        return {
            "status": "success",
            "fy": fy,
            "is_user_supplied": is_user_supplied,
            "created_by": created_by
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/techno-recalculate-sail")
async def recalculate_sail_targets(payload: dict):
    """
    Recalculate SAIL targets from plant-level targets.
    Payload: { fy: str } or { report_month: str }
    Accepts both FY and report_month for backward compatibility.
    """
    try:
        fy = payload.get("fy", "")
        report_month = payload.get("report_month", "")

        # Convert report_month to FY if fy not provided
        if not fy and report_month:
            from db import get_fy_for_month
            fy = get_fy_for_month(report_month)

        if not fy:
            raise ValueError("fy or report_month is required")

        from page_techno import compute_sail_targets
        computed = compute_sail_targets(fy)

        return {"status": "success", "fy": fy, "computed": computed}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-plant-targets")
async def get_techno_plant_targets(fy: str = Query("2026-27"), plant: str = Query(None)):
    """
    Get plant-level techno targets for a given FY.
    If plant specified, return targets for that plant only.
    Otherwise return for all 5 plants.
    Response: { fy, plants: {plant: {param: value}} }
    """
    try:
        plants_to_fetch = [plant] if plant else ["BSP", "DSP", "RSP", "BSL", "ISP"]
        result = {}

        for p in plants_to_fetch:
            plan_result = db.get_techno_plant_plan(p, fy)
            plan_data = plan_result.get('data', {})
            result[p] = {}
            for param_name, param_obj in plan_data.items():
                # Extract value from {value, unit} structure
                if isinstance(param_obj, dict):
                    value = param_obj.get('value')
                else:
                    value = param_obj
                if value is not None:
                    result[p][param_name] = value

        return {"fy": fy, "plants": result}
    except Exception as e:
        return {"fy": fy, "plants": {}, "error": str(e)}


@app.post("/api/techno-plant-targets")
async def save_techno_plant_targets(payload: dict):
    """
    Save plant-level techno targets for a FY.
    Payload: { fy: str, plants: {plant: {param: {value, unit}}} }
    """
    try:
        fy = payload.get("fy", "")
        plants_data = payload.get("plants", {})

        if not fy:
            raise ValueError("fy is required")

        saved_count = 0
        for plant, params in plants_data.items():
            if params:
                # Ensure params are in {param: {value, unit}} format
                formatted_params = {}
                for param_name, param_value in params.items():
                    if isinstance(param_value, dict) and 'value' in param_value:
                        formatted_params[param_name] = param_value
                    else:
                        # If just a value, try to infer unit or leave as is
                        formatted_params[param_name] = {"value": param_value, "unit": ""}

                db.save_techno_plant_plan(plant, fy, formatted_params, is_user_supplied=True)
                saved_count += 1

        return {"status": "success", "fy": fy, "plants_saved": saved_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-page-targets")
async def get_techno_page_targets(page: int = Query(...), fy: str = Query(...)):
    """Target-entry columns for a pages 28-30 param (plant/unit/param_key,
    discovered from data ever reported at any month) plus each column's
    currently-saved target for this FY, from techno_plan_fy. No SAIL column
    — page 27's own targets page (/data-entry/targets) already covers SAIL."""
    cfg = generate_techno_target_columns(page)
    if not cfg:
        raise HTTPException(status_code=400, detail=f"Page {page} has no target-entry schema.")

    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    cache = {}
    try:
        for sec in cfg["sections"]:
            for col in sec["columns"]:
                key = (col["plant"], col["unit"])
                if key not in cache:
                    cur.execute(
                        "SELECT techno_json FROM techno_plan_fy WHERE plant_name=? AND unit=? AND fy=?",
                        (*key, fy),
                    )
                    row = cur.fetchone()
                    cache[key] = json.loads(row[0]) if row and row[0] else {}
                obj = cache[key].get(col["param_key"])
                col["target"] = obj.get("value") if isinstance(obj, dict) else obj
    finally:
        conn.close()

    return {"fy": fy, **cfg}


@app.post("/api/techno-page-targets")
async def save_techno_page_targets(payload: dict):
    """Save pages 28-30 target-entry values.
    Payload: { fy, entries: [{plant, unit, param_key, unit_str, value}] }
    Merges into any existing techno_plan_fy row for (plant, unit, fy) so
    saving one section's targets never clobbers another section's already-
    saved values under the same (plant, unit)."""
    fy = payload.get("fy", "")
    entries = payload.get("entries", [])
    if not fy:
        raise HTTPException(status_code=400, detail="fy is required")

    grouped = {}
    for e in entries:
        grouped.setdefault((e["plant"], e["unit"]), []).append(e)

    saved = 0
    for (plant, unit), rows in grouped.items():
        existing = db.get_techno_plan(plant, fy, unit)
        merged = dict(existing.get("data", {}))
        for e in rows:
            v = e.get("value")
            if v is None or v == "":
                continue
            try:
                merged[e["param_key"]] = {"value": float(v), "unit": e.get("unit_str", "")}
                saved += 1
            except (TypeError, ValueError):
                continue
        db.save_techno_plan(plant, fy, unit, merged, is_user_supplied=True)

    return {"status": "success", "fy": fy, "saved": saved}


@app.get("/api/techno-sms-targets")
async def get_techno_sms_targets(fy: str = Query("2026-27")):
    """
    Get SMS-wise (shop-wise) techno targets for a given FY.
    Response: { fy, sms_shops: {shop: {param: {value, unit}}} }
    """
    try:
        sms_shops = [
            "BSP SMS-2", "BSP SMS-3",
            "DSP SMS",
            "RSP SMS-1", "RSP SMS-2",
            "BSL SMS-1", "BSL SMS-2",
            "ISP SMS-1",
        ]
        result = {}

        for shop in sms_shops:
            plant = shop.split()[0]
            shop_result = db.get_techno_plan(plant, fy, shop)
            if shop_result and shop_result.get('data'):
                raw_data = shop_result['data']
                shop_params = {}
                for param_name, param_obj in raw_data.items():
                    if isinstance(param_obj, dict):
                        value = param_obj.get('value')
                    else:
                        value = param_obj
                    if value is not None:
                        shop_params[param_name] = value
                result[shop] = shop_params

        return {"fy": fy, "sms_shops": result}
    except Exception as e:
        return {"fy": fy, "sms_shops": {}, "error": str(e)}


@app.post("/api/techno-sms-targets")
async def save_techno_sms_targets(payload: dict):
    """
    Save SMS-wise (shop-wise) techno targets for a FY.
    Payload: { fy: str, sms_shops: {shop: {param: {value, unit}}} }
    """
    try:
        fy = payload.get("fy", "")
        sms_data = payload.get("sms_shops", {})

        if not fy:
            raise ValueError("fy is required")

        saved_count = 0
        for shop, params in sms_data.items():
            if params:
                plant = shop.split()[0]  # Extract plant from "BSP SMS-2"
                unit = shop
                # Ensure params are in {param: {value, unit}} format
                formatted_params = {}
                for param_name, param_value in params.items():
                    if isinstance(param_value, dict) and 'value' in param_value:
                        formatted_params[param_name] = param_value
                    else:
                        formatted_params[param_name] = {"value": param_value, "unit": ""}

                db.save_techno_plan(plant, fy, unit, formatted_params, is_user_supplied=True)
                saved_count += 1

        return {"status": "success", "fy": fy, "shops_saved": saved_count}
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
        # Query SMS items grouped by plant and SMS identifier
        # Items are named: "SMS-2 BLOOM", "SMS-2 SLAB", "SMS-3 BILLET105", etc.
        cur.execute(f"""
            SELECT plant_name, item_name, SUM(month_actual)
            FROM production_plan_table
            WHERE report_month IN ({ph})
              AND item_name LIKE '%SMS%'
            GROUP BY plant_name, item_name
        """, months)

        # Build SMS-wise production totals: {(plant, sms_id): total_cs_production}
        sms_production = {}
        for plant_name, item_name, cs_prod in cur.fetchall():
            # Extract SMS identifier from item_name (e.g., "SMS-2 BLOOM" → "SMS-2")
            sms_id = item_name.split()[0]  # Get first part
            key = (plant_name, sms_id)
            sms_production[key] = sms_production.get(key, 0) + (cs_prod or 0)

        # Map shop names to CS production weights
        shop_cs_weights = {}
        for shop, plant in shop_to_plant.items():
            sms_id = shop.split()[-1]  # Get SMS identifier from "BSP SMS-2" → "SMS-2"
            weight = sms_production.get((plant, sms_id))
            if weight is None:
                # ISP's production items are named "SMS CCM-1&2"/"SMS CCM-3" —
                # the shop number isn't in the item name's first token, so the
                # exact (plant, sms_id) lookup above misses. When a plant has
                # only one SMS shop, fall back to its total SMS production.
                plant_shops = [s for s, p in shop_to_plant.items() if p == plant]
                if len(plant_shops) == 1:
                    weight = sum(v for (p, _sid), v in sms_production.items() if p == plant)
            shop_cs_weights[shop] = weight or 0

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
            plan_result = db.get_techno_plant_plan(plant, fy)
            plant_data = plan_result.get('data', {}) if plan_result else {}
            if plant_data:
                for param, param_obj in plant_data.items():
                    value = param_obj.get('value') if isinstance(param_obj, dict) else param_obj
                    if value is not None:
                        if param not in bf_targets:
                            bf_targets[param] = []
                        weight = hm_weights.get(plant, 0)
                        if weight:
                            bf_targets[param].append((value, weight))

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
                # Get the shop-level (SMS-wise) data actually entered via
                # /api/techno-sms-targets — stored under unit=<shop name>,
                # not the plant-wide unit='Shop' record.
                plan_result = db.get_techno_plan(plant, fy, shop)
                shop_data = plan_result.get('data', {}) if plan_result else {}
                weight = shop_cs_weights.get(shop, 0)

                if isinstance(shop_data, dict):
                    param_obj = shop_data.get(param)
                    param_val = param_obj.get('value') if isinstance(param_obj, dict) else param_obj
                    if param_val is not None:
                        sms_targets[param].append((shop, param_val, weight))

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
                total_val = sum(v * w for _, v, w in values)
                total_weight = sum(w for _, v, w in values)
                sail_sms[param] = round(total_val / total_weight, 3) if total_weight else None

                # Store calculation details for HM Consumption and Scrap
                if param in ["Hot Metal Consumption", "Scrap Consumption"]:
                    shop_details = []
                    for shop, v, w in values:
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

        # Save computed SAIL values in {param: {value, unit}} format
        computed_sail = {}
        for param, value in {**sail_bf, **sail_sms}.items():
            computed_sail[param] = {"value": value, "unit": ""}

        db.save_sail_techno_plan(fy, computed_sail, is_user_supplied=False,
                                calculated_json=computed_sail, calculation_method={})

        return {
            "status": "success",
            "fy": fy,
            "sail_bf": sail_bf,
            "sail_sms": sail_sms,
            "bf_calculations": bf_calc_steps,
            "sms_calculations": sms_calc_steps,
            "production_metadata": production_metadata,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-summary")
async def get_techno_summary(fy: str = Query("2026-27")):
    """
    Get comprehensive techno targets summary for PDF and visualization
    Returns BF and SMS targets with graph data
    """
    try:
        fy_year = int(fy.split("-")[0])

        conn = sqlite3.connect(db.DB_PATH)
        cur = conn.cursor()

        # Get all plants and their BF targets
        plants = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']
        bf_data = {}
        for plant in plants:
            plan_result = db.get_techno_plant_plan(plant, fy)
            plan_data = plan_result.get('data', {}) if plan_result else {}
            if plan_data:
                # Extract values from {param: {value, unit}} format
                formatted_data = {}
                for param, param_obj in plan_data.items():
                    if isinstance(param_obj, dict):
                        formatted_data[param] = param_obj
                    else:
                        formatted_data[param] = {"value": param_obj, "unit": ""}
                bf_data[plant] = formatted_data

        # Get all SMS shops and their targets
        sms_shops = [
            "BSP SMS-2", "BSP SMS-3",
            "DSP SMS",
            "RSP SMS-1", "RSP SMS-2",
            "BSL SMS-1", "BSL SMS-2",
            "ISP SMS-1",
        ]
        sms_data = {}
        for shop in sms_shops:
            plant = shop.split()[0]
            shop_result = db.get_techno_plan(plant, fy, shop)
            shop_data = shop_result.get('data', {}) if shop_result else {}
            if shop_data:
                sms_data[shop] = shop_data

        # Get SAIL targets
        sail_result = db.get_sail_techno_plan(fy)
        sail_data = sail_result.get('data', {}) if sail_result else {}

        # Get production data for context
        months = (
            [f"{fy_year}-{m:02d}" for m in range(4, 13)] +
            [f"{fy_year + 1}-{m:02d}" for m in range(1, 4)]
        )
        ph = ",".join("?" * len(months))

        # HM production by plant
        cur.execute(f"""
            SELECT plant_name, SUM(month_actual)
            FROM production_plan_table
            WHERE report_month IN ({ph}) AND item_name = 'Hot Metal'
              AND plant_name IN ('BSP','DSP','RSP','BSL','ISP')
            GROUP BY plant_name
        """, months)
        hm_weights = {row[0]: row[1] for row in cur.fetchall()}

        # CS production by plant and SMS shop
        shop_to_plant = {
            "BSP SMS-2": "BSP", "BSP SMS-3": "BSP",
            "DSP SMS": "DSP",
            "RSP SMS-1": "RSP", "RSP SMS-2": "RSP",
            "BSL SMS-1": "BSL", "BSL SMS-2": "BSL",
            "ISP SMS-1": "ISP",
        }
        shop_cs_weights = {}
        for shop, plant in shop_to_plant.items():
            shop_parts = shop.split()
            sms_identifier = " ".join(shop_parts[1:]) if len(shop_parts) > 1 else shop
            cur.execute(f"""
                SELECT SUM(month_actual)
                FROM production_plan_table
                WHERE report_month IN ({ph})
                  AND (item_name = ? OR item_name LIKE ?)
                  AND plant_name = ?
            """, months + [sms_identifier, sms_identifier + " %", plant])
            result = cur.fetchone()
            weight = result[0] if result and result[0] else None
            if weight is None:
                # ISP's production items are named "SMS CCM-1&2"/"SMS CCM-3" —
                # the shop number isn't in the item name, so the exact/prefix
                # match above misses. When a plant has only one SMS shop, fall
                # back to summing all of its "SMS%" production items.
                plant_shops = [s for s, p in shop_to_plant.items() if p == plant]
                if len(plant_shops) == 1:
                    cur.execute(f"""
                        SELECT SUM(month_actual)
                        FROM production_plan_table
                        WHERE report_month IN ({ph})
                          AND item_name LIKE 'SMS%'
                          AND plant_name = ?
                    """, months + [plant])
                    fallback = cur.fetchone()
                    weight = fallback[0] if fallback and fallback[0] else 0
            shop_cs_weights[shop] = weight or 0

        conn.close()

        return {
            "status": "success",
            "fy": fy,
            "bf_targets": bf_data,
            "sms_targets": sms_data,
            "sail_targets": sail_data,
            "production_context": {
                "hm_weights": hm_weights,
                "sms_cs_weights": shop_cs_weights
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8082))
    uvicorn.run(app, host="0.0.0.0", port=port)
