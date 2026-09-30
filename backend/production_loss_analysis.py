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

Tonnage is capacity-based, not a plant-wide daily rate: each unit has a
share of its stage's capacity, an outage takes that unit's capacity out
for the hours it was actually down, and only the part the month's
headroom above target can't absorb is a loss (spare units - the standby
converter, the other reheating furnaces - absorb the rest). The explained
loss never exceeds the actual shortfall. See compute_loss_for_item. (The
old approach - any unit down = the whole plant's output lost that day, at
actual / non-affected days - produced losses many times the month's output.)

Each CR event also carries its ABP schedule slot (the free-text `period`
column, parsed by parse_abp_period) and two flags — `abp_planned_here`
(the ABP planned this CR for the month under analysis) and
`executed_this_month`. A CR planned for the month but not executed then is
surfaced in the events list as context (it doesn't move the loss numbers —
if anything the un-taken downtime lifts actual above plan, showing up as a
negative residual).
"""

import re
from datetime import date, datetime, timedelta
from calendar import monthrange
from typing import Optional, List, Dict, Any, Callable, Tuple

_MONTH_ABBR_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "july": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

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


def parse_abp_period(text: Optional[str]) -> List[str]:
    """The Capital Repair `period` column is a free-text ABP schedule slot:
    "Aug'26", "Sep-Oct'26", "July'26/Nov'26", "Apr'26, Jan'27". Return the
    sorted 'YYYY-MM' months it names — used to flag a CR the ABP planned for
    the month under analysis that wasn't actually executed then."""
    if not text:
        return []
    months: set = set()
    for clause in re.split(r"[,/]", text):
        yr = re.search(r"(\d{2})(?!\d)", clause)
        if not yr:
            continue
        year = 2000 + int(yr.group(1))
        nums = [_MONTH_ABBR_NUM[w.lower()] for w in re.findall(r"[A-Za-z]+", clause)
                if w.lower() in _MONTH_ABBR_NUM]
        if not nums:
            continue
        head = clause.split("'")[0]
        if len(nums) >= 2 and "-" in head:  # a "May-Jun'26" style range
            a, b = nums[0], nums[-1]
            m, y = a, (year - 1 if b < a else year)   # "Dec-Jan'27" -> Dec'26, Jan'27
            while True:
                months.add(f"{y:04d}-{m:02d}")
                if m == b:
                    break
                m = m % 12 + 1
                if m == 1:
                    y += 1
        else:
            for n in nums:
                months.add(f"{year:04d}-{n:02d}")
    return sorted(months)


# ---------------------------------------------------------------------------
# Cause classification
# ---------------------------------------------------------------------------

def classify_cause(unit_type: Optional[str], sms_subtag: Optional[str],
                   unit_name: Optional[str] = None) -> str:
    """'BF'|'CONVERTER'|'CASTER'|'MILL'|'OTHER'. 'OTHER' covers a specific SMS
    unit with no Converter/Caster sub-tag, Coke/Sinter/General rows, and
    unclassified (unit_type is None) rows — none of these attribute to
    HM/CS/FS under the stated causal model, but they're still surfaced in the
    events list. A whole-shop event (unit_name == 'Shop') for BF or SMS DOES
    attribute: BF Shop -> BF; SMS Shop -> CONVERTER (the governing upstream
    stage — the whole shop being down stops crude steel there)."""
    is_shop = (unit_name or "").strip().lower() == "shop"
    if unit_type == "BF":
        return "BF"
    if unit_type == "SMS":
        if sms_subtag == "CONVERTER":
            return "CONVERTER"
        if sms_subtag == "CASTER":
            return "CASTER"
        return "CONVERTER" if is_shop else "OTHER"
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
# Capacity model
# ---------------------------------------------------------------------------

# Converters are run N-installed / M-normally-blowing (SAIL's BOF shops run
# "2 out of 3", the third being relined or on standby), so one converter
# down eats the standby first and costs nothing. Casters are assumed to have
# no standby. These are defaults for every SMS shop - no converter/caster
# counts are stored anywhere.
CONVERTER_POOL = (3, 2)   # (installed, normally operating)
CASTER_POOL = (3, 3)

# Which production stage (and so which capacity) each item draws on, and
# which stage a cause class takes capacity out of.
ITEM_STAGE = {"HM": "BF", "CS": "SMS", "FS": "MILL"}
CAUSE_STAGE = {"BF": "BF", "CONVERTER": "SMS", "CASTER": "SMS", "MILL": "MILL"}

_TEXT_HOURS = re.compile(r"(?<![\d:.])(\d+(?:\.\d+)?)\s*(?:hrs?|hours?)\b", re.IGNORECASE)
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
_CR_IN_BD = re.compile(r"capital\s+repair|relining|\bC\.?R\b", re.IGNORECASE)


def _norm(s: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


# Unit names as the best-day records spell them vs the breakdown/CR logs.
MILL_ALIASES = {
    "MERCHANTMILL": "MM", "PM": "PLATEMILL", "FINISHEDRAILSRSM": "RSM", "FINISHEDRAILSURM": "URM",
    "HOTSTRIPMILL": "HSM", "WF": "WAP", "BARMILL": "BRM", "NEWPLATEMILL": "NPM",
}
_CONVERTER_WORD = re.compile(r"\b(conv(?:ert[oe]r)?|bof|ld)[-#.:\s]*(?:no\.?\s*)?([A-Z]|\d+)\b", re.IGNORECASE)
_CASTER_WORD = re.compile(r"\b(caster|ccm|ccp|cv|ck|m/c)[-#.:\s]*(?:no\.?\s*)?(\d+|[A-Z])?\b", re.IGNORECASE)
# A breakdown-log row the plant itself calls planned ("Planned S/D w.e.f.
# 0920 hrs") is routine planned maintenance, which the ABP allows for - it
# takes capacity out but isn't a loss vs target. ("unplanned" doesn't match.)
_PLANNED_BD = re.compile(r"\bplanned\b", re.IGNORECASE)
# One reheating furnace / one strand of a mill down: the mill keeps rolling
# on the others, so only that share of it is out. Defaults - furnace/strand
# counts per mill aren't stored anywhere.
MILL_PART_SHARE = (
    (re.compile(r"\bRHF\b|\bRHF\s*[-#]?\s*\d|reheat\w*\s+furnace", re.IGNORECASE), 1 / 3, "one reheating furnace"),
    (re.compile(r"\bstrand\b", re.IGNORECASE), 1 / 2, "one strand"),
)
_INSTEAD_OF = re.compile(r"(\d+)\s*days?\s+instead\s+of\s+(\d+)\s*days?", re.IGNORECASE)
_PLAN_DAYS = re.compile(r"\d+(?:\.\d+)?")


def infer_cr_unit(shop: Optional[str], equipment: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """(unit_type, unit_name, sms_subtag) for a Capital Repair row nobody
    classified, from its free-text shop/equipment - "BFs"/"No-4" -> BF-4,
    "SMS3"/"BOF-1" -> SMS-3 converter, "SMS3"/"CV-1" -> SMS-3 caster,
    "Mills"/"Plate Mill" -> mill. Sinter/coke/RMHP rows stay unclassified."""
    sh, eq = (shop or "").strip(), (equipment or "").strip()
    both = f"{sh} {eq}"
    if re.search(r"\bBF|blast", both, re.IGNORECASE):
        m = re.search(r"(\d+)", eq)
        return ("BF", f"BF-{m.group(1)}" if m else "Shop", None)
    if re.search(r"SMS|BOF|steel\s*melt", sh, re.IGNORECASE):
        m = re.search(r"SMS\s*-?\s*(IV|V|I{1,3}|\d+)", sh, re.IGNORECASE)
        shop_name = f"SMS-{_ROMAN.get(m.group(1).upper(), m.group(1))}" if m else "SMS"
        if not eq or eq.lower() == "shop":
            return ("SMS", "Shop", "CONVERTER")
        if _CASTER_WORD.search(eq):
            return ("SMS", shop_name, "CASTER")
        if _CONVERTER_WORD.search(eq) or re.match(r"conv", eq, re.IGNORECASE):
            return ("SMS", shop_name, "CONVERTER")
        return ("SMS", shop_name, None)
    if re.search(r"mill", sh, re.IGNORECASE) or re.search(r"mill|\b[A-Z]{2,4}M\b", eq):
        return ("MILL", eq or sh, None)
    return (None, None, None)


def sub_unit(kind: str, text: Optional[str]) -> Optional[str]:
    """Which converter/caster of a shop a row is about ("BOF-1", "Conv.#Q",
    "Caster-4", "CV1"), so two overlapping rows about the same one aren't
    counted as two machines down. None when the text doesn't say."""
    rx = _CONVERTER_WORD if kind == "CONVERTER" else _CASTER_WORD if kind == "CASTER" else None
    m = rx.search(text or "") if rx else None
    if not m or not m.group(2):
        return None
    # "CV-1" and "CK-1" are different casters; "Caster-4" / "CCM-4" / "M/c-4"
    # are the same family of name.
    family = m.group(1).upper() if kind == "CASTER" and m.group(1).upper() in ("CV", "CK") else ""
    return family + m.group(2).upper()


def planned_days_of(planned_days, schedule_days_text) -> Optional[float]:
    """planned_days, else the figure in the free-text schedule ("11 days",
    "45*"; "1+10+2*" sums)."""
    if planned_days:
        return float(planned_days)
    t = schedule_days_text or ""
    nums = [float(n) for n in _PLAN_DAYS.findall(t)]
    if not nums:
        return None
    return sum(nums) if "+" in t else nums[0]


def unit_key(unit_type: Optional[str], unit_name: Optional[str], sms_subtag: Optional[str] = None) -> Optional[str]:
    """Breakdown/CR unit -> the capacity-model key: 'BF-4', 'BF-SHOP',
    'SMS-3', 'SMS-SHOP', or a normalised mill name ('PLATEMILL'). Converters
    and casters key on their shop (the pool is shop-level). None for units
    that don't feed HM/CS/FS (Coke, Sinter, General)."""
    name = (unit_name or "").strip()
    if unit_type == "BF":
        if name.lower() == "shop":
            return "BF-SHOP"
        m = re.search(r"(\d+)", name)
        return f"BF-{m.group(1)}" if m else None
    if unit_type == "SMS":
        if name.lower() == "shop":
            return "SMS-SHOP"
        m = re.search(r"(\d+|IV|V|I{1,3})\s*$", name.upper())
        if not m:
            return "SMS"
        g = m.group(1)
        return f"SMS-{_ROMAN.get(g, g)}"
    if unit_type == "MILL":
        key = _norm(name)
        return MILL_ALIASES.get(key, key) or None
    return None


def event_day_hours(start_ts: Optional[str], end_ts: Optional[str], ongoing: bool,
                    override_hours: Optional[float], cause_text: Optional[str],
                    now: datetime) -> Tuple[Dict[str, float], str]:
    """Hours a unit was effectively down on each day of an event, and where
    the figure came from:
      'override' - hours_lost_override (equivalent full-stop hours, which is
                   how a partial/restricted-regime outage is entered)
      'text'     - "3 hrs" in the cause, for date-only rows (a date-only row
                   otherwise reads as whole days)
      'span'     - the start/end timestamps as recorded
    A date-only end means through the end of that day; an ongoing row runs
    to `now`. Explicit hours are spread over the recorded span pro rata."""
    if not start_ts:
        return {}, "span"
    date_only = len(start_ts.strip()) <= 10 and (not end_ts or len(end_ts.strip()) <= 10)
    start = datetime.fromisoformat(start_ts.strip()[:16] if len(start_ts.strip()) > 10 else start_ts.strip()[:10])
    if end_ts:
        e = end_ts.strip()
        end = datetime.fromisoformat(e[:16]) if len(e) > 10 else datetime.fromisoformat(e[:10]) + timedelta(days=1)
    elif ongoing:
        end = now
    else:
        end = datetime.fromisoformat(start_ts.strip()[:10]) + timedelta(days=1)
    span_h = (end - start).total_seconds() / 3600
    if span_h <= 0:
        return {}, "span"

    total_h, source = span_h, "span"
    if override_hours is not None and override_hours >= 0:
        total_h, source = float(override_hours), "override"
    elif date_only:
        m = _TEXT_HOURS.search(cause_text or "")
        if m and 0 < float(m.group(1)) < span_h:
            total_h, source = float(m.group(1)), "text"
    scale = min(1.0, total_h / span_h)

    out: Dict[str, float] = {}
    cur = start
    while cur < end:
        nxt = min(end, datetime.combine(cur.date() + timedelta(days=1), datetime.min.time()))
        out[cur.date().isoformat()] = out.get(cur.date().isoformat(), 0.0) + (nxt - cur).total_seconds() / 3600 * scale
        cur = nxt
    return out, source


class _Stage:
    """One production stage's month: capacity-tonnes out of service, split
    planned (on-schedule CR - already priced into the ABP) vs unplanned
    (CR overrun / breakdown). Units are tracked day by day so overlapping
    rows for the same unit never count it down for more than 24 h a day,
    and pooled converters/casters only lose output once the standby is used."""

    def __init__(self, stage_tpd: float, unit_tpd: Dict[str, float]):
        self.stage_tpd = stage_tpd
        self.unit_tpd = unit_tpd
        # (unit, kind) -> day -> sub-unit -> {"planned": h, "cr": h, "bd": h}
        self.hours: Dict[Tuple[str, str], Dict[str, Dict[str, Dict[str, float]]]] = {}

    def add(self, unit: str, kind: str, day: str, bucket: str, h: float, sub: str = "") -> None:
        """`sub` = which converter/caster of a pooled shop (unknown -> a
        per-row id, i.e. assumed to be a different machine)."""
        d = (self.hours.setdefault((unit, kind), {}).setdefault(day, {})
             .setdefault(sub, {"planned": 0.0, "cr": 0.0, "bd": 0.0}))
        d[bucket] += h

    def capacity(self, unit: str, kind: str) -> Tuple[float, int, float]:
        """(t/day per unit-equivalent, standby unit-equivalents, cap on
        unit-hours per day). A '-SHOP' row takes the whole stage out; a unit
        the caller gave no capacity for gets the stage's average unit (or
        the whole stage when it's the only one)."""
        if unit.endswith("SHOP"):
            return self.stage_tpd, 0, 24
        if unit in self.unit_tpd:
            base = self.unit_tpd[unit]
        elif self.unit_tpd:
            base = sum(self.unit_tpd.values()) / len(self.unit_tpd)
        else:
            base = self.stage_tpd
        if kind == "CONVERTER":
            n, m = CONVERTER_POOL
            return base / m, n - m, 24 * n
        if kind == "CASTER":
            n, m = CASTER_POOL
            return base / m, n - m, 24 * n
        return base, 0, 24

    def tonnes(self) -> Dict[str, float]:
        """Capacity-tonnes lost this month: planned / cr (overrun) / bd."""
        tot = {"planned": 0.0, "cr": 0.0, "bd": 0.0}
        for (unit, kind), days in self.hours.items():
            tpd, standby, cap_h = self.capacity(unit, kind)
            spare_h = standby * 24
            for subs in days.values():
                # One machine is down at most 24 h a day, planned first.
                planned = cr = bd = 0.0
                for b in subs.values():
                    p = min(b["planned"], 24.0)
                    u = min(b["cr"] + b["bd"], 24.0 - p)
                    f = u / (b["cr"] + b["bd"]) if b["cr"] + b["bd"] else 0.0
                    planned, cr, bd = planned + p, cr + b["cr"] * f, bd + b["bd"] * f
                planned = min(planned, cap_h)
                unpl = min(cr + bd, cap_h - planned)
                lost_planned = max(0.0, planned - spare_h)
                lost_unpl = max(0.0, planned + unpl - spare_h) - lost_planned
                if unpl > 0:
                    share_cr = cr / (cr + bd)
                    tot["cr"] += lost_unpl * share_cr * tpd / 24
                    tot["bd"] += lost_unpl * (1 - share_cr) * tpd / 24
                tot["planned"] += lost_planned * tpd / 24
        return tot


def _item_of_cause(cause: str) -> set:
    return {item for item, causes in RELEVANT_CAUSES.items() if cause in causes}


def _collect(stages: Dict[str, _Stage], month: str, item: str,
             cr_rows: List[Dict[str, Any]], bd_rows: List[Dict[str, Any]],
             today: str, now: datetime) -> Dict[str, Any]:
    """Feed every CR/breakdown row's day-hours in `month` into its stage;
    returns the events list (with per-event hours/tonnes for drill-down)."""
    relevant = RELEVANT_CAUSES[item]
    month_start, month_end = month_bounds(month)
    events, unclassified = [], []
    cr_units_days: Dict[str, set] = {}   # unit -> days a CR had it down (for BD de-dup)
    overrun_days, bd_days = set(), set()

    for row in cr_rows:
        if not row.get("unit_type") or not row.get("unit_name"):
            ut, un, st = infer_cr_unit(row.get("shop"), row.get("equipment"))
            if ut:
                row = {**row, "unit_type": ut, "unit_name": un, "sms_subtag": st, "inferred_unit": True}
        row = {**row, "planned_days": planned_days_of(row.get("planned_days"), row.get("schedule_days"))}
        unit_type = row.get("unit_type")
        if not unit_type or not row.get("unit_name"):
            unclassified.append({"source": "cr", "id": row.get("id"), "shop": row.get("shop"),
                                 "equipment": row.get("equipment"), "activity": row.get("activity")})
            continue
        cause = classify_cause(unit_type, row.get("sms_subtag"), row.get("unit_name"))
        a_start = row.get("actual_start")
        overrun = cr_overrun_interval(a_start, row.get("actual_end"), bool(row.get("actual_ongoing")),
                                      row.get("planned_days"), today)
        planned_days_missing = a_start is not None and row.get("planned_days") is None
        status = "overrun" if overrun else ("ongoing" if row.get("actual_ongoing") else
                 ("on-schedule" if a_start else "not-started"))
        abp_months = parse_abp_period(row.get("abp_period"))
        a_end_eff = row.get("actual_end") or (today if row.get("actual_ongoing") else a_start)
        executed_this_month = bool(a_start and a_end_eff and _clip(a_start, a_end_eff, month_start, month_end))
        ev = {
            "source": "cr", "id": row.get("id"), "cause": cause, "cause_relevant": cause in relevant,
            "unit_name": row.get("unit_name"), "sms_subtag": row.get("sms_subtag"),
            "activity": row.get("activity"),
            "actual_start": a_start, "actual_end": row.get("actual_end"),
            "actual_ongoing": bool(row.get("actual_ongoing")), "planned_days": row.get("planned_days"),
            "status": status, "planned_days_missing": planned_days_missing,
            "equipment": row.get("equipment"), "inferred_unit": bool(row.get("inferred_unit")),
            "abp_period": row.get("abp_period"), "abp_planned_here": month in abp_months,
            "executed_this_month": executed_this_month,
        }
        key = unit_key(unit_type, row.get("unit_name"), row.get("sms_subtag"))
        if cause in relevant and key and executed_this_month:
            stage = stages[CAUSE_STAGE[cause]]
            kind = row.get("sms_subtag") if unit_type == "SMS" else ""
            clipped = _clip(a_start, a_end_eff, month_start, month_end)
            sub = sub_unit(kind or "", row.get("equipment")) or f"cr{row.get('id')}"
            for d in _date_range(*clipped):
                in_overrun = overrun is not None and overrun[0] <= d <= overrun[1]
                stage.add(key, kind or "", d, "cr" if in_overrun else "planned", 24.0, sub)
                cr_units_days.setdefault(key, set()).add(d)
                if in_overrun:
                    overrun_days.add(d)
            if overrun:
                c = _clip(overrun[0], overrun[1], month_start, month_end)
                if c:
                    ev["overrun_days_this_month"] = len(_date_range(*c))
        events.append(ev)

    for row in bd_rows:
        unit_type = row.get("unit_type")
        if not unit_type or not row.get("unit_name"):
            unclassified.append({"source": "bd", "id": row.get("id"), "cause_text": row.get("cause")})
            continue
        cause = classify_cause(unit_type, row.get("sms_subtag"), row.get("unit_name"))
        ev = {
            "source": "bd", "id": row.get("id"), "cause": cause,
            "unit_name": row.get("unit_name"), "sms_subtag": row.get("sms_subtag"),
            "cause_text": row.get("cause"),
            "start_ts": row.get("start_ts"), "end_ts": row.get("end_ts"),
            "is_ongoing": bool(row.get("is_ongoing")),
        }
        key = unit_key(unit_type, row.get("unit_name"), row.get("sms_subtag"))
        if cause in relevant and key:
            day_h, source = event_day_hours(row.get("start_ts"), row.get("end_ts"), bool(row.get("is_ongoing")),
                                            row.get("hours_lost_override"), row.get("cause"), now)
            day_h = {d: h for d, h in day_h.items() if month_start <= d <= month_end and h > 0}
            if day_h:
                ev["days_this_month"] = len(day_h)
                ev["hours_this_month"] = round(sum(day_h.values()), 1)
                ev["hours_source"] = source
                start_dt = (row.get("start_ts") or "").strip()
                end_dt = (row.get("end_ts") or "").strip()
                if key.endswith("SHOP") and source == "span" and len(start_dt) <= 10 and len(end_dt) <= 10:
                    # "All BFs impacted due to wet raw material" over whole
                    # days: a shop-wide slowdown, not a shop-wide stop - with
                    # no hours given there's no honest tonnage to put on it.
                    ev["unquantified"] = True
                elif cr_units_days.get(key, set()) & set(day_h) and _CR_IN_BD.search(row.get("cause") or ""):
                    ev["duplicate_of_cr"] = True     # the CR itself, also logged as a breakdown
                else:
                    stage = stages[CAUSE_STAGE[cause]]
                    kind = row.get("sms_subtag") if unit_type == "SMS" else ""
                    sub = sub_unit(kind or "", row.get("cause")) or f"bd{row.get('id')}"
                    cause_txt = row.get("cause") or ""
                    share = 1.0
                    if unit_type == "MILL":
                        for rx, frac, what in MILL_PART_SHARE:
                            if rx.search(cause_txt):
                                share, ev["partial"] = frac, what
                                break
                    is_planned = bool(_PLANNED_BD.search(cause_txt))
                    if is_planned:
                        ev["planned_shutdown"] = True
                    # "Extended Capital Repair 17 days instead of 11 days in
                    # ABP": the first 11 days were planned, only 6 are loss.
                    m = _INSTEAD_OF.search(row.get("cause") or "")
                    planned_left = float(m.group(2)) * 24 if m and float(m.group(1)) > float(m.group(2)) else 0.0
                    if m and planned_left:
                        ev["planned_days_in_text"] = int(m.group(2))
                    all_h, _ = event_day_hours(row.get("start_ts"), row.get("end_ts"), bool(row.get("is_ongoing")),
                                               row.get("hours_lost_override"), row.get("cause"), now)
                    for d in sorted(all_h):
                        h = all_h[d] * share
                        if is_planned:
                            if month_start <= d <= month_end:
                                stage.add(key, kind or "", d, "planned", h, sub)
                            continue
                        p = min(h, planned_left)
                        planned_left -= p
                        if month_start <= d <= month_end:
                            if p:
                                stage.add(key, kind or "", d, "planned", p, sub)
                            if h - p > 0:
                                stage.add(key, kind or "", d, "cr" if m else "bd", h - p, sub)
                                (overrun_days if m else bd_days).add(d)
                    tpd, _standby, _cap = stage.capacity(key, kind or "")
                    ev["unit_capacity_tpd"] = round(tpd, 1)
                    ev["capacity_out_t"] = round(tpd * share * ev["hours_this_month"] / 24, 1)
        events.append(ev)

    return {"events": events, "unclassified": unclassified,
            "overrun_days": len(overrun_days), "breakdown_days": len(bd_days - overrun_days)}


def _shortfall_vs_capacity(target: float, capacity: float) -> float:
    return max(0.0, target - capacity)


def compute_loss_for_item(plant: str, item: str, month: str,
                          cr_rows: List[Dict[str, Any]], bd_rows: List[Dict[str, Any]],
                          today: str, plan: Optional[float], actual: Optional[float],
                          capacity: Optional[Dict[str, Any]] = None,
                          hm_plan: Optional[float] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Loss vs target, not vs a naive daily rate.

    capacity = {"BF": {"stage_tpd": K, "units": {"BF-4": t/day, ...}},
                "SMS": {...}, "MILL": {...}}  (see api_production_loss.py)

    For the month (spare capacity on other days can make up an outage):
      capacity        K x days, less capacity-tonnes out on planned CR
      need            the ABP target
      lost            capacity-tonnes out on CR overrun + breakdowns
      loss            = max(0, need - (capacity - lost)) - max(0, need - capacity)
    i.e. only the part of the outage the plant's headroom above target
    couldn't absorb. For Crude Steel the SMS and the BFs (via hot metal,
    at the month's CS/HM ratio) both constrain it; the loss is split between
    them by what each alone would have cost. The explained loss is then
    capped at the actual shortfall - a breakdown can't explain more than
    was actually lost, and nothing when the target was met."""
    now = now or datetime.combine(_parse(today), datetime.now().time())
    y, m = int(month[0:4]), int(month[5:7])
    days_in_month = monthrange(y, m)[1]
    capacity = capacity or {}

    stages = {st: _Stage(float((capacity.get(st) or {}).get("stage_tpd") or 0.0),
                         dict((capacity.get(st) or {}).get("units") or {}))
              for st in ("BF", "SMS", "MILL")}
    col = _collect(stages, month, item, cr_rows, bd_rows, today, now)

    out = {
        "month": month, "plan": plan, "actual": actual,
        "cr_overrun_days": col["overrun_days"], "breakdown_days": col["breakdown_days"],
        "cr_overrun_loss_t": None, "breakdown_loss_t": None, "residual_t": None,
        "rate_basis": "capacity", "capacity": None,
        "events": col["events"], "unclassified_events": col["unclassified"],
    }
    main = ITEM_STAGE[item]
    if plan is None or not stages[main].stage_tpd:
        out["rate_basis"] = "unavailable"
        return out

    def stage_month(st):
        s = stages[st]
        t = s.tonnes()
        return s.stage_tpd * days_in_month - t["planned"], t["cr"], t["bd"]

    need = plan
    cap_main, cr_main, bd_main = stage_month(main)

    if item == "CS" and stages["BF"].stage_tpd and hm_plan:
        ratio = plan / hm_plan                      # CS per t of HM this month
        cap_bf, cr_bf, bd_bf = stage_month("BF")

        def possible(bf_out, sms_out):
            return min((cap_bf - bf_out) * ratio, cap_main - sms_out)
        base = _shortfall_vs_capacity(need, possible(0, 0))
        total = _shortfall_vs_capacity(need, possible(cr_bf + bd_bf, cr_main + bd_main)) - base
        l_bf = _shortfall_vs_capacity(need, possible(cr_bf + bd_bf, 0)) - base
        l_sms = _shortfall_vs_capacity(need, possible(0, cr_main + bd_main)) - base
        w = l_bf + l_sms
        parts = []
        if w > 0:
            parts = [(total * l_bf / w, cr_bf, bd_bf), (total * l_sms / w, cr_main, bd_main)]
        lost_gross = (cr_bf + bd_bf) * ratio + cr_main + bd_main
        headroom = possible(0, 0) - need
    else:
        total = (_shortfall_vs_capacity(need, cap_main - cr_main - bd_main)
                 - _shortfall_vs_capacity(need, cap_main))
        parts = [(total, cr_main, bd_main)]
        lost_gross = cr_main + bd_main
        headroom = cap_main - need

    cr_loss = sum(t * cr / (cr + bd) for t, cr, bd in parts if cr + bd > 0)
    bd_loss = sum(t * bd / (cr + bd) for t, cr, bd in parts if cr + bd > 0)

    capped = False
    if actual is not None:
        shortfall = max(0.0, plan - actual)
        if cr_loss + bd_loss > shortfall:
            f = shortfall / (cr_loss + bd_loss)
            cr_loss, bd_loss, capped = cr_loss * f, bd_loss * f, True
        out["residual_t"] = round(plan - actual - cr_loss - bd_loss, 2)

    out["cr_overrun_loss_t"] = round(cr_loss, 2)
    out["breakdown_loss_t"] = round(bd_loss, 2)
    out["capacity"] = {
        "stage_tpd": round(stages[main].stage_tpd, 1),
        "target_tpd": round(need / days_in_month, 1),
        "headroom_t": round(headroom, 1),
        "capacity_out_t": round(lost_gross, 1),
        "absorbed_t": round(max(0.0, lost_gross - total), 1),
        "capped_by_shortfall": capped,
    }
    return out


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
                 fetch_month_data: Callable[[str, str], Dict[str, Any]],
                 today: Optional[str] = None) -> Dict[str, Any]:
    """period_{a,b} =
      {'kind': 'month', 'value': 'YYYY-MM'}
      {'kind': 'fy',    'value': '2026-27'}
      {'kind': 'range', 'start': 'YYYY-MM', 'end': 'YYYY-MM', 'value': <display label>}
    'range' is the general building block for a quarter, a half-year, or any
    N-month club — the caller (api_production_loss.py) resolves those into
    concrete start/end months; this module only ever sees a plain range.
    fetch_month_data(plant, month) -> {plan, actual, hm_plan, cr_rows,
    bd_rows, capacity} is injected so this module never touches the DB
    itself — see api_production_loss.py for the real implementation."""
    if today is None:
        today = date.today().isoformat()
    if item not in RELEVANT_CAUSES:
        raise ValueError(f"Unknown item: {item!r} (expected HM/CS/FS)")

    def _series(period: Dict[str, str]) -> Dict[str, Any]:
        months = _months_for_period(period)
        monthly = []
        for m in months:
            d = fetch_month_data(plant, m)
            monthly.append(compute_loss_for_item(
                plant, item, m, d["cr_rows"], d["bd_rows"], today, d["plan"], d["actual"],
                capacity=d.get("capacity"), hm_plan=d.get("hm_plan")))
        return {"kind": period["kind"], "label": period["value"], "months": months, "monthly": monthly}

    return {
        "plant": plant, "item": item,
        "series_a": _series(period_a),
        "series_b": _series(period_b) if period_b else None,
    }
