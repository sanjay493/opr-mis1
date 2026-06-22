import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

con = sqlite3.connect('mis_reports.db')

group = input("Enter group_code (e.g. COKE_SINTER) or ENTER for all: ").strip() or None
month = input("Enter month YYYY-MM or ENTER for all: ").strip() or None

q = """
    SELECT m.group_code, m.section, m.row_label, m.unit,
           t.report_month, t.actual, t.cum_actual
    FROM techno_param_master m
    JOIN techno_monthly t ON t.param_id = m.param_id
    WHERE 1=1
"""
params = []
if group:
    q += " AND m.group_code = ?"
    params.append(group)
if month:
    q += " AND t.report_month = ?"
    params.append(month)
q += " ORDER BY m.group_code, m.sort_order, t.report_month"

rows = con.execute(q, params).fetchall()
print(f"\n{'Group':15s} {'Section':25s} {'Label':15s} {'Unit':15s} {'Month':8s} {'Actual':12s} {'Cum'}")
print("-" * 105)
cur_grp = cur_sec = None
for r in rows:
    if r[0] != cur_grp:
        print(f"\n=== {r[0]} ===")
        cur_grp, cur_sec = r[0], None
    if r[1] != cur_sec:
        print(f"  -- {r[1]} ({r[3]}) --")
        cur_sec = r[1]
    print(f"  {r[2]:15s}  {r[4]:8s}  {str(r[5] or ''):12s}  {str(r[6] or '')}")

print(f"\nTotal rows: {len(rows)}")
con.close()
