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
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700;900&family=Roboto+Mono:wght@400;500;700&display=swap');

        * { box-sizing: border-box; }

        body {
            font-family: 'Roboto', Arial, Helvetica, sans-serif;
            color: #0f172a;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }

        @page {
            size: A4 portrait;
            margin: 18mm 15mm 18mm 15mm;
        }

        /* Page 4: tighter margins to maximise usable area while keeping footer clear */
        @page page4-layout {
            size: A4 portrait;
            margin-top: 12mm;
            margin-right: 10mm;
            margin-bottom: 12mm;
            margin-left: 10mm;
        }

        .page4-page {
            page: page4-layout;
            padding-top: 0;
            padding-bottom: 0;
        }

        .page {
            page-break-after: always;
            break-after: page;
            page-break-inside: avoid;
            padding: 3mm 0;
        }

        .page:last-child {
            page-break-after: auto;
        }

        /* ══════════════════════════════════════════════════════
           COMMON STYLES
           ══════════════════════════════════════════════════════ */

        .report-title-section {
            text-align: center;
            margin-bottom: 15px;
        }

        .report-title-section h2 {
            font-size: 13pt;
            font-weight: 700;
            color: #0f172a;
            text-transform: uppercase;
            margin: 0;
        }

        .report-title-section h3 {
            font-size: 12pt;
            font-weight: 600;
            color: #475569;
            margin: 4px 0 0 0;
        }

        .report-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12pt;
            margin-top: 10px;
        }

        .report-table th {
            background-color: #f1f5f9;
            color: #0f172a;
            font-weight: 700;
            text-transform: uppercase;
            font-size: 11pt;
            padding: 5px 4px;
            border: 1px solid #94a3b8;
            text-align: center;
        }

        .report-table td {
            padding: 4px 4px;
            border: 1px solid #cbd5e1;
            font-family: 'Roboto', Arial, Helvetica, sans-serif;
            font-size: 12pt;
            text-align: right;
        }

        .report-table td.label-cell {
            text-align: left;
            font-family: 'Roboto', Arial, Helvetica, sans-serif;
            font-size: 11pt;
            font-weight: 500;
        }

        .highlights-box {
            background-color: #f8fafc;
            border-left: 3px solid #0284c7;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            font-size: 12pt;
        }

        .highlights-box h4 {
            font-weight: 700;
            text-transform: uppercase;
            color: #0f172a;
            margin: 0 0 5px 0;
            font-size: 13pt;
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

        /* ══════════════════════════════════════════════════════
           PAGE-SPECIFIC STYLES  (pages 1 – 14)
           Naming: .pageN-{element}  |  common stays in .report-table
           ══════════════════════════════════════════════════════ */

        /* ─── Page 1 – Cover ────────────────────────────────── */
        .page1-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 250mm;
            text-align: center;
            padding: 40mm 20mm;
        }

        .page1-accent {
            width: 80px;
            height: 6px;
            background-color: #0284c7;
            margin-bottom: 30px;
            border-radius: 3px;
        }

        .page1-title {
            font-size: 30pt;
            font-weight: 900;
            color: #0f172a;
            line-height: 1.1;
            margin-bottom: 10px;
            text-transform: uppercase;
        }

        .page1-subtitle {
            font-size: 14pt;
            font-weight: 500;
            color: #475569;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 60px;
        }

        .page1-meta {
            margin-top: auto;
            border-top: 1px solid #e2e8f0;
            padding-top: 30px;
            width: 100%;
            display: flex;
            justify-content: space-between;
            font-size: 9pt;
            color: #64748b;
        }

        /* ─── Page 2 – Index ────────────────────────────────── */
        .page2-heading {
            font-size: 20pt;
            font-weight: bold;
            color: #333;
            padding-bottom: 8px;
            border-bottom: 2px solid #000;
            margin-bottom: 14px;
            text-align: center;
        }

        .page2-table {
            line-height: 1.4;
            background-color: white;
        }

        .page2-table th {
            background-color: #f0f0f0;
            border: 1px solid #000;
            color: #333;
            text-transform: none;
            font-size: 10.5pt;
            padding: 8px 10px;
            font-weight: bold;
            text-align: center;
            vertical-align: middle;
        }

        .page2-table td {
            border: 1px solid #000;
            font-size: 10.5pt;
            padding: 8px 10px;
            font-family: 'Roboto', Arial, Helvetica, sans-serif;
            text-align: left;
            vertical-align: top;
            color: #333;
            font-weight: normal;
        }

        .page2-table td.center {
            text-align: center;
        }

        .page2-table td.sno {
            font-weight: bold;
            text-align: center;
        }

        /* ─── Page 3 – SAIL Performance Summary ─────────────── */
        .page3-section-heading {
            font-size: 13pt;
            font-weight: 700;
            margin: 10px 0 4px 0;
            text-transform: uppercase;
            color: #0f172a;
        }

        /* ─── Page 4 – Production Performance vs APP ─────────── */
        .page4-heading {
            font-size: 10pt;
            font-weight: 700;
            color: #060177;
            margin: 0;
            text-transform: uppercase;
        }

        .page4-meta {
            font-size: 8.5pt;
            font-weight: 500;
            color: #475569;
            margin-bottom: 2px;
        }

        .page4-table { table-layout: fixed; width: 100%; border: 2.5px solid #1e293b; }
        .page4-table th { font-size: 8pt; padding: 1.5px 2px; line-height: 1.0; }
        .page4-table td { font-size: 8pt; padding: 1.5px 2px; line-height: 1.0; }
        .page4-table col.c-items    { width: 13%; }
        .page4-table col.c-plant    { width:  5%; }
        .page4-table col.c-ann      { width:  7%; }
        .page4-table col.c-num      { width:  6%; }
        .page4-table col.c-num-sm   { width:5.5%; }

        /* item-group block separator */
        .page4-table tr.group-first td { border-top: 2px solid #374151; }

        /* Annual APP column */
        .page4-table td.col-ann,
        .page4-table thead th.col-ann {
            background-color: #dbeafe !important;
            border-left:  2px solid #1d4ed8;
            border-right: 2px solid #1d4ed8;
        }

        /* Month Actual column */
        .page4-table td.col-m-act,
        .page4-table thead th.col-m-act { background-color: #d1fae5 !important; }

        /* Cumulative section left wall */
        .page4-table td.col-ytd-app,
        .page4-table thead th.col-ytd-app { border-left: 2.5px solid #1e293b; }

        /* Cumulative Actual column */
        .page4-table td.col-ytd-act,
        .page4-table thead th.col-ytd-act { background-color: #d1fae5 !important; }

        /* SAIL aggregate rows */
        .page4-table tr.sail-row td {
            font-weight: 700;
            background-color: #eff6ff !important;
        }

        /* ─── Pages 5–6 – Plant-Wise Performance ─────────────── */
        .page5-6-heading {
            font-size: 12pt;
            font-weight: 700;
            color: #060177;
            margin: 0;
            text-transform: uppercase;
        }

        .page5-6-unit {
            font-size: 10pt;
            font-weight: 500;
            color: #475569;
        }

        .page5-6-table { table-layout: fixed; width: 100%; border: 2.5px solid #1e293b; }
        .page5-6-table th { font-size: 11pt; padding: 4px 4px; line-height: 1; vertical-align: middle; }
        .page5-6-table td { font-size: 11pt; padding: 4px 4px; line-height: 1; }

        .page5-6-plant-cell {
            font-size: 11pt;
            font-weight: 700;
            text-align: center;
            vertical-align: middle;
        }

        /* plant group separator */
        .page5-6-table tr.plant-first td { border-top: 2px solid #374151; }

        /* Annual Plan column */
        .page5-6-table td.col-ann,
        .page5-6-table thead th.col-ann {
            background-color: #dbeafe !important;
            border-left:  2px solid #1d4ed8;
            border-right: 2px solid #1d4ed8;
        }

        /* Month Actual column */
        .page5-6-table td.col-m-act,
        .page5-6-table thead th.col-m-act { background-color: #d1fae5 !important; }

        /* Cumulative section left wall */
        .page5-6-table td.col-ytd-plan,
        .page5-6-table thead th.col-ytd-plan { border-left: 2.5px solid #1e293b; }

        /* Cumulative Actual column */
        .page5-6-table td.col-ytd-act,
        .page5-6-table thead th.col-ytd-act { background-color: #d1fae5 !important; }

        /* SAIL plant rows */
        .page5-6-table tr.sail-row td {
            font-weight: 700;
            background-color: #eff6ff !important;
        }

        /* ─── Pages 7–13 – Month-wise Production Trend ──────── */
        .page7-13-heading {
            font-size: 12pt;
            font-weight: 700;
            color: #060177;
            margin: 0;
            text-transform: uppercase;
        }

        .page7-13-unit {
            font-size: 9pt;
            font-weight: 500;
            color: #475569;
            text-transform: vertical-rl;
        }

        .page7-13-trend-table { font-size: 6pt !important; }
        .page7-13-trend-table th { font-size: 5pt !important; padding: 3px 1.5px; }
        .page7-13-trend-table td { font-size: 5.5pt !important; padding: 2.5px 1.5px; }

        .page7-13-yearly-table { table-layout: fixed; width: 100%; border-collapse: collapse; }
        .page7-13-yearly-table th {
            font-size: 10pt; padding: 3.5px 3px; line-height: 1;
            background: #1e3a5f; color: #fff; text-align: center; white-space: nowrap; font-weight: 700;
        }
        .page7-13-yearly-table th.qtr-hdr { background: #2d4f7f; }
        .page7-13-yearly-table th.tot-hdr { background: #1a3050; }
        .page7-13-yearly-table td {
            font-size: 10pt; padding: 3.5px 3px; line-height: 1;
            text-align: right; border: 0.3pt solid #cbd5e1;
        }
        .page7-13-yearly-table td.plant-cell {
            font-size: 10pt; font-weight: 700; text-align: center;
            vertical-align: middle; background: #e8edf3; color: #1e3a5f;
        }
        .page7-13-yearly-table td.plant-cell.agg-sail  { background: #bbf7d0; }
        .page7-13-yearly-table td.plant-cell.agg-5p    { background: #fef08a; }
        .page7-13-yearly-table td.year-cell {
            font-size: 10pt; text-align: left; padding-left: 4px; white-space: nowrap;
        }
        .page7-13-yearly-table tr.plan-row   { background: #dbeafe; font-weight: 700; }
        .page7-13-yearly-table tr.sail-row   { background: #dcfce7; font-weight: 700; }
        .page7-13-yearly-table tr.fp-row     { background: #fef9c3; font-weight: 700; }
        .page7-13-yearly-table tr.plant-first { border-top: 1.5pt solid #64748b; }
        .page7-13-yearly-table td.qtr-cell   { background: #f0f5ff; font-weight: 600; }
        .page7-13-yearly-table td.total-cell { background: #e8f0fb; font-weight: 700; }
        .page7-13-yearly-table thead tr.item-heading-row th {
            background: white; border-bottom: 2px solid #0f172a; border-top: none;
            padding: 0 0 4px 0; vertical-align: bottom;
        }
        .page7-13-yearly-table thead tr.item-heading-row th.heading-title {
            font-size: 12pt; font-weight: 700; color: #060177;
            text-transform: uppercase; text-align: left;
        }
        .page7-13-yearly-table thead tr.item-heading-row th.heading-unit {
            font-size: 10pt; font-weight: 500; color: #475569;
            text-transform: none; text-align: right;
        }

        .page7-13-section-page {
            page-break-before: always;
            break-before: page;
            padding: 3mm 0;
        }
        .page7-13-item-block { margin-bottom: 20pt; }
        .page7-13-separator {
            border: none;
            border-top: 1.5pt solid #0f172a;
            margin: 16pt 0 10pt 0;
        }

        /* ─── Page 14 – Production by Process ───────────────── */
        .page14-table { table-layout: fixed; width: 100%; border-collapse: collapse; border: 2px solid #1e293b; margin-bottom: 10pt; }
        .page14-table th { font-size: 8pt; padding: 2px 3px; line-height: 1.1; text-align: center; vertical-align: middle; border: 1px solid #94a3b8; }
        .page14-table td { font-size: 8.5pt; padding: 2px 3px; line-height: 1.1; text-align: right; border: 1px solid #cbd5e1; }
        .page14-table td.plant-col { text-align: left; font-weight: 600; background-color: #f8fafc; }
        .page14-table tr.agg-row td { font-weight: 700; background-color: #fef9c3 !important; }
        .page14-table tr.sail-row td { font-weight: 700; background-color: #dcfce7 !important; }
        .page14-table td.cs-col { background-color: #dbeafe !important; }
        .page14-table td.cc-col { background-color: #d1fae5 !important; }
        .page14-table td.prev-sep { border-left: 2.5px solid #1e293b; }

        /* ── pages 15-17: Category Wise Saleable Steel ──────────────────── */
        .catwise-wrap { margin-bottom: 6pt; }
        .catwise-plant-title { font-weight: 700; font-size: 10pt; text-decoration: underline; margin: 4pt 0 3pt 0; }
        .catwise-table { table-layout: fixed; width: 100%; border-collapse: collapse; border: 2px solid #1e293b; margin-bottom: 6pt; font-size: 7.5pt; }
        .catwise-table col.col-lbl { width: 33%; }
        .catwise-table col.col-num { width: 11.2%; }
        .catwise-table th { background-color: #1e3a5f; color: #fff; padding: 2px 3px; text-align: center; vertical-align: middle; border: 1px solid #334155; font-size: 7pt; line-height: 1.2; font-weight: 600; }
        .catwise-table th.lbl-th { text-align: left; }
        .catwise-table td { padding: 1.5px 4px; border: 1px solid #cbd5e1; line-height: 1.2; }
        .catwise-table td.lbl-td { text-align: left; }
        .catwise-table td.num-td { text-align: right; }
        .catwise-table tr.cw-data td { background-color: #f8fafc; }
        .catwise-table tr.cw-section-data td { background-color: #eff6ff; font-weight: 600; }
        .catwise-table tr.cw-section-hdr td { background-color: #e2e8f0; font-weight: 700; font-size: 7.5pt; }
        .catwise-table tr.cw-subtotal td { background-color: #fef9c3; font-weight: 700; }
        .catwise-table tr.cw-pct td { background-color: #f1f5f9; font-style: italic; font-size: 6.8pt; }
        .catwise-table tr.cw-total td { background-color: #dcfce7; font-weight: 700; }
        .catwise-table tr.cw-separator { height: 3px; }
        .catwise-table tr.cw-separator td { border: none; background: transparent; padding: 0; }

        /* ── page 18: Segment Wise Production ───────────────────────────── */
        .segwise-table { table-layout: fixed; width: 100%; border-collapse: collapse; border: 2px solid #1e293b; font-size: 7.5pt; }
        .segwise-table col.col-lbl { width: 27%; }
        .segwise-table col.col-num { width: 12.2%; }
        .segwise-table th { background-color: #1e3a5f; color: #fff; padding: 2px 3px; text-align: center; vertical-align: middle; border: 1px solid #334155; font-size: 7pt; line-height: 1.2; font-weight: 600; }
        .segwise-table th.lbl-th { text-align: left; }
        .segwise-table td { padding: 1.5px 4px; border: 1px solid #cbd5e1; line-height: 1.2; }
        .segwise-table td.lbl-td { text-align: left; }
        .segwise-table td.num-td { text-align: right; }
        .segwise-table tr.sw-data td { background-color: #f8fafc; }
        .segwise-table tr.sw-seg-hdr td { background-color: #1e3a5f; color: #fff; font-weight: 700; font-size: 8pt; padding: 3px 5px; border: 1px solid #334155; }
        .segwise-table tr.sw-plant-lbl td { background-color: #dbeafe; font-weight: 700; font-size: 7.5pt; }
        .segwise-table tr.sw-seg-total td { background-color: #fef9c3; font-weight: 700; }
        .segwise-table tr.sw-seg-pct td { background-color: #f1f5f9; font-weight: 700; font-style: italic; }
        .segwise-table tr.sw-grand-total td { background-color: #dcfce7; font-weight: 700; font-size: 8pt; }
        .segwise-table tr.sw-separator { height: 3px; }
        .segwise-table tr.sw-separator td { border: none; background: transparent; padding: 0; }
    </style>
</head>
<body>
    {% set total_pages = total_report_pages %}
    {% for page in pages %}
    {% if page.type == 'trend_section' %}
    <div class="page7-13-section-page">
        {% for item in page['items'] %}
        {% if not loop.first %}<hr class="page7-13-separator">{% endif %}
        <div class="page7-13-item-block">
            <table class="page7-13-yearly-table">
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
                    <tr class="item-heading-row">
                        <th colspan="18" class="heading-title">MONTH-WISE PRODUCTION TREND : {{ item.item_display }}</th>
                        <th class="heading-unit">Unit: {{ item.unit }}</th>
                    </tr>
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
    </div>
    {% else %}
    <div class="page{% if page.type == 'page4_table' %} page4-page{% endif %}">

        {% if page.type == 'cover' %}
            <div class="page1-container">
                <div class="page1-accent"></div>
                <h1 class="page1-title">{{ page.title }}</h1>
                <p class="page1-subtitle">O P E R A T I O N S   D I R E C T O R A T E</p>
                <div class="page1-meta">
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

        {% if page.type == 'index' %}
            <h2 class="page2-heading">{{ page.title }}</h2>
            <table class="report-table page2-table" style="width: 100%;">
                <thead>
                    <tr>
                        <th style="width: 8%; text-align: center;">S.No.</th>
                        <th style="width: 77%; text-align: left;">Contents</th>
                        <th style="width: 15%; text-align: center;">Page</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in page.rows %}
                    <tr>
                        <td class="sno" style="font-family: inherit;">{{ row.sno }}</td>
                        <td style="font-family: inherit;">{{ row.title }}</td>
                        <td class="center" style="font-family: inherit;">{{ row.page_range }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

        {% elif page.type == 'summary' %}
            <div class="report-title-section">
                <h2>{{ page.title }}</h2>
                <h3>{{ month }}</h3>
            </div>
            <h4 class="page3-section-heading">
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
            <h4 class="page3-section-heading">
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
            <table class="report-table page7-13-trend-table">
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
            <table class="page7-13-yearly-table">
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
                    <tr class="item-heading-row">
                        <th colspan="18" class="heading-title">MONTH-WISE PRODUCTION TREND : {{ page.item_display }}</th>
                        <th class="heading-unit">Unit: {{ page.unit }}</th>
                    </tr>
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
                <h2 class="page4-heading">
                    SAIL: Production Performance during {{ m_name }}'{{ short_y }} and Apr-{{ short_m }}'{{ short_y }}
                </h2>
                <h2 class="page4-heading" style="color: #0f172a;">
                    w.r.t APP
                </h2>
            </div>
            <div class="page4-meta" style="display: flex; justify-content: space-between;">
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
                        <th rowspan="2" class="col-ann" style="vertical-align: middle;">APP<br/>{{ target_header.split()[1] }}</th>
                        <th colspan="4">{{ short_m }}'{{ short_y }}</th>
                        <th rowspan="2" style="vertical-align: middle;">{{ short_m }}'{{ short_prev_y }}<br/>Actual</th>
                        <th rowspan="2" style="vertical-align: middle;">%Gr.<br/>{{ short_m }}'{{ short_prev_y }}</th>
                        <th colspan="4">Apr-{{ short_m }}'{{ short_y }}</th>
                        <th rowspan="2" style="vertical-align: middle;">Apr-{{ short_m }}'{{ short_prev_y }}<br/>Actual</th>
                        <th rowspan="2" style="vertical-align: middle;">%Gr.<br/>Apr-{{ short_m }}'{{ short_prev_y }}</th>
                    </tr>
                    <tr>
                        <th>APP</th><th class="col-m-act">Actual</th><th>Var</th><th>%Ful.</th>
                        <th class="col-ytd-app">APP</th><th class="col-ytd-act">Actual</th><th>Var</th><th>%Ful.</th>
                    </tr>
                </thead>
                {% set col_cls = ['col-ann','','col-m-act','','','','','col-ytd-app','col-ytd-act','','','',''] %}
                <tbody>
                    {% for row in page.rows %}
                    <tr class="{% if row.is_first_in_group %}group-first {% endif %}{% if row.plant == 'SAIL' %}sail-row{% endif %}">
                        {% if row.is_first_in_group %}
                        <td class="label-cell" rowspan="{{ row.group_size }}"
                            style="font-weight: 700; font-size: 8pt; vertical-align: middle;
                                   background-color: #f8fafc; padding: 1px 2px 1px 4px;
                                   overflow: hidden; font-family: 'Roboto', Arial, Helvetica, sans-serif;">
                            {{ row.item }}
                        </td>
                        {% endif %}
                        <td class="label-cell"
                            style="font-weight: 600; font-size: 8pt; text-align: center;
                                   background-color: #f8fafc; padding: 1px 2px;
                                   font-family: 'Roboto', Arial, Helvetica, sans-serif;
                                   white-space: nowrap; overflow: hidden;">
                            {{ row.plant }}
                        </td>
                        {% for val in row['values'] %}<td{% if col_cls[loop.index0] %} class="{{ col_cls[loop.index0] }}"{% endif %}>{{ val }}</td>{% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

        {% elif page.type == 'concast_performance' %}{# rendered in the block below #}

        {% elif page.type == 'prod_by_process' %}{# rendered in the block below #}

        {% elif page.type == 'catwise_saleable' %}{# rendered in the block below #}

        {% elif page.type == 'segment_wise' %}{# rendered in the block below #}

        {% elif page.type == 'performance_summary_table' %}
            <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:2px;">
                <h2 class="page5-6-heading">
                    PLANT-WISE PRODUCTION PERFORMANCE :{{ short_m }}'{{ short_y }} and Apr-{{ short_m }}'{{ short_y }}
                </h2>
                <span class="page5-6-unit">Unit:000 T</span>
            </div>
            <table class="report-table page5-6-table" style="table-layout:fixed;width:100%;">
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
                        <th rowspan="2" style="padding:3px 3px;"></th>
                        <th rowspan="2" style="padding:3px 3px;text-align:left;"></th>
                        <th rowspan="2" class="col-ann" style="padding:3px 3px;">{{ fy_str }}<br/>Plan</th>
                        <th colspan="3" style="padding:3px 3px;">{{ short_m }}'{{ short_y }}</th>
                        <th rowspan="2" style="padding:3px 3px;">{{ short_m }}'{{ prev_y }}<br/>Act</th>
                        <th rowspan="2" style="padding:3px 3px;">%Gr.<br/>{{ short_m }}'{{ prev_y }}</th>
                        <th colspan="3" style="padding:3px 3px;">Apr-{{ short_m }}'{{ short_y }}</th>
                        <th rowspan="2" style="padding:3px 3px;">Apr-{{ short_m }}'{{ prev_y }}<br/>Act</th>
                        <th rowspan="2" style="padding:3px 3px;">%Gr.<br/>Apr-{{ short_m }}'{{ prev_y }}</th>
                    </tr>
                    <tr>
                        <th style="padding:3px 3px;">Plan</th>
                        <th class="col-m-act" style="padding:3px 3px;">Actual</th>
                        <th style="padding:3px 3px;">%Ful</th>
                        <th class="col-ytd-plan" style="padding:3px 3px;">Plan</th>
                        <th class="col-ytd-act" style="padding:3px 3px;">Actual</th>
                        <th style="padding:3px 3px;">%Ful</th>
                    </tr>
                </thead>
                {% set col_cls = ['col-ann','','col-m-act','','','','col-ytd-plan','col-ytd-act','','',''] %}
                <tbody>
                    {% set ns = namespace(cur_plant='', plant_rows={}) %}
                    {% for row in page.rows %}
                        {% if row.plant != ns.cur_plant %}
                            {% set ns.cur_plant = row.plant %}
                            {% set plant_size = page.rows | selectattr('plant','equalto',row.plant) | list | length %}
                            <tr class="plant-first{% if row.plant == 'SAIL' %} sail-row{% endif %}" style="{{ 'font-weight:700;' if row.bold else '' }}">
                                <td rowspan="{{ plant_size }}" class="page5-6-plant-cell" style="padding:2px 3px;">{{ row.plant }}</td>
                                <td style="text-align:left;padding:2px 3px;font-weight:{{ '700' if row.bold else '400' }};">{{ row.label }}</td>
                                {% for val in row['values'] %}<td{% if col_cls[loop.index0] %} class="{{ col_cls[loop.index0] }}"{% endif %} style="text-align:right;padding:2px 3px;">{{ val }}</td>{% endfor %}
                            </tr>
                        {% else %}
                            <tr class="{% if row.plant == 'SAIL' %}sail-row{% endif %}" style="{{ 'font-weight:700;' if row.bold else '' }}">
                                <td style="text-align:left;padding:2px 3px;font-weight:{{ '700' if row.bold else '400' }};">{{ row.label }}</td>
                                {% for val in row['values'] %}<td{% if col_cls[loop.index0] %} class="{{ col_cls[loop.index0] }}"{% endif %} style="text-align:right;padding:2px 3px;">{{ val }}</td>{% endfor %}
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

        {% if page.type == 'concast_performance' %}
            <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:3px;">
                <h2 style="font-size:13pt;font-weight:700;color:#060177;margin:0;text-transform:uppercase;">
                    CONCAST PRODUCTION PERFORMANCE – {{ short_m }}'{{ short_y }}
                </h2>
                <span style="font-size:8.5pt;color:#475569;font-weight:500;">Unit: Tonnes</span>
            </div>

            {# ── Monthly table ── #}
            <table style="width:100%;border-collapse:collapse;table-layout:fixed;margin-bottom:14pt;">
                <colgroup>
                    <col style="width:12%"/>
                    <col style="width:12%"/>
                    <col style="width:11%"/>
                    <col style="width:11%"/>
                    <col style="width:7%"/>
                    <col style="width:11%"/>
                    <col style="width:11%"/>
                </colgroup>
                <thead>
                    <tr style="background:#1e3a5f;color:#fff;">
                        <th rowspan="2" style="padding:3px 4px;font-size:10.5pt;border:1px solid #94a3b8;vertical-align:middle;">PLANT</th>
                        <th rowspan="2" style="padding:3px 4px;font-size:10.5pt;border:1px solid #94a3b8;vertical-align:middle;">{{ fy_str }}<br/>Plan</th>
                        <th colspan="3" style="padding:3px 4px;font-size:10.5pt;border:1px solid #94a3b8;">{{ short_m }}'{{ short_y }}</th>
                        <th rowspan="2" style="padding:3px 4px;font-size:10.5pt;border:1px solid #94a3b8;vertical-align:middle;">{{ short_m }}'{{ short_prev_y }}<br/>Actual</th>
                        <th rowspan="2" style="padding:3px 4px;font-size:10.5pt;border:1px solid #94a3b8;vertical-align:middle;">% Growth over<br/>{{ short_m }}'{{ short_prev_y }}</th>
                    </tr>
                    <tr style="background:#2d4f7f;color:#fff;">
                        <th style="padding:2px 4px;font-size:10.5pt;border:1px solid #94a3b8;">Plan</th>
                        <th style="padding:2px 4px;font-size:10.5pt;border:1px solid #94a3b8;">Actual</th>
                        <th style="padding:2px 4px;font-size:10.5pt;border:1px solid #94a3b8;">% Ful.</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in page.monthly %}
                    {% set bg = '#dcfce7' if row.plant == 'SAIL' else ('#fef9c3' if row.plant == '5 Plants' else 'white') %}
                    <tr style="background:{{ bg }};{% if row.bold %}font-weight:700;{% endif %}">
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;font-weight:{{ '700' if row.bold else '500' }};">{{ row.plant }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;background:#dbeafe;">{{ row.ann_plan }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;">{{ row.m_plan }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;background:#d1fae5;">{{ row.m_act }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;">{{ row.m_pct }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;">{{ row.cply_act }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;">{{ row.m_growth }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            {# ── YTD table ── #}
            <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
                <colgroup>
                    <col style="width:12%"/>
                    <col style="width:12%"/>
                    <col style="width:11%"/>
                    <col style="width:11%"/>
                    <col style="width:7%"/>
                    <col style="width:11%"/>
                    <col style="width:11%"/>
                </colgroup>
                <thead>
                    <tr style="background:#1e3a5f;color:#fff;">
                        <th rowspan="2" style="padding:3px 4px;font-size:10.5pt;border:1px solid #94a3b8;vertical-align:middle;">PLANT</th>
                        <th rowspan="2" style="padding:3px 4px;font-size:10.5pt;border:1px solid #94a3b8;vertical-align:middle;">{{ fy_str }}<br/>Plan</th>
                        <th colspan="3" style="padding:3px 4px;font-size:10.5pt;border:1px solid #94a3b8;">Apr-{{ short_m }}'{{ short_y }}</th>
                        <th rowspan="2" style="padding:3px 4px;font-size:10.5pt;border:1px solid #94a3b8;vertical-align:middle;">Apr-{{ short_m }}'{{ short_prev_y }}<br/>Actual</th>
                        <th rowspan="2" style="padding:3px 4px;font-size:10.5pt;border:1px solid #94a3b8;vertical-align:middle;">% Growth over<br/>Apr-{{ short_m }}'{{ short_prev_y }}</th>
                    </tr>
                    <tr style="background:#2d4f7f;color:#fff;">
                        <th style="padding:2px 4px;font-size:10.5pt;border:1px solid #94a3b8;">Plan</th>
                        <th style="padding:2px 4px;font-size:10.5pt;border:1px solid #94a3b8;">Actual</th>
                        <th style="padding:2px 4px;font-size:10.5pt;border:1px solid #94a3b8;">% Ful.</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in page.ytd %}
                    {% set bg = '#dcfce7' if row.plant == 'SAIL' else ('#fef9c3' if row.plant == '5 Plants' else 'white') %}
                    <tr style="background:{{ bg }};{% if row.bold %}font-weight:700;{% endif %}">
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;font-weight:{{ '700' if row.bold else '500' }};">{{ row.plant }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;background:#dbeafe;">{{ row.ann_plan }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;">{{ row.ytd_plan }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;background:#d1fae5;">{{ row.ytd_act }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;">{{ row.ytd_pct }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;">{{ row.ytd_cply }}</td>
                        <td style="padding:2px 4px;font-size:10.5pt;border:1px solid #cbd5e1;text-align:right;">{{ row.ytd_growth }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% endif %}{# end concast_performance #}

        {% if page.type == 'prod_by_process' %}
            <div style="display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1.5px solid #0f172a;padding-bottom:3px;margin-bottom:6px;">
                <h2 style="font-size:12pt;font-weight:700;color:#060177;margin:0;text-transform:uppercase;">
                    PRODUCTION BY PROCESS
                </h2>
                <span style="font-size:8pt;color:#475569;font-weight:500;">Unit: Tonnes</span>
            </div>

            {# ── Monthly Table ── #}
            <table class="page14-table">
                <colgroup>
                    <col style="width:9%"/>
                    <col style="width:7%"/><col style="width:6%"/><col style="width:7%"/><col style="width:7%"/><col style="width:7%"/><col style="width:7%"/>
                    <col style="width:7%"/><col style="width:6%"/><col style="width:7%"/><col style="width:7%"/><col style="width:7%"/><col style="width:7%"/>
                </colgroup>
                <thead>
                    <tr style="background:#1e3a5f;color:#fff;">
                        <th rowspan="2">PLANT</th>
                        <th colspan="6">{{ short_m }}'{{ short_y }}</th>
                        <th colspan="6" style="border-left:2.5px solid #5a7fa0;">{{ short_m }}'{{ short_prev_y }}</th>
                    </tr>
                    <tr style="background:#2d4f7f;color:#fff;">
                        <th>BOF</th><th>EAF</th><th class="cc-col">CC</th><th class="cs-col">CS</th><th>BOF<br/>%CS</th><th>CC<br/>%CS</th>
                        <th style="border-left:2.5px solid #5a7fa0;">BOF</th><th>EAF</th><th class="cc-col">CC</th><th class="cs-col">CS</th><th>BOF<br/>%CS</th><th>CC<br/>%CS</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in page.monthly %}
                    {% set pr = page.monthly_prev[loop.index0] %}
                    <tr class="{% if row.plant == 'SAIL' %}sail-row{% elif row.bold %}agg-row{% endif %}">
                        <td class="plant-col">{{ row.plant }}</td>
                        <td>{{ row.bof }}</td><td>{{ row.eaf }}</td>
                        <td class="cc-col">{{ row.cc }}</td><td class="cs-col">{{ row.cs }}</td>
                        <td>{{ row.bof_pct }}</td><td>{{ row.cc_pct }}</td>
                        <td class="prev-sep">{{ pr.bof }}</td><td>{{ pr.eaf }}</td>
                        <td class="cc-col">{{ pr.cc }}</td><td class="cs-col">{{ pr.cs }}</td>
                        <td>{{ pr.bof_pct }}</td><td>{{ pr.cc_pct }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            {# ── YTD Table ── #}
            <table class="page14-table">
                <colgroup>
                    <col style="width:9%"/>
                    <col style="width:7%"/><col style="width:6%"/><col style="width:7%"/><col style="width:7%"/><col style="width:7%"/><col style="width:7%"/>
                    <col style="width:7%"/><col style="width:6%"/><col style="width:7%"/><col style="width:7%"/><col style="width:7%"/><col style="width:7%"/>
                </colgroup>
                <thead>
                    <tr style="background:#1e3a5f;color:#fff;">
                        <th rowspan="2">PLANT</th>
                        <th colspan="6">Apr-{{ short_m }}'{{ short_y }}</th>
                        <th colspan="6" style="border-left:2.5px solid #5a7fa0;">Apr-{{ short_m }}'{{ short_prev_y }}</th>
                    </tr>
                    <tr style="background:#2d4f7f;color:#fff;">
                        <th>BOF</th><th>EAF</th><th class="cc-col">CC</th><th class="cs-col">CS</th><th>BOF<br/>%CS</th><th>CC<br/>%CS</th>
                        <th style="border-left:2.5px solid #5a7fa0;">BOF</th><th>EAF</th><th class="cc-col">CC</th><th class="cs-col">CS</th><th>BOF<br/>%CS</th><th>CC<br/>%CS</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in page.ytd %}
                    {% set pr = page.ytd_prev[loop.index0] %}
                    <tr class="{% if row.plant == 'SAIL' %}sail-row{% elif row.bold %}agg-row{% endif %}">
                        <td class="plant-col">{{ row.plant }}</td>
                        <td>{{ row.bof }}</td><td>{{ row.eaf }}</td>
                        <td class="cc-col">{{ row.cc }}</td><td class="cs-col">{{ row.cs }}</td>
                        <td>{{ row.bof_pct }}</td><td>{{ row.cc_pct }}</td>
                        <td class="prev-sep">{{ pr.bof }}</td><td>{{ pr.eaf }}</td>
                        <td class="cc-col">{{ pr.cc }}</td><td class="cs-col">{{ pr.cs }}</td>
                        <td>{{ pr.bof_pct }}</td><td>{{ pr.cc_pct }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% endif %}{# end prod_by_process #}

        {% if page.type == 'catwise_saleable' %}
        <div class="catwise-wrap">
        {% for section in page.sections %}
            <div class="catwise-plant-title">{{ section.label }}</div>
            <table class="catwise-table">
                <colgroup>
                    <col class="col-lbl">
                    <col class="col-num"><col class="col-num"><col class="col-num">
                    <col class="col-num"><col class="col-num"><col class="col-num">
                </colgroup>
                <thead>
                    <tr>
                        <th rowspan="2" class="lbl-th">CATEGORY</th>
                        <th rowspan="2">2026-27<br/>Plan</th>
                        <th colspan="3">{{ page.month_label }}</th>
                        <th rowspan="2">{{ page.cply_label }}<br/>Actual</th>
                        <th rowspan="2">% Gr.<br/>over<br/>{{ page.cply_label }}</th>
                    </tr>
                    <tr>
                        <th>Plan</th><th>Actual</th><th>% Ful</th>
                    </tr>
                </thead>
                <tbody>
                {% for row in section.rows %}
                    {% if row.type == 'separator' %}
                    <tr class="cw-separator"><td colspan="7"></td></tr>
                    {% elif row.type == 'section-hdr' %}
                    <tr class="cw-section-hdr">
                        <td colspan="7" class="lbl-td">{{ row.label }}</td>
                    </tr>
                    {% else %}
                    <tr class="cw-{{ row.type }}">
                        <td class="lbl-td">{{ row.label }}</td>
                        <td class="num-td">{{ row.ann_plan }}</td>
                        <td class="num-td">{{ row.m_plan }}</td>
                        <td class="num-td">{{ row.m_act }}</td>
                        <td class="num-td">{{ row.m_pct }}</td>
                        <td class="num-td">{{ row.cply_act }}</td>
                        <td class="num-td">{{ row.m_growth }}</td>
                    </tr>
                    {% endif %}
                {% endfor %}
                </tbody>
            </table>
        {% endfor %}
        </div>
        {% endif %}{# end catwise_saleable #}

        {% if page.type == 'segment_wise' %}
        <table class="segwise-table">
            <colgroup>
                <col class="col-lbl">
                <col class="col-num"><col class="col-num"><col class="col-num">
                <col class="col-num"><col class="col-num"><col class="col-num">
            </colgroup>
            <thead>
                <tr>
                    <th rowspan="2" class="lbl-th">CATEGORY</th>
                    <th rowspan="2">2026-27<br/>Plan</th>
                    <th colspan="3">{{ page.month_label }}</th>
                    <th rowspan="2">{{ page.cply_label }}<br/>Actual</th>
                    <th rowspan="2">% Gr.<br/>over<br/>{{ page.cply_label }}</th>
                </tr>
                <tr>
                    <th>Plan</th><th>Actual</th><th>% Ful</th>
                </tr>
            </thead>
            <tbody>
            {% for row in page.rows %}
                {% if row.type == 'separator' %}
                <tr class="sw-separator"><td colspan="7"></td></tr>
                {% elif row.type == 'seg-hdr' %}
                <tr class="sw-seg-hdr">
                    <td colspan="7" class="lbl-td">{{ row.label }}</td>
                </tr>
                {% elif row.type == 'plant-lbl' %}
                <tr class="sw-plant-lbl">
                    <td colspan="7" class="lbl-td">{{ row.label }}</td>
                </tr>
                {% elif row.type == 'seg-pct' %}
                <tr class="sw-seg-pct">
                    <td class="lbl-td">{{ row.label }}</td>
                    <td class="num-td">{{ row.ann_plan }}</td>
                    <td class="num-td">{{ row.m_plan }}</td>
                    <td class="num-td">{{ row.m_act }}</td>
                    <td class="num-td"></td>
                    <td class="num-td">{{ row.cply_act }}</td>
                    <td class="num-td"></td>
                </tr>
                {% else %}
                <tr class="sw-{{ row.type }}">
                    <td class="lbl-td">{{ row.label }}</td>
                    <td class="num-td">{{ row.ann_plan }}</td>
                    <td class="num-td">{{ row.m_plan }}</td>
                    <td class="num-td">{{ row.m_act }}</td>
                    <td class="num-td">{{ row.m_pct }}</td>
                    <td class="num-td">{{ row.cply_act }}</td>
                    <td class="num-td">{{ row.m_growth }}</td>
                </tr>
                {% endif %}
            {% endfor %}
            </tbody>
        </table>
        {% endif %}{# end segment_wise #}

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
            display_header_footer=True,
            header_template=(
                '<div style="width:100%;padding:0 15mm;box-sizing:border-box;'
                'font-family:Arial,sans-serif;font-size:7.5pt;font-weight:500;'
                'color:#64748b;text-align:center;border-bottom:0.5px solid #e2e8f0;'
                'padding-bottom:3px;">'
                'Steel Authority of India Limited - Operations Monthly Informatics'
                '</div>'
            ),
            footer_template=(
                '<div style="width:100%;padding:0 15mm;box-sizing:border-box;'
                'font-family:Arial,sans-serif;font-size:7.5pt;color:#64748b;'
                'display:flex;justify-content:space-between;'
                'border-top:0.5px solid #e2e8f0;padding-top:3px;">'
                '<span>Prepared by: MIS Group</span>'
                '<span>Page <span class="pageNumber"></span>'
                ' of <span class="totalPages"></span></span>'
                '</div>'
            ),
            margin={
                "top": "18mm",
                "right": "15mm",
                "bottom": "18mm",
                "left": "15mm",
            },
        )
        browser.close()
    return pdf_bytes


async def build_pdf_response(request: PDFRequest, pages_override: list = None) -> StreamingResponse:
    import asyncio
    import traceback as tb
    from jinja2 import Template

    try:
        vars = _resolve_month_vars(request.month)

        total_report_pages = len(request.pages)

        flat_pages = []
        src = pages_override if pages_override is not None else [p_data.dict() for p_data in request.pages]
        for p in src:
            if p.get("page", 0) > 18:
                continue
            if p.get("type") == "page4_table":
                p["rows"] = _group_page4_rows(p.get("rows", []))
            flat_pages.append(p)

        # Collect all consecutive trend pages into ONE section so items flow
        # continuously across pages instead of each forcing a new page break.
        pages_to_render = []
        i = 0
        while i < len(flat_pages):
            p = flat_pages[i]
            if p.get("type") in ("trend_yearly", "trend_combined"):
                all_items = []
                first_pg = p.get("page", "?")
                last_pg  = first_pg
                while i < len(flat_pages) and flat_pages[i].get("type") in ("trend_yearly", "trend_combined"):
                    tp = flat_pages[i]
                    if tp.get("type") == "trend_combined":
                        all_items.extend(tp.get("items", []))
                    else:
                        all_items.append(tp)
                    last_pg = tp.get("page", last_pg)
                    i += 1
                pages_to_render.append({
                    "type": "trend_section",
                    "page": first_pg,
                    "items": all_items,
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
