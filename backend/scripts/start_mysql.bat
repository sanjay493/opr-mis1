@echo off
rem Starts the MIS MySQL server if not already running, then refreshes today's backup
tasklist /FI "IMAGENAME eq mysqld.exe" | find /I "mysqld.exe" >nul
if errorlevel 1 (
  start "MySQL-MIS" /MIN "D:\mysql\mysql-8.4.8-winx64\bin\mysqld.exe" --defaults-file=D:\mysql\my.ini --console
  timeout /t 15 /nobreak >nul
)
call D:\mysql\backup_mysql.bat
exit /b 0
