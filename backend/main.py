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
from page7_13 import generate_trend_page_rows, generate_combined_trend_items, TREND_PAGES
from page17_concast import generate_concast_data
from page_prod_by_process import generate_prod_by_process
from page_catwise_saleable import generate_catwise_saleable
from page_segment_wise import generate_segment_wise
from page_special_steel import generate_special_steel_plant, generate_special_steel_sail
from page_opening_stock import generate_opening_stock
from page_ipt import generate_ipt
from page_techno import generate_techno, TECHNO_PAGES
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
                    page["type"]  = "segment_wise"
                    page["title"] = "SEGMENT WISE PRODUCTION"
                    sw = generate_segment_wise(month)
                    page["rows"]  = sw["rows"]

        # Always regenerate special steel pages (data from special_steel_orders,
        # independent of production_table / production_plan_table)
        import datetime as _dt
        _dt_obj = _dt.datetime.strptime(month, "%Y-%m")
        _ml = _dt_obj.strftime("%b'%y")
        _cl = _dt.datetime(_dt_obj.year - 1, _dt_obj.month, 1).strftime("%b'%y")
        _SPECIAL_PLANTS = {19: "BSP", 20: "DSP", 21: "RSP", 22: "BSL", 23: "ISP"}
        for page in pages_config:
            pg = page.get("page")
            if pg in _SPECIAL_PLANTS or pg == 24:
                page["month_label"] = _ml
                page["cply_label"]  = _cl
            if pg in _SPECIAL_PLANTS:
                ss = generate_special_steel_plant(month, _SPECIAL_PLANTS[pg])
                page.update(ss)
                page["type"] = "special_steel"
            if pg == 24:
                ss = generate_special_steel_sail(month)
                page.update(ss)
                page["type"] = "special_steel"
            if pg == 25:
                page.update(generate_opening_stock(month))
                page["type"] = "opening_stock"
            if pg == 26:
                page.update(generate_ipt(month))
                page["type"] = "ipt_status"
            if pg in TECHNO_PAGES:
                page.update(generate_techno(month, pg))
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
            p["type"] = "segment_wise"
            p["rows"]  = generate_segment_wise(request.month)["rows"]
        _SP = {19: "BSP", 20: "DSP", 21: "RSP", 22: "BSL", 23: "ISP"}
        if pg in _SP:
            ss = generate_special_steel_plant(request.month, _SP[pg])
            p.update(ss); p["type"] = "special_steel"
        if pg == 24:
            ss = generate_special_steel_sail(request.month)
            p.update(ss); p["type"] = "special_steel"
        if pg == 25:
            p.update(generate_opening_stock(request.month))
            p["type"] = "opening_stock"
        if pg == 26:
            p.update(generate_ipt(request.month))
            p["type"] = "ipt_status"
        if pg in TECHNO_PAGES:
            p.update(generate_techno(request.month, pg))
            p["type"] = "techno_params"
        enriched.append(p)
    return await build_pdf_response(request, pages_override=enriched, page_layouts=request.page_layouts, font_config=request.font_config)


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

        if plant_name == "DSP":
            import excel_extractor_dsp
            aliases = db.get_pdf_item_aliases("DSP")
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        pool,
                        lambda: excel_extractor_dsp.extract_preview(
                            tmp_path, month, aliases=aliases, block=extract_block)
                    ),
                    timeout=300.0,
                )
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
                cur.execute("""
                    INSERT INTO techno_table (report_month, plant_name, parameter_name, unit, month_actual, ytd_actual)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(report_month, plant_name, parameter_name)
                    DO UPDATE SET unit=excluded.unit, month_actual=excluded.month_actual,
                                  ytd_actual=excluded.ytd_actual
                """, (month, plant, r.get("parameter"), r.get("unit", ""),
                      r.get("month_actual"), r.get("ytd_actual")))
                if r.get("month_actual") is not None or r.get("ytd_actual") is not None:
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
            db.save_techno_value(month, pid, r.get("actual"), r.get("cum_actual"))
            saved_mill += 1

        saved_ss = 0
        for r in payload.get("special_steel_rows", []):
            if r.get("status") != "ok":
                continue  # skip "total" rows (cross-check only) and anything not ok
            db.save_special_steel_entry(
                month, plant,
                r.get("product", ""), r.get("quality_grade", ""),
                r.get("sort_order", 0),
                r.get("order_qty"), r.get("actual_despatch"),
                section=r.get("section", ""),
            )
            saved_ss += 1

        total = saved_prod + saved_plan + saved_te + saved_mill + saved_ss
        if total:
            db.log_extraction(plant, month, payload.get("file_name", ""),
                              payload.get("sheets", ""),
                              payload.get("source_type", "Preview Confirmed"), total)
        msg = (f"Inserted {saved_prod} production, {saved_plan} plan, {saved_te} techno, "
               f"{saved_mill} mill techno, {saved_ss} special steel values for {plant} {month}.")
        if saved_aliases:
            msg += f" Remembered {saved_aliases} item-name mapping(s) for future extractions."
        return {
            "status": "success",
            "saved_production": saved_prod,
            "saved_plan": saved_plan,
            "saved_techno": saved_te,
            "saved_mill_techno": saved_mill,
            "saved_special_steel": saved_ss,
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
    return {"status": "success", "saved": saved,
            "message": f"Inserted {saved} techno parameter values for {plant} {month}."}


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
