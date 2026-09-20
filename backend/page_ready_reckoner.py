"""
"Ready Reckoner" — Annexure-1 (5 Integrated Steel Plants: BSP/DSP/RSP/BSL/
ISP) and Annexure-2 (3 Special Steel Plants: ASP/SSP/VISL), right after
"Details of Rakes Detention Plant Wise", at the very end of the report.
Source: Report_format/"Ready Reckoner (Plant wise Details).pdf" and
"Ready Reckoner Special Steel Plant.docx".

THREE pages per plant (per direct instruction, 2026-09-20 — was one page
combining all three): 1) the process-flow diagram, 2) the "Major
Facilities"/Unit-wise Capacity table, 3) the "Mill-wise Product Profile"/
Product Mix table. Unlike every other page in this report, this content is
static reference material, not month-scoped — the same regardless of which
report month is open — so it's read/written straight from
ready_reckoner_pages (see db.py's own comment), never through the generic
per-month page_configs flow.

Editing happens inline in the /report live preview (ReadyReckonerTemplate.js
contentEditable regions, editor/admin only), which POSTs straight to this
table via /api/ready-reckoner/{plant_code} — see main.py. The two HTML
blocks are rendered with Jinja's |safe: they're only ever written by an
authenticated editor/admin (server-side role check in main.py, not just a
hidden client-side control), the same trust level already given to other
admin-entered free text elsewhere (e.g. rail_prod_despatch_note).

The process-flow diagram is a file on disk (backend/static/ready_reckoner/)
so the browser preview can serve it directly over plain HTTP; PDF
generation base64-encodes that same file at render time instead (reusing
page_cover.py's _file_data_uri — Playwright's PDF renderer has no live
network access at render time, so a /static/... URL that works fine in the
browser preview won't resolve inside the exported PDF).
"""
import os

from page_cover import _file_data_uri
import db

ISP_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
SSP_PLANTS = ["ASP", "SSP", "VISL"]

_SUBTYPES = ["process_flow", "capacity", "product_mix"]
_SUBTYPE_LABELS = {
    "process_flow": "Process Flow",
    "capacity": "Unit-wise Capacity",
    "product_mix": "Product Mix",
}


def _paginate(plants: list, first_id: int) -> dict:
    """page_id -> (plant_code, subtype), 3 consecutive ids per plant
    (process_flow, capacity, product_mix in that order — the actual
    print order, since main.py's pages_config/​_pages_list append loops
    just walk this dict's keys in insertion order), starting at first_id."""
    out = {}
    pg = first_id
    for plant in plants:
        for subtype in _SUBTYPES:
            out[pg] = (plant, subtype)
            pg += 1
    return out


# Sentinel page id -> (plant code, subtype). Mirrors CR_PAGES's shape
# (page_capital_repair.py) — 3 pages per plant, inserted right after the
# Rake Detention pages. Ids 1041-1064 (24 total: 15 ISP + 9 SSP) — chosen
# to sit clear of Rake Detention's own sentinels (1026-1029, 1038-1040).
ISP_PAGES = _paginate(ISP_PLANTS, 1041)   # 1041-1055
SSP_PAGES = _paginate(SSP_PLANTS, 1056)   # 1056-1064

_PLANT_NAMES = {
    "BSP": "Bhilai Steel Plant", "DSP": "Durgapur Steel Plant",
    "RSP": "Rourkela Steel Plant", "BSL": "Bokaro Steel Plant", "ISP": "IISCO Steel Plant",
    "ASP": "Alloy Steels Plant", "SSP": "Salem Steel Plant", "VISL": "Visvesvaraya Iron and Steel Plant",
}

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static", "ready_reckoner")
os.makedirs(_STATIC_DIR, exist_ok=True)

_MIME_BY_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif"}


def image_path_for(plant_code: str, filename: str) -> str:
    """Where an uploaded process-flow diagram for `plant_code` is written
    on disk, keeping the uploaded file's own extension (mime is derived
    from it at render time — see generate_ready_reckoner_page)."""
    ext = os.path.splitext(filename)[1].lower() or ".png"
    return os.path.join(_STATIC_DIR, f"{plant_code}{ext}")


def generate_ready_reckoner_page(plant_code: str, subtype: str) -> dict:
    """subtype: one of "process_flow" / "capacity" / "product_mix" — see
    ISP_PAGES/SSP_PAGES. Always reads the full row (cheap — one small
    row) but only the requested subtype's own content actually gets
    rendered (see ready_reckoner_plant.html); the other fields are still
    included so a template branch never has to special-case a missing
    key."""
    row = db.get_ready_reckoner_page(plant_code) or {}
    image_uri = ""
    image_path = row.get("process_flow_image_path")
    if image_path and os.path.exists(image_path):
        mime = _MIME_BY_EXT.get(os.path.splitext(image_path)[1].lower(), "image/png")
        image_uri = _file_data_uri(image_path, mime)

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
        "capacity_html": row.get("capacity_html") or "",
        "product_mix_html": row.get("product_mix_html") or "",
    }
