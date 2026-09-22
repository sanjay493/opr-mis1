import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import PDFRequest, PageData
import main as main_mod
import pdf as pdf_mod

MONTH = "2026-08"

def mkpage(pg):
    return {"page": pg, "title": "", "type": ""}

async def main():
    req = PDFRequest(month=MONTH, pages=[PageData(**mkpage(3))], full_export=True)
    enriched, dyn_layouts = main_mod._enrich_pdf_pages(req)
    idx = next((i for i, p in enumerate(enriched) if p.get("page") == 3.6), None)
    if idx is not None:
        enriched = enriched[:idx]
    print("batch page ids:", [p.get("page") for p in enriched])
    pdf_bytes, filename = await pdf_mod.generate_pdf_bytes(req, pages_override=enriched, page_layouts=dyn_layouts or None, font_config=None)
    out_path = os.path.join(os.path.dirname(__file__), "batch_fullctx.pdf")
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print("wrote", out_path, len(pdf_bytes), "bytes")

asyncio.run(main())
