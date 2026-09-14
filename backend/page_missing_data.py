"""
Missing Data Checklist — for a selected report_month, lists every monthly
data source the OMI Report (`/report`) depends on and whether it's been
submitted yet, grouped by report page/section and (where the underlying
table is plant-keyed) broken out per plant, each with the data-entry/
upload page(s) that would supply it. See docs/DATA_MODEL_AND_REPORT_PAGES.md
§3/§9.3 for the authoritative table/page/data-entry-page mapping this is
built from.

Deliberately scoped to genuinely monthly, currently-live-in-the-report
sources only — a presence check ("does this table have a row for
report_month/this plant yet") answers "did anyone forget to submit this
month's X", which is the actual question this page exists to answer.
Excluded, on purpose:
  - Annual/FY-keyed tables (techno_plan_fy, cost_trend_annual,
    special_steel_abp_table's per-plant target, special_steel_phys_perf/
    _meta/_note, special_steel_ipt_requirement, capital_repair_table,
    bf_benchmark_*, item_capacity_table) — these are targets/config, not
    something submitted fresh each month.
  - breakdown_table — zero rows can legitimately mean zero breakdowns that
    month, not missing data; flagging it would cry wolf every clean month.
  - mines_production_monthly / mines_despatch_*_monthly — per
    DATA_MODEL_AND_REPORT_PAGES.md §4.7's caveat, the SAIL Mines report page
    doesn't actually read these yet (the Iron Ore group tables there are
    still hardcoded), so a "missing" flag here wouldn't correspond to
    anything visibly wrong in the report.
  - key_highlights_narrative — page_key_highlights.py is "built, not
    currently in the report" per the same doc.
  - External/annexure reports (DO Letter, JPC, SEFI, 1-Page Report, Steel
    Bulletin) — not part of the `/report` OMI document itself.
  - techno_data's per-unit detail within pages 27-35 (which exact BF/SMS/
    Coke/Mill unit each plant should have) — checked only at "has this
    plant submitted ANY non-General-unit techno_data row this month"
    granularity; a genuinely per-unit/per-parameter audit would need a
    hardcoded registry of every valid unit per plant (plant_registry.py's
    PLANT_UNITS is for a different purpose - breakdown/CR unit
    classification, not a "required this month" list) and risks false
    "missing" flags for units a plant doesn't even have.
  - Key Parameters manual-entry fields (CAPEX, RLTIFR, Demurrage, etc. -
    also unit='General') aren't split out from the coarser EPI/Coal checks
    below; a General-unit row that's ONLY these isn't currently flagged as
    matching either the EPI or Coal check, which is correct (neither is
    actually present), but isn't surfaced as its own line either.
"""
import json as _json
import sys
from pathlib import Path

import db

_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from coal_co2_epi_extractor import ENVIRO_KEY_UNITS  # noqa: E402
from coal_omi_extractor import COAL_KEY_UNITS  # noqa: E402

_5P = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_POWER_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP", "SSP", "VISP", "CFP", "SAIL"]

_EPI_KEYS = set(ENVIRO_KEY_UNITS)          # sp_co2_emission, sp_water_consumption, sp_pm_emission
_COAL_KEYS = set(COAL_KEY_UNITS)           # indigenous_pcc, indigenous_mcc, imported_hard_coal, imported_soft_coal

_UPLOADS_PAGE = {"label": "Coal / CO2 / Power Uploads", "link": "/data-entry/uploads"}


def _rows(sql: str, params: list) -> list:
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def _distinct_plants(table: str, month_col: str, report_month: str) -> set:
    return {r[0] for r in _rows(f"SELECT DISTINCT plant_name FROM {table} WHERE {month_col} = ?", [report_month])}


def _any_row(table: str, month_col: str, report_month: str) -> bool:
    return bool(_rows(f"SELECT 1 FROM {table} WHERE {month_col} = ? LIMIT 1", [report_month]))


def _plant_check(label: str, present_set: set, data_entry: list) -> list:
    return [
        {"label": plant, "present": plant in present_set, "data_entry": data_entry}
        for plant in ([label] if isinstance(label, str) else label)
    ]


def _techno_data_presence(report_month: str) -> dict:
    """One pass over techno_data for report_month -> presence sets for the
    4 things it feeds that this checklist tracks (see module docstring for
    why unit-level detail beyond this split isn't attempted)."""
    rows = _rows("SELECT plant, unit, techno_json FROM techno_data WHERE report_month = ?", [report_month])
    other_unit_plants, epi_plants, coal_plants, coal_stock_sail = set(), set(), set(), False
    for plant, unit, tj in rows:
        if unit == "Coal_Receipt_Stock":
            if plant == "SAIL":
                coal_stock_sail = True
            continue
        if unit != "General":
            other_unit_plants.add(plant)
            continue
        try:
            parsed = _json.loads(tj) or {}
        except (ValueError, TypeError):
            continue
        keys = set(parsed.get("month") or {}) | set(parsed.get("till_month") or {})
        if keys & _EPI_KEYS:
            epi_plants.add(plant)
        if keys & _COAL_KEYS:
            coal_plants.add(plant)
    return {
        "other_unit_plants": other_unit_plants,
        "epi_plants": epi_plants,
        "coal_plants": coal_plants,
        "coal_stock_sail": coal_stock_sail,
    }


def generate_missing_data(report_month: str) -> dict:
    prod_plants = _distinct_plants("production_table", "report_month", report_month)
    ss_plants = _distinct_plants("special_steel_orders", "report_month", report_month)
    stock_plants = _distinct_plants("stock_table", "stock_month", report_month)
    power_plants = _distinct_plants("power_data_table", "report_month", report_month)
    techno = _techno_data_presence(report_month)

    sections = [
        {
            "id": "production",
            "title": "Production Data",
            "report_pages": "1 (At-a-Glance), 3, 4, 5–6, 7–12, 13, 14, 15–17, 18",
            "checks": _plant_check(_5P, prod_plants, [
                {"label": "Production Upload (Actuals)", "link": "/upload"},
                {"label": "Production Data Entry (manual)", "link": "/data-entry/production"},
            ]),
        },
        {
            "id": "special_steel",
            "title": "Special Steel — Orders & Despatch",
            "report_pages": "19–24 (+ Special Steel Trend)",
            "checks": _plant_check(_5P, ss_plants, [
                {"label": "Production, Stock & Special Steel Upload", "link": "/upload"},
                {"label": "Special Steel Manual Entry (ISP)", "link": "/data-entry/special-steel"},
            ]),
        },
        {
            "id": "opening_stock",
            "title": "Opening Stock",
            "report_pages": "25",
            "checks": _plant_check(_5P, stock_plants, [
                {"label": "Opening Stock", "link": "/data-entry/opening-stock"},
            ]),
        },
        {
            "id": "techno_params",
            "title": "Techno-Economic Parameters (BF / Coke & Coal Chemicals / Iron Making / BOF Shop / Mill-wise)",
            "report_pages": "27–35",
            "checks": _plant_check(_5P, techno["other_unit_plants"], [
                {"label": "Techno Upload", "link": "/data-entry/techno"},
                {"label": "Techno Manual Entry", "link": "/data-entry/techno-manual"},
            ]),
        },
        {
            "id": "epi",
            "title": "CO2 / Water / PM EPI",
            "report_pages": "35.4",
            "checks": _plant_check(_5P, techno["epi_plants"], [
                _UPLOADS_PAGE,
                {"label": "CO2/Water/PM Manual Entry", "link": "/data-entry/co2-water-pm-manual"},
                {"label": "CO2/Water/PM (extracted params)", "link": "/data-entry/co2-water-pm"},
            ]),
        },
        {
            "id": "coal_consumption",
            "title": "Coal Consumption (Indigenous/Imported Coking Coal)",
            "report_pages": "35.5",
            "checks": _plant_check(_5P, techno["coal_plants"], [
                _UPLOADS_PAGE,
                {"label": "Coal Consumption Dashboard", "link": "/data-entry/coal-consumption"},
            ]),
        },
        {
            "id": "coal_receipt_stock",
            "title": "Coking Coal Receipts & Stock (SAIL)",
            "report_pages": "35.6",
            "checks": [{
                "label": "SAIL",
                "present": techno["coal_stock_sail"],
                "data_entry": [_UPLOADS_PAGE],
            }],
        },
        {
            "id": "power",
            "title": "Power Data",
            "report_pages": "35.7",
            "checks": _plant_check(_POWER_PLANTS, power_plants, [_UPLOADS_PAGE]),
        },
        {
            "id": "cost_trend",
            "title": "Cost Trend (HM / CS / SS)",
            "report_pages": "3.61–3.63 (+ Key Parameters CoP rows)",
            "checks": [{
                "label": "SAIL (all plants)",
                "present": _any_row("cost_trend_monthly", "report_month", report_month),
                "data_entry": [
                    {"label": "Cost Trend", "link": "/data-entry/cost-trend"},
                    {"label": "Cost Trend Excel Extractor", "link": "/data-entry/cost-trend-extract"},
                ],
            }],
        },
        {
            "id": "sail_mines",
            "title": "SAIL Mines Production & Despatch",
            "report_pages": "4.5",
            "checks": [{
                "label": "SAIL Mines",
                "present": _any_row("sail_mines_monthly", "report_month", report_month),
                "data_entry": [{"label": "SAIL Mines Entry", "link": "/data-entry/sail-mines"}],
            }],
        },
        {
            "id": "ipt",
            "title": "IPT (Inter-Plant Transfer) Status",
            "report_pages": "26",
            "checks": [{
                "label": "All routes",
                "present": _any_row("ipt_table", "report_month", report_month),
                "data_entry": [{"label": "IPT Status", "link": "/data-entry/ipt"}],
                "note": "No rows can also mean no transfers occurred this month — verify before treating as missing.",
            }],
        },
        {
            "id": "steel_sector_performance",
            "title": "Indian Steel Sector Performance (PIB)",
            "report_pages": "2.1–2.3",
            "checks": [{
                "label": "PIB Release",
                "present": _any_row("steel_sector_performance_table", "report_month", report_month),
                "data_entry": [{"label": "Steel Sector Performance", "link": "/data-entry/steel-sector-performance"}],
            }],
        },
        {
            "id": "special_steel_abp",
            "title": "Special Steel ABP",
            "report_pages": "19–24 (ABP column)",
            "checks": [{
                "label": "All plants",
                "present": _any_row("special_steel_abp_table", "report_month", report_month),
                "data_entry": [{"label": "Special Steel ABP", "link": "/data-entry/special-steel-abp"}],
            }],
        },
        {
            "id": "page3_narrative",
            "title": "Production Summary Narrative",
            "report_pages": "3",
            "checks": [{
                "label": "SAIL",
                "present": bool(_rows(
                    "SELECT 1 FROM page3_narrative WHERE report_month = ? "
                    "AND (COALESCE(production_narrative,'') != '' OR COALESCE(highlights,'') != '')",
                    [report_month])),
                "data_entry": [{"label": "Report page 3 (inline edit)", "link": "/report"}],
            }],
        },
    ]

    total = sum(len(s["checks"]) for s in sections)
    missing = sum(1 for s in sections for c in s["checks"] if not c["present"])

    return {
        "report_month": report_month,
        "sections": sections,
        "total_checks": total,
        "missing_count": missing,
    }
