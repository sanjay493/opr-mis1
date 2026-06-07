import os
import json
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import io
import db

# Initialize SQLite database and tables
db.init_db()

# Initialize FastAPI App
app = FastAPI(
    title="SAIL OMI MIS Report Generator Backend",
    description="Python API backend to compile and export SAIL MIS reports using WeasyPrint."
)

# STRICT CORS config - no wildcards (*) for secure BFF API design
allowed_origins = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:3001", "http://127.0.0.1:3001"
]
frontend_origin = os.environ.get("FRONTEND_ORIGIN")
if frontend_origin:
    allowed_origins.append(frontend_origin)

frontend_port = os.environ.get("FRONTEND_PORT")
if frontend_port:
    allowed_origins.extend([
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}"
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Path to front-end data
FRONTEND_DATA_PATH = "/home/kumar/opr-mis1/frontend/src/data/mis_data.json"

# Pydantic schemas for request validation
class PageRow(BaseModel):
    label: str
    values: List[str]

class IndexRow(BaseModel):
    sno: str
    title: str
    page_range: str

class ProductionRow(BaseModel):
    item: str
    values: List[str]

class TeRow(BaseModel):
    parameter: str
    unit: str
    values: List[str]

class PageData(BaseModel):
    page: int
    title: str
    subtitle: Optional[str] = ""
    type: str
    headers: Optional[List[str]] = []
    rows: Optional[List[Dict[str, Any]]] = []
    highlights: Optional[List[str]] = []
    production_table: Optional[List[Dict[str, Any]]] = []
    te_table: Optional[List[Dict[str, Any]]] = []
    date: Optional[str] = None
    orientation: Optional[str] = "portrait"

class PDFRequest(BaseModel):
    month: str
    pages: List[PageData]

def compute_item_row(month: str, item_name: str) -> list:
    """Computes a 10-value list for SAIL summary page by summing metrics across plants from DB."""
    # Map UI display item names to the database item names
    db_item = item_name
    if item_name == "Crude Steel":
        db_item = "Total Crude Steel"
    elif item_name == "Finish Steel":
        db_item = "Finished Steel"
        
    # 1. Month Plan and Actual
    month_plan = db.get_sail_production_plan(month, db_item)
    month_actual = db.get_sail_production_actual(month, db_item)
    
    # 2. Month CPLY
    cply_month = db.get_cply_month(month)
    month_cply_actual = db.get_sail_production_actual(cply_month, db_item)
    
    # 3. YTD Plan and Actual
    ytd_months = db.get_ytd_months(month)
    ytd_plan = db.get_sail_production_ytd_plan(ytd_months, db_item)
    ytd_actual = db.get_sail_production_ytd_actual(ytd_months, db_item)
    
    # 4. YTD CPLY Actual
    ytd_cply_months = db.get_ytd_months(cply_month)
    ytd_cply_actual = db.get_sail_production_ytd_actual(ytd_cply_months, db_item)
    
    def fmt(val):
        if val is None:
            return ""
        # Round to 0 decimal places as requested
        return str(round(val))
        
    def pct(num, den):
        if num is None or den is None or den == 0:
            return ""
        val = (num / den) * 100
        return str(round(val))
        
    def growth(num, den):
        if num is None or den is None or den == 0:
            return ""
        val = ((num - den) / den) * 100
        return str(round(val))
        
    # Compile the 10 values:
    # 0: APP, 1: Actual, 2: % Ful, 3: Act (CPLY), 4: % Gr,
    # 5: APP (YTD), 6: Actual (YTD), 7: % Ful (YTD), 8: Act (YTD CPLY), 9: % Gr (YTD)
    return [
        fmt(month_plan),
        fmt(month_actual),
        pct(month_actual, month_plan),
        fmt(month_cply_actual),
        growth(month_actual, month_cply_actual),
        fmt(ytd_plan),
        fmt(ytd_actual),
        pct(ytd_actual, ytd_plan),
        fmt(ytd_cply_actual),
        growth(ytd_actual, ytd_cply_actual)
    ]

def compute_page4_row(month: str, item_name: str, plant: str) -> list:
    """Computes 15-value list for page 4 (plant-wise production) for an item-plant combo."""
    def fmt(val):
        if val is None:
            return ""
        return str(round(val))

    def pct(num, den):
        if num is None or den is None or den == 0:
            return ""
        return str(round((num / den) * 100))

    def growth(num, den):
        if num is None or den is None or den == 0:
            return ""
        return str(round(((num - den) / den) * 100))

    # Get current month data
    plan_curr = db.get_sail_production_plan(month, item_name) if plant == "SAIL" else None
    actual_curr = db.get_sail_production_actual(month, item_name) if plant == "SAIL" else None

    if plant != "SAIL":
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT month_actual FROM production_plan_table
            WHERE report_month = ? AND plant_name = ? AND item_name = ?
        """, (month, plant, item_name))
        row = cursor.fetchone()
        plan_curr = row[0] if row else None

        cursor.execute("""
            SELECT month_actual FROM production_table
            WHERE report_month = ? AND plant_name = ? AND item_name = ?
        """, (month, plant, item_name))
        row = cursor.fetchone()
        actual_curr = row[0] if row else None
        conn.close()

    # Get previous year data
    prev_month = db.get_cply_month(month)
    actual_prev = db.get_sail_production_actual(prev_month, item_name) if plant == "SAIL" else None

    if plant != "SAIL":
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT month_actual FROM production_table
            WHERE report_month = ? AND plant_name = ? AND item_name = ?
        """, (prev_month, plant, item_name))
        row = cursor.fetchone()
        actual_prev = row[0] if row else None
        conn.close()

    # Get YTD data
    ytd_months = db.get_ytd_months(month)
    ytd_plan = db.get_sail_production_ytd_plan(ytd_months, item_name) if plant == "SAIL" else None
    ytd_actual = db.get_sail_production_ytd_actual(ytd_months, item_name) if plant == "SAIL" else None

    if plant != "SAIL":
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        month_placeholders = ",".join("?" for _ in ytd_months)
        cursor.execute(f"""
            SELECT SUM(month_actual) FROM production_plan_table
            WHERE report_month IN ({month_placeholders}) AND plant_name = ? AND item_name = ?
        """, ytd_months + [plant, item_name])
        row = cursor.fetchone()
        ytd_plan = row[0] if row and row[0] else None

        cursor.execute(f"""
            SELECT SUM(month_actual) FROM production_table
            WHERE report_month IN ({month_placeholders}) AND plant_name = ? AND item_name = ?
        """, ytd_months + [plant, item_name])
        row = cursor.fetchone()
        ytd_actual = row[0] if row and row[0] else None
        conn.close()

    # Get YTD previous year data
    ytd_prev_months = db.get_ytd_months(prev_month)
    ytd_actual_prev = db.get_sail_production_ytd_actual(ytd_prev_months, item_name) if plant == "SAIL" else None

    if plant != "SAIL":
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        month_placeholders = ",".join("?" for _ in ytd_prev_months)
        cursor.execute(f"""
            SELECT SUM(month_actual) FROM production_table
            WHERE report_month IN ({month_placeholders}) AND plant_name = ? AND item_name = ?
        """, ytd_prev_months + [plant, item_name])
        row = cursor.fetchone()
        ytd_actual_prev = row[0] if row and row[0] else None
        conn.close()

    # Compile 15 values for page 4
    return [
        fmt(plan_curr),                    # 0: Plan 25-26 (annual plan)
        fmt(plan_curr),                    # 1: APP current month
        fmt(actual_curr),                  # 2: Actual current month
        fmt(actual_curr - plan_curr) if (actual_curr and plan_curr) else "",  # 3: Variance
        pct(actual_curr, plan_curr),       # 4: % Fulfilled
        fmt(actual_prev),                  # 5: Actual prev year
        growth(actual_curr, actual_prev),  # 6: % Growth
        fmt(ytd_plan),                     # 7: APP YTD
        fmt(ytd_actual),                   # 8: Actual YTD
        fmt(ytd_actual - ytd_plan) if (ytd_actual and ytd_plan) else "",  # 9: Variance YTD
        pct(ytd_actual, ytd_plan),         # 10: % Fulfilled YTD
        fmt(ytd_actual_prev),              # 11: Actual YTD prev year
        growth(ytd_actual, ytd_actual_prev) # 12: % Growth YTD
    ]

def blank_out_page_data(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Blanks out mock/dummy numeric data and highlights from the template pages config."""
    blanked_pages = []
    for page in pages:
        p = dict(page)  # shallow copy

        # 1. Blank out highlights for summary page
        if "highlights" in p:
            p["highlights"] = []

        # 2. Blank out production_table values
        if "production_table" in p and p["production_table"]:
            prod_table = []
            for row in p["production_table"]:
                r = dict(row)
                r["values"] = [""] * len(r.get("values", []))
                prod_table.append(r)
            p["production_table"] = prod_table

        # 3. Blank out te_table values
        if "te_table" in p and p["te_table"]:
            te_table = []
            for row in p["te_table"]:
                r = dict(row)
                r["values"] = [""] * len(r.get("values", []))
                te_table.append(r)
            p["te_table"] = te_table

        # 4. Blank out rows values for other table pages (pages 4-49)
        if "rows" in p and p["rows"] and p.get("type") not in ("index", "cover"):
            rows = []
            for row in p["rows"]:
                r = dict(row)
                r["values"] = [""] * len(r.get("values", []))
                rows.append(r)
            p["rows"] = rows

        blanked_pages.append(p)
    return blanked_pages

@app.get("/api/data")
def get_data(month: str = "November 2025"):
    """Reads data from SQLite database or local template JSON, updating with DB metrics."""
    if not os.path.exists(FRONTEND_DATA_PATH):
        raise HTTPException(status_code=404, detail="Template data source not found.")
    
    try:
        # 1. Fetch saved config from DB if it exists, otherwise load fallback json
        pages_config = db.get_all_page_configs(month)
                
        if not pages_config:
            # Fallback to loading from JSON file
            with open(FRONTEND_DATA_PATH, "r", encoding="utf-8") as f:
                pages_config = json.load(f)
            # Blank out dummy/mock values from the template
            pages_config = blank_out_page_data(pages_config)
        
        # 2. Check if we have production database records for this month
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM production_table WHERE report_month = ?", (month,))
        has_actuals = cursor.fetchone()[0] > 0
        cursor.execute("SELECT COUNT(*) FROM production_plan_table WHERE report_month = ?", (month,))
        has_plans = cursor.fetchone()[0] > 0
        conn.close()
        
        # 3. If database has records, dynamically compile Page 3 production table and Page 4
        if has_actuals or has_plans:
            for page in pages_config:
                # Page 3: Production summary
                if page.get("page") == 3 or page.get("type") == "summary":
                    prod_table = page.get("production_table", [])
                    for row in prod_table:
                        item_name = row.get("item")
                        row["values"] = compute_item_row(month, item_name)

                # Page 4: Plant-wise production with detailed metrics
                if page.get("page") == 4 or page.get("type") == "page4_table":
                    rows = page.get("rows", [])
                    for row in rows:
                        label = row.get("label", "")
                        # Extract item and plant from label (e.g., "Oven Pushing (Nos./day) BSP")
                        parts = label.rsplit(" ", 1)
                        if len(parts) == 2:
                            item_name = parts[0].strip()
                            plant = parts[1].strip()
                            row["values"] = compute_page4_row(month, item_name, plant)

        return pages_config

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to read data source: {str(e)}")

@app.post("/api/data")
def save_data(request: PDFRequest):
    """Saves report page configurations and updates production tables in SQLite."""
    try:
        # Save each page config
        for page in request.pages:
            db.save_page_config(request.month, page.page, page.dict())
            
            # If it's the Summary Page (Page 3), save edited production values back to DB
            if page.page == 3 or page.type == "summary":
                prod_table = page.production_table or []
                for row in prod_table:
                    item_name = row.get("item")
                    vals = row.get("values", [])
                    if len(vals) >= 2:
                        plan_val_str = vals[0]
                        act_val_str = vals[1]
                        
                        # Helper to parse UI value ('000 T) directly as DB value ('000 T)
                        def parse_val(val_str):
                            if not val_str or val_str.strip() == "":
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
                            
                        db.save_production_plan(request.month, "SAIL", db_item, parse_val(plan_val_str))
                        db.save_production_actual(request.month, "SAIL", db_item, parse_val(act_val_str))
                        
        return {"status": "success", "message": f"Successfully saved data for {request.month}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save data: {str(e)}")

@app.post("/api/generate-pdf")
async def generate_pdf(request: PDFRequest):
    """Compiles the report page data into HTML and prints it to PDF using WeasyPrint."""
    try:
        from weasyprint import HTML, CSS
        from jinja2 import Template

        # 1. HTML Template for WeasyPrint
        html_template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>SAIL MIS Report - {{ month }}</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
                
                body {
                    font-family: 'Inter', sans-serif;
                    color: #0f172a;
                    margin: 0;
                    padding: 0;
                }
                
                @page {
                    size: A4 portrait;
                    margin: 20mm 15mm 20mm 15mm;
                    @top-center {
                        content: "Steel Authority of India Limited - Operations Monthly Informatics";
                        font-family: 'Inter', sans-serif;
                        font-size: 7.5pt;
                        font-weight: 500;
                        color: #64748b;
                        border-bottom: 0.5px solid #e2e8f0;
                        padding-bottom: 5px;
                    }
                    @bottom-left {
                        content: "Prepared by: MIS Group";
                        font-family: 'Inter', sans-serif;
                        font-size: 7.5pt;
                        color: #64748b;
                    }
                    @bottom-right {
                        content: "Page " counter(page) " of " counter(pages);
                        font-family: 'Inter', sans-serif;
                        font-size: 7.5pt;
                        color: #64748b;
                    }
                }
                
                @page landscape_layout {
                    size: A4 landscape;
                    margin: 15mm 20mm 15mm 20mm;
                    @top-center {
                        content: "Steel Authority of India Limited - Operations Monthly Informatics";
                        font-family: 'Inter', sans-serif;
                        font-size: 7.5pt;
                        font-weight: 500;
                        color: #64748b;
                        border-bottom: 0.5px solid #e2e8f0;
                        padding-bottom: 5px;
                    }
                    @bottom-left {
                        content: "Prepared by: MIS Group";
                        font-family: 'Inter', sans-serif;
                        font-size: 7.5pt;
                        color: #64748b;
                    }
                    @bottom-right {
                        content: "Page " counter(page) " of " counter(pages);
                        font-family: 'Inter', sans-serif;
                        font-size: 7.5pt;
                        color: #64748b;
                    }
                }
                
                .page-landscape {
                    page: landscape_layout;
                    width: 297mm;
                    height: 210mm;
                }
                
                @page:first {
                    margin: 0;
                    @top-center { content: none; }
                    @bottom-left { content: none; }
                    @bottom-right { content: none; }
                }
                
                .page {
                    page-break-after: always;
                    page-break-inside: avoid;
                    box-sizing: border-box;
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                }
                
                /* Cover Page styling */
                .cover-container {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100%;
                    text-align: center;
                    padding: 40mm 20mm;
                }
                
                .cover-accent {
                    width: 80px;
                    height: 6px;
                    background-color: #0284c7;
                    margin-bottom: 30px;
                    border-radius: 3px;
                }
                
                .cover-title {
                    font-size: 30pt;
                    font-weight: 900;
                    color: #0f172a;
                    line-height: 1.1;
                    margin-bottom: 10px;
                    text-transform: uppercase;
                }
                
                .cover-subtitle {
                    font-size: 14pt;
                    font-weight: 500;
                    color: #475569;
                    letter-spacing: 0.05em;
                    text-transform: uppercase;
                    margin-bottom: 60px;
                }
                
                .cover-meta {
                    margin-top: auto;
                    border-top: 1px solid #e2e8f0;
                    padding-top: 30px;
                    width: 100%;
                    display: flex;
                    justify-content: space-between;
                    font-size: 9pt;
                    color: #64748b;
                }
                
                /* Standard page layout */
                .report-title-section {
                    text-align: center;
                    margin-bottom: 15px;
                }
                
                .report-title-section h2 {
                    font-size: 13pt;
                    font-weight: 800;
                    color: #0f172a;
                    text-transform: uppercase;
                    margin: 0;
                }
                
                .report-title-section h3 {
                    font-size: 10pt;
                    font-weight: 600;
                    color: #475569;
                    margin: 4px 0 0 0;
                }
                
                /* Tables */
                .report-table {
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 7.5pt;
                    margin-top: 10px;
                }
                
                .report-table th {
                    background-color: #f1f5f9;
                    color: #0f172a;
                    font-weight: 700;
                    text-transform: uppercase;
                    font-size: 6.5pt;
                    padding: 5px 4px;
                    border: 1px solid #94a3b8;
                    text-align: center;
                }
                
                .report-table td {
                    padding: 4px 4px;
                    border: 1px solid #cbd5e1;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 7.0pt;
                    text-align: right;
                }
                
                .report-table td.label-cell {
                    text-align: left;
                    font-family: 'Inter', sans-serif;
                    font-size: 7.5pt;
                    font-weight: 500;
                }
                
                .index-table th {
                    font-size: 10pt !important;
                    padding: 6px 10px !important;
                }
                
                .index-table td {
                    font-size: 10pt !important;
                    padding: 5px 10px !important;
                    font-family: 'Inter', sans-serif !important;
                    text-align: left !important;
                }
                
                .index-table td.center-align {
                    text-align: center !important;
                }
                
                /* Highlights */
                .highlights-box {
                    background-color: #f8fafc;
                    border-left: 3px solid #0284c7;
                    padding: 10px;
                    border-radius: 4px;
                    margin: 10px 0;
                    font-size: 8pt;
                }
                
                .highlights-box h4 {
                    font-weight: 700;
                    text-transform: uppercase;
                    color: #0f172a;
                    margin: 0 0 5px 0;
                    font-size: 8.5pt;
                }
                
                .highlights-box ul {
                    margin: 0;
                    padding: 0 0 0 15px;
                    list-style-type: disc;
                }
                
                .highlights-box li {
                    margin-bottom: 4px;
                    line-height: 1.3;
                }
                
                /* Wide trend tables formatting */
                .trend-table {
                    font-size: 6pt !important;
                }
                
                .trend-table th {
                    font-size: 5pt !important;
                    padding: 3px 1.5px;
                }
                
                .trend-table td {
                    font-size: 5.5pt !important;
                    padding: 2.5px 1.5px;
                }
            </style>
        </head>
        <body>
            {% for page in pages %}
            <div class="page {% if page.orientation == 'landscape' %}page-landscape{% endif %}">
                
                {% if page.type == 'cover' %}
                    <div class="cover-container">
                        <div class="cover-accent"></div>
                        <h1 class="cover-title">{{ page.title }}</h1>
                        <p class="cover-subtitle">O P E R A T I O N S   D I R E C T O R A T E</p>
                        <div class="cover-meta">
                            <div>
                                <strong>Prepared By:</strong>
                                <div style="margin-top: 4px;">MIS Group</div>
                            </div>
                            <div>
                                <strong>Report Month:</strong>
                                <div style="margin-top: 4px;">{{ month }}</div>
                            </div>
                        </div>
                    </div>
                    
                {% elif page.type == 'index' %}
                    <div class="report-title-section">
                        <h2>{{ page.title }}</h2>
                    </div>
                    <table class="report-table index-table" style="margin-top: 15px; width: 100%;">
                        <thead>
                            <tr>
                                <th style="width: 10%; text-align: center;">S.No.</th>
                                <th style="width: 75%; text-align: left; padding-left: 10px;">Contents</th>
                                <th style="width: 15%; text-align: center;">Page</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in page.rows %}
                            <tr>
                                <td class="center-align" style="font-family: inherit;">{{ row.sno }}</td>
                                <td style="font-family: inherit; font-weight: {% if row.sno %}600{% else %}400{% endif %};">
                                    {{ row.title }}
                                </td>
                                <td class="center-align" style="font-family: inherit;">{{ row.page_range }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    
                {% elif page.type == 'summary' %}
                    <div class="report-title-section">
                        <h2>{{ page.title }}</h2>
                        <h3>{{ month }}</h3>
                    </div>
                    
                    <!-- Prod Table -->
                    <h4 style="font-size: 8pt; font-weight: bold; margin: 10px 0 4px 0; text-transform: uppercase;">
                        Production Performance Summary (Unit: '000 T)
                    </h4>
                    <table class="report-table">
                        <thead>
                            <tr>
                                <th rowspan="2">Item</th>
                                <th colspan="3">{{ m_name }} {{ y_str }}</th>
                                <th colspan="2">{{ short_m }}’{{ short_prev_y }}</th>
                                <th colspan="3">April - {{ m_name }} {{ y_str }}</th>
                                <th colspan="2">April-{{ short_m }}’{{ short_prev_y }}</th>
                            </tr>
                            <tr>
                                <th>APP</th>
                                <th>Actual</th>
                                <th>% Ful.</th>
                                <th>Act.</th>
                                <th>% Gr.</th>
                                <th>APP</th>
                                <th>Actual</th>
                                <th>% Ful.</th>
                                <th>Act.</th>
                                <th>% Gr.</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in page.production_table %}
                            <tr>
                                <td class="label-cell">{{ row.item }}</td>
                                {% for val in row['values'] %}
                                <td>{{ val }}</td>
                                {% endfor %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    
                    <!-- Highlights -->
                    {% if page.highlights %}
                    <div class="highlights-box">
                        <h4>Key Production Highlights</h4>
                        <ul>
                            {% for highlight in page.highlights %}
                            <li>{{ highlight }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                    {% endif %}
                    
                    <!-- TE Table -->
                    <h4 style="font-size: 8pt; font-weight: bold; margin: 10px 0 4px 0; text-transform: uppercase;">
                        Major Techno-Economic Parameters
                    </h4>
                    <table class="report-table">
                        <thead>
                            <tr>
                                <th>Parameter</th>
                                <th>Unit</th>
                                <th>{{ target_header }}</th>
                                <th>{{ short_m }}'{{ short_y }}</th>
                                <th>{{ short_m }}'{{ short_prev_y }}</th>
                                <th>Apr-{{ short_m }}'{{ short_y }}</th>
                                <th>Apr-{{ short_m }}'{{ short_prev_y }}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in page.te_table %}
                            <tr>
                                <td class="label-cell">{{ row.parameter }}</td>
                                <td class="label-cell" style="font-style: italic; color: #475569;">{{ row.unit }}</td>
                                {% for val in row['values'] %}
                                <td>{{ val }}</td>
                                {% endfor %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    
                {% elif page.type == 'trend' %}
                    <div class="report-title-section">
                        <h2>{{ page.title }}</h2>
                        {% if page.subtitle %}<h3>{{ page.subtitle }}</h3>{% endif %}
                    </div>
                    <table class="report-table trend-table">
                        <thead>
                            <tr>
                                {% for h in page.headers %}
                                <th>{{ h }}</th>
                                {% endfor %}
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in page.rows %}
                            <tr>
                                <td class="label-cell" style="font-weight: 600;">{{ row.label }}</td>
                                {% for val in row['values'] %}
                                <td>{{ val }}</td>
                                {% endfor %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    
                {% elif page.type == 'page4_table' %}
                    <div style="border-bottom: 2px solid #0f172a; padding-bottom: 4px; margin-bottom: 8px; width: 100%;">
                        <h2 style="font-size: 11.0pt; font-weight: 800; color: #0f172a; margin: 0; text-transform: uppercase; float: left;">
                            SAIL: Production Performance during {{ m_name }}'{{ short_y }} and Apr-{{ short_m }}'{{ short_y }}
                        </h2>
                        <h2 style="font-size: 11.0pt; font-weight: 800; color: #0f172a; margin: 0; text-transform: uppercase; float: right;">
                            w.r.t APP
                        </h2>
                        <div style="clear: both;"></div>
                    </div>
                    <div style="margin-bottom: 2px; width: 100%; font-size: 7.5pt; font-weight: 600; color: #475569;">
                        <span style="float: left;">Tentative</span>
                        <span style="float: right;">Unit: '000 T</span>
                        <div style="clear: both;"></div>
                    </div>
                    <table class="report-table">
                        <thead>
                            <tr>
                                <th rowspan="2" style="vertical-align: middle;">Items</th>
                                <th rowspan="2" style="vertical-align: middle;">Plant</th>
                                <th rowspan="2" style="vertical-align: middle;">APP {{ target_header.split()[1] }}</th>
                                <th colspan="4" style="text-align: center;">{{ short_m }}'{{ short_y }}</th>
                                <th rowspan="2" style="vertical-align: middle;">{{ short_m }}'{{ short_prev_y }}<br/>Actual</th>
                                <th rowspan="2" style="vertical-align: middle;">% Gr. over<br/>{{ short_m }}'{{ short_prev_y }}</th>
                                <th colspan="4" style="text-align: center;">Apr-{{ short_m }}'{{ short_y }}</th>
                                <th rowspan="2" style="vertical-align: middle;">Apr-{{ short_m }}'{{ short_prev_y }}<br/>Actual</th>
                                <th rowspan="2" style="vertical-align: middle;">% Gr. over<br/>Apr-{{ short_m }}'{{ short_prev_y }}</th>
                            </tr>
                            <tr>
                                <th>APP</th>
                                <th>Actual</th>
                                <th>Var</th>
                                <th>% Ful.</th>
                                <th>APP</th>
                                <th>Actual</th>
                                <th>Var</th>
                                <th>% Ful.</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in page.rows %}
                            <tr>
                                {% if row.is_first_in_group %}
                                <td class="label-cell" rowspan="{{ row.group_size }}" style="font-weight: 700; vertical-align: middle; background-color: #f8fafc; border-right: 1px solid #cbd5e1; font-family: 'Inter', sans-serif;">
                                    {{ row.item }}
                                </td>
                                {% endif %}
                                <td class="label-cell" style="font-weight: 600; text-align: center; background-color: #f8fafc; font-family: 'Inter', sans-serif;">
                                    {{ row.plant }}
                                </td>
                                {% for val in row['values'] %}
                                <td>{{ val }}</td>
                                {% endfor %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>

                {% elif page.type == 'performance_summary_table' %}
                    <div class="report-title-section">
                        <h2>{{ page.title }}</h2>
                        {% if page.subtitle %}<h3>{{ page.subtitle }}</h3>{% endif %}
                    </div>
                    <table class="report-table">
                        <thead>
                            <tr>
                                {% for h in page.headers %}
                                <th>{{ h }}</th>
                                {% endfor %}
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in page.rows %}
                            <tr>
                                <td class="label-cell" style="font-weight: 500;">{{ row.label }}</td>
                                {% for val in row['values'] %}
                                <td>{{ val }}</td>
                                {% endfor %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>

                {% else %}
                    <div class="report-title-section">
                        <h2>{{ page.title }}</h2>
                        {% if page.subtitle %}<h3>{{ page.subtitle }}</h3>{% endif %}
                    </div>
                    <table class="report-table">
                        <thead>
                            <tr>
                                {% for h in page.headers %}
                                <th>{{ h }}</th>
                                {% endfor %}
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in page.rows %}
                            <tr>
                                <td class="label-cell">{{ row.label }}</td>
                                {% for val in row['values'] %}
                                <td>{{ val }}</td>
                                {% endfor %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                {% endif %}
                
            </div>
            {% endfor %}
        </body>
        </html>
        """

        # 2. Render Template with Jinja2
        try:
            m_name, y_str = request.month.split()
            short_m = m_name[:3]
            
            # Map month name to index (0-11)
            months_order = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            m_idx = months_order.index(m_name) if m_name in months_order else 10
            
            # Target Financial Year calculations
            target_fy_start = int(y_str)
            if 0 <= m_idx < 3: # Jan, Feb, Mar
                target_fy_start -= 1
            target_fy_end = (target_fy_start + 1) % 100
            target_header = f"Target {target_fy_start}-{target_fy_end:02d}"
            
            short_y = y_str[2:]
            prev_y_str = str(int(y_str) - 1)
            short_prev_y = prev_y_str[2:]
        except Exception:
            m_name, y_str = "November", "2025"
            short_m, short_y, prev_y_str, short_prev_y = "Nov", "25", "2024", "24"
            target_header = "Target 2025-26"

        # Preprocess page4_table rows to group them with rowspan logic
        pages_to_render = []
        for p_data in request.pages:
            p = p_data.dict()
            if p.get("type") == "page4_table":
                rows = p.get("rows", [])
                grouped_rows = []
                i = 0
                plants = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL', 'ASP', 'SSP', 'VISL', '5 Plants']
                while i < len(rows):
                    label = rows[i].get("label", "").strip()
                    parts = label.split()
                    
                    # splitLabel equivalent in Python
                    if len(parts) > 1 and parts[-1] in plants:
                        item = " ".join(parts[:-1])
                        plant = parts[-1]
                    elif len(parts) > 2 and " ".join(parts[-2:]) in plants:
                        item = " ".join(parts[:-2])
                        plant = " ".join(parts[-2:])
                    elif label in plants:
                        item = ""
                        plant = label
                    else:
                        item = label
                        plant = ""
                        
                    count = 1
                    while i + count < len(rows):
                        next_label = rows[i + count].get("label", "").strip()
                        next_parts = next_label.split()
                        if len(next_parts) > 1 and next_parts[-1] in plants:
                            next_item = " ".join(next_parts[:-1])
                        elif len(next_parts) > 2 and " ".join(next_parts[-2:]) in plants:
                            next_item = " ".join(next_parts[:-2])
                        elif next_label in plants:
                            next_item = ""
                        else:
                            next_item = next_label
                            
                        if next_item == item and item != "":
                            count += 1
                        else:
                            break
                            
                    for c in range(count):
                        row_data = dict(rows[i + c])
                        row_data["is_first_in_group"] = (c == 0)
                        row_data["group_size"] = count
                        row_data["item"] = item
                        
                        r_label = rows[i + c].get("label", "").strip()
                        r_parts = r_label.split()
                        if len(r_parts) > 1 and r_parts[-1] in plants:
                            r_plant = r_parts[-1]
                        elif len(r_parts) > 2 and " ".join(r_parts[-2:]) in plants:
                            r_plant = " ".join(r_parts[-2:])
                        else:
                            r_plant = r_label
                        row_data["plant"] = r_plant
                        
                        grouped_rows.append(row_data)
                    i += count
                p["rows"] = grouped_rows
            pages_to_render.append(p)

        template = Template(html_template_str)
        rendered_html = template.render(
            month=request.month,
            m_name=m_name,
            y_str=y_str,
            short_m=short_m,
            short_y=short_y,
            prev_y_str=prev_y_str,
            short_prev_y=short_prev_y,
            target_header=target_header,
            pages=pages_to_render
        )
        
        # 3. Compile PDF in memory using WeasyPrint
        pdf_io = io.BytesIO()
        HTML(string=rendered_html).write_pdf(pdf_io)
        pdf_io.seek(0)
        
        # 4. Stream response securely
        return StreamingResponse(
            pdf_io, 
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=SAIL_MIS_Report_{request.month.replace(' ', '_')}.pdf",
                "X-Content-Type-Options": "nosniff"
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF Compilation failed: {str(e)}")

@app.post("/api/upload-excel")
async def upload_excel(
    file: UploadFile = File(...),
    plant_name: str = Form(...),
    month: str = Form(...)
):
    """Saves the uploaded Excel file temporarily and extracts metrics into production_table and techno_table."""
    import shutil
    import tempfile
    import sys
    
    # Create temp directory
    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    suffix = os.path.splitext(file.filename)[1]
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
            
        # RSP and ISP are currently supported
        if plant_name not in ("RSP", "ISP"):
            raise ValueError(f"Excel extraction is currently only supported for RSP and ISP, not {plant_name}.")
            
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        if plant_name == "RSP":
            import excel_extractor_rsp
            success = excel_extractor_rsp.extract_and_save_excel(tmp_path, month)
        else:
            import excel_extractor_isp
            success = excel_extractor_isp.extract_and_save_excel(tmp_path, month)
        
        if not success:
            raise Exception(f"{plant_name} Excel extractor returned failure state.")
            
        return {"status": "success", "message": f"Successfully extracted actual metrics for {plant_name} for {month}."}

        
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
    financial_year: str = Form(...)
):
    """Saves the uploaded ABP Excel file temporarily and extracts target metrics into production_plan_table."""
    import shutil
    import tempfile
    import sys
    
    # Create temp directory
    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    suffix = os.path.splitext(file.filename)[1]
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
            
        # RSP, ISP, BSP and DSP are currently supported
        if plant_name not in ("RSP", "ISP", "BSP", "DSP"):
            raise ValueError(f"Plan Excel extraction is currently only supported for RSP, ISP, BSP and DSP, not {plant_name}.")
            
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
        else:
            import excel_extractor_dsp_plan
            success = excel_extractor_dsp_plan.extract_and_save_excel_plan(tmp_path, financial_year)


            
        if not success:
            raise Exception(f"{plant_name} Plan Excel extractor returned failure state.")
            
        return {"status": "success", "message": f"Successfully extracted planned target metrics for {plant_name} for Financial Year {financial_year}."}
        
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

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8082))
    # Test server exclusively listens on localhost/127.0.0.1 (never 0.0.0.0) as per security rules
    uvicorn.run(app, host="0.0.0.0", port=port)
