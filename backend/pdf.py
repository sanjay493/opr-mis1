import io
import os
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from jinja2 import Environment, FileSystemLoader
from models import PDFRequest

_TMPL_DIR = os.path.join(os.path.dirname(__file__), 'page_templates')
_jinja_env = Environment(loader=FileSystemLoader(_TMPL_DIR), autoescape=False)


def _split_label(label, threshold: int = 20, tail_scale: float = 0.82) -> str:
    """Keep a long, single-line label from wrapping (or getting silently
    clipped by overflow:hidden) by shrinking everything after the first word.
    Short labels pass through unchanged; a single very long word with no
    space shrinks in its entirety since there's nothing else to split."""
    label = "" if label is None else str(label)
    if len(label) <= threshold:
        return label
    first, _, rest = label.partition(" ")
    if not rest:
        return f'<span style="font-size:{tail_scale}em;">{label}</span>'
    return f'{first} <span style="font-size:{tail_scale}em;">{rest}</span>'


_jinja_env.filters['split_label'] = _split_label


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


def _render_pdf_sync(front_html: str, main_html: str, font_family: str = _DEFAULT_FONT, report_month: str = "") -> bytes:
    """Run Playwright synchronously (called from a thread to avoid event-loop conflicts).

    Rendered as two separate PDF documents so the header/footer (with page
    numbering) only appears from page 3 onward: `front_html` (cover + index,
    pages 1-2) is rendered without header/footer, and `main_html` (page 3+) is
    rendered with header/footer, which makes Chromium's own pageNumber/totalPages
    counters naturally read "Page 1 of N" for the first page of the main content.
    The two PDFs are then merged into one.
    """
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter
    hdr_font = f"'{font_family}',Arial,sans-serif"
    margin = {"top": "12mm", "right": "15mm", "bottom": "12mm", "left": "15mm"}

    writer = PdfWriter()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        if front_html:
            page = browser.new_page()
            page.set_content(front_html, wait_until="domcontentloaded")
            front_bytes = page.pdf(
                format="A4",
                print_background=True,
                display_header_footer=False,
                margin=margin,
            )
            page.close()
            for p in PdfReader(io.BytesIO(front_bytes)).pages:
                writer.add_page(p)

        if main_html:
            page = browser.new_page()
            page.set_content(main_html, wait_until="domcontentloaded")
            main_bytes = page.pdf(
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template=(
                    f'<div style="width:100%;padding:0 15mm;box-sizing:border-box;'
                    f'font-family:{hdr_font};font-size:7.5pt;font-weight:500;'
                    f'color:#64748b;text-align:center;border-bottom:0.5px solid #e2e8f0;'
                    f'padding-bottom:3px;">'
                    f'OMI - {report_month}'
                    f'</div>'
                ),
                footer_template=(
                    f'<div style="width:100%;padding:0 15mm;box-sizing:border-box;'
                    f'font-family:{hdr_font};font-size:7.5pt;color:#64748b;'
                    f'display:flex;justify-content:space-between;'
                    f'border-top:0.5px solid #e2e8f0;padding-top:3px;">'
                    f'<span>figures are provision</span>'
                    f'<span>MIS Operations</span>'
                    f'<span>OMI - {report_month}</span>'
                    f'<span>for internal circulation only</span>'
                    f'<span>Page <span class="pageNumber"></span>'
                    f' of <span class="totalPages"></span></span>'
                    f'</div>'
                ),
                margin=margin,
            )
            page.close()
            for p in PdfReader(io.BytesIO(main_bytes)).pages:
                writer.add_page(p)

        browser.close()

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


async def build_pdf_response(request: PDFRequest, pages_override: list = None, page_layouts: dict = None, font_config=None) -> StreamingResponse:
    import asyncio
    import traceback as tb
    from models import FontConfig

    try:
        from layout_loader import load_layout_config
        from colors_loader import load_colors_config
        _layout_cfg = load_layout_config()
        _colors = load_colors_config()
        _g = _layout_cfg["global"]
        _g_table = _g.get("table", {})

        vars = _resolve_month_vars(request.month)

        _cfg_fc = FontConfig(
            family=       _g.get("font_family",  "IBM Plex Sans"),
            td_size=      _g_table.get("td",      11.5),  # Increased from 9.5 for better readability
            th_size=      _g_table.get("th",      11.0),  # Increased from 9.0 for better readability
            title_size=   _g.get("title_size",   15.0),  # Increased from 13.0 for better readability
            heading_size= _g.get("heading_size", 12.0),  # Increased from 10.5 for consistency
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

        # Cover (page 1) + index (page 2) are rendered as a separate document
        # without header/footer; page 3 onward gets the header/footer, so
        # Chromium's own page-numbering naturally starts at "Page 1 of N" there.
        front_pages = [p for p in pages_to_render if p.get("page", 0) <= 2]
        main_pages = [p for p in pages_to_render if p.get("page", 0) > 2]

        _template = _jinja_env.get_template('main.html')
        _render_kwargs = dict(
            month=request.month,
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
            colors=_colors,
            **vars,
        )
        front_html = _template.render(pages=front_pages, **_render_kwargs) if front_pages else ""
        main_html = _template.render(pages=main_pages, **_render_kwargs) if main_pages else ""

        # Run sync Playwright in a thread so it doesn't fight the asyncio event loop
        loop = asyncio.get_event_loop()
        report_month_display = f"{vars['m_name']} {vars['y_str']}"
        pdf_bytes = await loop.run_in_executor(None, _render_pdf_sync, front_html, main_html, fc.family, report_month_display)

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
