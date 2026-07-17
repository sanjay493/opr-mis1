"""
Production record statistics — best/2nd-best by calendar month, FY quarter,
FY half, and top-5 FY / calendar years for the major production items.
Computed for the SAIL group aggregates ('sail5', 'all8') and for every
individual plant/unit (keyed by plant code, e.g. 'BSP', 'ASP').
Used by the /api/production-records endpoint.
"""
import sqlite3
import db

ITEMS = ['Total Sinter', 'Hot Metal', 'Total Crude Steel',
         'Saleable Steel', 'Pig Iron', 'Finished Steel']
SAIL5 = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']
ALL8  = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL']

_MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

_Q_LABELS = {1: 'Q1 (Apr-Jun)', 2: 'Q2 (Jul-Sep)',
             3: 'Q3 (Oct-Dec)',  4: 'Q4 (Jan-Mar)'}
_H_LABELS = {1: 'H1 (Apr-Sep)', 2: 'H2 (Oct-Mar)'}


def _ph(lst):
    return ','.join('?' * len(lst))


def _mon_label(ym):
    m = int(ym[5:7])
    return f"{_MON[m]}'{ym[2:4]}"


def _fy_label(fy_start):
    return f"{fy_start}-{str(fy_start + 1)[2:]}"


def _fy_expr():
    return ("CASE WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER)>=4 "
            "THEN CAST(SUBSTR(report_month,1,4) AS INTEGER) "
            "ELSE CAST(SUBSTR(report_month,1,4) AS INTEGER)-1 END")


def _q_expr():
    return ("CASE "
            "WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER) IN (4,5,6)    THEN 1 "
            "WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER) IN (7,8,9)    THEN 2 "
            "WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER) IN (10,11,12) THEN 3 "
            "ELSE 4 END")


def _item_sort_key():
    """Process-order sort for item names; alphabetical fallback if main's
    helpers aren't importable (lazy import avoids a circular import — main
    imports this module at startup, we only need main at request time)."""
    try:
        from main import normalize_item_name, production_item_sort_key
        return lambda n: production_item_sort_key(normalize_item_name(n))
    except Exception:
        return lambda n: n


def generate_records() -> dict:
    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    sort_key = _item_sort_key()
    try:
        result = {}
        groups = [('sail5', SAIL5), ('all8', ALL8)] + [(p, [p]) for p in ALL8]
        for group_name, plants in groups:
            ph = _ph(plants)
            # Group scopes keep the summary items (unit-level items don't sum
            # meaningfully across plants); single-plant scopes cover every
            # unit/item that plant has ever reported (BF#1, SMS-2, URM …).
            if len(plants) == 1:
                cur.execute(
                    "SELECT DISTINCT item_name FROM production_table WHERE plant_name=?",
                    plants)
                items = sorted((r[0] for r in cur.fetchall()), key=sort_key)
                where = f"plant_name IN ({ph})"
                args  = list(plants)
            else:
                items = ITEMS
                where = f"item_name IN ({_ph(ITEMS)}) AND plant_name IN ({ph})"
                args  = ITEMS + plants

            grp = {
                'items':       items,
                'cal_months':  {i: {} for i in items},
                'fy_quarters': {i: {} for i in items},
                'fy_halves':   {i: {} for i in items},
                'top5_fy':     {i: [] for i in items},
                'top5_cy':     {i: [] for i in items},
                'best_month':  {},
                'best_quarter':{},
            }

            # ── Calendar month: top 2 per (item, month number). The global
            #    best/2nd-best month are always contained in this set. ───────
            cur.execute(f"""
                SELECT item_name,
                       CAST(SUBSTR(report_month,6,2) AS INTEGER) AS mon_num,
                       report_month,
                       SUM(month_actual) AS total
                FROM production_table
                WHERE {where}
                GROUP BY item_name, report_month
                ORDER BY item_name, mon_num, total DESC
            """, args)
            for item, mon_num, rm, total in cur.fetchall():
                cal = grp['cal_months'].get(item)
                if cal is None or total is None:
                    continue
                rows = cal.setdefault(mon_num, [])
                if len(rows) < 2:
                    rows.append({'period': _mon_label(rm), 'month': rm,
                                 'total': round(total, 3)})

            # ── FY quarter: top 2 per (item, quarter) ────────────────────────
            cur.execute(f"""
                SELECT item_name,
                       {_q_expr()} AS qnum,
                       {_fy_expr()} AS fy_start,
                       SUM(month_actual) AS total
                FROM production_table
                WHERE {where}
                GROUP BY item_name, qnum, fy_start
                HAVING COUNT(DISTINCT report_month) = 3
                ORDER BY item_name, qnum, total DESC
            """, args)
            for item, qnum, fy_start, total in cur.fetchall():
                fy_q = grp['fy_quarters'].get(item)
                if fy_q is None or total is None:
                    continue
                rows = fy_q.setdefault(_Q_LABELS[qnum], [])
                if len(rows) < 2:
                    rows.append({'period': _fy_label(fy_start),
                                 'fy_start': fy_start,
                                 'total': round(total, 3)})

            # ── FY half: top 2 per (item, half) ──────────────────────────────
            cur.execute(f"""
                SELECT item_name,
                       CASE WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER) BETWEEN 4 AND 9
                            THEN 1 ELSE 2 END AS hnum,
                       {_fy_expr()} AS fy_start,
                       SUM(month_actual) AS total
                FROM production_table
                WHERE {where}
                GROUP BY item_name, hnum, fy_start
                HAVING COUNT(DISTINCT report_month) = 6
                ORDER BY item_name, hnum, total DESC
            """, args)
            for item, hnum, fy_start, total in cur.fetchall():
                fy_h = grp['fy_halves'].get(item)
                if fy_h is None or total is None:
                    continue
                rows = fy_h.setdefault(_H_LABELS[hnum], [])
                if len(rows) < 2:
                    rows.append({'period': _fy_label(fy_start),
                                 'fy_start': fy_start,
                                 'total': round(total, 3)})

            # ── Top 5 FY per item ────────────────────────────────────────────
            cur.execute(f"""
                SELECT item_name, {_fy_expr()} AS fy_start, SUM(month_actual) AS total
                FROM production_table
                WHERE {where}
                GROUP BY item_name, fy_start
                HAVING COUNT(DISTINCT report_month) = 12
                ORDER BY item_name, total DESC
            """, args)
            for item, fy_start, total in cur.fetchall():
                rows = grp['top5_fy'].get(item)
                if rows is None or total is None:
                    continue
                if len(rows) < 5:
                    rows.append({'period': _fy_label(fy_start),
                                 'total': round(total, 3)})

            # ── Top 5 CY per item ────────────────────────────────────────────
            cur.execute(f"""
                SELECT item_name, SUBSTR(report_month,1,4) AS yr, SUM(month_actual) AS total
                FROM production_table
                WHERE {where}
                GROUP BY item_name, yr
                HAVING COUNT(DISTINCT report_month) = 12
                ORDER BY item_name, total DESC
            """, args)
            for item, yr, total in cur.fetchall():
                rows = grp['top5_cy'].get(item)
                if rows is None or total is None:
                    continue
                if len(rows) < 5:
                    rows.append({'period': yr, 'total': round(total, 3)})

            # ── Best ever month / quarter, derived from the top-2 sets ───────
            for item in items:
                flat = [r for rows in grp['cal_months'][item].values() for r in rows]
                best = max(flat, key=lambda r: r['total'], default=None)
                grp['best_month'][item] = {
                    'period': best['period'] if best else None,
                    'month':  best['month'] if best else None,
                    'total':  best['total'] if best else None,
                }

                qflat = [(label, r)
                         for label, rows in grp['fy_quarters'][item].items()
                         for r in rows]
                if qflat:
                    label, r = max(qflat, key=lambda t: t[1]['total'])
                    qnum = int(label[1])
                    grp['best_quarter'][item] = {
                        'period':   f"{r['period']} {label}",
                        'qnum':     qnum,
                        'fy_start': r['fy_start'],
                        'total':    r['total'],
                    }
                else:
                    grp['best_quarter'][item] = {
                        'period': None, 'qnum': None,
                        'fy_start': None, 'total': None,
                    }

            result[group_name] = grp

        # Latest month with production data — lets the UI flag records that
        # were set just now (period ending at/near this month).
        cur.execute("""
            SELECT MAX(report_month) FROM production_table
            WHERE report_month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
        """)
        result['latest_month'] = cur.fetchone()[0]
        return result
    finally:
        conn.close()
