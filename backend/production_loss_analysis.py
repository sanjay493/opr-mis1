"""
Production-loss analysis engine for Hot Metal / Crude Steel / Finished Steel,
driven by Capital Repair (capital_repair_table) and Breakdown (breakdown_table)
events. Pure module — no FastAPI/DB imports; all data is injected by the
caller (see api_production_loss.py) so this stays independently testable.

Methodology (per the plant engineer's own explanation of how the ABP works):

  The ABP monthly plan already accounts for scheduled Capital Repairs, so a
  CR that finishes within its planned `schedule_days` is NOT a cause of
  shortfall vs. plan — it's already priced into the plan number. Only two
  things explain a vs.-plan shortfall:
    1. CR OVERRUN — the portion of a CR's actual duration beyond its planned
       schedule (the plan didn't anticipate the extension).
    2. BREAKDOWNS — wholly unplanned, never reflected in ABP, so the full
       breakdown span counts.
  Whatever gap remains after subtracting both is "residual" (unexplained —
  input shortage, quality, demand, etc.) and is reported as its own bucket,
  never silently absorbed.

Causal model (plant physics, per the engineer): Hot Metal is affected only
by Blast Furnace CR/breakdown. Crude Steel is affected by BF, Converter, or
Caster CR/breakdown, in priority order BF > Converter > Caster (an HM
shortage from a down BF can't be compensated by converter/caster
availability, so when both are down the same day, that day is attributed to
the BF alone — not double-counted). Finished Steel is affected only by
CR/breakdown of the Mills.

Since production_table/production_plan_table are monthly-only (no daily
actuals), tonnage loss is necessarily an approximation: a "self-referencing"
daily rate (that unit's own actual output ÷ its own running days that
month), falling back to the ABP rate only when affected days consume the
entire month.
"""

from datetime import date, timedelta
from calendar import monthrange
from typing import Optional, List, Dict, Any, Callable, Tuple

# Cause classes, in Crude Steel attribution priority (lower number wins).
CAUSE_PRIORITY = {"BF": 0, "CONVERTER": 1, "CASTER": 2, "MILL": 0}

# Which cause classes matter for each production item.
RELEVANT_CAUSES = {
    "HM": {"BF"},
    "CS": {"BF", "CONVERTER", "CASTER"},
    "FS": {"MILL"},
}

ITEM_NAMES = {"HM": "Hot Metal", "CS": "Total Crude Steel", "FS": "Finished Steel"}


# ---------------------------------------------------------------------------
# Date helpers — 'YYYY-MM-DD' strings in, 'YYYY-MM-DD' strings out. All
# interval/overlap math happens here in Python; nothing is compared in SQL.
# ---------------------------------------------------------------------------

def _parse(d: str) -> date:
    return date(int(d[0:4]), int(d[5:7]), int(d[8:10]))


def _iso(d: date) -> str:
    return d.isoformat()


def _add_days(d: str, n: int) -> str:
    return _iso(_parse(d) + timedelta(days=n))


def month_bounds(report_month: str) -> Tuple[str, str]:
    """'2026-06' -> ('2026-06-01', '2026-06-30')."""
    y, m = int(report_month[0:4]), int(report_month[5:7])
    last_day = monthrange(y, m)[1]
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{last_day:02d}"


def _date_range(start: str, end: str) -> List[str]:
    """Inclusive list of 'YYYY-MM-DD' from start to end."""
    if start > end:
        return []
    s, e = _parse(start), _parse(end)
    out, cur = [], s
    while cur <= e:
        out.append(_iso(cur))
        cur += timedelta(days=1)
    return out


def _clip(start: str, end: str, lo: str, hi: str) -> Optional[Tuple[str, str]]:
    """Intersect [start,end] with [lo,hi]; None if they don't overlap."""
    cs, ce = max(start, lo), min(end, hi)
    return (cs, ce) if cs <= ce else None


def _months_in_fy(fy_label: str) -> List[str]:
    """'2026-27' -> ['2026-04', ..., '2027-03'] (Indian FY: Apr-Mar)."""
    start_year = int(fy_label[0:4])
    out = []
    for i in range(12):
        m, y = 4 + i, start_year
        if m > 12:
            m -= 12
            y += 1
        out.append(f"{y:04d}-{m:02d}")
    return out


def _months_in_range(start_month: str, end_month: str) -> List[str]:
    """Inclusive list of 'YYYY-MM' from start_month to end_month — the
    building block for quarters, half-years, or any N-month club the caller
    wants (a quarter/half is just a range with the right start/end)."""
    y1, m1 = int(start_month[0:4]), int(start_month[5:7])
    y2, m2 = int(end_month[0:4]), int(end_month[5:7])
    if (y1, m1) > (y2, m2):
        raise ValueError(f"range start {start_month!r} is after end {end_month!r}")
    out = []
    y, m = y1, m1
    while (y, m) <= (y2, m2):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


# ---------------------------------------------------------------------------
# Cause classification
# ---------------------------------------------------------------------------

def classify_cause(unit_type: Optional[str], sms_subtag: Optional[str]) -> str:
    """'BF'|'CONVERTER'|'CASTER'|'MILL'|'OTHER'. 'OTHER' covers SMS rows with
    no Converter/Caster sub-tag, Coke/Sinter/General rows, and unclassified
    (unit_type is None) rows — none of these attribute to HM/CS/FS under the
    stated causal model, but they're still surfaced in the events list."""
    if unit_type == "BF":
        return "BF"
    if unit_type == "SMS":
        if sms_subtag == "CONVERTER":
            return "CONVERTER"
        if sms_subtag == "CASTER":
            return "CASTER"
        return "OTHER"
    if unit_type == "MILL":
        return "MILL"
    return "OTHER"


# ---------------------------------------------------------------------------
# Capital Repair overrun
# ---------------------------------------------------------------------------

def cr_overrun_interval(actual_start: Optional[str], actual_end: Optional[str],
                         actual_ongoing: bool, planned_days: Optional[float],
                         today: str) -> Optional[Tuple[str, str]]:
    """Days beyond the planned schedule only — None if the row is on-schedule,
    still within its planned days, or missing the data needed to tell
    (actual_start or planned_days absent). `today` bounds an still-ongoing
    CR's "so far" extent; intersecting the result against a specific month's
    bounds (done by the caller) is what actually keeps a later month's
    ongoing progress from leaking into an earlier, already-closed month."""
    if not actual_start or planned_days is None or planned_days <= 0:
        return None
    planned_end = _add_days(actual_start, int(planned_days) - 1)
    effective_end = today if (actual_ongoing or not actual_end) else actual_end
    if effective_end <= planned_end:
        return None
    return (_add_days(planned_end, 1), effective_end)


# ---------------------------------------------------------------------------
# Affected-day computation (day-by-day, priority-deduplicated for CS)
# ---------------------------------------------------------------------------

def affected_days_for_item(item: str, plant: str, month: str,
                            cr_rows: List[Dict[str, Any]], bd_rows: List[Dict[str, Any]],
                            today: str) -> Dict[str, Any]:
    """item in {'HM','CS','FS'}. Returns cr_overrun_days, breakdown_days,
    affected_days (their sum, already deduplicated day-by-day), the full
    events list (including on-schedule/irrelevant rows, for drill-down), and
    unclassified_events (rows with no unit_type — never dropped silently)."""
    relevant = RELEVANT_CAUSES[item]
    month_start, month_end = month_bounds(month)
    days = _date_range(month_start, month_end)
    day_sources: Dict[str, Dict[str, Dict[str, list]]] = {d: {} for d in days}

    events, unclassified = [], []

    for row in cr_rows:
        unit_type = row.get("unit_type")
        if not unit_type or not row.get("unit_name"):
            unclassified.append({"source": "cr", "id": row.get("id"),
                                  "shop": row.get("shop"), "equipment": row.get("equipment"),
                                  "activity": row.get("activity")})
            continue
        cause = classify_cause(unit_type, row.get("sms_subtag"))
        overrun = cr_overrun_interval(row.get("actual_start"), row.get("actual_end"),
                                       bool(row.get("actual_ongoing")), row.get("planned_days"), today)
        # "ongoing" alone doesn't say whether it's still within schedule or
        # simply un-assessable — planned_days is required to tell the two
        # apart, so flag its absence explicitly rather than letting "ongoing"
        # read as a confirmed "on schedule so far".
        planned_days_missing = row.get("actual_start") is not None and row.get("planned_days") is None
        status = "overrun" if overrun else ("ongoing" if row.get("actual_ongoing") else
                 ("on-schedule" if row.get("actual_start") else "not-started"))
        ev = {
            "source": "cr", "id": row.get("id"), "cause": cause,
            "unit_name": row.get("unit_name"), "sms_subtag": row.get("sms_subtag"),
            "activity": row.get("activity"),
            "actual_start": row.get("actual_start"), "actual_end": row.get("actual_end"),
            "actual_ongoing": bool(row.get("actual_ongoing")), "planned_days": row.get("planned_days"),
            "status": status, "planned_days_missing": planned_days_missing,
        }
        if cause in relevant and overrun:
            clipped = _clip(overrun[0], overrun[1], month_start, month_end)
            if clipped:
                ev["overrun_days_this_month"] = len(_date_range(*clipped))
                for d in _date_range(*clipped):
                    day_sources[d].setdefault(cause, {}).setdefault("cr", []).append(row.get("id"))
        events.append(ev)

    for row in bd_rows:
        unit_type = row.get("unit_type")
        if not unit_type or not row.get("unit_name"):
            unclassified.append({"source": "bd", "id": row.get("id"), "cause_text": row.get("cause")})
            continue
        cause = classify_cause(unit_type, row.get("sms_subtag"))
        start_date = (row.get("start_ts") or "")[:10]
        is_ongoing = bool(row.get("is_ongoing"))
        end_date = (row.get("end_ts") or "")[:10] if row.get("end_ts") else (today if is_ongoing else None)
        ev = {
            "source": "bd", "id": row.get("id"), "cause": cause,
            "unit_name": row.get("unit_name"), "sms_subtag": row.get("sms_subtag"),
            "cause_text": row.get("cause"),
            "start_ts": row.get("start_ts"), "end_ts": row.get("end_ts"), "is_ongoing": is_ongoing,
        }
        if cause in relevant and start_date and end_date and end_date >= start_date:
            clipped = _clip(start_date, end_date, month_start, month_end)
            if clipped:
                ev["days_this_month"] = len(_date_range(*clipped))
                for d in _date_range(*clipped):
                    day_sources[d].setdefault(cause, {}).setdefault("bd", []).append(row.get("id"))
        events.append(ev)

    cr_overrun_days = breakdown_days = 0
    for d in days:
        causes_today = day_sources[d]
        if not causes_today:
            continue
        governing = min(causes_today.keys(), key=lambda c: CAUSE_PRIORITY.get(c, 99))
        # If the governing cause has both a breakdown and a CR-overrun active
        # the same day, count it as a breakdown day — a breakdown is a
        # directly-reported unplanned event, CR-overrun is a derived
        # classification, so the more certain cause wins the tie-break.
        if "bd" in causes_today[governing]:
            breakdown_days += 1
        else:
            cr_overrun_days += 1

    return {
        "cr_overrun_days": cr_overrun_days,
        "breakdown_days": breakdown_days,
        "affected_days": cr_overrun_days + breakdown_days,
        "events": events,
        "unclassified_events": unclassified,
    }


# ---------------------------------------------------------------------------
# Rate + loss computation
# ---------------------------------------------------------------------------

def self_referencing_rate(month: str, affected_days: int,
                           actual_value: Optional[float],
                           abp_value: Optional[float]) -> Tuple[Optional[float], str]:
    """rate = actual / (days_in_month - affected_days) ('self'); falls back
    to abp_value / days_in_month ('abp') only when affected days consume the
    whole month (or actual is missing). None/'unavailable' if neither works."""
    y, m = int(month[0:4]), int(month[5:7])
    days_in_month = monthrange(y, m)[1]
    running_days = days_in_month - affected_days
    if running_days > 0 and actual_value is not None:
        return actual_value / running_days, "self"
    if abp_value is not None:
        return abp_value / days_in_month, "abp"
    return None, "unavailable"


def compute_loss_for_item(plant: str, item: str, month: str,
                           cr_rows: List[Dict[str, Any]], bd_rows: List[Dict[str, Any]],
                           today: str, plan: Optional[float], actual: Optional[float]) -> Dict[str, Any]:
    aff = affected_days_for_item(item, plant, month, cr_rows, bd_rows, today)
    rate, basis = self_referencing_rate(month, aff["affected_days"], actual, plan)

    cr_overrun_loss_t = round(rate * aff["cr_overrun_days"], 2) if rate is not None else None
    breakdown_loss_t = round(rate * aff["breakdown_days"], 2) if rate is not None else None

    residual_t = None
    if plan is not None and actual is not None:
        shortfall = plan - actual
        explained = (cr_overrun_loss_t or 0) + (breakdown_loss_t or 0)
        residual_t = round(shortfall - explained, 2)

    return {
        "month": month, "plan": plan, "actual": actual,
        "cr_overrun_days": aff["cr_overrun_days"], "breakdown_days": aff["breakdown_days"],
        "cr_overrun_loss_t": cr_overrun_loss_t, "breakdown_loss_t": breakdown_loss_t,
        "residual_t": residual_t, "rate_basis": basis,
        "events": aff["events"], "unclassified_events": aff["unclassified_events"],
    }


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def _months_for_period(period: Dict[str, str]) -> List[str]:
    if period["kind"] == "month":
        return [period["value"]]
    if period["kind"] == "fy":
        return _months_in_fy(period["value"])
    if period["kind"] == "range":
        return _months_in_range(period["start"], period["end"])
    raise ValueError(f"Unknown period kind: {period['kind']!r}")


def build_report(plant: str, item: str, period_a: Dict[str, str], period_b: Optional[Dict[str, str]],
                  fetch_month_data: Callable[[str, str], Tuple[Optional[float], Optional[float],
                                                                List[Dict[str, Any]], List[Dict[str, Any]]]],
                  today: Optional[str] = None) -> Dict[str, Any]:
    """period_{a,b} =
      {'kind': 'month', 'value': 'YYYY-MM'}
      {'kind': 'fy',    'value': '2026-27'}
      {'kind': 'range', 'start': 'YYYY-MM', 'end': 'YYYY-MM', 'value': <display label>}
    'range' is the general building block for a quarter, a half-year, or any
    N-month club — the caller (api_production_loss.py) resolves those into
    concrete start/end months; this module only ever sees a plain range.
    fetch_month_data(plant, month) -> (plan, actual, cr_rows, bd_rows) is
    injected so this module never touches the DB itself — see
    api_production_loss.py for the real implementation."""
    if today is None:
        today = date.today().isoformat()
    if item not in RELEVANT_CAUSES:
        raise ValueError(f"Unknown item: {item!r} (expected HM/CS/FS)")

    def _series(period: Dict[str, str]) -> Dict[str, Any]:
        months = _months_for_period(period)
        monthly = []
        for m in months:
            plan, actual, cr_rows, bd_rows = fetch_month_data(plant, m)
            monthly.append(compute_loss_for_item(plant, item, m, cr_rows, bd_rows, today, plan, actual))
        return {"kind": period["kind"], "label": period["value"], "months": months, "monthly": monthly}

    return {
        "plant": plant, "item": item,
        "series_a": _series(period_a),
        "series_b": _series(period_b) if period_b else None,
    }
