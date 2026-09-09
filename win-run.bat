@echo off
setlocal

cd /d "%~dp0"

if not exist .venv (
    echo Creating Python virtual environment (.venv)...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt
echo Starting VlahX Engine...
python run.py
pause
