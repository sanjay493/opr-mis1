"""Commentary & Market PDF extractor (excel_extractors/
pdf_extractor_market_commentary) against the Sep'26 CMO/BigMint deck
(Report_format/Market/dc_2026-09.pdf): Steel Sales "Key Performance
Parameters" bullets (month + April-to-month) and the "Movement of Key
Prices-International" chart's 7 USD/T series.

Pins down:
  - bullets: one per slide line, the slide number dropped, and closely
    spaced lines (the Apr-Sep "Products with YoY Growth" list) joined into
    one bullet with line breaks;
  - prices: value labels assigned to their series by colour (matched to the
    legend, not hard-coded), the Finished Steel chart's months inferred from
    the Raw Materials axis (its own axis labels are drawn, not text).

Skipped if the sample PDF is absent.
"""

import pytest

from conftest import find_sample

SAMPLE = "Market/dc_2026-09.pdf"

_cache = {}


def _extract():
    if "r" not in _cache:
        path = find_sample(SAMPLE)
        if path is None:
            pytest.skip(f"sample not present: {SAMPLE}")
        from excel_extractors import pdf_extractor_market_commentary as ex
        _cache["r"] = ex.extract_market_commentary_pdf(str(path))
    return _cache["r"]


def test_report_month_and_no_warnings():
    r = _extract()
    assert r["report_month"] == "2026-09"
    assert r["warnings"] == []
    # PDF page 4 (India's Macro Economic Indicators) has no text layer (an
    # image) — its newest month is OCR'd separately (see the macro tests).
    assert r["skipped_pages"] == [4]


def test_month_bullets():
    items = _extract()["commentary"]["month_items"]
    assert len(items) == 21
    assert items[0] == "Cash Collection : 11,588 Cr (16% YoY growth; CPLY : 9,953 Cr)"
    assert items[9] == ("Highest Ever September Sales: Strls: 1.30 Lac T, GP GC Coils/Sheets : 22 KT "
                        "& PMP : 2.52 Lac T")
    assert items[10] == "NSC 1st round safety audit completed in all 20 HC/CHA warehouses"
    # The slide number "2" printed on the same baseline is not part of the bullet.
    assert items[-1] == "Vande Bharat wheels (forged) : 437 nos. supplied"


def test_ytd_bullets_join_continuation_lines():
    items = _extract()["commentary"]["ytd_items"]
    assert len(items) == 11
    assert items[0] == "Total Sales : 9.41 Mn T (6% YoY growth excl NSL; CPLY : 8.83 Mn T)"
    assert items[4] == ("Products with YoY Growth: CR Coils/Sheets (5.40 Lac T; 13%),\n"
                        "HSM Plates(3.5 Lac T; 17%),\nTMT(15.99 Lac T; 12%) &\nWR Coils (3.55 Lac T; 3%)")
    assert items[-1] == "Vande Bharat wheels (forged) : 2076 nos. supplied (CPLY: 268 nos.)"


RAW_MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
              "2026-06", "2026-07", "2026-08", "2026-09"]
FIN_MONTHS = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
              "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]

EXPECTED_PRICES = {
    "premium_hcc_aus_cnf_paradip":           dict(zip(RAW_MONTHS, [247, 263, 250, 255, 264, 265, 251, 254, 298])),
    "iron_ore_fines_aus_cfr_china_fe61":     dict(zip(RAW_MONTHS, [107, 99, 106, 107, 109, 101, 98, 96, 95])),
    "iron_ore_fines_india_fob_paradip_fe57": dict(zip(RAW_MONTHS, [67, 62, 61, 63, 62, 55, 55, 55, 56])),
    "hrc_fob_rizhao_china":     dict(zip(FIN_MONTHS, [464, 464, 468, 470, 465, 481, 505, 518, 516, 498, 495, 510])),
    "hrc_cfr_antwerp_europe":   dict(zip(FIN_MONTHS, [594, 576, 570, 561, 616, 620, 699, 698, 679, 645, 658, 665])),
    "hrc_cfr_west_coast_india": dict(zip(FIN_MONTHS, [489, 489, 493, 495, 494, 511, 535, 548, 546, 528, 525, 545])),
    "rebars_exw_donghua_china": dict(zip(FIN_MONTHS, [437, 440, 439, 442, 436, 444, 456, 477, 457, 448, 440, 442])),
}


@pytest.mark.parametrize("code", sorted(EXPECTED_PRICES))
def test_price_series(code):
    series = _extract()["market_prices"]["series"]
    assert series[code] == EXPECTED_PRICES[code]


def test_price_months():
    assert _extract()["market_prices"]["months"] == FIN_MONTHS


# India Macro Economic Indicators (PDF page 4) — a pasted image; only the
# newest month column is OCR'd (plus the previous one, as an alignment
# check). Values exactly as printed in the image.
MACRO_AUG26 = {
    "crude_steel_prod": 14.8, "pig_iron_prod": 0.78, "steel_exports": 1.09, "steel_imports": 0.52,
    "iron_ore_imports": 2.22, "coal_prod": 66.9, "coal_imports": 18.9, "auto_prod": 3.16,
    "auto_sales": 2.40, "power_consumption": 5.45, "merchandise_exports": 43.8,
    "ev_registrations": 2.98, "gst_collections": 1.99, "manufacturing_pmi": 52.8,
}
MACRO_JUL26 = {
    "crude_steel_prod": 14.3, "pig_iron_prod": 0.78, "steel_exports": 1.06, "steel_imports": 0.57,
    "iron_ore_imports": 0.59, "coal_prod": 69.8, "coal_imports": 20.0, "auto_prod": 3.4,
    "auto_sales": 2.47, "power_consumption": 5.5, "merchandise_exports": 44.2,
    "ev_registrations": 3.20, "gst_collections": 2.11, "manufacturing_pmi": 53.5,
}


def _macro():
    m = _extract()["macro"]
    if m.get("ocr_unavailable"):
        pytest.skip("Tesseract OCR not installed")
    return m


def test_macro_latest_month_ocr():
    m = _macro()
    assert m["month"] == "2026-08"
    assert m["values"] == MACRO_AUG26


def test_macro_previous_month_for_alignment_check():
    m = _macro()
    assert m["prev_month"] == "2026-07"
    assert m["prev_values"] == MACRO_JUL26
