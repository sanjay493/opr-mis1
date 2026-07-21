@echo off
setlocal enabledelayedexpansion
rem Daily MySQL backup of mis_reports -> C:\opr-mis1\Report_format\db_backup
rem Fails LOUDLY on any problem: non-zero exit code, entry in backup_error.log,
rem and a popup dialog. Never overwrites a good backup with a bad one - the
rem dump is written to a temp file and only moved into place after it passes
rem sanity checks (mysqldump exit code, minimum size, completion footer).
rem Safe to run repeatedly: same-day runs overwrite that day's file.

set BACKUP_DIR=C:\opr-mis1\Report_format\db_backup
set LOG_FILE=C:\mysql\backup_error.log
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%i
set FINAL_FILE=%BACKUP_DIR%\mis_reports_%TODAY%.sql
set TMP_FILE=%BACKUP_DIR%\.mis_reports_%TODAY%.sql.tmp

rem Refuse to run if the server isn't up - avoids dumping against a dead socket
tasklist /FI "IMAGENAME eq mysqld.exe" | findstr /I "mysqld.exe" >nul
if errorlevel 1 (
  call :fail "mysqld.exe is not running - backup skipped"
  exit /b 1
)

"C:\mysql\mysql-9.7.1-winx64\bin\mysqldump.exe" --defaults-extra-file=C:\mysql\backup.cnf ^
  --single-transaction --no-tablespaces --routines --triggers mis_reports > "%TMP_FILE%" 2>>"%LOG_FILE%"
set DUMP_RC=%ERRORLEVEL%

if not "%DUMP_RC%"=="0" (
  call :fail "mysqldump exited with code %DUMP_RC% - see %LOG_FILE%"
  del "%TMP_FILE%" 2>nul
  exit /b 1
)

for %%F in ("%TMP_FILE%") do set SIZE=%%~zF
if "%SIZE%"=="" set SIZE=0
if %SIZE% LSS 1024 (
  call :fail "dump file suspiciously small (%SIZE% bytes)"
  del "%TMP_FILE%" 2>nul
  exit /b 1
)

findstr /C:"-- Dump completed on" "%TMP_FILE%" >nul
if errorlevel 1 (
  call :fail "dump file missing completion footer - likely truncated"
  del "%TMP_FILE%" 2>nul
  exit /b 1
)

move /y "%TMP_FILE%" "%FINAL_FILE%" >nul

rem keep the last 14 days (only prune once we know today's backup is good)
forfiles /p "%BACKUP_DIR%" /m mis_reports_*.sql /d -14 /c "cmd /c del @path" 2>nul

exit /b 0

:fail
echo %date% %time% - BACKUP FAILED - %~1 >> "%LOG_FILE%"
start "" /min powershell -NoProfile -WindowStyle Hidden -Command ^
  "Add-Type -AssemblyName System.Windows.Forms;" ^
  "$icon = [System.Windows.Forms.NotifyIcon]::new();" ^
  "$icon.Icon = [System.Drawing.SystemIcons]::Error;" ^
  "$icon.Visible = $true;" ^
  "$icon.ShowBalloonTip(20000, 'MIS Backup Failed', '%~1', [System.Windows.Forms.ToolTipIcon]::Error);" ^
  "Start-Sleep -Seconds 20;" ^
  "$icon.Dispose()"
exit /b 0
