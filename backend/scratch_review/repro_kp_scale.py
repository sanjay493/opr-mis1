import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import PDFRequest, PageData
import pdf as pdf_mod

MONTH = "2026-08"

def mkpage(pg):
    return {"page": pg, "title": "", "type": ""}

async def run(label, page_ids):
    pages = [mkpage(pg) for pg in page_ids]
    req = PDFRequest(month=MONTH, pages=[PageData(**p) for p in pages], full_export=False)
    # Reuse main._enrich_pdf_pages just to populate real content for the
    # exact pages we listed (no auto-insertion happens since full_export=False).
    import main as main_mod
    enriched, dyn_layouts = main_mod._enrich_pdf_pages(req)
    print(label, "page ids:", [p.get("page") for p in enriched])
    pdf_bytes, filename = await pdf_mod.generate_pdf_bytes(req, pages_override=enriched, page_layouts=dyn_layouts or None, font_config=None)
    out_path = os.path.join(os.path.dirname(__file__), f"{label}.pdf")
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(label, "wrote", out_path, len(pdf_bytes), "bytes")

async def main():
    await run("batch_small", [3, 3.05, 3.2, 3.3, 3.5])

asyncio.run(main())
