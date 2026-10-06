"""Shared period math, DB-backed figures, all-time best-ever scanning and
prose/table formatting for the Board Note quarterly production-performance
report generator.

This is a generalization of the already-validated, hardcoded-period logic in
`_update_bn_board_report.py` (kept in the repo as a reference-only scratch
script) off its 2026-27/Q2/H1 constants, into functions parameterized by
`fy_start`/`quarter`/`plant`, plus the per-plant `ITEMS_FOR_PLANT` extension
for `best_ever_bullets` (previously SAIL-only there).
"""

import page4
import page_do_letter as pdl
from constants import FIVE_PLANTS as _5P

# {db_item: page4 item config dict}, giving period_sum/row_values access to
# each item's "five_plants"/"sail_set" aggregation lists.
_ITEMS = {i["db_item"]: i for i in page4.PAGE4_ITEMS}

SMALL_PLANTS = {"ASP", "SSP", "VISL"}

BIG5_PLANTS = _5P  # ["BSP", "DSP", "RSP", "BSL", "ISP"]

# --------------------------------------------------------------------------
# Period math
# --------------------------------------------------------------------------


def fy_months(fy_start: int) -> list:
    """All 12 'YYYY-MM' months of the financial year starting in April
    `fy_start`."""
    return [f"{fy_start}-{m:02d}" for m in range(4, 13)] + [
        f"{fy_start + 1}-{m:02d}" for m in range(1, 4)
    ]


def quarter_months(fy_start: int, quarter: int) -> list:
    """The 3 calendar-month strings ('YYYY-MM') of quarter `quarter`
    (1-4) of the financial year starting in April `fy_start`."""
    return fy_months(fy_start)[(quarter - 1) * 3: quarter * 3]


def long_period_months(fy_start: int, quarter: int):
    """The FY's first 6/9/12 months for quarter 2/3/4 (H-1, 9-months,
    full FY respectively); `None` for quarter 1 (no "long period" exists
    yet)."""
    if quarter == 1:
        return None
    n = quarter * 3
    return fy_months(fy_start)[:n]


def quarter_label(fy_start: int, quarter: int) -> str:
    yy = str(fy_start)[2:]
    zz = str(fy_start + 1)[2:]
    return f"Q-{quarter}’{yy}-{zz}"


def long_period_label(fy_start: int, quarter: int):
    if quarter == 1:
        return None
    yy = str(fy_start)[2:]
    zz = str(fy_start + 1)[2:]
    if quarter == 2:
        return f"H-1’{yy}-{zz}"
    if quarter == 3:
        return f"9M’{yy}-{zz}"
    return f"FY’{yy}-{zz}"


# --------------------------------------------------------------------------
# Per-plant item applicability (for best_ever_bullets)
# --------------------------------------------------------------------------

_BIG5_AND_SAIL_ITEMS = [
    ("Hot Metal", "Hot Metal"),
    ("Crude Steel", "Total Crude Steel"),
    ("Saleable Steel", "Saleable Steel"),
    ("Finished Steel", "Finished Steel"),
]
_SPECIAL2_ITEMS = [
    ("Crude Steel", "Total Crude Steel"),
    ("Saleable Steel", "Saleable Steel"),
    ("Finished Steel", "Finished Steel"),
]
_VISL_ITEMS = [
    ("Saleable Steel", "Saleable Steel"),
    ("Finished Steel", "Finished Steel"),
]

ITEMS_FOR_PLANT = {}
for _p in BIG5_PLANTS + ["SAIL"]:
    ITEMS_FOR_PLANT[_p] = list(_BIG5_AND_SAIL_ITEMS)
for _p in ["ASP", "SSP"]:
    ITEMS_FOR_PLANT[_p] = list(_SPECIAL2_ITEMS)
ITEMS_FOR_PLANT["VISL"] = list(_VISL_ITEMS)


# --------------------------------------------------------------------------
# pick_best
# --------------------------------------------------------------------------


def pick_best(totals: dict, cur_fy: int):
    """Given {fy_start: total}, return (cur_v, best_prev_v, best_prev_fy)
    if the current FY's total is a new all-time record, else None."""
    others = {fy: v for fy, v in totals.items() if fy != cur_fy}
    if cur_fy not in totals or not others:
        return None
    best_fy = max(others, key=others.get)
    if totals[cur_fy] > others[best_fy]:
        return totals[cur_fy], others[best_fy], best_fy
    return None


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------


def fmt_tbl(v, plant: str) -> str:
    if v is None:
        return ""
    if plant in SMALL_PLANTS:
        return f"{v:.3f}"
    return str(round(v))


def fmt_ann(v) -> str:
    return "" if v is None else str(round(v))


def fmt_pct(v) -> str:
    return "" if v is None else str(v)


def fmt_mt(v) -> str:
    if v is None:
        return ""
    return f"{v / 1000.0:.3f}"


def fmt_t(v) -> str:
    if v is None:
        return ""
    return f"{v * 1000.0:,.0f}"


def imp_phrase(v) -> str:
    if v is None:
        return ""
    return f"an improvement of {v}%" if v >= 0 else f"a decline of {abs(v)}%"


def improvement_pct(cur_v, cply_v, higher_is_better: bool):
    """None when either figure is missing or `cply_v` is 0 (nothing to
    divide by) -- a later task's SAIL techno-improvement sentences can
    legitimately have a missing figure and must not crash or guess."""
    if cur_v is None or cply_v is None or cply_v == 0:
        return None
    if higher_is_better:
        return round((cur_v - cply_v) / cply_v * 100)
    return round((cply_v - cur_v) / cply_v * 100)


def fuel_rate_fallback(tgt: dict) -> dict:
    """Return a new dict with "Fuel Rate" filled in as Coke Rate + Nut Coke
    Rate + CDI Rate when it is None and all three components are present
    -- same rule techno_aggregates.py applies to actuals."""
    result = dict(tgt)
    if result.get("Fuel Rate") is None:
        coke, nut, cdi = result.get("Coke Rate"), result.get("Nut Coke Rate"), result.get("CDI Rate")
        if coke is not None and nut is not None and cdi is not None:
            result["Fuel Rate"] = coke + nut + cdi
    return result


# --------------------------------------------------------------------------
# DB-backed figures
# --------------------------------------------------------------------------


def period_sum(cur, table: str, months: list, plant: str, db_item: str):
    cfg = _ITEMS.get(db_item, {})
    fp, ss = cfg.get("five_plants", []), cfg.get("sail_set", [])
    total, found = 0.0, False
    for m in months:
        v = page4._p4_get(cur, table, m, plant, db_item, fp, ss)
        if v is not None:
            total += v
            found = True
    return total if found else None


def conv_sum(cur, months: list):
    total, found = 0.0, False
    for m in months:
        c = pdl._fetch_conversion(cur, m)
        if c is not None:
            total += c
            found = True
    return total if found else None


def _check_add_conv(plant: str, db_item: str, add_conv: bool) -> None:
    """Conversion is only ever added for SAIL's Finished Steel figure -- never
    any other plant, and never any other item, even SAIL's own."""
    if add_conv and not (plant == "SAIL" and db_item == "Finished Steel"):
        raise ValueError(
            f"add_conv=True is only valid for plant='SAIL', db_item='Finished Steel' "
            f"(got plant={plant!r}, db_item={db_item!r})"
        )


def row_values(cur, plant: str, db_item: str, cur_months: list, cply_months: list,
                fy_start: int, add_conv: bool = False):
    """(ann, abp_period, act_period, pct_ful, cply_act, pct_gr) for one
    table row. add_conv: only true for SAIL Finished Steel."""
    _check_add_conv(plant, db_item, add_conv)
    ann = period_sum(cur, "plan", fy_months(fy_start), plant, db_item)
    abp = period_sum(cur, "plan", cur_months, plant, db_item)
    act = period_sum(cur, "act", cur_months, plant, db_item)
    cply = period_sum(cur, "act", cply_months, plant, db_item)
    if add_conv:
        # A missing Conversion figure must blank out the total, not be
        # silently treated as 0 (which would understate SAIL's Finished
        # Steel and skew %Growth) -- consistent with best_ever, which
        # already skips any FY it has no Conversion data for.
        if act is not None:
            cv = conv_sum(cur, cur_months)
            act = act + cv if cv is not None else None
        if cply is not None:
            cvp = conv_sum(cur, cply_months)
            cply = cply + cvp if cvp is not None else None
    pct = round(act / abp * 100) if (act is not None and abp) else None
    gr = round((act - cply) / cply * 100) if (act is not None and cply) else None
    return ann, abp, act, pct, cply, gr


# --------------------------------------------------------------------------
# All-time best-ever
# --------------------------------------------------------------------------


def _fy_start_years(lo, hi):
    return range(lo, hi + 1)


def best_ever(cur, plant: str, db_item: str, period_months_fn, cur_fy_start: int, add_conv: bool = False):
    _check_add_conv(plant, db_item, add_conv)
    totals = {}
    for fy in _fy_start_years(1960, cur_fy_start):
        months = period_months_fn(fy)
        act = period_sum(cur, "act", months, plant, db_item)
        if act is None:
            continue
        if add_conv:
            cv = conv_sum(cur, months)
            if cv is None:
                continue
            act += cv
        totals[fy] = act
    return pick_best(totals, cur_fy_start)


def best_ever_bullets(cur, plant: str, period_months_fn, cur_fy_start: int, style: str) -> list:
    """style: 'q1' -> 'Previous best : X MT in Q-1'YY-ZZ'
              'q2' -> 'Previous best : X MT in Q-2'YY-ZZ'
              'h1' -> 'Prev. best : X MT in Apr-Sep'YY'"""
    bullets = []
    for label, db_item in ITEMS_FOR_PLANT.get(plant, []):
        add_conv = plant == "SAIL" and label == "Finished Steel"
        r = best_ever(cur, plant, db_item, period_months_fn, cur_fy_start, add_conv)
        if not r:
            continue
        cur_v, prev_v, prev_fy = r
        cur_mt = round(cur_v / 1000.0, 3)
        prev_mt = round(prev_v / 1000.0, 3)
        yy = str(prev_fy)[2:]
        if style in ("q1", "q2"):
            zz = str(prev_fy + 1)[2:]
            q = style[1]
            bullets.append(f"{label} production of {cur_mt} MT (Previous best : {prev_mt} MT in Q-{q}'{yy}-{zz})")
        else:
            bullets.append(f"{label} production of {cur_mt} MT (Prev. best : {prev_mt} MT in Apr-Sep'{yy})")
    return bullets
