@echo off
rem Starts the MIS MySQL server if not already running, then refreshes today's backup.
rem
rem Fully machine-portable: this file is git-tracked and shared across machines
rem with different local MySQL installs (different drive letters, versions,
rem ports). It reads MYSQL_BIN_DIR and MYSQL_PORT from backend\.env (untracked,
rem per-machine) instead of hardcoding a path. The MySQL "install root" (my.ini,
rem backup.cnf, data\, backup_error.log) is assumed to be the parent of
rem MYSQL_BIN_DIR's basedir - e.g. MYSQL_BIN_DIR=C:\mysql\mysql-9.7.1-winx64\bin
rem implies install root C:\mysql. This mirrors how every install here has been
rem laid out (D:\mysql\mysql-8.4.8-winx64\bin -> D:\mysql, etc).
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "ENV_FILE=%SCRIPT_DIR%..\.env"

if not exist "%ENV_FILE%" (
  echo ERROR: %ENV_FILE% not found - cannot determine MySQL install location.
  exit /b 1
)

set "MYSQL_BIN_DIR="
set "MYSQL_PORT="
for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
  if "%%A"=="MYSQL_BIN_DIR" set "MYSQL_BIN_DIR=%%B"
  if "%%A"=="MYSQL_PORT" set "MYSQL_PORT=%%B"
)

if not defined MYSQL_BIN_DIR (
  echo ERROR: MYSQL_BIN_DIR not set in %ENV_FILE%.
  exit /b 1
)
if not defined MYSQL_PORT set "MYSQL_PORT=3306"

set "MYSQL_BIN_DIR=%MYSQL_BIN_DIR:/=\%"
for %%I in ("%MYSQL_BIN_DIR%") do set "MYSQL_BASEDIR=%%~dpI"
set "BASEDIR_NOSLASH=%MYSQL_BASEDIR:~0,-1%"
for %%I in ("%BASEDIR_NOSLASH%") do set "MYSQL_ROOT=%%~dpI"
set "MYSQL_ROOT=%MYSQL_ROOT:~0,-1%"

netstat -ano | findstr "127.0.0.1:%MYSQL_PORT%" | findstr "LISTENING" >nul
if errorlevel 1 (
  del "%MYSQL_ROOT%\data\*.pid" 2>nul
  powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath '%MYSQL_BIN_DIR%\mysqld.exe' -ArgumentList '--defaults-file=%MYSQL_ROOT%\my.ini'"
  timeout /t 15 /nobreak >nul
)
call "%SCRIPT_DIR%backup_mysql.bat"
exit /b %ERRORLEVEL%
