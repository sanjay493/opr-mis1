

PS D:\opr-mis1> sqlite3 D:\opr-mis1\backend\mis_reports.db .tables;


PS D:\opr-mis1> sqlite3 D:\opr-mis1\backend\mis_reports.db ".schema production_table;"




sqlite3 D:\opr-mis1\backend\mis_reports.db "SELECT * FROM production_table WHERE report_month='2026-04' AND plant_name='ASP';"

