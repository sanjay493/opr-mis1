"""The report cover designs an editor can pick per month. 'classic' is the
original artwork cover (cover.html); every other id has its own
page_templates/cover_<id>.html with a photo area. Picker thumbnails are
frontend/public/cover/designs/<id>.png (scripts/render_cover_thumbs.py)."""

DESIGNS = [
    {"id": "classic", "label": "Classic"},
    {"id": "split", "label": "Split"},
    {"id": "band", "label": "Photo band"},
    {"id": "editorial", "label": "Editorial"},
    {"id": "industrial", "label": "Industrial"},
    {"id": "grid", "label": "Minimal grid"},
    {"id": "corporate", "label": "Corporate"},
    {"id": "mosaic", "label": "Mosaic"},
    {"id": "spotlight", "label": "Spotlight"},
    {"id": "blueprint", "label": "Blueprint"},
    {"id": "cinematic", "label": "Cinematic"},
    {"id": "nightfall", "label": "Nightfall"},
    {"id": "horizon", "label": "Horizon"},
    {"id": "triptych", "label": "Triptych"},
    {"id": "swiss", "label": "Swiss blue"},
    {"id": "diagonal", "label": "Diagonal"},
    {"id": "cornercut", "label": "Corner cut"},
    {"id": "diamond", "label": "Diamond"},
]
DESIGN_IDS = tuple(d["id"] for d in DESIGNS)
PHOTO_DESIGN_IDS = tuple(i for i in DESIGN_IDS if i != "classic")
