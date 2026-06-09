import io
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from models import PDFRequest

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>SAIL MIS Report - {{ month }}</title>
    <style>
        * { box-sizing: border-box; }

        body {
            font-family: Arial, Helvetica, sans-serif;
            color: #0f172a;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }

        @page {
            size: A4 portrait;
            margin: 15mm 15mm 15mm 15mm;
        }

        .page {
            page-break-after: always;
            break-after: page;
            page-break-inside: avoid;
            padding: 5mm 0 3mm 0;
        }

        .page:last-child {
            page-break-after: auto;
        }

        /* Running header/footer for non-cover pages */
        .page-header-bar {
            text-align: center;
            font-size: 7.5pt;
            font-weight: 500;
            color: #64748b;
            border-bottom: 0.5px solid #e2e8f0;
            padding-bottom: 4px;
            margin-bottom: 8px;
        }

        .page-footer-bar {
            display: flex;
            justify-content: space-between;
            font-size: 7.5pt;
            color: #64748b;
            border-top: 0.5px solid #e2e8f0;
            padding-top: 4px;
            margin-top: 8px;
        }

        .cover-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 250mm;
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

        .report-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 11pt;
            margin-top: 10px;
        }

        .report-table th {
            background-color: #f1f5f9;
            color: #0f172a;
            font-weight: 700;
            text-transform: uppercase;
            font-size: 11.5pt;
            padding: 5px 4px;
            border: 1px solid #94a3b8;
            text-align: center;
        }

        .report-table td {
            padding: 4px 4px;
            border: 1px solid #cbd5e1;
            font-family: 'Courier New', Courier, monospace;
            font-size: 11.5pt;
            text-align: right;
        }

        .report-table td.label-cell {
            text-align: left;
            font-family: Arial, Helvetica, sans-serif;
            font-size: 11.5pt;
            font-weight: 500;
        }

        .index-table th {
            font-size: 12pt !important;
            padding: 9px 10px !important;
        }

        .index-table td {
            font-size: 12pt !important;
            padding: 9px 10px !important;
            font-family: 'Inter', sans-serif !important;
            text-align: left !important;
        }

        .index-table td.center-align {
            text-align: center !important;
        }

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

        .trend-table { font-size: 6pt !important; }
        .trend-table th { font-size: 5pt !important; padding: 3px 1.5px; }
        .trend-table td { font-size: 5.5pt !important; padding: 2.5px 1.5px; }

        /* Pages 7-13 month-wise yearly trend */
        .trend-yearly-table { table-layout: fixed; width: 100%; border-collapse: collapse; }
        .trend-yearly-table th {
            font-size: 11.5pt; padding: 3px 2px; line-height: 1.15;
            background: #1e3a5f; color: #fff; text-align: center; white-space: nowrap; font-weight: 700;
        }
        .trend-yearly-table th.qtr-hdr { background: #2d4f7f; }
        .trend-yearly-table th.tot-hdr { background: #1a3050; }
        .trend-yearly-table td {
            font-size: 11.5pt; padding: 2px 2px; line-height: 1.2;
            text-align: right; border: 0.3pt solid #cbd5e1;
        }
        .trend-yearly-table td.plant-cell {
            font-size: 11.5pt; font-weight: 700; text-align: center;
            vertical-align: middle; background: #e8edf3; color: #1e3a5f;
        }
        .trend-yearly-table td.plant-cell.agg-sail  { background: #bbf7d0; }
        .trend-yearly-table td.plant-cell.agg-5p    { background: #fef08a; }
        .trend-yearly-table td.year-cell {
            font-size: 11.5pt; text-align: left; padding-left: 3px; white-space: nowrap;
        }
        .trend-yearly-table tr.plan-row   { background: #dbeafe; font-weight: 700; }
        .trend-yearly-table tr.sail-row   { background: #dcfce7; font-weight: 700; }
        .trend-yearly-table tr.fp-row     { background: #fef9c3; font-weight: 700; }
        .trend-yearly-table tr.plant-first { border-top: 1.5pt solid #64748b; }
        .trend-yearly-table td.qtr-cell   { background: #f0f5ff; font-weight: 600; }
        .trend-yearly-table td.total-cell { background: #e8f0fb; font-weight: 700; }

        /* Continuous trend section (pages 7-13 grouped into one PDF flow) */
        .trend-section-page {
            page-break-before: always;
            break-before: page;
            padding: 5mm 0 3mm 0;
        }
        .trend-item-block { margin-bottom: 12pt; }
        .trend-item-separator {
            border: none;
            border-top: 1.5pt solid #0f172a;
            margin: 10pt 0 6pt 0;
        }

        /* Page 4 — tight layout to fit 15 cols on A4 portrait */
        .page4-table { table-layout: fixed; width: 100%; }
        .page4-table th { font-size: 5.5pt; padding: 2px 2px; line-height: 1.15; }
        .page4-table td { font-size: 6pt;   padding: 1px 2px; line-height: 1.15; }
        .page4-table col.c-items    { width: 13%; }
        .page4-table col.c-plant    { width:  5%; }
        .page4-table col.c-ann      { width:  7%; }
        .page4-table col.c-num      { width:  6%; }
        .page4-table col.c-num-sm   { width:5.5%; }
    </style>
</head>
<body>
    {% set total_pages = total_report_pages %}
    {% for page in pages %}
    {% if page.type == 'trend_section' %}
    <div class="trend-section-page">
        <div class="page-header-bar">
            Steel Authority of India Limited - Operations Monthly Informatics
        </div>
        {% for item in page['items'] %}
        {% if not loop.first %}<hr class="trend-item-separator">{% endif %}
        <div class="trend-item-block">
            <div style="display:flex;justify-content:space-between;align-items:flex-end;
                        border-bottom:2px solid #0f172a;padding-bottom:4px;margin-bottom:5px;">
                <h2 style="font-size:9pt;font-weight:800;color:#060177;margin:0;text-transform:uppercase;">
                    MONTH-WISE PRODUCTION TREND : {{ item.item_display }}
                </h2>
                <span style="font-size:7.5pt;font-weight:600;color:#475569;">Unit: {{ item.unit }}</span>
            </div>
            <table class="trend-yearly-table">
                <colgroup>
                    <col style="width:4.5%"/>
                    <col style="width:10%"/>
                    <col style="width:4.5%"/><col style="width:4.5%"/><col style="width:4.5%"/>
                    <col style="width:5%"/>
                    <col style="width:4.5%"/><col style="width:4.5%"/><col style="width:4.5%"/>
                    <col style="width:5%"/>
                    <col style="width:4.5%"/><col style="width:4.5%"/><col style="width:4.5%"/>
                    <col style="width:5%"/>
                    <col style="width:4.5%"/><col style="width:4.5%"/><col style="width:4.5%"/>
                    <col style="width:5%"/>
                    <col style="width:5.5%"/>
                </colgroup>
                <thead>
                    <tr>
                        <th>Plant</th><th>Year</th>
                        <th>Apr</th><th>May</th><th>Jun</th><th class="qtr-hdr">Q1</th>
                        <th>Jul</th><th>Aug</th><th>Sep</th><th class="qtr-hdr">Q2</th>
                        <th>Oct</th><th>Nov</th><th>Dec</th><th class="qtr-hdr">Q3</th>
                        <th>Jan</th><th>Feb</th><th>Mar</th><th class="qtr-hdr">Q4</th>
                        <th class="tot-hdr">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in item.rows %}
                    {% set v = row['values'] %}
                    {% set plant = row['plant'] %}
                    {% set row_cls %}{{ 'plan-row' if row['is_plan'] else '' }}{{ ' sail-row' if plant == 'SAIL' else '' }}{{ ' fp-row' if plant == '5 Plants' else '' }}{{ ' plant-first' if row['is_first_in_plant'] else '' }}{% endset %}
                    <tr class="{{ row_cls }}">
                        {% if row['is_first_in_plant'] %}
                        {% set pcls %}plant-cell{{ ' agg-sail' if plant == 'SAIL' else '' }}{{ ' agg-5p' if plant == '5 Plants' else '' }}{% endset %}
                        <td class="{{ pcls }}" rowspan="{{ row['plant_row_count'] }}">{{ plant }}</td>
                        {% endif %}
                        <td class="year-cell" style="{{ 'font-weight:700;' if row['is_plan'] else '' }}">{{ row['year_label'] }}</td>
                        <td>{{ v[0] }}</td><td>{{ v[1] }}</td><td>{{ v[2] }}</td>
                        <td class="qtr-cell">{{ v[3] }}</td>
                        <td>{{ v[4] }}</td><td>{{ v[5] }}</td><td>{{ v[6] }}</td>
                        <td class="qtr-cell">{{ v[7] }}</td>
                        <td>{{ v[8] }}</td><td>{{ v[9] }}</td><td>{{ v[10] }}</td>
                        <td class="qtr-cell">{{ v[11] }}</td>
                        <td>{{ v[12] }}</td><td>{{ v[13] }}</td><td>{{ v[14] }}</td>
                        <td class="qtr-cell">{{ v[15] }}</td>
                        <td class="total-cell">{{ v[16] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endfor %}
        <div class="page-footer-bar">
            <span>Prepared by: MIS Group</span>
            <span>Pages {{ page.page_range }} of {{ total_pages }}</span>
        </div>
    </div>
    {% else %}
    <div class="page">

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

        {% else %}
        <div class="page-header-bar">
            Steel Authority of India Limited - Operations Monthly Informatics
        </div>

        {% if page.type == 'index' %}
            <div class="report-title-section"><h2>{{ page.title }}</h2></div>
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
                        <td style="font-family: inherit; font-weight: {% if row.sno %}600{% else %}400{% endif %};">{{ row.title }}</td>
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
            <h4 style="font-size: 8pt; font-weight: bold; margin: 10px 0 4px 0; text-transform: uppercase;">
                Production Performance Summary (Unit: '000 T)
            </h4>
            <table class="report-table">
                <thead>
                    <tr>
                        <th rowspan="2">Item</th>
                        <th colspan="3">{{ m_name }} {{ y_str }}</th>
                        <th colspan="2">{{ short_m }}'{{ short_prev_y }}</th>
                        <th colspan="3">April - {{ m_name }} {{ y_str }}</th>
                        <th colspan="2">April-{{ short_m }}'{{ short_prev_y }}</th>
                    </tr>
                    <tr>
                        <th>APP</th><th>Actual</th><th>% Ful.</th>
                        <th>Act.</th><th>% Gr.</th>
                        <th>APP</th><th>Actual</th><th>% Ful.</th>
                        <th>Act.</th><th>% Gr.</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in page.production_table %}
                    <tr>
                        <td class="label-cell">{{ row.item }}</td>
                        {% for val in row['values'] %}<td>{{ val }}</td>{% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% if page.highlights %}
            <div class="highlights-box">
                <h4>Key Production Highlights</h4>
                <ul>{% for h in page.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
            </div>
            {% endif %}
            <h4 style="font-size: 8pt; font-weight: bold; margin: 10px 0 4px 0; text-transform: uppercase;">
                Major Techno-Economic Parameters
            </h4>
            <table class="report-table">
                <thead>
                    <tr>
                        <th>Parameter</th><th>Unit</th>
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
                        {% for val in row['values'] %}<td>{{ val }}</td>{% endfor %}
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
                    <tr>{% for h in page.headers %}<th>{{ h }}</th>{% endfor %}</tr>
                </thead>
                <tbody>
                    {% for row in page.rows %}
                    <tr>
                        <td class="label-cell" style="font-weight: 600;">{{ row.label }}</td>
                        {% for val in row['values'] %}<td>{{ val }}</td>{% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

        {% elif page.type == 'trend_yearly' %}
            <div style="display:flex;justify-content:space-between;align-items:flex-end;
                        border-bottom:2px solid #0f172a;padding-bottom:4px;margin-bottom:5px;">
                <h2 style="font-size:9pt;font-weight:800;color:#060177;margin:0;text-transform:uppercase;">
                    MONTH-WISE PRODUCTION TREND : {{ page.item_display }}
                </h2>
                <span style="font-size:7.5pt;font-weight:600;color:#475569;">Unit: {{ page.unit }}</span>
            </div>
            <table class="trend-yearly-table">
                <colgroup>
                    <col style="width:4.5%"/>
                    <col style="width:10%"/>
                    <col style="width:4.5%"/><col style="width:4.5%"/><col style="width:4.5%"/>
                    <col style="width:5%"/>
                    <col style="width:4.5%"/><col style="width:4.5%"/><col style="width:4.5%"/>
                    <col style="width:5%"/>
                    <col style="width:4.5%"/><col style="width:4.5%"/><col style="width:4.5%"/>
                    <col style="width:5%"/>
                    <col style="width:4.5%"/><col style="width:4.5%"/><col style="width:4.5%"/>
                    <col style="width:5%"/>
                    <col style="width:5.5%"/>
                </colgroup>
                <thead>
                    <tr>
                        <th>Plant</th><th>Year</th>
                        <th>Apr</th><th>May</th><th>Jun</th><th class="qtr-hdr">Q1</th>
                        <th>Jul</th><th>Aug</th><th>Sep</th><th class="qtr-hdr">Q2</th>
                        <th>Oct</th><th>Nov</th><th>Dec</th><th class="qtr-hdr">Q3</th>
                        <th>Jan</th><th>Feb</th><th>Mar</th><th class="qtr-hdr">Q4</th>
                        <th class="tot-hdr">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in page.rows %}
                    {% set v = row['values'] %}
                    {% set plant = row['plant'] %}
                    {% set row_cls %}{{ 'plan-row' if row['is_plan'] else '' }}{{ ' sail-row' if plant == 'SAIL' else '' }}{{ ' fp-row' if plant == '5 Plants' else '' }}{{ ' plant-first' if row['is_first_in_plant'] else '' }}{% endset %}
                    <tr class="{{ row_cls }}">
                        {% if row['is_first_in_plant'] %}
                        {% set pcls %}plant-cell{{ ' agg-sail' if plant == 'SAIL' else '' }}{{ ' agg-5p' if plant == '5 Plants' else '' }}{% endset %}
                        <td class="{{ pcls }}" rowspan="{{ row['plant_row_count'] }}">{{ plant }}</td>
                        {% endif %}
                        <td class="year-cell" style="{{ 'font-weight:700;' if row['is_plan'] else '' }}">{{ row['year_label'] }}</td>
                        <td>{{ v[0] }}</td><td>{{ v[1] }}</td><td>{{ v[2] }}</td>
                        <td class="qtr-cell">{{ v[3] }}</td>
                        <td>{{ v[4] }}</td><td>{{ v[5] }}</td><td>{{ v[6] }}</td>
                        <td class="qtr-cell">{{ v[7] }}</td>
                        <td>{{ v[8] }}</td><td>{{ v[9] }}</td><td>{{ v[10] }}</td>
                        <td class="qtr-cell">{{ v[11] }}</td>
                        <td>{{ v[12] }}</td><td>{{ v[13] }}</td><td>{{ v[14] }}</td>
                        <td class="qtr-cell">{{ v[15] }}</td>
                        <td class="total-cell">{{ v[16] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

        {% elif page.type == 'page4_table' %}
            <div style="display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 1.5px solid #0f172a; padding-bottom: 3px; margin-bottom: 4px;">
                <h2 style="font-size: 9.5pt; font-weight: 800; color: #060177; margin: 0; text-transform: uppercase;">
                    SAIL: Production Performance during {{ m_name }}'{{ short_y }} and Apr-{{ short_m }}'{{ short_y }}
                </h2>
                <h2 style="font-size: 9.5pt; font-weight: 800; color: #0f172a; margin: 0; text-transform: uppercase;">
                    w.r.t APP
                </h2>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 6.5pt; font-weight: 600; color: #475569; margin-bottom: 3px;">
                <span>Tentative</span><span>Unit: '000 T</span>
            </div>
            <table class="report-table page4-table">
                <colgroup>
                    <col class="c-items" />
                    <col class="c-plant" />
                    <col class="c-ann" />
                    <col class="c-num" /><col class="c-num" /><col class="c-num-sm" /><col class="c-num-sm" />
                    <col class="c-num" /><col class="c-num-sm" />
                    <col class="c-num" /><col class="c-num" /><col class="c-num-sm" /><col class="c-num-sm" />
                    <col class="c-num" /><col class="c-num-sm" />
                </colgroup>
                <thead>
                    <tr>
                        <th rowspan="2" style="vertical-align: middle; text-align: left; padding-left: 3px;">Items</th>
                        <th rowspan="2" style="vertical-align: middle;">Plant</th>
                        <th rowspan="2" style="vertical-align: middle;">APP<br/>{{ target_header.split()[1] }}</th>
                        <th colspan="4">{{ short_m }}'{{ short_y }}</th>
                        <th rowspan="2" style="vertical-align: middle;">{{ short_m }}'{{ short_prev_y }}<br/>Actual</th>
                        <th rowspan="2" style="vertical-align: middle;">%Gr.<br/>{{ short_m }}'{{ short_prev_y }}</th>
                        <th colspan="4">Apr-{{ short_m }}'{{ short_y }}</th>
                        <th rowspan="2" style="vertical-align: middle;">Apr-{{ short_m }}'{{ short_prev_y }}<br/>Actual</th>
                        <th rowspan="2" style="vertical-align: middle;">%Gr.<br/>Apr-{{ short_m }}'{{ short_prev_y }}</th>
                    </tr>
                    <tr>
                        <th>APP</th><th>Actual</th><th>Var</th><th>%Ful.</th>
                        <th>APP</th><th>Actual</th><th>Var</th><th>%Ful.</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in page.rows %}
                    <tr>
                        {% if row.is_first_in_group %}
                        <td class="label-cell" rowspan="{{ row.group_size }}"
                            style="font-weight: 700; font-size: 5.5pt; vertical-align: middle;
                                   background-color: #f8fafc; padding: 1px 2px 1px 3px;
                                   overflow: hidden; font-family: Arial, Helvetica, sans-serif;">
                            {{ row.item }}
                        </td>
                        {% endif %}
                        <td class="label-cell"
                            style="font-weight: 600; font-size: 5.5pt; text-align: center;
                                   background-color: #f8fafc; padding: 1px 2px;
                                   font-family: Arial, Helvetica, sans-serif;">
                            {{ row.plant }}
                        </td>
                        {% for val in row['values'] %}<td>{{ val }}</td>{% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

        {% elif page.type == 'performance_summary_table' %}
            <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:2px;">
                <h2 style="font-size:11.5pt;font-weight:850;color:#060177;margin:0;text-transform:uppercase;">
                    PLANT-WISE PRODUCTION PERFORMANCE :{{ short_m }}'{{ short_y }} and Apr-{{ short_m }}'{{ short_y }}
                </h2>
                <span style="font-size:11.5pt;font-weight:600;color:#475569;">Unit:000 T</span>
            </div>
            <table class="report-table" style="table-layout:fixed;width:100%;font-size:6pt;">
                <colgroup>
                    <col style="width:4%"/>
                    <col style="width:20%"/>
                    <col style="width:8%"/>
                    <col style="width:5.5%"/>
                    <col style="width:5.5%"/>
                    <col style="width:5%"/>
                    <col style="width:6%"/>
                    <col style="width:6%"/>
                    <col style="width:6%"/>
                    <col style="width:6%"/>
                    <col style="width:5%"/>
                    <col style="width:6%"/>
                    <col style="width:6%"/>
                </colgroup>
                <thead>
                    <tr>
                        <th rowspan="2" style="padding:2px 2px;"></th>
                        <th rowspan="2" style="padding:2px 2px;text-align:left;"></th>
                        <th rowspan="2" style="padding:2px 2px;">{{ fy_str }}<br/>Plan</th>
                        <th colspan="3" style="padding:2px 2px;">{{ short_m }}'{{ short_y }}</th>
                        <th rowspan="2" style="padding:2px 2px;">{{ short_m }}'{{ prev_y }}<br/>Act</th>
                        <th rowspan="2" style="padding:2px 2px;">%Gr.<br/>{{ short_m }}'{{ prev_y }}</th>
                        <th colspan="3" style="padding:2px 2px;">Apr-{{ short_m }}'{{ short_y }}</th>
                        <th rowspan="2" style="padding:2px 2px;">Apr-{{ short_m }}'{{ prev_y }}<br/>Act</th>
                        <th rowspan="2" style="padding:2px 2px;">%Gr.<br/>Apr-{{ short_m }}'{{ prev_y }}</th>
                    </tr>
                    <tr>
                        <th style="padding:2px 2px;">Plan</th>
                        <th style="padding:2px 2px;">Actual</th>
                        <th style="padding:2px 2px;">%Ful</th>
                        <th style="padding:2px 2px;">Plan</th>
                        <th style="padding:2px 2px;">Actual</th>
                        <th style="padding:2px 2px;">%Ful</th>
                    </tr>
                </thead>
                <tbody>
                    {% set ns = namespace(cur_plant='', plant_rows={}) %}
                    {% for row in page.rows %}
                        {% if row.plant != ns.cur_plant %}
                            {% set ns.cur_plant = row.plant %}
                            {% set plant_size = page.rows | selectattr('plant','equalto',row.plant) | list | length %}
                            <tr style="{{ 'font-weight:700;background:#f0f4f8;' if row.bold else '' }}">
                                <td rowspan="{{ plant_size }}" style="font-size:11.5pt;font-weight:800;text-align:center;vertical-align:middle;padding:1px 2px;">{{ row.plant }}</td>
                                <td style="text-align:left;padding:1px 3px;font-weight:{{ '700' if row.bold else '400' }};">{{ row.label }}</td>
                                {% for val in row['values'] %}<td style="text-align:right;padding:1px 2px;">{{ val }}</td>{% endfor %}
                            </tr>
                        {% else %}
                            <tr style="{{ 'font-weight:700;background:#f0f4f8;' if row.bold else '' }}">
                                <td style="text-align:left;padding:1px 3px;font-weight:{{ '700' if row.bold else '400' }};">{{ row.label }}</td>
                                {% for val in row['values'] %}<td style="text-align:right;padding:1px 2px;">{{ val }}</td>{% endfor %}
                            </tr>
                        {% endif %}
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
                    <tr>{% for h in page.headers %}<th>{{ h }}</th>{% endfor %}</tr>
                </thead>
                <tbody>
                    {% for row in page.rows %}
                    <tr>
                        <td class="label-cell">{{ row.label }}</td>
                        {% for val in row['values'] %}<td>{{ val }}</td>{% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% endif %}

        <div class="page-footer-bar">
            <span>Prepared by: MIS Group</span>
            <span>Page {{ page.page }} of {{ total_pages }}</span>
        </div>

        {% endif %}{# end non-cover #}
    </div>
    {% endif %}{# end else (non-trend_section) #}
    {% endfor %}
</body>
</html>
"""

_PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL', 'ASP', 'SSP', 'VISL', '5 Plants']

_MONTHS_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


def _resolve_month_vars(month: str) -> dict:
    try:
        year = int(month[:4])
        m_num = int(month[5:7])
        m_name = _MONTH_NAMES[m_num]
        short_m = m_name[:3]
        y_str = str(year)
        short_y = y_str[2:]
        prev_y_str = str(year - 1)
        short_prev_y = prev_y_str[2:]
        # FY: Jan-Mar belong to FY of previous calendar year
        target_fy_start = year if m_num >= 4 else year - 1
        target_fy_end = (target_fy_start + 1) % 100
        target_header = f"Target {target_fy_start}-{target_fy_end:02d}"
        fy_str = f"{target_fy_start}-{target_fy_end:02d}"
    except Exception:
        m_name, y_str = "November", "2025"
        short_m, short_y, prev_y_str, short_prev_y = "Nov", "25", "2024", "24"
        target_fy_start, target_fy_end = 2025, 26
        target_header = "Target 2025-26"
        fy_str = "2025-26"
    return dict(
        m_name=m_name, y_str=y_str, short_m=short_m,
        short_y=short_y, prev_y_str=prev_y_str, short_prev_y=short_prev_y,
        prev_y=short_prev_y,
        target_header=target_header,
        fy_str=fy_str,
    )


def _split_label(label: str):
    parts = label.split()
    if len(parts) > 1 and parts[-1] in _PLANTS:
        return " ".join(parts[:-1]), parts[-1]
    if len(parts) > 2 and " ".join(parts[-2:]) in _PLANTS:
        return " ".join(parts[:-2]), " ".join(parts[-2:])
    if label in _PLANTS:
        return "", label
    return label, ""


def _group_page4_rows(rows: list) -> list:
    grouped = []
    i = 0
    while i < len(rows):
        item, plant = _split_label(rows[i].get("label", "").strip())
        count = 1
        while i + count < len(rows):
            next_item, _ = _split_label(rows[i + count].get("label", "").strip())
            if next_item == item and item:
                count += 1
            else:
                break
        for c in range(count):
            row_data = dict(rows[i + c])
            _, r_plant = _split_label(rows[i + c].get("label", "").strip())
            row_data.update(
                is_first_in_group=(c == 0),
                group_size=count,
                item=item,
                plant=r_plant,
            )
            grouped.append(row_data)
        i += count
    return grouped


def _render_pdf_sync(html: str) -> bytes:
    """Run Playwright synchronously (called from a thread to avoid event-loop conflicts)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="domcontentloaded")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={
                "top": "15mm",
                "right": "15mm",
                "bottom": "15mm",
                "left": "15mm",
            },
        )
        browser.close()
    return pdf_bytes


async def build_pdf_response(request: PDFRequest) -> StreamingResponse:
    import asyncio
    import traceback as tb
    from jinja2 import Template

    try:
        vars = _resolve_month_vars(request.month)

        total_report_pages = len(request.pages)

        flat_pages = []
        for p_data in request.pages:
            p = p_data.dict()
            if p.get("page", 0) > 36:
                continue
            if p.get("type") == "page4_table":
                p["rows"] = _group_page4_rows(p.get("rows", []))
            flat_pages.append(p)

        # Group consecutive trend pages (trend_yearly / trend_combined) into one continuous PDF section
        pages_to_render = []
        i = 0
        while i < len(flat_pages):
            p = flat_pages[i]
            if p.get("type") in ("trend_yearly", "trend_combined"):
                start_i = i
                trend_items = []
                while i < len(flat_pages) and flat_pages[i].get("type") in ("trend_yearly", "trend_combined"):
                    tp = flat_pages[i]
                    if tp.get("type") == "trend_combined":
                        # Expand sub-items so the template renders each as a separate table
                        for sub in tp.get("items", []):
                            trend_items.append(sub)
                    else:
                        trend_items.append(tp)
                    i += 1
                first_pg = flat_pages[start_i].get("page", "?")
                last_pg  = flat_pages[i - 1].get("page", "?")
                pages_to_render.append({
                    "type": "trend_section",
                    "items": trend_items,
                    "page_range": f"{first_pg}-{last_pg}",
                })
            else:
                pages_to_render.append(p)
                i += 1

        rendered_html = Template(HTML_TEMPLATE).render(
            month=request.month,
            pages=pages_to_render,
            total_report_pages=total_report_pages,
            **vars,
        )

        # Run sync Playwright in a thread so it doesn't fight the asyncio event loop
        loop = asyncio.get_event_loop()
        pdf_bytes = await loop.run_in_executor(None, _render_pdf_sync, rendered_html)

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=SAIL_MIS_Report_"
                    f"{request.month.replace(' ', '_')}.pdf"
                ),
                "X-Content-Type-Options": "nosniff",
            },
        )
    except Exception as e:
        detail = f"PDF Compilation failed: {type(e).__name__}: {e}\n{tb.format_exc()}"
        print(detail)
        raise HTTPException(status_code=500, detail=detail)
