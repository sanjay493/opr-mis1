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
