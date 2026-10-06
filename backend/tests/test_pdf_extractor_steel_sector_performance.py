"""PIB 'Indian Steel Sector Performance' PDF extractor, checked against the two
real monthly releases (Aug and Sep 2026). Skipped where the I: drive folder
isn't mounted."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "excel_extractors"))
import pdf_extractor_steel_sector_performance as pdf  # noqa: E402

PIB_DIR = "I:/My Drive/Report_format/pib"
SEP_PDF = os.path.join(PIB_DIR, "Press Release_ Press Information Bureau.pdf")
AUG_PDF = os.path.join(PIB_DIR, "Press Release_ Press Information Bureau Aug.pdf")

needs_pib = pytest.mark.skipif(
    not (os.path.exists(SEP_PDF) and os.path.exists(AUG_PDF)),
    reason="PIB release PDFs not mounted",
)


@needs_pib
def test_every_table_gets_its_own_rows_in_both_releases():
    expected = {"1a": 3, "1b": 4, "1c": 4, "2": 1, "3a": 4, "4a": 4, "5": 3}
    for path in (SEP_PDF, AUG_PDF):
        tables = pdf.extract_preview(path, "2026-09")["tables"]
        counts = {k: len(tables[k]["rows"]) for k in expected}
        assert counts == expected, path


@needs_pib
def test_table_rows_carry_their_own_labels():
    for path in (SEP_PDF, AUG_PDF):
        tables = pdf.extract_preview(path, "2026-09")["tables"]
        assert tables["1c"]["rows"][0][0] == "TMT (10 mm)"
        assert tables["4a"]["rows"][0][0].startswith("NMDC Iron Ore Baila Lump")
        assert tables["5"]["rows"][0][0] == "Nifty Metal Index (avg.)"


@needs_pib
def test_net_trade_position_is_a_3a_footnote_not_a_row():
    sep = pdf.extract_preview(SEP_PDF, "2026-09")["tables"]["3a"]
    aug = pdf.extract_preview(AUG_PDF, "2026-09")["tables"]["3a"]
    assert not any("Net Trade" in (r[0] or "") for r in sep["rows"] + aug["rows"])
    assert any("India was net importer" in f and "Apr-Sep 2026" in f for f in sep["footnotes"])
    assert any("India was net importer" in f and "Apr-Aug 2026" in f for f in aug["footnotes"])


@needs_pib
def test_text_sections_are_keyed_by_topic_not_printed_number():
    sep = pdf.extract_preview(SEP_PDF, "2026-09")["text_sections"]
    aug = pdf.extract_preview(AUG_PDF, "2026-09")["text_sections"]

    # September has no International Co-operation section, and Green Steel is
    # printed as "7." — it must still land under key 8 and key 7 must be absent.
    assert set(sep) == {"6", "8"}
    assert sep["8"]["heading"].startswith("7. Green Steel")
    assert any("Green Steel Certificates" in p for p in sep["8"]["paragraphs"])

    # Section 6 must stop at the Green Steel heading, not run into section 8.
    assert not any("Green Steel Certificates" in p for p in sep["6"]["paragraphs"])
    assert any("SAIL and Bharat Coking Coal" in p for p in sep["6"]["paragraphs"])

    # The release's page 4 opens a new paragraph in section 6, after a
    # sentence-ending line at the foot of page 3 — it must not merge into it.
    assert len(aug["6"]["paragraphs"]) == 4
    assert aug["6"]["paragraphs"][-1].startswith("NMDC has successfully lit up")

    assert set(aug) == {"6", "7", "8"}
    assert aug["7"]["heading"].startswith("7. International Co-operation")
    assert aug["8"]["heading"].startswith("8. Green Steel")
