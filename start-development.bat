@echo off
rem Starts the SAIL MIS application in development mode (local only, auto-reload).
rem Backend : FastAPI (uvicorn --reload) on http://127.0.0.1:8082
rem Frontend: Next.js dev server on http://localhost:3000, launched through
rem           frontend/server.js (a custom server — forwards each visitor's
rem           real IP to the backend as x-forwarded-for, since Next's own
rem           rewrite proxy doesn't; see next.config.mjs for the /api/*
rem           rewrite itself)
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

rem Every venv tool runs as "venv\Scripts\python.exe -m <tool>", never through its
rem pip-generated launcher (uvicorn.exe, pip.exe, playwright.exe): those launchers
rem are unsigned and this machines Device Guard policy blocks them, while
rem python.exe itself is signed by the Python Software Foundation.
rem
rem Keeps this machine's venv/Chromium build in sync with whatever's
rem committed (backend\requirements.txt is pinned to exact versions) -
rem unpinned/drifted versions across machines is what used to cause the
rem same report to render with a different layout and take different
rem time to generate on different PCs. Cheap no-op when already in sync
rem (pip/playwright both skip anything already satisfied), so safe to run
rem on every startup rather than relying on remembering to do it by hand
rem after a `git pull`.
echo Syncing backend Python dependencies to the pinned versions...
call "%~dp0backend\venv\Scripts\python.exe" -m pip install -r "%~dp0backend\requirements.txt"
if errorlevel 1 (
  echo WARNING: pip install failed - continuing with whatever is already installed.
  echo   Run manually:  backend\venv\Scripts\python -m pip install -r backend\requirements.txt
)

echo Syncing Playwright's Chromium build to match...
call "%~dp0backend\venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
  echo WARNING: playwright install failed - continuing with whatever Chromium build is already cached.
  echo   Run manually:  backend\venv\Scripts\python -m playwright install chromium
)

echo Starting FastAPI backend on port 8082 (--reload)...
start "MIS Backend (8082, dev)" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8082 --reload"

echo Starting Next.js dev server on port 3000...
start "MIS Frontend (3000, dev)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Both servers launching in separate windows, with auto-reload enabled.
echo Open the app at:  http://localhost:3000
echo Close those windows (or Ctrl+C in them) to stop the servers.
