@echo off
cd /d "%~dp0"
set BACKEND_DIR=%~dp0
python -m uvicorn server:socket_app --host 0.0.0.0 --port 8001
pause
