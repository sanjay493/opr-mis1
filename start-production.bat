@echo off
rem Starts the SAIL MIS application in production mode, reachable across the LAN.
rem Backend : FastAPI (uvicorn) on http://0.0.0.0:8082 (proxied via the frontend)
rem Frontend: Next.js production server on http://0.0.0.0:80
rem
rem Browsers only talk to port 80; the Next.js server proxies /api/* to the
rem backend locally, so no firewall rule for port 8082 is needed.
rem Rebuild the frontend after any code change with:  cd frontend && npm run build

cd /d "%~dp0"

echo Stopping any process already using ports 8082 and 80...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8082" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":80 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

echo Starting FastAPI backend on port 8082...
start "MIS Backend (8082)" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe main.py"

echo Starting Next.js production server on port 80...
start "MIS Frontend (80)" cmd /k "cd /d %~dp0frontend && npm start -- -p 80"

echo.
echo Both servers launching in separate windows.
echo Open the app at:  http://10.135.5.15
echo Close those windows (or Ctrl+C in them) to stop the servers.
