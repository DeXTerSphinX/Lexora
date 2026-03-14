@echo off
start "Lexora Backend" cmd /k "cd /d %~dp0 && python -m uvicorn api.app:app --reload --port 8000"
start "Lexora Frontend" cmd /k "cd /d %~dp0frontend && python -m http.server 3000"
timeout /t 2 /nobreak >nul
start http://localhost:3000/Login.html
