import sqlite3

conn = sqlite3.connect("backend/mis_reports.db")
cursor = conn.cursor()

cursor.execute("SELECT DISTINCT report_month FROM production_table ORDER BY report_month")
rows = [r[0] for r in cursor.fetchall()]
print("All distinct report_month values:")
for r in rows:
    print(" ", r)

cursor.execute("SELECT COUNT(*) FROM production_table")
print("\nTotal rows:", cursor.fetchone()[0])

# Also show sample full rows
cursor.execute("SELECT * FROM production_table LIMIT 5")
print("\nSample rows:")
for r in cursor.fetchall():
    print(" ", r)

conn.close()
