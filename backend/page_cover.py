"""
Cover page (page 1) — dynamic per-report-month content composited onto the
static SAIL branding chrome (page_templates/cover.html, .page1-* CSS in
main.html). Design follows the two hand-mocked reference images in
Report_format/ ("cover page.png", "cover page 2.png") — the two samples
differ from each other in layout, so this reproduces their shared elements
(logo, title, Prepared By/Report Month cards, a 4-KPI "Performance at a
Glance" strip, a values footer). The corner photo and product-strip photos
are real SAIL plant/product stills (user-supplied, originally in
Report_format/RightCorner.jpg and Report_format/products/*), pre-cropped
and compressed into frontend/public/cover/ and embedded as base64 data
URIs — this app's PDF pipeline has no internet access at render time (see
project-offline-fonts memory: fonts are already self-hosted for the same
reason), so every image has to be a local file baked into the HTML rather
than fetched. The point of this page is to regenerate correctly for
whatever report_month is selected, not just the July 2026 the two mockups
happened to show.

KPI figures (Hot Metal / Crude Steel / Finished Steel / Saleable Steel,
Million-T with %-of-APP and %-growth-vs-CPLY) reuse report_utils.
compute_item_row — the exact same source "MIS at a Glance" (page 2.5)
already uses for these 4 items — but re-derives the raw MT figure directly
from db.get_sail_production_actual rather than reusing compute_item_row's
own pre-rounded whole-'000T string, since this page displays 3-decimal MT
(matching the reference mockups) rather than at-a-glance's whole-'000T.
"""
import base64
import os

import db
from report_utils import compute_item_row

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "sail_logo.png")
_COVER_ASSET_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "cover")
_CORNER_PHOTO_PATH = os.path.join(_COVER_ASSET_DIR, "right_corner.jpg")
_KPI_ITEMS = ["Hot Metal", "Crude Steel", "Finished Steel", "Saleable Steel"]
_DB_ITEM = {"Crude Steel": "Total Crude Steel"}

# label -> filename under frontend/public/cover/products/; images are
# pre-cropped/compressed stills of actual SAIL products (see the resize
# script used when these were added — originals came from user-supplied
# photos in Report_format/products/, not stock/hand-drawn art).
_PRODUCTS = [
    ("Plates", "plates.jpg"),
    ("HR Coils", "hr_coils.jpg"),
    ("TMT Bars", "tmt_bars.jpg"),
    ("Structurals", "structurals.jpg"),
    ("Wire Rods", "wire_rods.jpg"),
    ("Rails", "rails.jpg"),
]

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_logo_cache = None
_corner_photo_cache = None
_product_cache: dict = {}


def _file_data_uri(path: str, mime: str) -> str:
    """Embedded as base64 rather than an <img src="file://..."> path — a
    data URI is self-contained inside the HTML string Playwright renders,
    so it works regardless of what working directory/sandbox the PDF
    render happens in, with no filesystem-path resolution to get wrong."""
    try:
        with open(path, "rb") as f:
            return f"data:{mime};base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return ""


def _logo_data_uri() -> str:
    global _logo_cache
    if _logo_cache is None:
        _logo_cache = _file_data_uri(_LOGO_PATH, "image/png")
    return _logo_cache


def _corner_photo_data_uri() -> str:
    global _corner_photo_cache
    if _corner_photo_cache is None:
        _corner_photo_cache = _file_data_uri(_CORNER_PHOTO_PATH, "image/jpeg")
    return _corner_photo_cache


def _products() -> list:
    out = []
    for label, filename in _PRODUCTS:
        if filename not in _product_cache:
            _product_cache[filename] = _file_data_uri(
                os.path.join(_COVER_ASSET_DIR, "products", filename), "image/jpeg"
            )
        uri = _product_cache[filename]
        if uri:
            out.append({"label": label, "img": uri})
    return out


def _kpi_row(report_month: str, item: str) -> dict:
    db_item = _DB_ITEM.get(item, item)
    v = compute_item_row(report_month, item)
    raw_000t = db.get_sail_production_actual(report_month, db_item)
    mt = f"{raw_000t / 1000:.3f}" if raw_000t is not None else "—"
    pct_ful = v[3]
    growth = v[5]
    return {
        "label": item.upper(),
        "mt": mt,
        "pct_ful": pct_ful or "—",
        "growth": growth,
        "growth_good": None if growth in (None, "") else int(growth) >= 0,
    }


def generate_cover(report_month: str) -> dict:
    y, m = int(report_month[:4]), int(report_month[5:7])
    return {
        "type": "cover",
        "title": "OPERATIONS MONTHLY INFORMATICS",
        "month_display": f"{_MON_ABBR[m]}-{y}",
        "month_short": f"{_MON_ABBR[m]}'{y % 100:02d}",
        "logo_data_uri": _logo_data_uri(),
        "corner_image_data_uri": _corner_photo_data_uri(),
        "kpis": [_kpi_row(report_month, item) for item in _KPI_ITEMS],
        "products": _products(),
    }
