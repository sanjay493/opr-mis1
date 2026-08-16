import functools
import io
import os
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
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
# every Chromium launch (several per PDF, see _measure_page3_overflow /
# _measure_trend_page_breaks) even though request.font_config is always
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
            f"@font-face {{ font-family: '{family}'; font-style: {style}; "
            f"font-weight: {weight}; font-display: swap; "
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


def _render_pdf(browser, front_html: str, main_html: str, font_family: str = _DEFAULT_FONT, report_month: str = "",
                 dept_badges: dict = None) -> bytes:
    """Render one PDF using an already-launched Chromium `browser`. Callers
    (the page3-overflow / trend-break measurement passes and the final
    render, see _generate_pdf_sync) all share a single browser instance for
    the whole request instead of each launching/closing its own Chromium
    process — several passes per request previously meant several full
    browser launches, which is pure overhead since it's the same renderer
    doing the same job each time.

    Rendered as two separate PDF documents so the header/footer (with page
    numbering) only appears from page 3 onward: `front_html` (cover + index,
    pages 1-2) is rendered without header/footer, and `main_html` (page 3+) is
    rendered with header/footer, which makes Chromium's own pageNumber/totalPages
    counters naturally read "Page 1 of N" for the first page of the main content.
    The two PDFs are then merged into one.
    """
    from pypdf import PdfReader, PdfWriter
    hdr_font = f"'{font_family}',Arial,sans-serif"
    margin = {"top": "12mm", "right": "15mm", "bottom": "12mm", "left": "15mm"}

    writer = PdfWriter()

    if front_html:
        page = browser.new_page()
        page.set_content(front_html, wait_until="domcontentloaded")
        page.evaluate("document.fonts.ready")
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
        # Web fonts load asynchronously; without waiting for them, two
        # separate renders of the same HTML (as the trend-page split
        # measurement pass and the final render both are) can land text
        # with slightly different fallback/final font metrics, shifting
        # row heights just enough to move the real page break away from
        # the one measured — so both passes need this to agree.
        page.evaluate("document.fonts.ready")
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
        if dept_badges:
            main_bytes = _apply_dept_badges(main_bytes, dept_badges, browser, font_family)
        for p in PdfReader(io.BytesIO(main_bytes)).pages:
            writer.add_page(p)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _measure_page3_overflow(browser, main_pages: list, template, render_kwargs: dict,
                             font_family: str, report_month: str) -> bool:
    """Render the *entire* main document (mirrors _measure_trend_page_breaks
    below — rendering page 3 in isolation was tried first and does NOT
    reliably reproduce the break it gets embedded after pages 1-2; verified
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


def _measure_trend_page_breaks(browser, trend_page: dict, main_pages: list, template, render_kwargs: dict,
                                font_family: str, report_month: str) -> dict:
    """Render the *entire* main document (all of main_pages, not just the
    trend section) with a unique marker appended to each trend row's
    year-label, then inspect the produced PDF to see which physical page
    each row actually lands on. Returns {(item_index, row_index): page_index}.

    Measuring the trend section in isolation (its own standalone render) does
    NOT reliably reproduce the same page breaks it gets when embedded after
    pages 3-6 — verified empirically, root cause not fully pinned down but
    the effect is real and large enough to move a group across a page
    boundary. Rendering the same main_pages list here as the final render
    uses removes that gap; only the trend rows' text differs (the markers),
    which does not itself shift the breaks (verified separately).

    Table cells use table-layout:fixed and white-space:nowrap (see
    trend_yearly.html/main.html), so the extra marker text doesn't wrap or
    change row height either.

    Only renders main_pages up through the trend section itself, dropping
    everything after it (the ~25-30 techno/special-steel/capital-repair
    pages on a full report) — pagination flows top-to-bottom, so content
    after the trend section can't move where its own rows land, only
    content before it can (which stays intact here)."""
    import re
    from pypdf import PdfReader

    marker_re = re.compile(r"@@(\d+)_(\d+)@@")
    marked_items = []
    for ii, it in enumerate(trend_page.get("items", [])):
        new_rows = []
        for ri, row in enumerate(it.get("rows", [])):
            r = dict(row)
            r["year_label"] = f'{row.get("year_label", "")} @@{ii}_{ri}@@'
            new_rows.append(r)
        marked_items.append({**it, "rows": new_rows})
    marked_page = {**trend_page, "items": marked_items}
    trend_idx = next(i for i, p in enumerate(main_pages) if p is trend_page)
    marked_main_pages = [
        marked_page if p is trend_page else p for p in main_pages[:trend_idx + 1]
    ]

    html = template.render(pages=marked_main_pages, **render_kwargs)
    pdf_bytes = _render_pdf(browser, "", html, font_family, report_month)

    page_of = {}
    reader = PdfReader(io.BytesIO(pdf_bytes))
    for pi, p in enumerate(reader.pages):
        text = p.extract_text() or ""
        for m in marker_re.finditer(text):
            page_of[(int(m.group(1)), int(m.group(2)))] = pi
    return page_of


def _apply_trend_page_splits(trend_page: dict, page_of: dict) -> None:
    """Mutate trend_page's rows in place: within each plant/SAIL group,
    recompute is_first_in_plant/plant_row_count so the rowspan'd plant-name
    cell is split at every point page_of shows a page-index change — one
    merged, vertically-centered label per physical page instead of one for
    the whole group (which would leave later pages blank when the group
    spills over). A group with any row missing a measurement is left as a
    single whole-group merge — the pre-existing, safe default."""
    for ii, it in enumerate(trend_page.get("items", [])):
        rows = it.get("rows", [])
        i = 0
        while i < len(rows):
            plant = rows[i]["plant"]
            j = i
            while j < len(rows) and rows[j]["plant"] == plant:
                j += 1
            pages = [page_of.get((ii, k)) for k in range(i, j)]
            if all(p is not None for p in pages):
                seg_start = i
                for k in range(i, j):
                    if k > i and pages[k - i] != pages[k - i - 1]:
                        for m in range(seg_start, k):
                            rows[m]["is_first_in_plant"] = (m == seg_start)
                            rows[m]["plant_row_count"] = k - seg_start
                        seg_start = k
                for m in range(seg_start, j):
                    rows[m]["is_first_in_plant"] = (m == seg_start)
                    rows[m]["plant_row_count"] = j - seg_start
            i = j


def _generate_pdf_sync(front_pages: list, main_pages: list, template, render_kwargs: dict,
                        merged_page_layouts: dict, font_family: str, report_month: str) -> bytes:
    """Single Playwright entry point for a whole PDF request: launches
    Chromium exactly once and reuses it for every pass — the page-3 overflow
    check, the trend-page-break measurement, and the final render — instead
    of each of those launching (and closing) its own browser process. This
    is purely an execution-plumbing change (same HTML, same measurements,
    same output); it does not affect layout, fonts, or page counts.

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

        # Trend pages (7-12) flow continuously and can spill a plant/SAIL
        # group across two physical pages. A merged rowspan cell only shows
        # its label on the page the group started on, leaving the
        # continuation blank — so measure the real page breaks first (using
        # the full main_pages document, not an isolated slice — see
        # _measure_trend_page_breaks) and split the rowspan at that exact
        # row, one merged/centered label per physical page instead of one
        # for the whole group.
        for _tp in main_pages:
            if _tp.get("type") == "trend_section":
                _page_of = _measure_trend_page_breaks(
                    browser, _tp, main_pages, template, render_kwargs, font_family, report_month,
                )
                _apply_trend_page_splits(_tp, _page_of)

        front_html = template.render(pages=front_pages, **render_kwargs) if front_pages else ""
        main_html = template.render(pages=main_pages, **render_kwargs) if main_pages else ""
        dept_badges = {p.get("page"): p.get("dept_badge") for p in main_pages if p.get("dept_badge")}
        pdf_bytes = _render_pdf(browser, front_html, main_html, font_family, report_month, dept_badges=dept_badges)

        browser.close()

    return pdf_bytes


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
        _font_family_css = f"'{fc.family}', Arial, Helvetica, sans-serif"
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
