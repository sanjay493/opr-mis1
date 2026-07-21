@echo off
rem Starts the SAIL MIS application in development mode (local only, auto-reload).
rem Backend : FastAPI (uvicorn --reload) on http://127.0.0.1:8082
rem Frontend: Next.js dev server on http://localhost:3000 (proxies /api/* to
rem           the backend via next.config.mjs rewrites)
rem
rem Both servers auto-reload on file changes - no rebuild/restart needed
rem while developing. For a LAN-reachable production build, use
rem start-production.bat instead.

cd /d "%~dp0"

echo Stopping any process already using ports 8082 and 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8082" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

echo Checking MySQL server...
tasklist /FI "IMAGENAME eq mysqld.exe" | findstr /I "mysqld.exe" >nul
if errorlevel 1 (
  echo MySQL not running - starting it...
  call "%~dp0backend\scripts\start_mysql.bat"
) else (
  echo MySQL already running.
)

echo Starting FastAPI backend on port 8082 (--reload)...
start "MIS Backend (8082, dev)" cmd /k "cd /d %~dp0backend && venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8082 --reload"

echo Starting Next.js dev server on port 3000...
start "MIS Frontend (3000, dev)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Both servers launching in separate windows, with auto-reload enabled.
echo Open the app at:  http://localhost:3000
echo Close those windows (or Ctrl+C in them) to stop the servers.
