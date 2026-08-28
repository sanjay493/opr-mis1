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
  - the "SAIL Performance at a Glance" 6-hexagon honeycomb — Hot Metal /
    Crude Steel / Finished Steel / Saleable Steel (from
    report_utils.compute_item_row, the same source "MIS at a Glance" page
    2.5 uses — but re-deriving the raw MT figure directly from
    db.get_sail_production_actual rather than reusing compute_item_row's
    own pre-rounded whole-'000T string, since this page displays
    3-decimal MT), plus Iron Ore Production and Iron Ore Sales Despatch
    (SAIL totals for the report month, rolled up from the mine-level
    entry tables — same source as page 4.5). All Million-T with
    %-of-plan and %-growth-vs-CPLY.
  - a thin admin line in the bottom wave band
"""
import base64
import os

import db
from report_utils import compute_item_row

_COVER_ASSET_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "cover")
_BG_PATH = os.path.join(_COVER_ASSET_DIR, "cover_bg.jpg")
# Crude Steel's production_table item name differs from its display label;
# every other honeycomb item matches. Iron Ore hex labels ("IRON ORE
# PRODUCTION" / "IRON ORE SALES DESPATCH") must match the kpi_icons keys
# in cover.html / CoverTemplate.js.
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


def _norm_growth(growth) -> int | None:
    try:
        return int(round(float(growth)))
    except (TypeError, ValueError):
        return None


def _kpi_row(report_month: str, item: str) -> dict:
    db_item = _DB_ITEM.get(item, item)
    v = compute_item_row(report_month, item)
    raw_000t = db.get_sail_production_actual(report_month, db_item)
    mt = f"{raw_000t / 1000:.3f}" if raw_000t is not None else "—"
    g = _norm_growth(v[5])
    return {
        "label": item.upper(),
        "kind": "steel",
        "mt": mt,
        "pct_ful": v[3] or "—",
        "growth": g,
        "growth_abs": abs(g) if g is not None else None,
        "growth_good": None if g is None else g >= 0,
    }


def _sum_groups(node: dict, field: str):
    vals = [g.get(field) for g in (node or {}).values() if g.get(field) is not None]
    return sum(vals) if vals else None


def _mines_kpi_row(report_month: str, label: str, kind: str) -> dict:
    """Report-month SAIL-total Iron Ore Mines figure for the cover
    honeycomb, rolled up per group from the mine-level entry tables (same
    source as page 4.5). kind 'prod' = fresh Lump+Fines production;
    'sales_despatch' = despatch to the SALES (3rd-party) end-use. Shows
    %-of-plan and growth vs CPLY where those are available."""
    y = int(report_month[:4])
    cply_month = f"{y - 1}{report_month[4:]}"
    if kind == "prod":
        roll = db.get_iron_ore_group_rollup_monthly([report_month, cply_month])
        section = "iron_ore_prod"
    else:
        roll = db.get_iron_ore_sales_group_rollup_monthly([report_month, cply_month])
        section = "iron_ore_sales_despatch"

    cur = (roll.get(report_month) or {}).get(section) or {}
    prev = (roll.get(cply_month) or {}).get(section) or {}
    actual = _sum_groups(cur, "actual")
    plan = _sum_groups(cur, "plan")
    cply = _sum_groups(prev, "actual")

    g = round((actual - cply) / cply * 100) if actual is not None and cply else None
    return {
        "label": label,
        "kind": "ore",
        "mt": f"{actual / 1000:.3f}" if actual is not None else "—",
        "pct_ful": f"{actual / plan * 100:.0f}" if actual is not None and plan else "—",
        "growth": g,
        "growth_abs": abs(g) if g is not None else None,
        "growth_good": None if g is None else g >= 0,
    }


def generate_cover(report_month: str) -> dict:
    y, m = int(report_month[:4]), int(report_month[5:7])
    return {
        "type": "cover",
        "bg_data_uri": _bg_data_uri(),
        "month_display": f"{_MON_ABBR[m]}-{y}",
        "month_short": f"{_MON_ABBR[m]}'{y % 100:02d}",
        # Honeycomb order = 3 columns of 2: left (Hot Metal / Crude Steel),
        # middle (the two Iron Ore Mines figures), right (Finished / Saleable
        # Steel). See .page1-hex-{0..5} in main.html.
        "kpis": [
            _kpi_row(report_month, "Hot Metal"),
            _kpi_row(report_month, "Crude Steel"),
            _mines_kpi_row(report_month, "IRON ORE PRODUCTION", "prod"),
            _mines_kpi_row(report_month, "IRON ORE SALES DESPATCH", "sales_despatch"),
            _kpi_row(report_month, "Finished Steel"),
            _kpi_row(report_month, "Saleable Steel"),
        ],
    }
