"""
"Major Environmental Performance Indicators (EPIs)" — landscape page
reproducing Report_format/Coal_co2/co2/epi.pdf's format: Sp. CO2 Emission /
Sp. Water Consumption / Sp. PM Emission, each a 6-row (BSP/DSP/RSP/BSL/ISP/
SAIL) block under 2 prior-FY actuals, the current FY's target, one growing
column per FY-to-date month, a same-month-last-year comparison, and two
FY-cumulative columns (this FY so far, and last FY's full total).

Sits right before the Coal Consumption page (EPI_PAGE_ID, main.py) — the
position the original 1-47 page plan always reserved for it (see
_INDEX_SECTIONS' "Major Environmental Performance Indicators (EPIs)" row in
main.py), which the mill-wise techno pages (27-35) ended up fully occupying
before this page existed.

No new computation here at all: these 3 parameters (techno_data unit=
"General", keys sp_co2_emission/sp_water_consumption/sp_pm_emission) are
already part of page_techno.py's page-27 "Major Techno-Economic Parameters"
table — generate_major_techno_from_db() already computes per-plant values
plus a Crude-Steel-weighted SAIL row, 2 prior-FY actuals, current-FY target
(from techno_plant_plan), FY-to-date monthly values, and both FY-cumulative
columns, for every section it builds. This page just calls that function
and keeps only the 3 sections it needs — reusing the exact figures page 27
already shows (and validates) rather than re-deriving them.
"""
from page_techno import generate_major_techno_from_db

_EPI_LABELS = ["Sp. CO2 Emission", "Sp. Water Consumption", "Sp. PM Emission"]


def generate_epi(report_month: str) -> dict:
    major = generate_major_techno_from_db(report_month)
    sections = [s for s in major["sections"] if s.get("label") in _EPI_LABELS]
    # Keep them in the fixed CO2/Water/PM order regardless of page 27's own
    # section ordering.
    sections.sort(key=lambda s: _EPI_LABELS.index(s["label"]))

    return {
        "type": "epi",
        "title": "Major Environmental Performance Indicators (EPIs)",
        "fy2_label": major["fy2_label"],
        "fy1_label": major["fy1_label"],
        "target_label": major["target_label"],
        "month_labels": major["month_labels"],
        "cply_label": major["cply_label"],
        "cum_label": major["cum_label"],
        "cum_cply_label": major["cum_cply_label"],
        "sections": sections,
    }
