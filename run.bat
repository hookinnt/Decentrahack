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

echo [SYSTEM] Starting Web Dashboard...
python app.py

pause
