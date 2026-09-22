import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import PDFRequest, PageData
from page7_13 import generate_trend_page_rows, generate_combined_trend_items, TREND_PAGES
import pdf as pdf_mod

MONTH = "2026-08"

def mkpage(pg):
    cfg = TREND_PAGES.get(pg, {})
    base = {"page": pg, "title": f"10 Years Month Wise Production : {cfg.get('display','')}",
            "type": "trend_yearly", "item_display": cfg.get("display",""), "unit": cfg.get("unit","")}
    if cfg.get("combined_items"):
        base["type"] = "trend_combined"
        base["items"] = generate_combined_trend_items(MONTH, pg)
        base["rows"] = []
    else:
        base["rows"] = generate_trend_page_rows(MONTH, pg)
    return base

async def main():
    pages = [mkpage(pg) for pg in range(7, 13)]  # 7..12
    req = PDFRequest(month=MONTH, pages=[PageData(**p) for p in pages], full_export=False)
    pdf_bytes, filename = await pdf_mod.generate_pdf_bytes(req, pages_override=pages, page_layouts=None, font_config=None)
    out_path = os.path.join(os.path.dirname(__file__), "trend_aug2026.pdf")
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print("wrote", out_path, len(pdf_bytes), "bytes")

asyncio.run(main())
