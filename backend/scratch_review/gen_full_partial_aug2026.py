import asyncio, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import PDFRequest, PageData
import main as main_mod
import pdf as pdf_mod

MONTH = "2026-08"
HERE = os.path.dirname(os.path.abspath(__file__))

# Mirrors frontend/src/app/report/page.js ALL_PAGE_NUMBERS (sorted via
# _PAGE_SORT_POS overrides) -- the full "select all" page-id list, in the
# same physical print order the report page sends.
ALL_PAGE_NUMBERS = [
    1, 2, 2.1, 2.2, 2.3, 2.41, 2.42, 2.5, 3, 3.05, 3.2, 3.3, 3.5, 3.6, 3.61,
    3.62, 3.63, 4, 4.5, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18,
    19, 20, 21, 22, 23, 24, 1024, 18.5, 1025, 25, 26, 27, 28, 29, 29.5, 30,
    31, 32, 33, 34, 35, 35.4, 35.5, 35.6, 35.7, 36, 37, 38, 39, 40, 1026,
    1027, 1038, 1039, 1040, 1028, 1029, 1041, 1042, 1043, 1044, 1045, 1046,
    1047, 1048, 1049, 1050, 1051, 1052, 1053, 1054, 1055, 1056, 1057, 1058,
]

# The docstring's own example of a realistic partial export ("pages 1-9")
# -- front matter through "SAIL Performance - 1 Page Summary", Index (page
# 2) included, everything after page 3 excluded. This is the case
# main._enrich_pdf_pages / pdf._correct_dynamic_index_pagination call out
# by name as needing to NOT get the full-export sentinel auto-insertion,
# and as needing every _INDEX_SECTIONS row past "SAIL Performance - 1 Page
# Summary" to fall back to its nominal count (anchor never rendered).
PARTIAL_PAGE_NUMBERS = ALL_PAGE_NUMBERS[:9]


def fetch_page(pg):
    # Mirrors the frontend: it fetches each page's fully-typed content via
    # GET /api/data?page_number=... (main.get_data) BEFORE building the PDF
    # export payload, so PageData.type/rows etc. are already correct going
    # in. A blank {"page": pg, "type": ""} stub (as the smaller repro_*.py
    # scripts use for isolated page batches) breaks for page 2 (Index),
    # page 5/6 (performance_summary_table) and page 13 (concast) -- those
    # never get a "type" assigned inside _enrich_pdf_pages itself, only in
    # get_data's own base pages_config -- and fall through main.html's
    # generic-table {% else %} branch with real, non-'values'-keyed rows,
    # crashing template.render (confirmed 2026-09-22: TypeError:
    # 'builtin_function_or_method' object is not iterable, from Jinja's
    # subscript-miss fallback to the dict's own bound .values method).
    result = main_mod.get_data(MONTH, page_number=pg)
    return result[0] if result else {"page": pg, "title": "", "type": ""}


async def run(label: str, page_ids: list, full_export: bool):
    t0 = time.perf_counter()
    pages = [fetch_page(pg) for pg in page_ids]
    print(f"[{label}] fetched {len(pages)} base pages ({time.perf_counter() - t0:.1f}s so far)")
    req = PDFRequest(month=MONTH, pages=[PageData(**p) for p in pages], full_export=full_export)
    enriched, dyn_layouts = main_mod._enrich_pdf_pages(req)
    print(f"[{label}] enriched to {len(enriched)} page dicts "
          f"({time.perf_counter() - t0:.1f}s so far)")
    pdf_bytes, filename = await pdf_mod.generate_pdf_bytes(
        req, pages_override=enriched, page_layouts=dyn_layouts or None, font_config=None,
    )
    out_path = os.path.join(HERE, f"{label}.pdf")
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"[{label}] wrote {out_path} ({len(pdf_bytes)} bytes) "
          f"total {time.perf_counter() - t0:.1f}s")
    return out_path


async def main():
    await run("full_aug2026", ALL_PAGE_NUMBERS, full_export=True)
    await run("partial_aug2026", PARTIAL_PAGE_NUMBERS, full_export=False)


asyncio.run(main())
