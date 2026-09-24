"""
"Annexure-III : 5 ISPs Major Units Records" — per-plant, per-major-unit
best-ever production records (Annual/Monthly/Daily), appended at the very
end of the PDF report, right after the Ready Reckoner Annexures. Mirrors
page_ready_reckoner.py's separator + per-plant page shape.

Source for BSP/BSL/RSP/ISP: I:\\My Drive\\Report_format\\Plants Best\\
{BSP,BSL,RSP,ISP}.xlsx — Annual/Monthly there were cross-checked against
production_table via scripts/verify_major_unit_best_records.py. DSP has no
such workbook; its unit list + item_name mapping were given directly (per
instruction, 2026-09-23), so there was no Annual/Monthly xlsx cross-check
for it and its Daily figures start empty (no source to backfill from —
filled in going forward via /data-entry/major-unit-daily). A plant with an
empty registry (none currently) would have its page omitted from
pages_config until filled in — see MAJOR_UNIT_ACTIVE_PAGES.

"Saleable Steel Despatch" (item_names=["Saleable Steel Despatch"]) was added
to every plant's registry per instruction (2026-09-23) — ISP/DSP already had
it (ISP's under the pre-existing label "Saleable Steel loading", kept as-is
since it already carries backfilled Daily data under that key); BSP/BSL/RSP
did not, and none of their source workbooks list it either, so like DSP it
has no Annual/Monthly xlsx cross-check and starts with no Daily figure
(filled in going forward via /data-entry/major-unit-daily). It will show as
NOT_IN_WORKBOOK for BSP/BSL/RSP in verify_major_unit_best_records.py — expected.

Annual/Monthly bests are NEVER stored — they're computed live from
production_table (see best_for_unit below), the same "single source of
truth" principle as page_records.py's generate_records(). Only Daily bests
have no existing DB home (production_table is monthly grain) and are
stored in major_unit_daily_record (see db.py).

_UNIT_REGISTRY maps each plant's major units (in report-page order) to the
production_table item_name(s) that unit's figure is made of — most are a
single item, a few are a genuine sum of two+ casting/rolling routes (e.g.
BSL/RSP's SMS shops report an Ingot route and a CCM route as separate
production_table items that together make that SMS's total crude steel).
Entries with item_names=[] have no confident production_table mapping
(verified via scripts/verify_major_unit_best_records.py against each
plant's source xlsx) — their Annual/Monthly best render as "—"; only their
Daily best (from major_unit_daily_record, entered from the source xlsx /
the data-entry page) is shown.
"""
import html

import db

ISP_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]

_PLANT_NAMES = {
    "BSP": "Bhilai Steel Plant", "DSP": "Durgapur Steel Plant",
    "RSP": "Rourkela Steel Plant", "BSL": "Bokaro Steel Plant", "ISP": "IISCO Steel Plant",
}

# unit_of_measure per row — 'T' (Annual/Monthly are '000 T per the source
# workbooks' own headers, scaled ×1000 at render time to match Daily's
# plain-T grain — see best_for_unit) or 'Nos/day' for Oven Pushing, whose
# monthly *value itself* is already a rate, never summed across a year.
_T = "T"
_RATE = "Nos/day"

# plant -> [{label, item_names: [...], unit: 'T'|'Nos/day'}, ...] in the
# same order as that plant's source xlsx.
_UNIT_REGISTRY = {
    "BSL": [
        {"label": "Oven Pushing",        "item_names": ["Oven Pushing (nos/day)"], "unit": _RATE},
        {"label": "Total Sinter",        "item_names": ["Total Sinter"],           "unit": _T},
        {"label": "Blast Furnace-1",     "item_names": ["BF#1"],                   "unit": _T},
        {"label": "Blast Furnace-2",     "item_names": ["BF#2"],                   "unit": _T},
        {"label": "Blast Furnace-3",     "item_names": ["BF#3"],                   "unit": _T},
        {"label": "Blast Furnace-4",     "item_names": ["BF#4"],                   "unit": _T},
        {"label": "Blast Furnace-5",     "item_names": ["BF#5"],                   "unit": _T},
        {"label": "Total Hot Metal",     "item_names": ["Hot Metal"],              "unit": _T},
        {"label": "Steel Melting Shop-1","item_names": ["SMS-1 Ingot", "SMS-1 CCM-1"], "unit": _T},
        {"label": "Steel Melting Shop-2","item_names": ["SMS-2 CCM-1&2"],          "unit": _T},
        {"label": "Total Crude Steel",   "item_names": ["Total Crude Steel"],      "unit": _T},
        {"label": "Hot Strip Mill",      "item_names": ["HSM Total HR Coil"],      "unit": _T},
        {"label": "CRM-1,2",             "item_names": ["CR(1&2) Total Saleable"], "unit": _T},
        {"label": "CRM-3",               "item_names": ["CR III Total Saleable"],  "unit": _T},
        {"label": "Saleable Steel",      "item_names": ["Saleable Steel"],         "unit": _T},
        {"label": "Saleable Steel Despatch", "item_names": ["Saleable Steel Despatch"], "unit": _T},
    ],
    "RSP": [
        {"label": "Oven Pushing : Old",   "item_names": [], "unit": _RATE},
        {"label": "COB#6",                "item_names": ["COB#6"], "unit": _RATE},
        {"label": "Eqvt. Oven Pushing",   "item_names": ["Oven Pushing (nos/day)"], "unit": _RATE},
        {"label": "Sinter : SP-I",        "item_names": ["SP-1"], "unit": _T},
        {"label": "Sinter : SP-II",       "item_names": ["SP-2"], "unit": _T},
        {"label": "Sinter : SP-III",      "item_names": ["SP-3"], "unit": _T},
        {"label": "Sinter - Total",       "item_names": ["Total Sinter"], "unit": _T},
        {"label": "BF#1",                 "item_names": ["BF#1"], "unit": _T},
        {"label": "BF#4",                 "item_names": ["BF#4"], "unit": _T},
        {"label": "BF#5",                 "item_names": ["BF#5"], "unit": _T},
        {"label": "Hot Metal",            "item_names": ["Hot Metal"], "unit": _T},
        {"label": "SMS-I",                "item_names": ["SMS-1 Ingot", "SMS-1 CCM-1"], "unit": _T},
        {"label": "SMS-II",               "item_names": ["SMS-2 CCM-1&2", "SMS-2 CCM-3", "SMS-2 CCM-4"], "unit": _T},
        {"label": "Crude Steel - Total",  "item_names": ["Total Crude Steel"], "unit": _T},
        {"label": "HR Coils prod. HSM-2", "item_names": ["HSM-2 Total HR Coil"], "unit": _T},
        {"label": "PM Plates prod.",      "item_names": ["OPM Plate"], "unit": _T},
        {"label": "New Plate Mill",       "item_names": ["NPM Plate"], "unit": _T},
        {"label": "Saleable Steel Despatch", "item_names": ["Saleable Steel Despatch"], "unit": _T},
    ],
    "ISP": [
        {"label": "Oven Pushing",         "item_names": ["Oven Pushing (nos/day)"], "unit": _RATE},
        {"label": "Sinter",               "item_names": ["Total Sinter"], "unit": _T},
        {"label": "Hot Metal",            "item_names": ["Hot Metal"], "unit": _T},
        {"label": "Crude Steel",          "item_names": ["Total Crude Steel"], "unit": _T},
        {"label": "WRM",                  "item_names": ["WRMILL"], "unit": _T},
        {"label": "Bar Mill",             "item_names": ["BARMILL"], "unit": _T},
        {"label": "USM",                  "item_names": ["USMILL"], "unit": _T},
        {"label": "SEMIS",                "item_names": ["Saleable Semis"], "unit": _T},
        {"label": "FIN. STEEL",           "item_names": ["Finished Steel"], "unit": _T},
        {"label": "Saleable Steel",       "item_names": ["Saleable Steel"], "unit": _T},
        {"label": "Saleable Steel loading","item_names": ["Saleable Steel Despatch"], "unit": _T},
    ],
    "BSP": [
        # BF#1, BF#1-7, SMS-I and the 4 Cast Steel semis rows (SMS-2 Blooms/
        # Slabs, SMS-3 Billets/Blooms) removed per direct instruction, 2026-09-23.
        {"label": "COB-11 (Pushings/day)",      "item_names": ["COB#11"], "unit": _RATE},
        {"label": "Eq. Oven Pushing",           "item_names": ["Oven Pushing (nos/day)"], "unit": _RATE},
        {"label": "SP-II",                      "item_names": ["SP-2"], "unit": _T},
        {"label": "SP-III M/c-1",               "item_names": ["SP-3 M/C-1"], "unit": _T},
        {"label": "SP-III M/c-2",               "item_names": ["SP-3 M/C-2"], "unit": _T},
        {"label": "SP-III",                     "item_names": ["SP-3"], "unit": _T},
        {"label": "Total Sinter",               "item_names": ["Total Sinter"], "unit": _T},
        {"label": "BF#4",                       "item_names": ["BF#4"], "unit": _T},
        {"label": "BF#5",                       "item_names": ["BF#5"], "unit": _T},
        {"label": "BF#6",                       "item_names": ["BF#6"], "unit": _T},
        {"label": "BF#7",                       "item_names": ["BF#7"], "unit": _T},
        {"label": "BF#8",                       "item_names": ["BF#8"], "unit": _T},
        {"label": "Total Hot Metal",            "item_names": ["Hot Metal"], "unit": _T},
        {"label": "SMS-II",                     "item_names": ["SMS-2"], "unit": _T},
        {"label": "SMS-III",                    "item_names": ["SMS-3"], "unit": _T},
        {"label": "Total Crude Steel",          "item_names": ["Total Crude Steel"], "unit": _T},
        {"label": "Finished Rails: RSM",        "item_names": ["RSM_RAIL"], "unit": _T},
        {"label": "Finished Rails: URM",        "item_names": ["URM_RAIL"], "unit": _T},
        {"label": "Total Finished Rails",       "item_names": ["RSM_RAIL", "URM_RAIL"], "unit": _T},
        {"label": "Prime Rails: RSM",           "item_names": ["RSMPRIME"], "unit": _T},
        {"label": "Prime Rails: URM",           "item_names": ["URMPRIME"], "unit": _T},
        {"label": "Total Prime Rails",          "item_names": ["RSMPRIME", "URMPRIME"], "unit": _T},
        {"label": "Merchant Mill",              "item_names": ["MM"], "unit": _T},
        # WIRERODS is BSP's WRM total (= OTHERS(WRM) + TMT COILS(WRM), which only
        # exist from 2025-04) and carries the full history back to 2010.
        {"label": "WRM",                        "item_names": ["WIRERODS"], "unit": _T},
        {"label": "BRM",                        "item_names": ["BARS&RODMILL"], "unit": _T},
        {"label": "Plate Mill",                 "item_names": ["PLATEMILL"], "unit": _T},
        {"label": "Total Finished Steel",       "item_names": ["Finished Steel"], "unit": _T},
        {"label": "Total Saleable Steel",       "item_names": ["Saleable Steel"], "unit": _T},
        {"label": "Saleable Steel Despatch",    "item_names": ["Saleable Steel Despatch"], "unit": _T},
    ],
    # Unit list + production_table mapping per direct instruction, 2026-09-23
    # (DSP has no source "Plants Best" workbook — no Annual/Monthly xlsx
    # cross-check was run for these, unlike BSP/BSL/RSP/ISP; the live
    # production_table figures ARE the record here). "W&F" = Wheel & Axle
    # combined (production_table has no single item for it) — sum of
    # 'wheel plant' + 'Axle plant', same pattern as BSL/RSP's SMS shops
    # summing an Ingot + a CCM route. No Daily source either — those rows
    # start empty and are filled in via /data-entry/major-unit-daily going
    # forward (see that page's own note about DSP).
    "DSP": [
        {"label": "Oven Pushing",            "item_names": ["Oven Pushing (nos/day)"], "unit": _RATE},
        {"label": "SP-1",                    "item_names": ["SP-1"], "unit": _T},
        {"label": "SP-2",                    "item_names": ["SP-2"], "unit": _T},
        {"label": "Sinter - Total",          "item_names": ["Total Sinter"], "unit": _T},
        {"label": "BF-2",                    "item_names": ["BF#2"], "unit": _T},
        {"label": "BF-3",                    "item_names": ["BF#3"], "unit": _T},
        {"label": "BF-4",                    "item_names": ["BF#4"], "unit": _T},
        {"label": "Hot Metal - Total",       "item_names": ["Hot Metal"], "unit": _T},
        {"label": "Crude Steel - Total",     "item_names": ["Total Crude Steel"], "unit": _T},
        {"label": "MSM",                     "item_names": ["MSM"], "unit": _T},
        {"label": "SM",                      "item_names": ["SM"], "unit": _T},
        {"label": "MM",                      "item_names": ["MM"], "unit": _T},
        {"label": "W&F",                     "item_names": ["wheel plant", "Axle plant"], "unit": _T},
        {"label": "Finished Steel",          "item_names": ["Finished Steel"], "unit": _T},
        {"label": "Saleable Steel",          "item_names": ["Saleable Steel"], "unit": _T},
        {"label": "Saleable Steel Despatch", "item_names": ["Saleable Steel Despatch"], "unit": _T},
    ],
}


def _fy_of(report_month: str) -> int:
    y, m = int(report_month[:4]), int(report_month[5:7])
    return y if m >= 4 else y - 1


def _fy_label(fy_start: int) -> str:
    return f"{fy_start}-{str(fy_start + 1)[2:]}"


def _mon_label(report_month: str) -> str:
    _MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    y, m = report_month[:4], int(report_month[5:7])
    return f"{_MON[m]}'{y[2:]}"


def _days_in(report_month: str) -> int:
    import calendar
    y, m = int(report_month[:4]), int(report_month[5:7])
    return calendar.monthrange(y, m)[1]


def best_for_unit(cur, plant: str, item_names: list, is_rate: bool) -> dict:
    """{'month_best': {'value','period'} | None, 'fy_best': {'value','period'} | None}
    for one registry unit — computed live from production_table, summing
    item_names per month (tonnage) or per-day-weighted-averaging them
    (rate items) across a complete FY (12 months present) for fy_best.
    month_best is just the single highest monthly value in the plant's
    whole history. Returns Nones throughout for an unmapped unit
    (item_names == [])."""
    empty = {"month_best": None, "fy_best": None}
    if not item_names:
        return empty

    ph = ",".join("?" * len(item_names))
    cur.execute(f"""
        SELECT report_month, SUM(month_actual)
        FROM production_table
        WHERE plant_name = ? AND item_name IN ({ph})
        GROUP BY report_month
    """, [plant] + item_names)
    monthly = {rm: v for rm, v in cur.fetchall() if v is not None}
    if not monthly:
        return empty

    best_rm = max(monthly, key=lambda rm: monthly[rm])
    month_best = {"value": round(monthly[best_rm], 3), "period": _mon_label(best_rm)}

    fy_groups = {}
    for rm, v in monthly.items():
        fy_groups.setdefault(_fy_of(rm), {})[rm] = v
    fy_best = None
    for fy_start, months in fy_groups.items():
        if len(months) != 12:
            continue
        if is_rate:
            wsum = sum(v * _days_in(rm) for rm, v in months.items())
            wdays = sum(_days_in(rm) for rm in months)
            total = wsum / wdays if wdays else None
        else:
            total = sum(months.values())
        if total is None:
            continue
        total = round(total, 3)
        if fy_best is None or total > fy_best["value"]:
            fy_best = {"value": total, "period": _fy_label(fy_start)}
    return {"month_best": month_best, "fy_best": fy_best}


def registry_for(plant: str) -> list:
    return _UNIT_REGISTRY.get(plant, [])


# Sentinel page ids — clear of every existing range (1024-1029/1038-1040
# trend/rail/SS-physical/rake-detention, 1041-1058 Ready Reckoner ISP/SSP,
# 1059-1066 Ready Reckoner's reserved product-mix overflow). One id per
# plant is reserved so a future plant needing renumbering-free insertion
# stays possible (see MAJOR_UNIT_PAGES / main.py wiring).
MAJOR_UNIT_SEPARATOR_PAGE_ID = 1067
MAJOR_UNIT_PAGES = {1068 + i: plant for i, plant in enumerate(ISP_PLANTS)}  # 1068-1072

# Plants with an actual registry (i.e. either a source workbook was read and
# mapped, or the unit list + mapping was given directly, as for DSP — see
# module docstring) — this report's physical page set. A plant with an
# empty registry would have its id stay reserved in MAJOR_UNIT_PAGES above
# but left out of pages_config until filled in.
MAJOR_UNIT_ACTIVE_PAGES = {pg: plant for pg, plant in MAJOR_UNIT_PAGES.items() if _UNIT_REGISTRY.get(plant)}


def generate_major_unit_separator() -> dict:
    """A blank Annexure separator page, right before the section's first
    plant page — same shape as page_ready_reckoner.generate_ready_reckoner_
    separator."""
    return {
        "type": "major_unit_records_separator",
        "title": "Annexure-III : 5 ISPs Major Units Records",
        "annexure_label": "Annexure-III",
        "group_label": "5 ISPs Major Units Records",
    }


def _fmt_num(value: float) -> str:
    s = f"{value:,.2f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _fmt_period(period: str) -> str:
    """Wraps a period (FY/month/date) in its own span so the template can
    give it a distinguished color, set apart from the record value beside
    it — this env's autoescape is off (see pdf.py), so the span is emitted
    as real HTML; `period` is always one of our own computed labels
    (_fy_label/_mon_label/an ISO date string), never editor-entered text."""
    return f'<span class="mur-period">({period})</span>'


def _fmt_pair(pair) -> str:
    """{'value','period'} -> '1,156.89 <span class="mur-period">(2024-25)
    </span>', or '—' when None."""
    if not pair or pair.get("value") is None:
        return "—"
    return f"{_fmt_num(pair['value'])} {_fmt_period(pair['period'])}"


def _fmt_daily(daily) -> str:
    if not daily:
        return "—"
    if daily.get("value") is not None:
        date_part = f" {_fmt_period(daily['date'])}" if daily.get("date") else ""
        return f"{_fmt_num(daily['value'])}{date_part}"
    remarks = daily.get("remarks")
    # Unlike value/period, remarks is free text an editor typed into
    # /data-entry/major-unit-daily — escape it since this env's autoescape
    # is off (see pdf.py's _rr_cell for the same rule on a similar field).
    return html.escape(remarks) if remarks else "—"


# Rows worth calling out visually on the printed page (see
# major_unit_records_plant.html's CSS) — driven by the same semantic keys
# used everywhere else in this module (item_names / rate-vs-tonnage) rather
# than by matching each plant's own wording for a label, since that varies
# a lot (e.g. "Total Hot Metal" / "Hot Metal - Total" / bare "Hot Metal" all
# mean the same thing). A plant missing one of these (e.g. RSP has no
# "Saleable Steel" row at all) simply never gets that class — nothing to
# highlight there.
_HIGHLIGHT_TOTAL_ITEM_NAMES = {
    ("Hot Metal",), ("Total Crude Steel",), ("Finished Steel",),
    ("Saleable Steel",), ("Saleable Steel Despatch",),
}


def _row_class(item_names: list, is_rate: bool) -> str:
    if is_rate:
        # Every Nos/day row is a single oven/COB pushing rate (Oven
        # Pushing, Eq./Eqvt. Oven Pushing, COB#6, COB#11, ...) — mapped or
        # not (RSP's "Oven Pushing : Old" is unmapped but still a pushing
        # row), so this only needs the unit, not item_names.
        return "mur-row-pushing"
    if tuple(item_names) in _HIGHLIGHT_TOTAL_ITEM_NAMES:
        return "mur-row-total"
    return ""


def generate_major_unit_page(plant_code: str) -> dict:
    """One plant's Annexure-III page: Unit / Annual Best / Monthly Best /
    Daily Best. Annual/Monthly are computed live from production_table
    (best_for_unit); Daily is read from major_unit_daily_record. Each row
    carries both the raw figures (annual/monthly/daily) and pre-formatted
    display strings (annual_display/monthly_display/daily_display) — the
    template only renders strings, all number/period formatting happens
    here, same division of labor as page_ready_reckoner.py's rows."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        daily_by_unit = db.get_major_unit_daily_records_all().get(plant_code, {})
        rows = []
        for unit in registry_for(plant_code):
            live = best_for_unit(cur, plant_code, unit["item_names"], unit["unit"] == _RATE)
            daily_row = daily_by_unit.get(unit["label"])
            daily = ({"value": daily_row["value"], "date": daily_row["record_date"],
                      "remarks": daily_row["remarks"]}
                     if daily_row and (daily_row["value"] is not None or daily_row["remarks"])
                     else None)
            rows.append({
                "label": unit["label"],
                "unit": unit["unit"],
                "row_class": _row_class(unit["item_names"], unit["unit"] == _RATE),
                "annual_display": _fmt_pair(live["fy_best"]),
                "monthly_display": _fmt_pair(live["month_best"]),
                "daily_display": _fmt_daily(daily),
            })
    finally:
        conn.close()

    return {
        "type": "major_unit_records",
        "title": f"{_PLANT_NAMES.get(plant_code, plant_code)} — Major Units Records",
        "plant_code": plant_code,
        "plant_name": _PLANT_NAMES.get(plant_code, plant_code),
        "rows": rows,
    }
