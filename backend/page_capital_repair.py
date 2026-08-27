"""
Capital Repair schedule — pages 36-40 (one per plant), placed right after the
Mill-wise Techno pages (31-35). Source: Report_format/CR.pdf.

Data source: capital_repair_table
  (plant, fy, shop, equipment, activity, schedule_days, period, actual, sort_order)

All fields except `actual` are the fixed yearly-repair-plan text as supplied
by the plants (kept as free text — schedules are things like "7 days/20 days"
or "1+10+2*", not clean numbers). `actual` is the only field ever edited after
seeding, via the data-entry page, as repairs are actually carried out.

BSL's Sinter Plant is modelled as ONE shop ("Sinter Plant") with three
equipment rows (BAND-1/2/3), matching how BSP has two separate shops
(SP-2, SP-3) but BSL has a single sinter plant with three machines.
"""
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


def generate_capital_repair(plant: str, fy: str = "2026-27") -> dict:
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, shop, equipment, activity, schedule_days, period, actual
            FROM capital_repair_table
            WHERE plant=? AND fy=?
            ORDER BY sort_order ASC, id ASC
        """, (plant, fy))
        rows = cur.fetchall()

        sections, by_shop = [], {}
        for rid, shop, equipment, activity, schedule_days, period, actual in rows:
            row = {
                "id": rid,
                "equipment": equipment or "",
                "activity": activity or "",
                "schedule_days": schedule_days or "",
                "period": period or "",
                "actual": actual or "",
            }
            if shop not in by_shop:
                by_shop[shop] = {"shop": shop, "rows": []}
                sections.append(by_shop[shop])
            by_shop[shop]["rows"].append(row)

        return {
            "title": f"Major Repair / Capital Repair Plan of SAIL {fy}",
            "subtitle": _PLANT_TITLE.get(plant, plant),
            "plant": plant,
            "fy": fy,
            "sections": sections,
        }
    finally:
        conn.close()
