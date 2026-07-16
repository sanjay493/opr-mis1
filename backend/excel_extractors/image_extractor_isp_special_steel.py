"""ISP Special Steel — PNG/JPEG image extractor (OCR via Tesseract).

ISP's monthly Special Steel report arrives as a screenshot of a PPC ISP email
(not Excel/PDF like the other plants' reports), so this extractor OCRs the
image instead of parsing cells. The email always contains one plain
3-column table:

    PRODUCTS | ORDER | DESPATCH

followed by however many of the six known mills are reported that month — a
mill with no activity is sometimes omitted entirely rather than shown as a
zero row. Requires the Tesseract OCR engine to be installed on the host
(pip's `pytesseract` is only a wrapper around the `tesseract` binary).

Header line "... FOR THE MO(N)TH OF <Month>,<Year>" gives the report month
(the source recurringly misspells MONTH as MOTH — the regex only anchors on
"OF <Month>,<Year>" so that typo doesn't matter).
"""
import os
import re
import shutil
import logging
from typing import Optional

logger = logging.getLogger("excel_extractor")

MONTH_NUMS = {
    "JANUARY": "01", "FEBRUARY": "02", "MARCH": "03", "APRIL": "04",
    "MAY": "05", "JUNE": "06", "JULY": "07", "AUGUST": "08",
    "SEPTEMBER": "09", "OCTOBER": "10", "NOVEMBER": "11", "DECEMBER": "12",
}

# quality_grade/section stay blank (well, "TOTAL") for ISP — _gen_isp in
# page_special_steel.py groups only by (plant, product), matching the
# sentinel the manual-entry page already uses for this plant.
_CANONICAL_MILLS = ["WR COIL", "TMT COIL", "TMT BAR", "STRUCTURALS", "150 BLT", "200 BLM"]
_MILL_BY_KEY = {re.sub(r"[^A-Z0-9]", "", m): m for m in _CANONICAL_MILLS}

_HEADER_RE = re.compile(r"\bOF\s+([A-Za-z]+)\s*,?\s*(\d{4})", re.IGNORECASE)
_ROW_RE = re.compile(
    r"^([A-Za-z0-9 &/\-\|]+?)\s+[\(\[]?(-?[\d,]+(?:\.\d+)?)[\)\]]?\s+[\(\[]?(-?[\d,]+(?:\.\d+)?)[\)\]]?\s*$"
)


def _get_tesseract():
    """Import pytesseract, pointing it at the Windows default install path
    when the `tesseract` binary isn't already on PATH."""
    import pytesseract
    if shutil.which("tesseract") is None:
        default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default):
            pytesseract.pytesseract.tesseract_cmd = default
    return pytesseract


def _parse_month(text: str) -> Optional[str]:
    m = _HEADER_RE.search(text)
    if not m:
        return None
    mon = MONTH_NUMS.get(m.group(1).strip().upper())
    if not mon:
        return None
    return f"{m.group(2)}-{mon}"


def _clean_num(s: str) -> Optional[float]:
    s = s.replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _ocr_text(image_path: str) -> str:
    pytesseract = _get_tesseract()
    from PIL import Image
    img = Image.open(image_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return pytesseract.image_to_string(img)


def _parse_rows(text: str) -> list:
    """Scan every line for '<label> <order> <despatch>'; only lines whose
    label matches a known ISP mill (after stripping punctuation/spaces) are
    kept — this naturally skips header/noise lines (title, Gmail banners,
    'Regards', signature) without needing to locate the table boundaries."""
    rows = []
    sort = 0
    seen = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _ROW_RE.match(line)
        if not m:
            continue
        label, order_s, despatch_s = m.groups()
        key = re.sub(r"[^A-Z0-9]", "", label.upper())
        mill = _MILL_BY_KEY.get(key)
        if not mill or mill in seen:
            continue
        seen.add(mill)
        sort += 1
        rows.append({
            "product":         mill,
            "quality_grade":   "TOTAL",
            "section":         "",
            "sort_order":      sort,
            "order_qty":       _clean_num(order_s),
            "actual_despatch": _clean_num(despatch_s),
            "unit":            "T",
            "cell":            "OCR",
            "status":          "ok",
        })
    return rows


def extract_preview(image_path: str, report_month: str) -> dict:
    """Parse an ISP Special Steel report screenshot (PNG/JPEG) via OCR.
    Returns the standard preview dict with special_steel_rows — same shape
    as the RSP/DSP/BSL Special Steel extractors, so it plugs into the
    existing /api/extract-preview → /api/confirm-extraction flow."""
    text = _ocr_text(image_path)
    db_month = _parse_month(text) or report_month
    rows = _parse_rows(text)

    return {
        "plant":              "ISP",
        "month":              db_month,
        "source_type":        "Special Steel Report (Image/OCR)",
        "sheets":             "",
        "workbook_sheets":    [],
        "production_rows":    [],
        "techno_rows":        [],
        "techno_param_rows":  [],
        "special_steel_rows": rows,
        "special_steel_note": (
            f"OCR read {len(rows)} of {len(_CANONICAL_MILLS)} known mills. "
            "Verify Order/Despatch figures against the image before inserting."
        ),
    }


def extract_and_save_image(image_path: str, report_month: str, source_file_name: str = "") -> bool:
    """Parse + save directly (no confirm step) — mirrors extract_and_save_excel
    in the other plant extractors, for callers that don't need a preview."""
    import db as _db
    result = extract_preview(image_path, report_month)
    db_month = result["month"]
    rows = [r for r in result["special_steel_rows"]
            if r["status"] == "ok" and (r.get("order_qty") is not None or r.get("actual_despatch") is not None)]
    if not rows:
        return False
    _db.clear_special_steel_orders(db_month, "ISP")
    for r in rows:
        _db.save_special_steel_entry(
            db_month, "ISP",
            r["product"], r["quality_grade"],
            r["sort_order"],
            r.get("order_qty"), r.get("actual_despatch"),
            section="",
        )
    _db.log_extraction(
        plant="ISP", report_month=db_month,
        file_name=source_file_name, sheet_name="",
        source_type="Special Steel Report (Image/OCR)",
        items_extracted=len(rows))
    logger.info(f"ISP Special Steel (image OCR): {len(rows)} rows saved for {db_month}.")
    return True
