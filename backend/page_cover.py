"""
Cover page (page 1) — dynamic per-report-month content overlaid on the
static SAIL branding artwork (page_templates/cover.html, .page1-* CSS in
main.html). The background is the user-supplied design in
Report_format/coverPage.png (logo, title, "Prepared By" — all baked into
the image, A4-proportioned so it fills the page edge-to-edge with no
crop/stretch), compressed into frontend/public/cover/cover_bg.jpg and
embedded as a base64 data URI — this app's PDF pipeline has no internet
access at render time (see project-offline-fonts memory: fonts are
already self-hosted for the same reason), so the image has to be a local
file baked into the HTML rather than fetched.

Everything month-dependent is overlaid as text on top of that fixed
artwork, positioned into the image's own blank space (the faint world-map
watermark in its lower-left, where there's nothing else printed):
  - Report Month (the image has no month baked in)
  - the "SAIL Performance at a Glance" 2x2 KPI grid — Hot Metal / Crude
    Steel / Finished Steel / Saleable Steel, Million-T with %-of-APP and
    %-growth-vs-CPLY, reusing report_utils.compute_item_row (the same
    source "MIS at a Glance" page 2.5 already uses for these 4 items) —
    but re-deriving the raw MT figure directly from
    db.get_sail_production_actual rather than reusing compute_item_row's
    own pre-rounded whole-'000T string, since this page displays
    3-decimal MT.
  - a thin admin line in the bottom wave band
"""
import base64
import os

import db
from report_utils import compute_item_row

_COVER_ASSET_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "cover")
_BG_PATH = os.path.join(_COVER_ASSET_DIR, "cover_bg.jpg")
_KPI_ITEMS = ["Hot Metal", "Crude Steel", "Finished Steel", "Saleable Steel"]
_DB_ITEM = {"Crude Steel": "Total Crude Steel"}

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_bg_cache = None


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


def _bg_data_uri() -> str:
    global _bg_cache
    if _bg_cache is None:
        _bg_cache = _file_data_uri(_BG_PATH, "image/jpeg")
    return _bg_cache


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
        "bg_data_uri": _bg_data_uri(),
        "month_display": f"{_MON_ABBR[m]}-{y}",
        "month_short": f"{_MON_ABBR[m]}'{y % 100:02d}",
        "kpis": [_kpi_row(report_month, item) for item in _KPI_ITEMS],
    }
