"""
"Annexure-4 : SAIL (8 Plants) Production Trend" -- Hot Metal, Crude Steel,
Pig Iron and Saleable Steel (with its Semi Finished Steel / Finished Steel
components shown indented, dash-prefixed, right under Saleable Steel),
FY-wise from FY2007-08 onward. Appended at the very end of the PDF report,
right after "Annexure-3 : 5 ISPs Major Units Records" -- mirrors
page_major_unit_records.py's separator + content-page shape.

Two stacked tables on the one content page: FY2007-08..FY2016-17 (a fixed
decade) on the bottom, FY2017-18 onward (grows with report_month) on top --
per direct instruction, the bottom table always starts at FY2007-08.

Aggregation mirrors conventions already established elsewhere in this
codebase for these exact figures:
  - Hot Metal / Total Crude Steel / Pig Iron / Saleable Steel: prefer the
    directly-stored 'SAIL' plant row for a month, falling back to a live sum
    of all 8 plants -- same as page7_13.py's _sail_or_sum.
  - Finished Steel: prefer a LIVE sum of all 8 plants (self-consistent --
    doesn't drift when a constituent plant's own figure is corrected
    afterwards), falling back to the stored SAIL row only when the live sum
    would be partial -- same as page7_13.py's _live_sum_or_sail_fallback /
    prefer_live_sum. SSP/VISL, which don't track Finished Steel separately,
    fall back to their own Saleable Steel figure for that month -- same
    _FS_ALIAS fold as page5_6.py / page7_13.py.
  - Semi Finished Steel: no stored SAIL row exists for this at all -- always
    a live sum of BSP/DSP/RSP/BSL/ISP's own "Saleable Semis" item plus ASP's
    Saleable Steel minus Finished Steel (ASP has no separate semis item) --
    the exact SAIL "Semi-finished steel" formula from page5_6.py's
    PAGE5_PLANTS SAIL row. SSP/VISL are excluded, same as page5_6.py, since
    neither reports a semis/finished split at all.

Every closed FY (2007-08..2025-26) is then overridden with the verified
figures in _REFERENCE_VALUES below, sourced from SAIL's own published
PRODUCTION summary (2026-09-25) -- production_table's live computation
disagreed with it on 61 of 114 cells, overwhelmingly on Pig Iron (entirely
missing pre-2012-13) and Semi Finished Steel (entirely missing pre-2012-13,
and wrong even where present -- the live formula above just doesn't match
whatever SAIL's own source table derives it from). See
docs/SAIL8_TREND_DATA_CORRECTIONS.md for the full cell-by-cell list, kept
for whoever backfills/fixes production_table later -- once a closed year's
DB figures are corrected to match, its _REFERENCE_VALUES entry becomes dead
code to remove, not a value to keep updating (same convention as
page_major_unit_records.py's _ANNUAL_RECORD_FLOOR). Only the still-open
current FY (not in the source table) comes from the live computation.
"""
import db
from constants import ALL_PLANTS as _SAIL_8

_FIVE_ISPS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_FS_ALIAS_PLANTS = frozenset({"SSP", "VISL"})

# Sentinel page ids -- clear of every existing range, right after Annexure-3
# (page_major_unit_records.py's MAJOR_UNIT_PAGES ends at 1072). See main.py's
# wiring (import block, _INDEX_SECTIONS/_INDEX_SECTION_ANCHORS, pages_config
# assembly x2, per-page dispatch x2).
SAIL8_TREND_SEPARATOR_PAGE_ID = 1073
SAIL8_TREND_PAGE_ID = 1074

# Bottom table's fixed decade, per direct instruction ("bottom table start
# data from FY 2007-08") -- FY2007-08 through FY2016-17. Top table picks up
# at FY2017-18 and grows with report_month.
_BOTTOM_FY_START = 2007
_BOTTOM_FY_END = 2016


def _fy_of(report_month: str) -> int:
    y, m = int(report_month[:4]), int(report_month[5:7])
    return y if m >= 4 else y - 1


def _fy_label(fy_start: int) -> str:
    return f"{fy_start % 100:02d}-{(fy_start + 1) % 100:02d}"


_MON_ABBR = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _running_year_label(report_month: str) -> str:
    """The current (still-open) FY's column header: 'Apr-<report month>' --
    e.g. 'Apr-Aug'26' for report_month 2026-08 -- rather than a closed
    FY's plain 'yy-yy' label, since this year only has data through
    report_month."""
    y, m = int(report_month[:4]), int(report_month[5:7])
    return f"Apr-{_MON_ABBR[m]}'{y % 100:02d}"


def _year_label(fy_start: int, report_month: str, cur_fy: int) -> str:
    return _running_year_label(report_month) if fy_start == cur_fy else _fy_label(fy_start)


def _fy_months(fy_start: int) -> list:
    months = [f"{fy_start}-{m:02d}" for m in range(4, 13)]
    months += [f"{fy_start + 1}-{m:02d}" for m in range(1, 4)]
    return months


def _months_for_fy(fy_start: int, report_month: str, cur_fy: int) -> list:
    if fy_start > cur_fy:
        return []
    months = _fy_months(fy_start)
    if fy_start == cur_fy:
        months = [m for m in months if m <= report_month]
    return months


def generate_sail8_trend_separator() -> dict:
    """A blank Annexure separator page, right before the content page --
    same shape as page_major_unit_records.generate_major_unit_separator."""
    return {
        "type": "sail8_trend_separator",
        "title": "Annexure-4 : SAIL (8 Plants) Production Trend",
        "annexure_label": "Annexure-4",
        "group_label": "SAIL (8 Plants) Production Trend (FY 2007-08 onwards)",
    }


def _direct_or_live(item: str, month: str, data: dict, sail_direct: dict):
    direct = sail_direct.get(item, {}).get(month)
    if direct is not None:
        return direct
    pv = [data.get(item, {}).get(p, {}).get(month) for p in _SAIL_8]
    return sum(v for v in pv if v is not None) if any(v is not None for v in pv) else None


def _finished_steel_value(month: str, data: dict, sail_direct: dict):
    pv = []
    for p in _SAIL_8:
        v = data.get("Finished Steel", {}).get(p, {}).get(month)
        if v is None and p in _FS_ALIAS_PLANTS:
            v = data.get("Saleable Steel", {}).get(p, {}).get(month)
        pv.append(v)
    if all(v is not None for v in pv):
        return sum(pv)
    return sail_direct.get("Finished Steel", {}).get(month)


def _semi_finished_value(month: str, data: dict):
    total, found = 0.0, False
    for p in _FIVE_ISPS:
        v = data.get("Saleable Semis", {}).get(p, {}).get(month)
        if v is not None:
            total += v
            found = True
    asp_sale = data.get("Saleable Steel", {}).get("ASP", {}).get(month)
    asp_fin = data.get("Finished Steel", {}).get("ASP", {}).get(month)
    if asp_sale is not None and asp_fin is not None:
        total += (asp_sale - asp_fin)
        found = True
    return total if found else None


# Verified figures for every closed FY, sourced from SAIL's own published
# PRODUCTION summary (2026-09-25) -- see the module docstring above and
# docs/SAIL8_TREND_DATA_CORRECTIONS.md. FY2025-26's own Semi Finished +
# Finished Steel (2638 + 16952 = 19590) doesn't add up to its own Saleable
# Steel (19177) -- an inconsistency in the source table itself, not a
# transcription error here; kept as published rather than silently
# "corrected" against a formula. Every other year's two components do sum
# to that year's Saleable Steel exactly.
_REFERENCE_VALUES = {
    2007: {"Hot Metal": 15199, "Crude Steel": 13964, "Pig Iron": 441, "Saleable Steel": 13044, "Semi Finished Steel": 2243, "Finished Steel": 10801},
    2008: {"Hot Metal": 14442, "Crude Steel": 13411, "Pig Iron": 267, "Saleable Steel": 12494, "Semi Finished Steel": 2206, "Finished Steel": 10288},
    2009: {"Hot Metal": 14505, "Crude Steel": 13506, "Pig Iron": 323, "Saleable Steel": 12632, "Semi Finished Steel": 2392, "Finished Steel": 10240},
    2010: {"Hot Metal": 14888, "Crude Steel": 13761, "Pig Iron": 261, "Saleable Steel": 12887, "Semi Finished Steel": 2394, "Finished Steel": 10493},
    2011: {"Hot Metal": 14116, "Crude Steel": 13350, "Pig Iron": 106, "Saleable Steel": 12400, "Semi Finished Steel": 2527, "Finished Steel": 9872},
    2012: {"Hot Metal": 14266, "Crude Steel": 13417, "Pig Iron": 214, "Saleable Steel": 12385, "Semi Finished Steel": 2422, "Finished Steel": 9962},
    2013: {"Hot Metal": 14447, "Crude Steel": 13579, "Pig Iron": 223, "Saleable Steel": 12880, "Semi Finished Steel": 2760, "Finished Steel": 10120},
    2014: {"Hot Metal": 15413, "Crude Steel": 13908, "Pig Iron": 634, "Saleable Steel": 12842, "Semi Finished Steel": 3007, "Finished Steel": 9835},
    2015: {"Hot Metal": 15721, "Crude Steel": 14279, "Pig Iron": 642, "Saleable Steel": 12381, "Semi Finished Steel": 3054, "Finished Steel": 9327},
    2016: {"Hot Metal": 15726, "Crude Steel": 14496, "Pig Iron": 495, "Saleable Steel": 13867, "Semi Finished Steel": 3170, "Finished Steel": 10697},
    2017: {"Hot Metal": 15982, "Crude Steel": 15020, "Pig Iron": 270, "Saleable Steel": 14074, "Semi Finished Steel": 2610, "Finished Steel": 11464},
    2018: {"Hot Metal": 17513, "Crude Steel": 16266, "Pig Iron": 480, "Saleable Steel": 15069, "Semi Finished Steel": 3169, "Finished Steel": 11900},
    2019: {"Hot Metal": 17438, "Crude Steel": 16155, "Pig Iron": 570, "Saleable Steel": 15147, "Semi Finished Steel": 2995, "Finished Steel": 12152},
    2020: {"Hot Metal": 16582, "Crude Steel": 15215, "Pig Iron": 584, "Saleable Steel": 14602, "Semi Finished Steel": 3797, "Finished Steel": 10805},
    2021: {"Hot Metal": 18733, "Crude Steel": 17366, "Pig Iron": 564, "Saleable Steel": 16896, "Semi Finished Steel": 3171, "Finished Steel": 13724},
    2022: {"Hot Metal": 19409, "Crude Steel": 18291, "Pig Iron": 368, "Saleable Steel": 17246, "Semi Finished Steel": 2277, "Finished Steel": 14969},
    2023: {"Hot Metal": 20496, "Crude Steel": 19240, "Pig Iron": 426, "Saleable Steel": 18437, "Semi Finished Steel": 2686, "Finished Steel": 15751},
    2024: {"Hot Metal": 20306, "Crude Steel": 19174, "Pig Iron": 410, "Saleable Steel": 17940, "Semi Finished Steel": 2534, "Finished Steel": 15406},
    2025: {"Hot Metal": 20483, "Crude Steel": 19434, "Pig Iron": 301, "Saleable Steel": 19177, "Semi Finished Steel": 2638, "Finished Steel": 16952},
}


_ROW_DEFS = [
    ("Hot Metal", False, lambda m, data, sd: _direct_or_live("Hot Metal", m, data, sd)),
    ("Crude Steel", False, lambda m, data, sd: _direct_or_live("Total Crude Steel", m, data, sd)),
    ("Pig Iron", False, lambda m, data, sd: _direct_or_live("Pig Iron", m, data, sd)),
    ("Saleable Steel", False, lambda m, data, sd: _direct_or_live("Saleable Steel", m, data, sd)),
    ("Semi Finished Steel", True, lambda m, data, sd: _semi_finished_value(m, data)),
    ("Finished Steel", True, lambda m, data, sd: _finished_steel_value(m, data, sd)),
]


def _fmt(v):
    return "—" if v is None else f"{round(v):,}"


def _fy_value(fn, months, data, sail_direct):
    vals = [fn(m, data, sail_direct) for m in months]
    nz = [v for v in vals if v is not None]
    return sum(nz) if nz else None


def _build_table(fy_list: list, report_month: str, cur_fy: int, data: dict, sail_direct: dict) -> dict:
    years = [_year_label(fy, report_month, cur_fy) for fy in fy_list]
    months_by_fy = [_months_for_fy(fy, report_month, cur_fy) for fy in fy_list]
    rows = []
    for label, indent, fn in _ROW_DEFS:
        values = [
            _REFERENCE_VALUES[fy][label] if fy in _REFERENCE_VALUES else _fy_value(fn, months, data, sail_direct)
            for fy, months in zip(fy_list, months_by_fy)
        ]
        rows.append({"label": label, "indent": indent, "values": [_fmt(v) for v in values]})
    return {"years": years, "rows": rows}


def generate_sail8_trend_annexure(report_month: str) -> dict:
    cur_fy = _fy_of(report_month)
    bottom_fys = list(range(_BOTTOM_FY_START, _BOTTOM_FY_END + 1))
    top_fy_start = _BOTTOM_FY_END + 1
    top_fys = list(range(top_fy_start, max(cur_fy, top_fy_start) + 1))

    item_names = ["Hot Metal", "Total Crude Steel", "Pig Iron", "Saleable Steel",
                  "Finished Steel", "Saleable Semis"]
    direct_items = ["Hot Metal", "Total Crude Steel", "Pig Iron", "Saleable Steel", "Finished Steel"]

    conn = db.connect()
    cur = conn.cursor()
    ph_i = ",".join("?" for _ in item_names)
    ph_p = ",".join("?" for _ in _SAIL_8)
    cur.execute(
        f"SELECT plant_name, item_name, report_month, month_actual FROM production_table "
        f"WHERE item_name IN ({ph_i}) AND plant_name IN ({ph_p}) AND report_month <= ?",
        item_names + _SAIL_8 + [report_month],
    )
    data = {}
    for plant, item, rm, val in cur.fetchall():
        if val is None:
            continue
        data.setdefault(item, {}).setdefault(plant, {})[rm] = val

    ph_d = ",".join("?" for _ in direct_items)
    cur.execute(
        f"SELECT item_name, report_month, month_actual FROM production_table "
        f"WHERE item_name IN ({ph_d}) AND plant_name='SAIL' AND report_month <= ?",
        direct_items + [report_month],
    )
    sail_direct = {}
    for item, rm, val in cur.fetchall():
        if val is not None:
            sail_direct.setdefault(item, {})[rm] = val
    conn.close()

    return {
        "type": "sail8_trend_annexure",
        "title": "SAIL (8 Plants) — Production Trend",
        "unit": "'000 T",
        "top_table": _build_table(top_fys, report_month, cur_fy, data, sail_direct),
        "bottom_table": _build_table(bottom_fys, report_month, cur_fy, data, sail_direct),
    }
