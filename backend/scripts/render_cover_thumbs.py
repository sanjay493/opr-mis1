"""Writes frontend/public/cover/designs/<id>.png, the design tiles in the
/report Cover card: each photo design rendered with sample figures and the
bundled photo, plus Classic from its artwork. Re-run after editing any
page_templates/cover_<id>.html.

    venv\Scripts\python.exe -m scripts.render_cover_thumbs   (from backend/)
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

import cover_designs  # noqa: E402
import cover_render  # noqa: E402
import page_cover  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "public", "cover", "designs")
WIDTH = 300
HEIGHT = round(WIDTH * 297 / 210)


def _save(im: Image.Image, design: str) -> None:
    im.convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS).save(os.path.join(OUT_DIR, f"{design}.png"), optimize=True)
    print(f"wrote {design}.png")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    _save(Image.open(page_cover._BG_PATH), "classic")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 794, "height": 1123}, device_scale_factor=1)
        for design in cover_designs.PHOTO_DESIGN_IDS:
            page.set_content(cover_render.render_cover_html(cover_render.sample_page(design)), wait_until="load")
            _save(Image.open(io.BytesIO(page.screenshot(clip={"x": 0, "y": 0, "width": 794, "height": 1121}))), design)
        browser.close()


if __name__ == "__main__":
    main()
