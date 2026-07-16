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


def generate_records() -> dict:
    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    try:
        result = {}
        groups = [('sail5', SAIL5), ('all8', ALL8)] + [(p, [p]) for p in ALL8]
        for group_name, plants in groups:
            ph  = _ph(plants)
            grp = {
                'cal_months':  {},
                'fy_quarters': {},
                'fy_halves':   {},
                'top5_fy':     {},
                'top5_cy':     {},
                'best_month':  {},
                'best_quarter':{},
            }

            for item in ITEMS:
                args = [item] + plants

                # ── Calendar month: top 2 per month number ───────────────────
                cur.execute(f"""
                    SELECT CAST(SUBSTR(report_month,6,2) AS INTEGER) AS mon_num,
                           report_month,
                           SUM(month_actual) AS total
                    FROM production_table
                    WHERE item_name=? AND plant_name IN ({ph})
                    GROUP BY report_month
                    ORDER BY mon_num, total DESC
                """, args)
                cal = {}
                for mon_num, rm, total in cur.fetchall():
                    if mon_num not in cal:
                        cal[mon_num] = []
                    if len(cal[mon_num]) < 2:
                        cal[mon_num].append({'period': _mon_label(rm),
                                             'month': rm,
                                             'total': round(total, 3)})
                grp['cal_months'][item] = cal

                # ── FY quarter: top 2 per quarter ────────────────────────────
                cur.execute(f"""
                    SELECT {_q_expr()} AS qnum,
                           {_fy_expr()} AS fy_start,
                           SUM(month_actual) AS total
                    FROM production_table
                    WHERE item_name=? AND plant_name IN ({ph})
                    GROUP BY qnum, fy_start
                    HAVING COUNT(DISTINCT report_month) = 3
                    ORDER BY qnum, total DESC
                """, args)
                fy_q = {}
                for qnum, fy_start, total in cur.fetchall():
                    ql = _Q_LABELS[qnum]
                    if ql not in fy_q:
                        fy_q[ql] = []
                    if len(fy_q[ql]) < 2:
                        fy_q[ql].append({'period': _fy_label(fy_start),
                                         'fy_start': fy_start,
                                         'total': round(total, 3)})
                grp['fy_quarters'][item] = fy_q

                # ── FY half: top 2 per half ───────────────────────────────────
                cur.execute(f"""
                    SELECT CASE WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER) BETWEEN 4 AND 9
                                THEN 1 ELSE 2 END AS hnum,
                           {_fy_expr()} AS fy_start,
                           SUM(month_actual) AS total
                    FROM production_table
                    WHERE item_name=? AND plant_name IN ({ph})
                    GROUP BY hnum, fy_start
                    HAVING COUNT(DISTINCT report_month) = 6
                    ORDER BY hnum, total DESC
                """, args)
                fy_h = {}
                for hnum, fy_start, total in cur.fetchall():
                    hl = _H_LABELS[hnum]
                    if hl not in fy_h:
                        fy_h[hl] = []
                    if len(fy_h[hl]) < 2:
                        fy_h[hl].append({'period': _fy_label(fy_start),
                                         'fy_start': fy_start,
                                         'total': round(total, 3)})
                grp['fy_halves'][item] = fy_h

                # ── Top 5 FY ─────────────────────────────────────────────────
                cur.execute(f"""
                    SELECT {_fy_expr()} AS fy_start, SUM(month_actual) AS total
                    FROM production_table
                    WHERE item_name=? AND plant_name IN ({ph})
                    GROUP BY fy_start
                    HAVING COUNT(DISTINCT report_month) = 12
                    ORDER BY total DESC LIMIT 5
                """, args)
                grp['top5_fy'][item] = [
                    {'period': _fy_label(r[0]), 'total': round(r[1], 3)}
                    for r in cur.fetchall()
                ]

                # ── Top 5 CY ─────────────────────────────────────────────────
                cur.execute(f"""
                    SELECT SUBSTR(report_month,1,4) AS yr, SUM(month_actual) AS total
                    FROM production_table
                    WHERE item_name=? AND plant_name IN ({ph})
                    GROUP BY yr
                    HAVING COUNT(DISTINCT report_month) = 12
                    ORDER BY total DESC LIMIT 5
                """, args)
                grp['top5_cy'][item] = [
                    {'period': r[0], 'total': round(r[1], 3)}
                    for r in cur.fetchall()
                ]

                # ── Best ever month ───────────────────────────────────────────
                cur.execute(f"""
                    SELECT report_month, SUM(month_actual) AS total
                    FROM production_table
                    WHERE item_name=? AND plant_name IN ({ph})
                    GROUP BY report_month
                    ORDER BY total DESC LIMIT 1
                """, args)
                row = cur.fetchone()
                grp['best_month'][item] = {
                    'period': _mon_label(row[0]) if row else None,
                    'month':  row[0] if row else None,
                    'total':  round(row[1], 3) if row else None,
                }

                # ── Best ever quarter ─────────────────────────────────────────
                cur.execute(f"""
                    SELECT {_q_expr()} AS qnum,
                           {_fy_expr()} AS fy_start,
                           SUM(month_actual) AS total
                    FROM production_table
                    WHERE item_name=? AND plant_name IN ({ph})
                    GROUP BY qnum, fy_start
                    HAVING COUNT(DISTINCT report_month) = 3
                    ORDER BY total DESC LIMIT 1
                """, args)
                row = cur.fetchone()
                grp['best_quarter'][item] = {
                    'period': (f"{_fy_label(row[1])} {_Q_LABELS[row[0]]}"
                               if row else None),
                    'qnum':     row[0] if row else None,
                    'fy_start': row[1] if row else None,
                    'total':  round(row[2], 3) if row else None,
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
