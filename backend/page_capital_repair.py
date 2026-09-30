"""
Capital Repair schedule — pages 36-40 (one per plant), placed right after the
Mill-wise Techno pages (31-35). Source: Report_format/CR.pdf.

Data source: capital_repair_table
  (plant, fy, shop, equipment, activity, schedule_days, period, actual, sort_order)

Plan fields are the yearly-repair-plan text as supplied by the plants (kept
as free text — schedules are things like "7 days/20 days" or "1+10+2*", not
clean numbers). The data-entry page edits them, adds/deletes rows (e.g. a
second CR of the same unit in the FY, as its own row) and reorders them
(sort_order); `actual` is updated as repairs are actually carried out.

BSL's Sinter Plant is modelled as ONE shop ("Sinter Plant") with three
equipment rows (BAND-1/2/3), matching how BSP has two separate shops
(SP-2, SP-3) but BSL has a single sinter plant with three machines.
"""
import re
from datetime import date, timedelta

import db

CR_PAGES = {
    36: "BSP",
    37: "DSP",
    38: "RSP",
    39: "BSL",
    40: "ISP",
}

_PLANT_TITLE = {
    "BSP": "Bhilai Steel Plant",
    "DSP": "Durgapur Steel Plant",
    "RSP": "Rourkela Steel Plant",
    "BSL": "Bokaro Steel Plant",
    "ISP": "IISCO Steel Plant",
}


def fy_from_month(report_month: str) -> str:
    """'2026-06' -> '2026-27' (Indian FY: Apr-Mar)."""
    y, m = int(report_month[:4]), int(report_month[5:7])
    start = y if m >= 4 else y - 1
    return f"{start}-{(start + 1) % 100:02d}"


def _d_m_yy(iso_date: str) -> str:
    """'2026-06-07' -> '7.6.26' (matches the source PDF's date convention)."""
    y, m, d = iso_date.split("-")
    return f"{int(d)}.{int(m)}.{y[2:]}"


def format_cr_actual(actual_start: str | None, actual_end: str | None, actual_ongoing: bool) -> str:
    """Derive the printed 'Actual' text from structured dates, in the same
    free-text convention the source PDF/plants already use
    ('19.4.26-30.4.26' or '7.6.26-cont..'). Single source of truth going
    forward: the capital_repair_table.actual column is written from this,
    never entered as free text again, so pages 36-40 keep rendering
    unchanged (CapitalRepairTemplate.js reads that column verbatim)."""
    if not actual_start:
        return ""
    if actual_ongoing or not actual_end:
        return f"{_d_m_yy(actual_start)}-cont.."
    return f"{_d_m_yy(actual_start)}-{_d_m_yy(actual_end)}"


def _add_merge_spans(rows: list) -> None:
    """Within one shop section, merge consecutive rows' common cells - a
    unit with two Capital Repairs planned in the FY is entered as two rows,
    printed with its Equipment (and Activity, when also the same) cell
    spanning both. Hierarchical: Activity only merges within an Equipment
    run. Sets row["equipment_span"] / row["activity_span"]: n = print the
    cell with rowspan n, 0 = covered by a cell above (skip it)."""
    i = 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1]["equipment"] == rows[i]["equipment"]:
            j += 1
        for k in range(i, j + 1):
            rows[k]["equipment_span"] = (j - i + 1) if k == i else 0
        a = i
        while a <= j:
            b = a
            while b + 1 <= j and rows[b + 1]["activity"] == rows[a]["activity"]:
                b += 1
            for k in range(a, b + 1):
                rows[k]["activity_span"] = (b - a + 1) if k == a else 0
            a = b + 1
        i = j + 1


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_PERIOD_TOKEN = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(?:'\s*(\d{2}))?",
                           re.IGNORECASE)
_ACTUAL_TEXT = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{2})\s*-\s*(?:(\d{1,2})\.(\d{1,2})\.(\d{2})|cont)",
                          re.IGNORECASE)


def _period_months(period: str):
    """Free-text Period -> (first, last) 'YYYY-MM', or None when it names
    no month ("Aligned with BF Capital Repair."). Handles "Jun'26",
    "May-Jun'26", "Apr+May'26", "Nov'26-Mar'27", "July'26/Nov'26",
    "26th April to 5th May'26": a month without its own year takes the
    year of the next month after it, one year earlier if it's a later
    calendar month (a range across the year end)."""
    toks = [(_MONTHS[m.group(1).lower()], m.group(2)) for m in _PERIOD_TOKEN.finditer(period or "")]
    if not toks:
        return None
    out, next_y, next_m = [], None, None
    for mon, yy in reversed(toks):
        if yy:
            y = 2000 + int(yy)
        elif next_y is not None:
            y = next_y - 1 if mon > next_m else next_y
        else:
            return None                      # no year anywhere to anchor it
        out.append(f"{y}-{mon:02d}")
        next_y, next_m = y, mon
    return min(out), max(out)


def _actual_dates(actual_start, actual_end, actual_ongoing, actual_text):
    """(start, end) ISO dates, end None = ongoing - from the structured
    columns, else parsed from older free-text rows ("15.4.26-14.5.26",
    "29.6.26-contd."). None when there's nothing parseable."""
    if actual_start:
        return actual_start, (None if actual_ongoing else actual_end)
    m = _ACTUAL_TEXT.match(actual_text or "")
    if not m:
        return None
    d, mo, y = m.group(1, 2, 3)
    start = f"20{y}-{int(mo):02d}-{int(d):02d}"
    end = f"20{m.group(6)}-{int(m.group(5)):02d}-{int(m.group(4)):02d}" if m.group(4) else None
    return start, end


def _actual_cell(report_month, period, actual_start, actual_end, actual_ongoing, actual_text):
    """The Actual cell as of report_month ('YYYY-MM'): (text, status).

    Only work that had started by the end of the report month is shown -
    if it runs past that month (or is still ongoing) it prints as
    "d.m.yy-cont..". Otherwise, relative to the Period: starting after the
    report month -> "Scheduled"; started by the report month (including a
    Period still running, e.g. "Aug-Sep'26" on the August report) but not
    executed -> "Deferred", per direct instruction 2026-09-26; no month in
    the Period -> blank."""
    if not report_month:
        return actual_text or "", ("actual" if actual_text else "")
    dates = _actual_dates(actual_start, actual_end, actual_ongoing, actual_text)
    if dates:
        start, end = dates
        if start[:7] <= report_month:
            if end is None or end[:7] > report_month:
                return f"{_d_m_yy(start)}-cont..", "actual"
            return f"{_d_m_yy(start)}-{_d_m_yy(end)}", "actual"
        # started after the report month: not yet an actual as of this report
    elif (actual_text or "").strip():
        return actual_text, "actual"         # unparseable free text - show as entered
    span = _period_months(period)
    if span:
        first, _last = span
        if report_month < first:
            return "Scheduled", "scheduled"
        return "Deferred", "deferred"
    return "", ""


def generate_capital_repair(plant: str, fy: str = "2026-27", report_month: str | None = None) -> dict:
    """report_month ('YYYY-MM'): the report being generated - the Actual
    column is shown as of that month (see _actual_cell). Without it the
    stored Actual text is shown as-is."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, shop, equipment, activity, schedule_days, period, actual,
                   actual_start, actual_end, actual_ongoing
            FROM capital_repair_table
            WHERE plant=? AND fy=?
            ORDER BY sort_order ASC, id ASC
        """, (plant, fy))
        rows = cur.fetchall()

        # Sections are runs of CONSECUTIVE rows sharing a shop, in the
        # user's saved order (the data-entry page can reorder rows by drag
        # and drop) - a shop that reappears later starts a new section
        # rather than pulling its rows back up out of order.
        sections = []
        for (rid, shop, equipment, activity, schedule_days, period, actual,
             a_start, a_end, a_ongoing) in rows:
            text, status = _actual_cell(report_month, period, a_start, a_end, a_ongoing, actual)
            row = {
                "id": rid,
                "equipment": equipment or "",
                "activity": activity or "",
                "schedule_days": schedule_days or "",
                "period": period or "",
                "actual": text,
                "actual_status": status,
            }
            if not sections or sections[-1]["shop"] != shop:
                sections.append({"shop": shop, "rows": []})
            sections[-1]["rows"].append(row)
        for sec in sections:
            _add_merge_spans(sec["rows"])

        return {
            "title": f"Major Repair / Capital Repair Plan of SAIL {fy}",
            "subtitle": _PLANT_TITLE.get(plant, plant),
            "plant": plant,
            "fy": fy,
            "sections": sections,
        }
    finally:
        conn.close()


_FY_MONTH_ORDER = ["04", "05", "06", "07", "08", "09", "10", "11", "12", "01", "02", "03"]
_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fy_months(fy: str) -> list[str]:
    """'2026-27' -> ['2026-04', ..., '2026-12', '2027-01', '2027-02', '2027-03']."""
    start = int(fy[:4])
    end = start + 1
    return [f"{start}-{m}" for m in _FY_MONTH_ORDER[:9]] + [f"{end}-{m}" for m in _FY_MONTH_ORDER[9:]]


def _month_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{_MONTH_ABBR[int(m) - 1]}'{y[2:]}"


def _plan_days_text(schedule_days) -> str:
    """Free-text schedule ("9 days", "45*", "7 days/20 days") -> printable,
    adding "days" when the plant gave a bare number ("10" -> "10 days")."""
    s = (schedule_days or "").strip()
    if s and "day" not in s.lower() and re.match(r"^[\d.+*/\s-]+$", s):
        return f"{s} days"
    return s


def _plan_days_number(schedule_days):
    """Scheduled days as a number for sizing the Plan bar: "9 days" -> 9,
    "45*" -> 45, "1+10+2*" -> 13, "7 days/20 days" -> 7 (first figure).
    None when there's no figure (the bar then fills the whole Period)."""
    s = schedule_days or ""
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", s)]
    if not nums:
        return None
    n = round(sum(nums) if "+" in s else nums[0])
    return n if n > 0 else None


def _month_end(ym: str) -> date:
    y, m = int(ym[:4]), int(ym[5:7])
    return (date(y, m, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def _month_segments(start: date, last: date) -> dict:
    """Inclusive date range -> {'YYYY-MM': (from, to, days)}, from/to being
    the fraction of that month the range covers (0..1), for drawing a bar
    to scale: 7.6.26-7.8.26 -> {'2026-06': (0.2, 1.0, 24),
    '2026-07': (0.0, 1.0, 31), '2026-08': (0.0, 0.226, 7)}."""
    out = {}
    d = start
    while d <= last:
        m_end = _month_end(d.strftime("%Y-%m"))
        seg_end = min(last, m_end)
        dim = m_end.day
        out[d.strftime("%Y-%m")] = ((d.day - 1) / dim, seg_end.day / dim, (seg_end - d).days + 1)
        d = seg_end + timedelta(days=1)
    return out


def _plan_range(first: str, last: str, days):
    """Where the Plan bar goes: the Period gives only months, so `days`
    scheduled days are centred in it (Sep'26 + 9 days -> 11.9-19.9;
    May-Jun'26 + 45 days -> 9.5-22.6). No/too many days -> whole Period."""
    p_start, p_end = date.fromisoformat(first + "-01"), _month_end(last)
    total = (p_end - p_start).days + 1
    if not days or days >= total:
        return p_start, p_end
    start = p_start + timedelta(days=(total - days) // 2)
    return start, start + timedelta(days=days - 1)


def generate_capital_repair_calendar(plant: str, fy: str) -> dict:
    """One row per unit (shop/equipment), one column per FY month (Apr-Mar):
    which months it was Planned (from the free-text Period) vs actually
    under repair (from the structured/parsed Actual dates), for a Gantt-
    style plan-vs-actual calendar. A unit with more than one Capital Repair
    row in the FY (e.g. two separate CRs) has its plan/actual spans merged
    into that one row — a Gantt row can show more than one bar.

    Each month cell also carries its day counts: plan_days = the scheduled
    days, printed in the first month of the Period (a multi-month Period
    gives no per-month split); actual_days = days actually under repair in
    that month (an ongoing repair counts up to today). plan_bars /
    actual_bars = [[from, to, tooltip], ...] - from/to are fractions of the
    month for drawing the bars to scale: actual from the real dates, plan
    from the scheduled days centred in the Period (see _plan_range).
    Each repair (DB row) is "done", "ongoing", "deferred" (not started
    though its planned Period began in an earlier month - as on the
    monthly report, where a Period started by the report month and not
    executed prints "Deferred") or "pending" (planned for this month or
    later). summary counts repairs by state; a row's status is its most
    pressing one: ongoing > deferred > done > "" (nothing started yet)."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT shop, equipment, activity, period, actual,
                   actual_start, actual_end, actual_ongoing, schedule_days
            FROM capital_repair_table
            WHERE plant=? AND fy=?
            ORDER BY sort_order ASC, id ASC
        """, (plant, fy))
        rows = cur.fetchall()
    finally:
        conn.close()

    months = _fy_months(fy)
    today = date.today()

    units = {}       # (shop, equipment) -> {"activities": set, "plan": set, "actual": set}
    unit_order = []
    shop_order = []
    for shop, equipment, activity, period, actual, a_start, a_end, a_ongoing, schedule_days in rows:
        shop = shop or ""
        equipment = equipment or ""
        key = (shop, equipment)
        if key not in units:
            units[key] = {"activities": [], "plan": set(), "actual": set(),
                          "plan_days": {}, "actual_days": {},
                          "plan_bars": {}, "actual_bars": {}, "states": []}
            unit_order.append(key)
            if shop not in shop_order:
                shop_order.append(shop)
        entry = units[key]
        if activity and activity not in entry["activities"]:
            entry["activities"].append(activity)

        span = _period_months(period)
        if span:
            first, last = span
            entry["plan"].update(m for m in months if first <= m <= last)
            p_start, p_end = _plan_range(first, last, _plan_days_number(schedule_days))
            tip = "Plan: " + " · ".join(x for x in ((period or "").strip(), _plan_days_text(schedule_days)) if x)
            for m, (f, t, _n) in _month_segments(p_start, p_end).items():
                entry["plan_bars"].setdefault(m, []).append([round(f, 4), round(t, 4), tip])
        plan_days = _plan_days_text(schedule_days)
        if span and plan_days:
            entry["plan_days"].setdefault(span[0], []).append(plan_days)

        dates = _actual_dates(a_start, a_end, a_ongoing, actual)
        if dates:
            start, end = dates
            d0 = date.fromisoformat(start)
            d1 = date.fromisoformat(end) if end else max(d0, today)
            total = (d1 - d0).days + 1
            tip = (f"Actual: {_d_m_yy(start)} – {_d_m_yy(end)} ({total} day{'' if total == 1 else 's'})" if end
                   else f"Actual: {_d_m_yy(start)} – in progress ({total} days so far)")
            for m, (f, t, n) in _month_segments(d0, d1).items():
                if m in months:
                    entry["actual"].add(m)
                    entry["actual_days"][m] = entry["actual_days"].get(m, 0) + n
                    entry["actual_bars"].setdefault(m, []).append([round(f, 4), round(t, 4), tip])
            entry["states"].append("done" if end else "ongoing")
        else:
            entry["states"].append("deferred" if span and span[0] < today.strftime("%Y-%m") else "pending")

    sections = []
    for shop in shop_order:
        unit_rows = []
        for key in unit_order:
            s, equipment = key
            if s != shop:
                continue
            entry = units[key]
            states = entry["states"]
            unit_rows.append({
                "unit": equipment,
                "status": next((st for st in ("ongoing", "deferred", "done") if st in states), ""),
                "activity": " / ".join(entry["activities"]),
                "months": [{
                    "plan": m in entry["plan"],
                    "actual": m in entry["actual"],
                    "plan_days": " + ".join(entry["plan_days"].get(m, [])),
                    "actual_days": entry["actual_days"].get(m),
                    "plan_bars": entry["plan_bars"].get(m, []),
                    "actual_bars": entry["actual_bars"].get(m, []),
                } for m in months],
            })
        sections.append({"shop": shop, "rows": unit_rows})

    return {
        "plant": plant,
        "plant_title": _PLANT_TITLE.get(plant, plant),
        "fy": fy,
        "month_labels": [_month_label(m) for m in months],
        "months": months,
        "today": today.isoformat(),
        "summary": {
            "repairs": sum(len(u["states"]) for u in units.values()),
            "done": sum(u["states"].count("done") for u in units.values()),
            "ongoing": sum(u["states"].count("ongoing") for u in units.values()),
            "deferred": sum(u["states"].count("deferred") for u in units.values()),
            "pending": sum(u["states"].count("pending") for u in units.values()),
        },
        "sections": sections,
    }
