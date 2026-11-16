"""Annexure-1 SAIL Mining at a Glance: the page dict, the separators and the badge group."""
import page_mining_leases as pml
import page_ready_reckoner as prr
import report_utils


def test_separator_labels():
    m = prr.generate_ready_reckoner_separator("MINING")
    assert (m["annexure_label"], m["group_label"], m["title"]) == (
        "Annexure-1", "SAIL Mining at a Glance", "Annexure-1 : SAIL Mining at a Glance")
    i = prr.generate_ready_reckoner_separator("ISP")
    assert (i["annexure_label"], i["group_label"]) == ("Annexure-2", "5 ISPs & 3 SSPs Ready Reckoner")


def test_page_dict(monkeypatch):
    monkeypatch.setattr(pml.mining_leases, "_stored", lambda: [])
    p = pml.generate_mining_leases()
    assert (p["type"], p["title"], p["available"], p["rows"]) == ("mining_leases", "SAIL Mining at a Glance", False, [])


def test_ids_are_free_and_in_the_annexure_badge_group():
    assert (pml.MINING_SEPARATOR_PAGE_ID, pml.MINING_PAGE_ID) == (1075, 1076)
    assert report_utils.dept_badge_group(1075) == report_utils.dept_badge_group(1076) == 11
    order = report_utils._CANONICAL_PAGE_ORDER
    assert order.index(1075) + 1 == order.index(1076) and order.index(1076) < order.index(prr.ISP_SEPARATOR_PAGE_ID)
