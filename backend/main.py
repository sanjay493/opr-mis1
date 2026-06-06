import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import io

# Initialize FastAPI App
app = FastAPI(
    title="SAIL OMI MIS Report Generator Backend",
    description="Python API backend to compile and export SAIL MIS reports using WeasyPrint."
)

# STRICT CORS config - no wildcards (*) for secure BFF API design
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"],
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

@app.get("/api/data")
def get_data():
    """Reads initial dummy data from local frontend configuration file."""
    if not os.path.exists(FRONTEND_DATA_PATH):
        raise HTTPException(status_code=404, detail="Mock data source not found.")
    
    try:
        with open(FRONTEND_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read data source: {str(e)}")

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
                                <th colspan="3">{{ month }}</th>
                                <th colspan="2">CPLY Comparison</th>
                                <th colspan="3">Apr-Nov YTD</th>
                                <th colspan="2">YTD CPLY Comparison</th>
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
                                <th>Target 2025-26</th>
                                <th>Nov'25</th>
                                <th>Nov'24</th>
                                <th>Apr-Nov'25</th>
                                <th>Apr-Nov'24</th>
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
                                {% set label_parts = row.label.strip().split() %}
                                {% if label_parts|length > 1 and label_parts[-1] in ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL', 'ASP', 'SSP', 'VISL'] %}
                                    <td class="label-cell" style="font-weight: 500;">{{ label_parts[:-1]|join(' ') }}</td>
                                    <td class="label-cell" style="font-weight: 500;">{{ label_parts[-1] }}</td>
                                {% else %}
                                    {% if row.label in ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL', 'ASP', 'SSP', 'VISL'] %}
                                        <td class="label-cell" style="font-weight: 500;"></td>
                                        <td class="label-cell" style="font-weight: 500;">{{ row.label }}</td>
                                    {% else %}
                                        <td class="label-cell" style="font-weight: 500;">{{ row.label }}</td>
                                        <td class="label-cell" style="font-weight: 500;"></td>
                                    {% endif %}
                                {% endif %}
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
        template = Template(html_template_str)
        rendered_html = template.render(
            month=request.month,
            pages=[p.dict() for p in request.pages]
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

if __name__ == "__main__":
    import uvicorn
    # Test server exclusively listens on localhost/127.0.0.1 (never 0.0.0.0) as per security rules
    uvicorn.run(app, host="127.0.0.1", port=8082)
