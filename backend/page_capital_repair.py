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

        # Sections are runs of CONSECUTIVE rows sharing a shop, in the
        # user's saved order (the data-entry page can reorder rows by drag
        # and drop) - a shop that reappears later starts a new section
        # rather than pulling its rows back up out of order.
        sections = []
        for rid, shop, equipment, activity, schedule_days, period, actual in rows:
            row = {
                "id": rid,
                "equipment": equipment or "",
                "activity": activity or "",
                "schedule_days": schedule_days or "",
                "period": period or "",
                "actual": actual or "",
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
