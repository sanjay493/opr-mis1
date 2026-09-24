import functools
import io
import os
import re
import time as _time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

# All PDF generation runs on this single dedicated thread so the persistent
# Chromium instance in pdf.py's _PW_STATE (thread-affinity-bound, like every
# Playwright sync-API object) is always driven from the same thread — the
# default asyncio executor hands work to whichever pool thread is free,
# which would crash Playwright's sync API on the second concurrent call.
# This also naturally serializes report generation, which was already the
# case in practice (single office user, one report at a time).
_PDF_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdf-render")
from fastapi import HTTPException
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
from models import PDFRequest
from report_utils import dept_badge_group

_TMPL_DIR = os.path.join(os.path.dirname(__file__), 'page_templates')
_jinja_env = Environment(loader=FileSystemLoader(_TMPL_DIR), autoescape=False)


def _rr_cell(value):
    """Jinja filter for ready_reckoner_plant.html: escapes plain-data cell
    text (this env's autoescape is off globally, see above, so {{ }} alone
    never escapes) and turns a "\\n" line break — the one thing these cells
    are allowed to carry, see db.py's own comment above _READY_RECKONER_COLS
    — into a real <br>. Never trust this on a field that might already
    contain HTML; it's for plain-data-only content specifically."""
    import html as _html_mod
    if value is None:
        return ""
    return _html_mod.escape(str(value)).replace("\n", "<br>")


_jinja_env.filters['rr_cell'] = _rr_cell


def _rr_facility(value):
    """Jinja filter for the Unit-wise Capacity table's Facility column: like
    |rr_cell, but a "[...]" part (e.g. "Blast Furnaces [BF-1, BF-4, BF-5]")
    moves to its own 2nd line and is shown in black, brackets included,
    while the facility name before it stays on one unwrapped line. Text
    with no "[" renders exactly as |rr_cell does."""
    import html as _html_mod
    if value is None:
        return ""
    text = str(value)
    cut = text.find("[")
    if cut <= 0:
        return _rr_cell(text)
    name = _html_mod.escape(text[:cut].strip()).replace("\n", "<br>")
    rest = _html_mod.escape(text[cut:].strip()).replace("\n", "<br>")
    return (f'<span class="rr-facility-name">{name}</span><br>'
            f'<span class="rr-facility-bracket">{rest}</span>')


_jinja_env.filters['rr_facility'] = _rr_facility


# Runs in a child process — see _page_texts_many. argv: PDF file paths;
# prints one JSON list per file (that file's per-page texts). Every pdfium
# object is closed explicitly, in order.
_PDFIUM_TEXTS_SCRIPT = r"""
import json, sys
import pypdfium2 as pdfium
out = []
for path in sys.argv[1:]:
    doc = pdfium.PdfDocument(path)
    texts = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            textpage = page.get_textpage()
            try:
                texts.append(textpage.get_text_range() or "")
            finally:
                textpage.close()
                page.close()
    finally:
        doc.close()
    out.append(texts)
sys.stdout.write(json.dumps(out))
"""


def _page_texts_many(pdfs: list) -> list:
    """Every physical page's text layer, in order, for each PDF in `pdfs` —
    used only to find the invisible @@PGSTART_N@@ / @@TROW_..@@ markers.

    pypdfium2 (installed as a pdfplumber dependency) is ~12x faster than
    pypdf's extract_text() here (0.6s vs 7.5s on a 15-page trend section;
    pypdf re-parses the big embedded web fonts on every page). But pdfium
    is not thread-safe, and inside the server it crashed the whole worker
    process twice (2026-09-23, pdfium.dll 0x80000003 / 0xc0000409 — no
    Python exception, the job just never finished). So it runs in a short-
    lived child process instead: nothing else in that process can touch
    pdfium, and a crash there can't take the server down. One child per
    call, so batch small PDFs together. If the child fails for any reason,
    falls back to pypdf in-process (slow but safe) and logs it."""
    import json
    import subprocess
    import sys
    import tempfile

    if not pdfs:
        return []
    with tempfile.TemporaryDirectory(prefix="pdf-texts-") as tmp:
        paths = []
        for i, data in enumerate(pdfs):
            path = os.path.join(tmp, f"{i}.pdf")
            with open(path, "wb") as f:
                f.write(data)
            paths.append(path)
        try:
            proc = subprocess.run([sys.executable, "-c", _PDFIUM_TEXTS_SCRIPT, *paths],
                                  capture_output=True, timeout=300)
            if proc.returncode == 0:
                texts = json.loads(proc.stdout.decode("utf-8"))
                if len(texts) == len(pdfs):
                    return texts
            detail = proc.stderr.decode("utf-8", "replace").strip()[-500:] or f"exit code {proc.returncode:#x}"
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"
    print(f"[pdf] pdfium text extraction failed ({detail}); falling back to pypdf")
    from pypdf import PdfReader
    return [[(p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages] for data in pdfs]


def _page_texts(pdf_bytes: bytes) -> list:
    """_page_texts_many for a single PDF."""
    return _page_texts_many([pdf_bytes])[0]

# ── PDF generation timing (backend terminal diagnostics) ───────────────────
# Module-level, not per-request: safe because _PDF_EXECUTOR above is a
# single-worker pool, so only one report ever renders at a time (see its own
# comment) — no risk of two requests' phases interleaving in this list.
# _generate_pdf_sync resets it at the start of every render and prints a
# sorted breakdown + grand total from it at the end (see that function and
# _print_timing_summary below). Added to answer "which page/phase is slow
# and why" directly from the terminal instead of guessing.
_TIMING_LOG = []

# Layout problems detected during the current render — each is printed as a
# "[pdf] LAYOUT WARNING" line in the backend console as it's found, and
# again in the end-of-render summary. Reset per render, like _TIMING_LOG.
# What each warning means and how to recover: backend/docs/
# PDF_LAYOUT_GUARDRAILS.md. layout_guard.py --render reads this list too.
_LAYOUT_WARNINGS = []

# Below this per-page fit zoom a page is noticeably harder to read.
_MIN_LEGIBLE_ZOOM = 0.85


def _layout_warn(msg: str) -> None:
    _LAYOUT_WARNINGS.append(msg)
    print(f"[pdf] LAYOUT WARNING: {msg}  -> see backend/docs/PDF_LAYOUT_GUARDRAILS.md")


@contextmanager
def _time_phase(label: str):
    """Records (label, elapsed_seconds) into _TIMING_LOG for the current
    render. Labels aren't required to be unique — a repeated phase (e.g. one
    trend-split probe pass per loop iteration) just shows up as multiple
    rows in the summary, which is useful in itself (how many passes ran)."""
    t0 = _time.perf_counter()
    try:
        yield
    finally:
        _TIMING_LOG.append((label, _time.perf_counter() - t0))


def _print_timing_summary(total_seconds: float):
    print(f"[pdf-timing] TOTAL render time: {total_seconds:.1f}s")
    # Rows are a flat log, not a clean partition — a "— TOTAL"/"(TOTAL)" row
    # (e.g. "main content — TOTAL", "trend-split hook (cache MISS, TOTAL)")
    # already includes the time of the individual pass/reprobe rows listed
    # below it, so don't add those together expecting 100%.
    for label, secs in sorted(_TIMING_LOG, key=lambda t: -t[1]):
        pct = (secs / total_seconds * 100) if total_seconds else 0
        print(f"[pdf-timing]   {secs:7.1f}s ({pct:4.1f}%)  {label}")


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
# source of truth shared by every page.pdf() call for it, including
# _plan_trend_layout's probe prints, which must use this exact same margin
# so their measured page counts match what the final print produces.
_MAIN_MARGIN = {"top": "10mm", "right": "15mm", "bottom": "9mm", "left": "15mm"}
# The Index (page 2) is rendered without a Chromium header/footer, so it
# doesn't need the ~9-10mm the main pages reserve for those bars — a tighter
# top/bottom keeps the (now longer) contents list on one page. Top is the
# tightest (see .pg-2 / .page2-heading in main.html) so the 32-row list,
# Annexure-III included, stays on a single sheet.
_FRONT_MARGIN = {"top": "4mm", "right": "13mm", "bottom": "8mm", "left": "13mm"}

# Printable area (width, height in mm) inside _MAIN_MARGIN for portrait A4,
# and inside _render_landscape_page_pdf's margin for landscape A4.
_PRINTABLE_PORTRAIT_MM = (210 - 15 - 15, 297 - 10 - 9)
_PRINTABLE_LANDSCAPE_MM = (297 - 10 - 10, 210 - 12 - 10)
_PX_PER_MM = 96 / 25.4

# A single .page up to this much taller than one sheet is scaled down to fit
# that sheet; anything taller is genuinely multi-page content, left alone.
_VFIT_MAX_OVERFLOW = 1.10

_FIT_PAGES_JS = """([W, H, maxOver]) => {
  const fitted = [];
  for (const pg of document.querySelectorAll('.page')) {
    const r0 = pg.getBoundingClientRect();
    let right = r0.width;
    for (const el of pg.getElementsByTagName('*')) {
      const r = el.getBoundingClientRect();
      if (r.width && r.right - r0.left > right) right = r.right - r0.left;
    }
    let z = right > W + 0.5 ? (W * 0.99) / right : 1;   // 1% margin: rounding can land a px over
    if (z < 1) pg.style.zoom = z;
    // Vertical fill: a page whose table opts in (data-vgrow - the techno
    // parameter pages 27-30) and already fits gets its body-cell padding
    // grown until the page, at the zoom just applied, fills the sheet -
    // instead of leaving a band of empty space at the bottom. Bisected
    // against the real layout, so it adapts to month/row count without
    // per-page tuned constants.
    // data-vgrow-mm / data-vgrow-wmm are that page's real usable height and
    // width on paper (its own @page margins differ from the generic
    // printable area W x H this whole pass is laid out at). While filling,
    // the page is laid out at its real print width - at the narrower
    // generic width labels wrap onto more lines, so a fill measured there
    // printed shorter than measured and still left a gap at the bottom.
    // The too-tall check below uses the same width/height, then the width
    // is restored so the whole-job overflow check further down is unchanged.
    const vtbl = pg.querySelector('table[data-vgrow]');
    const mm = 96 / 25.4;
    const Hp = vtbl && vtbl.dataset.vgrowMm ? +vtbl.dataset.vgrowMm * mm : H;
    const Wp = vtbl && vtbl.dataset.vgrowWmm ? +vtbl.dataset.vgrowWmm * mm : 0;
    if (Wp) pg.style.width = (Wp / z) + 'px';   // zoom scales it back to Wp on screen
    if (vtbl && pg.dataset.vfit !== 'off') {
      const target = Hp * 0.985;
      const zh = () => pg.getBoundingClientRect().height;   // already zoomed
      if (zh() < target) {
        // Row-spanning section labels are left alone - growing them too made
        // Chromium's print layout spread the extra height unevenly (first
        // rows of a section tighter than the rest).
        const cells = Array.from(vtbl.querySelectorAll('tbody td:not([rowspan])'));
        const base = cells.map((c) => {
          const cs = getComputedStyle(c);
          return [parseFloat(cs.paddingTop) || 0, parseFloat(cs.paddingBottom) || 0];
        });
        const apply = (x) => cells.forEach((c, i) => {
          c.style.setProperty('padding-top', (base[i][0] + x) + 'px', 'important');
          c.style.setProperty('padding-bottom', (base[i][1] + x) + 'px', 'important');
        });
        let lo = 0, hi = 12;
        for (let it = 0; it < 12; it++) {
          const mid = (lo + hi) / 2;
          apply(mid);
          if (zh() <= target) lo = mid; else hi = mid;
        }
        // data-vgrow-step: snap the growth down to a multiple of it, e.g.
        // 0.5px on a table whose rows are a whole number of px, so they stay
        // whole (fractional rows print with an uneven baseline rhythm).
        const step = +(vtbl.dataset.vgrowStep || 0);
        apply(step ? Math.floor(lo / step) * step : lo);
      }
    }
    if (pg.dataset.vfit !== 'off') {
      const h = pg.getBoundingClientRect().height;
      if (h > Hp && h <= Hp * maxOver) { z = z * (Hp * 0.985) / h; pg.style.zoom = z; }
    }
    if (Wp) pg.style.width = '';
    if (z < 1) {
      const m = (pg.querySelector('.pg-badge-marker') || {}).textContent || '';
      fitted.push([m.replace(/@|PGSTART_/g, ''), +z.toFixed(3)]);
    }
  }
  // Rightmost element box after fitting (boxes, not scrollWidth: text
  // spilling a few px past its own table cell doesn't trigger Chromium's
  // whole-job shrink, a box past the printable width does).
  let right = 0;
  for (const el of document.body.getElementsByTagName('*')) {
    const r = el.getBoundingClientRect();
    if (r.width && r.right > right) right = r.right;
  }
  return {fitted, overflow: right - W};
}"""


def _load_for_print(page, html: str, printable_mm: tuple) -> None:
    """set_content + wait for web fonts, then _fit_pages_for_print. Every
    print of report pages goes through this, so probes and final prints see
    the same per-page scaling."""
    w_mm, h_mm = printable_mm
    page.set_viewport_size({"width": round(w_mm * _PX_PER_MM), "height": round(h_mm * _PX_PER_MM)})
    page.emulate_media(media="print")
    page.set_content(html, wait_until="domcontentloaded")
    page.evaluate("document.fonts.ready")
    _fit_pages_for_print(page, printable_mm)


def _fit_pages_for_print(page, printable_mm: tuple) -> list:
    """Scales individual .page blocks (CSS zoom) that don't fit the sheet,
    laid out at the real printable width in print media:

    - wider than the printable width -> scaled to fit the width. Without
      this, Chromium's print shrink-to-fit scales the WHOLE print job to the
      widest page: one overflowing table (page 24's .ssd-table, a Ready
      Reckoner product-mix table) was printing all ~90 portrait pages at
      ~94.7%, leaving every page with a band of empty space at the bottom.
    - up to _VFIT_MAX_OVERFLOW taller than one sheet -> scaled to fit it,
      unless the page opts out with data-vfit="off" (see main.html).

    Everything else prints at 100%. Returns [(page id, zoom), ...]."""
    w_mm, h_mm = printable_mm
    res = page.evaluate(_FIT_PAGES_JS, [w_mm * _PX_PER_MM, h_mm * _PX_PER_MM, _VFIT_MAX_OVERFLOW])
    fitted = res["fitted"]
    if fitted:
        print("[pdf] fit-to-page: " + ", ".join(f"{pid} @ {z:.0%}" for pid, z in fitted))
    for pid, z in fitted:
        if z < _MIN_LEGIBLE_ZOOM:
            _layout_warn(f"page {pid} had to be shrunk to {z:.0%} to fit - its content has outgrown "
                         f"the page (tighten that page's layout rather than rely on shrinking)")
    if res["overflow"] > 2:   # tolerate sub-pixel rounding
        _layout_warn(f"content is still {res['overflow']:.0f}px wider than the printable area after "
                     f"per-page fitting - Chromium will shrink EVERY page in this print job "
                     f"(the whole-report shrink). Likely an element outside any .page block.")
    return fitted


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


# Self-hosted from Google Fonts (each family embeds both its "latin" and
# "latin-ext" subsets — see _LATIN_EXT_RANGE below for why latin alone
# isn't enough) rather than the previous
# @import url('https://fonts.googleapis.com/...') — that hit the network on
# every Chromium launch (see _measure_page3_overflow) even though
# request.font_config is always
# None in practice today (backend/main.py always calls build_pdf_response
# with font_config=None, so _DEFAULT_FONT/layout_config.json's font_family
# is what actually renders) — but the picker exists in the schema, so this
# keeps it offline-capable if it's ever wired up. Files + source URLs are
# in backend/fonts/manifest.json.
#
# The report's body font (layout_config.json's global font_family) and its
# narrow-column font (used directly by several page templates) both used
# to be Microsoft fonts — "Aptos" and "Arial Narrow" — neither of which
# ships with a plain Windows install (both come bundled with Office
# 2021+/Microsoft 365 instead), so whether they rendered correctly, and
# identically, depended on what happened to be installed on whichever
# machine generated the PDF. That silently changed this report's text
# metrics — and therefore its shrink-to-fit widths and page breaks —
# between machines. Both are now real, fully self-hosted, open-license
# fonts instead: "IBM Plex Sans" (body) and "IBM Plex Sans Condensed"
# (narrow columns) — same type family, so the two cuts stay visually
# coherent, and IBM Plex was chosen specifically for dense-table
# legibility. "Aptos" (Hanken Grotesk under that name) and
# "Roboto Condensed" remain below as selectable catalog fonts — no longer
# the defaults anywhere, but harmless to leave in place since a font is
# only ever actually embedded when something requests it by name.
_FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')

_FONT_SLUGS = {
    "IBM Plex Sans": "ibm-plex-sans", "IBM Plex Mono": "ibm-plex-mono",
    "IBM Plex Sans Condensed": "ibm-plex-sans-condensed",
    "Source Sans 3": "source-sans-3", "Source Code Pro": "source-code-pro",
    "Roboto": "roboto", "Roboto Mono": "roboto-mono",
    "Noto Sans": "noto-sans", "Noto Sans Mono": "noto-sans-mono",
    "Lato": "lato",
    "Aptos": "aptos-sub", "Roboto Condensed": "roboto-condensed",
}


# Currency symbols — including the Indian Rupee sign, U+20B9, used all
# over this report's price/cost tables — live in Google Fonts' "latin-ext"
# subset, not "latin". Every font here was only ever self-hosted from
# "latin" (see the module-level comment above _FONTS_DIR), so ₹ silently
# rendered blank (no glyph at all, not even a tofu box, since font-display:
# block paints nothing until a face resolves) on any font actually used
# for report body text. Confirmed identical across every family fetched
# here — this is Google's standard subset boundary, not font-specific.
_LATIN_EXT_RANGE = (
    "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, "
    "U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, "
    "U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF"
)


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
    weight_styles = []
    ext_name = f"{slug}-ext.woff2"
    for path in sorted(glob.glob(os.path.join(_FONTS_DIR, slug, f"{slug}-*.woff2"))):
        if os.path.basename(path) == ext_name:
            continue  # the latin-ext companion file, handled below
        name = os.path.splitext(os.path.basename(path))[0]
        weight, style = name.rsplit("-", 2)[-2:]
        weight_styles.append((weight, style))
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
    ext_path = os.path.join(_FONTS_DIR, slug, ext_name)
    if os.path.exists(ext_path) and weight_styles:
        with open(ext_path, "rb") as f:
            ext_b64 = base64.b64encode(f.read()).decode("ascii")
        for weight, style in weight_styles:
            blocks.append(
                f"@font-face {{ font-family: '{family}'; font-style: {style}; "
                f"font-weight: {weight}; font-display: block; "
                f"unicode-range: {_LATIN_EXT_RANGE}; "
                f"src: url(data:font/woff2;base64,{ext_b64}) format('woff2'); }}"
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
    # "Aptos" and "Roboto Condensed" are no longer layout_config.json's
    # defaults (see the self-hosting note above _FONT_SLUGS) — kept as
    # selectable catalog fonts only.
    "Aptos":         {"import": _catalog_import("Aptos", "Roboto Mono"), "mono": "Roboto Mono"},
    "IBM Plex Sans Condensed": {"import": _catalog_import("IBM Plex Sans Condensed", "IBM Plex Mono"), "mono": "IBM Plex Mono"},
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
    10: ("#8b5e34", "#ffffff"), # brown   — Rakes Detention (1026,1027,1038-1040,1028,1029)
    11: ("#701a75", "#ffffff"), # dark purple — Ready Reckoner (1041-1058, +1059-1066 overflow)
}


def _dept_badge_html(side: str, group: int, font_family: str) -> str:
    """The corner department badge, absolutely positioned at its page
    block's true top corner — part of the one post-render overlay
    _stamp_main_overlays merges onto each page. Stamped afterward rather
    than rendered in the main document because Chromium hard-clips anything
    positioned outside the printable area (the header/footer margin band),
    so it can't reach the physical corner the way the live preview does."""
    bg, fg = _BADGE_COLORS[group]
    if side == "right":
        side_css = "right:0;border-radius:999px 0 0 999px;padding-left:12px;padding-right:7px;"
    else:
        side_css = "left:0;border-radius:0 999px 999px 0;padding-left:7px;padding-right:12px;"
    return (
        '<div style="position:absolute;top:0;' + side_css +
        f"font-family:'{font_family}',Arial,sans-serif;"
        'font-size:6.5pt;font-weight:700;letter-spacing:0.04em;'
        'text-transform:uppercase;white-space:nowrap;line-height:1;'
        'padding-top:4px;padding-bottom:4px;'
        f'background:{bg};color:{fg};">Operations Directorate</div>'
    )


_PGSTART_RE = re.compile(r"@@PGSTART_(\d+(?:\.\d+)?)@@")


def _page_markers(page_texts: list) -> dict:
    """{report page id: physical index of its first page} from every
    @@PGSTART_N@@ marker in page_texts (see _page_texts). Ids come back as
    int when whole (3, not 3.0) so they match page dicts' own "page"."""
    found = {}
    for k, text in enumerate(page_texts):
        for m in _PGSTART_RE.finditer(text):
            rp = float(m.group(1))
            if rp == int(rp):
                rp = int(rp)
            found.setdefault(rp, k)
    return found


def _badge_group_by_physical(n: int, dept_badges: dict, start_of: dict) -> dict:
    """{physical page index: badge group} — each report page's badge covers
    every physical page from its own @@PGSTART@@ marker up to the next
    report page's, so a page that spills onto extra physical pages (the
    trend section, a long techno table) badges all of them."""
    ordered = sorted(start_of.items(), key=lambda kv: kv[1])
    group_of = {}
    for idx, (report_pg, start_k) in enumerate(ordered):
        badge = dept_badges.get(report_pg)
        if not badge:
            continue
        end_k = ordered[idx + 1][1] if idx + 1 < len(ordered) else n
        for k in range(start_k, end_k):
            group_of[k] = badge["group"]
    return group_of


def _render_landscape_page_pdf(browser, html: str, font_family: str) -> bytes:
    """Render one page's HTML standalone at genuine A4-landscape physical
    dimensions (297x210mm), for a page (e.g. Large BFs) too wide for the
    fixed A4-portrait `format="A4"` every other main-content page shares in
    one combined page.pdf() call — Chromium's page.pdf() `format`/`width`/
    `height` are fixed per call and always win over any @page CSS `size`
    rule (see _render_pdf's docstring re: margin), so genuine landscape
    needs its own separate call, spliced into the final document by
    _generate_pdf_sync. No Chromium-native header/footer here
    (display_header_footer=False) — _stamp_main_overlays draws a
    matching one afterward for every main-content page uniformly, since
    Chromium's own pageNumber/totalPages counters reset to 1/1 for this
    call and can't be offset to match its true position once spliced into
    the middle of the full document."""
    page = browser.new_page()
    _load_for_print(page, html, _PRINTABLE_LANDSCAPE_MM)
    pdf_bytes = page.pdf(
        format="A4",
        landscape=True,
        print_background=True,
        display_header_footer=False,
        margin={"top": "12mm", "right": "10mm", "bottom": "10mm", "left": "10mm"},
    )
    page.close()
    return pdf_bytes


def _main_header_footer_overlay_block_html(font_family: str, report_month: str, page_num: int, total_pages: int,
                                            margin_side: str, w_mm: float, h_mm: float, badge_html: str = "") -> str:
    """One physical page's post-render overlay: header bar, footer bar with
    a Python-computed "Page N of TOTAL", and (if given) its corner
    department badge — as a page-sized block (position:absolute within its
    own explicitly-sized wrapper) meant to be concatenated with other
    pages' blocks, so _stamp_main_overlays prints every page's overlay in
    one page.pdf() call per distinct page size. The block's own box IS the
    page's full physical rectangle, so top:0/bottom:0/left:0/right:0 land
    exactly on the physical page edges. Visually identical to _render_pdf's
    own header_template/footer_template."""
    hdr_font = f"'{font_family}',Arial,sans-serif"
    return (
        f'<div class="stamp-page" style="position:relative;width:{w_mm}mm;height:{h_mm}mm;'
        f'overflow:hidden;">'
        f'<div style="position:absolute;top:0;left:0;right:0;padding:3mm {margin_side} 0;'
        f'box-sizing:border-box;font-family:{hdr_font};font-size:7.5pt;font-weight:500;'
        f'color:#64748b;text-align:center;border-bottom:0.5px solid #e2e8f0;'
        f'padding-bottom:3px;">OMI - {report_month}</div>'
        f'<div style="position:absolute;bottom:0;left:0;right:0;padding:0 {margin_side} 2.5mm;'
        f'box-sizing:border-box;font-family:{hdr_font};font-size:7.5pt;color:#64748b;'
        f'display:flex;justify-content:space-between;'
        f'border-top:0.5px solid #e2e8f0;padding-top:3px;">'
        f'<span>figures are provisional</span>'
        f'<span>MIS Operations</span>'
        f'<span>OMI - {report_month}</span>'
        f'<span>for internal circulation only</span>'
        f'<span>Page {page_num} of {total_pages}</span>'
        f'</div>{badge_html}</div>'
    )


def _wrap_stamp_batch_html(blocks: list) -> str:
    """Wraps _main_header_footer_overlay_block_html blocks into one
    document, each forced onto its own printed page via page-break-after
    (the same CSS-paginated-blocks technique main.html already uses for the
    whole report's many logical pages in one page.pdf() call) — see
    _stamp_main_overlays."""
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        'html,body{margin:0;padding:0;background:transparent;}'
        '.stamp-page{page-break-after:always;}'
        '.stamp-page:last-child{page-break-after:auto;}'
        '</style></head><body>' + ''.join(blocks) + '</body></html>'
    )


def _index_declared_total_pages():
    """Last page number printed in the report's Index (page 2). The Index
    also lists external annexures appended to the printed report as-is —
    "Details of Rakes Detention", the "Ready Reckoner" annexures — which have
    no generated pages behind them here, so the Index's last page number is
    larger than the count of pages this PDF actually renders. The footer's
    "Page N of TOTAL" should match the Index, not the render count, so this
    value (not len(main pages)) is what's stamped as the total.

    Derived from main._INDEX_SECTIONS' page counts, so it moves on its own
    whenever a section is added, split, or removed. Lazy import — main.py
    imports this module, so a top-level import would be circular."""
    try:
        from main import _INDEX_SECTIONS
        total = sum(int(count) for _title, count in _INDEX_SECTIONS)
        return total or None
    except Exception:
        return None


def _stamp_main_overlays(pdf_bytes: bytes, browser, font_family: str, report_month: str,
                         main_start: int, main_count: int, total_pages: int = None,
                         dept_badges: dict = None, start_of: dict = None) -> bytes:
    """The single post-render overlay pass over the assembled document:
    onto every page in the [main_start, main_start+main_count) physical
    range it merges ONE overlay page carrying the header, the footer's
    "Page N of TOTAL", and — for pages dept_badges covers — the corner
    department badge. Cover/Index pages outside that range are untouched.

    Why post-render at all: the main content is assembled from several
    page.pdf() calls (portrait pages + spliced-in landscape runs, see
    _render_landscape_page_pdf), and Chromium's own pageNumber/totalPages
    counters are per call, so only a Python-computed stamp numbers every
    page correctly; and the badge must sit at the true physical corner,
    which Chromium clips from in-document content (see _dept_badge_html).

    The header/footer and badge used to be two separate passes, each
    reading, merging onto and re-writing the whole ~100-page document; one
    combined overlay per page does that work once. Overlays are batched
    into as few page.pdf() calls as there are distinct physical page sizes
    (1, or 2 with landscape pages).

    `total_pages` is the "of N" shown in the footer — the Index's declared
    last page (see _index_declared_total_pages), which counts the external
    annexures too; falls back to `main_count`. Per-page numbering runs
    1..main_count.

    `start_of` ({report page id: physical index}, see _page_markers) is
    required whenever dept_badges is given. Badge side alternates with the
    footer's page number (odd = right), so it stays correct across a
    section's continuation pages."""
    from pypdf import PdfReader, PdfWriter

    footer_total = total_pages or main_count

    reader = PdfReader(io.BytesIO(pdf_bytes))
    n = len(reader.pages)
    group_of = _badge_group_by_physical(n, dept_badges, start_of) if dept_badges and start_of else {}

    # (rounded width, rounded height) -> [(physical index, page_num), ...],
    # preserving the true (unrounded) w_pt/h_pt seen for that dimension so
    # the batch's own page.pdf() call sizes to it exactly.
    groups: dict = {}
    dims: dict = {}
    for k in range(main_start, min(main_start + main_count, n)):
        page = reader.pages[k]
        w_pt, h_pt = float(page.mediabox.width), float(page.mediabox.height)
        dim_key = (round(w_pt), round(h_pt))
        dims[dim_key] = (w_pt, h_pt)
        groups.setdefault(dim_key, []).append((k, k - main_start + 1))

    overlay_by_index = {}
    for dim_key, entries in groups.items():
        w_pt, h_pt = dims[dim_key]
        margin_side = "15mm" if round(w_pt) < round(h_pt) else "10mm"
        w_mm, h_mm = w_pt * 25.4 / 72, h_pt * 25.4 / 72
        blocks = []
        for k, page_num in entries:
            group = group_of.get(k)
            badge_html = (_dept_badge_html("right" if page_num % 2 == 1 else "left", group, font_family)
                          if group is not None else "")
            blocks.append(_main_header_footer_overlay_block_html(
                font_family, report_month, page_num, footer_total, margin_side, w_mm, h_mm, badge_html))
        op = browser.new_page()
        op.set_content(_wrap_stamp_batch_html(blocks), wait_until="domcontentloaded")
        batch_pdf = op.pdf(
            width=f"{w_mm}mm", height=f"{h_mm}mm",
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            print_background=True,
        )
        op.close()
        batch_pages = PdfReader(io.BytesIO(batch_pdf)).pages
        for (k, _page_num), overlay_page in zip(entries, batch_pages):
            overlay_by_index[k] = overlay_page

    writer = PdfWriter()
    for k in range(n):
        page = reader.pages[k]
        overlay_page = overlay_by_index.get(k)
        if overlay_page is not None:
            page.merge_page(overlay_page)
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _render_pdf(browser, front_html: str, main_html: str, font_family: str = _DEFAULT_FONT, report_month: str = "",
                 cover_html: str = "", main_header_footer: bool = True,
                 total_pages_override: int = None, phase_prefix: str = "render") -> bytes:
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
    """
    from pypdf import PdfReader, PdfWriter
    hdr_font = f"'{font_family}',Arial,sans-serif"
    margin = _MAIN_MARGIN
    zero_margin = {"top": "0", "right": "0", "bottom": "0", "left": "0"}

    writer = PdfWriter()

    if cover_html:
        with _time_phase(f"{phase_prefix}: cover page"):
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
        with _time_phase(f"{phase_prefix}: front/index page"):
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
        with _time_phase(f"{phase_prefix}: main content — initial layout"):
            _load_for_print(page, main_html, _PRINTABLE_PORTRAIT_MM)
        # "of N": the Index's declared last page when the caller supplies it
        # (it counts the external annexures the report appends as-is — see
        # _index_declared_total_pages), else Chromium's own page total.
        _total_html = str(total_pages_override) if total_pages_override else '<span class="totalPages"></span>'
        _footer_html = (
            f'<div style="width:100%;padding:0 15mm;box-sizing:border-box;'
            f'font-family:{hdr_font};font-size:7.5pt;color:#64748b;'
            f'display:flex;justify-content:space-between;'
            f'border-top:0.5px solid #e2e8f0;padding-top:3px;">'
            f'<span>figures are provisional</span>'
            f'<span>MIS Operations</span>'
            f'<span>OMI - {report_month}</span>'
            f'<span>for internal circulation only</span>'
            f'<span>Page <span class="pageNumber"></span> of {_total_html}</span>'
            f'</div>'
        )
        # prefer_css_page_size=True (2026-09-18): per Chrome DevTools
        # Protocol's own Page.printToPDF docs, preferCSSPageSize "Defaults
        # to false, in which case the content will be scaled to fit the
        # paper size" — that default-false scale-to-fit is the documented
        # root cause behind page_techno.py's techno_month_table_font_size()
        # and this file's own page-3-overflow handling: ANY main-content
        # page overflowing format="A4" here can silently rescale the WHOLE
        # merged document, not just that one page. True=off disables that
        # global rescale, so an overflowing page just extends onto extra
        # physical pages instead of shrinking every other page with it.
        # Verified no regression from flipping this on a representative
        # sample (generate_pdf_bytes(pages_override=[...]), pixel-diffed):
        # a normal content page (4), the special-steel donut pairing (23,
        # 24 — see page_special_steel_donut.py's _bubble_chart_svg
        # docstring), and — the highest-risk case, since named @page rules
        # like .techno-mill-page's "size: A4 landscape" already silently
        # take effect TODAY even with this flag at its default false, per
        # the base @page{} rule's own comment above re: a past landscape-
        # bleed bug — a techno-mill page (31) alone. All came out
        # pixel-identical bar sub-point page-box rounding (<0.5mm, from
        # Chromium computing "A4" from the CSS keyword rather than from
        # Playwright's format="A4" inches conversion). Could NOT reproduce
        # the original whole-document-shrink failure itself even forcing a
        # raw (unmitigated) 12-YTD-month page 28/29 techno table — those
        # already fit the printable width fine at their static config font
        # size given the layout tuning done since that bug was first
        # logged, so this is defense-in-depth for whenever a page DOES
        # overflow again, not a fix verified against a live repro. Re-run
        # that same pages_override probe (or a full real-report render)
        # before trusting this further if content grows enough to actually
        # overflow a page again.
        with _time_phase(f"{phase_prefix}: main content — final print"):
            main_bytes = page.pdf(
                format="A4",
                prefer_css_page_size=True,
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
                footer_template=_footer_html if main_header_footer else '<span></span>',
                margin=margin,
            )
            page.close()
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
    idx3 = next((i for i, p in enumerate(main_pages) if p.get("page") == 3), None)
    if idx3 is None:
        return False
    next_marker = None
    measured_pages = main_pages[:idx3 + 1]
    if idx3 + 1 < len(main_pages):
        next_marker = f"@@PGSTART_{main_pages[idx3 + 1].get('page')}@@"
        measured_pages = main_pages[:idx3 + 2]

    html = template.render(pages=measured_pages, **render_kwargs)
    with _time_phase("page3 overflow check"):
        pdf_bytes = _render_pdf(browser, "", html, font_family, report_month, phase_prefix="page3-overflow probe")
    p3_physical = next_physical = None
    for pi, text in enumerate(_page_texts(pdf_bytes)):
        if p3_physical is None and "@@PGSTART_3@@" in text:
            p3_physical = pi
        if next_marker and next_physical is None and next_marker in text:
            next_physical = pi
    if p3_physical is None or next_physical is None:
        # Can't determine (page 3 is the last page in this request, or a
        # marker wasn't found) — don't guess, leave the default layout.
        return False
    return (next_physical - p3_physical) > 1


def _ready_reckoner_details_fits(browser, page_data: dict, template, render_kwargs: dict,
                                  font_family: str, report_month: str) -> bool:
    """True if `page_data` (a ready_reckoner 'details' page — Unit-wise
    Capacity + Product Mix combined at its configured 12pt font, per direct
    instruction 2026-09-22) prints on a single physical page. Measured by a
    real isolated render+print, never guessed from row counts: table cells
    wrap unpredictably, so only an actual Chromium print can answer this
    reliably.

    Unlike page 3 (_measure_page3_overflow, which explicitly rejects
    isolating that page because its break position depends on what's
    rendered around it), a ready-reckoner content page has no such
    dependency: it's its own `.page` div with a forced page-break-after,
    self-contained regardless of neighbors, and _render_pdf's margin is a
    fixed constant rather than derived from surrounding content — so
    printing it alone in its own tiny document reproduces the exact same
    break it would get at its real spot in the full report."""
    import io as _io
    from pypdf import PdfReader

    html = template.render(pages=[page_data], **render_kwargs)
    with _time_phase(f"ready-reckoner fit probe: {page_data.get('plant_code')}"):
        pdf_bytes = _render_pdf(browser, "", html, font_family, report_month,
                                 phase_prefix="ready-reckoner fit probe")
    return len(PdfReader(_io.BytesIO(pdf_bytes)).pages) <= 1


def _split_ready_reckoner_overflow(main_pages: list, browser, template, render_kwargs: dict,
                                    font_family: str, report_month: str) -> None:
    """Mutates `main_pages` in place: for every ready_reckoner 'details'
    page (Unit-wise Capacity + Product Mix combined) that
    _ready_reckoner_details_fits measures as NOT fitting one physical page,
    re-labels it 'capacity' (Unit-wise Capacity alone) and inserts a new
    'product_mix' page (Product Mix alone) right after it, using that
    plant's reserved id from PRODUCT_MIX_OVERFLOW_PAGE_ID — see
    page_ready_reckoner.py's module docstring. Per direct instruction,
    2026-09-22: merge onto one page only when there's room at the
    configured 12pt content font, never by shrinking it. Live preview is
    untouched (it always shows the merged 'details' page — see
    ReadyReckonerTemplate.js's own comment) since this only ever runs on
    main_pages built for a PDF export.

    This DOES fire against the real ready_reckoner_pages data (measured
    2026-09-22: BSP, RSP and BSL don't fit their combined table at 12pt;
    DSP, ISP, and all 3 SSPs do) — so the footer's "Page N of TOTAL" and the
    Index's own declared Annexure-1/2 page range must both account for
    however many plants split. NOT auto-corrected here (that was tried and
    then deliberately removed, 2026-09-22, in favor of hand-maintaining
    both in main.py's _INDEX_SECTIONS — update those two counts whenever a
    Ready Reckoner data-entry edit changes which plants split)."""
    from page_ready_reckoner import generate_ready_reckoner_page, PRODUCT_MIX_OVERFLOW_PAGE_ID
    from report_utils import assign_dept_badges

    i = 0
    while i < len(main_pages):
        p = main_pages[i]
        if p.get("type") == "ready_reckoner" and p.get("subtype") == "details":
            if not _ready_reckoner_details_fits(browser, p, template, render_kwargs, font_family, report_month):
                plant_code = p.get("plant_code")
                overflow_id = PRODUCT_MIX_OVERFLOW_PAGE_ID.get(plant_code)
                if overflow_id is not None:
                    p["subtype"] = "capacity"
                    p["subtype_label"] = "Unit-wise Capacity"
                    p["title"] = f"Ready Reckoner – {p.get('plant_name')} – Unit-wise Capacity"
                    pm_page = generate_ready_reckoner_page(plant_code, "product_mix")
                    pm_page["page"] = overflow_id
                    assign_dept_badges([pm_page])
                    main_pages.insert(i + 1, pm_page)
                    i += 1
        i += 1


# Tightest top/bottom margins (mm) _plan_trend_layout may shrink the trend
# section's configured ones (layout_config.json's marginTop/marginBottom for
# its first page, currently 7mm/5mm) down to — any tighter risks crowding
# the printed header/footer.
_TREND_MIN_TOP_MARGIN_MM = 4
_TREND_MIN_BOTTOM_MARGIN_MM = 2

# A plant/SAIL group may split across a page break only if at least this
# many of its rows land on EACH side of the break; otherwise the whole group
# moves to the next page.
_TREND_MIN_SPLIT_ROWS = 3

# Checks after applying the planned segments (see _plan_trend_layout).
_TREND_MAX_VERIFY_PASSES = 3

# content hash of the trend section's HTML -> the plan _plan_trend_layout
# measured for it (margins + every row's segment fields), so a repeat export
# of unchanged data skips its probe prints. Capped.
_TREND_PLAN_CACHE: dict = {}
_TREND_PLAN_CACHE_MAX_ENTRIES = 200

_TREND_ROW_FIELDS = ("tbody_start", "rowspan_start", "plant_row_count", "label_hidden")


def _trend_groups(rows: list) -> list:
    """(start, end) of every run of consecutive rows sharing a plant."""
    groups, i = [], 0
    while i < len(rows):
        j = i
        while j < len(rows) and rows[j]["plant"] == rows[i]["plant"]:
            j += 1
        groups.append((i, j))
        i = j
    return groups


def _set_trend_blocks(rows: list, start: int, bounds: list, label_hidden: bool) -> None:
    """Makes each [a, b) in bounds its own <tbody> block with its own
    rowspan'd plant label (see trend_section.html)."""
    for a, b in bounds:
        for k in range(a, b):
            rows[k]["tbody_start"] = rows[k]["rowspan_start"] = (k == a)
            rows[k]["plant_row_count"] = b - a
            rows[k]["label_hidden"] = label_hidden


def _check_trend_pieces(items: list, page_of: list) -> None:
    """Layout warnings for the final trend plan, from its last probe:
    a piece of a split group shorter than _TREND_MIN_SPLIT_ROWS, or one
    unbreakable block whose rows still landed on more than one page."""
    for it, pages in zip(items, page_of):
        rows = it.get("rows", [])
        name = it.get("item_display", "?")
        for a, b in _trend_groups(rows):
            starts = [k for k in range(a, b) if rows[k].get("tbody_start")] or [a]
            edges = starts + [b]
            pieces = list(zip(edges, edges[1:]))
            plant = rows[a]["plant"]
            for s, e in pieces:
                if len({pages[k] for k in range(s, e)}) > 1:
                    _layout_warn(f"trend section: {name} / {plant} rows {s - a + 1}-{e - a} span a page "
                                 f"break inside one block (block taller than a page?)")
                if len(pieces) > 1 and e - s < _TREND_MIN_SPLIT_ROWS:
                    _layout_warn(f"trend section: {name} / {plant} split leaves only {e - s} row(s) on "
                                 f"one page (minimum {_TREND_MIN_SPLIT_ROWS})")


def _plan_trend_layout(browser, trend_pages: list, template, render_kwargs: dict) -> None:
    """Decides where plant/SAIL groups in the trend section (pages 7-13) may
    split across a page, and picks the section's top/bottom margins. Mutates
    each row's block fields (_TREND_ROW_FIELDS) and
    render_kwargs["page_layouts"] in place; must run before main_html is
    rendered.

    Rule: a group splits only when at least _TREND_MIN_SPLIT_ROWS of its rows
    land on each side of the break, else it moves to the next page whole;
    each piece gets its own plant label.

    Chromium chooses the break points itself: the probe print cuts each
    group into unbreakable <tbody> blocks — its first MIN rows, each middle
    row alone, its last MIN rows — so the only places Chromium CAN break a
    group leave >= MIN rows on both sides (a group shorter than 2*MIN is one
    block). The probe shows where each group actually broke; each group is
    then rebuilt as one block per page-piece, labelled, and re-printed to
    verify. A piece can grow slightly once its label is filled in, and
    could then be pushed whole onto the next page; if two pieces of a group
    end up on the same page they're merged back and it's re-checked.

    The trend section always starts on a fresh page with the same print
    options as the final render, so it's probed in isolation: each print is
    ~14 pages, not the whole report. The tighter _TREND_MIN_* margins are
    kept only if they save a page."""
    import hashlib

    if not trend_pages:
        return
    page_layouts = render_kwargs.setdefault("page_layouts", {})
    keys = [str(tp.get("page")) for tp in trend_pages]
    base = page_layouts.get(keys[0], {})
    default = (base.get("marginTop", 7), base.get("marginBottom", 5))
    floor = (min(default[0], _TREND_MIN_TOP_MARGIN_MM), min(default[1], _TREND_MIN_BOTTOM_MARGIN_MM))
    items = [it for tp in trend_pages for it in tp.get("items", [])]

    def _apply_margins(margins):
        for key in keys:
            entry = dict(page_layouts.get(key, {}))
            entry["marginTop"], entry["marginBottom"] = margins
            page_layouts[key] = entry

    def _render():
        return template.render(pages=trend_pages, **render_kwargs)

    cache_key = hashlib.sha256(_render().encode("utf-8")).hexdigest()
    cached = _TREND_PLAN_CACHE.get(cache_key)
    if cached is not None:
        _apply_margins(cached["margins"])
        for it, saved_rows in zip(items, cached["rows"]):
            for row, saved in zip(it.get("rows", []), saved_rows):
                row.update(saved)
        return

    page = browser.new_page()

    def _probe():
        """Prints the trend section alone; returns (page count,
        [[physical page of each row] per item])."""
        _load_for_print(page, _render(), _PRINTABLE_PORTRAIT_MM)
        pdf_bytes = page.pdf(format="A4", prefer_css_page_size=True, print_background=True,
                             display_header_footer=False, margin=_MAIN_MARGIN)
        texts = _page_texts(pdf_bytes)
        found = {}
        for pno, text in enumerate(texts):
            for ii, k in re.findall(r"@@TROW_(\d+)_(\d+)@@", text):
                found.setdefault((int(ii), int(k)), pno)
        return len(texts), [[found.get((ii, k)) for k in range(len(it.get("rows", [])))]
                            for ii, it in enumerate(items)]

    def _chunk_all():
        m = _TREND_MIN_SPLIT_ROWS
        for it in items:
            rows = it.get("rows", [])
            for a, b in _trend_groups(rows):
                if b - a < 2 * m:
                    bounds = [(a, b)]
                else:
                    bounds = [(a, a + m)] + [(k, k + 1) for k in range(a + m, b - m)] + [(b - m, b)]
                _set_trend_blocks(rows, a, bounds, label_hidden=True)

    try:
        # 1. Chunked probe at each candidate margin; keep the tighter margins
        #    only if they save a page.
        _chunk_all()
        _apply_margins(default)
        chosen, (n_pages, page_of) = default, _probe()
        if floor != default:
            _apply_margins(floor)
            n_floor, page_of_floor = _probe()
            if n_floor < n_pages:
                chosen, n_pages, page_of = floor, n_floor, page_of_floor
        _apply_margins(chosen)

        # 2. One labelled block per page-piece of each group, where the
        #    chunked probe put its breaks.
        for it, pages in zip(items, page_of):
            rows = it.get("rows", [])
            for a, b in _trend_groups(rows):
                if any(p is None for p in pages[a:b]):
                    bounds = [(a, b)]  # marker not found: don't split blind
                else:
                    cuts = [k for k in range(a + 1, b) if pages[k] != pages[k - 1]]
                    edges = [a] + cuts + [b]
                    bounds = list(zip(edges, edges[1:]))
                _set_trend_blocks(rows, a, bounds, label_hidden=False)

        # 3. Verify; merge pieces of a group that landed on the same page.
        for _ in range(_TREND_MAX_VERIFY_PASSES):
            _n, page_of = _probe()
            merged = False
            for it, pages in zip(items, page_of):
                rows = it.get("rows", [])
                for a, b in _trend_groups(rows):
                    starts = [k for k in range(a, b) if rows[k]["tbody_start"]]
                    if len(starts) < 2:
                        continue
                    edges = starts + [b]
                    bounds = [list(p) for p in zip(edges, edges[1:])]
                    kept = [bounds[0]]
                    for s, e in bounds[1:]:
                        if pages[s] is not None and pages[s] == pages[kept[-1][0]]:
                            kept[-1][1] = e
                            merged = True
                        else:
                            kept.append([s, e])
                    if len(kept) != len(bounds):
                        _set_trend_blocks(rows, a, [tuple(p) for p in kept], label_hidden=False)
            if not merged:
                break
        else:
            _layout_warn("trend section: page-split planning did not settle within "
                         f"{_TREND_MAX_VERIFY_PASSES} checks - a plant label may repeat on one page")
        _check_trend_pieces(items, page_of)
    finally:
        page.close()

    if len(_TREND_PLAN_CACHE) >= _TREND_PLAN_CACHE_MAX_ENTRIES:
        _TREND_PLAN_CACHE.pop(next(iter(_TREND_PLAN_CACHE)))
    _TREND_PLAN_CACHE[cache_key] = {
        "margins": chosen,
        "rows": [[{f: row.get(f) for f in _TREND_ROW_FIELDS} for row in it.get("rows", [])] for it in items],
    }


def _marker_page_index(page_texts: list, page_id) -> int:
    """Physical index (0-based) of the first entry in `page_texts` (each
    one a physical page's own extract_text() output) carrying page_id's
    own @@PGSTART_N@@ marker, or None if not found. Shared by every
    marker-based measurement/splice in this file — see main.html's
    .pg-badge-marker comment for why this text-marker technique exists at
    all, and _measure_page3_overflow for the pattern this generalizes."""
    marker = f"@@PGSTART_{page_id}@@"
    return next((i for i, t in enumerate(page_texts) if marker in t), None)


# _INDEX_SECTIONS rows whose OWN nominal page count is never replaced by a
# real measurement in _correct_dynamic_index_pagination, even though every
# other row is. Ready Reckoner's per-plant overflow (a plant's combined
# Unit-wise Capacity + Product Mix page splitting into 2 when it doesn't fit
# at the configured font — see _split_ready_reckoner_overflow) already tried
# auto-correcting the Index for this, then had that deliberately reverted on
# 2026-09-22 in favor of hand-maintaining main.py's _INDEX_SECTIONS counts
# instead (see _split_ready_reckoner_overflow's own docstring) — the exact
# reasoning for the revert isn't recorded, so rather than silently re-
# overriding that recorded decision, this generalization carves these two
# rows back out. Their STARTING page number is still corrected for free
# (every row's page_range is computed from the cumulative real counts of
# every row before it) — only their own span stays hand-maintained.
_INDEX_ROWS_NOT_AUTO_CORRECTED = {
    "Annexure-1 : 5 ISPs Ready Reckoner",
    "Annexure-2 : 3 SSPs Ready Reckoner",
}


def _correct_dynamic_index_pagination(pdf_bytes: bytes, browser, front_pages: list, main_pages: list,
                                       template, render_kwargs: dict, font_family: str, report_month: str,
                                       nominal_total) -> tuple:
    """Post-render fix-up, generalized (2026-09-22) across every
    main.py._INDEX_SECTIONS row — was _correct_dynamic_trend_pagination,
    fixing only the trend row, until real reports showed the same drift
    elsewhere: "SAIL Large BFs - Performance Snapshot" declared 2 physical
    pages but rendering as 1, and "Plant Wise Area Wise TEPs" declared 10
    but rendering as 9, each throwing off the Index-declared page number
    (and the footer's "Page N of TOTAL") for every row after it, including
    both Ready Reckoner annexures.

    Every row's nominal count in _INDEX_SECTIONS is a hand-maintained
    number that drifts the moment that row's real content grows or shrinks
    enough to gain or lose a physical page — the trend row was simply the
    first place this got a proper per-render fix (its page count depends
    on the month's data — see _plan_trend_layout).

    Fixed the same way for every row now: every page dict in `main_pages`
    still carries its own @@PGSTART_{{page.page}}@@ marker (see main.html's
    .pg-badge-marker comment). main._INDEX_SECTION_ANCHORS gives, for every
    _INDEX_SECTIONS row in the same order, the `page` id of that row's FIRST
    page dict — regardless of how many page dicts or physical pages the row
    actually ends up spanning. A row's TRUE physical-page count is simply
    the gap between its own anchor's physical position (from the just-
    rendered `pdf_bytes`, same @@PGSTART_N@@ marker technique
    _measure_page3_overflow uses) and the next row's anchor's physical
    position (or the document's end, for the last row) — this naturally
    absorbs a page dict overflowing onto an extra physical page anywhere
    inside the row (e.g. TEPs' own IRON_MAKING_PAGE_2_ID spilling over)
    without needing to know a row's internal dict structure at all, exactly
    as it already did for the trend row's own internal item/plant splits.

    _INDEX_ROWS_NOT_AUTO_CORRECTED (Ready Reckoner's two annexure rows)
    always keep their nominal count rather than a measured one — see that
    set's own comment. A row whose anchor marker isn't found at all (a
    genuine partial export missing that section), or whose OWN measured
    span comes back <= 0 (a marker collision/ordering surprise — don't
    trust it), falls back to nominal too rather than guess.

    Must run on a `pdf_bytes` whose main-content footer band is still
    BLANK (main_header_footer=False on whatever _render_pdf call produced
    it) — the caller's own _stamp_main_overlays call, using this
    function's returned total, is the only thing that ever draws footer
    text onto these pages. Stamping before this ran, or stamping twice,
    would double-print overlapping "Page N of TOTAL" text — see the
    "main content — TOTAL" call sites in _generate_pdf_sync for why both
    branches now defer all footer stamping until after this runs.

    Returns (pdf_bytes, total_pages): pdf_bytes is returned unchanged and
    total_pages == nominal_total in the common case (every row already
    matches its nominal count this month, or there's no Index in this
    render at all — e.g. a partial export)."""
    from pypdf import PdfReader, PdfWriter
    from main import _INDEX_SECTIONS, _INDEX_SECTION_ANCHORS

    if not main_pages:
        return pdf_bytes, nominal_total

    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_texts = _page_texts(pdf_bytes)

    index_i = _marker_page_index(page_texts, 2)
    if index_i is None:
        return pdf_bytes, nominal_total  # no Index in this render (e.g. a partial export)

    # Physical index of every row's own anchor marker, in row order; None
    # where that page dict never rendered at all (e.g. a partial export
    # missing that section entirely).
    anchor_pos = [_marker_page_index(page_texts, anchor) for anchor in _INDEX_SECTION_ANCHORS]

    n = len(_INDEX_SECTIONS)
    rows = []
    cursor = 1
    changed = False
    for i, (title, nominal_count) in enumerate(_INDEX_SECTIONS):
        real_count = None
        start = anchor_pos[i]
        if title not in _INDEX_ROWS_NOT_AUTO_CORRECTED and start is not None:
            if i + 1 < n and anchor_pos[i + 1] is not None:
                real_count = anchor_pos[i + 1] - start
            elif i + 1 == n:
                real_count = len(page_texts) - start
        count = real_count if real_count is not None and real_count > 0 else nominal_count
        if count != nominal_count:
            changed = True
        page_range = str(cursor) if count == 1 else f"{cursor}-{cursor + count - 1}"
        rows.append({"sno": str(i + 1), "title": title, "page_range": page_range})
        cursor += count
    new_total = cursor - 1

    if not changed:
        return pdf_bytes, nominal_total  # every row already matches its nominal count

    index_page = next((dict(p) for p in front_pages if p.get("page") == 2), None)
    if index_page is None:
        return pdf_bytes, nominal_total
    index_page["rows"] = rows

    new_index_html = template.render(pages=[index_page], **render_kwargs)
    op = browser.new_page()
    try:
        op.set_content(new_index_html, wait_until="domcontentloaded")
        op.evaluate("document.fonts.ready")
        new_index_bytes = op.pdf(
            format="A4", print_background=True, display_header_footer=False, margin=_FRONT_MARGIN,
        )
    finally:
        op.close()
    new_index_reader = PdfReader(io.BytesIO(new_index_bytes))
    if len(new_index_reader.pages) != 1:
        # The corrected Index somehow spilled onto a 2nd physical page --
        # every downstream physical position this function assumed would
        # now be wrong. Don't guess at a fix; leave the nominal Index/
        # total in place rather than risk corrupting the document.
        return pdf_bytes, nominal_total

    writer = PdfWriter()
    for k, p in enumerate(reader.pages):
        writer.add_page(new_index_reader.pages[0] if k == index_i else p)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue(), new_total


_PW_STATE = {"pw": None, "browser": None}


def _get_persistent_browser():
    """Reuses one Chromium instance across PDF jobs instead of launching a
    fresh one per report. A cold chromium.launch() can take anywhere from
    ~20s to 180s+ depending on system/antivirus load (each launch is a new,
    previously-unscanned process as far as Windows Defender is concerned),
    and that cost used to sit directly in the critical path of every single
    report generation. generate_pdf_bytes always runs _generate_pdf_sync on
    the single-worker _PDF_EXECUTOR thread, so this module-level state is
    never touched from more than one thread at a time — no lock needed.
    """
    from playwright.sync_api import sync_playwright
    browser = _PW_STATE["browser"]
    if browser is not None:
        try:
            if browser.is_connected():
                return browser
        except Exception:
            pass
    if _PW_STATE["pw"] is None:
        _PW_STATE["pw"] = sync_playwright().start()
    browser = _PW_STATE["pw"].chromium.launch()
    _PW_STATE["browser"] = browser
    # `pip install -r requirements.txt` pins the playwright *package* but
    # never re-downloads the Chromium *binary* it drives — a machine whose
    # browser cache predates the current pin (or was populated under a
    # different one) keeps rendering with a stale Chromium build forever,
    # completely invisibly: `pip freeze` still reports the pinned package
    # version. Confirmed root cause of two machines on the identical commit
    # (identical pip freeze too) producing a different physical page count
    # for the same month's trend section, 2026-09-19 — one had chromium-1234
    # (151.0.7922.34), the other an older cached build. Logged once per
    # process (not per report) so a future drift like this shows up in the
    # server's own logs instead of only surfacing as a mismatched PDF
    # someone has to notice and diff by hand.
    print(f"[pdf] Chromium: {browser.version} ({_PW_STATE['pw'].chromium.executable_path})")
    return browser


def _generate_pdf_sync(front_pages: list, main_pages: list, template, render_kwargs: dict,
                        merged_page_layouts: dict, font_family: str, report_month: str) -> bytes:
    """Single Playwright entry point for a whole PDF request: reuses the
    persistent Chromium instance (see _get_persistent_browser) for every
    pass — the page-3 overflow check and the final render — instead of
    launching (and closing) a fresh browser process per report. This is
    purely an execution-plumbing change (same HTML, same measurements,
    same output); it does not affect layout, fonts, or page counts.

    Trend-table pagination is planned beforehand by _plan_trend_layout,
    on the trend section alone (see its docstring).

    Mutates main_pages/merged_page_layouts in place exactly as the previous
    per-pass functions did (trend row is_first_in_plant/plant_row_count, and
    merged_page_layouts["3"]'s margins) — render_kwargs["page_layouts"] *is*
    merged_page_layouts (same dict object), so the final template.render()
    below picks up the page-3 adjustment automatically.
    """
    _TIMING_LOG.clear()
    _LAYOUT_WARNINGS.clear()
    try:
        import layout_guard
        for msg in layout_guard.changed_file_warnings():
            _layout_warn(msg)
    except Exception as e:  # the guard must never break a render
        print(f"[pdf] layout_guard check skipped: {type(e).__name__}: {e}")
    _render_t0 = _time.perf_counter()

    # Footer "Page N of TOTAL": TOTAL is the Index's declared last page (it
    # counts the external annexures the printed report appends as-is), not
    # the count of pages this PDF renders. Only for a full report (page 2 /
    # Index present); a single-page fetch keeps Chromium's own page total.
    _has_index = any(p.get("page") == 2 for p in front_pages)
    footer_total_override = _index_declared_total_pages() if _has_index else None

    browser = _get_persistent_browser()

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
            # Margins/table padding alone still weren't enough on months with
            # more Highlights sections (quarter/half/FY-end months, up to 9
            # lines) — verified empirically (generate_pdf_bytes against 10
            # real report months) that neither lever fixes those months on
            # its own, but tightening the narrative/Highlights line-height
            # (1.4 -> 1.15, font size untouched) together with a shorter
            # chart SVG viewBox (168 -> 130, main_pages' page-3 dict is
            # mutated in place below) reliably does. Chart height alone,
            # even down to a viewBox of 40, did nothing by itself in the
            # same test — page 3's content above the charts already ran the
            # page out of room with zero slack left for row 2 of the chart
            # grid, so it's the combination that creates the needed margin,
            # not either change alone.
            _p3_entry["p3TextLineHeight"] = 1.15
            merged_page_layouts["3"] = _p3_entry
            _p3 = next((p for p in main_pages if p.get("page") == 3), None)
            if _p3 is not None and _p3.get("chart_data"):
                from page_techno import generate_summary_chart_html
                _p3["_chart_html"] = generate_summary_chart_html(_p3["chart_data"], vh=130)

    # Ready Reckoner: split a plant's combined Unit-wise Capacity + Product
    # Mix page across 2 physical pages instead of the usual 1, but only for
    # a plant whose content actually measures as not fitting at the
    # configured 12pt font — see _split_ready_reckoner_overflow. The footer
    # total and the Index's own declared Annexure-1/2 range are NOT
    # auto-corrected for this (per direct instruction, 2026-09-22 — was
    # auto-corrected until now): both are hand-maintained in main.py's
    # _INDEX_SECTIONS instead, so update that whenever a Ready Reckoner
    # data-entry edit changes which plants split.
    if any(p.get("type") == "ready_reckoner" and p.get("subtype") == "details" for p in main_pages):
        _split_ready_reckoner_overflow(main_pages, browser, template, render_kwargs, font_family, report_month)

    # Trend section: must run before main_html is rendered below — it sets
    # the rows' page-split blocks and may change the section's margins in
    # render_kwargs["page_layouts"].
    _trend_pages = [p for p in main_pages if p.get("type") == "trend_section"]
    if _trend_pages:
        with _time_phase("trend layout plan"):
            _plan_trend_layout(browser, _trend_pages, template, render_kwargs)

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
    # header/footer from scratch (_stamp_main_overlays) — Chromium's
    # own pageNumber/totalPages counters are per-call and reset to 1/1
    # for the spliced-in pages, so nothing downstream of them would show
    # a correct "Page N of TOTAL" without this.
    # Pages that need a genuinely wider physical page: "Large BFs" +
    # the 3 Cost Trend pages right after it (one contiguous block near
    # page 3.6), "Special Steel Plants Physical Performance" (a second
    # block near page 24), "Major Environmental Performance
    # Indicators (EPIs) - Plant Wise" (page_epi.py, per direct
    # instruction — its many FY-to-date monthly columns need the extra
    # width), "Rail Production & Dispatch from BSP" (page 18.5,
    # page_rail_report.py — one column per FY since 2015-16 needs the
    # extra width too), and "Movement of Key Prices - International" /
    # "India Macro Economic Indicators" (pages 2.41/2.42, page_market_
    # prices.py / page_macro_indicators.py — a 2-chart landscape page and a
    # 13-column monthly matrix, per direct instruction, 2026-09-17). Each
    # contiguous run is rendered separately at
    # true A4-landscape and spliced back into the merged document at its
    # original position, then every main-content page's header/footer
    # is re-stamped from scratch (Chromium's own pageNumber/totalPages
    # counters are per-call).
    _LANDSCAPE_TYPES = ("bf_large_annexure", "cost_trend", "special_steel_physical", "epi", "rail_report",
                        "market_prices", "macro_indicators")

    def _is_landscape_page(p: dict) -> bool:
        """True for a fixed landscape page type, OR a page that opted into
        landscape for itself via a "pdf_landscape" flag on its own page
        dict (e.g. page_ready_reckoner.py's process-flow page, whose
        orientation follows the uploaded diagram's own shape rather than a
        page-type-wide rule)."""
        return p.get("type") in _LANDSCAPE_TYPES or bool(p.get("pdf_landscape"))

    from pypdf import PdfReader

    _landscape_pages = [p for p in main_pages if _is_landscape_page(p)]
    if not _landscape_pages:
        main_html = template.render(pages=main_pages, **render_kwargs) if main_pages else ""
        # main_header_footer=False (was True — baking Chromium's own inline
        # footer straight into this one print call) since 2026-09-22: with
        # the trend section's page count depending on its data, its real page
        # count (and therefore the correct "of TOTAL") isn't known until
        # AFTER this render — see _correct_dynamic_index_pagination and the
        # _stamp_main_overlays call below, the same blank-then-stamp
        # pattern the landscape branch already used. Stamping the footer
        # inline here and then overlaying a second, corrected one on top
        # would double-print overlapping text — _stamp_main_overlays
        # only ever draws over a page whose footer band is genuinely blank.
        with _time_phase("main content — TOTAL"):
            pdf_bytes = _render_pdf(browser, front_html, main_html, font_family, report_month,
                                     cover_html=cover_html,
                                     main_header_footer=False, phase_prefix="main content")
        with _time_phase("dynamic index pagination check"):
            pdf_bytes, footer_total_override = _correct_dynamic_index_pagination(
                pdf_bytes, browser, front_pages, main_pages, template, render_kwargs,
                font_family, report_month, footer_total_override)
        _main_texts = _page_texts(pdf_bytes)
        _main_start = _marker_page_index(_main_texts, main_pages[0].get("page")) if main_pages else 0
        if _main_start is None:
            _main_start = 0
        with _time_phase("header/footer + dept badge overlay"):
            pdf_bytes = _stamp_main_overlays(pdf_bytes, browser, font_family, report_month,
                                             _main_start, len(_main_texts) - _main_start,
                                             total_pages=footer_total_override,
                                             dept_badges=dept_badges, start_of=_page_markers(_main_texts))
    else:
        from pypdf import PdfReader, PdfWriter

        # Group the landscape pages into contiguous runs; each run's
        # "next_page" is the first non-landscape page after it (or None
        # if the run ends the document).
        _runs = []  # [{"pages": [...], "_end": idx, "next_page": id_or_None}]
        _prev_i = -2
        for _i, _p in enumerate(main_pages):
            if not _is_landscape_page(_p):
                continue
            if _runs and _prev_i == _i - 1:
                _runs[-1]["pages"].append(_p)
            else:
                _runs.append({"pages": [_p]})
            _runs[-1]["_end"] = _i + 1
            _prev_i = _i
        for _r in _runs:
            _start = _r["_end"] - len(_r["pages"])
            _r["next_page"] = next((p.get("page") for p in main_pages[_r["_end"]:]
                                    if not _is_landscape_page(p)), None)
            # the non-landscape page immediately before this run — used
            # to detect a "marker leak" (next_page's @@PGSTART@@ landing
            # at the bottom of prev_page's own physical page), which would
            # otherwise splice the run one page too early.
            _r["prev_page"] = next((p.get("page") for p in reversed(main_pages[:_start])
                                    if not _is_landscape_page(p)), None)

        _rest_pages = [p for p in main_pages if not _is_landscape_page(p)]

        main_html_rest = template.render(pages=_rest_pages, **render_kwargs) if _rest_pages else ""
        with _time_phase("main content (portrait pages) — TOTAL"):
            base_bytes = _render_pdf(browser, front_html, main_html_rest, font_family, report_month,
                                      cover_html=cover_html, main_header_footer=False,
                                      phase_prefix="main content (portrait pages)")

        base_reader = PdfReader(io.BytesIO(base_bytes))
        run_readers = []
        run_bytes = []
        for _r in _runs:
            _run_pages_desc = ", ".join(f"{p.get('page')}({p.get('type')})" for p in _r["pages"])
            with _time_phase(f"landscape run: {_run_pages_desc}"):
                _run_bytes = _render_landscape_page_pdf(
                    browser, template.render(pages=_r["pages"], **render_kwargs), font_family)
            run_readers.append(PdfReader(io.BytesIO(_run_bytes)))
            run_bytes.append(_run_bytes)

        # Extracted once, in one batch, and reused for every marker lookup
        # below (splice positioning AND, if dept_badges is set, its
        # physical-page map).
        base_page_texts, *run_page_texts = _page_texts_many([base_bytes, *run_bytes])

        def _marker_index(texts, page_id):
            marker = f"@@PGSTART_{page_id}@@"
            for k, text in enumerate(texts):
                if marker in text:
                    return k
            return None

        main_start = _marker_index(base_page_texts, _rest_pages[0].get("page")) if _rest_pages else 0
        if main_start is None:
            main_start = 0

        # base_reader page index -> list of run indices to insert *before* it
        _inserts = {}
        for run_idx, r in enumerate(_runs):
            at = _marker_index(base_page_texts, r["next_page"]) if r["next_page"] else len(base_reader.pages)
            if at is None:
                at = len(base_reader.pages)
            # If next_page's marker leaked onto the previous non-landscape
            # page's own physical page (i.e. that page carries BOTH
            # markers), splice after it rather than before — otherwise
            # the landscape run lands a page too early, ahead of content
            # that visually belongs before it.
            elif r["prev_page"] is not None and at < len(base_reader.pages) \
                    and f"@@PGSTART_{r['prev_page']}@@" in base_page_texts[at]:
                at += 1
            _inserts.setdefault(at, []).append(run_idx)

        # Every report page's physical index in the about-to-be-assembled
        # spliced_bytes, derived arithmetically from the same assembly loop
        # that builds it below, instead of re-extracting text from
        # spliced_bytes afterward — a report page's content is entirely
        # within base_reader OR entirely within one run, never split across
        # both, so base/run markers never collide.
        dept_start_of = None
        if dept_badges:
            base_markers = _page_markers(base_page_texts)
            run_markers = [_page_markers(texts) for texts in run_page_texts]
            spliced_index_of_base = {}
            spliced_index_of_run = {}  # run_idx -> {run_relative_idx: spliced_idx}

        writer = PdfWriter()
        spliced_idx = 0
        for k in range(len(base_reader.pages) + 1):
            for run_idx in _inserts.get(k, []):
                rr = run_readers[run_idx]
                for j, p in enumerate(rr.pages):
                    writer.add_page(p)
                    if dept_badges:
                        spliced_index_of_run.setdefault(run_idx, {})[j] = spliced_idx
                    spliced_idx += 1
            if k < len(base_reader.pages):
                writer.add_page(base_reader.pages[k])
                if dept_badges:
                    spliced_index_of_base[k] = spliced_idx
                spliced_idx += 1

        if dept_badges:
            dept_start_of = {}
            for report_pg, base_idx in base_markers.items():
                if base_idx in spliced_index_of_base:
                    dept_start_of[report_pg] = spliced_index_of_base[base_idx]
            for run_idx, markers in enumerate(run_markers):
                for report_pg, run_rel_idx in markers.items():
                    idx = spliced_index_of_run.get(run_idx, {}).get(run_rel_idx)
                    if idx is not None:
                        dept_start_of[report_pg] = idx

        out = io.BytesIO()
        writer.write(out)
        spliced_bytes = out.getvalue()

        _total_landscape = sum(len(rr.pages) for rr in run_readers)
        main_count = len(base_reader.pages) + _total_landscape - main_start
        with _time_phase("dynamic index pagination check"):
            spliced_bytes, footer_total_override = _correct_dynamic_index_pagination(
                spliced_bytes, browser, front_pages, main_pages, template, render_kwargs,
                font_family, report_month, footer_total_override)
        with _time_phase("header/footer + dept badge overlay (post-splice)"):
            spliced_bytes = _stamp_main_overlays(spliced_bytes, browser, font_family, report_month,
                                                 main_start, main_count,
                                                 total_pages=footer_total_override,
                                                 dept_badges=dept_badges, start_of=dept_start_of)
        pdf_bytes = spliced_bytes

    _print_timing_summary(_time.perf_counter() - _render_t0)
    if _LAYOUT_WARNINGS:
        print(f"[pdf] {len(_LAYOUT_WARNINGS)} LAYOUT WARNING(S) in this render:")
        for msg in _LAYOUT_WARNINGS:
            print(f"[pdf]   - {msg}")
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
        # one of its own web fonts — _font_family_css below always lists
        # fc.family first, so a family with no catalog entry would just cost
        # real work building a ~300-400KB base64 @font-face block (see
        # FONT_CATALOG / _local_font_face_css above) for nothing. In
        # practice fc.family is always "IBM Plex Sans" (layout_config.json's
        # default) or a real request.font_config catalog pick.
        _catalog_entry = FONT_CATALOG.get(fc.family)
        _font_imports   = _catalog_entry["import"] if _catalog_entry else ""
        # Cover page (.page1-container in main.html) always renders in Roboto
        # regardless of the report's chosen body font, so its @font-face has
        # to be embedded unconditionally rather than only when fc.family
        # itself is "Roboto".
        if fc.family != "Roboto":
            _font_imports += "\n" + _local_font_face_css("Roboto")
        # Several page templates (at-a-glance, key highlights, best-ever /
        # best-calendar-month, special steel, the .pg-7 override, the
        # non-major techno_params pages, and the .pg-27 major-TEP override)
        # hardcode 'IBM Plex Sans Condensed'/'IBM Plex Sans' directly in
        # their own inline styles, independent of fc.family entirely — so
        # the condensed cut's @font-face has to be embedded unconditionally
        # too, the same way Roboto is above for the cover page. (The
        # regular cut doesn't need this: it's already covered by
        # FONT_CATALOG above whenever fc.family is "IBM Plex Sans", which
        # is every render today.)
        if fc.family != "IBM Plex Sans Condensed":
            _font_imports += "\n" + _local_font_face_css("IBM Plex Sans Condensed")
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
                # _stamp_main_overlays below, which recomputes "side" itself
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
        # Always _PDF_EXECUTOR (not the default pool): the persistent browser
        # in _PW_STATE must always be driven from the same thread.
        loop = asyncio.get_event_loop()
        report_month_display = f"{vars['m_name']} {vars['y_str']}"

        pdf_bytes = await loop.run_in_executor(
            _PDF_EXECUTOR, functools.partial(
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
