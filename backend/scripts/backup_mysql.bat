@echo off
rem Daily MySQL backup of mis_reports -> D:\opr-mis1\Report_format\db_backup
rem Safe to run repeatedly: same-day runs overwrite that day's file.
set BACKUP_DIR=D:\opr-mis1\Report_format\db_backup
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%i
"D:\mysql\mysql-8.4.8-winx64\bin\mysqldump.exe" --defaults-extra-file=D:\mysql\backup.cnf ^
  --single-transaction --no-tablespaces --routines --triggers mis_reports > "%BACKUP_DIR%\mis_reports_%TODAY%.sql"
rem keep the last 14 days
forfiles /p "%BACKUP_DIR%" /m mis_reports_*.sql /d -14 /c "cmd /c del @path" 2>nul
exit /b 0
