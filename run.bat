@echo off
color 0b
echo ======================================================
echo    Starting Oracle Risk Manager (Solana) - FINAL
echo ======================================================

if not exist venv\Scripts\activate.bat (
    echo [ERROR] Virtual environment 'venv' not found.
    echo Please run 'python -m venv venv' and 'pip install -r requirements.txt'
    pause
    exit /b
)

call venv\Scripts\activate.bat
echo [SYSTEM] Virtual Environment Activated.

if not exist .env (
    echo [WARNING] .env file not found. Make sure GEMINI_API_KEY is set.
)

echo [SYSTEM] Starting Demo Dashboard on port 8080...
start /b python -m http.server 8080 -d demo

echo [SYSTEM] Opening projects in browser...
timeout /t 2 >nul
start http://127.0.0.1:5000
start http://127.0.0.1:8080

echo [SYSTEM] Starting Live Web Dashboard (app.py) on port 5000...
python app.py

pause
