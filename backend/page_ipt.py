"""
IPT (Inter-Plant Transfer) Status — page 26.

Data source: ipt_table
  (report_month, item, from_plant, to_plant, unit, sort_order, plan, actual)

Columns: Item | From | To | Unit | <Month> Plan/Actual | <Apr-Month> Plan/Actual
Cumulative = SUM across FY months Apr → report month.
Routes shown = union of routes having any record in the FY so far,
so a route transferred only in earlier months still appears.
"""
import sqlite3
import db

_MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _month_label(ym):
    return f"{_MON[int(ym[5:7])]}'{ym[2:4]}"

def _cum_label(months):
    if len(months) == 1:
        return _month_label(months[0])
    return f"{_MON[int(months[0][5:7])]}-{_month_label(months[-1])}"

def _fy_label(report_month):
    y, m = int(report_month[:4]), int(report_month[5:7])
    fy = y if m >= 4 else y - 1
    return f"{fy % 100}-{(fy + 1) % 100:02d}"

def _fmt(v):
    return "" if v is None else str(int(round(v)))


def generate_ipt(report_month: str) -> dict:
    ytd_months = db.get_ytd_months(report_month)

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    try:
        ph = ",".join("?" * len(ytd_months))

        # union of routes seen this FY, keeping entry order
        cur.execute(f"""
            SELECT item, from_plant, to_plant, unit, MIN(sort_order)
            FROM ipt_table
            WHERE report_month IN ({ph})
            GROUP BY item, from_plant, to_plant
            ORDER BY MIN(sort_order), item, from_plant, to_plant
        """, ytd_months)
        routes = cur.fetchall()

        # current-month values
        cur.execute("""
            SELECT item, from_plant, to_plant, plan, actual, plan_tonnage, actual_tonnage
            FROM ipt_table WHERE report_month=?
        """, (report_month,))
        cur_map = {(i, f, t): (p, a, pt, at) for i, f, t, p, a, pt, at in cur.fetchall()}

        # cumulative values (SUM skips NULLs; NULL when every value is NULL)
        cur.execute(f"""
            SELECT item, from_plant, to_plant,
                   SUM(plan), SUM(actual), SUM(plan_tonnage), SUM(actual_tonnage)
            FROM ipt_table
            WHERE report_month IN ({ph})
            GROUP BY item, from_plant, to_plant
        """, ytd_months)
        cum_map = {(i, f, t): (p, a, pt, at) for i, f, t, p, a, pt, at in cur.fetchall()}

        # group routes by item, preserving order of first appearance
        sections, by_item = [], {}
        for item, frm, to, unit, _ in routes:
            mp, ma, mpt, mat = cur_map.get((item, frm, to), (None, None, None, None))
            cp, ca, cpt, cat = cum_map.get((item, frm, to), (None, None, None, None))
            is_rake = (unit or "").strip().lower() == "rake"
            row = {
                "from": frm, "to": to, "unit": unit,
                "plan": _fmt(mp), "actual": _fmt(ma),
                "cum_plan": _fmt(cp), "cum_actual": _fmt(ca),
                # tonnes equivalent — only meaningful for Rake routes
                "plan_t":       _fmt(mpt) if is_rake else "",
                "actual_t":     _fmt(mat) if is_rake else "",
                "cum_plan_t":   _fmt(cpt) if is_rake else "",
                "cum_actual_t": _fmt(cat) if is_rake else "",
            }
            if item not in by_item:
                by_item[item] = {"item": item, "rows": []}
                sections.append(by_item[item])
            by_item[item]["rows"].append(row)

        return {
            "title": f"IPT Status for FY {_fy_label(report_month)}",
            "variant": "ipt_status",
            "month_label": _month_label(report_month),
            "cum_label": _cum_label(ytd_months),
            "sections": sections,
        }
    finally:
        conn.close()
