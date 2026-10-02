"""Rake detention PDF extractor (page_rake_detention_pdf_extractor) against
the monthly "Average Plant Detention Report" samples in
Report_format/Miscellaneous (Feb, Mar, Jun, Jul, Aug, Sep 2026).

Pins down the fixes for:
  - Jun/Sep'26 page 1 rendering its header letter-spaced ("W A G O N"),
    which skipped BSP/DSP/RSP entirely;
  - the report title's "COMMODITY" being taken as the column header,
    which dropped every wagon-type label;
  - rows being paired with the Wagon Types registry by position, which
    filed older reports' rows (9 BSP inward rows vs 15 in the registry)
    and ISP's differently-ordered rows under the wrong wagon type.

Needs the sample PDFs (skipped if absent) and the live DB's Wagon Types
registry (rake_detention_master) — matching is against it.
"""

import pytest

from conftest import find_sample

FOLDER = "Miscellaneous"
SAMPLES = {
    "2026-02": "Average Plant Detention Report for the priod _(01-02-2026 to 28-02-2026).pdf",
    "2026-03": "Average Plant Detention Report for the period_(01-03-2026 to 31-03-2026).pdf",
    "2026-06": "Average Plant Detention Report for the period_(01-06-2026 to 30-06-2026).pdf",
    "2026-07": "Average Plant Detention Report for the period _(01-07-2026 to 31-07-2026).pdf",
    "2026-08": "Average Plant Detention Report for the period_(01-08-2026 to 31-08-2026.pdf",
    "2026-09": "Average Plant Detention report for the period _(01-09-2026 to 30-09-2026).pdf",
}

_cache = {}


def _extract(month):
    if month not in _cache:
        path = find_sample(f"{FOLDER}/{SAMPLES[month]}")
        if path is None:
            pytest.skip(f"sample not present: {SAMPLES[month]}")
        import page_rake_detention_pdf_extractor as ex
        _cache[month] = ex.extract_rake_detention_pdf(str(path), month)
    return _cache[month]


def _row(result, plant, section, commodity, wagon):
    rows = [r for r in result["plants"][plant][section]["rows"]
            if r["status"] == "ok" and r["matched_row_label"] == wagon
            and (commodity is None or (r["commodity"] or "").replace(" ", "") == commodity.replace(" ", ""))]
    assert len(rows) == 1, f"{plant}/{section} {commodity} {wagon}: {len(rows)} matches"
    return rows[0]


@pytest.mark.parametrize("month", sorted(SAMPLES))
def test_every_plant_and_summary_extracted(month):
    r = _extract(month)
    assert set(r["plants"]) == {"BSP", "DSP", "RSP", "BSL", "ISP"}
    assert len(r["summary"]) == 9
    assert r["warnings"] == []
    for plant, sections in r["plants"].items():
        for section, sec in sections.items():
            assert sec["total"] is not None, f"{plant}/{section} total row missing"
            statuses = {row["status"] for row in sec["rows"]}
            assert statuses <= {"ok", "missing_in_pdf"}, f"{plant}/{section}: {statuses}"


def test_september_page1_plants_extracted():
    r = _extract("2026-09")
    assert _row(r, "BSP", "INWARD", "Ind.Coking Coal", "BOXN")["monthly"]["2026-09"] == 11.4
    assert _row(r, "BSP", "INWARD", "Ind.Coking Coal", "BOST")["monthly"]["2026-09"] == 9.0


def test_older_report_rows_land_on_their_own_wagon_type():
    # FY 2025-26 report: 9 BSP inward rows vs 15 in today's registry.
    r = _extract("2026-02")
    bsp = r["plants"]["BSP"]["INWARD"]["rows"]
    assert sum(row["status"] == "ok" for row in bsp) == 9
    assert _row(r, "BSP", "INWARD", "Iron Ore", "BOBS/N")["monthly"]["2026-02"] == 3.2
    assert _row(r, "BSP", "INWARD", "Iron Ore", "BOXN")["monthly"]["2026-02"] == 9.4
    assert _row(r, "BSP", "INWARD", "Flux", "BOBS/N")["monthly"]["2026-02"] == 2.1
    assert _row(r, "BSP", "INWARD", "Boiler Coal", "BOXN")["monthly"]["2026-02"] == 17.2


def test_misplaced_commodity_text_does_not_misfile_rows():
    # BSP's "Boiler Coal" text is drawn on Imp. Coking Coal's BOSM line.
    r = _extract("2026-08")
    assert _row(r, "BSP", "INWARD", "Imp.Coking Coal", "BOSM")["monthly"]["2026-08"] == 17.0
    assert _row(r, "BSP", "INWARD", "Boiler Coal", "BOXN")["monthly"]["2026-08"] == 9.5


def test_rows_in_a_different_order_than_the_registry():
    # ISP lists its BCME rows ahead of the IISD ones; the registry groups by commodity.
    r = _extract("2026-08")
    assert _row(r, "ISP", "INWARD", "Ind. Coking Coal", "BOXN (IISD) *")["monthly"]["2026-08"] == 5.0
    assert _row(r, "ISP", "INWARD", "Imp. Coking Coal", "BOXN (IISD) *")["monthly"]["2026-08"] == 6.5
    assert _row(r, "ISP", "INWARD", "Iron Ore", "BOXN (IISD) *")["monthly"]["2026-08"] == 9.6


def test_wrapped_labels_are_reassembled():
    # ISP Overall: "BOXN (NEW" / numbers / "PLANT) *"
    r = _extract("2026-08")
    row = _row(r, "ISP", "OVERALL", None, "BOXN (NEW PLANT) *")
    assert row["monthly"]["2026-08"] == 7.3
