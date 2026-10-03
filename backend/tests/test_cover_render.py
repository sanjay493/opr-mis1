"""Photo cover designs: page data, dispatch, and a real one-page A4 render
per design (Playwright + pypdf), for normal, tall and wide photos and for a
month with no figures yet."""

import base64
import io

import pytest
from PIL import Image
from pypdf import PdfReader

import cover_designs
import cover_render
import cover_store
import page_cover

RENDERED_DESIGNS = list(cover_designs.PHOTO_DESIGN_IDS)


def _photo_uri(size):
    buf = io.BytesIO()
    Image.new("RGB", size, (180, 60, 20)).save(buf, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


def _pdf(browser, html):
    page = browser.new_page()
    page.set_content(html, wait_until="load")
    data = page.pdf(format="A4", print_background=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
    page.close()
    return PdfReader(io.BytesIO(data))


@pytest.mark.parametrize("design", RENDERED_DESIGNS)
@pytest.mark.parametrize("photo_size", [(1600, 1067), (900, 1600), (1600, 400)])
def test_design_renders_exactly_one_page(browser, design, photo_size):
    reader = _pdf(browser, cover_render.render_cover_html(
        cover_render.sample_page(design, photo_uri=_photo_uri(photo_size))))
    assert len(reader.pages) == 1
    # designs may wrap the title or set it in capitals
    text = " ".join(reader.pages[0].extract_text().split()).casefold()
    for needle in ("Sep-2026", "1.723", "Operations Monthly Informatics", "MIS Group"):
        assert needle.casefold() in text, needle


@pytest.mark.parametrize("design", RENDERED_DESIGNS)
def test_month_without_figures_still_one_page(browser, design):
    reader = _pdf(browser, cover_render.render_cover_html(cover_render.sample_page(design, blank=True)))
    assert len(reader.pages) == 1
    assert "—" in reader.pages[0].extract_text()


_CLIPPED_JS = """() => {
    const root = document.querySelector('body > div');
    const box = root.getBoundingClientRect();
    const out = [];
    for (const el of root.querySelectorAll('*')) {
        const r = el.getBoundingClientRect();
        if (r.width && r.height && (r.bottom > box.bottom + 0.5 || r.right > box.right + 0.5)) {
            out.push(el.className + ' ' + Math.round(r.bottom - box.bottom) + 'px');
        }
    }
    return out;
}"""


@pytest.mark.parametrize("design", RENDERED_DESIGNS)
@pytest.mark.parametrize("blank", [False, True])
def test_nothing_is_cut_off_at_the_page_edge(browser, design, blank):
    """The design box hides overflow (so it can never spill onto a second
    page) - this catches content that would silently be cut off instead."""
    page = browser.new_page(viewport={"width": 794, "height": 1123})
    page.set_content(cover_render.render_cover_html(cover_render.sample_page(design, blank=blank)), wait_until="load")
    clipped = page.evaluate(_CLIPPED_JS)
    page.close()
    assert clipped == []


def _stub_kpis(monkeypatch):
    monkeypatch.setattr(page_cover, "_kpi_row", lambda m, item: {"label": item.upper(), "kind": "steel", "mt": "1.000",
                                                                   "pct_ful": "99", "growth": 1, "growth_abs": 1, "growth_good": True})
    monkeypatch.setattr(page_cover, "_mines_kpi_row", lambda m, label, kind: {"label": label, "kind": "ore", "mt": "2.000",
                                                                               "pct_ful": "90", "growth": -1, "growth_abs": 1, "growth_good": False})


def test_month_without_setting_is_classic_unchanged(monkeypatch):
    _stub_kpis(monkeypatch)
    monkeypatch.setattr(cover_store, "get_setting", lambda m: None)
    page = page_cover.generate_cover("2026-09")
    assert set(page) == {"type", "bg_data_uri", "month_display", "month_short", "kpis"}


def test_settings_table_error_falls_back_to_classic(monkeypatch):
    _stub_kpis(monkeypatch)

    def boom(month):
        raise RuntimeError("Table 'mis_reports.report_cover_settings' doesn't exist")
    monkeypatch.setattr(cover_store, "get_setting", boom)
    assert "design" not in page_cover.generate_cover("2026-09")


def test_saved_photo_design_adds_photo_fields(monkeypatch):
    _stub_kpis(monkeypatch)
    monkeypatch.setattr(cover_store, "get_setting", lambda m: {"design": "split", "photo_mode": "random", "photo_id": 7})
    monkeypatch.setattr(cover_store, "resolve_photo", lambda pid, month="": (None, cover_store.BUNDLED_PHOTO))
    page = page_cover.generate_cover("2026-09")
    assert page["design"] == "split" and page["report_month"] == "2026-09"
    assert page["photo_data_uri"].startswith("data:image/jpeg;base64,")
    assert page["logo_data_uri"].startswith("data:image/png;base64,")
    assert page["photo_id"] is None


def test_preview_override_beats_saved_setting(monkeypatch):
    _stub_kpis(monkeypatch)
    monkeypatch.setattr(cover_store, "get_setting", lambda m: {"design": "split", "photo_mode": "random", "photo_id": 7})
    seen = {}

    def fake_resolve(pid, month=""):
        seen["pid"] = pid
        return None, cover_store.BUNDLED_PHOTO
    monkeypatch.setattr(cover_store, "resolve_photo", fake_resolve)
    page = page_cover.generate_cover("2026-09", design="split", photo_id=3)
    assert seen["pid"] == 3 and page["design"] == "split"
    assert "design" not in page_cover.generate_cover("2026-09", design="classic")


def test_photo_lookup_error_uses_bundled_photo(monkeypatch):
    """A DB error while resolving the photo must not fail the report."""
    _stub_kpis(monkeypatch)
    monkeypatch.setattr(cover_store, "get_setting", lambda m: {"design": "split", "photo_mode": "random", "photo_id": 7})

    def boom(pid, month=""):
        raise RuntimeError("Lost connection to MySQL server")
    monkeypatch.setattr(cover_store, "resolve_photo", boom)
    page = page_cover.generate_cover("2026-09")
    assert page["design"] == "split" and page["photo_id"] is None
    assert page["photo_data_uri"] == page_cover._file_data_uri(cover_store.BUNDLED_PHOTO, "image/jpeg")


def test_resolve_photo_gets_the_month(monkeypatch):
    _stub_kpis(monkeypatch)
    monkeypatch.setattr(cover_store, "get_setting", lambda m: {"design": "split", "photo_mode": "random", "photo_id": None})
    seen = {}

    def fake_resolve(pid, month=""):
        seen["month"] = month
        return None, cover_store.BUNDLED_PHOTO
    monkeypatch.setattr(cover_store, "resolve_photo", fake_resolve)
    page_cover.generate_cover("2026-09")
    assert seen["month"] == "2026-09"


def test_unknown_saved_design_renders_classic(monkeypatch):
    _stub_kpis(monkeypatch)
    monkeypatch.setattr(cover_store, "get_setting", lambda m: {"design": "retired", "photo_mode": "random", "photo_id": None})
    assert "design" not in page_cover.generate_cover("2026-09")


def test_cover_html_dispatch_includes_design_template():
    import pdf
    html = pdf._jinja_env.get_template("cover.html").render(page=cover_render.sample_page("split"), colors={})
    assert 'class="cover-split"' in html and "page1-container" not in html
