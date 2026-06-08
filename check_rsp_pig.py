import sqlite3
conn = sqlite3.connect(r'h:\opr-mis1\backend\mis_reports.db')
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print("Tables:", [r[0] for r in cur.fetchall()])

cur.execute("PRAGMA table_info(production_table)")
print("\n=== production_table columns ===")
for row in cur.fetchall():
    print(row)

cur.execute("""
    SELECT report_month, plant_name, item_name, month_actual
    FROM production_table
    WHERE plant_name = 'RSP' AND item_name = 'Pig Iron'
    ORDER BY
        CASE SUBSTR(report_month,1,3)
            WHEN 'Apr' THEN 1 WHEN 'May' THEN 2 WHEN 'Jun' THEN 3
            WHEN 'Jul' THEN 4 WHEN 'Aug' THEN 5 WHEN 'Sep' THEN 6
            WHEN 'Oct' THEN 7 WHEN 'Nov' THEN 8 WHEN 'Dec' THEN 9
            WHEN 'Jan' THEN 10 WHEN 'Feb' THEN 11 WHEN 'Mar' THEN 12
        END
""")
print("\n=== RSP Pig Iron current values ===")
for row in cur.fetchall():
    print(row)
conn.close()
