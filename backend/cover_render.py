"""
Standalone HTML for a photo cover design (cover_designs.PHOTO_DESIGN_IDS):
the /report preview iframe (api_cover /api/cover/html), the per-design
render tests and the picker thumbnails. The PDF renders the very same
page_templates/cover_<design>.html inside main.html (via cover.html), so
preview and export can't drift apart.
"""
import functools

import cover_store
import page_cover
import pdf

# Every photo design uses only these; main.html already embeds all three for
# every PDF render.
_FONTS = ("IBM Plex Sans", "IBM Plex Sans Condensed", "Roboto")


@functools.lru_cache(maxsize=1)
def _font_css() -> str:
    return "\n".join(pdf._local_font_face_css(f) for f in _FONTS)


def render_cover_html(page: dict) -> str:
    return pdf._jinja_env.get_template("cover_preview.html").render(page=page, font_css=_font_css())


def cover_document(month: str, design=None, photo_id=None):
    """Full A4 HTML for the month's cover, or None when it is Classic."""
    page = page_cover.generate_cover(month, design=design, photo_id=photo_id)
    return render_cover_html(page) if page.get("design") else None


def _kpi(label, kind, mt, pct, growth):
    return {"label": label, "kind": kind, "mt": mt, "pct_ful": pct,
            "growth": growth, "growth_abs": abs(growth) if growth is not None else None,
            "growth_good": None if growth is None else growth >= 0}


def sample_page(design: str, photo_uri=None, blank: bool = False) -> dict:
    """Fixed Sep-2026 figures (or all '—' when blank) for tests/thumbnails."""
    rows = [("HOT METAL", "steel", "1.723", "98", 4), ("CRUDE STEEL", "steel", "1.602", "97", 3),
            ("IRON ORE PRODUCTION", "ore", "3.101", "101", 6), ("IRON ORE SALES DESPATCH", "ore", "0.412", "88", -5),
            ("FINISHED STEEL", "steel", "1.398", "95", 2), ("SALEABLE STEEL", "steel", "1.512", "96", -1)]
    kpis = [_kpi(lbl, kind, "—" if blank else mt, "—" if blank else pct, None if blank else g)
            for lbl, kind, mt, pct, g in rows]
    return {
        "type": "cover", "design": design, "report_month": "2026-09", "photo_id": None,
        "month_display": "Sep-2026", "month_short": "Sep'26", "kpis": kpis,
        "photo_data_uri": photo_uri or page_cover._file_data_uri(cover_store.BUNDLED_PHOTO, "image/jpeg"),
        "logo_data_uri": page_cover._logo_data_uri(),
    }
