@echo off
setlocal enabledelayedexpansion
rem Daily MySQL backup of mis_reports -> <repo root>\Report_format\db_backup
rem
rem Fully machine-portable: this file is git-tracked and shared across machines
rem with different repo locations and MySQL installs. The repo root and backup
rem dir are derived from this script's own location (%~dp0..\..), and the
rem MySQL bin dir / install root are read from backend\.env (untracked,
rem per-machine) the same way start_mysql.bat does. Nothing here is hardcoded
rem to a specific drive letter.
rem
rem Fails LOUDLY on any problem: non-zero exit code, entry in backup_error.log,
rem and a popup dialog. Never overwrites a good backup with a bad one - the
rem dump is written to a temp file and only moved into place after it passes
rem sanity checks (mysqldump exit code, minimum size, completion footer).
rem Safe to run repeatedly: same-day runs overwrite that day's file.

set "SCRIPT_DIR=%~dp0"
set "ENV_FILE=%SCRIPT_DIR%..\.env"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"
set "BACKUP_DIR=%REPO_ROOT%\Report_format\db_backup"

if not exist "%ENV_FILE%" (
  echo ERROR: %ENV_FILE% not found - cannot determine MySQL install location.
  exit /b 1
)

set "MYSQL_BIN_DIR="
for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
  if "%%A"=="MYSQL_BIN_DIR" set "MYSQL_BIN_DIR=%%B"
)
if not defined MYSQL_BIN_DIR (
  echo ERROR: MYSQL_BIN_DIR not set in %ENV_FILE%.
  exit /b 1
)

set "MYSQL_BIN_DIR=%MYSQL_BIN_DIR:/=\%"
for %%I in ("%MYSQL_BIN_DIR%") do set "MYSQL_BASEDIR=%%~dpI"
set "BASEDIR_NOSLASH=%MYSQL_BASEDIR:~0,-1%"
for %%I in ("%BASEDIR_NOSLASH%") do set "MYSQL_ROOT=%%~dpI"
set "MYSQL_ROOT=%MYSQL_ROOT:~0,-1%"

set LOG_FILE=%MYSQL_ROOT%\backup_error.log
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

"%MYSQL_BIN_DIR%\mysqldump.exe" --defaults-extra-file="%MYSQL_ROOT%\backup.cnf" ^
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
if errorlevel 1 (
  call :fail "move into place failed (errorlevel %ERRORLEVEL%) - good dump left at %TMP_FILE%, NOT deleted"
  exit /b 1
)
if not exist "%FINAL_FILE%" (
  call :fail "move reported success but %FINAL_FILE% is missing - good dump left at %TMP_FILE%, NOT deleted"
  exit /b 1
)

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
