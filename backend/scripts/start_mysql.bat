@echo off
rem Starts the MIS MySQL server if not already running, then refreshes today's backup
rem Portable install lives at C:\mysql, on port 3307 (3306 is held by an
rem unrelated pre-existing MySQL90 Windows service on this machine).
netstat -ano | findstr "127.0.0.1:3307" | findstr "LISTENING" >nul
if errorlevel 1 (
  del "C:\mysql\data\*.pid" 2>nul
  powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath 'C:\mysql\mysql-9.7.1-winx64\bin\mysqld.exe' -ArgumentList '--defaults-file=C:\mysql\my.ini'"
  timeout /t 15 /nobreak >nul
)
call C:\mysql\backup_mysql.bat
exit /b %ERRORLEVEL%
