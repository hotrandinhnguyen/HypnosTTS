@echo off
title HypnosTTS Launcher

echo [HypnosTTS] Starting backend on :8000 ...
start "HypnosTTS Backend" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && uvicorn app.backend.main:app --reload --port 8000"

echo [HypnosTTS] Starting frontend on :5173 ...
start "HypnosTTS Frontend" cmd /k "cd /d %~dp0\app\frontend && npm run dev"

echo.
echo Both windows are open.
echo   Backend : http://localhost:8000
echo   Frontend: http://localhost:5173
echo.
pause
