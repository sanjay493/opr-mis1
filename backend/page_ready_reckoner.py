"""
"Ready Reckoner" — Annexure-1 (5 Integrated Steel Plants: BSP/DSP/RSP/BSL/
ISP) and Annexure-2 (3 Special Steel Plants: ASP/SSP/VISL), right after
"Details of Rakes Detention Plant Wise", at the very end of the report.
Source: Report_format/"Ready Reckoner (Plant wise Details).pdf" and
"Ready Reckoner Special Steel Plant.docx".

TWO pages per plant in the common case (per direct instruction, 2026-09-21
— was three: the "Major Facilities"/Unit-wise Capacity table and the
"Mill-wise Product Profile"/Product Mix table are small enough to
consolidate onto one page together, while the process-flow diagram keeps
its own dedicated page since it needs the full page to stay legible): 1)
the process-flow diagram, 2) the combined Unit-wise Capacity + Product Mix
tables ("details"). PDF generation only (never the live preview, which
always shows the merged "details" page — see ReadyReckonerTemplate.js's
own comment) falls back to 3 pages for a plant whose combined table content
doesn't actually fit one physical page at its configured 12pt font: the
"details" page id gets re-rendered as "capacity" alone, and the reserved
overflow id from PRODUCT_MIX_OVERFLOW_PAGES (never used by default) carries
"product_mix" alone right after it — per direct instruction, 2026-09-22:
merge only when there's room, never by shrinking the font. Decided by a
real isolated print-and-measure per plant, not guessed from row counts —
see pdf.py's _ready_reckoner_details_fits. Each group (ISP/SSP) also gets
its own blank separator/title page right before its first plant — see
ISP_SEPARATOR_PAGE_ID/SSP_SEPARATOR_PAGE_ID and
generate_ready_reckoner_separator below. Unlike every other page in this
report, the plant content is static reference material, not month-scoped —
the same regardless of which report month is open — so it's read/written
straight from ready_reckoner_pages (see db.py's own comment), never through
the generic per-month page_configs flow.

Editing happens in the dedicated /data-entry/ready-reckoner form
(editor/admin only), which POSTs straight to this table via /api/ready-
reckoner/{plant_code} — see main.py. capacity_rows/product_mix_headers/
product_mix_rows/product_mix_caption are plain data (no HTML/markup/style —
see db.py's own comment above _READY_RECKONER_COLS, 2026-09-21); the PDF
template (ready_reckoner_plant.html) and the live preview (ReadyReckoner
Template.js) both build the actual <table> markup and apply coloring/bold-
total styling at render time instead of it being stored.

The process-flow diagram is a file on disk (backend/static/ready_reckoner/)
so the browser preview can serve it directly over plain HTTP; PDF
generation base64-encodes that same file at render time instead (reusing
page_cover.py's _file_data_uri — Playwright's PDF renderer has no live
network access at render time, so a /static/... URL that works fine in the
browser preview won't resolve inside the exported PDF).
"""
import os

from PIL import Image

from page_cover import _file_data_uri
import db

ISP_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
SSP_PLANTS = ["ASP", "SSP", "VISL"]

_SUBTYPES = ["process_flow", "details"]
_SUBTYPE_LABELS = {
    "process_flow": "Process Flow",
    "details": "Unit-wise Capacity & Product Mix",
    # Only ever used for the PDF-only overflow fallback (see module
    # docstring) — "details" splits into these two when it doesn't fit.
    "capacity": "Unit-wise Capacity",
    "product_mix": "Product Mix",
}


def _paginate(plants: list, first_id: int) -> dict:
    """page_id -> (plant_code, subtype), 2 consecutive ids per plant
    (process_flow, details in that order — the actual print order, since
    main.py's pages_config/​_pages_list append loops just walk this dict's
    keys in insertion order), starting at first_id."""
    out = {}
    pg = first_id
    for plant in plants:
        for subtype in _SUBTYPES:
            out[pg] = (plant, subtype)
            pg += 1
    return out


# Sentinel page id -> (plant code, subtype). Mirrors CR_PAGES's shape
# (page_capital_repair.py) — 2 pages per plant, inserted right after the
# Rake Detention pages, each group preceded by its own blank separator page
# (ISP_SEPARATOR_PAGE_ID/SSP_SEPARATOR_PAGE_ID). Ids 1041-1058 (18 total: a
# separator + 10 ISP + a separator + 6 SSP) — chosen to sit clear of Rake
# Detention's own sentinels (1026-1029, 1038-1040). Was 1041-1064 (3 pages/
# plant, no separators) until 2026-09-21 — see module docstring.
ISP_SEPARATOR_PAGE_ID = 1041
ISP_PAGES = _paginate(ISP_PLANTS, 1042)   # 1042-1051
SSP_SEPARATOR_PAGE_ID = 1052
SSP_PAGES = _paginate(SSP_PLANTS, 1053)   # 1053-1058

# One reserved id per plant (8 total, 1059-1066 — right after SSP_PAGES,
# still clear of every other sentinel range) for the PDF-only "product_mix"
# overflow fallback described in the module docstring. Never included in
# pages_config by default (see main.py) — pdf.py inserts one of these only
# for a plant whose combined "details" content actually measures as not
# fitting one physical page. A flat plant -> id map, not a paginated dict
# like ISP_PAGES/SSP_PAGES, since there's exactly one reserved id per plant
# regardless of group.
PRODUCT_MIX_OVERFLOW_PAGE_ID = {
    plant: 1059 + i for i, plant in enumerate(ISP_PLANTS + SSP_PLANTS)
}

_PLANT_NAMES = {
    "BSP": "Bhilai Steel Plant", "DSP": "Durgapur Steel Plant",
    "RSP": "Rourkela Steel Plant", "BSL": "Bokaro Steel Plant", "ISP": "IISCO Steel Plant",
    "ASP": "Alloy Steels Plant", "SSP": "Salem Steel Plant", "VISL": "Visvesvaraya Iron and Steel Plant",
}

# These 5 plants' process-flow pages always print in landscape (BSL/DSP/
# ISP/RSP per direct instruction 2026-09-20; BSP added 2026-09-22, switched
# from portrait to landscape once its diagram was replaced with a wide one),
# regardless of the uploaded diagram's own aspect ratio — unlike every other
# plant, which falls back to the width>height auto-detection in
# generate_ready_reckoner_page below. Pinned explicitly so the layout
# doesn't flip back to portrait if an editor later replaces one of these
# plants' diagrams with a taller image.
_FORCE_LANDSCAPE_PLANTS = {"BSL", "BSP", "DSP", "ISP", "RSP"}

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static", "ready_reckoner")
os.makedirs(_STATIC_DIR, exist_ok=True)

_MIME_BY_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif"}


def image_path_for(plant_code: str, filename: str) -> str:
    """Where an uploaded process-flow diagram for `plant_code` is written
    on disk, keeping the uploaded file's own extension (mime is derived
    from it at render time — see generate_ready_reckoner_page)."""
    ext = os.path.splitext(filename)[1].lower() or ".png"
    return os.path.join(_STATIC_DIR, f"{plant_code}{ext}")


_SEPARATOR_LABELS = {
    "ISP": ("Annexure-1", "5 ISPs Ready Reckoner"),
    "SSP": ("Annexure-2", "3 SSPs Ready Reckoner"),
}


def generate_ready_reckoner_separator(group: str) -> dict:
    """group: "ISP" or "SSP" — see ISP_SEPARATOR_PAGE_ID/SSP_SEPARATOR_PAGE_ID.
    A blank page (no header content beyond a centered title) printed right
    before that group's first plant page, per direct instruction,
    2026-09-21: "Annexure-1"/"Annexure-2" in black, "5 ISPs Ready
    Reckoner"/"3 SSPs Ready Reckoner" in rust brown on the next line, both
    centered on an otherwise blank page — see ready_reckoner_separator.html."""
    annexure_label, group_label = _SEPARATOR_LABELS[group]
    return {
        "type": "ready_reckoner_separator",
        "title": f"{annexure_label} : {group_label}",
        "annexure_label": annexure_label,
        "group_label": group_label,
    }


def generate_ready_reckoner_page(plant_code: str, subtype: str) -> dict:
    """subtype: one of "process_flow" / "details" (see ISP_PAGES/SSP_PAGES)
    or "capacity" / "product_mix" (the PDF-only overflow fallback — see
    module docstring and PRODUCT_MIX_OVERFLOW_PAGE_ID). Always reads the
    full row (cheap — one small row) but only the requested subtype's own
    content actually gets rendered (see ready_reckoner_plant.html); the
    other fields are still included so a template branch never has to
    special-case a missing key."""
    row = db.get_ready_reckoner_page(plant_code) or {}
    image_uri = ""
    image_landscape = False
    image_path = row.get("process_flow_image_path")
    if image_path and os.path.exists(image_path):
        mime = _MIME_BY_EXT.get(os.path.splitext(image_path)[1].lower(), "image/png")
        image_uri = _file_data_uri(image_path, mime)
        # Pick the PDF page's own physical orientation to match the
        # diagram's shape, rather than always forcing a wide flowchart
        # into a portrait page (see pdf.py's _is_landscape_page, which
        # this "pdf_landscape" flag feeds — the same splice-render
        # mechanism as bf_large_annexure/epi/etc., just driven by image
        # shape instead of a fixed page type). Overridden unconditionally
        # for _FORCE_LANDSCAPE_PLANTS below, regardless of what this
        # measures.
        try:
            with Image.open(image_path) as img:
                width, height = img.size
            image_landscape = width > height
        except Exception:
            image_landscape = False

    plant_name = row.get("plant_name") or _PLANT_NAMES.get(plant_code, plant_code)
    subtype_label = _SUBTYPE_LABELS[subtype]
    return {
        "type": "ready_reckoner",
        "title": f"Ready Reckoner – {plant_name} – {subtype_label}",
        "plant_code": plant_code,
        "plant_name": plant_name,
        "plant_group": row.get("plant_group") or ("SSP" if plant_code in SSP_PLANTS else "ISP"),
        "subtype": subtype,
        "subtype_label": subtype_label,
        "image_data_uri": image_uri,
        "pdf_landscape": subtype == "process_flow" and (plant_code in _FORCE_LANDSCAPE_PLANTS or image_landscape),
        "capacity_rows": row.get("capacity_rows") or [],
        "product_mix_headers": row.get("product_mix_headers") or [],
        "product_mix_rows": row.get("product_mix_rows") or [],
        "product_mix_caption": row.get("product_mix_caption") or "",
    }
