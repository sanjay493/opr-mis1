"""
Diagnostic script: print each section line-by-line with cell indices
Run: python diag_pdf.py
"""
import sys
import re
sys.path.insert(0, '.')

PDF_PATH = r"../Report_format/MONTHEND/BSL_BlastFurnace_31052025.pdf"

try:
    import pdfplumber
    pdf_text = ""
    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pdf_text += t + "\n"
    print(f"[pdfplumber] Read {len(pdf_text)} chars")
except Exception as e:
    print(f"pdfplumber failed: {e}")
    import PyPDF2
    pdf_text = ""
    with open(PDF_PATH, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pdf_text += t + "\n"
    print(f"[PyPDF2] Read {len(pdf_text)} chars")


def show_section(title, start_key, end_key=None):
    idx = pdf_text.find(start_key)
    if idx < 0:
        print(f"\n{'='*60}")
        print(f"SECTION: {title}  -- NOT FOUND (searched: {start_key!r})")
        return
    end = len(pdf_text)
    if end_key:
        e = pdf_text.find(end_key, idx)
        if e > 0:
            end = e
    section = pdf_text[idx:end]
    lines = section.split("\n")[:40]
    print(f"\n{'='*60}")
    print(f"SECTION: {title}  (starts at char {idx})")
    print(f"{'='*60}")
    for i, line in enumerate(lines):
        if "|" in line:
            cells = [c.strip() for c in line.split("|")]
            print(f"  L{i:02d} [{len(cells)} cells] RAW: {line[:120]}")
            for ci, cell in enumerate(cells):
                if cell:
                    print(f"        [{ci}] = {cell!r}")
        else:
            print(f"  L{i:02d} (no pipes): {line[:100]}")


show_section("PRODUCTION PERFORMANCE", "PRODUCTION PERFORMANCE", "COKE RATE")
show_section("QUALITY PARAMETERS", "COKE RATE", "Consumption")
show_section("CONSUMPTION", "Consumption", None)
