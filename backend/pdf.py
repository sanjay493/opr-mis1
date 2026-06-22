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
        {{ font_imports }}

        * { box-sizing: border-box; }

        :root {
            --font-primary: {{ font_family_css }};
            --font-mono: {{ mono_family_css }};
            --sz-title:   {{ title_size }}pt;
            --sz-heading: {{ heading_size }}pt;
            --sz-th:      {{ th_size }}pt;
            --sz-td:      {{ td_size }}pt;
        }

        body {
            font-family: var(--font-primary);
            color: #0f172a;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }

        @page {
            size: A4 portrait;
            margin: 5mm 15mm 5mm 15mm;
        }

        /* Page 4: tighter margins to maximise usable area while keeping footer clear */
        @page page4-layout {
            size: A4 portrait;
            margin-top: 7mm;
            margin-right: 10mm;
            margin-bottom: 5mm;
            margin-left: 10mm;
        }

        .page4-page {
            page: page4-layout;
            padding-top: 0;
            padding-bottom: 0;
        }

        /* Pages 5–6: same tight side margins as page 4 to match trend-page content width */
        @page page5-6-layout {
            size: A4 portrait;
            margin-top: 7mm;
            margin-right: 10mm;
            margin-bottom: 5mm;
            margin-left: 10mm;
        }

        .page5-6-page {
            page: page5-6-layout;
            padding-top: 0;
            padding-bottom: 0;
        }

        /* Pages 27–35: techno-economic parameter pages — portrait */
        @page techno-layout {
            size: A4 portrait;
            margin-top: 5mm;
            margin-right: 5mm;
            margin-bottom: 5mm;
            margin-left: 5mm;
        }

        .techno-page {
            page: techno-layout;
            padding-top: 0;
            padding-bottom: 0;
        }

        /* Page 28: same portrait layout */
        @page techno-tight-layout {
            size: A4 portrait;
            margin-top: 5mm;
            margin-right: 5mm;
            margin-bottom: 5mm;
            margin-left: 5mm;
        }

        .techno-tight-page {
            page: techno-tight-layout;
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
            font-size: var(--sz-title);
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
            font-size: var(--sz-td);
            margin-top: 10px;
        }

        .report-table th {
            background-color: #f1f5f9;
            color: #0f172a;
            font-weight: 700;
            text-transform: uppercase;
            font-size: var(--sz-th);
            padding: 5px 4px;
            border: 1px solid #94a3b8;
            text-align: center;
        }

        .report-table td {
            padding: 4px 4px;
            border: 1px solid #cbd5e1;
            font-family: inherit;
            font-size: var(--sz-td);
            text-align: right;
        }

        .report-table td.label-cell {
            text-align: left;
            font-family: inherit;
            font-size: var(--sz-td);
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
            font-family: inherit;
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
            font-size: 10pt;
            font-weight: 700;
            margin: 5px 0 3px 0;
            color: #0f172a;
        }
        .page3-narrative {
            font-size: var(--sz-td);
            line-height: 1.4;
            margin: 2px 0 4px 0;
        }
        .page3-footnote {
            font-size: 7.5pt;
            font-style: italic;
            color: #475569;
            margin-top: 2px;
        }
        .page3-chart-grid { margin-top: 6px; }
        .page3-chart-row  { display: flex; gap: 4px; margin-bottom: 3px; }
        .page3-chart-cell { flex: 1; border: 0.5px solid #e2e8f0; border-radius: 3px; padding: 2px; }

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
        .page4-table th { font-size: 8.5pt; padding: 1.5px 2px; line-height: 1.0; }
        .page4-table td { font-size: 8.5pt; padding: 1.5px 2px; line-height: 1.0; }
        .page4-table col.c-items    { width: 10%; }
        .page4-table col.c-plant    { width:  6%; }
        .page4-table col.c-ann      { width:  8%; }
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
        .page5-6-table th { font-size: 8.5pt; padding: 4px 4px; line-height: 1; vertical-align: middle; }
        .page5-6-table td { font-size: 8.5pt; padding: 4px 4px; line-height: 1; }

        .page5-6-plant-cell {
            font-size: 8.5pt;
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
            font-size: 10pt; font-weight: 700; color: #1e293b;
            text-transform: none; text-align: right; white-space: nowrap;
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
        .segwise-table { table-layout: fixed; width: 100%; border-collapse: collapse; border: 2px solid #1e293b; font-size: 7pt; }
        .segwise-table th { background-color: #1e3a5f; color: #fff; padding: 2px 3px; text-align: center; vertical-align: middle; border: 1px solid #334155; font-size: 6.5pt; line-height: 1.2; font-weight: 600; }
        .segwise-table th.lbl-th { text-align: left; }
        .segwise-table td { padding: 1px 3px; border: 1px solid #cbd5e1; line-height: 1.2; }
        .segwise-table td.lbl-td { text-align: left; }
        .segwise-table td.num-td { text-align: right; }
        .segwise-table td.sw-group-cell { background-color: #1e3a5f; color: #fff; font-weight: 700; text-align: center; vertical-align: middle; border: 1px solid #334155; }
        .segwise-table td.sw-plant-cell { background-color: #dbeafe; font-weight: 700; text-align: center; vertical-align: middle; }
        .segwise-table tr.sw-data td { background-color: #f8fafc; }
        .segwise-table tr.sw-seg-total td { background-color: #fef9c3; font-weight: 700; }
        .segwise-table tr.sw-seg-pct td { background-color: #f1f5f9; font-weight: 700; font-style: italic; }
        .segwise-table tr.sw-grand-total td { background-color: #dcfce7; font-weight: 700; }

        /* ── Page-specific font overrides ───────────────────────────────── */
        .pg-7, .pg-7 th, .pg-7 td {
            font-family: 'Arial Narrow', Arial, sans-serif !important;
        }
    </style>
    {% if page_layouts %}
    <style>
    {% for page in pages %}
    {% set _pl = page_layouts.get(page.page|string, {}) %}
    {% if _pl %}
    {% if _pl.get('fontSize') %}
    .pg-{{ page.page }} th,
    .pg-{{ page.page }} td { font-size: {{ _pl.get('fontSize') }}pt !important; }
    {% endif %}
    {% if _pl.get('fontFamily') %}
    .pg-{{ page.page }},
    .pg-{{ page.page }} th,
    .pg-{{ page.page }} td { font-family: '{{ _pl.get("fontFamily") }}', Arial, sans-serif !important; }
    {% endif %}
    {% if _pl.get('fitToPage') %}
    .pg-{{ page.page }} th,
    .pg-{{ page.page }} td { font-size: 7pt !important; padding: 1px 2px !important; line-height: 1.0 !important; }
    .pg-{{ page.page }} .report-title-section { margin-bottom: 6px !important; }
    .pg-{{ page.page }} .highlights-box { padding: 5px !important; margin: 4px 0 !important; font-size: 7pt !important; }
    .pg-{{ page.page }} .highlights-box li { margin-bottom: 1px !important; }
    {% endif %}
    {% endif %}
    {% endfor %}
    </style>
    {% endif %}
</head>
<body>
    {% set total_pages = total_report_pages %}
    {% for page in pages %}
    {% set _pl = page_layouts.get(page.page|string, {}) %}
    {% if page.type == 'trend_section' %}
    <div class="page7-13-section-page pg-{{ page.page }}"{% if _pl %} style="padding: {{ _pl.get('marginTop', 15) }}mm {{ _pl.get('marginLR', 15) }}mm {{ _pl.get('marginBottom', 15) }}mm {{ _pl.get('marginLR', 15) }}mm;"{% endif %}>
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
                        <th colspan="15" class="heading-title">MONTH-WISE PRODUCTION TREND : {{ item.item_display }}</th>
                        <th colspan="4" class="heading-unit">Unit: {{ item.unit }}</th>
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
    <div class="page pg-{{ page.page }}{% if page.type == 'page4_table' %} page4-page{% elif page.type == 'performance_summary_table' %} page5-6-page{% elif page.type == 'techno_params' %}{% if page.page == 28 %} techno-tight-page{% else %} techno-page{% endif %}{% endif %}"{% if _pl %} style="padding: {{ _pl.get('marginTop', 15) }}mm {{ _pl.get('marginLR', 15) }}mm {{ _pl.get('marginBottom', 15) }}mm {{ _pl.get('marginLR', 15) }}mm;"{% endif %}>

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
                <h2>{{ page.title }}: {{ short_m }}'{{ short_y }}</h2>
            </div>

            {# ── Production narrative ── #}
            <p class="page3-section-heading" style="margin-bottom:1px;">Production:</p>
            <p class="page3-section-heading" style="margin-top:0;margin-bottom:2px;">{{ short_m }}'{{ short_y }}:</p>
            {% if page.production_narrative %}
            <p class="page3-narrative">{{ page.production_narrative }}</p>
            {% endif %}

            {# ── Compact production table (5 data cols: APP, Actual, %Ful, CPLY Act, %Gr) ── #}
            <div style="text-align:right;font-size:7.5pt;font-style:italic;margin-bottom:2px;">Unit: '000 T</div>
            <table class="report-table" style="table-layout:fixed;width:100%;">
                <thead>
                    <tr>
                        <th rowspan="2" style="width:22%;text-align:left;">Item</th>
                        <th colspan="3" style="text-align:center;">{{ m_name }} {{ y_str }}</th>
                        <th rowspan="2" style="text-align:center;white-space:normal;line-height:1.2;">{{ short_m }}'{{ short_prev_y }}<br/>Act.</th>
                        <th rowspan="2" style="text-align:center;white-space:normal;line-height:1.2;">% Gr.<br/>w.r.t.<br/>{{ short_m }}'{{ short_prev_y }}</th>
                    </tr>
                    <tr>
                        <th>APP</th><th>Actual</th><th>% Ful.</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in page.production_table %}
                    {% set vals = row.get('values') or [] %}
                    <tr>
                        <td class="label-cell">{{ row.item }}</td>
                        {% for i in range(5) %}<td style="font-weight:{{ '700' if i == 1 else '400' }}">{{ vals[i] if vals|length > i else '' }}</td>{% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <p class="page3-footnote">*includes conversion</p>

            {# ── Highlights ── #}
            {% if page.highlights %}
            <p class="page3-section-heading">Highlights:</p>
            <div style="font-size:var(--sz-td);line-height:1.4;white-space:pre-wrap;">{% for h in page.highlights %}{{ h }}
{% endfor %}</div>
            {% endif %}

            {# ── TE table: Target | Month | CPLY | Apr-Mon | CPLY Apr-Mon ── #}
            <p class="page3-section-heading" style="margin-top:5px;">TE parameters performance:</p>
            <table class="report-table" style="table-layout:fixed;width:100%;">
                <thead>
                    <tr>
                        <th style="width:24%;text-align:left;">Parameter</th>
                        <th style="width:10%;">Unit</th>
                        <th style="width:13%;">{{ target_header }}</th>
                        <th style="width:13%;font-weight:700;">{{ short_m }}'{{ short_y }}</th>
                        <th style="width:13%;">{{ short_m }}'{{ short_prev_y }}</th>
                        <th style="width:14%;">Apr-{{ short_m }}'{{ short_y }}</th>
                        <th style="width:13%;">Apr-{{ short_m }}'{{ short_prev_y }}</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in page.te_table %}
                    <tr>
                        <td class="label-cell" style="font-weight:600;">{{ row.parameter }}</td>
                        <td class="label-cell" style="font-style:italic;color:#475569;">{{ row.unit }}</td>
                        <td style="text-align:right;">{{ row['values'][0] if row['values']|length > 0 else '' }}</td>
                        <td style="font-weight:700;text-align:right;">{{ row['values'][1] if row['values']|length > 1 else '' }}</td>
                        <td style="text-align:right;">{{ row['values'][2] if row['values']|length > 2 else '' }}</td>
                        <td style="text-align:right;">{{ row['values'][3] if row['values']|length > 3 else '' }}</td>
                        <td style="text-align:right;">{{ row['values'][4] if row['values']|length > 4 else '' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            {# ── Bar charts ── #}
            {% if page._chart_html %}{{ page._chart_html | safe }}{% endif %}

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
                        <th colspan="15" class="heading-title">MONTH-WISE PRODUCTION TREND : {{ page.item_display }}</th>
                        <th colspan="4" class="heading-unit">Unit: {{ page.unit }}</th>
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
                        {% if row.is_conversion %}
                        <td colspan="2" class="label-cell"
                            style="font-weight: 700; font-size: 8pt; vertical-align: middle;
                                   padding: 1px 2px 1px 4px; font-family: inherit;">
                            Conversion
                        </td>
                        {% elif row.is_sail_incl_conv %}
                        <td colspan="2" class="label-cell"
                            style="font-weight: 700; font-size: 8pt; vertical-align: middle;
                                   padding: 1px 2px 1px 4px; font-family: inherit;">
                            SAIL incl. conversion
                        </td>
                        {% else %}
                        {% if row.is_first_in_group %}
                        <td class="label-cell" rowspan="{{ row.group_size }}"
                            style="font-weight: 700; font-size: 8pt; vertical-align: middle;
                                   background-color: #f8fafc; padding: 1px 2px 1px 4px;
                                   overflow: hidden; font-family: inherit;">
                            {{ row.item }}
                        </td>
                        {% endif %}
                        <td class="label-cell"
                            style="font-weight: 600; font-size: 8pt; text-align: center;
                                   background-color: #f8fafc; padding: 1px 2px;
                                   font-family: inherit;
                                   white-space: nowrap; overflow: hidden;">
                            {{ row.plant }}
                        </td>
                        {% endif %}
                        {% for val in row['values'] %}<td{% if col_cls[loop.index0] %} class="{{ col_cls[loop.index0] }}"{% endif %}>{{ val }}</td>{% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

        {% elif page.type == 'concast_performance' %}{# rendered in the block below #}

        {% elif page.type == 'prod_by_process' %}{# rendered in the block below #}

        {% elif page.type == 'catwise_saleable' %}{# rendered in the block below #}

        {% elif page.type == 'segment_wise' %}{# rendered in the block below #}

        {% elif page.type == 'special_steel' %}{# rendered in the block below #}

        {% elif page.type == 'opening_stock' %}{# rendered in the block below #}

        {% elif page.type == 'ipt_status' %}{# rendered in the block below #}

        {% elif page.type == 'techno_params' %}{# rendered in the block below #}

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
        {% set cum_lbl = 'Apr-' ~ page.month_label %}
        {% set cum_cply_lbl = 'Apr-' ~ page.cply_label %}
        <table class="segwise-table">
            <colgroup>
                <col style="width:5%"><col style="width:5%"><col style="width:13%">
                <col style="width:7%">
                <col style="width:6%"><col style="width:6%"><col style="width:5%">
                <col style="width:6%"><col style="width:5%">
                <col style="width:6%"><col style="width:6%"><col style="width:5%">
                <col style="width:6%"><col style="width:5%">
            </colgroup>
            <thead>
                <tr>
                    <th rowspan="2">Group</th>
                    <th rowspan="2">Plant</th>
                    <th rowspan="2" class="lbl-th">Item</th>
                    <th rowspan="2">Plan<br/>26-27</th>
                    <th colspan="3">{{ page.month_label }}</th>
                    <th rowspan="2">{{ page.cply_label }}<br/>Actual</th>
                    <th rowspan="2">% Gr.<br/>over<br/>{{ page.cply_label }}</th>
                    <th colspan="3">{{ cum_lbl }}</th>
                    <th rowspan="2">{{ cum_cply_lbl }}<br/>Actual</th>
                    <th rowspan="2">% Gr<br/>Over<br/>{{ cum_cply_lbl }}</th>
                </tr>
                <tr>
                    <th>Plan</th><th>Actual</th><th>%Ful</th>
                    <th>Plan</th><th>Actual</th><th>%Ful</th>
                </tr>
            </thead>
            <tbody>
            {% for row in page.rows %}
                {% if row.type == 'separator' %}
                {# skip separators — visual sections now provided by group/plant cells #}
                {% elif row.type in ('seg-total', 'seg-pct', 'grand-total') %}
                <tr class="sw-{{ row.type }}">
                    <td colspan="3" class="lbl-td">{{ row.label }}</td>
                    <td class="num-td">{{ row.ann_plan }}</td>
                    <td class="num-td">{{ row.m_plan }}</td>
                    <td class="num-td">{{ row.m_act }}</td>
                    <td class="num-td">{{ row.m_pct }}</td>
                    <td class="num-td">{{ row.cply_act }}</td>
                    <td class="num-td">{{ row.m_growth }}</td>
                    <td class="num-td">{{ row.cum_plan }}</td>
                    <td class="num-td">{{ row.cum_act }}</td>
                    <td class="num-td">{{ row.cum_pct }}</td>
                    <td class="num-td">{{ row.cum_cply }}</td>
                    <td class="num-td">{{ row.cum_growth }}</td>
                </tr>
                {% else %}
                <tr class="sw-{{ row.type }}">
                    {% if row.show_group %}<td rowspan="{{ row.group_span }}" class="sw-group-cell">{{ row.group }}</td>{% endif %}
                    {% if row.show_plant %}<td rowspan="{{ row.plant_span }}" class="sw-plant-cell">{{ row.plant }}</td>{% endif %}
                    <td class="lbl-td">{{ row.label }}</td>
                    <td class="num-td">{{ row.ann_plan }}</td>
                    <td class="num-td">{{ row.m_plan }}</td>
                    <td class="num-td">{{ row.m_act }}</td>
                    <td class="num-td">{{ row.m_pct }}</td>
                    <td class="num-td">{{ row.cply_act }}</td>
                    <td class="num-td">{{ row.m_growth }}</td>
                    <td class="num-td">{{ row.cum_plan }}</td>
                    <td class="num-td">{{ row.cum_act }}</td>
                    <td class="num-td">{{ row.cum_pct }}</td>
                    <td class="num-td">{{ row.cum_cply }}</td>
                    <td class="num-td">{{ row.cum_growth }}</td>
                </tr>
                {% endif %}
            {% endfor %}
            </tbody>
        </table>
        {% endif %}{# end segment_wise #}

        {% if page.type == 'special_steel' %}

        {% if page.variant == 'isp_sail_combined' %}
        {# ── Page 23: ISP mill-wise + SAIL summary combined on one portrait page ── #}
        <div style="padding:6px;font-family:'Arial Narrow',Arial,sans-serif;font-size:7.5pt;">

          {% set d = page.isp %}
          <div style="text-align:center;font-weight:700;font-size:10pt;margin-bottom:3px;">{{ d.title }}</div>
          <div style="text-align:right;font-size:6.8pt;margin-bottom:2px;">Unit: Tonnes</div>
          <table style="width:100%;border-collapse:collapse;border:2px solid #1e293b;table-layout:fixed;font-size:6.5pt;">
            <colgroup>
              <col style="width:20%"/>
              <col style="width:8%"/><col style="width:8%"/><col style="width:6%"/>
              <col style="width:6.5%"/><col style="width:5.5%"/>
              <col style="width:8%"/><col style="width:8%"/><col style="width:6%"/>
              <col style="width:6.5%"/><col style="width:5.5%"/>
            </colgroup>
            <thead>
              <tr style="background:#1e3a5f;color:#fff;">
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;text-align:left;">Quality / Grade</th>
                <th colspan="3" style="padding:2px 3px;border:1px solid #334155;">{{ d.month_label }}</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">{{ d.cply_label }}<br/>Actual</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">%Gr<br/>{{ d.cply_label }}</th>
                <th colspan="3" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">{{ d.cum_label }}</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">{{ d.cum_cply_label }}<br/>Actual</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">%Gr<br/>{{ d.cum_cply_label }}</th>
              </tr>
              <tr style="background:#2d4f7f;color:#fff;">
                <th style="padding:2px 3px;border:1px solid #334155;">Order</th>
                <th style="padding:2px 3px;border:1px solid #334155;">Actual</th>
                <th style="padding:2px 3px;border:1px solid #334155;">%Ful</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">Order</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">Actual</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">%Ful</th>
              </tr>
            </thead>
            <tbody>
            {% for row in d.rows %}
              {% if row.type == 'separator' %}
              <tr style="height:2px;"><td colspan="11" style="border:none;padding:0;"></td></tr>
              {% elif row.type == 'grand-total' %}
              <tr style="background:#dcfce7;font-weight:700;">
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">{{ row.label }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_growth }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_growth }}</td>
              </tr>
              {% else %}
              <tr style="background:#f8fafc;">
                <td style="padding:1.5px 3px;padding-left:10px;border:1px solid #cbd5e1;text-align:left;">{{ row.label }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_growth }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_growth }}</td>
              </tr>
              {% endif %}
            {% endfor %}
            <tr style="height:2px;"><td colspan="11" style="border:none;padding:0;"></td></tr>
            <tr style="background:#e0f2fe;font-weight:600;">
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">Saleable Steel Production</td>
              <td colspan="2" style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ d.saleable_production.current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ d.saleable_production.cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td colspan="2" style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ d.saleable_production.cum_current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ d.saleable_production.cum_cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ d.saleable_production.cum_pct_growth }}</td>
            </tr>
            <tr style="background:#e0f2fe;font-weight:600;">
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">Special Steel % of Saleable Steel</td>
              <td colspan="2" style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ d.special_pct.current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ d.special_pct.cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td colspan="2" style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ d.special_pct.cum_current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ d.special_pct.cum_cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
            </tr>
            </tbody>
          </table>

          <div style="margin-top:6px;"></div>

          {% set d = page.sail %}
          <div style="text-align:center;font-weight:700;font-size:10pt;margin-bottom:3px;">{{ d.title }}</div>
          <div style="text-align:center;font-weight:600;font-size:8pt;margin-bottom:3px;">{{ d.month_label }}</div>
          <div style="text-align:right;font-size:6.8pt;margin-bottom:2px;">Unit: Tonnes</div>
          <table style="width:100%;border-collapse:collapse;border:2px solid #1e293b;table-layout:fixed;font-size:6.8pt;">
            <colgroup>
              <col style="width:13%"/><col style="width:8%"/>
              <col style="width:7%"/><col style="width:7%"/><col style="width:5.5%"/>
              <col style="width:6%"/><col style="width:5%"/>
              <col style="width:7%"/><col style="width:7%"/><col style="width:5.5%"/>
              <col style="width:6%"/><col style="width:5%"/>
            </colgroup>
            <thead>
              <tr style="background:#1e3a5f;color:#fff;">
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;text-align:left;">Plants</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">ABP<br/>26-27</th>
                <th colspan="3" style="padding:2px 3px;border:1px solid #334155;">{{ d.month_label }}</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">{{ d.cply_label }}<br/>Actual</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">%Gr<br/>{{ d.cply_label }}</th>
                <th colspan="3" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">{{ d.cum_label }}</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">{{ d.cum_cply_label }}<br/>Actual</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">%Gr<br/>{{ d.cum_cply_label }}</th>
              </tr>
              <tr style="background:#2d4f7f;color:#fff;">
                <th style="padding:2px 3px;border:1px solid #334155;">Orders</th>
                <th style="padding:2px 3px;border:1px solid #334155;">Actual</th>
                <th style="padding:2px 3px;border:1px solid #334155;">%Ful</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">Orders</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">Actual</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">%Ful</th>
              </tr>
            </thead>
            <tbody>
            {% for row in d.rows %}
            {% set bg = '#dcfce7' if row.type == 'sail-total' else '#f8fafc' %}
            {% set fw = '700' if row.type == 'sail-total' else '400' %}
            <tr style="background:{{ bg }};font-weight:{{ fw }};">
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">{{ row.label }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.abp }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.orders }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.actual }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_ful }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_growth }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_orders }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_actual }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_ful }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_growth }}</td>
            </tr>
            {% endfor %}
            <tr style="height:2px;"><td colspan="12" style="border:none;padding:0;"></td></tr>
            <tr style="background:#e0f2fe;font-weight:600;">
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">Saleable Steel production</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ d.saleable_production.abp }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ d.saleable_production.current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ d.saleable_production.cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ d.saleable_production.pct_growth }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ d.saleable_production.cum_current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ d.saleable_production.cum_cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ d.saleable_production.cum_pct_growth }}</td>
            </tr>
            <tr style="background:#e0f2fe;font-weight:600;">
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">Special Steel % of Saleable Steel</td>
              <td colspan="2" style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ d.special_pct.current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ d.special_pct.cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ d.special_pct.cum_current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ d.special_pct.cum_cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
            </tr>
            </tbody>
          </table>
        </div>

        {% else %}
        {# ── existing sail_summary / plant_detail rendering ── #}
        <div style="padding:6px;font-family:Arial,sans-serif;font-size:7.5pt;">
          <div style="text-align:center;font-weight:700;font-size:10pt;margin-bottom:3px;">{{ page.title }}</div>
          {% if page.variant == 'sail_summary' %}
          <div style="text-align:center;font-weight:600;font-size:8pt;margin-bottom:3px;">{{ page.month_label }}</div>
          {% endif %}
          <div style="text-align:right;font-size:6.8pt;margin-bottom:2px;">Unit: Tonnes</div>

          {% if page.variant == 'sail_summary' %}
          {# ── SAIL consolidated table — 12 cols ── #}
          <table style="width:100%;border-collapse:collapse;border:2px solid #1e293b;table-layout:fixed;font-size:6.8pt;">
            <colgroup>
              <col style="width:13%"/><col style="width:8%"/>
              <col style="width:7%"/><col style="width:7%"/><col style="width:5.5%"/>
              <col style="width:6%"/><col style="width:5%"/>
              <col style="width:7%"/><col style="width:7%"/><col style="width:5.5%"/>
              <col style="width:6%"/><col style="width:5%"/>
            </colgroup>
            <thead>
              <tr style="background:#1e3a5f;color:#fff;">
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;text-align:left;">Plants</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">ABP<br/>26-27</th>
                <th colspan="3" style="padding:2px 3px;border:1px solid #334155;">{{ page.month_label }}</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">{{ page.cply_label }}<br/>Actual</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">%Gr<br/>{{ page.cply_label }}</th>
                <th colspan="3" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">{{ page.cum_label }}</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">{{ page.cum_cply_label }}<br/>Actual</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">%Gr<br/>{{ page.cum_cply_label }}</th>
              </tr>
              <tr style="background:#2d4f7f;color:#fff;">
                <th style="padding:2px 3px;border:1px solid #334155;">Orders</th>
                <th style="padding:2px 3px;border:1px solid #334155;">Actual</th>
                <th style="padding:2px 3px;border:1px solid #334155;">%Ful</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">Orders</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">Actual</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">%Ful</th>
              </tr>
            </thead>
            <tbody>
            {% for row in page.rows %}
            {% set bg = '#dcfce7' if row.type == 'sail-total' else '#f8fafc' %}
            {% set fw = '700' if row.type == 'sail-total' else '400' %}
            <tr style="background:{{ bg }};font-weight:{{ fw }};">
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">{{ row.label }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.abp }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.orders }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.actual }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_ful }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_growth }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_orders }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_actual }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_ful }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_growth }}</td>
            </tr>
            {% endfor %}
            <tr style="height:2px;"><td colspan="12" style="border:none;padding:0;"></td></tr>
            <tr style="background:#e0f2fe;font-weight:600;">
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">Saleable Steel production</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ page.saleable_production.abp }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ page.saleable_production.current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ page.saleable_production.cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ page.saleable_production.pct_growth }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ page.saleable_production.cum_current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ page.saleable_production.cum_cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ page.saleable_production.cum_pct_growth }}</td>
            </tr>
            <tr style="background:#e0f2fe;font-weight:600;">
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">Special Steel % of Saleable Steel</td>
              <td colspan="2" style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ page.special_pct.current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ page.special_pct.cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ page.special_pct.cum_current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ page.special_pct.cum_cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
            </tr>
            </tbody>
          </table>

          {% else %}
          {# ── Plant detail / ISP table — 11 cols ── #}
          <table style="width:100%;border-collapse:collapse;border:2px solid #1e293b;table-layout:fixed;font-size:6.5pt;">
            <colgroup>
              <col style="width:20%"/>
              <col style="width:8%"/><col style="width:8%"/><col style="width:6%"/>
              <col style="width:6.5%"/><col style="width:5.5%"/>
              <col style="width:8%"/><col style="width:8%"/><col style="width:6%"/>
              <col style="width:6.5%"/><col style="width:5.5%"/>
            </colgroup>
            <thead>
              <tr style="background:#1e3a5f;color:#fff;">
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;text-align:left;">Quality / Grade</th>
                <th colspan="3" style="padding:2px 3px;border:1px solid #334155;">{{ page.month_label }}</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">{{ page.cply_label }}<br/>Actual</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">%Gr<br/>{{ page.cply_label }}</th>
                <th colspan="3" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">{{ page.cum_label }}</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">{{ page.cum_cply_label }}<br/>Actual</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">%Gr<br/>{{ page.cum_cply_label }}</th>
              </tr>
              <tr style="background:#2d4f7f;color:#fff;">
                <th style="padding:2px 3px;border:1px solid #334155;">Order</th>
                <th style="padding:2px 3px;border:1px solid #334155;">Actual</th>
                <th style="padding:2px 3px;border:1px solid #334155;">%Ful</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">Order</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">Actual</th>
                <th style="padding:2px 3px;border:1px solid #2d5016;background:#2d5016;">%Ful</th>
              </tr>
            </thead>
            <tbody>
            {% for row in page.rows %}
              {% if row.type == 'separator' %}
              <tr style="height:2px;"><td colspan="11" style="border:none;padding:0;"></td></tr>
              {% elif row.type == 'product-hdr' %}
              <tr style="background:#1e3a5f;color:#fff;font-weight:700;">
                <td colspan="11" style="padding:2px 5px;border:1px solid #334155;text-align:left;">{{ row.label }}</td>
              </tr>
              {% elif row.type == 'grand-total' %}
              <tr style="background:#dcfce7;font-weight:700;">
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">{{ row.label }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_growth }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_growth }}</td>
              </tr>
              {% elif row.type == 'subtotal' %}
              <tr style="background:#fed7aa;font-weight:700;">
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">{{ row.label }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_growth }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_growth }}</td>
              </tr>
              {% elif row.type == 'product-total' %}
              <tr style="background:#fef9c3;font-weight:700;">
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">{{ row.label }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_growth }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_growth }}</td>
              </tr>
              {% else %}
              <tr style="background:#f8fafc;">
                <td style="padding:1.5px 3px;padding-left:10px;border:1px solid #cbd5e1;text-align:left;">{{ row.label }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ row.pct_growth }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_orders }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_actual }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_ful }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_cply }}</td>
                <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ row.cum_pct_growth }}</td>
              </tr>
              {% endif %}
            {% endfor %}
            <tr style="height:2px;"><td colspan="11" style="border:none;padding:0;"></td></tr>
            <tr style="background:#e0f2fe;font-weight:600;">
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">Saleable Steel Production</td>
              <td colspan="2" style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ page.saleable_production.current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ page.saleable_production.cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td colspan="2" style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ page.saleable_production.cum_current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ page.saleable_production.cum_cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ page.saleable_production.cum_pct_growth }}</td>
            </tr>
            <tr style="background:#e0f2fe;font-weight:600;">
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:left;">Special Steel % of Saleable Steel</td>
              <td colspan="2" style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ page.special_pct.current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;text-align:right;">{{ page.special_pct.cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #cbd5e1;"></td>
              <td colspan="2" style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ page.special_pct.cum_current }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;text-align:right;">{{ page.special_pct.cum_cply }}</td>
              <td style="padding:1.5px 3px;border:1px solid #b7d4a0;"></td>
            </tr>
            </tbody>
          </table>
          {% endif %}
        </div>
        {% endif %}{# end isp_sail_combined else #}
        {% endif %}{# end special_steel #}

        {% if page.type == 'opening_stock' %}
        <div style="padding:6px;font-family:Arial,sans-serif;font-size:7pt;">
          <div style="text-align:center;font-weight:700;font-size:10pt;margin-bottom:3px;">{{ page.title }}</div>
          <div style="text-align:right;font-size:6.5pt;margin-bottom:2px;">Unit: {{ page.unit }}</div>
          <table style="width:100%;border-collapse:collapse;border:2px solid #1e293b;table-layout:fixed;font-size:6.3pt;">
            <colgroup>
              <col style="width:18px"/><col style="width:14px"/>
              <col style="width:8%"/><col style="width:7%"/>
              {% for c in page.col_labels %}<col/>{% endfor %}
              <col style="width:9%"/>
            </colgroup>
            <thead>
              <tr style="background:#1e3a5f;color:#fff;">
                <th colspan="3" style="padding:2px 3px;border:1px solid #334155;"></th>
                <th style="padding:2px 3px;border:1px solid #334155;">PLANT</th>
                {% for c in page.col_labels %}
                <th style="padding:2px 3px;border:1px solid #334155;">{{ c }}</th>
                {% endfor %}
                <th style="padding:2px 3px;border:1px solid #334155;">{{ page.var_label }}</th>
              </tr>
            </thead>
            <tbody>
            {% for sec in page.sections %}
              {% for row in sec.rows %}
              {% if row.sail and row.bold %}{% set bg = '#dcfce7' %}
              {% elif row.sail %}{% set bg = '#eff6ff' %}
              {% elif row.bold %}{% set bg = '#fef9c3' %}
              {% else %}{% set bg = '#f8fafc' %}{% endif %}
              <tr style="background:{{ bg }};{% if row.bold %}font-weight:700;{% endif %}">
                {% if loop.first %}
                <td rowspan="{{ sec.rows | length }}" style="border:1px solid #94a3b8;background:#e2e8f0;text-align:center;vertical-align:middle;font-weight:700;font-size:5.6pt;padding:1px;">
                  <div style="writing-mode:vertical-rl;transform:rotate(180deg);white-space:nowrap;margin:auto;">{{ sec.label }}</div>
                </td>
                <td rowspan="{{ sec.rows | length }}" style="border:1px solid #94a3b8;background:#e2e8f0;text-align:center;vertical-align:middle;font-size:5.4pt;padding:1px;">
                  <div style="writing-mode:vertical-rl;transform:rotate(180deg);white-space:nowrap;margin:auto;">{{ sec.code }}</div>
                </td>
                {% endif %}
                <td style="padding:1px 3px;border:1px solid #94a3b8;text-align:left;font-size:5.8pt;white-space:normal;word-break:break-word;">{{ row.sub }}</td>
                {% if (row.plant_rowspan | default(1)) > 0 %}
                <td rowspan="{{ row.plant_rowspan | default(1) }}" style="padding:1px 3px;border:1px solid #94a3b8;text-align:left;vertical-align:middle;{% if row.plant == 'SAIL' %}font-weight:700;{% endif %}">{{ row.plant }}</td>
                {% endif %}
                {% for v in row['values'] %}
                <td style="padding:1px 3px;border:1px solid #94a3b8;text-align:right;">{{ v }}</td>
                {% endfor %}
                <td style="padding:1px 3px;border:1px solid #94a3b8;text-align:right;font-weight:600;">{{ row.var }}</td>
              </tr>
              {% endfor %}
            {% endfor %}
            </tbody>
          </table>
          <div style="display:flex;justify-content:space-between;font-size:5.8pt;color:#475569;margin-top:2px;">
            <span>Figures are provisional</span><span>For internal use</span>
          </div>
        </div>
        {% endif %}{# end opening_stock #}

        {% if page.type == 'ipt_status' %}
        <div style="padding:10px;font-family:Arial,sans-serif;font-size:7.5pt;">
          <div style="text-align:center;font-weight:700;font-size:10pt;margin-bottom:6px;">{{ page.title }}</div>
          <table style="width:100%;border-collapse:collapse;border:2px solid #1e293b;table-layout:fixed;font-size:7.5pt;">
            <colgroup>
              <col style="width:24%"/><col style="width:9%"/><col style="width:9%"/><col style="width:8%"/>
              <col style="width:12.5%"/><col style="width:12.5%"/><col style="width:12.5%"/><col style="width:12.5%"/>
            </colgroup>
            <thead>
              <tr style="background:#1e3a5f;color:#fff;">
                <th rowspan="2" style="padding:3px 4px;border:1px solid #334155;text-align:left;">Item</th>
                <th rowspan="2" style="padding:3px 4px;border:1px solid #334155;">From</th>
                <th rowspan="2" style="padding:3px 4px;border:1px solid #334155;">To</th>
                <th rowspan="2" style="padding:3px 4px;border:1px solid #334155;">Unit</th>
                <th colspan="2" style="padding:3px 4px;border:1px solid #334155;">{{ page.month_label }}</th>
                <th colspan="2" style="padding:3px 4px;border:1px solid #334155;">{{ page.cum_label }}</th>
              </tr>
              <tr style="background:#2d4f7f;color:#fff;">
                <th style="padding:3px 4px;border:1px solid #334155;">Plan</th>
                <th style="padding:3px 4px;border:1px solid #334155;">Actual</th>
                <th style="padding:3px 4px;border:1px solid #334155;">Plan</th>
                <th style="padding:3px 4px;border:1px solid #334155;">Actual</th>
              </tr>
            </thead>
            <tbody>
            {% for sec in page.sections %}
              {% set sbg = '#f8fafc' if loop.index0 % 2 else '#ffffff' %}
              {% for row in sec.rows %}
              <tr style="background:{{ sbg }};">
                {% if loop.first %}
                <td rowspan="{{ sec.rows | length }}" style="padding:2px 5px;border:1px solid #94a3b8;text-align:left;font-weight:600;vertical-align:middle;">{{ sec.item }}</td>
                {% endif %}
                <td style="padding:2px 5px;border:1px solid #94a3b8;text-align:center;">{{ row.from }}</td>
                <td style="padding:2px 5px;border:1px solid #94a3b8;text-align:center;">{{ row.to }}</td>
                <td style="padding:2px 5px;border:1px solid #94a3b8;text-align:center;">{{ row.unit }}</td>
                <td style="padding:2px 5px;border:1px solid #94a3b8;text-align:right;">{{ row.plan }}{% if row.plan_t %}<div style="font-size:5.6pt;color:#475569;">({{ row.plan_t }} T)</div>{% endif %}</td>
                <td style="padding:2px 5px;border:1px solid #94a3b8;text-align:right;">{{ row.actual }}{% if row.actual_t %}<div style="font-size:5.6pt;color:#475569;">({{ row.actual_t }} T)</div>{% endif %}</td>
                <td style="padding:2px 5px;border:1px solid #94a3b8;text-align:right;">{{ row.cum_plan }}{% if row.cum_plan_t %}<div style="font-size:5.6pt;color:#475569;">({{ row.cum_plan_t }} T)</div>{% endif %}</td>
                <td style="padding:2px 5px;border:1px solid #94a3b8;text-align:right;">{{ row.cum_actual }}{% if row.cum_actual_t %}<div style="font-size:5.6pt;color:#475569;">({{ row.cum_actual_t }} T)</div>{% endif %}</td>
              </tr>
              {% endfor %}
            {% endfor %}
            </tbody>
          </table>
        </div>
        {% endif %}{# end ipt_status #}

        {% if page.type == 'techno_params' %}
        {% set _is_major = page.page == 27 %}
        {% set _tsz = '5pt' if page.page == 28 else ('6pt' if _is_major else '5pt') %}
        <div style="padding:4px;font-family:'Arial Narrow',Arial,sans-serif;font-size:{{ _tsz }};">
          <div style="text-align:center;font-weight:700;font-size:9pt;">{{ page.title }}</div>
          {% if page.subtitle %}
          <div style="text-align:center;font-weight:600;font-size:7.5pt;margin-bottom:3px;">{{ page.subtitle }}</div>
          {% endif %}
          {% set _tbsz = '4.8pt' if page.page == 28 else ('5.8pt' if _is_major else '4.8pt') %}
          <table style="width:100%;border-collapse:collapse;border:2px solid #1e293b;table-layout:fixed;font-size:{{ _tbsz }};margin-top:2px;">
            <colgroup>
              {% if _is_major %}
              <col style="width:20%"/><col style="width:10%"/>
              {% else %}
              <col style="width:13%"/><col style="width:13%"/><col style="width:7%"/>
              {% endif %}
              {% set ncols = 6 + (page.month_labels | length) %}
              {% for i in range(ncols) %}<col/>{% endfor %}
            </colgroup>
            <thead>
              <tr style="background:#1e3a5f;color:#fff;">
                {% if _is_major %}
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;text-align:left;">Parameters</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">Plants</th>
                {% else %}
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;text-align:left;">Shop / Plant</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">Parameters</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">Unit</th>
                {% endif %}
                <th colspan="2" style="padding:2px 3px;border:1px solid #334155;background:#475569;">Actual</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;background:#7c2d12;">{{ page.target_label }}</th>
                <th colspan="{{ page.month_labels | length }}" style="padding:2px 3px;border:1px solid #334155;">Actual</th>
                <th rowspan="2" style="padding:2px 3px;border:1px solid #334155;">{{ page.cply_label }}<br/>Actual</th>
                <th colspan="2" style="padding:2px 3px;border:1px solid #334155;background:#2d5016;">Actual</th>
              </tr>
              <tr style="background:#2d4f7f;color:#fff;">
                <th style="padding:2px 3px;border:1px solid #334155;background:#475569;">{{ page.fy2_label }}</th>
                <th style="padding:2px 3px;border:1px solid #334155;background:#475569;">{{ page.fy1_label }}</th>
                {% for m in page.month_labels %}
                <th style="padding:2px 3px;border:1px solid #334155;">{{ m }}</th>
                {% endfor %}
                <th style="padding:2px 3px;border:1px solid #334155;background:#2d5016;">{{ page.cum_label }}</th>
                <th style="padding:2px 3px;border:1px solid #334155;background:#2d5016;">{{ page.cum_cply_label }}</th>
              </tr>
            </thead>
            <tbody>
            {% for sec in page.sections %}
              {% set sbg = '#f8fafc' if loop.index0 % 2 else '#ffffff' %}
              {% for row in sec.rows %}
              <tr style="background:{{ sbg }};">
                {% if loop.first %}
                {% if _is_major %}
                {% set _sec_unit = sec.rows[0].unit if sec.rows else '' %}
                {% set _sec_label = (sec.label ~ ' (' ~ _sec_unit ~ ')') if _sec_unit else sec.label %}
                <td rowspan="{{ sec.rows | length }}" style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:left;font-weight:700;vertical-align:top;background:#e2e8f0;">{{ _sec_label }}</td>
                {% else %}
                <td rowspan="{{ sec.rows | length }}" style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:left;font-weight:700;vertical-align:top;background:#e2e8f0;">{{ sec.label }}</td>
                {% endif %}
                {% endif %}
                <td style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:left;">{{ row.label }}</td>
                {% if not _is_major %}
                <td style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:center;font-size:5.6pt;">{{ row.unit }}</td>
                {% endif %}
                <td style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:right;">{{ row.fy2 }}</td>
                <td style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:right;">{{ row.fy1 }}</td>
                <td style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:right;background:#fef3ec;">{{ row.target }}</td>
                {% for v in row.months %}
                <td style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:right;">{{ v }}</td>
                {% endfor %}
                <td style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:right;">{{ row.cply }}</td>
                <td style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:right;background:#f3faf0;">{{ row.cum }}</td>
                <td style="padding:0.5px 2px;border:1px solid #94a3b8;text-align:right;background:#f3faf0;">{{ row.cum_cply }}</td>
              </tr>
              {% endfor %}
            {% endfor %}
            </tbody>
          </table>
          <div style="display:flex;justify-content:space-between;font-size:5.8pt;color:#475569;margin-top:2px;">
            <span>figures are provisional</span><span>for internal circulation only</span>
          </div>
        </div>
        {% endif %}{# end techno_params #}

        {% endif %}{# end non-cover #}
    </div>
    {% endif %}{# end else (non-trend_section) #}
    {% endfor %}
</body>
</html>
"""

FONT_CATALOG = {
    "IBM Plex Sans": {
        "import": "@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=IBM+Plex+Mono:wght@400;500;700&display=swap');",
        "mono": "IBM Plex Mono",
    },
    "Source Sans 3": {
        "import": "@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Source+Code+Pro:wght@400;500;700&display=swap');",
        "mono": "Source Code Pro",
    },
    "Roboto": {
        "import": "@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700;900&family=Roboto+Mono:wght@400;500;700&display=swap');",
        "mono": "Roboto Mono",
    },
    "Noto Sans": {
        "import": "@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Noto+Sans+Mono:wght@400;500;700&display=swap');",
        "mono": "Noto Sans Mono",
    },
    "Lato": {
        "import": "@import url('https://fonts.googleapis.com/css2?family=Lato:ital,wght@0,300;0,400;0,700;0,900;1,400&family=Roboto+Mono:wght@400;500;700&display=swap');",
        "mono": "Roboto Mono",
    },
}
_DEFAULT_FONT = "IBM Plex Sans"

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


def _render_pdf_sync(html: str, font_family: str = _DEFAULT_FONT) -> bytes:
    """Run Playwright synchronously (called from a thread to avoid event-loop conflicts)."""
    from playwright.sync_api import sync_playwright
    hdr_font = f"'{font_family}',Arial,sans-serif"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="domcontentloaded")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template=(
                f'<div style="width:100%;padding:0 15mm;box-sizing:border-box;'
                f'font-family:{hdr_font};font-size:7.5pt;font-weight:500;'
                f'color:#64748b;text-align:center;border-bottom:0.5px solid #e2e8f0;'
                f'padding-bottom:3px;">'
                f'Steel Authority of India Limited – Operations Monthly Informatics'
                f'</div>'
            ),
            footer_template=(
                f'<div style="width:100%;padding:0 15mm;box-sizing:border-box;'
                f'font-family:{hdr_font};font-size:7.5pt;color:#64748b;'
                f'display:flex;justify-content:space-between;'
                f'border-top:0.5px solid #e2e8f0;padding-top:3px;">'
                f'<span>Prepared by: MIS Group</span>'
                f'<span>Page <span class="pageNumber"></span>'
                f' of <span class="totalPages"></span></span>'
                f'</div>'
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


async def build_pdf_response(request: PDFRequest, pages_override: list = None, page_layouts: dict = None, font_config=None) -> StreamingResponse:
    import asyncio
    import traceback as tb
    from jinja2 import Template
    from models import FontConfig

    try:
        from layout_loader import load_layout_config
        _layout_cfg = load_layout_config()
        _g = _layout_cfg["global"]

        vars = _resolve_month_vars(request.month)

        _cfg_fc = FontConfig(
            family=       _g.get("font_family",  "IBM Plex Sans"),
            td_size=      _g.get("td_size",       9.5),
            th_size=      _g.get("th_size",       9.0),
            title_size=   _g.get("title_size",   13.0),
            heading_size= _g.get("heading_size", 10.5),
        )
        fc = font_config or request.font_config or _cfg_fc
        _catalog_entry = FONT_CATALOG.get(fc.family, FONT_CATALOG[_DEFAULT_FONT])
        _font_imports   = _catalog_entry["import"]
        _font_family_css = f"'{fc.family}', Arial, Helvetica, sans-serif"
        _mono_family_css = f"'{_catalog_entry['mono']}', 'Courier New', monospace"

        total_report_pages = len(request.pages)

        flat_pages = []
        src = pages_override if pages_override is not None else [p_data.dict() for p_data in request.pages]
        for p in src:
            if p.get("type") == "page4_table":
                p["rows"] = _group_page4_rows(p.get("rows", []))
            if p.get("type") == "summary" and p.get("chart_data"):
                from page_techno import generate_summary_chart_html
                p["_chart_html"] = generate_summary_chart_html(p["chart_data"])
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

        _merged_page_layouts = {
            **_layout_cfg["pages"],
            **(page_layouts or {}),
            **(request.page_layouts or {}),
        }

        rendered_html = Template(HTML_TEMPLATE).render(
            month=request.month,
            pages=pages_to_render,
            total_report_pages=total_report_pages,
            page_layouts=_merged_page_layouts,
            # Typography variables
            font_imports=_font_imports,
            font_family_css=_font_family_css,
            mono_family_css=_mono_family_css,
            td_size=fc.td_size,
            th_size=fc.th_size,
            title_size=fc.title_size,
            heading_size=fc.heading_size,
            **vars,
        )

        # Run sync Playwright in a thread so it doesn't fight the asyncio event loop
        loop = asyncio.get_event_loop()
        pdf_bytes = await loop.run_in_executor(None, _render_pdf_sync, rendered_html, fc.family)

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
