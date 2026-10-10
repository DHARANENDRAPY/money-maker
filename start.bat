@echo off
title Trade Intelligence AI Launcher
cls
echo ===================================================
echo        TRADE INTELLIGENCE AI - STARTUP SYSTEM       
echo ===================================================
echo.

set "PROJECT_DIR=d:\money_maker"

echo [1/3] Launching FastAPI Backend on port 8000...
start "Trade AI - Backend API" cmd /k "title Trade AI Backend && cd /d "%PROJECT_DIR%\backend" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/3] Launching Vite Frontend on port 5173...
start "Trade AI - Frontend UI" cmd /k "title Trade AI Frontend && cd /d "%PROJECT_DIR%\frontend" && npm run dev"

echo [3/3] Waiting for servers to initialize...
timeout /t 5 /nobreak >nul

echo.
echo ===================================================
echo  SERVICES READY:
echo   - Web Terminal : http://localhost:5173
echo   - Backend Docs : http://127.0.0.1:8000/docs
echo   - Feed Status  : Live Angel One SmartAPI Feed
echo ===================================================
echo.
echo Opening Trade Intelligence AI in your browser...
start "" "http://localhost:5173"

echo.
echo [OK] Both servers are now running in background windows.
echo You can minimize this window.
timeout /t 5 >nul
exit
