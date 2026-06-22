import io
import os
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from jinja2 import Environment, FileSystemLoader
from models import PDFRequest

_TMPL_DIR = os.path.join(os.path.dirname(__file__), 'page_templates')
_jinja_env = Environment(loader=FileSystemLoader(_TMPL_DIR), autoescape=False)


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
                "top": "12mm",
                "right": "15mm",
                "bottom": "12mm",
                "left": "15mm",
            },
        )
        browser.close()
    return pdf_bytes


async def build_pdf_response(request: PDFRequest, pages_override: list = None, page_layouts: dict = None, font_config=None) -> StreamingResponse:
    import asyncio
    import traceback as tb
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

        rendered_html = _jinja_env.get_template('main.html').render(
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
