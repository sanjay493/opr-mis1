"""
Annexure-1 "SAIL Mining at a Glance": a separator page (page_ready_reckoner's
separator, "MINING"), then one page with the Details of SAIL Mining Leases table
(mining_leases.py), its mine / state / lease / mineral / area / reserves /
status cells merged down as the data entry's spans say. Sentinel ids sit clear
of every other range (Annexure-4 ends at 1074).
"""
import mining_leases

MINING_SEPARATOR_PAGE_ID = 1075
MINING_PAGE_ID = 1076


def generate_mining_leases() -> dict:
    return {"type": "mining_leases", "title": "SAIL Mining at a Glance", **mining_leases.build_page()}
