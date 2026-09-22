import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import PDFRequest, PageData
from page7_13 import generate_trend_page_rows, generate_combined_trend_items, TREND_PAGES
import pdf as pdf_mod
from pypdf import PdfReader
import io

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

    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_texts = [(p.extract_text() or "") for p in reader.pages]

    # Rebuild the SAME "all_items" grouping pdf.py uses (trend_section)
    all_items = []
    for p in pages:
        if p["type"] == "trend_combined":
            all_items.extend(p["items"])
        else:
            all_items.append(p)

    violations = []
    for ii, it in enumerate(all_items):
        rows = it.get("rows", [])
        n = len(rows)
        page_for_row = []
        for k in range(n):
            marker = f"@@TROW_{ii}_{k}@@"
            found = next((pno for pno, t in enumerate(page_texts) if marker in t), None)
            page_for_row.append(found)
        i = 0
        while i < n:
            plant = rows[i]["plant"]
            j = i
            while j < n and rows[j]["plant"] == plant:
                j += 1
            pages_seen = page_for_row[i:j]
            if all(p is not None for p in pages_seen):
                distinct = []
                for p in pages_seen:
                    if not distinct or distinct[-1] != p:
                        distinct.append(p)
                if len(distinct) > 1:
                    # compute segment sizes
                    segs = [1]
                    for a, b in zip(pages_seen, pages_seen[1:]):
                        if a == b:
                            segs[-1] += 1
                        else:
                            segs.append(1)
                    item_name = it.get("item_display", "?")
                    violations.append((item_name, plant, segs))
            i = j

    print(f"total physical pages: {len(reader.pages)}")
    if not violations:
        print("NO multi-page plant groups found -- every group fits on one page.")
    else:
        print(f"{len(violations)} group(s) still split across pages:")
        for item_name, plant, segs in violations:
            flag = "  <-- ORPHAN (<3 rows in a segment)" if min(segs) < 3 else ""
            print(f"  {item_name} / {plant}: segments {segs}{flag}")

asyncio.run(main())
