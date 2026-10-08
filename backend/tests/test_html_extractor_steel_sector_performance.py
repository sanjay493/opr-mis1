"""PIB 'Indian Steel Sector Performance' URL extractor, checked against saved
copies of the two real release pages (the content container of each, from
PressReleasePage.aspx?PRID=2306471 (Aug) and PRID=2319469 (Sep)). Fetching is
replaced by the fixture, so these run without network access."""

import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "excel_extractors"))
import html_extractor_steel_sector_performance as h  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "steel_sector")
AUG_URL = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2306471"
SEP_URL = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2319469"


def _extract(monkeypatch, fixture, url):
    with open(os.path.join(FIXTURES, fixture), encoding="utf-8") as f:
        page = f.read()
    monkeypatch.setattr(h, "_fetch_html", lambda _url: page)
    return h.extract_preview_from_url(url, "2026-09")


def test_every_table_gets_its_own_rows_in_both_releases(monkeypatch):
    expected = {"1a": 3, "1b": 4, "1c": 4, "2": 1, "3a": 4, "4a": 4, "5": 3}
    for fixture, url in (("pib_aug_container.html", AUG_URL), ("pib_sep_container.html", SEP_URL)):
        tables = _extract(monkeypatch, fixture, url)["tables"]
        assert {k: len(tables[k]["rows"]) for k in expected} == expected, fixture


def test_net_trade_position_is_a_3a_footnote_not_a_row(monkeypatch):
    aug = _extract(monkeypatch, "pib_aug_container.html", AUG_URL)["tables"]["3a"]
    sep = _extract(monkeypatch, "pib_sep_container.html", SEP_URL)["tables"]["3a"]
    assert not any("Net Trade" in (r[0] or "") for r in aug["rows"] + sep["rows"])
    assert any("India was net importer" in f and "Apr-Aug 2026" in f for f in aug["footnotes"])
    assert any("India was net importer" in f and "Apr-Sep 2026" in f for f in sep["footnotes"])


def test_text_sections_are_keyed_by_topic_not_printed_number(monkeypatch):
    sep = _extract(monkeypatch, "pib_sep_container.html", SEP_URL)["text_sections"]
    aug = _extract(monkeypatch, "pib_aug_container.html", AUG_URL)["text_sections"]

    assert set(sep) == {"6", "8"}
    assert sep["8"]["heading"].startswith("7. Green Steel")
    assert any("Green Steel Certificates" in p for p in sep["8"]["paragraphs"])
    assert not any("Green Steel Certificates" in p for p in sep["6"]["paragraphs"])

    assert set(aug) == {"6", "7", "8"}
    assert aug["7"]["heading"].startswith("7. International Co-operation")
    assert aug["8"]["heading"].startswith("8. Green Steel")
    assert len(aug["6"]["paragraphs"]) == 4


def test_table_1a_items_are_read_from_the_page(monkeypatch):
    items = _extract(monkeypatch, "pib_sep_container.html", SEP_URL)["production_overview_1a_items"]
    assert [i["item"] for i in items] == ["Crude Steel", "Hot Metal", "Finished Steel"]
    assert items[0]["report_month"] == 14.1


def test_non_pib_host_is_refused_before_any_fetch():
    with pytest.raises(ValueError):
        h._fetch_html("https://example.com/PressReleasePage.aspx?PRID=1")


@pytest.mark.parametrize("given, expected", [
    ("https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2319469&reg=48&lang=1",
     "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2319469&reg=48&lang=1"),
    ("https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2306471",
     "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2306471&lang=1"),
    (SEP_URL, "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2319469&lang=1"),
])
def test_any_pib_release_link_is_fetched_as_press_release_page(given, expected):
    assert h._page_url(given) == expected


@pytest.mark.parametrize("bad", [
    "https://example.com/PressReleasePage.aspx?PRID=1",
    "https://www.pib.gov.in/PressReleasePage.aspx",
])
def test_non_pib_or_id_less_links_are_rejected(bad):
    with pytest.raises(ValueError):
        h._page_url(bad)


def test_pasted_html_is_parsed_like_a_fetched_page():
    with open(os.path.join(FIXTURES, "pib_sep_container.html"), encoding="utf-8") as f:
        page = f.read()
    preview = h.extract_preview_from_html(page, "2026-09")
    assert preview["tables"]["1a"]["rows"][0][:2] == ["Crude Steel", "14.1"]
    assert preview["source_url"] is None


def test_fetch_retries_a_stalled_request(monkeypatch):
    import requests

    calls = []

    class _Resp:
        text = "<html>ok</html>"

        def raise_for_status(self):
            pass

    def fake_get(url, **_kw):
        calls.append(url)
        if len(calls) < 3:
            raise requests.exceptions.ReadTimeout("stalled")
        return _Resp()

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    assert h._fetch_html(SEP_URL) == "<html>ok</html>"
    assert len(calls) == 3
