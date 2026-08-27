import functools
import io
import os
from fastapi import HTTPException
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
from models import PDFRequest
from report_utils import dept_badge_group

_TMPL_DIR = os.path.join(os.path.dirname(__file__), 'page_templates')
_jinja_env = Environment(loader=FileSystemLoader(_TMPL_DIR), autoescape=False)


def _split_label(label, threshold: int = 20, tail_scale: float = 0.82) -> str:
    """Keep a long, single-line label from wrapping (or getting silently
    clipped by overflow:hidden) by shrinking everything after the first word.
    Short labels pass through unchanged. A label with no space to split on
    (e.g. slash-joined grade names like "MMn/HMn/.../Cr5") is left at normal
    font size — there's nothing to split, so shrinking the whole label just
    made it harder to read without solving the overflow risk anyway."""
    label = "" if label is None else str(label)
    if len(label) <= threshold:
        return label
    first, _, rest = label.partition(" ")
    if not rest:
        return label
    return f'{first} <span style="font-size:{tail_scale}em;">{rest}</span>'


_jinja_env.filters['split_label'] = _split_label

# The print margin main_html (pages 3+) is always rendered with — a single
# source of truth shared by every page.pdf() call for it, including the
# trend-table rowspan "probe" print in _make_trend_split_hook, which must
# use this exact same margin so its measured page breaks match what the
# final page.pdf() call actually produces.
_MAIN_MARGIN = {"top": "10mm", "right": "15mm", "bottom": "9mm", "left": "15mm"}
# The Index (page 2) is rendered without a Chromium header/footer, so it
# doesn't need the ~9-10mm the main pages reserve for those bars — a tighter
# top/bottom keeps the (now longer) contents list on one page.
_FRONT_MARGIN = {"top": "8mm", "right": "13mm", "bottom": "8mm", "left": "13mm"}


def _pgclass(page_num) -> str:
    """CSS-safe page-number class suffix: "29" -> "29", 29.5 -> "29-5".
    Sentinel float page ids (2.5, 3.5, 29.5, ...) rendered straight into a
    class name (pg-29.5) parse as TWO chained class selectors in any CSS
    rule that targets it (.pg-29.5 td means "class pg-29 AND class 5" —
    never matches a real element, which only carries the single class
    "pg-29.5") — every .pg-{{ page.page }} rule in main.html/
    trend_section.html silently never applied to any float-numbered page.
    Used for BOTH the div's own class and every selector that targets it,
    so they always agree."""
    return str(page_num).replace(".", "-")


_jinja_env.filters['pgclass'] = _pgclass


# Self-hosted from Google Fonts (Latin subset only) rather than the previous
# @import url('https://fonts.googleapis.com/...') — that hit the network on
# every Chromium launch (see _measure_page3_overflow) even though
# request.font_config is always
# None in practice today (backend/main.py always calls build_pdf_response
# with font_config=None, so _DEFAULT_FONT/layout_config.json's "Arial
# Narrow" is what actually renders) — but the picker exists in the schema,
# so this keeps it offline-capable if it's ever wired up. Files + source
# URLs are in backend/fonts/manifest.json.
_FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')

_FONT_SLUGS = {
    "IBM Plex Sans": "ibm-plex-sans", "IBM Plex Mono": "ibm-plex-mono",
    "Source Sans 3": "source-sans-3", "Source Code Pro": "source-code-pro",
    "Roboto": "roboto", "Roboto Mono": "roboto-mono",
    "Noto Sans": "noto-sans", "Noto Sans Mono": "noto-sans-mono",
    "Lato": "lato",
}


@functools.lru_cache(maxsize=None)
def _local_font_face_css(family: str) -> str:
    """@font-face rules for one font family, built from its locally-cached
    woff2 files (base64-embedded so they load with no filesystem/network
    access from within Playwright's set_content(), which has no base URL to
    resolve a relative/file:// path against)."""
    import base64
    import glob

    slug = _FONT_SLUGS[family]
    blocks = []
    for path in sorted(glob.glob(os.path.join(_FONTS_DIR, slug, f"{slug}-*.woff2"))):
        name = os.path.splitext(os.path.basename(path))[0]
        weight, style = name.rsplit("-", 2)[-2:]
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        blocks.append(
            # font-display: block (not swap) — this is a one-shot captured
            # PDF render, not a live page, so there's no reason to ever
            # paint with a fallback font: `swap` shows fallback text
            # immediately and reflows once the embedded font decodes, and
            # that swap-triggered reflow is exactly the kind of thing that
            # can make the trend-page-break measurement pass and the final
            # render pass (two separate page.pdf() calls — see _render_pdf's
            # own "two separate renders... can land text with slightly
            # different fallback/final font metrics" comment) disagree on a
            # row's height by a hair, silently shifting a page break by one
            # row without leaving anything as visible as a missing marker.
            # `block` paints invisible text until the (already base64-
            # embedded, so near-instant) font is ready, so both passes lay
            # out with the real font's metrics from the start.
            f"@font-face {{ font-family: '{family}'; font-style: {style}; "
            f"font-weight: {weight}; font-display: block; "
            f"src: url(data:font/woff2;base64,{b64}) format('woff2'); }}"
        )
    return "\n".join(blocks)


def _catalog_import(sans_family: str, mono_family: str) -> str:
    return _local_font_face_css(sans_family) + "\n" + _local_font_face_css(mono_family)


FONT_CATALOG = {
    "IBM Plex Sans": {"import": _catalog_import("IBM Plex Sans", "IBM Plex Mono"), "mono": "IBM Plex Mono"},
    "Source Sans 3": {"import": _catalog_import("Source Sans 3", "Source Code Pro"), "mono": "Source Code Pro"},
    "Roboto":        {"import": _catalog_import("Roboto", "Roboto Mono"), "mono": "Roboto Mono"},
    "Noto Sans":     {"import": _catalog_import("Noto Sans", "Noto Sans Mono"), "mono": "Noto Sans Mono"},
    "Lato":          {"import": _catalog_import("Lato", "Roboto Mono"), "mono": "Roboto Mono"},
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


# Same 9-slot categorical palette as frontend/src/app/globals.css's
# .dept-badge.grp-N — keep both in sync; never reorder without re-validating
# (dataviz skill six-check gate).
_BADGE_COLORS = {
    1: ("#2a78d6", "#ffffff"),  # blue    — Summary (3-6)
    2: ("#eb6834", "#0b0b0b"),  # orange  — Trends (7-12)
    3: ("#1baf7a", "#0b0b0b"),  # aqua    — Concast/Process (13-14)
    4: ("#eda100", "#0b0b0b"),  # yellow  — Category/Segment (15-18)
    5: ("#e87ba4", "#0b0b0b"),  # magenta — Special Steel (19-24)
    6: ("#008300", "#ffffff"),  # green   — Stock/IPT (25-26)
    7: ("#4a3aa7", "#ffffff"),  # violet  — Techno Params (27-30)
    8: ("#e34948", "#0b0b0b"),  # red     — Mill Techno (31-35)
    9: ("#0a9698", "#0b0b0b"),  # teal    — Capital Repair (36-40)
}


def _dept_badge_overlay_html(side: str, group: int, font_family: str) -> str:
    """A minimal, transparent-background full-page document containing only
    the corner badge, positioned at true (0,0) — used to stamp the badge
    directly onto an already-rendered page via pypdf, since Chromium clips
    anything the *main* document positions outside its printable area (see
    _apply_dept_badges)."""
    bg, fg = _BADGE_COLORS[group]
    if side == "right":
        side_css = "right:0; border-radius:999px 0 0 999px; padding-left:12px; padding-right:7px;"
    else:
        side_css = "left:0; border-radius:0 999px 999px 0; padding-left:7px; padding-right:12px;"
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        'html,body{margin:0;padding:0;background:transparent;}'
        '.dept-badge{position:absolute;top:0;' + side_css +
        f"font-family:'{font_family}',Arial,sans-serif;"
        'font-size:6.5pt;font-weight:700;letter-spacing:0.04em;'
        'text-transform:uppercase;white-space:nowrap;line-height:1;'
        'padding-top:4px;padding-bottom:4px;'
        f'background:{bg};color:{fg};'
        '}</style></head><body>'
        '<div class="dept-badge">Operations Directorate</div>'
        '</body></html>'
    )


def _apply_dept_badges(main_bytes: bytes, dept_badges: dict, browser, font_family: str) -> bytes:
    """Post-render overlay pass: stamps each page's corner badge at the TRUE
    physical page corner. Chromium's print-to-PDF hard-clips any content the
    main document positions outside its printable area (Playwright reserves
    a fixed margin band for header/footer — verified empirically that
    content pushed past it just disappears), so the badge can't reach the
    corner the way the live preview does (there, the page container IS the
    full physical page). Stamping it on afterward, as its own tiny
    zero-margin PDF merged onto each target page, sidesteps that clip
    entirely.

    dept_badges: {report_page_number: {"group": int, "side": "left"|"right"}}
    (see report_utils.assign_dept_badges — the "side" value here is never
    actually read; every page's side is recomputed below from its own true
    physical position instead). Physical page positions are found via
    the invisible @@PGSTART_N@@ markers main.html/trend_section.html emit at
    the start of every page, rather than assumed 1:1 with dept_badges' keys —
    the trend pages (7-12) can expand into a different number of physical
    pages than logical entries depending on row count, so a fixed offset
    would drift out of sync there. The side actually stamped is recomputed
    from each physical page's own position (matching the footer's "Page X of
    N"), not copied from the logical entry, so left/right alternation stays
    correct across a split section's continuation pages too.
    """
    import re
    from pypdf import PdfReader, PdfWriter

    if not dept_badges:
        return main_bytes

    reader = PdfReader(io.BytesIO(main_bytes))
    n = len(reader.pages)

    marker_re = re.compile(r"@@PGSTART_(\d+(?:\.\d+)?)@@")
    start_of = {}
    for k in range(n):
        text = reader.pages[k].extract_text() or ""
        for m in marker_re.finditer(text):
            rp = float(m.group(1))
            if rp == int(rp):
                rp = int(rp)
            if rp not in start_of:
                start_of[rp] = k

    if not start_of:
        return main_bytes

    ordered = sorted(start_of.items(), key=lambda kv: kv[1])  # by physical index
    group_of_physical = {}
    for idx, (report_pg, start_k) in enumerate(ordered):
        end_k = ordered[idx + 1][1] - 1 if idx + 1 < len(ordered) else n - 1
        badge = dept_badges.get(report_pg)
        if not badge:
            continue
        for k in range(start_k, end_k + 1):
            group_of_physical[k] = badge["group"]

    if not group_of_physical:
        return main_bytes

    overlay_cache = {}
    writer = PdfWriter()
    for k in range(n):
        page = reader.pages[k]
        group = group_of_physical.get(k)
        if group is not None:
            side = "right" if (k + 1) % 2 == 1 else "left"
            w_pt, h_pt = float(page.mediabox.width), float(page.mediabox.height)
            cache_key = (side, group, round(w_pt), round(h_pt))
            overlay_page = overlay_cache.get(cache_key)
            if overlay_page is None:
                html = _dept_badge_overlay_html(side, group, font_family)
                op = browser.new_page()
                op.set_content(html, wait_until="domcontentloaded")
                badge_pdf = op.pdf(
                    width=f"{w_pt * 25.4 / 72}mm", height=f"{h_pt * 25.4 / 72}mm",
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    print_background=True,
                )
                op.close()
                overlay_page = PdfReader(io.BytesIO(badge_pdf)).pages[0]
                overlay_cache[cache_key] = overlay_page
            page.merge_page(overlay_page)
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _render_landscape_page_pdf(browser, html: str, font_family: str) -> bytes:
    """Render one page's HTML standalone at genuine A4-landscape physical
    dimensions (297x210mm), for a page (e.g. Large BFs) too wide for the
    fixed A4-portrait `format="A4"` every other main-content page shares in
    one combined page.pdf() call — Chromium's page.pdf() `format`/`width`/
    `height` are fixed per call and always win over any @page CSS `size`
    rule (see _render_pdf's docstring re: margin), so genuine landscape
    needs its own separate call, spliced into the final document by
    _generate_pdf_sync. No Chromium-native header/footer here
    (display_header_footer=False) — _stamp_main_page_numbers draws a
    matching one afterward for every main-content page uniformly, since
    Chromium's own pageNumber/totalPages counters reset to 1/1 for this
    call and can't be offset to match its true position once spliced into
    the middle of the full document."""
    page = browser.new_page()
    page.set_content(html, wait_until="domcontentloaded")
    page.evaluate("document.fonts.ready")
    pdf_bytes = page.pdf(
        format="A4",
        landscape=True,
        print_background=True,
        display_header_footer=False,
        margin={"top": "12mm", "right": "10mm", "bottom": "10mm", "left": "10mm"},
    )
    page.close()
    return pdf_bytes


def _main_header_footer_overlay_html(font_family: str, report_month: str, page_num: int, total_pages: int,
                                      margin_side: str = "15mm") -> str:
    """A minimal, transparent-background full-page document containing a
    header bar (top) and footer bar (bottom) — visually identical to
    _render_pdf's own header_template/footer_template, but with `page_num`/
    `total_pages` baked in as plain Python values instead of Chromium's
    auto-computed pageNumber/totalPages classes. Used by
    _stamp_main_page_numbers to give every main-content page a CORRECT
    "Page N of TOTAL" once a genuinely-landscape page (see
    _render_landscape_page_pdf) has been spliced into the middle of the
    sequence: Chromium's own counters are per-page.pdf()-call and can't be
    offset, so once the sequence is assembled from more than one call, only
    a post-render, Python-computed stamp can get every page's number right."""
    hdr_font = f"'{font_family}',Arial,sans-serif"
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        'html,body{margin:0;padding:0;background:transparent;}'
        '</style></head><body>'
        f'<div style="position:fixed;top:0;left:0;right:0;padding:3mm {margin_side} 0;'
        f'box-sizing:border-box;font-family:{hdr_font};font-size:7.5pt;font-weight:500;'
        f'color:#64748b;text-align:center;border-bottom:0.5px solid #e2e8f0;'
        f'padding-bottom:3px;">OMI - {report_month}</div>'
        f'<div style="position:fixed;bottom:0;left:0;right:0;padding:0 {margin_side} 2.5mm;'
        f'box-sizing:border-box;font-family:{hdr_font};font-size:7.5pt;color:#64748b;'
        f'display:flex;justify-content:space-between;'
        f'border-top:0.5px solid #e2e8f0;padding-top:3px;">'
        f'<span>figures are provision</span>'
        f'<span>MIS Operations</span>'
        f'<span>OMI - {report_month}</span>'
        f'<span>for internal circulation only</span>'
        f'<span>Page {page_num} of {total_pages}</span>'
        f'</div></body></html>'
    )


def _stamp_main_page_numbers(pdf_bytes: bytes, browser, font_family: str, report_month: str,
                              main_start: int, main_count: int) -> bytes:
    """Post-render overlay pass (same merge_page technique as
    _apply_dept_badges): draws a correct, Python-computed header+footer
    (see _main_header_footer_overlay_html) onto every page in the
    [main_start, main_start+main_count) physical range — the pages that
    used to get Chromium's own auto pageNumber/totalPages footer from
    _render_pdf's single main_html call, before a spliced-in landscape page
    (_render_landscape_page_pdf) made a single call's auto-numbering
    impossible to keep correct across the whole range. Cover/Index pages
    outside this range are untouched (they carry no footer either way)."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    overlay_cache = {}
    for k in range(len(reader.pages)):
        page = reader.pages[k]
        if main_start <= k < main_start + main_count:
            page_num = k - main_start + 1
            w_pt, h_pt = float(page.mediabox.width), float(page.mediabox.height)
            cache_key = (page_num, main_count, round(w_pt), round(h_pt))
            overlay_page = overlay_cache.get(cache_key)
            if overlay_page is None:
                margin_side = "15mm" if round(w_pt) < round(h_pt) else "10mm"
                html = _main_header_footer_overlay_html(font_family, report_month, page_num, main_count, margin_side)
                op = browser.new_page()
                op.set_content(html, wait_until="domcontentloaded")
                stamp_pdf = op.pdf(
                    width=f"{w_pt * 25.4 / 72}mm", height=f"{h_pt * 25.4 / 72}mm",
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    print_background=True,
                )
                op.close()
                overlay_page = PdfReader(io.BytesIO(stamp_pdf)).pages[0]
                overlay_cache[cache_key] = overlay_page
            page.merge_page(overlay_page)
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _render_pdf(browser, front_html: str, main_html: str, font_family: str = _DEFAULT_FONT, report_month: str = "",
                 dept_badges: dict = None, cover_html: str = "", main_header_footer: bool = True,
                 main_pre_pdf_hook=None) -> bytes:
    """Render one PDF using an already-launched Chromium `browser`. Callers
    (the page3-overflow measurement pass and the final render, see
    _generate_pdf_sync) all share a single browser instance for the whole
    request instead of each launching/closing its own Chromium process —
    several passes per request previously meant several full browser
    launches, which is pure overhead since it's the same renderer doing the
    same job each time.

    Rendered as up to three separate PDF documents, merged together:
    `cover_html` (page 1 alone, if present) is rendered with a zero margin
    so its full-bleed background photo actually reaches the physical page
    edge; `front_html` (page 2, Index) is rendered without header/footer at
    the normal margin; `main_html` (page 3+) is rendered with header/footer
    at the normal margin, which makes Chromium's own pageNumber/totalPages
    counters naturally read "Page 1 of N" for the first page of the main
    content. main.html's own CSS already declares `@page cover-layout {
    margin: 0 }` for the cover — but Playwright/Chromium's page.pdf()
    `margin` option always overrides any `@page` margin from the page's own
    CSS, so the cover was silently still getting the standard 12mm/15mm
    margin (a visible gap along the top/side of the full-bleed photo)
    unless it gets its own page.pdf() call with an explicit zero margin.

    main_pre_pdf_hook(page), if given, runs on the live main_html page right
    after it settles (content loaded, fonts ready) and right before
    page.pdf() prints it — see _make_trend_split_hook, which uses this to
    measure real row geometry and swap in a corrected re-render, all within
    this same page object, before it gets printed.
    """
    from pypdf import PdfReader, PdfWriter
    hdr_font = f"'{font_family}',Arial,sans-serif"
    margin = _MAIN_MARGIN
    zero_margin = {"top": "0", "right": "0", "bottom": "0", "left": "0"}

    writer = PdfWriter()

    if cover_html:
        page = browser.new_page()
        page.set_content(cover_html, wait_until="domcontentloaded")
        page.evaluate("document.fonts.ready")
        cover_bytes = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=False,
            margin=zero_margin,
        )
        page.close()
        for p in PdfReader(io.BytesIO(cover_bytes)).pages:
            writer.add_page(p)

    if front_html:
        page = browser.new_page()
        page.set_content(front_html, wait_until="domcontentloaded")
        page.evaluate("document.fonts.ready")
        front_bytes = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=False,
            margin=_FRONT_MARGIN,
        )
        page.close()
        for p in PdfReader(io.BytesIO(front_bytes)).pages:
            writer.add_page(p)

    if main_html:
        page = browser.new_page()
        page.set_content(main_html, wait_until="domcontentloaded")
        # Web fonts load asynchronously; without waiting for them, the
        # geometry main_pre_pdf_hook measures below could land text with
        # slightly different fallback/final font metrics than what actually
        # prints, shifting row heights just enough to move the real page
        # break away from the one measured.
        page.evaluate("document.fonts.ready")
        if main_pre_pdf_hook:
            corrected_html = main_pre_pdf_hook(page)
            if corrected_html:
                page.set_content(corrected_html, wait_until="domcontentloaded")
                page.evaluate("document.fonts.ready")
        main_bytes = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=main_header_footer,
            header_template=(
                f'<div style="width:100%;padding:0 15mm;box-sizing:border-box;'
                f'font-family:{hdr_font};font-size:7.5pt;font-weight:500;'
                f'color:#64748b;text-align:center;border-bottom:0.5px solid #e2e8f0;'
                f'padding-bottom:3px;">'
                f'OMI - {report_month}'
                f'</div>'
            ) if main_header_footer else '<span></span>',
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
            ) if main_header_footer else '<span></span>',
            margin=margin,
        )
        page.close()
        if dept_badges:
            main_bytes = _apply_dept_badges(main_bytes, dept_badges, browser, font_family)
        for p in PdfReader(io.BytesIO(main_bytes)).pages:
            writer.add_page(p)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _measure_page3_overflow(browser, main_pages: list, template, render_kwargs: dict,
                             font_family: str, report_month: str) -> bool:
    """Render the *entire* main document (rendering page 3 in isolation was
    tried first and does NOT reliably reproduce the break it gets embedded
    after pages 1-2; verified
    empirically the same way that function's own docstring already found
    for trend pages, root cause equally unpinned) and report whether page 3
    spills onto a 2nd physical page for this month's content. Narrative
    length, highlights count, and which TE parameters have values all vary
    month to month, so this is checked per-render rather than assumed.

    Detected via the @@PGSTART_N@@ markers every page emits (see main.html):
    if the very next page after page 3 lands more than one physical page
    after page 3's own start, page 3 must have consumed an extra page.

    Only renders main_pages up through the page *after* page 3 — pagination
    flows top-to-bottom, so nothing beyond that can move page 3's own break
    (unlike the isolation this docstring's first paragraph rules out, which
    dropped content *before* page 3; here everything before and including
    the one page needed for the measurement stays intact). For a full
    ~40-page report this skips laying out/printing the ~35 trailing pages
    that have no bearing on the answer."""
    import io as _io
    from pypdf import PdfReader

    idx3 = next((i for i, p in enumerate(main_pages) if p.get("page") == 3), None)
    if idx3 is None:
        return False
    next_marker = None
    measured_pages = main_pages[:idx3 + 1]
    if idx3 + 1 < len(main_pages):
        next_marker = f"@@PGSTART_{main_pages[idx3 + 1].get('page')}@@"
        measured_pages = main_pages[:idx3 + 2]

    html = template.render(pages=measured_pages, **render_kwargs)
    pdf_bytes = _render_pdf(browser, "", html, font_family, report_month)
    reader = PdfReader(_io.BytesIO(pdf_bytes))

    p3_physical = next_physical = None
    for pi, pg in enumerate(reader.pages):
        text = pg.extract_text() or ""
        if p3_physical is None and "@@PGSTART_3@@" in text:
            p3_physical = pi
        if next_marker and next_physical is None and next_marker in text:
            next_physical = pi
    if p3_physical is None or next_physical is None:
        # Can't determine (page 3 is the last page in this request, or a
        # marker wasn't found) — don't guess, leave the default layout.
        return False
    return (next_physical - p3_physical) > 1


# Cap on _make_trend_split_hook's probe/correct/re-probe loop — each pass is
# one extra full page.pdf() call, so this bounds worst-case cost; real-world
# corrections have been observed to stabilize in 2-3 passes (see that
# function's own docstring).
_MAX_TREND_SPLIT_PASSES = 5


# Reduced top/bottom margin candidates tried by _pick_trend_margins against
# the trend section's configured defaults (layout_config.json's
# "7-13".marginTop/marginBottom, currently 7mm/5mm) — whichever combination
# leaves the fewest orphaned split segments (see _TREND_MIN_SPLIT_SEGMENT_
# ROWS below), then the fewest split plant groups overall, wins. Neither
# floor is ever crossed: any tighter risks crowding the printed header/
# footer.
_TREND_MIN_TOP_MARGIN_MM = 4
_TREND_MIN_BOTTOM_MARGIN_MM = 2

# A split group must leave at least this many rows on BOTH sides of any
# page break — fewer reads as an orphan (a lone plant-label letter or two
# stranded at the top or bottom of a page). 3 is the smallest acceptable
# segment (per direct instruction). Two mechanisms use it: _pick_trend_
# margins treats any smaller segment as a heavy penalty when choosing
# margins, and _enforce_trend_min_segments then hard-guarantees it by
# injecting a forced page break (row['break_before']) wherever the probe
# print still shows a shorter segment.
_TREND_MIN_SPLIT_SEGMENT_ROWS = 3


def _trend_group_page_spans(trend_pages: list, page_texts: list) -> list:
    """For every plant/SAIL group in every item on every trend_section page,
    resolve each of its rows' real physical page from its @@TROW_item_row@@
    marker (same lookup _make_trend_split_hook's own loop does) and return
    one (item_idx, plant, distinct_page_count) tuple per *complete* group
    (every row's marker found) — incomplete groups are omitted rather than
    guessed at. Read-only: unlike _apply_trend_page_splits this never
    touches rowspan_start/plant_row_count, so it's safe to call while
    comparing candidate margins before any row has been corrected."""
    spans = []
    for tp in trend_pages:
        for ii, it in enumerate(tp.get("items", [])):
            rows = it.get("rows", [])
            n = len(rows)
            i = 0
            while i < n:
                plant = rows[i]["plant"]
                j = i
                while j < n and rows[j]["plant"] == plant:
                    j += 1
                pages_seen = set()
                complete = True
                for k in range(i, j):
                    marker = f"@@TROW_{ii}_{k}@@"
                    found = next((pno for pno, text in enumerate(page_texts) if marker in text), None)
                    if found is None:
                        complete = False
                        break
                    pages_seen.add(found)
                if complete:
                    spans.append((ii, plant, len(pages_seen)))
                i = j
    return spans


def _trend_group_segment_sizes(trend_pages: list, page_texts: list) -> list:
    """Like _trend_group_page_spans but, for every complete plant/SAIL group
    that lands on more than one physical page, returns its ordered per-page
    row counts (e.g. [9, 3] for a 12-row group split 9-then-3) instead of
    just how many distinct pages it touched. _trend_group_page_spans's bare
    page count can't tell a 9/3 split (an orphaned 3-row continuation) apart
    from a 6/6 split (a clean one) — both are "2 pages" — so
    _pick_trend_margins uses this instead to penalize the former."""
    out = []
    for tp in trend_pages:
        for ii, it in enumerate(tp.get("items", [])):
            rows = it.get("rows", [])
            n = len(rows)
            i = 0
            while i < n:
                plant = rows[i]["plant"]
                j = i
                while j < n and rows[j]["plant"] == plant:
                    j += 1
                pages_for_rows = []
                complete = True
                for k in range(i, j):
                    marker = f"@@TROW_{ii}_{k}@@"
                    found = next((pno for pno, text in enumerate(page_texts) if marker in text), None)
                    if found is None:
                        complete = False
                        break
                    pages_for_rows.append(found)
                if complete and pages_for_rows:
                    segs = [1]
                    for prev_pg, cur_pg in zip(pages_for_rows, pages_for_rows[1:]):
                        if cur_pg == prev_pg:
                            segs[-1] += 1
                        else:
                            segs.append(1)
                    if len(segs) > 1:
                        out.append((ii, plant, segs))
                i = j
    return out


def _trend_orphan_penalty(segment_sizes: list) -> int:
    """Total shortfall below _TREND_MIN_SPLIT_SEGMENT_ROWS across every
    segment of every split group — 0 once no split leaves a continuation
    (on either side of the break) shorter than the minimum."""
    return sum(
        max(0, _TREND_MIN_SPLIT_SEGMENT_ROWS - size)
        for _, _, segs in segment_sizes
        for size in segs
    )


def _pick_trend_margins(page, template, pages_list: list, render_kwargs: dict, margin: dict,
                         trend_pages: list) -> None:
    """Tries shrinking the trend section's own configured top/bottom margins
    (page_layouts["<first_pg>"]["marginTop"]/["marginBottom"], see
    trend_section.html's inline padding) toward _TREND_MIN_TOP_MARGIN_MM /
    _TREND_MIN_BOTTOM_MARGIN_MM and keeps whichever (top, bottom)
    combination scores best — first by fewest orphaned split segments (a
    continuation shorter than _TREND_MIN_SPLIT_SEGMENT_ROWS rows, see
    _trend_orphan_penalty), then by fewest split plant groups overall (ties
    go to the combination with the larger margins, tried first). Mutates
    render_kwargs["page_layouts"] in place; _make_trend_split_hook runs its
    own probe/correct loop against whatever this picks. Only top/bottom are
    tuned (per direct request) — left/right stay at their configured
    values.

    This does NOT touch any row's rowspan_start/plant_row_count — it only
    measures, via _trend_group_page_spans/_trend_group_segment_sizes, how
    each candidate actually paginates. Whichever candidate wins still goes
    through the normal probe/correct/re-probe convergence afterward to get
    its rowspan boundaries right; this step only chooses which margins that
    convergence should run against."""
    from pypdf import PdfReader

    page_layouts = render_kwargs.setdefault("page_layouts", {})
    keys = [str(tp.get("page")) for tp in trend_pages]
    if not keys:
        return
    base = dict(page_layouts.get(keys[0], {}))
    default_top = base.get("marginTop", 7)
    default_bottom = base.get("marginBottom", 5)

    def _apply(top_mm, bottom_mm):
        for key in keys:
            entry = dict(page_layouts.get(key, {}))
            entry["marginTop"] = top_mm
            entry["marginBottom"] = bottom_mm
            page_layouts[key] = entry

    def _severity(top_mm, bottom_mm):
        _apply(top_mm, bottom_mm)
        html = template.render(pages=pages_list, **render_kwargs)
        page.set_content(html, wait_until="domcontentloaded")
        page.evaluate("document.fonts.ready")
        probe_bytes = page.pdf(
            format="A4", print_background=True, display_header_footer=False, margin=margin,
        )
        page_texts = [(p.extract_text() or "") for p in PdfReader(io.BytesIO(probe_bytes)).pages]
        spans = _trend_group_page_spans(trend_pages, page_texts)
        split_extra_pages = sum(count - 1 for _, _, count in spans if count > 1)
        orphan_penalty = _trend_orphan_penalty(_trend_group_segment_sizes(trend_pages, page_texts))
        return (orphan_penalty, split_extra_pages)

    best_margins = (default_top, default_bottom)
    best_severity = _severity(*best_margins)
    if best_severity == (0, 0):
        return  # nothing splits at the default margins -- page already reflects them

    top_floor = min(default_top, _TREND_MIN_TOP_MARGIN_MM)
    bottom_floor = min(default_bottom, _TREND_MIN_BOTTOM_MARGIN_MM)
    for candidate in ((default_top, bottom_floor), (top_floor, default_bottom), (top_floor, bottom_floor)):
        if candidate == best_margins or best_severity == (0, 0):
            continue
        severity = _severity(*candidate)
        if severity < best_severity:
            best_severity, best_margins = severity, candidate

    # Whichever candidate's _severity() call ran last is what `page`'s live
    # content currently reflects; re-render/set_content once more so it's
    # guaranteed in sync with the winning margins before the caller's own
    # probe/correct loop begins.
    _apply(*best_margins)
    html = template.render(pages=pages_list, **render_kwargs)
    page.set_content(html, wait_until="domcontentloaded")
    page.evaluate("document.fonts.ready")


def _trend_split_snapshot(trend_pages: list) -> tuple:
    """Cheap fingerprint of every row's current rowspan_start/plant_row_count
    /break_before across all trend_section pages, used by
    _make_trend_split_hook to detect when another probe-and-correct
    iteration would no longer change anything (see that function's docstring
    for why one iteration isn't always enough). break_before is included so
    a pass that only adds a forced page-break (see
    _enforce_trend_min_segments) still keeps the loop going."""
    out = []
    for tp in trend_pages:
        for it in tp.get("items", []):
            for row in it.get("rows", []):
                out.append((row.get("rowspan_start"), row.get("plant_row_count"),
                            row.get("break_before")))
    return tuple(out)


def _make_trend_split_hook(pages_list: list, template, render_kwargs: dict, margin: dict):
    """Builds a main_pre_pdf_hook (see _render_pdf) that measures and
    corrects trend-table rowspan splits in place on the live page about to
    be printed. Returns None (no hook needed) if pages_list has no
    trend_section page.

    Measures real physical pagination by actually printing the page (a
    "probe" PDF) and reading back each row's true page from its own text
    layer via a per-row @@TROW_item_row@@ marker (trend_section.html; same
    in-flow/near-zero-size/transparent .pg-badge-marker technique
    @@PGSTART_N@@ already relies on elsewhere in this file — see that
    class's own comment for why position:absolute and display:block were
    both rejected for it). This replaces an earlier design that tried to
    *arithmetically replicate* Chromium's print pagination from live
    (unpaginated, screen-rendered) row geometry: verified against the
    actual probe print, that arithmetic was demonstrably wrong for several
    plant groups (e.g. Sinter/DSP, Hot Metal/SAIL) — it estimated a page
    break partway through a group that, in the real print, never spilled
    onto a second page at all, so the corrected render still split the
    rowspan cell in two for no reason. Reading the break back from an
    actual print sidesteps needing to replicate Chromium's own
    layout/fragmentation math (subpixel rounding, orphan handling, etc.)
    at all.

    A still-earlier design already tried a two-render, marker-based
    approach and abandoned it as unreliable — but that one baked the
    per-row markers directly into the *visible* row labels of a *separate*
    measurement document, which could itself shift layout (or diverge
    between two nominally-identical renders) relative to the real final
    render. Here the marker is the same near-zero-size/transparent inline
    element the file already uses successfully for page-level markers, and
    the "probe" print is not a separate document — it is one extra
    page.pdf() call on this exact same live `page`/HTML.

    One probe-and-correct pass is NOT enough on its own: measured directly
    against a real corrected print, splitting a plant-label rowspan cell
    into several smaller `<td rowspan>` pieces does very occasionally
    change that cell's own row-height contribution after all (a short
    segment's stacked letters, e.g. "D<br>S<br>P", can be taller than that
    handful of rows' own natural height, forcing them slightly taller) —
    contrary to what an earlier version of this docstring assumed. That
    height nudge shifts everything below it, which can move a later
    group's real page break by a row or more, so a correction computed
    from a single probe can go stale the moment it's printed. Fixed here by
    looping: probe, correct, print again, and re-probe *that* corrected
    print — repeating until a probe's page_of stops changing anything
    (typically converges in 2-3 rounds), capped at _MAX_TREND_SPLIT_PASSES
    so a pathological oscillation can't loop forever; whatever the last
    pass computed is used either way.

    Before that loop starts, _pick_trend_margins gets one shot at shrinking
    the section's own configured top/bottom margins (down to
    _TREND_MIN_TOP_MARGIN_MM / _TREND_MIN_BOTTOM_MARGIN_MM) if doing so
    measurably reduces orphaned split segments (a continuation shorter than
    _TREND_MIN_SPLIT_SEGMENT_ROWS rows) or how many plant groups end up
    split across a page break at all — fewer/shorter splits rather than
    just correctly-placed ones."""
    trend_pages = [p for p in pages_list if p.get("type") == "trend_section"]
    if not trend_pages:
        return None

    def hook(page):
        from pypdf import PdfReader

        _pick_trend_margins(page, template, pages_list, render_kwargs, margin, trend_pages)

        html = None
        prev_snapshot = _trend_split_snapshot(trend_pages)
        for _ in range(_MAX_TREND_SPLIT_PASSES):
            probe_bytes = page.pdf(
                format="A4", print_background=True, display_header_footer=False, margin=margin,
            )
            page_texts = [(p.extract_text() or "") for p in PdfReader(io.BytesIO(probe_bytes)).pages]

            for tp in trend_pages:
                page_of = {}
                for ii, it in enumerate(tp.get("items", [])):
                    for k in range(len(it.get("rows", []))):
                        marker = f"@@TROW_{ii}_{k}@@"
                        for pno, text in enumerate(page_texts):
                            if marker in text:
                                page_of[(ii, k)] = pno
                                break
                if page_of:
                    _apply_trend_page_splits(tp, page_of)
                    _enforce_trend_min_segments(tp, page_of)

            new_snapshot = _trend_split_snapshot(trend_pages)
            if new_snapshot == prev_snapshot:
                break
            prev_snapshot = new_snapshot
            html = template.render(pages=pages_list, **render_kwargs)
            page.set_content(html, wait_until="domcontentloaded")
            page.evaluate("document.fonts.ready")

        return html

    return hook


def _apply_trend_page_splits(trend_page: dict, page_of: dict) -> None:
    """Mutate trend_page's rows in place: within each plant/SAIL group,
    recompute rowspan_start/plant_row_count so the rowspan'd plant-name
    cell is split at every point page_of shows a page-index change — one
    merged, vertically-centered label per physical page instead of one for
    the whole group (which would leave later pages blank when the group
    spills over).

    page_of comes from _make_trend_split_hook's probe print, keyed by every
    row's real physical page as read back from its @@TROW_item_row@@ marker
    — a group with any row whose marker wasn't found (extraction hiccup)
    just falls back to its default single, un-split rowspan for the whole
    group rather than risk an incomplete/wrong split.

    Deliberately does NOT touch is_first_in_plant: that field marks the
    group's true first row (drives trend_section.html's thick .plant-first
    separator border, one per genuine plant change) and must stay put even
    when a page break lands mid-group — otherwise the row starting the new
    physical page was picking up a spurious thick line, indistinguishable
    from a real plant boundary, purely because it happened to fall at the
    top of a page."""
    for ii, it in enumerate(trend_page.get("items", [])):
        rows = it.get("rows", [])
        n = len(rows)
        page_for_row = [page_of.get((ii, k)) for k in range(n)]

        i = 0
        while i < n:
            plant = rows[i]["plant"]
            j = i
            while j < n and rows[j]["plant"] == plant:
                j += 1
            pages = page_for_row[i:j]
            if pages and all(p is not None for p in pages):
                seg_start = i
                for k in range(i, j):
                    if k > i and pages[k - i] != pages[k - i - 1]:
                        for m in range(seg_start, k):
                            rows[m]["rowspan_start"] = (m == seg_start)
                            rows[m]["plant_row_count"] = k - seg_start
                        seg_start = k
                for m in range(seg_start, j):
                    rows[m]["rowspan_start"] = (m == seg_start)
                    rows[m]["plant_row_count"] = j - seg_start
            i = j


def _enforce_trend_min_segments(trend_page: dict, page_of: dict) -> None:
    """Mutate trend_page's rows in place: set row['break_before'] on the
    fewest rows needed so that, wherever a plant/SAIL group splits across a
    physical page break, neither side of the break carries fewer than
    _TREND_MIN_SPLIT_SEGMENT_ROWS rows.

    page_of is the same probe-print row->page map _apply_trend_page_splits
    reads. This function only ever ADDS a forced break (never clears one)
    and every break it adds pushes rows forward onto a later page, so
    repeated passes converge: a group with no acceptable interior split just
    ends up wholly on the later page (any group here is at most ~12 rows, so
    it always fits once it starts at the top of a fresh page). break_before
    rides along in _trend_split_snapshot, so _make_trend_split_hook's loop
    re-probes after a pass that adds one, and its _MAX_TREND_SPLIT_PASSES
    cap bounds the worst case.

    Handled precisely for the common two-segment split; any 3+ segment
    group (would need a group taller than a whole page — not possible at
    these row counts, but guarded anyway) is just shoved wholesale onto the
    next page and re-probed."""
    MIN = _TREND_MIN_SPLIT_SEGMENT_ROWS
    for ii, it in enumerate(trend_page.get("items", [])):
        rows = it.get("rows", [])
        n = len(rows)
        page_for_row = [page_of.get((ii, k)) for k in range(n)]

        i = 0
        while i < n:
            plant = rows[i]["plant"]
            j = i
            while j < n and rows[j]["plant"] == plant:
                j += 1
            pages = page_for_row[i:j]
            if pages and all(p is not None for p in pages):
                # segment boundaries within [i, j): (start, end-exclusive)
                segs = []
                seg_start = i
                for k in range(i + 1, j):
                    if pages[k - i] != pages[k - i - 1]:
                        segs.append((seg_start, k))
                        seg_start = k
                segs.append((seg_start, j))

                def _force(target):
                    target = max(i, min(target, j - 1))
                    if not rows[target].get("break_before"):
                        rows[target]["break_before"] = True

                if len(segs) > 2:
                    _force(i)  # pathological — move the whole group forward
                elif len(segs) == 2:
                    (a0, a1), (b0, b1) = segs
                    if a1 - a0 < MIN:
                        # too few rows before the break — move the whole
                        # group onto the next page (the split, if any, then
                        # lands deeper into the group)
                        _force(i)
                    elif b1 - b0 < MIN:
                        # too few rows in the continuation — pull the break
                        # earlier so exactly MIN rows carry over
                        _force(j - MIN)
            i = j


def _generate_pdf_sync(front_pages: list, main_pages: list, template, render_kwargs: dict,
                        merged_page_layouts: dict, font_family: str, report_month: str) -> bytes:
    """Single Playwright entry point for a whole PDF request: launches
    Chromium exactly once and reuses it for every pass — the page-3 overflow
    check and the final render — instead of each of those launching (and
    closing) its own browser process. This is purely an execution-plumbing
    change (same HTML, same measurements, same output); it does not affect
    layout, fonts, or page counts.

    The trend-table rowspan split (see _make_trend_split_hook) happens
    inline inside the final render's own _render_pdf call, measured on the
    exact page that becomes the PDF — not as a separate pass here.

    Mutates main_pages/merged_page_layouts in place exactly as the previous
    per-pass functions did (trend row is_first_in_plant/plant_row_count, and
    merged_page_layouts["3"]'s margins) — render_kwargs["page_layouts"] *is*
    merged_page_layouts (same dict object), so the final template.render()
    below picks up the page-3 adjustment automatically.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # Page 3 (SAIL Performance Summary): narrative/highlights length and
        # which TE parameters carry values both vary month to month, so
        # whether the page overflows its single-page budget isn't knowable
        # from the schema — only tighten its margins/table padding for
        # months that actually need it, never as a blanket default.
        if any(p.get("page") == 3 for p in main_pages):
            if _measure_page3_overflow(browser, main_pages, template, render_kwargs, font_family, report_month):
                _p3_entry = dict(merged_page_layouts.get("3", {}))
                _p3_entry["marginTop"] = 2
                _p3_entry["marginBottom"] = 1
                _p3_entry["tablePaddingV"] = 0.5
                merged_page_layouts["3"] = _p3_entry

        # Page 1 (Cover) is rendered as its own document with a zero page
        # margin (see _render_pdf's docstring — page.pdf()'s margin option
        # always wins over the @page CSS the template already declares for
        # it), separately from page 2 (Index), which keeps the normal margin.
        _cover_pages = [p for p in front_pages if p.get("page") == 1]
        _other_front_pages = [p for p in front_pages if p.get("page") != 1]
        cover_html = template.render(pages=_cover_pages, **render_kwargs) if _cover_pages else ""
        front_html = template.render(pages=_other_front_pages, **render_kwargs) if _other_front_pages else ""
        dept_badges = {p.get("page"): p.get("dept_badge") for p in main_pages if p.get("dept_badge")}

        # "Large BFs" (bf_large_annexure) and the 3 Cost Trend pages right
        # after it (cost_trend: 3.61/3.62/3.63, per direct instruction) are
        # the main-content pages that need a genuinely wider physical page
        # (see _render_landscape_page_pdf's docstring — Chromium's
        # page.pdf() format is fixed per call, so this can't share the
        # single portrait main_html call every other page does). Split them
        # out as one contiguous block (they're inserted contiguously — see
        # main.py's page-list assembly), render it separately at true A4-
        # landscape dimensions, splice it into the merged document at its
        # original position, then re-stamp every main-content page's
        # header/footer from scratch (_stamp_main_page_numbers) — Chromium's
        # own pageNumber/totalPages counters are per-call and reset to 1/1
        # for the spliced-in pages, so nothing downstream of them would show
        # a correct "Page N of TOTAL" without this.
        # Pages that need a genuinely wider physical page: "Large BFs" +
        # the 3 Cost Trend pages right after it (one contiguous block near
        # page 3.6), and "Special Steel Plants Physical Performance" (a
        # second block near page 24). Each contiguous run is rendered
        # separately at true A4-landscape and spliced back into the merged
        # document at its original position, then every main-content page's
        # header/footer is re-stamped from scratch (Chromium's own
        # pageNumber/totalPages counters are per-call).
        _LANDSCAPE_TYPES = ("bf_large_annexure", "cost_trend", "special_steel_physical")
        _landscape_pages = [p for p in main_pages if p.get("type") in _LANDSCAPE_TYPES]
        if not _landscape_pages:
            main_html = template.render(pages=main_pages, **render_kwargs) if main_pages else ""
            _trend_hook = _make_trend_split_hook(main_pages, template, render_kwargs, _MAIN_MARGIN)
            pdf_bytes = _render_pdf(browser, front_html, main_html, font_family, report_month,
                                     dept_badges=dept_badges, cover_html=cover_html,
                                     main_pre_pdf_hook=_trend_hook)
        else:
            from pypdf import PdfReader, PdfWriter

            # Group the landscape pages into contiguous runs; each run's
            # "next_page" is the first non-landscape page after it (or None
            # if the run ends the document).
            _runs = []  # [{"pages": [...], "_end": idx, "next_page": id_or_None}]
            _prev_i = -2
            for _i, _p in enumerate(main_pages):
                if _p.get("type") not in _LANDSCAPE_TYPES:
                    continue
                if _runs and _prev_i == _i - 1:
                    _runs[-1]["pages"].append(_p)
                else:
                    _runs.append({"pages": [_p]})
                _runs[-1]["_end"] = _i + 1
                _prev_i = _i
            for _r in _runs:
                _r["next_page"] = next((p.get("page") for p in main_pages[_r["_end"]:]
                                        if p.get("type") not in _LANDSCAPE_TYPES), None)

            _rest_pages = [p for p in main_pages if p.get("type") not in _LANDSCAPE_TYPES]

            main_html_rest = template.render(pages=_rest_pages, **render_kwargs) if _rest_pages else ""
            _trend_hook = _make_trend_split_hook(_rest_pages, template, render_kwargs, _MAIN_MARGIN)
            base_bytes = _render_pdf(browser, front_html, main_html_rest, font_family, report_month,
                                      dept_badges=None, cover_html=cover_html, main_header_footer=False,
                                      main_pre_pdf_hook=_trend_hook)

            base_reader = PdfReader(io.BytesIO(base_bytes))
            run_readers = [
                PdfReader(io.BytesIO(_render_landscape_page_pdf(
                    browser, template.render(pages=r["pages"], **render_kwargs), font_family)))
                for r in _runs
            ]

            def _marker_index(reader, page_id):
                marker = f"@@PGSTART_{page_id}@@"
                for k, pg in enumerate(reader.pages):
                    if marker in (pg.extract_text() or ""):
                        return k
                return None

            main_start = _marker_index(base_reader, _rest_pages[0].get("page")) if _rest_pages else 0
            if main_start is None:
                main_start = 0

            # base_reader page index -> list of run readers to insert *before* it
            _inserts = {}
            for r, rr in zip(_runs, run_readers):
                at = _marker_index(base_reader, r["next_page"]) if r["next_page"] else len(base_reader.pages)
                if at is None:
                    at = len(base_reader.pages)
                _inserts.setdefault(at, []).append(rr)

            writer = PdfWriter()
            for k in range(len(base_reader.pages) + 1):
                for rr in _inserts.get(k, []):
                    for p in rr.pages:
                        writer.add_page(p)
                if k < len(base_reader.pages):
                    writer.add_page(base_reader.pages[k])

            out = io.BytesIO()
            writer.write(out)
            spliced_bytes = out.getvalue()

            _total_landscape = sum(len(rr.pages) for rr in run_readers)
            main_count = len(base_reader.pages) + _total_landscape - main_start
            spliced_bytes = _stamp_main_page_numbers(spliced_bytes, browser, font_family, report_month,
                                                      main_start, main_count)
            if dept_badges:
                spliced_bytes = _apply_dept_badges(spliced_bytes, dept_badges, browser, font_family)
            pdf_bytes = spliced_bytes

        browser.close()

    return pdf_bytes


async def generate_pdf_bytes(request: PDFRequest, pages_override: list = None, page_layouts: dict = None, font_config=None) -> tuple[bytes, str]:
    """Runs the actual Playwright render and returns (pdf_bytes, filename).
    Split out from build_pdf_response so a background job runner (see
    main.py's /api/generate-pdf/start) can call it without needing an
    HTTP response object — a full report now regularly takes 20+ minutes,
    far past any reasonable synchronous HTTP timeout."""
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
            title_size=   _g.get("title_size",   13.0),  # Increased from 13.0 for better readability
            heading_size= _g.get("heading_size", 12.0),  # Increased from 10.5 for consistency
        )
        fc = font_config or request.font_config or _cfg_fc
        # Only apply FONT_CATALOG's @font-face CSS when fc.family is actually
        # one of its own web fonts. The previous fallback-to-IBM-Plex-Sans
        # here was misleading: it always injected *some* font CSS even when
        # fc.family (e.g. "Arial Narrow", the current layout_config.json
        # default and every techno-page override's own choice) isn't a
        # catalog key at all — _font_family_css below always lists fc.family
        # first, so that CSS was never actually applied to any rendered text;
        # it just cost real work building a ~300-400KB base64 @font-face
        # block (see FONT_CATALOG / _local_font_face_css above) for nothing.
        # Arial Narrow and Arial are both preinstalled Windows fonts, so this
        # is normally a no-op eliminated entirely; a real catalog font
        # (family="Roboto", etc., e.g. via request.font_config) still gets
        # its @font-face CSS as before.
        _catalog_entry = FONT_CATALOG.get(fc.family)
        _font_imports   = _catalog_entry["import"] if _catalog_entry else ""
        # Cover page (.page1-container in main.html) always renders in Roboto
        # regardless of the report's chosen body font, so its @font-face has
        # to be embedded unconditionally rather than only when fc.family
        # itself is "Roboto" (see comment above on _font_imports normally
        # being a no-op for the "Arial Narrow" default).
        if fc.family != "Roboto":
            _font_imports += "\n" + _local_font_face_css("Roboto")
        _font_family_css = f"'{fc.family}', sans-serif"
        _mono_name = _catalog_entry["mono"] if _catalog_entry else "Courier New"
        _mono_family_css = f"'{_mono_name}', 'Courier New', monospace"

        total_report_pages = len(request.pages)

        flat_pages = []
        src = pages_override if pages_override is not None else [p_data.dict() for p_data in request.pages]
        for p in src:
            if p.get("type") == "page4_table":
                p["rows"] = _group_page4_rows(p.get("rows", []))
            if p.get("type") == "summary" and p.get("chart_data"):
                from page_techno import generate_summary_chart_html
                p["_chart_html"] = generate_summary_chart_html(p["chart_data"])
            if p.get("page") == 6:
                from page5_6 import generate_page6_trend_charts_html
                p["_page6_charts_html"] = generate_page6_trend_charts_html(request.month)
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
                # Only "group" is ever read back out of this — see
                # _apply_dept_badges below, which recomputes "side" itself
                # from each physical PDF page's own position (this merged
                # block can expand into more physical pages than the
                # logical page count here, so any "side" computed at this
                # point couldn't stay correct across all of them anyway).
                _badge_group = dept_badge_group(first_pg)
                pages_to_render.append({
                    "type": "trend_section",
                    "page": first_pg,
                    "items": all_items,
                    "page_range": f"{first_pg}-{last_pg}",
                    "dept_badge": {"group": _badge_group} if _badge_group is not None else None,
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
        # Run sync Playwright in a thread so it doesn't fight the asyncio event loop.
        # Everything Playwright-related (page-3 overflow check, trend-break
        # measurement, final render) happens inside one call sharing a single
        # browser instance — see _generate_pdf_sync — instead of three
        # separate executor round-trips each launching its own Chromium.
        loop = asyncio.get_event_loop()
        report_month_display = f"{vars['m_name']} {vars['y_str']}"

        pdf_bytes = await loop.run_in_executor(
            None, functools.partial(
                _generate_pdf_sync, front_pages, main_pages, _template, _render_kwargs,
                _merged_page_layouts, fc.family, report_month_display,
            ),
        )

        filename = f"SAIL_MIS_Report_{request.month.replace(' ', '_')}.pdf"
        return pdf_bytes, filename
    except Exception as e:
        detail = f"PDF Compilation failed: {type(e).__name__}: {e}\n{tb.format_exc()}"
        print(detail)
        raise HTTPException(status_code=500, detail=detail)


async def build_pdf_response(request: PDFRequest, pages_override: list = None, page_layouts: dict = None, font_config=None) -> Response:
    """Synchronous (blocking-HTTP-request) entry point, kept for any caller
    that wants a single-shot response rather than the async job flow. Not
    used by main.py's report-export path anymore (see generate_pdf_bytes's
    docstring for why)."""
    pdf_bytes, filename = await generate_pdf_bytes(request, pages_override, page_layouts, font_config)
    # A plain Response, not StreamingResponse(io.BytesIO(...)) — the whole
    # PDF is already in memory, and StreamingResponse iterates its content
    # using BytesIO's default __iter__, which reads line-by-line (splitting
    # on b'\n', extremely common in binary PDF data). A ~3MB report body
    # measured 176k+ newlines — that's 176k+ separate ASGI send() calls
    # instead of one, which is what was actually turning a fast render into
    # a multi-minute response (verified: a 61s render, then 5+ min just to
    # stream a partial download of the result).
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Content-Type-Options": "nosniff",
        },
    )
